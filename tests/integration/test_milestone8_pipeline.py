from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "experiments" / "scripts" / "run_milestone8_pipeline.py"
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_milestone8_pipeline_runs_bounded_manifest_slice(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    figures_dir = tmp_path / "figures"
    log_dir = tmp_path / "logs"
    manifest = _tiny_manifest(seed_count=2)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(PIPELINE),
            "--manifest",
            str(manifest_path),
            "--raw-dir",
            str(raw_dir),
            "--processed-dir",
            str(processed_dir),
            "--figures-dir",
            str(figures_dir),
            "--log-dir",
            str(log_dir),
            "--workers",
            "2",
            "--bootstrap-iterations",
            "50",
            "--bootstrap-seed",
            "17",
            "--max-curve-points",
            "5",
            "--overwrite-derived",
            "--skip-final-checks",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == ""
    assert (raw_dir / "manifest_run_summary.json").exists()
    assert (processed_dir / "aggregation_summary.json").exists()
    assert (processed_dir / "statistics_summary.json").exists()
    assert (figures_dir / "figure_summary.json").exists()
    assert (log_dir / "milestone8_pipeline.done.json").exists()

    status = json.loads(
        (log_dir / "milestone8_pipeline_status.json").read_text(encoding="utf-8")
    )
    assert status["status"] == "completed"
    assert status["workers"] == 2
    assert status["stage_count"] == 5
    assert [stage["stage"] for stage in status["stages"]] == [
        "run",
        "validate",
        "aggregate",
        "statistics",
        "figures",
    ]
    assert status["skip_final_checks"] is True
    assert all(Path(stage["log_path"]).exists() for stage in status["stages"])


def _tiny_manifest(*, seed_count: int) -> dict[str, object]:
    loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = deepcopy(loaded)
    manifest["manifest_name"] = "tiny-milestone8-pipeline-test"
    manifest["fixed_hyperparameters"]["agents"] = 6
    manifest["fixed_hyperparameters"]["horizon"] = 12
    manifest["fixed_hyperparameters"]["arms"] = 3
    manifest["fixed_hyperparameters"]["arm_means_easy_gap"] = [0.75, 0.55, 0.35]
    manifest["fixed_hyperparameters"]["dynamic_topology"]["change_round"] = 6
    manifest["run_seeds"] = {
        "type": "inclusive_range",
        "start": 1000,
        "end": 1000 + seed_count - 1,
        "count": seed_count,
    }
    manifest["topology_parameters"] = {
        "ring": {
            "family": "ring",
            "parameters": {},
        }
    }
    manifest["primary_run_groups"] = [
        {
            "name": "tiny_clean_static",
            "topologies": ["ring"],
            "topology_mode": "static",
            "algorithms": ["independent", "mean"],
            "attack": {
                "strategy": "no_attack",
                "byzantine_fraction": 0.0,
                "placement": "none",
                "target_arm": None,
                "inflated_mean": 1.0,
            },
            "seed_count": seed_count,
            "planned_runs": 2 * seed_count,
        }
    ]
    manifest["sensitivity_run_groups"] = []
    manifest["run_count_estimate"] = {
        "primary_planned_runs": 2 * seed_count,
        "sensitivity_planned_runs": 0,
        "total_planned_runs": 2 * seed_count,
    }
    return manifest
