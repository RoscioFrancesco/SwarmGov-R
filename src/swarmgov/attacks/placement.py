"""Deterministic Byzantine-node placement policies."""

from __future__ import annotations

from math import floor, isfinite

import numpy as np

from swarmgov.graphs import GeneratedGraph


class PlacementError(ValueError):
    """Raised when Byzantine placement is invalid."""


def select_byzantine_nodes(
    *,
    graph: GeneratedGraph,
    fraction: float,
    policy: str,
    rng: np.random.Generator,
) -> tuple[int, ...]:
    """Select Byzantine node IDs under a deterministic placement policy."""

    count = byzantine_count(graph.num_nodes, fraction)
    if count == 0:
        if policy != "none":
            raise PlacementError("zero Byzantine fraction requires policy 'none'")
        return ()

    if policy == "random":
        nodes = rng.choice(graph.num_nodes, size=count, replace=False)
        return tuple(sorted(int(node) for node in nodes))
    if policy == "degree_centrality":
        nx_graph = graph.to_networkx()
        ranked_nodes = sorted(
            nx_graph.nodes,
            key=lambda node: (-nx_graph.degree[node], node),
        )
        return tuple(int(node) for node in ranked_nodes[:count])
    raise PlacementError(f"unsupported Byzantine placement policy: {policy!r}")


def byzantine_count(num_nodes: int, fraction: float) -> int:
    """Convert a configured fraction into a node count.

    The core experiments use floor(fraction * n), preserving an actual
    Byzantine fraction that never exceeds the configured upper bound.
    """

    if not isinstance(num_nodes, int) or isinstance(num_nodes, bool) or num_nodes <= 0:
        raise PlacementError("num_nodes must be a positive integer")
    if not isinstance(fraction, int | float) or isinstance(fraction, bool):
        raise PlacementError("fraction must be a number in [0, 1]")
    as_float = float(fraction)
    if not isfinite(as_float) or not 0.0 <= as_float <= 1.0:
        raise PlacementError("fraction must be in [0, 1]")
    count = floor(as_float * num_nodes)
    if as_float > 0.0 and count == 0:
        raise PlacementError(
            "positive Byzantine fraction selects zero nodes; increase agents "
            "or fraction"
        )
    if count >= num_nodes:
        raise PlacementError("Byzantine placement must leave at least one honest node")
    return count
