#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, fail, ok


SCHEMA = "abyss_machine_first_run_installed_projection_v1"
BOOTSTRAP = REPO_ROOT / "scripts" / "abyss-machine-bootstrap"
SRC_ROOT = REPO_ROOT / "src"
PROFILE_MANIFEST = REPO_ROOT / "manifests" / "bootstrap_profiles.manifest.json"
SOURCE_PACKAGE_ROOT = SRC_ROOT / "abyss_machine"
SOURCE_PUBLIC_SEED_ROOTS = {
    "manifests": REPO_ROOT / "manifests",
    "generated": REPO_ROOT / "generated",
}
PORTABILITY_SCAN_EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
PORTABILITY_NEEDLES = {
    "operator_home_path": b"/home/" + b"dionysus",
    "current_checkout_path": str(REPO_ROOT).encode("utf-8"),
}

HELP_SURFACES: tuple[tuple[str, ...], ...] = (
    (),
    ("artifacts",),
    ("changes",),
    ("docs",),
    ("topology",),
    ("graph",),
    ("maps",),
    ("rag",),
    ("stack-bridge",),
    ("self-awareness",),
    ("storage",),
    ("typing",),
    ("nervous",),
    ("resource",),
    ("mode",),
    ("observability",),
    ("cooling",),
    ("processes",),
    ("heartbeats",),
    ("reactions",),
    ("responses",),
    ("ai",),
    ("ai", "cpu"),
)
REQUIRED_TOP_LEVEL = {
    "doctor",
    "changes",
    "docs",
    "topology",
    "graph",
    "maps",
    "rag",
    "stack-bridge",
    "self-awareness",
    "storage",
    "resource",
    "ai",
    "artifacts",
    "nervous",
    "typing",
    "dictation",
    "mode",
    "observability",
    "cooling",
    "processes",
    "heartbeats",
    "reactions",
    "responses",
}
REQUIRED_ARTIFACT_COMMANDS = {
    "build-sidecars",
    "sign",
    "verify",
    "release-check",
    "bundle-register",
    "bundle-registry",
    "registry-latest",
    "bundle-registry-upgrade",
    "evidence-promote",
    "requirements",
    "producer-profiles",
    "scenarios",
    "affected",
    "trust-gate",
    "trust-tools",
    "trust-tools-python",
    "trust-coverage",
    "update-lane",
    "update-verify",
    "update-repo-build",
    "update-repo-verify",
    "scitt-verify",
    "oci-verify",
}
REQUIRED_STORAGE_COMMANDS = {
    "status",
    "validate",
    "policy",
    "paths",
    "hooks",
    "run-hooks",
    "podman-preflight",
    "inventory",
    "pressure",
    "cleanup-plan",
    "monitor",
    "write-preflight",
    "apply",
}
REQUIRED_CHANGES_COMMANDS = {
    "status",
    "paths",
    "latest",
    "index",
    "record",
    "close",
    "preflight",
}
REQUIRED_DOCS_COMMANDS = {
    "status",
    "paths",
    "audit",
    "mesh",
    "mesh-validate",
    "decisions-index",
}
REQUIRED_TOPOLOGY_COMMANDS = {
    "status",
    "paths",
    "validate",
    "audit",
}
REQUIRED_GRAPH_COMMANDS = {
    "status",
    "query",
    "validate",
}
REQUIRED_MAPS_COMMANDS = {
    "status",
    "paths",
    "policy",
    "build",
    "query",
    "packet",
    "validate",
}
REQUIRED_RAG_COMMANDS = {
    "status",
    "paths",
    "policy",
    "trace",
    "refresh",
    "latest",
    "eval",
    "validate",
}
REQUIRED_STACK_BRIDGE_COMMANDS = {
    "status",
    "paths",
    "export",
    "latest",
    "validate",
    "observability",
    "sync-static",
}
REQUIRED_SELF_AWARENESS_COMMANDS = {
    "paths",
    "status",
    "capabilities",
    "requirements",
    "requirement-probes",
    "trace-context",
    "collect",
    "query",
    "correlate",
    "timeline",
    "spatial-graph",
    "context",
    "episodes",
    "alerts",
    "investigate",
    "replay",
    "activation-smoke",
    "brief",
    "failure-matrix",
    "working-stack",
    "coverage-audit",
    "completion-audit",
    "stack-closure-dossier",
    "probe",
    "export",
    "validate",
    "autolink",
    "cycle",
}
REQUIRED_TYPING_COMMANDS = {
    "paths",
    "policy",
    "capture-gate",
    "privacy-selftest",
    "nervous-refresh",
    "validate",
    "redact-test",
}
REQUIRED_NERVOUS_COMMANDS = {
    "paths",
    "policy",
    "sources",
    "privacy",
    "privacy-status",
    "capture-status",
    "validate",
    "redact-test",
    "index-status",
    "index-build",
    "index-validate",
    "semantic-status",
    "semantic-build",
    "semantic-maintain",
    "semantic-search",
    "semantic-eval",
    "synthesis-build",
    "synthesis-latest",
    "synthesis-validate",
}
REQUIRED_RESOURCE_COMMANDS = {
    "paths",
    "status",
    "policy",
    "plan",
    "orchestrator",
    "launch",
    "validate",
}
REQUIRED_MODE_COMMANDS = {
    "list",
    "get",
    "status",
    "paths",
    "policy",
    "plan",
    "validate",
    "set",
    "reconcile",
}
REQUIRED_OBSERVABILITY_COMMANDS = {
    "status",
    "paths",
    "latest",
    "collect",
}
REQUIRED_COOLING_COMMANDS = {
    "status",
    "paths",
    "validate",
    "recommend",
    "apply",
    "thermal-audit",
    "fan-validate",
    "fan-series",
    "tfn1-write",
    "rapl-smoothing",
}
REQUIRED_PROCESSES_COMMANDS = {
    "paths",
    "validate",
    "latest",
    "snapshot",
    "game-guard",
    "containers",
    "thermal-attribution",
    "thermal-plan",
    "desktop-compositor",
}
REQUIRED_HEARTBEATS_COMMANDS = {
    "pulse",
    "status",
    "paths",
    "validate",
}
REQUIRED_REACTIONS_COMMANDS = {
    "status",
    "paths",
    "validate",
}
REQUIRED_RESPONSES_COMMANDS = {
    "status",
    "paths",
    "validate",
}
REQUIRED_AI_COMMANDS = {
    "status",
    "paths",
    "validate",
    "devices",
    "models",
    "capabilities",
    "policy",
    "storage",
    "runtime",
    "report",
    "llm",
    "token-accounting",
    "workload",
    "cpu",
    "tts",
    "eval",
    "benchmark",
    "config",
}
REQUIRED_AI_CPU_COMMANDS = {
    "topology",
    "thermal-map",
    "route",
    "launch",
    "test",
}
CRITICAL_HELP_OPTIONS: dict[tuple[str, ...], set[str]] = {
    ("artifacts", "materialize-subjects"): {
        "--registry-dir",
        "--consumer-intent",
        "--source-repo",
        "--trust-root-mode",
        "--record-id",
        "--allow-non-latest",
        "--json",
    },
    ("artifacts", "trust-gate"): {
        "--registry-dir",
        "--artifact-class",
        "--subject-digest",
        "--record-id",
        "--consumer-intent",
        "--source-repo",
        "--trust-root-mode",
        "--allow-non-latest",
        "--json",
    },
    ("artifacts", "evidence-promote"): {
        "--registry-dir",
        "--lifecycle-state",
        "--source-repo",
        "--source-ref",
        "--producer",
        "--trust-root-mode",
        "--json",
    },
    ("artifacts", "trust-coverage"): {
        "--registry-dir",
        "--manual-evidence-root",
        "--durable-only",
        "--json",
    },
    ("artifacts", "registry-latest"): {
        "--registry-dir",
        "--artifact-class",
        "--consumer-intent",
        "--subject-digest",
        "--source-repo",
        "--trust-root-mode",
        "--json",
    },
    ("artifacts", "scenarios"): {
        "--scenario-id",
        "--artifact-class",
        "--json",
    },
    ("artifacts", "update-verify"): {
        "--previous-trusted",
        "--now",
        "--registry-dir",
        "--subject-digest",
        "--source-repo",
        "--trust-root-mode",
        "--require-trust-gate",
        "--inspect-only",
        "--json",
    },
    ("artifacts", "update-repo-build"): {
        "--target-file",
        "--target-path",
        "--artifact-class",
        "--version",
        "--key-dir",
        "--dev-generate-keys",
        "--root-expires",
        "--targets-expires",
        "--snapshot-expires",
        "--timestamp-expires",
        "--now",
        "--json",
    },
    ("artifacts", "update-repo-verify"): {
        "--target-path",
        "--artifact-class",
        "--target-digest",
        "--previous-trusted",
        "--now",
        "--registry-dir",
        "--subject-digest",
        "--source-repo",
        "--trust-root-mode",
        "--require-trust-gate",
        "--inspect-only",
        "--json",
    },
    ("artifacts", "scitt-verify"): {
        "--receipt",
        "--external-relying-party",
        "--require-receipt",
        "--statement-class",
        "--artifact-digest",
        "--issuer",
        "--transparency-service",
        "--now",
        "--json",
    },
    ("artifacts", "oci-verify"): {
        "--artifact-class",
        "--registry-ref",
        "--subject-digest",
        "--required-referrer-type",
        "--registry-dir",
        "--record-id",
        "--record-subject-digest",
        "--source-repo",
        "--trust-root-mode",
        "--consumer-intent",
        "--allow-tag-reference",
        "--allow-missing-referrers",
        "--require-trust-gate",
        "--inspect-only",
        "--json",
    },
    ("nervous", "synthesis-build"): {
        "--scope",
        "--date",
        "--hour",
        "--json",
    },
    ("nervous", "semantic-build"): {
        "--max-chunks",
        "--batch-size",
        "--device",
        "--force",
        "--rebuild",
        "--json",
    },
    ("nervous", "semantic-maintain"): {
        "--min-delta",
        "--max-stale-minutes",
        "--timeout",
        "--dry-run",
        "--force-refresh",
        "--max-chunks",
        "--batch-size",
        "--rebuild",
        "--no-thermal-sample",
        "--refresh-index-first",
        "--no-refresh-index-first",
        "--json",
    },
    ("nervous", "semantic-search"): {
        "--query",
        "--limit",
        "--no-dedupe",
        "--source",
        "--schema",
        "--since",
        "--until",
        "--severity",
        "--sensitivity",
        "--force",
        "--json",
    },
    ("resource", "plan"): {
        "--class",
        "--kind",
        "--latency",
        "--unattended",
        "--force",
        "--scope",
        "--bytes",
        "--target",
        "--no-thermal-sample",
        "--json",
    },
    ("resource", "launch"): {
        "--class",
        "--kind",
        "--latency",
        "--unattended",
        "--force",
        "--dry-run",
        "--scope",
        "--unit",
        "--no-same-dir",
        "--timeout",
        "--bytes",
        "--target",
        "--no-thermal-sample",
        "--success-on-block",
        "--json",
    },
    ("ai", "cpu", "route"): {
        "--class",
        "--latency",
        "--force",
        "--json",
    },
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def _timeout_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        process.kill()


def command_result(command: list[str], *, cwd: Path, env: dict[str, str], timeout: float = 60) -> dict[str, Any]:
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            _kill_process_group(process)
            stdout, stderr = process.communicate()
        else:
            stdout = _timeout_output(exc.stdout)
            stderr = _timeout_output(exc.stderr)
        return {
            "command": command,
            "returncode": 124,
            "stdout": _timeout_output(stdout),
            "stderr": _timeout_output(stderr) + f"\ncommand timed out after {timeout} seconds",
            "timed_out": True,
            "timeout_sec": timeout,
        }
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": False,
    }


def run_json(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 60) -> dict[str, Any]:
    result = command_result(command, cwd=cwd, env=env, timeout=timeout)
    if result["returncode"] != 0:
        raise RuntimeError(f"{' '.join(command)} failed: {str(result['stderr'])[-1000:]}")
    try:
        payload = json.loads(str(result["stdout"]))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(command)} did not emit JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{' '.join(command)} emitted non-object JSON")
    return payload


def extract_subcommands(help_text: str) -> list[str]:
    match = re.search(r"\{([^}\n]+)\}", help_text)
    if not match:
        return []
    return sorted(part.strip() for part in match.group(1).split(",") if part.strip())


def env_without_pythonpath(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def source_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def projection_paths(root: Path) -> dict[str, Path]:
    home = root / "home" / "agent"
    return {
        "root": root,
        "home": home,
        "etc_root": root / "etc" / "abyss-machine",
        "state_root": root / "var" / "lib" / "abyss-machine",
        "srv_root": root / "srv" / "abyss-machine",
        "run_root": root / "run" / "abyss-machine",
        "abyss_os_root": root / "srv" / "AbyssOS",
        "vault_mount": root / "abyss",
        "local_bin_dir": root / "usr" / "local" / "bin",
        "local_libexec_dir": root / "usr" / "local" / "libexec",
        "systemd_system_dir": root / "etc" / "systemd" / "system",
        "systemd_user_dir": home / ".config" / "systemd" / "user",
        "share_root": root / "usr" / "local" / "share" / "abyss-machine",
    }


def projection_env(paths: dict[str, Path]) -> dict[str, str]:
    env = env_without_pythonpath()
    env.update(
        {
            "USER": "agent",
            "HOME": str(paths["home"]),
            "ABYSS_USER": "agent",
            "ABYSS_USER_HOME": str(paths["home"]),
            "ABYSS_MACHINE_ETC_ROOT": str(paths["etc_root"]),
            "ABYSS_MACHINE_STATE_ROOT": str(paths["state_root"]),
            "ABYSS_MACHINE_ROOT": str(paths["srv_root"]),
            "ABYSS_MACHINE_RUN_ROOT": str(paths["run_root"]),
            "ABYSS_MACHINE_CACHE_ROOT": str(paths["srv_root"] / "cache"),
            "ABYSS_MACHINE_RUNTIME_ROOT": str(paths["srv_root"] / "runtimes"),
            "ABYSS_MACHINE_STORAGE_ROOT": str(paths["srv_root"] / "storage"),
            "ABYSS_MACHINE_TMP_ROOT": str(paths["srv_root"] / "tmp"),
            "ABYSS_OS_ROOT": str(paths["abyss_os_root"]),
            "ABYSS_VAULT_MOUNT": str(paths["vault_mount"]),
            "ABYSS_LOCAL_BIN_DIR": str(paths["local_bin_dir"]),
            "ABYSS_LOCAL_LIBEXEC_DIR": str(paths["local_libexec_dir"]),
            "ABYSS_SYSTEMD_SYSTEM_DIR": str(paths["systemd_system_dir"]),
            "ABYSS_SYSTEMD_USER_DIR": str(paths["systemd_user_dir"]),
            "ABYSS_MACHINE_ARTIFACT_TRUST_RUNTIME_ROOT": str(
                paths["srv_root"] / "runtimes" / "artifact-trust"
            ),
            "ABYSS_MACHINE_ARTIFACT_TRUST_CACHE_ROOT": str(paths["srv_root"] / "cache" / "artifact-trust"),
            "ABYSS_AI_HOME": str(paths["srv_root"] / "runtimes" / "home" / "agent" / "abyss-ai"),
        }
    )
    return env


def bootstrap_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--profile",
        "linux-systemd-core",
        "--apply",
        "--user",
        "agent",
        "--home",
        str(paths["home"]),
        "--etc-root",
        str(paths["etc_root"]),
        "--state-root",
        str(paths["state_root"]),
        "--srv-root",
        str(paths["srv_root"]),
        "--run-root",
        str(paths["run_root"]),
        "--abyss-os-root",
        str(paths["abyss_os_root"]),
        "--vault-mount",
        str(paths["vault_mount"]),
        "--local-bin-dir",
        str(paths["local_bin_dir"]),
        "--local-libexec-dir",
        str(paths["local_libexec_dir"]),
        "--systemd-system-dir",
        str(paths["systemd_system_dir"]),
        "--systemd-user-dir",
        str(paths["systemd_user_dir"]),
        "--skip-artifact-trust-gate",
        "--json",
    ]


def source_help_report(tmp_root: Path) -> dict[str, Any]:
    env = source_env()
    surfaces: dict[str, list[str]] = {}
    failures: list[str] = []
    for surface in HELP_SURFACES:
        command = [sys.executable, "-m", "abyss_machine.cli", *surface, "--help"]
        result = command_result(command, cwd=tmp_root, env=env, timeout=60)
        key = "top-level" if not surface else " ".join(surface)
        if result["returncode"] != 0:
            failures.append(f"source help failed for {key}: {str(result['stderr'])[-500:]}")
            surfaces[key] = []
            continue
        surfaces[key] = extract_subcommands(str(result["stdout"]))
    return {
        "status": "ok" if not failures else "failed",
        "surfaces": surfaces,
        "failures": failures,
        "requires_pythonpath_src": True,
    }


def installed_help_report(executable: Path, *, cwd: Path, env: dict[str, str], label: str, timeout: float = 60) -> dict[str, Any]:
    surfaces: dict[str, list[str]] = {}
    failures: list[str] = []
    for surface in HELP_SURFACES:
        command = [str(executable), *surface, "--help"]
        result = command_result(command, cwd=cwd, env=env, timeout=timeout)
        key = "top-level" if not surface else " ".join(surface)
        if result["returncode"] != 0:
            failures.append(f"{label} help failed for {key}: {str(result['stderr'])[-500:]}")
            surfaces[key] = []
            continue
        surfaces[key] = extract_subcommands(str(result["stdout"]))
    return {
        "status": "ok" if not failures else "failed",
        "executable": str(executable),
        "surfaces": surfaces,
        "failures": failures,
    }


def critical_help_option_report(
    command_prefix: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
    timeout: float = 60,
) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for surface, required_options in CRITICAL_HELP_OPTIONS.items():
        command = [*command_prefix, *surface, "--help"]
        key = " ".join(surface)
        result = command_result(command, cwd=cwd, env=env, timeout=timeout)
        row = {
            "command": command,
            "status": "ok" if result["returncode"] == 0 else "failed",
            "required_options": sorted(required_options),
            "missing_options": [],
        }
        if result["returncode"] != 0:
            row["stderr_tail"] = str(result["stderr"])[-500:]
            failures.append(f"{label} critical help failed for {key}: {row['stderr_tail']}")
        else:
            help_text = str(result["stdout"])
            missing = sorted(option for option in required_options if option not in help_text)
            row["missing_options"] = missing
            if missing:
                failures.append(f"{label} critical help for {key} missing options: {', '.join(missing)}")
        commands[key] = row
    return {
        "status": "ok" if not failures else "failed",
        "commands": commands,
        "failures": failures,
    }


def source_critical_help_option_report(tmp_root: Path) -> dict[str, Any]:
    return critical_help_option_report(
        [sys.executable, "-m", "abyss_machine.cli"],
        cwd=tmp_root,
        env=source_env(),
        label="source",
    )


def installed_critical_help_option_report(
    executable: Path,
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
    timeout: float = 60,
) -> dict[str, Any]:
    return critical_help_option_report([str(executable)], cwd=cwd, env=env, label=label, timeout=timeout)


def compare_required_commands(surfaces: dict[str, list[str]]) -> list[str]:
    failures: list[str] = []
    checks = {
        "top-level": REQUIRED_TOP_LEVEL,
        "artifacts": REQUIRED_ARTIFACT_COMMANDS,
        "changes": REQUIRED_CHANGES_COMMANDS,
        "docs": REQUIRED_DOCS_COMMANDS,
        "topology": REQUIRED_TOPOLOGY_COMMANDS,
        "graph": REQUIRED_GRAPH_COMMANDS,
        "maps": REQUIRED_MAPS_COMMANDS,
        "rag": REQUIRED_RAG_COMMANDS,
        "stack-bridge": REQUIRED_STACK_BRIDGE_COMMANDS,
        "self-awareness": REQUIRED_SELF_AWARENESS_COMMANDS,
        "storage": REQUIRED_STORAGE_COMMANDS,
        "typing": REQUIRED_TYPING_COMMANDS,
        "nervous": REQUIRED_NERVOUS_COMMANDS,
        "resource": REQUIRED_RESOURCE_COMMANDS,
        "mode": REQUIRED_MODE_COMMANDS,
        "observability": REQUIRED_OBSERVABILITY_COMMANDS,
        "cooling": REQUIRED_COOLING_COMMANDS,
        "processes": REQUIRED_PROCESSES_COMMANDS,
        "heartbeats": REQUIRED_HEARTBEATS_COMMANDS,
        "reactions": REQUIRED_REACTIONS_COMMANDS,
        "responses": REQUIRED_RESPONSES_COMMANDS,
        "ai": REQUIRED_AI_COMMANDS,
        "ai cpu": REQUIRED_AI_CPU_COMMANDS,
    }
    for surface, required in checks.items():
        actual = set(surfaces.get(surface, []))
        missing = sorted(required - actual)
        if missing:
            failures.append(f"{surface} missing commands: {', '.join(missing)}")
    return failures


def compare_parity(source: dict[str, list[str]], installed: dict[str, list[str]], label: str) -> list[str]:
    failures: list[str] = []
    for surface in sorted(set(source) | set(installed)):
        source_set = set(source.get(surface, []))
        installed_set = set(installed.get(surface, []))
        if source_set != installed_set:
            missing = sorted(source_set - installed_set)
            extra = sorted(installed_set - source_set)
            details = []
            if missing:
                details.append(f"missing={','.join(missing)}")
            if extra:
                details.append(f"extra={','.join(extra)}")
            failures.append(f"{label} parity mismatch for {surface}: {'; '.join(details)}")
    return failures


def public_file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_file_digests(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rows[path.relative_to(root).as_posix()] = public_file_digest(path)
    return rows


def compare_digest_maps(
    source: dict[str, str],
    installed: dict[str, str],
    *,
    label: str,
    failures: list[str],
) -> dict[str, Any]:
    source_keys = set(source)
    installed_keys = set(installed)
    missing = sorted(source_keys - installed_keys)
    extra = sorted(installed_keys - source_keys)
    digest_mismatches = sorted(
        path for path in source_keys & installed_keys if source[path] != installed[path]
    )
    if missing:
        failures.append(f"{label} missing files: {', '.join(missing)}")
    if extra:
        failures.append(f"{label} extra files: {', '.join(extra)}")
    if digest_mismatches:
        failures.append(f"{label} digest mismatches: {', '.join(digest_mismatches)}")
    return {
        "source_files": len(source),
        "installed_files": len(installed),
        "missing": missing,
        "extra": extra,
        "digest_mismatches": digest_mismatches,
    }


def content_parity_report(
    *,
    label: str,
    installed_cli: Path,
    installed_package_root: Path,
    installed_share_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    cli_row = {
        "source": str(REPO_ROOT / "src" / "abyss_machine" / "cli.py"),
        "installed": str(installed_cli),
        "status": "ok",
    }
    source_cli = REPO_ROOT / "src" / "abyss_machine" / "cli.py"
    if not installed_cli.is_file():
        cli_row["status"] = "missing"
        failures.append(f"{label} CLI missing: {installed_cli}")
    else:
        source_digest = public_file_digest(source_cli)
        installed_digest = public_file_digest(installed_cli)
        cli_row["source_sha256"] = source_digest
        cli_row["installed_sha256"] = installed_digest
        if source_digest != installed_digest:
            cli_row["status"] = "digest_mismatch"
            failures.append(f"{label} CLI digest mismatch: {installed_cli}")

    package_row = compare_digest_maps(
        relative_file_digests(SOURCE_PACKAGE_ROOT),
        relative_file_digests(installed_package_root),
        label=f"{label} package",
        failures=failures,
    )
    package_row["source"] = str(SOURCE_PACKAGE_ROOT)
    package_row["installed"] = str(installed_package_root)

    public_seed_rows: dict[str, dict[str, Any]] = {}
    for root_id, source_root in SOURCE_PUBLIC_SEED_ROOTS.items():
        row = compare_digest_maps(
            relative_file_digests(source_root),
            relative_file_digests(installed_share_root / root_id),
            label=f"{label} public seed {root_id}",
            failures=failures,
        )
        row["source"] = str(source_root)
        row["installed"] = str(installed_share_root / root_id)
        public_seed_rows[root_id] = row

    return {
        "status": "ok" if not failures else "failed",
        "label": label,
        "cli": cli_row,
        "package": package_row,
        "public_seed": public_seed_rows,
        "failures": failures,
    }


def package_projection_report(paths: dict[str, Path]) -> dict[str, Any]:
    source_modules = sorted(path.name for path in SOURCE_PACKAGE_ROOT.glob("*.py"))
    installed_package = paths["local_libexec_dir"] / "abyss_machine"
    installed_modules = sorted(path.name for path in installed_package.glob("*.py"))
    share_root = paths["share_root"]
    source_public_seed = {
        "manifests": sorted(path.relative_to(REPO_ROOT / "manifests").as_posix() for path in (REPO_ROOT / "manifests").rglob("*") if path.is_file()),
        "generated": sorted(path.relative_to(REPO_ROOT / "generated").as_posix() for path in (REPO_ROOT / "generated").rglob("*") if path.is_file()),
    }
    installed_public_seed = {
        "manifests": sorted(path.relative_to(share_root / "manifests").as_posix() for path in (share_root / "manifests").rglob("*") if path.is_file()),
        "generated": sorted(path.relative_to(share_root / "generated").as_posix() for path in (share_root / "generated").rglob("*") if path.is_file()),
    }
    failures: list[str] = []
    if source_modules != installed_modules:
        failures.append("installed package modules differ from source package modules")
    if source_public_seed != installed_public_seed:
        failures.append("installed public seed share differs from source manifests/generated roots")
    return {
        "status": "ok" if not failures else "failed",
        "package_target": str(installed_package),
        "source_modules": source_modules,
        "installed_modules": installed_modules,
        "share_root": str(share_root),
        "source_public_seed": source_public_seed,
        "installed_public_seed": installed_public_seed,
        "failures": failures,
    }


def module_import_report(paths: dict[str, Path]) -> dict[str, Any]:
    env = env_without_pythonpath()
    code = (
        "import json, pathlib, sys\n"
        f"sys.path.insert(0, {str(paths['local_libexec_dir'])!r})\n"
        "import abyss_machine.cli as cli\n"
        "print(json.dumps({'cli_file': str(pathlib.Path(cli.__file__).resolve()), "
        "'path0': sys.path[0]}, sort_keys=True))\n"
    )
    payload = run_json([sys.executable, "-c", code], cwd=paths["root"], env=env)
    cli_file = Path(str(payload["cli_file"]))
    package_root = paths["local_libexec_dir"] / "abyss_machine"
    ok_path = cli_file.is_relative_to(package_root)
    return {
        "status": "ok" if ok_path else "failed",
        "cli_file": str(cli_file),
        "expected_package_root": str(package_root),
        "uses_source_checkout": cli_file.is_relative_to(REPO_ROOT),
    }


def installed_cli_constants(paths: dict[str, Path], env: dict[str, str]) -> dict[str, str]:
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(paths['local_libexec_dir'])!r})\n"
        "import abyss_machine.cli as cli\n"
        "print(json.dumps({\n"
        "  'typing_root': str(cli.TYPING_ROOT),\n"
        "  'typing_policy': str(cli.TYPING_POLICY_PATH),\n"
        "  'typing_refresh_service': cli.TYPING_NERVOUS_REFRESH_SERVICE,\n"
        "  'nervous_root': str(cli.NERVOUS_ROOT),\n"
        "  'nervous_privacy': str(cli.NERVOUS_PRIVACY_CONFIG_PATH),\n"
        "  'nervous_private_capture': str(cli.NERVOUS_PRIVATE_CAPTURE_ROOT),\n"
        "}, sort_keys=True))\n"
    )
    payload = run_json([sys.executable, "-c", code], cwd=paths["root"], env=env)
    return {str(key): str(value) for key, value in payload.items()}


def root_projection_report(paths: dict[str, Path]) -> dict[str, Any]:
    expected = {
        "etc_root": paths["etc_root"],
        "state_root": paths["state_root"],
        "srv_root": paths["srv_root"],
        "srv_cache_root": paths["srv_root"] / "cache",
        "srv_runtimes_root": paths["srv_root"] / "runtimes",
        "srv_storage_root": paths["srv_root"] / "storage",
        "srv_tmp_root": paths["srv_root"] / "tmp",
        "run_root": paths["run_root"],
        "local_bin_dir": paths["local_bin_dir"],
        "local_libexec_dir": paths["local_libexec_dir"],
        "systemd_system_dir": paths["systemd_system_dir"],
        "systemd_user_dir": paths["systemd_user_dir"],
        "public_seed_share_root": paths["share_root"],
    }
    rows = {key: {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir()} for key, path in expected.items()}
    failures = [f"{key} missing or not a directory: {row['path']}" for key, row in rows.items() if not row["is_dir"]]
    live_prefixes = ("/etc/abyss-machine", "/var/lib/abyss-machine", "/srv/abyss-machine", "/run/abyss-machine", "/usr/local")
    for key, row in rows.items():
        value = str(row["path"])
        if value in live_prefixes:
            failures.append(f"{key} points at live root {value}")
    return {"status": "ok" if not failures else "failed", "roots": rows, "failures": failures}


def profile_unit_report(paths: dict[str, Path]) -> dict[str, Any]:
    manifest = read_json(PROFILE_MANIFEST)
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        raise RuntimeError("bootstrap profile manifest must define profiles")
    failures: list[str] = []
    profile_rows: dict[str, dict[str, list[str]]] = {}
    for profile_id in ("linux-systemd-core", "typing-intake", "nervous-local"):
        scopes = profiles.get(profile_id)
        if not isinstance(scopes, dict):
            failures.append(f"missing profile {profile_id}")
            continue
        profile_rows[profile_id] = {"system": [], "user": []}
        for scope in ("system", "user"):
            unit_root = paths["systemd_system_dir"] if scope == "system" else paths["systemd_user_dir"]
            units = scopes.get(scope)
            if not isinstance(units, list):
                failures.append(f"profile {profile_id} {scope} units must be a list")
                continue
            for unit in units:
                unit_path = unit_root / str(unit)
                profile_rows[profile_id][scope].append(str(unit_path))
                if not unit_path.is_file():
                    failures.append(f"profile {profile_id} missing installed {scope} unit {unit}")
    typing_units = set(profiles.get("typing-intake", {}).get("user", [])) if isinstance(profiles.get("typing-intake"), dict) else set()
    nervous_units = set(profiles.get("nervous-local", {}).get("user", [])) if isinstance(profiles.get("nervous-local"), dict) else set()
    if "abyss-machine-typing-nervous-refresh.timer" not in typing_units:
        failures.append("typing-intake profile must include abyss-machine-typing-nervous-refresh.timer")
    if "abyss-nervous-browser-content-capture.timer" not in nervous_units:
        failures.append("nervous-local profile must carry browser capture as opt-in, not enabled by core")
    return {"status": "ok" if not failures else "failed", "profiles": profile_rows, "failures": failures}


def enable_profile_dry_run_report(profile: str) -> dict[str, Any]:
    payload = run_json(
        [sys.executable, str(BOOTSTRAP), "enable-profile", "--profile", profile, "--dry-run", "--json"],
        cwd=REPO_ROOT,
        env=source_env(),
        timeout=60,
    )
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    return {
        "profile": profile,
        "ok": payload.get("ok") is True,
        "dry_run": payload.get("dry_run") is True,
        "units": sorted(str(action.get("unit")) for action in actions if isinstance(action, dict) and action.get("unit")),
    }


def organ_bootstrap_report(installed: Path, paths: dict[str, Path], env: dict[str, str]) -> dict[str, Any]:
    failures: list[str] = []
    expected_configs = {
        "typing_policy": paths["etc_root"] / "typing-policy.json",
        "nervous_policy": paths["etc_root"] / "nervous" / "policy.json",
        "nervous_privacy": paths["etc_root"] / "nervous" / "privacy.json",
        "nervous_sources": paths["etc_root"] / "nervous" / "sources.json",
        "nervous_index": paths["etc_root"] / "nervous" / "index.json",
    }
    config_rows = {key: {"path": str(path), "exists": path.is_file()} for key, path in expected_configs.items()}
    for key, row in config_rows.items():
        if not row["exists"]:
            failures.append(f"missing config {key}: {row['path']}")

    typing_paths = run_json([str(installed), "typing", "paths", "--json"], cwd=paths["root"], env=env, timeout=60)
    nervous_paths = run_json([str(installed), "nervous", "paths", "--json"], cwd=paths["root"], env=env, timeout=60)
    constants = installed_cli_constants(paths, env)
    typing_text = json.dumps(typing_paths, sort_keys=True)
    nervous_text = json.dumps(nervous_paths, sort_keys=True)
    for expected in (str(paths["state_root"] / "typing"), str(paths["etc_root"] / "typing-policy.json")):
        if expected not in typing_text:
            failures.append(f"typing paths do not reference temp projection path {expected}")
    for expected in (
        str(paths["state_root"] / "nervous"),
        str(paths["etc_root"] / "nervous" / "privacy.json"),
    ):
        if expected not in nervous_text:
            failures.append(f"nervous paths do not reference temp projection path {expected}")
    expected_constants = {
        "typing_root": str(paths["state_root"] / "typing"),
        "typing_policy": str(paths["etc_root"] / "typing-policy.json"),
        "typing_refresh_service": "abyss-machine-typing-nervous-refresh.service",
        "nervous_root": str(paths["state_root"] / "nervous"),
        "nervous_privacy": str(paths["etc_root"] / "nervous" / "privacy.json"),
        "nervous_private_capture": str(paths["srv_root"] / "storage" / "nervous" / "captures"),
    }
    for key, expected in expected_constants.items():
        if constants.get(key) != expected:
            failures.append(f"installed CLI constant {key} mismatch: {constants.get(key)!r}")

    enable_typing = enable_profile_dry_run_report("typing-intake")
    enable_nervous = enable_profile_dry_run_report("nervous-local")
    for profile_payload in (enable_typing, enable_nervous):
        if not profile_payload["ok"] or not profile_payload["dry_run"]:
            failures.append(f"enable-profile {profile_payload['profile']} must stay dry-run in proof")

    return {
        "status": "ok" if not failures else "failed",
        "configs": config_rows,
        "typing_paths_schema": typing_paths.get("schema"),
        "nervous_paths_schema": nervous_paths.get("schema"),
        "installed_cli_constants": constants,
        "enable_profile_dry_runs": {
            "typing-intake": enable_typing,
            "nervous-local": enable_nervous,
        },
        "collector_activation": "not_performed",
        "raw_text_or_browser_capture": "not_collected",
        "failures": failures,
    }


def self_awareness_projection_report(installed: Path, paths: dict[str, Path], env: dict[str, str]) -> dict[str, Any]:
    failures: list[str] = []
    self_awareness_paths = run_json([str(installed), "self-awareness", "paths", "--json"], cwd=paths["root"], env=env, timeout=60)
    paths_text = json.dumps(self_awareness_paths, sort_keys=True)
    expected_paths = (
        str(paths["state_root"] / "self-awareness"),
        str(paths["state_root"] / "self-awareness" / "events" / "latest.json"),
        str(paths["etc_root"] / "SELF-AWARENESS.md"),
    )
    for expected in expected_paths:
        if expected not in paths_text:
            failures.append(f"self-awareness paths do not reference temp projection path {expected}")
    policy = self_awareness_paths.get("policy") if isinstance(self_awareness_paths.get("policy"), dict) else {}
    if policy.get("read_only_stack_consumer") is not True:
        failures.append("self-awareness paths policy must declare read_only_stack_consumer")
    if policy.get("host_layer_mutates_stack") is not False:
        failures.append("self-awareness paths policy must not mutate abyss-stack")
    if policy.get("automatic_remediation") is not False:
        failures.append("self-awareness paths policy must not authorize automatic remediation")
    commands = self_awareness_paths.get("commands") if isinstance(self_awareness_paths.get("commands"), dict) else {}
    command_text = "\n".join(str(value) for value in commands.values())
    missing_commands = sorted(
        command for command in REQUIRED_SELF_AWARENESS_COMMANDS
        if f"abyss-machine self-awareness {command}" not in command_text
    )
    if missing_commands:
        failures.append(f"self-awareness paths missing command contract keys: {', '.join(missing_commands)}")
    return {
        "status": "ok" if not failures else "failed",
        "paths_schema": self_awareness_paths.get("schema"),
        "root": self_awareness_paths.get("root"),
        "policy": policy,
        "commands": sorted(commands),
        "latest_paths": {
            key: value.get("latest")
            for key, value in self_awareness_paths.items()
            if isinstance(value, dict) and isinstance(value.get("latest"), str)
        },
        "live_collectors_enabled": False,
        "refresh_or_probe_run": False,
        "failures": failures,
    }


def portability_scan_report(paths: dict[str, Path]) -> dict[str, Any]:
    roots = {
        "source": REPO_ROOT,
        "temp_projection": paths["root"],
    }
    findings: list[dict[str, Any]] = []
    for root_id, root in roots.items():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in PORTABILITY_SCAN_EXCLUDED_PARTS for part in path.parts):
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                findings.append({
                    "root": root_id,
                    "path": str(path),
                    "needle": "read_error",
                    "detail": str(exc),
                })
                continue
            for needle_id, needle in PORTABILITY_NEEDLES.items():
                if needle not in data:
                    continue
                finding: dict[str, Any] = {
                    "root": root_id,
                    "path": str(path),
                    "needle": needle_id,
                }
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    finding["binary_match"] = True
                else:
                    needle_text = needle.decode("utf-8")
                    finding["lines"] = [
                        lineno
                        for lineno, line in enumerate(text.splitlines(), 1)
                        if needle_text in line
                    ][:20]
                findings.append(finding)
    failures = [
        f"{finding['needle']} found in {finding['root']}:{finding['path']}"
        for finding in findings
    ]
    return {
        "status": "ok" if not findings else "failed",
        "roots": {key: str(value) for key, value in roots.items()},
        "needles": sorted(PORTABILITY_NEEDLES),
        "findings": findings,
        "failures": failures,
    }


def host_installed_report(args: argparse.Namespace, paths: dict[str, Path]) -> dict[str, Any]:
    host_cli = Path(args.host_cli)
    if not args.require_host_installed:
        return {
            "status": "skipped",
            "reason": "host installed projection is advisory unless --require-host-installed is set",
            "required": False,
            "mode": "skipped_non_required_host_installed_projection",
            "failures": [],
            "critical_help_options": {"status": "skipped", "failures": []},
            "content_parity": {"status": "skipped", "failures": []},
        }
    if not host_cli.exists():
        return {"status": "unavailable", "reason": f"{host_cli} does not exist", "required": bool(args.require_host_installed)}
    if not os.access(host_cli, os.X_OK):
        return {"status": "unavailable", "reason": f"{host_cli} is not executable", "required": bool(args.require_host_installed)}
    env = projection_env(paths)
    host_timeout = getattr(args, "host_advisory_timeout", None)
    if host_timeout is None:
        host_timeout = 60.0 if args.require_host_installed else 5.0
    report = installed_help_report(host_cli, cwd=paths["root"], env=env, label="host-installed", timeout=float(host_timeout))
    if args.require_host_installed:
        report["critical_help_options"] = installed_critical_help_option_report(
            host_cli,
            cwd=paths["root"],
            env=env,
            label="host-installed",
            timeout=float(host_timeout),
        )
    else:
        report["critical_help_options"] = {
            "status": "skipped",
            "reason": "host installed critical option checks are advisory; pass --require-host-installed to require and run them",
            "commands": {},
            "failures": [],
        }
    report["content_parity"] = content_parity_report(
        label="host-installed",
        installed_cli=host_cli,
        installed_package_root=Path(args.host_libexec_dir) / "abyss_machine",
        installed_share_root=Path(args.host_share_root),
    )
    report["required"] = bool(args.require_host_installed)
    report["mode"] = "read_only_help_and_content_parity"
    return report


def build_report(args: argparse.Namespace, projection_root: Path) -> dict[str, Any]:
    paths = projection_paths(projection_root)
    paths["home"].mkdir(parents=True, exist_ok=True)
    env = projection_env(paths)
    install_payload = run_json([sys.executable, str(BOOTSTRAP), "install", *bootstrap_args(paths)], cwd=REPO_ROOT, env=source_env())
    installed = paths["local_bin_dir"] / "abyss-machine"

    source_help = source_help_report(paths["root"])
    temp_installed_help = installed_help_report(installed, cwd=paths["root"], env=env, label="temp-installed")
    source_critical_options = source_critical_help_option_report(paths["root"])
    temp_critical_options = installed_critical_help_option_report(installed, cwd=paths["root"], env=env, label="temp-installed")
    temp_content_parity = content_parity_report(
        label="temp-installed",
        installed_cli=paths["local_libexec_dir"] / "abyss-machine",
        installed_package_root=paths["local_libexec_dir"] / "abyss_machine",
        installed_share_root=paths["share_root"],
    )
    host_installed = host_installed_report(args, paths)

    failures: list[str] = []
    failures.extend(source_help.get("failures", []))
    failures.extend(temp_installed_help.get("failures", []))
    failures.extend(source_critical_options.get("failures", []))
    failures.extend(temp_critical_options.get("failures", []))
    failures.extend(temp_content_parity.get("failures", []))
    failures.extend(compare_required_commands(source_help["surfaces"]))
    failures.extend(compare_required_commands(temp_installed_help["surfaces"]))
    failures.extend(compare_parity(source_help["surfaces"], temp_installed_help["surfaces"], "temp-installed"))
    if host_installed.get("status") == "ok":
        host_parity_failures = compare_parity(source_help["surfaces"], host_installed["surfaces"], "host-installed")
        host_option_failures = host_installed.get("critical_help_options", {}).get("failures", [])
        host_content_failures = host_installed.get("content_parity", {}).get("failures", [])
        if args.require_host_installed:
            failures.extend(host_parity_failures)
            failures.extend(str(item) for item in host_option_failures)
            failures.extend(str(item) for item in host_content_failures)
        host_installed["parity_failures"] = host_parity_failures
        host_installed["option_failures"] = host_option_failures
        host_installed["content_parity_failures"] = host_content_failures
    elif args.require_host_installed:
        failures.append(f"host installed CLI unavailable: {host_installed.get('reason')}")

    root_report = root_projection_report(paths)
    package_report = package_projection_report(paths)
    import_report = module_import_report(paths)
    unit_report = profile_unit_report(paths)
    organ_report = organ_bootstrap_report(installed, paths, env)
    self_awareness_report = self_awareness_projection_report(installed, paths, env)
    portability_report = portability_scan_report(paths)
    for section in (root_report, package_report, import_report, unit_report, organ_report, self_awareness_report, portability_report):
        failures.extend(section.get("failures", []))
    if import_report.get("status") != "ok" or import_report.get("uses_source_checkout") is True:
        failures.append("installed module import does not prove temp libexec package ownership")

    return {
        "schema": SCHEMA,
        "ok": not failures,
        "projection_root": str(paths["root"]),
        "bootstrap": {
            "schema": install_payload.get("schema"),
            "version": install_payload.get("version"),
            "command": install_payload.get("command"),
            "ok": install_payload.get("ok"),
            "dry_run": install_payload.get("dry_run"),
            "actions": len(install_payload.get("actions", [])) if isinstance(install_payload.get("actions"), list) else 0,
        },
        "roots": root_report,
        "source_cli": source_help,
        "temp_installed_cli": temp_installed_help,
        "source_critical_help_options": source_critical_options,
        "temp_installed_critical_help_options": temp_critical_options,
        "temp_installed_content_parity": temp_content_parity,
        "host_installed_cli": host_installed,
        "package_projection": package_report,
        "module_import": import_report,
        "profile_units": unit_report,
        "typing_nervous": organ_report,
        "self_awareness": self_awareness_report,
        "portability_scan": portability_report,
        "host_closeout_route": {
            "preflight": "abyss-machine changes preflight --intent TEXT --surface /usr/local/bin/abyss-machine --json",
            "apply": "scripts/abyss-machine-bootstrap install --profile linux-systemd-core --apply --json",
            "daemon_reload": "systemctl daemon-reload and systemctl --user daemon-reload after a real host projection",
            "installed_smoke": "scripts/validators/first_run_installed_projection.py --require-host-installed --json",
            "ledger_close": "abyss-machine changes close ... after validation and rollback notes",
            "temp_validator_mutates_live_ledger": False,
        },
        "failures": failures,
    }


def temp_parent(args: argparse.Namespace) -> Path | None:
    if args.tmp_root:
        parent = Path(args.tmp_root)
        parent.mkdir(parents=True, exist_ok=True)
        return parent
    configured = os.environ.get("ABYSS_MACHINE_FIRST_RUN_TMPDIR")
    candidates = [Path(configured)] if configured else [Path("/srv/abyss-machine/tmp")]
    for candidate in candidates:
        if candidate.is_dir() and os.access(candidate, os.W_OK):
            return candidate
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a first-run installed abyss-machine projection in temp roots.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tmp-root", help="Parent directory for the temporary projection root.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the projection root for debugging.")
    parser.add_argument("--host-cli", default="/usr/local/bin/abyss-machine")
    parser.add_argument("--host-libexec-dir", default="/usr/local/libexec")
    parser.add_argument("--host-share-root", default="/usr/local/share/abyss-machine")
    parser.add_argument("--host-advisory-timeout", type=float, default=None)
    parser.add_argument("--require-host-installed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    parent = temp_parent(args)
    projection_root = Path(tempfile.mkdtemp(prefix="abyss-machine-first-run-", dir=str(parent) if parent else None))
    try:
        report = build_report(args, projection_root)
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "ok": False,
            "projection_root": str(projection_root),
            "failures": [str(exc)],
        }
    finally:
        if not args.keep_temp:
            shutil.rmtree(projection_root, ignore_errors=True)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report.get("ok") is True:
        if not args.json:
            return ok("first-run installed projection validation passed")
        return 0
    if args.json:
        return 1
    return fail("first-run installed projection validation failed", [str(item) for item in report.get("failures", [])])


if __name__ == "__main__":
    raise SystemExit(main())
