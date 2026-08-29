# SwarmGov-R Experiment Plan

Status: frozen before confirmatory execution on 2026-08-26.

This document freezes the Milestone 8 confirmatory analysis plan. Milestone 7
pilot outputs are exploratory technical validation only; they may be used to
estimate runtime and check the pipeline, but not to change hypotheses after
confirmatory execution starts.

## Primary Question

Under which combinations of communication topology, Byzantine fraction, and
graph change does robust decentralized aggregation outperform both ordinary
one-hop weighted pooling and independent learning?

The project remains a reproduction, extension candidate, and stress test of
decentralized bandit and robust aggregation ideas. It does not claim novelty or
real-world safety from pilot data.

## Frozen Hyperparameters

- Agents: `25` for confirmatory runs.
- Arms: `5`.
- Horizon: `2000` rounds.
- Reward family: stationary Bernoulli bandit.
- Primary arm means: `[0.75, 0.65, 0.60, 0.35, 0.25]`.
- Exploration constant: `1.41421356237`.
- Communication interval: every round for one-hop communication algorithms.
- Median aggregation: one valid empirical estimate per source and arm.
- Trimmed mean: `trim_count=1`, `trim_fraction=null`.
- Small-neighbourhood policy: `median_fallback`.
- Dynamic topology: one edge-rewiring event at round `1000`.
- Dynamic rewire fraction: `0.2`.
- Dynamic connectivity: preserve connectivity when possible; otherwise fail
  for the primary grid.
- Recovery metric: pre-change baseline window `5`, sustained recovery window
  `5`, tolerance `0.05` expected regret per round.

The horizon is deliberately lower than the initial canonical `10000` because
the current simulator stores per-round action and reward records for
reproducibility. This is a bounded feasibility decision, not a performance
tuning decision.

## Seed Policy

Pilot seeds are `0..19`. Confirmatory seeds are frozen as `1000..1099`.

All algorithms inside a matched condition use the same run seed set and the
same component seed stream contract:

- `environment`;
- `graph`;
- `agents`;
- `attack`;
- `simulation`;
- `analysis`.

Failed or missing seeds must be logged. Seeds must not be removed because their
outcomes are inconvenient.

## Algorithms

Confirmatory algorithm labels are:

- `independent`: independent UCB1 with no communication.
- `centralized_clean_reference`: centralized pooled shared-action UCB1 on clean
  static runs only.
- `mean`: one-hop weighted pooling UCB1 with `aggregation.method=mean`.
- `median`: one-hop UCB1 with per-source median aggregation.
- `trimmed_mean`: one-hop UCB1 with per-source trimmed-mean aggregation.

The centralized reference is a clean-information learning baseline, not an
omniscient oracle and not an attacked Byzantine baseline.

## Topologies

Static graph families:

- complete graph;
- ring graph;
- Watts-Strogatz small-world graph with `k=4`, `p=0.1`;
- Barabasi-Albert scale-free graph with `m=2`.

Dynamic topology is tested only on ring, small-world, and scale-free graphs.
Dynamic complete-graph rewiring is excluded because the fixed-edge-count
rewiring process has no absent complete-graph edges to add.

## Attacks

Primary attacked condition:

- strategy: `coordinated_target`;
- Byzantine fraction: `0.2`;
- placements: `random` and `degree_centrality`;
- target arm: `3`;
- inflated mean: `1.0`;
- knowledge level: oblivious.

Sensitivity attacked condition:

- strategy: `constant_inflation`;
- Byzantine fraction: `0.2`;
- placement: `random`;
- target arm: `3`;
- inflated mean: `1.0`;
- topology mode: static.

The controlled value-corruption threat model remains fixed: Byzantine agents
may corrupt outgoing reward sums while reported counts remain truthful and
derived means stay internally consistent. Attacks do not modify environment
rewards, honest-agent state, graph structure, RNG state, or stored local
observations.

## Confirmatory Matrix

The machine-readable manifest is
`experiments/manifests/confirmatory_m8_manifest.json`.

Primary run groups:

- Clean static all-topology reference: complete, ring, small-world, scale-free;
  independent, centralized clean reference, mean, median, trimmed mean; 100
  seeds; `2000` runs.
- Clean dynamic communication-topology comparison: ring, small-world,
  scale-free; mean, median, trimmed mean; 100 seeds; `900` runs.
- Coordinated static attack comparison: ring and scale-free; independent,
  mean, median, trimmed mean; random and degree-centrality placement; 100
  seeds; `1600` runs.
- Coordinated dynamic attack comparison: ring and scale-free; mean, median,
  trimmed mean; random and degree-centrality placement; 100 seeds; `1200`
  runs.

Primary planned runs: `5700`.

Sensitivity run group:

- Constant-inflation static attack: ring and scale-free; independent, mean,
  median, trimmed mean; random placement; 100 seeds; `800` runs.

Total planned runs including sensitivity: `6500`.

## Milestone 7 Runtime Estimate

The Milestone 7 pilot completed `1260/1260` planned exploratory runs with zero
failures in `807.58` seconds on the current machine. The observed mean runtime
was `0.64` seconds per pilot run, or approximately
`0.000534` seconds per simulated agent-round.

Using a linear agent-round projection from the pilot, the frozen Milestone 8
manifest is estimated at:

- primary matrix: approximately `42.3` single-process hours;
- primary plus sensitivity matrix: approximately `48.2` single-process hours.

This is a planning estimate only. Milestone 8 should implement compact result
writing and parallel manifest execution before running the full confirmatory
matrix.

## Output Storage Contract

Per-run confirmatory records use the compact `confirmatory_compact_v1` schema
documented in `docs/confirmatory-output-format.md`. The schema stores final
metrics, provenance, graph and topology-change metadata, node identities,
attack metadata, communication metrics, aggregation summaries, and sampled
regret curves. It intentionally excludes raw per-round action logs, raw reward
logs, full agent state snapshots, and verbose diagnostics from completed run
records.

The default result directory for the confirmatory runner is:

```text
results/raw/confirmatory-m8/
```

The storage contract is an engineering prerequisite for the confirmatory grid;
it is not itself scientific evidence and does not change the frozen hypotheses,
seed set, algorithms, attacks, or metric definitions.

The manifest runner may execute independent runs in parallel with
`--workers N`. This is an execution-speed decision only: it does not alter run
keys, seed derivation, graph generation, algorithms, metrics, or the frozen
primary matrix. Existing completed records are skipped on resume unless
`--overwrite` is explicitly provided.

Before aggregation or plotting, the intended result directory must pass:

```bash
python experiments/scripts/validate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8
```

The validation report checks the selected manifest slice for missing, failed,
duplicated, unexpected, unreadable, and schema-incompatible records. A failed
validation report blocks confirmatory aggregation until the issue is explained
or the affected run is repaired by rerunning it from the manifest.

After validation passes, deterministic processed tables are generated with:

```bash
python experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The processed artifacts are documented in
`docs/confirmatory-aggregation.md`. They are inputs to the later statistical
step and do not by themselves constitute final confidence intervals or
scientific conclusions.

Confidence-interval summaries are generated from the processed tables with:

```bash
python experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

`docs/confirmatory-statistics.md` records the CI policy: normal-approximation
intervals across independent seeds for condition and curve summaries, and
deterministic paired percentile bootstrap intervals for seed-paired
differences. Rounds are summarized per stored round and are not treated as
independent replicates.

Figures and compact report tables are generated from the statistical summaries
with:

```bash
python experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8
```

The figure/table contract is documented in
`docs/confirmatory-figures.md`. Figure outputs inherit the status of the input
data: canary or partial manifest slices remain technical validation only.

Before any long confirmatory execution, the end-to-end canary pipeline should
pass from a fresh output directory:

```bash
python experiments/scripts/run_confirmatory_canary_pipeline.py \
  --output-root results/canary/confirmatory-m8-e2e \
  --max-runs 2
```

The wrapper runs the manifest runner, validator, aggregator, statistical
summarizer, and figure/table generator over the same bounded manifest slice.
It writes `canary_pipeline_summary.json` and is documented in
`docs/confirmatory-canary-pipeline.md`. Passing this canary is a technical
pipeline gate only; it does not alter the frozen seed set, hypotheses,
hyperparameters, or required full validation.

The full primary pipeline can be run unattended with:

```bash
python experiments/scripts/run_milestone8_pipeline.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --raw-dir results/raw/confirmatory-m8 \
  --processed-dir results/processed/confirmatory-m8 \
  --figures-dir results/figures/confirmatory-m8 \
  --workers 12 \
  --overwrite-derived
```

This wrapper does not change the manifest. It resumes completed raw records,
repairs invalid partial records when encountered, validates the selected
manifest slice, regenerates derived processed/statistical/figure artifacts,
runs lint and tests, and records stage logs under
`results/raw/confirmatory-m8/_milestone8_pipeline/`.

## Metrics

Primary metrics:

- final mean per-honest-agent cumulative regret;
- regret curves over honest agents;
- total honest-population regret;
- best-arm identification rate;
- median, 90th percentile, and maximum honest-agent regret;
- recovery time for dynamic runs;
- messages sent and scalar values transmitted.

Byzantine nodes are excluded from honest-agent regret and identification
metrics. They may be reported separately later, but not mixed into the primary
honest-agent metrics.

## Statistical Analysis

All uncertainty is computed across independent seeds, not across rounds within
a run.

Primary summaries:

- mean final regret with 95% confidence intervals across seeds;
- paired differences versus independent UCB for matching static conditions;
- paired differences versus one-hop weighted pooling for robust aggregation;
- fairness summaries across honest agents;
- recovery summaries for dynamic runs;
- communication cost versus regret for selected conditions.

Paired comparisons use matched seed identities. If bootstrap utilities are
available in Milestone 8, use paired bootstrap confidence intervals for
differences; otherwise report normal-approximation intervals and mark this as a
limitation.

## Figure Plan

Required final figures generated from processed data:

- cumulative regret curves for clean and coordinated attacked conditions;
- final regret versus algorithm and topology;
- random versus degree-centrality attacker placement on ring and scale-free
  graphs;
- static versus dynamic topology with the change point marked;
- fairness or worst-decile honest-agent regret;
- communication cost versus regret for selected algorithms.

Milestone 7 figure prototypes are labelled exploratory and stored under
`results/figures/milestone7-pilot/`.

## Exclusions

The following remain outside Milestone 8's frozen primary plan:

- adaptive attacks;
- arbitrary-message attacks;
- reputation weighting;
- dynamic complete-graph rewiring;
- dynamic no-communication independent UCB runs;
- attacked centralized pooled baselines;
- frontend or dashboard work;
- manual alteration of figure values.

Any change to seed sets, hyperparameters, metric definitions, threat model, or
primary run groups after confirmatory execution begins requires a dated
decision-log entry.
