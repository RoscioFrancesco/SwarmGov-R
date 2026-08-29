# Limitations And Threats To Validity

Status: Milestone 9 report limitations after Milestone 8 primary results,
created on 2026-08-29.

## Experiment Scope

The completed Milestone 8 evidence covers the primary confirmatory grid only.
The static constant-inflation sensitivity group in
`experiments/manifests/confirmatory_m8_manifest.json` has not been executed.
The project therefore should not claim sensitivity robustness beyond the
coordinated-target primary attack.

The confirmatory grid uses one reward setting:

```text
[0.75, 0.65, 0.60, 0.35, 0.25]
```

This is the easy-gap Bernoulli setting. The hard-gap setting planned earlier
has not been included in completed confirmatory results.

The confirmatory horizon is `2000` rounds, not the original canonical `10000`
round horizon. This was a feasibility decision documented before execution,
but it limits claims about long-run behavior.

## Threat Model

The core Byzantine model is controlled value corruption. Byzantine agents may
falsify outgoing reward sums, while reported counts remain truthful. They may
not invent sample support, change graph edges, alter honest state, tamper with
environment rewards, access private RNG state, or modify stored ground-truth
observations.

This makes the attack model useful for controlled stress testing, but weaker
than an arbitrary-message Byzantine model. Results should not be described as
protection against fully adaptive or arbitrary Byzantine behavior.

Implemented primary attacks are oblivious. Adaptive attacks and
environment-aware attacks are not part of the completed evidence.

## Communication And Environment Assumptions

Communication is synchronous, instantaneous, lossless, and every-round for
one-hop communication algorithms. There are no delays, drops, queues,
asynchronous clocks, bandwidth constraints, or message scheduling failures.

The Bernoulli bandit has no arm collisions. Multiple agents may select the
same arm in the same round and receive independent rewards. This excludes
congestion, resource depletion, matching conflicts, or interference between
agents.

The environment is stationary. Arm reward probabilities do not drift over
time.

## Algorithmic Limitations

The decentralized methods are one-hop pooling methods. They do not implement
iterative consensus or multi-hop information diffusion.

The median and trimmed-mean methods use one empirical estimate per valid source
and source-count effective support in UCB. Their poor Milestone 8 performance
should be interpreted as a result about these implemented one-hop robust UCB
baselines, not as a general impossibility result for robust aggregation.

The trimmed-mean parameter is fixed at `trim_count=1` with
`median_fallback`. It was not tuned after confirmatory results, but the project
has not completed a sensitivity study over trim parameters.

The centralized pooled shared-action baseline is a clean-information reference
and not an omniscient oracle. It is only run for clean static comparisons and
must not be used as a deployable attacked baseline.

## Topology Limitations

Dynamic topology is represented by one controlled edge-rewiring event at the
preconfigured change round. The project does not yet study periodic churn,
mobile agents, directed graphs, weighted graphs, asynchronous network changes,
or attacker-driven topology manipulation.

Dynamic complete-graph rewiring is excluded because the fixed-edge-count
rewiring rule has no absent edges to add in a complete graph.

Byzantine identities remain fixed through the dynamic topology event. This
isolates topology change, but does not model attackers entering, leaving, or
relocating.

## Statistical Limitations

The primary grid uses `100` seeds per condition, which supports uncertainty
estimation for the configured conditions but does not eliminate model
sensitivity. Rounds within a run are not independent replicates.

Condition and curve intervals use normal approximations across seeds. Paired
algorithm differences use deterministic paired bootstrap intervals. No
multiple-comparison correction is currently applied across all reported
condition slices.

Some secondary comparisons in `docs/confirmatory-results.md`, such as attack
damage and dynamic-vs-static effects, are seed-paired summaries derived from
`run_metrics.csv` for interpretation. They should be presented as secondary
descriptive evidence unless promoted into a frozen analysis table in later
work.

## Result Interpretation Limitations

The Milestone 8 primary results do not support the claim that median or
trimmed-mean aggregation protect against the configured Byzantine attack. They
also do not support the claim that dynamic topology always harms performance.

Clean one-hop mean pooling improves average regret in static clean conditions,
but fairness metrics show that some topologies can still have worse
worst-decile honest-agent regret than independent UCB.

The project is a synthetic controlled benchmark. It does not establish
real-world safety, misinformation resistance, or deployment readiness.

## Engineering Limitations

Raw confirmatory records and processed curve tables are large and are ignored
by Git. Reproduction requires rerunning the manifest or preserving the local
`results/` directory.

The current figure generator is intentionally simple and standard-library
based. It produces reproducible SVGs, but it is not a full interactive
dashboard.

The repository is not currently a Git repository in this workspace, so local
Git commit hashes were not available during final result generation.
