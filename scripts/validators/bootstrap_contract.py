#!/usr/bin/env python3
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, fail, load_json, ok, rel, require


BOOTSTRAP = REPO_ROOT / "scripts" / "abyss-machine-bootstrap"
PROFILE_MANIFEST = REPO_ROOT / "manifests" / "bootstrap_profiles.manifest.json"


def load_bootstrap_module() -> Any:
    loader = importlib.machinery.SourceFileLoader("abyss_machine_bootstrap_under_test", str(BOOTSTRAP))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("unable to load bootstrap module spec")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run_bootstrap(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP), *args, "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"bootstrap {' '.join(args)} failed: {result.stderr[-1000:]}")
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("bootstrap output must be a JSON object")
    return payload


def main() -> int:
    failures: list[str] = []
    manifest = load_json(PROFILE_MANIFEST)
    module = load_bootstrap_module()
    expected_profiles = manifest.get("profiles")
    actual_profiles = getattr(module, "PROFILE_UNITS", None)
    if not isinstance(expected_profiles, dict) or not isinstance(actual_profiles, dict):
        return fail("bootstrap profile manifests must be objects")
    require(actual_profiles == expected_profiles, "bootstrap PROFILE_UNITS must match manifests/bootstrap_profiles.manifest.json", failures)

    for profile, scopes in expected_profiles.items():
        if not isinstance(scopes, dict):
            failures.append(f"profile {profile} must be an object")
            continue
        for scope, units in scopes.items():
            root = REPO_ROOT / "systemd" / str(scope)
            require(root.is_dir(), f"profile {profile} references missing systemd scope root: {rel(root)}", failures)
            if not isinstance(units, list):
                failures.append(f"profile {profile} scope {scope} must list units")
                continue
            for unit in units:
                path = root / str(unit)
                require(path.is_file(), f"profile {profile} references missing unit: {rel(path)}", failures)

    doctor = run_bootstrap("doctor", "--dry-run")
    require(doctor.get("ok") is True, "doctor dry-run must be ok", failures)
    checks = doctor.get("checks") if isinstance(doctor.get("checks"), dict) else {}
    for key in [
        "config_templates_exist",
        "systemd_templates_exist",
        "cli_source_exists",
        "package_source_exists",
        "artifact_policy_exists",
        "contract_abi_exists",
    ]:
        require(checks.get(key) is True, f"doctor check {key} must be true", failures)

    render = run_bootstrap("render", "--profile", "linux-systemd-core", "--dry-run")
    require(render.get("ok") is True and render.get("dry_run") is True, "render dry-run must be ok and dry_run", failures)
    render_actions = render.get("actions") if isinstance(render.get("actions"), list) else []
    require(any("config-templates/etc/abyss-machine" in str(item.get("source", "")) for item in render_actions if isinstance(item, dict)), "render actions must use config-templates source root", failures)

    install = run_bootstrap(
        "install",
        "--profile",
        "linux-systemd-core",
        "--dry-run",
        "--skip-artifact-trust-gate",
    )
    require(install.get("ok") is True and install.get("dry_run") is True, "install dry-run must be ok and dry_run", failures)
    install_actions = install.get("actions") if isinstance(install.get("actions"), list) else []
    require(any("/systemd/system/" in str(item.get("source", "")) for item in install_actions if isinstance(item, dict)), "install actions must include systemd/system sources", failures)
    require(any("/systemd/user/" in str(item.get("source", "")) for item in install_actions if isinstance(item, dict)), "install actions must include systemd/user sources", failures)
    require(any(item.get("action") == "install_cli" and item.get("package_target") for item in install_actions if isinstance(item, dict)), "install actions must include CLI package modules", failures)
    require(any(item.get("action") == "install_public_seed" and item.get("target") for item in install_actions if isinstance(item, dict)), "install actions must include public seed share projection", failures)

    if failures:
        return fail("bootstrap contract validation failed", failures)
    return ok("bootstrap contract validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
