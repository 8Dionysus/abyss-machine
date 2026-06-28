from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "abyss_machine_source_install_runtime_parity_v1"
MAX_SAMPLE_ITEMS = 20


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": True, "stat_error": str(exc)}
    return {
        "path": str(path),
        "exists": True,
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size_bytes": int(stat.st_size),
        "mode": oct(stat.st_mode & 0o777),
    }


def relative_file_digests(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rows[path.relative_to(root).as_posix()] = file_sha256(path)
    return rows


def _sample(items: Sequence[str], limit: int = MAX_SAMPLE_ITEMS) -> list[str]:
    return list(items[:limit])


def compare_digest_maps(
    source: Mapping[str, str],
    installed: Mapping[str, str],
    *,
    label: str,
    sample_limit: int = MAX_SAMPLE_ITEMS,
) -> dict[str, Any]:
    source_keys = set(source)
    installed_keys = set(installed)
    missing = sorted(source_keys - installed_keys)
    extra = sorted(installed_keys - source_keys)
    mismatched = sorted(path for path in source_keys & installed_keys if source[path] != installed[path])
    failures: list[str] = []
    if missing:
        failures.append(f"{label} missing files: {len(missing)}")
    if extra:
        failures.append(f"{label} extra files: {len(extra)}")
    if mismatched:
        failures.append(f"{label} digest mismatches: {len(mismatched)}")
    return {
        "status": "ok" if not failures else "failed",
        "label": label,
        "source_file_count": len(source),
        "installed_file_count": len(installed),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "digest_mismatch_count": len(mismatched),
        "missing_sample": _sample(missing, sample_limit),
        "extra_sample": _sample(extra, sample_limit),
        "digest_mismatch_sample": _sample(mismatched, sample_limit),
        "failures": failures,
    }


def compare_cli_file(source_cli: Path, installed_cli: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": path_state(source_cli),
        "installed": path_state(installed_cli),
        "status": "ok",
    }
    failures: list[str] = []
    if not source_cli.is_file():
        row["status"] = "failed"
        failures.append(f"source CLI missing: {source_cli}")
    elif not installed_cli.is_file():
        row["status"] = "failed"
        failures.append(f"installed CLI missing: {installed_cli}")
    else:
        source_digest = file_sha256(source_cli)
        installed_digest = file_sha256(installed_cli)
        row["source_sha256"] = source_digest
        row["installed_sha256"] = installed_digest
        if source_digest != installed_digest:
            row["status"] = "failed"
            failures.append("installed CLI digest differs from source CLI")
    row["failures"] = failures
    return row


def content_parity_summary(
    *,
    repo_root: Path,
    installed_cli: Path,
    installed_libexec_dir: Path,
    installed_share_root: Path,
    sample_limit: int = MAX_SAMPLE_ITEMS,
) -> dict[str, Any]:
    source_package_root = repo_root / "src" / "abyss_machine"
    source_seed_roots = {
        "generated": repo_root / "generated",
        "manifests": repo_root / "manifests",
    }
    cli = compare_cli_file(repo_root / "src" / "abyss_machine" / "cli.py", installed_cli)
    package = compare_digest_maps(
        relative_file_digests(source_package_root),
        relative_file_digests(installed_libexec_dir / "abyss_machine"),
        label="installed package",
        sample_limit=sample_limit,
    )
    package["source"] = str(source_package_root)
    package["installed"] = str(installed_libexec_dir / "abyss_machine")
    public_seed: dict[str, Any] = {}
    for root_id, source_root in source_seed_roots.items():
        row = compare_digest_maps(
            relative_file_digests(source_root),
            relative_file_digests(installed_share_root / root_id),
            label=f"installed public seed {root_id}",
            sample_limit=sample_limit,
        )
        row["source"] = str(source_root)
        row["installed"] = str(installed_share_root / root_id)
        public_seed[root_id] = row
    failures = list(cli["failures"]) + list(package["failures"])
    for row in public_seed.values():
        failures.extend(row["failures"])
    return {
        "status": "ok" if not failures else "failed",
        "cli": cli,
        "package": package,
        "public_seed": public_seed,
        "failures": failures,
    }


def compact_json_projection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"json_type": type(payload).__name__}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    check_counts: dict[str, int] = {}
    for check in checks:
        if not isinstance(check, dict):
            continue
        level = str(check.get("level") or check.get("status") or "unknown")
        check_counts[level] = check_counts.get(level, 0) + 1
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "ok": payload.get("ok"),
        "schema": payload.get("schema"),
        "version": payload.get("version"),
        "status": payload.get("status") or summary.get("status"),
        "summary_status": summary.get("status"),
        "check_count": len(checks),
        "check_counts": check_counts,
        "failure_count": check_counts.get("fail", 0) + check_counts.get("failed", 0),
        "warning_count": check_counts.get("warn", 0) + check_counts.get("warning", 0),
    }


def compact_command_result(
    *,
    name: str,
    command: Sequence[str],
    returncode: int,
    stdout: str,
    stderr: str,
    timed_out: bool = False,
) -> dict[str, Any]:
    payload: Any = None
    json_ok = False
    if stdout.strip():
        try:
            payload = json.loads(stdout)
            json_ok = True
        except json.JSONDecodeError:
            payload = None
    status = "timeout" if timed_out else "ok" if returncode == 0 else "failed"
    row: dict[str, Any] = {
        "name": name,
        "command": list(command),
        "status": status,
        "returncode": int(returncode),
        "timed_out": bool(timed_out),
        "json_ok": json_ok,
        "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
        "stderr_bytes": len(stderr.encode("utf-8", errors="replace")),
    }
    if json_ok:
        row["projection"] = compact_json_projection(payload)
    elif stderr:
        row["stderr_tail"] = stderr[-500:]
    return row


def runtime_summary(runtime_checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures = [
        str(check.get("name") or check.get("command") or "runtime")
        for check in runtime_checks
        if check.get("status") not in {"ok", "skipped"}
    ]
    warnings = [
        str(check.get("name") or check.get("command") or "runtime")
        for check in runtime_checks
        if isinstance(check.get("projection"), dict) and int(check["projection"].get("warning_count") or 0) > 0
    ]
    return {
        "status": "ok" if not failures else "failed",
        "check_count": len(runtime_checks),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failure_checks": failures,
        "warning_checks": warnings,
        "checks": list(runtime_checks),
    }


def build_parity_document(
    *,
    generated_at: str,
    repo_root: Path,
    installed_cli: Path,
    installed_libexec_dir: Path,
    installed_share_root: Path,
    runtime_checks: Sequence[Mapping[str, Any]],
    sample_limit: int = MAX_SAMPLE_ITEMS,
) -> dict[str, Any]:
    content = content_parity_summary(
        repo_root=repo_root,
        installed_cli=installed_cli,
        installed_libexec_dir=installed_libexec_dir,
        installed_share_root=installed_share_root,
        sample_limit=sample_limit,
    )
    runtime = runtime_summary(runtime_checks)
    failures = list(content["failures"])
    if runtime["status"] != "ok":
        failures.extend(f"runtime check failed: {item}" for item in runtime["failure_checks"])
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "ok": not failures,
        "status": "ok" if not failures else "failed",
        "repo_root": str(repo_root),
        "installed": {
            "cli": str(installed_cli),
            "libexec_dir": str(installed_libexec_dir),
            "share_root": str(installed_share_root),
        },
        "content_parity": content,
        "runtime": runtime,
        "failures": failures,
        "privacy": {
            "compact_summary_only": True,
            "raw_runtime_stdout_included": False,
            "raw_runtime_json_included": False,
        },
    }
