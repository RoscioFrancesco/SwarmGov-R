"""Static communication graph generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import networkx as nx
import numpy as np


class GraphError(ValueError):
    """Raised when a communication graph cannot be generated or validated."""


@dataclass(frozen=True)
class GeneratedGraph:
    family: str
    num_nodes: int
    edges: tuple[tuple[int, int], ...]
    graph_seed: int
    parameters: dict[str, Any]
    connected: bool
    components: tuple[tuple[int, ...], ...]

    def to_networkx(self) -> nx.Graph:
        graph = nx.Graph()
        graph.add_nodes_from(range(self.num_nodes))
        graph.add_edges_from(self.edges)
        return graph

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TopologyChangeEvent:
    change_round: int
    rewire_fraction: float
    preserve_connectivity: bool
    rewire_seed: int
    requested_edge_changes: int
    edges_before: tuple[tuple[int, int], ...]
    removed_edges: tuple[tuple[int, int], ...]
    added_edges: tuple[tuple[int, int], ...]
    edges_after: tuple[tuple[int, int], ...]
    connected_before: bool
    connected_after: bool
    components_before: tuple[tuple[int, ...], ...]
    components_after: tuple[tuple[int, ...], ...]
    attempts: int

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def generate_static_graph(
    *,
    family: str,
    num_nodes: int,
    parameters: Mapping[str, Any],
    rng: np.random.Generator,
) -> GeneratedGraph:
    if num_nodes <= 0:
        raise GraphError("num_nodes must be positive")
    graph_seed = int(rng.integers(0, np.iinfo(np.uint32).max, dtype=np.uint32))
    normalized_parameters = dict(parameters)

    if family == "complete":
        graph = nx.complete_graph(num_nodes)
    elif family == "ring":
        graph = _generate_ring(num_nodes)
    elif family == "small_world":
        graph = _generate_small_world(num_nodes, normalized_parameters, graph_seed)
    elif family == "scale_free":
        graph = _generate_scale_free(num_nodes, normalized_parameters, graph_seed)
    else:
        raise GraphError(f"unsupported graph family: {family}")

    graph = nx.convert_node_labels_to_integers(graph, ordering="sorted")
    edges = _canonical_edges(graph)
    components = _components(graph)
    return GeneratedGraph(
        family=family,
        num_nodes=num_nodes,
        edges=edges,
        graph_seed=graph_seed,
        parameters=normalized_parameters,
        connected=_is_connected(graph),
        components=components,
    )


def rewire_graph_once(
    *,
    graph: GeneratedGraph,
    change_round: int,
    rewire_fraction: float,
    preserve_connectivity: bool,
    rng: np.random.Generator,
    max_attempts: int = 1000,
) -> tuple[GeneratedGraph, TopologyChangeEvent]:
    """Apply one deterministic edge-churn event to an existing graph."""

    if change_round <= 0:
        raise GraphError("change_round must be positive")
    if not 0.0 <= rewire_fraction <= 1.0:
        raise GraphError("rewire_fraction must be in [0, 1]")
    if max_attempts <= 0:
        raise GraphError("max_attempts must be positive")

    base_graph = graph.to_networkx()
    edges_before = _canonical_edges(base_graph)
    requested_changes = _edge_change_count(len(edges_before), rewire_fraction)
    rewire_seed = int(rng.integers(0, np.iinfo(np.uint32).max, dtype=np.uint32))

    if requested_changes == 0:
        event = _topology_event(
            change_round=change_round,
            rewire_fraction=rewire_fraction,
            preserve_connectivity=preserve_connectivity,
            rewire_seed=rewire_seed,
            requested_edge_changes=0,
            edges_before=edges_before,
            removed_edges=(),
            added_edges=(),
            graph_after=base_graph,
            attempts=0,
        )
        return graph, event

    addition_pool = _non_edges(base_graph)
    if not addition_pool:
        raise GraphError(
            "cannot rewire a graph with fixed edge count when no alternate "
            "non-edges exist"
        )
    if len(addition_pool) < requested_changes:
        raise GraphError(
            "rewire_fraction requests more edge additions than pre-change "
            "non-edges allow"
        )
    local_rng = np.random.default_rng(rewire_seed)
    last_event: TopologyChangeEvent | None = None
    for attempt in range(1, max_attempts + 1):
        candidate = base_graph.copy()
        removed_edges = _sample_edges(
            edges_before,
            count=requested_changes,
            rng=local_rng,
        )
        candidate.remove_edges_from(removed_edges)
        added_edges = _sample_edges(
            addition_pool,
            count=requested_changes,
            rng=local_rng,
        )
        candidate.add_edges_from(added_edges)
        event = _topology_event(
            change_round=change_round,
            rewire_fraction=rewire_fraction,
            preserve_connectivity=preserve_connectivity,
            rewire_seed=rewire_seed,
            requested_edge_changes=requested_changes,
            edges_before=edges_before,
            removed_edges=removed_edges,
            added_edges=added_edges,
            graph_after=candidate,
            attempts=attempt,
        )
        last_event = event
        if preserve_connectivity and not event.connected_after:
            continue
        return _generated_graph_from_networkx(graph, candidate), event

    if preserve_connectivity:
        raise GraphError(
            "could not rewire graph while preserving connectivity "
            f"after {max_attempts} attempts"
        )
    if last_event is None:
        raise GraphError("could not rewire graph")
    final_graph = graph.to_networkx()
    final_graph.remove_edges_from(last_event.removed_edges)
    final_graph.add_edges_from(last_event.added_edges)
    return _generated_graph_from_networkx(graph, final_graph), last_event


def neighbors_by_node(graph: GeneratedGraph) -> dict[int, tuple[int, ...]]:
    nx_graph = graph.to_networkx()
    return {
        node: tuple(sorted(nx_graph.neighbors(node))) for node in range(graph.num_nodes)
    }


def directed_edges(graph: GeneratedGraph) -> tuple[tuple[int, int], ...]:
    return tuple(directed for u, v in graph.edges for directed in ((u, v), (v, u)))


def _generate_ring(num_nodes: int) -> nx.Graph:
    if num_nodes < 3:
        raise GraphError("ring graph requires at least three nodes")
    return nx.cycle_graph(num_nodes)


def _generate_small_world(
    num_nodes: int,
    parameters: dict[str, Any],
    graph_seed: int,
) -> nx.Graph:
    if num_nodes < 3:
        raise GraphError("small_world graph requires at least three nodes")
    k = _positive_int_parameter(
        parameters,
        "k",
        default=_default_small_world_k(num_nodes),
    )
    if k >= num_nodes:
        raise GraphError("small_world parameter k must be smaller than num_nodes")
    if k % 2 != 0:
        raise GraphError("small_world parameter k must be even")
    p = _fraction_parameter(parameters, "p", default=0.1)
    parameters["k"] = k
    parameters["p"] = p
    return nx.connected_watts_strogatz_graph(
        num_nodes,
        k,
        p,
        tries=100,
        seed=graph_seed,
    )


def _generate_scale_free(
    num_nodes: int,
    parameters: dict[str, Any],
    graph_seed: int,
) -> nx.Graph:
    if num_nodes < 2:
        raise GraphError("scale_free graph requires at least two nodes")
    m = _positive_int_parameter(parameters, "m", default=1)
    if m >= num_nodes:
        raise GraphError("scale_free parameter m must be smaller than num_nodes")
    parameters["m"] = m
    return nx.barabasi_albert_graph(num_nodes, m, seed=graph_seed)


def _generated_graph_from_networkx(
    source: GeneratedGraph,
    graph: nx.Graph,
) -> GeneratedGraph:
    return GeneratedGraph(
        family=source.family,
        num_nodes=source.num_nodes,
        edges=_canonical_edges(graph),
        graph_seed=source.graph_seed,
        parameters=dict(source.parameters),
        connected=_is_connected(graph),
        components=_components(graph),
    )


def _topology_event(
    *,
    change_round: int,
    rewire_fraction: float,
    preserve_connectivity: bool,
    rewire_seed: int,
    requested_edge_changes: int,
    edges_before: tuple[tuple[int, int], ...],
    removed_edges: tuple[tuple[int, int], ...],
    added_edges: tuple[tuple[int, int], ...],
    graph_after: nx.Graph,
    attempts: int,
) -> TopologyChangeEvent:
    return TopologyChangeEvent(
        change_round=change_round,
        rewire_fraction=rewire_fraction,
        preserve_connectivity=preserve_connectivity,
        rewire_seed=rewire_seed,
        requested_edge_changes=requested_edge_changes,
        edges_before=edges_before,
        removed_edges=removed_edges,
        added_edges=added_edges,
        edges_after=_canonical_edges(graph_after),
        connected_before=_is_connected_from_edges(
            num_nodes=graph_after.number_of_nodes(),
            edges=edges_before,
        ),
        connected_after=_is_connected(graph_after),
        components_before=_components_from_edges(
            num_nodes=graph_after.number_of_nodes(),
            edges=edges_before,
        ),
        components_after=_components(graph_after),
        attempts=attempts,
    )


def _edge_change_count(edge_count: int, rewire_fraction: float) -> int:
    if edge_count <= 0 or rewire_fraction == 0.0:
        return 0
    requested = int(np.floor(edge_count * rewire_fraction))
    return min(edge_count, max(1, requested))


def _sample_edges(
    edges: tuple[tuple[int, int], ...],
    *,
    count: int,
    rng: np.random.Generator,
) -> tuple[tuple[int, int], ...]:
    if count > len(edges):
        raise GraphError("cannot sample more edges than candidates")
    indices = rng.choice(len(edges), size=count, replace=False)
    return tuple(sorted(edges[int(index)] for index in indices))


def _non_edges(graph: nx.Graph) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((min(u, v), max(u, v)) for u, v in nx.non_edges(graph)))


def _canonical_edges(graph: nx.Graph) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((min(u, v), max(u, v)) for u, v in graph.edges()))


def _components(graph: nx.Graph) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(sorted(component)) for component in nx.connected_components(graph)
    )


def _components_from_edges(
    *,
    num_nodes: int,
    edges: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, ...], ...]:
    graph = nx.Graph()
    graph.add_nodes_from(range(num_nodes))
    graph.add_edges_from(edges)
    return _components(graph)


def _is_connected(graph: nx.Graph) -> bool:
    return graph.number_of_nodes() > 0 and nx.is_connected(graph)


def _is_connected_from_edges(
    *,
    num_nodes: int,
    edges: tuple[tuple[int, int], ...],
) -> bool:
    graph = nx.Graph()
    graph.add_nodes_from(range(num_nodes))
    graph.add_edges_from(edges)
    return _is_connected(graph)


def _default_small_world_k(num_nodes: int) -> int:
    candidate = min(4, num_nodes - 1)
    if candidate % 2 != 0:
        candidate -= 1
    return max(candidate, 2)


def _positive_int_parameter(
    parameters: Mapping[str, Any],
    name: str,
    *,
    default: int,
) -> int:
    value = parameters.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise GraphError(f"{name} must be a positive integer")
    return value


def _fraction_parameter(
    parameters: Mapping[str, Any],
    name: str,
    *,
    default: float,
) -> float:
    value = parameters.get(name, default)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise GraphError(f"{name} must be a number in [0, 1]")
    as_float = float(value)
    if not 0.0 <= as_float <= 1.0:
        raise GraphError(f"{name} must be in [0, 1]")
    return as_float
