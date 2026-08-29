from __future__ import annotations

from swarmgov.attacks import (
    AttackContext,
    ConstantInflationAttack,
    CoordinatedTargetAttack,
    NoAttackStrategy,
    apply_message_attacks,
)
from swarmgov.messages import Message


def test_no_attack_preserves_clean_message_exactly() -> None:
    message = _message()
    preserved = NoAttackStrategy().corrupt(message, _context())

    assert preserved is message


def test_constant_inflation_modifies_only_reward_information() -> None:
    original = _message()

    corrupted = ConstantInflationAttack(
        target_arm=1,
        inflated_mean=1.0,
    ).corrupt(original, _context())

    assert corrupted.sender == original.sender
    assert corrupted.receiver == original.receiver
    assert corrupted.round_index == original.round_index
    assert corrupted.counts == original.counts
    assert corrupted.metadata == original.metadata
    assert corrupted.reward_sums == (1.0, 3.0, 0.0)
    assert corrupted.empirical_means == (0.5, 1.0, 0.0)
    assert original.reward_sums == (1.0, 0.0, 0.0)


def test_constant_inflation_promotes_configured_target_arm() -> None:
    corrupted = ConstantInflationAttack(
        target_arm=1,
        inflated_mean=0.9,
    ).corrupt(_message(), _context())

    assert corrupted.empirical_means[1] == 0.9
    assert corrupted.empirical_means[1] > corrupted.empirical_means[0]


def test_coordinated_attackers_emit_consistent_target_messages() -> None:
    messages = (
        _message(sender=0, receiver=3),
        _message(sender=2, receiver=3),
    )

    application = apply_message_attacks(
        messages=messages,
        byzantine_nodes=(0, 2),
        strategy=CoordinatedTargetAttack(target_arm=1, inflated_mean=1.0),
        context=_context(),
    )

    assert tuple(message.empirical_means[1] for message in application.messages) == (
        1.0,
        1.0,
    )
    assert tuple(message.reward_sums[1] for message in application.messages) == (
        3.0,
        3.0,
    )


def test_honest_messages_remain_unchanged_and_diagnostics_are_recorded() -> None:
    byzantine_message = _message(sender=0, receiver=2)
    honest_message = _message(sender=1, receiver=2)

    application = apply_message_attacks(
        messages=(byzantine_message, honest_message),
        byzantine_nodes=(0,),
        strategy=ConstantInflationAttack(target_arm=1, inflated_mean=1.0),
        context=_context(),
        diagnostics_enabled=True,
    )

    assert application.messages[1] is honest_message
    assert application.messages[1] == honest_message
    assert len(application.diagnostics) == 1
    diagnostic = application.diagnostics[0]
    assert diagnostic.sender == 0
    assert diagnostic.receiver == 2
    assert diagnostic.round_index == 1
    assert diagnostic.strategy == "constant_inflation"
    assert diagnostic.original_message == byzantine_message
    assert diagnostic.corrupted_message == application.messages[0]


def _message(sender: int = 0, receiver: int = 1) -> Message:
    return Message(
        sender=sender,
        receiver=receiver,
        round_index=1,
        counts=(2, 3, 0),
        reward_sums=(1.0, 0.0, 0.0),
        metadata={"protocol": "one_hop_weighted_pooling_ucb1"},
    )


def _context() -> AttackContext:
    return AttackContext(round_index=1, num_arms=3)
