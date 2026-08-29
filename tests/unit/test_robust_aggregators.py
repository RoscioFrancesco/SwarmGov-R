from __future__ import annotations

import numpy as np
import pytest

from swarmgov.aggregators import AggregationError, MedianAggregator
from swarmgov.aggregators.robust import TrimmedMeanAggregator
from swarmgov.messages import Message


def test_median_odd_number_of_values() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.2]),
        messages=(_message(1, 0.8), _message(2, 0.5)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.statistics.counts == (3,)
    assert result.statistics.reward_sums == pytest.approx((1.5,))


def test_median_even_number_of_values_averages_middle_pair() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.2]),
        messages=(_message(1, 0.4), _message(2, 0.6), _message(3, 0.8)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.statistics.counts == (4,)
    assert result.statistics.reward_sums == pytest.approx((2.0,))


def test_median_one_valid_value_returns_it_unchanged() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.7]),
        messages=(_message(1, 0.0, count=0),),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.7,))
    assert result.statistics.counts == (1,)


def test_median_no_valid_value_marks_arm_unobserved() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([0]),
        local_reward_sums=np.asarray([0.0]),
        messages=(_message(1, 0.0, count=0),),
        round_index=1,
    )

    assert result.statistics.counts == (0,)
    assert result.statistics.reward_sums == (0.0,)
    assert result.statistics.empirical_means == (0.0,)


def test_median_ignores_one_extreme_high_outlier() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.4]),
        messages=(_message(1, 0.45), _message(2, 1.0)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.45,))


def test_median_ignores_one_extreme_low_outlier() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.0]),
        messages=(_message(1, 0.45), _message(2, 0.5)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.45,))


def test_byzantine_count_inflation_does_not_add_median_votes() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.4]),
        messages=(
            _message(1, 0.9, count=1000),
            _message(2, 0.5, count=1),
        ),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.diagnostics.valid_sources_per_arm == (3,)
    assert result.diagnostics.effective_counts == (3,)


def test_unavailable_arm_estimates_are_excluded_not_zero() -> None:
    result = MedianAggregator().aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.8]),
        messages=(_message(1, 0.0, count=0),),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.8,))
    assert result.diagnostics.valid_sources_per_arm == (1,)


def test_trimmed_mean_removes_one_value_from_each_tail() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.1]),
        messages=(_message(1, 0.2), _message(2, 0.8), _message(3, 0.9)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.statistics.counts == (2,)
    assert result.diagnostics.trimmed_from_each_tail == (1,)
    assert result.diagnostics.fallback_used_per_arm == (False,)


def test_trimmed_mean_handles_duplicate_values() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.1]),
        messages=(_message(1, 0.5), _message(2, 0.5), _message(3, 0.9)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))


def test_trim_fraction_converts_with_floor_per_arm() -> None:
    result = TrimmedMeanAggregator(trim_fraction=0.2).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.1]),
        messages=(
            _message(1, 0.2),
            _message(2, 0.4),
            _message(3, 0.8),
            _message(4, 1.0),
        ),
        round_index=1,
    )

    assert result.diagnostics.trimmed_from_each_tail == (1,)
    assert result.statistics.empirical_means == pytest.approx(((0.2 + 0.4 + 0.8) / 3,))


def test_trimmed_mean_one_source_uses_median_fallback() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.7]),
        messages=(),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.7,))
    assert result.diagnostics.fallback_used_per_arm == (True,)


def test_trimmed_mean_two_sources_use_median_fallback() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.2]),
        messages=(_message(1, 0.8),),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.diagnostics.fallback_used_per_arm == (True,)


def test_trimmed_mean_requested_trimming_that_removes_all_values_falls_back() -> None:
    result = TrimmedMeanAggregator(trim_count=2).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.2]),
        messages=(_message(1, 0.8), _message(2, 1.0)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.8,))
    assert result.diagnostics.trimmed_from_each_tail == (0,)
    assert result.diagnostics.fallback_used_per_arm == (True,)


def test_trimmed_mean_no_fallback_when_enough_sources_exist() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.1]),
        messages=(_message(1, 0.5), _message(2, 0.9)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.5,))
    assert result.diagnostics.fallback_used_per_arm == (False,)


def test_trimmed_mean_removes_extreme_byzantine_value() -> None:
    result = TrimmedMeanAggregator(trim_count=1).aggregate(
        local_counts=np.asarray([1]),
        local_reward_sums=np.asarray([0.4]),
        messages=(_message(1, 0.45), _message(2, 0.5), _message(3, 1.0)),
        round_index=1,
    )

    assert result.statistics.empirical_means == pytest.approx((0.475,))


def test_aggregators_do_not_mutate_messages_or_local_state() -> None:
    counts = np.asarray([1])
    reward_sums = np.asarray([0.4])
    message = _message(1, 1.0)
    original_message = message.to_record()

    MedianAggregator().aggregate(
        local_counts=counts,
        local_reward_sums=reward_sums,
        messages=(message,),
        round_index=1,
    )

    assert counts.tolist() == [1]
    assert reward_sums.tolist() == [0.4]
    assert message.to_record() == original_message


def test_aggregator_outputs_are_deterministic_and_valid() -> None:
    kwargs = {
        "local_counts": np.asarray([1, 1]),
        "local_reward_sums": np.asarray([0.4, 0.7]),
        "messages": (_message(1, 1.0, arm_count=2),),
        "round_index": 1,
    }

    first = MedianAggregator().aggregate(**kwargs)
    second = MedianAggregator().aggregate(**kwargs)

    assert first == second
    assert all(0.0 <= value <= 1.0 for value in first.statistics.empirical_means)
    assert all(np.isfinite(value) for value in first.statistics.reward_sums)


def test_malformed_inputs_follow_validation_policy() -> None:
    with pytest.raises(AggregationError, match="reward_sums cannot exceed counts"):
        MedianAggregator().aggregate(
            local_counts=np.asarray([1]),
            local_reward_sums=np.asarray([2.0]),
            messages=(),
            round_index=1,
        )


def test_round_incompatible_messages_are_rejected() -> None:
    with pytest.raises(AggregationError, match="round"):
        MedianAggregator().aggregate(
            local_counts=np.asarray([1]),
            local_reward_sums=np.asarray([0.4]),
            messages=(_message(1, 0.5, round_index=2),),
            round_index=1,
        )


def _message(
    sender: int,
    mean: float,
    *,
    count: int = 1,
    round_index: int = 1,
    arm_count: int = 1,
) -> Message:
    counts = tuple(count for _ in range(arm_count))
    reward_sums = tuple(float(count) * mean for _ in range(arm_count))
    return Message(
        sender=sender,
        receiver=0,
        round_index=round_index,
        counts=counts,
        reward_sums=reward_sums,
        metadata={"protocol": "one_hop_weighted_pooling_ucb1"},
    )
