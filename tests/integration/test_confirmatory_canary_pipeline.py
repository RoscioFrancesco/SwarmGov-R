from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT / "experiments" / "scripts" / "run_confirmatory_canary_pipeline.py"
)


def test_confirmatory_canary_pipeline_runs_end_to_end(tmp_path: Path) -> None:
    output_root = tmp_path / "confirmatory-canary"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--max-runs",
            "2",
            "--max-curve-points",
            "5",
            "--bootstrap-iterations",
            "50",
            "--bootstrap-seed",
            "17",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "canary_pipeline_status=completed" in completed.stdout
    assert (output_root / "raw" / "manifest_run_summary.json").exists()
    assert (output_root / "validation" / "validation_report.json").exists()
    assert (output_root / "processed" / "aggregation_summary.json").exists()
    assert (output_root / "statistics" / "statistics_summary.json").exists()
    assert (output_root / "figures" / "figure_summary.json").exists()
    assert (output_root / "figures" / "report_tables.md").exists()

    pipeline_summary = json.loads(
        (output_root / "canary_pipeline_summary.json").read_text(encoding="utf-8")
    )
    assert pipeline_summary["status"] == "completed"
    assert pipeline_summary["max_runs"] == 2
    assert pipeline_summary["bootstrap"]["iterations"] == 50
    assert "not confirmatory scientific evidence" in pipeline_summary["notes"]
    assert [stage["stage"] for stage in pipeline_summary["stages"]] == [
        "run",
        "validate",
        "aggregate",
        "statistics",
        "figures",
    ]
    assert all(stage["returncode"] == 0 for stage in pipeline_summary["stages"])

    validation_report = json.loads(
        (output_root / "validation" / "validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert validation_report["status"] == "passed"
    assert validation_report["expected_runs"] == 2

    figure_summary = json.loads(
        (output_root / "figures" / "figure_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert figure_summary["schema_version"] == "confirmatory_figures_v1"


def test_confirmatory_canary_pipeline_rejects_nonempty_output_root(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "confirmatory-canary"
    output_root.mkdir()
    (output_root / "existing.txt").write_text("existing", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output-root",
            str(output_root),
            "--max-runs",
            "1",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "output root is not empty" in completed.stderr
    assert not (output_root / "canary_pipeline_summary.json").exists()
