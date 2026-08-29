"""Aggregate validated compact confirmatory records into tidy CSV tables."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "experiments" / "scripts"
for path in (SRC_ROOT, SCRIPT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_confirmatory_manifest import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_DIR,
    PlannedRun,
    expand_manifest,
)
from validate_confirmatory_results import validate_confirmatory_results  # noqa: E402

from swarmgov.analysis.compact import COMPACT_RECORD_SCHEMA_VERSION  # noqa: E402

AGGREGATE_SCHEMA_VERSION = "confirmatory_aggregate_v1"
DEFAULT_PROCESSED_DIR = Path("results/processed/confirmatory-m8")

RUN_METRICS_FILE = "run_metrics.csv"
PER_AGENT_FILE = "per_agent_regret.csv"
CURVES_FILE = "regret_curves.csv"
PAIRED_FILE = "paired_differences.csv"
SUMMARY_FILE = "aggregation_summary.json"
VALIDATION_REPORT_FILE = "validation_report.json"

CONDITION_KEYS = (
    "group_kind",
    "group_name",
    "seed",
    "topology",
    "topology_mode",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "target_arm",
    "inflated_mean",
)

RUN_METRIC_COLUMNS = (
    "run_key",
    "group_kind",
    "group_name",
    "seed",
    "topology",
    "topology_mode",
    "algorithm_label",
    "aggregation",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "target_arm",
    "inflated_mean",
    "runtime_seconds",
    "schema_version",
    "algorithm_name",
    "horizon",
    "num_agents",
    "honest_count",
    "byzantine_count",
    "graph_family",
    "graph_num_nodes",
    "graph_edge_count",
    "graph_connected",
    "graph_seed",
    "topology_change_enabled",
    "topology_change_round",
    "topology_recovered",
    "topology_recovery_round",
    "total_population_regret",
    "mean_per_agent_regret",
    "median_honest_regret",
    "worst_decile_honest_regret",
    "max_honest_regret",
    "best_arm",
    "best_arm_identification_rate",
    "messages_sent",
    "scalar_values_sent",
    "messages_per_agent_mean",
    "scalar_values_per_agent_mean",
    "aggregation_events",
    "arm_aggregation_events",
    "fallback_events",
    "fallback_arm_events",
    "invalid_messages_rejected",
    "attack_diagnostics_count",
    "aggregation_diagnostics_count",
)

PER_AGENT_COLUMNS = (
    "run_key",
    "group_kind",
    "group_name",
    "seed",
    "topology",
    "topology_mode",
    "algorithm_label",
    "aggregation",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "agent_id",
    "agent_index",
    "final_regret",
)

CURVE_COLUMNS = (
    "run_key",
    "group_kind",
    "group_name",
    "seed",
    "topology",
    "topology_mode",
    "algorithm_label",
    "aggregation",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "round",
    "mean_regret",
    "total_regret",
)

PAIRED_COLUMNS = (
    "comparison",
    "baseline_algorithm_label",
    "target_algorithm_label",
    "baseline_run_key",
    "target_run_key",
    "group_kind",
    "group_name",
    "seed",
    "topology",
    "topology_mode",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "target_arm",
    "inflated_mean",
    "baseline_mean_per_agent_regret",
    "target_mean_per_agent_regret",
    "mean_per_agent_regret_difference",
    "baseline_total_population_regret",
    "target_total_population_regret",
    "total_population_regret_difference",
    "baseline_best_arm_identification_rate",
    "target_best_arm_identification_rate",
    "best_arm_identification_rate_difference",
    "baseline_messages_sent",
    "target_messages_sent",
    "messages_sent_difference",
    "baseline_scalar_values_sent",
    "target_scalar_values_sent",
    "scalar_values_sent_difference",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--input-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_PROCESSED_DIR))
    parser.add_argument(
        "--group-kind",
        choices=("primary", "sensitivity", "all"),
        default="primary",
        help="Which manifest groups to aggregate.",
    )
    parser.add_argument(
        "--run-group",
        action="append",
        default=None,
        help="Restrict aggregation to one or more manifest group names.",
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Aggregate only the first N confirmatory seeds inside each group.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Aggregate only the first N expanded runs.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing processed aggregate artifacts.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    planned_outputs = _planned_output_paths(output_dir)
    _ensure_can_write(planned_outputs, overwrite=args.overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)

    validation_report_path = output_dir / VALIDATION_REPORT_FILE
    validation_report = validate_confirmatory_results(
        manifest_path=manifest_path,
        output_dir=input_dir,
        group_kind=args.group_kind,
        run_groups=args.run_group,
        max_seeds=args.max_seeds,
        max_runs=args.max_runs,
        report_path=validation_report_path,
    )
    _write_json(validation_report_path, validation_report)
    if validation_report["status"] != "passed":
        print("aggregation_status=blocked_by_validation")
        print(f"validation_status={validation_report['status']}")
        print(f"validation_report={validation_report_path}")
        return 1

    manifest = _load_manifest(manifest_path)
    planned_runs = list(
        expand_manifest(
            manifest,
            group_kind=args.group_kind,
            run_groups=args.run_group,
            max_seeds=args.max_seeds,
        )
    )
    if args.max_runs is not None:
        if args.max_runs <= 0:
            raise ValueError("--max-runs must be positive")
        planned_runs = planned_runs[: args.max_runs]

    records = [_load_completed_record(input_dir, planned) for planned in planned_runs]
    metric_rows = [_run_metric_row(record) for record in records]
    per_agent_rows = list(_per_agent_rows(records))
    curve_rows = list(_curve_rows(records))
    paired_rows = _paired_difference_rows(metric_rows)

    _write_csv(output_dir / RUN_METRICS_FILE, RUN_METRIC_COLUMNS, metric_rows)
    _write_csv(output_dir / PER_AGENT_FILE, PER_AGENT_COLUMNS, per_agent_rows)
    _write_csv(output_dir / CURVES_FILE, CURVE_COLUMNS, curve_rows)
    _write_csv(output_dir / PAIRED_FILE, PAIRED_COLUMNS, paired_rows)

    summary = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_name": manifest.get("manifest_name"),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "group_kind": args.group_kind,
        "run_groups": args.run_group,
        "max_seeds": args.max_seeds,
        "max_runs": args.max_runs,
        "compact_schema_version": COMPACT_RECORD_SCHEMA_VERSION,
        "validation_report": str(validation_report_path),
        "validation_status": validation_report["status"],
        "row_counts": {
            "run_metrics": len(metric_rows),
            "per_agent_regret": len(per_agent_rows),
            "regret_curves": len(curve_rows),
            "paired_differences": len(paired_rows),
        },
        "outputs": {name: str(path) for name, path in planned_outputs.items()},
        "notes": (
            "These processed tables are aggregation inputs only. Scientific "
            "claims require the later confidence-interval/statistical step."
        ),
    }
    _write_json(output_dir / SUMMARY_FILE, summary)

    print("aggregation_status=completed")
    print(f"validation_status={validation_report['status']}")
    print(f"run_metrics_rows={len(metric_rows)}")
    print(f"per_agent_regret_rows={len(per_agent_rows)}")
    print(f"regret_curve_rows={len(curve_rows)}")
    print(f"paired_difference_rows={len(paired_rows)}")
    print(f"summary={output_dir / SUMMARY_FILE}")
    return 0


def _planned_output_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "run_metrics": output_dir / RUN_METRICS_FILE,
        "per_agent_regret": output_dir / PER_AGENT_FILE,
        "regret_curves": output_dir / CURVES_FILE,
        "paired_differences": output_dir / PAIRED_FILE,
        "summary": output_dir / SUMMARY_FILE,
    }


def _ensure_can_write(paths: dict[str, Path], *, overwrite: bool) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "processed aggregate artifacts already exist; pass --overwrite "
            f"to replace them: {names}"
        )


def _load_completed_record(input_dir: Path, planned: PlannedRun) -> dict[str, Any]:
    path = input_dir / planned.filename
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"completed record is not a JSON object: {path}")
    return record


def _run_metric_row(record: dict[str, Any]) -> dict[str, object]:
    planned = _required_dict(record, "planned_run")
    result = _required_dict(record, "result")
    metrics = _required_dict(result, "metrics")
    identifiers = _required_dict(result, "identifiers")
    graph = _required_dict(result, "graph")
    node_sets = _required_dict(result, "node_sets")
    attack = _required_dict(result, "attack")
    recovery = _dict_or_empty(metrics.get("recovery"))
    communication = _dict_or_empty(metrics.get("communication"))
    aggregation_summary = _dict_or_empty(metrics.get("aggregation_summary"))
    diagnostics_summary = _dict_or_empty(result.get("diagnostics_summary"))

    messages_per_agent = _numeric_list(communication.get("messages_per_agent"))
    scalar_values_per_agent = _numeric_list(
        communication.get("scalar_values_per_agent")
    )
    return {
        **_planned_fields(planned),
        "runtime_seconds": record.get("runtime_seconds"),
        "schema_version": result.get("schema_version"),
        "algorithm_name": identifiers.get("algorithm"),
        "horizon": identifiers.get("horizon"),
        "num_agents": identifiers.get("num_agents"),
        "honest_count": len(_list_or_empty(node_sets.get("honest_nodes"))),
        "byzantine_count": attack.get(
            "byzantine_count",
            len(_list_or_empty(node_sets.get("byzantine_nodes"))),
        ),
        "graph_family": graph.get("family"),
        "graph_num_nodes": graph.get("num_nodes"),
        "graph_edge_count": len(_list_or_empty(graph.get("edges"))),
        "graph_connected": graph.get("connected"),
        "graph_seed": graph.get("graph_seed"),
        "topology_change_enabled": recovery.get("enabled"),
        "topology_change_round": recovery.get("change_round"),
        "topology_recovered": recovery.get("recovered"),
        "topology_recovery_round": recovery.get("recovery_round"),
        "total_population_regret": metrics.get("total_population_regret"),
        "mean_per_agent_regret": metrics.get("mean_per_agent_regret"),
        "median_honest_regret": metrics.get("median_honest_regret"),
        "worst_decile_honest_regret": metrics.get("worst_decile_honest_regret"),
        "max_honest_regret": metrics.get("max_honest_regret"),
        "best_arm": metrics.get("best_arm"),
        "best_arm_identification_rate": metrics.get(
            "best_arm_identification_rate"
        ),
        "messages_sent": communication.get("messages_sent"),
        "scalar_values_sent": communication.get("scalar_values_sent"),
        "messages_per_agent_mean": _mean(messages_per_agent),
        "scalar_values_per_agent_mean": _mean(scalar_values_per_agent),
        "aggregation_events": aggregation_summary.get("aggregation_events"),
        "arm_aggregation_events": aggregation_summary.get("arm_aggregation_events"),
        "fallback_events": aggregation_summary.get("fallback_events"),
        "fallback_arm_events": aggregation_summary.get("fallback_arm_events"),
        "invalid_messages_rejected": aggregation_summary.get(
            "invalid_messages_rejected"
        ),
        "attack_diagnostics_count": diagnostics_summary.get(
            "attack_diagnostics_count"
        ),
        "aggregation_diagnostics_count": diagnostics_summary.get(
            "aggregation_diagnostics_count"
        ),
    }


def _per_agent_rows(records: Iterable[dict[str, Any]]) -> Iterable[dict[str, object]]:
    for record in records:
        planned = _required_dict(record, "planned_run")
        result = _required_dict(record, "result")
        metrics = _required_dict(result, "metrics")
        node_sets = _required_dict(result, "node_sets")
        regrets = _list_or_empty(metrics.get("per_agent_final_regret"))
        honest_nodes = _list_or_empty(node_sets.get("honest_nodes"))
        for index, regret in enumerate(regrets):
            agent_id = honest_nodes[index] if index < len(honest_nodes) else index
            yield {
                **_condition_fields(planned),
                "run_key": planned["run_key"],
                "algorithm_label": planned["algorithm_label"],
                "aggregation": planned["aggregation"],
                "agent_id": agent_id,
                "agent_index": index,
                "final_regret": regret,
            }


def _curve_rows(records: Iterable[dict[str, Any]]) -> Iterable[dict[str, object]]:
    for record in records:
        planned = _required_dict(record, "planned_run")
        result = _required_dict(record, "result")
        curves = _required_dict(result, "curves")
        rounds = _list_or_empty(curves.get("rounds"))
        mean_regret = _list_or_empty(curves.get("mean_regret"))
        total_regret = _list_or_empty(curves.get("total_regret"))
        for round_index, mean_value, total_value in zip(
            rounds,
            mean_regret,
            total_regret,
            strict=True,
        ):
            yield {
                **_condition_fields(planned),
                "run_key": planned["run_key"],
                "algorithm_label": planned["algorithm_label"],
                "aggregation": planned["aggregation"],
                "round": round_index,
                "mean_regret": mean_value,
                "total_regret": total_value,
            }


def _paired_difference_rows(
    metric_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_condition: dict[tuple[object, ...], dict[str, dict[str, object]]] = {}
    for row in metric_rows:
        key = tuple(row[name] for name in CONDITION_KEYS)
        by_condition.setdefault(key, {})[str(row["algorithm_label"])] = row

    paired_rows: list[dict[str, object]] = []
    for runs in by_condition.values():
        independent = runs.get("independent")
        mean = runs.get("mean")
        if independent is not None:
            for algorithm, target in sorted(runs.items()):
                if algorithm == "independent":
                    continue
                paired_rows.append(
                    _paired_row(
                        comparison="vs_independent",
                        baseline=independent,
                        target=target,
                    )
                )
        if mean is not None:
            for algorithm in ("median", "trimmed_mean"):
                target = runs.get(algorithm)
                if target is not None:
                    paired_rows.append(
                        _paired_row(
                            comparison="vs_mean",
                            baseline=mean,
                            target=target,
                        )
                    )
    return paired_rows


def _paired_row(
    *,
    comparison: str,
    baseline: dict[str, object],
    target: dict[str, object],
) -> dict[str, object]:
    row = {
        "comparison": comparison,
        "baseline_algorithm_label": baseline["algorithm_label"],
        "target_algorithm_label": target["algorithm_label"],
        "baseline_run_key": baseline["run_key"],
        "target_run_key": target["run_key"],
    }
    for key in CONDITION_KEYS:
        row[key] = target[key]
    for metric in (
        "mean_per_agent_regret",
        "total_population_regret",
        "best_arm_identification_rate",
        "messages_sent",
        "scalar_values_sent",
    ):
        baseline_value = baseline[metric]
        target_value = target[metric]
        row[f"baseline_{metric}"] = baseline_value
        row[f"target_{metric}"] = target_value
        row[f"{metric}_difference"] = _numeric_difference(
            target_value,
            baseline_value,
        )
    return row


def _planned_fields(planned: dict[str, object]) -> dict[str, object]:
    return {
        "run_key": planned["run_key"],
        "group_kind": planned["group_kind"],
        "group_name": planned["group_name"],
        "seed": planned["seed"],
        "topology": planned["topology"],
        "topology_mode": planned["topology_mode"],
        "algorithm_label": planned["algorithm_label"],
        "aggregation": planned["aggregation"],
        "attack_strategy": planned["attack_strategy"],
        "byzantine_fraction": planned["byzantine_fraction"],
        "byzantine_placement": planned["byzantine_placement"],
        "target_arm": planned["target_arm"],
        "inflated_mean": planned["inflated_mean"],
    }


def _condition_fields(planned: dict[str, object]) -> dict[str, object]:
    return {key: planned[key] for key in CONDITION_KEYS}


def _required_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent[key]
    if not isinstance(value, dict):
        raise TypeError(f"expected {key} to be a JSON object")
    return value


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _numeric_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if isinstance(item, (int, float))]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _numeric_difference(target: object, baseline: object) -> float | None:
    if not isinstance(target, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    return float(target) - float(baseline)


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: Iterable[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in fieldnames})


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _load_manifest(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a JSON object")
    return loaded


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
