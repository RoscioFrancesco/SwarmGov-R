from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "experiments" / "manifests" / "confirmatory_m8_manifest.json"


def test_confirmatory_manifest_counts_match_declared_matrix() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    seed_count = manifest["run_seeds"]["count"]

    primary_count = sum(
        _group_run_count(group, seed_count)
        for group in manifest["primary_run_groups"]
    )
    sensitivity_count = sum(
        _group_run_count(group, seed_count)
        for group in manifest["sensitivity_run_groups"]
    )

    assert seed_count == 100
    assert manifest["run_seeds"]["start"] == 1000
    assert manifest["run_seeds"]["end"] == 1099
    assert primary_count == manifest["run_count_estimate"]["primary_planned_runs"]
    assert (
        sensitivity_count
        == manifest["run_count_estimate"]["sensitivity_planned_runs"]
    )
    assert (
        primary_count + sensitivity_count
        == manifest["run_count_estimate"]["total_planned_runs"]
    )


def test_confirmatory_manifest_excludes_invalid_baseline_combinations() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_groups = [
        *manifest["primary_run_groups"],
        *manifest["sensitivity_run_groups"],
    ]

    for group in all_groups:
        if group["topology_mode"] == "dynamic":
            assert "complete" not in group["topologies"]
            assert "independent" not in group["algorithms"]
            assert "centralized_clean_reference" not in group["algorithms"]
        if group["attack"]["strategy"] != "no_attack":
            assert "centralized_clean_reference" not in group["algorithms"]
            assert group["attack"]["target_arm"] == 3
            assert group["attack"]["byzantine_fraction"] == 0.2

    assert manifest["confirmatory_results_present"] is True
    assert manifest["status"] == "completed_primary"
    assert manifest["completed_primary_results"]["completed_runs"] == 5700
    assert manifest["completed_primary_results"]["failed_runs"] == 0


def _group_run_count(group: dict[str, object], seed_count: int) -> int:
    attack = group["attack"]
    placement_multiplier = len(attack.get("placements", [attack.get("placement")]))
    return (
        len(group["topologies"])
        * len(group["algorithms"])
        * placement_multiplier
        * seed_count
    )
