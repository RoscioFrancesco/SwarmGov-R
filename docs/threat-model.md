# Threat Model

Status: implemented through Milestone 6.
Created: 2026-08-25.

## Core Model

SwarmGov-R currently uses a controlled value-corruption threat model. Byzantine
agents follow the same local reward-observation process as other agents, but
may corrupt outgoing messages before neighbours receive them.

The authoritative message fields are:

- `counts`: truthful per-arm local observation counts;
- `reward_sums`: per-arm reward sums that Byzantine senders may falsify.

`empirical_means` are derived from `reward_sums / counts` inside the typed
`Message` object. They are diagnostic/result fields, not independently trusted
message inputs.

## Allowed Byzantine Action

In Milestone 4, a Byzantine sender may change only outgoing `reward_sums`.
Reported counts remain truthful. Corrupted `reward_sums` must remain in
`[0, count]` for each Bernoulli arm, so derived empirical means stay in
`[0, 1]` and are internally consistent with the transmitted support.

If a Byzantine agent has count zero for the target arm, the core model does not
allow it to invent support. The target arm's reward sum therefore remains zero
until that sender has observed the target arm at least once.

## Disallowed Action

Byzantine agents may not:

- modify environment rewards;
- change honest-agent local state;
- change their own stored ground-truth observations;
- change message sender, receiver, round, metadata, or counts;
- alter the communication graph except through the separately configured
  topology-change process;
- read or mutate private RNG state;
- modify honest-agent code;
- change the environment's true arm means.

## Implemented Strategies

- `no_attack`: identity strategy for clean communication.
- `constant_inflation`: sets the configured suboptimal target arm's outgoing
  reward sum to `inflated_mean * truthful_count`.
- `coordinated_target`: all Byzantine senders use the same configured
  suboptimal target arm and inflated mean.

All Milestone 4 attacks are oblivious. Environment-aware, adaptive,
sign/order-inversion, and arbitrary-message attacks are deferred.

## Placement

Byzantine placement is deterministic:

- `random`: samples the Byzantine node set without replacement from the
  `attack` seed stream and records the sorted node IDs;
- `degree_centrality`: selects highest-degree nodes, breaking ties by smaller
  node ID.

The configured Byzantine count is `floor(fraction * number_of_agents)`. A
positive fraction that selects zero nodes is rejected, and every run must leave
at least one honest node.

## Communication Assumptions

Communication is synchronous, instantaneous, and lossless at configured
communication rounds. Messages sent after round `t` observations are available
before the next selection step. There are no delays, drops, queues, or
asynchronous clocks.

The Bernoulli bandit has no arm collisions. Multiple agents may select the same
arm in the same round and receive independent rewards from that arm's fixed
distribution.

## Dynamic Topology Isolation

Milestone 6 dynamic topology is a simulator-controlled graph process, not a
Byzantine capability. Byzantine nodes are selected once from the initial graph
and remain fixed after the topology event. A topology change may alter who can
receive a Byzantine sender's messages, but it does not let the attacker choose
or edit edges.

## Diagnostics

When `attack.diagnostics` is enabled, the run records one diagnostic entry for
each Byzantine outgoing message:

- original honest-form message;
- corrupted message;
- sender;
- receiver;
- round;
- attack strategy.

Diagnostic recording does not alter normal simulation behaviour. It is intended
for Stage A validation, not for large confirmatory sweeps.

## Robust Aggregation Non-Claims

Milestone 5 median and trimmed-mean aggregators are empirical one-hop robust
aggregation baselines under this controlled value-corruption model. They do not
change the threat model, do not identify Byzantine nodes, and do not provide a
theoretical Byzantine-safety guarantee in the current documentation.
