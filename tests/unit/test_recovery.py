from __future__ import annotations

import numpy as np
import pytest

from swarmgov.metrics.recovery import RecoveryMetricError, summarize_recovery_time


def test_recovery_time_matches_hand_computed_curve() -> None:
    per_round_mean_regret = [0.0, 0.0, 0.0, 0.3, 0.2, 0.0, 0.0, 0.1]
    curve = tuple(float(value) for value in np.cumsum(per_round_mean_regret))

    summary = summarize_recovery_time(
        curve,
        enabled=True,
        change_round=4,
        baseline_window=3,
        recovery_window=2,
        tolerance=0.05,
    )

    assert summary.pre_change_reference == pytest.approx(0.1)
    assert summary.recovered is True
    assert summary.recovery_round == 5
    assert summary.post_change_rounds_evaluated == 4


def test_recovery_time_records_unrecovered_runs() -> None:
    per_round_mean_regret = [0.0, 0.0, 0.0, 0.3, 0.2, 0.2, 0.2, 0.2]
    curve = tuple(float(value) for value in np.cumsum(per_round_mean_regret))

    summary = summarize_recovery_time(
        curve,
        enabled=True,
        change_round=4,
        baseline_window=3,
        recovery_window=2,
        tolerance=0.05,
    )

    assert summary.recovered is False
    assert summary.recovery_round is None


def test_recovery_time_disabled_record_is_explicit() -> None:
    summary = summarize_recovery_time(
        (0.1, 0.2),
        enabled=False,
        change_round=None,
    )

    assert summary.enabled is False
    assert summary.pre_change_reference is None
    assert summary.recovered is False


def test_recovery_time_rejects_missing_change_round_when_enabled() -> None:
    with pytest.raises(RecoveryMetricError, match="change_round"):
        summarize_recovery_time((0.1, 0.2), enabled=True, change_round=None)
