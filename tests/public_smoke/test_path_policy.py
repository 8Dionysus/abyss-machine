from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "abyss-machine-bootstrap"
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.path_policy import AbyssMachinePathPolicy


def test_path_policy_renders_install_contract_roots() -> None:
    policy = AbyssMachinePathPolicy.from_values(
        user="agent",
        home="/home/agent",
        etc_root="/x/etc",
        state_root="/x/state",
        srv_root="/x/srv",
        run_root="/x/run",
        vault_mount="/x/vault",
    )

    assert policy.render_vars()["ABYSS_MACHINE_ETC"] == "/x/etc"
    assert policy.render_vars()["ABYSS_MACHINE_STATE"] == "/x/state"
    assert policy.render_vars()["ABYSS_MACHINE_SRV"] == "/x/srv"
    assert policy.render_vars()["ABYSS_MACHINE_RUN"] == "/x/run"
    assert policy.render_vars()["ABYSS_BACKUP_ROOT"] == "/x/vault/Backups"
    assert policy.cli_defaults()["systemd_user_dir"] == "/home/agent/.config/systemd/user"

    assert {str(path) for path in policy.install_roots} == {
        "/x/etc",
        "/x/state",
        "/x/srv",
        "/x/srv/cache",
        "/x/srv/runtimes",
        "/x/srv/storage",
        "/x/srv/tmp",
    }


def test_bootstrap_uses_path_policy_overrides() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BOOTSTRAP),
            "doctor",
            "--dry-run",
            "--user",
            "agent",
            "--home",
            "/tmp/agent",
            "--etc-root",
            "/tmp/agent/etc",
            "--state-root",
            "/tmp/agent/state",
            "--srv-root",
            "/tmp/agent/srv",
            "--run-root",
            "/tmp/agent/run",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["vars"]["ABYSS_USER"] == "agent"
    assert payload["vars"]["ABYSS_USER_HOME"] == "/tmp/agent"
    assert payload["vars"]["ABYSS_MACHINE_ETC"] == "/tmp/agent/etc"
    assert payload["vars"]["ABYSS_MACHINE_STATE"] == "/tmp/agent/state"
    assert payload["vars"]["ABYSS_MACHINE_SRV"] == "/tmp/agent/srv"
    assert payload["vars"]["ABYSS_MACHINE_RUN"] == "/tmp/agent/run"


def test_cli_core_paths_follow_environment_policy() -> None:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "ABYSS_MACHINE_ETC_ROOT": "/tmp/cli/etc",
            "ABYSS_MACHINE_STATE_ROOT": "/tmp/cli/state",
            "ABYSS_MACHINE_ROOT": "/tmp/cli/srv",
            "ABYSS_MACHINE_RUN_ROOT": "/tmp/cli/run",
        }
    )
    code = """
import json
from abyss_machine import cli
print(json.dumps({
    "manifest": str(cli.MANIFEST_PATH),
    "state": str(cli.STATE_DIR),
    "run": str(cli.RUNTIME_DIR),
    "srv": str(cli.ABYSS_MACHINE_ROOT),
    "typing_policy": str(cli.TYPING_POLICY_PATH),
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "manifest": "/tmp/cli/etc/bridge.json",
        "state": "/tmp/cli/state",
        "run": "/tmp/cli/run",
        "srv": "/tmp/cli/srv",
        "typing_policy": "/tmp/cli/etc/typing-policy.json",
    }
