"""Aggregation rules."""

from swarmgov.aggregators.base import (
    AggregatedStatistics,
    AggregationDiagnostics,
    AggregationError,
    AggregationResult,
    Aggregator,
)
from swarmgov.aggregators.mean import (
    CountWeightedMeanAggregator,
    aggregate_count_weighted_mean,
)
from swarmgov.aggregators.robust import MedianAggregator, TrimmedMeanAggregator


def build_aggregator(
    *,
    method: str,
    trim_count: int | None = None,
    trim_fraction: float | None = None,
    small_neighborhood_policy: str = "median_fallback",
) -> Aggregator:
    if method == "mean":
        return CountWeightedMeanAggregator()
    if method == "median":
        return MedianAggregator()
    if method == "trimmed_mean":
        return TrimmedMeanAggregator(
            trim_count=trim_count,
            trim_fraction=trim_fraction,
            small_neighborhood_policy=small_neighborhood_policy,
        )
    raise AggregationError(f"unsupported aggregation method: {method!r}")


__all__ = [
    "AggregatedStatistics",
    "AggregationDiagnostics",
    "AggregationError",
    "AggregationResult",
    "Aggregator",
    "CountWeightedMeanAggregator",
    "MedianAggregator",
    "TrimmedMeanAggregator",
    "aggregate_count_weighted_mean",
    "build_aggregator",
]
