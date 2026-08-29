# Confirmatory Output Format

Status: Milestone 8 Step 2 storage contract, created on 2026-08-27.

This document defines the compact per-run output written by
`experiments/scripts/run_confirmatory_manifest.py`. The format is intended for
the frozen Milestone 8 confirmatory matrix, but creating this contract does not
execute the matrix.

## Locations

Default output directory:

```text
results/raw/confirmatory-m8/
```

Per completed run:

```text
<run-key>.json
```

Per failed run:

```text
<run-key>.failed.json
```

Manifest execution summary:

```text
manifest_run_summary.json
```

The runner skips existing completed per-run JSON files by default, so an
interrupted execution can be resumed without overwriting completed records.

## Completed Run Record

A completed run record is a JSON object with these top-level fields:

- `status`: always `completed` for successful records.
- `completed_at_utc`: UTC completion timestamp.
- `manifest_path`: manifest path used by the runner.
- `manifest_name`: manifest identifier.
- `manifest_status_at_execution`: frozen or planning status recorded in the
  manifest.
- `planned_run`: expanded run identity from the manifest.
- `runtime_seconds`: wall-clock runtime for the individual run.
- `python_version`: Python interpreter version string.
- `platform`: platform string.
- `dependency_versions`: selected package versions.
- `resolved_config`: fully resolved simulator configuration.
- `result`: compact result payload.

## Compact Result Payload

The compact payload is versioned as:

```text
confirmatory_compact_v1
```

The payload has these sections:

- `schema_version`: compact schema version.
- `payload_policy`: explicit flags for excluded bulky fields and curve
  sampling policy.
- `identifiers`: run ID, algorithm, seed, horizon, and number of agents.
- `graph`: generated graph metadata and edge list recorded by the simulator.
- `topology_change`: dynamic-topology event metadata, or a disabled record.
- `node_sets`: honest and Byzantine node identities.
- `attack`: attack strategy and selected Byzantine nodes.
- `aggregation`: aggregation method and parameters.
- `metrics`: final regret, fairness, recovery, identification, communication,
  and aggregation-summary metrics.
- `curves`: sampled regret curves with stored round numbers.
- `diagnostics_summary`: counts of diagnostics that were produced, without
  storing verbose diagnostic payloads.

The compact record intentionally excludes:

- `actions_by_round`;
- `rewards_by_round`;
- full agent state snapshots;
- full attack diagnostic messages;
- full aggregation diagnostic messages.

These exclusions keep confirmatory storage manageable while preserving the
metrics, provenance, topology, attack metadata, and regret curves needed for
validation, aggregation, and plotting.

## Curve Sampling

The default policy stores every regret-curve point up to a maximum of `2000`
points:

```bash
python experiments/scripts/run_confirmatory_manifest.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --curve-stride 1 \
  --max-curve-points 2000
```

When downsampling is requested, the first and last curve points are preserved
and the stored `curves.rounds` array records the original one-indexed round for
each stored value.

`--max-curve-points` must be at least `2`, because the compact record preserves
both the first and last curve point when a curve has more than one round.

The manifest summary records the selected schema version and curve sampling
policy.

## Failure Records

Failure records contain:

- `status`: always `failed`;
- `completed_at_utc`;
- `manifest_path`;
- `manifest_name`;
- `planned_run`;
- `runtime_seconds`;
- `error`;
- `config_data`.

Failure records are diagnostic artifacts. They are not valid completed runs and
must be handled by the later result-validation step.

## Validation

Validate a result directory with:

```bash
python experiments/scripts/validate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8
```

The validator expands the manifest and checks completed, failed, missing,
duplicated, unexpected, and incompatible records before any aggregation step.
It writes a JSON validation report, defaulting to:

```text
<output-dir>/validation_report.json
```

A `passed` report means every expected run in the selected manifest slice has
one compatible completed record and there are no failed, duplicate,
unexpected, unreadable, or incompatible JSON records. A `failed` report is
diagnostic only; it must not be treated as scientific evidence.

When validating a deliberately small canary, pass the same `--max-runs`,
`--max-seeds`, `--group-kind`, or `--run-group` filters that were used to
create the canary.

## Aggregation

After validation passes, create processed CSV tables with:

```bash
python experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The processed-table contract is documented in
`docs/confirmatory-aggregation.md`.

## Downstream Contract

Later Milestone 8 aggregation and statistics scripts should read metrics from:

```text
result.metrics
```

and curves from:

```text
result.curves
```

They should check `result.schema_version` before interpreting a record. Any
incompatible storage change must bump the compact schema version and add a
dated decision-log entry.

Statistics and plotting steps will consume this compact schema through the
processed tables without rerunning experiments, but only after validation
passes for the intended manifest slice.
