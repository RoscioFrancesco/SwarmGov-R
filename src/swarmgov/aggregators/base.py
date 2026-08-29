"""Common interfaces and helpers for one-hop aggregation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from swarmgov.messages import Message


class AggregationError(ValueError):
    """Raised when aggregation inputs are invalid."""


@dataclass(frozen=True)
class AggregatedStatistics:
    counts: tuple[int, ...]
    reward_sums: tuple[float, ...]
    empirical_means: tuple[float, ...]

    def counts_array(self) -> np.ndarray:
        return np.asarray(self.counts, dtype=np.int64)

    def reward_sums_array(self) -> np.ndarray:
        return np.asarray(self.reward_sums, dtype=float)


@dataclass(frozen=True)
class AggregationDiagnostics:
    method: str
    valid_sources_per_arm: tuple[int, ...]
    aggregate_means: tuple[float, ...]
    effective_counts: tuple[int, ...]
    trimmed_from_each_tail: tuple[int, ...]
    fallback_used_per_arm: tuple[bool, ...]
    invalid_messages_rejected: int = 0

    def to_record(self) -> dict[str, object]:
        return {
            "method": self.method,
            "valid_sources_per_arm": list(self.valid_sources_per_arm),
            "aggregate_means": list(self.aggregate_means),
            "effective_counts": list(self.effective_counts),
            "trimmed_from_each_tail": list(self.trimmed_from_each_tail),
            "fallback_used_per_arm": list(self.fallback_used_per_arm),
            "invalid_messages_rejected": self.invalid_messages_rejected,
        }


@dataclass(frozen=True)
class AggregationResult:
    statistics: AggregatedStatistics
    diagnostics: AggregationDiagnostics


class Aggregator(Protocol):
    """Stateless one-hop aggregation interface."""

    method: str

    def aggregate(
        self,
        *,
        local_counts: np.ndarray,
        local_reward_sums: np.ndarray,
        messages: Sequence[Message],
        round_index: int,
    ) -> AggregationResult:
        """Aggregate local statistics with latest one-hop messages."""


def validate_statistics(counts: np.ndarray, reward_sums: np.ndarray) -> None:
    if counts.ndim != 1 or reward_sums.ndim != 1 or counts.shape != reward_sums.shape:
        raise AggregationError("counts and reward_sums must be one-dimensional matches")
    if np.any(counts < 0):
        raise AggregationError("counts must be non-negative")
    if np.any(~np.isfinite(reward_sums)) or np.any(reward_sums < 0):
        raise AggregationError("reward_sums must be finite and non-negative")
    if np.any(reward_sums > counts):
        raise AggregationError("reward_sums cannot exceed counts")


def source_estimates_by_arm(
    *,
    local_counts: np.ndarray,
    local_reward_sums: np.ndarray,
    messages: Sequence[Message],
    round_index: int,
) -> tuple[tuple[float, ...], ...]:
    counts = np.asarray(local_counts, dtype=np.int64).copy()
    reward_sums = np.asarray(local_reward_sums, dtype=float).copy()
    validate_statistics(counts, reward_sums)

    estimates: list[list[float]] = [[] for _ in range(len(counts))]
    _append_source_estimates(estimates, counts, reward_sums)
    for message in messages:
        if message.round_index != round_index:
            raise AggregationError("message round does not match aggregation round")
        message_counts = np.asarray(message.counts, dtype=np.int64)
        message_sums = np.asarray(message.reward_sums, dtype=float)
        validate_statistics(message_counts, message_sums)
        if message_counts.shape != counts.shape:
            raise AggregationError("message arm count does not match local state")
        _append_source_estimates(estimates, message_counts, message_sums)
    return tuple(tuple(arm_estimates) for arm_estimates in estimates)


def statistics_from_means_and_counts(
    *,
    means: Sequence[float],
    counts: Sequence[int],
) -> AggregatedStatistics:
    count_array = np.asarray(tuple(counts), dtype=np.int64)
    means_array = np.asarray(tuple(means), dtype=float)
    if count_array.ndim != 1 or means_array.ndim != 1:
        raise AggregationError("means and counts must be one-dimensional")
    if count_array.shape != means_array.shape:
        raise AggregationError("means and counts must have matching shapes")
    if np.any(count_array < 0):
        raise AggregationError("effective counts must be non-negative")
    if np.any(~np.isfinite(means_array)):
        raise AggregationError("aggregate means must be finite")
    if np.any(means_array < 0.0) or np.any(means_array > 1.0):
        raise AggregationError("aggregate means must be in [0, 1]")

    reward_sums = means_array * count_array
    reward_sums[count_array == 0] = 0.0
    validate_statistics(count_array, reward_sums)
    return AggregatedStatistics(
        counts=tuple(int(value) for value in count_array),
        reward_sums=tuple(float(value) for value in reward_sums),
        empirical_means=tuple(float(value) for value in means_array),
    )


def _append_source_estimates(
    estimates: list[list[float]],
    counts: np.ndarray,
    reward_sums: np.ndarray,
) -> None:
    observed = np.flatnonzero(counts > 0)
    for arm in observed:
        estimates[int(arm)].append(float(reward_sums[arm] / counts[arm]))
