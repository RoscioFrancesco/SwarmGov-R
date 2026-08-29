# Confirmatory Statistics

Status: Milestone 8 Step 5 statistics contract, created on 2026-08-27.

This document describes
`experiments/scripts/summarize_confirmatory_results.py`, which reads the
processed CSV tables from Step 4 and writes statistical summaries for final
analysis and plotting. The script does not run simulations and does not modify
raw results.

## Command

```bash
python experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

Existing statistical artifacts are not overwritten unless `--overwrite` is
provided.

## Inputs

The input directory must contain a valid Step 4 aggregation output:

- `aggregation_summary.json`;
- `run_metrics.csv`;
- `regret_curves.csv`;
- `paired_differences.csv`.

The aggregation summary must have:

```text
schema_version = confirmatory_aggregate_v1
validation_status = passed
```

This preserves the rule that statistics can only be computed from a validated
and aggregated manifest slice.

## Outputs

The statistics schema version is:

```text
confirmatory_statistics_v1
```

Files:

- `condition_summary.csv`: one row per condition, algorithm, and final metric.
- `curve_summary.csv`: one row per condition, algorithm, stored round, and
  curve metric.
- `paired_summary.csv`: one row per paired comparison group and paired
  difference metric.
- `statistics_summary.json`: schema version, row counts, CI policy, bootstrap
  configuration, and output paths.

## Confidence Intervals

`condition_summary.csv` uses normal-approximation 95% confidence intervals
across independent seeds for final run-level metrics.

`curve_summary.csv` uses normal-approximation 95% confidence intervals across
independent seeds for each stored round. Rounds are not treated as independent
replicates.

`paired_summary.csv` uses deterministic paired percentile bootstrap intervals
for seed-paired differences. The default settings are:

```text
bootstrap_iterations = 2000
bootstrap_seed = 20260827
```

The paired table summarizes target-minus-baseline differences inherited from
`paired_differences.csv`. Negative regret differences mean the target algorithm
had lower regret than the baseline for that condition and seed set.

When a deliberately small canary has only one seed or one pair, confidence
intervals are degenerate and equal to the observed mean. Such summaries are
technical validation only, not scientific evidence.

## Metrics

Final condition summaries include:

- mean per-agent regret;
- total population regret;
- median honest-agent regret;
- worst-decile honest-agent regret;
- maximum honest-agent regret;
- best-arm identification rate;
- messages sent;
- scalar values sent.

Paired summaries include differences for:

- mean per-agent regret;
- total population regret;
- best-arm identification rate;
- messages sent;
- scalar values sent.

Any incompatible change to these summaries must bump
`confirmatory_statistics_v1` and add a dated decision-log entry.

## Figures And Tables

After statistical summaries are available, generate SVG figures and compact
report tables with:

```bash
python experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8
```

The figure/table contract is documented in
`docs/confirmatory-figures.md`.
