"""Compact record construction for confirmatory experiment storage."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from swarmgov.simulation import MultiAgentRunResult

COMPACT_RECORD_SCHEMA_VERSION = "confirmatory_compact_v1"


@dataclass(frozen=True)
class CurveSamplingConfig:
    """Deterministic curve sampling policy for compact result records."""

    stride: int = 1
    max_points: int = 2000

    def __post_init__(self) -> None:
        if self.stride <= 0:
            raise ValueError("curve sampling stride must be positive")
        if self.max_points < 2:
            raise ValueError("max curve points must be at least 2")


def compact_multi_agent_result(
    result: MultiAgentRunResult,
    *,
    curve_sampling: CurveSamplingConfig,
) -> dict[str, object]:
    """Build the compact, versioned M8 result payload.

    The compact payload intentionally excludes raw actions, raw rewards,
    agent-state snapshots, and verbose diagnostics. It keeps final metrics,
    graph/topology metadata, node identities, communication cost, and sampled
    regret curves needed for confirmatory aggregation and plotting.
    """

    per_agent = np.asarray(result.per_agent_final_regret, dtype=float)
    mean_curve = _sample_curve(result.mean_regret_curve, curve_sampling)
    total_curve = _sample_curve(result.total_regret_curve, curve_sampling)
    if mean_curve["rounds"] != total_curve["rounds"]:
        raise ValueError("mean and total regret curves sampled different rounds")

    return {
        "schema_version": COMPACT_RECORD_SCHEMA_VERSION,
        "payload_policy": {
            "raw_actions_stored": False,
            "raw_rewards_stored": False,
            "agent_states_stored": False,
            "attack_diagnostics_stored": False,
            "aggregation_diagnostics_stored": False,
            "curve_sampling": {
                "stride": curve_sampling.stride,
                "max_points": curve_sampling.max_points,
                "original_points": len(result.mean_regret_curve),
                "stored_points": len(mean_curve["rounds"]),
            },
        },
        "identifiers": {
            "run_id": result.run_id,
            "algorithm": result.algorithm,
            "seed": result.seed,
            "horizon": result.horizon,
            "num_agents": result.num_agents,
        },
        "graph": result.graph,
        "topology_change": result.topology_change,
        "node_sets": {
            "honest_nodes": result.honest_nodes,
            "byzantine_nodes": result.byzantine_nodes,
        },
        "attack": result.attack,
        "aggregation": result.aggregation,
        "metrics": {
            "total_population_regret": result.total_population_regret,
            "mean_per_agent_regret": result.mean_per_agent_regret,
            "median_honest_regret": float(np.median(per_agent)),
            "worst_decile_honest_regret": float(np.quantile(per_agent, 0.9)),
            "max_honest_regret": float(np.max(per_agent)),
            "per_agent_final_regret": result.per_agent_final_regret,
            "recovery": result.recovery,
            "best_arm": result.best_arm,
            "preferred_arms": result.preferred_arms,
            "best_arm_identification_rate": result.best_arm_identification_rate,
            "communication": result.communication,
            "aggregation_summary": result.aggregation_summary,
        },
        "curves": {
            "rounds": mean_curve["rounds"],
            "mean_regret": mean_curve["values"],
            "total_regret": total_curve["values"],
        },
        "diagnostics_summary": {
            "attack_diagnostics_count": len(result.attack_diagnostics),
            "aggregation_diagnostics_count": len(result.aggregation_diagnostics),
        },
    }


def _sample_curve(
    values: Sequence[float],
    sampling: CurveSamplingConfig,
) -> dict[str, tuple[float, ...] | tuple[int, ...]]:
    if not values:
        return {"rounds": (), "values": ()}
    selected = tuple(range(0, len(values), sampling.stride))
    if selected[-1] != len(values) - 1:
        selected = (*selected, len(values) - 1)
    if len(selected) > sampling.max_points:
        selected = _evenly_spaced_indices(len(values), sampling.max_points)
    return {
        "rounds": tuple(index + 1 for index in selected),
        "values": tuple(float(values[index]) for index in selected),
    }


def _evenly_spaced_indices(total_points: int, max_points: int) -> tuple[int, ...]:
    step = (total_points - 1) / (max_points - 1)
    indices = {round(position * step) for position in range(max_points)}
    indices.add(0)
    indices.add(total_points - 1)
    return tuple(sorted(indices))
