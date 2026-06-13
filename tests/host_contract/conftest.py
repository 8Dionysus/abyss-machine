from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ABYSS_MACHINE_BIN = Path(os.environ.get("ABYSS_MACHINE_BIN", "/usr/local/libexec/abyss-machine"))


@pytest.fixture(scope="session")
def abyss_machine_module() -> Any:
    loader = importlib.machinery.SourceFileLoader("abyss_machine_under_test", str(ABYSS_MACHINE_BIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"unable to load spec for {ABYSS_MACHINE_BIN}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def run_abyss_machine() -> Any:
    def _run(*args: str, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        return subprocess.run(
            ["abyss-machine", *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )

    return _run


def parse_json_stdout(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout is not JSON; returncode={result.returncode}, stderr={result.stderr[-500:]}, stdout={result.stdout[-500:]}"
        ) from exc
    if not isinstance(payload, dict):
        raise AssertionError(f"stdout JSON is not an object: {type(payload).__name__}")
    return payload
