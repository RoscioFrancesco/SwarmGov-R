from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import copyfile

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_validate_config_cli_accepts_smoke_config() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swarmgov",
            "validate-config",
            "--config",
            "configs/smoke.yaml",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '"name": "smoke-one-hop-weighted-pooling-clean"' in result.stdout
    assert "configuration error" not in result.stderr


def test_run_command_executes_clean_multi_agent_smoke(tmp_path: Path) -> None:
    config_path = tmp_path / "smoke.yaml"
    copyfile(REPO_ROOT / "configs" / "smoke.yaml", config_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "swarmgov",
            "run",
            "--config",
            str(config_path),
            "--output-dir",
            str(tmp_path / "results"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '"algorithm": "one_hop_weighted_pooling_ucb1"' in result.stdout
    assert '"mean_per_agent_regret"' in result.stdout
    assert list((tmp_path / "results").glob("*.json"))
