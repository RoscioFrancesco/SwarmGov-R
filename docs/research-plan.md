# SwarmGov-R Research Plan

Status: preregistration-style plan updated through Milestone 7.
Created: 2026-08-25.

## Research Question

Under which combinations of communication topology, Byzantine fraction, and
graph change does robust decentralized aggregation outperform both ordinary
consensus and independent learning?

This question may be narrowed after the literature review, but it must remain
centered on decentralized learning, adversarial information, and graph
structure.

## Motivation

SwarmGov-R studies when information sharing helps a population of learning
agents and when unreliable communication makes collaboration harmful. The
project is an empirical research benchmark, not a social simulation or
interface project.

## Problem Setting

The core environment is a stationary stochastic multi-armed bandit with
Bernoulli rewards. Each arm has a fixed mean in `(0, 1)`. Honest agents select
arms, observe only their own sampled rewards, maintain local sufficient
statistics, and may exchange typed statistics with graph neighbors. The
environment owns the true means; learning algorithms must never access them.

The communication graph is undirected in the core study. Required static graph
families are complete, ring, Watts-Strogatz small-world, and Barabasi-Albert
scale-free graphs. Graph generation must be deterministic under explicit seed
streams.

## Threat Model

The core threat model is controlled value corruption. Byzantine agents may
falsify outgoing reward information through the message interface, while the
simulator keeps ground-truth observations in agent/environment state.

Clean messages use per-arm `counts` and `reward_sums` as authoritative fields.
Empirical means are derived from those two fields for diagnostics and records;
they are not an independent clean-message source.

The current threat model keeps reported counts truthful in the core experiment.
Implemented attacks may modify only outgoing `reward_sums`; corrupted
empirical means are then derived from the corrupted sums and truthful counts.
Attacks do not modify environment rewards, honest-agent state, graph structure,
RNG streams, or stored local observations.

Implemented attacks are `no_attack`, `constant_inflation`, and
`coordinated_target`. Constant inflation and coordinated target are oblivious
message-level attacks that promote a configured suboptimal arm. Sign/order
inversion, adaptive attacks, and arbitrary-message attacks are outside the
current milestone.

Byzantine agents may not:

- change honest agents' received rewards;
- read private random-number-generator state;
- modify honest agent code;
- change the environment's true arm means;
- alter the communication graph except through the configured graph-change
  process.

Initial attacks will be oblivious. Environment-aware and adaptive attacks are
out of scope until the required baselines, controlled attacks, robust
aggregation, and dynamic topology experiments are implemented and tested.

Byzantine placement is deterministic from configuration and seed. Random
placement uses the `attack` seed stream; degree-centrality placement selects
highest-degree nodes with node-id tie-breaking. The number of Byzantine nodes
is `floor(fraction * number_of_agents)` and must leave at least one honest
agent.

## Baselines And Algorithms

Required methods, in implementation order:

1. Independent UCB1.
2. Centralized pooled shared-action UCB1 using honest observations only.
3. One-hop weighted pooling UCB1 as the current non-robust collaborative
   baseline.
4. One-hop median-UCB.
5. One-hop trimmed-mean UCB.

Reputation-weighted aggregation is optional and deferred until after the core
study is complete.

The current one-hop weighted pooling baseline is not iterative consensus or
dynamic information diffusion. Each agent sends local cumulative counts and
reward sums to graph neighbours, then chooses using a count-weighted pool of
its own local statistics and one current snapshot from each neighbour.

Median and trimmed mean remain one-hop pooling methods. They operate over one
empirical estimate per valid source, including the receiving agent's local
estimate once. Unavailable arm estimates are excluded rather than treated as
zero. The robust effective-support rule for UCB is source-count based: median
uses the number of valid source estimates, and trimmed mean uses the number of
retained estimates or all valid estimates under median fallback. This is a
heuristic robust one-hop UCB baseline and does not claim standard UCB regret
guarantees.

The trimmed-mean small-neighbourhood policy is `median_fallback`: when the
requested symmetric trimming would remove every value, the median is used and
diagnostics mark the fallback.

The centralized pooled shared-action baseline is currently defined only for
clean pooled learning runs. It is not an omniscient oracle and is not silently
reinterpreted under Byzantine message corruption.

## Hypotheses

- H1: Clean collaboration reduces cumulative regret relative to independent
  UCB, especially in well-connected graphs.
- H2: Mean-based one-hop pooling degrades rapidly when Byzantine agents inject
  extreme or coordinated messages.
- H3: Median and trimmed-mean aggregation improve adversarial robustness but
  may learn more slowly than mean-based one-hop pooling without attackers.
- H4: Sparse graphs diffuse information slowly; hub-dominated graphs are
  sensitive to whether central nodes are honest or Byzantine.
- H5: Centrality-targeted attackers cause more damage than the same Byzantine
  fraction placed uniformly at random.
- H6: Topology churn increases regret and recovery time, with effects depending
  on connectivity, placement, and aggregation.

These are hypotheses to test, not conclusions to confirm.

## Primary Extension

The planned extension beyond static decentralized-bandit experiments is a
controlled dynamic-topology process:

- generate an initial connected graph;
- at a predetermined change round, remove and add a configured fraction of
  edges;
- preserve node count;
- preserve connectivity when possible, or record disconnected components;
- keep Byzantine identities fixed to isolate topology change;
- log pre-change and post-change edge sets.

Milestone 6 implements this as one edge-rewiring event for
`one_hop_weighted_pooling_ucb1` runs. The event is applied after local
observations at the configured change round and before message construction for
that round. Dynamic complete-graph rewiring is rejected under the current
fixed-edge-count rule because a complete graph has no absent edges to add.
Requested rewiring fractions that exceed the pre-change non-edge capacity of a
graph are also rejected rather than converted into partial rewiring.

The current implementation records the event and an initial recovery-time
metric. These are technical prerequisites for later static/dynamic pilot and
confirmatory comparisons, not final evidence.

## Communication Model

Unless a later decision changes the model, communication is synchronous,
instantaneous, and lossless at configured communication rounds. The initial
clean collaborative baseline communicates every round. Messages sent after
round `t` observations are available before the next selection step. There are
no delays, packet drops, bandwidth queues, asynchronous clocks, or
communication noise.

There are no arm collisions in the Bernoulli environment. Multiple agents may
pull the same arm in the same round and receive independent rewards from the
same fixed arm distribution.

## Pilot And Confirmatory Matrix

The canonical full grid is too large for immediate execution. The preliminary
matrix used to guide pilot planning was:

- Agents: 25 for pilot and confirmatory runs; smaller for tests and smoke.
- Arms: 5.
- Reward settings: one easy gap and one hard gap.
- Topologies: complete, ring, small-world, scale-free.
- Byzantine fractions: 0.0, 0.1, 0.2, 0.3.
- Placement: random and degree-targeted.
- Attacks: none, constant inflation, coordinated target.
- Algorithms: independent UCB1, centralized pooled shared-action UCB1, one-hop
  count-weighted mean pooling UCB1, one-hop median UCB1, one-hop trimmed-mean
  UCB1.
- Topology change: static and one rewiring event at halfway through the
  horizon.
- Pilot seeds: 0 through 19.
- Confirmatory seeds: 1000 through 1099.

Milestone 7 freezes the confirmatory analysis plan in
`docs/experiment-plan.md` before any confirmatory execution. The machine-readable
manifest is `experiments/manifests/confirmatory_m8_manifest.json`.

The frozen Milestone 8 primary matrix uses a bounded 2000-round horizon with 25
agents, 5 arms, all required static graph families for clean reference runs,
and dynamic ring, small-world, and scale-free runs. Complete dynamic rewiring
is excluded because the fixed-edge-count process has no absent complete-graph
edges to add.

The primary adversarial condition is coordinated target attack with Byzantine
fraction `0.2`, random and degree-centrality placements, target arm `3`, and
inflated mean `1.0`. Constant inflation remains included as a static
sensitivity group. Adaptive attacks, arbitrary-message attacks, reputation
weighting, and attacked centralized baselines remain outside the frozen primary
plan.

Milestone 7 pilot outputs are exploratory only. They may inform runtime and
pipeline readiness, but not final scientific claims.

## Metrics

Metrics to implement and document before final experiments:

- cumulative regret over honest agents;
- final-horizon regret;
- best-arm identification rate;
- median, upper-quantile, and maximum honest-agent regret;
- recovery time after topology change;
- messages and scalar values transmitted;
- paired differences between algorithms over shared seeds.

Rounds within a run are not independent replicates. Statistical uncertainty is
reported across independent seeds.

## Reproducibility Commitments

Every run must be recoverable from a configuration file and seed. Each run
record should include resolved configuration, master seed, derived component
seeds, graph parameters and edge data, Byzantine identities, algorithm
hyperparameters, topology-change event, runtime, completion status, Python
version, dependency versions, and git commit when available.

Seed streams are derived with `numpy.random.SeedSequence`. Environment, graph,
agent tie-breaking, attack, simulation, and analysis randomness are separated.
Paired algorithm comparisons reuse the same environment and graph streams.

## Paper Or Algorithm To Reproduce

Initial reproduction target: independent UCB1 and consensus-based
decentralized UCB ideas, using Auer et al. (2002) for single-agent UCB1 and
Landgren et al. (2021) plus Martinez-Rubio et al. (2019) as the first
decentralized cooperative reference points.

Initial robust-bandit comparison target: Zhu et al. (2024) and Hu et al. (2026)
will be inspected more deeply before any claim that the dynamic-topology
experiment is a novel extension. Current project language should remain
"reproduction", "benchmark", "stress test", or "extension candidate".

## Non-Goals

The core project excludes LLM agents, fictional societies, blockchain/token
systems, robotics, a production web app, human-subject work, private personal
data, unrelated RL environments, unsupported real-world safety claims, and
theoretical regret proofs unless a precise tractable result emerges naturally.
