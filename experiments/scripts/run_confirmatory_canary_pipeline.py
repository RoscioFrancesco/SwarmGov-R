"""Run a bounded end-to-end confirmatory canary pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path("experiments/manifests/confirmatory_m8_manifest.json")
DEFAULT_OUTPUT_ROOT = Path("results/canary/confirmatory-m8-e2e")

RUNNER = REPO_ROOT / "experiments" / "scripts" / "run_confirmatory_manifest.py"
VALIDATOR = (
    REPO_ROOT / "experiments" / "scripts" / "validate_confirmatory_results.py"
)
AGGREGATOR = (
    REPO_ROOT / "experiments" / "scripts" / "aggregate_confirmatory_results.py"
)
SUMMARIZER = (
    REPO_ROOT / "experiments" / "scripts" / "summarize_confirmatory_results.py"
)
FIGURES = REPO_ROOT / "experiments" / "scripts" / "generate_confirmatory_figures.py"


@dataclass(frozen=True)
class PipelinePaths:
    root: Path
    raw: Path
    validation: Path
    processed: Path
    statistics: Path
    figures: Path
    summary: Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--group-kind",
        choices=("primary", "sensitivity", "all"),
        default="primary",
        help="Which manifest groups to use for the canary slice.",
    )
    parser.add_argument(
        "--run-group",
        action="append",
        default=None,
        help="Restrict the canary to one or more manifest group names.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=2,
        help="Number of expanded manifest runs to execute.",
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Use only the first N confirmatory seeds inside each group.",
    )
    parser.add_argument(
        "--curve-stride",
        type=int,
        default=1,
        help="Store every Nth regret-curve point in compact raw records.",
    )
    parser.add_argument(
        "--max-curve-points",
        type=int,
        default=5,
        help="Maximum stored regret-curve points per compact raw record.",
    )
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=200,
        help="Bootstrap resamples for paired statistical canary summaries.",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20260827,
        help="Deterministic bootstrap seed for paired summaries.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow child stages to overwrite matching existing artifacts.",
    )
    args = parser.parse_args()

    if args.max_runs <= 0:
        raise ValueError("--max-runs must be positive")
    if args.max_seeds is not None and args.max_seeds <= 0:
        raise ValueError("--max-seeds must be positive")
    if args.bootstrap_iterations <= 0:
        raise ValueError("--bootstrap-iterations must be positive")

    manifest = Path(args.manifest)
    paths = _paths(Path(args.output_root))
    _prepare_output_root(paths.root, overwrite=args.overwrite)
    for directory in (
        paths.raw,
        paths.validation,
        paths.processed,
        paths.statistics,
        paths.figures,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    stages: list[dict[str, object]] = []
    status = "completed"
    try:
        stages.append(
            _run_stage(
                "run",
                _runner_command(args, manifest, paths.raw),
            )
        )
        stages.append(
            _run_stage(
                "validate",
                _validator_command(
                    args,
                    manifest,
                    paths.raw,
                    paths.validation / "validation_report.json",
                ),
            )
        )
        stages.append(
            _run_stage(
                "aggregate",
                _aggregator_command(args, manifest, paths.raw, paths.processed),
            )
        )
        stages.append(
            _run_stage(
                "statistics",
                _statistics_command(args, paths.processed, paths.statistics),
            )
        )
        stages.append(
            _run_stage(
                "figures",
                _figures_command(paths.statistics, paths.figures, args.overwrite),
            )
        )
    except subprocess.CalledProcessError as exc:
        status = "failed"
        stages.append(
            {
                "stage": "failed_command",
                "returncode": exc.returncode,
                "command": exc.cmd,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            }
        )

    summary = _summary(
        args=args,
        manifest=manifest,
        paths=paths,
        stages=stages,
        status=status,
    )
    _write_json(paths.summary, summary)
    print(f"canary_pipeline_status={status}")
    print(f"output_root={paths.root}")
    print(f"summary={paths.summary}")
    return 0 if status == "completed" else 1


def _paths(root: Path) -> PipelinePaths:
    return PipelinePaths(
        root=root,
        raw=root / "raw",
        validation=root / "validation",
        processed=root / "processed",
        statistics=root / "statistics",
        figures=root / "figures",
        summary=root / "canary_pipeline_summary.json",
    )


def _prepare_output_root(root: Path, *, overwrite: bool) -> None:
    if root.exists() and any(root.iterdir()) and not overwrite:
        raise FileExistsError(
            f"output root is not empty: {root}. "
            "Choose a new --output-root or pass --overwrite."
        )
    root.mkdir(parents=True, exist_ok=True)


def _runner_command(
    args: argparse.Namespace,
    manifest: Path,
    raw_dir: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--manifest",
        str(manifest),
        "--output-dir",
        str(raw_dir),
        "--group-kind",
        args.group_kind,
        "--max-runs",
        str(args.max_runs),
        "--curve-stride",
        str(args.curve_stride),
        "--max-curve-points",
        str(args.max_curve_points),
        "--progress-interval",
        "1",
    ]
    _append_optional_filters(command, args)
    if args.overwrite:
        command.append("--overwrite")
    return command


def _validator_command(
    args: argparse.Namespace,
    manifest: Path,
    raw_dir: Path,
    report_path: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(VALIDATOR),
        "--manifest",
        str(manifest),
        "--output-dir",
        str(raw_dir),
        "--group-kind",
        args.group_kind,
        "--max-runs",
        str(args.max_runs),
        "--report-path",
        str(report_path),
    ]
    _append_optional_filters(command, args)
    return command


def _aggregator_command(
    args: argparse.Namespace,
    manifest: Path,
    raw_dir: Path,
    processed_dir: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(AGGREGATOR),
        "--manifest",
        str(manifest),
        "--input-dir",
        str(raw_dir),
        "--output-dir",
        str(processed_dir),
        "--group-kind",
        args.group_kind,
        "--max-runs",
        str(args.max_runs),
    ]
    _append_optional_filters(command, args)
    if args.overwrite:
        command.append("--overwrite")
    return command


def _statistics_command(
    args: argparse.Namespace,
    processed_dir: Path,
    statistics_dir: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(SUMMARIZER),
        "--input-dir",
        str(processed_dir),
        "--output-dir",
        str(statistics_dir),
        "--bootstrap-iterations",
        str(args.bootstrap_iterations),
        "--bootstrap-seed",
        str(args.bootstrap_seed),
    ]
    if args.overwrite:
        command.append("--overwrite")
    return command


def _figures_command(
    statistics_dir: Path,
    figures_dir: Path,
    overwrite: bool,
) -> list[str]:
    command = [
        sys.executable,
        str(FIGURES),
        "--input-dir",
        str(statistics_dir),
        "--output-dir",
        str(figures_dir),
    ]
    if overwrite:
        command.append("--overwrite")
    return command


def _append_optional_filters(command: list[str], args: argparse.Namespace) -> None:
    if args.max_seeds is not None:
        command.extend(["--max-seeds", str(args.max_seeds)])
    for run_group in args.run_group or []:
        command.extend(["--run-group", str(run_group)])


def _run_stage(stage: str, command: list[str]) -> dict[str, object]:
    print(f"stage={stage}")
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return {
        "stage": stage,
        "returncode": completed.returncode,
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _summary(
    *,
    args: argparse.Namespace,
    manifest: Path,
    paths: PipelinePaths,
    stages: list[dict[str, object]],
    status: str,
) -> dict[str, object]:
    return {
        "status": status,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest": str(manifest),
        "output_root": str(paths.root),
        "group_kind": args.group_kind,
        "run_groups": args.run_group,
        "max_runs": args.max_runs,
        "max_seeds": args.max_seeds,
        "curve_sampling": {
            "stride": args.curve_stride,
            "max_points": args.max_curve_points,
        },
        "bootstrap": {
            "iterations": args.bootstrap_iterations,
            "seed": args.bootstrap_seed,
        },
        "directories": {
            "raw": str(paths.raw),
            "validation": str(paths.validation),
            "processed": str(paths.processed),
            "statistics": str(paths.statistics),
            "figures": str(paths.figures),
        },
        "key_outputs": {
            "raw_summary": str(paths.raw / "manifest_run_summary.json"),
            "validation_report": str(paths.validation / "validation_report.json"),
            "aggregation_summary": str(paths.processed / "aggregation_summary.json"),
            "statistics_summary": str(paths.statistics / "statistics_summary.json"),
            "figure_summary": str(paths.figures / "figure_summary.json"),
            "report_tables": str(paths.figures / "report_tables.md"),
        },
        "stages": stages,
        "notes": (
            "This is a bounded end-to-end technical canary. It is not "
            "confirmatory scientific evidence and does not replace the full "
            "Milestone 8 sweep."
        ),
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
