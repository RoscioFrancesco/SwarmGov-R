"""Message-level Byzantine attack strategies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from swarmgov.messages import Message


class AttackError(ValueError):
    """Raised when an attack strategy is invalid."""


@dataclass(frozen=True)
class AttackContext:
    """Context visible to an oblivious message-level attack."""

    round_index: int
    num_arms: int


class AttackStrategy(Protocol):
    """Interface for message-level Byzantine corruption."""

    @property
    def name(self) -> str:
        """Stable strategy identifier used in records and diagnostics."""

    def corrupt(self, message: Message, context: AttackContext) -> Message:
        """Return the message received by neighbors."""


@dataclass(frozen=True)
class AttackDiagnostic:
    """Diagnostic record for one corrupted outgoing message."""

    strategy: str
    sender: int
    receiver: int
    round_index: int
    original_message: Message
    corrupted_message: Message

    def to_record(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "sender": self.sender,
            "receiver": self.receiver,
            "round_index": self.round_index,
            "original_message": self.original_message.to_record(),
            "corrupted_message": self.corrupted_message.to_record(),
        }


@dataclass(frozen=True)
class AttackApplication:
    """Messages plus optional diagnostics after attack application."""

    messages: tuple[Message, ...]
    diagnostics: tuple[AttackDiagnostic, ...]


@dataclass(frozen=True)
class NoAttackStrategy:
    """Identity strategy for clean communication."""

    name: str = "no_attack"

    def corrupt(self, message: Message, context: AttackContext) -> Message:
        _validate_context(message, context)
        return message


@dataclass(frozen=True)
class ConstantInflationAttack:
    """Inflate the reported mean of one configured suboptimal arm."""

    target_arm: int
    inflated_mean: float = 1.0
    name: str = "constant_inflation"

    def __post_init__(self) -> None:
        _validate_target_attack(self.target_arm, self.inflated_mean)

    def corrupt(self, message: Message, context: AttackContext) -> Message:
        _validate_context(message, context)
        return _inflate_target_arm(
            message=message,
            target_arm=self.target_arm,
            inflated_mean=self.inflated_mean,
        )


@dataclass(frozen=True)
class CoordinatedTargetAttack:
    """Promote the same configured target arm from every Byzantine sender."""

    target_arm: int
    inflated_mean: float = 1.0
    name: str = "coordinated_target"

    def __post_init__(self) -> None:
        _validate_target_attack(self.target_arm, self.inflated_mean)

    def corrupt(self, message: Message, context: AttackContext) -> Message:
        _validate_context(message, context)
        return _inflate_target_arm(
            message=message,
            target_arm=self.target_arm,
            inflated_mean=self.inflated_mean,
        )


def build_attack_strategy(
    *,
    strategy: str,
    target_arm: int | None,
    inflated_mean: float,
) -> AttackStrategy:
    if strategy == "no_attack":
        return NoAttackStrategy()
    if target_arm is None:
        raise AttackError(f"{strategy} requires a target arm")
    if strategy == "constant_inflation":
        return ConstantInflationAttack(
            target_arm=target_arm,
            inflated_mean=inflated_mean,
        )
    if strategy == "coordinated_target":
        return CoordinatedTargetAttack(
            target_arm=target_arm,
            inflated_mean=inflated_mean,
        )
    raise AttackError(f"unsupported attack strategy: {strategy!r}")


def apply_message_attacks(
    *,
    messages: Sequence[Message],
    byzantine_nodes: Sequence[int],
    strategy: AttackStrategy,
    context: AttackContext,
    diagnostics_enabled: bool = False,
) -> AttackApplication:
    """Apply a strategy to outgoing messages from Byzantine senders only."""

    byzantine_set = set(byzantine_nodes)
    attacked_messages: list[Message] = []
    diagnostics: list[AttackDiagnostic] = []
    for message in messages:
        if message.sender not in byzantine_set:
            attacked_messages.append(message)
            continue
        corrupted = strategy.corrupt(message, context)
        attacked_messages.append(corrupted)
        if diagnostics_enabled:
            diagnostics.append(
                AttackDiagnostic(
                    strategy=strategy.name,
                    sender=message.sender,
                    receiver=message.receiver,
                    round_index=message.round_index,
                    original_message=message,
                    corrupted_message=corrupted,
                )
            )
    return AttackApplication(
        messages=tuple(attacked_messages),
        diagnostics=tuple(diagnostics),
    )


def _inflate_target_arm(
    *,
    message: Message,
    target_arm: int,
    inflated_mean: float,
) -> Message:
    if target_arm >= len(message.counts):
        raise AttackError("target_arm is outside the message arm range")
    reward_sums = list(message.reward_sums)
    count = message.counts[target_arm]
    reward_sums[target_arm] = float(count) * inflated_mean
    return Message(
        sender=message.sender,
        receiver=message.receiver,
        round_index=message.round_index,
        counts=message.counts,
        reward_sums=tuple(reward_sums),
        metadata=message.metadata,
    )


def _validate_target_attack(target_arm: int, inflated_mean: float) -> None:
    if (
        not isinstance(target_arm, int)
        or isinstance(target_arm, bool)
        or target_arm < 0
    ):
        raise AttackError("target_arm must be a non-negative integer")
    if (
        not isinstance(inflated_mean, int | float)
        or isinstance(inflated_mean, bool)
        or not 0.0 <= float(inflated_mean) <= 1.0
    ):
        raise AttackError("inflated_mean must be a number in [0, 1]")


def _validate_context(message: Message, context: AttackContext) -> None:
    if context.round_index != message.round_index:
        raise AttackError("attack context round does not match message round")
    if context.num_arms != len(message.counts):
        raise AttackError("attack context arm count does not match message")
