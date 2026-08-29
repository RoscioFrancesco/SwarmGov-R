from __future__ import annotations

import numpy as np
import pytest

from swarmgov.messages import Message, MessageError, make_message


def test_make_message_derives_empirical_means_and_payload_size() -> None:
    message = make_message(
        sender=0,
        receiver=1,
        round_index=3,
        counts=np.asarray([2, 0]),
        reward_sums=np.asarray([1.0, 0.0]),
    )

    assert message.empirical_means == (0.5, 0.0)
    assert message.scalar_payload_size == 4


def test_message_rejects_round_mismatch_shape() -> None:
    with pytest.raises(MessageError, match="equal lengths"):
        Message(
            sender=0,
            receiver=1,
            round_index=1,
            counts=(1, 2),
            reward_sums=(1.0,),
        )


def test_message_rejects_reward_sum_that_exceeds_count() -> None:
    with pytest.raises(MessageError, match="\\[0, count\\]"):
        Message(
            sender=0,
            receiver=1,
            round_index=1,
            counts=(2,),
            reward_sums=(3.0,),
        )
