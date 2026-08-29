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
SUMMARIZER = (
    REPO_ROOT / "experiments" / "scripts" / "summarize_confirmatory_results.py"
)
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_confirmatory_statistics_writes_ci_summaries(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tiny_manifest.json"
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    stats_dir = tmp_path / "statistics"
    manifest = _tiny_manifest(
        group_name="statistics_clean_static",
        algorithms=["independent", "mean", "median"],
        seed_count=2,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(raw_dir),
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(AGGREGATOR),
            "--manifest",
            str(manifest_path),
            "--input-dir",
            str(raw_dir),
            "--output-dir",
            str(processed_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SUMMARIZER),
            "--input-dir",
            str(processed_dir),
            "--output-dir",
            str(stats_dir),
            "--bootstrap-iterations",
            "200",
            "--bootstrap-seed",
            "17",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "statistics_status=completed" in completed.stdout
    condition_summary = _read_csv(stats_dir / "condition_summary.csv")
    curve_summary = _read_csv(stats_dir / "curve_summary.csv")
    paired_summary = _read_csv(stats_dir / "paired_summary.csv")
    summary = json.loads(
        (stats_dir / "statistics_summary.json").read_text(encoding="utf-8")
    )

    assert len(condition_summary) == 24
    assert len(curve_summary) == 72
    assert len(paired_summary) == 15
    assert summary["schema_version"] == "confirmatory_statistics_v1"
    assert summary["bootstrap_iterations"] == 200
    assert summary["bootstrap_seed"] == 17
    assert summary["row_counts"]["paired_summary"] == 15

    regret_rows = [
        row
        for row in condition_summary
        if row["algorithm_label"] == "mean"
        and row["metric"] == "mean_per_agent_regret"
    ]
    assert len(regret_rows) == 1
    assert regret_rows[0]["n"] == "2"
    assert regret_rows[0]["ci_method"] == "normal_approximation"
    assert float(regret_rows[0]["ci95_low"]) <= float(regret_rows[0]["mean"])
    assert float(regret_rows[0]["ci95_high"]) >= float(regret_rows[0]["mean"])

    paired_rows = [
        row
        for row in paired_summary
        if row["comparison"] == "vs_independent"
        and row["target_algorithm_label"] == "mean"
        and row["metric"] == "mean_per_agent_regret_difference"
    ]
    assert len(paired_rows) == 1
    assert paired_rows[0]["n_pairs"] == "2"
    assert paired_rows[0]["ci_method"] == "paired_percentile_bootstrap"
    assert paired_rows[0]["bootstrap_iterations"] == "200"
    assert paired_rows[0]["bootstrap_seed"] == "17"


def test_confirmatory_statistics_rejects_unvalidated_aggregation(
    tmp_path: Path,
) -> None:
    processed_dir = tmp_path / "processed"
    stats_dir = tmp_path / "statistics"
    processed_dir.mkdir()
    (processed_dir / "aggregation_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "confirmatory_aggregate_v1",
                "validation_status": "failed",
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SUMMARIZER),
            "--input-dir",
            str(processed_dir),
            "--output-dir",
            str(stats_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "validation status is not passed" in completed.stderr
    assert not (stats_dir / "condition_summary.csv").exists()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tiny_manifest(
    *,
    group_name: str,
    algorithms: list[str],
    seed_count: int,
) -> dict[str, object]:
    loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = deepcopy(loaded)
    manifest["manifest_name"] = "tiny-confirmatory-statistics-test"
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
            "seed_count": seed_count,
            "planned_runs": len(algorithms) * seed_count,
        }
    ]
    manifest["sensitivity_run_groups"] = []
    manifest["run_count_estimate"] = {
        "primary_planned_runs": len(algorithms) * seed_count,
        "sensitivity_planned_runs": 0,
        "total_planned_runs": len(algorithms) * seed_count,
    }
    return manifest
