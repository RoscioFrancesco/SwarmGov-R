"""Validate compact confirmatory result records against a manifest."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
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
    study_config_from_manifest,
)

from swarmgov.analysis.compact import COMPACT_RECORD_SCHEMA_VERSION  # noqa: E402
from swarmgov.config import StudyConfig  # noqa: E402

IGNORED_JSON_FILENAMES = {
    "manifest_run_summary.json",
    "validation_report.json",
}


@dataclass(frozen=True)
class ValidationIssue:
    category: str
    path: str | None
    run_key: str | None
    message: str

    def to_record(self) -> dict[str, object]:
        return {
            "category": self.category,
            "path": self.path,
            "run_key": self.run_key,
            "message": self.message,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--group-kind",
        choices=("primary", "sensitivity", "all"),
        default="primary",
        help="Which manifest groups to validate.",
    )
    parser.add_argument(
        "--run-group",
        action="append",
        default=None,
        help="Restrict validation to one or more manifest group names.",
    )
    parser.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Validate only the first N confirmatory seeds inside each group.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Validate only the first N expanded runs.",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        help="Where to write the JSON validation report.",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=20,
        help="Maximum issue lines to print to stdout.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    report_path = (
        Path(args.report_path)
        if args.report_path is not None
        else output_dir / "validation_report.json"
    )
    report = validate_confirmatory_results(
        manifest_path=manifest_path,
        output_dir=output_dir,
        group_kind=args.group_kind,
        run_groups=args.run_group,
        max_seeds=args.max_seeds,
        max_runs=args.max_runs,
        report_path=report_path,
    )
    _write_report(report_path, report)
    _print_summary(report, report_path, max_issues=args.max_issues)
    return 0 if report["status"] == "passed" else 1


def validate_confirmatory_results(
    *,
    manifest_path: Path,
    output_dir: Path,
    group_kind: str = "primary",
    run_groups: list[str] | None = None,
    max_seeds: int | None = None,
    max_runs: int | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    manifest = _load_manifest(manifest_path)
    planned_runs = list(
        expand_manifest(
            manifest,
            group_kind=group_kind,
            run_groups=run_groups,
            max_seeds=max_seeds,
        )
    )
    if max_runs is not None:
        if max_runs <= 0:
            raise ValueError("--max-runs must be positive")
        planned_runs = planned_runs[:max_runs]

    expected_by_key = {planned.run_key: planned for planned in planned_runs}
    expected_keys = set(expected_by_key)
    issues: list[ValidationIssue] = []
    records_by_claimed_key: dict[str, list[str]] = defaultdict(list)
    record_keys_seen: set[str] = set()
    valid_completed_keys: set[str] = set()
    failed_expected_keys: set[str] = set()
    completed_record_count = 0
    failed_record_count = 0

    for path in _record_paths(output_dir, report_path=report_path):
        loaded = _load_json_record(path)
        filename_key = _run_key_from_filename(path)
        if isinstance(loaded, ValidationIssue):
            issues.append(loaded)
            continue
        record = loaded
        if not isinstance(record, dict):
            issues.append(
                ValidationIssue(
                    category="read_error",
                    path=str(path),
                    run_key=filename_key,
                    message="record is not a JSON object",
                )
            )
            continue

        planned_record = record.get("planned_run")
        claimed_key = (
            planned_record.get("run_key")
            if isinstance(planned_record, dict)
            else None
        )
        if isinstance(claimed_key, str):
            records_by_claimed_key[claimed_key].append(str(path))
            record_keys_seen.add(claimed_key)
        else:
            issues.append(
                ValidationIssue(
                    category="incompatible_record",
                    path=str(path),
                    run_key=filename_key,
                    message="record has no planned_run.run_key",
                )
            )

        if filename_key not in expected_keys:
            issues.append(
                ValidationIssue(
                    category="unexpected_file",
                    path=str(path),
                    run_key=filename_key,
                    message="filename run key is not present in the manifest",
                )
            )
        if isinstance(claimed_key, str) and claimed_key not in expected_keys:
            issues.append(
                ValidationIssue(
                    category="unexpected_file",
                    path=str(path),
                    run_key=claimed_key,
                    message="claimed run key is not present in the manifest",
                )
            )
        if isinstance(claimed_key, str) and claimed_key != filename_key:
            issues.append(
                ValidationIssue(
                    category="incompatible_record",
                    path=str(path),
                    run_key=claimed_key,
                    message="filename run key does not match planned_run.run_key",
                )
            )

        expected = expected_by_key.get(claimed_key or filename_key)
        if path.name.endswith(".failed.json"):
            failed_record_count += 1
            if expected is not None and isinstance(claimed_key, str):
                failed_expected_keys.add(claimed_key)
            issues.extend(_validate_failure_record(record, expected, path))
            continue

        completed_record_count += 1
        record_issues = _validate_completed_record(
            record=record,
            expected=expected,
            manifest=manifest,
            output_dir=output_dir,
            path=path,
        )
        issues.extend(record_issues)
        if not record_issues and isinstance(claimed_key, str):
            valid_completed_keys.add(claimed_key)

    duplicate_keys = {
        run_key: paths
        for run_key, paths in records_by_claimed_key.items()
        if len(paths) > 1
    }
    for run_key, paths in sorted(duplicate_keys.items()):
        issues.append(
            ValidationIssue(
                category="duplicate_run_key",
                path=None,
                run_key=run_key,
                message=f"run key appears in {len(paths)} records",
            )
        )

    missing_keys = sorted(expected_keys - record_keys_seen)
    incomplete_keys = sorted(expected_keys - valid_completed_keys)
    status = "passed" if not issues and not incomplete_keys else "failed"
    issue_records = [issue.to_record() for issue in issues]
    return {
        "status": status,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_name": manifest.get("manifest_name"),
        "output_dir": str(output_dir),
        "group_kind": group_kind,
        "run_groups": run_groups,
        "max_seeds": max_seeds,
        "max_runs": max_runs,
        "compact_schema_version": COMPACT_RECORD_SCHEMA_VERSION,
        "expected_runs": len(expected_keys),
        "completed_records": completed_record_count,
        "valid_completed_runs": len(valid_completed_keys),
        "failed_records": failed_record_count,
        "failed_expected_run_keys": sorted(failed_expected_keys),
        "missing_run_keys": missing_keys,
        "incomplete_run_keys": incomplete_keys,
        "duplicate_run_keys": sorted(duplicate_keys),
        "issues": issue_records,
        "counts": {
            "issues": len(issue_records),
            "missing_records": len(missing_keys),
            "incomplete_expected_runs": len(incomplete_keys),
            "duplicate_run_keys": len(duplicate_keys),
            "unexpected_files": _count_issues(issues, "unexpected_file"),
            "incompatible_records": _count_issues(issues, "incompatible_record"),
            "read_errors": _count_issues(issues, "read_error"),
        },
    }


def _record_paths(output_dir: Path, *, report_path: Path | None) -> list[Path]:
    if not output_dir.exists():
        return []
    ignored = set(IGNORED_JSON_FILENAMES)
    if report_path is not None and report_path.parent == output_dir:
        ignored.add(report_path.name)
    return sorted(
        path
        for path in output_dir.glob("*.json")
        if path.is_file() and path.name not in ignored
    )


def _load_json_record(path: Path) -> dict[str, object] | ValidationIssue:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return ValidationIssue(
            category="read_error",
            path=str(path),
            run_key=_run_key_from_filename(path),
            message=str(exc),
        )


def _run_key_from_filename(path: Path) -> str:
    if path.name.endswith(".failed.json"):
        return path.name[: -len(".failed.json")]
    if path.name.endswith(".json"):
        return path.name[: -len(".json")]
    return path.stem


def _validate_failure_record(
    record: dict[str, object],
    expected: PlannedRun | None,
    path: Path,
) -> list[ValidationIssue]:
    run_key = _claimed_run_key(record)
    issues: list[ValidationIssue] = []
    if record.get("status") != "failed":
        issues.append(
            _issue(path, run_key, "incompatible_record", "failure record status")
        )
    if expected is not None and record.get("planned_run") != expected.to_record():
        issues.append(
            _issue(path, run_key, "incompatible_record", "failure planned_run")
        )
    if not isinstance(record.get("error"), str) or not record["error"]:
        issues.append(_issue(path, run_key, "incompatible_record", "failure error"))
    if not isinstance(record.get("config_data"), dict):
        issues.append(
            _issue(path, run_key, "incompatible_record", "failure config_data")
        )
    return issues


def _validate_completed_record(
    *,
    record: dict[str, object],
    expected: PlannedRun | None,
    manifest: dict[str, Any],
    output_dir: Path,
    path: Path,
) -> list[ValidationIssue]:
    run_key = _claimed_run_key(record)
    issues: list[ValidationIssue] = []
    required_top_level = (
        "status",
        "completed_at_utc",
        "manifest_path",
        "manifest_name",
        "manifest_status_at_execution",
        "planned_run",
        "runtime_seconds",
        "python_version",
        "platform",
        "dependency_versions",
        "resolved_config",
        "result",
    )
    for field in required_top_level:
        if field not in record:
            issues.append(
                _issue(path, run_key, "incompatible_record", f"missing {field}")
            )
    if record.get("status") != "completed":
        issues.append(_issue(path, run_key, "incompatible_record", "status"))
    if expected is None:
        return issues

    if record.get("manifest_name") != expected.manifest_name:
        issues.append(_issue(path, run_key, "incompatible_record", "manifest_name"))
    if record.get("planned_run") != expected.to_record():
        issues.append(_issue(path, run_key, "incompatible_record", "planned_run"))

    expected_config = StudyConfig.from_mapping(
        study_config_from_manifest(manifest, expected, output_dir)
    ).resolved_dict()
    actual_config = record.get("resolved_config")
    if not isinstance(actual_config, dict):
        issues.append(_issue(path, run_key, "incompatible_record", "resolved_config"))
    elif _strip_output_dir(actual_config) != _strip_output_dir(expected_config):
        issues.append(
            _issue(path, run_key, "incompatible_record", "resolved_config mismatch")
        )

    result = record.get("result")
    if not isinstance(result, dict):
        issues.append(_issue(path, run_key, "incompatible_record", "result object"))
        return issues

    issues.extend(_validate_result_payload(result, expected_config, path, run_key))
    return issues


def _validate_result_payload(
    result: dict[str, object],
    expected_config: dict[str, Any],
    path: Path,
    run_key: str | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if result.get("schema_version") != COMPACT_RECORD_SCHEMA_VERSION:
        issues.append(_issue(path, run_key, "incompatible_record", "schema_version"))

    for field in (
        "actions_by_round",
        "rewards_by_round",
        "agent_states",
        "attack_diagnostics",
        "aggregation_diagnostics",
    ):
        if field in result:
            issues.append(
                _issue(path, run_key, "incompatible_record", f"raw field {field}")
            )

    payload_policy = result.get("payload_policy")
    if not isinstance(payload_policy, dict):
        issues.append(_issue(path, run_key, "incompatible_record", "payload_policy"))
    else:
        for field in (
            "raw_actions_stored",
            "raw_rewards_stored",
            "agent_states_stored",
            "attack_diagnostics_stored",
            "aggregation_diagnostics_stored",
        ):
            if payload_policy.get(field) is not False:
                issues.append(_issue(path, run_key, "incompatible_record", field))

    identifiers = result.get("identifiers")
    if isinstance(identifiers, dict):
        expected_horizon = expected_config["experiment"]["horizon"]
        expected_agents = expected_config["population"]["agents"]
        expected_seed = expected_config["experiment"]["seeds"][0]
        expected_algorithm = expected_config["algorithm"]["name"]
        expected_identifiers = {
            "seed": expected_seed,
            "horizon": expected_horizon,
            "num_agents": expected_agents,
            "algorithm": expected_algorithm,
        }
        for key, expected_value in expected_identifiers.items():
            if identifiers.get(key) != expected_value:
                issues.append(
                    _issue(path, run_key, "incompatible_record", f"identifier {key}")
                )
    else:
        issues.append(_issue(path, run_key, "incompatible_record", "identifiers"))

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        issues.append(_issue(path, run_key, "incompatible_record", "metrics"))
    else:
        issues.extend(_validate_metrics(metrics, result, path, run_key))

    curves = result.get("curves")
    if not isinstance(curves, dict):
        issues.append(_issue(path, run_key, "incompatible_record", "curves"))
    else:
        horizon = expected_config["experiment"]["horizon"]
        issues.extend(_validate_curves(curves, payload_policy, horizon, path, run_key))

    return issues


def _validate_metrics(
    metrics: dict[str, object],
    result: dict[str, object],
    path: Path,
    run_key: str | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_metrics = (
        "total_population_regret",
        "mean_per_agent_regret",
        "median_honest_regret",
        "worst_decile_honest_regret",
        "max_honest_regret",
        "per_agent_final_regret",
        "recovery",
        "best_arm",
        "preferred_arms",
        "best_arm_identification_rate",
        "communication",
        "aggregation_summary",
    )
    for field in required_metrics:
        if field not in metrics:
            issues.append(
                _issue(path, run_key, "incompatible_record", f"metric {field}")
            )
    for field in (
        "total_population_regret",
        "mean_per_agent_regret",
        "median_honest_regret",
        "worst_decile_honest_regret",
        "max_honest_regret",
        "best_arm_identification_rate",
    ):
        if field in metrics and not _is_finite_number(metrics[field]):
            issues.append(
                _issue(path, run_key, "incompatible_record", f"numeric {field}")
            )

    per_agent = metrics.get("per_agent_final_regret")
    node_sets = result.get("node_sets")
    honest_nodes = (
        node_sets.get("honest_nodes") if isinstance(node_sets, dict) else None
    )
    if not isinstance(per_agent, list) or not all(
        _is_finite_number(value) for value in per_agent
    ):
        issues.append(
            _issue(path, run_key, "incompatible_record", "per_agent_final_regret")
        )
    elif isinstance(honest_nodes, list) and len(per_agent) != len(honest_nodes):
        issues.append(
            _issue(
                path,
                run_key,
                "incompatible_record",
                "per-agent regret length",
            )
        )

    if not isinstance(metrics.get("communication"), dict):
        issues.append(_issue(path, run_key, "incompatible_record", "communication"))
    if not isinstance(metrics.get("aggregation_summary"), dict):
        issues.append(
            _issue(path, run_key, "incompatible_record", "aggregation_summary")
        )
    return issues


def _validate_curves(
    curves: dict[str, object],
    payload_policy: object,
    horizon: int,
    path: Path,
    run_key: str | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rounds = curves.get("rounds")
    mean_regret = curves.get("mean_regret")
    total_regret = curves.get("total_regret")
    if not isinstance(rounds, list) or not rounds:
        return [_issue(path, run_key, "incompatible_record", "curve rounds")]
    if not isinstance(mean_regret, list) or not isinstance(total_regret, list):
        return [_issue(path, run_key, "incompatible_record", "curve values")]
    if len(rounds) != len(mean_regret) or len(rounds) != len(total_regret):
        issues.append(_issue(path, run_key, "incompatible_record", "curve lengths"))
    if rounds[0] != 1 or rounds[-1] != horizon:
        issues.append(_issue(path, run_key, "incompatible_record", "curve endpoints"))
    if any(not isinstance(value, int) for value in rounds):
        issues.append(_issue(path, run_key, "incompatible_record", "curve round type"))
    if any(left >= right for left, right in zip(rounds, rounds[1:], strict=False)):
        issues.append(_issue(path, run_key, "incompatible_record", "curve order"))
    for field_name, values in (
        ("mean_regret", mean_regret),
        ("total_regret", total_regret),
    ):
        if not all(_is_finite_number(value) for value in values):
            issues.append(
                _issue(path, run_key, "incompatible_record", f"curve {field_name}")
            )
        if any(left > right for left, right in zip(values, values[1:], strict=False)):
            issues.append(
                _issue(
                    path,
                    run_key,
                    "incompatible_record",
                    f"nonmonotonic {field_name}",
                )
            )

    if isinstance(payload_policy, dict):
        sampling = payload_policy.get("curve_sampling")
        if not isinstance(sampling, dict):
            issues.append(
                _issue(path, run_key, "incompatible_record", "curve_sampling")
            )
        elif sampling.get("stored_points") != len(rounds):
            issues.append(
                _issue(path, run_key, "incompatible_record", "stored_points")
            )
    return issues


def _strip_output_dir(config: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(config))
    experiment = copied.get("experiment")
    if isinstance(experiment, dict):
        experiment.pop("output_dir", None)
    return copied


def _claimed_run_key(record: dict[str, object]) -> str | None:
    planned = record.get("planned_run")
    if not isinstance(planned, dict):
        return None
    run_key = planned.get("run_key")
    return run_key if isinstance(run_key, str) else None


def _issue(
    path: Path,
    run_key: str | None,
    category: str,
    message: str,
) -> ValidationIssue:
    return ValidationIssue(
        category=category,
        path=str(path),
        run_key=run_key,
        message=message,
    )


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _count_issues(issues: list[ValidationIssue], category: str) -> int:
    return sum(1 for issue in issues if issue.category == category)


def _load_manifest(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a JSON object")
    return loaded


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _print_summary(
    report: dict[str, object],
    report_path: Path,
    *,
    max_issues: int,
) -> None:
    counts = report["counts"]
    if not isinstance(counts, dict):
        raise TypeError("report counts must be a dictionary")
    print(f"validation_status={report['status']}")
    print(f"expected_runs={report['expected_runs']}")
    print(f"completed_records={report['completed_records']}")
    print(f"valid_completed_runs={report['valid_completed_runs']}")
    print(f"failed_records={report['failed_records']}")
    print(f"missing_records={counts['missing_records']}")
    print(f"incomplete_expected_runs={counts['incomplete_expected_runs']}")
    print(f"duplicate_run_keys={counts['duplicate_run_keys']}")
    print(f"unexpected_files={counts['unexpected_files']}")
    print(f"incompatible_records={counts['incompatible_records']}")
    print(f"read_errors={counts['read_errors']}")
    print(f"report={report_path}")
    issues = report["issues"]
    if isinstance(issues, list) and issues:
        for issue in issues[:max_issues]:
            if not isinstance(issue, dict):
                continue
            print(
                "issue="
                f"{issue.get('category')}|"
                f"{issue.get('run_key')}|"
                f"{issue.get('path')}|"
                f"{issue.get('message')}",
            )
        if len(issues) > max_issues:
            print(f"issue_remaining={len(issues) - max_issues}")


if __name__ == "__main__":
    raise SystemExit(main())
