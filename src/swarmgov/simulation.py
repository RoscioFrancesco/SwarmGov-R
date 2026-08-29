"""Simulation orchestration for implemented milestones."""

from __future__ import annotations

import json
import platform
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from swarmgov.agents.ucb import UCB1Agent
from swarmgov.aggregators import (
    AggregationDiagnostics,
    Aggregator,
    aggregate_count_weighted_mean,
    build_aggregator,
)
from swarmgov.attacks import (
    AttackContext,
    AttackDiagnostic,
    AttackStrategy,
    apply_message_attacks,
    build_attack_strategy,
    select_byzantine_nodes,
)
from swarmgov.communication import (
    build_round_messages,
    inbound_messages_by_receiver,
    should_communicate,
)
from swarmgov.config import StudyConfig
from swarmgov.environment import BernoulliBanditEnvironment
from swarmgov.graphs import (
    GeneratedGraph,
    TopologyChangeEvent,
    generate_static_graph,
    rewire_graph_once,
)
from swarmgov.messages import Message
from swarmgov.metrics.communication import summarize_communication
from swarmgov.metrics.recovery import summarize_recovery_time
from swarmgov.metrics.regret import summarize_population_regret, summarize_regret
from swarmgov.seeds import ComponentSeed, derive_run_component_seeds


class SimulationError(ValueError):
    """Raised when a configured simulation is unsupported or invalid."""


MULTI_AGENT_ALGORITHMS = {
    "independent_ucb1",
    "centralized_pooled_shared_action_ucb1",
    "one_hop_weighted_pooling_ucb1",
}


@dataclass(frozen=True)
class SingleAgentRunResult:
    run_id: str
    algorithm: str
    seed: int
    horizon: int
    actions: tuple[int, ...]
    rewards: tuple[float, ...]
    final_regret: float
    regret_curve: tuple[float, ...]
    per_round_regret: tuple[float, ...]
    best_arm: int
    preferred_arm: int
    best_arm_identified: bool
    agent_state: dict[str, object]
    output_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MultiAgentRunResult:
    run_id: str
    algorithm: str
    seed: int
    horizon: int
    num_agents: int
    graph: dict[str, Any]
    topology_change: dict[str, object]
    honest_nodes: tuple[int, ...]
    byzantine_nodes: tuple[int, ...]
    attack: dict[str, object]
    aggregation: dict[str, object]
    actions_by_round: tuple[tuple[int, ...], ...]
    rewards_by_round: tuple[tuple[float, ...], ...]
    total_population_regret: float
    mean_per_agent_regret: float
    per_agent_final_regret: tuple[float, ...]
    total_regret_curve: tuple[float, ...]
    mean_regret_curve: tuple[float, ...]
    recovery: dict[str, object]
    best_arm: int
    preferred_arms: tuple[int, ...]
    best_arm_identification_rate: float
    communication: dict[str, object]
    agent_states: tuple[dict[str, object], ...]
    attack_diagnostics: tuple[dict[str, object], ...]
    aggregation_summary: dict[str, object]
    aggregation_diagnostics: tuple[dict[str, object], ...]
    output_path: str | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def run_configured_experiment(
    config: StudyConfig,
    *,
    output_dir: str | Path | None = None,
    write: bool = True,
) -> SingleAgentRunResult | MultiAgentRunResult:
    if config.population.agents == 1:
        return run_single_agent(config, output_dir=output_dir, write=write)
    return run_multi_agent(config, output_dir=output_dir, write=write)


def run_single_agent(
    config: StudyConfig,
    *,
    output_dir: str | Path | None = None,
    write: bool = True,
) -> SingleAgentRunResult:
    """Run one independent UCB1 agent against a Bernoulli bandit."""

    _validate_single_agent_config(config)
    run_seed = config.experiment.seeds[0]
    component_seeds = derive_run_component_seeds(
        config.seeds.master,
        run_seed,
        config.seeds.streams,
    )
    if "environment" not in component_seeds or "agents" not in component_seeds:
        raise SimulationError("seed streams must include 'environment' and 'agents'")

    environment = BernoulliBanditEnvironment.from_means(config.bandit.arm_means)
    env_rng = component_seeds["environment"].rng()
    agent_rng = component_seeds["agents"].rng()
    agent = UCB1Agent(
        num_arms=config.bandit.arms,
        exploration_c=_exploration_c(config),
        rng=agent_rng,
    )

    started = perf_counter()
    actions: list[int] = []
    rewards: list[float] = []
    for round_index in range(1, config.experiment.horizon + 1):
        arm = agent.select_arm(round_index)
        reward = environment.sample(arm, env_rng)
        agent.observe(arm, reward)
        actions.append(arm)
        rewards.append(reward)

    regret = summarize_regret(config.bandit.arm_means, actions)
    preferred_arm = agent.preferred_arm()
    run_id = f"{config.name}_seed-{run_seed}"
    result = SingleAgentRunResult(
        run_id=run_id,
        algorithm=config.algorithm.name,
        seed=run_seed,
        horizon=config.experiment.horizon,
        actions=tuple(actions),
        rewards=tuple(rewards),
        final_regret=regret.final_regret,
        regret_curve=regret.regret_curve,
        per_round_regret=regret.per_round_regret,
        best_arm=environment.optimal_arm,
        preferred_arm=preferred_arm,
        best_arm_identified=preferred_arm == environment.optimal_arm,
        agent_state=agent.snapshot(),
    )

    if not write:
        return result

    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else Path(config.experiment.output_dir)
    )
    output_path = target_dir / f"{run_id}.json"
    _write_single_agent_result(
        result=result,
        config=config,
        component_seeds=component_seeds,
        output_path=output_path,
        runtime_seconds=perf_counter() - started,
    )
    return SingleAgentRunResult(
        **{**result.to_record(), "output_path": str(output_path)}
    )


def _validate_single_agent_config(config: StudyConfig) -> None:
    if config.population.agents != 1:
        raise SimulationError("Milestone 2 run supports exactly one agent")
    if config.population.byzantine_fraction != 0.0:
        raise SimulationError("Milestone 2 run does not support Byzantine agents")
    if config.communication.enabled:
        raise SimulationError("Milestone 2 run does not support communication")
    if config.topology_change.enabled:
        raise SimulationError("Milestone 2 run does not support topology changes")
    if config.algorithm.name != "independent_ucb1":
        raise SimulationError("Milestone 2 run supports only independent_ucb1")
    if len(config.experiment.seeds) != 1:
        raise SimulationError("Milestone 2 run expects exactly one experiment seed")


def run_multi_agent(
    config: StudyConfig,
    *,
    output_dir: str | Path | None = None,
    write: bool = True,
) -> MultiAgentRunResult:
    """Run a static-graph multi-agent baseline or message-level attack."""

    _validate_multi_agent_config(config)
    run_seed = config.experiment.seeds[0]
    component_seeds = derive_run_component_seeds(
        config.seeds.master,
        run_seed,
        config.seeds.streams,
    )
    required_streams = ["environment", "graph", "agents"]
    if config.population.byzantine_fraction > 0.0:
        required_streams.append("attack")
    _require_streams(component_seeds, tuple(required_streams))

    started = perf_counter()
    environment = BernoulliBanditEnvironment.from_means(config.bandit.arm_means)
    graph_rng = component_seeds["graph"].rng()
    graph = generate_static_graph(
        family=config.graph.family,
        num_nodes=config.population.agents,
        parameters=config.graph.parameters,
        rng=graph_rng,
    )
    byzantine_nodes = _select_byzantine_nodes(
        config=config,
        graph=graph,
        component_seeds=component_seeds,
    )
    honest_nodes = _honest_nodes(config.population.agents, byzantine_nodes)
    attack_strategy = _build_attack_strategy(config)
    aggregator = _build_aggregator(config)
    reward_table = _precompute_rewards(
        environment=environment,
        horizon=config.experiment.horizon,
        num_agents=config.population.agents,
        rng=component_seeds["environment"].rng(),
    )

    if config.algorithm.name == "centralized_pooled_shared_action_ucb1":
        result = _run_centralized_pooled_shared_action(
            config=config,
            graph=graph,
            reward_table=reward_table,
            topology_event=None,
            component_seeds=component_seeds,
            honest_nodes=honest_nodes,
            byzantine_nodes=byzantine_nodes,
        )
    else:
        result = _run_decentralized_agents(
            config=config,
            graph=graph,
            graph_rng=graph_rng,
            reward_table=reward_table,
            component_seeds=component_seeds,
            honest_nodes=honest_nodes,
            byzantine_nodes=byzantine_nodes,
            aggregator=aggregator,
            attack_strategy=attack_strategy,
        )

    if not write:
        return result

    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else Path(config.experiment.output_dir)
    )
    output_path = target_dir / f"{result.run_id}.json"
    _write_result_record(
        result=result,
        config=config,
        component_seeds=component_seeds,
        output_path=output_path,
        runtime_seconds=perf_counter() - started,
    )
    return MultiAgentRunResult(
        **{**result.to_record(), "output_path": str(output_path)}
    )


def _run_decentralized_agents(
    *,
    config: StudyConfig,
    graph: GeneratedGraph,
    graph_rng: np.random.Generator,
    reward_table: np.ndarray,
    component_seeds: Mapping[str, ComponentSeed],
    honest_nodes: tuple[int, ...],
    byzantine_nodes: tuple[int, ...],
    aggregator: Aggregator,
    attack_strategy: AttackStrategy,
) -> MultiAgentRunResult:
    agent_rngs = _agent_rngs(component_seeds, config.population.agents)
    agents = tuple(
        UCB1Agent(
            num_arms=config.bandit.arms,
            exploration_c=_exploration_c(config),
            rng=agent_rngs[agent_index],
        )
        for agent_index in range(config.population.agents)
    )
    decision_counts = [
        np.zeros(config.bandit.arms, dtype=np.int64)
        for _ in range(config.population.agents)
    ]
    decision_sums = [
        np.zeros(config.bandit.arms, dtype=float)
        for _ in range(config.population.agents)
    ]
    actions_by_round: list[tuple[int, ...]] = []
    rewards_by_round: list[tuple[float, ...]] = []
    all_messages: list[Message] = []
    attack_diagnostics: list[AttackDiagnostic] = []
    aggregation_summary = _empty_aggregation_summary()
    aggregation_diagnostics: list[dict[str, object]] = []
    active_graph = graph
    topology_event: TopologyChangeEvent | None = None

    for round_index in range(1, config.experiment.horizon + 1):
        actions = _select_decentralized_actions(
            config=config,
            agents=agents,
            round_index=round_index,
            decision_counts=decision_counts,
            decision_sums=decision_sums,
        )
        rewards = tuple(
            float(reward_table[round_index - 1, agent_index, arm])
            for agent_index, arm in enumerate(actions)
        )
        for agent_index, (agent, arm, reward) in enumerate(
            zip(agents, actions, rewards, strict=True)
        ):
            agent.observe(arm, reward)
            decision_counts[agent_index] = agent.counts.copy()
            decision_sums[agent_index] = agent.reward_sums.copy()

        if _should_apply_topology_change(
            config=config,
            round_index=round_index,
            topology_event=topology_event,
        ):
            active_graph, topology_event = _apply_topology_change(
                config=config,
                graph=active_graph,
                graph_rng=graph_rng,
            )

        if (
            config.algorithm.name == "one_hop_weighted_pooling_ucb1"
            and should_communicate(
                round_index=round_index,
                enabled=config.communication.enabled,
                interval=config.communication.interval,
            )
        ):
            local_counts = [agent.counts.copy() for agent in agents]
            local_sums = [agent.reward_sums.copy() for agent in agents]
            messages = build_round_messages(
                graph=active_graph,
                round_index=round_index,
                local_counts=local_counts,
                local_reward_sums=local_sums,
                protocol=config.algorithm.name,
            )
            attack_application = apply_message_attacks(
                messages=messages,
                byzantine_nodes=byzantine_nodes,
                strategy=attack_strategy,
                context=AttackContext(
                    round_index=round_index,
                    num_arms=config.bandit.arms,
                ),
                diagnostics_enabled=config.attack.diagnostics,
            )
            messages = attack_application.messages
            attack_diagnostics.extend(attack_application.diagnostics)
            all_messages.extend(messages)
            inbound = inbound_messages_by_receiver(
                messages,
                num_nodes=config.population.agents,
            )
            pooled_counts, pooled_sums, round_diagnostics = _apply_one_hop_aggregation(
                aggregator=aggregator,
                local_counts=local_counts,
                local_reward_sums=local_sums,
                inbound_messages=inbound,
                round_index=round_index,
            )
            _update_aggregation_summary(aggregation_summary, round_diagnostics)
            if config.aggregation.diagnostics:
                aggregation_diagnostics.extend(
                    _aggregation_diagnostic_records(
                        round_index=round_index,
                        diagnostics_by_receiver=round_diagnostics,
                    )
                )
            decision_counts = pooled_counts
            decision_sums = pooled_sums

        actions_by_round.append(actions)
        rewards_by_round.append(rewards)

    preferred_arms = tuple(
        agent.preferred_arm_from_statistics(
            decision_counts[agent_index],
            decision_sums[agent_index],
        )
        for agent_index, agent in enumerate(agents)
    )
    return _build_multi_result(
        config=config,
        graph=graph,
        topology_event=topology_event,
        honest_nodes=honest_nodes,
        byzantine_nodes=byzantine_nodes,
        actions_by_round=actions_by_round,
        rewards_by_round=rewards_by_round,
        preferred_arms=preferred_arms,
        agent_states=tuple(agent.snapshot() for agent in agents),
        messages=tuple(all_messages),
        attack_diagnostics=tuple(attack_diagnostics),
        aggregation_summary=aggregation_summary,
        aggregation_diagnostics=tuple(aggregation_diagnostics),
    )


def _run_centralized_pooled_shared_action(
    *,
    config: StudyConfig,
    graph: GeneratedGraph,
    reward_table: np.ndarray,
    topology_event: TopologyChangeEvent | None,
    component_seeds: Mapping[str, ComponentSeed],
    honest_nodes: tuple[int, ...],
    byzantine_nodes: tuple[int, ...],
) -> MultiAgentRunResult:
    central_agent = UCB1Agent(
        num_arms=config.bandit.arms,
        exploration_c=_exploration_c(config),
        rng=_agent_rngs(component_seeds, 1)[0],
    )
    actions_by_round: list[tuple[int, ...]] = []
    rewards_by_round: list[tuple[float, ...]] = []
    for round_index in range(1, config.experiment.horizon + 1):
        arm = central_agent.select_arm(central_agent.total_observations + 1)
        actions = tuple(arm for _ in range(config.population.agents))
        rewards = tuple(
            float(reward_table[round_index - 1, agent_index, arm])
            for agent_index in range(config.population.agents)
        )
        for reward in rewards:
            central_agent.observe(arm, reward)
        actions_by_round.append(actions)
        rewards_by_round.append(rewards)

    preferred_arm = central_agent.preferred_arm()
    return _build_multi_result(
        config=config,
        graph=graph,
        topology_event=topology_event,
        honest_nodes=honest_nodes,
        byzantine_nodes=byzantine_nodes,
        actions_by_round=actions_by_round,
        rewards_by_round=rewards_by_round,
        preferred_arms=tuple(preferred_arm for _ in range(config.population.agents)),
        agent_states=(central_agent.snapshot(),),
        messages=(),
        attack_diagnostics=(),
        aggregation_summary=_empty_aggregation_summary(),
        aggregation_diagnostics=(),
    )


def _select_decentralized_actions(
    *,
    config: StudyConfig,
    agents: tuple[UCB1Agent, ...],
    round_index: int,
    decision_counts: list[np.ndarray],
    decision_sums: list[np.ndarray],
) -> tuple[int, ...]:
    if config.algorithm.name == "independent_ucb1":
        return tuple(agent.select_arm(round_index) for agent in agents)
    return tuple(
        agent.select_arm_from_statistics(
            round_index,
            decision_counts[agent_index],
            decision_sums[agent_index],
        )
        for agent_index, agent in enumerate(agents)
    )


def _apply_one_hop_weighted_pooling(
    *,
    local_counts: list[np.ndarray],
    local_reward_sums: list[np.ndarray],
    inbound_messages: dict[int, tuple[Message, ...]],
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Pool fresh local cumulative snapshots with one-hop neighbor snapshots.

    The function is intentionally stateless: it never receives or adds the
    previous round's pooled decision statistics. This prevents cumulative
    neighbor messages from being double-counted across rounds.
    """

    pooled_counts, pooled_sums, _ = _apply_one_hop_aggregation(
        aggregator=build_aggregator(method="mean"),
        local_counts=local_counts,
        local_reward_sums=local_reward_sums,
        inbound_messages=inbound_messages,
        round_index=None,
    )
    return pooled_counts, pooled_sums


def _apply_one_hop_aggregation(
    *,
    aggregator: Aggregator,
    local_counts: list[np.ndarray],
    local_reward_sums: list[np.ndarray],
    inbound_messages: dict[int, tuple[Message, ...]],
    round_index: int | None,
) -> tuple[list[np.ndarray], list[np.ndarray], dict[int, AggregationDiagnostics]]:
    """Apply a configured stateless one-hop aggregator to each receiver."""

    pooled_counts: list[np.ndarray] = []
    pooled_sums: list[np.ndarray] = []
    diagnostics_by_receiver: dict[int, AggregationDiagnostics] = {}
    for agent_index, (counts, reward_sums) in enumerate(
        zip(local_counts, local_reward_sums, strict=True)
    ):
        if round_index is None:
            aggregate = aggregate_count_weighted_mean(
                local_counts=counts,
                local_reward_sums=reward_sums,
                messages=inbound_messages[agent_index],
            )
            pooled_counts.append(aggregate.counts_array())
            pooled_sums.append(aggregate.reward_sums_array())
            continue
        result = aggregator.aggregate(
            local_counts=counts,
            local_reward_sums=reward_sums,
            messages=inbound_messages[agent_index],
            round_index=round_index,
        )
        pooled_counts.append(result.statistics.counts_array())
        pooled_sums.append(result.statistics.reward_sums_array())
        diagnostics_by_receiver[agent_index] = result.diagnostics
    return pooled_counts, pooled_sums, diagnostics_by_receiver


def _build_multi_result(
    *,
    config: StudyConfig,
    graph: GeneratedGraph,
    topology_event: TopologyChangeEvent | None,
    honest_nodes: tuple[int, ...],
    byzantine_nodes: tuple[int, ...],
    actions_by_round: list[tuple[int, ...]],
    rewards_by_round: list[tuple[float, ...]],
    preferred_arms: tuple[int, ...],
    agent_states: tuple[dict[str, object], ...],
    messages: tuple[Message, ...],
    attack_diagnostics: tuple[AttackDiagnostic, ...],
    aggregation_summary: dict[str, int],
    aggregation_diagnostics: tuple[dict[str, object], ...],
) -> MultiAgentRunResult:
    environment = BernoulliBanditEnvironment.from_means(config.bandit.arm_means)
    honest_actions = _select_actions_for_nodes(actions_by_round, honest_nodes)
    honest_preferred_arms = tuple(preferred_arms[node] for node in honest_nodes)
    regret = summarize_population_regret(config.bandit.arm_means, honest_actions)
    recovery = summarize_recovery_time(
        regret.mean_regret_curve,
        change_round=config.topology_change.change_round,
        enabled=config.topology_change.enabled,
    )
    communication = summarize_communication(
        messages,
        num_agents=config.population.agents,
    )
    identified = sum(arm == environment.optimal_arm for arm in honest_preferred_arms)
    run_seed = config.experiment.seeds[0]
    run_id = (
        f"{config.name}_{config.algorithm.name}_{config.graph.family}_seed-{run_seed}"
    )
    aggregation_summary_record: dict[str, object] = {
        key: value for key, value in aggregation_summary.items()
    }
    return MultiAgentRunResult(
        run_id=run_id,
        algorithm=config.algorithm.name,
        seed=run_seed,
        horizon=config.experiment.horizon,
        num_agents=config.population.agents,
        graph=graph.to_record(),
        topology_change=_topology_change_record(config, topology_event),
        honest_nodes=honest_nodes,
        byzantine_nodes=byzantine_nodes,
        attack=_attack_record(config, byzantine_nodes),
        aggregation=_aggregation_record(config),
        actions_by_round=tuple(actions_by_round),
        rewards_by_round=tuple(rewards_by_round),
        total_population_regret=regret.total_final_regret,
        mean_per_agent_regret=regret.mean_per_agent_final_regret,
        per_agent_final_regret=regret.per_agent_final_regret,
        total_regret_curve=regret.total_regret_curve,
        mean_regret_curve=regret.mean_regret_curve,
        recovery=recovery.to_record(),
        best_arm=environment.optimal_arm,
        preferred_arms=preferred_arms,
        best_arm_identification_rate=identified / len(honest_nodes),
        communication=communication.to_record(),
        agent_states=agent_states,
        attack_diagnostics=tuple(
            diagnostic.to_record() for diagnostic in attack_diagnostics
        ),
        aggregation_summary=aggregation_summary_record,
        aggregation_diagnostics=aggregation_diagnostics,
    )


def _validate_multi_agent_config(config: StudyConfig) -> None:
    if config.population.agents < 2:
        raise SimulationError(
            "Milestone 6 multi-agent run requires at least two agents"
        )
    if len(config.experiment.seeds) != 1:
        raise SimulationError("Milestone 6 run expects exactly one experiment seed")
    if config.algorithm.name not in MULTI_AGENT_ALGORITHMS:
        raise SimulationError(
            f"Milestone 6 supports only {sorted(MULTI_AGENT_ALGORITHMS)}"
        )
    if (
        config.topology_change.enabled
        and config.algorithm.name != "one_hop_weighted_pooling_ucb1"
    ):
        raise SimulationError(
            "Milestone 6 topology changes are defined for "
            "one_hop_weighted_pooling_ucb1 communication runs"
        )
    if (
        config.population.byzantine_fraction > 0.0
        and config.algorithm.name == "centralized_pooled_shared_action_ucb1"
    ):
        raise SimulationError(
            "centralized_pooled_shared_action_ucb1 is currently defined only "
            "for clean pooled learning runs"
        )
    if (
        config.algorithm.name == "one_hop_weighted_pooling_ucb1"
        and not config.communication.enabled
    ):
        raise SimulationError(
            "one_hop_weighted_pooling_ucb1 requires communication.enabled=true"
        )
    if (
        config.algorithm.name != "one_hop_weighted_pooling_ucb1"
        and config.communication.enabled
    ):
        raise SimulationError(
            f"{config.algorithm.name} should use communication.enabled=false"
        )


def _select_byzantine_nodes(
    *,
    config: StudyConfig,
    graph: GeneratedGraph,
    component_seeds: Mapping[str, ComponentSeed],
) -> tuple[int, ...]:
    if config.population.byzantine_fraction == 0.0:
        return ()
    try:
        return select_byzantine_nodes(
            graph=graph,
            fraction=config.population.byzantine_fraction,
            policy=config.population.byzantine_placement,
            rng=component_seeds["attack"].rng(),
        )
    except ValueError as exc:
        raise SimulationError(str(exc)) from exc


def _honest_nodes(
    num_agents: int,
    byzantine_nodes: tuple[int, ...],
) -> tuple[int, ...]:
    byzantine_set = set(byzantine_nodes)
    honest = tuple(node for node in range(num_agents) if node not in byzantine_set)
    if not honest:
        raise SimulationError("at least one honest node is required")
    return honest


def _build_attack_strategy(config: StudyConfig) -> AttackStrategy:
    try:
        return build_attack_strategy(
            strategy=config.attack.strategy,
            target_arm=config.attack.target_arm,
            inflated_mean=config.attack.inflated_mean,
        )
    except ValueError as exc:
        raise SimulationError(str(exc)) from exc


def _build_aggregator(config: StudyConfig) -> Aggregator:
    try:
        return build_aggregator(
            method=config.aggregation.method,
            trim_count=config.aggregation.trim_count,
            trim_fraction=config.aggregation.trim_fraction,
            small_neighborhood_policy=config.aggregation.small_neighborhood_policy,
        )
    except ValueError as exc:
        raise SimulationError(str(exc)) from exc


def _should_apply_topology_change(
    *,
    config: StudyConfig,
    round_index: int,
    topology_event: TopologyChangeEvent | None,
) -> bool:
    return (
        config.topology_change.enabled
        and topology_event is None
        and config.topology_change.change_round == round_index
    )


def _apply_topology_change(
    *,
    config: StudyConfig,
    graph: GeneratedGraph,
    graph_rng: np.random.Generator,
) -> tuple[GeneratedGraph, TopologyChangeEvent]:
    try:
        return rewire_graph_once(
            graph=graph,
            change_round=config.topology_change.change_round or 0,
            rewire_fraction=config.topology_change.rewire_fraction,
            preserve_connectivity=config.topology_change.preserve_connectivity,
            rng=graph_rng,
        )
    except ValueError as exc:
        raise SimulationError(str(exc)) from exc


def _topology_change_record(
    config: StudyConfig,
    event: TopologyChangeEvent | None,
) -> dict[str, object]:
    if not config.topology_change.enabled:
        return {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": config.topology_change.preserve_connectivity,
            "event": None,
        }
    if event is None:
        raise SimulationError("enabled topology change was not applied")
    return {
        "enabled": True,
        "change_round": config.topology_change.change_round,
        "rewire_fraction": config.topology_change.rewire_fraction,
        "preserve_connectivity": config.topology_change.preserve_connectivity,
        "event": event.to_record(),
    }


def _attack_record(
    config: StudyConfig,
    byzantine_nodes: tuple[int, ...],
) -> dict[str, object]:
    return {
        "strategy": config.attack.strategy,
        "knowledge": "oblivious",
        "target_arm": config.attack.target_arm,
        "inflated_mean": config.attack.inflated_mean,
        "diagnostics_enabled": config.attack.diagnostics,
        "byzantine_fraction_configured": config.population.byzantine_fraction,
        "byzantine_count": len(byzantine_nodes),
        "placement": config.population.byzantine_placement,
    }


def _aggregation_record(config: StudyConfig) -> dict[str, object]:
    return {
        "method": config.aggregation.method,
        "trim_count": config.aggregation.trim_count,
        "trim_fraction": config.aggregation.trim_fraction,
        "small_neighborhood_policy": config.aggregation.small_neighborhood_policy,
        "diagnostics_enabled": config.aggregation.diagnostics,
        "information_scope": "one_hop",
        "effective_support_rule": (
            "summed_counts_for_mean_source_count_for_robust_methods"
        ),
    }


def _empty_aggregation_summary() -> dict[str, int]:
    return {
        "aggregation_events": 0,
        "arm_aggregation_events": 0,
        "fallback_events": 0,
        "fallback_arm_events": 0,
        "invalid_messages_rejected": 0,
    }


def _update_aggregation_summary(
    summary: dict[str, int],
    diagnostics_by_receiver: dict[int, AggregationDiagnostics],
) -> None:
    for diagnostic in diagnostics_by_receiver.values():
        summary["aggregation_events"] += 1
        summary["arm_aggregation_events"] += len(diagnostic.valid_sources_per_arm)
        fallback_arm_events = sum(diagnostic.fallback_used_per_arm)
        summary["fallback_arm_events"] += fallback_arm_events
        if fallback_arm_events > 0:
            summary["fallback_events"] += 1
        summary["invalid_messages_rejected"] += diagnostic.invalid_messages_rejected


def _aggregation_diagnostic_records(
    *,
    round_index: int,
    diagnostics_by_receiver: dict[int, AggregationDiagnostics],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "round_index": round_index,
            "receiver": receiver,
            **diagnostic.to_record(),
        }
        for receiver, diagnostic in sorted(diagnostics_by_receiver.items())
    )


def _select_actions_for_nodes(
    actions_by_round: list[tuple[int, ...]],
    nodes: tuple[int, ...],
) -> list[tuple[int, ...]]:
    return [tuple(actions[node] for node in nodes) for actions in actions_by_round]


def _require_streams(
    component_seeds: Mapping[str, ComponentSeed],
    stream_names: tuple[str, ...],
) -> None:
    missing = [name for name in stream_names if name not in component_seeds]
    if missing:
        raise SimulationError(f"missing required seed streams: {missing}")


def _agent_rngs(
    component_seeds: Mapping[str, ComponentSeed],
    num_agents: int,
) -> tuple[np.random.Generator, ...]:
    children = component_seeds["agents"].seed_sequence().spawn(num_agents)
    return tuple(np.random.default_rng(child) for child in children)


def _precompute_rewards(
    *,
    environment: BernoulliBanditEnvironment,
    horizon: int,
    num_agents: int,
    rng: np.random.Generator,
) -> np.ndarray:
    probabilities = np.asarray(environment.arm_means, dtype=float)
    reward_table = rng.binomial(
        n=1,
        p=probabilities,
        size=(horizon, num_agents, environment.num_arms),
    )
    return reward_table.astype(float)


def _exploration_c(config: StudyConfig) -> float:
    raw_value = config.algorithm.parameters.get("exploration_c")
    if raw_value is None:
        raise SimulationError("algorithm.parameters.exploration_c is required")
    if not isinstance(raw_value, int | float) or isinstance(raw_value, bool):
        raise SimulationError("algorithm.parameters.exploration_c must be numeric")
    value = float(raw_value)
    if not np.isfinite(value) or value < 0.0:
        raise SimulationError(
            "algorithm.parameters.exploration_c must be non-negative and finite"
        )
    return value


def _write_single_agent_result(
    *,
    result: SingleAgentRunResult,
    config: StudyConfig,
    component_seeds: Mapping[str, ComponentSeed],
    output_path: Path,
    runtime_seconds: float,
) -> None:
    if output_path.exists() and not config.experiment.overwrite:
        raise SimulationError(
            f"result file already exists and overwrite is false: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "completed",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependency_versions": _dependency_versions(),
        "resolved_config": config.resolved_dict(),
        "run_component_seeds": {
            name: seed.to_record() for name, seed in component_seeds.items()
        },
        "result": result.to_record(),
    }
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_result_record(
    *,
    result: SingleAgentRunResult | MultiAgentRunResult,
    config: StudyConfig,
    component_seeds: Mapping[str, ComponentSeed],
    output_path: Path,
    runtime_seconds: float,
) -> None:
    if output_path.exists() and not config.experiment.overwrite:
        raise SimulationError(
            f"result file already exists and overwrite is false: {output_path}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "completed",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependency_versions": _dependency_versions(),
        "resolved_config": config.resolved_dict(),
        "run_component_seeds": {
            name: seed.to_record() for name, seed in component_seeds.items()
        },
        "result": result.to_record(),
    }
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _dependency_versions() -> dict[str, str]:
    packages = ("networkx", "numpy", "PyYAML", "swarmgov-r")
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions
