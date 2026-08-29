"""Communication scheduling and message routing."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from swarmgov.graphs import GeneratedGraph, directed_edges
from swarmgov.messages import Message, make_message


class CommunicationError(ValueError):
    """Raised when communication is configured incorrectly."""


def should_communicate(
    *,
    round_index: int,
    enabled: bool,
    interval: int,
) -> bool:
    if round_index <= 0:
        raise CommunicationError("round_index must be positive")
    if interval <= 0:
        raise CommunicationError("interval must be positive")
    return enabled and round_index % interval == 0


def build_round_messages(
    *,
    graph: GeneratedGraph,
    round_index: int,
    local_counts: Sequence[np.ndarray],
    local_reward_sums: Sequence[np.ndarray],
    protocol: str,
) -> tuple[Message, ...]:
    if (
        len(local_counts) != graph.num_nodes
        or len(local_reward_sums) != graph.num_nodes
    ):
        raise CommunicationError("local statistics must match graph node count")
    messages: list[Message] = []
    for sender, receiver in directed_edges(graph):
        messages.append(
            make_message(
                sender=sender,
                receiver=receiver,
                round_index=round_index,
                counts=local_counts[sender],
                reward_sums=local_reward_sums[sender],
                metadata={"protocol": protocol},
            )
        )
    return tuple(messages)


def inbound_messages_by_receiver(
    messages: Sequence[Message],
    *,
    num_nodes: int,
) -> dict[int, tuple[Message, ...]]:
    grouped: dict[int, list[Message]] = {node: [] for node in range(num_nodes)}
    for message in messages:
        if message.receiver not in grouped:
            raise CommunicationError("message receiver is outside graph node range")
        grouped[message.receiver].append(message)
    return {
        receiver: tuple(sorted(receiver_messages, key=lambda msg: msg.sender))
        for receiver, receiver_messages in grouped.items()
    }
