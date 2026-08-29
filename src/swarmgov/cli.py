"""Command-line utilities for the SwarmGov-R foundation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from swarmgov.config import ConfigError, load_config
from swarmgov.simulation import SimulationError, run_configured_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swarmgov")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-config",
        help="Validate a SwarmGov-R YAML configuration.",
    )
    validate.add_argument("--config", required=True, help="Path to a YAML config file.")

    run = subparsers.add_parser(
        "run",
        help="Run the implemented experiment for a SwarmGov-R configuration.",
    )
    run.add_argument("--config", required=True, help="Path to a YAML config file.")
    run.add_argument(
        "--output-dir",
        help="Optional output directory override for the result JSON.",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved configuration without running an experiment.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "validate-config":
            config = load_config(args.config)
            print(json.dumps(config.resolved_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            config = load_config(args.config)
            if args.dry_run:
                print(json.dumps(config.resolved_dict(), indent=2, sort_keys=True))
                return 0
            result = run_configured_experiment(config, output_dir=args.output_dir)
            print(json.dumps(result.to_record(), indent=2, sort_keys=True))
            return 0
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 1
    except SimulationError as exc:
        print(f"simulation error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2
