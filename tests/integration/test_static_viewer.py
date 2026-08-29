from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "experiments" / "scripts" / "build_static_viewer.py"


def test_static_viewer_builds_self_contained_local_html(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    figure_dir = tmp_path / "figures"
    output_path = tmp_path / "viewer" / "index.html"
    manifest_path = tmp_path / "manifest.json"
    processed_dir.mkdir()
    figure_dir.mkdir()

    _write_pilot_inputs(processed_dir)
    _write_figures(figure_dir)
    manifest_path.write_text(
        json.dumps(
            {
                "run_count_estimate": {
                    "primary_planned_runs": 10,
                    "total_planned_runs": 12,
                }
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--processed-dir",
            str(processed_dir),
            "--figure-dir",
            str(figure_dir),
            "--output",
            str(output_path),
            "--manifest",
            str(manifest_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    html = output_path.read_text(encoding="utf-8")
    assert f"viewer={output_path}" in completed.stdout
    assert "SwarmGov-R Milestone 7 Viewer" in html
    assert "Exploratory pilot only - not confirmatory evidence" in html
    assert "exploratory_regret_curves_ring_clean_static.svg" in html
    assert "fetch(" not in html
    assert "http://" not in html
    assert "https://" not in html


def _write_pilot_inputs(processed_dir: Path) -> None:
    (processed_dir / "final_regret_summary.csv").write_text(
        dedent(
            """\
            topology,condition,topology_mode,aggregation,completed_runs,failed_runs,mean_final_honest_regret,ci95_low,ci95_high,mean_best_arm_identification_rate,mean_worst_decile_honest_regret,mean_fallback_frequency,mean_runtime_seconds,exploratory_only
            ring,clean,static,independent,2,0,1.2,1.0,1.4,0.5,2.0,0.0,0.1,True
            ring,clean,static,mean,2,0,0.8,0.7,0.9,1.0,1.5,0.0,0.2,True
            """
        ),
        encoding="utf-8",
    )
    (processed_dir / "paired_differences.csv").write_text(
        dedent(
            """\
            topology,condition,topology_mode,aggregation,baseline,paired_seeds,mean_paired_difference_final_mean_regret,ci95_low,ci95_high,exploratory_only
            ring,clean,static,mean,independent_static,2,-0.4,-0.5,-0.3,True
            """
        ),
        encoding="utf-8",
    )
    (processed_dir / "pilot_summary.json").write_text(
        json.dumps(
            {
                "planned_runs": 2,
                "completed_runs": 2,
                "failed_runs": 0,
            }
        ),
        encoding="utf-8",
    )
    (processed_dir / "runtime_estimate.json").write_text(
        json.dumps(
            {
                "total_runtime_seconds": 2.5,
                "mean_runtime_seconds_per_run": 1.25,
                "pilot_seed_count": 2,
                "pilot_horizon": 12,
                "pilot_agents": 6,
                "confirmatory_projection": {
                    "estimated_primary_runtime_hours_single_process": 0.5,
                    "estimated_total_runtime_hours_single_process": 0.7,
                },
            }
        ),
        encoding="utf-8",
    )


def _write_figures(figure_dir: Path) -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    (figure_dir / "exploratory_final_regret_overview.svg").write_text(
        svg,
        encoding="utf-8",
    )
    (figure_dir / "exploratory_regret_curves_ring_clean_static.svg").write_text(
        svg,
        encoding="utf-8",
    )
