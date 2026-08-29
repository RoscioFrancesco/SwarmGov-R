"""Count-weighted mean aggregation for decentralized baselines."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from swarmgov.aggregators.base import (
    AggregatedStatistics,
    AggregationDiagnostics,
    AggregationError,
    AggregationResult,
    validate_statistics,
)
from swarmgov.messages import Message


@dataclass(frozen=True)
class CountWeightedMeanAggregator:
    """Existing one-hop count-weighted pooling baseline."""

    method: str = "mean"

    def aggregate(
        self,
        *,
        local_counts: np.ndarray,
        local_reward_sums: np.ndarray,
        messages: Sequence[Message],
        round_index: int,
    ) -> AggregationResult:
        statistics = aggregate_count_weighted_mean(
            local_counts=local_counts,
            local_reward_sums=local_reward_sums,
            messages=messages,
            round_index=round_index,
        )
        diagnostics = AggregationDiagnostics(
            method=self.method,
            valid_sources_per_arm=_valid_sources_per_arm(
                local_counts=local_counts,
                messages=messages,
            ),
            aggregate_means=statistics.empirical_means,
            effective_counts=statistics.counts,
            trimmed_from_each_tail=tuple(0 for _ in statistics.counts),
            fallback_used_per_arm=tuple(False for _ in statistics.counts),
        )
        return AggregationResult(statistics=statistics, diagnostics=diagnostics)


def aggregate_count_weighted_mean(
    *,
    local_counts: np.ndarray,
    local_reward_sums: np.ndarray,
    messages: Sequence[Message],
    round_index: int | None = None,
) -> AggregatedStatistics:
    counts = np.asarray(local_counts, dtype=np.int64).copy()
    reward_sums = np.asarray(local_reward_sums, dtype=float).copy()
    validate_statistics(counts, reward_sums)

    for message in messages:
        if round_index is not None and message.round_index != round_index:
            raise AggregationError("message round does not match aggregation round")
        message_counts = np.asarray(message.counts, dtype=np.int64)
        message_sums = np.asarray(message.reward_sums, dtype=float)
        validate_statistics(message_counts, message_sums)
        if message_counts.shape != counts.shape:
            raise AggregationError("message arm count does not match local state")
        counts += message_counts
        reward_sums += message_sums

    means = np.zeros_like(reward_sums, dtype=float)
    observed = counts > 0
    means[observed] = reward_sums[observed] / counts[observed]
    return AggregatedStatistics(
        counts=tuple(int(value) for value in counts),
        reward_sums=tuple(float(value) for value in reward_sums),
        empirical_means=tuple(float(value) for value in means),
    )


def _valid_sources_per_arm(
    *,
    local_counts: np.ndarray,
    messages: Sequence[Message],
) -> tuple[int, ...]:
    counts = np.asarray(local_counts, dtype=np.int64)
    valid_sources = (counts > 0).astype(np.int64)
    for message in messages:
        message_counts = np.asarray(message.counts, dtype=np.int64)
        valid_sources += message_counts > 0
    return tuple(int(value) for value in valid_sources)
