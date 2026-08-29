# Confirmatory Artifact Reproduction

Status: public artifact instructions for `v0.1.0-m8-primary`, created on
2026-08-29.

This document explains how an external reader can verify the archived
Milestone 8 primary artifacts and regenerate processed tables and figures
without repeating the full simulation sweep.

## Artifact Version

```text
artifact_version: v0.1.0-m8-primary
manifest: experiments/manifests/confirmatory_m8_manifest.json
manifest_status: completed_primary
validated_primary_runs: 5700
failed_primary_runs: 0
```

The raw result records were generated before the repository had a Git history,
so the raw per-run provenance cannot report a source commit hash. The public
release tag and checksums provide the archival provenance for the downloadable
artifact bundle.

## Release Assets

The intended GitHub Release or Zenodo record should include:

```text
swarmgov-r-m8-primary-artifacts-v0.1.0-m8-primary.tar.gz
SHA256SUMS.txt
```

The artifact archive contains:

```text
experiments/manifests/confirmatory_m8_manifest.json
results/raw/confirmatory-m8/
results/processed/confirmatory-m8/
results/figures/confirmatory-m8/
```

The raw directory contains the 5700 primary run records plus pipeline metadata.
The processed directory contains intermediate and summary tables. The figures
directory contains regenerated SVG figures and compact report tables.

## Verify Checksums

After downloading the release assets into one directory, run:

```bash
shasum -a 256 -c SHA256SUMS.txt
```

The command should report `OK` for every listed file.

## Restore Artifacts

From the repository root, extract the archive:

```bash
tar -xzf swarmgov-r-m8-primary-artifacts-v0.1.0-m8-primary.tar.gz
```

This restores the `results/raw/confirmatory-m8/`,
`results/processed/confirmatory-m8/`, and `results/figures/confirmatory-m8/`
trees expected by the scripts.

## Install Dependencies

Create and activate a virtual environment, then install the locked
dependencies and the local package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
```

## Validate Raw Records

Validate the raw records against the completed primary manifest:

```bash
python experiments/scripts/validate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --output-dir results/raw/confirmatory-m8 \
  --group-kind primary
```

Expected result:

```text
status: passed
expected_runs: 5700
valid_completed_runs: 5700
failed_records: 0
```

## Regenerate Tables And Figures

Regenerate processed tables from raw records:

```bash
python experiments/scripts/aggregate_confirmatory_results.py \
  --manifest experiments/manifests/confirmatory_m8_manifest.json \
  --input-dir results/raw/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8 \
  --group-kind primary \
  --overwrite
```

Regenerate statistical summaries:

```bash
python experiments/scripts/summarize_confirmatory_results.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/processed/confirmatory-m8 \
  --bootstrap-iterations 2000 \
  --bootstrap-seed 20260827 \
  --overwrite
```

Regenerate figures and report tables:

```bash
python experiments/scripts/generate_confirmatory_figures.py \
  --input-dir results/processed/confirmatory-m8 \
  --output-dir results/figures/confirmatory-m8 \
  --overwrite
```

These commands do not repeat the full simulation sweep. They consume archived
raw records and regenerate the derived tables and figures.

## Important Scope Note

The archive is evidence for the completed Milestone 8 primary grid only. It
does not include completed sensitivity runs, hard-gap experiments, adaptive
attacks, arbitrary-message Byzantine attacks, or reputation weighting.
