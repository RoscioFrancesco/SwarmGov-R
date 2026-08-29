# Metrics

Status: metric definitions through Milestone 8 primary results.
Created: 2026-08-25.

## Cumulative Expected Regret

For a single honest agent in a stationary Bernoulli bandit, let `mu[a]` be the
true mean reward of arm `a`, and let `a_t` be the arm selected at round `t`.
The optimal expected reward is:

```text
mu_star = max_a mu[a]
```

The per-round expected regret is:

```text
r_t = mu_star - mu[a_t]
```

The cumulative expected regret through round `T` is:

```text
R_T = sum_{t=1..T} r_t
```

The implementation in `swarmgov.metrics.regret` returns:

- `per_round_regret`: the sequence `r_t`;
- `regret_curve`: cumulative regret after each round;
- `final_regret`: the final value `R_T`.

This metric uses true arm means and therefore belongs to evaluation code, not
agent decision logic. The agent never receives `mu`.

## Best-Arm Identification

Best-arm identification is reported at the end of a run:

```text
best_arm_identified = agent_preferred_arm == argmax_a mu[a]
```

The agent's preferred arm is the arm with highest empirical mean at the end of
the run, with deterministic RNG-based tie-breaking.

For multi-agent runs, SwarmGov-R reports:

```text
best_arm_identification_rate =
    number of honest agents preferring argmax_a mu[a] / number of honest agents
```

In Byzantine runs, Byzantine nodes are excluded from this rate unless a future
result explicitly reports a separate all-population metric.

## Multi-Agent Population Regret

For a population with `H` honest agents, let `a_{t,i}` be the arm selected by
honest agent `i` at round `t`. Per-agent cumulative regret is:

```text
R_{T,i} = sum_{t=1..T} (mu_star - mu[a_{t,i}])
```

The implementation reports:

- `per_agent_final_regret`: one final regret value per honest agent;
- `total_regret_curve`: `sum_i R_{t,i}` over rounds;
- `mean_regret_curve`: `(1 / N) sum_i R_{t,i}` over rounds;
- `total_population_regret`: final total regret;
- `mean_per_agent_regret`: final mean per-agent regret.

When Byzantine nodes exist, these fields are computed over honest nodes only.
The result record includes `honest_nodes` and `byzantine_nodes` to identify the
evaluated subset.

## Communication Cost

Milestone 6 counts communication for one-hop weighted pooling runs. Each
undirected edge in the active graph produces two directed messages at a
communication round, one in each direction. In dynamic-topology runs, messages
before the change use the initial graph and messages at/after the change use
the post-change graph. The count is based on transmitted messages after any
configured message-level attack is applied; the scalar payload size is
unchanged by the current controlled value-corruption attacks.

Each typed clean message transmits two authoritative per-arm vectors:

- sample counts;
- reward sums;

Empirical means are derived locally from `reward_sums / counts` for diagnostics
and records. They are not authoritative transmitted fields in the clean-message
model.

Therefore:

```text
scalar_payload_size = 2 * number_of_arms
messages_sent = number of directed messages sent
scalar_values_sent = sum over messages of scalar_payload_size
```

The implementation also records per-agent message and scalar counts by sender.
Attack diagnostics, when enabled, are validation records and are not counted as
additional communication.

## Aggregation Diagnostics

Milestone 5 result records include an `aggregation` block identifying the
one-hop aggregation method and hyperparameters. For normal runs, detailed
diagnostics are disabled and the lightweight `aggregation_summary` records:

- receiver-round aggregation events;
- arm-level aggregation events;
- receiver-round events with at least one fallback;
- arm-level median fallback events;
- invalid-message rejections.

When `aggregation.diagnostics` is enabled, each receiver-round aggregation also
records per-arm valid source counts, aggregate means, effective counts, tail
trimming, fallback flags, and invalid-message rejections.

Median and trimmed mean use source-count effective support in the UCB decision
statistics. Count-weighted mean keeps summed sample counts.

## Dynamic Topology Event Metrics

Milestone 6 result records include a `topology_change` block. When enabled, it
records:

- change round;
- configured rewiring fraction;
- connectivity policy;
- derived `rewire_seed`;
- requested edge-change count;
- edges before and after the event;
- removed and added edges;
- connected components before and after;
- number of rewiring attempts used.

The graph-change event is provenance for interpreting dynamic runs. It is not
itself a performance metric.

## Recovery Time

Milestone 6 implements a first recovery-time metric in
`swarmgov.metrics.recovery`. The metric uses the cumulative mean honest regret
curve, derives per-round increments, and compares post-change rolling regret to
a pre-change reference.

Default rule:

```text
baseline_window = 5
recovery_window = 5
tolerance = 0.05 expected regret per round
```

The pre-change reference is the mean per-round expected regret over the window
ending at the change round. This includes the change round because the
topology event is applied after local observations and before communication at
that round.

`recovery_round` is the first post-change round whose sustained
`recovery_window` mean is at most:

```text
pre_change_reference + tolerance
```

If no such sustained window exists before the horizon, the run records
`recovered: false` and `recovery_round: null`.

## Communication Model

Milestone 6 uses a synchronous, instantaneous, lossless communication model at
the configured communication rounds. In the smoke configuration this occurs
every round. Messages sent after observations at round `t` are available for
the next arm-selection step; there are no delays, dropped messages, bandwidth
queues, packet corruption, or asynchronous clocks.

The bandit environment has no arm collisions. If multiple agents select the
same arm in the same round, each receives an independent Bernoulli reward from
that arm's fixed distribution; one agent's pull does not reduce another
agent's reward.

## Scope Boundary

Fairness and worst-decile honest-agent regret are implemented for Milestone 8
primary result tables. Byzantine-only metrics are not fully implemented yet.
The current recovery-time metric is a fixed initial rule and should be
sensitivity-checked before strong recovery claims.
