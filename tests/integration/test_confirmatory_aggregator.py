from __future__ import annotations

import csv
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "experiments" / "scripts" / "run_confirmatory_manifest.py"
AGGREGATOR = (
    REPO_ROOT / "experiments" / "scripts" / "aggregate_confirmatory_results.py"
)
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_confirmatory_aggregator_writes_tidy_tables(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    manifest = _tiny_manifest(
        group_name="aggregator_clean_static",
        algorithms=["independent", "mean", "median"],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(input_dir),
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(AGGREGATOR),
            "--manifest",
            str(manifest_path),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "aggregation_status=completed" in completed.stdout
    run_metrics = _read_csv(output_dir / "run_metrics.csv")
    per_agent = _read_csv(output_dir / "per_agent_regret.csv")
    curves = _read_csv(output_dir / "regret_curves.csv")
    paired = _read_csv(output_dir / "paired_differences.csv")
    summary = json.loads(
        (output_dir / "aggregation_summary.json").read_text(encoding="utf-8")
    )

    assert len(run_metrics) == 3
    assert len(per_agent) == 18
    assert len(curves) == 36
    assert len(paired) == 3
    assert summary["schema_version"] == "confirmatory_aggregate_v1"
    assert summary["validation_status"] == "passed"
    assert summary["row_counts"]["run_metrics"] == 3
    assert {row["comparison"] for row in paired} == {
        "vs_independent",
        "vs_mean",
    }
    assert {
        (row["comparison"], row["target_algorithm_label"]) for row in paired
    } == {
        ("vs_independent", "mean"),
        ("vs_independent", "median"),
        ("vs_mean", "median"),
    }


def test_confirmatory_aggregator_blocks_unvalidated_inputs(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    input_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    manifest = _tiny_manifest(
        group_name="aggregator_incomplete_static",
        algorithms=["independent", "mean"],
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(input_dir),
            "--max-runs",
            "1",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(AGGREGATOR),
            "--manifest",
            str(manifest_path),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "aggregation_status=blocked_by_validation" in completed.stdout
    assert (output_dir / "validation_report.json").exists()
    assert not (output_dir / "run_metrics.csv").exists()
    report = json.loads((output_dir / "validation_report.json").read_text())
    assert report["status"] == "failed"
    assert report["counts"]["missing_records"] == 1


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tiny_manifest(*, group_name: str, algorithms: list[str]) -> dict[str, object]:
    loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = deepcopy(loaded)
    manifest["manifest_name"] = "tiny-confirmatory-aggregator-test"
    manifest["fixed_hyperparameters"]["agents"] = 6
    manifest["fixed_hyperparameters"]["horizon"] = 12
    manifest["fixed_hyperparameters"]["arms"] = 3
    manifest["fixed_hyperparameters"]["arm_means_easy_gap"] = [0.75, 0.55, 0.35]
    manifest["fixed_hyperparameters"]["dynamic_topology"]["change_round"] = 6
    manifest["run_seeds"] = {
        "type": "inclusive_range",
        "start": 1000,
        "end": 1000,
        "count": 1,
    }
    manifest["topology_parameters"] = {
        "ring": {
            "family": "ring",
            "parameters": {},
        }
    }
    manifest["primary_run_groups"] = [
        {
            "name": group_name,
            "topologies": ["ring"],
            "topology_mode": "static",
            "algorithms": algorithms,
            "attack": {
                "strategy": "no_attack",
                "byzantine_fraction": 0.0,
                "placement": "none",
                "target_arm": None,
                "inflated_mean": 1.0,
            },
            "seed_count": 1,
            "planned_runs": len(algorithms),
        }
    ]
    manifest["sensitivity_run_groups"] = []
    manifest["run_count_estimate"] = {
        "primary_planned_runs": len(algorithms),
        "sensitivity_planned_runs": 0,
        "total_planned_runs": len(algorithms),
    }
    return manifest
