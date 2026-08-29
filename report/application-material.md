# SwarmGov-R Application Material

Status: Milestone 9 draft, 2026-08-29.

Use only the text below if the corresponding local result artifacts remain
available and unchanged. The claims are based on the completed Milestone 8
primary confirmatory grid.

## Short Abstract

SwarmGov-R is a reproducible experimental study of decentralized
multi-armed bandit learning under unreliable communication. I built a Python
simulator in which 25 UCB-style agents learn Bernoulli rewards over static and
dynamic communication graphs, while Byzantine agents may corrupt outgoing
reward information under a controlled value-corruption threat model. The
completed primary grid contains 5700 validated runs with 100 matched seeds per
primary condition, comparing independent UCB1, a clean centralized pooled
shared-action reference, one-hop mean pooling, one-hop median aggregation, and
one-hop trimmed-mean aggregation. In clean static runs, one-hop mean pooling
reduced final mean honest-agent regret relative to independent UCB across all
tested topologies, with paired differences from -34.59 to -103.85. Under the
coordinated Byzantine attack, median and trimmed mean did not outperform mean
pooling in the primary grid. The project therefore contributes a tested
benchmark and an evidence-bounded negative finding: naive robust one-hop
aggregation is not sufficient for Byzantine robustness under this model.

## CV Bullets

- Built SwarmGov-R, a reproducible Python simulator for decentralized
  multi-armed bandits under Byzantine message corruption and dynamic
  communication graphs, comparing 5 learning/aggregation strategies across 4
  topology families and 5700 validated confirmatory runs.
- Implemented deterministic seed management, typed configurations, graph
  generation, one-hop communication, Byzantine-node placement, coordinated
  message attacks, robust aggregation baselines, dynamic rewiring, validation,
  confidence intervals, and regenerated SVG result figures.
- Found that one-hop mean pooling reduced clean static final mean regret versus
  independent UCB in every tested topology, with paired differences:
  complete -103.85 [-104.38, -103.32], ring -36.31 [-37.14, -35.51],
  small-world -53.22 [-54.11, -52.26], and scale-free -34.59
  [-36.24, -33.00].
- Showed that degree-centrality Byzantine placement was more damaging than
  random placement for one-hop mean pooling under coordinated attack, with
  degree-minus-random regret increases from 6.61 to 10.11 across the tested
  static and dynamic attacked conditions.
- Documented a negative robustness result: the implemented one-hop median and
  trimmed-mean UCB baselines did not protect against coordinated target
  attacks in the primary grid, and fairness metrics revealed worst-decile risks
  hidden by average regret.

## Motivation-Letter Connection

My earlier Monte Carlo work developed my interest in uncertainty,
reproducibility, and stochastic simulation. NexusRank then pushed that interest
toward graph modeling and information propagation. SwarmGov-R combines both
threads into a research question about robust decentralized decision-making:
when should learning agents trust information from their neighbors, and when
does communication become a liability? The project gave me practice in
mathematical modeling, controlled experimental design, reproducible software
engineering, statistical comparison across matched seeds, and honest reporting
of negative results. It connects naturally to future study in machine
learning, reinforcement learning, optimization, uncertainty, and networked
systems.

## One-Sentence Version

SwarmGov-R is a reproducible benchmark showing that communication can strongly
improve decentralized bandit learning in clean settings, but that naive
one-hop robust aggregation does not reliably protect against controlled
Byzantine misinformation.

## Do Not Claim

- Do not claim that SwarmGov-R solves misinformation.
- Do not claim a novel theorem or theoretical regret bound.
- Do not claim that median or trimmed mean are generally Byzantine-safe.
- Do not claim that dynamic topology always harms learning.
- Do not claim evidence from the unexecuted sensitivity group or hard-gap
  setting.
