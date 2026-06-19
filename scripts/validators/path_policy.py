#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys

from _common import REPO_ROOT, fail, ok, require


SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.path_policy import AbyssMachinePathPolicy  # noqa: E402


def cli_constants_with_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(SRC_ROOT),
            "ABYSS_USER": "agent",
            "ABYSS_USER_HOME": "/tmp/abyss-user",
            "ABYSS_MACHINE_ETC_ROOT": "/tmp/abyss/etc",
            "ABYSS_MACHINE_STATE_ROOT": "/tmp/abyss/state",
            "ABYSS_MACHINE_ROOT": "/tmp/abyss/srv",
            "ABYSS_MACHINE_RUN_ROOT": "/tmp/abyss/run",
            "ABYSS_MACHINE_CACHE_ROOT": "/tmp/abyss/cache",
            "ABYSS_MACHINE_RUNTIME_ROOT": "/tmp/abyss/runtimes",
            "ABYSS_MACHINE_STORAGE_ROOT": "/tmp/abyss/storage",
            "ABYSS_MACHINE_TMP_ROOT": "/tmp/abyss/tmp",
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
    "cache": str(cli.ABYSS_MACHINE_CACHE_ROOT),
    "runtimes": str(cli.ABYSS_MACHINE_RUNTIME_ROOT),
    "storage": str(cli.ABYSS_MACHINE_STORAGE_ROOT),
    "tmp": str(cli.ABYSS_MACHINE_TMP_ROOT),
    "typing_policy": str(cli.TYPING_POLICY_PATH),
    "nervous_root": str(cli.NERVOUS_ROOT),
}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "CLI import failed")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("CLI import payload must be an object")
    return {str(key): str(value) for key, value in payload.items()}


def main() -> int:
    failures: list[str] = []

    defaults = AbyssMachinePathPolicy.from_values(
        user="agent",
        home="/home/agent",
        etc_root="/etc/abyss-machine",
        state_root="/var/lib/abyss-machine",
        srv_root="/srv/abyss-machine",
        run_root="/run/abyss-machine",
        vault_mount="/abyss",
    )
    require(defaults.render_vars()["ABYSS_MACHINE_ETC"] == "/etc/abyss-machine", "default etc root mismatch", failures)
    require(defaults.render_vars()["ABYSS_MACHINE_STATE"] == "/var/lib/abyss-machine", "default state root mismatch", failures)
    require(defaults.render_vars()["ABYSS_MACHINE_SRV"] == "/srv/abyss-machine", "default srv root mismatch", failures)
    require(defaults.render_vars()["ABYSS_MACHINE_RUN"] == "/run/abyss-machine", "default run root mismatch", failures)
    require(defaults.render_vars()["ABYSS_BACKUP_ROOT"] == "/abyss/Backups", "default backup root mismatch", failures)

    install_roots = {str(path) for path in defaults.install_roots}
    for path in (
        "/etc/abyss-machine",
        "/var/lib/abyss-machine",
        "/srv/abyss-machine",
        "/srv/abyss-machine/cache",
        "/srv/abyss-machine/runtimes",
        "/srv/abyss-machine/storage",
        "/srv/abyss-machine/tmp",
    ):
        require(path in install_roots, f"install roots missing {path}", failures)

    custom = AbyssMachinePathPolicy.from_values(
        user="agent",
        home="/tmp/agent",
        etc_root="/tmp/etc",
        state_root="/tmp/state",
        srv_root="/tmp/srv",
        run_root="/tmp/run",
        cache_root="/tmp/cache",
        runtimes_root="/tmp/runtimes",
        storage_root="/tmp/storage",
        tmp_root="/tmp/tmp",
    )
    require(str(custom.cache_root) == "/tmp/cache", "custom cache root mismatch", failures)
    require(str(custom.runtimes_root) == "/tmp/runtimes", "custom runtimes root mismatch", failures)
    require(str(custom.storage_root) == "/tmp/storage", "custom storage root mismatch", failures)
    require(str(custom.tmp_root) == "/tmp/tmp", "custom tmp root mismatch", failures)

    bootstrap_source = (REPO_ROOT / "scripts" / "abyss-machine-bootstrap").read_text(encoding="utf-8")
    cli_source = (REPO_ROOT / "src" / "abyss_machine" / "cli.py").read_text(encoding="utf-8")
    require("AbyssMachinePathPolicy" in bootstrap_source, "bootstrap must use AbyssMachinePathPolicy", failures)
    require("DEFAULT_PATH_POLICY" in bootstrap_source, "bootstrap must use DEFAULT_PATH_POLICY defaults", failures)
    require("PATH_POLICY = DEFAULT_PATH_POLICY" in cli_source, "CLI must expose PATH_POLICY from DEFAULT_PATH_POLICY", failures)

    try:
        constants = cli_constants_with_env()
    except RuntimeError as exc:
        failures.append(str(exc))
    else:
        expected = {
            "manifest": "/tmp/abyss/etc/bridge.json",
            "state": "/tmp/abyss/state",
            "run": "/tmp/abyss/run",
            "srv": "/tmp/abyss/srv",
            "cache": "/tmp/abyss/cache",
            "runtimes": "/tmp/abyss/runtimes",
            "storage": "/tmp/abyss/storage",
            "tmp": "/tmp/abyss/tmp",
            "typing_policy": "/tmp/abyss/etc/typing-policy.json",
            "nervous_root": "/tmp/abyss/state/nervous",
        }
        for key, value in expected.items():
            require(constants.get(key) == value, f"CLI env override mismatch for {key}: {constants.get(key)!r}", failures)

    if failures:
        return fail("path policy validation failed", failures)
    return ok("path policy validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
