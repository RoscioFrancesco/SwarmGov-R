"""Robust one-hop source-level aggregation baselines."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import floor

import numpy as np

from swarmgov.aggregators.base import (
    AggregationDiagnostics,
    AggregationError,
    AggregationResult,
    source_estimates_by_arm,
    statistics_from_means_and_counts,
)
from swarmgov.messages import Message


@dataclass(frozen=True)
class MedianAggregator:
    """Unweighted median over one empirical estimate per source."""

    method: str = "median"

    def aggregate(
        self,
        *,
        local_counts: np.ndarray,
        local_reward_sums: np.ndarray,
        messages: Sequence[Message],
        round_index: int,
    ) -> AggregationResult:
        estimates_by_arm = source_estimates_by_arm(
            local_counts=local_counts,
            local_reward_sums=local_reward_sums,
            messages=messages,
            round_index=round_index,
        )
        means: list[float] = []
        effective_counts: list[int] = []
        for estimates in estimates_by_arm:
            if not estimates:
                means.append(0.0)
                effective_counts.append(0)
                continue
            means.append(float(np.median(np.asarray(estimates, dtype=float))))
            effective_counts.append(len(estimates))

        statistics = statistics_from_means_and_counts(
            means=means,
            counts=effective_counts,
        )
        diagnostics = AggregationDiagnostics(
            method=self.method,
            valid_sources_per_arm=tuple(
                len(estimates) for estimates in estimates_by_arm
            ),
            aggregate_means=statistics.empirical_means,
            effective_counts=statistics.counts,
            trimmed_from_each_tail=tuple(0 for _ in statistics.counts),
            fallback_used_per_arm=tuple(False for _ in statistics.counts),
        )
        return AggregationResult(statistics=statistics, diagnostics=diagnostics)


@dataclass(frozen=True)
class TrimmedMeanAggregator:
    """Symmetric unweighted trimmed mean over source-level estimates."""

    trim_count: int | None = None
    trim_fraction: float | None = None
    small_neighborhood_policy: str = "median_fallback"
    method: str = "trimmed_mean"

    def __post_init__(self) -> None:
        if (self.trim_count is None) == (self.trim_fraction is None):
            raise AggregationError(
                "trimmed_mean requires exactly one of trim_count or trim_fraction"
            )
        if self.trim_count is not None and (
            not isinstance(self.trim_count, int)
            or isinstance(self.trim_count, bool)
            or self.trim_count < 0
        ):
            raise AggregationError("trim_count must be a non-negative integer")
        if (
            self.trim_fraction is not None
            and not 0.0 <= float(self.trim_fraction) <= 1.0
        ):
            raise AggregationError("trim_fraction must be in [0, 1]")
        if self.small_neighborhood_policy != "median_fallback":
            raise AggregationError(
                "small_neighborhood_policy must be 'median_fallback'"
            )

    def aggregate(
        self,
        *,
        local_counts: np.ndarray,
        local_reward_sums: np.ndarray,
        messages: Sequence[Message],
        round_index: int,
    ) -> AggregationResult:
        estimates_by_arm = source_estimates_by_arm(
            local_counts=local_counts,
            local_reward_sums=local_reward_sums,
            messages=messages,
            round_index=round_index,
        )
        means: list[float] = []
        effective_counts: list[int] = []
        trimmed_from_each_tail: list[int] = []
        fallback_used: list[bool] = []

        for estimates in estimates_by_arm:
            valid_count = len(estimates)
            if valid_count == 0:
                means.append(0.0)
                effective_counts.append(0)
                trimmed_from_each_tail.append(0)
                fallback_used.append(False)
                continue

            sorted_values = np.sort(np.asarray(estimates, dtype=float))
            requested_trim = self._trim_count_for(valid_count)
            if requested_trim * 2 >= valid_count:
                means.append(float(np.median(sorted_values)))
                effective_counts.append(valid_count)
                trimmed_from_each_tail.append(0)
                fallback_used.append(True)
                continue

            retained = sorted_values[requested_trim : valid_count - requested_trim]
            means.append(float(np.mean(retained)))
            effective_counts.append(int(len(retained)))
            trimmed_from_each_tail.append(requested_trim)
            fallback_used.append(False)

        statistics = statistics_from_means_and_counts(
            means=means,
            counts=effective_counts,
        )
        diagnostics = AggregationDiagnostics(
            method=self.method,
            valid_sources_per_arm=tuple(
                len(estimates) for estimates in estimates_by_arm
            ),
            aggregate_means=statistics.empirical_means,
            effective_counts=statistics.counts,
            trimmed_from_each_tail=tuple(trimmed_from_each_tail),
            fallback_used_per_arm=tuple(fallback_used),
        )
        return AggregationResult(statistics=statistics, diagnostics=diagnostics)

    def _trim_count_for(self, valid_count: int) -> int:
        if self.trim_count is not None:
            return self.trim_count
        if self.trim_fraction is None:
            raise AggregationError("trim_fraction unexpectedly missing")
        return int(floor(float(self.trim_fraction) * valid_count))
