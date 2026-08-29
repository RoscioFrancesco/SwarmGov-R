from __future__ import annotations

import numpy as np

from swarmgov.attacks import (
    AttackContext,
    ConstantInflationAttack,
    apply_message_attacks,
)
from swarmgov.communication import build_round_messages, inbound_messages_by_receiver
from swarmgov.graphs import generate_static_graph
from swarmgov.simulation import _apply_one_hop_weighted_pooling


def test_attacked_message_moves_one_hop_pooling_toward_target_arm() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=2,
        parameters={},
        rng=np.random.default_rng(0),
    )
    local_counts = [np.asarray([1, 1]), np.asarray([1, 1])]
    local_sums = [np.asarray([0.0, 0.0]), np.asarray([0.0, 0.0])]
    clean_messages = build_round_messages(
        graph=graph,
        round_index=1,
        local_counts=local_counts,
        local_reward_sums=local_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )

    clean_counts, clean_sums = _apply_one_hop_weighted_pooling(
        local_counts=local_counts,
        local_reward_sums=local_sums,
        inbound_messages=inbound_messages_by_receiver(clean_messages, num_nodes=2),
    )
    attacked_messages = apply_message_attacks(
        messages=clean_messages,
        byzantine_nodes=(1,),
        strategy=ConstantInflationAttack(target_arm=1, inflated_mean=1.0),
        context=AttackContext(round_index=1, num_arms=2),
    ).messages
    attacked_counts, attacked_sums = _apply_one_hop_weighted_pooling(
        local_counts=local_counts,
        local_reward_sums=local_sums,
        inbound_messages=inbound_messages_by_receiver(attacked_messages, num_nodes=2),
    )

    assert clean_counts[0].tolist() == [2, 2]
    assert attacked_counts[0].tolist() == [2, 2]
    assert clean_sums[0].tolist() == [0.0, 0.0]
    assert attacked_sums[0].tolist() == [0.0, 1.0]
    assert attacked_sums[0][1] / attacked_counts[0][1] == 0.5
