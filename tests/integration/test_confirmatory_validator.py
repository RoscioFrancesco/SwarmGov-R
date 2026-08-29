from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "experiments" / "scripts" / "run_confirmatory_manifest.py"
VALIDATOR = (
    REPO_ROOT / "experiments" / "scripts" / "validate_confirmatory_results.py"
)
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_confirmatory_validator_accepts_complete_canary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    output_dir = tmp_path / "results"
    report_path = tmp_path / "validation_report.json"
    manifest = _tiny_manifest(
        group_name="validator_clean_static",
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
            str(output_dir),
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
            str(VALIDATOR),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--report-path",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "validation_status=passed" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["expected_runs"] == 2
    assert report["valid_completed_runs"] == 2
    assert report["counts"]["issues"] == 0


def test_confirmatory_validator_detects_bad_result_set(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    output_dir = tmp_path / "results"
    report_path = tmp_path / "validation_report.json"
    group_name = "validator_issue_static"
    algorithms = ["independent", "mean", "median", "trimmed_mean"]
    manifest = _tiny_manifest(group_name=group_name, algorithms=algorithms)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--max-runs",
            "2",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    independent_key = _run_key(group_name, "independent")
    mean_key = _run_key(group_name, "mean")
    median_key = _run_key(group_name, "median")

    mean_path = output_dir / f"{mean_key}.json"
    mean_record = json.loads(mean_path.read_text(encoding="utf-8"))
    mean_record["result"]["schema_version"] = "old_schema"
    mean_path.write_text(json.dumps(mean_record, indent=2), encoding="utf-8")

    independent_record = json.loads(
        (output_dir / f"{independent_key}.json").read_text(encoding="utf-8")
    )
    (output_dir / "duplicate_copy.json").write_text(
        json.dumps(independent_record, indent=2),
        encoding="utf-8",
    )
    (output_dir / f"{median_key}.failed.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "planned_run": _planned_record(group_name, "median"),
                "error": "synthetic validation failure",
                "config_data": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--report-path",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "validation_status=failed" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["counts"]["missing_records"] == 1
    assert report["failed_records"] == 1
    assert report["counts"]["duplicate_run_keys"] == 1
    assert report["counts"]["unexpected_files"] >= 1
    assert report["counts"]["incompatible_records"] >= 1
    assert mean_key in report["incomplete_run_keys"]


def _tiny_manifest(*, group_name: str, algorithms: list[str]) -> dict[str, object]:
    loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = deepcopy(loaded)
    manifest["manifest_name"] = "tiny-confirmatory-validator-test"
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


def _run_key(group_name: str, algorithm: str) -> str:
    return (
        f"primary_{group_name}_seed-1000_ring_static_"
        f"{algorithm}_no_attack_none"
    )


def _planned_record(group_name: str, algorithm: str) -> dict[str, object]:
    aggregation = algorithm if algorithm in {"median", "trimmed_mean"} else "mean"
    return {
        "manifest_name": "tiny-confirmatory-validator-test",
        "group_kind": "primary",
        "group_name": group_name,
        "seed": 1000,
        "topology": "ring",
        "topology_mode": "static",
        "algorithm_label": algorithm,
        "aggregation": aggregation,
        "attack_strategy": "no_attack",
        "byzantine_fraction": 0.0,
        "byzantine_placement": "none",
        "target_arm": None,
        "inflated_mean": 1.0,
        "run_key": _run_key(group_name, algorithm),
    }
