from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.path_policy import AbyssMachinePathPolicy
from abyss_machine.typing_nervous_policy import TypingNervousPolicy


def test_typing_nervous_policy_derives_organ_roots_from_path_policy() -> None:
    path_policy = AbyssMachinePathPolicy.from_values(
        user="agent",
        home="/tmp/agent",
        etc_root="/tmp/etc",
        state_root="/tmp/state",
        srv_root="/tmp/srv",
        run_root="/tmp/run",
        cache_root="/tmp/cache",
        storage_root="/tmp/storage",
        tmp_root="/tmp/tmp",
        environ={},
    )

    constants = TypingNervousPolicy.from_path_policy(path_policy, environ={}).as_cli_constants()

    assert constants["TYPING_ROOT"] == Path("/tmp/state/typing")
    assert constants["TYPING_POLICY_PATH"] == Path("/tmp/etc/typing-policy.json")
    assert constants["TYPING_BROWSER_EXTENSION_ROOT"] == Path("/tmp/srv/tools/typing/firefox-extension")
    assert constants["TYPING_BROWSER_NATIVE_HOST_PATH"] == Path("/tmp/srv/tools/typing/browser-native-host")
    assert constants["TYPING_BROWSER_WEBEXTENSION_SELFTEST_TMP_ROOT"] == Path(
        "/tmp/tmp/typing-browser-webextension-selftest"
    )
    assert constants["TYPING_BROWSER_WEBEXTENSION_NPM_CACHE"] == Path("/tmp/cache/npm")
    assert constants["TYPING_CODEX_SESSIONS_ROOT"] == Path("/tmp/agent/.codex/sessions")
    assert constants["NERVOUS_ROOT"] == Path("/tmp/state/nervous")
    assert constants["NERVOUS_CONFIG_DIR"] == Path("/tmp/etc/nervous")
    assert constants["NERVOUS_PRIVATE_CAPTURE_ROOT"] == Path("/tmp/storage/nervous/captures")
    assert constants["NERVOUS_SEARCH_INDEX_DB_PATH"] == Path("/tmp/storage/nervous/indexes/sqlite/nervous.db")
    assert constants["NERVOUS_SEMANTIC_INDEX_DB_PATH"] == Path("/tmp/storage/nervous/indexes/semantic/semantic.db")
    assert constants["TYPING_NERVOUS_REFRESH_SERVICE"] == "abyss-machine-typing-nervous-refresh.service"
    assert constants["NERVOUS_PASSIVE_CHRONICLE_SERVICE"] == "abyss-nervous-passive-chronicle.service"


def test_typing_nervous_policy_honors_subsystem_overrides() -> None:
    path_policy = AbyssMachinePathPolicy.from_values(
        user="agent",
        home="/tmp/agent",
        state_root="/tmp/state",
        srv_root="/tmp/srv",
        storage_root="/tmp/storage",
        tmp_root="/tmp/tmp",
        environ={},
    )

    constants = TypingNervousPolicy.from_path_policy(
        path_policy,
        environ={
            "ABYSS_MACHINE_TYPING_ROOT": "/override/typing",
            "ABYSS_MACHINE_NERVOUS_ROOT": "/override/nervous",
            "ABYSS_MACHINE_USER_SYSTEMD_DIR": "/override/systemd/user",
            "ABYSS_MACHINE_NERVOUS_INDEX_DB": "/override/nervous.db",
            "ABYSS_MACHINE_TYPING_BROWSER_WEBEXTENSION_NPM_CACHE": "/override/npm",
        },
    ).as_cli_constants()

    assert constants["TYPING_ROOT"] == Path("/override/typing")
    assert constants["NERVOUS_ROOT"] == Path("/override/nervous")
    assert constants["TYPING_USER_SYSTEMD_DIR"] == Path("/override/systemd/user")
    assert constants["NERVOUS_SEARCH_INDEX_DB_PATH"] == Path("/override/nervous.db")
    assert constants["TYPING_BROWSER_WEBEXTENSION_NPM_CACHE"] == Path("/override/npm")


def test_cli_typing_nervous_constants_follow_environment_policy() -> None:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(SRC_ROOT),
            "ABYSS_USER": "agent",
            "ABYSS_USER_HOME": "/tmp/agent",
            "ABYSS_MACHINE_ETC_ROOT": "/tmp/cli/etc",
            "ABYSS_MACHINE_STATE_ROOT": "/tmp/cli/state",
            "ABYSS_MACHINE_ROOT": "/tmp/cli/srv",
            "ABYSS_MACHINE_CACHE_ROOT": "/tmp/cli/cache",
            "ABYSS_MACHINE_STORAGE_ROOT": "/tmp/cli/storage",
            "ABYSS_MACHINE_TMP_ROOT": "/tmp/cli/tmp",
        }
    )
    code = """
import json
from abyss_machine import cli
print(json.dumps({
    "typing_root": str(cli.TYPING_ROOT),
    "typing_browser_extension": str(cli.TYPING_BROWSER_EXTENSION_ROOT),
    "typing_browser_tmp": str(cli.TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT),
    "typing_npm_cache": str(cli.TYPING_BROWSER_WEBEXTENSION_NPM_CACHE),
    "nervous_root": str(cli.NERVOUS_ROOT),
    "nervous_capture": str(cli.NERVOUS_PRIVATE_CAPTURE_ROOT),
    "nervous_index_db": str(cli.NERVOUS_SEARCH_INDEX_DB_PATH),
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
    assert json.loads(result.stdout) == {
        "typing_root": "/tmp/cli/state/typing",
        "typing_browser_extension": "/tmp/cli/srv/tools/typing/firefox-extension",
        "typing_browser_tmp": "/tmp/cli/tmp/typing-browser-atspi-selftest",
        "typing_npm_cache": "/tmp/cli/cache/npm",
        "nervous_root": "/tmp/cli/state/nervous",
        "nervous_capture": "/tmp/cli/storage/nervous/captures",
        "nervous_index_db": "/tmp/cli/storage/nervous/indexes/sqlite/nervous.db",
    }
