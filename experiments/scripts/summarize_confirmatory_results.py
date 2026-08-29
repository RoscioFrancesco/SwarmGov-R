"""Summarize processed confirmatory tables with confidence intervals."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPO_ROOT / "experiments" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from aggregate_confirmatory_results import (  # noqa: E402
    AGGREGATE_SCHEMA_VERSION,
    CURVES_FILE,
    DEFAULT_PROCESSED_DIR,
    PAIRED_FILE,
    RUN_METRICS_FILE,
)
from aggregate_confirmatory_results import (  # noqa: E402
    SUMMARY_FILE as AGGREGATION_SUMMARY_FILE,
)

STATISTICS_SCHEMA_VERSION = "confirmatory_statistics_v1"
CONDITION_SUMMARY_FILE = "condition_summary.csv"
CURVE_SUMMARY_FILE = "curve_summary.csv"
PAIRED_SUMMARY_FILE = "paired_summary.csv"
STATISTICS_SUMMARY_FILE = "statistics_summary.json"

NORMAL_Z_95 = 1.959963984540054

SUMMARY_KEYS = (
    "group_kind",
    "group_name",
    "topology",
    "topology_mode",
    "algorithm_label",
    "aggregation",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "target_arm",
    "inflated_mean",
)

PAIR_SUMMARY_KEYS = (
    "comparison",
    "baseline_algorithm_label",
    "target_algorithm_label",
    "group_kind",
    "group_name",
    "topology",
    "topology_mode",
    "attack_strategy",
    "byzantine_fraction",
    "byzantine_placement",
    "target_arm",
    "inflated_mean",
)

SUMMARY_METRICS = (
    "mean_per_agent_regret",
    "total_population_regret",
    "median_honest_regret",
    "worst_decile_honest_regret",
    "max_honest_regret",
    "best_arm_identification_rate",
    "messages_sent",
    "scalar_values_sent",
)

PAIR_DIFFERENCE_METRICS = (
    "mean_per_agent_regret_difference",
    "total_population_regret_difference",
    "best_arm_identification_rate_difference",
    "messages_sent_difference",
    "scalar_values_sent_difference",
)

CURVE_METRICS = (
    "mean_regret",
    "total_regret",
)

CONDITION_SUMMARY_COLUMNS = (
    *SUMMARY_KEYS,
    "metric",
    "n",
    "mean",
    "std",
    "sem",
    "ci95_low",
    "ci95_high",
    "min",
    "max",
    "ci_method",
)

CURVE_SUMMARY_COLUMNS = (
    *SUMMARY_KEYS,
    "round",
    "metric",
    "n",
    "mean",
    "std",
    "sem",
    "ci95_low",
    "ci95_high",
    "min",
    "max",
    "ci_method",
)

PAIRED_SUMMARY_COLUMNS = (
    *PAIR_SUMMARY_KEYS,
    "metric",
    "n_pairs",
    "mean_difference",
    "std_difference",
    "sem_difference",
    "ci95_low",
    "ci95_high",
    "min_difference",
    "max_difference",
    "ci_method",
    "bootstrap_iterations",
    "bootstrap_seed",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(DEFAULT_PROCESSED_DIR))
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Where to write statistical summaries. Defaults to --input-dir.",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=2000,
        help="Bootstrap resamples for paired-difference confidence intervals.",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20260827,
        help="Deterministic seed for paired bootstrap summaries.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing statistical summary artifacts.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir) if args.output_dir is not None else input_dir
    if args.bootstrap_iterations <= 0:
        raise ValueError("--bootstrap-iterations must be positive")

    planned_outputs = _planned_output_paths(output_dir)
    _ensure_can_write(planned_outputs, overwrite=args.overwrite)
    _validate_aggregation_summary(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_rows = _read_csv(input_dir / RUN_METRICS_FILE)
    curve_rows = _read_csv(input_dir / CURVES_FILE)
    paired_rows = _read_csv(input_dir / PAIRED_FILE)

    condition_summary = _condition_summary_rows(run_rows)
    curve_summary = _curve_summary_rows(curve_rows)
    paired_summary = _paired_summary_rows(
        paired_rows,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )

    _write_csv(
        output_dir / CONDITION_SUMMARY_FILE,
        CONDITION_SUMMARY_COLUMNS,
        condition_summary,
    )
    _write_csv(output_dir / CURVE_SUMMARY_FILE, CURVE_SUMMARY_COLUMNS, curve_summary)
    _write_csv(
        output_dir / PAIRED_SUMMARY_FILE,
        PAIRED_SUMMARY_COLUMNS,
        paired_summary,
    )

    summary = {
        "schema_version": STATISTICS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "aggregation_schema_version": AGGREGATE_SCHEMA_VERSION,
        "bootstrap_iterations": args.bootstrap_iterations,
        "bootstrap_seed": args.bootstrap_seed,
        "ci_policy": {
            "condition_summary": "normal_approximation_across_seeds",
            "curve_summary": "normal_approximation_across_seeds_per_round",
            "paired_summary": "deterministic_paired_percentile_bootstrap",
            "single_seed": "degenerate_ci_equal_to_observed_mean",
        },
        "row_counts": {
            "condition_summary": len(condition_summary),
            "curve_summary": len(curve_summary),
            "paired_summary": len(paired_summary),
        },
        "outputs": {name: str(path) for name, path in planned_outputs.items()},
        "notes": (
            "Rounds are summarized per stored round across seeds, not treated "
            "as independent replicates. Canary or partial summaries are "
            "technical validation only."
        ),
    }
    _write_json(output_dir / STATISTICS_SUMMARY_FILE, summary)

    print("statistics_status=completed")
    print(f"condition_summary_rows={len(condition_summary)}")
    print(f"curve_summary_rows={len(curve_summary)}")
    print(f"paired_summary_rows={len(paired_summary)}")
    print(f"summary={output_dir / STATISTICS_SUMMARY_FILE}")
    return 0


def _planned_output_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "condition_summary": output_dir / CONDITION_SUMMARY_FILE,
        "curve_summary": output_dir / CURVE_SUMMARY_FILE,
        "paired_summary": output_dir / PAIRED_SUMMARY_FILE,
        "summary": output_dir / STATISTICS_SUMMARY_FILE,
    }


def _ensure_can_write(paths: dict[str, Path], *, overwrite: bool) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "statistical summary artifacts already exist; pass --overwrite "
            f"to replace them: {names}"
        )


def _validate_aggregation_summary(input_dir: Path) -> None:
    summary_path = input_dir / AGGREGATION_SUMMARY_FILE
    if not summary_path.exists():
        raise FileNotFoundError(f"missing aggregation summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("aggregation summary must be a JSON object")
    if summary.get("schema_version") != AGGREGATE_SCHEMA_VERSION:
        raise ValueError("unsupported aggregation schema version")
    if summary.get("validation_status") != "passed":
        raise ValueError("aggregation validation status is not passed")
    for filename in (RUN_METRICS_FILE, CURVES_FILE, PAIRED_FILE):
        path = input_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"missing processed table: {path}")


def _condition_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_key(row, SUMMARY_KEYS)].append(row)

    output: list[dict[str, object]] = []
    for key, group_rows in sorted(grouped.items()):
        base = dict(zip(SUMMARY_KEYS, key, strict=True))
        for metric in SUMMARY_METRICS:
            values = _numeric_values(row.get(metric, "") for row in group_rows)
            output.append(
                {
                    **base,
                    "metric": metric,
                    **_normal_summary(values),
                }
            )
    return output


def _curve_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    group_keys = (*SUMMARY_KEYS, "round")
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_key(row, group_keys)].append(row)

    output: list[dict[str, object]] = []
    for key, group_rows in sorted(grouped.items(), key=_curve_sort_key):
        base = dict(zip(group_keys, key, strict=True))
        for metric in CURVE_METRICS:
            values = _numeric_values(row.get(metric, "") for row in group_rows)
            output.append(
                {
                    **base,
                    "metric": metric,
                    **_normal_summary(values),
                }
            )
    return output


def _paired_summary_rows(
    rows: list[dict[str, str]],
    *,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_key(row, PAIR_SUMMARY_KEYS)].append(row)

    rng = random.Random(bootstrap_seed)
    output: list[dict[str, object]] = []
    for key, group_rows in sorted(grouped.items()):
        base = dict(zip(PAIR_SUMMARY_KEYS, key, strict=True))
        for metric in PAIR_DIFFERENCE_METRICS:
            values = _numeric_values(row.get(metric, "") for row in group_rows)
            output.append(
                {
                    **base,
                    "metric": metric,
                    **_paired_bootstrap_summary(
                        values,
                        rng=rng,
                        iterations=bootstrap_iterations,
                        bootstrap_seed=bootstrap_seed,
                    ),
                }
            )
    return output


def _normal_summary(values: list[float]) -> dict[str, object]:
    n = len(values)
    if n == 0:
        return _empty_summary("no_values")
    mean_value = sum(values) / n
    if n == 1:
        return {
            "n": n,
            "mean": mean_value,
            "std": 0.0,
            "sem": 0.0,
            "ci95_low": mean_value,
            "ci95_high": mean_value,
            "min": mean_value,
            "max": mean_value,
            "ci_method": "degenerate_single_seed",
        }
    std_value = _sample_std(values, mean_value)
    sem_value = std_value / math.sqrt(n)
    margin = NORMAL_Z_95 * sem_value
    return {
        "n": n,
        "mean": mean_value,
        "std": std_value,
        "sem": sem_value,
        "ci95_low": mean_value - margin,
        "ci95_high": mean_value + margin,
        "min": min(values),
        "max": max(values),
        "ci_method": "normal_approximation",
    }


def _paired_bootstrap_summary(
    values: list[float],
    *,
    rng: random.Random,
    iterations: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    n = len(values)
    if n == 0:
        return {
            **_empty_summary("no_values"),
            "n_pairs": 0,
            "mean_difference": "",
            "std_difference": "",
            "sem_difference": "",
            "min_difference": "",
            "max_difference": "",
            "bootstrap_iterations": iterations,
            "bootstrap_seed": bootstrap_seed,
        }
    mean_value = sum(values) / n
    if n == 1:
        return {
            "n_pairs": n,
            "mean_difference": mean_value,
            "std_difference": 0.0,
            "sem_difference": 0.0,
            "ci95_low": mean_value,
            "ci95_high": mean_value,
            "min_difference": mean_value,
            "max_difference": mean_value,
            "ci_method": "degenerate_single_pair",
            "bootstrap_iterations": iterations,
            "bootstrap_seed": bootstrap_seed,
        }

    bootstrap_means = []
    for _ in range(iterations):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        bootstrap_means.append(total / n)
    bootstrap_means.sort()
    std_value = _sample_std(values, mean_value)
    sem_value = std_value / math.sqrt(n)
    return {
        "n_pairs": n,
        "mean_difference": mean_value,
        "std_difference": std_value,
        "sem_difference": sem_value,
        "ci95_low": _percentile(bootstrap_means, 2.5),
        "ci95_high": _percentile(bootstrap_means, 97.5),
        "min_difference": min(values),
        "max_difference": max(values),
        "ci_method": "paired_percentile_bootstrap",
        "bootstrap_iterations": iterations,
        "bootstrap_seed": bootstrap_seed,
    }


def _empty_summary(method: str) -> dict[str, object]:
    return {
        "n": 0,
        "mean": "",
        "std": "",
        "sem": "",
        "ci95_low": "",
        "ci95_high": "",
        "min": "",
        "max": "",
        "ci_method": method,
    }


def _sample_std(values: Sequence[float], mean_value: float) -> float:
    return math.sqrt(
        sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    )


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute percentile of empty values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (percentile / 100.0) * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _key(row: dict[str, str], fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def _curve_sort_key(item: tuple[tuple[str, ...], list[dict[str, str]]]) -> tuple:
    key, _ = item
    round_value = _float_or_none(key[-1])
    round_sort = round_value if round_value is not None else math.inf
    return (*key[:-1], round_sort)


def _numeric_values(values: Iterable[str]) -> list[float]:
    parsed = []
    for value in values:
        numeric = _float_or_none(value)
        if numeric is not None:
            parsed.append(numeric)
    return parsed


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
