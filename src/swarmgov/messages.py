"""Typed communication messages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


class MessageError(ValueError):
    """Raised when a message is malformed."""


@dataclass(frozen=True)
class Message:
    """Clean communication message.

    ``counts`` and ``reward_sums`` are the authoritative transmitted per-arm
    fields. ``empirical_means`` is derived locally for diagnostics and result
    records; aggregation code must not trust it as an independent source.
    """

    sender: int
    receiver: int
    round_index: int
    counts: tuple[int, ...]
    reward_sums: tuple[float, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    empirical_means: tuple[float, ...] = field(init=False)

    def __post_init__(self) -> None:
        _validate_node("sender", self.sender)
        _validate_node("receiver", self.receiver)
        if self.sender == self.receiver:
            raise MessageError("sender and receiver must differ")
        if not isinstance(self.round_index, int) or self.round_index <= 0:
            raise MessageError("round_index must be a positive integer")
        if not self.counts:
            raise MessageError("message must contain at least one arm")
        if len(self.counts) != len(self.reward_sums):
            raise MessageError("counts and reward_sums must have equal lengths")
        empirical_means = []
        for count, reward_sum in zip(
            self.counts,
            self.reward_sums,
            strict=True,
        ):
            empirical_means.append(_derive_empirical_mean(count, reward_sum))
        object.__setattr__(self, "empirical_means", tuple(empirical_means))

    @property
    def scalar_payload_size(self) -> int:
        return len(self.counts) + len(self.reward_sums)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def make_message(
    *,
    sender: int,
    receiver: int,
    round_index: int,
    counts: np.ndarray,
    reward_sums: np.ndarray,
    metadata: Mapping[str, Any] | None = None,
) -> Message:
    counts_array = np.asarray(counts, dtype=np.int64)
    sums_array = np.asarray(reward_sums, dtype=float)
    if counts_array.shape != sums_array.shape or counts_array.ndim != 1:
        raise MessageError("counts and reward_sums must be one-dimensional matches")
    return Message(
        sender=sender,
        receiver=receiver,
        round_index=round_index,
        counts=tuple(int(value) for value in counts_array),
        reward_sums=tuple(float(value) for value in sums_array),
        metadata={} if metadata is None else dict(metadata),
    )


def _validate_node(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MessageError(f"{name} must be a non-negative integer")


def _derive_empirical_mean(count: int, reward_sum: float) -> float:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise MessageError("counts must be non-negative integers")
    if not isinstance(reward_sum, int | float) or not np.isfinite(reward_sum):
        raise MessageError("reward_sums must be finite numbers")
    reward_sum_float = float(reward_sum)
    if reward_sum_float < 0.0 or reward_sum_float > count:
        raise MessageError("reward_sums must be in [0, count]")
    if count == 0:
        if reward_sum_float != 0.0:
            raise MessageError("unobserved arms must have zero reward sum")
        return 0.0
    return reward_sum_float / count
