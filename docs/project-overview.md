# SwarmGov-R Project Overview

Status: public overview for external readers, created on 2026-08-29.

This document explains the project without relying on any internal agent guide.
It is the best first stop after the README for a reader who wants to understand
what the simulator does and what the completed results mean.

## One-Sentence Summary

SwarmGov-R is a reproducible benchmark for testing when decentralized
multi-armed bandit agents benefit from sharing information, and when Byzantine
message corruption makes that sharing unreliable.

## Core Idea

Each agent repeatedly chooses one action from a fixed set of actions. In
bandit terminology, an action is called an **arm**. Each arm has an unknown
reward probability. The agent's goal is to learn which arm is best while losing
as little reward as possible during exploration.

The project compares agents that learn alone with agents that share local
statistics over a communication graph. Some agents can be Byzantine: they may
send misleading reward information to their neighbors. The experiment asks
whether communication still helps, whether robust aggregation helps, and how
the graph structure changes the answer.

## What Is Being Simulated

The environment is a stationary Bernoulli multi-armed bandit:

- there are `K` arms;
- arm `a` has a fixed but hidden success probability `mu[a]`;
- when an agent chooses arm `a`, it receives reward `1` with probability
  `mu[a]` and reward `0` otherwise;
- agents do not know `mu[a]`;
- the simulator uses `mu[a]` only for reward sampling and evaluation.

At each round, an honest agent:

1. chooses an arm using its current UCB-style estimates;
2. receives a Bernoulli reward from the environment;
3. updates its own local counts and reward sums;
4. sends local statistics to graph neighbors if communication is enabled;
5. aggregates received messages;
6. uses the updated estimates for the next round.

## Agents And Algorithms

The implemented deployable baselines are:

- `independent`: each agent runs UCB1 using only its own observations.
- `mean`: each agent combines its own local statistics with one-hop neighbor
  statistics using count-weighted pooling.
- `median`: each agent uses the median of one empirical estimate per valid
  source and arm.
- `trimmed_mean`: each agent sorts one empirical estimate per source and arm,
  trims one value from each tail when possible, and averages the remainder.

The project also includes `centralized_clean_reference`, a clean pooled
shared-action UCB1 reference. It is not a deployable decentralized agent and
not an omniscient oracle.

## Communication Model

Communication happens over an undirected graph. Nodes are agents and edges are
message channels. The implemented graph families are:

- complete graph;
- ring graph;
- Watts-Strogatz small-world graph;
- Barabasi-Albert scale-free graph.

For one-hop communication algorithms, messages are synchronous,
instantaneous, lossless, and sent every round. A message contains authoritative
per-arm counts and reward sums. Empirical means are derived from those two
fields.

The project also implements one controlled dynamic topology process: at a
preconfigured round, the simulator rewires a fraction of edges while keeping
the node set fixed and preserving connectivity for the primary grid.

## Byzantine Threat Model

The completed experiments use controlled value corruption:

- Byzantine agents may falsify outgoing reward sums;
- reported counts remain truthful;
- corrupted reward sums must stay internally consistent with reported counts;
- attacks do not change environment rewards, honest-agent state, stored
  ground-truth observations, graph structure, or RNG state.

The implemented attacks are:

- `no_attack`;
- `constant_inflation`, which promotes one configured suboptimal arm;
- `coordinated_target`, where all Byzantine agents promote the same
  suboptimal arm.

Byzantine nodes can be selected uniformly at random or by degree centrality.

## Metrics

The main metric is expected cumulative regret for honest agents. Regret is the
gap between the expected reward of the best arm and the expected reward of the
arm actually chosen, accumulated over time.

The project also reports:

- total honest-population regret;
- best-arm identification rate;
- median and worst-decile honest-agent regret;
- recovery time after dynamic topology changes;
- messages sent and scalar values transmitted.

Byzantine agents are excluded from honest-agent regret and identification
metrics.

## Completed Confirmatory Evidence

The completed primary confirmatory grid contains:

- `5700` completed runs;
- `0` failed runs;
- `100` matched seeds per primary condition;
- `25` agents;
- `5` Bernoulli arms;
- horizon `2000`;
- arm means `[0.75, 0.65, 0.60, 0.35, 0.25]`;
- Byzantine fraction `0.2` in attacked primary runs;
- coordinated-target attack in attacked primary runs;
- static and dynamic topology comparisons.

The main result is bounded:

- one-hop mean pooling has the lowest final mean honest-agent regret point
  estimate among deployable methods in all 15 primary condition slices;
- clean one-hop mean communication reduces final mean regret relative to
  independent UCB in every tested static topology;
- coordinated Byzantine attacks measurably damage mean pooling, especially
  when Byzantine nodes are placed by degree centrality;
- the implemented one-hop median and trimmed-mean baselines do not protect
  against the coordinated-target attack in the primary grid;
- dynamic topology has mixed effects rather than a single always-bad or
  always-good direction;
- fairness metrics show that average regret can hide worse outcomes for the
  worst-decile honest agents.

## What The Project Does Not Claim

The project does not claim that:

- median or trimmed mean are generally useless;
- mean pooling is always the best decentralized method;
- dynamic topology always hurts;
- the simulator solves misinformation;
- the results transfer directly to real-world social systems;
- the centralized clean reference is an omniscient oracle;
- the unexecuted sensitivity grid supports any result.

## Where To Look Next

- `README.md`: installation, commands, repository map, and headline result.
- `report/paper.md`: research-report draft.
- `docs/confirmatory-results.md`: detailed result interpretation with tables.
- `docs/limitations.md`: assumptions and threats to validity.
- `docs/experiment-plan.md`: frozen confirmatory analysis plan.
- `docs/metrics.md`: exact metric definitions.
- `docs/threat-model.md`: Byzantine model and communication assumptions.
- `report/application-material.md`: concise abstract and CV bullets.
