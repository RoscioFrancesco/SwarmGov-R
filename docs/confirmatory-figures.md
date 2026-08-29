# Confirmatory Figures And Tables

Status: Milestone 8 Step 6 figure/table contract, created on 2026-08-27.

This document describes
`experiments/scripts/generate_confirmatory_figures.py`, which reads Step 5
statistical summaries and generates SVG figures plus compact report tables.
The script does not run simulations, does not recompute statistics, and does
not modify raw or processed result records.

## Command

```bash
python experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8
```

Existing figure/table artifacts are not overwritten unless `--overwrite` is
provided.

## Inputs

The input directory must contain:

- `statistics_summary.json`;
- `condition_summary.csv`;
- `curve_summary.csv`;
- `paired_summary.csv`.

`statistics_summary.json` must use:

```text
schema_version = confirmatory_statistics_v1
```

This preserves the analysis order:

```text
raw compact records -> validation -> processed tables -> statistics -> figures
```

## Outputs

The figure schema version is:

```text
confirmatory_figures_v1
```

Default output directory:

```text
results/figures/confirmatory-m8/
```

Files:

- `final_regret_by_algorithm.svg`;
- `mean_regret_curves.svg`;
- `paired_regret_differences.svg`;
- `fairness_worst_decile.svg`;
- `communication_vs_regret.svg`;
- `final_regret_table.csv`;
- `paired_regret_table.csv`;
- `report_tables.md`;
- `figure_summary.json`.

SVG figures are generated directly from CSV summaries using only the Python
standard library. They are deterministic and can be regenerated from saved
processed data.

## Interpretation Rules

The generated figures and tables inherit the status of their input data.
If the input is a canary or partial manifest slice, the outputs are technical
validation artifacts only. Scientific claims require the completed and
validated confirmatory matrix.

`paired_regret_differences.svg` and `paired_regret_table.csv` report
target-minus-baseline differences. Negative regret differences mean the target
algorithm has lower regret than the baseline for the summarized condition.

`mean_regret_curves.svg` selects one representative curve condition from
`curve_summary.csv`, preferring the clean static all-topology group when
present. Additional figure variants may be added later, but they must continue
to consume saved statistical summaries rather than raw simulation state.

Any incompatible change to these outputs must bump `confirmatory_figures_v1`
and add a dated decision-log entry.
