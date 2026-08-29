# Confirmatory Canary Pipeline

Status: Milestone 8 Step 7 end-to-end technical canary, created on 2026-08-27.

This document describes
`experiments/scripts/run_confirmatory_canary_pipeline.py`, a bounded wrapper
around the current Milestone 8 pipeline:

```text
manifest runner -> validator -> aggregator -> statistics -> figures
```

The canary exists to verify that the pipeline stages interoperate from a
single command before any long confirmatory execution. It is not a
confirmatory experiment and cannot support scientific claims.

## Command

Run the default primary-manifest canary:

```bash
python experiments/scripts/run_confirmatory_canary_pipeline.py \
  --output-root results/canary/confirmatory-m8-e2e \
  --max-runs 2
```

For a faster development check with fewer bootstrap resamples:

```bash
python experiments/scripts/run_confirmatory_canary_pipeline.py \
  --output-root /tmp/swarmgov-confirmatory-e2e \
  --max-runs 2 \
  --max-curve-points 5 \
  --bootstrap-iterations 50 \
  --bootstrap-seed 17
```

Use a fresh `--output-root` for each different canary slice. Existing output
roots are rejected unless `--overwrite` is provided.

## Inputs

Default manifest:

```text
experiments/manifests/confirmatory_m8_manifest.json
```

Useful filters:

- `--group-kind primary|sensitivity|all`;
- `--run-group <name>`, repeatable;
- `--max-runs N`;
- `--max-seeds N`;
- `--curve-stride N`;
- `--max-curve-points N`.

The same filters are passed through to the runner, validator, and aggregator
so the partial canary slice is checked against the exact intended subset.

## Outputs

Default output root:

```text
results/canary/confirmatory-m8-e2e/
```

Subdirectories:

- `raw/`: compact per-run records and `manifest_run_summary.json`;
- `validation/`: `validation_report.json`;
- `processed/`: aggregation CSVs and `aggregation_summary.json`;
- `statistics/`: confidence-interval summary CSVs and
  `statistics_summary.json`;
- `figures/`: SVG figures, compact tables, and `figure_summary.json`.

The wrapper also writes:

```text
canary_pipeline_summary.json
```

This summary records the stage commands, return codes, stdout/stderr, key
output paths, curve sampling, bootstrap settings, and an explicit
technical-only note.

## Interpretation

A completed canary proves only that the pipeline can execute a small manifest
slice end to end. With `--max-runs 2`, intervals may be degenerate or based on
too little data to interpret statistically. Treat every canary artifact as
technical validation, not evidence for or against a research hypothesis.

Full Milestone 8 claims still require the completed frozen manifest, validation
with zero missing or incompatible records, processed tables, confidence
intervals across the frozen seed set, and regenerated figures from those
processed summaries.
