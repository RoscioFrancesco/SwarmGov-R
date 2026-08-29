"""Communication cost metrics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from swarmgov.messages import Message


@dataclass(frozen=True)
class CommunicationSummary:
    messages_sent: int
    scalar_values_sent: int
    messages_per_agent: tuple[int, ...]
    scalar_values_per_agent: tuple[int, ...]

    def to_record(self) -> dict[str, object]:
        return {
            "messages_sent": self.messages_sent,
            "scalar_values_sent": self.scalar_values_sent,
            "messages_per_agent": list(self.messages_per_agent),
            "scalar_values_per_agent": list(self.scalar_values_per_agent),
        }


def summarize_communication(
    messages: Sequence[Message],
    *,
    num_agents: int,
) -> CommunicationSummary:
    messages_per_agent = [0 for _ in range(num_agents)]
    scalar_values_per_agent = [0 for _ in range(num_agents)]
    for message in messages:
        messages_per_agent[message.sender] += 1
        scalar_values_per_agent[message.sender] += message.scalar_payload_size
    return CommunicationSummary(
        messages_sent=len(messages),
        scalar_values_sent=sum(scalar_values_per_agent),
        messages_per_agent=tuple(messages_per_agent),
        scalar_values_per_agent=tuple(scalar_values_per_agent),
    )
