from __future__ import annotations

from swarmgov.analysis import (
    COMPACT_RECORD_SCHEMA_VERSION,
    CurveSamplingConfig,
    compact_multi_agent_result,
)
from swarmgov.config import StudyConfig
from swarmgov.simulation import run_multi_agent


def test_compact_result_excludes_raw_actions_rewards_and_agent_states() -> None:
    result = run_multi_agent(StudyConfig.from_mapping(_base_config()), write=False)

    compact = compact_multi_agent_result(
        result,
        curve_sampling=CurveSamplingConfig(),
    )

    assert compact["schema_version"] == COMPACT_RECORD_SCHEMA_VERSION
    assert compact["payload_policy"]["raw_actions_stored"] is False
    assert compact["payload_policy"]["raw_rewards_stored"] is False
    assert compact["payload_policy"]["agent_states_stored"] is False
    assert "actions_by_round" not in compact
    assert "rewards_by_round" not in compact
    assert "agent_states" not in compact
    assert "metrics" in compact
    assert "curves" in compact


def test_compact_result_curve_sampling_preserves_first_and_last_rounds() -> None:
    result = run_multi_agent(StudyConfig.from_mapping(_base_config()), write=False)

    compact = compact_multi_agent_result(
        result,
        curve_sampling=CurveSamplingConfig(stride=3, max_points=4),
    )

    assert compact["payload_policy"]["curve_sampling"] == {
        "stride": 3,
        "max_points": 4,
        "original_points": 12,
        "stored_points": 4,
    }
    assert compact["curves"]["rounds"][0] == 1
    assert compact["curves"]["rounds"][-1] == 12
    assert len(compact["curves"]["mean_regret"]) == 4
    assert len(compact["curves"]["total_regret"]) == 4


def test_curve_sampling_config_rejects_invalid_values() -> None:
    try:
        CurveSamplingConfig(stride=0)
    except ValueError as exc:
        assert "stride" in str(exc)
    else:
        raise AssertionError("expected stride validation error")

    for max_points in (0, 1):
        try:
            CurveSamplingConfig(max_points=max_points)
        except ValueError as exc:
            assert "max curve points" in str(exc)
        else:
            raise AssertionError("expected max_points validation error")


def _base_config() -> dict[str, object]:
    return {
        "name": "compact-result-test",
        "stage": "stage_a",
        "description": "compact result unit test",
        "seeds": {
            "master": 2468,
            "streams": ["environment", "graph", "agents", "attack", "simulation"],
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
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": 12,
            "seeds": [0],
            "output_dir": "results/raw/compact-result-test",
            "overwrite": False,
        },
    }
