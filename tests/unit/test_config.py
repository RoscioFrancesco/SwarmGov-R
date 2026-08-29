from __future__ import annotations

from pathlib import Path

import pytest

from swarmgov.config import ConfigError, StudyConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_smoke_config_loads_and_resolves_component_seeds() -> None:
    config = load_config(REPO_ROOT / "configs" / "smoke.yaml")
    resolved = config.resolved_dict()

    assert config.name == "smoke-one-hop-weighted-pooling-clean"
    assert config.population.agents == 5
    assert config.population.byzantine_fraction == 0.0
    assert config.bandit.reward_family == "bernoulli"
    assert config.communication.enabled is True
    assert config.aggregation.method == "mean"
    assert config.attack.strategy == "no_attack"
    assert "environment" in resolved["derived_component_seeds"]


def test_attacked_smoke_config_loads() -> None:
    config = load_config(REPO_ROOT / "configs" / "attacked_smoke.yaml")

    assert config.population.byzantine_fraction == 0.2
    assert config.population.byzantine_placement == "degree_centrality"
    assert config.attack.strategy == "coordinated_target"
    assert config.attack.target_arm == 1
    assert config.attack.diagnostics is True


def test_dynamic_smoke_config_loads() -> None:
    config = load_config(REPO_ROOT / "configs" / "dynamic_smoke.yaml")

    assert config.topology_change.enabled is True
    assert config.topology_change.change_round == 30
    assert config.topology_change.rewire_fraction == 0.25
    assert config.topology_change.preserve_connectivity is True


def test_config_rejects_arm_count_mismatch() -> None:
    data = _base_config()
    data["bandit"]["arms"] = 4

    with pytest.raises(ConfigError, match="bandit.arms"):
        StudyConfig.from_mapping(data)


def test_config_rejects_invalid_probability() -> None:
    data = _base_config()
    data["bandit"]["arm_means"] = [0.8, 1.2, 0.3]

    with pytest.raises(ConfigError, match="inside"):
        StudyConfig.from_mapping(data)


def test_config_rejects_enabled_topology_change_without_round() -> None:
    data = _base_config()
    data["topology_change"]["enabled"] = True

    with pytest.raises(ConfigError, match="change_round"):
        StudyConfig.from_mapping(data)


def test_config_rejects_enabled_topology_change_without_rewiring() -> None:
    data = _base_config()
    data["algorithm"]["name"] = "one_hop_weighted_pooling_ucb1"
    data["communication"]["enabled"] = True
    data["topology_change"] = {
        "enabled": True,
        "change_round": 10,
        "rewire_fraction": 0.0,
        "preserve_connectivity": True,
    }

    with pytest.raises(ConfigError, match="positive rewire_fraction"):
        StudyConfig.from_mapping(data)


def test_config_rejects_disabled_topology_change_with_non_neutral_fields() -> None:
    data = _base_config()
    data["topology_change"]["change_round"] = 10

    with pytest.raises(ConfigError, match="disabled topology changes"):
        StudyConfig.from_mapping(data)


def test_config_rejects_dynamic_topology_for_non_communication_baseline() -> None:
    data = _base_config()
    data["topology_change"] = {
        "enabled": True,
        "change_round": 10,
        "rewire_fraction": 0.25,
        "preserve_connectivity": True,
    }

    with pytest.raises(ConfigError, match="one_hop_weighted_pooling"):
        StudyConfig.from_mapping(data)


def test_config_rejects_dynamic_topology_on_complete_graph() -> None:
    data = _base_config()
    data["algorithm"]["name"] = "one_hop_weighted_pooling_ucb1"
    data["communication"]["enabled"] = True
    data["graph"]["family"] = "complete"
    data["topology_change"] = {
        "enabled": True,
        "change_round": 10,
        "rewire_fraction": 0.25,
        "preserve_connectivity": True,
    }

    with pytest.raises(ConfigError, match="complete graphs"):
        StudyConfig.from_mapping(data)


def test_config_rejects_optimal_attack_target() -> None:
    data = _base_config()
    data["population"]["byzantine_fraction"] = 0.4
    data["population"]["byzantine_placement"] = "random"
    data["attack"] = {
        "strategy": "constant_inflation",
        "target_arm": 0,
        "inflated_mean": 1.0,
        "diagnostics": False,
    }

    with pytest.raises(ConfigError, match="suboptimal"):
        StudyConfig.from_mapping(data)


def test_config_accepts_trimmed_mean_with_single_trim_parameter() -> None:
    data = _base_config()
    data["algorithm"]["name"] = "one_hop_weighted_pooling_ucb1"
    data["communication"]["enabled"] = True
    data["aggregation"] = {
        "method": "trimmed_mean",
        "trim_count": 1,
        "trim_fraction": None,
        "small_neighborhood_policy": "median_fallback",
        "diagnostics": True,
    }

    config = StudyConfig.from_mapping(data)

    assert config.aggregation.method == "trimmed_mean"
    assert config.aggregation.trim_count == 1


def test_config_rejects_conflicting_trim_parameters() -> None:
    data = _base_config()
    data["algorithm"]["name"] = "one_hop_weighted_pooling_ucb1"
    data["communication"]["enabled"] = True
    data["aggregation"] = {
        "method": "trimmed_mean",
        "trim_count": 1,
        "trim_fraction": 0.2,
        "small_neighborhood_policy": "median_fallback",
        "diagnostics": False,
    }

    with pytest.raises(ConfigError, match="exactly one"):
        StudyConfig.from_mapping(data)


def test_config_rejects_robust_aggregation_for_independent_baseline() -> None:
    data = _base_config()
    data["aggregation"] = {
        "method": "median",
        "trim_count": None,
        "trim_fraction": None,
        "small_neighborhood_policy": "median_fallback",
        "diagnostics": False,
    }

    with pytest.raises(ConfigError, match="non-communication"):
        StudyConfig.from_mapping(data)


def _base_config() -> dict[str, object]:
    return {
        "name": "test",
        "stage": "stage_a",
        "description": "test config",
        "seeds": {
            "master": 1,
            "streams": ["environment", "graph", "agents"],
        },
        "population": {
            "agents": 3,
            "byzantine_fraction": 0.0,
            "byzantine_placement": "none",
        },
        "bandit": {
            "arms": 3,
            "arm_means": [0.8, 0.5, 0.3],
            "reward_family": "bernoulli",
        },
        "algorithm": {
            "name": "independent_ucb1",
            "parameters": {"exploration_c": 1.41421356237},
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
            "horizon": 50,
            "seeds": [0],
            "output_dir": "results/raw/test",
            "overwrite": False,
        },
    }
