from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "experiments" / "scripts" / "run_milestone7_pilot.py"


def test_milestone7_pilot_dry_run_validates_configured_grid() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            "configs/pilot_m7.yaml",
            "--max-seeds",
            "1",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "planned_runs=63" in completed.stdout
    assert "run_seeds=[0]" in completed.stdout


def test_milestone7_pilot_writes_processed_tables_and_figures(tmp_path: Path) -> None:
    config_path = tmp_path / "tiny_m7_pilot.yaml"
    output_dir = tmp_path / "processed"
    figure_dir = tmp_path / "figures"
    config_path.write_text(
        dedent(
            """
            name: tiny-milestone7-pilot
            stage: stage_b
            description: Tiny Milestone 7 pilot test.

            seeds:
              master: 20260826
              run_seeds: [0, 1]
              streams: [environment, graph, agents, attack, simulation, analysis]

            population:
              agents: 6

            bandit:
              arms: 3
              arm_means: [0.75, 0.55, 0.35]
              reward_family: bernoulli

            algorithm:
              exploration_c: 1.0

            communication:
              interval: 1

            aggregations: [mean, median, trimmed_mean]
            include_independent_baseline: true

            trimmed_mean:
              trim_count: 1
              small_neighborhood_policy: median_fallback

            topology_modes: [static, dynamic]

            dynamic_topology:
              change_round: 6
              rewire_fraction: 0.2
              preserve_connectivity: true

            topologies:
              ring:
                family: ring
                parameters: {}

            conditions:
              clean:
                byzantine_fraction: 0.0
                byzantine_placement: none
                attack:
                  strategy: no_attack
                  target_arm: null
                  inflated_mean: 1.0

            experiment:
              horizon: 12
              output_dir: ignored-by-test
              figure_dir: ignored-by-test
              overwrite: true
            """
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--figure-dir",
            str(figure_dir),
            "--max-seeds",
            "1",
            "--progress-interval",
            "0",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    pilot_summary = json.loads((output_dir / "pilot_summary.json").read_text())
    runtime_estimate = json.loads((output_dir / "runtime_estimate.json").read_text())

    assert pilot_summary["status"] == "completed"
    assert pilot_summary["planned_runs"] == 7
    assert pilot_summary["completed_runs"] == 7
    assert pilot_summary["exploratory_only"] is True
    assert runtime_estimate["status"] == "observed"
    assert (output_dir / "final_regret_summary.csv").exists()
    assert (output_dir / "paired_differences.csv").exists()
    assert (
        figure_dir / "exploratory_regret_curves_ring_clean_static.svg"
    ).exists()
    assert (
        figure_dir / "exploratory_regret_curves_ring_clean_dynamic.svg"
    ).exists()
    assert (figure_dir / "exploratory_final_regret_overview.svg").exists()
