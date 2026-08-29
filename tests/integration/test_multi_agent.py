from __future__ import annotations

from swarmgov.config import StudyConfig
from swarmgov.simulation import MultiAgentRunResult, run_multi_agent


def test_clean_multi_agent_runs_are_reproducible_across_required_graphs() -> None:
    families = ("complete", "ring", "small_world", "scale_free")
    for family in families:
        config = StudyConfig.from_mapping(
            _base_multi_agent_config(family, "one_hop_weighted_pooling_ucb1")
        )

        first = run_multi_agent(config, write=False)
        second = run_multi_agent(config, write=False)

        assert isinstance(first, MultiAgentRunResult)
        assert first.graph == second.graph
        assert first.actions_by_round == second.actions_by_round
        assert first.rewards_by_round == second.rewards_by_round
        assert first.mean_regret_curve == second.mean_regret_curve
        assert first.communication["messages_sent"] > 0


def test_clean_multi_agent_baselines_execute_on_complete_graph() -> None:
    for algorithm in (
        "independent_ucb1",
        "centralized_pooled_shared_action_ucb1",
        "one_hop_weighted_pooling_ucb1",
    ):
        config = StudyConfig.from_mapping(
            _base_multi_agent_config("complete", algorithm)
        )

        result = run_multi_agent(config, write=False)

        assert result.algorithm == algorithm
        assert len(result.actions_by_round) == 12
        assert result.graph["family"] == "complete"


def _base_multi_agent_config(family: str, algorithm: str) -> dict[str, object]:
    communication_enabled = algorithm == "one_hop_weighted_pooling_ucb1"
    return {
        "name": "integration-clean",
        "stage": "stage_a",
        "description": "clean multi-agent integration test",
        "seeds": {
            "master": 4242,
            "streams": ["environment", "graph", "agents", "simulation"],
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
            "horizon": 12,
            "seeds": [0],
            "output_dir": "results/raw/integration-clean",
            "overwrite": False,
        },
    }


def _graph_parameters(family: str) -> dict[str, object]:
    if family == "small_world":
        return {"k": 2, "p": 0.25}
    if family == "scale_free":
        return {"m": 1}
    return {}
