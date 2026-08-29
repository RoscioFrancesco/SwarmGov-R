"""Regret metrics for bandit runs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


class MetricError(ValueError):
    """Raised when metric inputs are malformed."""


@dataclass(frozen=True)
class RegretSummary:
    final_regret: float
    regret_curve: tuple[float, ...]
    per_round_regret: tuple[float, ...]


@dataclass(frozen=True)
class PopulationRegretSummary:
    total_final_regret: float
    mean_per_agent_final_regret: float
    per_agent_final_regret: tuple[float, ...]
    total_regret_curve: tuple[float, ...]
    mean_regret_curve: tuple[float, ...]
    per_agent_regret_curves: tuple[tuple[float, ...], ...]


def expected_regret_for_arm(arm_means: Iterable[float], arm: int) -> float:
    means = _validated_means(arm_means)
    if not isinstance(arm, int) or isinstance(arm, bool):
        raise MetricError("arm must be an integer")
    if not 0 <= arm < len(means):
        raise MetricError(f"arm index {arm} is outside valid range [0, {len(means)})")
    return float(np.max(means) - means[arm])


def per_round_expected_regret(
    arm_means: Iterable[float],
    actions: Iterable[int],
) -> np.ndarray:
    means = _validated_means(arm_means)
    action_array = _validated_actions(actions, len(means))
    return np.max(means) - means[action_array]


def cumulative_expected_regret(
    arm_means: Iterable[float],
    actions: Iterable[int],
) -> np.ndarray:
    return np.cumsum(per_round_expected_regret(arm_means, actions))


def summarize_regret(
    arm_means: Iterable[float],
    actions: Iterable[int],
) -> RegretSummary:
    per_round = per_round_expected_regret(arm_means, actions)
    curve = np.cumsum(per_round)
    final = float(curve[-1]) if len(curve) else 0.0
    return RegretSummary(
        final_regret=final,
        regret_curve=tuple(float(value) for value in curve),
        per_round_regret=tuple(float(value) for value in per_round),
    )


def summarize_population_regret(
    arm_means: Iterable[float],
    actions_by_round: Iterable[Iterable[int]],
) -> PopulationRegretSummary:
    means = _validated_means(arm_means)
    actions = np.asarray(tuple(tuple(row) for row in actions_by_round), dtype=np.int64)
    if actions.ndim != 2:
        raise MetricError("actions_by_round must be a two-dimensional sequence")
    for action in actions.flat:
        if not 0 <= int(action) < len(means):
            raise MetricError(
                f"action index {int(action)} is outside valid range [0, {len(means)})"
            )
    per_round = np.max(means) - means[actions]
    per_agent_curves = np.cumsum(per_round, axis=0)
    total_curve = per_agent_curves.sum(axis=1)
    mean_curve = per_agent_curves.mean(axis=1)
    per_agent_final = per_agent_curves[-1, :]
    return PopulationRegretSummary(
        total_final_regret=float(total_curve[-1]),
        mean_per_agent_final_regret=float(mean_curve[-1]),
        per_agent_final_regret=tuple(float(value) for value in per_agent_final),
        total_regret_curve=tuple(float(value) for value in total_curve),
        mean_regret_curve=tuple(float(value) for value in mean_curve),
        per_agent_regret_curves=tuple(
            tuple(float(value) for value in per_agent_curves[:, agent_index])
            for agent_index in range(actions.shape[1])
        ),
    )


def _validated_means(arm_means: Iterable[float]) -> np.ndarray:
    means = np.asarray(tuple(arm_means), dtype=float)
    if means.ndim != 1 or len(means) == 0:
        raise MetricError("arm_means must be a non-empty one-dimensional sequence")
    if np.any(~np.isfinite(means)):
        raise MetricError("arm_means must be finite")
    return means


def _validated_actions(actions: Iterable[int], num_arms: int) -> np.ndarray:
    action_tuple = tuple(actions)
    if not action_tuple:
        return np.asarray([], dtype=np.int64)
    for action in action_tuple:
        if not isinstance(action, int) or isinstance(action, bool):
            raise MetricError("actions must contain only integer arm indices")
        if not 0 <= action < num_arms:
            raise MetricError(
                f"action index {action} is outside valid range [0, {num_arms})"
            )
    return np.asarray(action_tuple, dtype=np.int64)
