# Configuration Notes

Status: updated through Milestone 7.

## Aggregation

One-hop communication runs use the `aggregation` section:

```yaml
aggregation:
  method: mean
  trim_count: null
  trim_fraction: null
  small_neighborhood_policy: median_fallback
  diagnostics: false
```

Valid methods are:

- `mean`: the existing count-weighted one-hop pooling baseline;
- `median`: unweighted median over one estimate per valid source;
- `trimmed_mean`: symmetric unweighted trimmed mean over one estimate per valid
  source.

`median` and `trimmed_mean` are robust-aggregation baselines, not proven
Byzantine-safe algorithms in this project.

## Trimmed Mean

`trimmed_mean` requires exactly one trimming parameter:

- `trim_count`: fixed number removed from each tail; or
- `trim_fraction`: converted as `floor(trim_fraction * valid_source_count)` for
  each arm.

The only implemented small-neighbourhood policy is `median_fallback`. If
requested trimming would remove every estimate, the aggregator returns the
median and marks fallback diagnostics.

Trim parameters are invalid for `mean` and `median`.

## Diagnostics

`aggregation.diagnostics: true` records one diagnostic object per
receiver-round aggregation. This is intended for tests and tiny validation runs.
Normal pilot/experiment runs keep detailed diagnostics off and use the
lightweight `aggregation_summary` in result records.

`attack.diagnostics` remains separate and records original/corrupted messages
for Byzantine outgoing messages.

## Dynamic Topology

One-hop communication runs may enable one controlled topology-change event:

```yaml
topology_change:
  enabled: true
  change_round: 30
  rewire_fraction: 0.25
  preserve_connectivity: true
```

When enabled, `change_round` must be inside the horizon and
`rewire_fraction` must be positive. When disabled, `change_round` must be
`null` and `rewire_fraction` must be `0.0`.

The event is applied after local observations at the change round and before
message construction for that round. It removes and adds the same number of
undirected edges:

```text
max(1, floor(rewire_fraction * current_edge_count))
```

Added edges must be absent before the event; removed edges are not re-added in
the same event. If the requested fraction is too large for the available
pre-change non-edges, the run fails loudly. The event records edge lists before
and after, removed and added edges, connected components, and the derived
`rewire_seed`.

Complete graphs are rejected for dynamic rewiring under this fixed-edge-count
rule because they have no absent edges to add without returning to the original
complete graph.

## Examples

Median one-hop pooling:

```yaml
algorithm:
  name: one_hop_weighted_pooling_ucb1
communication:
  interval: 1
  enabled: true
aggregation:
  method: median
  trim_count: null
  trim_fraction: null
  small_neighborhood_policy: median_fallback
  diagnostics: false
```

Trimmed-mean one-hop pooling:

```yaml
aggregation:
  method: trimmed_mean
  trim_count: 1
  trim_fraction: null
  small_neighborhood_policy: median_fallback
  diagnostics: false
```

Dynamic one-hop smoke run:

```yaml
algorithm:
  name: one_hop_weighted_pooling_ucb1
communication:
  interval: 1
  enabled: true
topology_change:
  enabled: true
  change_round: 30
  rewire_fraction: 0.25
  preserve_connectivity: true
```

Milestone 7 exploratory pilot dry-run:

```bash
python experiments/scripts/run_milestone7_pilot.py \
  --config configs/pilot_m7.yaml \
  --max-seeds 1 \
  --dry-run
```

The full Milestone 7 pilot uses seeds `0..19` and writes compact processed
tables to `results/processed/milestone7-pilot/` and exploratory SVG prototypes
to `results/figures/milestone7-pilot/`. These outputs are not confirmatory
evidence.

Milestone 8 confirmatory planning is captured in:

```text
docs/experiment-plan.md
experiments/manifests/confirmatory_m8_manifest.json
```

The manifest is a planned matrix, not an executed result set.

Confirmatory per-run storage is documented in:

```text
docs/confirmatory-output-format.md
```

The manifest runner accepts `--curve-stride` and `--max-curve-points` to bound
stored regret-curve payloads without changing the underlying simulator horizon
or metric definitions.

For long confirmatory execution, pass `--workers N` to run independent manifest
records in parallel. The default is `--workers 1`. Parallel execution preserves
the same run keys, seeds, compact schema, and skip-on-resume behaviour.

Validate a completed or canary manifest slice with:

```bash
python experiments/scripts/validate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8
```

Use the same `--max-runs`, `--max-seeds`, `--group-kind`, or `--run-group`
filters when validating a deliberately partial canary directory.

Aggregate a validated raw directory into processed tables with:

```bash
python experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The aggregation output contract is documented in:

```text
docs/confirmatory-aggregation.md
```

Compute confidence-interval summaries from processed tables with:

```bash
python experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The statistics output contract is documented in:

```text
docs/confirmatory-statistics.md
```

Generate SVG figures and compact report tables with:

```bash
python experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8
```

The figure/table output contract is documented in:

```text
docs/confirmatory-figures.md
```

Run the full confirmatory canary pipeline over a tiny manifest slice with:

```bash
python experiments/scripts/run_confirmatory_canary_pipeline.py \
  --output-root results/canary/confirmatory-m8-e2e \
  --max-runs 2
```

The canary passes the same manifest filters through runner, validator,
aggregator, statistics, and figure generation, then writes
`canary_pipeline_summary.json`. The contract is documented in:

```text
docs/confirmatory-canary-pipeline.md
```

Canary outputs are technical validation only and should not be mixed with full
confirmatory result directories.

Run the full Milestone 8 primary pipeline with:

```bash
python experiments/scripts/run_milestone8_pipeline.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --raw-dir results/raw/confirmatory-m8 \
  --processed-dir results/processed/confirmatory-m8 \
  --figures-dir results/figures/confirmatory-m8 \
  --workers 12 \
  --overwrite-derived
```

Use `--detach --notify` for unattended execution. The pipeline writes
`milestone8_pipeline_status.json`, stage logs, and completion/failure marker
files under `results/raw/confirmatory-m8/_milestone8_pipeline/`.
