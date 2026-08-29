from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "experiments" / "scripts" / "run_confirmatory_manifest.py"
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_confirmatory_runner_dry_run_expands_frozen_primary_manifest() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "planned_runs=5700" in completed.stdout
    assert "expected_full_primary_runs=5700" in completed.stdout
    assert "expected_full_total_runs=6500" in completed.stdout
    assert (
        "primary_clean_static_all_topologies_seed-1000_complete_static_independent"
        in completed.stdout
    )


def test_confirmatory_runner_dry_run_expands_full_manifest() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--group-kind",
            "all",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "planned_runs=6500" in completed.stdout


def test_confirmatory_runner_canary_writes_compact_records_and_resumes(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    output_dir = tmp_path / "confirmatory"
    manifest = _tiny_manifest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    first = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--max-runs",
            "2",
            "--workers",
            "2",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "completed_runs=2 skipped_existing_runs=0 failed_runs=0" in first.stdout
    records = sorted(output_dir.glob("*.json"))
    run_records = [path for path in records if path.name != "manifest_run_summary.json"]
    assert len(run_records) == 2
    record = json.loads(run_records[0].read_text(encoding="utf-8"))
    assert record["status"] == "completed"
    assert record["planned_run"]["seed"] == 1000
    assert record["result"]["schema_version"] == "confirmatory_compact_v1"
    assert record["result"]["payload_policy"]["raw_actions_stored"] is False
    assert record["result"]["payload_policy"]["raw_rewards_stored"] is False
    assert "actions_by_round" not in record["result"]
    assert "rewards_by_round" not in record["result"]
    assert len(record["result"]["curves"]["mean_regret"]) == 12
    assert len(record["result"]["curves"]["rounds"]) == 12
    assert record["result"]["metrics"]["mean_per_agent_regret"] >= 0.0

    second = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--max-runs",
            "2",
            "--workers",
            "2",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "completed_runs=0 skipped_existing_runs=2 failed_runs=0" in second.stdout
    summary = json.loads(
        (output_dir / "manifest_run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["planned_runs"] == 2
    assert summary["skipped_existing_runs"] == 2
    assert summary["workers"] == 2


def test_confirmatory_runner_repairs_invalid_existing_record(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    output_dir = tmp_path / "confirmatory"
    manifest = _tiny_manifest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    first_run = (
        "primary_tiny_clean_static_seed-1000_ring_static_independent_"
        "no_attack_none.json"
    )
    output_dir.mkdir()
    (output_dir / first_run).write_text("{partial", encoding="utf-8")

    blocked = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--max-runs",
            "1",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert blocked.returncode != 0
    assert "existing record is not a valid completed record" in blocked.stderr

    repaired = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--max-runs",
            "1",
            "--repair-invalid-existing",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "completed_runs=1 skipped_existing_runs=0 failed_runs=0" in repaired.stdout
    record = json.loads((output_dir / first_run).read_text(encoding="utf-8"))
    assert record["status"] == "completed"
    assert record["result"]["schema_version"] == "confirmatory_compact_v1"


def _tiny_manifest() -> dict[str, object]:
    loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = deepcopy(loaded)
    manifest["manifest_name"] = "tiny-confirmatory-runner-test"
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
            "seed_count": 1,
            "planned_runs": 2,
        }
    ]
    manifest["sensitivity_run_groups"] = []
    manifest["run_count_estimate"] = {
        "primary_planned_runs": 2,
        "sensitivity_planned_runs": 0,
        "total_planned_runs": 2,
    }
    return manifest
