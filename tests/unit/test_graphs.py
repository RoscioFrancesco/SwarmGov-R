from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from swarmgov.graphs import (
    GeneratedGraph,
    GraphError,
    generate_static_graph,
    neighbors_by_node,
    rewire_graph_once,
)


def test_complete_graph_has_expected_edges() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=4,
        parameters={},
        rng=np.random.default_rng(1),
    )

    assert graph.num_nodes == 4
    assert len(graph.edges) == 6
    assert graph.connected is True


def test_ring_graph_has_degree_two_for_each_node() -> None:
    graph = generate_static_graph(
        family="ring",
        num_nodes=5,
        parameters={},
        rng=np.random.default_rng(1),
    )
    nx_graph = graph.to_networkx()

    assert all(degree == 2 for _, degree in nx_graph.degree())
    assert neighbors_by_node(graph)[0] == (1, 4)


def test_random_graph_families_are_deterministic_under_same_rng_seed() -> None:
    first = generate_static_graph(
        family="scale_free",
        num_nodes=8,
        parameters={"m": 2},
        rng=np.random.default_rng(99),
    )
    second = generate_static_graph(
        family="scale_free",
        num_nodes=8,
        parameters={"m": 2},
        rng=np.random.default_rng(99),
    )

    assert first.graph_seed == second.graph_seed
    assert first.edges == second.edges


def test_small_world_graph_is_connected() -> None:
    graph = generate_static_graph(
        family="small_world",
        num_nodes=8,
        parameters={"k": 2, "p": 0.25},
        rng=np.random.default_rng(2),
    )

    assert nx.is_connected(graph.to_networkx())


def test_small_world_default_k_is_valid_for_four_nodes() -> None:
    graph = generate_static_graph(
        family="small_world",
        num_nodes=4,
        parameters={},
        rng=np.random.default_rng(2),
    )

    assert graph.parameters["k"] == 2
    assert graph.connected


def test_small_world_rejects_odd_k() -> None:
    with pytest.raises(GraphError, match="even"):
        generate_static_graph(
            family="small_world",
            num_nodes=5,
            parameters={"k": 3, "p": 0.2},
            rng=np.random.default_rng(0),
        )


def test_rewire_graph_once_is_deterministic_and_connected() -> None:
    graph = generate_static_graph(
        family="ring",
        num_nodes=8,
        parameters={},
        rng=np.random.default_rng(10),
    )

    first_graph, first_event = rewire_graph_once(
        graph=graph,
        change_round=4,
        rewire_fraction=0.25,
        preserve_connectivity=True,
        rng=np.random.default_rng(99),
    )
    second_graph, second_event = rewire_graph_once(
        graph=graph,
        change_round=4,
        rewire_fraction=0.25,
        preserve_connectivity=True,
        rng=np.random.default_rng(99),
    )

    assert first_graph.edges == second_graph.edges
    assert first_event.to_record() == second_event.to_record()
    assert first_event.edges_before == graph.edges
    assert first_event.edges_after == first_graph.edges
    assert first_event.edges_after != graph.edges
    assert len(first_event.removed_edges) == first_event.requested_edge_changes
    assert len(first_event.added_edges) == first_event.requested_edge_changes
    assert first_graph.num_nodes == graph.num_nodes
    assert first_graph.connected is True
    assert first_event.connected_before is True
    assert first_event.connected_after is True


def test_rewire_graph_records_components_when_connectivity_is_not_required() -> None:
    graph = GeneratedGraph(
        family="manual",
        num_nodes=4,
        edges=((0, 1),),
        graph_seed=0,
        parameters={},
        connected=False,
        components=((0, 1), (2,), (3,)),
    )

    changed_graph, event = rewire_graph_once(
        graph=graph,
        change_round=2,
        rewire_fraction=1.0,
        preserve_connectivity=False,
        rng=np.random.default_rng(3),
    )

    assert changed_graph.num_nodes == 4
    assert event.connected_after is False
    assert len(event.components_after) > 1
    assert event.edges_after == changed_graph.edges


def test_rewire_graph_rejects_complete_graph_no_op() -> None:
    graph = generate_static_graph(
        family="complete",
        num_nodes=4,
        parameters={},
        rng=np.random.default_rng(4),
    )

    with pytest.raises(GraphError, match="no alternate"):
        rewire_graph_once(
            graph=graph,
            change_round=2,
            rewire_fraction=0.25,
            preserve_connectivity=True,
            rng=np.random.default_rng(5),
        )


def test_rewire_graph_rejects_fraction_larger_than_available_new_edges() -> None:
    graph = GeneratedGraph(
        family="manual",
        num_nodes=4,
        edges=((0, 1), (0, 2), (0, 3), (1, 2), (1, 3)),
        graph_seed=0,
        parameters={},
        connected=True,
        components=((0, 1, 2, 3),),
    )

    with pytest.raises(GraphError, match="pre-change non-edges"):
        rewire_graph_once(
            graph=graph,
            change_round=2,
            rewire_fraction=0.5,
            preserve_connectivity=True,
            rng=np.random.default_rng(5),
        )
