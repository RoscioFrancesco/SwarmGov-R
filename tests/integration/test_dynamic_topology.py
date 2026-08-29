from __future__ import annotations

from copy import deepcopy

from swarmgov.config import StudyConfig
from swarmgov.simulation import run_multi_agent


def test_dynamic_topology_run_records_event_and_recovery_metric() -> None:
    result = run_multi_agent(StudyConfig.from_mapping(_dynamic_config()), write=False)
    event = result.topology_change["event"]

    assert result.topology_change["enabled"] is True
    assert event is not None
    assert event["change_round"] == 7
    assert event["requested_edge_changes"] == 2
    assert _edges(event["edges_before"]) == _edges(result.graph["edges"])
    assert _edges(event["edges_after"]) != _edges(event["edges_before"])
    assert event["connected_before"] is True
    assert event["connected_after"] is True
    assert result.recovery["enabled"] is True
    assert result.recovery["change_round"] == 7
    assert result.recovery["baseline_window"] == 5
    assert result.recovery["recovery_window"] == 5


def test_static_and_dynamic_runs_match_through_change_round() -> None:
    static_data = _static_config()
    dynamic_data = _dynamic_config()

    static = run_multi_agent(StudyConfig.from_mapping(static_data), write=False)
    dynamic = run_multi_agent(StudyConfig.from_mapping(dynamic_data), write=False)
    change_round = dynamic_data["topology_change"]["change_round"]

    assert static.graph == dynamic.graph
    assert dynamic.topology_change["event"] is not None
    assert _edges(dynamic.topology_change["event"]["edges_after"]) != _edges(
        static.graph["edges"]
    )
    assert (
        dynamic.actions_by_round[:change_round]
        == static.actions_by_round[:change_round]
    )
    assert (
        dynamic.rewards_by_round[:change_round]
        == static.rewards_by_round[:change_round]
    )


def test_dynamic_topology_runs_are_reproducible() -> None:
    config = StudyConfig.from_mapping(_dynamic_config())

    first = run_multi_agent(config, write=False)
    second = run_multi_agent(config, write=False)

    assert first.topology_change == second.topology_change
    assert first.actions_by_round == second.actions_by_round
    assert first.rewards_by_round == second.rewards_by_round
    assert first.mean_regret_curve == second.mean_regret_curve
    assert first.recovery == second.recovery


def test_byzantine_set_is_fixed_across_topology_change() -> None:
    static_data = _static_config()
    dynamic_data = _dynamic_config()
    _enable_no_attack_byzantine_nodes(static_data)
    _enable_no_attack_byzantine_nodes(dynamic_data)

    static = run_multi_agent(StudyConfig.from_mapping(static_data), write=False)
    dynamic = run_multi_agent(StudyConfig.from_mapping(dynamic_data), write=False)

    assert static.byzantine_nodes == dynamic.byzantine_nodes
    assert dynamic.byzantine_nodes
    assert dynamic.topology_change["event"] is not None


def _dynamic_config() -> dict[str, object]:
    return {
        "name": "dynamic-integration",
        "stage": "stage_a",
        "description": "dynamic topology integration test",
        "seeds": {
            "master": 9090,
            "streams": ["environment", "graph", "agents", "attack", "simulation"],
        },
        "population": {
            "agents": 8,
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
            "family": "ring",
            "parameters": {},
        },
        "communication": {
            "interval": 1,
            "enabled": True,
        },
        "aggregation": {
            "method": "mean",
            "trim_count": None,
            "trim_fraction": None,
            "small_neighborhood_policy": "median_fallback",
            "diagnostics": False,
        },
        "attack": {
            "strategy": "no_attack",
            "target_arm": None,
            "inflated_mean": 1.0,
            "diagnostics": False,
        },
        "topology_change": {
            "enabled": True,
            "change_round": 7,
            "rewire_fraction": 0.25,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": 14,
            "seeds": [0],
            "output_dir": "results/raw/dynamic-integration",
            "overwrite": False,
        },
    }


def _static_config() -> dict[str, object]:
    data = deepcopy(_dynamic_config())
    data["name"] = "static-integration"
    data["topology_change"] = {
        "enabled": False,
        "change_round": None,
        "rewire_fraction": 0.0,
        "preserve_connectivity": True,
    }
    return data


def _enable_no_attack_byzantine_nodes(data: dict[str, object]) -> None:
    data["population"]["byzantine_fraction"] = 0.25
    data["population"]["byzantine_placement"] = "degree_centrality"


def _edges(raw_edges) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(tuple(edge) for edge in raw_edges))
