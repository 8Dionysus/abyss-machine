from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

from . import storage_contracts


ProcessSnapshotPort = Callable[[int, float], Mapping[str, Any]]
FdTargetsPort = Callable[[int, int], tuple[Sequence[str], bool]]
CommandRunnerPort = Callable[[Sequence[str], float], Mapping[str, Any]]
EuidPort = Callable[[], int]
ClockPort = Callable[[], float]


def current_euid() -> int:
    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid):
        return int(geteuid())
    return 0


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
