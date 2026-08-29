"""Run the Milestone 8 primary confirmatory pipeline end to end."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path("experiments/manifests/confirmatory_m8_manifest.json")
DEFAULT_RAW_DIR = Path("results/raw/confirmatory-m8")
DEFAULT_PROCESSED_DIR = Path("results/processed/confirmatory-m8")
DEFAULT_FIGURES_DIR = Path("results/figures/confirmatory-m8")

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
    raw_dir: Path
    processed_dir: Path
    statistics_dir: Path
    figures_dir: Path
    log_dir: Path
    status_path: Path
    pid_path: Path
    done_path: Path
    failed_path: Path


def main() -> int:
    if "--detach" in sys.argv[1:]:
        return _detach_current_invocation()

    args = _parse_args()
    paths = _paths(args)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    paths.figures_dir.mkdir(parents=True, exist_ok=True)
    paths.pid_path.write_text(f"{_current_pid()}\n", encoding="utf-8")
    _remove_completion_markers(paths)

    started = perf_counter()
    started_at_utc = datetime.now(UTC).isoformat()
    stages: list[dict[str, object]] = []
    status = "completed"
    failure: dict[str, object] | None = None
    _write_status(
        paths,
        args=args,
        status="running",
        current_stage=None,
        stages=stages,
        started_at_utc=started_at_utc,
    )

    try:
        for stage_name, command in _stage_commands(args, paths):
            stage = _run_stage(stage_name, command, paths.log_dir)
            stages.append(stage)
            _write_status(
                paths,
                args=args,
                status="running",
                current_stage=stage_name,
                stages=stages,
                started_at_utc=started_at_utc,
            )
    except subprocess.CalledProcessError as exc:
        status = "failed"
        failure = {
            "stage": _stage_name_from_command(exc.cmd),
            "returncode": exc.returncode,
            "command": exc.cmd,
        }
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        failure = {"stage": "pipeline", "error": str(exc)}

    runtime_seconds = perf_counter() - started
    final_payload = _status_payload(
        paths=paths,
        args=args,
        status=status,
        current_stage=None,
        stages=stages,
        started_at_utc=started_at_utc,
        runtime_seconds=runtime_seconds,
        failure=failure,
    )
    _write_json(paths.status_path, final_payload)
    marker_path = paths.done_path if status == "completed" else paths.failed_path
    marker_path.write_text(
        json.dumps(final_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    notification = _send_notification(status=status, paths=paths, enabled=args.notify)
    if notification is not None:
        final_payload["notification"] = notification
        _write_json(paths.status_path, final_payload)
    return 0 if status == "completed" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--processed-dir", default=str(DEFAULT_PROCESSED_DIR))
    parser.add_argument(
        "--statistics-dir",
        default=None,
        help="Defaults to --processed-dir, matching the documented M8 contract.",
    )
    parser.add_argument("--figures-dir", default=str(DEFAULT_FIGURES_DIR))
    parser.add_argument("--log-dir", default=None)
    parser.add_argument(
        "--group-kind",
        choices=("primary", "sensitivity", "all"),
        default="primary",
    )
    parser.add_argument("--run-group", action="append", default=None)
    parser.add_argument("--max-seeds", type=int, default=None)
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--progress-interval", type=int, default=50)
    parser.add_argument("--curve-stride", type=int, default=1)
    parser.add_argument("--max-curve-points", type=int, default=2000)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260827)
    parser.add_argument(
        "--overwrite-derived",
        action="store_true",
        help="Regenerate processed/statistical/figure artifacts from raw records.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Best-effort macOS notification after completion or failure.",
    )
    parser.add_argument(
        "--skip-final-checks",
        action="store_true",
        help="Skip final lint and pytest stages; intended only for tiny tests.",
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Launch this pipeline in a detached background process and exit.",
    )
    args = parser.parse_args()
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    if args.max_seeds is not None and args.max_seeds <= 0:
        raise ValueError("--max-seeds must be positive")
    if args.max_runs is not None and args.max_runs <= 0:
        raise ValueError("--max-runs must be positive")
    if args.bootstrap_iterations <= 0:
        raise ValueError("--bootstrap-iterations must be positive")
    return args


def _detach_current_invocation() -> int:
    child_args = [arg for arg in sys.argv[1:] if arg != "--detach"]
    command = [sys.executable, str(Path(__file__).resolve()), *child_args]
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"milestone8_pipeline_pid={process.pid}")
    print("milestone8_pipeline_status=detached")
    return 0


def _paths(args: argparse.Namespace) -> PipelinePaths:
    raw_dir = Path(args.raw_dir)
    processed_dir = Path(args.processed_dir)
    statistics_dir = (
        Path(args.statistics_dir) if args.statistics_dir is not None else processed_dir
    )
    figures_dir = Path(args.figures_dir)
    log_dir = (
        Path(args.log_dir)
        if args.log_dir is not None
        else raw_dir / "_milestone8_pipeline"
    )
    return PipelinePaths(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        statistics_dir=statistics_dir,
        figures_dir=figures_dir,
        log_dir=log_dir,
        status_path=log_dir / "milestone8_pipeline_status.json",
        pid_path=log_dir / "milestone8_pipeline.pid",
        done_path=log_dir / "milestone8_pipeline.done.json",
        failed_path=log_dir / "milestone8_pipeline.failed.json",
    )


def _stage_commands(
    args: argparse.Namespace,
    paths: PipelinePaths,
) -> list[tuple[str, list[str]]]:
    manifest = str(Path(args.manifest))
    commands = [
        (
            "run",
            [
                sys.executable,
                str(RUNNER),
                "--manifest",
                manifest,
                "--output-dir",
                str(paths.raw_dir),
                "--group-kind",
                args.group_kind,
                "--workers",
                str(args.workers),
                "--progress-interval",
                str(args.progress_interval),
                "--curve-stride",
                str(args.curve_stride),
                "--max-curve-points",
                str(args.max_curve_points),
                "--repair-invalid-existing",
            ],
        ),
        (
            "validate",
            [
                sys.executable,
                str(VALIDATOR),
                "--manifest",
                manifest,
                "--output-dir",
                str(paths.raw_dir),
                "--group-kind",
                args.group_kind,
                "--report-path",
                str(paths.processed_dir / "validation_report.json"),
            ],
        ),
        (
            "aggregate",
            [
                sys.executable,
                str(AGGREGATOR),
                "--manifest",
                manifest,
                "--input-dir",
                str(paths.raw_dir),
                "--output-dir",
                str(paths.processed_dir),
                "--group-kind",
                args.group_kind,
            ],
        ),
        (
            "statistics",
            [
                sys.executable,
                str(SUMMARIZER),
                "--input-dir",
                str(paths.processed_dir),
                "--output-dir",
                str(paths.statistics_dir),
                "--bootstrap-iterations",
                str(args.bootstrap_iterations),
                "--bootstrap-seed",
                str(args.bootstrap_seed),
            ],
        ),
        (
            "figures",
            [
                sys.executable,
                str(FIGURES),
                "--input-dir",
                str(paths.statistics_dir),
                "--output-dir",
                str(paths.figures_dir),
            ],
        ),
    ]
    if not args.skip_final_checks:
        commands.extend(
            [
                (
                    "lint",
                    [sys.executable, "-m", "ruff", "check", "."],
                ),
                (
                    "tests",
                    [sys.executable, "-m", "pytest"],
                ),
            ]
        )
    commands = _append_filters(commands, args)
    if args.overwrite_derived:
        commands = _append_overwrite_to_derived_stages(commands)
    return commands


def _append_filters(
    commands: list[tuple[str, list[str]]],
    args: argparse.Namespace,
) -> list[tuple[str, list[str]]]:
    filtered: list[tuple[str, list[str]]] = []
    for stage, command in commands:
        command = list(command)
        if stage in {"run", "validate", "aggregate"}:
            if args.max_seeds is not None:
                command.extend(["--max-seeds", str(args.max_seeds)])
            if args.max_runs is not None:
                command.extend(["--max-runs", str(args.max_runs)])
            for run_group in args.run_group or []:
                command.extend(["--run-group", str(run_group)])
        filtered.append((stage, command))
    return filtered


def _append_overwrite_to_derived_stages(
    commands: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    rewritten: list[tuple[str, list[str]]] = []
    for stage, command in commands:
        command = list(command)
        if stage in {"aggregate", "statistics", "figures"}:
            command.append("--overwrite")
        rewritten.append((stage, command))
    return rewritten


def _run_stage(
    stage_name: str,
    command: list[str],
    log_dir: Path,
) -> dict[str, object]:
    log_path = log_dir / f"{stage_name}.log"
    started = perf_counter()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now(UTC).isoformat()}] stage={stage_name}\n")
        log.write(f"command={json.dumps(command)}\n")
        log.flush()
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
        )
        log.write(
            f"[{datetime.now(UTC).isoformat()}] "
            f"stage={stage_name} returncode={completed.returncode}\n"
        )
    return {
        "stage": stage_name,
        "status": "completed",
        "returncode": completed.returncode,
        "runtime_seconds": perf_counter() - started,
        "command": command,
        "log_path": str(log_path),
    }


def _write_status(
    paths: PipelinePaths,
    *,
    args: argparse.Namespace,
    status: str,
    current_stage: str | None,
    stages: list[dict[str, object]],
    started_at_utc: str | None,
) -> None:
    payload = _status_payload(
        paths=paths,
        args=args,
        status=status,
        current_stage=current_stage,
        stages=stages,
        started_at_utc=started_at_utc,
        runtime_seconds=None,
        failure=None,
    )
    _write_json(paths.status_path, payload)


def _status_payload(
    *,
    paths: PipelinePaths,
    args: argparse.Namespace,
    status: str,
    current_stage: str | None,
    stages: list[dict[str, object]],
    started_at_utc: str | None,
    runtime_seconds: float | None,
    failure: dict[str, object] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "milestone8_pipeline_status_v1",
        "status": status,
        "current_stage": current_stage,
        "started_at_utc": started_at_utc,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": runtime_seconds,
        "manifest": args.manifest,
        "group_kind": args.group_kind,
        "run_groups": args.run_group,
        "max_seeds": args.max_seeds,
        "max_runs": args.max_runs,
        "workers": args.workers,
        "curve_sampling": {
            "stride": args.curve_stride,
            "max_points": args.max_curve_points,
        },
        "bootstrap": {
            "iterations": args.bootstrap_iterations,
            "seed": args.bootstrap_seed,
        },
        "skip_final_checks": args.skip_final_checks,
        "directories": {
            "raw": str(paths.raw_dir),
            "processed": str(paths.processed_dir),
            "statistics": str(paths.statistics_dir),
            "figures": str(paths.figures_dir),
            "logs": str(paths.log_dir),
        },
        "stage_count": len(stages),
        "stages": stages,
        "failure": failure,
        "signal_files": {
            "done": str(paths.done_path),
            "failed": str(paths.failed_path),
            "pid": str(paths.pid_path),
        },
        "notes": (
            "This pipeline runs the frozen Milestone 8 manifest slice through "
            "execution, validation, aggregation, statistics, figures, lint, "
            "and tests. Confirmatory claims require status=completed for the "
            "full primary manifest."
        ),
    }
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _remove_completion_markers(paths: PipelinePaths) -> None:
    for marker in (paths.done_path, paths.failed_path):
        if marker.exists():
            marker.unlink()


def _send_notification(
    *,
    status: str,
    paths: PipelinePaths,
    enabled: bool,
) -> dict[str, object] | None:
    if not enabled:
        return None
    osascript = shutil.which("osascript")
    if osascript is None:
        return {"status": "skipped", "reason": "osascript not found"}
    title = "SwarmGov-R Milestone 8"
    message = (
        "Confirmatory pipeline completed"
        if status == "completed"
        else "Confirmatory pipeline failed"
    )
    script = (
        f'display notification "{message}" '
        f'with title "{title}" subtitle "{paths.status_path}"'
    )
    try:
        completed = subprocess.run(  # noqa: S603
            [osascript, "-e", script],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error": str(exc)}
    return {
        "status": "sent" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _stage_name_from_command(command: object) -> str | None:
    if not isinstance(command, list):
        return None
    command_text = " ".join(str(part) for part in command)
    if "run_confirmatory_manifest.py" in command_text:
        return "run"
    if "validate_confirmatory_results.py" in command_text:
        return "validate"
    if "aggregate_confirmatory_results.py" in command_text:
        return "aggregate"
    if "summarize_confirmatory_results.py" in command_text:
        return "statistics"
    if "generate_confirmatory_figures.py" in command_text:
        return "figures"
    if "ruff" in command_text:
        return "lint"
    if "pytest" in command_text:
        return "tests"
    return None


def _current_pid() -> int:
    try:
        import os

        return os.getpid()
    except Exception:  # noqa: BLE001
        return -1


if __name__ == "__main__":
    raise SystemExit(main())
