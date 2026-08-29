"""Recovery-time metrics for dynamic-topology runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


class RecoveryMetricError(ValueError):
    """Raised when recovery metric inputs are malformed."""


@dataclass(frozen=True)
class RecoverySummary:
    enabled: bool
    change_round: int | None
    baseline_window: int
    recovery_window: int
    tolerance: float
    pre_change_reference: float | None
    recovered: bool
    recovery_round: int | None
    post_change_rounds_evaluated: int

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def summarize_recovery_time(
    mean_regret_curve: tuple[float, ...],
    *,
    change_round: int | None,
    enabled: bool,
    baseline_window: int = 5,
    recovery_window: int = 5,
    tolerance: float = 0.05,
) -> RecoverySummary:
    """Find when post-change per-round regret returns near pre-change behavior.

    The metric uses the cumulative mean honest regret curve, derives per-round
    increments, computes a pre-change reference over the window immediately
    before the event, and returns the first post-change round whose sustained
    window is within `reference + tolerance`.
    """

    if not enabled:
        return RecoverySummary(
            enabled=False,
            change_round=None,
            baseline_window=baseline_window,
            recovery_window=recovery_window,
            tolerance=tolerance,
            pre_change_reference=None,
            recovered=False,
            recovery_round=None,
            post_change_rounds_evaluated=0,
        )
    if change_round is None:
        raise RecoveryMetricError("enabled recovery metrics require a change_round")
    if baseline_window <= 0 or recovery_window <= 0:
        raise RecoveryMetricError("recovery windows must be positive")
    if tolerance < 0.0 or not np.isfinite(tolerance):
        raise RecoveryMetricError("tolerance must be non-negative and finite")

    cumulative = np.asarray(mean_regret_curve, dtype=float)
    if cumulative.ndim != 1 or len(cumulative) == 0:
        raise RecoveryMetricError("mean_regret_curve must be a non-empty sequence")
    if np.any(~np.isfinite(cumulative)):
        raise RecoveryMetricError("mean_regret_curve must contain finite values")
    if not 0 < change_round < len(cumulative):
        raise RecoveryMetricError("change_round must be inside the regret curve")

    per_round = np.diff(np.concatenate(([0.0], cumulative)))
    reference_start = max(0, change_round - baseline_window)
    reference_end = change_round
    reference_values = per_round[reference_start:reference_end]
    pre_change_reference = float(np.mean(reference_values))

    first_start = change_round
    last_start = len(per_round) - recovery_window
    recovery_round: int | None = None
    for start_index in range(first_start, last_start + 1):
        window = per_round[start_index : start_index + recovery_window]
        if float(np.mean(window)) <= pre_change_reference + tolerance:
            recovery_round = start_index + 1
            break

    return RecoverySummary(
        enabled=True,
        change_round=change_round,
        baseline_window=baseline_window,
        recovery_window=recovery_window,
        tolerance=tolerance,
        pre_change_reference=pre_change_reference,
        recovered=recovery_round is not None,
        recovery_round=recovery_round,
        post_change_rounds_evaluated=max(0, len(per_round) - change_round),
    )
