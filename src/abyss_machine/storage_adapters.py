from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Mapping, Sequence

from . import storage_contracts


ProcessSnapshotPort = Callable[[int, float], Mapping[str, Any]]
FdTargetsPort = Callable[[int, int], tuple[Sequence[str], bool]]
CommandRunnerPort = Callable[[Sequence[str], float], Mapping[str, Any]]
CommandExistsPort = Callable[[str], bool]
DiskUsagePort = Callable[[Path], Any]
PathChildrenPort = Callable[[Path], Sequence[Path]]
SizeBytesPort = Callable[[Path, float], int | None]
EuidPort = Callable[[], int]
ClockPort = Callable[[], float]
HookRunnerPort = Callable[[Path, str, Mapping[str, str], float], Mapping[str, Any]]


def current_euid() -> int:
    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid):
        return int(geteuid())
    return 0


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_tool_process(command: Sequence[str], timeout: float) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(command),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout"}
    except OSError as exc:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(exc)}


def directory_size(path: Path) -> int:
    total = 0
    try:
        for current, _, filenames in os.walk(path):
            for filename in filenames:
                try:
                    total += (Path(current) / filename).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def measure_path_size_bytes(
    path: Path,
    timeout: float = 20.0,
    *,
    command_exists: CommandExistsPort = tool_available,
    command_runner: CommandRunnerPort = run_tool_process,
) -> int | None:
    if not path.exists():
        return None
    if command_exists("du"):
        out = dict(command_runner(["du", "-sbx", str(path)], timeout))
        if out.get("ok"):
            first_line = str(out.get("stdout") or "").splitlines()
            first = first_line[0].split() if first_line else []
            if first:
                try:
                    return int(first[0])
                except ValueError:
                    pass
    try:
        return path.stat().st_size if path.is_file() else directory_size(path)
    except OSError:
        return None


def path_mtime_iso(path: Path) -> str | None:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    except OSError:
        return None


def path_atime_iso(path: Path) -> str | None:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_atime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    except OSError:
        return None


def path_age_days(path: Path, *, clock: ClockPort = time.time) -> float | None:
    try:
        age = clock() - path.stat().st_mtime
    except OSError:
        return None
    return round(age / 86400.0, 2)


def existing_ancestor(path: Path) -> Path:
    cursor = path
    while not cursor.exists() and cursor != cursor.parent:
        cursor = cursor.parent
    return cursor if cursor.exists() else Path("/")


def disk_usage_summary(path: Path, *, disk_usage: DiskUsagePort = shutil.disk_usage) -> dict[str, Any]:
    anchor = existing_ancestor(path)
    try:
        usage = disk_usage(anchor)
    except OSError as exc:
        return {"path": str(path), "anchor": str(anchor), "ok": False, "error": str(exc)}
    try:
        total = int(usage.total)
        used = int(usage.used)
        free = int(usage.free)
    except AttributeError:
        total = int(usage[0])
        used = int(usage[1])
        free = int(usage[2])
    percent = round((used / total) * 100.0, 2) if total else None
    return {
        "path": str(path),
        "anchor": str(anchor),
        "ok": True,
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_percent": percent,
    }


def path_storage_status(
    path: Path,
    expected_target: Path | None = None,
    *,
    include_size: bool = True,
    directory_size_fn: Callable[[Path], int] = directory_size,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_symlink": path.is_symlink(),
    }
    if expected_target is not None:
        item["expected_target"] = str(expected_target)
        item["target_exists"] = expected_target.exists()
    try:
        if path.exists() or path.is_symlink():
            item["resolved"] = str(path.resolve())
    except OSError as exc:
        item["resolve_error"] = str(exc)
    if include_size and path.exists():
        if path.is_dir():
            item["size_bytes"] = directory_size_fn(path)
        else:
            try:
                item["size_bytes"] = path.stat().st_size
            except OSError:
                item["size_bytes"] = None
    return item


def inventory_item_status(
    spec: Mapping[str, Any],
    *,
    measure: bool = True,
    size_bytes: SizeBytesPort = measure_path_size_bytes,
    clock: ClockPort = time.time,
) -> dict[str, Any]:
    path = Path(str(spec["path"]))
    item = dict(spec)
    exists = path.exists()
    item["exists"] = exists
    item["is_symlink"] = path.is_symlink()
    item["mtime"] = path_mtime_iso(path) if exists else None
    item["age_days"] = path_age_days(path, clock=clock) if exists else None
    if exists:
        try:
            item["resolved"] = str(path.resolve())
        except OSError:
            item["resolved"] = None
    item["measured"] = bool(measure and exists)
    item["size_bytes"] = size_bytes(path, 20.0) if item["measured"] else None
    return item


def list_path_children(path: Path) -> Sequence[Path]:
    return sorted(path.iterdir(), key=lambda item: item.name.lower())


def home_review_inventory_specs(
    *,
    home: Path,
    existing_paths: Sequence[str],
    children: PathChildrenPort = list_path_children,
) -> list[dict[str, Any]]:
    existing = {str(path) for path in existing_paths}
    try:
        candidates = list(children(home))
    except OSError:
        return []
    specs: list[dict[str, Any]] = []
    for child in candidates:
        if str(child) in existing:
            continue
        clean_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", child.name).strip("-").lower()
        if not clean_name:
            clean_name = hashlib.sha256(child.name.encode("utf-8")).hexdigest()[:12]
        specs.append({
            "id": "home_review_" + clean_name,
            "path": str(child),
            "category": "operator_review",
            "disposition": "manual_review",
            "reclaimability": "unknown",
            "confidence": "low",
            "reason": "Home top-level item included only for full review; no automatic cleanup.",
            "safe_automatic_cleanup": False,
            "measure_light": False,
            "tags": ["root", "home-review"],
        })
    return specs


def hook_directory_status(path: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    if path.exists():
        try:
            children = sorted(path.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            children = []
            errors.append(str(exc))
        for child in children:
            if child.name.startswith("."):
                continue
            is_file = child.is_file()
            entries.append({
                "name": child.name,
                "path": str(child),
                "is_file": is_file,
                "is_dir": child.is_dir(),
                "executable": is_file and os.access(child, os.X_OK),
                "disabled": child.name.endswith(".disabled"),
            })
    return {
        "path": str(path),
        "exists": path.exists(),
        "entries": entries,
        "executable_count": sum(1 for item in entries if item.get("executable") and not item.get("disabled")),
        "errors": errors,
    }


def run_hook_process(path: Path, stdin: str, env: Mapping[str, str], timeout: float) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [str(path)],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=dict(env),
        )
        return {
            "path": str(path),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip()[-4000:],
            "stderr": proc.stderr.strip()[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"path": str(path), "returncode": 124, "ok": False, "stderr": "timeout"}
    except OSError as exc:
        return {"path": str(path), "returncode": 127, "ok": False, "stderr": str(exc)}


def run_hook_stage_document(
    *,
    stage: str,
    valid_stages: Sequence[str],
    directories: Sequence[Path],
    payload: Mapping[str, Any] | None,
    enforce: bool,
    timeout: float,
    schema_prefix: str,
    version: str,
    generated_at: str,
    storage_policy_path: Path,
    abyss_machine_root: Path,
    cache_root: Path,
    runtime_root: Path,
    storage_root: Path,
    base_env: Mapping[str, str] | None = None,
    hook_runner: HookRunnerPort = run_hook_process,
) -> dict[str, Any]:
    valid_stage_names = {str(item) for item in valid_stages}
    if stage not in valid_stage_names:
        return {
            "schema": f"{schema_prefix}_storage_hooks_run_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "stage": stage,
            "error": "invalid hook stage",
            "valid_stages": sorted(valid_stage_names),
        }
    hook_payload = {
        "schema": f"{schema_prefix}_storage_hook_event_v1",
        "version": version,
        "generated_at": generated_at,
        "stage": stage,
        "payload": dict(payload or {}),
    }
    stdin = json.dumps(hook_payload, sort_keys=False)
    results: list[dict[str, Any]] = []
    for directory in directories:
        status = hook_directory_status(directory)
        for entry in status.get("entries", []):
            if not isinstance(entry, dict) or not entry.get("executable") or entry.get("disabled"):
                continue
            path = Path(str(entry.get("path")))
            env = dict(base_env or {})
            env.update({
                "ABYSS_MACHINE_HOOK_STAGE": stage,
                "ABYSS_MACHINE_STORAGE_POLICY": str(storage_policy_path),
                "ABYSS_MACHINE_ROOT": str(abyss_machine_root),
                "ABYSS_MACHINE_CACHE_ROOT": str(cache_root),
                "ABYSS_MACHINE_RUNTIME_ROOT": str(runtime_root),
                "ABYSS_MACHINE_STORAGE_ROOT": str(storage_root),
            })
            result = dict(hook_runner(path, stdin, env, timeout))
            result.setdefault("path", str(path))
            results.append(result)
    failed = [item for item in results if not item.get("ok")]
    return {
        "schema": f"{schema_prefix}_storage_hooks_run_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not failed or not enforce,
        "stage": stage,
        "enforce": enforce,
        "payload": hook_payload,
        "results": results,
        "summary": {
            "executed": len(results),
            "failed": len(failed),
            "blocked": bool(failed and enforce),
        },
    }


def path_text_matches(candidate: str, text: str | None) -> bool:
    if not candidate or not text:
        return False
    candidate = candidate.rstrip("/")
    clean_text = text.replace(" (deleted)", "")
    if candidate in clean_text:
        return True
    if clean_text.startswith("/"):
        clean_text = clean_text.rstrip("/")
        return clean_text == candidate or clean_text.startswith(candidate + "/")
    return False


def read_proc_fd_targets(pid: int, max_fd_per_process: int = 512) -> tuple[list[str], bool]:
    fd_root = Path("/proc") / str(pid) / "fd"
    try:
        fd_entries = list(fd_root.iterdir())[:max_fd_per_process]
    except OSError:
        return [], True
    targets: list[str] = []
    for entry in fd_entries:
        try:
            target = str(entry.readlink())
        except OSError:
            continue
        if target:
            targets.append(target)
    return targets, False


def process_path_usage_document(
    *,
    paths: Sequence[str],
    process_snapshot: ProcessSnapshotPort,
    generated_at: str,
    schema_prefix: str,
    version: str,
    process_latest_path: Path,
    interval: float = 0.5,
    top: int = 30,
    fd_targets: FdTargetsPort = read_proc_fd_targets,
    max_fd_per_process: int = 512,
) -> dict[str, Any]:
    unique_paths = sorted({path for path in paths if path and path != "/"})
    path_results: dict[str, dict[str, Any]] = {
        path: {
            "path": path,
            "active": False,
            "status": "clear",
            "active_processes": [],
            "match_sources": [],
        }
        for path in unique_paths
    }
    snapshot = dict(process_snapshot(max(top, 30), interval))
    processes = [item for item in snapshot.get("processes", []) if isinstance(item, dict)]
    fd_scan_errors = 0
    for proc in processes:
        pid = proc.get("pid")
        if not isinstance(pid, int):
            continue
        fields = {
            "cmdline": str(proc.get("cmdline") or ""),
            "cwd": str(proc.get("cwd") or ""),
            "exe": str(proc.get("exe") or ""),
            "cgroup": " ".join(str(item) for item in proc.get("cgroup", []) if isinstance(item, str)),
        }
        matches_by_path: dict[str, set[str]] = {path: set() for path in unique_paths}
        for path in unique_paths:
            for source, text in fields.items():
                if path_text_matches(path, text):
                    matches_by_path[path].add(source)
        fd_paths, fd_error = fd_targets(pid, max_fd_per_process)
        if fd_error:
            fd_scan_errors += 1
        for target in fd_paths:
            for path in unique_paths:
                if path_text_matches(path, target):
                    matches_by_path[path].add("fd")
        for path, sources in matches_by_path.items():
            if not sources:
                continue
            process_summary = {
                "pid": pid,
                "ppid": proc.get("ppid"),
                "uid": proc.get("uid"),
                "name": proc.get("name"),
                "comm": proc.get("comm"),
                "workload_hint": proc.get("workload_hint"),
                "vmrss_kib": proc.get("vmrss_kib"),
                "cpu_system_percent": proc.get("cpu_system_percent"),
                "match_sources": sorted(sources),
                "cmdline": proc.get("cmdline"),
            }
            path_results[path]["active"] = True
            path_results[path]["status"] = "blocked_active_process"
            if len(path_results[path]["active_processes"]) < 20:
                path_results[path]["active_processes"].append(process_summary)
            for source in sorted(sources):
                marker = {"pid": pid, "source": source}
                if marker not in path_results[path]["match_sources"]:
                    path_results[path]["match_sources"].append(marker)
    return {
        "schema": f"{schema_prefix}_storage_process_path_usage_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(snapshot.get("ok")),
        "capture": {
            "source": "/proc snapshot plus cwd/exe/cmdline/cgroup/fd path matching",
            "facts_only": True,
            "interval_sec": interval,
            "top_limit": top,
            "paths": len(unique_paths),
            "fd_limit_per_process": max_fd_per_process,
            "fd_scan_errors": fd_scan_errors,
            "snapshot_latest": str(process_latest_path),
        },
        "snapshot": {
            "generated_at": snapshot.get("generated_at"),
            "summary": snapshot.get("summary"),
        },
        "paths": list(path_results.values()),
        "summary": {
            "paths": len(unique_paths),
            "active_paths": sum(1 for item in path_results.values() if item.get("active")),
            "active_process_refs": sum(len(item.get("active_processes", [])) for item in path_results.values()),
        },
        "non_claims": [
            "A clear guard means no active accessible process reference was observed in this short sample, not proof that deletion is globally safe.",
            "Inaccessible root-owned process file descriptors may be omitted when the command is run without elevated privileges.",
        ],
    }


def execute_cleanup_action(
    action: Mapping[str, Any],
    *,
    age_days: float,
    abyss_machine_tmp_root: Path,
    command_runner: CommandRunnerPort,
    euid: EuidPort = current_euid,
    clock: ClockPort = time.time,
) -> dict[str, Any]:
    action_type = str(action.get("action_type") or "")
    action_id = str(action.get("id") or "")
    path = Path(str(action.get("path") or ""))
    if action_type == "package_manager_clean" and action_id == "var_cache_libdnf5":
        if euid() != 0:
            return {"ok": False, "blocked": True, "reason": "requires_root_pkexec"}
        command = ["dnf5", "clean", "all"]
        out = dict(command_runner(command, 120.0))
        return {"ok": bool(out.get("ok")), "command": command, "result": out}
    if action_type == "rebuildable_cache_pressure_valve" and action_id == "home_npm_cache":
        verify = dict(command_runner(["npm", "cache", "verify"], 120.0))
        clean = (
            dict(command_runner(["npm", "cache", "clean", "--force"], 120.0))
            if verify.get("ok")
            else {"ok": False, "skipped": True, "reason": "npm cache verify failed"}
        )
        return {"ok": bool(verify.get("ok")) and bool(clean.get("ok")), "commands": [verify, clean]}
    if action_type == "age_based_generated_temp_cleanup" and storage_contracts.is_relative_to_path(path, abyss_machine_tmp_root):
        return _execute_age_based_temp_cleanup(path, age_days=age_days, clock=clock)
    return {"ok": False, "blocked": True, "reason": "manual_review_only_or_not_allowlisted"}


def _execute_age_based_temp_cleanup(path: Path, *, age_days: float, clock: ClockPort) -> dict[str, Any]:
    cutoff = clock() - (max(1.0, float(age_days)) * 86400.0)
    removed_files: list[str] = []
    removed_dirs: list[str] = []
    errors: list[dict[str, str]] = []
    try:
        for current, dirnames, filenames in os.walk(path, topdown=False):
            current_path = Path(current)
            if current_path.is_symlink():
                continue
            for filename in filenames:
                candidate = current_path / filename
                try:
                    stat = candidate.lstat()
                    if candidate.is_symlink() or stat.st_mtime > cutoff:
                        continue
                    candidate.unlink()
                    removed_files.append(str(candidate))
                except OSError as exc:
                    errors.append({"path": str(candidate), "error": str(exc)})
            for dirname in dirnames:
                candidate_dir = current_path / dirname
                try:
                    if candidate_dir.is_symlink() or candidate_dir.stat().st_mtime > cutoff:
                        continue
                    candidate_dir.rmdir()
                    removed_dirs.append(str(candidate_dir))
                except OSError:
                    pass
    except OSError as exc:
        errors.append({"path": str(path), "error": str(exc)})
    return {
        "ok": not errors,
        "removed_files": removed_files[:200],
        "removed_dirs": removed_dirs[:200],
        "removed_file_count": len(removed_files),
        "removed_dir_count": len(removed_dirs),
        "errors": errors[:50],
    }
