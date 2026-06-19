#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _common import REPO_ROOT, fail, ok, require


SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.path_policy import AbyssMachinePathPolicy  # noqa: E402
from abyss_machine.typing_nervous_policy import TypingNervousPolicy  # noqa: E402


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
    "typing_root": str(cli.TYPING_ROOT),
    "typing_policy": str(cli.TYPING_POLICY_PATH),
    "typing_browser_extension": str(cli.TYPING_BROWSER_EXTENSION_ROOT),
    "typing_browser_host": str(cli.TYPING_BROWSER_NATIVE_HOST_PATH),
    "typing_browser_webextension_tmp": str(cli.TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP_ROOT),
    "typing_browser_atspi_tmp": str(cli.TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT),
    "typing_npm_cache": str(cli.TYPING_BROWSER_WEBEXTENSION_NPM_CACHE),
    "typing_codex_sessions": str(cli.TYPING_CODEX_SESSIONS_ROOT),
    "typing_user_systemd": str(cli.TYPING_USER_SYSTEMD_DIR),
    "typing_refresh_service": cli.TYPING_NERVOUS_REFRESH_SERVICE,
    "nervous_root": str(cli.NERVOUS_ROOT),
    "nervous_config": str(cli.NERVOUS_CONFIG_DIR),
    "nervous_private_capture": str(cli.NERVOUS_PRIVATE_CAPTURE_ROOT),
    "nervous_browser_tmp": str(cli.NERVOUS_BROWSER_TMP_ROOT),
    "nervous_index_db": str(cli.NERVOUS_SEARCH_INDEX_DB_PATH),
    "nervous_semantic_db": str(cli.NERVOUS_SEMANTIC_INDEX_DB_PATH),
    "nervous_chronicle_service": cli.NERVOUS_PASSIVE_CHRONICLE_SERVICE,
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

    path_policy = AbyssMachinePathPolicy.from_values(
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
        environ={},
    )
    constants = TypingNervousPolicy.from_path_policy(path_policy, environ={}).as_cli_constants()
    expected_paths = {
        "TYPING_ROOT": "/tmp/state/typing",
        "TYPING_POLICY_PATH": "/tmp/etc/typing-policy.json",
        "TYPING_BROWSER_EXTENSION_ROOT": "/tmp/srv/tools/typing/firefox-extension",
        "TYPING_BROWSER_NATIVE_HOST_PATH": "/tmp/srv/tools/typing/browser-native-host",
        "TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP_ROOT": "/tmp/tmp/typing-browser-webextension-selftest",
        "TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT": "/tmp/tmp/typing-browser-atspi-selftest",
        "TYPING_BROWSER_WEBEXTENSION_NPM_CACHE": "/tmp/cache/npm",
        "TYPING_CODEX_SESSIONS_ROOT": "/tmp/agent/.codex/sessions",
        "TYPING_BROWSER_NATIVE_HOST_USER_MANIFEST": (
            "/tmp/agent/.mozilla/native-messaging-hosts/org.abyss_machine.typing_intake.json"
        ),
        "TYPING_USER_SYSTEMD_DIR": "/tmp/agent/.config/systemd/user",
        "NERVOUS_ROOT": "/tmp/state/nervous",
        "NERVOUS_CONFIG_DIR": "/tmp/etc/nervous",
        "NERVOUS_PRIVATE_CAPTURE_ROOT": "/tmp/storage/nervous/captures",
        "NERVOUS_BROWSER_TMP_ROOT": "/tmp/tmp/nervous/browser-history",
        "NERVOUS_SEARCH_INDEX_ROOT": "/tmp/storage/nervous/indexes",
        "NERVOUS_SEARCH_INDEX_DB_PATH": "/tmp/storage/nervous/indexes/sqlite/nervous.db",
        "NERVOUS_SEMANTIC_INDEX_ROOT": "/tmp/storage/nervous/indexes/semantic",
        "NERVOUS_SEMANTIC_INDEX_DB_PATH": "/tmp/storage/nervous/indexes/semantic/semantic.db",
        "NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH": (
            "/tmp/agent/.config/systemd/user/"
            "abyss-nervous-passive-chronicle.service.d/50-derived-refresh.conf"
        ),
    }
    for key, expected in expected_paths.items():
        require(str(constants.get(key)) == expected, f"policy constant mismatch for {key}", failures)

    require(
        constants.get("TYPING_NERVOUS_REFRESH_SERVICE") == "abyss-machine-typing-nervous-refresh.service",
        "typing nervous refresh service name mismatch",
        failures,
    )
    require(
        constants.get("NERVOUS_PASSIVE_CHRONICLE_SERVICE") == "abyss-nervous-passive-chronicle.service",
        "nervous passive chronicle service name mismatch",
        failures,
    )

    override_policy = TypingNervousPolicy.from_path_policy(
        path_policy,
        environ={
            "ABYSS_MACHINE_TYPING_ROOT": "/override/typing",
            "ABYSS_MACHINE_NERVOUS_ROOT": "/override/nervous",
            "ABYSS_MACHINE_USER_SYSTEMD_DIR": "/override/systemd/user",
            "ABYSS_MACHINE_NERVOUS_INDEX_DB": "/override/nervous.db",
            "ABYSS_MACHINE_TYPING_BROWSER_WEBEXTENSION_NPM_CACHE": "/override/npm",
        },
    ).as_cli_constants()
    require(str(override_policy["TYPING_ROOT"]) == "/override/typing", "typing root override mismatch", failures)
    require(str(override_policy["NERVOUS_ROOT"]) == "/override/nervous", "nervous root override mismatch", failures)
    require(
        str(override_policy["TYPING_USER_SYSTEMD_DIR"]) == "/override/systemd/user",
        "user systemd override mismatch",
        failures,
    )
    require(
        str(override_policy["NERVOUS_SEARCH_INDEX_DB_PATH"]) == "/override/nervous.db",
        "nervous db override mismatch",
        failures,
    )
    require(
        str(override_policy["TYPING_BROWSER_WEBEXTENSION_NPM_CACHE"]) == "/override/npm",
        "npm cache override mismatch",
        failures,
    )

    try:
        cli_constants = cli_constants_with_env()
    except RuntimeError as exc:
        failures.append(str(exc))
    else:
        expected_cli = {
            "typing_root": "/tmp/abyss/state/typing",
            "typing_policy": "/tmp/abyss/etc/typing-policy.json",
            "typing_browser_extension": "/tmp/abyss/srv/tools/typing/firefox-extension",
            "typing_browser_host": "/tmp/abyss/srv/tools/typing/browser-native-host",
            "typing_browser_webextension_tmp": "/tmp/abyss/tmp/typing-browser-webextension-selftest",
            "typing_browser_atspi_tmp": "/tmp/abyss/tmp/typing-browser-atspi-selftest",
            "typing_npm_cache": "/tmp/abyss/cache/npm",
            "typing_codex_sessions": "/tmp/abyss-user/.codex/sessions",
            "typing_user_systemd": "/tmp/abyss-user/.config/systemd/user",
            "typing_refresh_service": "abyss-machine-typing-nervous-refresh.service",
            "nervous_root": "/tmp/abyss/state/nervous",
            "nervous_config": "/tmp/abyss/etc/nervous",
            "nervous_private_capture": "/tmp/abyss/storage/nervous/captures",
            "nervous_browser_tmp": "/tmp/abyss/tmp/nervous/browser-history",
            "nervous_index_db": "/tmp/abyss/storage/nervous/indexes/sqlite/nervous.db",
            "nervous_semantic_db": "/tmp/abyss/storage/nervous/indexes/semantic/semantic.db",
            "nervous_chronicle_service": "abyss-nervous-passive-chronicle.service",
        }
        for key, value in expected_cli.items():
            require(cli_constants.get(key) == value, f"CLI organ policy mismatch for {key}", failures)

    source = (REPO_ROOT / "src" / "abyss_machine" / "cli.py").read_text(encoding="utf-8")
    require(
        "TYPING_NERVOUS_POLICY = DEFAULT_TYPING_NERVOUS_POLICY" in source,
        "CLI must expose typing/nervous constants from TypingNervousPolicy",
        failures,
    )
    require(
        '"/srv/abyss-machine/tmp/typing-browser-atspi-selftest"' not in source,
        "typing tmp defaults must not be hard-coded in CLI",
        failures,
    )

    if failures:
        return fail("typing/nervous policy validation failed", failures)
    return ok("typing/nervous policy validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
