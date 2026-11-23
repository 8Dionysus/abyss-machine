"""Artifact and release bundles organ CLI, moved out of the abyss_machine core CLI.

`abyss_machine.cli` keeps the `artifacts` command names and
delegates here lazily. Shared core helpers are reached as `_core.<name>`,
so callers and tests that patch `abyss_machine.cli` keep the same effect.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import fcntl
import fnmatch
import grp
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import secrets
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from abyss_machine import cli as _core

_ORGAN_PACKAGE = "abyss_machine.organs.artifacts"
sys.dont_write_bytecode = True

globals().update(
    {
        "artifact_bundles": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.artifact_bundles"),
        "kag_artifacts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.kag_artifacts"),
    }
)

ai_cli = _core._lazy_import_module("abyss_machine.organs.ai.cli", allow_eager=False)


ARTIFACTS_BUNDLE_REGISTRY_ROOT = _core.ARTIFACTS_ROOT / "bundle-registry"


ARTIFACTS_BUNDLE_REGISTRY_INDEX_PATH = ARTIFACTS_BUNDLE_REGISTRY_ROOT / "index.json"


ARTIFACTS_TRUST_TOOLS_ROOT = _core.ARTIFACTS_ROOT / "trust-tools"


ARTIFACTS_TRUST_TOOLS_LATEST_PATH = ARTIFACTS_TRUST_TOOLS_ROOT / "latest.json"


ARTIFACTS_TRUST_TOOLS_PROOF_ROOT = ARTIFACTS_TRUST_TOOLS_ROOT / "proofs"


ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH = ARTIFACTS_TRUST_TOOLS_PROOF_ROOT / "latest.json"


ARTIFACTS_TRUST_COVERAGE_ROOT = _core.ARTIFACTS_ROOT / "trust-coverage"


ARTIFACTS_TRUST_COVERAGE_LATEST_PATH = ARTIFACTS_TRUST_COVERAGE_ROOT / "latest.json"


ARTIFACTS_REQUIREMENTS_ROOT = _core.ARTIFACTS_ROOT / "requirements"


ARTIFACTS_REQUIREMENTS_LATEST_PATH = ARTIFACTS_REQUIREMENTS_ROOT / "latest.json"


ARTIFACTS_PRODUCER_PROFILES_ROOT = _core.ARTIFACTS_ROOT / "producer-profiles"


ARTIFACTS_PRODUCER_PROFILES_LATEST_PATH = ARTIFACTS_PRODUCER_PROFILES_ROOT / "latest.json"


ARTIFACTS_SCENARIOS_ROOT = _core.ARTIFACTS_ROOT / "scenarios"


ARTIFACTS_SCENARIOS_LATEST_PATH = ARTIFACTS_SCENARIOS_ROOT / "latest.json"


ARTIFACTS_AFFECTED_ROOT = _core.ARTIFACTS_ROOT / "affected"


ARTIFACTS_AFFECTED_LATEST_PATH = ARTIFACTS_AFFECTED_ROOT / "latest.json"


ARTIFACTS_UPDATE_LANE_ROOT = _core.ARTIFACTS_ROOT / "update-lane"


ARTIFACTS_UPDATE_LANE_LATEST_PATH = ARTIFACTS_UPDATE_LANE_ROOT / "latest.json"


ARTIFACTS_OCI_PUBLICATION_ROOT = _core.ARTIFACTS_ROOT / "oci-publication"


ARTIFACTS_OCI_PUBLICATION_LATEST_PATH = ARTIFACTS_OCI_PUBLICATION_ROOT / "latest.json"


ARTIFACTS_OCI_CONSUMPTION_ROOT = _core.ARTIFACTS_ROOT / "oci-consumption"


ARTIFACTS_OCI_CONSUMPTION_LATEST_PATH = ARTIFACTS_OCI_CONSUMPTION_ROOT / "latest.json"


ARTIFACT_TRUST_RUNTIME_ROOT = Path(
    os.environ.get(
        "ABYSS_MACHINE_ARTIFACT_TRUST_RUNTIME_ROOT",
        str(_core.ABYSS_MACHINE_RUNTIME_ROOT / "artifact-trust"),
    )
)


ARTIFACT_TRUST_BIN_DIR = ARTIFACT_TRUST_RUNTIME_ROOT / "bin"


ARTIFACT_TRUST_CACHE_ROOT = Path(
    os.environ.get(
        "ABYSS_MACHINE_ARTIFACT_TRUST_CACHE_ROOT",
        str(_core.ABYSS_MACHINE_CACHE_ROOT / "artifact-trust"),
    )
)


ARTIFACT_TRUST_PYTHON_VENV_DIR = ARTIFACT_TRUST_RUNTIME_ROOT / "python"


ARTIFACT_TRUST_PYTHON_RECORD_PATH = ARTIFACT_TRUST_RUNTIME_ROOT / "python-tools.json"


ARTIFACT_TRUST_PYTHON_PACKAGE_LOCK: tuple[dict[str, Any], ...] = (
    {
        "tool_id": "in_toto_verify",
        "package": "in-toto",
        "version": "3.1.0",
        "binaries": ["in-toto-verify"],
    },
    {
        "tool_id": "cyclonedx_py",
        "package": "cyclonedx-bom",
        "version": "7.3.0",
        "binaries": ["cyclonedx-py"],
    },
)


ABYSS_RESTIC_BIN = Path(os.environ.get("ABYSS_RESTIC_BIN", str(_core.ABYSS_BACKUP_ROOT / "bin" / "restic")))


ABYSS_RESTIC_REPO = Path(os.environ.get("ABYSS_RESTIC_REPO", str(_core.ABYSS_BACKUP_ROOT / "restic" / "system")))


ABYSS_RESTIC_PASSWORD_FILE = Path(os.environ.get("ABYSS_RESTIC_PASSWORD_FILE", str(_core.ABYSS_BACKUP_ROOT / "secrets" / "restic-system.password")))


ABYSS_RESTIC_CACHE_DIR = Path(os.environ.get("ABYSS_RESTIC_CACHE_DIR", str(_core.ABYSS_BACKUP_ROOT / "tmp" / "restic-cache")))


def parse_json_object_argument(raw: str, *, argument_name: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{argument_name} must decode to a JSON object")
    return data


def path_mtime_iso(path: Path) -> str | None:
    return _core.storage_adapters.path_mtime_iso(path)


def path_atime_iso(path: Path) -> str | None:
    return _core.storage_adapters.path_atime_iso(path)


ARTIFACT_TRUST_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "cosign",
        "binary": "cosign",
        "controls": ["sigstore_cosign"],
        "version_args": ["version", "--json"],
        "role": "Sigstore/Cosign signing and verification for blobs, OCI artifacts, attestations, and release assets.",
        "install_route": "host-managed prebuilt binary under /srv/abyss-machine/runtimes/artifact-trust/bin",
    },
    {
        "id": "slsa_verifier",
        "binary": "slsa-verifier",
        "controls": ["slsa_in_toto"],
        "version_args": ["version"],
        "role": "Verification of SLSA provenance generated by supported builders.",
        "install_route": "host-managed release binary or Go toolchain route under /srv/abyss-machine/runtimes/artifact-trust",
    },
    {
        "id": "in_toto_verify",
        "binary": "in-toto-verify",
        "controls": ["slsa_in_toto"],
        "version_args": ["--version"],
        "role": "Generic in-toto layout/link verification for non-SLSA attestations.",
        "install_route": "host-managed Python runtime route under /srv/abyss-machine/runtimes/artifact-trust",
    },
    {
        "id": "c2patool",
        "binary": "c2patool",
        "controls": ["c2pa"],
        "version_args": ["--version"],
        "role": "C2PA manifest read/add/inspection route for public media exports.",
        "install_route": "host-managed release binary or Cargo route under /srv/abyss-machine/runtimes/artifact-trust",
    },
    {
        "id": "syft",
        "binary": "syft",
        "controls": ["sbom"],
        "version_args": ["version", "-o", "json"],
        "role": "General SBOM generation for packages, filesystems, archives, and container images.",
        "install_route": "host-managed release binary under /srv/abyss-machine/runtimes/artifact-trust/bin",
    },
    {
        "id": "cyclonedx_py",
        "binary": "cyclonedx-py",
        "controls": ["sbom"],
        "version_args": ["--version"],
        "role": "Python environment and project SBOM generation in CycloneDX format.",
        "install_route": "host-managed Python runtime route under /srv/abyss-machine/runtimes/artifact-trust",
    },
    {
        "id": "cdxgen",
        "binary": "cdxgen",
        "controls": ["sbom", "ml_bom"],
        "version_args": ["--version"],
        "role": "CycloneDX generation path for broad SBOM and AI/ML-BOM capable surfaces.",
        "install_route": "host-managed Node runtime route under /srv/abyss-machine/runtimes/artifact-trust",
    },
    {
        "id": "oras",
        "binary": "oras",
        "controls": ["oci_artifact"],
        "version_args": ["version"],
        "role": "OCI artifact push/pull plumbing for signed bundles and registry-backed artifacts.",
        "install_route": "host-managed release binary under /srv/abyss-machine/runtimes/artifact-trust/bin",
    },
)


ARTIFACT_TRUST_CONTROL_TOOLS: dict[str, tuple[str, ...]] = {
    "sigstore_cosign": ("cosign",),
    "slsa_in_toto": ("slsa_verifier", "in_toto_verify"),
    "c2pa": ("c2patool",),
    "sbom": ("syft", "cyclonedx_py", "cdxgen"),
    "ml_bom": ("cdxgen",),
    "oci_artifact": ("oras",),
}


def artifact_trust_tool_path_env() -> str:
    path_entries = [str(ARTIFACT_TRUST_BIN_DIR)]
    current_path = os.environ.get("PATH")
    if current_path:
        path_entries.append(current_path)
    return os.pathsep.join(path_entries)


def artifact_trust_tool_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = artifact_trust_tool_path_env()
    env.setdefault("XDG_CACHE_HOME", str(ARTIFACT_TRUST_CACHE_ROOT / "xdg-cache"))
    env.setdefault("SIGSTORE_TUF_ROOT", str(ARTIFACT_TRUST_CACHE_ROOT / "sigstore-tuf"))
    return env


def artifact_trust_tool_version_payload(tool_id: str, stdout: str) -> dict[str, Any]:
    if not stdout:
        return {}
    clean_stdout = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    if tool_id in {"cosign", "syft"}:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return {"raw": clean_stdout[:400]}
        if isinstance(payload, dict):
            return payload
    if tool_id == "cdxgen":
        lines = [line.strip() for line in clean_stdout.splitlines() if line.strip()]
        payload: dict[str, str] = {}
        for line in lines:
            version_match = re.search(r"CycloneDX Generator\s+([^\s]+)", line)
            if version_match:
                payload["application"] = "cdxgen"
                payload["version"] = version_match.group(1)
                continue
            runtime_match = re.search(r"Runtime:\s*([^,]+),\s*Version:\s*(.+)", line)
            if runtime_match:
                payload["runtime"] = runtime_match.group(1).strip()
                payload["runtime_version"] = runtime_match.group(2).strip()
        if payload:
            payload["raw"] = clean_stdout[:400]
            return payload
    if tool_id in {"slsa_verifier", "oras"}:
        parsed: dict[str, str] = {}
        for line in clean_stdout.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized = key.strip()
            if normalized in {
                "Version",
                "GitVersion",
                "GitCommit",
                "Git commit",
                "GitTreeState",
                "Git tree state",
                "BuildDate",
                "GoVersion",
                "Go version",
                "Compiler",
                "Platform",
                "OS/Arch",
            }:
                parsed[normalized] = value.strip()
        if parsed:
            return parsed
    if tool_id == "in_toto_verify":
        match = re.search(r"\bin-toto-verify\s+([^\s]+)", clean_stdout)
        if match:
            return {"application": "in-toto-verify", "version": match.group(1), "raw": clean_stdout[:400]}
    if tool_id == "cyclonedx_py":
        match = re.search(r"\b(\d+(?:\.\d+){1,3})\b", clean_stdout)
        if match:
            return {"application": "cyclonedx-py", "version": match.group(1), "raw": clean_stdout[:400]}
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            return {"raw": re.sub(r"\x1b\[[0-9;]*m", "", line)[:400]}
    return {"raw": clean_stdout[:400]}


def artifact_trust_tool_status(spec: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    binary = str(spec["binary"])
    resolved = shutil.which(binary, path=env.get("PATH"))
    managed_candidate = ARTIFACT_TRUST_BIN_DIR / binary
    source = "missing"
    if resolved:
        try:
            source = "host-managed-runtime" if Path(resolved).resolve() == managed_candidate.resolve() else "path"
        except OSError:
            source = "path"
    result: dict[str, Any] = {
        "id": spec["id"],
        "binary": binary,
        "available": bool(resolved),
        "status": "available" if resolved else "missing",
        "path": resolved,
        "source": source,
        "controls": spec["controls"],
        "role": spec["role"],
        "install_route": spec["install_route"],
    }
    if not resolved:
        return result

    version_args = [str(item) for item in spec.get("version_args", [])]
    version = _core.run([resolved, *version_args], timeout=15.0, env=env)
    result["version_command"] = [resolved, *version_args]
    result["version_ok"] = bool(version.get("ok"))
    result["version_returncode"] = version.get("returncode")
    result["version"] = artifact_trust_tool_version_payload(str(spec["id"]), str(version.get("stdout") or ""))
    if not version.get("ok"):
        result["version_error"] = version.get("stderr") or version.get("stdout")
    return result


def artifacts_trust_tools(write_latest: bool = True) -> dict[str, Any]:
    env = artifact_trust_tool_env()
    tools = {str(spec["id"]): artifact_trust_tool_status(spec, env) for spec in ARTIFACT_TRUST_TOOL_SPECS}
    controls: dict[str, dict[str, Any]] = {}
    for control, tool_ids in ARTIFACT_TRUST_CONTROL_TOOLS.items():
        available = [tool_id for tool_id in tool_ids if tools.get(tool_id, {}).get("available")]
        controls[control] = {
            "status": "available" if available else "missing",
            "available_tools": available,
            "candidate_tools": list(tool_ids),
        }
    missing_controls = sorted(control for control, payload in controls.items() if payload.get("status") != "available")
    missing_tools = sorted(tool_id for tool_id, payload in tools.items() if not payload.get("available"))
    available_tools = sorted(tool_id for tool_id, payload in tools.items() if payload.get("available"))
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_tools_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "summary": {
            "status": "ready" if not missing_controls else "partial",
            "available_tools": available_tools,
            "missing_tools": missing_tools,
            "available_controls": sorted(set(controls) - set(missing_controls)),
            "missing_controls": missing_controls,
        },
        "runtime": {
            "root": str(ARTIFACT_TRUST_RUNTIME_ROOT),
            "bin": str(ARTIFACT_TRUST_BIN_DIR),
            "cache_root": str(ARTIFACT_TRUST_CACHE_ROOT),
            "path_prefix": str(ARTIFACT_TRUST_BIN_DIR),
        },
        "controls": controls,
        "tools": tools,
        "claim_limits": [
            "Tool discovery proves local invocation only; it does not prove any artifact was externally signed or verified.",
            "Cosign availability is not a replacement for artifact-specific signature verification evidence.",
            "SLSA/in-toto, C2PA, SBOM, ML-BOM, and OCI controls remain incomplete when their required tools are missing.",
            "C2PA tool availability does not prove a public media asset has a trusted claim signature, accepted certificate policy, tamper check, or privacy review.",
            "ORAS availability does not prove an artifact was published to an external OCI registry, pulled by digest, authenticated, or signed.",
            "cdxgen availability proves only that CycloneDX SBOM/ML-BOM generation can run locally; it does not prove model, dataset, conversion, or framework identity completeness for a specific AI artifact.",
            "cdxgen exit status alone is not an ML-BOM trust gate; generated CycloneDX content must be checked for required machine-learning-model, data, service, and cdx:ai identity fields.",
            "npm registry integrity and package-lock evidence for cdxgen do not replace Sigstore, SLSA/in-toto, or artifact-specific release provenance.",
            "Host-managed tools under /srv/abyss-machine/runtimes are runtime dependencies, not source truth.",
        ],
        "latest": str(ARTIFACTS_TRUST_TOOLS_LATEST_PATH),
        "proof_route": {
            "command": "abyss-machine artifacts trust-tools-proof --json",
            "latest": str(ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH),
            "purpose": "positive and negative generic in-toto/Python SBOM proof for host-managed Python trust tools",
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_TRUST_TOOLS_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_TRUST_TOOLS_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifact_trust_python_packages() -> list[str]:
    return [f"{item['package']}=={item['version']}" for item in ARTIFACT_TRUST_PYTHON_PACKAGE_LOCK]


def _artifact_trust_python_expected_binaries() -> list[str]:
    binaries: list[str] = []
    for item in ARTIFACT_TRUST_PYTHON_PACKAGE_LOCK:
        binaries.extend(str(binary) for binary in item.get("binaries", []))
    return sorted(set(binaries))


def artifacts_trust_tools_python(
    *,
    apply: bool = False,
    force: bool = False,
    python_executable: str = "",
    write_latest: bool = True,
) -> dict[str, Any]:
    python_bin = python_executable or _core.sys.executable
    venv_dir = ARTIFACT_TRUST_PYTHON_VENV_DIR
    venv_python = venv_dir / "bin" / "python"
    cache_root = ARTIFACT_TRUST_CACHE_ROOT / "pip"
    packages = artifact_trust_python_packages()
    expected_binaries = _artifact_trust_python_expected_binaries()
    actions: list[dict[str, Any]] = [
        {
            "action": "create_python_venv",
            "command": [python_bin, "-m", "venv", str(venv_dir)],
            "target": str(venv_dir),
        },
        {
            "action": "install_python_packages",
            "command": [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                *packages,
            ],
            "packages": packages,
            "cache_root": str(cache_root),
        },
    ]
    for binary in expected_binaries:
        actions.append(
            {
                "action": "link_python_tool",
                "source": str(venv_dir / "bin" / binary),
                "target": str(ARTIFACT_TRUST_BIN_DIR / binary),
            }
        )

    data: dict[str, Any] = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_tools_python_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "dry_run": not apply,
        "force": force,
        "python": {
            "executable": python_bin,
            "venv": str(venv_dir),
            "venv_python": str(venv_python),
        },
        "runtime": {
            "root": str(ARTIFACT_TRUST_RUNTIME_ROOT),
            "bin": str(ARTIFACT_TRUST_BIN_DIR),
            "cache_root": str(ARTIFACT_TRUST_CACHE_ROOT),
            "pip_cache": str(cache_root),
            "record": str(ARTIFACT_TRUST_PYTHON_RECORD_PATH),
        },
        "package_lock": list(ARTIFACT_TRUST_PYTHON_PACKAGE_LOCK),
        "expected_binaries": expected_binaries,
        "actions": actions,
        "claim_limits": [
            "This prepares host-managed Python trust-tool entrypoints only; it does not verify any specific artifact.",
            "Pinned package installation is runtime state under /srv/abyss-machine/runtimes, not source truth.",
            "Generic in-toto verification supplements SLSA verifier evidence; existing SLSA verifier controls remain valid where artifact policy allows them.",
            "cyclonedx-py supplements syft/cdxgen for Python packages; SBOM trust still requires artifact-specific semantic checks.",
        ],
    }
    if not apply:
        return data

    failures: list[dict[str, Any]] = []
    ARTIFACT_TRUST_BIN_DIR.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    venv_result = _core.run([python_bin, "-m", "venv", str(venv_dir)], timeout=120.0)
    actions[0]["result"] = venv_result
    if not venv_result.get("ok"):
        failures.append({"action": "create_python_venv", "result": venv_result})
    if not failures:
        env = artifact_trust_tool_env()
        env["PIP_CACHE_DIR"] = str(cache_root)
        install_cmd = [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *packages,
        ]
        install_result = _core.run(install_cmd, timeout=300.0, env=env)
        actions[1]["result"] = install_result
        if not install_result.get("ok"):
            failures.append({"action": "install_python_packages", "result": install_result})

    if not failures:
        for action in actions:
            if action.get("action") != "link_python_tool":
                continue
            source = Path(str(action["source"]))
            target = Path(str(action["target"]))
            if not source.is_file():
                result = {"ok": False, "error": "source_binary_missing"}
                action["result"] = result
                failures.append({"action": "link_python_tool", "source": str(source), "target": str(target), "result": result})
                continue
            if target.exists() or target.is_symlink():
                try:
                    already_linked = target.resolve() == source.resolve()
                except OSError:
                    already_linked = False
                if already_linked:
                    action["result"] = {"ok": True, "status": "already_linked"}
                    continue
                if not force:
                    result = {"ok": False, "error": "target_exists_without_force"}
                    action["result"] = result
                    failures.append({"action": "link_python_tool", "source": str(source), "target": str(target), "result": result})
                    continue
                if target.is_dir():
                    result = {"ok": False, "error": "target_is_directory"}
                    action["result"] = result
                    failures.append({"action": "link_python_tool", "source": str(source), "target": str(target), "result": result})
                    continue
                target.unlink()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)
            action["result"] = {"ok": True, "status": "linked"}

    status = artifacts_trust_tools(write_latest=False)
    data["trust_tools"] = status.get("summary")
    data["tool_status"] = {
        tool_id: status.get("tools", {}).get(tool_id)
        for tool_id in ("in_toto_verify", "cyclonedx_py")
        if isinstance(status.get("tools"), dict)
    }
    if failures:
        data["ok"] = False
        data["failures"] = failures
        return data

    record_error = _core.safe_atomic_write_json(ARTIFACT_TRUST_PYTHON_RECORD_PATH, data, 0o664)
    if record_error:
        data["ok"] = False
        data["write_errors"] = [record_error]
        return data
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_TRUST_TOOLS_LATEST_PATH, artifacts_trust_tools(write_latest=False), 0o664)
        if latest_error:
            data["ok"] = False
            data["write_errors"] = [latest_error]
    return data


def artifact_trust_cyclonedx_python_sbom_check(
    sbom: dict[str, Any],
    *,
    expected_name: str,
    expected_version: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if sbom.get("bomFormat") != "CycloneDX":
        errors.append("sbom must use CycloneDX bomFormat")
    if not str(sbom.get("specVersion") or ""):
        errors.append("sbom must include CycloneDX specVersion")
    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        errors.append("sbom must include at least one component")
        components = []
    matches: list[dict[str, Any]] = []
    for item in components:
        if not isinstance(item, dict):
            continue
        if item.get("name") == expected_name and item.get("version") == expected_version:
            matches.append(item)
    if not matches:
        errors.append(f"sbom must include {expected_name}=={expected_version}")
    for item in matches:
        if item.get("type") != "library":
            errors.append(f"{expected_name} component must be type=library")
        purl = str(item.get("purl") or "")
        if purl != f"pkg:pypi/{expected_name}@{expected_version}":
            errors.append(f"{expected_name} component must include expected PyPI purl")
    return {
        "ok": not errors,
        "errors": errors,
        "component_count": len(components),
        "matched_components": matches,
    }


def _artifact_trust_tools_proof_add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    expected: str,
    ok: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "id": check_id,
        "expected": expected,
        "ok": bool(ok),
        "message": message,
    }
    if details:
        item["details"] = details
    checks.append(item)


def _artifact_trust_tools_in_toto_fixture_script() -> str:
    return r'''
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from in_toto.models.layout import Layout, Step
from in_toto.models.metadata import Metablock
from securesystemslib.signer import CryptoSigner, SSlibKey

root = Path(sys.argv[1])
in_toto_run = Path(sys.argv[2])
python_bin = Path(sys.argv[3])
link_dir = root / "links"
work_dir = root / "work"
link_dir.mkdir(parents=True, exist_ok=True)
work_dir.mkdir(parents=True, exist_ok=True)

private_key = ed25519.Ed25519PrivateKey.generate()
private_path = root / "functionary.key"
public_path = root / "functionary.pub"
private_path.write_bytes(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
public_path.write_bytes(private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
public_key = SSlibKey.from_crypto(private_key.public_key())
public_key_dict = public_key.to_dict()
public_key_dict["keyid"] = public_key.keyid
signer = CryptoSigner.from_priv_key_uri("file2:" + str(private_path), public_key)

command = [
    str(python_bin),
    "-c",
    "from pathlib import Path; Path('dist').mkdir(exist_ok=True); "
    "Path('dist/hello.txt').write_text('hello from in-toto proof\\n', encoding='utf-8')",
]


def write_layout(path: Path, product_rule: str) -> None:
    layout = Layout()
    layout.add_functionary_key(public_key_dict)
    step = Step(name="package")
    step.pubkeys = [public_key.keyid]
    step.expected_command = command
    step.add_product_rule_from_string(product_rule)
    step.add_product_rule_from_string("DISALLOW *")
    layout.steps.append(step)
    metadata = Metablock(signed=layout)
    metadata.create_signature(signer)
    metadata.dump(path)


write_layout(root / "root.layout", "CREATE dist/hello.txt")
write_layout(root / "root-negative.layout", "CREATE dist/not-produced.txt")

run_result = subprocess.run(
    [
        str(in_toto_run),
        "-n",
        "package",
        "--signing-key",
        str(private_path),
        "-p",
        "dist/hello.txt",
        "--base-path",
        str(work_dir),
        "-d",
        str(link_dir),
        "--",
        *command,
    ],
    cwd=str(work_dir),
    text=True,
    capture_output=True,
)
private_path.unlink(missing_ok=True)
link_files = sorted(link_dir.glob("package.*.link"))
print(json.dumps({
    "ok": run_result.returncode == 0 and len(link_files) == 1,
    "returncode": run_result.returncode,
    "stdout_tail": run_result.stdout[-800:],
    "stderr_tail": run_result.stderr[-800:],
    "root_layout": str(root / "root.layout"),
    "negative_layout": str(root / "root-negative.layout"),
    "public_key": str(public_path),
    "link_dir": str(link_dir),
    "link_files": [str(path) for path in link_files],
    "work_dir": str(work_dir),
    "keyid": public_key.keyid,
}))
'''


def artifact_trust_tools_proof(write_latest: bool = True) -> dict[str, Any]:
    generated_at = _core.now_iso()
    status = artifacts_trust_tools(write_latest=False)
    tools = status.get("tools") if isinstance(status.get("tools"), dict) else {}
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, Any] = {}
    proof_root = ARTIFACTS_TRUST_TOOLS_PROOF_ROOT

    in_toto_verify_text = str(_core.nested_get(tools, ["in_toto_verify", "path"]) or "")
    cyclonedx_py_text = str(_core.nested_get(tools, ["cyclonedx_py", "path"]) or "")
    in_toto_verify = Path(in_toto_verify_text) if in_toto_verify_text else Path()
    cyclonedx_py = Path(cyclonedx_py_text) if cyclonedx_py_text else Path()
    venv_python = ARTIFACT_TRUST_PYTHON_VENV_DIR / "bin" / "python"
    in_toto_run = ARTIFACT_TRUST_PYTHON_VENV_DIR / "bin" / "in-toto-run"

    tool_paths = {
        "in_toto_verify": in_toto_verify_text,
        "in_toto_run": str(in_toto_run),
        "cyclonedx_py": cyclonedx_py_text,
        "venv_python": str(venv_python),
    }
    for tool_id, path in tool_paths.items():
        path_obj = Path(path) if path else Path()
        _artifact_trust_tools_proof_add_check(
            checks,
            check_id=f"tool_available:{tool_id}",
            expected="pass",
            ok=bool(path and path_obj.is_file()),
            message=f"{tool_id} is available for proof execution",
            details={"path": path},
        )

    if all(item["ok"] for item in checks if str(item.get("id", "")).startswith("tool_available:")):
        _core.ABYSS_MACHINE_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="artifact-trust-tools-proof-", dir=str(_core.ABYSS_MACHINE_TMP_ROOT)) as tmp:
            tmp_root = Path(tmp)
            env = artifact_trust_tool_env()
            builder = _core.run(
                [
                    str(venv_python),
                    "-c",
                    _artifact_trust_tools_in_toto_fixture_script(),
                    str(tmp_root / "in-toto"),
                    str(in_toto_run),
                    str(venv_python),
                ],
                timeout=60.0,
                env=env,
            )
            builder_payload: dict[str, Any] = {}
            if builder.get("ok"):
                try:
                    builder_payload = json.loads(str(builder.get("stdout") or "{}"))
                except json.JSONDecodeError as exc:
                    builder_payload = {"ok": False, "error": f"builder_json_error:{exc}"}
            _artifact_trust_tools_proof_add_check(
                checks,
                check_id="in_toto_fixture_builder",
                expected="pass",
                ok=bool(builder.get("ok")) and bool(builder_payload.get("ok")),
                message="in-toto signed layout/link fixture can be generated by the host-managed Python runtime",
                details={
                    "returncode": builder.get("returncode"),
                    "builder": {key: builder_payload.get(key) for key in ("ok", "returncode", "keyid", "stderr_tail")},
                },
            )
            if builder_payload.get("ok"):
                for path_key in ("root_layout", "negative_layout", "public_key"):
                    path_text = str(builder_payload.get(path_key) or "")
                    if path_text and Path(path_text).is_file():
                        artifacts[f"in_toto_{path_key}_sha256"] = _core.sha256_path(Path(path_text))
                link_hashes = []
                for path_text in builder_payload.get("link_files") if isinstance(builder_payload.get("link_files"), list) else []:
                    path = Path(str(path_text))
                    if path.is_file():
                        link_hashes.append({"path": path.name, "sha256": _core.sha256_path(path)})
                artifacts["in_toto_link_files"] = link_hashes

                positive = _core.run(
                    [
                        str(in_toto_verify),
                        "--layout",
                        str(builder_payload["root_layout"]),
                        "--verification-keys",
                        str(builder_payload["public_key"]),
                        "--link-dir",
                        str(builder_payload["link_dir"]),
                    ],
                    timeout=60.0,
                    env=env,
                )
                _artifact_trust_tools_proof_add_check(
                    checks,
                    check_id="in_toto_verify_positive",
                    expected="pass",
                    ok=bool(positive.get("ok")),
                    message="in-toto-verify accepts the signed layout and matching link metadata",
                    details={"returncode": positive.get("returncode"), "stderr_tail": str(positive.get("stderr") or "")[-800:]},
                )

                negative = _core.run(
                    [
                        str(in_toto_verify),
                        "--layout",
                        str(builder_payload["negative_layout"]),
                        "--verification-keys",
                        str(builder_payload["public_key"]),
                        "--link-dir",
                        str(builder_payload["link_dir"]),
                    ],
                    timeout=60.0,
                    env=env,
                )
                _artifact_trust_tools_proof_add_check(
                    checks,
                    check_id="in_toto_verify_negative_product_rule",
                    expected="fail",
                    ok=not bool(negative.get("ok")) and _core.safe_int(negative.get("returncode"), 0) != 0,
                    message="in-toto-verify rejects a signed layout whose product rule does not match the link metadata",
                    details={"returncode": negative.get("returncode"), "stderr_tail": str(negative.get("stderr") or "")[-800:]},
                )

            sbom_root = tmp_root / "cyclonedx-py"
            sbom_root.mkdir(parents=True, exist_ok=True)
            requirements_path = sbom_root / "requirements.txt"
            requirements_path.write_text("idna==3.7\n", encoding="utf-8")
            sbom_path = sbom_root / "sbom.json"
            positive_sbom = _core.run(
                [
                    str(cyclonedx_py),
                    "requirements",
                    str(requirements_path),
                    "--of",
                    "JSON",
                    "--output-reproducible",
                    "--validate",
                    "-o",
                    str(sbom_path),
                ],
                timeout=60.0,
                env=env,
            )
            sbom_payload, sbom_error = _core.load_json_document(sbom_path)
            sbom_check = artifact_trust_cyclonedx_python_sbom_check(
                sbom_payload if isinstance(sbom_payload, dict) else {},
                expected_name="idna",
                expected_version="3.7",
            )
            if sbom_path.is_file():
                artifacts["cyclonedx_py_positive_sbom_sha256"] = _core.sha256_path(sbom_path)
            _artifact_trust_tools_proof_add_check(
                checks,
                check_id="cyclonedx_py_positive_python_package_sbom",
                expected="pass",
                ok=bool(positive_sbom.get("ok")) and bool(sbom_check.get("ok")),
                message="cyclonedx-py produces a semantic Python package SBOM for a frozen requirements inventory",
                details={
                    "returncode": positive_sbom.get("returncode"),
                    "json_error": sbom_error,
                    "semantic": sbom_check,
                    "stderr_tail": str(positive_sbom.get("stderr") or "")[-800:],
                },
            )

            negative_requirements_path = sbom_root / "negative-requirements.txt"
            negative_requirements_path.write_text("idna\n", encoding="utf-8")
            negative_sbom_path = sbom_root / "negative-sbom.json"
            negative_sbom = _core.run(
                [
                    str(cyclonedx_py),
                    "requirements",
                    str(negative_requirements_path),
                    "--of",
                    "JSON",
                    "--output-reproducible",
                    "--validate",
                    "-o",
                    str(negative_sbom_path),
                ],
                timeout=60.0,
                env=env,
            )
            negative_payload, negative_error = _core.load_json_document(negative_sbom_path)
            negative_check = artifact_trust_cyclonedx_python_sbom_check(
                negative_payload if isinstance(negative_payload, dict) else {},
                expected_name="idna",
                expected_version="3.7",
            )
            if negative_sbom_path.is_file():
                artifacts["cyclonedx_py_negative_sbom_sha256"] = _core.sha256_path(negative_sbom_path)
            _artifact_trust_tools_proof_add_check(
                checks,
                check_id="cyclonedx_py_negative_unfrozen_inventory_semantics",
                expected="fail",
                ok=bool(negative_sbom.get("ok")) and not bool(negative_check.get("ok")),
                message="Python SBOM proof rejects an unfrozen requirements inventory even when cyclonedx-py exits successfully",
                details={
                    "returncode": negative_sbom.get("returncode"),
                    "json_error": negative_error,
                    "semantic": negative_check,
                    "stderr_tail": str(negative_sbom.get("stderr") or "")[-800:],
                },
            )

    failures = [item for item in checks if not item.get("ok")]
    positives = [item for item in checks if item.get("expected") == "pass"]
    negatives = [item for item in checks if item.get("expected") == "fail"]
    data: dict[str, Any] = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_tools_proof_v1",
        "version": _core.VERSION,
        "generated_at": generated_at,
        "ok": not failures,
        "summary": {
            "status": "ok" if not failures else "fail",
            "checks": len(checks),
            "failures": len(failures),
            "positive_checks": len(positives),
            "negative_checks": len(negatives),
            "proven_tools": ["in_toto_verify", "cyclonedx_py"] if not failures else [],
        },
        "runtime": {
            "root": str(ARTIFACT_TRUST_RUNTIME_ROOT),
            "bin": str(ARTIFACT_TRUST_BIN_DIR),
            "python_venv": str(ARTIFACT_TRUST_PYTHON_VENV_DIR),
        },
        "tool_paths": tool_paths,
        "trust_tools": status.get("summary"),
        "checks": checks,
        "artifacts": artifacts,
        "latest": str(ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH),
        "non_claims": [
            "This proves the generic Python trust tools can execute positive and negative toy proofs on this host.",
            "This does not replace artifact-specific ABI, SBOM, SLSA/in-toto, Sigstore, C2PA, OCI, TUF, SCITT, or trust-gate evidence.",
            "Synthetic in-toto keys are temporary proof fixtures and are not release trust roots.",
            "The negative CycloneDX case proves semantic readback is required because cyclonedx-py can exit successfully on an unfrozen inventory.",
        ],
    }
    if write_latest:
        stamped_path = proof_root / generated_at[:4] / generated_at[5:7] / f"{generated_at.replace(':', '').replace('-', '')}.json"
        errors = [error for error in [
            _core.safe_atomic_write_json(stamped_path, data, 0o664),
            _core.safe_atomic_write_json(ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH, data, 0o664),
            _core.safe_append_jsonl(_core.ai_daily_jsonl_path(proof_root), data, 0o664),
            _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664),
        ] if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
            data["summary"]["status"] = "fail"
            data["summary"]["failures"] = data["summary"].get("failures", 0) + len(errors)
    return data


ARTIFACT_TRUST_COVERAGE_EXTERNAL_BLOCKERS: dict[str, str] = {
    "bootstrap_install_bundle": "No real bootstrap/install release artifact has been selected, built, signed, and registered yet.",
    "runtime_or_container_artifact": "No real runtime/container/OCI artifact has been selected, published by digest, signed, and registered yet.",
    "ai_model_or_runtime_bundle": "No publishable AI model/runtime bundle with ML-BOM, model/dataset identity, provenance, and signature has been selected yet.",
    "browser_extension_package": "No browser extension source zip/XPI package has been built, provenance-checked, and registered yet.",
    "public_media_export": "No concrete public media export with C2PA claim, tamper check, privacy route, and registry record has been selected yet.",
    "host_local_evidence": "The registry contains only a public-safe local provenance sample; a real private evidence packet needs owner review before latest promotion.",
    "aoa_session_memory_portable_bundle": "No clean aoa-session-memory portable kernel export has been audited, provenance-checked, and registered for workspace/update consumption yet.",
}


ARTIFACT_PRODUCTION_TRUST_ROOT_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "artifact_class": "bootstrap_install_bundle",
        "source_repo": "abyss-machine",
        "local_consumer_intent": "installer",
        "public_consumer_intent": "public_release",
        "objective_ref": "production_trust_roots.bootstrap_install_bundle",
    },
    {
        "artifact_class": "aoa_session_memory_portable_bundle",
        "source_repo": "aoa-session-memory",
        "local_consumer_intent": "update_client",
        "public_consumer_intent": "public_release",
        "objective_ref": "production_trust_roots.aoa_session_memory_portable_bundle",
    },
)


def artifact_trust_coverage_class_id(payload: dict[str, Any]) -> str:
    for value in (
        payload.get("artifact_class"),
        _core.nested_get(payload, ["record", "artifact_class"]),
        _core.nested_get(payload, ["verification", "artifact_class"]),
    ):
        if value:
            return str(value)
    latest = payload.get("latest_by_artifact_class")
    if isinstance(latest, dict) and len(latest) == 1:
        return str(next(iter(latest)))
    return ""


def artifact_trust_coverage_evidence_is_negative(path: Path, payload: dict[str, Any]) -> bool:
    name = path.name.lower()
    parent = path.parent.name.lower()
    negative_tokens = (
        "bad",
        "missing",
        "wrong",
        "tamper",
        "invalid",
        "unverified",
        "deny",
        "revoked",
        "after-revoke",
        "quarantined",
        "manual-review",
        "manual_review",
    )
    if any(token in name or token in parent for token in negative_tokens):
        return True
    if payload.get("ok") is False or payload.get("verification_ok") is False:
        return True
    record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
    if record.get("terminal_state") is True:
        return True
    if str(record.get("lifecycle_state") or "") in artifact_bundles.BUNDLE_TERMINAL_STATES:
        return True
    return False


def artifact_trust_coverage_evidence_is_positive(path: Path, payload: dict[str, Any]) -> bool:
    name = path.name.lower()
    if artifact_trust_coverage_evidence_is_negative(path, payload):
        return False
    if payload.get("ok") is True or payload.get("verification_ok") is True:
        return any(token in name for token in ("verify", "release-check", "register", "registry", "promote", "trust-gate", "gate", "positive", "allow"))
    return False


def artifact_trust_coverage_is_evidence_file(path: Path) -> bool:
    name = path.name.lower()
    evidence_tokens = (
        "verify",
        "release-check",
        "register",
        "registry",
        "promote",
        "trust-gate",
        "gate",
        "summary",
        "positive",
        "negative",
        "missing",
        "wrong",
        "bad",
        "unverified",
        "deny",
        "revoked",
        "tamper",
        "invalid",
    )
    return any(token in name for token in evidence_tokens)


def artifact_trust_coverage_dir_has_evidence_files(path: Path) -> bool:
    if not path.is_dir():
        return False
    candidates = list(path.glob("*.json")) + list(path.glob("*-bundle/*.json")) + list(path.glob("negative/*.json"))
    return any(artifact_trust_coverage_is_evidence_file(candidate) for candidate in candidates)


def artifact_trust_coverage_evidence_roots(
    extra_roots: list[str] | None = None,
    *,
    include_defaults: bool = True,
) -> list[Path]:
    roots = [_core.ABYSS_MACHINE_TMP_ROOT, ARTIFACTS_TRUST_TOOLS_ROOT / "manual-evidence"] if include_defaults else []
    roots.extend(Path(item) for item in extra_roots or [] if item)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def artifact_trust_coverage_collect_manual_evidence(
    extra_roots: list[str] | None = None,
    *,
    include_defaults: bool = True,
) -> dict[str, dict[str, list[str]]]:
    evidence: dict[str, dict[str, list[str]]] = {}
    candidate_dirs: list[Path] = []
    for root in artifact_trust_coverage_evidence_roots(extra_roots, include_defaults=include_defaults):
        if not root.is_dir():
            continue
        if any(token in root.name for token in ("manual", "persistent-abi-registry", "trust-coverage")):
            candidate_dirs.append(root)
        candidate_dirs.extend(
            path
            for path in root.iterdir()
            if path.is_dir() and artifact_trust_coverage_dir_has_evidence_files(path)
        )
        for pattern in ("*manual*", "*bundle*", "persistent-abi-registry-*", "trust-coverage-*"):
            candidate_dirs.extend(path for path in root.glob(pattern) if path.is_dir())

    for directory in sorted({path for path in candidate_dirs}, key=lambda item: str(item)):
        candidates = list(directory.glob("*.json")) + list(directory.glob("*-bundle/*.json")) + list(directory.glob("negative/*.json"))
        for path in sorted(candidates):
            if not artifact_trust_coverage_is_evidence_file(path):
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            class_id = artifact_trust_coverage_class_id(payload)
            if not class_id:
                continue
            bucket = evidence.setdefault(class_id, {"positive": [], "negative": []})
            ref = str(path)
            if artifact_trust_coverage_evidence_is_negative(path, payload):
                if ref not in bucket["negative"]:
                    bucket["negative"].append(ref)
            elif artifact_trust_coverage_evidence_is_positive(path, payload):
                if ref not in bucket["positive"]:
                    bucket["positive"].append(ref)
    return evidence


def artifact_trust_coverage_external_status(
    class_id: str,
    rule: dict[str, Any],
    latest: dict[str, Any] | None,
    records: list[dict[str, Any]],
) -> str:
    sigstore_rule = rule.get("sigstore_cosign") if isinstance(rule.get("sigstore_cosign"), dict) else {}
    c2pa_rule = rule.get("c2pa") if isinstance(rule.get("c2pa"), dict) else {}
    slsa_rule = rule.get("slsa_in_toto") if isinstance(rule.get("slsa_in_toto"), dict) else {}
    if latest is None:
        if records:
            states = sorted({str(record.get("lifecycle_state") or "unknown") for record in records if isinstance(record, dict)})
            signed_records = [
                record
                for record in records
                if isinstance(record, dict)
                and record.get("signature_required") is True
                and str(record.get("signature_status") or "") == "signed"
            ]
            if signed_records:
                return f"registered_signed_not_latest; states={','.join(states)}; local-key Cosign is not Fulcio/Rekor provenance"
            return f"registered_not_latest; states={','.join(states)}"
        if sigstore_rule.get("required") is True or c2pa_rule.get("required") is True:
            return "required_by_policy_but_no_registered_artifact"
        if slsa_rule.get("required") is True:
            return "provenance_required_but_no_registered_artifact"
        return "no_registered_artifact"
    if latest.get("signature_required") is True:
        return str(latest.get("signature_status") or "signature_required_status_unknown")
    if str(latest.get("signature_status") or "") == "not_required":
        return "local_policy_signature_decision_not_required; this is not a cryptographic signature"
    return str(latest.get("signature_status") or "not_recorded")


def artifact_trust_coverage_consumer_intent(class_id: str) -> str:
    if class_id == "bootstrap_install_bundle":
        return "installer"
    if class_id == "aoa_session_memory_portable_bundle":
        return "update_client"
    if class_id in {"runtime_or_container_artifact", "ai_model_or_runtime_bundle"}:
        return "runtime"
    if class_id in {"browser_extension_package", "public_media_export"}:
        return "release_consumer"
    return "agent"


def artifact_trust_source_repo_aliases(source_repo: str) -> list[str]:
    repo = str(source_repo or "").strip()
    if not repo:
        return []
    aliases = [repo]
    if repo == "aoa-session-memory":
        aliases.extend([".aoa", "bundles/aoa-session-memory"])
    return list(dict.fromkeys(aliases))


def artifact_trust_source_workspace_roots(source_root: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if source_root is not None:
        roots.extend([source_root, source_root.parent])
    env_roots = os.environ.get("ABYSS_MACHINE_ARTIFACT_WORKSPACE_ROOTS", "")
    for raw in env_roots.split(os.pathsep):
        if raw.strip():
            roots.append(Path(raw).expanduser())
    roots.extend([
        Path.cwd(),
        Path.cwd().parent,
        artifact_bundles.REPO_ROOT,
        artifact_bundles.REPO_ROOT.parent,
        Path("/srv/AbyssOS"),
        Path.home() / "src",
    ])
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve(strict=False))
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def artifact_trust_source_repo_roots(source_repo: str, *, source_root: Path | None = None) -> list[Path]:
    repo = str(source_repo or "").strip()
    roots: list[Path] = []
    if source_root is not None and (not repo or repo == "abyss-machine"):
        roots.append(source_root)
    if not repo or repo == "abyss-machine":
        roots.append(artifact_bundles.REPO_ROOT)
    aliases = artifact_trust_source_repo_aliases(repo)
    for workspace_root in artifact_trust_source_workspace_roots(source_root):
        roots.append(workspace_root)
        for alias in aliases:
            roots.append(workspace_root / alias)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            key = str(root.resolve(strict=False))
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def artifact_trust_split_manifest_ref(manifest_ref: str, fallback_source_repo: str) -> tuple[str, str]:
    ref = str(manifest_ref or "").strip()
    source_repo = str(fallback_source_repo or "").strip()
    if not ref.startswith("repo:"):
        return source_repo, ref
    repo_ref = ref.removeprefix("repo:")
    for alias in artifact_trust_source_repo_aliases(source_repo) + ["abyss-machine"]:
        prefix = f"{alias}/"
        if repo_ref.startswith(prefix):
            return alias if alias != "abyss-machine" else "abyss-machine", repo_ref[len(prefix):]
    if "/" in repo_ref:
        owner, path = repo_ref.split("/", 1)
        return owner, path
    return source_repo, ref


def artifact_trust_is_bundle_manifest_ref(manifest_ref: str, *, source_repo: str) -> bool:
    _repo, normalized_ref = artifact_trust_split_manifest_ref(manifest_ref, source_repo)
    return str(normalized_ref or "").endswith(".bundle.json")


def artifact_trust_load_source_manifest(
    manifest_ref: str,
    *,
    source_repo: str,
    source_root: Path | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    resolved_source_repo, normalized_ref = artifact_trust_split_manifest_ref(manifest_ref, source_repo)
    if not normalized_ref:
        return None, {
            "source_repo": resolved_source_repo or None,
            "manifest_ref": None,
            "resolved": False,
            "error": "source_manifest_ref_missing",
            "search_roots": [],
        }
    path = Path(normalized_ref)
    search_roots = artifact_trust_source_repo_roots(resolved_source_repo, source_root=source_root)
    candidates: list[tuple[Path, Path | None]] = []
    if path.is_absolute():
        candidates.append((path, None))
    else:
        candidates.extend((root / path, root) for root in search_roots)
    unique_candidates: list[tuple[Path, Path | None]] = []
    seen: set[str] = set()
    for candidate, root in candidates:
        try:
            key = str(candidate.resolve(strict=False))
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append((candidate, root))
    for candidate, root in unique_candidates:
        if not candidate.is_file():
            continue
        try:
            manifest = artifact_bundles.load_bundle_manifest(candidate)
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
            return None, {
                "source_repo": resolved_source_repo or None,
                "manifest_ref": normalized_ref,
                "resolved": False,
                "path": str(candidate),
                "error": str(exc),
                "search_roots": [str(root) for root in search_roots[:12]],
            }
        return manifest, {
            "source_repo": resolved_source_repo or None,
            "manifest_ref": normalized_ref,
            "resolved": True,
            "path": str(candidate),
            "source_root": str(root) if root is not None else None,
            "search_roots": [str(root) for root in search_roots[:12]],
        }
    return None, {
        "source_repo": resolved_source_repo or None,
        "manifest_ref": normalized_ref,
        "resolved": False,
        "error": f"source_manifest_unresolved:{normalized_ref}",
        "search_roots": [str(root) for root in search_roots[:12]],
    }


def artifact_trust_coverage_source_freshness(
    class_id: str,
    *,
    latest: dict[str, Any] | None,
    requirement: dict[str, Any],
    source_root: Path | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    current_abi_digests: list[str] = []
    manifest_ref = ""
    manifest_error = ""
    manifest_resolution: dict[str, Any] = {}
    current_consumer_contract: dict[str, Any] | None = None
    latest_consumer_contract: dict[str, Any] | None = None
    consumer_contract_matches_latest = False

    if not isinstance(latest, dict):
        return {
            "checked": False,
            "freshness": "unknown",
            "reasons": [],
            "claim_limit": "Source freshness is checked only after a latest durable registry record exists.",
        }

    source_repo = str(latest.get("source_repo") or requirement.get("owner_repo") or "")
    controls = requirement.get("controls") if isinstance(requirement.get("controls"), dict) else {}
    required_controls = [str(item) for item in controls.get("required", []) if str(item)]
    abi_required = "abi_signature" in required_controls
    source_route = requirement.get("source_route") if isinstance(requirement.get("source_route"), dict) else {}
    generated_surfaces = source_route.get("generated_contract_surfaces")
    if isinstance(generated_surfaces, list):
        for surface in generated_surfaces:
            if not isinstance(surface, dict):
                continue
            digest = str(surface.get("source_tree_hash") or "")
            if digest:
                current_abi_digests.append(digest)

    latest_abi_digest = str(latest.get("abi_subject_digest") or "")
    if current_abi_digests:
        if not latest_abi_digest:
            reasons.append("abi_subject_digest_missing")
        elif latest_abi_digest not in current_abi_digests:
            reasons.append("abi_subject_digest_stale")

    requirement_owner_repo = str(requirement.get("owner_repo") or "")
    candidate_rows: list[dict[str, str]] = []

    def add_manifest_candidate(ref: Any, *, candidate_source_repo: str, basis: str) -> None:
        ref_text = str(ref or "")
        if not ref_text:
            return
        row = {
            "ref": ref_text,
            "source_repo": str(candidate_source_repo or ""),
            "basis": basis,
        }
        if row not in candidate_rows:
            candidate_rows.append(row)

    add_manifest_candidate(latest.get("bundle_manifest_ref"), candidate_source_repo=source_repo, basis="latest.bundle_manifest_ref")
    add_manifest_candidate(latest.get("source_ref"), candidate_source_repo=source_repo, basis="latest.source_ref")
    for item in latest.get("source_refs", []) if isinstance(latest.get("source_refs"), list) else []:
        add_manifest_candidate(item, candidate_source_repo=source_repo, basis="latest.source_refs")
    for item in source_route.get("bundle_manifest_refs", []) if isinstance(source_route.get("bundle_manifest_refs"), list) else []:
        add_manifest_candidate(
            item,
            candidate_source_repo=requirement_owner_repo or source_repo,
            basis="requirement.source_route.bundle_manifest_refs",
        )

    candidate_reasons: list[str] = []
    allowed_manifest_owners = {item for item in {source_repo, requirement_owner_repo} if item}
    for candidate in candidate_rows:
        candidate_ref = candidate["ref"]
        candidate_source_repo = candidate["source_repo"]
        manifest_ref = candidate_ref
        if not artifact_trust_is_bundle_manifest_ref(candidate_ref, source_repo=candidate_source_repo):
            manifest_resolution = {
                "source_repo": candidate_source_repo or None,
                "manifest_ref": candidate_ref,
                "resolved": False,
                "skipped": True,
                "basis": candidate["basis"],
                "reason": "source_ref_is_not_bundle_manifest",
            }
            continue
        manifest, manifest_resolution = artifact_trust_load_source_manifest(
            candidate_ref,
            source_repo=candidate_source_repo,
            source_root=source_root,
        )
        manifest_resolution["basis"] = candidate["basis"]
        if manifest is None:
            manifest_error = str(manifest_resolution.get("error") or "source_manifest_unresolved")
            if "source_manifest_unresolved" not in candidate_reasons:
                candidate_reasons.append("source_manifest_unresolved")
            continue
        manifest_class = str(manifest.get("artifact_class") or "")
        manifest_owner = str(manifest.get("owner_repo") or "")
        if manifest_class != class_id or (manifest_owner and allowed_manifest_owners and manifest_owner not in allowed_manifest_owners):
            manifest_error = "source_manifest_mismatch"
            manifest_resolution["resolved"] = False
            manifest_resolution["error"] = manifest_error
            manifest_resolution["manifest_artifact_class"] = manifest_class or None
            manifest_resolution["manifest_owner_repo"] = manifest_owner or None
            if "source_manifest_mismatch" not in candidate_reasons:
                candidate_reasons.append("source_manifest_mismatch")
            continue
        manifest_error = ""
        manifest_contract = manifest.get("consumer_contract")
        if isinstance(manifest_contract, dict) and manifest_contract:
            record_contract = latest.get("consumer_contract")
            candidate_latest_contract = record_contract if isinstance(record_contract, dict) else None
            if candidate_latest_contract != manifest_contract:
                current_consumer_contract = manifest_contract
                latest_consumer_contract = candidate_latest_contract
                if "consumer_contract_stale" not in candidate_reasons:
                    candidate_reasons.append("consumer_contract_stale")
                continue
            current_consumer_contract = manifest_contract
            latest_consumer_contract = candidate_latest_contract
            consumer_contract_matches_latest = True
            candidate_reasons = []
            break
        if abi_required and not current_abi_digests:
            if "source_contract_uncheckable" not in candidate_reasons:
                candidate_reasons.append("source_contract_uncheckable")
            continue
        candidate_reasons = []
        break
    if not consumer_contract_matches_latest:
        for reason in candidate_reasons:
            if reason not in reasons:
                reasons.append(reason)

    checked = bool(current_abi_digests or current_consumer_contract is not None or reasons)
    return {
        "checked": checked,
        "freshness": "stale" if reasons else "fresh" if checked else "unknown",
        "reasons": reasons,
        "source_repo": source_repo or None,
        "current_abi_subject_digests": current_abi_digests,
        "latest_abi_subject_digest": latest_abi_digest or None,
        "bundle_manifest_ref": manifest_ref or None,
        "manifest_resolution": manifest_resolution or None,
        "manifest_error": manifest_error or None,
        "current_consumer_contract": current_consumer_contract,
        "latest_consumer_contract": latest_consumer_contract,
        "claim_limit": "Source freshness compares current local ABI/manifest contracts with the latest durable registry record; it does not rebuild or promote evidence.",
    }


def artifact_trust_coverage_row_status(
    class_id: str,
    *,
    latest: dict[str, Any] | None,
    records: list[dict[str, Any]],
    required_controls: list[str],
    manual_positive: list[str],
    manual_negative: list[str],
    gate: dict[str, Any] | None,
    source_freshness: dict[str, Any] | None = None,
    durable_only: bool = False,
) -> tuple[str, str]:
    if latest is None:
        if records:
            states = sorted({str(record.get("lifecycle_state") or "unknown") for record in records if isinstance(record, dict)})
            signed = any(
                isinstance(record, dict)
                and record.get("signature_required") is True
                and str(record.get("signature_status") or "") == "signed"
                for record in records
            )
            if signed:
                return (
                    "DEFERRED_WITH_REAL_BLOCKER",
                    "A signed built-local artifact exists, but no latest-eligible installed-parity record has been promoted yet.",
                )
            return "DEFERRED_WITH_REAL_BLOCKER", f"Persistent registry has records but no latest-eligible verified record; states={','.join(states)}."
        blocker = ARTIFACT_TRUST_COVERAGE_EXTERNAL_BLOCKERS.get(class_id)
        if blocker:
            return "DEFERRED_WITH_REAL_BLOCKER", blocker
        return "DEFERRED_WITH_REAL_BLOCKER", "No persistent registry record exists for this artifact class."
    verified_controls = set(str(item) for item in latest.get("verified_controls", []) if str(item))
    missing_controls = [control for control in required_controls if control not in verified_controls]
    if not latest.get("verification_ok") or missing_controls:
        return "DEFERRED_WITH_REAL_BLOCKER", "Persistent registry latest exists but required controls are not fully verified."
    if not isinstance(gate, dict) or gate.get("verdict") not in {"allow", "warn"}:
        verdict = gate.get("verdict") if isinstance(gate, dict) else "missing"
        reasons = gate.get("reasons", []) if isinstance(gate, dict) else []
        reason_text = f"; reasons={', '.join(str(item) for item in reasons[:3])}" if reasons else ""
        return "DEFERRED_WITH_REAL_BLOCKER", f"Consumer trust-gate did not allow registry latest; verdict={verdict}{reason_text}."
    if isinstance(source_freshness, dict) and source_freshness.get("freshness") == "stale":
        reasons = [str(item) for item in source_freshness.get("reasons", []) if str(item)]
        reason_text = ", ".join(reasons[:3]) if reasons else "source_freshness_stale"
        return "DEFERRED_WITH_REAL_BLOCKER", f"Persistent registry latest is stale against current source contracts: {reason_text}."
    public_media_c2pa_blocker = ""
    if class_id == "public_media_export" and isinstance(gate, dict):
        warnings = [str(item) for item in gate.get("warnings", []) if str(item)]
        inspected_claims = gate.get("inspected_claims") if isinstance(gate.get("inspected_claims"), dict) else {}
        c2pa_trust = inspected_claims.get("c2pa_trust") if isinstance(inspected_claims.get("c2pa_trust"), dict) else {}
        c2pa_not_production = bool(c2pa_trust) and c2pa_trust.get("production_trust_list_trusted") is not True
        onboarding = c2pa_trust.get("credential_onboarding") if isinstance(c2pa_trust.get("credential_onboarding"), dict) else {}
        warning_marks_gap = any(
            any(marker in warning for marker in artifact_bundles.C2PA_TRUST_GAP_WARNINGS)
            or "C2PA production trust anchors are not configured" in warning
            or warning == artifact_bundles.C2PA_PRE_ORGANIZATION_WARNING
            for warning in warnings
        )
        if c2pa_not_production or warning_marks_gap:
            onboarding_text = (
                f" Current credential onboarding phase is {onboarding.get('phase')}; "
                f"legal subject state is {onboarding.get('legal_subject_state')}."
                if onboarding
                else ""
            )
            public_media_c2pa_blocker = (
                "Public media export has release evidence and valid C2PA asset binding, "
                f"but the C2PA signing credential is not production trust-list trusted.{onboarding_text}"
            )
    if durable_only:
        if public_media_c2pa_blocker:
            return "DEFERRED_WITH_REAL_BLOCKER", public_media_c2pa_blocker
        return "DURABLE_GATE_COVERED", ""
    if not manual_positive:
        return "DEFERRED_WITH_REAL_BLOCKER", "Manual positive installed evidence was not found for this artifact class."
    if not manual_negative:
        return "DEFERRED_WITH_REAL_BLOCKER", "Manual negative/adversarial installed evidence was not found for this artifact class."
    if public_media_c2pa_blocker:
        return "DEFERRED_WITH_REAL_BLOCKER", public_media_c2pa_blocker
    return "FULLY_COVERED", ""


def artifact_trust_coverage_c2pa_onboarding(
    c2pa_trust: dict[str, Any],
    requirement: dict[str, Any],
) -> dict[str, Any]:
    latest_onboarding = (
        c2pa_trust.get("credential_onboarding")
        if isinstance(c2pa_trust.get("credential_onboarding"), dict)
        else {}
    )
    requirement_onboarding = (
        requirement.get("credential_onboarding")
        if isinstance(requirement.get("credential_onboarding"), dict)
        else {}
    )
    production_trusted = c2pa_trust.get("production_trust_list_trusted") is True
    if latest_onboarding:
        onboarding = dict(latest_onboarding)
        if (
            production_trusted
            and onboarding.get("production_claim_allowed") is True
            and not artifact_bundles._c2pa_onboarding_production_ready(onboarding)
        ):
            onboarding["production_claim_allowed"] = False
            onboarding["readiness_source"] = "legacy_record_without_explicit_production_onboarding_marker"
            onboarding["claim_limit"] = (
                "Latest C2PA trust-list evidence predates the explicit production onboarding marker; "
                "coverage reports the trust-list phase but does not allow production claims until a fresh verifier record carries the marker."
            )
        if not isinstance(onboarding.get("operating_window"), dict):
            onboarding["operating_window"] = artifact_bundles.c2pa_operating_window(
                onboarding,
                production_ready=artifact_bundles._c2pa_onboarding_production_ready(onboarding),
            )
        return onboarding
    if production_trusted:
        onboarding = {
            "schema": artifact_bundles.C2PA_CREDENTIAL_ONBOARDING_SCHEMA,
            "phase": "production_trust_list_ready",
            "legal_subject_state": "legacy_record_requires_explicit_onboarding_marker",
            "interim_posture": "production_c2pa_trust_list",
            "production_onboarding_declared": False,
            "production_claim_allowed": False,
            "readiness_source": "legacy_c2pa_trust_verdict_without_explicit_onboarding",
            "claim_limit": (
                "Latest record proves production C2PA Trust List validation, but it predates the explicit onboarding packet; "
                "rerun verification with current manifest/policy before making a production public-media claim."
            ),
        }
        onboarding["operating_window"] = artifact_bundles.c2pa_operating_window(
            onboarding,
            production_ready=False,
        )
        return onboarding
    return dict(requirement_onboarding)


def artifact_trust_coverage_operating_posture(
    rows: list[dict[str, Any]],
    *,
    durable_only: bool = False,
) -> dict[str, Any]:
    internal_blockers: list[dict[str, Any]] = []
    public_claim_blockers: list[dict[str, Any]] = []
    warning_artifacts: list[dict[str, Any]] = []

    for row in rows:
        artifact_class = str(row.get("artifact_class") or "")
        status = str(row.get("status") or "")
        blocker = str(row.get("remaining_blocker") or "")
        trust_verdict = str(_core.nested_get(row, ["installed_verification", "trust_gate_verdict"]) or "")
        onboarding = row.get("credential_onboarding") if isinstance(row.get("credential_onboarding"), dict) else {}
        operating_window = (
            onboarding.get("operating_window")
            if isinstance(onboarding.get("operating_window"), dict)
            else {}
        )
        is_pre_org_c2pa = bool(
            artifact_class == "public_media_export"
            and onboarding.get("phase") == "pre_organization"
            and onboarding.get("production_claim_allowed") is not True
        )

        if trust_verdict == "warn":
            warning_artifacts.append({
                "artifact_class": artifact_class,
                "trust_gate_verdict": trust_verdict,
            })

        c2pa_public_claim_only_blocker = bool(
            is_pre_org_c2pa
            and (
                "C2PA signing credential is not production trust-list trusted" in blocker
                or "C2PA credential onboarding" in blocker
            )
        )

        if is_pre_org_c2pa:
            public_claim_blockers.append({
                "artifact_class": artifact_class,
                "reason": blocker or artifact_bundles.C2PA_PRE_ORGANIZATION_WARNING,
                "phase": onboarding.get("phase"),
                "legal_subject_state": onboarding.get("legal_subject_state"),
                "blocked_claims": onboarding.get("blocked_claims", []),
                "required_before_production_claim": onboarding.get("required_before_production_claim", []),
                "operating_window": operating_window
                or artifact_bundles.c2pa_operating_window(production_ready=False),
            })

        covered_statuses = {"DURABLE_GATE_COVERED"} if durable_only else {"FULLY_COVERED"}
        if status not in covered_statuses and not c2pa_public_claim_only_blocker:
            internal_blockers.append({
                "artifact_class": artifact_class,
                "status": status,
                "reason": blocker or "coverage_not_ready",
                "trust_gate_verdict": trust_verdict or None,
            })

    profile = "pre_organization" if public_claim_blockers else "organization_backed"
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_operating_posture_v1",
        "profile": profile,
        "evidence_mode": "durable_registry_only" if durable_only else "manual_e2e_plus_durable_registry",
        "os_internal_consumption": {
            "ready": not internal_blockers,
            "blocked_artifact_classes": internal_blockers,
            "admitted_trust_gate_verdicts": ["allow", "warn"],
            "claim_limit": (
                "ready=true means non-public-production blockers are absent for the selected evidence mode; "
                "warn verdicts still require consumers to preserve the warning."
            ),
        },
        "public_release_claims": {
            "production_ready": not internal_blockers and not public_claim_blockers,
            "blocked_artifact_classes": public_claim_blockers,
            "claim_limit": (
                "production_ready=false blocks unqualified public production trust claims; it does not block "
                "local OS Abyss integrity evidence or explicit warn-mode release-consumer admission."
            ),
        },
        "warning_artifacts": warning_artifacts,
        "next_transition": {
            "target_profile": "organization_backed",
            "blocked_by": sorted({str(item.get("artifact_class") or "") for item in public_claim_blockers if item.get("artifact_class")}),
            "current_operating_windows": sorted({
                str(_core.nested_get(item, ["operating_window", "minimum_horizon"]) or "")
                for item in public_claim_blockers
                if _core.nested_get(item, ["operating_window", "minimum_horizon"])
            }),
            "review_cadence": sorted({
                str(_core.nested_get(item, ["operating_window", "review_cadence"]) or "")
                for item in public_claim_blockers
                if _core.nested_get(item, ["operating_window", "review_cadence"])
            }),
            "required_before_transition": sorted({
                str(step)
                for item in public_claim_blockers
                for step in item.get("required_before_production_claim", [])
                if str(step)
            }),
        },
        "claim_limits": [
            "This posture is computed from the trust-coverage rows; it does not mint credentials, signatures, attestations, receipts, or release artifacts.",
            "pre_organization is an operating profile for current OS Abyss work, not a substitute for a legal subject or production C2PA Trust List credential.",
        ],
    }


def artifact_trust_coverage_trust_root_posture(registry_dir: Path) -> dict[str, Any]:
    registry = artifact_bundles.read_bundle_registry(registry_dir)
    latest_by_class = registry.get("latest_by_artifact_class") if isinstance(registry.get("latest_by_artifact_class"), dict) else {}
    rows: list[dict[str, Any]] = []

    for target in ARTIFACT_PRODUCTION_TRUST_ROOT_TARGETS:
        artifact_class = str(target["artifact_class"])
        source_repo = str(target["source_repo"])
        local_intent = str(target["local_consumer_intent"])
        public_intent = str(target["public_consumer_intent"])
        latest = latest_by_class.get(artifact_class) if isinstance(latest_by_class.get(artifact_class), dict) else {}
        actual_mode = str(latest.get("trust_root_mode") or "") if latest else ""
        local_gate = artifact_bundles.trust_gate(
            registry_dir,
            artifact_class=artifact_class,
            consumer_intent=local_intent,
            expected_source_repo=source_repo,
            require_latest=True,
        )
        public_gate = artifact_bundles.trust_gate(
            registry_dir,
            artifact_class=artifact_class,
            consumer_intent=public_intent,
            expected_source_repo=source_repo,
            require_latest=True,
        )
        public_trust_root = _core.nested_get(public_gate, ["inspected_claims", "trust_root"]) or {}
        public_trust_root_evidence = _core.nested_get(public_gate, ["inspected_claims", "trust_root_evidence"]) or {}
        non_local_ready = bool(
            actual_mode in artifact_bundles.PRODUCTION_RELEASE_TRUST_ROOT_MODES
            and public_gate.get("verdict") in {"allow", "warn"}
            and public_trust_root_evidence.get("ok") is True
        )
        local_ready = bool(local_gate.get("verdict") in {"allow", "warn"})
        if not latest:
            status = "missing_latest_record"
        elif non_local_ready:
            status = "non_local_release_root_ready"
        elif local_ready:
            status = "local_ready_release_root_missing"
        else:
            status = "not_consumable"
        rows.append({
            "schema": f"{_core.SCHEMA_PREFIX}_production_trust_root_posture_row_v1",
            "artifact_class": artifact_class,
            "source_repo": source_repo,
            "objective_ref": target["objective_ref"],
            "latest_record_id": latest.get("record_id") if latest else None,
            "latest_subject_digest": latest.get("subject_digest") if latest else None,
            "latest_trust_root_mode": actual_mode or None,
            "status": status,
            "local_consumption": {
                "consumer_intent": local_intent,
                "ready": local_ready,
                "verdict": local_gate.get("verdict"),
                "reasons": local_gate.get("reasons", []),
            },
            "public_release_consumption": {
                "consumer_intent": public_intent,
                "ready": bool(public_gate.get("verdict") in {"allow", "warn"}),
                "verdict": public_gate.get("verdict"),
                "reasons": public_gate.get("reasons", []),
                "expected_modes": public_trust_root.get("production_expected_modes", []),
            },
            "non_local_release_root": {
                "ready": non_local_ready,
                "actual_mode": actual_mode or None,
                "accepted_modes": sorted(artifact_bundles.PRODUCTION_RELEASE_TRUST_ROOT_MODES),
                "evidence_required": public_trust_root_evidence.get("required"),
                "evidence_ok": public_trust_root_evidence.get("ok"),
                "evidence_ref": public_trust_root_evidence.get("evidence_ref"),
                "errors": public_trust_root_evidence.get("errors", []),
                "warnings": public_trust_root_evidence.get("warnings", []),
            },
            "claim_limit": (
                "Local installer/update readiness can be true with host_managed evidence; "
                "public production release readiness requires github_oidc, oci_registry, or public_release evidence."
            ),
        })

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    public_ready = bool(rows) and all(row.get("non_local_release_root", {}).get("ready") is True for row in rows)
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_production_trust_root_posture_v1",
        "summary": {
            "critical_targets": len(rows),
            "non_local_release_root_ready": status_counts.get("non_local_release_root_ready", 0),
            "local_ready_release_root_missing": status_counts.get("local_ready_release_root_missing", 0),
            "missing_latest_record": status_counts.get("missing_latest_record", 0),
            "not_consumable": status_counts.get("not_consumable", 0),
            "critical_public_release_ready": public_ready,
            "status_counts": status_counts,
        },
        "rows": rows,
        "claim_limits": [
            "This posture is computed from durable registry latest records and trust-gate results; it does not mint or replace trust roots.",
            "host_managed can admit local installer/update consumption when update-root evidence is present, but it is not a public release trust root.",
            "GitHub OIDC is treated as a producer adapter, not as the OS Abyss trust plane itself.",
        ],
    }


def artifacts_trust_coverage(
    *,
    registry_dir: Path | None = None,
    manual_evidence_roots: list[str] | None = None,
    durable_only: bool = False,
    source_root: Path | None = None,
    source_repo: str = "",
    source_ref: str = "",
    write_latest: bool = True,
) -> dict[str, Any]:
    registry_root = registry_dir if registry_dir is not None else ARTIFACTS_BUNDLE_REGISTRY_ROOT
    source_root_path = Path(source_root).expanduser() if source_root is not None else artifact_bundles.REPO_ROOT
    source_root_mode = "explicit" if source_root is not None else "resolved_default"
    policy = artifact_bundles.load_policy(source_root_path)
    classes = policy.get("artifact_classes") if isinstance(policy.get("artifact_classes"), dict) else {}
    registry = artifact_bundles.read_bundle_registry(registry_root)
    trust_tools = artifacts_trust_tools(write_latest=False)
    manual_evidence = (
        {}
        if durable_only
        else artifact_trust_coverage_collect_manual_evidence(manual_evidence_roots, include_defaults=True)
    )
    latest_by_class = registry.get("latest_by_artifact_class") if isinstance(registry.get("latest_by_artifact_class"), dict) else {}
    records = registry.get("records") if isinstance(registry.get("records"), list) else []
    available_controls = set(trust_tools.get("summary", {}).get("available_controls", []))
    requested_source_repo = str(source_repo or "").strip()
    requested_source_ref = str(source_ref or "").strip()
    affected_by_class: dict[str, dict[str, Any]] = {}
    affected_context: dict[str, Any] = {"checked": False}
    if requested_source_repo or requested_source_ref:
        affected_context = artifact_bundles.artifact_affected(
            [],
            changed_source_repo=requested_source_repo,
            changed_source_ref=requested_source_ref,
            registry_dir=registry_root,
            repo_root=source_root_path,
        )
        for affected_row in affected_context.get("rows", []):
            if not isinstance(affected_row, dict):
                continue
            affected_class = str(affected_row.get("artifact_class") or "")
            if affected_class:
                affected_by_class[affected_class] = affected_row
    source_context = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_source_context_v1",
        "public_seed_root": str(source_root_path),
        "public_seed_root_mode": source_root_mode,
        "requested_source_repo": requested_source_repo or None,
        "requested_source_ref": requested_source_ref or None,
        "affected_checked": bool(requested_source_repo or requested_source_ref),
        "affected_summary": affected_context.get("summary") if isinstance(affected_context.get("summary"), dict) else None,
        "claim_limit": (
            "public_seed_root selects the local policy/ABI/manifest read-model for source freshness; "
            "requested_source_repo/ref only checks whether durable evidence proves that source context."
        ),
    }
    rows: list[dict[str, Any]] = []

    for class_id, rule in classes.items():
        if not isinstance(rule, dict) or not isinstance(rule.get("identity"), dict):
            continue
        requirement = artifact_bundles.artifact_requirement_row(
            str(class_id),
            registry_dir=registry_root,
            repo_root=source_root_path,
        )
        identity = rule["identity"]
        required_controls = artifact_bundles.required_controls_for_rule(rule)
        deferred_controls = artifact_bundles.deferred_controls_for_rule(rule)
        class_records = [record for record in records if isinstance(record, dict) and record.get("artifact_class") == class_id]
        newest_record = sorted(class_records, key=lambda record: str(record.get("created_at") or ""))[-1] if class_records else {}
        latest = latest_by_class.get(class_id) if isinstance(latest_by_class.get(class_id), dict) else None
        consumer_intent = artifact_trust_coverage_consumer_intent(str(class_id))
        gate = (
            artifact_bundles.trust_gate(
                registry_root,
                artifact_class=str(class_id),
                consumer_intent=consumer_intent,
                require_latest=True,
            )
            if latest is not None
            else {}
        )
        source_freshness = artifact_trust_coverage_source_freshness(
            str(class_id),
            latest=latest,
            requirement=requirement,
            source_root=source_root_path,
        )
        affected_row = affected_by_class.get(str(class_id), {})
        affected_drift = affected_row.get("drift") if isinstance(affected_row.get("drift"), dict) else {}
        if affected_row:
            source_freshness["affected_drift"] = {
                "verdict": affected_row.get("verdict"),
                "freshness": affected_row.get("freshness"),
                "reasons": affected_row.get("reasons", []),
                "source_ref_status": affected_row.get("source_ref_status"),
                "abi_subject_status": affected_row.get("abi_subject_status"),
                "drift": affected_drift,
            }
            if affected_drift.get("operationally_blocking") is True:
                source_freshness["checked"] = True
                source_freshness["freshness"] = "stale"
                reasons = [str(item) for item in source_freshness.get("reasons", []) if str(item)]
                affected_reasons = affected_row.get("reasons", []) if isinstance(affected_row.get("reasons"), list) else []
                for reason in affected_reasons:
                    reason_text = str(reason or "")
                    if reason_text and reason_text not in reasons:
                        reasons.append(reason_text)
                drift_status = str(affected_drift.get("status") or "")
                if drift_status:
                    drift_reason = f"source_context_{drift_status}"
                    if drift_reason not in reasons:
                        reasons.append(drift_reason)
                source_freshness["reasons"] = reasons
        evidence_bucket = manual_evidence.get(class_id, {"positive": [], "negative": []})
        manual_positive = evidence_bucket.get("positive", [])[:16]
        manual_negative = evidence_bucket.get("negative", [])[:16]
        status, blocker = artifact_trust_coverage_row_status(
            str(class_id),
            latest=latest,
            records=class_records,
            required_controls=required_controls,
            manual_positive=manual_positive,
            manual_negative=manual_negative,
            gate=gate,
            source_freshness=source_freshness,
            durable_only=durable_only,
        )
        source_verification = [
            str(item) for item in identity.get("verification", [])
        ] if isinstance(identity.get("verification"), list) else []
        consumer_contract = latest.get("consumer_contract") if isinstance(latest, dict) and isinstance(latest.get("consumer_contract"), dict) else {}
        consumer_path = {
            "registry_query": f"abyss-machine artifacts bundle-registry --artifact-class {class_id} --json",
            "trust_gate": f"abyss-machine artifacts trust-gate --artifact-class {class_id} --consumer-intent {consumer_intent} --json",
            "stable_interface": consumer_contract.get("stable_interface"),
            "consumer_expectation": latest.get("consumer_expectation") if isinstance(latest, dict) else identity.get("consumer_expectation"),
        }
        unavailable_required_controls = [
            control
            for control in required_controls
            if control in ARTIFACT_TRUST_CONTROL_TOOLS and control not in available_controls
        ]
        if unavailable_required_controls and status != "FULLY_COVERED":
            status = "DEFERRED_WITH_REAL_BLOCKER"
            blocker = f"Required trust controls have no available local toolchain: {', '.join(unavailable_required_controls)}"
        credential_onboarding: dict[str, Any] = {}
        if str(class_id) == "public_media_export":
            inspected_claims = gate.get("inspected_claims") if isinstance(gate.get("inspected_claims"), dict) else {}
            c2pa_trust = inspected_claims.get("c2pa_trust") if isinstance(inspected_claims.get("c2pa_trust"), dict) else {}
            credential_onboarding = artifact_trust_coverage_c2pa_onboarding(c2pa_trust, requirement)
        row = {
            "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_coverage_row_v1",
            "artifact_class": class_id,
            "owner": identity.get("owner_repo"),
            "real_artifact": {
                "surface_state": identity.get("surface_state"),
                "content_identity": identity.get("content_identity"),
                "authority_ref": identity.get("authority_ref"),
                "registered_subject_digest": latest.get("subject_digest") if isinstance(latest, dict) else None,
                "bundle_ref": latest.get("bundle_ref") if isinstance(latest, dict) else None,
                "registered_record_count": len(class_records),
                "newest_record_state": newest_record.get("lifecycle_state") if isinstance(newest_record, dict) else None,
                "newest_record_id": newest_record.get("record_id") if isinstance(newest_record, dict) else None,
                "newest_subject_digest": newest_record.get("subject_digest") if isinstance(newest_record, dict) else None,
            },
            "required_controls": required_controls,
            "deferred_controls": deferred_controls,
            "source_verification": source_verification,
            "source_context": {
                "public_seed_root": str(source_root_path),
                "public_seed_root_mode": source_root_mode,
                "requested_source_repo": requested_source_repo or None,
                "requested_source_ref": requested_source_ref or None,
                "affected_verdict": affected_row.get("verdict") if affected_row else None,
                "affected_drift_status": affected_drift.get("status") if affected_drift else None,
            },
            "installed_verification": {
                "evidence_mode": "durable_registry_only" if durable_only else "manual_e2e_plus_durable_registry",
                "latest_record_verification_ok": latest.get("verification_ok") if isinstance(latest, dict) else False,
                "verified_controls": latest.get("verified_controls", []) if isinstance(latest, dict) else [],
                "manual_positive_evidence_count": len(evidence_bucket.get("positive", [])),
                "manual_negative_evidence_count": len(evidence_bucket.get("negative", [])),
                "trust_gate_ok": gate.get("ok") if isinstance(gate, dict) else False,
                "trust_gate_verdict": gate.get("verdict") if isinstance(gate, dict) else None,
            },
            "source_freshness": source_freshness,
            "persistent_registry_status": {
                "registry_dir": str(registry_root),
                "record_count": len(class_records),
                "has_latest": latest is not None,
                "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
                "latest_state": latest.get("lifecycle_state") if isinstance(latest, dict) else None,
                "latest_eligible": latest.get("latest_eligible") if isinstance(latest, dict) else False,
                "verification_missing": latest.get("verification_missing", []) if isinstance(latest, dict) else [],
                "verification_errors": latest.get("verification_errors", []) if isinstance(latest, dict) else [],
                "trust_gate_verdict": gate.get("verdict") if isinstance(gate, dict) else None,
                "trust_gate_reasons": gate.get("reasons", []) if isinstance(gate, dict) else [],
            },
            "consumer_path": consumer_path,
            "manual_positive_evidence": manual_positive,
            "manual_negative_evidence": manual_negative,
            "external_signature_provenance_status": artifact_trust_coverage_external_status(str(class_id), rule, latest, class_records),
            "claim_limits": [
                "FULLY_COVERED means required local controls, current source freshness, persistent latest selection, artifact-specific production blockers absent, trust-gate allow or warn verdict, consumer path, and manual positive/negative evidence are present.",
                "signature_status:not_required is a policy decision, not a cryptographic signature.",
                "Tool availability is not artifact-specific provenance or signature verification.",
            ],
            "status": status,
            "remaining_blocker": blocker,
        }
        if credential_onboarding:
            row["credential_onboarding"] = credential_onboarding
        rows.append(row)

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    operating_posture = artifact_trust_coverage_operating_posture(rows, durable_only=durable_only)
    trust_root_posture = artifact_trust_coverage_trust_root_posture(registry_root)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trust_coverage_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "summary": {
            "artifact_classes": len(rows),
            "fully_covered": status_counts.get("FULLY_COVERED", 0),
            "durable_gate_covered": status_counts.get("DURABLE_GATE_COVERED", 0),
            "deferred_with_real_blocker": status_counts.get("DEFERRED_WITH_REAL_BLOCKER", 0),
            "blocked_external": status_counts.get("BLOCKED_EXTERNAL", 0),
            "status_counts": status_counts,
            "registry_records": _core.nested_get(registry, ["summary", "records"]),
            "registry_latest": _core.nested_get(registry, ["summary", "latest"]),
            "trust_tools_status": _core.nested_get(trust_tools, ["summary", "status"]),
            "operating_profile": operating_posture["profile"],
            "os_internal_consumption_ready": _core.nested_get(operating_posture, ["os_internal_consumption", "ready"]),
            "public_release_claims_production_ready": _core.nested_get(operating_posture, ["public_release_claims", "production_ready"]),
            "critical_production_trust_roots_ready": _core.nested_get(
                trust_root_posture,
                ["summary", "critical_public_release_ready"],
            ),
        },
        "operating_posture": operating_posture,
        "trust_root_posture": trust_root_posture,
        "policy_ref": artifact_bundles.POLICY_REF,
        "abi_ref": artifact_bundles.ABI_REF,
        "registry": {
            "dir": str(registry_root),
            "summary": registry.get("summary"),
            "path_status": registry.get("path_status"),
            "warnings": registry.get("warnings", []),
        },
        "trust_tools": trust_tools.get("summary"),
        "source_context": source_context,
        "evidence_mode": "durable_registry_only" if durable_only else "manual_e2e_plus_durable_registry",
        "manual_evidence_roots": [
            str(path)
            for path in artifact_trust_coverage_evidence_roots(
                manual_evidence_roots,
                include_defaults=not durable_only,
            )
        ],
        "rows": rows,
        "latest": str(ARTIFACTS_TRUST_COVERAGE_LATEST_PATH),
        "claim_limits": [
            "This matrix is a coverage read-model. It does not create signatures, attestations, C2PA claims, SBOMs, or release artifacts.",
            "Rows without a real registered artifact remain deferred even when the relevant local toolchain is available.",
            "Rows without manual negative/adversarial evidence are not FULLY_COVERED.",
            "Rows without a trust-gate allow or warn verdict for the selected consumer intent are not FULLY_COVERED.",
            "Rows with artifact-specific production blockers, such as untrusted public-media C2PA credentials, are not FULLY_COVERED even when the trust-gate admits with warn.",
            "DURABLE_GATE_COVERED ignores tmp/manual evidence and only proves persistent registry latest plus consumer trust-gate admission.",
        ],
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_TRUST_COVERAGE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_TRUST_COVERAGE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_git_changed_paths(repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path.cwd()
    changed: set[str] = set()
    commands = (
        ["git", "diff", "--name-only", "--relative"],
        ["git", "diff", "--name-only", "--relative", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(changed)


def _git_output(command: list[str], *, repo_root: Path, timeout: float = 5.0) -> str:
    result = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def artifacts_git_dirty_digest(
    changed_paths: list[str] | None = None,
    *,
    repo_root: Path | None = None,
) -> str:
    root = repo_root or Path.cwd()
    paths = [str(path) for path in changed_paths or [] if str(path)]
    digest = hashlib.sha256()
    for label, base_command in (
        ("worktree", ["git", "diff", "--binary", "--relative"]),
        ("cached", ["git", "diff", "--binary", "--cached", "--relative"]),
    ):
        command = [*base_command]
        if paths:
            command.extend(["--", *paths])
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            timeout=10.0,
        )
        if result.returncode != 0:
            continue
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(result.stdout)
        digest.update(b"\0")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=10.0,
    )
    if untracked.returncode == 0:
        path_filter = set(paths)
        for item in sorted(line.strip() for line in untracked.stdout.splitlines() if line.strip()):
            if path_filter and item not in path_filter:
                continue
            candidate = root / item
            if not candidate.is_file():
                continue
            digest.update(b"untracked\0")
            digest.update(item.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(candidate.read_bytes()).hexdigest().encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def artifacts_git_source_refresh_ref(
    changed_paths: list[str] | None = None,
    *,
    repo_root: Path | None = None,
) -> str:
    root = repo_root or Path.cwd()
    head = _git_output(["git", "rev-parse", "HEAD"], repo_root=root)
    if not head:
        return ""
    branch = _git_output(["git", "branch", "--show-current"], repo_root=root)
    base = f"{branch}-{head}" if branch else head
    paths = [str(path) for path in changed_paths or [] if str(path)]
    if paths:
        base = f"{base}+dirty-{artifacts_git_dirty_digest(paths, repo_root=root)}"
    return f"source-refresh:{base}"


def artifacts_requirements(
    *,
    artifact_class: str = "",
    registry_dir: Path | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    registry_root = registry_dir if registry_dir is not None else ARTIFACTS_BUNDLE_REGISTRY_ROOT
    data = artifact_bundles.artifact_requirements(
        artifact_class=str(artifact_class or ""),
        registry_dir=registry_root,
    )
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_REQUIREMENTS_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_REQUIREMENTS_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_REQUIREMENTS_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def _parse_owner_repo_root_overrides(values: Iterable[str] | None) -> tuple[dict[str, Path], list[str]]:
    roots: dict[str, Path] = {}
    errors: list[str] = []
    for value in values or []:
        text = str(value or "")
        if "=" not in text:
            errors.append(f"owner_repo_root_override_must_use_OWNER=PATH:{text}")
            continue
        owner, path = text.split("=", 1)
        owner = owner.strip()
        path = path.strip()
        if not owner or not path:
            errors.append(f"owner_repo_root_override_must_use_OWNER=PATH:{text}")
            continue
        roots[owner] = Path(path)
    return roots, errors


def artifacts_producer_profiles(
    *,
    profile_id: str = "",
    owner_repo: str = "",
    artifact_class: str = "",
    workspace_root: Path | None = None,
    owner_repo_root: Iterable[str] | None = None,
    require_command_resolution: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    owner_repo_roots, parse_errors = _parse_owner_repo_root_overrides(owner_repo_root)
    effective_workspace_root = workspace_root
    if effective_workspace_root is None and require_command_resolution:
        effective_workspace_root = _core.PATH_POLICY.abyss_os_root
    data = artifact_bundles.artifact_producer_profiles(
        profile_id=str(profile_id or ""),
        owner_repo=str(owner_repo or ""),
        artifact_class=str(artifact_class or ""),
        workspace_root=effective_workspace_root,
        owner_repo_roots=owner_repo_roots,
        require_command_resolution=require_command_resolution,
    )
    if workspace_root is None and effective_workspace_root is not None:
        data["workspace_root_defaulted"] = str(effective_workspace_root)
    if parse_errors:
        data["ok"] = False
        data.setdefault("errors", []).extend(parse_errors)
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_PRODUCER_PROFILES_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_PRODUCER_PROFILES_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_PRODUCER_PROFILES_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_scenarios(
    *,
    scenario_id: str = "",
    artifact_class: str = "",
    registry_dir: Path | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    data = artifact_bundles.artifact_scenario_matrix(
        scenario_id=str(scenario_id or ""),
        artifact_class=str(artifact_class or ""),
        registry_dir=registry_dir,
    )
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_SCENARIOS_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_SCENARIOS_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_SCENARIOS_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_affected(
    *,
    artifact_class: str = "",
    registry_dir: Path | None = None,
    changed_paths: list[str] | None = None,
    changed_source_repo: str = "",
    changed_source_ref: str = "",
    accept_sibling_lag: bool = False,
    fail_on_blocking: bool = False,
    fail_on_accepted_lag: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    registry_root = registry_dir if registry_dir is not None else ARTIFACTS_BUNDLE_REGISTRY_ROOT
    explicit_paths = [str(item) for item in changed_paths or [] if str(item)]
    paths = explicit_paths if explicit_paths else ([] if changed_source_repo else artifacts_git_changed_paths())
    inferred_source_ref = ""
    if not changed_source_ref and paths and not explicit_paths and not changed_source_repo:
        inferred_source_ref = artifacts_git_source_refresh_ref(paths)
    effective_source_ref = str(changed_source_ref or inferred_source_ref or "")
    data = artifact_bundles.artifact_affected(
        paths,
        changed_source_repo=str(changed_source_repo or ""),
        changed_source_ref=effective_source_ref,
        artifact_class=str(artifact_class or ""),
        registry_dir=registry_root,
        accept_sibling_lag=accept_sibling_lag,
    )
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["changed_path_source"] = "explicit" if explicit_paths else ("source_repo_only" if changed_source_repo else "git_dirty_or_empty")
    data["changed_source_ref_source"] = (
        "explicit"
        if changed_source_ref
        else ("git_dirty_snapshot" if inferred_source_ref else "not_provided")
    )
    data["latest"] = str(ARTIFACTS_AFFECTED_LATEST_PATH)
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    blocking_count = int(summary.get("operationally_blocking") or 0)
    accepted_lag_count = int(summary.get("accepted_lag") or 0)
    gate_reasons: list[str] = []
    if fail_on_blocking and blocking_count:
        gate_reasons.append(f"operationally_blocking:{blocking_count}")
    if fail_on_accepted_lag and accepted_lag_count:
        gate_reasons.append(f"accepted_lag:{accepted_lag_count}")
    exit_code = 1 if not data.get("ok") else (2 if gate_reasons else 0)
    data["gate"] = {
        "enabled": bool(fail_on_blocking or fail_on_accepted_lag),
        "fail_on_blocking": fail_on_blocking,
        "fail_on_accepted_lag": fail_on_accepted_lag,
        "allowed": not gate_reasons and bool(data.get("ok")),
        "blocking_count": blocking_count,
        "accepted_lag_count": accepted_lag_count,
        "reasons": gate_reasons,
        "exit_code": exit_code,
        "claim_limit": "Affected gate only turns detected drift into a process exit code; it does not rebuild, verify, promote, or consume artifacts.",
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_AFFECTED_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_AFFECTED_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
            gate = data.get("gate")
            if isinstance(gate, dict):
                updated_reasons = list(gate.get("reasons", []))
                if "write_errors_present" not in updated_reasons:
                    updated_reasons.append("write_errors_present")
                gate["allowed"] = False
                gate["reasons"] = updated_reasons
                gate["exit_code"] = 1
    return data


def artifacts_registry_latest(
    *,
    artifact_class: str,
    registry_dir: Path | None = None,
    consumer_intent: str = "agent",
    subject_digest: str = "",
    expected_source_repo: str = "",
    expected_source_ref: str = "",
    expected_access_policy: str = "",
    expected_trust_root_mode: str = "",
) -> dict[str, Any]:
    registry_root = registry_dir if registry_dir is not None else ARTIFACTS_BUNDLE_REGISTRY_ROOT
    registry = artifact_bundles.read_bundle_registry(registry_root, artifact_class=artifact_class)
    latest_by_class = registry.get("latest_by_artifact_class") if isinstance(registry.get("latest_by_artifact_class"), dict) else {}
    scoped_latest = (
        registry.get("latest_by_artifact_class_and_source_repo", {}).get(
            artifact_class,
            {},
        )
        if isinstance(
            registry.get("latest_by_artifact_class_and_source_repo"),
            dict,
        )
        else {}
    )
    latest = (
        scoped_latest.get(expected_source_repo) or latest_by_class.get(artifact_class)
        if expected_source_repo and isinstance(scoped_latest, dict)
        else latest_by_class.get(artifact_class)
    )
    if not isinstance(latest, dict):
        latest = None
    gate = artifact_bundles.trust_gate(
        registry_root,
        artifact_class=artifact_class,
        subject_digest=subject_digest,
        consumer_intent=consumer_intent,
        expected_source_repo=expected_source_repo,
        expected_source_ref=expected_source_ref,
        expected_access_policy=expected_access_policy,
        expected_trust_root_mode=expected_trust_root_mode,
        require_latest=True,
    )
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifact_registry_latest_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": bool(latest is not None and gate.get("ok")),
        "artifact_class": artifact_class,
        "consumer_intent": consumer_intent,
        "registry_dir": str(registry_root),
        "has_latest": latest is not None,
        "latest_record_id": latest.get("record_id") if isinstance(latest, dict) else None,
        "latest_subject_digest": latest.get("subject_digest") if isinstance(latest, dict) else None,
        "latest_lifecycle_state": latest.get("lifecycle_state") if isinstance(latest, dict) else None,
        "record": latest,
        "trust_gate": gate,
        "registry_summary": registry.get("summary", {}),
        "claim_limits": [
            "registry-latest is a read-model over the durable bundle registry and consumer trust-gate; it does not build, verify, or promote artifacts.",
            "ok=true means a latest registry record exists and the trust gate returned allow or warn for the selected consumer intent.",
        ],
    }
    if latest is None:
        data["errors"] = ["no_latest_record"]
    elif not gate.get("ok"):
        data["errors"] = [str(item) for item in gate.get("reasons", [])] or ["trust_gate_not_allowed"]
    else:
        data["errors"] = []
    return data


def _iter_update_lane_history(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*/*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _current_external_tuf_evidence(
    record: dict[str, Any],
    *,
    registry_dir: Path,
) -> dict[str, Any] | None:
    if record.get("schema") != "abyss_machine_tuf_repository_verify_v1":
        return None
    if record.get("ok") is not True or record.get("verdict") != "allow" or record.get("metadata_ok") is not True:
        return None
    artifact_class = str(record.get("artifact_class") or "")
    target_path = str(record.get("target_path") or "")
    if not artifact_class or not target_path:
        return None
    trusted_root = record.get("trusted_root") if isinstance(record.get("trusted_root"), dict) else {}
    if trusted_root.get("required") is not True or trusted_root.get("provided") is not True:
        return None
    if trusted_root.get("trusted_root_match") is not True and trusted_root.get("rotation") is not True:
        return None
    if trusted_root.get("errors"):
        return None
    expiration_freshness = _tuf_role_expiration_freshness(record)
    if expiration_freshness.get("ok") is not True:
        return None
    consumer = record.get("consumer_admission") if isinstance(record.get("consumer_admission"), dict) else {}
    if consumer.get("required") is not True:
        return None
    subject_digest = str(consumer.get("subject_digest") or "")
    expected_source_repo = str(consumer.get("expected_source_repo") or "")
    expected_trust_root_mode = str(consumer.get("expected_trust_root_mode") or "")
    if not subject_digest:
        return None
    live_gate = artifact_bundles.trust_gate(
        registry_dir,
        artifact_class=artifact_class,
        subject_digest=subject_digest,
        consumer_intent="update_client",
        expected_source_repo=expected_source_repo,
        expected_trust_root_mode=expected_trust_root_mode,
        require_latest=True,
    )
    if live_gate.get("ok") is not True or live_gate.get("verdict") not in {"allow", "warn"}:
        return None
    target_digest = str(record.get("target_digest") or "")
    if target_digest and not target_digest.startswith("sha256:"):
        target_digest = "sha256:" + target_digest
    return {
        "schema": "abyss_machine_update_lane_external_tuf_evidence_v1",
        "status": "verified_current",
        "artifact_class": artifact_class,
        "target_path": target_path,
        "target_digest": target_digest or None,
        "repository_dir": record.get("repository_dir"),
        "trusted_root_path": record.get("trusted_root_path"),
        "previous_trusted_path": record.get("previous_trusted_path"),
        "role_versions": record.get("role_versions"),
        "role_expirations": record.get("role_expirations"),
        "role_expiration_freshness": expiration_freshness,
        "timestamp_sha256": record.get("timestamp_sha256"),
        "verified_at": record.get("generated_at"),
        "trusted_root": {
            "trusted_root_match": trusted_root.get("trusted_root_match"),
            "rotation": trusted_root.get("rotation"),
            "trusted_root_sha256": trusted_root.get("trusted_root_sha256"),
            "repository_root_sha256": trusted_root.get("repository_root_sha256"),
        },
        "consumer_admission": {
            "verdict": live_gate.get("verdict"),
            "subject_digest": subject_digest,
            "source_repo": expected_source_repo or None,
            "trust_root_mode": expected_trust_root_mode or None,
            "record_id": live_gate.get("record_id"),
            "latest_record_id": live_gate.get("latest_record_id"),
        },
        "claim_limit": "External TUF evidence is current only when role expirations remain valid and the stored repository verification is still admitted by the live durable artifact trust-gate.",
    }


def _tuf_role_expiration_freshness(record: dict[str, Any]) -> dict[str, Any]:
    expirations = record.get("role_expirations") if isinstance(record.get("role_expirations"), dict) else {}
    now_dt = dt.datetime.now(dt.UTC)
    parsed_expirations: dict[str, str] = {}
    errors: list[str] = []
    for role in ("root", "targets", "snapshot", "timestamp"):
        raw_expires = expirations.get(role)
        expires = artifact_bundles._parse_time(raw_expires)
        if expires is None:
            errors.append(f"{role}_expires_missing_or_invalid")
            continue
        parsed_expirations[role] = expires.isoformat().replace("+00:00", "Z")
        if expires <= now_dt:
            errors.append(f"{role}_expired")
    return {
        "ok": not errors,
        "checked_at": now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "role_expirations": parsed_expirations,
        "errors": errors,
    }


def _external_tuf_evidence_by_class(
    *,
    history_root: Path,
    registry_dir: Path,
    artifact_classes: set[str],
) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for record in _iter_update_lane_history(history_root):
        artifact_class = str(record.get("artifact_class") or "")
        if artifact_class not in artifact_classes or artifact_class in evidence:
            continue
        current = _current_external_tuf_evidence(record, registry_dir=registry_dir)
        if current is not None:
            evidence[artifact_class] = current
        if len(evidence) == len(artifact_classes):
            break
    return evidence


def _current_external_scitt_evidence(
    record: dict[str, Any],
    *,
    registry_dir: Path,
) -> dict[str, Any] | None:
    if record.get("schema") != "abyss_machine_scitt_receipt_verify_v1":
        return None
    if record.get("ok") is not True or record.get("verdict") != "allow":
        return None
    if record.get("external_relying_party") is not True:
        return None
    if record.get("receipt_required") is not True or record.get("receipt_present") is not True:
        return None
    if record.get("receipt_ok") is not True:
        return None
    registry_link = record.get("registry_link") if isinstance(record.get("registry_link"), dict) else {}
    if registry_link.get("required") is not True or registry_link.get("checked") is not True:
        return None
    if registry_link.get("record_found") is not True or registry_link.get("digest_match") is not True:
        return None
    if registry_link.get("errors"):
        return None
    artifact_class = str(registry_link.get("artifact_class") or "")
    record_id = str(registry_link.get("record_id") or "")
    if not artifact_class or not record_id:
        return None
    live_gate = artifact_bundles.trust_gate(
        registry_dir,
        artifact_class=artifact_class,
        record_id=record_id,
        consumer_intent="update_client",
        require_latest=True,
    )
    if live_gate.get("ok") is not True or live_gate.get("verdict") not in {"allow", "warn"}:
        return None
    return {
        "schema": "abyss_machine_update_lane_scitt_external_receipt_evidence_v1",
        "status": "verified_current",
        "artifact_class": artifact_class,
        "statement_class": record.get("statement_class"),
        "statement_digest": record.get("statement_digest"),
        "artifact_digest": record.get("artifact_digest"),
        "issuer": record.get("issuer"),
        "receipt_schema": record.get("receipt_schema"),
        "transparency_service": record.get("transparency_service"),
        "verified_at": record.get("generated_at"),
        "registry_link": {
            "record_id": record_id,
            "latest_record_id": registry_link.get("latest_record_id"),
            "digest_match": registry_link.get("digest_match"),
        },
        "consumer_admission": {
            "verdict": live_gate.get("verdict"),
            "consumer_intent": "update_client",
            "record_id": live_gate.get("record_id"),
            "latest_record_id": live_gate.get("latest_record_id"),
        },
        "claim_limit": (
            "SCITT external receipt evidence is current only when the stored receipt verification still "
            "binds to the live durable registry latest and update-client trust-gate admission."
        ),
    }


def _external_scitt_evidence_by_class(
    *,
    history_root: Path,
    registry_dir: Path,
    artifact_classes: set[str],
) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for record in _iter_update_lane_history(history_root):
        artifact_class = ""
        registry_link = record.get("registry_link") if isinstance(record.get("registry_link"), dict) else {}
        if registry_link:
            artifact_class = str(registry_link.get("artifact_class") or "")
        if artifact_class not in artifact_classes or artifact_class in evidence:
            continue
        current = _current_external_scitt_evidence(record, registry_dir=registry_dir)
        if current is not None:
            evidence[artifact_class] = current
        if len(evidence) == len(artifact_classes):
            break
    return evidence


def artifacts_update_lane(
    *,
    artifact_class: str = "",
    history_root: Path | None = None,
    registry_dir: Path | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    data = artifact_bundles.update_lane_status(
        artifact_class=str(artifact_class or ""),
    )
    selected_update_classes = {
        str(row.get("artifact_class") or "")
        for row in data.get("rows", [])
        if isinstance(row, dict) and row.get("applies") is True and row.get("artifact_class")
    }
    if selected_update_classes:
        resolved_history_root = history_root or ARTIFACTS_UPDATE_LANE_ROOT
        resolved_registry_dir = registry_dir or ARTIFACTS_BUNDLE_REGISTRY_ROOT
        external_tuf = _external_tuf_evidence_by_class(
            history_root=resolved_history_root,
            registry_dir=resolved_registry_dir,
            artifact_classes=selected_update_classes,
        )
        external_scitt = _external_scitt_evidence_by_class(
            history_root=resolved_history_root,
            registry_dir=resolved_registry_dir,
            artifact_classes=selected_update_classes,
        )
        for row in data.get("rows", []):
            if not isinstance(row, dict):
                continue
            row_artifact_class = str(row.get("artifact_class") or "")
            tuf_evidence = external_tuf.get(row_artifact_class)
            if tuf_evidence:
                row["status"] = "TUF_EXTERNAL_REPOSITORY_VERIFIED"
                row["external_tuf_repository"] = tuf_evidence
            scitt_evidence = external_scitt.get(row_artifact_class)
            if scitt_evidence:
                row["scitt_status"] = "SCITT_EXTERNAL_RECEIPT_VERIFIED"
                row["scitt_external_receipt"] = scitt_evidence
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        tuf_verified_count = len(external_tuf)
        scitt_verified_count = len(external_scitt)
        summary["external_tuf_verified_artifact_classes"] = tuf_verified_count
        summary["tuf_required_for_update_client"] = max(0, len(selected_update_classes) - tuf_verified_count)
        summary["scitt_external_receipt_verified_artifact_classes"] = scitt_verified_count
        summary["scitt_receipt_required_for_external_relying_party"] = max(
            0,
            len(selected_update_classes) - scitt_verified_count,
        )
        data["summary"] = summary
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_UPDATE_LANE_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_UPDATE_LANE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_UPDATE_LANE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_update_repo_build(
    repository_dir: Path,
    *,
    target_file: Path,
    target_path: str = "",
    artifact_class: str = "",
    version: int = 1,
    key_dir: Path | None = None,
    generate_missing_keys: bool = False,
    root_expires: str = "",
    targets_expires: str = "",
    snapshot_expires: str = "",
    timestamp_expires: str = "",
    now: str = "",
    write_latest: bool = True,
) -> dict[str, Any]:
    data = artifact_bundles.build_tuf_repository(
        repository_dir,
        target_file=target_file,
        target_path=target_path,
        artifact_class=artifact_class,
        version=version,
        key_dir=key_dir,
        generate_missing_keys=generate_missing_keys,
        root_expires=root_expires,
        targets_expires=targets_expires,
        snapshot_expires=snapshot_expires,
        timestamp_expires=timestamp_expires,
        now=str(now or "") or None,
    )
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_UPDATE_LANE_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_UPDATE_LANE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_UPDATE_LANE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_update_verify(
    metadata_path: Path,
    *,
    previous_trusted_path: Path | None = None,
    now: str = "",
    registry_dir: Path | None = None,
    subject_digest: str = "",
    expected_source_repo: str = "",
    expected_trust_root_mode: str = "",
    require_trust_gate: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    metadata, metadata_error = _core.load_json_document(metadata_path)
    previous: dict[str, Any] | None = None
    previous_error = ""
    if previous_trusted_path is not None:
        previous, previous_error = _core.load_json_document(previous_trusted_path)
    if metadata_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": "abyss_machine_update_metadata_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "metadata_path": str(metadata_path),
            "previous_trusted_path": str(previous_trusted_path) if previous_trusted_path else None,
            "verdict": "deny",
            "metadata_ok": False,
            "consumer_admission": {
                "required": bool(require_trust_gate),
                "verdict": "deny",
                "consumer_intent": "update_client",
                "registry_dir": str(registry_dir) if registry_dir is not None else None,
                "subject_digest": subject_digest or None,
                "expected_source_repo": expected_source_repo or None,
                "expected_trust_root_mode": expected_trust_root_mode or None,
                "errors": ["metadata_unavailable"],
                "trust_gate": None,
            },
            "errors": [f"metadata_{metadata_error}"],
            "warnings": [],
        }
    elif previous_error:
        data = {
            "ok": False,
            "schema": "abyss_machine_update_metadata_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "metadata_path": str(metadata_path),
            "previous_trusted_path": str(previous_trusted_path) if previous_trusted_path else None,
            "verdict": "deny",
            "metadata_ok": False,
            "consumer_admission": {
                "required": bool(require_trust_gate),
                "verdict": "deny",
                "consumer_intent": "update_client",
                "registry_dir": str(registry_dir) if registry_dir is not None else None,
                "subject_digest": subject_digest or None,
                "expected_source_repo": expected_source_repo or None,
                "expected_trust_root_mode": expected_trust_root_mode or None,
                "errors": ["previous_trusted_unavailable"],
                "trust_gate": None,
            },
            "errors": [f"previous_trusted_{previous_error}"],
            "warnings": [],
        }
    else:
        data = artifact_bundles.verify_update_metadata(
            metadata or {},
            previous_trusted=previous,
            now=str(now or "") or None,
            registry_dir=registry_dir,
            subject_digest=subject_digest,
            expected_source_repo=expected_source_repo,
            expected_trust_root_mode=expected_trust_root_mode,
            require_trust_gate=require_trust_gate,
        )
        data["metadata_path"] = str(metadata_path)
        data["previous_trusted_path"] = str(previous_trusted_path) if previous_trusted_path else None
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_UPDATE_LANE_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_UPDATE_LANE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_UPDATE_LANE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_update_repo_verify(
    repository_dir: Path,
    *,
    target_path: str,
    artifact_class: str = "",
    target_digest: str = "",
    trusted_root_path: Path | None = None,
    previous_trusted_path: Path | None = None,
    now: str = "",
    registry_dir: Path | None = None,
    subject_digest: str = "",
    expected_source_repo: str = "",
    expected_trust_root_mode: str = "",
    require_trusted_root: bool = False,
    require_trust_gate: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    trusted_root: dict[str, Any] | None = None
    trusted_root_error = ""
    if trusted_root_path is not None:
        trusted_root, trusted_root_error = _core.load_json_document(trusted_root_path)
    previous: dict[str, Any] | None = None
    previous_error = ""
    if previous_trusted_path is not None:
        previous, previous_error = _core.load_json_document(previous_trusted_path)
    if trusted_root_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": "abyss_machine_tuf_repository_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "repository_dir": str(repository_dir),
            "trusted_root_path": str(trusted_root_path),
            "previous_trusted_path": str(previous_trusted_path) if previous_trusted_path else None,
            "target_path": target_path,
            "artifact_class": artifact_class or None,
            "verdict": "deny",
            "metadata_ok": False,
            "errors": [f"trusted_root_{trusted_root_error}"],
            "warnings": [],
        }
    elif previous_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": "abyss_machine_tuf_repository_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "repository_dir": str(repository_dir),
            "trusted_root_path": str(trusted_root_path) if trusted_root_path else None,
            "previous_trusted_path": str(previous_trusted_path),
            "target_path": target_path,
            "artifact_class": artifact_class or None,
            "verdict": "deny",
            "metadata_ok": False,
            "errors": [f"previous_trusted_{previous_error}"],
            "warnings": [],
        }
    else:
        data = artifact_bundles.verify_tuf_repository(
            repository_dir,
            target_path=target_path,
            artifact_class=artifact_class,
            target_digest=target_digest,
            trusted_root=trusted_root,
            previous_trusted=previous,
            now=str(now or "") or None,
            registry_dir=registry_dir,
            subject_digest=subject_digest,
            expected_source_repo=expected_source_repo,
            expected_trust_root_mode=expected_trust_root_mode,
            require_trusted_root=require_trusted_root,
            require_trust_gate=require_trust_gate,
        )
        data["trusted_root_path"] = str(trusted_root_path) if trusted_root_path else None
        data["previous_trusted_path"] = str(previous_trusted_path) if previous_trusted_path else None
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_UPDATE_LANE_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_UPDATE_LANE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_UPDATE_LANE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_scitt_verify(
    statement_path: Path,
    *,
    receipt_path: Path | None = None,
    external_relying_party: bool = False,
    require_receipt: bool = False,
    registry_dir: Path | None = None,
    expected_record_id: str = "",
    require_registry_link: bool = False,
    expected_statement_class: str = "",
    expected_artifact_digest: str = "",
    expected_issuer: str = "",
    expected_transparency_service: str = "",
    now: str = "",
    write_latest: bool = True,
) -> dict[str, Any]:
    statement, statement_error = _core.load_json_document(statement_path)
    receipt: dict[str, Any] | None = None
    receipt_error = ""
    if receipt_path is not None:
        receipt, receipt_error = _core.load_json_document(receipt_path)
    if statement_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": "abyss_machine_scitt_receipt_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "statement_path": str(statement_path),
            "receipt_path": str(receipt_path) if receipt_path else None,
            "verdict": "deny",
            "errors": [f"statement_{statement_error}"],
            "warnings": [],
        }
    elif receipt_error:
        data = {
            "ok": False,
            "schema": "abyss_machine_scitt_receipt_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "statement_path": str(statement_path),
            "receipt_path": str(receipt_path) if receipt_path else None,
            "verdict": "deny",
            "errors": [f"receipt_{receipt_error}"],
            "warnings": [],
        }
    else:
        data = artifact_bundles.verify_scitt_receipt(
            statement or {},
            receipt=receipt,
            external_relying_party=external_relying_party,
            require_receipt=require_receipt,
            registry_dir=registry_dir,
            expected_record_id=expected_record_id,
            require_registry_link=require_registry_link,
            expected_statement_class=expected_statement_class,
            expected_artifact_digest=expected_artifact_digest,
            expected_issuer=expected_issuer,
            expected_transparency_service=expected_transparency_service,
            now=str(now or "") or None,
        )
        data["statement_path"] = str(statement_path)
        data["receipt_path"] = str(receipt_path) if receipt_path else None
        data["registry_dir"] = str(registry_dir) if registry_dir else None
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_UPDATE_LANE_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_UPDATE_LANE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_UPDATE_LANE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_oci_verify(
    evidence_path: Path,
    *,
    artifact_class: str = "",
    registry_ref: str = "",
    subject_digest: str = "",
    required_referrer_types: list[str] | None = None,
    registry_dir: Path | None = None,
    record_id: str = "",
    record_subject_digest: str = "",
    source_repo: str = "",
    trust_root_mode: str = "",
    consumer_intent: str = "runtime",
    allow_tag_reference: bool = False,
    allow_missing_referrers: bool = False,
    require_trust_gate: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    evidence, evidence_error = _core.load_json_document(evidence_path)
    if evidence_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": "abyss_machine_oci_publication_verify_v1",
            "policy_ref": artifact_bundles.POLICY_REF,
            "evidence_path": str(evidence_path),
            "verdict": "deny",
            "errors": [f"evidence_{evidence_error}"],
            "warnings": [],
        }
    else:
        container_schema = str(evidence.get("schema") or "") if isinstance(evidence, dict) else ""
        unwrapped = False
        if (
            container_schema == artifact_bundles.OCI_LAYOUT_PUBLICATION_SCHEMA
            and isinstance(evidence.get("evidence"), dict)
        ):
            evidence = evidence["evidence"]
            unwrapped = True
        data = artifact_bundles.verify_oci_publication(
            evidence or {},
            expected_artifact_class=artifact_class,
            expected_registry_ref=registry_ref,
            expected_subject_digest=subject_digest,
            required_referrer_types=required_referrer_types or [],
            registry_dir=registry_dir,
            expected_record_id=record_id,
            expected_record_subject_digest=record_subject_digest,
            expected_source_repo=source_repo,
            expected_trust_root_mode=trust_root_mode,
            consumer_intent=consumer_intent,
            require_digest_ref=not allow_tag_reference,
            require_referrers=not allow_missing_referrers,
            require_trust_gate=require_trust_gate,
        )
        data["evidence_path"] = str(evidence_path)
        data["evidence_container_schema"] = container_schema or None
        data["evidence_unwrapped"] = unwrapped
        data["registry_dir"] = str(registry_dir) if registry_dir else None
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_OCI_PUBLICATION_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_OCI_PUBLICATION_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_OCI_PUBLICATION_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def parse_oci_referrer_arg(value: str) -> dict[str, Any]:
    artifact_type, separator, path_text = str(value).partition("=")
    if not separator or not artifact_type.strip() or not path_text.strip():
        raise ValueError("OCI referrer must use ARTIFACT_TYPE=PATH")
    return {
        "artifact_type": artifact_type.strip(),
        "path": path_text.strip(),
    }


def artifacts_oci_layout_publish(
    subject_path: Path,
    layout_dir: Path,
    *,
    artifact_class: str,
    registry_ref: str,
    artifact_type: str = "",
    subject_media_type: str = "",
    referrers: list[dict[str, Any]] | None = None,
    record_id: str = "",
    record_subject_digest: str = "",
    write_latest: bool = True,
) -> dict[str, Any]:
    data = artifact_bundles.build_oci_layout_publication(
        subject_path,
        layout_dir,
        artifact_class=artifact_class,
        registry_ref=registry_ref,
        artifact_type=artifact_type or artifact_bundles.OCI_DEFAULT_SUBJECT_ARTIFACT_TYPE,
        subject_media_type=subject_media_type or artifact_bundles.OCI_CONTENT_DESCRIPTOR_MEDIA_TYPE,
        referrers=referrers or [],
        record_id=record_id,
        record_subject_digest=record_subject_digest,
    )
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_OCI_PUBLICATION_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_OCI_PUBLICATION_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_OCI_PUBLICATION_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_oci_consume(
    evidence_path: Path,
    output_dir: Path,
    *,
    artifact_class: str = "",
    registry_ref: str = "",
    subject_digest: str = "",
    required_referrer_types: list[str] | None = None,
    registry_dir: Path | None = None,
    record_id: str = "",
    record_subject_digest: str = "",
    source_repo: str = "",
    trust_root_mode: str = "",
    consumer_intent: str = "runtime",
    allow_tag_reference: bool = False,
    allow_missing_referrers: bool = False,
    require_trust_gate: bool = True,
    write_latest: bool = True,
) -> dict[str, Any]:
    evidence, evidence_error = _core.load_json_document(evidence_path)
    if evidence_error:
        data: dict[str, Any] = {
            "ok": False,
            "schema": artifact_bundles.OCI_CONSUMPTION_SCHEMA,
            "policy_ref": artifact_bundles.POLICY_REF,
            "evidence_path": str(evidence_path),
            "output_dir": str(output_dir),
            "verdict": "deny",
            "errors": [f"evidence_{evidence_error}"],
            "warnings": [],
        }
    else:
        container_schema = str(evidence.get("schema") or "") if isinstance(evidence, dict) else ""
        unwrapped = False
        if (
            container_schema == artifact_bundles.OCI_LAYOUT_PUBLICATION_SCHEMA
            and isinstance(evidence.get("evidence"), dict)
        ):
            evidence = evidence["evidence"]
            unwrapped = True
        data = artifact_bundles.consume_oci_publication(
            evidence or {},
            output_dir,
            expected_artifact_class=artifact_class,
            expected_registry_ref=registry_ref,
            expected_subject_digest=subject_digest,
            required_referrer_types=required_referrer_types or [],
            registry_dir=registry_dir,
            expected_record_id=record_id,
            expected_record_subject_digest=record_subject_digest,
            expected_source_repo=source_repo,
            expected_trust_root_mode=trust_root_mode,
            consumer_intent=consumer_intent,
            allow_tag_reference=allow_tag_reference,
            allow_missing_referrers=allow_missing_referrers,
            require_trust_gate=require_trust_gate,
        )
        data["evidence_path"] = str(evidence_path)
        data["evidence_container_schema"] = container_schema or None
        data["evidence_unwrapped"] = unwrapped
        data["output_dir"] = str(output_dir)
        data["registry_dir"] = str(registry_dir) if registry_dir else None
    data["version"] = _core.VERSION
    data["generated_at"] = _core.now_iso()
    data["latest"] = str(ARTIFACTS_OCI_CONSUMPTION_LATEST_PATH)
    if write_latest:
        latest_error = _core.safe_atomic_write_json(ARTIFACTS_OCI_CONSUMPTION_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(ARTIFACTS_OCI_CONSUMPTION_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_paths() -> dict[str, Any]:
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_paths_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "root": str(_core.ARTIFACTS_ROOT),
        "agent_entrypoint": str(_core.ARTIFACTS_AGENTS_PATH),
        "route_law": str(_core.ARTIFACTS_ROUTE_LAW_PATH),
        "index": str(_core.ARTIFACTS_INDEX_PATH),
        "inventory": {
            "latest": str(_core.ARTIFACTS_INVENTORY_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_INVENTORY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts inventory --scope ai-cache --json",
        },
        "trace": {
            "latest": str(_core.ARTIFACTS_TRACE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_TRACE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts trace PATH --json",
        },
        "usage": {
            "latest": str(_core.ARTIFACTS_USAGE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_USAGE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts usage PATH --json",
        },
        "timeline": {
            "latest": str(_core.ARTIFACTS_TIMELINE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_TIMELINE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts timeline PATH --json",
        },
        "snapshot": {
            "latest": str(_core.ARTIFACTS_SNAPSHOT_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_SNAPSHOT_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts snapshot --scope ai-cache --json",
        },
        "observe": {
            "latest": str(_core.ARTIFACTS_OBSERVE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_OBSERVE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts observe PATH --seconds 120 --json",
        },
        "restore_check": {
            "latest": str(_core.ARTIFACTS_RESTORE_CHECK_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_RESTORE_CHECK_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts restore-check PATH --json",
        },
        "quarantine_rehearsal": {
            "latest": str(_core.ARTIFACTS_REHEARSAL_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_REHEARSAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts quarantine-rehearsal PATH --verify-workload NAME --json",
        },
        "content_identity": {
            "latest": str(_core.ARTIFACTS_CONTENT_IDENTITY_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_CONTENT_IDENTITY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts content-identity PATH --json",
        },
        "classify": {
            "latest": str(_core.ARTIFACTS_CLASSIFY_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_CLASSIFY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts classify --scope ai-cache --json",
        },
        "bundle_registry": {
            "root": str(ARTIFACTS_BUNDLE_REGISTRY_ROOT),
            "index": str(ARTIFACTS_BUNDLE_REGISTRY_INDEX_PATH),
            "records_glob": str(ARTIFACTS_BUNDLE_REGISTRY_ROOT / artifact_bundles.BUNDLE_REGISTRY_RECORDS_DIR / "*.json"),
            "register_command": "abyss-machine artifacts bundle-register BUNDLE_DIR --lifecycle-state manually-verified --json",
            "query_command": "abyss-machine artifacts bundle-registry --artifact-class public_source_seed --json",
        },
        "artifact_subject_store": {
            "root": str(artifact_bundles.DEFAULT_ARTIFACT_SUBJECT_STORE_ROOT),
            "search_scope": artifact_bundles.artifact_subject_store_scope(),
            "materialize_command": "abyss-machine artifacts materialize-subjects BUNDLE_DIR --manifest OWNER_MANIFEST --json",
            "verify_rule": "artifact bundle verification checks signed artifact.subjects.json against this local store when the source subject path is not present",
        },
        "trust_tools": {
            "latest": str(ARTIFACTS_TRUST_TOOLS_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_TRUST_TOOLS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "proof_latest": str(ARTIFACTS_TRUST_TOOLS_PROOF_LATEST_PATH),
            "proof_daily_glob": str(ARTIFACTS_TRUST_TOOLS_PROOF_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "runtime_root": str(ARTIFACT_TRUST_RUNTIME_ROOT),
            "bin_dir": str(ARTIFACT_TRUST_BIN_DIR),
            "cache_root": str(ARTIFACT_TRUST_CACHE_ROOT),
            "command": "abyss-machine artifacts trust-tools --json",
            "proof_command": "abyss-machine artifacts trust-tools-proof --json",
            "claim_limit": "Tool discovery is not artifact-specific signature or provenance verification.",
        },
        "trust_coverage": {
            "latest": str(ARTIFACTS_TRUST_COVERAGE_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_TRUST_COVERAGE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts trust-coverage --json",
            "claim_limit": "Coverage matrix is a read-model; it does not replace artifact-specific positive/negative verification.",
        },
        "requirements": {
            "latest": str(ARTIFACTS_REQUIREMENTS_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_REQUIREMENTS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts requirements --artifact-class public_source_seed --json",
            "claim_limit": "Requirements report is a policy/read-model projection; it does not produce evidence.",
        },
        "producer_profiles": {
            "latest": str(ARTIFACTS_PRODUCER_PROFILES_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_PRODUCER_PROFILES_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts producer-profiles --artifact-class public_source_seed --json",
            "claim_limit": "Producer profiles are policy/read-model projections; they do not run owner validators or produce sidecars.",
        },
        "scenarios": {
            "latest": str(ARTIFACTS_SCENARIOS_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_SCENARIOS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts scenarios --json",
            "claim_limit": "Scenario matrix is a policy/manifests/coverage read-model; it does not build, verify, promote, or consume artifacts.",
        },
        "affected": {
            "latest": str(ARTIFACTS_AFFECTED_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_AFFECTED_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts affected --changed-path PATH --json",
            "gate_command": "abyss-machine artifacts affected --changed-path PATH --fail-on-blocking --json",
            "claim_limit": "Affected report detects declared source/profile drift; gate flags can fail closed on blocking drift or accepted sibling lag, but the command does not rebuild or consume artifacts.",
        },
        "update_lane": {
            "latest": str(ARTIFACTS_UPDATE_LANE_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_UPDATE_LANE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts update-lane --json",
            "repository_build_command": "abyss-machine artifacts update-repo-build REPOSITORY --target-file TARGET_FILE --target-path TARGET --artifact-class ARTIFACT_CLASS --key-dir KEY_DIR --json",
            "verify_command": "abyss-machine artifacts update-verify artifact.update.tuf.json --previous-trusted previous.json --registry-dir REGISTRY_DIR --subject-digest SUBJECT_DIGEST --source-repo SOURCE_REPO --trust-root-mode TRUST_ROOT_MODE --require-trust-gate --json",
            "repository_verify_command": "abyss-machine artifacts update-repo-verify REPOSITORY --target-path TARGET --trusted-root trusted-root.json --previous-trusted previous-tuf-client-state.json --registry-dir REGISTRY_DIR --artifact-class ARTIFACT_CLASS --subject-digest SUBJECT_DIGEST --source-repo SOURCE_REPO --trust-root-mode TRUST_ROOT_MODE --require-trusted-root --require-trust-gate --json",
            "scitt_verify_command": "abyss-machine artifacts scitt-verify STATEMENT.json --receipt RECEIPT.json --external-relying-party --registry-dir REGISTRY_DIR --record-id RECORD_ID --require-registry-link --statement-class release_update_artifact --artifact-digest SHA256 --issuer ISSUER --transparency-service TS --json",
            "metadata_sidecar": artifact_bundles.TUF_UPDATE_METADATA_SIDECAR,
            "claim_limit": "Update lane builds and verifies external TUF repositories for updateable targets, then still requires OS Abyss trust-gate admission; public-channel key ceremony and live SCITT service remain separate production layers.",
        },
        "oci_publication": {
            "latest": str(ARTIFACTS_OCI_PUBLICATION_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_OCI_PUBLICATION_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "layout_publish_command": "abyss-machine artifacts oci-layout-publish SUBJECT --layout-dir OCI_LAYOUT --artifact-class runtime_or_container_artifact --registry-ref REGISTRY/NAME --referrer application/vnd.dev.sigstore.bundle.v0.3+json=artifact.sigstore.json --json",
            "verify_command": "abyss-machine artifacts oci-verify OCI_PUBLICATION_EVIDENCE.json --registry-dir REGISTRY_DIR --record-id RECORD_ID --artifact-class runtime_or_container_artifact --required-referrer-type application/vnd.dev.sigstore.bundle.v0.3+json --require-trust-gate --json",
            "consume_command": "abyss-machine artifacts oci-consume OCI_PUBLICATION_EVIDENCE.json --output-dir OUTPUT --registry-dir REGISTRY_DIR --record-id RECORD_ID --artifact-class runtime_or_container_artifact --required-referrer-type application/vnd.dev.sigstore.bundle.v0.3+json --json",
            "claim_limit": "OCI publication verification checks digest-pinned subject/referrers evidence and durable trust-gate admission. The local OCI-layout producer/consumer route proves digest-pinned pull and attached referrers without claiming an external registry push.",
        },
        "oci_consumption": {
            "latest": str(ARTIFACTS_OCI_CONSUMPTION_LATEST_PATH),
            "daily_glob": str(ARTIFACTS_OCI_CONSUMPTION_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts oci-consume OCI_PUBLICATION_EVIDENCE.json --output-dir OUTPUT --registry-dir REGISTRY_DIR --record-id RECORD_ID --artifact-class runtime_or_container_artifact --json",
            "claim_limit": "OCI consumption is fail-closed by default: digest-pinned reference, required referrers, and durable trust-gate admission must pass before local OCI-layout materialization.",
        },
        "quarantine": {
            "latest": str(_core.ARTIFACTS_QUARANTINE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_QUARANTINE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts quarantine --path PATH --verify-workload NAME --json",
        },
        "validate": {
            "latest": str(_core.ARTIFACTS_VALIDATE_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_VALIDATE_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "command": "abyss-machine artifacts validate --json",
        },
        "policy": {
            "read_model": True,
            "automatic_deletion": False,
            "size_date_refs_are_insufficient_for_delete_ok": True,
            "confidence_required_for_cleanup_recommendation": True,
        },
    }


def artifact_known_specs(scope: str = "all") -> list[dict[str, Any]]:
    semantic_root = _core.AI_OPENVINO_CACHE_ROOT / "semantic-embedding-Qwen3-Embedding-0.6B-int8-ov-44a80578e6d51bf5"
    specs = [
        {
            "id": "ai_cache_gemma4",
            "path": str(_core.AI_CACHE_ROOT / "gemma4"),
            "scopes": ["all", "ai-cache"],
            "kind": "model-cache",
            "owner_guess": "abyss-machine:llm",
            "source_route": "local Gemma4 model/cache surface",
            "config_tokens": ["gemma4", "abyss-gemma4", str(_core.AI_CACHE_ROOT / "gemma4")],
            "expected_services": ["abyss-gemma4-spark-digest.timer"],
            "cleanup_posture": "quarantine-first",
            "workload_probe": "gemma4-spark",
        },
        {
            "id": "ai_openvino_dictation_server",
            "path": str(_core.AI_OPENVINO_CACHE_ROOT / "dictation-server"),
            "scopes": ["all", "ai-cache", "openvino"],
            "kind": "openvino-compile-cache",
            "owner_guess": "abyss-machine:dictation",
            "source_route": "abyss-dictation-server.service with ABYSS_OPENVINO_CACHE_DIR",
            "config_tokens": ["ABYSS_OPENVINO_CACHE_DIR", "abyss-dictation-server", "whisper-large-v3-turbo", str(_core.AI_OPENVINO_CACHE_ROOT)],
            "expected_services": ["abyss-dictation-server.service"],
            "cleanup_posture": "do-not-clean-without-controlled-dictation-test",
            "workload_probe": "dictation",
        },
        {
            "id": "ai_qwen3_reranker_model",
            "path": str(_core.AI_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov"),
            "scopes": ["all", "ai-cache"],
            "kind": "model-cache",
            "owner_guess": "abyss-machine:nervous-rerank",
            "source_route": "/etc/abyss-machine/nervous/index.json and rerank-api container route",
            "config_tokens": ["qwen3-reranker-0.6b-int8-ov", str(_core.AI_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov")],
            "expected_containers": ["rerank-api"],
            "cleanup_posture": "do-not-clean-while-rerank-route-active",
            "workload_probe": "rerank-api",
        },
        {
            "id": "ai_openvino_qwen3_reranker",
            "path": str(_core.AI_OPENVINO_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov"),
            "scopes": ["all", "ai-cache", "openvino"],
            "kind": "openvino-compile-cache",
            "owner_guess": "abyss-machine:nervous-rerank",
            "source_route": "/etc/abyss-machine/nervous/index.json cache_dir and rerank-api container route",
            "config_tokens": ["qwen3-reranker-0.6b-int8-ov", str(_core.AI_OPENVINO_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov")],
            "expected_containers": ["rerank-api"],
            "cleanup_posture": "do-not-clean-while-rerank-route-active",
            "workload_probe": "rerank-api",
        },
        {
            "id": "ai_openvino_semantic_embedding_qwen3",
            "path": str(semantic_root),
            "scopes": ["all", "ai-cache", "openvino"],
            "kind": "openvino-compile-cache",
            "owner_guess": "abyss-machine:nervous-semantic",
            "source_route": "OpenVINO embedding eval/canary cache",
            "config_tokens": ["semantic-embedding-Qwen3", "Qwen3-Embedding-0.6B", str(semantic_root)],
            "historical_ref_paths": ["/srv/abyss-machine/tmp/ai/qwen3-embedding-pooling-canary-20260515T061654Z.json"],
            "cleanup_posture": "quarantine-first",
            "workload_probe": "nervous-semantic",
        },
        {
            "id": "ai_tts_cache",
            "path": str(_core.AI_TTS_CACHE_ROOT),
            "scopes": ["all", "ai-cache"],
            "kind": "tts-cache",
            "owner_guess": "abyss-machine:tts",
            "source_route": "TTS profiles and generated OpenVINO/PyTorch artifacts",
            "config_tokens": ["abyss-tts", "qwen3_tts_openvino", str(_core.AI_TTS_CACHE_ROOT)],
            "expected_services": ["abyss-tts-server.service"],
            "cleanup_posture": "archive-candidate-after-offload",
            "workload_probe": "tts",
        },
        {
            "id": "ai_qwen36_cache",
            "path": str(_core.AI_CACHE_ROOT / "qwen3.6"),
            "scopes": ["all", "ai-cache"],
            "kind": "model-cache",
            "owner_guess": "abyss-machine:llm-archive",
            "source_route": "operator-approved full vault offload",
            "config_tokens": ["qwen3.6", str(_core.AI_CACHE_ROOT / "qwen3.6")],
            "cleanup_posture": "archive-candidate-after-offload",
            "workload_probe": "manual-restore",
        },
        {
            "id": "host_ai_runtimes",
            "path": str(_core.ABYSS_MACHINE_RUNTIME_ROOT),
            "scopes": ["all", "runtimes"],
            "kind": "runtime-layer",
            "owner_guess": "abyss-machine:runtime",
            "source_route": "host-managed AI/tool runtimes",
            "config_tokens": [str(_core.ABYSS_MACHINE_RUNTIME_ROOT), "ABYSS_AI_HOME"],
            "cleanup_posture": "review-obsolete-only",
            "workload_probe": "runtime-smoke",
        },
        {
            "id": "host_storage_layers",
            "path": str(_core.ABYSS_MACHINE_STORAGE_ROOT),
            "scopes": ["all", "storage"],
            "kind": "storage-layer",
            "owner_guess": "abyss-machine:storage",
            "source_route": "rootless Podman graphroot, host storage and local evidence",
            "config_tokens": [str(_core.ABYSS_MACHINE_STORAGE_ROOT), "rootless Podman", "containers/storage"],
            "cleanup_posture": "protected-active-storage",
            "workload_probe": "podman-preflight",
        },
    ]
    if scope in {"", "all"}:
        return specs
    return [spec for spec in specs if scope in spec.get("scopes", [])]


def artifact_spec_for_path(path: Path) -> dict[str, Any]:
    target = path.expanduser()
    best: dict[str, Any] | None = None
    best_len = -1
    for spec in artifact_known_specs("all"):
        spec_path = Path(str(spec.get("path") or ""))
        if str(target) == str(spec_path) or _core.is_relative_to_path(target, spec_path) or _core.is_relative_to_path(spec_path, target):
            length = len(str(spec_path))
            if length > best_len:
                best = spec
                best_len = length
    if best:
        return dict(best)
    return {
        "id": "path_" + _core.stable_hash_json({"path": str(target)}, length=16),
        "path": str(target),
        "scopes": ["all"],
        "kind": "unknown-artifact",
        "owner_guess": "unknown",
        "source_route": "unknown",
        "config_tokens": [str(target), target.name],
        "cleanup_posture": "unknown",
        "workload_probe": "manual",
    }


def artifact_backup_rel(path: Path) -> str | None:
    if _core.is_relative_to_path(path, _core.ABYSS_MACHINE_ROOT):
        return "srv-abyss-machine/" + str(path.relative_to(_core.ABYSS_MACHINE_ROOT))
    if _core.is_relative_to_path(path, Path("/srv")):
        return "srv-" + str(path.relative_to(Path("/srv"))).replace("/", "/")
    if _core.is_relative_to_path(path, Path.home() / "src"):
        return "home-src/" + str(path.relative_to(Path.home() / "src"))
    return None


def artifact_system_restic_covered(path: Path) -> bool:
    covered_roots = [Path("/home"), Path("/etc"), _core.STATE_DIR]
    excluded_roots = [Path("/abyss"), Path("/tmp"), Path("/var/tmp"), Path("/mnt"), Path("/media")]
    if any(_core.is_relative_to_path(path, excluded) for excluded in excluded_roots):
        return False
    return any(_core.is_relative_to_path(path, root) for root in covered_roots)


def artifact_system_restic_env() -> dict[str, str]:
    env = os.environ.copy()
    env["RESTIC_REPOSITORY"] = str(ABYSS_RESTIC_REPO)
    env["RESTIC_PASSWORD_FILE"] = str(ABYSS_RESTIC_PASSWORD_FILE)
    env["RESTIC_CACHE_DIR"] = str(ABYSS_RESTIC_CACHE_DIR)
    return env


def artifact_system_restic_base_state(path: Path) -> dict[str, Any]:
    latest_status, latest_error = _core.load_json_document(_core.BACKUP_LATEST_PATH)
    system_lane = _core.nested_get(latest_status, ["lanes", "system", "latest_success"]) if isinstance(latest_status, dict) else None
    covered = artifact_system_restic_covered(path)
    return {
        "engine": "restic",
        "covered_by_policy": covered,
        "vault_mounted": Path("/abyss").is_mount(),
        "binary": str(ABYSS_RESTIC_BIN),
        "binary_exists": ABYSS_RESTIC_BIN.exists(),
        "repo": str(ABYSS_RESTIC_REPO),
        "repo_initialized": (ABYSS_RESTIC_REPO / "config").exists(),
        "password_file_exists": ABYSS_RESTIC_PASSWORD_FILE.exists(),
        "latest_success": system_lane if isinstance(system_lane, dict) else None,
        "latest_status_load_error": latest_error,
        "restore_command": (
            f"RESTIC_REPOSITORY={shlex.quote(str(ABYSS_RESTIC_REPO))} "
            f"RESTIC_PASSWORD_FILE={shlex.quote(str(ABYSS_RESTIC_PASSWORD_FILE))} "
            f"RESTIC_CACHE_DIR={shlex.quote(str(ABYSS_RESTIC_CACHE_DIR))} "
            f"{shlex.quote(str(ABYSS_RESTIC_BIN))} restore latest --target / --include {shlex.quote(str(path))}"
            if covered else None
        ),
    }


def artifact_system_restic_inventory(path: Path, max_nodes: int = 10000, timeout: float = 30.0) -> dict[str, Any]:
    state = artifact_system_restic_base_state(path)
    if not state.get("covered_by_policy"):
        state.update({"ok": False, "reason": "path_not_covered_by_system_restic_policy", "nodes": {}})
        return state
    blockers = []
    if not state.get("vault_mounted"):
        blockers.append("vault_not_mounted")
    if not state.get("binary_exists"):
        blockers.append("restic_binary_missing")
    if not state.get("repo_initialized"):
        blockers.append("restic_repo_not_initialized")
    if not state.get("password_file_exists"):
        blockers.append("restic_password_file_missing")
    if blockers:
        state.update({"ok": False, "reason": "blocked", "blockers": blockers, "nodes": {}})
        return state
    cmd = [str(ABYSS_RESTIC_BIN), "ls", "latest", "--json", "--recursive", str(path)]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=artifact_system_restic_env(),
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        state.update({"ok": False, "reason": str(exc), "command": cmd, "nodes": {}})
        return state
    nodes: dict[str, dict[str, Any]] = {}
    snapshot: dict[str, Any] | None = None
    parse_errors = 0
    truncated = False
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if not isinstance(item, dict):
            continue
        if item.get("message_type") == "snapshot":
            snapshot = {key: item.get(key) for key in ("id", "short_id", "time", "paths", "hostname", "username")}
            continue
        if item.get("message_type") == "node" and item.get("path"):
            nodes[str(item.get("path"))] = {
                "path": item.get("path"),
                "type": item.get("type"),
                "size": item.get("size"),
                "mtime": item.get("mtime"),
                "mode": item.get("mode"),
                "permissions": item.get("permissions"),
            }
            if len(nodes) >= max_nodes:
                truncated = True
                break
    state.update({
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": cmd,
        "snapshot": snapshot,
        "node_count": len(nodes),
        "truncated": truncated,
        "parse_errors": parse_errors,
        "stderr_tail": proc.stderr[-1200:] if proc.stderr else "",
        "nodes": nodes,
    })
    return state


def artifact_backup_state(path: Path) -> dict[str, Any]:
    vault_root = Path("/abyss/Backups/heavy")
    rel = artifact_backup_rel(path)
    system_restic = artifact_system_restic_base_state(path)
    state: dict[str, Any] = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifact_backup_state_v1",
        "vault_root": str(vault_root),
        "vault_mounted": Path("/abyss").is_mount(),
        "local_to_heavy_rel": rel,
        "latest": {"path": None, "exists": False},
        "offload": {"path": None, "exists": False},
        "preserved_deleted": [],
        "system_restic": system_restic,
        "status": "not-backed-up-or-unknown",
        "restore_command": None,
    }
    if not rel:
        state["status"] = "unsupported-local-path"
        return state
    latest = vault_root / "latest" / rel
    offload = vault_root / "offloaded" / rel
    state["latest"] = {"path": str(latest), "exists": latest.exists(), "size_bytes": _core.du_size_bytes(latest, timeout=5.0) if latest.exists() else None}
    state["offload"] = {"path": str(offload), "exists": offload.exists(), "size_bytes": _core.du_size_bytes(offload, timeout=5.0) if offload.exists() else None}
    preserved_root = vault_root / "preserved-deleted"
    preserved: list[dict[str, Any]] = []
    if preserved_root.exists():
        try:
            candidates = sorted(preserved_root.iterdir(), key=lambda item: item.name, reverse=True)
        except OSError:
            candidates = []
        for run_dir in candidates[:40]:
            candidate = run_dir / rel
            if candidate.exists():
                preserved.append({
                    "run_id": run_dir.name,
                    "path": str(candidate),
                    "exists": True,
                    "size_bytes": _core.du_size_bytes(candidate, timeout=5.0),
                })
                if len(preserved) >= 5:
                    break
    state["preserved_deleted"] = preserved
    restore_source = None
    if offload.exists():
        state["status"] = "explicit-offload"
        restore_source = offload
    elif latest.exists():
        state["status"] = "heavy-latest"
        restore_source = latest
    elif preserved:
        state["status"] = "preserved-deleted"
        restore_source = Path(str(preserved[0]["path"]))
    if restore_source is not None:
        state["restore_command"] = (
            f"mkdir -p {shlex.quote(str(path.parent))} && "
            f"rsync -aHAX --info=progress2 {shlex.quote(str(restore_source))}/ {shlex.quote(str(path))}/"
        )
    return state


def artifact_path_stats(path: Path, backup: dict[str, Any]) -> dict[str, Any]:
    exists = path.exists()
    size = _core.du_size_bytes(path, timeout=5.0) if exists else None
    effective_size = size
    if effective_size is None:
        for key in ("offload", "latest"):
            candidate = backup.get(key) if isinstance(backup.get(key), dict) else {}
            if isinstance(candidate.get("size_bytes"), int):
                effective_size = candidate.get("size_bytes")
                break
    if effective_size is None:
        for candidate in backup.get("preserved_deleted", []) if isinstance(backup.get("preserved_deleted"), list) else []:
            if isinstance(candidate, dict) and isinstance(candidate.get("size_bytes"), int):
                effective_size = candidate.get("size_bytes")
                break
    return {
        "path": str(path),
        "exists": exists,
        "is_dir": path.is_dir() if exists else False,
        "is_file": path.is_file() if exists else False,
        "is_symlink": path.is_symlink(),
        "size_bytes": size,
        "effective_size_bytes": effective_size,
        "mtime": path_mtime_iso(path) if exists else None,
        "atime": path_atime_iso(path) if exists else None,
        "atime_signal": {
            "mount": "/srv" if _core.is_relative_to_path(path, Path("/srv")) else None,
            "expected_mode": "relatime" if _core.is_relative_to_path(path, Path("/srv")) else "unknown",
            "strength": "weak",
            "reason": "atime is useful context on /srv but cannot prove unused status by itself",
        },
    }


def artifact_text_matches_path(path: Path, text: str | None) -> bool:
    return _core.storage_match_path_text(str(path), text or "")


def artifact_search_tokens(path: Path, tokens: list[str]) -> list[str]:
    needles = []
    for token in [str(path), path.name, *tokens]:
        clean = str(token or "").strip()
        if clean and len(clean) >= 4 and clean not in needles:
            needles.append(clean)
    return needles


def artifact_evidence_source_kind(file_path: Path) -> str:
    text = str(file_path)
    lower = text.lower()
    name = file_path.name
    suffix = file_path.suffix.lower()
    if ".bak" in lower or lower.endswith("~") or "/backup" in lower or "pre-sync" in lower:
        return "historical_config"
    if _core.is_relative_to_path(file_path, Path.home() / ".config/systemd/user"):
        return "live_config"
    if _core.is_relative_to_path(file_path, _core.STATE_DIR):
        return "generated_history"
    if (
        suffix in {".md", ".rst", ".txt"}
        or "/decisions/" in text
        or name in {"AGENTS.md", "README.md", "CHANGELOG.md", "ROADMAP.md", "DOCS.md", "DESIGN.md", "TOPOLOGY.md", "commands.md"}
    ):
        return "docs_ref"
    if _core.is_relative_to_path(file_path, Path("/etc/abyss-machine")):
        return "source_config"
    if _core.is_relative_to_path(file_path, _core.ABYSS_MACHINE_ROOT / "tools"):
        return "source_tool"
    return "source_config"


def artifact_process_scan_ignored_pids(limit: int = 16) -> set[int]:
    ignored: set[int] = set()
    pid = os.getpid()
    for _ in range(limit):
        if pid <= 0 or pid in ignored:
            break
        ignored.add(pid)
        raw = _core.read_text(Path("/proc") / str(pid) / "stat")
        if not raw:
            break
        end = raw.rfind(")")
        if end < 0:
            break
        fields = raw[end + 2:].split()
        if len(fields) <= 1:
            break
        try:
            pid = int(fields[1])
        except ValueError:
            break
    return ignored


def artifact_process_ref_is_inspection(path: Path, comm: str, cmdline: str) -> bool:
    if not artifact_text_matches_path(path, cmdline):
        return False
    command_text = cmdline.strip()
    if "abyss-machine artifacts " in command_text:
        return True
    if comm.strip() in {"jq", "rg", "grep", "sed", "awk", "zsh", "bash", "sh"} and "artifacts " in command_text:
        return True
    return False


def artifact_process_refs(path: Path, limit: int = 40) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    fd_scan_errors = 0
    ignored_pids = artifact_process_scan_ignored_pids()
    for proc_dir in sorted(Path("/proc").glob("[0-9]*"), key=lambda item: int(item.name)):
        try:
            pid = int(proc_dir.name)
        except ValueError:
            continue
        if pid in ignored_pids:
            continue
        comm = _core.read_text(proc_dir / "comm") or ""
        cmdline = proc_cmdline(pid, max_len=500)
        if artifact_process_ref_is_inspection(path, comm, cmdline):
            continue
        sources: set[str] = set()
        if artifact_text_matches_path(path, cmdline):
            sources.add("cmdline")
        for kind in ("cwd", "root", "exe"):
            target = safe_readlink(proc_dir / kind)
            if artifact_text_matches_path(path, target):
                sources.add(kind)
        try:
            fd_entries = list((proc_dir / "fd").iterdir())[:1024]
        except OSError:
            fd_entries = []
            fd_scan_errors += 1
        for fd_entry in fd_entries:
            target = safe_readlink(fd_entry)
            if artifact_text_matches_path(path, target):
                sources.add("fd")
                break
        if sources:
            refs.append({
                "pid": pid,
                "comm": comm.strip(),
                "sources": sorted(sources),
                "cmdline": cmdline,
            })
            if len(refs) >= limit:
                break
    return {
        "active": bool(refs),
        "refs": refs,
        "ref_count": len(refs),
        "fd_scan_errors": fd_scan_errors,
        "ignored_pid_count": len(ignored_pids),
        "source": "/proc cwd/root/exe/fd/cmdline scan",
        "non_claim": "refs=0 means no accessible live process reference was observed; it is not delete permission.",
    }


def artifact_config_scan_files() -> list[Path]:
    roots = [
        Path("/etc/abyss-machine"),
        Path.home() / ".config/systemd/user",
        _core.ABYSS_MACHINE_ROOT / "tools",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for current, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                dirname for dirname in dirnames
                if dirname not in {"__pycache__", ".git"}
            ]
            dirnames.sort()
            for filename in sorted(filenames):
                candidate = Path(current) / filename
                if filename.endswith((".pyc", ".so", ".db", ".sqlite", ".png", ".jpg", ".jpeg", ".webp", ".wav")):
                    continue
                files.append(candidate)
                if len(files) >= 1500:
                    return files
    return files


def artifact_config_refs(path: Path, tokens: list[str], max_hits: int = 40) -> dict[str, Any]:
    needles = artifact_search_tokens(path, tokens)
    strong_needles = {str(path), path.name}
    live_source_kinds = {"live_config"}
    hits: list[dict[str, Any]] = []
    by_source_kind: dict[str, int] = {}
    strong_hit_count = 0
    strong_live_hit_count = 0
    strong_source_config_hit_count = 0
    active_evidence_hit_count = 0
    for file_path in artifact_config_scan_files():
        source_kind = artifact_evidence_source_kind(file_path)
        try:
            stat = file_path.stat()
            if stat.st_size > 8 * 1024 * 1024:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            matched = [needle for needle in needles if needle in line]
            if not matched:
                continue
            strong_matches = [needle for needle in matched if needle in strong_needles]
            if strong_matches:
                strong_hit_count += 1
            by_source_kind[source_kind] = by_source_kind.get(source_kind, 0) + 1
            active_evidence = source_kind in live_source_kinds
            source_config_evidence = source_kind in {"source_config", "source_tool"}
            if active_evidence:
                active_evidence_hit_count += 1
            if active_evidence and strong_matches:
                strong_live_hit_count += 1
            if source_config_evidence and strong_matches:
                strong_source_config_hit_count += 1
            if len(hits) < max_hits:
                hits.append({
                    "path": str(file_path),
                    "line": line_no,
                    "matched": matched[:4],
                    "strong_matched": strong_matches[:4],
                    "source_kind": source_kind,
                    "active_evidence": active_evidence,
                    "source_config_evidence": source_config_evidence,
                    "strength": (
                        "strong-live"
                        if active_evidence and strong_matches
                        else "strong-source"
                        if source_config_evidence and strong_matches
                        else "strong-context"
                        if strong_matches
                        else "context"
                    ),
                    "claim": (
                        "live config route evidence"
                        if active_evidence
                        else "source config reference; route context, not current live proof"
                        if source_config_evidence
                        else "non-live reference; useful context but not active-route proof"
                    ),
                })
    return {
        "hits": hits,
        "hit_count": sum(by_source_kind.values()),
        "strong_hit_count": strong_hit_count,
        "strong_live_hit_count": strong_live_hit_count,
        "strong_source_config_hit_count": strong_source_config_hit_count,
        "active_evidence_hit_count": active_evidence_hit_count,
        "by_source_kind": by_source_kind,
        "scan_roots": ["/etc/abyss-machine", str(Path.home() / ".config/systemd/user"), str(_core.ABYSS_MACHINE_ROOT / "tools")],
        "source": "split live/source/docs/history config scan",
        "non_claim": "source_config, docs_ref, historical_config, and generated_history hits do not prove current active usage by themselves.",
    }


def artifact_service_refs(spec: dict[str, Any]) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for unit in spec.get("expected_services", []) if isinstance(spec.get("expected_services"), list) else []:
        if not unit:
            continue
        state = _core.user_systemd_unit(str(unit))
        props = _core.systemd_unit_properties(str(unit), ["FragmentPath", "ExecStart", "Environment"], user=True, timeout=2.0)
        units.append({
            "unit": unit,
            "scope": "user",
            "state": state,
            "properties": props.get("properties", {}),
        })
    return {
        "active": any(item.get("state", {}).get("is_active") for item in units),
        "units": units,
        "unit_count": len(units),
    }


def artifact_container_refs(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    expected = {str(item) for item in spec.get("expected_containers", []) if item}
    matches: list[dict[str, Any]] = []
    if not _core.command_exists("podman"):
        return {"active": False, "containers": [], "error": "podman not installed"}
    ps_data, ps_error = _core.podman_json(["ps", "-a", "--format", "json"], timeout=10.0)
    if ps_error or not isinstance(ps_data, list):
        return {"active": False, "containers": [], "error": ps_error or "podman ps failed"}
    ids = [str(item.get("Id")) for item in ps_data if isinstance(item, dict) and item.get("Id")]
    inspect_data: Any = []
    if ids:
        inspect_data, _ = _core.podman_json(["inspect", *ids], timeout=20.0)
    inspected = inspect_data if isinstance(inspect_data, list) else []
    for item in inspected:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").lstrip("/")
        config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        state = item.get("State") if isinstance(item.get("State"), dict) else {}
        mounts = item.get("Mounts") if isinstance(item.get("Mounts"), list) else []
        mount_hits = []
        for mount in mounts:
            if not isinstance(mount, dict):
                continue
            source = str(mount.get("Source") or "")
            destination = str(mount.get("Destination") or "")
            if artifact_text_matches_path(path, source) or artifact_text_matches_path(path, destination):
                mount_hits.append({"source": source, "destination": destination, "mode": mount.get("Mode")})
        env_hits = [
            value for value in config.get("Env", []) if isinstance(value, str) and (str(path) in value or path.name in value)
        ]
        expected_hit = name in expected or any(token in name for token in expected)
        if mount_hits or env_hits or expected_hit:
            matches.append({
                "id": str(item.get("Id") or "")[:12],
                "name": name,
                "running": bool(state.get("Running")),
                "mount_hits": mount_hits[:8],
                "env_hits": env_hits[:8],
                "expected_name_match": expected_hit,
            })
    return {
        "active": any(item.get("running") for item in matches),
        "containers": matches[:20],
        "container_count": len(matches),
        "source": "podman inspect read-only",
    }


def artifact_historical_refs(spec: dict[str, Any]) -> dict[str, Any]:
    refs = []
    for raw_path in spec.get("historical_ref_paths", []) if isinstance(spec.get("historical_ref_paths"), list) else []:
        path = Path(str(raw_path))
        refs.append({
            "path": str(path),
            "exists": path.exists(),
            "strength": "weak",
            "reason": "tmp/canary/log evidence proves historical generation, not active route ownership",
        })
    return {"refs": refs, "ref_count": len(refs)}


def artifact_journal_units(spec: dict[str, Any]) -> list[str]:
    units = [str(item) for item in spec.get("expected_services", []) if item]
    workload = str(spec.get("workload_probe") or "")
    extra = {
        "nervous-semantic": [_core.NERVOUS_SEMANTIC_MAINTAIN_SERVICE, _core.NERVOUS_SEMANTIC_MAINTAIN_TIMER],
        "dictation": ["abyss-dictation-server.service"],
        "tts": ["abyss-tts-server.service"],
        "gemma4-spark": ["abyss-gemma4-spark-digest.service", "abyss-gemma4-spark-digest.timer"],
    }.get(workload, [])
    for unit in extra:
        if unit not in units:
            units.append(unit)
    return units


def artifact_usage_event(
    kind: str,
    source: str,
    strength: str,
    claim: str,
    *,
    time_value: str | None = None,
    path: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "kind": kind,
        "source": source,
        "strength": strength,
        "claim": claim,
    }
    if time_value:
        event["time"] = time_value
    if path:
        event["path"] = path
    if data:
        event["data"] = data
    return event


def artifact_journal_usage_refs(path: Path, spec: dict[str, Any], max_events: int = 30) -> list[dict[str, Any]]:
    if not _core.command_exists("journalctl"):
        return []
    tokens = artifact_search_tokens(path, [str(item) for item in spec.get("config_tokens", []) if item])
    events: list[dict[str, Any]] = []
    for unit in artifact_journal_units(spec):
        out = _core.run(["journalctl", "--user", "-u", unit, "-n", "300", "--no-pager", "-o", "short-iso"], timeout=4.0)
        if not out.get("ok"):
            continue
        for line in str(out.get("stdout") or "").splitlines():
            matched = [token for token in tokens if token in line]
            if not matched:
                continue
            line_time = line.split(maxsplit=1)[0] if line.split(maxsplit=1) else None
            events.append(artifact_usage_event(
                "journal_match",
                "systemd-user-journal",
                "historical-live-log",
                "journal line from a route unit mentions this artifact or model token",
                time_value=line_time,
                data={
                    "unit": unit,
                    "matched": matched[:4],
                    "line": line[-500:],
                },
            ))
            if len(events) >= max_events:
                return events
    return events


def artifact_podman_log_usage_refs(path: Path, spec: dict[str, Any], container_refs: dict[str, Any], max_events: int = 20) -> list[dict[str, Any]]:
    if not _core.command_exists("podman"):
        return []
    tokens = artifact_search_tokens(path, [str(item) for item in spec.get("config_tokens", []) if item])
    events: list[dict[str, Any]] = []
    containers = container_refs.get("containers") if isinstance(container_refs.get("containers"), list) else []
    for container in containers[:8]:
        if not isinstance(container, dict):
            continue
        name = str(container.get("name") or container.get("id") or "")
        if not name:
            continue
        out = _core.run(["podman", "logs", "--since", "30d", "--tail", "300", name], timeout=5.0)
        if not out.get("ok"):
            continue
        for line in str(out.get("stdout") or "").splitlines():
            matched = [token for token in tokens if token in line]
            if not matched:
                continue
            events.append(artifact_usage_event(
                "podman_log_match",
                "podman-logs",
                "historical-container-log",
                "container log line mentions this artifact or model token",
                data={
                    "container": name,
                    "matched": matched[:4],
                    "line": line[-500:],
                },
            ))
            if len(events) >= max_events:
                return events
    return events


def artifact_generated_usage_paths(spec: dict[str, Any]) -> list[Path]:
    paths = [
        _core.BACKUP_LATEST_PATH,
        _core.PROCESS_LATEST_PATH,
        _core.PROCESS_CONTAINER_LATEST_PATH,
        _core.STORAGE_INVENTORY_LATEST_PATH,
        _core.STORAGE_PRESSURE_LATEST_PATH,
        _core.STORAGE_CLEANUP_PLAN_LATEST_PATH,
        _core.AI_STORAGE_LATEST_PATH,
        _core.AI_LLM_REGISTRY_LATEST_PATH,
        _core.AI_LLM_RESIDENT_AUDIT_LATEST_PATH,
        _core.AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH,
        _core.AI_LLM_RESIDENT_EVALS_LATEST_PATH,
        _core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH,
        _core.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH,
        _core.NERVOUS_SEMANTIC_EVAL_LATEST_PATH,
        _core.NERVOUS_RERANK_LATEST_PATH,
        _core.NERVOUS_RERANK_EVAL_LATEST_PATH,
        _core.DICTATION_TRANSCRIPT_LATEST_PATH,
        _core.AI_TTS_LATEST_PATH,
        ai_cli.AI_TTS_INVENTORY_LATEST_PATH,
        _core.AI_TTS_SERVER_LATEST_PATH,
        _core.ARTIFACTS_INVENTORY_LATEST_PATH,
        _core.ARTIFACTS_TRACE_LATEST_PATH,
        _core.ARTIFACTS_CLASSIFY_LATEST_PATH,
        _core.ARTIFACTS_QUARANTINE_LATEST_PATH,
    ]
    workload = str(spec.get("workload_probe") or "")
    if workload == "nervous-semantic":
        paths.extend([
            _core.ai_daily_jsonl_path(_core.NERVOUS_SEMANTIC_MAINTAIN_ROOT),
            _core.ai_daily_jsonl_path(_core.NERVOUS_SEMANTIC_EVAL_ROOT),
        ])
    if workload in {"rerank-api", "nervous-semantic"}:
        paths.extend([_core.ai_daily_jsonl_path(_core.NERVOUS_RERANK_EVAL_ROOT)])
    paths.extend([
        _core.ai_daily_jsonl_path(_core.ARTIFACTS_INVENTORY_ROOT),
        _core.ai_daily_jsonl_path(_core.ARTIFACTS_TRACE_ROOT),
        _core.ai_daily_jsonl_path(_core.ARTIFACTS_CLASSIFY_ROOT),
        _core.ai_daily_jsonl_path(_core.ARTIFACTS_QUARANTINE_ROOT),
    ])
    unique: list[Path] = []
    for candidate in paths:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def artifact_generated_usage_refs(path: Path, spec: dict[str, Any], max_events: int = 30) -> list[dict[str, Any]]:
    tokens = artifact_search_tokens(path, [str(item) for item in spec.get("config_tokens", []) if item])
    events: list[dict[str, Any]] = []
    for file_path in artifact_generated_usage_paths(spec):
        try:
            stat = file_path.stat()
            if stat.st_size > 8 * 1024 * 1024:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matched = [token for token in tokens if token in text]
        if not matched:
            continue
        time_value = path_mtime_iso(file_path)
        if file_path.suffix == ".json":
            loaded, _ = _core.load_json_document(file_path)
            if isinstance(loaded, dict):
                time_value = str(loaded.get("generated_at") or loaded.get("created_at") or time_value)
        preview = ""
        for raw_line in text.splitlines():
            if any(token in raw_line for token in matched):
                preview = raw_line[-500:]
                if raw_line.lstrip().startswith("{"):
                    try:
                        loaded_line = json.loads(raw_line)
                    except json.JSONDecodeError:
                        loaded_line = None
                    if isinstance(loaded_line, dict):
                        time_value = str(loaded_line.get("generated_at") or loaded_line.get("created_at") or time_value)
                break
        events.append(artifact_usage_event(
            "generated_history_match",
            "abyss-machine-generated-readmodel",
            "context",
            "generated latest/history mentions this artifact; this proves prior observation, not current active need",
            time_value=time_value,
            path=str(file_path),
            data={
                "matched": matched[:4],
                "preview": preview,
            },
        ))
        if len(events) >= max_events:
            break
    return events


def artifact_backup_usage_refs(backup: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if backup.get("vault_mounted"):
        events.append(artifact_usage_event(
            "vault_state",
            "vault-mount",
            "context",
            "vault mount was visible during this evidence scan",
            time_value=_core.now_iso(),
            path=str(Path("/abyss")),
        ))
    for key in ("latest", "offload"):
        item = backup.get(key) if isinstance(backup.get(key), dict) else {}
        if not item.get("exists"):
            continue
        candidate = Path(str(item.get("path") or ""))
        events.append(artifact_usage_event(
            f"backup_{key}",
            "abyss-vault-heavy",
            "restore",
            f"artifact has a vault {key} restore source",
            time_value=path_mtime_iso(candidate),
            path=str(candidate),
            data={"size_bytes": item.get("size_bytes")},
        ))
    for item in backup.get("preserved_deleted", []) if isinstance(backup.get("preserved_deleted"), list) else []:
        if not isinstance(item, dict) or not item.get("exists"):
            continue
        candidate = Path(str(item.get("path") or ""))
        events.append(artifact_usage_event(
            "backup_preserved_deleted",
            "abyss-vault-heavy",
            "restore",
            "artifact has a preserved-deleted restore source",
            time_value=path_mtime_iso(candidate),
            path=str(candidate),
            data={"run_id": item.get("run_id"), "size_bytes": item.get("size_bytes")},
        ))
    return events


def artifact_usage_events(record: dict[str, Any], spec: dict[str, Any], max_events: int = 160) -> list[dict[str, Any]]:
    path = Path(str(record.get("path") or spec.get("path") or "")).expanduser()
    events: list[dict[str, Any]] = []
    path_state = record.get("path_state") if isinstance(record.get("path_state"), dict) else {}
    if path_state.get("exists"):
        events.append(artifact_usage_event(
            "filesystem_state",
            "filesystem-stat",
            "weak",
            "local path exists; mtime/atime are weak context and never prove unused status",
            time_value=str(path_state.get("mtime") or ""),
            path=str(path),
            data={
                "size_bytes": path_state.get("size_bytes"),
                "atime": path_state.get("atime"),
                "atime_signal": path_state.get("atime_signal"),
            },
        ))
    process_refs = record.get("process_refs") if isinstance(record.get("process_refs"), dict) else {}
    for ref in process_refs.get("refs", []) if isinstance(process_refs.get("refs"), list) else []:
        if not isinstance(ref, dict):
            continue
        events.append(artifact_usage_event(
            "process_ref",
            "/proc",
            "live",
            "current process references the artifact path",
            time_value=record.get("generated_at"),
            data={
                "pid": ref.get("pid"),
                "comm": ref.get("comm"),
                "sources": ref.get("sources"),
                "cmdline": ref.get("cmdline"),
            },
        ))
    service_refs = record.get("service_refs") if isinstance(record.get("service_refs"), dict) else {}
    for unit in service_refs.get("units", []) if isinstance(service_refs.get("units"), list) else []:
        if not isinstance(unit, dict):
            continue
        state = unit.get("state") if isinstance(unit.get("state"), dict) else {}
        active = bool(state.get("is_active"))
        events.append(artifact_usage_event(
            "service_state",
            "systemd-user",
            "live" if active else "context",
            "user service route is active now" if active else "user service route exists or was inspected but is not active now",
            time_value=record.get("generated_at"),
            data={
                "unit": unit.get("unit"),
                "active": active,
                "state": state,
                "properties": unit.get("properties"),
            },
        ))
    container_refs = record.get("container_refs") if isinstance(record.get("container_refs"), dict) else {}
    for container in container_refs.get("containers", []) if isinstance(container_refs.get("containers"), list) else []:
        if not isinstance(container, dict):
            continue
        running = bool(container.get("running"))
        events.append(artifact_usage_event(
            "container_state",
            "podman-inspect",
            "live" if running else "context",
            "podman container route is running now" if running else "podman container route exists but is not running now",
            time_value=record.get("generated_at"),
            data=container,
        ))
    config_refs = record.get("config_refs") if isinstance(record.get("config_refs"), dict) else {}
    for hit in config_refs.get("hits", []) if isinstance(config_refs.get("hits"), list) else []:
        if not isinstance(hit, dict):
            continue
        source_kind = str(hit.get("source_kind") or "unknown")
        active = bool(hit.get("active_evidence"))
        events.append(artifact_usage_event(
            "config_ref",
            source_kind,
            str(hit.get("strength") or ("strong-live" if active and hit.get("strong_matched") else "context")),
            "live config mentions this artifact" if active else str(hit.get("claim") or "non-live config/doc/history reference mentions this artifact"),
            path=str(hit.get("path") or ""),
            data=hit,
        ))
    historical_refs = record.get("historical_refs") if isinstance(record.get("historical_refs"), dict) else {}
    for ref in historical_refs.get("refs", []) if isinstance(historical_refs.get("refs"), list) else []:
        if not isinstance(ref, dict) or not ref.get("exists"):
            continue
        events.append(artifact_usage_event(
            "historical_ref",
            "declared-historical-ref",
            "weak",
            "declared canary/tmp/log reference proves historical generation only",
            time_value=path_mtime_iso(Path(str(ref.get("path") or ""))),
            path=str(ref.get("path") or ""),
            data=ref,
        ))
    events.extend(artifact_journal_usage_refs(path, spec))
    events.extend(artifact_podman_log_usage_refs(path, spec, container_refs))
    events.extend(artifact_generated_usage_refs(path, spec))
    backup = record.get("backup_state") if isinstance(record.get("backup_state"), dict) else {}
    events.extend(artifact_backup_usage_refs(backup))
    events.sort(key=lambda event: str(event.get("time") or ""), reverse=True)
    return events[:max_events]


def artifact_usage_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for event in events:
        by_kind[str(event.get("kind") or "unknown")] = by_kind.get(str(event.get("kind") or "unknown"), 0) + 1
        by_source[str(event.get("source") or "unknown")] = by_source.get(str(event.get("source") or "unknown"), 0) + 1

    def first_event(kinds: set[str], strengths: set[str] | None = None) -> dict[str, Any] | None:
        for event in events:
            if str(event.get("kind") or "") in kinds:
                if strengths is not None and str(event.get("strength") or "") not in strengths:
                    continue
                return event
        return None

    return {
        "event_count": len(events),
        "by_kind": by_kind,
        "by_source": by_source,
        "current_live_event_count": sum(1 for event in events if event.get("strength") == "live"),
        "strong_live_config_event_count": sum(1 for event in events if event.get("strength") == "strong-live"),
        "historical_route_log_event_count": sum(1 for event in events if event.get("kind") in {"journal_match", "podman_log_match"}),
        "generated_history_event_count": sum(1 for event in events if event.get("kind") == "generated_history_match"),
        "backup_restore_event_count": sum(1 for event in events if str(event.get("kind") or "").startswith("backup_")),
        "last_current_live_event": first_event({"process_ref", "service_state", "container_state"}, {"live"}),
        "last_historical_route_log_event": first_event({"journal_match", "podman_log_match"}),
        "last_backup_restore_event": first_event({"backup_latest", "backup_offload", "backup_preserved_deleted"}),
        "delete_ok": False,
        "non_claim": "A timeline can prove observed use and restore routes; it cannot prove future non-use or grant deletion.",
    }


def artifact_real_probe(record: dict[str, Any]) -> dict[str, Any]:
    workload = str(record.get("workload_probe") or "manual")
    if workload == "nervous-semantic":
        return {
            "workload": workload,
            "probe_type": "bounded-semantic-rebuild-after-quarantine",
            "proves": "semantic embedding route can rebuild/use the model after the local compile cache is quarantined",
            "commands": [
                "abyss-machine nervous semantic-status --json",
                "abyss-machine nervous semantic-build --max-chunks 8 --batch-size 1 --device CPU --rebuild --json",
                "abyss-machine nervous semantic-status --json",
            ],
            "insufficient_commands": [
                "abyss-machine nervous semantic-status --json",
                "abyss-machine nervous semantic-maintain --dry-run --json",
                "abyss-machine nervous semantic-search --query TEXT --json",
            ],
            "non_claim": "status, search, and dry-run do not prove compile-cache rebuild safety.",
        }
    probes = {
        "dictation": {
            "probe_type": "dictation-route-smoke-after-quarantine",
            "commands": ["systemctl --user restart abyss-dictation-server.service", "abyss-machine dictation status --json"],
            "proves": "dictation route starts and reports healthy after cache quarantine",
        },
        "rerank-api": {
            "probe_type": "rerank-container-route-smoke",
            "commands": ["abyss-machine processes containers --json"],
            "proves": "rerank-api container route remains present and healthy after quarantine",
        },
        "tts": {
            "probe_type": "tts-route-smoke-after-quarantine",
            "commands": ["systemctl --user restart abyss-tts-server.service", "abyss-machine ai tts status --json"],
            "proves": "TTS server route starts and reports healthy after cache quarantine",
        },
        "gemma4-spark": {
            "probe_type": "gemma4-spark-route-smoke",
            "commands": ["systemctl --user start abyss-gemma4-spark-digest.service", "abyss-machine ai llm resident status --json"],
            "proves": "Gemma4 Spark scheduled route can run after quarantine",
        },
        "manual-restore": {
            "probe_type": "manual-restore-check",
            "commands": ["use record.backup_state.restore_command if the operator chooses to restore"],
            "proves": "operator can restore the offloaded artifact back to its original path",
        },
    }
    data = probes.get(workload, {
        "probe_type": "manual-route-specific-probe",
        "commands": ["operator-defined workload probe required"],
        "proves": "unknown route requires operator-defined proof",
    })
    return {"workload": workload, **data}


def artifact_decision(record: dict[str, Any]) -> dict[str, Any]:
    process_refs = record.get("process_refs") if isinstance(record.get("process_refs"), dict) else {}
    service_refs = record.get("service_refs") if isinstance(record.get("service_refs"), dict) else {}
    container_refs = record.get("container_refs") if isinstance(record.get("container_refs"), dict) else {}
    config_refs = record.get("config_refs") if isinstance(record.get("config_refs"), dict) else {}
    backup = record.get("backup_state") if isinstance(record.get("backup_state"), dict) else {}
    path_state = record.get("path_state") if isinstance(record.get("path_state"), dict) else {}
    protection = record.get("protection") if isinstance(record.get("protection"), dict) else {}
    if protection.get("decision") == "deny":
        return {
            "classification": "protected",
            "decision": "do-not-touch-from-abyss-machine",
            "confidence": "high",
            "reasons": ["protected_path"],
        }
    if process_refs.get("active"):
        return {
            "classification": "hot",
            "decision": "keep-hot",
            "confidence": "high",
            "reasons": ["active_process_reference"],
        }
    if service_refs.get("active") or container_refs.get("active"):
        reasons = []
        if service_refs.get("active"):
            reasons.append("active_service_route")
        if container_refs.get("active"):
            reasons.append("active_container_route")
        return {
            "classification": "active-route",
            "decision": "do-not-clean-without-controlled-workload-test",
            "confidence": "high",
            "reasons": reasons,
        }
    if not path_state.get("exists") and backup.get("status") in {"explicit-offload", "preserved-deleted", "heavy-latest"}:
        return {
            "classification": "archive-candidate",
            "decision": "local-absent-restore-from-vault-if-needed",
            "confidence": "high",
            "reasons": ["local_absent", f"backup_state:{backup.get('status')}"],
        }
    if _core.safe_int(config_refs.get("strong_live_hit_count"), 0) > 0:
        return {
            "classification": "active-route",
            "decision": "quarantine-only-after-route-specific-test",
            "confidence": "medium",
            "reasons": ["strong_live_config_reference"],
        }
    if backup.get("status") in {"explicit-offload", "heavy-latest", "preserved-deleted"}:
        return {
            "classification": "quarantine-first",
            "decision": "controlled-quarantine-plus-workload-probe-before-removal",
            "confidence": "medium",
            "reasons": ["backup_state_known", "no_active_refs_observed", "no_live_route_ref_found"],
        }
    if record.get("kind") in {"openvino-compile-cache", "model-cache"}:
        return {
            "classification": "regenerable",
            "decision": "not-delete-ok-without-backup-or-workload-proof",
            "confidence": "low",
            "reasons": ["cache_like", "backup_state_unknown"],
        }
    return {
        "classification": "unknown",
        "decision": "manual-review-required",
        "confidence": "low",
        "reasons": ["insufficient_evidence"],
    }


def artifact_record_for_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(spec.get("path") or "")).expanduser()
    backup = artifact_backup_state(path)
    record = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifact_record_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "id": str(spec.get("id") or "path_" + _core.stable_hash_json({"path": str(path)}, length=16)),
        "path": str(path),
        "kind": spec.get("kind") or "unknown-artifact",
        "owner_guess": spec.get("owner_guess") or "unknown",
        "source_route": spec.get("source_route") or "unknown",
        "cleanup_posture": spec.get("cleanup_posture") or "unknown",
        "workload_probe": spec.get("workload_probe") or "manual",
        "path_state": artifact_path_stats(path, backup),
        "protection": _core.storage_path_protection(path),
        "process_refs": artifact_process_refs(path),
        "service_refs": artifact_service_refs(spec),
        "container_refs": artifact_container_refs(path, spec),
        "config_refs": artifact_config_refs(path, [str(item) for item in spec.get("config_tokens", []) if item]),
        "historical_refs": artifact_historical_refs(spec),
        "backup_state": backup,
        "evidence_strength": {
            "strong": ["active process refs", "active service/container route", "live config refs", "verified backup state"],
            "weak": ["mtime", "atime", "size", "tmp/canary/log traces", "refs=0 by itself"],
            "insufficient_alone": ["old date", "large size", "no open fd", "name looks obsolete"],
        },
        "policy": {
            "facts_only": True,
            "automatic_deletion": False,
            "delete_ok_requires_explicit_operator_action": True,
            "date_size_or_refs_alone_never_delete_ok": True,
        },
    }
    record["decision"] = artifact_decision(record)
    record["classification"] = record["decision"]["classification"]
    record["confidence"] = record["decision"]["confidence"]
    return record


def artifacts_inventory(scope: str = "all", write_latest: bool = True, with_usage: bool = False) -> dict[str, Any]:
    records = [artifact_record_for_spec(spec) for spec in artifact_known_specs(scope)]
    specs_by_id = {str(spec.get("id")): spec for spec in artifact_known_specs(scope)}
    if with_usage:
        for record in records:
            spec = specs_by_id.get(str(record.get("id"))) or artifact_spec_for_path(Path(str(record.get("path") or "")))
            events = artifact_usage_events(record, spec, max_events=80)
            record["usage_summary"] = artifact_usage_summary(events)
    by_class: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for record in records:
        by_class[str(record.get("classification") or "unknown")] = by_class.get(str(record.get("classification") or "unknown"), 0) + 1
        by_confidence[str(record.get("confidence") or "unknown")] = by_confidence.get(str(record.get("confidence") or "unknown"), 0) + 1
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_inventory_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "scope": scope,
        "with_usage": with_usage,
        "paths": {
            "latest": str(_core.ARTIFACTS_INVENTORY_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_INVENTORY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "index": str(_core.ARTIFACTS_INDEX_PATH),
        },
        "summary": {
            "records": len(records),
            "existing_local": sum(1 for item in records if item.get("path_state", {}).get("exists")),
            "backed_by_latest": sum(1 for item in records if item.get("backup_state", {}).get("latest", {}).get("exists")),
            "backed_by_offload": sum(1 for item in records if item.get("backup_state", {}).get("offload", {}).get("exists")),
            "backed_by_preserved_deleted": sum(1 for item in records if item.get("backup_state", {}).get("preserved_deleted")),
            "by_classification": by_class,
            "by_confidence": by_confidence,
        },
        "records": records,
        "policy": {
            "facts_only": True,
            "automatic_deletion": False,
            "confidence_required": True,
            "cleanup_classes": ["hot", "active-route", "archive-candidate", "quarantine-first", "regenerable", "protected", "unknown"],
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INVENTORY_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_INVENTORY_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_trace(path: str, write_latest: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    spec = artifact_spec_for_path(target)
    record = artifact_record_for_spec(spec)
    usage_events = artifact_usage_events(record, spec, max_events=120)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_trace_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "path": str(target),
        "matched_spec_id": record.get("id"),
        "record": record,
        "trace": {
            "process_refs": record.get("process_refs"),
            "service_refs": record.get("service_refs"),
            "container_refs": record.get("container_refs"),
            "config_refs": record.get("config_refs"),
            "historical_refs": record.get("historical_refs"),
            "backup_state": record.get("backup_state"),
        },
        "decision": record.get("decision"),
        "usage_summary": artifact_usage_summary(usage_events),
        "non_claims": [
            "This trace is current evidence, not a future guarantee.",
            "A clear process scan does not prove an artifact will never be needed.",
            "Cleanup decisions require controlled workload proof or explicit operator approval.",
        ],
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_TRACE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_TRACE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_usage(path: str, write_latest: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    spec = artifact_spec_for_path(target)
    record = artifact_record_for_spec(spec)
    events = artifact_usage_events(record, spec)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_usage_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "path": str(target),
        "matched_spec_id": record.get("id"),
        "record": record,
        "summary": artifact_usage_summary(events),
        "real_probe": artifact_real_probe(record),
        "events": events,
        "policy": {
            "facts_only": True,
            "automatic_deletion": False,
            "timeline_does_not_prove_future_nonuse": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_USAGE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_USAGE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_timeline(path: str, write_latest: bool = True) -> dict[str, Any]:
    usage = artifacts_usage(path, write_latest=False)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_timeline_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": bool(usage.get("ok")),
        "path": usage.get("path"),
        "matched_spec_id": usage.get("matched_spec_id"),
        "summary": usage.get("summary"),
        "timeline": usage.get("events", []),
        "real_probe": usage.get("real_probe"),
        "decision": usage.get("record", {}).get("decision") if isinstance(usage.get("record"), dict) else None,
        "policy": usage.get("policy"),
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_TIMELINE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_TIMELINE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifact_snapshot_jsonl_paths(days: int = 14) -> list[Path]:
    today = dt.datetime.now(dt.timezone.utc).astimezone()
    paths: list[Path] = []
    for offset in range(max(1, min(int(days), 366))):
        value = today - dt.timedelta(days=offset)
        paths.append(_core.ARTIFACTS_SNAPSHOT_ROOT / f"{value.year:04d}" / f"{value.month:02d}" / f"{value.strftime('%Y-%m-%d')}.jsonl")
    return paths


def artifact_snapshot_history_summary(current_records: list[dict[str, Any]], days: int = 14) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in current_records:
        artifact_id = str(record.get("id") or "")
        if artifact_id:
            by_id.setdefault(artifact_id, {
                "id": artifact_id,
                "snapshots": 0,
                "current_live_snapshots": 0,
                "last_current_live_event": None,
                "last_snapshot_at": None,
            })

    def ingest(snapshot: dict[str, Any]) -> None:
        generated_at = str(snapshot.get("generated_at") or "")
        for item in snapshot.get("records", []) if isinstance(snapshot.get("records"), list) else []:
            if not isinstance(item, dict):
                continue
            artifact_id = str(item.get("id") or "")
            if not artifact_id:
                continue
            target = by_id.setdefault(artifact_id, {
                "id": artifact_id,
                "snapshots": 0,
                "current_live_snapshots": 0,
                "last_current_live_event": None,
                "last_snapshot_at": None,
            })
            target["snapshots"] = int(target.get("snapshots") or 0) + 1
            if generated_at and str(target.get("last_snapshot_at") or "") < generated_at:
                target["last_snapshot_at"] = generated_at
            summary = item.get("usage_summary") if isinstance(item.get("usage_summary"), dict) else {}
            if _core.safe_int(summary.get("current_live_event_count"), 0) > 0:
                target["current_live_snapshots"] = int(target.get("current_live_snapshots") or 0) + 1
                live = summary.get("last_current_live_event") if isinstance(summary.get("last_current_live_event"), dict) else None
                if live and str((target.get("last_current_live_event") or {}).get("time") or "") < str(live.get("time") or ""):
                    target["last_current_live_event"] = live

    for path in artifact_snapshot_jsonl_paths(days):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines[-200:]:
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                ingest(parsed)
    ingest({"generated_at": _core.now_iso(), "records": current_records})
    return {
        "window_days": max(1, min(int(days), 366)),
        "artifacts": list(by_id.values()),
        "no_current_live_in_window": [
            artifact_id for artifact_id, item in by_id.items()
            if int(item.get("snapshots") or 0) > 0 and int(item.get("current_live_snapshots") or 0) == 0
        ],
        "non_claim": "Snapshot history proves observed samples only; it cannot prove future non-use.",
    }


def artifacts_snapshot(scope: str = "all", history_days: int = 14, write_latest: bool = True) -> dict[str, Any]:
    specs = artifact_known_specs(scope)
    records: list[dict[str, Any]] = []
    by_class: dict[str, int] = {}
    for spec in specs:
        record = artifact_record_for_spec(spec)
        events = artifact_usage_events(record, spec, max_events=160)
        summary = artifact_usage_summary(events)
        item = {
            "id": record.get("id"),
            "path": record.get("path"),
            "kind": record.get("kind"),
            "classification": record.get("classification"),
            "confidence": record.get("confidence"),
            "decision": record.get("decision"),
            "path_state": record.get("path_state"),
            "process_refs": record.get("process_refs"),
            "service_refs": record.get("service_refs"),
            "container_refs": record.get("container_refs"),
            "config_refs": record.get("config_refs"),
            "historical_refs": record.get("historical_refs"),
            "backup_state": record.get("backup_state"),
            "usage_summary": summary,
            "usage_events": events,
        }
        records.append(item)
        by_class[str(record.get("classification") or "unknown")] = by_class.get(str(record.get("classification") or "unknown"), 0) + 1
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_snapshot_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "scope": scope,
        "summary": {
            "records": len(records),
            "by_classification": by_class,
            "current_live_records": sum(1 for item in records if _core.safe_int((item.get("usage_summary") or {}).get("current_live_event_count"), 0) > 0),
            "backed_records": sum(1 for item in records if (item.get("backup_state") or {}).get("status") in {"explicit-offload", "heavy-latest", "preserved-deleted"}),
        },
        "history_summary": artifact_snapshot_history_summary(records, days=history_days),
        "records": records,
        "paths": {
            "latest": str(_core.ARTIFACTS_SNAPSHOT_LATEST_PATH),
            "daily_glob": str(_core.ARTIFACTS_SNAPSHOT_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "policy": {
            "facts_only": True,
            "automatic_deletion": False,
            "snapshot_history_is_observed_samples_not_future_nonuse": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_SNAPSHOT_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_SNAPSHOT_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifact_inotify_start(path: Path, recursive: bool) -> tuple[subprocess.Popen[str] | None, dict[str, Any]]:
    if not _core.command_exists("inotifywait"):
        return None, {"available": False, "reason": "inotifywait not installed"}
    if not path.exists():
        return None, {"available": False, "reason": "path does not exist"}
    cmd = ["inotifywait", "-q", "-m", "-e", "open,access,modify,create,delete,move"]
    if recursive and path.is_dir():
        cmd.append("-r")
    cmd.append(str(path))
    try:
        proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return None, {"available": False, "reason": str(exc), "command": cmd}
    return proc, {"available": True, "recursive": bool(recursive), "command": cmd}


def artifacts_observe(path: str, seconds: float = 120.0, interval: float = 1.0, recursive: bool = False, write_latest: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    duration = max(0.0, min(float(seconds), 3600.0))
    sample_interval = max(0.1, min(float(interval), 60.0))
    started = _core.now_iso()
    started_monotonic = time.monotonic()
    spec = artifact_spec_for_path(target)
    initial_usage = artifacts_usage(str(target), write_latest=False)
    inotify_proc, inotify_status = artifact_inotify_start(target, recursive=recursive)
    samples: list[dict[str, Any]] = []
    try:
        while True:
            process_refs = artifact_process_refs(target)
            samples.append({
                "time": _core.now_iso(),
                "process_refs": process_refs,
                "live_ref_count": process_refs.get("ref_count"),
            })
            if time.monotonic() - started_monotonic >= duration:
                break
            time.sleep(min(sample_interval, max(0.0, duration - (time.monotonic() - started_monotonic))))
            if duration <= 0:
                break
    finally:
        stdout = ""
        stderr = ""
        if inotify_proc is not None:
            try:
                inotify_proc.terminate()
                stdout, stderr = inotify_proc.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                inotify_proc.kill()
                stdout, stderr = inotify_proc.communicate(timeout=2.0)
            inotify_status["returncode"] = inotify_proc.returncode
            inotify_status["events"] = [
                line for line in stdout.splitlines()
                if line.strip() and not artifact_process_ref_is_inspection(target, "inotifywait", line)
            ][:200]
            if stderr.strip():
                inotify_status["stderr_tail"] = stderr[-1200:]
    final_usage = artifacts_usage(str(target), write_latest=False)
    observed_process_samples = [
        sample for sample in samples
        if _core.safe_int(sample.get("live_ref_count"), 0) > 0
    ]
    inotify_events = inotify_status.get("events") if isinstance(inotify_status.get("events"), list) else []
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_observe_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "path": str(target),
        "matched_spec_id": spec.get("id"),
        "seconds_requested": seconds,
        "seconds_observed": round(time.monotonic() - started_monotonic, 3),
        "started_at": started,
        "finished_at": _core.now_iso(),
        "initial_usage_summary": initial_usage.get("summary"),
        "final_usage_summary": final_usage.get("summary"),
        "samples": samples,
        "inotify": inotify_status,
        "summary": {
            "sample_count": len(samples),
            "process_access_observed": bool(observed_process_samples),
            "inotify_access_observed": bool(inotify_events),
            "access_observed": bool(observed_process_samples or inotify_events),
            "observed_process_sample_count": len(observed_process_samples),
            "inotify_event_count": len(inotify_events),
        },
        "policy": {
            "facts_only": True,
            "automatic_deletion": False,
            "observe_window_does_not_prove_future_nonuse": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_OBSERVE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_OBSERVE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifact_restore_source(backup: dict[str, Any]) -> tuple[str | None, Path | None]:
    for key in ("offload", "latest"):
        item = backup.get(key) if isinstance(backup.get(key), dict) else {}
        if item.get("exists") and item.get("path"):
            return key, Path(str(item.get("path")))
    for item in backup.get("preserved_deleted", []) if isinstance(backup.get("preserved_deleted"), list) else []:
        if isinstance(item, dict) and item.get("exists") and item.get("path"):
            return "preserved_deleted", Path(str(item.get("path")))
    return None, None


def artifact_restore_sample_files(source: Path, max_files: int = 8, hash_limit_bytes: int = 64 * 1024 * 1024) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if source.is_file():
        candidates = [source]
        root = source.parent
    else:
        root = source
        candidates = []
        try:
            for current, dirnames, filenames in os.walk(source):
                dirnames.sort()
                for filename in sorted(filenames):
                    candidates.append(Path(current) / filename)
                    if len(candidates) >= max_files:
                        break
                if len(candidates) >= max_files:
                    break
        except OSError:
            candidates = []
    for candidate in candidates[:max_files]:
        item: dict[str, Any] = {
            "path": str(candidate),
            "rel": str(candidate.relative_to(root)) if _core.is_relative_to_path(candidate, root) else candidate.name,
        }
        try:
            stat = candidate.stat()
            item.update({
                "size_bytes": stat.st_size,
                "mode": oct(stat.st_mode & 0o7777),
                "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
                "readable": os.access(candidate, os.R_OK),
            })
            if stat.st_size <= hash_limit_bytes:
                item["sha256"] = _core.sha256_path(candidate)
            else:
                item["sha256"] = None
                item["hash_skipped_reason"] = f"file larger than {hash_limit_bytes} bytes"
        except OSError as exc:
            item["error"] = str(exc)
        files.append(item)
    return files


def artifacts_restore_check(path: str, write_latest: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    spec = artifact_spec_for_path(target)
    record = artifact_record_for_spec(spec)
    backup = record.get("backup_state") if isinstance(record.get("backup_state"), dict) else {}
    source_kind, source = artifact_restore_source(backup)
    restic_inventory = artifact_system_restic_inventory(target, max_nodes=32, timeout=20.0) if source is None else None
    restic_node = (
        (restic_inventory.get("nodes") or {}).get(str(target))
        if isinstance(restic_inventory, dict) and isinstance(restic_inventory.get("nodes"), dict)
        else None
    )
    if source is None and restic_node:
        source_kind = "system_restic_latest"
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"level": level, "key": key, "message": message}
        if details is not None:
            item["details"] = details
        checks.append(item)

    add("ok" if backup.get("vault_mounted") else "fail", "vault_mounted", "vault is mounted" if backup.get("vault_mounted") else "vault is not mounted")
    add(
        "ok" if source is not None or restic_node else "fail",
        "restore_source_selected",
        "restore source selected" if source is not None or restic_node else "no restore source found",
        {"source_kind": source_kind, "source": str(source) if source else "restic:latest:" + str(target) if restic_node else None},
    )
    if source is not None:
        add("ok" if source.exists() else "fail", "restore_source_exists", "restore source exists" if source.exists() else "restore source missing", {"source": str(source)})
        add("ok" if os.access(source, os.R_OK) else "fail", "restore_source_readable", "restore source is readable" if os.access(source, os.R_OK) else "restore source is not readable", {"source": str(source)})
    elif isinstance(restic_inventory, dict):
        add(
            "ok" if restic_inventory.get("ok") else "fail",
            "system_restic_latest_listed",
            "restic latest lists restore source" if restic_inventory.get("ok") else "restic latest could not list restore source",
            {
                "covered_by_policy": restic_inventory.get("covered_by_policy"),
                "node_found": bool(restic_node),
                "returncode": restic_inventory.get("returncode"),
                "reason": restic_inventory.get("reason"),
                "blockers": restic_inventory.get("blockers"),
                "stderr_tail": restic_inventory.get("stderr_tail"),
            },
        )
        if restic_inventory.get("ok"):
            add(
                "ok" if restic_node else "fail",
                "system_restic_path_exists",
                "path exists in restic latest" if restic_node else "path is not present in restic latest",
                {"path": str(target), "snapshot": restic_inventory.get("snapshot"), "node": restic_node},
            )
    parent_protection = _core.storage_path_protection(target.parent)
    add(
        "ok" if parent_protection.get("decision") != "deny" else "fail",
        "restore_target_parent_allowed",
        "restore target parent is allowed by storage policy" if parent_protection.get("decision") != "deny" else "restore target parent is denied by storage policy",
        {"target_parent": str(target.parent), "protection": parent_protection},
    )
    sample_files = artifact_restore_sample_files(source) if source is not None and source.exists() else []
    emitted_samples = sample_files or ([restic_node] if isinstance(restic_node, dict) else [])
    add(
        "ok" if emitted_samples else "warn",
        "restore_source_sample_read",
        "sample files read from restore source" if emitted_samples else "no sample files read from restore source",
        {"sample_count": len(emitted_samples), "source_kind": source_kind},
    )
    fails = sum(1 for item in checks if item.get("level") == "fail")
    warnings_count = sum(1 for item in checks if item.get("level") == "warn")
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_restore_check_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": fails == 0,
        "path": str(target),
        "matched_spec_id": record.get("id"),
        "source_kind": source_kind,
        "restore_source": str(source) if source else "restic:latest:" + str(target) if restic_node else None,
        "restore_command": backup.get("restore_command") or _core.nested_get(backup, ["system_restic", "restore_command"]),
        "record": record,
        "system_restic": {
            key: value for key, value in (restic_inventory or {}).items()
            if key != "nodes"
        } if isinstance(restic_inventory, dict) else None,
        "checks": checks,
        "summary": {
            "status": "fail" if fails else "warn" if warnings_count else "ok",
            "fails": fails,
            "warnings": warnings_count,
            "checks": len(checks),
            "sample_files": len(emitted_samples),
            "system_restic_node_found": bool(restic_node),
        },
        "sample_files": emitted_samples,
        "policy": {
            "dry_run": True,
            "copies_data": False,
            "automatic_restore": False,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_RESTORE_CHECK_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_RESTORE_CHECK_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_quarantine_rehearsal(
    path: str,
    verify_workload: str,
    observe_seconds: float = 0.0,
    write_latest: bool = True,
) -> dict[str, Any]:
    target = Path(path).expanduser()
    usage = artifacts_usage(str(target), write_latest=False)
    snapshot_latest, snapshot_error = _core.load_json_document(_core.ARTIFACTS_SNAPSHOT_LATEST_PATH)
    restore_check = artifacts_restore_check(str(target), write_latest=False)
    quarantine = artifacts_quarantine_plan(str(target), verify_workload, write_latest=False)
    observe = artifacts_observe(str(target), seconds=observe_seconds, interval=0.5, write_latest=False) if observe_seconds > 0 else {
        "planned_command": f"abyss-machine artifacts observe {shlex.quote(str(target))} --seconds 120 --json",
        "executed": False,
    }
    blocked_reasons = list(quarantine.get("blocked_reasons", []) if isinstance(quarantine.get("blocked_reasons"), list) else [])
    if not restore_check.get("ok"):
        blocked_reasons.append("restore_check_not_ok")
    if isinstance(observe, dict) and observe.get("executed", True) is not False:
        summary = observe.get("summary") if isinstance(observe.get("summary"), dict) else {}
        if summary.get("access_observed"):
            blocked_reasons.append("observe_access_observed")
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_quarantine_rehearsal_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": not blocked_reasons,
        "dry_run": True,
        "path": str(target),
        "verify_workload": verify_workload,
        "blocked_reasons": blocked_reasons,
        "usage": usage,
        "snapshot_history": {
            "latest_path": str(_core.ARTIFACTS_SNAPSHOT_LATEST_PATH),
            "latest_exists": _core.ARTIFACTS_SNAPSHOT_LATEST_PATH.exists(),
            "load_error": snapshot_error,
            "summary": snapshot_latest.get("history_summary") if isinstance(snapshot_latest, dict) else None,
        },
        "observe": observe,
        "restore_check": restore_check,
        "quarantine_plan": quarantine,
        "rollback": {
            "restore_command": restore_check.get("restore_command"),
            "restore_source": restore_check.get("restore_source"),
            "rule": "restore immediately if workload probe fails or live evidence appears",
        },
        "policy": {
            "this_command_is_rehearsal_only": True,
            "moves_data": False,
            "deletes_data": False,
            "requires_explicit_apply_for_future_mutation": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_REHEARSAL_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_REHEARSAL_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifact_content_identity_file(
    path: Path,
    root: Path,
    max_file_bytes: int,
    restic_nodes: dict[str, dict[str, Any]] | None = None,
    restic_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rel = str(path.relative_to(root)) if _core.is_relative_to_path(path, root) else path.name
    item: dict[str, Any] = {"path": str(path), "rel": rel}
    try:
        stat = path.stat()
        item.update({
            "size_bytes": stat.st_size,
            "inode": stat.st_ino,
            "device": stat.st_dev,
            "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        })
        if stat.st_size <= max_file_bytes:
            item["sha256"] = _core.sha256_path(path)
        else:
            item["sha256"] = None
            item["hash_skipped_reason"] = f"file larger than {max_file_bytes} bytes"
    except OSError as exc:
        item["error"] = str(exc)
    backup = artifact_backup_state(path)
    restic_node = (restic_nodes or {}).get(str(path))
    system_restic = backup.get("system_restic") if isinstance(backup.get("system_restic"), dict) else {}
    if isinstance(restic_state, dict):
        system_restic = {**system_restic, **{key: value for key, value in restic_state.items() if key != "nodes"}}
    system_restic_latest_exists = bool(restic_node)
    item["vault"] = {
        "rel": backup.get("local_to_heavy_rel"),
        "status": backup.get("status"),
        "latest_exists": _core.nested_get(backup, ["latest", "exists"]),
        "offload_exists": _core.nested_get(backup, ["offload", "exists"]),
        "preserved_deleted_count": len(backup.get("preserved_deleted", []) if isinstance(backup.get("preserved_deleted"), list) else []),
        "restore_command": backup.get("restore_command"),
        "system_restic": {
            "covered_by_policy": system_restic.get("covered_by_policy"),
            "latest_exists": system_restic_latest_exists,
            "snapshot": system_restic.get("snapshot"),
            "node": restic_node,
            "restore_command": system_restic.get("restore_command"),
            "latest_success": system_restic.get("latest_success"),
            "check_ok": system_restic.get("ok"),
            "check_reason": system_restic.get("reason"),
        },
    }
    return item


def artifact_content_identity_previous_hashes() -> dict[str, list[dict[str, Any]]]:
    previous, _ = _core.load_json_document(_core.ARTIFACTS_CONTENT_IDENTITY_LATEST_PATH)
    by_hash: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(previous, dict):
        return by_hash
    previous_root = str(previous.get("root") or "")
    for item in previous.get("files", []) if isinstance(previous.get("files"), list) else []:
        if not isinstance(item, dict):
            continue
        sha = str(item.get("sha256") or "")
        if not sha:
            continue
        if previous_root:
            item = dict(item)
            item["_scan_root"] = previous_root
        by_hash.setdefault(sha, []).append(item)
    return by_hash


def artifacts_content_identity(path: str, max_files: int = 500, max_file_bytes: int = 512 * 1024 * 1024, write_latest: bool = True) -> dict[str, Any]:
    root = Path(path).expanduser()
    files: list[Path] = []
    if root.is_file():
        files = [root]
    elif root.is_dir():
        try:
            for current, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in sorted(dirnames) if name not in {"__pycache__", ".git"}]
                for filename in sorted(filenames):
                    files.append(Path(current) / filename)
                    if len(files) >= max_files:
                        break
                if len(files) >= max_files:
                    break
        except OSError:
            files = []
    identity_root = root if root.is_dir() else root.parent
    restic_inventory = artifact_system_restic_inventory(identity_root, max_nodes=max(1000, min(max_files * 12, 20000)), timeout=30.0)
    restic_nodes = restic_inventory.get("nodes") if isinstance(restic_inventory.get("nodes"), dict) else {}
    current = [
        artifact_content_identity_file(file_path, identity_root, max_file_bytes, restic_nodes=restic_nodes, restic_state=restic_inventory)
        for file_path in files
    ]
    current_by_hash: dict[str, list[dict[str, Any]]] = {}
    for item in current:
        sha = str(item.get("sha256") or "")
        if sha:
            current_by_hash.setdefault(sha, []).append(item)
    previous_by_hash = artifact_content_identity_previous_hashes()
    moves: list[dict[str, Any]] = []
    for sha, items in current_by_hash.items():
        previous_items = previous_by_hash.get(sha, [])
        previous_paths_for_hash = {str(previous.get("path") or "") for previous in previous_items}
        current_paths_for_hash = {str(item.get("path") or "") for item in items}
        for previous in previous_items:
            if str(previous.get("path") or "") in current_paths_for_hash:
                continue
            for item in items:
                if str(item.get("path") or "") in previous_paths_for_hash:
                    continue
                if previous.get("path") != item.get("path"):
                    moves.append({
                        "sha256": sha,
                        "moved_from": previous.get("path"),
                        "moved_to": item.get("path"),
                        "size_bytes": item.get("size_bytes"),
                    })
    duplicates = [
        {"sha256": sha, "paths": [str(item.get("path")) for item in items], "size_bytes": items[0].get("size_bytes")}
        for sha, items in current_by_hash.items()
        if len(items) > 1
    ]
    current_paths = {str(item.get("path")) for item in current}
    local_deleted_preserved: list[dict[str, Any]] = []
    for previous_items in previous_by_hash.values():
        for previous in previous_items:
            previous_path = str(previous.get("path") or "")
            previous_scan_root = str(previous.get("_scan_root") or "")
            same_scan_root = previous_scan_root == str(root)
            under_current_root = bool(previous_path and _core.is_relative_to_path(Path(previous_path), root))
            if previous_path and previous_path not in current_paths and (same_scan_root or under_current_root):
                vault = previous.get("vault") if isinstance(previous.get("vault"), dict) else {}
                previous_restic = vault.get("system_restic") if isinstance(vault.get("system_restic"), dict) else {}
                if _core.safe_int(vault.get("preserved_deleted_count"), 0) > 0 or previous_restic.get("latest_exists"):
                    local_deleted_preserved.append({
                        "path": previous_path,
                        "sha256": previous.get("sha256"),
                        "vault": vault,
                    })
    already_in_heavy = sum(
        1 for item in current
        if (item.get("vault") or {}).get("latest_exists")
        or (item.get("vault") or {}).get("offload_exists")
        or _core.safe_int((item.get("vault") or {}).get("preserved_deleted_count"), 0) > 0
    )
    already_in_system_restic = sum(
        1 for item in current
        if _core.nested_get(item, ["vault", "system_restic", "latest_exists"])
    )
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_content_identity_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "root": str(root),
        "max_files": max_files,
        "max_file_bytes": max_file_bytes,
        "summary": {
            "files_scanned": len(current),
            "hashed_files": sum(1 for item in current if item.get("sha256")),
            "hash_skipped_files": sum(1 for item in current if item.get("hash_skipped_reason")),
            "moves_detected": len(moves),
            "same_content_different_path": len(duplicates),
            "already_in_vault": len({str(item.get("path")) for item in current if (item.get("vault") or {}).get("latest_exists") or (item.get("vault") or {}).get("offload_exists") or _core.safe_int((item.get("vault") or {}).get("preserved_deleted_count"), 0) > 0 or _core.nested_get(item, ["vault", "system_restic", "latest_exists"])}),
            "already_in_heavy_vault": already_in_heavy,
            "already_in_system_restic": already_in_system_restic,
            "local_deleted_preserved_candidates": len(local_deleted_preserved),
            "unsupported_vault_rel": sum(1 for item in current if not (item.get("vault") or {}).get("rel")),
            "system_restic_covered_by_policy": bool(restic_inventory.get("covered_by_policy")),
            "system_restic_check_ok": bool(restic_inventory.get("ok")),
        },
        "system_restic": {
            key: value for key, value in restic_inventory.items()
            if key != "nodes"
        },
        "moves": moves[:200],
        "same_content_different_path": duplicates[:200],
        "local_deleted_preserved_candidates": local_deleted_preserved[:200],
        "files": current,
        "policy": {
            "facts_only": True,
            "moves_are_detected_by_content_hash": True,
            "does_not_delete_or_move": True,
            "heavy_backup_does_move_reconcile": True,
            "system_restic_is_restore_evidence_not_move_reconcile": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_CONTENT_IDENTITY_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_CONTENT_IDENTITY_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_classify(scope: str = "all", write_latest: bool = True) -> dict[str, Any]:
    inventory = artifacts_inventory(scope=scope, write_latest=False)
    records = inventory.get("records") if isinstance(inventory.get("records"), list) else []
    classes: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        classes.setdefault(str(record.get("classification") or "unknown"), []).append({
            "id": record.get("id"),
            "path": record.get("path"),
            "decision": record.get("decision"),
            "confidence": record.get("confidence"),
            "backup_status": record.get("backup_state", {}).get("status") if isinstance(record.get("backup_state"), dict) else None,
        })
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_classify_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "scope": scope,
        "summary": inventory.get("summary"),
        "classes": classes,
        "policy": inventory.get("policy"),
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_CLASSIFY_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_CLASSIFY_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_quarantine_plan(path: str, verify_workload: str, write_latest: bool = True) -> dict[str, Any]:
    target = Path(path).expanduser()
    trace = artifacts_trace(str(target), write_latest=False)
    record = trace.get("record") if isinstance(trace.get("record"), dict) else {}
    decision = record.get("decision") if isinstance(record.get("decision"), dict) else {}
    backup = record.get("backup_state") if isinstance(record.get("backup_state"), dict) else {}
    blocked_reasons: list[str] = []
    if not record.get("path_state", {}).get("exists"):
        blocked_reasons.append("local_path_absent")
    if backup.get("status") not in {"explicit-offload", "heavy-latest", "preserved-deleted"}:
        blocked_reasons.append("backup_state_not_proven")
    if decision.get("classification") in {"hot", "active-route", "protected"}:
        blocked_reasons.append(f"classification:{decision.get('classification')}")
    clean_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(target).strip("/")).strip("-") or _core.stable_hash_json({"path": str(target)}, length=16)
    quarantine_target = _core.ABYSS_MACHINE_STORAGE_ROOT / "artifact-quarantine" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") / clean_name
    workload_commands = {
        "dictation": ["systemctl --user restart abyss-dictation-server.service", "abyss-machine dictation status --json"],
        "rerank-api": ["abyss-machine processes containers --json"],
        "nervous-semantic": [
            "abyss-machine nervous semantic-status --json",
            "abyss-machine nervous semantic-build --max-chunks 8 --batch-size 1 --device CPU --rebuild --json",
            "abyss-machine nervous semantic-status --json",
        ],
        "tts": ["systemctl --user restart abyss-tts-server.service", "abyss-machine ai tts status --json"],
        "gemma4-spark": ["systemctl --user start abyss-gemma4-spark-digest.service", "abyss-machine ai llm resident status --json"],
        "manual-restore": ["use record.backup_state.restore_command if the operator chooses to restore"],
        "manual": ["operator-defined workload probe required"],
    }
    probe_record = dict(record)
    probe_record["workload_probe"] = verify_workload
    real_probe = artifact_real_probe(probe_record)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_artifacts_quarantine_plan_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": not blocked_reasons,
        "dry_run": True,
        "path": str(target),
        "verify_workload": verify_workload,
        "blocked_reasons": blocked_reasons,
        "quarantine_target": str(quarantine_target),
        "record": record,
        "planned_steps": [
            "confirm backup state and restore command",
            "run pre_cache_cleanup hooks with enforce before any future move",
            f"move local path to {quarantine_target}",
            "run selected workload probe",
            "restore immediately if probe fails or route evidence contradicts quarantine",
            "record final decision and run storage/artifact validators",
        ],
        "workload_probe": real_probe,
        "workload_probe_commands": real_probe.get("commands") or workload_commands.get(verify_workload, workload_commands["manual"]),
        "insufficient_probe_commands": real_probe.get("insufficient_commands", []),
        "restore_command": backup.get("restore_command"),
        "policy": {
            "this_command_is_plan_only": True,
            "automatic_deletion": False,
            "requires_explicit_operator_confirmation_for_future_apply": True,
            "requires_change_record_for_mutation": True,
            "date_size_or_refs_alone_never_delete_ok": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_QUARANTINE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_QUARANTINE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def artifacts_validate_document_from_checks(
    checks: list[dict[str, Any]],
    *,
    strict: bool,
    paths: dict[str, Any],
    inventory_summary: Any,
    latest: Any,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return artifact_bundles.artifacts_validate_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=generated_at or _core.now_iso(),
        checks=checks,
        strict=strict,
        paths=paths,
        inventory_summary=inventory_summary,
        latest_path=latest,
    )


def artifacts_validate(strict: bool = False, write_latest: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    _core.validation_add_path_exists(checks, f"doc:{_core.ARTIFACTS_AGENTS_PATH}", _core.ARTIFACTS_AGENTS_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, f"doc:{_core.ARTIFACTS_ROUTE_LAW_PATH}", _core.ARTIFACTS_ROUTE_LAW_PATH, "file", required=True)
    _core.validation_add_path_exists(checks, f"dir:{_core.ARTIFACTS_ROOT}", _core.ARTIFACTS_ROOT, "dir", required=False)
    inventory = artifacts_inventory(scope="ai-cache", write_latest=False)
    records = {str(item.get("id")): item for item in inventory.get("records", []) if isinstance(item, dict)}
    required_ids = {
        "ai_cache_gemma4",
        "ai_openvino_dictation_server",
        "ai_qwen3_reranker_model",
        "ai_openvino_qwen3_reranker",
        "ai_openvino_semantic_embedding_qwen3",
        "ai_tts_cache",
        "ai_qwen36_cache",
    }
    missing = sorted(required_ids - set(records))
    _core.topology_validation_add(
        checks,
        "fail" if missing else "ok",
        "artifact_required_ai_cache_records",
        "AI-cache first-increment artifact records are present" if not missing else "AI-cache first-increment artifact records are missing",
        {"missing": missing},
    )
    dictation = records.get("ai_openvino_dictation_server", {})
    _core.topology_validation_add(
        checks,
        "ok" if dictation.get("classification") == "active-route" and dictation.get("confidence") == "high" else "warn",
        "artifact_dictation_active_route",
        "dictation OpenVINO cache classifies as active-route with high confidence",
        {"classification": dictation.get("classification"), "confidence": dictation.get("confidence"), "decision": dictation.get("decision")},
    )
    semantic = records.get("ai_openvino_semantic_embedding_qwen3", {})
    _core.topology_validation_add(
        checks,
        "ok" if semantic.get("classification") in {"quarantine-first", "active-route"} else "warn",
        "artifact_semantic_embedding_bounded_decision",
        "semantic embedding cache has a bounded non-delete-ok classification",
        {"classification": semantic.get("classification"), "confidence": semantic.get("confidence"), "decision": semantic.get("decision")},
    )
    semantic_probe = artifact_real_probe({"workload_probe": "nervous-semantic"})
    semantic_probe_commands = [str(item) for item in semantic_probe.get("commands", []) if item]
    bounded_semantic_probe_present = any(
        "semantic-build" in command
        and "--max-chunks 8" in command
        and "--batch-size 1" in command
        and "--rebuild" in command
        for command in semantic_probe_commands
    )
    _core.topology_validation_add(
        checks,
        "ok" if bounded_semantic_probe_present else "fail",
        "artifact_semantic_probe_is_bounded_rebuild",
        "semantic cache proof uses a bounded rebuild probe, not status/dry-run alone",
        {"commands": semantic_probe_commands, "insufficient": semantic_probe.get("insufficient_commands")},
    )
    paths_doc = artifacts_paths()
    lifecycle_keys = {
        "snapshot",
        "observe",
        "restore_check",
        "quarantine_rehearsal",
        "content_identity",
        "bundle_registry",
        "trust_tools",
        "trust_coverage",
        "update_lane",
    }
    missing_lifecycle = sorted(lifecycle_keys - set(paths_doc))
    _core.topology_validation_add(
        checks,
        "fail" if missing_lifecycle else "ok",
        "artifact_lifecycle_goal_commands_registered",
        "artifact lifecycle goal commands are registered in paths" if not missing_lifecycle else "artifact lifecycle goal commands are missing from paths",
        {"missing": missing_lifecycle},
    )
    bundle_registry_paths = paths_doc.get("bundle_registry") if isinstance(paths_doc.get("bundle_registry"), dict) else {}
    registry_commands = [
        str(bundle_registry_paths.get("register_command") or ""),
        str(bundle_registry_paths.get("query_command") or ""),
    ]
    _core.topology_validation_add(
        checks,
        "ok" if all(command for command in registry_commands) and any("bundle-register" in command for command in registry_commands) and any("bundle-registry" in command for command in registry_commands) else "fail",
        "artifact_bundle_registry_read_model_registered",
        "artifact bundle registry write and latest-query commands are registered in paths",
        {"commands": registry_commands, "index": bundle_registry_paths.get("index")},
    )
    trust_tools_paths = paths_doc.get("trust_tools") if isinstance(paths_doc.get("trust_tools"), dict) else {}
    trust_tools = artifacts_trust_tools(write_latest=False)
    trust_summary = trust_tools.get("summary") if isinstance(trust_tools.get("summary"), dict) else {}
    _core.topology_validation_add(
        checks,
        (
            "ok"
            if trust_tools_paths.get("command")
            and trust_tools_paths.get("runtime_root")
            and trust_tools_paths.get("proof_command")
            and trust_tools_paths.get("proof_latest")
            else "fail"
        ),
        "artifact_trust_tools_route_registered",
        "artifact external trust-tool discovery and proof routes are registered in paths",
        {
            "command": trust_tools_paths.get("command"),
            "proof_command": trust_tools_paths.get("proof_command"),
            "runtime_root": trust_tools_paths.get("runtime_root"),
            "latest": trust_tools_paths.get("latest"),
            "proof_latest": trust_tools_paths.get("proof_latest"),
        },
    )
    _core.topology_validation_add(
        checks,
        "ok" if trust_summary.get("status") == "ready" else "warn",
        "artifact_external_trust_toolchain_audited",
        "external artifact trust toolchain is audited; missing controls remain explicit",
        {
            "status": trust_summary.get("status"),
            "available_tools": trust_summary.get("available_tools"),
            "missing_tools": trust_summary.get("missing_tools"),
            "missing_controls": trust_summary.get("missing_controls"),
        },
    )
    trust_coverage_paths = paths_doc.get("trust_coverage") if isinstance(paths_doc.get("trust_coverage"), dict) else {}
    trust_coverage = artifacts_trust_coverage(write_latest=False)
    trust_coverage_summary = trust_coverage.get("summary") if isinstance(trust_coverage.get("summary"), dict) else {}
    coverage_classes = _core.safe_int(trust_coverage_summary.get("artifact_classes"), 0)
    coverage_count_sum = sum(
        _core.safe_int(trust_coverage_summary.get(key), 0)
        for key in ("fully_covered", "deferred_with_real_blocker", "blocked_external")
    )
    _core.topology_validation_add(
        checks,
        "ok" if trust_coverage_paths.get("command") and trust_coverage_paths.get("latest") else "fail",
        "artifact_trust_coverage_route_registered",
        "artifact trust coverage matrix route is registered in paths",
        {
            "command": trust_coverage_paths.get("command"),
            "latest": trust_coverage_paths.get("latest"),
        },
    )
    _core.topology_validation_add(
        checks,
        "ok" if coverage_classes and coverage_count_sum == coverage_classes else "fail",
        "artifact_trust_coverage_matrix_complete",
        "artifact trust coverage matrix accounts for every policy artifact class without requiring false full coverage",
        {
            "summary": trust_coverage_summary,
            "deferred": [
                row.get("artifact_class")
                for row in trust_coverage.get("rows", [])
                if isinstance(row, dict) and row.get("status") != "FULLY_COVERED"
            ],
        },
    )
    update_lane_paths = paths_doc.get("update_lane") if isinstance(paths_doc.get("update_lane"), dict) else {}
    update_lane = artifacts_update_lane(write_latest=False)
    update_summary = update_lane.get("summary") if isinstance(update_lane.get("summary"), dict) else {}
    update_rows = [row for row in update_lane.get("rows", []) if isinstance(row, dict)]
    _core.topology_validation_add(
        checks,
        "ok" if update_lane_paths.get("command") and update_lane_paths.get("repository_build_command") and update_lane_paths.get("repository_verify_command") and update_lane_paths.get("verify_command") and update_lane_paths.get("metadata_sidecar") == artifact_bundles.TUF_UPDATE_METADATA_SIDECAR else "fail",
        "artifact_update_lane_route_registered",
        "artifact update lane status, repository build, and verification commands are registered in paths",
        {
            "command": update_lane_paths.get("command"),
            "repository_build_command": update_lane_paths.get("repository_build_command"),
            "repository_verify_command": update_lane_paths.get("repository_verify_command"),
            "verify_command": update_lane_paths.get("verify_command"),
            "metadata_sidecar": update_lane_paths.get("metadata_sidecar"),
            "latest": update_lane_paths.get("latest"),
        },
    )
    _core.topology_validation_add(
        checks,
        "ok" if update_summary.get("tuf_status") == "external_repository_producer_v1" and update_summary.get("updateable_artifact_classes", 0) > 0 and update_summary.get("blocking_v1") is False else "fail",
        "artifact_update_transparency_lane_policy_ready",
        "TUF update lane has an external repository producer/verifier for updateable artifacts and SCITT is non-blocking v1",
        {
            "summary": update_summary,
            "artifact_classes": [row.get("artifact_class") for row in update_rows],
        },
    )
    lifecycle_samples = {
        "restore_check_policy": artifacts_restore_check(str(_core.AI_CACHE_ROOT / "qwen3.6"), write_latest=False).get("policy"),
        "rehearsal_policy": artifacts_quarantine_rehearsal(str(_core.AI_CACHE_ROOT / "qwen3.6"), "manual-restore", write_latest=False).get("policy"),
    }
    _core.topology_validation_add(
        checks,
        "ok" if all(isinstance(policy, dict) and not policy.get("copies_data", False) and not policy.get("moves_data", False) and not policy.get("deletes_data", False) for policy in lifecycle_samples.values() if isinstance(policy, dict)) else "fail",
        "artifact_lifecycle_commands_non_mutating",
        "restore-check and quarantine-rehearsal advertise non-mutating policy",
        lifecycle_samples,
    )
    _core.topology_validation_add(
        checks,
        "ok" if all(record.get("decision", {}).get("decision") for record in records.values()) else "fail",
        "artifact_records_have_decisions",
        "artifact records carry explicit decisions and confidence",
        {"records": len(records)},
    )
    data = artifacts_validate_document_from_checks(
        checks,
        strict=strict,
        paths=artifacts_paths(),
        inventory_summary=inventory.get("summary"),
        latest=_core.ARTIFACTS_VALIDATE_LATEST_PATH,
    )
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.ARTIFACTS_VALIDATE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.ARTIFACTS_VALIDATE_ROOT), data, 0o664)
        index_error = _core.safe_atomic_write_json(_core.ARTIFACTS_INDEX_PATH, artifacts_paths(), 0o664)
        errors = [error for error in (latest_error, daily_error, index_error) if error]
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def proc_cmdline(pid: int, max_len: int = 700) -> str:
    return _core.process_adapters.proc_cmdline(pid, max_len=max_len)


def safe_readlink(path: Path) -> str | None:
    return _core.process_adapters.safe_readlink(path)


def add_artifacts_parser(add_top_level_parser: Any, selected_parser_choices: Any) -> None:
    artifacts_parser = add_top_level_parser("artifacts", help="inspect large host-local artifact evidence before cleanup/offload decisions")
    artifacts_sub = artifacts_parser.add_subparsers(dest="artifacts_command", required=True)
    artifacts_paths_parser = artifacts_sub.add_parser("paths")
    artifacts_paths_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_inventory_parser = artifacts_sub.add_parser("inventory")
    artifacts_inventory_parser.add_argument("--scope", default="all", choices=["all", "ai-cache", "openvino", "runtimes", "storage"])
    artifacts_inventory_parser.add_argument("--with-usage", action="store_true", help="include per-record usage summaries from live/history/vault evidence")
    artifacts_inventory_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_explain_parser = artifacts_sub.add_parser("explain")
    artifacts_explain_parser.add_argument("path")
    artifacts_explain_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trace_parser = artifacts_sub.add_parser("trace")
    artifacts_trace_parser.add_argument("path")
    artifacts_trace_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_usage_parser = artifacts_sub.add_parser("usage")
    artifacts_usage_parser.add_argument("path")
    artifacts_usage_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_timeline_parser = artifacts_sub.add_parser("timeline")
    artifacts_timeline_parser.add_argument("path")
    artifacts_timeline_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_snapshot_parser = artifacts_sub.add_parser("snapshot")
    artifacts_snapshot_parser.add_argument("--scope", default="all", choices=["all", "ai-cache", "openvino", "runtimes", "storage"])
    artifacts_snapshot_parser.add_argument("--history-days", type=int, default=14, help="snapshot history window for no-live-use summaries")
    artifacts_snapshot_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_observe_parser = artifacts_sub.add_parser("observe")
    artifacts_observe_parser.add_argument("path")
    artifacts_observe_parser.add_argument("--seconds", type=float, default=120.0)
    artifacts_observe_parser.add_argument("--interval", type=float, default=1.0)
    artifacts_observe_parser.add_argument("--recursive", action="store_true", help="use recursive inotifywait when available")
    artifacts_observe_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_restore_check_parser = artifacts_sub.add_parser("restore-check")
    artifacts_restore_check_parser.add_argument("path")
    artifacts_restore_check_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_rehearsal_parser = artifacts_sub.add_parser("quarantine-rehearsal")
    artifacts_rehearsal_parser.add_argument("path")
    artifacts_rehearsal_parser.add_argument("--verify-workload", default="manual")
    artifacts_rehearsal_parser.add_argument("--observe-seconds", type=float, default=0.0, help="run a short observe window inside the rehearsal")
    artifacts_rehearsal_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_content_identity_parser = artifacts_sub.add_parser("content-identity")
    artifacts_content_identity_parser.add_argument("path")
    artifacts_content_identity_parser.add_argument("--max-files", type=int, default=500)
    artifacts_content_identity_parser.add_argument("--max-file-bytes", type=int, default=512 * 1024 * 1024)
    artifacts_content_identity_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_classify_parser = artifacts_sub.add_parser("classify")
    artifacts_classify_parser.add_argument("target", nargs="?", help="optional artifact bundle directory for policy classification")
    artifacts_classify_parser.add_argument("--artifact-class", default="", help="policy artifact class to classify when no bundle identity exists")
    artifacts_classify_parser.add_argument("--scope", default="all", choices=["all", "ai-cache", "openvino", "runtimes", "storage"])
    artifacts_classify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_requirements_parser = artifacts_sub.add_parser("requirements")
    artifacts_requirements_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_requirements_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_requirements_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_producer_profiles_parser = artifacts_sub.add_parser("producer-profiles")
    artifacts_producer_profiles_parser.add_argument("--profile-id", default="", help="optional producer profile id filter")
    artifacts_producer_profiles_parser.add_argument("--owner-repo", default="", help="optional owner repository filter")
    artifacts_producer_profiles_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_producer_profiles_parser.add_argument("--workspace-root", default="", help="OS Abyss workspace root used to resolve owner-local producer commands")
    artifacts_producer_profiles_parser.add_argument("--owner-repo-root", action="append", default=[], help="explicit OWNER=PATH override for owner-local producer command resolution")
    artifacts_producer_profiles_parser.add_argument("--require-command-resolution", action="store_true", help="fail when declared owner-local producer commands cannot be resolved")
    artifacts_producer_profiles_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_scenarios_parser = artifacts_sub.add_parser("scenarios")
    artifacts_scenarios_parser.add_argument("--scenario-id", default="", help="optional OS artifact scenario id filter")
    artifacts_scenarios_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_scenarios_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_scenarios_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_affected_parser = artifacts_sub.add_parser("affected")
    artifacts_affected_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_affected_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_affected_parser.add_argument("--changed-path", action="append", default=[], help="repo-relative path changed in the current source/ref")
    artifacts_affected_parser.add_argument("--source-repo", default="", help="source repository that changed, for sibling lag detection")
    artifacts_affected_parser.add_argument("--source-ref", default="", help="opaque source/provenance token that the latest durable evidence must prove")
    artifacts_affected_parser.add_argument("--accept-sibling-lag", action="store_true", help="report sibling owner drift as accepted_lag instead of a blocker")
    artifacts_affected_parser.add_argument("--fail-on-blocking", action="store_true", help="exit 2 when affected drift is operationally blocking")
    artifacts_affected_parser.add_argument("--fail-on-accepted-lag", action="store_true", help="exit 2 when accepted sibling lag is present")
    artifacts_affected_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_update_lane_parser = artifacts_sub.add_parser("update-lane")
    artifacts_update_lane_parser.add_argument("--artifact-class", default="", help="optional updateable artifact class filter")
    artifacts_update_lane_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_update_verify_parser = artifacts_sub.add_parser("update-verify")
    artifacts_update_verify_parser.add_argument("metadata", help="TUF-style update metadata sidecar")
    artifacts_update_verify_parser.add_argument("--previous-trusted", default="", help="previous trusted update metadata state")
    artifacts_update_verify_parser.add_argument("--now", default="", help="override verification time as ISO-8601 UTC timestamp")
    artifacts_update_verify_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for update-client trust-gate")
    artifacts_update_verify_parser.add_argument("--subject-digest", default="", help="expected update target subject, aggregate, ABI, or record digest")
    artifacts_update_verify_parser.add_argument("--source-repo", default="", help="expected source repository for update target registry evidence")
    artifacts_update_verify_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode for update target registry evidence",
    )
    artifacts_update_verify_gate = artifacts_update_verify_parser.add_mutually_exclusive_group()
    artifacts_update_verify_gate.add_argument(
        "--require-trust-gate",
        dest="require_trust_gate",
        action="store_true",
        help="deny update-client consumption unless artifact trust-gate allows the target; this is the default",
    )
    artifacts_update_verify_gate.add_argument(
        "--inspect-only",
        dest="require_trust_gate",
        action="store_false",
        help="verify update metadata without consumer admission; not a consumption verdict",
    )
    artifacts_update_verify_parser.set_defaults(require_trust_gate=True)
    artifacts_update_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_update_repo_build_parser = artifacts_sub.add_parser("update-repo-build")
    artifacts_update_repo_build_parser.add_argument("repository", help="external TUF repository root to create or refresh")
    artifacts_update_repo_build_parser.add_argument("--target-file", required=True, help="local artifact file to copy into repository targets/")
    artifacts_update_repo_build_parser.add_argument("--target-path", default="", help="target path relative to repository targets/")
    artifacts_update_repo_build_parser.add_argument("--artifact-class", default="", help="OS Abyss artifact class represented by the target")
    artifacts_update_repo_build_parser.add_argument("--version", type=int, default=1, help="role metadata version for root/targets/snapshot/timestamp")
    artifacts_update_repo_build_parser.add_argument("--key-dir", default="", help="host-managed Ed25519 private key directory with root/targets/snapshot/timestamp .pem keys")
    artifacts_update_repo_build_parser.add_argument("--dev-generate-keys", action="store_true", help="generate missing Ed25519 keys for local proof; not a production key ceremony")
    artifacts_update_repo_build_parser.add_argument("--root-expires", default="", help="root role expiration timestamp")
    artifacts_update_repo_build_parser.add_argument("--targets-expires", default="", help="targets role expiration timestamp")
    artifacts_update_repo_build_parser.add_argument("--snapshot-expires", default="", help="snapshot role expiration timestamp")
    artifacts_update_repo_build_parser.add_argument("--timestamp-expires", default="", help="timestamp role expiration timestamp")
    artifacts_update_repo_build_parser.add_argument("--now", default="", help="override build time as ISO-8601 UTC timestamp")
    artifacts_update_repo_build_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_update_repo_verify_parser = artifacts_sub.add_parser("update-repo-verify")
    artifacts_update_repo_verify_parser.add_argument("repository", help="external TUF repository root containing metadata/ and targets/")
    artifacts_update_repo_verify_parser.add_argument("--target-path", required=True, help="target path relative to the TUF targets directory")
    artifacts_update_repo_verify_parser.add_argument("--artifact-class", default="", help="artifact class for optional update-client trust-gate admission")
    artifacts_update_repo_verify_parser.add_argument("--target-digest", default="", help="expected target sha256 digest")
    artifacts_update_repo_verify_parser.add_argument("--trusted-root", default="", help="out-of-band trusted TUF root metadata used for client bootstrap or root rotation")
    artifacts_update_repo_verify_parser.add_argument("--previous-trusted", default="", help="previous trusted TUF repository client state")
    artifacts_update_repo_verify_parser.add_argument("--now", default="", help="override verification time as ISO-8601 UTC timestamp")
    artifacts_update_repo_verify_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for update-client trust-gate")
    artifacts_update_repo_verify_parser.add_argument("--subject-digest", default="", help="expected update target subject, aggregate, ABI, or record digest")
    artifacts_update_repo_verify_parser.add_argument("--source-repo", default="", help="expected source repository for update target registry evidence")
    artifacts_update_repo_verify_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode for update target registry evidence",
    )
    artifacts_update_repo_verify_parser.add_argument("--require-trusted-root", action="store_true", help="deny repository verification unless a trusted root bootstrap is supplied")
    artifacts_update_repo_verify_gate = artifacts_update_repo_verify_parser.add_mutually_exclusive_group()
    artifacts_update_repo_verify_gate.add_argument(
        "--require-trust-gate",
        dest="require_trust_gate",
        action="store_true",
        help="deny update-client consumption unless artifact trust-gate allows the target; this is the default",
    )
    artifacts_update_repo_verify_gate.add_argument(
        "--inspect-only",
        dest="require_trust_gate",
        action="store_false",
        help="verify repository metadata without consumer admission; not a consumption verdict",
    )
    artifacts_update_repo_verify_parser.set_defaults(require_trust_gate=True)
    artifacts_update_repo_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_scitt_verify_parser = artifacts_sub.add_parser("scitt-verify")
    artifacts_scitt_verify_parser.add_argument("statement", help="SCITT-style signed statement JSON")
    artifacts_scitt_verify_parser.add_argument("--receipt", default="", help="SCITT-style receipt JSON")
    artifacts_scitt_verify_parser.add_argument("--external-relying-party", action="store_true", help="fail closed unless a receipt is present and bound to the statement")
    artifacts_scitt_verify_parser.add_argument("--require-receipt", action="store_true", help="require a receipt even outside external relying-party mode")
    artifacts_scitt_verify_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for durable record linkage")
    artifacts_scitt_verify_parser.add_argument("--record-id", default="", help="expected durable artifact registry record id")
    artifacts_scitt_verify_parser.add_argument("--require-registry-link", action="store_true", help="deny unless the statement subject binds to a durable registry record")
    artifacts_scitt_verify_parser.add_argument("--statement-class", default="", help="expected SCITT statement class")
    artifacts_scitt_verify_parser.add_argument("--artifact-digest", default="", help="expected artifact digest bound by the signed statement")
    artifacts_scitt_verify_parser.add_argument("--issuer", default="", help="expected statement issuer")
    artifacts_scitt_verify_parser.add_argument("--transparency-service", default="", help="expected transparency service id")
    artifacts_scitt_verify_parser.add_argument("--now", default="", help="override verification time as ISO-8601 UTC timestamp")
    artifacts_scitt_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_oci_verify_parser = artifacts_sub.add_parser("oci-verify")
    artifacts_oci_verify_parser.add_argument("evidence", help="OCI/ORAS publication evidence JSON")
    artifacts_oci_verify_parser.add_argument("--artifact-class", default="", help="expected artifact class")
    artifacts_oci_verify_parser.add_argument("--registry-ref", default="", help="expected digest-pinned OCI registry reference")
    artifacts_oci_verify_parser.add_argument("--subject-digest", default="", help="expected OCI subject manifest digest")
    artifacts_oci_verify_parser.add_argument("--required-referrer-type", action="append", default=[], help="required OCI referrer artifact type")
    artifacts_oci_verify_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for durable trust-gate")
    artifacts_oci_verify_parser.add_argument("--record-id", default="", help="expected durable artifact registry record id")
    artifacts_oci_verify_parser.add_argument("--record-subject-digest", default="", help="expected durable bundle subject/aggregate/ABI digest")
    artifacts_oci_verify_parser.add_argument("--source-repo", default="", help="expected source repository for trust-gate admission")
    artifacts_oci_verify_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode for durable registry evidence",
    )
    artifacts_oci_verify_parser.add_argument("--consumer-intent", default="runtime", help="trust-gate consumer intent")
    artifacts_oci_verify_parser.add_argument("--allow-tag-reference", action="store_true", help="do not deny tag-only OCI references")
    artifacts_oci_verify_parser.add_argument("--allow-missing-referrers", action="store_true", help="do not require referrer evidence")
    artifacts_oci_verify_gate = artifacts_oci_verify_parser.add_mutually_exclusive_group()
    artifacts_oci_verify_gate.add_argument(
        "--require-trust-gate",
        dest="require_trust_gate",
        action="store_true",
        help="deny unless durable trust-gate allows the linked record; this is the default",
    )
    artifacts_oci_verify_gate.add_argument(
        "--inspect-only",
        dest="require_trust_gate",
        action="store_false",
        help="verify OCI evidence without consumer admission; not a runtime consumption verdict",
    )
    artifacts_oci_verify_parser.set_defaults(require_trust_gate=True)
    artifacts_oci_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_oci_layout_publish_parser = artifacts_sub.add_parser("oci-layout-publish")
    artifacts_oci_layout_publish_parser.add_argument("subject", help="subject artifact file to publish into a local OCI layout")
    artifacts_oci_layout_publish_parser.add_argument("--layout-dir", required=True, help="local OCI layout directory")
    artifacts_oci_layout_publish_parser.add_argument("--artifact-class", required=True, help="artifact class for the OCI publication evidence")
    artifacts_oci_layout_publish_parser.add_argument("--registry-ref", required=True, help="OCI registry/name reference; the command pins it by digest")
    artifacts_oci_layout_publish_parser.add_argument("--artifact-type", default="", help="OCI artifactType for the subject manifest")
    artifacts_oci_layout_publish_parser.add_argument("--subject-media-type", default="", help="mediaType for the subject payload blob")
    artifacts_oci_layout_publish_parser.add_argument(
        "--referrer",
        action="append",
        default=[],
        help="attached referrer as ARTIFACT_TYPE=PATH; repeat for signature/SBOM/provenance",
    )
    artifacts_oci_layout_publish_parser.add_argument("--record-id", default="", help="durable artifact registry record id")
    artifacts_oci_layout_publish_parser.add_argument("--record-subject-digest", default="", help="durable bundle subject/aggregate/ABI digest")
    artifacts_oci_layout_publish_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_oci_consume_parser = artifacts_sub.add_parser("oci-consume")
    artifacts_oci_consume_parser.add_argument("evidence", help="OCI/ORAS publication evidence JSON")
    artifacts_oci_consume_parser.add_argument("--output-dir", required=True, help="directory for materialized subject/referrer proof")
    artifacts_oci_consume_parser.add_argument("--artifact-class", default="", help="expected artifact class")
    artifacts_oci_consume_parser.add_argument("--registry-ref", default="", help="expected digest-pinned OCI registry reference")
    artifacts_oci_consume_parser.add_argument("--subject-digest", default="", help="expected OCI subject manifest digest")
    artifacts_oci_consume_parser.add_argument("--required-referrer-type", action="append", default=[], help="required OCI referrer artifact type")
    artifacts_oci_consume_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for durable trust-gate")
    artifacts_oci_consume_parser.add_argument("--record-id", default="", help="expected durable artifact registry record id")
    artifacts_oci_consume_parser.add_argument("--record-subject-digest", default="", help="expected durable bundle subject/aggregate/ABI digest")
    artifacts_oci_consume_parser.add_argument("--source-repo", default="", help="expected source repository for trust-gate admission")
    artifacts_oci_consume_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode for durable registry evidence",
    )
    artifacts_oci_consume_parser.add_argument("--consumer-intent", default="runtime", help="trust-gate consumer intent")
    artifacts_oci_consume_parser.add_argument("--allow-tag-reference", action="store_true", help="do not deny tag-only OCI references")
    artifacts_oci_consume_parser.add_argument("--allow-missing-referrers", action="store_true", help="do not require referrer evidence")
    artifacts_oci_consume_gate = artifacts_oci_consume_parser.add_mutually_exclusive_group()
    artifacts_oci_consume_gate.add_argument(
        "--require-trust-gate",
        dest="require_trust_gate",
        action="store_true",
        help="deny unless durable trust-gate allows the linked record; this is the default",
    )
    artifacts_oci_consume_gate.add_argument(
        "--inspect-only",
        dest="require_trust_gate",
        action="store_false",
        help="verify and materialize local OCI layout without consumer admission; not a runtime consumption verdict",
    )
    artifacts_oci_consume_parser.set_defaults(require_trust_gate=True)
    artifacts_oci_consume_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_build_sidecars_parser = artifacts_sub.add_parser("build-sidecars")
    artifacts_build_sidecars_parser.add_argument("--bundle-dir", required=True)
    artifacts_build_sidecars_parser.add_argument("--artifact-class", default="public_source_seed")
    artifacts_build_sidecars_parser.add_argument("--contract-surface-id", default="")
    artifacts_build_sidecars_parser.add_argument("--manifest", default="", help="repo-local artifact bundle manifest")
    artifacts_build_sidecars_parser.add_argument("--subject-root", default="", help="runtime artifact subject root; never embedded as an absolute public ref")
    artifacts_build_sidecars_parser.add_argument("--owner-repo", default="", help="runtime source owner override for shared artifact manifests")
    artifacts_build_sidecars_parser.add_argument("--source-ref", default="", help="exact runtime source revision bound into the signed artifact identity")
    artifacts_build_sidecars_parser.add_argument("--access-policy", default="", help="expected artifact access policy identity")
    artifacts_build_sidecars_parser.add_argument("--mode", default="os_abyss_local", choices=["os_abyss_local", "github_release"])
    artifacts_build_sidecars_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_sign_parser = artifacts_sub.add_parser("sign")
    artifacts_sign_parser.add_argument("bundle_dir")
    artifacts_sign_parser.add_argument("--backend", default="policy-decision")
    artifacts_sign_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_kag_sign_parser = artifacts_sub.add_parser("kag-sign-identity")
    artifacts_kag_sign_parser.add_argument("payload")
    artifacts_kag_sign_parser.add_argument("--backend", default="cosign-local-key")
    artifacts_kag_sign_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_kag_verify_parser = artifacts_sub.add_parser("kag-verify-identity")
    artifacts_kag_verify_parser.add_argument("payload")
    artifacts_kag_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_verify_parser = artifacts_sub.add_parser("verify")
    artifacts_verify_parser.add_argument("bundle_dir")
    artifacts_verify_parser.add_argument("--subject-root", default="", help="runtime artifact subject root for byte verification")
    artifacts_verify_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_kag_retention_plan_parser = artifacts_sub.add_parser("kag-retention-plan")
    artifacts_kag_retention_plan_parser.add_argument("--cas-root", required=True)
    artifacts_kag_retention_plan_parser.add_argument("--registry-dir", required=True)
    artifacts_kag_retention_plan_parser.add_argument("--output", required=True)
    artifacts_kag_retention_plan_parser.add_argument("--pin-record-id", action="append", default=[])
    artifacts_kag_retention_plan_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_kag_retention_apply_parser = artifacts_sub.add_parser("kag-retention-apply")
    artifacts_kag_retention_apply_parser.add_argument("plan")
    artifacts_kag_retention_apply_parser.add_argument("--receipt", required=True)
    artifacts_kag_retention_apply_parser.add_argument("--confirm", action="store_true")
    artifacts_kag_retention_apply_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_materialize_subjects_parser = artifacts_sub.add_parser("materialize-subjects")
    artifacts_materialize_subjects_parser.add_argument("bundle_dir")
    artifacts_materialize_subjects_parser.add_argument("--store-root", default="", help="local artifact subject store root")
    artifacts_materialize_subjects_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root for consumer trust-gate")
    artifacts_materialize_subjects_parser.add_argument("--manifest", default="", help="explicit owner artifact bundle manifest for external subject materialization")
    artifacts_materialize_subjects_parser.add_argument("--subject-root", default="", help="runtime artifact subject root")
    artifacts_materialize_subjects_parser.add_argument("--consumer-intent", default="", help="consumer intent; defaults from artifact class")
    artifacts_materialize_subjects_parser.add_argument("--source-repo", default="", help="expected source repository")
    artifacts_materialize_subjects_parser.add_argument("--source-ref", default="", help="expected source snapshot or revision")
    artifacts_materialize_subjects_parser.add_argument("--access-policy", default="", help="expected access policy")
    artifacts_materialize_subjects_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode",
    )
    artifacts_materialize_subjects_parser.add_argument("--record-id", default="", help="specific registry record id")
    artifacts_materialize_subjects_parser.add_argument("--allow-non-latest", action="store_true", help="permit selecting a non-latest non-terminal record")
    artifacts_materialize_subjects_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_release_check_parser = artifacts_sub.add_parser("release-check")
    artifacts_release_check_parser.add_argument("bundle_dir")
    artifacts_release_check_parser.add_argument("--subject-root", default="", help="runtime artifact subject root for byte verification")
    artifacts_release_check_parser.add_argument(
        "--enforcement",
        default="blocking",
        choices=selected_parser_choices("artifacts", lambda: sorted(artifact_bundles.RELEASE_ENFORCEMENT_LEVELS)),
    )
    artifacts_release_check_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_bundle_register_parser = artifacts_sub.add_parser("bundle-register")
    artifacts_bundle_register_parser.add_argument("bundle_dir")
    artifacts_bundle_register_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_bundle_register_parser.add_argument(
        "--lifecycle-state",
        default="manually-verified",
        choices=selected_parser_choices("artifacts", lambda: artifact_bundles.BUNDLE_LIFECYCLE_STATES),
    )
    artifacts_bundle_register_parser.add_argument("--consumer-ref", action="append", default=[], help="consumer evidence reference")
    artifacts_bundle_register_parser.add_argument("--evidence-ref", action="append", default=[], help="manual or machine evidence reference")
    artifacts_bundle_register_parser.add_argument("--supersedes", action="append", default=[], help="record id superseded by this registration")
    artifacts_bundle_register_parser.add_argument("--revocation-reason", default="")
    artifacts_bundle_register_parser.add_argument("--source-repo", default="", help="source repository that produced the artifact")
    artifacts_bundle_register_parser.add_argument("--source-ref", default="", help="source ref, manifest, or revision used for the promoted artifact")
    artifacts_bundle_register_parser.add_argument("--subject-root", default="", help="runtime artifact subject root for verification before registration")
    artifacts_bundle_register_parser.add_argument(
        "--public-release-archive",
        default="",
        help="exact public release archive whose bytes must bind canonical subjects before registration",
    )
    artifacts_bundle_register_parser.add_argument("--producer", default="", help="producer identity for the promoted artifact")
    artifacts_bundle_register_parser.add_argument(
        "--trust-root-mode",
        default="local_dev",
        choices=selected_parser_choices("artifacts", lambda: artifact_bundles.TRUST_ROOT_MODES),
        help="trust root mode for this registry record",
    )
    artifacts_bundle_register_parser.add_argument(
        "--trust-root-evidence-json",
        default="",
        help="JSON object, or @path to one, proving host_managed update-root, github_oidc, oci_registry, or public_release trust-root claims",
    )
    artifacts_bundle_register_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_evidence_promote_parser = artifacts_sub.add_parser("evidence-promote")
    artifacts_evidence_promote_parser.add_argument("bundle_dir")
    artifacts_evidence_promote_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_evidence_promote_parser.add_argument(
        "--lifecycle-state",
        default="manually-verified",
        choices=selected_parser_choices("artifacts", lambda: artifact_bundles.BUNDLE_LIFECYCLE_STATES),
    )
    artifacts_evidence_promote_parser.add_argument("--consumer-ref", action="append", default=[], help="consumer evidence reference")
    artifacts_evidence_promote_parser.add_argument("--evidence-ref", action="append", default=[], help="manual or machine evidence reference")
    artifacts_evidence_promote_parser.add_argument("--supersedes", action="append", default=[], help="record id superseded by this promotion")
    artifacts_evidence_promote_parser.add_argument("--revocation-reason", default="")
    artifacts_evidence_promote_parser.add_argument("--source-repo", default="", help="source repository that produced the artifact")
    artifacts_evidence_promote_parser.add_argument("--source-ref", default="", help="source ref, manifest, or revision used for the promoted artifact")
    artifacts_evidence_promote_parser.add_argument("--subject-root", default="", help="runtime artifact subject root for verification before promotion")
    artifacts_evidence_promote_parser.add_argument(
        "--public-release-archive",
        default="",
        help="exact public release archive whose bytes must bind canonical subjects before promotion",
    )
    artifacts_evidence_promote_parser.add_argument("--producer", default="", help="producer identity for the promoted artifact")
    artifacts_evidence_promote_parser.add_argument(
        "--trust-root-mode",
        default="local_dev",
        choices=selected_parser_choices("artifacts", lambda: artifact_bundles.TRUST_ROOT_MODES),
        help="trust root mode for this promoted evidence record",
    )
    artifacts_evidence_promote_parser.add_argument(
        "--trust-root-evidence-json",
        default="",
        help="JSON object, or @path to one, proving host_managed update-root, github_oidc, oci_registry, or public_release trust-root claims",
    )
    artifacts_evidence_promote_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_bundle_registry_parser = artifacts_sub.add_parser("bundle-registry")
    artifacts_bundle_registry_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_bundle_registry_parser.add_argument("--artifact-class", default="")
    artifacts_bundle_registry_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_registry_latest_parser = artifacts_sub.add_parser("registry-latest")
    artifacts_registry_latest_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_registry_latest_parser.add_argument("--artifact-class", required=True)
    artifacts_registry_latest_parser.add_argument("--consumer-intent", default="agent")
    artifacts_registry_latest_parser.add_argument("--subject-digest", default="", help="expected subject, aggregate, ABI, or record digest")
    artifacts_registry_latest_parser.add_argument("--source-repo", default="", help="expected source repository")
    artifacts_registry_latest_parser.add_argument("--source-ref", default="", help="expected source snapshot or revision")
    artifacts_registry_latest_parser.add_argument("--access-policy", default="", help="expected access policy")
    artifacts_registry_latest_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode",
    )
    artifacts_registry_latest_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_bundle_registry_upgrade_parser = artifacts_sub.add_parser("bundle-registry-upgrade")
    artifacts_bundle_registry_upgrade_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_bundle_registry_upgrade_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_bundle_registry_upgrade_parser.add_argument("--source-repo", default="", help="default source repository for legacy records")
    artifacts_bundle_registry_upgrade_parser.add_argument("--producer", default="", help="default producer identity for legacy records")
    artifacts_bundle_registry_upgrade_parser.add_argument(
        "--trust-root-mode",
        default="host_managed",
        choices=selected_parser_choices("artifacts", lambda: artifact_bundles.TRUST_ROOT_MODES),
        help="trust root mode asserted for upgraded legacy registry records",
    )
    artifacts_bundle_registry_upgrade_parser.add_argument("--dry-run", action="store_true", help="report upgrades without writing records")
    artifacts_bundle_registry_upgrade_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_bundle_registry_repair_refs_parser = artifacts_sub.add_parser("bundle-registry-repair-evidence-refs")
    artifacts_bundle_registry_repair_refs_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_bundle_registry_repair_refs_parser.add_argument("--artifact-class", default="", help="optional artifact class filter")
    artifacts_bundle_registry_repair_refs_parser.add_argument(
        "--replacement-ref",
        default="",
        help="durable maintenance evidence ref to add when ephemeral refs are removed",
    )
    artifacts_bundle_registry_repair_refs_parser.add_argument(
        "--all-records",
        action="store_true",
        help="repair non-latest records too; default repairs only latest records",
    )
    artifacts_bundle_registry_repair_refs_parser.add_argument("--dry-run", action="store_true", help="report repairs without writing records")
    artifacts_bundle_registry_repair_refs_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trust_gate_parser = artifacts_sub.add_parser("trust-gate")
    artifacts_trust_gate_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_trust_gate_parser.add_argument("--artifact-class", required=True)
    artifacts_trust_gate_parser.add_argument("--subject-digest", default="", help="expected subject, aggregate, ABI, or record digest")
    artifacts_trust_gate_parser.add_argument("--record-id", default="", help="specific registry record id")
    artifacts_trust_gate_parser.add_argument("--consumer-intent", default="agent")
    artifacts_trust_gate_parser.add_argument("--source-repo", default="", help="expected source repository")
    artifacts_trust_gate_parser.add_argument("--source-ref", default="", help="expected source snapshot or revision")
    artifacts_trust_gate_parser.add_argument("--access-policy", default="", help="expected access policy")
    artifacts_trust_gate_parser.add_argument(
        "--trust-root-mode",
        default="",
        choices=selected_parser_choices("artifacts", lambda: ("", *artifact_bundles.TRUST_ROOT_MODES)),
        help="expected trust root mode",
    )
    artifacts_trust_gate_parser.add_argument("--allow-non-latest", action="store_true", help="permit selecting a non-latest non-terminal record")
    artifacts_trust_gate_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trust_tools_parser = artifacts_sub.add_parser("trust-tools")
    artifacts_trust_tools_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trust_tools_python_parser = artifacts_sub.add_parser("trust-tools-python")
    artifacts_trust_tools_python_parser.add_argument("--apply", action="store_true", help="create/update the host-managed Python trust-tool runtime")
    artifacts_trust_tools_python_parser.add_argument("--force", action="store_true", help="replace existing non-managed tool entrypoint symlinks")
    artifacts_trust_tools_python_parser.add_argument("--python", default="", help="Python executable used to create the host-managed venv")
    artifacts_trust_tools_python_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trust_tools_proof_parser = artifacts_sub.add_parser("trust-tools-proof")
    artifacts_trust_tools_proof_parser.add_argument("--no-write", action="store_true", help="run proof without updating durable latest/history")
    artifacts_trust_tools_proof_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_trust_coverage_parser = artifacts_sub.add_parser("trust-coverage")
    artifacts_trust_coverage_parser.add_argument("--registry-dir", default="", help="local artifact bundle registry root")
    artifacts_trust_coverage_parser.add_argument("--manual-evidence-root", action="append", default=[], help="extra manual evidence root")
    artifacts_trust_coverage_parser.add_argument(
        "--source-root",
        default="",
        help="explicit public seed root for policy/ABI/manifest source freshness",
    )
    artifacts_trust_coverage_parser.add_argument("--source-repo", default="", help="source owner repo for explicit drift/freshness context")
    artifacts_trust_coverage_parser.add_argument("--source-ref", default="", help="source ref that durable evidence must prove")
    artifacts_trust_coverage_parser.add_argument(
        "--durable-only",
        action="store_true",
        help="ignore tmp/manual evidence and report persistent registry plus trust-gate coverage",
    )
    artifacts_trust_coverage_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_quarantine_parser = artifacts_sub.add_parser("quarantine")
    artifacts_quarantine_parser.add_argument("--path", required=True)
    artifacts_quarantine_parser.add_argument("--verify-workload", default="manual")
    artifacts_quarantine_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    artifacts_validate_parser = artifacts_sub.add_parser("validate")
    artifacts_validate_parser.add_argument("--strict", action="store_true", help="treat warnings as non-zero")
    artifacts_validate_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def dispatch_artifacts(args: Any, parser: Any, argv: list[str]) -> int:
    if args.command == "artifacts":
        if args.artifacts_command == "paths":
            data = artifacts_paths()
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifacts root: {data.get('root')}")
                print(f"inventory latest: {data.get('inventory', {}).get('latest')}")
                print(f"validate: {data.get('validate', {}).get('command')}")
            return 0
        if args.artifacts_command == "inventory":
            data = artifacts_inventory(scope=str(args.scope), write_latest=True, with_usage=bool(args.with_usage))
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifacts inventory: records={summary.get('records')} existing={summary.get('existing_local')} classes={summary.get('by_classification')}")
                for record in data.get("records", [])[:12]:
                    decision = record.get("decision", {}) if isinstance(record.get("decision"), dict) else {}
                    print(f"{record.get('classification'):<16} {record.get('confidence'):<6} {record.get('id')} {decision.get('decision')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command in {"explain", "trace"}:
            data = artifacts_trace(str(args.path), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                record = data.get("record", {}) if isinstance(data.get("record"), dict) else {}
                decision = record.get("decision", {}) if isinstance(record.get("decision"), dict) else {}
                backup = record.get("backup_state", {}) if isinstance(record.get("backup_state"), dict) else {}
                print(f"artifact: {record.get('id')} {record.get('path')}")
                print(f"classification: {decision.get('classification')} confidence={decision.get('confidence')} decision={decision.get('decision')}")
                print(f"backup: {backup.get('status')} restore={backup.get('restore_command')}")
                print(f"process_refs: {record.get('process_refs', {}).get('ref_count') if isinstance(record.get('process_refs'), dict) else None}")
                print(f"config_refs: {record.get('config_refs', {}).get('hit_count') if isinstance(record.get('config_refs'), dict) else None}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "usage":
            data = artifacts_usage(str(args.path), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact usage: {data.get('matched_spec_id')} events={summary.get('event_count')} current_live={summary.get('current_live_event_count')}")
                print(f"last_live: {summary.get('last_current_live_event')}")
                print(f"last_route_log: {summary.get('last_historical_route_log_event')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "timeline":
            data = artifacts_timeline(str(args.path), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact timeline: {data.get('matched_spec_id')} events={summary.get('event_count')}")
                for event in data.get("timeline", [])[:12]:
                    print(f"{event.get('time') or '-'} {event.get('kind')} {event.get('source')} {event.get('strength')}: {event.get('claim')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "snapshot":
            data = artifacts_snapshot(scope=str(args.scope), history_days=int(args.history_days), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifacts snapshot: records={summary.get('records')} current_live={summary.get('current_live_records')} classes={summary.get('by_classification')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "observe":
            data = artifacts_observe(
                str(args.path),
                seconds=float(args.seconds),
                interval=float(args.interval),
                recursive=bool(args.recursive),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact observe: access_observed={summary.get('access_observed')} samples={summary.get('sample_count')} inotify={summary.get('inotify_event_count')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "restore-check":
            data = artifacts_restore_check(str(args.path), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact restore-check: {summary.get('status')} fails={summary.get('fails')} source={data.get('restore_source')}")
            return 0 if data.get("ok") else 2
        if args.artifacts_command == "quarantine-rehearsal":
            data = artifacts_quarantine_rehearsal(
                str(args.path),
                verify_workload=str(args.verify_workload),
                observe_seconds=float(args.observe_seconds),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifact quarantine rehearsal: ok={data.get('ok')} blocked={','.join(data.get('blocked_reasons', [])) or 'none'}")
            return 0 if data.get("ok") else 2
        if args.artifacts_command == "content-identity":
            data = artifacts_content_identity(
                str(args.path),
                max_files=int(args.max_files),
                max_file_bytes=int(args.max_file_bytes),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact content-identity: files={summary.get('files_scanned')} moves={summary.get('moves_detected')} duplicates={summary.get('same_content_different_path')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "classify":
            if args.target or args.artifact_class:
                data = artifact_bundles.classify_artifact(
                    str(args.target) if args.target else None,
                    artifact_class=str(args.artifact_class or "public_source_seed"),
                )
                if args.json:
                    _core.print_json(data)
                else:
                    print(f"artifact bundle classify: class={data.get('artifact_class')} required={','.join(data.get('required_controls', [])) or 'none'}")
                    for control, decision in data.get("deferred_controls", {}).items():
                        if isinstance(decision, dict):
                            print(f"not-required: {control}: {decision.get('reason')}")
                return 0 if data.get("ok") else 1
            data = artifacts_classify(scope=str(args.scope), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifacts classify: records={summary.get('records')} classes={summary.get('by_classification')}")
                for name, records in data.get("classes", {}).items():
                    print(f"{name}: {len(records)}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "requirements":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifacts_requirements(
                artifact_class=str(args.artifact_class or ""),
                registry_dir=registry_dir,
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact requirements: "
                    f"classes={summary.get('artifact_classes')} "
                    f"missing={len(summary.get('missing_artifact_classes', []))}"
                )
                for row in data.get("rows", []):
                    if isinstance(row, dict):
                        source = row.get("source_route", {}) if isinstance(row.get("source_route"), dict) else {}
                        controls = row.get("controls", {}) if isinstance(row.get("controls"), dict) else {}
                        print(
                            f"{row.get('artifact_class')}: "
                            f"owner={row.get('owner_repo')} "
                            f"contract={source.get('contract_surface_status')} "
                            f"required={','.join(controls.get('required', [])) or 'none'}"
                        )
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "producer-profiles":
            data = artifacts_producer_profiles(
                profile_id=str(args.profile_id or ""),
                owner_repo=str(args.owner_repo or ""),
                artifact_class=str(args.artifact_class or ""),
                workspace_root=Path(str(args.workspace_root)) if args.workspace_root else None,
                owner_repo_root=args.owner_repo_root,
                require_command_resolution=bool(args.require_command_resolution),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact producer profiles: "
                    f"profiles={summary.get('profiles')} "
                    f"artifact_classes={summary.get('artifact_class_count')}"
                )
                for row in data.get("rows", []):
                    if isinstance(row, dict):
                        print(
                            f"{row.get('profile_id')}: "
                            f"owner={row.get('owner_repo')} "
                            f"classes={','.join(row.get('artifact_classes', []))}"
                        )
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "scenarios":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_scenarios(
                scenario_id=str(args.scenario_id or ""),
                artifact_class=str(args.artifact_class or ""),
                registry_dir=registry_dir,
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact scenarios: "
                    f"scenarios={summary.get('scenarios')} "
                    f"synthetic={summary.get('executable_synthetic_coverage')} "
                    f"owner_required={summary.get('owner_or_manual_evidence_required')}"
                )
                for row in data.get("rows", []):
                    if isinstance(row, dict):
                        print(
                            f"{row.get('scenario_id')}: "
                            f"class={row.get('artifact_class')} "
                            f"coverage={row.get('coverage_status')} "
                            f"consumer={row.get('consumer_intent')}"
                        )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "affected":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifacts_affected(
                artifact_class=str(args.artifact_class or ""),
                registry_dir=registry_dir,
                changed_paths=[str(item) for item in args.changed_path],
                changed_source_repo=str(args.source_repo or ""),
                changed_source_ref=str(args.source_ref or ""),
                accept_sibling_lag=bool(args.accept_sibling_lag),
                fail_on_blocking=bool(args.fail_on_blocking),
                fail_on_accepted_lag=bool(args.fail_on_accepted_lag),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                gate = data.get("gate", {}) if isinstance(data.get("gate"), dict) else {}
                print(
                    "artifact affected: "
                    f"classes={summary.get('artifact_classes')} "
                    f"affected={summary.get('affected')} "
                    f"statuses={summary.get('status_counts')}"
                )
                for row in data.get("rows", []):
                    if isinstance(row, dict) and (row.get("affected") or row.get("verdict") != "fresh"):
                        drift = row.get("drift") if isinstance(row.get("drift"), dict) else {}
                        blocking = "blocking" if drift.get("operationally_blocking") else "nonblocking"
                        print(
                            f"{row.get('verdict')}: {row.get('artifact_class')}: "
                            f"drift={drift.get('status') or 'unknown'} {blocking}: "
                            f"{', '.join(row.get('reasons', [])) or 'registry/gate state'}"
                        )
                if gate.get("enabled") and not gate.get("allowed"):
                    print(f"artifact affected gate: deny reasons={','.join(gate.get('reasons', [])) or 'unknown'}")
            gate = data.get("gate", {}) if isinstance(data.get("gate"), dict) else {}
            return int(gate.get("exit_code") if isinstance(gate.get("exit_code"), int) else (0 if data.get("ok") else 1))
        if args.artifacts_command == "update-lane":
            data = artifacts_update_lane(
                artifact_class=str(args.artifact_class or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact update lane: "
                    f"tuf={summary.get('tuf_status')} "
                    f"scitt={summary.get('scitt_status')} "
                    f"updateable={summary.get('updateable_artifact_classes')}"
                )
                for row in data.get("rows", []):
                    if isinstance(row, dict):
                        print(f"{row.get('artifact_class')}: applies={row.get('applies')} sidecar={row.get('metadata_sidecar')}")
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "update-verify":
            previous_trusted = Path(str(args.previous_trusted)) if args.previous_trusted else None
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_update_verify(
                Path(str(args.metadata)),
                previous_trusted_path=previous_trusted,
                now=str(args.now or ""),
                registry_dir=registry_dir,
                subject_digest=str(args.subject_digest or ""),
                expected_source_repo=str(args.source_repo or ""),
                expected_trust_root_mode=str(args.trust_root_mode or ""),
                require_trust_gate=bool(args.require_trust_gate),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact update verify: "
                    f"verdict={data.get('verdict')} "
                    f"class={data.get('artifact_class')} "
                    f"metadata_sha256={data.get('metadata_sha256')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "update-repo-build":
            key_dir = Path(str(args.key_dir)) if args.key_dir else None
            data = artifacts_update_repo_build(
                Path(str(args.repository)),
                target_file=Path(str(args.target_file)),
                target_path=str(args.target_path or ""),
                artifact_class=str(args.artifact_class or ""),
                version=int(args.version),
                key_dir=key_dir,
                generate_missing_keys=bool(args.dev_generate_keys),
                root_expires=str(args.root_expires or ""),
                targets_expires=str(args.targets_expires or ""),
                snapshot_expires=str(args.snapshot_expires or ""),
                timestamp_expires=str(args.timestamp_expires or ""),
                now=str(args.now or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact update repo build: "
                    f"verdict={data.get('verdict')} "
                    f"target={data.get('target_path')} "
                    f"digest={data.get('target_digest')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "update-repo-verify":
            trusted_root = Path(str(args.trusted_root)) if args.trusted_root else None
            previous_trusted = Path(str(args.previous_trusted)) if args.previous_trusted else None
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_update_repo_verify(
                Path(str(args.repository)),
                target_path=str(args.target_path),
                artifact_class=str(args.artifact_class or ""),
                target_digest=str(args.target_digest or ""),
                trusted_root_path=trusted_root,
                previous_trusted_path=previous_trusted,
                now=str(args.now or ""),
                registry_dir=registry_dir,
                subject_digest=str(args.subject_digest or ""),
                expected_source_repo=str(args.source_repo or ""),
                expected_trust_root_mode=str(args.trust_root_mode or ""),
                require_trusted_root=bool(args.require_trusted_root),
                require_trust_gate=bool(args.require_trust_gate),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact update repo verify: "
                    f"verdict={data.get('verdict')} "
                    f"target={data.get('target_path')} "
                    f"timestamp={data.get('timestamp_sha256')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "scitt-verify":
            receipt_path = Path(str(args.receipt)) if args.receipt else None
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_scitt_verify(
                Path(str(args.statement)),
                receipt_path=receipt_path,
                external_relying_party=bool(args.external_relying_party),
                require_receipt=bool(args.require_receipt),
                registry_dir=registry_dir,
                expected_record_id=str(args.record_id or ""),
                require_registry_link=bool(args.require_registry_link),
                expected_statement_class=str(args.statement_class or ""),
                expected_artifact_digest=str(args.artifact_digest or ""),
                expected_issuer=str(args.issuer or ""),
                expected_transparency_service=str(args.transparency_service or ""),
                now=str(args.now or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact SCITT verify: "
                    f"verdict={data.get('verdict')} "
                    f"class={data.get('statement_class')} "
                    f"receipt_present={data.get('receipt_present')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "oci-verify":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_oci_verify(
                Path(str(args.evidence)),
                artifact_class=str(args.artifact_class or ""),
                registry_ref=str(args.registry_ref or ""),
                subject_digest=str(args.subject_digest or ""),
                required_referrer_types=[str(item) for item in args.required_referrer_type],
                registry_dir=registry_dir,
                record_id=str(args.record_id or ""),
                record_subject_digest=str(args.record_subject_digest or ""),
                source_repo=str(args.source_repo or ""),
                trust_root_mode=str(args.trust_root_mode or ""),
                consumer_intent=str(args.consumer_intent or "runtime"),
                allow_tag_reference=bool(args.allow_tag_reference),
                allow_missing_referrers=bool(args.allow_missing_referrers),
                require_trust_gate=bool(args.require_trust_gate),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact OCI verify: "
                    f"verdict={data.get('verdict')} "
                    f"class={data.get('artifact_class')} "
                    f"digest_pinned={data.get('digest_pinned')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "oci-layout-publish":
            try:
                referrers = [parse_oci_referrer_arg(str(item)) for item in args.referrer]
            except ValueError as exc:
                data = {"ok": False, "error": str(exc), "errors": [str(exc)]}
                if args.json:
                    _core.print_json(data)
                else:
                    print(f"error: {exc}")
                return 1
            data = artifacts_oci_layout_publish(
                Path(str(args.subject)),
                Path(str(args.layout_dir)),
                artifact_class=str(args.artifact_class or ""),
                registry_ref=str(args.registry_ref or ""),
                artifact_type=str(args.artifact_type or ""),
                subject_media_type=str(args.subject_media_type or ""),
                referrers=referrers,
                record_id=str(args.record_id or ""),
                record_subject_digest=str(args.record_subject_digest or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact OCI layout publish: "
                    f"ok={data.get('ok')} digest={data.get('subject_digest')} "
                    f"ref={data.get('registry_ref')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "oci-consume":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else None
            data = artifacts_oci_consume(
                Path(str(args.evidence)),
                Path(str(args.output_dir)),
                artifact_class=str(args.artifact_class or ""),
                registry_ref=str(args.registry_ref or ""),
                subject_digest=str(args.subject_digest or ""),
                required_referrer_types=[str(item) for item in args.required_referrer_type],
                registry_dir=registry_dir,
                record_id=str(args.record_id or ""),
                record_subject_digest=str(args.record_subject_digest or ""),
                source_repo=str(args.source_repo or ""),
                trust_root_mode=str(args.trust_root_mode or ""),
                consumer_intent=str(args.consumer_intent or "runtime"),
                allow_tag_reference=bool(args.allow_tag_reference),
                allow_missing_referrers=bool(args.allow_missing_referrers),
                require_trust_gate=bool(args.require_trust_gate),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact OCI consume: "
                    f"verdict={data.get('verdict')} "
                    f"ok={data.get('ok')} "
                    f"subject={_core.nested_get(data, ['pulled', 'subject', 'path'])}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
                for item in data.get("warnings", []):
                    print(f"warning: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "build-sidecars":
            data = artifact_bundles.build_sidecars(
                str(args.bundle_dir),
                artifact_class=str(args.artifact_class),
                contract_surface_id=str(args.contract_surface_id or "") or None,
                manifest_ref=str(args.manifest or "") or None,
                mode=str(args.mode),
                subject_root=str(args.subject_root or "") or None,
                owner_repo=str(args.owner_repo or ""),
                source_ref=str(args.source_ref or ""),
                access_policy=str(args.access_policy or ""),
            )
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifact bundle sidecars: {data.get('bundle_dir')} class={data.get('artifact_class')} surface={data.get('contract_surface_id')}")
                print(f"written: {', '.join(data.get('written', []))}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "sign":
            data = artifact_bundles.sign_bundle(str(args.bundle_dir), backend=str(args.backend))
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifact bundle sign: {data.get('status')} required={data.get('required')} reason={data.get('reason')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "kag-sign-identity":
            data = kag_artifacts.sign_kag_identity(
                str(args.payload),
                backend=str(args.backend),
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "KAG identity sign: "
                    f"ok={data.get('ok')} "
                    f"class={data.get('artifact_class')} "
                    f"digest={data.get('identity_digest')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "kag-verify-identity":
            data = kag_artifacts.verify_kag_identity_signature(str(args.payload))
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "KAG identity verify: "
                    f"ok={data.get('ok')} "
                    f"class={data.get('artifact_class')} "
                    f"digest={data.get('identity_digest')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "verify":
            data = artifact_bundles.verify_bundle(
                str(args.bundle_dir),
                subject_root=str(args.subject_root or "") or None,
                write=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifact bundle verify: ok={data.get('ok')} class={data.get('artifact_class')} required={','.join(data.get('required_controls', [])) or 'none'}")
                for item in data.get("missing", []):
                    print(f"missing: {item}")
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "kag-retention-plan":
            data = kag_artifacts.write_kag_retention_plan(
                str(args.cas_root),
                str(args.registry_dir),
                str(args.output),
                pinned_record_ids=[str(item) for item in args.pin_record_id],
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "KAG retention plan: "
                    f"allowed={data.get('deletion_allowed')} "
                    f"candidates={summary.get('candidate_files')} "
                    f"bytes={summary.get('candidate_bytes')}"
                )
                for item in data.get("blockers", []):
                    print(f"blocker: {item}")
            return 0 if data.get("deletion_allowed") else 1
        if args.artifacts_command == "kag-retention-apply":
            data = kag_artifacts.apply_kag_retention_plan(
                str(args.plan),
                str(args.receipt),
                confirm=bool(args.confirm),
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "KAG retention apply: "
                    f"ok={data.get('ok')} "
                    f"deleted={summary.get('deleted_files')} "
                    f"bytes={summary.get('deleted_bytes')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "materialize-subjects":
            store_root = Path(str(args.store_root)) if args.store_root else None
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifact_bundles.materialize_artifact_subjects(
                str(args.bundle_dir),
                store_root=store_root,
                registry_dir=registry_dir,
                manifest_ref=str(args.manifest or "") or None,
                subject_root=str(args.subject_root or "") or None,
                consumer_intent=str(args.consumer_intent or ""),
                expected_source_repo=str(args.source_repo or ""),
                expected_source_ref=str(args.source_ref or ""),
                expected_access_policy=str(args.access_policy or ""),
                expected_trust_root_mode=str(args.trust_root_mode or ""),
                record_id=str(args.record_id or ""),
                require_latest=not bool(args.allow_non_latest),
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact subjects materialize: "
                    f"ok={data.get('ok')} "
                    f"store_dir={data.get('store_dir')} "
                    f"admission={(data.get('materialization_admission') or {}).get('verdict') if isinstance(data.get('materialization_admission'), dict) else None} "
                    f"trust_gate={(data.get('trust_gate') or {}).get('verdict') if isinstance(data.get('trust_gate'), dict) else None}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "release-check":
            data = artifact_bundles.release_check(
                str(args.bundle_dir),
                enforcement=str(args.enforcement),
                subject_root=str(args.subject_root or "") or None,
            )
            if args.json:
                _core.print_json(data)
            else:
                verification = data.get("verification", {}) if isinstance(data.get("verification"), dict) else {}
                print(f"artifact bundle release-check: ok={data.get('ok')} verification_ok={data.get('verification_ok')} enforcement={data.get('enforcement')}")
                for item in verification.get("missing", []):
                    print(f"missing: {item}")
                for item in verification.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "bundle-register":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            try:
                trust_root_evidence = parse_json_object_argument(
                    str(args.trust_root_evidence_json or ""),
                    argument_name="--trust-root-evidence-json",
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                data = {"ok": False, "error": f"invalid --trust-root-evidence-json: {exc}"}
                if args.json:
                    _core.print_json(data)
                else:
                    print(data["error"])
                return 1
            data = artifact_bundles.write_bundle_registry_record(
                str(args.bundle_dir),
                registry_dir,
                lifecycle_state=str(args.lifecycle_state),
                consumer_refs=[str(item) for item in args.consumer_ref],
                evidence_refs=[str(item) for item in args.evidence_ref],
                supersedes=[str(item) for item in args.supersedes],
                revocation_reason=str(args.revocation_reason or ""),
                source_repo=str(args.source_repo or ""),
                source_ref=str(args.source_ref or ""),
                producer=str(args.producer or ""),
                trust_root_mode=str(args.trust_root_mode),
                trust_root_evidence=trust_root_evidence,
                subject_root=str(args.subject_root or "") or None,
                public_release_archive=(
                    str(args.public_release_archive or "") or None
                ),
            )
            if args.json:
                _core.print_json(data)
            else:
                record = data.get("record", {}) if isinstance(data.get("record"), dict) else {}
                print(f"artifact bundle register: ok={data.get('ok')} state={record.get('lifecycle_state')} latest={record.get('latest_eligible')}")
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "evidence-promote":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            try:
                trust_root_evidence = parse_json_object_argument(
                    str(args.trust_root_evidence_json or ""),
                    argument_name="--trust-root-evidence-json",
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                data = {"ok": False, "error": f"invalid --trust-root-evidence-json: {exc}"}
                if args.json:
                    _core.print_json(data)
                else:
                    print(data["error"])
                return 1
            data = artifact_bundles.promote_bundle_evidence(
                str(args.bundle_dir),
                registry_dir,
                lifecycle_state=str(args.lifecycle_state),
                consumer_refs=[str(item) for item in args.consumer_ref],
                evidence_refs=[str(item) for item in args.evidence_ref],
                supersedes=[str(item) for item in args.supersedes],
                revocation_reason=str(args.revocation_reason or ""),
                source_repo=str(args.source_repo or ""),
                source_ref=str(args.source_ref or ""),
                producer=str(args.producer or ""),
                trust_root_mode=str(args.trust_root_mode),
                trust_root_evidence=trust_root_evidence,
                subject_root=str(args.subject_root or "") or None,
                public_release_archive=(
                    str(args.public_release_archive or "") or None
                ),
            )
            if args.json:
                _core.print_json(data)
            else:
                promotion = data.get("promotion", {}) if isinstance(data.get("promotion"), dict) else {}
                print(
                    "artifact evidence promote: "
                    f"ok={data.get('ok')} "
                    f"class={promotion.get('artifact_class')} "
                    f"state={promotion.get('lifecycle_state')} "
                    f"trust_root={promotion.get('trust_root_mode')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "bundle-registry":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            artifact_class = str(args.artifact_class or "") or None
            data = artifact_bundles.read_bundle_registry(registry_dir, artifact_class=artifact_class)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact bundle registry: records={summary.get('records')} latest={summary.get('latest')}")
                for class_id, record in data.get("latest_by_artifact_class", {}).items():
                    if isinstance(record, dict):
                        print(f"latest: {class_id}: {record.get('record_id')} state={record.get('lifecycle_state')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "registry-latest":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifacts_registry_latest(
                artifact_class=str(args.artifact_class),
                registry_dir=registry_dir,
                consumer_intent=str(args.consumer_intent or "agent"),
                subject_digest=str(args.subject_digest or ""),
                expected_source_repo=str(args.source_repo or ""),
                expected_source_ref=str(args.source_ref or ""),
                expected_access_policy=str(args.access_policy or ""),
                expected_trust_root_mode=str(args.trust_root_mode or ""),
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact registry latest: "
                    f"ok={data.get('ok')} "
                    f"class={data.get('artifact_class')} "
                    f"record={data.get('latest_record_id')} "
                    f"verdict={_core.nested_get(data, ['trust_gate', 'verdict'])}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "bundle-registry-upgrade":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifact_bundles.upgrade_legacy_bundle_registry(
                registry_dir,
                artifact_class=str(args.artifact_class or ""),
                source_repo=str(args.source_repo or ""),
                producer=str(args.producer or ""),
                trust_root_mode=str(args.trust_root_mode),
                dry_run=bool(args.dry_run),
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact bundle registry upgrade: "
                    f"ok={data.get('ok')} "
                    f"dry_run={data.get('dry_run')} "
                    f"upgraded={summary.get('upgraded')} "
                    f"unchanged={summary.get('unchanged')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "bundle-registry-repair-evidence-refs":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifact_bundles.repair_bundle_registry_evidence_refs(
                registry_dir,
                artifact_class=str(args.artifact_class or ""),
                replacement_ref=str(args.replacement_ref or ""),
                latest_only=not bool(args.all_records),
                dry_run=bool(args.dry_run),
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact bundle registry evidence-ref repair: "
                    f"ok={data.get('ok')} "
                    f"dry_run={data.get('dry_run')} "
                    f"repaired={summary.get('repaired')} "
                    f"unchanged={summary.get('unchanged')}"
                )
                for item in data.get("errors", []):
                    print(f"error: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "trust-gate":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifact_bundles.trust_gate(
                registry_dir,
                artifact_class=str(args.artifact_class),
                subject_digest=str(args.subject_digest or ""),
                record_id=str(args.record_id or ""),
                consumer_intent=str(args.consumer_intent or "agent"),
                expected_source_repo=str(args.source_repo or ""),
                expected_source_ref=str(args.source_ref or ""),
                expected_access_policy=str(args.access_policy or ""),
                expected_trust_root_mode=str(args.trust_root_mode or ""),
                require_latest=not bool(args.allow_non_latest),
            )
            if args.json:
                _core.print_json(data)
            else:
                print(
                    "artifact trust gate: "
                    f"verdict={data.get('verdict')} "
                    f"class={data.get('artifact_class')} "
                    f"record={data.get('record_id')}"
                )
                for item in data.get("reasons", []):
                    print(f"reason: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "trust-tools":
            data = artifacts_trust_tools(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifact trust tools: {summary.get('status')} available={','.join(summary.get('available_tools', [])) or 'none'}")
                if summary.get("missing_controls"):
                    print(f"missing controls: {', '.join(summary.get('missing_controls', []))}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "trust-tools-python":
            data = artifacts_trust_tools_python(
                apply=bool(args.apply),
                force=bool(args.force),
                python_executable=str(args.python or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                mode = "apply" if args.apply else "dry-run"
                status_text = "ok" if data.get("ok") else "failed"
                print(f"artifact trust tools python: {status_text} mode={mode} venv={_core.nested_get(data, ['python', 'venv'])}")
                for item in data.get("failures", []):
                    print(f"failure: {item}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "trust-tools-proof":
            data = artifact_trust_tools_proof(write_latest=not bool(args.no_write))
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact trust tools proof: "
                    f"{summary.get('status')} checks={summary.get('checks')} failures={summary.get('failures')}"
                )
                for item in data.get("checks", []):
                    if not item.get("ok"):
                        print(f"failure: {item.get('id')}: {item.get('message')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "trust-coverage":
            registry_dir = Path(str(args.registry_dir)) if args.registry_dir else ARTIFACTS_BUNDLE_REGISTRY_ROOT
            data = artifacts_trust_coverage(
                registry_dir=registry_dir,
                manual_evidence_roots=[str(item) for item in args.manual_evidence_root],
                durable_only=bool(args.durable_only),
                source_root=Path(str(args.source_root)) if args.source_root else None,
                source_repo=str(args.source_repo or ""),
                source_ref=str(args.source_ref or ""),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(
                    "artifact trust coverage: "
                    f"classes={summary.get('artifact_classes')} "
                    f"fully_covered={summary.get('fully_covered')} "
                    f"durable_gate_covered={summary.get('durable_gate_covered')} "
                    f"deferred={summary.get('deferred_with_real_blocker')}"
                )
                for row in data.get("rows", []):
                    covered_statuses = {"FULLY_COVERED", "DURABLE_GATE_COVERED"}
                    if isinstance(row, dict) and row.get("status") not in covered_statuses:
                        print(f"{row.get('status')}: {row.get('artifact_class')}: {row.get('remaining_blocker')}")
            return 0 if data.get("ok") else 1
        if args.artifacts_command == "quarantine":
            data = artifacts_quarantine_plan(
                path=str(args.path),
                verify_workload=str(args.verify_workload),
                write_latest=True,
            )
            if args.json:
                _core.print_json(data)
            else:
                print(f"artifact quarantine plan: ok={data.get('ok')} dry_run={data.get('dry_run')} blocked={','.join(data.get('blocked_reasons', [])) or 'none'}")
                print(f"target: {data.get('quarantine_target')}")
            return 0 if data.get("ok") else 2
        if args.artifacts_command == "validate":
            data = artifacts_validate(strict=bool(args.strict), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
                print(f"artifacts validate: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
                for item in data.get("checks", []):
                    if item.get("level") != "ok":
                        print(f"{item.get('level')}: {item.get('key')}: {item.get('message')}")
            if data.get("summary", {}).get("fails"):
                return 1
            if args.strict and data.get("summary", {}).get("warnings"):
                return 2
            return 0
        parser.error("unknown artifacts command")
    parser.error("unknown command")
    return 64
