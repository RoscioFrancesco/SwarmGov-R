from __future__ import annotations

import numpy as np
import pytest

from swarmgov.metrics.regret import (
    MetricError,
    cumulative_expected_regret,
    expected_regret_for_arm,
    per_round_expected_regret,
    summarize_population_regret,
    summarize_regret,
)


def test_expected_regret_matches_hand_computed_example() -> None:
    means = [0.8, 0.5, 0.2]
    actions = [0, 1, 2, 1]

    np.testing.assert_allclose(
        per_round_expected_regret(means, actions),
        [0.0, 0.3, 0.6, 0.3],
    )
    np.testing.assert_allclose(
        cumulative_expected_regret(means, actions),
        [0.0, 0.3, 0.9, 1.2],
    )

    summary = summarize_regret(means, actions)
    assert summary.final_regret == pytest.approx(1.2)
    assert summary.regret_curve == pytest.approx((0.0, 0.3, 0.9, 1.2))


def test_expected_regret_for_arm_rejects_out_of_range_action() -> None:
    with pytest.raises(MetricError, match="outside"):
        expected_regret_for_arm([0.8, 0.5], 2)


def test_empty_action_sequence_has_zero_final_regret() -> None:
    summary = summarize_regret([0.8, 0.5], [])

    assert summary.final_regret == 0.0
    assert summary.regret_curve == ()


def test_population_regret_matches_hand_computed_example() -> None:
    summary = summarize_population_regret(
        [0.8, 0.5],
        [
            [0, 1],
            [1, 1],
        ],
    )

    assert summary.per_agent_final_regret == pytest.approx((0.3, 0.6))
    assert summary.total_regret_curve == pytest.approx((0.3, 0.9))
    assert summary.mean_regret_curve == pytest.approx((0.15, 0.45))
    assert summary.total_final_regret == pytest.approx(0.9)
