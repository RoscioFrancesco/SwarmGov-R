"""Run or dry-run the frozen Milestone 8 confirmatory manifest."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import platform
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from swarmgov.analysis.compact import (  # noqa: E402
    COMPACT_RECORD_SCHEMA_VERSION,
    CurveSamplingConfig,
    compact_multi_agent_result,
)
from swarmgov.config import StudyConfig  # noqa: E402
from swarmgov.simulation import MultiAgentRunResult, run_multi_agent  # noqa: E402

DEFAULT_MANIFEST = Path("experiments/manifests/confirmatory_m8_manifest.json")
DEFAULT_OUTPUT_DIR = Path("results/raw/confirmatory-m8")


@dataclass(frozen=True)
class PlannedRun:
    manifest_name: str
    group_kind: str
    group_name: str
    seed: int
    topology: str
    topology_mode: str
    algorithm_label: str
    aggregation: str
    attack_strategy: str
    byzantine_fraction: float
    byzantine_placement: str
    target_arm: int | None
    inflated_mean: float

    @property
    def run_key(self) -> str:
        return "_".join(
            [
                self.group_kind,
                self.group_name,
                f"seed-{self.seed}",
                self.topology,
                self.topology_mode,
                self.algorithm_label,
                self.attack_strategy,
                self.byzantine_placement,
            ]
        )

    @property
    def filename(self) -> str:
        return f"{self.run_key}.json"

    def to_record(self) -> dict[str, object]:
        return {
            "manifest_name": self.manifest_name,
            "group_kind": self.group_kind,
            "group_name": self.group_name,
            "seed": self.seed,
            "topology": self.topology,
            "topology_mode": self.topology_mode,
            "algorithm_label": self.algorithm_label,
            "aggregation": self.aggregation,
            "attack_strategy": self.attack_strategy,
            "byzantine_fraction": self.byzantine_fraction,
            "byzantine_placement": self.byzantine_placement,
            "target_arm": self.target_arm,
            "inflated_mean": self.inflated_mean,
            "run_key": self.run_key,
        }


@dataclass(frozen=True)
class RunOutcome:
    run_key: str
    filename: str
    status: str
    runtime_seconds: float
    error: str | None = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--group-kind",
        choices=("primary", "sensitivity", "all"),
        default="primary",
        help="Which manifest groups to expand.",
    )
    parser.add_argument(
        "--run-group",
        action="append",
        default=None,
        help="Restrict execution to one or more manifest group names.",
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Use only the first N confirmatory seeds inside each group.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Execute or display only the first N expanded runs.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=25,
        help="Print progress every N non-skipped runs.",
    )
    parser.add_argument(
        "--curve-stride",
        type=int,
        default=1,
        help="Store every Nth regret-curve point in compact result records.",
    )
    parser.add_argument(
        "--max-curve-points",
        type=int,
        default=2000,
        help="Maximum stored regret-curve points per compact result record.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing per-run result records.",
    )
    parser.add_argument(
        "--repair-invalid-existing",
        action="store_true",
        help=(
            "Rerun existing records that are unreadable or do not match the "
            "planned completed-record schema. Valid completed records are "
            "still skipped unless --overwrite is passed."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for executing non-skipped runs.",
    )
    args = parser.parse_args()
    if args.workers <= 0:
        raise ValueError("--workers must be positive")

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    manifest = _load_manifest(manifest_path)
    curve_sampling = CurveSamplingConfig(
        stride=args.curve_stride,
        max_points=args.max_curve_points,
    )
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

    _validate_planned_runs(manifest, planned_runs, output_dir)
    print(f"manifest={manifest_path}")
    print(f"output_dir={output_dir}")
    print(f"group_kind={args.group_kind}")
    print(f"planned_runs={len(planned_runs)}")
    print(f"expected_full_primary_runs={_expected_primary_runs(manifest)}")
    print(f"expected_full_total_runs={_expected_total_runs(manifest)}")
    print(f"compact_schema_version={COMPACT_RECORD_SCHEMA_VERSION}")
    print(
        f"curve_sampling=stride:{curve_sampling.stride},"
        f"max_points:{curve_sampling.max_points}",
    )
    print(f"workers={args.workers}")
    if args.dry_run:
        _print_dry_run_preview(planned_runs)
        return 0

    started = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, object]] = []
    pending_runs: list[PlannedRun] = []

    for planned in planned_runs:
        output_path = output_dir / planned.filename
        if output_path.exists() and not args.overwrite:
            if _existing_completed_record_matches(output_path, planned):
                skipped += 1
                continue
            if not args.repair_invalid_existing:
                raise ValueError(
                    "existing record is not a valid completed record; pass "
                    f"--repair-invalid-existing to rerun it: {output_path}"
                )
        pending_runs.append(planned)

    if pending_runs:
        outcomes = _execute_pending_runs(
            pending_runs=pending_runs,
            manifest_path=manifest_path,
            manifest=manifest,
            output_dir=output_dir,
            curve_sampling=curve_sampling,
            workers=args.workers,
        )
        for processed, outcome in enumerate(outcomes, start=1):
            if outcome.status == "completed":
                completed += 1
            else:
                failed += 1
                failures.append(
                    {
                        "run_key": outcome.run_key,
                        "filename": outcome.filename,
                        "error": outcome.error,
                        "output_path": str(output_dir / outcome.filename),
                    }
                )
            if args.progress_interval > 0 and (
                processed == 1
                or processed == len(pending_runs)
                or processed % args.progress_interval == 0
            ):
                elapsed = perf_counter() - started
                done = completed + failed + skipped
                print(
                    f"progress={done}/{len(planned_runs)} "
                    f"completed={completed} skipped={skipped} failed={failed} "
                    f"elapsed_seconds={elapsed:.1f}",
                    flush=True,
                )

    summary = {
        "status": "completed" if failed == 0 else "completed_with_failures",
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "group_kind": args.group_kind,
        "run_groups": args.run_group,
        "max_seeds": args.max_seeds,
        "max_runs": args.max_runs,
        "planned_runs": len(planned_runs),
        "completed_runs": completed,
        "skipped_existing_runs": skipped,
        "failed_runs": failed,
        "workers": args.workers,
        "runtime_seconds": perf_counter() - started,
        "failures": failures,
        "compact_schema_version": COMPACT_RECORD_SCHEMA_VERSION,
        "curve_sampling": {
            "stride": curve_sampling.stride,
            "max_points": curve_sampling.max_points,
        },
        "full_manifest_run_count_estimate": manifest["run_count_estimate"],
    }
    (output_dir / "manifest_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        f"completed_runs={completed} skipped_existing_runs={skipped} "
        f"failed_runs={failed}",
    )
    print(f"summary={output_dir / 'manifest_run_summary.json'}")
    return 1 if failed else 0


def _execute_pending_runs(
    *,
    pending_runs: list[PlannedRun],
    manifest_path: Path,
    manifest: dict[str, Any],
    output_dir: Path,
    curve_sampling: CurveSamplingConfig,
    workers: int,
) -> Iterable[RunOutcome]:
    if workers == 1:
        for planned in pending_runs:
            yield _run_single_planned(
                planned=planned,
                manifest_path=str(manifest_path),
                manifest=manifest,
                output_dir=str(output_dir),
                curve_sampling=curve_sampling,
            )
        return

    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _run_single_planned,
                planned=planned,
                manifest_path=str(manifest_path),
                manifest=manifest,
                output_dir=str(output_dir),
                curve_sampling=curve_sampling,
            )
            for planned in pending_runs
        ]
        for future in concurrent.futures.as_completed(futures):
            yield future.result()


def _run_single_planned(
    *,
    planned: PlannedRun,
    manifest_path: str,
    manifest: dict[str, Any],
    output_dir: str,
    curve_sampling: CurveSamplingConfig,
) -> RunOutcome:
    output_root = Path(output_dir)
    output_path = output_root / planned.filename
    run_started = perf_counter()
    config_data = study_config_from_manifest(manifest, planned, output_root)
    try:
        result = run_multi_agent(StudyConfig.from_mapping(config_data), write=False)
        if not isinstance(result, MultiAgentRunResult):
            raise RuntimeError("expected a multi-agent result")
        runtime_seconds = perf_counter() - run_started
        _write_compact_result(
            output_path=output_path,
            manifest_path=Path(manifest_path),
            manifest=manifest,
            planned=planned,
            config_data=config_data,
            result=result,
            runtime_seconds=runtime_seconds,
            curve_sampling=curve_sampling,
        )
        stale_failure_path = output_path.with_suffix(".failed.json")
        if stale_failure_path.exists():
            stale_failure_path.unlink()
        return RunOutcome(
            run_key=planned.run_key,
            filename=planned.filename,
            status="completed",
            runtime_seconds=runtime_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        runtime_seconds = perf_counter() - run_started
        _write_failure_record(
            output_path=output_path.with_suffix(".failed.json"),
            manifest_path=Path(manifest_path),
            manifest=manifest,
            planned=planned,
            config_data=config_data,
            error=str(exc),
            runtime_seconds=runtime_seconds,
        )
        return RunOutcome(
            run_key=planned.run_key,
            filename=planned.filename,
            status="failed",
            runtime_seconds=runtime_seconds,
            error=str(exc),
        )


def _existing_completed_record_matches(path: Path, planned: PlannedRun) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(record, dict):
        return False
    result = record.get("result")
    if not isinstance(result, dict):
        return False
    return (
        record.get("status") == "completed"
        and record.get("planned_run") == planned.to_record()
        and result.get("schema_version") == COMPACT_RECORD_SCHEMA_VERSION
    )


def expand_manifest(
    manifest: dict[str, Any],
    *,
    group_kind: str = "primary",
    run_groups: list[str] | None = None,
    max_seeds: int | None = None,
) -> Iterable[PlannedRun]:
    seed_values = _seed_values(manifest, max_seeds=max_seeds)
    selected_group_names = set(run_groups or [])
    for kind, group in _selected_groups(manifest, group_kind=group_kind):
        if selected_group_names and group["name"] not in selected_group_names:
            continue
        placements = _placements(group["attack"])
        for seed in seed_values:
            for topology in group["topologies"]:
                for algorithm_label in group["algorithms"]:
                    for placement in placements:
                        aggregation = _aggregation_for_algorithm(algorithm_label)
                        attack = group["attack"]
                        yield PlannedRun(
                            manifest_name=str(manifest["manifest_name"]),
                            group_kind=kind,
                            group_name=str(group["name"]),
                            seed=seed,
                            topology=str(topology),
                            topology_mode=str(group["topology_mode"]),
                            algorithm_label=str(algorithm_label),
                            aggregation=aggregation,
                            attack_strategy=str(attack["strategy"]),
                            byzantine_fraction=float(attack["byzantine_fraction"]),
                            byzantine_placement=str(placement),
                            target_arm=attack.get("target_arm"),
                            inflated_mean=float(attack["inflated_mean"]),
                        )


def study_config_from_manifest(
    manifest: dict[str, Any],
    planned: PlannedRun,
    output_dir: Path,
) -> dict[str, object]:
    hyper = manifest["fixed_hyperparameters"]
    is_independent = planned.algorithm_label == "independent"
    is_centralized = planned.algorithm_label == "centralized_clean_reference"
    algorithm_name = _algorithm_name(planned.algorithm_label)
    communication_enabled = not is_independent and not is_centralized
    topology_dynamic = planned.topology_mode == "dynamic"
    trim = hyper["trimmed_mean"]
    topology_change = (
        {
            "enabled": True,
            "change_round": hyper["dynamic_topology"]["change_round"],
            "rewire_fraction": hyper["dynamic_topology"]["rewire_fraction"],
            "preserve_connectivity": hyper["dynamic_topology"][
                "preserve_connectivity"
            ],
        }
        if topology_dynamic
        else {
            "enabled": False,
            "change_round": None,
            "rewire_fraction": 0.0,
            "preserve_connectivity": hyper["dynamic_topology"][
                "preserve_connectivity"
            ],
        }
    )
    aggregation_method = planned.aggregation
    return {
        "name": f"{manifest['manifest_name']}-{planned.run_key}",
        "stage": manifest["stage"],
        "description": (
            "Milestone 8 confirmatory manifest run. Results are confirmatory "
            "only when the frozen matrix is completed and validated."
        ),
        "seeds": {
            "master": manifest["master_seed"],
            "streams": [
                "environment",
                "graph",
                "agents",
                "attack",
                "simulation",
                "analysis",
            ],
        },
        "population": {
            "agents": hyper["agents"],
            "byzantine_fraction": planned.byzantine_fraction,
            "byzantine_placement": planned.byzantine_placement,
        },
        "bandit": {
            "arms": hyper["arms"],
            "arm_means": hyper["arm_means_easy_gap"],
            "reward_family": hyper["reward_family"],
        },
        "algorithm": {
            "name": algorithm_name,
            "parameters": {"exploration_c": hyper["exploration_c"]},
        },
        "graph": manifest["topology_parameters"][planned.topology],
        "communication": {
            "interval": hyper["communication_interval"],
            "enabled": communication_enabled,
        },
        "aggregation": {
            "method": aggregation_method,
            "trim_count": (
                trim["trim_count"] if aggregation_method == "trimmed_mean" else None
            ),
            "trim_fraction": (
                trim["trim_fraction"] if aggregation_method == "trimmed_mean" else None
            ),
            "small_neighborhood_policy": trim["small_neighborhood_policy"],
            "diagnostics": False,
        },
        "attack": {
            "strategy": planned.attack_strategy,
            "target_arm": planned.target_arm,
            "inflated_mean": planned.inflated_mean,
            "diagnostics": False,
        },
        "topology_change": topology_change,
        "experiment": {
            "horizon": hyper["horizon"],
            "seeds": [planned.seed],
            "output_dir": str(output_dir),
            "overwrite": False,
        },
    }


def _write_compact_result(
    *,
    output_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    planned: PlannedRun,
    config_data: dict[str, object],
    result: MultiAgentRunResult,
    runtime_seconds: float,
    curve_sampling: CurveSamplingConfig,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "completed",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_name": manifest["manifest_name"],
        "manifest_status_at_execution": manifest["status"],
        "planned_run": planned.to_record(),
        "runtime_seconds": runtime_seconds,
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependency_versions": _dependency_versions(),
        "resolved_config": StudyConfig.from_mapping(config_data).resolved_dict(),
        "result": compact_multi_agent_result(
            result,
            curve_sampling=curve_sampling,
        ),
    }
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_failure_record(
    *,
    output_path: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    planned: PlannedRun,
    config_data: dict[str, object],
    error: str,
    runtime_seconds: float,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "status": "failed",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_name": manifest["manifest_name"],
        "planned_run": planned.to_record(),
        "runtime_seconds": runtime_seconds,
        "error": error,
        "config_data": config_data,
    }
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _validate_planned_runs(
    manifest: dict[str, Any],
    planned_runs: list[PlannedRun],
    output_dir: Path,
) -> None:
    seen: set[str] = set()
    errors: list[str] = []
    for planned in planned_runs:
        if planned.run_key in seen:
            errors.append(f"duplicate run key: {planned.run_key}")
        seen.add(planned.run_key)
        try:
            StudyConfig.from_mapping(
                study_config_from_manifest(manifest, planned, output_dir)
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{planned.run_key}: {exc}")
    if errors:
        message = "\n".join(errors[:10])
        if len(errors) > 10:
            message += f"\n... {len(errors) - 10} more invalid runs"
        raise ValueError(f"invalid expanded manifest:\n{message}")


def _load_manifest(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a JSON object")
    return loaded


def _seed_values(manifest: dict[str, Any], *, max_seeds: int | None) -> list[int]:
    seed_spec = manifest["run_seeds"]
    if seed_spec["type"] != "inclusive_range":
        raise ValueError("only inclusive_range seed specs are supported")
    seeds = list(range(int(seed_spec["start"]), int(seed_spec["end"]) + 1))
    if len(seeds) != int(seed_spec["count"]):
        raise ValueError("manifest seed count does not match inclusive range")
    if max_seeds is None:
        return seeds
    if max_seeds <= 0:
        raise ValueError("--max-seeds must be positive")
    return seeds[:max_seeds]


def _selected_groups(
    manifest: dict[str, Any],
    *,
    group_kind: str,
) -> Iterable[tuple[str, dict[str, Any]]]:
    if group_kind in {"primary", "all"}:
        for group in manifest["primary_run_groups"]:
            yield "primary", group
    if group_kind in {"sensitivity", "all"}:
        for group in manifest["sensitivity_run_groups"]:
            yield "sensitivity", group


def _placements(attack: dict[str, Any]) -> tuple[str, ...]:
    if "placements" in attack:
        return tuple(str(placement) for placement in attack["placements"])
    return (str(attack["placement"]),)


def _aggregation_for_algorithm(algorithm_label: str) -> str:
    if algorithm_label in {"independent", "centralized_clean_reference", "mean"}:
        return "mean"
    if algorithm_label in {"median", "trimmed_mean"}:
        return algorithm_label
    raise ValueError(f"unsupported algorithm label: {algorithm_label}")


def _algorithm_name(algorithm_label: str) -> str:
    if algorithm_label == "independent":
        return "independent_ucb1"
    if algorithm_label == "centralized_clean_reference":
        return "centralized_pooled_shared_action_ucb1"
    if algorithm_label in {"mean", "median", "trimmed_mean"}:
        return "one_hop_weighted_pooling_ucb1"
    raise ValueError(f"unsupported algorithm label: {algorithm_label}")


def _expected_primary_runs(manifest: dict[str, Any]) -> int:
    return int(manifest["run_count_estimate"]["primary_planned_runs"])


def _expected_total_runs(manifest: dict[str, Any]) -> int:
    return int(manifest["run_count_estimate"]["total_planned_runs"])


def _print_dry_run_preview(planned_runs: list[PlannedRun]) -> None:
    for planned in planned_runs[:5]:
        print(f"preview={planned.run_key}")
    if len(planned_runs) > 5:
        print(f"preview_remaining={len(planned_runs) - 5}")


def _dependency_versions() -> dict[str, str]:
    packages = ("networkx", "numpy", "PyYAML", "swarmgov-r")
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "unknown"
    return versions


if __name__ == "__main__":
    raise SystemExit(main())
