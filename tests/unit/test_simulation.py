from __future__ import annotations

import json
from pathlib import Path

import pytest

from swarmgov.config import StudyConfig, load_config
from swarmgov.simulation import (
    MultiAgentRunResult,
    SimulationError,
    run_configured_experiment,
    run_multi_agent,
    run_single_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_single_agent_run_is_reproducible_without_writing() -> None:
    config = StudyConfig.from_mapping(_base_single_agent_config())

    first = run_single_agent(config, write=False)
    second = run_single_agent(config, write=False)

    assert first.actions == second.actions
    assert first.rewards == second.rewards
    assert first.regret_curve == second.regret_curve
    assert first.agent_state == second.agent_state


def test_single_agent_run_writes_valid_json(tmp_path: Path) -> None:
    config = StudyConfig.from_mapping(_base_single_agent_config())

    result = run_single_agent(config, output_dir=tmp_path)

    assert result.output_path is not None
    output_path = Path(result.output_path)
    record = json.loads(output_path.read_text(encoding="utf-8"))

    assert record["status"] == "completed"
    assert record["result"]["run_id"] == "test_seed-0"
    assert len(record["result"]["actions"]) == config.experiment.horizon
    assert len(record["result"]["regret_curve"]) == config.experiment.horizon
    assert "environment" in record["run_component_seeds"]


def test_single_agent_run_does_not_overwrite_by_default(tmp_path: Path) -> None:
    config = StudyConfig.from_mapping(_base_single_agent_config())
    run_single_agent(config, output_dir=tmp_path)

    with pytest.raises(SimulationError, match="overwrite"):
        run_single_agent(config, output_dir=tmp_path)


def test_single_agent_run_rejects_multi_agent_config() -> None:
    data = _base_single_agent_config()
    data["population"]["agents"] = 2

    config = StudyConfig.from_mapping(data)

    with pytest.raises(SimulationError, match="exactly one agent"):
        run_single_agent(config, write=False)


def test_smoke_config_runs_as_multi_agent_one_hop_pooling() -> None:
    config = load_config(REPO_ROOT / "configs" / "smoke.yaml")
    result = run_configured_experiment(config, write=False)

    assert isinstance(result, MultiAgentRunResult)
    assert result.algorithm == "one_hop_weighted_pooling_ucb1"
    assert result.graph["family"] == "small_world"
    assert result.communication["messages_sent"] > 0
    assert len(result.actions_by_round) == config.experiment.horizon


def test_centralized_pooled_run_rejects_byzantine_fraction() -> None:
    data = _base_multi_agent_config(
        "complete",
        "centralized_pooled_shared_action_ucb1",
    )
    _enable_byzantine_attack(data, strategy="no_attack")
    config = StudyConfig.from_mapping(data)

    with pytest.raises(SimulationError, match="clean pooled"):
        run_multi_agent(config, write=False)


def test_attacked_one_hop_run_records_byzantine_nodes_and_diagnostics() -> None:
    data = _base_multi_agent_config("complete", "one_hop_weighted_pooling_ucb1")
    _enable_byzantine_attack(data, strategy="coordinated_target")
    data["attack"]["diagnostics"] = True
    config = StudyConfig.from_mapping(data)

    result = run_multi_agent(config, write=False)

    assert result.byzantine_nodes == (0,)
    assert result.honest_nodes == (1, 2, 3)
    assert result.attack["strategy"] == "coordinated_target"
    assert result.attack["byzantine_count"] == 1
    assert result.attack_diagnostics
    assert {record["sender"] for record in result.attack_diagnostics} == {0}
    changed = [
        record
        for record in result.attack_diagnostics
        if (
            record["original_message"]["reward_sums"]
            != record["corrupted_message"]["reward_sums"]
        )
    ]
    assert changed
    assert all(
        record["original_message"]["counts"] == record["corrupted_message"]["counts"]
        for record in result.attack_diagnostics
    )


def test_zero_byzantine_fraction_preserves_clean_behavior_exactly() -> None:
    data = _base_multi_agent_config("complete", "one_hop_weighted_pooling_ucb1")
    explicit_no_attack_data = _base_multi_agent_config(
        "complete",
        "one_hop_weighted_pooling_ucb1",
    )
    explicit_no_attack_data["attack"] = {
        "strategy": "no_attack",
        "target_arm": None,
        "inflated_mean": 1.0,
        "diagnostics": True,
    }

    clean = run_multi_agent(StudyConfig.from_mapping(data), write=False)
    identity = run_multi_agent(
        StudyConfig.from_mapping(explicit_no_attack_data),
        write=False,
    )

    assert clean.actions_by_round == identity.actions_by_round
    assert clean.rewards_by_round == identity.rewards_by_round
    assert clean.mean_regret_curve == identity.mean_regret_curve
    assert clean.communication == identity.communication
    assert identity.attack_diagnostics == ()


def test_independent_ucb_is_unchanged_by_byzantine_configuration() -> None:
    clean_data = _base_multi_agent_config("complete", "independent_ucb1")
    attacked_data = _base_multi_agent_config("complete", "independent_ucb1")
    _enable_byzantine_attack(attacked_data, strategy="constant_inflation")

    clean = run_multi_agent(StudyConfig.from_mapping(clean_data), write=False)
    attacked = run_multi_agent(StudyConfig.from_mapping(attacked_data), write=False)

    clean_honest_actions = _actions_for_nodes(clean, attacked.honest_nodes)
    attacked_honest_actions = _actions_for_nodes(attacked, attacked.honest_nodes)

    assert attacked.byzantine_nodes == (0,)
    assert clean_honest_actions == attacked_honest_actions
    assert attacked.communication["messages_sent"] == 0
    assert attacked.attack_diagnostics == ()


def test_dynamic_topology_requires_one_hop_communication() -> None:
    data = _base_multi_agent_config("ring", "independent_ucb1")
    data["topology_change"] = {
        "enabled": True,
        "change_round": 5,
        "rewire_fraction": 0.25,
        "preserve_connectivity": True,
    }
    with pytest.raises(ValueError, match="one_hop_weighted_pooling"):
        StudyConfig.from_mapping(data)


def test_dynamic_topology_runtime_rejects_impossible_rewiring() -> None:
    data = _base_multi_agent_config("ring", "one_hop_weighted_pooling_ucb1")
    data["population"]["agents"] = 4
    data["topology_change"] = {
        "enabled": True,
        "change_round": 5,
        "rewire_fraction": 1.0,
        "preserve_connectivity": True,
    }
    config = StudyConfig.from_mapping(data)

    with pytest.raises(SimulationError, match="pre-change non-edges"):
        run_multi_agent(config, write=False)


def _base_single_agent_config() -> dict[str, object]:
    return {
        "name": "test",
        "stage": "stage_a",
        "description": "single-agent test",
        "seeds": {
            "master": 1,
            "streams": ["environment", "graph", "agents"],
        },
        "population": {
            "agents": 1,
            "byzantine_fraction": 0.0,
            "byzantine_placement": "none",
        },
        "bandit": {
            "arms": 2,
            "arm_means": [0.8, 0.4],
            "reward_family": "bernoulli",
        },
        "algorithm": {
            "name": "independent_ucb1",
            "parameters": {"exploration_c": 1.0},
        },
        "graph": {
            "family": "complete",
            "parameters": {},
        },
        "communication": {
            "interval": 1,
            "enabled": False,
        },
        "topology_change": {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": 10,
            "seeds": [0],
            "output_dir": "results/raw/test",
            "overwrite": False,
        },
    }


def _base_multi_agent_config(family: str, algorithm: str) -> dict[str, object]:
    communication_enabled = algorithm == "one_hop_weighted_pooling_ucb1"
    return {
        "name": "multi-test",
        "stage": "stage_a",
        "description": "multi-agent test",
        "seeds": {
            "master": 1,
            "streams": ["environment", "graph", "agents"],
        },
        "population": {
            "agents": 4,
            "byzantine_fraction": 0.0,
            "byzantine_placement": "none",
        },
        "bandit": {
            "arms": 2,
            "arm_means": [0.8, 0.4],
            "reward_family": "bernoulli",
        },
        "algorithm": {
            "name": algorithm,
            "parameters": {"exploration_c": 1.0},
        },
        "graph": {
            "family": family,
            "parameters": _graph_parameters(family),
        },
        "communication": {
            "interval": 1,
            "enabled": communication_enabled,
        },
        "topology_change": {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": 10,
            "seeds": [0],
            "output_dir": "results/raw/multi-test",
            "overwrite": False,
        },
    }


def _graph_parameters(family: str) -> dict[str, object]:
    if family == "small_world":
        return {"k": 2, "p": 0.2}
    if family == "scale_free":
        return {"m": 1}
    return {}


def _enable_byzantine_attack(
    data: dict[str, object],
    *,
    strategy: str,
) -> None:
    data["seeds"]["streams"] = ["environment", "graph", "agents", "attack"]
    data["population"]["byzantine_fraction"] = 0.25
    data["population"]["byzantine_placement"] = "degree_centrality"
    data["attack"] = {
        "strategy": strategy,
        "target_arm": 1 if strategy != "no_attack" else None,
        "inflated_mean": 1.0,
        "diagnostics": False,
    }


def _actions_for_nodes(
    result: MultiAgentRunResult,
    nodes: tuple[int, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(actions[node] for node in nodes) for actions in result.actions_by_round
    )
