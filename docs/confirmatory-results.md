# Confirmatory Results Summary

Status: Milestone 8 primary-result interpretation, created on 2026-08-29.

This document summarizes the completed Milestone 8 primary confirmatory grid.
It is an interpretation layer over saved result artifacts, not a change to the
frozen analysis plan.

## Data Sources

Primary artifacts:

- manifest: `experiments/manifests/confirmatory_m8_manifest.json`;
- raw records: `results/raw/confirmatory-m8/`;
- validation report: `results/processed/confirmatory-m8/validation_report.json`;
- processed tables: `results/processed/confirmatory-m8/`;
- generated figures and report tables: `results/figures/confirmatory-m8/`.

The completed primary grid contains:

- `5700` completed primary runs;
- `0` failed runs;
- `100` confirmatory seeds per primary condition;
- `25` agents, `5` Bernoulli arms, `2000` rounds;
- arm means `[0.75, 0.65, 0.60, 0.35, 0.25]`;
- coordinated-target Byzantine attack only for the primary attacked
  conditions;
- Byzantine fraction `0.2` for attacked primary conditions;
- random and degree-centrality Byzantine placement in attacked primary
  conditions.

The static constant-inflation sensitivity group in the manifest has not been
executed in these primary results.

## Reading Rules

Lower cumulative regret is better. Reported intervals are 95% confidence
intervals. Values from `condition_summary.csv` use normal-approximation
intervals across seeds. Values from `paired_summary.csv` use deterministic
paired bootstrap intervals over matched seeds. Secondary scenario comparisons
below are seed-paired differences computed from `run_metrics.csv` with the
same bootstrap seed `20260827`; they are used only to interpret attack and
dynamic effects.

The centralized clean reference is not included in the deployable-agent winner
counts below. It is a clean pooled shared-action learning reference, not an
omniscient oracle and not a decentralized agent.

## Main Findings

1. Across the 15 primary condition slices containing deployable methods,
   one-hop count-weighted mean pooling has the lowest final mean honest-agent
   regret point estimate in all 15 slices.
2. Clean communication helps when the aggregation rule is one-hop mean pooling:
   in clean static runs, mean pooling reduces final mean regret relative to
   independent UCB in every topology.
3. The implemented median and trimmed-mean one-hop UCB baselines do not protect
   against the coordinated-target attack in this primary grid. Under attack,
   both have substantially higher regret than one-hop mean pooling.
4. Coordinated Byzantine messages measurably damage one-hop mean pooling, but
   in the tested static attacked conditions they do not make mean pooling worse
   than independent UCB on average.
5. Degree-centrality attacker placement is consistently more damaging than
   random placement for one-hop mean pooling. This placement effect is not
   universal for the median and trimmed-mean baselines.
6. Dynamic topology has mixed effects. It does not uniformly increase regret:
   for one-hop mean pooling it is neutral on clean ring, worse on clean
   small-world, better on clean scale-free, neutral or worse on attacked ring,
   and better on attacked scale-free in this grid.
7. Average regret hides fairness risk. On clean ring and scale-free graphs,
   one-hop mean pooling improves mean regret relative to independent UCB but
   has worse worst-decile honest-agent regret.

## Clean Static Final Mean Regret

Source: `results/processed/confirmatory-m8/condition_summary.csv`, metric
`mean_per_agent_regret`.

| topology | independent | mean | median | trimmed_mean |
| --- | ---: | ---: | ---: | ---: |
| complete | 114.73 [114.22, 115.24] | 10.88 [10.60, 11.15] | 14.43 [5.02, 23.85] | 11.42 [2.86, 19.98] |
| ring | 114.73 [114.22, 115.24] | 78.42 [77.75, 79.10] | 388.80 [371.36, 406.24] | 211.38 [199.10, 223.67] |
| small_world | 114.73 [114.22, 115.24] | 61.51 [60.71, 62.31] | 309.13 [291.92, 326.33] | 273.71 [253.45, 293.96] |
| scale_free | 114.73 [114.22, 115.24] | 80.14 [78.56, 81.73] | 437.66 [417.53, 457.78] | 280.28 [268.35, 292.21] |

Interpretation: one-hop mean pooling is the clean-static winner by point
estimate in all four topologies. Median and trimmed mean are statistically
close to mean only on the complete graph; in ring, small-world, and scale-free
graphs they are much worse than mean and also worse than independent UCB.

## Clean Communication Benefit

Source: `results/processed/confirmatory-m8/paired_summary.csv`, metric
`mean_per_agent_regret_difference`. Values are mean minus independent; negative
means lower regret than independent UCB.

| topology | paired diff mean-independent | 95% CI |
| --- | ---: | ---: |
| complete | -103.85 | [-104.38, -103.32] |
| ring | -36.31 | [-37.14, -35.51] |
| small_world | -53.22 | [-54.11, -52.26] |
| scale_free | -34.59 | [-36.24, -33.00] |

Interpretation: H1 is supported for one-hop mean pooling in clean static runs.
It is not supported for all communication rules, because median and trimmed
mean often increase regret in sparse topologies.

## Robust Aggregation Under Coordinated Attack

Source: `results/processed/confirmatory-m8/paired_summary.csv`, metric
`mean_per_agent_regret_difference`. Values are robust method minus mean;
positive means higher regret than one-hop mean pooling.

| mode | topology | placement | median-mean | trimmed_mean-mean |
| --- | --- | --- | ---: | ---: |
| static | ring | random | 332.49 [312.96, 351.72] | 149.74 [135.43, 164.21] |
| static | ring | degree_centrality | 303.75 [282.78, 324.67] | 130.13 [116.58, 143.46] |
| static | scale_free | random | 363.25 [344.24, 382.07] | 223.42 [209.65, 237.50] |
| static | scale_free | degree_centrality | 407.11 [385.37, 430.19] | 203.21 [188.08, 218.85] |
| dynamic | ring | random | 306.60 [288.61, 323.69] | 174.06 [162.69, 185.83] |
| dynamic | ring | degree_centrality | 279.64 [259.50, 299.36] | 152.24 [140.09, 164.77] |
| dynamic | scale_free | random | 338.66 [322.70, 355.37] | 251.05 [239.76, 262.64] |
| dynamic | scale_free | degree_centrality | 366.01 [346.32, 385.51] | 232.64 [221.34, 244.11] |

Interpretation: H3 is not supported for the implemented one-hop median and
trimmed-mean UCB baselines in the tested coordinated-target setting. These
methods are not Byzantine-safe in the current empirical study.

## Byzantine Damage To Mean Pooling

Source: seed-paired differences from
`results/processed/confirmatory-m8/run_metrics.csv`. Values are coordinated
static attack minus clean static for one-hop mean pooling.

| topology | placement | paired diff | 95% CI |
| --- | --- | ---: | ---: |
| ring | random | 4.59 | [3.50, 5.69] |
| ring | degree_centrality | 11.74 | [11.01, 12.43] |
| scale_free | random | 1.96 | [0.62, 3.34] |
| scale_free | degree_centrality | 9.35 | [7.90, 10.75] |

Interpretation: H2 is partially supported. The coordinated attack damages
ordinary mean pooling, especially with degree-centrality placement, but in this
primary grid it does not cause the mean-pooling baseline to underperform
independent UCB on mean regret.

## Placement Effect On Mean Pooling

Source: seed-paired differences from
`results/processed/confirmatory-m8/run_metrics.csv`. Values are
degree-centrality placement minus random placement under coordinated attack for
one-hop mean pooling.

| mode | topology | paired diff | 95% CI |
| --- | --- | ---: | ---: |
| static | ring | 7.15 | [5.75, 8.47] |
| static | scale_free | 7.39 | [5.42, 9.35] |
| dynamic | ring | 10.11 | [8.57, 11.72] |
| dynamic | scale_free | 6.61 | [4.80, 8.41] |

Interpretation: H5 is supported for one-hop mean pooling. The result should
not be generalized to all algorithms, because robust-aggregator placement
effects are mixed.

## Dynamic Effect On Mean Pooling

Source: seed-paired differences from
`results/processed/confirmatory-m8/run_metrics.csv`. Values are dynamic minus
static for one-hop mean pooling.

| condition | topology | placement | paired diff | 95% CI |
| --- | --- | --- | ---: | ---: |
| clean | ring | none | -0.38 | [-1.01, 0.27] |
| clean | small_world | none | 2.60 | [1.90, 3.25] |
| clean | scale_free | none | -2.04 | [-2.83, -1.21] |
| attacked | ring | random | 0.08 | [-0.73, 0.86] |
| attacked | ring | degree_centrality | 3.05 | [1.96, 4.19] |
| attacked | scale_free | random | -1.19 | [-2.24, -0.21] |
| attacked | scale_free | degree_centrality | -1.97 | [-3.07, -0.89] |

Interpretation: H6 is mixed rather than uniformly supported. Dynamic topology
changes the outcome, but the direction depends on topology and attack
placement.

## Fairness Caveat

Source: `results/processed/confirmatory-m8/condition_summary.csv`, metric
`worst_decile_honest_regret`.

| topology | independent | mean | median | trimmed_mean |
| --- | ---: | ---: | ---: | ---: |
| complete | 131.38 [130.55, 132.22] | 11.21 [10.93, 11.49] | 14.72 [5.30, 24.13] | 11.69 [3.13, 20.25] |
| ring | 131.38 [130.55, 132.22] | 144.11 [140.99, 147.24] | 917.08 [896.07, 938.09] | 534.09 [485.13, 583.05] |
| small_world | 131.38 [130.55, 132.22] | 118.88 [115.49, 122.27] | 831.66 [794.46, 868.87] | 767.84 [720.29, 815.39] |
| scale_free | 131.38 [130.55, 132.22] | 141.10 [137.18, 145.01] | 942.65 [925.84, 959.46] | 778.67 [745.98, 811.37] |

Interpretation: average regret alone is insufficient. Clean mean pooling
improves average regret on ring and scale-free graphs, but worsens
worst-decile regret relative to independent UCB.

## Supported Conclusions

- Clean one-hop mean communication is beneficial for average regret in the
  static clean primary grid.
- The current robust one-hop median and trimmed-mean implementations are not
  successful robust defenses in this grid.
- Coordinated Byzantine messages measurably harm mean pooling, and targeting
  high-degree nodes is more damaging for mean pooling than random placement.
- Dynamic topology is consequential but not monotonic; it sometimes helps and
  sometimes hurts.
- Any paper or application material must state the controlled assumptions:
  Bernoulli rewards, truthful counts, value-only message corruption,
  synchronous lossless communication, no arm collisions, fixed 2000-round
  horizon, and no sensitivity/hard-gap results yet.

## Unsupported Claims

Do not claim that:

- median or trimmed mean are Byzantine-safe in this project;
- dynamic topology always increases regret;
- collaboration is always better than independent learning;
- the centralized clean reference is an omniscient oracle;
- the results transfer directly to real-world misinformation systems;
- the unexecuted sensitivity group supports any conclusion.
