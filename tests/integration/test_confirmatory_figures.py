from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURES = REPO_ROOT / "experiments" / "scripts" / "generate_confirmatory_figures.py"


def test_confirmatory_figure_generator_writes_figures_and_tables(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "statistics"
    output_dir = tmp_path / "figures"
    input_dir.mkdir()
    _write_statistics_fixture(input_dir)

    completed = subprocess.run(
        [
            sys.executable,
            str(FIGURES),
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

    assert "figure_status=completed" in completed.stdout
    expected = {
        "final_regret_by_algorithm.svg",
        "mean_regret_curves.svg",
        "paired_regret_differences.svg",
        "fairness_worst_decile.svg",
        "communication_vs_regret.svg",
        "final_regret_table.csv",
        "paired_regret_table.csv",
        "report_tables.md",
        "figure_summary.json",
    }
    assert {path.name for path in output_dir.iterdir()} == expected
    assert (output_dir / "final_regret_by_algorithm.svg").read_text().startswith(
        '<svg xmlns="http://www.w3.org/2000/svg"'
    )
    summary = json.loads((output_dir / "figure_summary.json").read_text())
    assert summary["schema_version"] == "confirmatory_figures_v1"
    assert summary["source_rows"]["condition_summary"] == 6
    assert summary["source_rows"]["paired_summary"] == 1
    table_rows = _read_csv(output_dir / "final_regret_table.csv")
    assert len(table_rows) == 2
    assert {row["algorithm"] for row in table_rows} == {"independent", "mean"}


def test_confirmatory_figure_generator_rejects_bad_statistics_schema(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "statistics"
    output_dir = tmp_path / "figures"
    input_dir.mkdir()
    _write_statistics_fixture(input_dir)
    (input_dir / "statistics_summary.json").write_text(
        json.dumps({"schema_version": "old_schema"}),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(FIGURES),
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

    assert completed.returncode != 0
    assert "unsupported statistics schema version" in completed.stderr
    assert not output_dir.exists()


def _write_statistics_fixture(input_dir: Path) -> None:
    (input_dir / "statistics_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "confirmatory_statistics_v1",
                "row_counts": {
                    "condition_summary": 6,
                    "curve_summary": 4,
                    "paired_summary": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    _write_csv(
        input_dir / "condition_summary.csv",
        [
            _condition_row("independent", "mean_per_agent_regret", 12.0, 10.0, 14.0),
            _condition_row("mean", "mean_per_agent_regret", 8.0, 7.0, 9.0),
            _condition_row(
                "independent",
                "worst_decile_honest_regret",
                16.0,
                14.0,
                18.0,
            ),
            _condition_row("mean", "worst_decile_honest_regret", 11.0, 9.0, 13.0),
            _condition_row("independent", "messages_sent", 0.0, 0.0, 0.0),
            _condition_row("mean", "messages_sent", 120.0, 115.0, 125.0),
        ],
    )
    _write_csv(
        input_dir / "curve_summary.csv",
        [
            _curve_row("independent", 1, 0.5),
            _curve_row("independent", 12, 12.0),
            _curve_row("mean", 1, 0.4),
            _curve_row("mean", 12, 8.0),
        ],
    )
    _write_csv(
        input_dir / "paired_summary.csv",
        [
            {
                "comparison": "vs_independent",
                "baseline_algorithm_label": "independent",
                "target_algorithm_label": "mean",
                "group_kind": "primary",
                "group_name": "clean_static_all_topologies",
                "topology": "ring",
                "topology_mode": "static",
                "attack_strategy": "no_attack",
                "byzantine_fraction": "0.0",
                "byzantine_placement": "none",
                "target_arm": "",
                "inflated_mean": "1.0",
                "metric": "mean_per_agent_regret_difference",
                "n_pairs": "2",
                "mean_difference": "-4.0",
                "std_difference": "0.5",
                "sem_difference": "0.25",
                "ci95_low": "-4.5",
                "ci95_high": "-3.5",
                "min_difference": "-4.5",
                "max_difference": "-3.5",
                "ci_method": "paired_percentile_bootstrap",
                "bootstrap_iterations": "200",
                "bootstrap_seed": "17",
            }
        ],
    )


def _condition_row(
    algorithm: str,
    metric: str,
    mean: float,
    low: float,
    high: float,
) -> dict[str, object]:
    return {
        "group_kind": "primary",
        "group_name": "clean_static_all_topologies",
        "topology": "ring",
        "topology_mode": "static",
        "algorithm_label": algorithm,
        "aggregation": "mean",
        "attack_strategy": "no_attack",
        "byzantine_fraction": "0.0",
        "byzantine_placement": "none",
        "target_arm": "",
        "inflated_mean": "1.0",
        "metric": metric,
        "n": "2",
        "mean": mean,
        "std": "0.5",
        "sem": "0.25",
        "ci95_low": low,
        "ci95_high": high,
        "min": low,
        "max": high,
        "ci_method": "normal_approximation",
    }


def _curve_row(algorithm: str, round_index: int, mean: float) -> dict[str, object]:
    row = _condition_row(algorithm, "mean_regret", mean, mean - 0.1, mean + 0.1)
    row["round"] = round_index
    return row


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
