from __future__ import annotations

import numpy as np
import pytest

from swarmgov.communication import (
    CommunicationError,
    build_round_messages,
    inbound_messages_by_receiver,
    should_communicate,
)
from swarmgov.graphs import generate_static_graph
from swarmgov.metrics.communication import summarize_communication


def test_communication_schedule_uses_interval() -> None:
    assert should_communicate(round_index=2, enabled=True, interval=2)
    assert not should_communicate(round_index=3, enabled=True, interval=2)
    assert not should_communicate(round_index=2, enabled=False, interval=2)


def test_communication_schedule_rejects_invalid_interval() -> None:
    with pytest.raises(CommunicationError, match="interval"):
        should_communicate(round_index=1, enabled=True, interval=0)


def test_build_round_messages_sends_one_directed_message_per_edge() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=3,
        parameters={},
        rng=np.random.default_rng(0),
    )
    counts = [np.asarray([1, 0]) for _ in range(3)]
    sums = [np.asarray([1.0, 0.0]) for _ in range(3)]

    messages = build_round_messages(
        graph=graph,
        round_index=1,
        local_counts=counts,
        local_reward_sums=sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    inbound = inbound_messages_by_receiver(messages, num_nodes=3)
    summary = summarize_communication(messages, num_agents=3)

    assert len(messages) == 6
    assert all(len(receiver_messages) == 2 for receiver_messages in inbound.values())
    assert summary.messages_per_agent == (2, 2, 2)
    assert summary.scalar_values_sent == 24
