from __future__ import annotations

import numpy as np
import pytest

from swarmgov.aggregators.mean import AggregationError, aggregate_count_weighted_mean
from swarmgov.messages import make_message


def test_count_weighted_mean_matches_hand_computed_example() -> None:
    message = make_message(
        sender=1,
        receiver=0,
        round_index=1,
        counts=np.asarray([1, 2]),
        reward_sums=np.asarray([0.0, 1.0]),
    )

    aggregate = aggregate_count_weighted_mean(
        local_counts=np.asarray([1, 0]),
        local_reward_sums=np.asarray([1.0, 0.0]),
        messages=(message,),
    )

    assert aggregate.counts == (2, 2)
    assert aggregate.reward_sums == pytest.approx((1.0, 1.0))
    assert aggregate.empirical_means == pytest.approx((0.5, 0.5))


def test_count_weighted_mean_rejects_shape_mismatch() -> None:
    message = make_message(
        sender=1,
        receiver=0,
        round_index=1,
        counts=np.asarray([1, 2, 3]),
        reward_sums=np.asarray([0.0, 1.0, 2.0]),
    )

    with pytest.raises(AggregationError, match="does not match"):
        aggregate_count_weighted_mean(
            local_counts=np.asarray([1, 0]),
            local_reward_sums=np.asarray([1.0, 0.0]),
            messages=(message,),
        )
