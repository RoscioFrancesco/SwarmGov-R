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


def test_repeated_cumulative_neighbor_snapshots_are_not_double_counted() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=2,
        parameters={},
        rng=np.random.default_rng(0),
    )

    round_one_counts = [np.asarray([1]), np.asarray([1])]
    round_one_sums = [np.asarray([1.0]), np.asarray([0.0])]
    round_one_messages = build_round_messages(
        graph=graph,
        round_index=1,
        local_counts=round_one_counts,
        local_reward_sums=round_one_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    round_one_inbound = inbound_messages_by_receiver(round_one_messages, num_nodes=2)

    pooled_counts, pooled_sums = _apply_one_hop_weighted_pooling(
        local_counts=round_one_counts,
        local_reward_sums=round_one_sums,
        inbound_messages=round_one_inbound,
    )

    assert [counts.tolist() for counts in pooled_counts] == [[2], [2]]
    assert [sums.tolist() for sums in pooled_sums] == [[1.0], [1.0]]

    repeated_messages = build_round_messages(
        graph=graph,
        round_index=2,
        local_counts=round_one_counts,
        local_reward_sums=round_one_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    repeated_inbound = inbound_messages_by_receiver(repeated_messages, num_nodes=2)

    repeated_counts, repeated_sums = _apply_one_hop_weighted_pooling(
        local_counts=round_one_counts,
        local_reward_sums=round_one_sums,
        inbound_messages=repeated_inbound,
    )

    assert [counts.tolist() for counts in repeated_counts] == [[2], [2]]
    assert [sums.tolist() for sums in repeated_sums] == [[1.0], [1.0]]


def test_growing_cumulative_snapshots_pool_once_per_current_observation() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=2,
        parameters={},
        rng=np.random.default_rng(0),
    )

    round_two_counts = [np.asarray([2]), np.asarray([2])]
    round_two_sums = [np.asarray([2.0]), np.asarray([1.0])]
    messages = build_round_messages(
        graph=graph,
        round_index=2,
        local_counts=round_two_counts,
        local_reward_sums=round_two_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    inbound = inbound_messages_by_receiver(messages, num_nodes=2)

    pooled_counts, pooled_sums = _apply_one_hop_weighted_pooling(
        local_counts=round_two_counts,
        local_reward_sums=round_two_sums,
        inbound_messages=inbound,
    )

    assert [counts.tolist() for counts in pooled_counts] == [[4], [4]]
    assert [sums.tolist() for sums in pooled_sums] == [[3.0], [3.0]]


def test_corrupted_cumulative_snapshots_are_not_double_counted() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=2,
        parameters={},
        rng=np.random.default_rng(0),
    )

    local_counts = [np.asarray([1, 1]), np.asarray([1, 1])]
    local_sums = [np.asarray([0.0, 0.0]), np.asarray([0.0, 0.0])]

    first_counts, first_sums = _pool_after_attack(
        graph=graph,
        round_index=1,
        local_counts=local_counts,
        local_sums=local_sums,
    )
    repeated_counts, repeated_sums = _pool_after_attack(
        graph=graph,
        round_index=2,
        local_counts=local_counts,
        local_sums=local_sums,
    )

    assert [counts.tolist() for counts in first_counts] == [[2, 2], [2, 2]]
    assert [counts.tolist() for counts in repeated_counts] == [[2, 2], [2, 2]]
    assert [sums.tolist() for sums in first_sums] == [[0.0, 1.0], [0.0, 0.0]]
    assert [sums.tolist() for sums in repeated_sums] == [[0.0, 1.0], [0.0, 0.0]]


def _pool_after_attack(
    *,
    graph,
    round_index: int,
    local_counts: list[np.ndarray],
    local_sums: list[np.ndarray],
):
    messages = build_round_messages(
        graph=graph,
        round_index=round_index,
        local_counts=local_counts,
        local_reward_sums=local_sums,
        protocol="one_hop_weighted_pooling_ucb1",
    )
    attacked_messages = apply_message_attacks(
        messages=messages,
        byzantine_nodes=(1,),
        strategy=ConstantInflationAttack(target_arm=1, inflated_mean=1.0),
        context=AttackContext(round_index=round_index, num_arms=2),
    ).messages
    return _apply_one_hop_weighted_pooling(
        local_counts=local_counts,
        local_reward_sums=local_sums,
        inbound_messages=inbound_messages_by_receiver(attacked_messages, num_nodes=2),
    )
