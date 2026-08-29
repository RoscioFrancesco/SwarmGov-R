# Confirmatory Aggregation

Status: Milestone 8 Step 4 aggregation contract, created on 2026-08-27.

This document describes
`experiments/scripts/aggregate_confirmatory_results.py`, which converts
validated compact confirmatory records into tidy processed tables. The
aggregation step does not run experiments and does not compute final confidence
intervals or scientific conclusions.

## Command

```bash
python experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The aggregator runs the Step 3 validation gate first. If validation fails, it
writes `validation_report.json`, prints `aggregation_status=blocked_by_validation`,
and does not write processed CSV tables.

For a canary or deliberately partial manifest slice, pass the same filters used
to generate and validate the raw records:

```bash
--max-runs N
--max-seeds N
--group-kind primary|sensitivity|all
--run-group <name>
```

Existing aggregate artifacts are not overwritten unless `--overwrite` is
provided.

## Outputs

Default processed directory:

```text
results/processed/confirmatory-m8/
```

Files:

- `run_metrics.csv`: one row per completed run, with scalar final metrics,
  condition fields, graph counts, attack metadata, communication totals, and
  aggregation counters.
- `per_agent_regret.csv`: one row per honest agent per run, for fairness and
  worst-agent analysis.
- `regret_curves.csv`: one row per stored curve point per run, using the
  already sampled compact curves from the raw records.
- `paired_differences.csv`: one row per seed-paired comparison when a baseline
  exists in the same condition.
- `validation_report.json`: validation report for the exact manifest slice
  being aggregated.
- `aggregation_summary.json`: row counts, paths, schema versions, and
  provenance for the processed artifacts.

The processed schema version is:

```text
confirmatory_aggregate_v1
```

## Paired Differences

Paired rows are computed within the same:

```text
group_kind, group_name, seed, topology, topology_mode, attack_strategy,
byzantine_fraction, byzantine_placement, target_arm, inflated_mean
```

The current paired rows include:

- every non-`independent` algorithm versus `independent`, when an independent
  baseline exists in that condition;
- `median` and `trimmed_mean` versus `mean`, when the one-hop mean baseline
  exists in that condition.

Each paired row stores target minus baseline differences for:

- mean per-agent regret;
- total population regret;
- best-arm identification rate;
- messages sent;
- scalar values sent.

Negative regret differences mean the target had lower regret than the baseline
for that paired seed and condition. These rows are deterministic inputs for
later confidence intervals and paired summaries; they are not final statistical
claims by themselves.

## Storage Rule

Large nested fields such as graph edge lists, preferred-arm vectors, and
per-agent communication vectors remain in the validated compact raw JSON. The
processed CSV files keep scalar columns and long tidy rows so downstream
statistics and plotting can read them without reparsing the raw simulator
payloads.

Any incompatible change to these processed tables must bump
`confirmatory_aggregate_v1` and add a dated decision-log entry.

## Statistical Summaries

After aggregation, compute condition, curve, and paired confidence-interval
summaries with:

```bash
python experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The statistics contract is documented in
`docs/confirmatory-statistics.md`.
