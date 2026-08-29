from __future__ import annotations

import numpy as np

from swarmgov.aggregators import build_aggregator
from swarmgov.attacks import (
    AttackContext,
    ConstantInflationAttack,
    apply_message_attacks,
)
from swarmgov.communication import build_round_messages, inbound_messages_by_receiver
from swarmgov.config import StudyConfig
from swarmgov.graphs import generate_static_graph
from swarmgov.simulation import run_multi_agent


def test_clean_mean_median_and_trimmed_mean_runs_complete() -> None:
    for method in ("mean", "median", "trimmed_mean"):
        result = run_multi_agent(
            StudyConfig.from_mapping(_base_config(method=method)),
            write=False,
        )

        assert result.aggregation["method"] == method
        assert len(result.actions_by_round) == 12
        assert result.communication["messages_sent"] > 0


def test_extreme_inflation_moves_mean_more_than_robust_aggregators() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=4,
        parameters={},
        rng=np.random.default_rng(0),
    )
    local_counts = [
        np.asarray([1, 1]),
        np.asarray([1, 1]),
        np.asarray([1, 1]),
        np.asarray([1, 1]),
    ]
    local_sums = [
        np.asarray([0.8, 0.0]),
        np.asarray([0.8, 0.0]),
        np.asarray([0.8, 0.0]),
        np.asarray([0.8, 0.0]),
    ]
    messages = build_round_messages(
        graph=graph,
        round_index=1,
        local_counts=local_counts,
        local_reward_sums=local_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    attacked_messages = apply_message_attacks(
        messages=messages,
        byzantine_nodes=(3,),
        strategy=ConstantInflationAttack(target_arm=1, inflated_mean=1.0),
        context=AttackContext(round_index=1, num_arms=2),
    ).messages
    inbound = inbound_messages_by_receiver(attacked_messages, num_nodes=4)

    mean_target = _aggregate_target_mean("mean", local_counts, local_sums, inbound)
    median_target = _aggregate_target_mean("median", local_counts, local_sums, inbound)
    trimmed_target = _aggregate_target_mean(
        "trimmed_mean",
        local_counts,
        local_sums,
        inbound,
    )

    assert mean_target == 0.25
    assert median_target == 0.0
    assert trimmed_target == 0.0
    assert mean_target > median_target
    assert mean_target > trimmed_target


def test_sparse_ring_exercises_trimmed_mean_small_neighborhood_policy() -> None:
    data = _base_config(method="trimmed_mean", family="ring")
    data["aggregation"]["diagnostics"] = True
    result = run_multi_agent(StudyConfig.from_mapping(data), write=False)

    assert result.aggregation["small_neighborhood_policy"] == "median_fallback"
    assert result.aggregation_summary["fallback_events"] > 0
    assert result.aggregation_diagnostics


def test_same_seed_reproduces_actions_messages_aggregates_and_metrics() -> None:
    data = _base_config(method="median")
    data["aggregation"]["diagnostics"] = True
    config = StudyConfig.from_mapping(data)

    first = run_multi_agent(config, write=False)
    second = run_multi_agent(config, write=False)

    assert first.actions_by_round == second.actions_by_round
    assert first.rewards_by_round == second.rewards_by_round
    assert first.communication == second.communication
    assert first.aggregation_summary == second.aggregation_summary
    assert first.aggregation_diagnostics == second.aggregation_diagnostics
    assert first.mean_regret_curve == second.mean_regret_curve


def test_zero_byzantine_fraction_preserves_median_clean_trajectory() -> None:
    implicit = _base_config(method="median")
    explicit = _base_config(method="median")
    explicit["attack"] = {
        "strategy": "no_attack",
        "target_arm": None,
        "inflated_mean": 1.0,
        "diagnostics": True,
    }

    first = run_multi_agent(StudyConfig.from_mapping(implicit), write=False)
    second = run_multi_agent(StudyConfig.from_mapping(explicit), write=False)

    assert first.actions_by_round == second.actions_by_round
    assert first.mean_regret_curve == second.mean_regret_curve
    assert second.attack_diagnostics == ()


def test_result_output_identifies_robust_aggregation_hyperparameters() -> None:
    result = run_multi_agent(
        StudyConfig.from_mapping(_base_config(method="trimmed_mean")),
        write=False,
    )

    assert result.aggregation["method"] == "trimmed_mean"
    assert result.aggregation["trim_count"] == 1
    assert result.aggregation["small_neighborhood_policy"] == "median_fallback"
    assert "source_count" in result.aggregation["effective_support_rule"]


def _aggregate_target_mean(
    method: str,
    local_counts: list[np.ndarray],
    local_sums: list[np.ndarray],
    inbound,
) -> float:
    aggregator = build_aggregator(
        method=method,
        trim_count=1 if method == "trimmed_mean" else None,
    )
    result = aggregator.aggregate(
        local_counts=local_counts[0],
        local_reward_sums=local_sums[0],
        messages=inbound[0],
        round_index=1,
    )
    return result.statistics.empirical_means[1]


def _base_config(
    *,
    method: str,
    family: str = "complete",
) -> dict[str, object]:
    return {
        "name": "robust-integration",
        "stage": "stage_a",
        "description": "robust aggregation integration test",
        "seeds": {
            "master": 777,
            "streams": ["environment", "graph", "agents", "attack"],
        },
        "population": {
            "agents": 5,
            "byzantine_fraction": 0.0,
            "byzantine_placement": "none",
        },
        "bandit": {
            "arms": 3,
            "arm_means": [0.75, 0.55, 0.35],
            "reward_family": "bernoulli",
        },
        "algorithm": {
            "name": "one_hop_weighted_pooling_ucb1",
            "parameters": {"exploration_c": 1.0},
        },
        "graph": {
            "family": family,
            "parameters": {},
        },
        "communication": {
            "interval": 1,
            "enabled": True,
        },
        "aggregation": {
            "method": method,
            "trim_count": 1 if method == "trimmed_mean" else None,
            "trim_fraction": None,
            "small_neighborhood_policy": "median_fallback",
            "diagnostics": False,
        },
        "topology_change": {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": 12,
            "seeds": [0],
            "output_dir": "results/raw/robust-integration",
            "overwrite": False,
        },
    }
