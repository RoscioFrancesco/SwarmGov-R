from __future__ import annotations

import numpy as np

from swarmgov.attacks.placement import byzantine_count, select_byzantine_nodes
from swarmgov.graphs import GeneratedGraph


def test_random_byzantine_placement_is_reproducible() -> None:
    graph = _manual_graph(
        num_nodes=6,
        edges=((0, 1), (1, 2), (2, 3), (3, 4), (4, 5)),
    )

    first = select_byzantine_nodes(
        graph=graph,
        fraction=0.5,
        policy="random",
        rng=np.random.default_rng(123),
    )
    second = select_byzantine_nodes(
        graph=graph,
        fraction=0.5,
        policy="random",
        rng=np.random.default_rng(123),
    )

    assert first == second
    assert len(first) == 3
    assert first == tuple(sorted(first))


def test_degree_centrality_placement_selects_expected_nodes() -> None:
    graph = _manual_graph(
        num_nodes=6,
        edges=((0, 1), (0, 2), (0, 3), (2, 4), (2, 5)),
    )

    selected = select_byzantine_nodes(
        graph=graph,
        fraction=0.34,
        policy="degree_centrality",
        rng=np.random.default_rng(999),
    )

    assert selected == (0, 2)


def test_byzantine_count_uses_floor_fraction() -> None:
    assert byzantine_count(25, 0.1) == 2
    assert byzantine_count(25, 0.2) == 5
    assert byzantine_count(25, 0.3) == 7


def _manual_graph(
    *,
    num_nodes: int,
    edges: tuple[tuple[int, int], ...],
) -> GeneratedGraph:
    return GeneratedGraph(
        family="manual",
        num_nodes=num_nodes,
        edges=tuple(sorted((min(u, v), max(u, v)) for u, v in edges)),
        graph_seed=0,
        parameters={},
        connected=True,
        components=(tuple(range(num_nodes)),),
    )
