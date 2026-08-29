"""Run the bounded Milestone 7 exploratory pilot and figure prototypes."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
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
    parser.add_argument("--config", default="configs/pilot_m7.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--figure-dir", default=None)
    parser.add_argument(
        "--manifest",
        default="experiments/manifests/confirmatory_m8_manifest.json",
        help="Optional Milestone 8 manifest used for a linear runtime projection.",
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Run only the first N configured seeds while preserving the full "
        "topology/condition/algorithm grid for those seeds.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=32,
        help="Print progress every N runs.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec_path = Path(args.config)
    spec = _load_yaml(spec_path)
    manifest = _load_optional_json(Path(args.manifest))
    run_seeds = _selected_run_seeds(spec, args.max_seeds)
    planned = list(_planned_runs(spec, run_seeds))
    _validate_planned_configs(spec, planned)

    output_dir = Path(args.output_dir or spec["experiment"]["output_dir"])
    figure_dir = Path(args.figure_dir or spec["experiment"]["figure_dir"])
    print(f"planned_runs={len(planned)}")
    print(f"run_seeds={run_seeds}")
    print(f"output_dir={output_dir}")
    print(f"figure_dir={figure_dir}")
    if args.dry_run:
        return 0

    started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    run_records: list[dict[str, object]] = []
    curve_records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for run_index, run_spec in enumerate(planned, start=1):
        config_data = _study_config_from_pilot(spec, run_spec)
        run_started = perf_counter()
        try:
            result = run_multi_agent(StudyConfig.from_mapping(config_data), write=False)
            if not isinstance(result, MultiAgentRunResult):
                raise RuntimeError("expected a multi-agent result")
            run_seconds = perf_counter() - run_started
            run_records.append(_run_record(run_spec, result, run_seconds))
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

    total_runtime = perf_counter() - started
    summary = _summary_records(run_records)
    paired_differences = _paired_difference_records(run_records)
    runtime_estimate = _runtime_estimate(
        records=run_records,
        total_runtime_seconds=total_runtime,
        spec=spec,
        manifest=manifest,
    )
    _write_csv(output_dir / "final_regret_summary.csv", summary)
    _write_csv(output_dir / "run_metrics.csv", run_records)
    _write_csv(output_dir / "mean_regret_curves.csv", curve_records)
    _write_csv(output_dir / "paired_differences.csv", paired_differences)
    (output_dir / "runtime_estimate.json").write_text(
        json.dumps(runtime_estimate, indent=2, sort_keys=True),
        encoding="utf-8",
    )
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
                "runtime_seconds": total_runtime,
                "exploratory_only": True,
                "figures": {
                    "directory": str(figure_dir),
                    "prototype_label": "exploratory pilot - not confirmatory evidence",
                },
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write_curve_svgs(figure_dir, curve_records)
    _write_final_regret_overview_svg(figure_dir, summary)
    print(f"completed_runs={len(run_records)} failed_runs={len(failures)}")
    print(f"processed_output_dir={output_dir}")
    print(f"figure_output_dir={figure_dir}")
    return 1 if failures else 0


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("pilot config must be a mapping")
    return loaded


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a JSON object")
    return loaded


def _selected_run_seeds(spec: dict[str, Any], max_seeds: int | None) -> list[int]:
    run_seeds = [int(seed) for seed in spec["seeds"]["run_seeds"]]
    if max_seeds is None:
        return run_seeds
    if max_seeds <= 0:
        raise ValueError("--max-seeds must be positive")
    return run_seeds[:max_seeds]


def _planned_runs(
    spec: dict[str, Any],
    run_seeds: list[int],
) -> Iterable[dict[str, object]]:
    for seed in run_seeds:
        for topology_name in spec["topologies"]:
            for condition_name in spec["conditions"]:
                if spec.get("include_independent_baseline", True):
                    yield {
                        "seed": int(seed),
                        "topology": topology_name,
                        "condition": condition_name,
                        "topology_mode": "static",
                        "aggregation": "independent",
                    }
                for topology_mode in spec["topology_modes"]:
                    for aggregation_name in spec["aggregations"]:
                        yield {
                            "seed": int(seed),
                            "topology": topology_name,
                            "condition": condition_name,
                            "topology_mode": topology_mode,
                            "aggregation": aggregation_name,
                        }


def _validate_planned_configs(
    spec: dict[str, Any],
    planned: list[dict[str, object]],
) -> None:
    errors: list[str] = []
    for run_spec in planned:
        try:
            StudyConfig.from_mapping(_study_config_from_pilot(spec, run_spec))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{run_spec}: {exc}")
    if errors:
        message = "\n".join(errors[:10])
        if len(errors) > 10:
            message += f"\n... {len(errors) - 10} more invalid runs"
        raise ValueError(f"invalid Milestone 7 pilot grid:\n{message}")


def _study_config_from_pilot(
    spec: dict[str, Any],
    run_spec: dict[str, object],
) -> dict[str, object]:
    aggregation = str(run_spec["aggregation"])
    topology_mode = str(run_spec["topology_mode"])
    topology = spec["topologies"][run_spec["topology"]]
    condition = spec["conditions"][run_spec["condition"]]
    is_independent = aggregation == "independent"
    dynamic_enabled = topology_mode == "dynamic"
    algorithm_name = (
        "independent_ucb1" if is_independent else "one_hop_weighted_pooling_ucb1"
    )
    aggregation_method = "mean" if is_independent else aggregation
    trim_count = (
        spec["trimmed_mean"]["trim_count"]
        if aggregation_method == "trimmed_mean"
        else None
    )
    topology_change = (
        {
            "enabled": True,
            "change_round": spec["dynamic_topology"]["change_round"],
            "rewire_fraction": spec["dynamic_topology"]["rewire_fraction"],
            "preserve_connectivity": spec["dynamic_topology"][
                "preserve_connectivity"
            ],
        }
        if dynamic_enabled
        else {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": spec["dynamic_topology"][
                "preserve_connectivity"
            ],
        }
    )

    return {
        "name": (
            f"{spec['name']}-{run_spec['condition']}-{run_spec['topology']}-"
            f"{topology_mode}-{aggregation}"
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
        "topology_change": topology_change,
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
    runtime_seconds: float,
) -> dict[str, object]:
    per_agent = np.asarray(result.per_agent_final_regret, dtype=float)
    arm_events = int(result.aggregation_summary["arm_aggregation_events"])
    fallback_arm_events = int(result.aggregation_summary["fallback_arm_events"])
    fallback_frequency = fallback_arm_events / arm_events if arm_events else 0.0
    topology_event = result.topology_change["event"]
    connected_after = (
        topology_event["connected_after"] if isinstance(topology_event, dict) else None
    )
    return {
        **run_spec,
        "run_id": result.run_id,
        "algorithm": result.algorithm,
        "completed": True,
        "runtime_seconds": runtime_seconds,
        "horizon": result.horizon,
        "num_agents": result.num_agents,
        "attack_strategy": result.attack["strategy"],
        "byzantine_placement": result.attack["placement"],
        "byzantine_count": result.attack["byzantine_count"],
        "topology_changed": topology_event is not None,
        "post_change_connected": connected_after,
        "recovered_after_change": result.recovery["recovered"],
        "recovery_round": result.recovery["recovery_round"],
        "final_total_honest_regret": result.total_population_regret,
        "final_mean_honest_regret": result.mean_per_agent_regret,
        "best_arm_identification_rate": result.best_arm_identification_rate,
        "median_honest_regret": float(np.median(per_agent)),
        "worst_decile_honest_regret": float(np.quantile(per_agent, 0.9)),
        "max_honest_regret": float(np.max(per_agent)),
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
        key = (
            record["topology"],
            record["condition"],
            record["topology_mode"],
            record["aggregation"],
        )
        grouped[key].append(record)

    summaries: list[dict[str, object]] = []
    for (topology, condition, topology_mode, aggregation), group in sorted(
        grouped.items()
    ):
        final_regrets = [float(item["final_mean_honest_regret"]) for item in group]
        best_rates = [float(item["best_arm_identification_rate"]) for item in group]
        worst_deciles = [float(item["worst_decile_honest_regret"]) for item in group]
        fallbacks = [float(item["fallback_frequency"]) for item in group]
        runtimes = [float(item["runtime_seconds"]) for item in group]
        ci_low, ci_high = _normal_ci(final_regrets)
        summaries.append(
            {
                "topology": topology,
                "condition": condition,
                "topology_mode": topology_mode,
                "aggregation": aggregation,
                "completed_runs": len(group),
                "failed_runs": 0,
                "mean_final_honest_regret": mean(final_regrets),
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "mean_best_arm_identification_rate": mean(best_rates),
                "mean_worst_decile_honest_regret": mean(worst_deciles),
                "mean_fallback_frequency": mean(fallbacks),
                "mean_runtime_seconds": mean(runtimes),
                "exploratory_only": True,
            }
        )
    return summaries


def _paired_difference_records(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_run = {
        (
            record["seed"],
            record["topology"],
            record["condition"],
            record["topology_mode"],
            record["aggregation"],
        ): record
        for record in records
    }
    differences: list[dict[str, object]] = []
    for record in records:
        independent = by_run.get(
            (
                record["seed"],
                record["topology"],
                record["condition"],
                "static",
                "independent",
            )
        )
        mean_baseline = by_run.get(
            (
                record["seed"],
                record["topology"],
                record["condition"],
                record["topology_mode"],
                "mean",
            )
        )
        regret = float(record["final_mean_honest_regret"])
        if independent is not None:
            differences.append(
                {
                    **_difference_key(record),
                    "baseline": "independent_static",
                    "paired_difference_final_mean_regret": regret
                    - float(independent["final_mean_honest_regret"]),
                }
            )
        if mean_baseline is not None and record["aggregation"] != "independent":
            differences.append(
                {
                    **_difference_key(record),
                    "baseline": "mean_same_topology_mode",
                    "paired_difference_final_mean_regret": regret
                    - float(mean_baseline["final_mean_honest_regret"]),
                }
            )
    return _summarize_differences(differences)


def _difference_key(record: dict[str, object]) -> dict[str, object]:
    return {
        "seed": record["seed"],
        "topology": record["topology"],
        "condition": record["condition"],
        "topology_mode": record["topology_mode"],
        "aggregation": record["aggregation"],
    }


def _summarize_differences(
    differences: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for record in differences:
        key = (
            record["topology"],
            record["condition"],
            record["topology_mode"],
            record["aggregation"],
            record["baseline"],
        )
        grouped[key].append(float(record["paired_difference_final_mean_regret"]))

    summaries: list[dict[str, object]] = []
    for (topology, condition, topology_mode, aggregation, baseline), values in sorted(
        grouped.items()
    ):
        ci_low, ci_high = _normal_ci(values)
        summaries.append(
            {
                "topology": topology,
                "condition": condition,
                "topology_mode": topology_mode,
                "aggregation": aggregation,
                "baseline": baseline,
                "paired_seeds": len(values),
                "mean_paired_difference_final_mean_regret": mean(values),
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "exploratory_only": True,
            }
        )
    return summaries


def _runtime_estimate(
    *,
    records: list[dict[str, object]],
    total_runtime_seconds: float,
    spec: dict[str, Any],
    manifest: dict[str, Any] | None,
) -> dict[str, object]:
    if not records:
        return {
            "status": "no_completed_runs",
            "exploratory_only": True,
        }
    simulated_agent_rounds = sum(
        int(record["horizon"]) * int(record["num_agents"]) for record in records
    )
    run_seconds = [float(record["runtime_seconds"]) for record in records]
    seconds_per_agent_round = total_runtime_seconds / simulated_agent_rounds
    estimate: dict[str, object] = {
        "status": "observed",
        "exploratory_only": True,
        "completed_runs": len(records),
        "total_runtime_seconds": total_runtime_seconds,
        "mean_runtime_seconds_per_run": mean(run_seconds),
        "median_runtime_seconds_per_run": float(np.median(run_seconds)),
        "max_runtime_seconds_per_run": max(run_seconds),
        "simulated_agent_rounds": simulated_agent_rounds,
        "observed_seconds_per_agent_round": seconds_per_agent_round,
        "linear_scaling_note": (
            "Use this only for order-of-magnitude planning. Confirmatory "
            "runtime will depend on topology density, horizon, raw-output "
            "choices, and parallelism."
        ),
        "pilot_horizon": spec["experiment"]["horizon"],
        "pilot_agents": spec["population"]["agents"],
        "pilot_seed_count": len({record["seed"] for record in records}),
    }
    if manifest is not None:
        estimate["confirmatory_projection"] = _confirmatory_projection(
            seconds_per_agent_round=seconds_per_agent_round,
            manifest=manifest,
        )
    return estimate


def _confirmatory_projection(
    *,
    seconds_per_agent_round: float,
    manifest: dict[str, Any],
) -> dict[str, object]:
    hyperparameters = manifest["fixed_hyperparameters"]
    run_counts = manifest["run_count_estimate"]
    agents = int(hyperparameters["agents"])
    horizon = int(hyperparameters["horizon"])
    primary_runs = int(run_counts["primary_planned_runs"])
    total_runs = int(run_counts["total_planned_runs"])
    primary_seconds = seconds_per_agent_round * primary_runs * agents * horizon
    total_seconds = seconds_per_agent_round * total_runs * agents * horizon
    return {
        "manifest_name": manifest["manifest_name"],
        "estimator": "linear_seconds_per_agent_round_from_milestone7_pilot",
        "agents": agents,
        "horizon": horizon,
        "primary_planned_runs": primary_runs,
        "total_planned_runs": total_runs,
        "estimated_primary_runtime_seconds_single_process": primary_seconds,
        "estimated_total_runtime_seconds_single_process": total_seconds,
        "estimated_primary_runtime_hours_single_process": primary_seconds / 3600.0,
        "estimated_total_runtime_hours_single_process": total_seconds / 3600.0,
        "caveat": (
            "This is a planning estimate only; Milestone 8 should add compact "
            "outputs and parallel execution before running the full manifest."
        ),
    }


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
    figure_dir: Path,
    curve_records: list[dict[str, object]],
) -> None:
    grouped_curves = _mean_curves(curve_records)
    for (topology, condition, topology_mode), curves in sorted(grouped_curves.items()):
        path = (
            figure_dir
            / f"exploratory_regret_curves_{topology}_{condition}_{topology_mode}.svg"
        )
        title = f"{topology} | {condition} | {topology_mode}"
        path.write_text(_svg_line_chart(curves, title=title), encoding="utf-8")


def _mean_curves(
    curve_records: list[dict[str, object]],
) -> dict[tuple[str, str, str], dict[str, list[tuple[int, float]]]]:
    grouped: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)
    for record in curve_records:
        key = (
            str(record["topology"]),
            str(record["condition"]),
            str(record["topology_mode"]),
            str(record["aggregation"]),
            int(record["round"]),
        )
        grouped[key].append(float(record["mean_honest_cumulative_regret"]))

    curves: dict[tuple[str, str, str], dict[str, list[tuple[int, float]]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for (topology, condition, topology_mode, aggregation, round_index), values in (
        grouped.items()
    ):
        curves[(topology, condition, topology_mode)][aggregation].append(
            (round_index, float(np.mean(values)))
        )
    for aggregation_curves in curves.values():
        for points in aggregation_curves.values():
            points.sort()
    return curves


def _svg_line_chart(
    curves: dict[str, list[tuple[int, float]]],
    *,
    title: str,
) -> str:
    width = 820
    height = 460
    margin = 62
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
        if max_round == 1:
            return margin
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
        safe_label = html.escape(label)
        paths.append(
            f'<path d="{" ".join(commands)}" fill="none" '
            f'stroke="{color}" stroke-width="2.2"/>'
        )
        legend_y = 78 + legend_index * 22
        legend.append(
            f'<line x1="594" y1="{legend_y}" x2="620" y2="{legend_y}" '
            f'stroke="{color}" stroke-width="2.2"/>'
            f'<text x="630" y="{legend_y + 4}" font-size="12">{safe_label}</text>'
        )
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<text x="{margin}" y="28" font-size="16" font-weight="700">'
            f'{html.escape(title)}</text>',
            f'<text x="{margin}" y="48" font-size="12" fill="#555">'
            "EXPLORATORY PILOT - not confirmatory evidence</text>",
            f'<line x1="{margin}" y1="{height - margin}" '
            f'x2="{width - margin}" y2="{height - margin}" '
            'stroke="#222"/>',
            f'<line x1="{margin}" y1="{margin}" '
            f'x2="{margin}" y2="{height - margin}" stroke="#222"/>',
            f'<text x="{width / 2}" y="{height - 16}" '
            'font-size="13" text-anchor="middle">round</text>',
            '<text x="18" y="240" font-size="13" '
            'transform="rotate(-90 18 240)" text-anchor="middle">'
            "mean honest cumulative regret</text>",
            f'<text x="{margin}" y="{height - margin + 18}" font-size="11">1</text>',
            f'<text x="{width - margin - 20}" y="{height - margin + 18}" '
            f'font-size="11">{max_round}</text>',
            f'<text x="24" y="{y_scale(max_value) + 4}" font-size="11">'
            f'{max_value:.2f}</text>',
            *paths,
            *legend,
            "</svg>",
        ]
    )


def _write_final_regret_overview_svg(
    figure_dir: Path,
    summary_records: list[dict[str, object]],
) -> None:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for record in summary_records:
        key = (
            str(record["condition"]),
            str(record["topology_mode"]),
            str(record["aggregation"]),
        )
        grouped[key].append(float(record["mean_final_honest_regret"]))
    bars = [
        {
            "condition": condition,
            "topology_mode": topology_mode,
            "aggregation": aggregation,
            "value": mean(values),
        }
        for (condition, topology_mode, aggregation), values in sorted(grouped.items())
    ]
    path = figure_dir / "exploratory_final_regret_overview.svg"
    path.write_text(_svg_bar_overview(bars), encoding="utf-8")


def _svg_bar_overview(records: list[dict[str, object]]) -> str:
    width = 1160
    height = 520
    margin_left = 88
    margin_bottom = 118
    top = 70
    colors = {
        "independent": "#1f77b4",
        "mean": "#d62728",
        "median": "#2ca02c",
        "trimmed_mean": "#9467bd",
    }
    max_value = max((float(record["value"]) for record in records), default=1.0)
    max_value = max(max_value, 1.0)
    plot_width = width - margin_left - 34
    plot_height = height - top - margin_bottom
    bar_gap = 6
    available_width = plot_width - bar_gap * max(len(records) - 1, 0)
    bar_width = max(10, available_width / len(records))

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="88" y="30" font-size="16" font-weight="700">'
        "Final mean honest regret overview</text>",
        '<text x="88" y="50" font-size="12" fill="#555">'
        "EXPLORATORY PILOT - averages across pilot topologies, not "
        "confirmatory evidence</text>",
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" '
        f'x2="{width - 34}" y2="{height - margin_bottom}" stroke="#222"/>',
        f'<line x1="{margin_left}" y1="{top}" x2="{margin_left}" '
        f'y2="{height - margin_bottom}" stroke="#222"/>',
        '<text x="22" y="260" font-size="13" '
        'transform="rotate(-90 22 260)" text-anchor="middle">'
        "final mean honest regret</text>",
    ]
    for index, record in enumerate(records):
        value = float(record["value"])
        x = margin_left + index * (bar_width + bar_gap)
        h = value * plot_height / max_value
        y = height - margin_bottom - h
        color = colors.get(str(record["aggregation"]), "#555555")
        label = (
            f"{record['condition']}|{record['topology_mode']}|"
            f"{record['aggregation']}"
        )
        elements.extend(
            [
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" '
                f'height="{h:.2f}" fill="{color}"/>',
                f'<text x="{x + bar_width / 2:.2f}" y="{height - margin_bottom + 12}" '
                'font-size="9" text-anchor="end" '
                f'transform="rotate(-50 {x + bar_width / 2:.2f} '
                f'{height - margin_bottom + 12})">{html.escape(label)}</text>',
            ]
        )
    elements.extend(
        [
            f'<text x="38" y="{top + 4}" font-size="11">{max_value:.2f}</text>',
            "</svg>",
        ]
    )
    return "\n".join(elements)


if __name__ == "__main__":
    raise SystemExit(main())
