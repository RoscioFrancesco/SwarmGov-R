"""Run the bounded Milestone 5 exploratory robust-aggregation pilot."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from swarmgov.config import StudyConfig  # noqa: E402
from swarmgov.simulation import MultiAgentRunResult, run_multi_agent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/pilot_m5.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Run only the first N configured seeds while preserving the full "
        "topology/condition/aggregation grid for those seeds.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=16,
        help="Print progress every N runs.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec_path = Path(args.config)
    spec = _load_yaml(spec_path)
    output_dir = Path(args.output_dir or spec["experiment"]["output_dir"])
    run_seeds = _selected_run_seeds(spec, args.max_seeds)
    planned = list(_planned_runs(spec, run_seeds))
    print(f"planned_runs={len(planned)}")
    print(f"run_seeds={run_seeds}")
    if args.dry_run:
        return 0

    started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_records: list[dict[str, object]] = []
    curve_records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for run_index, run_spec in enumerate(planned, start=1):
        config_data = _study_config_from_pilot(spec, run_spec)
        try:
            result = run_multi_agent(StudyConfig.from_mapping(config_data), write=False)
            if not isinstance(result, MultiAgentRunResult):
                raise RuntimeError("expected a multi-agent result")
            run_records.append(_run_record(run_spec, result))
            curve_records.extend(_curve_records(run_spec, result))
        except Exception as exc:  # noqa: BLE001
            failures.append({**run_spec, "error": str(exc)})
        if args.progress_interval > 0 and (
            run_index == 1
            or run_index == len(planned)
            or run_index % args.progress_interval == 0
        ):
            elapsed = perf_counter() - started
            print(
                f"progress={run_index}/{len(planned)} "
                f"completed={len(run_records)} failed={len(failures)} "
                f"elapsed_seconds={elapsed:.1f}",
                flush=True,
            )

    summary = _summary_records(run_records)
    _write_csv(output_dir / "final_regret_summary.csv", summary)
    _write_csv(output_dir / "run_metrics.csv", run_records)
    _write_csv(output_dir / "mean_regret_curves.csv", curve_records)
    (output_dir / "pilot_summary.json").write_text(
        json.dumps(
            {
                "status": "completed" if not failures else "completed_with_failures",
                "config": str(spec_path),
                "planned_runs": len(planned),
                "completed_runs": len(run_records),
                "failed_runs": len(failures),
                "configured_run_seeds": spec["seeds"]["run_seeds"],
                "executed_run_seeds": run_seeds,
                "reduced_seed_count": args.max_seeds,
                "runtime_seconds": perf_counter() - started,
                "exploratory_only": True,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_curve_svgs(output_dir, curve_records)
    print(f"completed_runs={len(run_records)} failed_runs={len(failures)}")
    print(f"output_dir={output_dir}")
    return 1 if failures else 0


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("pilot config must be a mapping")
    return loaded


def _selected_run_seeds(spec: dict[str, Any], max_seeds: int | None) -> list[int]:
    run_seeds = [int(seed) for seed in spec["seeds"]["run_seeds"]]
    if max_seeds is None:
        return run_seeds
    if max_seeds <= 0:
        raise ValueError("--max-seeds must be positive")
    return run_seeds[:max_seeds]


def _planned_runs(spec: dict[str, Any], run_seeds: list[int]):
    for seed in run_seeds:
        for topology_name in spec["topologies"]:
            for condition_name in spec["conditions"]:
                for aggregation_name in spec["aggregations"]:
                    yield {
                        "seed": int(seed),
                        "topology": topology_name,
                        "condition": condition_name,
                        "aggregation": aggregation_name,
                    }


def _study_config_from_pilot(
    spec: dict[str, Any],
    run_spec: dict[str, object],
) -> dict[str, object]:
    aggregation = str(run_spec["aggregation"])
    topology = spec["topologies"][run_spec["topology"]]
    condition = spec["conditions"][run_spec["condition"]]
    is_independent = aggregation == "independent"
    algorithm_name = (
        "independent_ucb1" if is_independent else "one_hop_weighted_pooling_ucb1"
    )
    aggregation_method = "mean" if is_independent else aggregation
    trim_count = (
        spec["trimmed_mean"]["trim_count"]
        if aggregation_method == "trimmed_mean"
        else None
    )
    return {
        "name": (
            f"{spec['name']}-{run_spec['condition']}-"
            f"{run_spec['topology']}-{aggregation}"
        ),
        "stage": spec["stage"],
        "description": spec["description"],
        "seeds": {
            "master": spec["seeds"]["master"],
            "streams": spec["seeds"]["streams"],
        },
        "population": {
            "agents": spec["population"]["agents"],
            "byzantine_fraction": condition["byzantine_fraction"],
            "byzantine_placement": condition["byzantine_placement"],
        },
        "bandit": spec["bandit"],
        "algorithm": {
            "name": algorithm_name,
            "parameters": {"exploration_c": spec["algorithm"]["exploration_c"]},
        },
        "graph": topology,
        "communication": {
            "interval": spec["communication"]["interval"],
            "enabled": not is_independent,
        },
        "aggregation": {
            "method": aggregation_method,
            "trim_count": trim_count,
            "trim_fraction": None,
            "small_neighborhood_policy": spec["trimmed_mean"][
                "small_neighborhood_policy"
            ],
            "diagnostics": False,
        },
        "attack": {
            **condition["attack"],
            "diagnostics": False,
        },
        "topology_change": {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": True,
        },
        "experiment": {
            "horizon": spec["experiment"]["horizon"],
            "seeds": [run_spec["seed"]],
            "output_dir": spec["experiment"]["output_dir"],
            "overwrite": spec["experiment"]["overwrite"],
        },
    }


def _run_record(
    run_spec: dict[str, object],
    result: MultiAgentRunResult,
) -> dict[str, object]:
    per_agent = np.asarray(result.per_agent_final_regret, dtype=float)
    arm_events = int(result.aggregation_summary["arm_aggregation_events"])
    fallback_arm_events = int(result.aggregation_summary["fallback_arm_events"])
    fallback_frequency = fallback_arm_events / arm_events if arm_events else 0.0
    return {
        **run_spec,
        "run_id": result.run_id,
        "completed": True,
        "final_total_honest_regret": result.total_population_regret,
        "final_mean_honest_regret": result.mean_per_agent_regret,
        "best_arm_identification_rate": result.best_arm_identification_rate,
        "worst_decile_honest_regret": float(np.quantile(per_agent, 0.9)),
        "fallback_frequency": fallback_frequency,
        "fallback_arm_events": fallback_arm_events,
        "arm_aggregation_events": arm_events,
        "messages_sent": result.communication["messages_sent"],
        "scalar_values_sent": result.communication["scalar_values_sent"],
    }


def _curve_records(
    run_spec: dict[str, object],
    result: MultiAgentRunResult,
) -> list[dict[str, object]]:
    return [
        {
            **run_spec,
            "round": round_index,
            "mean_honest_cumulative_regret": value,
        }
        for round_index, value in enumerate(result.mean_regret_curve, start=1)
    ]


def _summary_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        key = (record["topology"], record["condition"], record["aggregation"])
        grouped[key].append(record)

    summaries: list[dict[str, object]] = []
    for (topology, condition, aggregation), group in sorted(grouped.items()):
        final_regrets = [float(item["final_mean_honest_regret"]) for item in group]
        best_rates = [float(item["best_arm_identification_rate"]) for item in group]
        worst_deciles = [float(item["worst_decile_honest_regret"]) for item in group]
        fallbacks = [float(item["fallback_frequency"]) for item in group]
        ci_low, ci_high = _normal_ci(final_regrets)
        summaries.append(
            {
                "topology": topology,
                "condition": condition,
                "aggregation": aggregation,
                "completed_runs": len(group),
                "failed_runs": 0,
                "mean_final_honest_regret": mean(final_regrets),
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "mean_best_arm_identification_rate": mean(best_rates),
                "mean_worst_decile_honest_regret": mean(worst_deciles),
                "mean_fallback_frequency": mean(fallbacks),
            }
        )
    return summaries


def _normal_ci(values: list[float]) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    array = np.asarray(values, dtype=float)
    half_width = 1.96 * float(np.std(array, ddof=1)) / float(np.sqrt(len(array)))
    center = float(np.mean(array))
    return center - half_width, center + half_width


def _write_csv(path: Path, records: list[dict[str, object]]) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def _write_curve_svgs(
    output_dir: Path,
    curve_records: list[dict[str, object]],
) -> None:
    grouped_curves = _mean_curves(curve_records)
    for (topology, condition), curves in sorted(grouped_curves.items()):
        path = output_dir / f"mean_regret_curves_{topology}_{condition}.svg"
        path.write_text(_svg_line_chart(curves), encoding="utf-8")


def _mean_curves(
    curve_records: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, list[tuple[int, float]]]]:
    grouped: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
    for record in curve_records:
        key = (
            str(record["topology"]),
            str(record["condition"]),
            str(record["aggregation"]),
            int(record["round"]),
        )
        grouped[key].append(float(record["mean_honest_cumulative_regret"]))

    curves: dict[tuple[str, str], dict[str, list[tuple[int, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (topology, condition, aggregation, round_index), values in grouped.items():
        curves[(topology, condition)][aggregation].append(
            (round_index, float(np.mean(values)))
        )
    for aggregation_curves in curves.values():
        for points in aggregation_curves.values():
            points.sort()
    return curves


def _svg_line_chart(curves: dict[str, list[tuple[int, float]]]) -> str:
    width = 760
    height = 420
    margin = 54
    colors = {
        "independent": "#1f77b4",
        "mean": "#d62728",
        "median": "#2ca02c",
        "trimmed_mean": "#9467bd",
    }
    max_round = max(point[0] for points in curves.values() for point in points)
    max_value = max(point[1] for points in curves.values() for point in points)
    max_value = max(max_value, 1.0)

    def x_scale(round_index: int) -> float:
        return margin + (round_index - 1) * (width - 2 * margin) / (max_round - 1)

    def y_scale(value: float) -> float:
        return height - margin - value * (height - 2 * margin) / max_value

    paths: list[str] = []
    legend: list[str] = []
    for legend_index, (label, points) in enumerate(sorted(curves.items())):
        commands = [
            ("M" if index == 0 else "L")
            + f"{x_scale(round_index):.2f},{y_scale(value):.2f}"
            for index, (round_index, value) in enumerate(points)
        ]
        color = colors.get(label, "#333333")
        paths.append(
            f'<path d="{" ".join(commands)}" fill="none" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        legend_y = 24 + legend_index * 20
        legend.append(
            f'<line x1="560" y1="{legend_y}" x2="584" y2="{legend_y}" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="592" y="{legend_y + 4}" font-size="12">{label}</text>'
        )
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<line x1="{margin}" y1="{height - margin}" '
            f'x2="{width - margin}" y2="{height - margin}" '
            'stroke="#222"/>',
            f'<line x1="{margin}" y1="{margin}" '
            f'x2="{margin}" y2="{height - margin}" stroke="#222"/>',
            f'<text x="{width / 2}" y="{height - 12}" '
            'font-size="13" text-anchor="middle">round</text>',
            '<text x="16" y="220" font-size="13" '
            'transform="rotate(-90 16 220)" text-anchor="middle">'
            "mean honest cumulative regret</text>",
            *paths,
            *legend,
            "</svg>",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
