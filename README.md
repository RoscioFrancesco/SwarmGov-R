# SwarmGov-R

SwarmGov-R is a reproducible research project on decentralized cooperative
multi-armed bandits under unreliable communication. The current repository
state covers Milestone 0 through the Milestone 8 primary confirmatory grid:
research framing, deterministic Python simulation, Independent UCB1,
centralized pooled shared-action clean reference, one-hop mean/median/trimmed
aggregation, controlled Byzantine message attacks, dynamic topology, metrics,
validation, processed result tables, confidence intervals, and regenerated SVG
figures. Milestone 9 adds the first research-report draft and
application-ready summary material.

The completed primary grid has `5700/5700` runs with zero failed runs.
Adaptive attacks, arbitrary-message Byzantine attacks, reputation weighting,
the constant-inflation sensitivity grid, and hard-gap confirmatory experiments
are not completed yet.

## Research Question

Under which combinations of communication topology, Byzantine fraction, and
graph change does robust decentralized aggregation outperform both ordinary
one-hop weighted pooling and independent learning?

## Experiment Flow

```text
Bernoulli bandit means
        |
        v
UCB-style agents on a communication graph
        |
        v
local observations -> typed neighbour messages -> optional Byzantine corruption
        |
        v
one-hop aggregation: mean, median, or trimmed mean
        |
        v
honest-agent regret, identification, fairness, recovery, communication cost
        |
        v
validated raw records -> processed tables -> confidence intervals -> SVG figures
```

## Main Confirmatory Result

In the completed primary grid, one-hop count-weighted mean pooling has the
lowest final mean honest-agent regret point estimate among deployable methods
in all 15 primary condition slices. In clean static runs it reduces final mean
regret relative to independent UCB in every topology: complete `-103.85`
`[-104.38, -103.32]`, ring `-36.31` `[-37.14, -35.51]`,
small-world `-53.22` `[-54.11, -52.26]`, and scale-free `-34.59`
`[-36.24, -33.00]`.

The implemented one-hop median and trimmed-mean UCB baselines do not provide a
successful Byzantine defense in this grid. Under coordinated-target attack,
their regret is substantially higher than one-hop mean pooling in every
attacked primary condition. Dynamic topology has mixed effects rather than a
single monotonic direction.

Full result interpretation: `docs/confirmatory-results.md`.
Limitations and threats to validity: `docs/limitations.md`.
Report draft: `report/paper.md`.
Application material: `report/application-material.md`.
Plain-language project overview: `docs/project-overview.md`.

## Algorithms And Attacks

Implemented learning baselines:

- `independent`: independent UCB1 with no communication.
- `centralized_clean_reference`: clean pooled shared-action UCB1 reference,
  not an omniscient oracle and not a deployable decentralized agent.
- `mean`: one-hop count-weighted pooling UCB1.
- `median`: one-hop UCB1 with one empirical estimate per valid source.
- `trimmed_mean`: one-hop UCB1 with `trim_count=1` and median fallback.

Implemented Byzantine components:

- deterministic random Byzantine placement;
- deterministic degree-centrality Byzantine placement;
- `no_attack`;
- `constant_inflation`;
- `coordinated_target`.

Primary confirmatory attacked runs use the coordinated target attack with
Byzantine fraction `0.2`, target arm `3`, and inflated mean `1.0`.

## Setup

```bash
python3 -m pip install -e ".[dev]"
```

## Checks

```bash
python3 -m pytest
ruff check .
```

## Smoke Config Validation

```bash
python3 -m swarmgov validate-config --config configs/smoke.yaml
python3 -m swarmgov validate-config --config configs/attacked_smoke.yaml
python3 -m swarmgov validate-config --config configs/dynamic_smoke.yaml
python3 -m swarmgov run --config configs/smoke.yaml --dry-run
```

## Clean Multi-Agent Smoke Run

```bash
python3 -m swarmgov run --config configs/smoke.yaml
```

The command writes one JSON result under
`results/raw/smoke-one-hop-weighted-pooling-clean/`.

## Attacked Technical Smoke Run

```bash
python3 -m swarmgov run --config configs/attacked_smoke.yaml
```

The attacked smoke config uses one degree-centrality-selected Byzantine node
and the `coordinated_target` message attack with diagnostics enabled. Treat its
output only as technical validation of attack plumbing, not scientific
evidence.

## Dynamic Topology Smoke Run

```bash
python3 -m swarmgov run --config configs/dynamic_smoke.yaml
```

The dynamic smoke config applies one connected edge-rewiring event at round
`30` on a small-world graph and records the event plus a recovery-time metric.
Treat the output only as technical validation of Milestone 6 plumbing.

## Milestone 5 Exploratory Pilot

```bash
python3 experiments/scripts/run_milestone5_pilot.py --config configs/pilot_m5.yaml
```

The pilot compares independent UCB, one-hop mean, one-hop median, and one-hop
trimmed mean across clean and coordinated-target attack conditions on complete
and ring graphs for seeds `0..19`. Its outputs are exploratory technical
evidence only, not confirmatory results.

For a quick balanced technical check while developing, run the same grid over
the first few configured seeds:

```bash
python3 experiments/scripts/run_milestone5_pilot.py --config configs/pilot_m5.yaml --max-seeds 4
```

## Milestone 7 Exploratory Pilot And Figures

Dry-run the configured pilot grid:

```bash
python3 experiments/scripts/run_milestone7_pilot.py --config configs/pilot_m7.yaml --max-seeds 1 --dry-run
```

Run the full bounded Stage B pilot:

```bash
python3 experiments/scripts/run_milestone7_pilot.py --config configs/pilot_m7.yaml
```

The command writes compact CSV/JSON artifacts to
`results/processed/milestone7-pilot/` and exploratory SVG figure prototypes to
`results/figures/milestone7-pilot/`. These pilot figures are technical,
exploratory outputs only.

The frozen Milestone 8 plan is in `docs/experiment-plan.md`; the planned sweep
matrix is in `experiments/manifests/confirmatory_m8_manifest.json`.

## Confirmatory Manifest Runner

Dry-run the frozen primary manifest without executing experiments:

```bash
python3 experiments/scripts/run_confirmatory_manifest.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --dry-run
```

Run a tiny canary from the manifest before any long execution:

```bash
python3 experiments/scripts/run_confirmatory_manifest.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --max-runs 4 \
  --output-dir /tmp/swarmgov-confirmatory-canary
```

The full primary manifest expands to `5700` runs. The full primary plus
sensitivity manifest expands to `6500` runs with `--group-kind all`. Existing
completed JSON records are skipped by default so interrupted runs can resume
without overwriting completed results.

Process-level parallel execution is available without changing the manifest or
seed policy:

```bash
python3 experiments/scripts/run_confirmatory_manifest.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8 \
  --workers 8
```

Per-run records use the compact `confirmatory_compact_v1` schema documented in
`docs/confirmatory-output-format.md`. The runner stores final metrics,
provenance, graph metadata, attack metadata, communication metrics, and sampled
regret curves, but excludes raw per-round actions, raw rewards, agent-state
snapshots, and verbose diagnostics.

Curve storage can be bounded explicitly:

```bash
python3 experiments/scripts/run_confirmatory_manifest.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --max-runs 4 \
  --max-curve-points 2000 \
  --output-dir /tmp/swarmgov-confirmatory-canary
```

Validate a completed result directory before aggregation:

```bash
python3 experiments/scripts/validate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8
```

The validator expands the same manifest, checks compact schema compatibility,
and fails on missing, failed, duplicated, unexpected, or incompatible run
records. For a canary directory, pass the same `--max-runs`, `--max-seeds`, or
group filters used to create that canary.

Aggregate a validated result directory into processed CSV tables:

```bash
python3 experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The aggregator writes `run_metrics.csv`, `per_agent_regret.csv`,
`regret_curves.csv`, `paired_differences.csv`, `validation_report.json`, and
`aggregation_summary.json`. It blocks if validation fails. The processed
tables are deterministic inputs for later statistical analysis, not final
scientific claims.

Summarize processed tables with confidence intervals:

```bash
python3 experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8
```

The statistics step writes `condition_summary.csv`, `curve_summary.csv`,
`paired_summary.csv`, and `statistics_summary.json`. Paired summaries use a
deterministic bootstrap over matched seeds; condition and curve summaries use
normal-approximation intervals across seeds.

Generate SVG figures and compact report tables from the statistics:

```bash
python3 experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8
```

This writes final-regret, regret-curve, paired-difference, fairness, and
communication-vs-regret SVGs plus compact CSV/Markdown tables. The figures
inherit the status of their input data: canary inputs remain technical
validation only.

The report-local copies of the main SVGs are stored under `report/figures/`.

The completed primary outputs in this workspace are:

```text
results/processed/confirmatory-m8/
results/figures/confirmatory-m8/
```

Key generated files include `condition_summary.csv`, `paired_summary.csv`,
`final_regret_by_algorithm.svg`, `paired_regret_differences.svg`,
`fairness_worst_decile.svg`, `communication_vs_regret.svg`, and
`report_tables.md`.

Run the bounded end-to-end confirmatory canary in one command:

```bash
python3 experiments/scripts/run_confirmatory_canary_pipeline.py \
  --output-root results/canary/confirmatory-m8-e2e \
  --max-runs 2
```

The canary executes runner, validator, aggregator, statistics, and figure
generation over a tiny manifest slice. It writes a
`canary_pipeline_summary.json` under the output root and remains technical
validation only, not scientific evidence.

Run the full Milestone 8 primary pipeline automatically:

```bash
python3 experiments/scripts/run_milestone8_pipeline.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --raw-dir results/raw/confirmatory-m8 \
  --processed-dir results/processed/confirmatory-m8 \
  --figures-dir results/figures/confirmatory-m8 \
  --workers 12 \
  --overwrite-derived
```

Add `--detach --notify` to launch it in the background. The pipeline resumes
existing completed raw records, validates the full primary grid, regenerates
processed tables, computes confidence intervals, generates figures, runs lint
and tests, and writes status/log files under
`results/raw/confirmatory-m8/_milestone8_pipeline/`.

## Static Local Viewer

Generate a browser-openable HTML viewer for the exploratory Milestone 7
artifacts:

```bash
python3 experiments/scripts/build_static_viewer.py
```

Open `results/viewer/milestone7/index.html` directly in a browser. The viewer
uses local CSV/JSON/SVG files only, requires no server, and does not add
runtime dependencies.

The viewer is an exploratory Milestone 7 viewer. For the completed Milestone 8
confirmatory results, open the SVG files in `results/figures/confirmatory-m8/`
or the copies in `report/figures/` directly in a browser.

## Repository Structure

```text
configs/      reproducible smoke, pilot, and dynamic configurations
docs/         research plan, threat model, metrics, result interpretation
experiments/  manifest runners, validators, aggregation, statistics, figures
report/       Milestone 9 paper draft, application material, report figures
results/      local raw, processed, figure, and viewer artifacts
src/          swarmgov Python package
tests/        unit, integration, and regression tests
```

## Reproducibility

Runs are configured from YAML or manifest files and use deterministic component
seed streams derived from NumPy `SeedSequence`. Confirmatory aggregation is
blocked unless validation passes. The completed primary validation report is:

```text
results/processed/confirmatory-m8/validation_report.json
```

It records `5700` expected runs, `5700` completed runs, and `0` failed,
missing, duplicated, or incompatible records.

## License And Citation

No open-source license has been selected yet. Treat the repository as
all-rights-reserved until the project owner chooses a license.

Suggested citation while the project is a draft:

```text
Francesco Rosciori. SwarmGov-R: Robust Collective Learning under
Misinformation. Research project draft, 2026.
```
