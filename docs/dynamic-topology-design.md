# Dynamic Topology Design

Status: Milestone 6 design, implemented for one-hop communication runs.
Created: 2026-08-26.

## Scope

Milestone 6 implements one controlled topology-change process. It does not add
dynamic Byzantine placement, adaptive attacks, packet loss, asynchronous
communication, mobility, or periodic churn.

The process is available for `one_hop_weighted_pooling_ucb1` runs because that
is the implemented communication-based family. Independent UCB1 and the
centralized pooled shared-action baseline do not use dynamic topology
configurations.

## Event Timing

The configured event is applied at `topology_change.change_round` after local
arm selections, rewards, and local statistic updates for that round, but before
message construction for that round.

Consequences:

- actions and rewards through the change round are matched with an otherwise
  identical static run under the same seed;
- messages at the change round use the post-change graph;
- downstream decisions can diverge only after the changed communication has had
  a chance to affect pooled decision statistics.

## Rewiring Rule

Let `m` be the number of undirected edges before the event. For positive
`rewire_fraction`, the number of rewired edges is:

```text
edge_changes = max(1, floor(rewire_fraction * m))
```

The event removes `edge_changes` existing undirected edges and adds the same
number of undirected edges that were absent before the event. Removed edges are
not re-added during the same event. Node identities and node count are
preserved.

If the requested fraction requires more new edge additions than the pre-change
non-edge set allows, the run fails loudly instead of performing a partial
rewiring.

The graph RNG stream first generates the initial graph seed. The same stream
then derives a recorded `rewire_seed`, which drives the event-local edge
sampling. This keeps paired static/dynamic runs identical before the event while
making the topology change reproducible.

## Connectivity

When `preserve_connectivity` is true, rewiring is retried until the post-change
graph remains connected or the bounded attempt limit is exhausted. Exhaustion is
a simulation error rather than a silent disconnected run.

When `preserve_connectivity` is false, the event is allowed to disconnect the
graph and records the post-change connected components.

## Complete Graph Guardrail

A complete graph has no absent undirected edges. Under a fixed-edge-count
remove-and-add rewiring rule, a complete graph cannot change without re-adding
the same removed edges. Such a configuration is rejected instead of being
recorded as a false dynamic topology event.

## Byzantine Isolation

Byzantine node identities are selected once from the initial graph and remain
fixed through the topology change. The event may change which neighbours see
Byzantine messages, but it does not recalculate the Byzantine set.

## Recorded Event

Each dynamic run records:

- configured change round, rewiring fraction, and connectivity policy;
- `rewire_seed`;
- requested edge-change count;
- edge list before the event;
- removed and added edges;
- edge list after the event;
- connectedness and connected components before and after;
- number of attempts used.

These fields are technical provenance, not scientific evidence by themselves.
