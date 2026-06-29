from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import threading
import time
from typing import Any, Callable, Sequence

from . import process_contracts


SysconfPort = Callable[[str | int], int]
SleepPort = Callable[[float], None]
MonotonicPort = Callable[[], float]
CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[..., dict[str, Any]]
JsonLoaderPort = Callable[[Path], tuple[Any, str | None]]
NowIsoPort = Callable[[], str]
PidPort = Callable[[], int]
ThermalMapPort = Callable[[], dict[str, Any]]
ProcessInfoPort = Callable[[int], dict[str, Any] | None]
DocumentPort = Callable[[], dict[str, Any]]
PolicyPort = Callable[[dict[str, Any]], dict[str, Any]]
RoutePort = Callable[[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]

CONTAINER_LABEL_ALLOWLIST = {
    "PODMAN_SYSTEMD_UNIT",
    "com.docker.compose.container-number",
    "com.docker.compose.project",
    "com.docker.compose.project.config_files",
    "com.docker.compose.project.working_dir",
    "com.docker.compose.service",
    "io.podman.compose.project",
    "io.podman.compose.service",
    "io.podman.compose.version",
    "org.opencontainers.image.description",
    "org.opencontainers.image.source",
    "org.opencontainers.image.title",
    "org.opencontainers.image.url",
    "org.opencontainers.image.version",
}


def default_command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_int(path: Path) -> int | None:
    raw = _read_text(path).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_kib_field(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.split()
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clock_ticks(*, sysconf: SysconfPort = os.sysconf) -> int | None:
    try:
        ticks = int(sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK")))
    except (OSError, TypeError, ValueError):
        return None
    return ticks if ticks > 0 else None


def parse_proc_stat_text(raw: str, *, sysconf: SysconfPort = os.sysconf) -> dict[str, Any]:
    if not raw:
        return {}
    end = raw.rfind(")")
    start = raw.find("(")
    if start < 0 or end < 0 or end <= start:
        return {}
    comm = raw[start + 1:end]
    fields = raw[end + 2:].split()
    data: dict[str, Any] = {"comm": comm}
    if len(fields) > 0:
        data["state"] = fields[0]
    int_fields = {
        "ppid": 1,
        "utime_jiffies": 11,
        "stime_jiffies": 12,
        "priority": 15,
        "nice": 16,
        "threads": 17,
        "starttime_jiffies": 19,
    }
    for key, index in int_fields.items():
        if len(fields) > index:
            try:
                data[key] = int(fields[index])
            except ValueError:
                pass
    data["cpu_jiffies"] = int(data.get("utime_jiffies") or 0) + int(data.get("stime_jiffies") or 0)
    hz = clock_ticks(sysconf=sysconf)
    data["cpu_time_sec"] = round(float(data["cpu_jiffies"]) / float(hz), 3) if hz else None
    return data


def proc_total_jiffies(proc_root: Path = Path("/proc")) -> int | None:
    raw = _read_text(proc_root / "stat")
    if not raw:
        return None
    first = raw.splitlines()[0].split()
    if not first or first[0] != "cpu":
        return None
    total = 0
    for item in first[1:]:
        try:
            total += int(item)
        except ValueError:
            return None
    return total


def proc_stat_data(pid: int, proc_root: Path = Path("/proc"), *, sysconf: SysconfPort = os.sysconf) -> dict[str, Any]:
    return parse_proc_stat_text(_read_text(proc_root / str(pid) / "stat"), sysconf=sysconf)


def proc_task_stat_data(
    pid: int,
    tid: int,
    proc_root: Path = Path("/proc"),
    *,
    sysconf: SysconfPort = os.sysconf,
) -> dict[str, Any]:
    raw = _read_text(proc_root / str(pid) / "task" / str(tid) / "stat")
    data = parse_proc_stat_text(raw, sysconf=sysconf)
    fields = raw[raw.rfind(")") + 2:].split() if raw and ")" in raw else []
    if len(fields) > 36:
        try:
            data["processor"] = int(fields[36])
        except ValueError:
            pass
    return data


def proc_status_data(pid: int, proc_root: Path = Path("/proc")) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in _read_text(proc_root / str(pid) / "status").splitlines():
        key, sep, value = line.partition(":")
        if sep:
            result[key] = value.strip()
    return result


def proc_cmdline(pid: int, proc_root: Path = Path("/proc"), max_len: int = 700) -> str:
    try:
        raw = (proc_root / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""
    text = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    return text[:max_len]


def proc_io_data(pid: int, proc_root: Path = Path("/proc")) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in _read_text(proc_root / str(pid) / "io").splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        try:
            result[key.strip()] = int(value.strip())
        except ValueError:
            pass
    return result


def safe_readlink(path: Path) -> str | None:
    try:
        return str(path.readlink())
    except OSError:
        return None


def storage_matches_for_process(info: dict[str, Any], storage_roots: Sequence[Path | str]) -> list[str]:
    haystack = " ".join(str(info.get(key) or "") for key in ("cmdline", "cwd", "exe"))
    matches = []
    for root in storage_roots:
        root_text = str(root)
        if root_text and root_text in haystack:
            matches.append(root_text)
    return matches


def process_info(
    pid: int,
    *,
    proc_root: Path = Path("/proc"),
    storage_roots: Sequence[Path | str] = (),
    game_roots: Sequence[Path | str] = (),
    sysconf: SysconfPort = os.sysconf,
) -> dict[str, Any] | None:
    stat = proc_stat_data(pid, proc_root, sysconf=sysconf)
    status = proc_status_data(pid, proc_root)
    if not stat and not status:
        return None
    comm = str(stat.get("comm") or status.get("Name") or "")
    cmdline = proc_cmdline(pid, proc_root) or f"[{comm}]"
    uid = None
    uid_field = status.get("Uid")
    if uid_field:
        try:
            uid = int(uid_field.split()[0])
        except (ValueError, IndexError):
            uid = None
    proc_pid_root = proc_root / str(pid)
    cwd = safe_readlink(proc_pid_root / "cwd")
    exe = safe_readlink(proc_pid_root / "exe")
    info: dict[str, Any] = {
        "pid": pid,
        "ppid": stat.get("ppid") or parse_kib_field(status.get("PPid")),
        "uid": uid,
        "name": status.get("Name") or comm,
        "comm": comm,
        "state": status.get("State") or stat.get("state"),
        "cmdline": cmdline,
        "threads": stat.get("threads") or parse_kib_field(status.get("Threads")),
        "vmrss_kib": parse_kib_field(status.get("VmRSS")) or 0,
        "vmsize_kib": parse_kib_field(status.get("VmSize")) or 0,
        "cpu_jiffies": stat.get("cpu_jiffies"),
        "cpu_time_sec": stat.get("cpu_time_sec"),
        "starttime_jiffies": stat.get("starttime_jiffies"),
        "priority": stat.get("priority"),
        "nice": stat.get("nice"),
        "cwd": cwd,
        "exe": exe,
        "oom_score": _read_int(proc_pid_root / "oom_score"),
        "oom_score_adj": _read_int(proc_pid_root / "oom_score_adj"),
        "io": proc_io_data(pid, proc_root),
    }
    try:
        info["fd_count"] = len(list((proc_pid_root / "fd").iterdir()))
    except OSError:
        info["fd_count"] = None
    cgroup = _read_text(proc_pid_root / "cgroup")
    if cgroup:
        info["cgroup"] = cgroup.splitlines()[:6]
    info["storage_matches"] = storage_matches_for_process(info, storage_roots)
    info["game_role"] = process_contracts.game_role(cmdline, comm, cwd, exe, game_roots=list(game_roots))
    info["capability_role"] = process_contracts.capability_role(cmdline, comm, cwd, exe)
    info["workload_hint"] = process_contracts.workload_hint(cmdline, comm, cwd, exe, game_roots=list(game_roots))
    return info


def process_ids(proc_root: Path = Path("/proc")) -> list[int]:
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return []
    return sorted(int(entry.name) for entry in entries if entry.name.isdigit())


def collect_process_infos(
    *,
    proc_root: Path = Path("/proc"),
    storage_roots: Sequence[Path | str] = (),
    game_roots: Sequence[Path | str] = (),
    interval: float = 0.0,
    sleep: SleepPort = time.sleep,
    sysconf: SysconfPort = os.sysconf,
) -> dict[str, Any]:
    interval = max(0.0, float(interval))
    before_jiffies: dict[int, int] = {}
    total_before = proc_total_jiffies(proc_root)
    if interval > 0:
        for pid in process_ids(proc_root):
            stat = proc_stat_data(pid, proc_root, sysconf=sysconf)
            if stat.get("cpu_jiffies") is not None:
                before_jiffies[pid] = int(stat["cpu_jiffies"])
        sleep(interval)
    total_after = proc_total_jiffies(proc_root)
    processes: list[dict[str, Any]] = []
    inaccessible = 0
    for pid in process_ids(proc_root):
        info = process_info(pid, proc_root=proc_root, storage_roots=storage_roots, game_roots=game_roots, sysconf=sysconf)
        if info is None:
            inaccessible += 1
            continue
        if interval > 0 and info.get("cpu_jiffies") is not None:
            before = before_jiffies.get(int(info["pid"]))
            if before is not None and total_before is not None and total_after is not None and total_after > total_before:
                delta = max(0, int(info["cpu_jiffies"]) - before)
                info["cpu_system_percent"] = round((float(delta) / float(total_after - total_before)) * 100.0, 4)
        processes.append(info)
    return {
        "processes": processes,
        "inaccessible": inaccessible,
        "source": "live_proc_scan",
        "cpu_sample": {
            "interval_sec": interval,
            "total_before": total_before,
            "total_after": total_after,
            "sampled_pids": len(before_jiffies),
        },
    }


def process_thread_cpu_sample(
    *,
    proc_root: Path = Path("/proc"),
    now: NowIsoPort,
    monotonic: MonotonicPort = time.monotonic,
    sysconf: SysconfPort = os.sysconf,
) -> dict[str, Any]:
    threads: dict[str, dict[str, Any]] = {}
    inaccessible = 0
    processes_seen = 0
    try:
        pid_entries = list(proc_root.iterdir())
    except OSError:
        pid_entries = []
        inaccessible += 1
    for pid_entry in pid_entries:
        if not pid_entry.name.isdigit():
            continue
        pid = int(pid_entry.name)
        task_root = pid_entry / "task"
        try:
            task_entries = list(task_root.iterdir())
        except OSError:
            inaccessible += 1
            continue
        processes_seen += 1
        for task_entry in task_entries:
            if not task_entry.name.isdigit():
                continue
            tid = int(task_entry.name)
            stat = proc_task_stat_data(pid, tid, proc_root, sysconf=sysconf)
            if not stat:
                inaccessible += 1
                continue
            key = f"{pid}:{tid}"
            threads[key] = {
                "pid": pid,
                "tid": tid,
                "comm": stat.get("comm"),
                "state": stat.get("state"),
                "cpu_jiffies": stat.get("cpu_jiffies"),
                "processor": stat.get("processor"),
                "starttime_jiffies": stat.get("starttime_jiffies"),
                "priority": stat.get("priority"),
                "nice": stat.get("nice"),
            }
    return {
        "at": now(),
        "monotonic": monotonic(),
        "threads": threads,
        "summary": {
            "processes_seen": processes_seen,
            "threads_seen": len(threads),
            "inaccessible_or_exited": inaccessible,
        },
    }


def process_thermal_focus(thermal_map: dict[str, Any]) -> dict[str, Any]:
    summary = thermal_map.get("summary", {}) if isinstance(thermal_map.get("summary"), dict) else {}
    focus: set[int] = set()
    for key in ("hard_avoid_cpus", "critical_cpus", "route_avoid_cpus", "hot_cpus"):
        for cpu in summary.get(key, []) if isinstance(summary.get(key), list) else []:
            try:
                focus.add(int(cpu))
            except (TypeError, ValueError):
                pass
    per_cpu_map: dict[int, dict[str, Any]] = {}
    for item in thermal_map.get("per_cpu", []) if isinstance(thermal_map.get("per_cpu"), list) else []:
        if not isinstance(item, dict):
            continue
        try:
            cpu = int(item.get("cpu"))
        except (TypeError, ValueError):
            continue
        per_cpu_map[cpu] = {
            "cpu": cpu,
            "core_id": item.get("core_id"),
            "role": item.get("role"),
            "temperature_c": item.get("temperature_c"),
            "thermal_class": item.get("thermal_class"),
            "route_avoid": item.get("route_avoid"),
            "hard_avoid": item.get("hard_avoid"),
        }
    focus_details = [per_cpu_map[cpu] for cpu in sorted(focus) if cpu in per_cpu_map]
    return {
        "class": thermal_map.get("class"),
        "summary": summary,
        "focus_cpus": sorted(focus),
        "focus_cpu_details": focus_details,
        "per_cpu": per_cpu_map,
    }


def process_thermal_attribution_confidence(
    focus_cpu_sec: float,
    total_cpu_sec: float,
    focus_share: float,
    focus_cpus: list[int],
) -> str:
    if not focus_cpus or focus_cpu_sec <= 0:
        return "none"
    if focus_cpu_sec >= 0.35 and focus_share >= 0.70:
        return "high"
    if focus_cpu_sec >= 0.10 and focus_share >= 0.50:
        return "medium"
    if focus_cpu_sec >= 0.03:
        return "low"
    if total_cpu_sec >= 0.10:
        return "low"
    return "none"


def confidence_rank(confidence: str | None) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(str(confidence or "none"), 0)


def process_cpu_distribution(enriched_threads: list[dict[str, Any]], elapsed: float, top: int = 16) -> dict[str, Any]:
    by_cpu: dict[int, dict[str, Any]] = {}
    for thread in enriched_threads:
        if thread.get("observer_thread"):
            continue
        for processor in thread.get("processors", []) if isinstance(thread.get("processors"), list) else []:
            if not isinstance(processor, dict):
                continue
            try:
                cpu = int(processor.get("cpu"))
                cpu_sec = float(processor.get("cpu_sec") or 0.0)
            except (TypeError, ValueError):
                continue
            bucket = by_cpu.setdefault(
                cpu,
                {
                    "cpu": cpu,
                    "cpu_sec": 0.0,
                    "threads": 0,
                    "processes": set(),
                    "thermal": processor.get("thermal") if isinstance(processor.get("thermal"), dict) else {},
                },
            )
            bucket["cpu_sec"] = round(float(bucket["cpu_sec"]) + cpu_sec, 4)
            bucket["threads"] = int(bucket["threads"]) + 1
            try:
                bucket["processes"].add(int(thread.get("pid")))
            except (TypeError, ValueError):
                pass
    rows: list[dict[str, Any]] = []
    for bucket in by_cpu.values():
        cpu_sec = float(bucket.get("cpu_sec") or 0.0)
        rows.append({
            "cpu": bucket.get("cpu"),
            "cpu_sec": round(cpu_sec, 4),
            "cpu_percent_one_core": round((cpu_sec / max(0.001, elapsed)) * 100.0, 2),
            "threads": bucket.get("threads"),
            "processes": len(bucket.get("processes") or []),
            "thermal": bucket.get("thermal") or {},
        })
    rows = sorted(rows, key=lambda item: float(item.get("cpu_sec") or 0.0), reverse=True)
    return {
        "cpus_observed": len(rows),
        "cpu_sec_total": round(sum(float(item.get("cpu_sec") or 0.0) for item in rows), 4),
        "top": rows[: max(1, min(int(top), 64))],
    }


def process_thermal_incident(
    thermal_map: dict[str, Any],
    focus_cpus: list[int],
    candidate_processes: list[dict[str, Any]],
    cpu_distribution: dict[str, Any],
) -> dict[str, Any]:
    def ints(values: Any) -> list[int]:
        result: list[int] = []
        for value in values if isinstance(values, list) else []:
            try:
                result.append(int(value))
            except (TypeError, ValueError):
                pass
        return sorted(set(result))

    summary = thermal_map.get("summary", {}) if isinstance(thermal_map.get("summary"), dict) else {}
    thresholds = thermal_map.get("thresholds", {}) if isinstance(thermal_map.get("thresholds"), dict) else {}
    thermal_class = str(thermal_map.get("class") or "unknown")
    route_avoid_cpus = ints(summary.get("route_avoid_cpus", []))
    hard_avoid_cpus = ints(summary.get("hard_avoid_cpus", []))
    hot_cpus = ints(summary.get("hot_cpus", []))
    critical_cpus = ints(summary.get("critical_cpus", []))
    package_temp = summary.get("package_temperature_c_max")
    core_temp = summary.get("core_temperature_c_max")
    package_critical_threshold = float(thresholds.get("package_critical_temperature_c", thresholds.get("critical_temperature_c", 100.0)))
    hot_threshold = float(thresholds.get("hot_temperature_c", 90.0))
    package_critical = isinstance(package_temp, (int, float)) and package_temp >= package_critical_threshold
    package_hot = isinstance(package_temp, (int, float)) and package_temp >= hot_threshold
    broad_heat = package_hot or len(hot_cpus) >= 4 or len(route_avoid_cpus) >= 6
    top_candidate = candidate_processes[0] if candidate_processes else None
    top_confidence = _nested_get(top_candidate or {}, ["attribution", "confidence"]) or "none"
    cpu_top = cpu_distribution.get("top", []) if isinstance(cpu_distribution.get("top"), list) else []
    hottest_cpu_load = cpu_top[0] if cpu_top else None

    if package_critical:
        kind = "package_critical"
        severity = "critical"
        launch_recommendation = "defer_new_heavy_work"
    elif thermal_class == "critical" and focus_cpus:
        kind = "critical_hotspot"
        severity = "critical"
        launch_recommendation = "operator_only_route_new_work_away_from_critical_cpus"
    elif thermal_class == "critical":
        kind = "critical_global"
        severity = "critical"
        launch_recommendation = "defer_new_heavy_work_until_clearer_telemetry"
    elif broad_heat:
        kind = "broad_heat"
        severity = "hot"
        launch_recommendation = "defer_unattended_heavy_and_route_operator_work"
    elif focus_cpus:
        kind = "localized_hotspot"
        severity = "hot" if thermal_class == "hot" else "warm"
        launch_recommendation = "route_new_work_away_from_focus_cpus"
    elif thermal_class == "warm":
        kind = "warm_no_focus"
        severity = "warm"
        launch_recommendation = "prefer_bounded_routes"
    else:
        kind = "no_hotspot"
        severity = "green"
        launch_recommendation = "normal_route_policy"

    return {
        "kind": kind,
        "severity": severity,
        "thermal_class": thermal_class,
        "package_temperature_c_max": package_temp,
        "core_temperature_c_max": core_temp,
        "focus_cpus": focus_cpus,
        "route_avoid_cpus": route_avoid_cpus,
        "hard_avoid_cpus": hard_avoid_cpus,
        "hot_cpus": hot_cpus,
        "critical_cpus": critical_cpus,
        "package_hot": package_hot,
        "package_critical": package_critical,
        "broad_heat": broad_heat,
        "top_candidate": top_candidate,
        "top_candidate_confidence": top_confidence,
        "hottest_observed_cpu_load": hottest_cpu_load,
        "launch_recommendation": launch_recommendation,
        "operator_action": {
            "safe_default": "observe_and_route_new_work",
            "do_not_change_existing_user_process_affinity": True,
            "do_not_kill_or_throttle_from_this_result": True,
            "use_launch_wrapper_for_new_heavy_cpu_work": True,
        },
        "confidence_rule": "Attribution ranks candidates from repeated /proc thread CPU deltas; it is routing evidence, not exclusive causality proof.",
    }


def process_thermal_attribution_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    seconds: float,
    interval: float,
    top: int,
    thermal_map_port: ThermalMapPort,
    proc_root: Path = Path("/proc"),
    process_info_port: ProcessInfoPort | None = None,
    storage_roots: Sequence[Path | str] = (),
    game_roots: Sequence[Path | str] = (),
    now: NowIsoPort,
    monotonic: MonotonicPort = time.monotonic,
    sleep: SleepPort = time.sleep,
    sysconf: SysconfPort = os.sysconf,
    observer_pid: int | None = None,
) -> dict[str, Any]:
    seconds = max(0.5, min(float(seconds), 20.0))
    interval = max(0.2, min(float(interval), 5.0))
    top = max(5, min(int(top), 200))
    thermal_before = thermal_map_port()
    samples: list[dict[str, Any]] = []
    deadline = monotonic() + seconds
    while True:
        sample = process_thread_cpu_sample(proc_root=proc_root, now=now, monotonic=monotonic, sysconf=sysconf)
        samples.append(sample)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(interval, remaining))
    thermal_after = thermal_map_port()

    before_focus = process_thermal_focus(thermal_before)
    after_focus = process_thermal_focus(thermal_after)
    focus_cpus = sorted(set(before_focus.get("focus_cpus", [])) | set(after_focus.get("focus_cpus", [])))
    per_cpu: dict[int, dict[str, Any]] = {}
    per_cpu.update(before_focus.get("per_cpu", {}))
    per_cpu.update(after_focus.get("per_cpu", {}))
    elapsed = max(0.001, float(samples[-1]["monotonic"]) - float(samples[0]["monotonic"])) if len(samples) >= 2 else 0.001
    hz = clock_ticks(sysconf=sysconf) or 100
    observer = os.getpid() if observer_pid is None else int(observer_pid)

    thread_metrics: dict[str, dict[str, Any]] = {}
    skipped_segments = 0
    segment_count = 0
    for previous, current in zip(samples, samples[1:]):
        segment_count += 1
        prev_threads = previous.get("threads", {})
        cur_threads = current.get("threads", {})
        if not isinstance(prev_threads, dict) or not isinstance(cur_threads, dict):
            continue
        for key, cur in cur_threads.items():
            prev = prev_threads.get(key)
            if not isinstance(cur, dict) or not isinstance(prev, dict):
                continue
            if cur.get("starttime_jiffies") != prev.get("starttime_jiffies"):
                skipped_segments += 1
                continue
            cur_jiffies = cur.get("cpu_jiffies")
            prev_jiffies = prev.get("cpu_jiffies")
            if not isinstance(cur_jiffies, int) or not isinstance(prev_jiffies, int):
                skipped_segments += 1
                continue
            delta = max(0, cur_jiffies - prev_jiffies)
            if delta <= 0:
                continue
            processor = cur.get("processor")
            processor_int = int(processor) if isinstance(processor, int) else None
            metric = thread_metrics.setdefault(
                key,
                {
                    "pid": cur.get("pid"),
                    "tid": cur.get("tid"),
                    "comm": cur.get("comm"),
                    "state": cur.get("state"),
                    "starttime_jiffies": cur.get("starttime_jiffies"),
                    "cpu_jiffies_delta": 0,
                    "focus_cpu_jiffies_delta": 0,
                    "segments_with_cpu_delta": 0,
                    "processors_by_jiffies": {},
                    "focus_processors_by_jiffies": {},
                    "last_processor": processor_int,
                    "observer_thread": int(cur.get("pid") or -1) == observer,
                },
            )
            metric["cpu_jiffies_delta"] = int(metric["cpu_jiffies_delta"]) + delta
            metric["segments_with_cpu_delta"] = int(metric["segments_with_cpu_delta"]) + 1
            metric["last_processor"] = processor_int
            if processor_int is not None:
                bucket = metric["processors_by_jiffies"]
                bucket[str(processor_int)] = int(bucket.get(str(processor_int), 0)) + delta
                if processor_int in focus_cpus:
                    metric["focus_cpu_jiffies_delta"] = int(metric["focus_cpu_jiffies_delta"]) + delta
                    focus_bucket = metric["focus_processors_by_jiffies"]
                    focus_bucket[str(processor_int)] = int(focus_bucket.get(str(processor_int), 0)) + delta

    enriched_threads: list[dict[str, Any]] = []
    for metric in thread_metrics.values():
        total_jiffies = int(metric.get("cpu_jiffies_delta") or 0)
        focus_jiffies = int(metric.get("focus_cpu_jiffies_delta") or 0)
        total_sec = round(float(total_jiffies) / float(hz), 4)
        focus_sec = round(float(focus_jiffies) / float(hz), 4)
        focus_share = round(float(focus_jiffies) / float(total_jiffies), 4) if total_jiffies > 0 else 0.0
        processors = [
            {
                "cpu": int(cpu),
                "cpu_sec": round(float(jiffies) / float(hz), 4),
                "share": round(float(jiffies) / float(total_jiffies), 4) if total_jiffies > 0 else 0.0,
                "thermal": per_cpu.get(int(cpu), {}),
            }
            for cpu, jiffies in sorted(
                metric.get("processors_by_jiffies", {}).items(),
                key=lambda item: int(item[1]),
                reverse=True,
            )
        ]
        enriched_threads.append({
            "pid": metric.get("pid"),
            "tid": metric.get("tid"),
            "comm": metric.get("comm"),
            "state": metric.get("state"),
            "cpu_sec": total_sec,
            "focus_cpu_sec": focus_sec,
            "cpu_percent_one_core": round((total_sec / elapsed) * 100.0, 2),
            "focus_cpu_percent_one_core": round((focus_sec / elapsed) * 100.0, 2),
            "focus_cpu_share": focus_share,
            "processors": processors[:8],
            "last_processor": metric.get("last_processor"),
            "segments_with_cpu_delta": metric.get("segments_with_cpu_delta"),
            "observer_thread": metric.get("observer_thread"),
        })

    process_aggregates: dict[int, dict[str, Any]] = {}
    for thread in enriched_threads:
        try:
            pid = int(thread.get("pid"))
        except (TypeError, ValueError):
            continue
        proc = process_aggregates.setdefault(
            pid,
            {
                "pid": pid,
                "cpu_sec": 0.0,
                "focus_cpu_sec": 0.0,
                "threads_with_cpu_delta": 0,
                "focus_threads": 0,
                "top_threads": [],
                "processor_jiffies": {},
                "observer_process": pid == observer,
            },
        )
        proc["cpu_sec"] = round(float(proc["cpu_sec"]) + float(thread.get("cpu_sec") or 0.0), 4)
        proc["focus_cpu_sec"] = round(float(proc["focus_cpu_sec"]) + float(thread.get("focus_cpu_sec") or 0.0), 4)
        proc["threads_with_cpu_delta"] = int(proc["threads_with_cpu_delta"]) + 1
        if float(thread.get("focus_cpu_sec") or 0.0) > 0:
            proc["focus_threads"] = int(proc["focus_threads"]) + 1
        proc["top_threads"].append(thread)

    processes: list[dict[str, Any]] = []
    for pid, aggregate in process_aggregates.items():
        if process_info_port is not None:
            info = process_info_port(pid)
        else:
            info = process_info(pid, proc_root=proc_root, storage_roots=storage_roots, game_roots=game_roots, sysconf=sysconf)
        info = info or {"pid": pid, "cmdline": "[exited]", "comm": None, "name": None}
        top_threads = sorted(
            aggregate.get("top_threads", []),
            key=lambda item: (float(item.get("focus_cpu_sec") or 0.0), float(item.get("cpu_sec") or 0.0)),
            reverse=True,
        )[:8]
        total_sec = float(aggregate.get("cpu_sec") or 0.0)
        focus_sec = float(aggregate.get("focus_cpu_sec") or 0.0)
        focus_share = round(focus_sec / total_sec, 4) if total_sec > 0 else 0.0
        confidence = process_thermal_attribution_confidence(focus_sec, total_sec, focus_share, focus_cpus)
        processes.append({
            "pid": pid,
            "ppid": info.get("ppid"),
            "uid": info.get("uid"),
            "name": info.get("name"),
            "comm": info.get("comm"),
            "cmdline": info.get("cmdline"),
            "workload_hint": info.get("workload_hint"),
            "storage_matches": info.get("storage_matches"),
            "vmrss_kib": info.get("vmrss_kib"),
            "threads": info.get("threads"),
            "cpu_sec": round(total_sec, 4),
            "focus_cpu_sec": round(focus_sec, 4),
            "cpu_percent_one_core": round((total_sec / elapsed) * 100.0, 2),
            "focus_cpu_percent_one_core": round((focus_sec / elapsed) * 100.0, 2),
            "focus_cpu_share": focus_share,
            "threads_with_cpu_delta": aggregate.get("threads_with_cpu_delta"),
            "focus_threads": aggregate.get("focus_threads"),
            "top_threads": top_threads,
            "observer_process": aggregate.get("observer_process"),
            "attribution": {
                "confidence": confidence,
                "claim": "candidate_not_proof" if confidence != "none" else "background_cpu_observed",
                "basis": "Thread CPU deltas over the sample window, assigned to the thread's last reported processor for each segment.",
            },
        })

    candidate_processes = [
        item for item in processes
        if float(item.get("focus_cpu_sec") or 0.0) > 0 and not item.get("observer_process")
    ]
    top_focus = sorted(
        candidate_processes,
        key=lambda item: (float(item.get("focus_cpu_sec") or 0.0), float(item.get("cpu_sec") or 0.0)),
        reverse=True,
    )[:top]
    top_cpu = sorted(
        [item for item in processes if not item.get("observer_process")],
        key=lambda item: float(item.get("cpu_sec") or 0.0),
        reverse=True,
    )[:top]
    cpu_distribution = process_cpu_distribution(enriched_threads, elapsed, top=16)
    incident = process_thermal_incident(thermal_after, focus_cpus, top_focus, cpu_distribution)
    sample_summaries = [sample.get("summary", {}) for sample in samples]
    return {
        "schema": f"{schema_prefix}_process_thermal_attribution_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "paths": paths,
        "capture": {
            "source": "/proc task stat + abyss-machine ai cpu thermal-map",
            "seconds_requested": seconds,
            "interval_seconds": interval,
            "elapsed_seconds": round(elapsed, 3),
            "samples": len(samples),
            "segments": segment_count,
            "top_limit": top,
            "facts_only": True,
            "observer_pid": observer,
        },
        "thermal": {
            "before": {
                "class": thermal_before.get("class"),
                "summary": thermal_before.get("summary"),
                "focus_cpus": before_focus.get("focus_cpus"),
                "focus_cpu_details": before_focus.get("focus_cpu_details"),
            },
            "after": {
                "class": thermal_after.get("class"),
                "summary": thermal_after.get("summary"),
                "focus_cpus": after_focus.get("focus_cpus"),
                "focus_cpu_details": after_focus.get("focus_cpu_details"),
            },
            "focus_cpus": focus_cpus,
            "focus_cpu_details": [per_cpu[cpu] for cpu in focus_cpus if cpu in per_cpu],
        },
        "summary": {
            "processes_with_cpu_delta": len(processes),
            "threads_with_cpu_delta": len(enriched_threads),
            "focus_cpus": focus_cpus,
            "focus_process_candidates": len(candidate_processes),
            "focus_cpu_sec_total": round(sum(float(item.get("focus_cpu_sec") or 0.0) for item in processes), 4),
            "cpu_sec_total": round(sum(float(item.get("cpu_sec") or 0.0) for item in processes), 4),
            "incident_kind": incident.get("kind"),
            "incident_severity": incident.get("severity"),
            "top_candidate_confidence": incident.get("top_candidate_confidence"),
            "samples": sample_summaries,
            "skipped_segments": skipped_segments,
            "hottest_candidate": top_focus[0] if top_focus else None,
        },
        "incident": incident,
        "cpu_distribution": cpu_distribution,
        "top": {
            "focus_cpu_candidates": top_focus,
            "cpu": top_cpu,
            "threads": sorted(
                [item for item in enriched_threads if not item.get("observer_thread")],
                key=lambda item: (float(item.get("focus_cpu_sec") or 0.0), float(item.get("cpu_sec") or 0.0)),
                reverse=True,
            )[:top],
        },
        "processes": sorted(processes, key=lambda item: int(item.get("pid") or 0)),
        "policy": {
            "automation": "none",
            "action": "observe_only",
            "do_not_kill_or_throttle_from_this_result": True,
            "confidence_ceiling": "high",
            "reason": "Linux threads can migrate between CPUs; per-segment processor attribution is useful evidence but not exclusive causality.",
        },
        "non_claims": [
            "This is not proof that a process caused a thermal spike by itself.",
            "Thread processor is sampled from /proc stat and can change between samples.",
            "The abyss-machine observer process may appear in raw CPU data and is excluded from candidate rankings.",
            "Use repeated samples plus workload context before changing affinities, killing processes, or throttling work.",
        ],
    }


def process_thermal_plan_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    seconds: float,
    interval: float,
    top: int,
    attribution_port: DocumentPort,
    thermal_map_port: ThermalMapPort,
    game_guard_port: DocumentPort,
    mode_port: DocumentPort,
    policy_port: PolicyPort,
    route_port: RoutePort,
    battery_port: DocumentPort,
    desktop_compositor_port: DocumentPort,
    thermal_attribution_latest_path: str,
    game_guard_latest_path: str,
    desktop_compositor_latest_path: str,
) -> dict[str, Any]:
    seconds = max(0.5, min(float(seconds), 20.0))
    interval = max(0.2, min(float(interval), 5.0))
    top = max(5, min(int(top), 200))
    attribution = attribution_port()
    thermal_map = thermal_map_port()
    game_guard = game_guard_port()
    mode = mode_port()
    policy = policy_port(thermal_map)
    route_mode = {
        "effective_mode": mode.get("effective_mode"),
        "selected_mode": mode.get("selected_mode"),
    }
    route_battery = _nested_get(policy, ["current", "battery"]) or battery_port()
    desktop_compositor = desktop_compositor_port()
    routes: dict[str, Any] = {}
    for workload in ("background", "probe", "light", "interactive", "medium", "heavy", "sustained"):
        routes[workload] = route_port(workload, thermal_map, policy, route_mode, route_battery)

    focus_cpus = sorted({int(cpu) for cpu in _nested_get(thermal_map, ["summary", "route_avoid_cpus"]) or []})
    for key in ("hard_avoid_cpus", "hot_cpus", "critical_cpus"):
        for cpu in _nested_get(thermal_map, ["summary", key]) or []:
            try:
                focus_cpus.append(int(cpu))
            except (TypeError, ValueError):
                pass
    focus_cpus = sorted(set(focus_cpus))
    candidates = _nested_get(attribution, ["top", "focus_cpu_candidates"]) or []
    if not isinstance(candidates, list):
        candidates = []
    cpu_distribution = attribution.get("cpu_distribution", {}) if isinstance(attribution.get("cpu_distribution"), dict) else {}
    incident = process_thermal_incident(thermal_map, focus_cpus, candidates, cpu_distribution)
    recommended_new_work: dict[str, dict[str, Any]] = {}
    for workload, route in routes.items():
        recommended_new_work[workload] = {
            "allowed": bool(route.get("allowed")),
            "unattended_allowed": bool(route.get("unattended_allowed")),
            "cpuset": _nested_get(route, ["route", "cpuset"]),
            "thread_limit": _nested_get(route, ["route", "thread_limit"]),
        }
    if game_guard.get("active"):
        recommended_new_work["medium"]["unattended_allowed"] = False
        recommended_new_work["medium"]["game_guarded"] = True
        for key in ("heavy", "sustained"):
            item = recommended_new_work[key]
            item["route_would_allow"] = item.get("allowed")
            item["allowed"] = False
            item["unattended_allowed"] = False
            item["game_guarded"] = True
            item["operator_force_supported"] = True
    return {
        "schema": f"{schema_prefix}_process_thermal_plan_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(attribution.get("ok")) and bool(thermal_map.get("ok")),
        "scope": "process CPU thermal orchestration",
        "incident": incident,
        "thermal": {
            "class": thermal_map.get("class"),
            "summary": thermal_map.get("summary"),
            "episode": thermal_map.get("episode"),
            "focus_cpus": focus_cpus,
            "available_by_role_cpuset": thermal_map.get("available_by_role_cpuset"),
        },
        "attribution": {
            "latest": thermal_attribution_latest_path,
            "summary": attribution.get("summary"),
            "incident": attribution.get("incident"),
            "top_focus_cpu_candidates": candidates[: min(top, 10)],
            "cpu_distribution": cpu_distribution,
        },
        "mode": {
            "selected_mode": mode.get("selected_mode"),
            "effective_mode": mode.get("effective_mode"),
            "thermal_class": _nested_get(mode, ["operating", "thermal_class"]) or mode.get("thermal_class"),
            "launch_policy": mode.get("launch_policy"),
        },
        "ai_policy": {
            "class": policy.get("class"),
            "can_run_heavy": policy.get("can_run_heavy"),
            "can_run_routed_heavy": policy.get("can_run_routed_heavy"),
            "can_run_routed_heavy_unattended": policy.get("can_run_routed_heavy_unattended"),
            "heavy_policy": policy.get("heavy_policy"),
            "reasons": policy.get("reasons"),
        },
        "game_guard": {
            "active": game_guard.get("active"),
            "platform_present": game_guard.get("platform_present"),
            "summary": game_guard.get("summary"),
            "latest": game_guard_latest_path,
            "policy": game_guard.get("routing_policy"),
        },
        "desktop_compositor": {
            "latest": desktop_compositor_latest_path,
            "ok": desktop_compositor.get("ok"),
            "degraded": desktop_compositor.get("degraded"),
            "source": desktop_compositor.get("_bounded_source"),
            "timeout_sec": desktop_compositor.get("_bounded_timeout_sec"),
            "fresh_timeout": desktop_compositor.get("fresh_timeout"),
            "fresh_error": desktop_compositor.get("fresh_error"),
            "fallback": desktop_compositor.get("fallback"),
            "summary": desktop_compositor.get("summary"),
            "gnome_shell": desktop_compositor.get("gnome_shell"),
            "display": desktop_compositor.get("display"),
            "status_notifiers": desktop_compositor.get("status_notifiers"),
            "gnome_shell_extensions": {
                "enabled_count": _nested_get(desktop_compositor, ["gnome_shell_extensions", "enabled_count"]),
                "enabled_uuids": _nested_get(desktop_compositor, ["gnome_shell_extensions", "enabled_uuids"]),
                "vitals_enabled": _nested_get(desktop_compositor, ["gnome_shell_extensions", "vitals_enabled"]),
            },
            "atspi_windows": {
                "count": _nested_get(desktop_compositor, ["atspi_windows", "count"]),
                "counts_by_app": _nested_get(desktop_compositor, ["atspi_windows", "counts_by_app"]),
                "counts_by_role": _nested_get(desktop_compositor, ["atspi_windows", "counts_by_role"]),
            },
            "x11_windows": desktop_compositor.get("x11_windows"),
            "wayland_clients": {
                "count": _nested_get(desktop_compositor, ["wayland_clients", "count"]),
                "counts_by_comm": _nested_get(desktop_compositor, ["wayland_clients", "counts_by_comm"]),
            },
            "desktop_process_top": _nested_get(desktop_compositor, ["desktop_processes", "top"]),
            "policy": desktop_compositor.get("policy"),
        },
        "routes": routes,
        "recommended_new_work": recommended_new_work,
        "commands": {
            "fresh_plan": "abyss-machine processes thermal-plan --json",
            "fresh_attribution": "abyss-machine processes thermal-attribution --seconds 3 --interval 0.5 --json",
            "game_guard": "abyss-machine processes game-guard --json",
            "route_heavy": "abyss-machine ai cpu route --class heavy --json",
            "launch_heavy": "abyss-machine ai cpu launch --class heavy -- COMMAND...",
            "launch_heavy_dry_run": "abyss-machine ai cpu launch --class heavy --dry-run -- COMMAND...",
        },
        "policy": {
            "automation": "route_new_work_only",
            "do_not_change_existing_user_process_affinity": True,
            "do_not_change_existing_game_process_affinity": True,
            "do_not_kill_or_throttle_from_this_result": True,
            "game_guard_blocks_new_competing_heavy_work": True,
            "operator_force_supported": True,
            "future_stack_consumption": "abyss-stack may consume this plan and apply stack-owned launch policy without abyss-machine importing the stack.",
        },
        "paths": paths,
        "non_claims": [
            "This plan does not mutate running user processes.",
            "Attribution candidates are evidence for routing, not exclusive causality proof.",
            "Routes are applied only by explicit launch wrappers or future callers that consume them.",
        ],
    }


def _nested_get(data: Any, path: Sequence[str]) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def desktop_compact_text(value: Any, limit: int = 180) -> str:
    try:
        text = "" if value is None else str(value)
    except Exception:
        return "<unreadable>"
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def gsettings_string_array_values(raw: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"'([^']+)'", raw or "")]


def gnome_extension_path(
    uuid: str,
    *,
    home_path: Path | None = None,
    system_extension_root: Path = Path("/usr/share/gnome-shell/extensions"),
) -> Path | None:
    home = home_path if home_path is not None else Path.home()
    for path in (
        home / ".local" / "share" / "gnome-shell" / "extensions" / uuid,
        system_extension_root / uuid,
    ):
        if path.exists():
            return path
    return None


def process_gnome_shell_pid(
    *,
    proc_root: Path = Path("/proc"),
    sysconf: SysconfPort = os.sysconf,
) -> int | None:
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        stat = proc_stat_data(pid, proc_root, sysconf=sysconf)
        if stat.get("comm") != "gnome-shell":
            continue
        cmdline = proc_cmdline(pid, proc_root=proc_root, max_len=1000)
        if "--mode=user" in cmdline or "/gnome-shell" in cmdline or cmdline.startswith("gnome-shell"):
            return pid
    return None


def process_fd_kind_counts(pid: int, *, proc_root: Path = Path("/proc")) -> dict[str, int]:
    counts = {"total": 0, "pidfd": 0, "dmabuf": 0, "socket": 0, "timerfd": 0, "eventfd": 0}
    fd_root = proc_root / str(pid) / "fd"
    try:
        entries = list(fd_root.iterdir())
    except OSError:
        return counts
    counts["total"] = len(entries)
    for item in entries:
        target = safe_readlink(item)
        if target == "anon_inode:[pidfd]":
            counts["pidfd"] += 1
        elif str(target or "").startswith("/dmabuf"):
            counts["dmabuf"] += 1
        elif str(target or "").startswith("socket:"):
            counts["socket"] += 1
        elif target == "anon_inode:[timerfd]":
            counts["timerfd"] += 1
        elif target == "anon_inode:[eventfd]":
            counts["eventfd"] += 1
    return counts


def process_gnome_shell_thread_snapshot(
    pid: int,
    *,
    proc_root: Path = Path("/proc"),
    sysconf: SysconfPort = os.sysconf,
) -> dict[int, dict[str, Any]]:
    snapshot: dict[int, dict[str, Any]] = {}
    task_root = proc_root / str(pid) / "task"
    try:
        tasks = list(task_root.iterdir())
    except OSError:
        return snapshot
    for task in tasks:
        if not task.name.isdigit():
            continue
        tid = int(task.name)
        stat = proc_task_stat_data(pid, tid, proc_root, sysconf=sysconf)
        if not stat:
            continue
        snapshot[tid] = {
            "tid": tid,
            "comm": stat.get("comm"),
            "state": stat.get("state"),
            "cpu_jiffies": stat.get("cpu_jiffies"),
            "starttime_jiffies": stat.get("starttime_jiffies"),
            "wchan": _read_text(task / "wchan"),
        }
    return snapshot


def process_unit_states(
    units: Sequence[str],
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, str]:
    if not command_exists("systemctl"):
        return {unit: "systemctl_missing" for unit in units}
    states: dict[str, str] = {}
    for unit in units:
        out = runner(["systemctl", "--user", "is-active", unit], timeout=1.0)
        states[unit] = (out.get("stdout") or "").strip() or f"rc={out.get('returncode')}"
    return states


def process_gnome_shell_cpu_samples(
    pid: int,
    *,
    seconds: float,
    interval: float,
    units: Sequence[str] = (),
    proc_root: Path = Path("/proc"),
    sysconf: SysconfPort = os.sysconf,
    sleep: SleepPort = time.sleep,
    monotonic: MonotonicPort = time.monotonic,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> list[dict[str, Any]]:
    hz = clock_ticks(sysconf=sysconf) or 100
    samples: list[dict[str, Any]] = []
    started = monotonic()
    previous_at = started
    previous_proc = proc_stat_data(pid, proc_root, sysconf=sysconf)
    previous_threads = process_gnome_shell_thread_snapshot(pid, proc_root=proc_root, sysconf=sysconf)
    seq = 0
    while monotonic() - started < seconds:
        sleep(min(interval, max(0.01, seconds - (monotonic() - started))))
        now = monotonic()
        elapsed = max(0.001, now - previous_at)
        current_proc = proc_stat_data(pid, proc_root, sysconf=sysconf)
        current_threads = process_gnome_shell_thread_snapshot(pid, proc_root=proc_root, sysconf=sysconf)
        proc_delta = int(current_proc.get("cpu_jiffies") or 0) - int(previous_proc.get("cpu_jiffies") or 0)
        top_threads: list[dict[str, Any]] = []
        for tid, current in current_threads.items():
            previous = previous_threads.get(tid)
            if not isinstance(previous, dict):
                continue
            if current.get("starttime_jiffies") != previous.get("starttime_jiffies"):
                continue
            delta = int(current.get("cpu_jiffies") or 0) - int(previous.get("cpu_jiffies") or 0)
            if delta <= 0:
                continue
            top_threads.append({
                "tid": tid,
                "comm": current.get("comm"),
                "state": current.get("state"),
                "cpu_one_core_percent": round((float(delta) / float(hz)) / elapsed * 100.0, 2),
                "wchan": current.get("wchan"),
            })
        top_threads.sort(key=lambda item: float(item.get("cpu_one_core_percent") or 0.0), reverse=True)
        samples.append({
            "seq": seq,
            "elapsed_sec": round(now - started, 3),
            "segment_sec": round(elapsed, 3),
            "cpu_one_core_percent": round((float(max(0, proc_delta)) / float(hz)) / elapsed * 100.0, 2),
            "fd": process_fd_kind_counts(pid, proc_root=proc_root),
            "top_threads": top_threads[:8],
            "units": process_unit_states(units, command_exists=command_exists, runner=runner) if seq % 5 == 0 else None,
        })
        previous_at = now
        previous_proc = current_proc
        previous_threads = current_threads
        seq += 1
    return samples


def process_gdbus_property(
    dest: str,
    path: str,
    interface: str,
    prop: str,
    *,
    timeout: float = 2.0,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    if not command_exists("gdbus"):
        return {"ok": False, "error": "gdbus_missing"}
    out = runner(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            dest,
            "--object-path",
            path,
            "--method",
            "org.freedesktop.DBus.Properties.Get",
            interface,
            prop,
        ],
        timeout=timeout,
    )
    return {
        "ok": bool(out.get("ok")),
        "returncode": out.get("returncode"),
        "stdout": (out.get("stdout") or "").strip(),
        "stderr": (out.get("stderr") or "").strip(),
    }


def process_gnome_display_state(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "gdbus_available": command_exists("gdbus"),
    }
    if not data["gdbus_available"]:
        data["error"] = "gdbus_missing"
        return data
    animations = process_gdbus_property(
        "org.gnome.Shell.Introspect",
        "/org/gnome/Shell/Introspect",
        "org.gnome.Shell.Introspect",
        "AnimationsEnabled",
        command_exists=command_exists,
        runner=runner,
    )
    screen_size = process_gdbus_property(
        "org.gnome.Shell.Introspect",
        "/org/gnome/Shell/Introspect",
        "org.gnome.Shell.Introspect",
        "ScreenSize",
        command_exists=command_exists,
        runner=runner,
    )
    current = runner(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Mutter.DisplayConfig",
            "--object-path",
            "/org/gnome/Mutter/DisplayConfig",
            "--method",
            "org.gnome.Mutter.DisplayConfig.GetCurrentState",
        ],
        timeout=4.0,
    )
    raw = (current.get("stdout") or "").strip()
    current_mode: dict[str, Any] = {}
    marker = "'is-current': <true>"
    marker_index = raw.find(marker)
    if marker_index >= 0:
        mode_start = raw.rfind("('", 0, marker_index)
        fragment = raw[mode_start: marker_index + len(marker) + 80] if mode_start >= 0 else raw[: marker_index + len(marker) + 80]
        match = re.search(r"\('([^']+)',\s*([0-9]+),\s*([0-9]+),\s*([0-9.]+),\s*([0-9.]+)", fragment)
        if match:
            try:
                current_mode = {
                    "id": match.group(1),
                    "width": int(match.group(2)),
                    "height": int(match.group(3)),
                    "refresh_hz": round(float(match.group(4)), 3),
                    "preferred_scale": round(float(match.group(5)), 3),
                }
            except ValueError:
                current_mode = {"id": match.group(1)}
    display_name_match = re.search(r"'display-name': <'([^']+)'>", raw)
    min_refresh_match = re.search(r"'min-refresh-rate': <([0-9.]+)>", raw)
    logical_match = re.search(r"\[\(0,\s*0,\s*([0-9.]+),\s*uint32\s+([0-9]+),\s*(true|false)", raw)
    screen_match = re.search(r"<\(([0-9]+),\s*([0-9]+)\)>", screen_size.get("stdout") or "")
    refresh = current_mode.get("refresh_hz")
    data.update({
        "ok": bool(current.get("ok")),
        "animations_enabled": "<true>" in str(animations.get("stdout")),
        "screen_size": {
            "width": int(screen_match.group(1)),
            "height": int(screen_match.group(2)),
        } if screen_match else None,
        "display": {
            "name": display_name_match.group(1) if display_name_match else None,
            "current_mode": current_mode or None,
            "logical_scale": round(float(logical_match.group(1)), 3) if logical_match else None,
            "primary_logical_monitor": logical_match.group(3) == "true" if logical_match else None,
            "min_refresh_rate_hz": float(min_refresh_match.group(1)) if min_refresh_match else None,
            "high_refresh_active": isinstance(refresh, (int, float)) and float(refresh) >= 90.0,
        },
        "commands": {
            "display_config": "gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig --method org.gnome.Mutter.DisplayConfig.GetCurrentState",
            "animations": "gdbus call --session --dest org.gnome.Shell.Introspect --object-path /org/gnome/Shell/Introspect --method org.freedesktop.DBus.Properties.Get org.gnome.Shell.Introspect AnimationsEnabled",
        },
    })
    if not current.get("ok"):
        data["error"] = (current.get("stderr") or current.get("stdout") or "display_config_failed")[-1000:]
    return data


def process_mutter_session_paths(
    service: str,
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    if not command_exists("busctl"):
        return {"ok": False, "error": "busctl_missing", "session_paths": []}
    out = runner(["busctl", "--user", "tree", service], timeout=2.0)
    text = out.get("stdout") or ""
    paths: list[str] = []
    for match in re.findall(r"(/org/gnome/Mutter/(?:ScreenCast|RemoteDesktop)[^\s]*)", text):
        if "/Session" in match or "/Stream" in match:
            paths.append(match)
    return {
        "ok": bool(out.get("ok")),
        "service": service,
        "session_paths": sorted(set(paths)),
        "active_session_like_paths": len(set(paths)),
        "stderr": (out.get("stderr") or "").strip() or None,
    }


def process_status_notifier_items(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    prop = process_gdbus_property(
        "org.kde.StatusNotifierWatcher",
        "/StatusNotifierWatcher",
        "org.kde.StatusNotifierWatcher",
        "RegisteredStatusNotifierItems",
        command_exists=command_exists,
        runner=runner,
    )
    raw = prop.get("stdout") or ""
    refs = re.findall(r"'([^']+@/[^']+)'", raw)
    items: list[dict[str, Any]] = []
    for ref in refs:
        bus_name, item_path = ref.split("@", 1)
        status_out = runner(["busctl", "--user", "status", bus_name], timeout=2.0) if command_exists("busctl") else {"ok": False, "stdout": "", "stderr": "busctl_missing"}
        pid_match = re.search(r"^PID=([0-9]+)$", status_out.get("stdout") or "", re.MULTILINE)
        pid = int(pid_match.group(1)) if pid_match else None
        props_out = runner(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                bus_name,
                "--object-path",
                item_path,
                "--method",
                "org.freedesktop.DBus.Properties.GetAll",
                "org.kde.StatusNotifierItem",
            ],
            timeout=2.0,
        ) if command_exists("gdbus") else {"ok": False, "stdout": "", "stderr": "gdbus_missing"}
        props_raw = props_out.get("stdout") or ""

        def prop_string(name: str) -> str | None:
            match = re.search(rf"'{re.escape(name)}': <'([^']*)'>", props_raw)
            return match.group(1) if match else None

        items.append({
            "ref": ref,
            "bus_name": bus_name,
            "path": item_path,
            "owner_pid": pid,
            "owner_comm": _read_text(proc_root / str(pid) / "comm") if pid else None,
            "owner_cmdline": proc_cmdline(pid, proc_root=proc_root, max_len=300) if pid else None,
            "id": prop_string("Id"),
            "title": prop_string("Title"),
            "status": prop_string("Status"),
            "icon_name": prop_string("IconName"),
            "icon_theme_path": prop_string("IconThemePath"),
            "properties_ok": bool(props_out.get("ok")),
        })
    return {
        "ok": bool(prop.get("ok")),
        "items": items,
        "count": len(items),
        "raw": raw,
        "error": prop.get("stderr") or None,
    }


def process_gnome_shell_bus_status(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "busctl_available": command_exists("busctl"),
    }
    if not data["busctl_available"]:
        data["error"] = "busctl_missing"
        return data
    out = runner(["busctl", "--user", "status", "org.gnome.Shell"], timeout=2.0)
    text = out.get("stdout") or ""

    def line_value(key: str) -> str | None:
        match = re.search(rf"^{re.escape(key)}=(.*)$", text, re.MULTILINE)
        return match.group(1).strip() if match else None

    pid_text = line_value("PID")
    try:
        pid = int(pid_text) if pid_text else None
    except ValueError:
        pid = None
    data.update({
        "ok": bool(out.get("ok")),
        "pid": pid,
        "unique_name": line_value("UniqueName"),
        "comm": line_value("Comm"),
        "command_line": line_value("CommandLine"),
        "returncode": out.get("returncode"),
        "stderr": (out.get("stderr") or "").strip() or None,
    })
    return data


def process_gnome_shell_introspect_signals(
    seconds: float,
    unique_name: str | None,
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    sample_seconds = max(1.0, min(float(seconds), 5.0))
    data: dict[str, Any] = {
        "ok": False,
        "seconds": sample_seconds,
        "unique_name": unique_name,
        "dbus_monitor_available": command_exists("dbus-monitor"),
        "timeout_available": command_exists("timeout"),
        "source": "dbus-monitor session signal sample",
    }
    if not unique_name:
        data["error"] = "gnome_shell_unique_name_unavailable"
        return data
    if not data["dbus_monitor_available"] or not data["timeout_available"]:
        data["error"] = "dbus_monitor_or_timeout_missing"
        return data
    match = f"type='signal',sender='{unique_name}',path='/org/gnome/Shell/Introspect'"
    out = runner(
        ["timeout", f"{sample_seconds:.2f}", "dbus-monitor", "--session", match],
        timeout=sample_seconds + 2.0,
    )
    text = out.get("stdout") or ""
    counts: collections.Counter[str] = collections.Counter()
    times: list[float] = []
    for line in text.splitlines():
        time_match = re.search(r"signal time=([0-9.]+)", line)
        if time_match:
            try:
                times.append(float(time_match.group(1)))
            except ValueError:
                pass
        member_match = re.search(r"member=([A-Za-z0-9_]+)", line)
        if member_match:
            member = member_match.group(1)
            if member not in {"NameAcquired", "NameLost"}:
                counts[member] += 1
    elapsed = sample_seconds
    if len(times) >= 2:
        elapsed = max(0.001, times[-1] - times[0])
    rates = {name: round(float(count) / elapsed, 3) for name, count in counts.items()}
    data.update({
        "ok": bool(out.get("ok")) or out.get("returncode") == 124,
        "returncode": out.get("returncode"),
        "match": match,
        "signal_counts": dict(counts.most_common()),
        "signal_rates_hz": rates,
        "first_signal_time": min(times) if times else None,
        "last_signal_time": max(times) if times else None,
        "raw_line_count": len(text.splitlines()),
        "stderr": (out.get("stderr") or "").strip() or None,
    })
    return data


def process_vitals_extension_state(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
    home_path: Path | None = None,
    system_extension_root: Path = Path("/usr/share/gnome-shell/extensions"),
) -> dict[str, Any]:
    uuid = "Vitals@CoreCoding.com"
    data: dict[str, Any] = {
        "ok": False,
        "uuid": uuid,
        "enabled": False,
        "read_only": True,
        "does_not_modify_operator_preferences": True,
    }
    enabled_out = runner(["gsettings", "get", "org.gnome.shell", "enabled-extensions"], timeout=2.0) if command_exists("gsettings") else {"ok": False, "stdout": "", "stderr": "gsettings_missing"}
    enabled_raw = enabled_out.get("stdout") or ""
    data["enabled"] = uuid in enabled_raw
    data["enabled_raw_available"] = bool(enabled_out.get("ok"))
    data["enabled_raw_error"] = (enabled_out.get("stderr") or "").strip() or None

    extension_path = gnome_extension_path(
        uuid,
        home_path=home_path,
        system_extension_root=system_extension_root,
    )
    if extension_path is None:
        data["error"] = "extension_path_not_found"
        return data
    data["path"] = str(extension_path)
    metadata_path = extension_path / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    data["metadata"] = {
        "name": metadata.get("name"),
        "version": metadata.get("version"),
        "url": metadata.get("url"),
    }

    schema_dir = extension_path / "schemas"
    settings: dict[str, Any] = {}
    if command_exists("gsettings") and schema_dir.exists():
        out = runner(
            [
                "gsettings",
                "--schemadir",
                str(schema_dir),
                "list-recursively",
                "org.gnome.shell.extensions.vitals",
            ],
            timeout=2.0,
        )
        for line in (out.get("stdout") or "").splitlines():
            parts = line.split(" ", 2)
            if len(parts) != 3:
                continue
            _, key, value = parts
            if (
                key == "update-time"
                or key == "hot-sensors"
                or key == "fixed-widths"
                or key == "hide-icons"
                or key.startswith("show-")
            ):
                settings[key] = value
        data["settings_ok"] = bool(out.get("ok"))
        data["settings_error"] = (out.get("stderr") or "").strip() or None
    else:
        data["settings_error"] = "gsettings_or_schema_dir_missing"
    data["settings"] = settings
    data["ok"] = True
    return data


def process_gnome_shell_extensions_state(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
    home_path: Path | None = None,
    system_extension_root: Path = Path("/usr/share/gnome-shell/extensions"),
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "source": "gsettings + extension metadata read-only snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "does_not_call_gnome_extensions": True,
        "enabled": [],
        "disabled": [],
    }
    if not command_exists("gsettings"):
        data["error"] = "gsettings_missing"
        return data
    values: dict[str, list[str]] = {}
    raw: dict[str, str] = {}
    errors: dict[str, str | None] = {}
    ok = True
    for key in ("enabled-extensions", "disabled-extensions"):
        out = runner(["gsettings", "get", "org.gnome.shell", key], timeout=2.0)
        raw[key] = out.get("stdout") or ""
        errors[key] = (out.get("stderr") or "").strip() or None
        ok = ok and bool(out.get("ok"))
        values[key] = gsettings_string_array_values(raw[key])

    enabled_details: list[dict[str, Any]] = []
    for uuid in values.get("enabled-extensions", []):
        path = gnome_extension_path(
            uuid,
            home_path=home_path,
            system_extension_root=system_extension_root,
        )
        metadata: dict[str, Any] = {}
        if path is not None:
            metadata_path = path / "metadata.json"
            try:
                loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    metadata = loaded
            except (OSError, json.JSONDecodeError):
                metadata = {}
        enabled_details.append({
            "uuid": uuid,
            "path": str(path) if path is not None else None,
            "name": metadata.get("name"),
            "version": metadata.get("version"),
            "url": metadata.get("url"),
        })

    data.update({
        "ok": ok,
        "enabled_count": len(enabled_details),
        "enabled": enabled_details,
        "enabled_uuids": values.get("enabled-extensions", []),
        "disabled_uuids": values.get("disabled-extensions", []),
        "raw_available": ok,
        "raw_errors": errors,
        "vitals_enabled": "Vitals@CoreCoding.com" in values.get("enabled-extensions", []),
        "note": "GSettings enabled extensions show operator preference state; this does not prove live extension CPU attribution.",
    })
    return data


def process_atspi_panel_telemetry_churn(
    seconds: float,
    *,
    pyatspi_module: Any | None = None,
    timer_factory: Callable[[float, Callable[[], Any]], Any] = threading.Timer,
    signal_module: Any = signal,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    sample_seconds = max(1.0, min(float(seconds), 5.0))
    hard_timeout_seconds = sample_seconds + 1.0
    data: dict[str, Any] = {
        "ok": False,
        "seconds": sample_seconds,
        "hard_timeout_seconds": hard_timeout_seconds,
        "source": "AT-SPI read-only event sample",
        "read_only": True,
        "mutates_desktop_state": False,
    }
    if pyatspi_module is None:
        try:
            import pyatspi as loaded_pyatspi  # type: ignore
        except Exception as exc:
            data["error"] = f"pyatspi_unavailable: {exc}"
            return data
        pyatspi_module = loaded_pyatspi

    started = monotonic()
    counts: collections.Counter[str] = collections.Counter()
    top_labels: collections.Counter[str] = collections.Counter()
    samples: list[dict[str, Any]] = []
    metric_re = re.compile(
        r"^(?:"
        r"[0-9]+(?:\.[0-9]+)?\s*(?:%|\u00b0C|GHz|MHz|Hz|KB/s|MB/s|GB/s|B/s|GB|MB|KiB|MiB|GiB|B)"
        r"|[0-9]+"
        r")$"
    )

    def safe_event_text(value: Any, limit: int = 160) -> str:
        try:
            text = "" if value is None else str(value)
        except Exception:
            return "<unreadable>"
        text = " ".join(text.split())
        if len(text) > limit:
            return text[: limit - 3] + "..."
        return text

    def on_event(event: Any) -> None:
        try:
            source = event.source
            app = source.getApplication()
            app_name = safe_event_text(app.name)
            role = safe_event_text(source.getRoleName())
            name = safe_event_text(source.name)
        except Exception:
            return
        event_type = safe_event_text(getattr(event, "type", "unknown"), 120)
        counts[event_type] += 1
        if app_name == "gnome-shell" and role == "label":
            counts["gnome_shell_label_accessible_name"] += 1
            if metric_re.match(name):
                counts["gnome_shell_metric_label_accessible_name"] += 1
                top_labels[name] += 1
        if len(samples) < 30 and app_name == "gnome-shell" and role == "label":
            samples.append({
                "t": round(monotonic() - started, 3),
                "type": event_type,
                "name": name,
            })

    timed_out = False
    previous_alarm_handler: Any = None
    alarm_installed = False

    def on_alarm(signum: int, frame: Any) -> None:
        raise TimeoutError("atspi_panel_telemetry_timeout")

    try:
        pyatspi_module.Registry.registerEventListener(on_event, "object:property-change:accessible-name")
        timer = timer_factory(sample_seconds, pyatspi_module.Registry.stop)
        timer.daemon = True
        timer.start()
        try:
            try:
                previous_alarm_handler = signal_module.getsignal(signal_module.SIGALRM)
                signal_module.signal(signal_module.SIGALRM, on_alarm)
                signal_module.setitimer(signal_module.ITIMER_REAL, hard_timeout_seconds)
                alarm_installed = True
            except (AttributeError, ValueError):
                alarm_installed = False
            try:
                pyatspi_module.Registry.start()
            except TimeoutError:
                timed_out = True
                try:
                    pyatspi_module.Registry.stop()
                except Exception:
                    pass
        finally:
            timer.cancel()
            if alarm_installed:
                try:
                    signal_module.setitimer(signal_module.ITIMER_REAL, 0.0)
                    signal_module.signal(signal_module.SIGALRM, previous_alarm_handler)
                except Exception:
                    pass
    except Exception as exc:
        data["error"] = f"atspi_sample_failed: {exc}"
        return data

    elapsed = max(0.001, monotonic() - started)
    label_count = int(counts.get("gnome_shell_label_accessible_name", 0))
    metric_count = int(counts.get("gnome_shell_metric_label_accessible_name", 0))
    data.update({
        "ok": not timed_out,
        "timed_out": timed_out,
        "elapsed_sec": round(elapsed, 3),
        "event_counts": dict(counts.most_common()),
        "gnome_shell_label_rate_hz": round(float(label_count) / elapsed, 3),
        "gnome_shell_metric_label_rate_hz": round(float(metric_count) / elapsed, 3),
        "top_metric_labels": [{"label": label, "count": count} for label, count in top_labels.most_common(20)],
        "samples": samples,
    })
    if timed_out:
        data["error"] = "atspi_panel_telemetry_timeout"
    return data


def process_atspi_window_snapshot(
    *,
    pyatspi_module: Any | None = None,
    signal_module: Any = signal,
) -> dict[str, Any]:
    hard_timeout_seconds = 3.0
    data: dict[str, Any] = {
        "ok": False,
        "source": "AT-SPI read-only application/window tree snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "hard_timeout_seconds": hard_timeout_seconds,
        "timed_out": False,
        "windows": [],
        "applications": [],
    }
    if pyatspi_module is None:
        try:
            import pyatspi as loaded_pyatspi  # type: ignore
        except Exception as exc:
            data["error"] = f"pyatspi_unavailable: {exc}"
            return data
        pyatspi_module = loaded_pyatspi

    def safe_name(obj: Any) -> str:
        try:
            return desktop_compact_text(obj.name)
        except Exception:
            return "<unreadable>"

    def safe_role(obj: Any) -> str:
        try:
            return desktop_compact_text(obj.getRoleName())
        except Exception:
            return "<unreadable>"

    window_roles = {"frame", "window", "dialog", "alert", "terminal", "document frame"}
    windows: list[dict[str, Any]] = []
    applications: list[dict[str, Any]] = []
    previous_alarm_handler: Any = None
    alarm_installed = False

    def on_alarm(signum: int, frame: Any) -> None:
        raise TimeoutError("atspi_window_snapshot_timeout")

    try:
        try:
            previous_alarm_handler = signal_module.getsignal(signal_module.SIGALRM)
            signal_module.signal(signal_module.SIGALRM, on_alarm)
            signal_module.setitimer(signal_module.ITIMER_REAL, hard_timeout_seconds)
            alarm_installed = True
        except (AttributeError, ValueError):
            alarm_installed = False
        desktop = pyatspi_module.Registry.getDesktop(0)
        apps = list(desktop)
        for app_index, app in enumerate(apps[:80]):
            app_name = safe_name(app)
            app_role = safe_role(app)
            try:
                children = list(app)
            except Exception:
                children = []
            applications.append({
                "index": app_index,
                "name": app_name,
                "role": app_role,
                "child_count": len(children),
            })
            if app_role in {"application", "frame", "window", "dialog"}:
                windows.append({
                    "app": app_name,
                    "role": app_role,
                    "name": app_name,
                    "app_index": app_index,
                })
            for child_index, child in enumerate(children[:120]):
                role = safe_role(child)
                if role in window_roles:
                    windows.append({
                        "app": app_name,
                        "role": role,
                        "name": safe_name(child),
                        "app_index": app_index,
                        "child_index": child_index,
                    })
    except TimeoutError:
        data["timed_out"] = True
        data["error"] = "atspi_window_snapshot_timeout"
    except Exception as exc:
        data["error"] = f"desktop_children_unreadable: {exc}"
    finally:
        if alarm_installed:
            try:
                signal_module.setitimer(signal_module.ITIMER_REAL, 0.0)
                signal_module.signal(signal_module.SIGALRM, previous_alarm_handler)
            except Exception:
                pass

    counts_by_app = collections.Counter(str(item.get("app") or "unknown") for item in windows)
    counts_by_role = collections.Counter(str(item.get("role") or "unknown") for item in windows)
    data.update({
        "ok": not bool(data.get("timed_out")) and not bool(data.get("error")),
        "application_count": len(applications),
        "count": len(windows),
        "windows": windows[:120],
        "applications": applications[:80],
        "counts_by_app": dict(counts_by_app.most_common()),
        "counts_by_role": dict(counts_by_role.most_common()),
        "non_claim": "AT-SPI exposes accessible application/window objects; presence is context, not proof that an app caused GNOME Shell WindowsChanged churn.",
    })
    return data


def process_atspi_window_snapshot_probe_code(path: str = "/usr/local/libexec/abyss-machine") -> str:
    return f"""
import importlib.machinery
import importlib.util
import json
import os
import sys

path = {json.dumps(str(path))}
payload = None
try:
    parent = os.path.dirname(path)
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)
    loader = importlib.machinery.SourceFileLoader("abyss_machine_atspi_probe", path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    payload = mod.process_atspi_window_snapshot()
except BaseException as exc:
    payload = {{
        "ok": False,
        "source": "AT-SPI read-only application/window tree snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "error": f"atspi_window_snapshot_probe_failed: {{type(exc).__name__}}: {{exc}}",
        "exception_type": type(exc).__name__,
        "windows": [],
        "applications": [],
        "count": 0,
        "application_count": 0,
    }}

print(json.dumps(payload, ensure_ascii=False))
"""


def process_atspi_window_snapshot_bounded(
    *,
    timeout_sec: float = 1.5,
    command_runner_json: CommandRunnerPort,
    latest_loader: JsonLoaderPort,
    latest_path: Path,
    python_executable: str = sys.executable,
    probe_path: str = "/usr/local/libexec/abyss-machine",
) -> dict[str, Any]:
    timeout_sec = max(0.8, min(float(timeout_sec), 8.0))
    code = process_atspi_window_snapshot_probe_code(probe_path)
    command = [python_executable, "-c", code]
    fresh = command_runner_json(command, timeout=timeout_sec)
    if fresh.get("ok"):
        fresh["_bounded_source"] = "fresh_subprocess"
        fresh["_bounded_timeout_sec"] = timeout_sec
        return fresh

    latest, latest_error = latest_loader(latest_path)
    latest_atspi = latest.get("atspi_windows") if isinstance(latest, dict) and isinstance(latest.get("atspi_windows"), dict) else {}
    data = dict(latest_atspi) if latest_atspi else {
        "ok": False,
        "source": "AT-SPI read-only application/window tree snapshot",
        "windows": [],
        "applications": [],
        "count": 0,
        "application_count": 0,
    }
    data["degraded"] = True
    data["fresh_timeout"] = fresh.get("returncode") == 124
    data["fresh_error"] = fresh.get("error")
    data["fresh_returncode"] = fresh.get("returncode")
    data["fresh_command"] = fresh.get("command") or command
    data["fallback"] = {
        "source": "latest_desktop_compositor",
        "path": str(latest_path),
        "load_error": latest_error,
        "generated_at": latest.get("generated_at") if isinstance(latest, dict) else None,
        "ok": latest_atspi.get("ok") if latest_atspi else None,
        "count": latest_atspi.get("count") if latest_atspi else None,
    }
    data["_bounded_source"] = "latest_fallback_after_subprocess_failure"
    data["_bounded_timeout_sec"] = timeout_sec
    return data


def process_x11_window_snapshot(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "source": "wmctrl/xprop read-only X11 top-level window snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "wmctrl_available": command_exists("wmctrl"),
        "xprop_available": command_exists("xprop"),
        "windows": [],
    }
    if not data["wmctrl_available"]:
        data["error"] = "wmctrl_missing"
        return data
    out = runner(["env", "DISPLAY=:0", "wmctrl", "-lpGx"], timeout=2.0)
    windows: list[dict[str, Any]] = []
    selected_props = [
        "_NET_WM_NAME",
        "WM_NAME",
        "WM_CLASS",
        "_NET_WM_PID",
        "STEAM_GAME",
        "_VARIABLE_REFRESH",
        "_NET_WM_STATE",
        "_GTK_EDGE_CONSTRAINTS",
        "_NET_WM_WINDOW_TYPE",
    ]

    for line in (out.get("stdout") or "").splitlines():
        parts = line.split(None, 8)
        if len(parts) < 8:
            continue
        title = parts[8] if len(parts) >= 9 else ""
        try:
            pid: int | None = int(parts[2])
        except ValueError:
            pid = None
        try:
            geometry = {
                "x": int(parts[3]),
                "y": int(parts[4]),
                "width": int(parts[5]),
                "height": int(parts[6]),
            }
        except ValueError:
            geometry = None
        item: dict[str, Any] = {
            "window_id": parts[0],
            "desktop": parts[1],
            "pid": pid,
            "pid_note": "X11 _NET_WM_PID may be sandbox-internal for Flatpak/Xwayland clients",
            "geometry": geometry,
            "wm_class": parts[7],
            "title": title,
        }
        if data["xprop_available"]:
            prop_out = runner(
                ["env", "DISPLAY=:0", "xprop", "-id", parts[0], *selected_props],
                timeout=2.0,
            )
            props: dict[str, str] = {}
            for prop_line in (prop_out.get("stdout") or "").splitlines():
                key = prop_line.split("(", 1)[0].split(":", 1)[0].strip()
                value = prop_line.partition("=")[2].strip()
                if key:
                    props[key] = value[:500]
            item["selected_xprops"] = props
            item["xprop_ok"] = bool(prop_out.get("ok"))
            item["xprop_error"] = (prop_out.get("stderr") or "").strip() or None
        windows.append(item)
    data.update({
        "ok": bool(out.get("ok")),
        "returncode": out.get("returncode"),
        "count": len(windows),
        "windows": windows,
        "stderr": (out.get("stderr") or "").strip() or None,
    })
    return data


def parse_ss_users(text: str) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    for match in re.finditer(r'\("([^"]+)",pid=([0-9]+),fd=([0-9]+)\)', text):
        try:
            pid = int(match.group(2))
            fd = int(match.group(3))
        except ValueError:
            continue
        users.append({"comm": match.group(1), "pid": pid, "fd": fd})
    return users


def process_wayland_client_snapshot(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "source": "ss read-only Wayland socket peer snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "ss_available": command_exists("ss"),
        "clients": [],
    }
    if not data["ss_available"]:
        data["error"] = "ss_missing"
        return data
    out = runner(["ss", "-xapH", "-n", "-O"], timeout=4.0)
    endpoint_re = re.compile(
        r"(?P<local>(?:/[^ ]+|@[^ ]+|\*))\s+"
        r"(?P<local_inode>[0-9]+)\s+"
        r"(?P<peer>(?:/[^ ]+|@[^ ]+|\*))\s+"
        r"(?P<peer_inode>[0-9]+)\s+users:"
    )
    endpoints: list[dict[str, Any]] = []
    by_local_inode: dict[str, list[dict[str, Any]]] = {}
    for line in (out.get("stdout") or "").splitlines():
        match = endpoint_re.search(line)
        if not match:
            continue
        endpoint = {
            "local": match.group("local"),
            "local_inode": match.group("local_inode"),
            "peer": match.group("peer"),
            "peer_inode": match.group("peer_inode"),
            "users": parse_ss_users(line),
        }
        endpoints.append(endpoint)
        by_local_inode.setdefault(str(endpoint["local_inode"]), []).append(endpoint)

    clients: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for endpoint in endpoints:
        local = str(endpoint.get("local") or "")
        if "/wayland-" not in local:
            continue
        peer_inode = str(endpoint.get("peer_inode") or "")
        peer_endpoints = by_local_inode.get(peer_inode, [])
        server_users = endpoint.get("users") if isinstance(endpoint.get("users"), list) else []
        server_fds = [
            {"pid": item.get("pid"), "fd": item.get("fd")}
            for item in server_users
            if item.get("comm") == "gnome-shell"
        ]
        for peer_endpoint in peer_endpoints:
            for user in peer_endpoint.get("users") or []:
                try:
                    pid = int(user.get("pid"))
                except (TypeError, ValueError):
                    continue
                key = (pid, peer_inode)
                if key in seen:
                    continue
                seen.add(key)
                clients.append({
                    "comm": user.get("comm"),
                    "pid": pid,
                    "fd": user.get("fd"),
                    "socket_inode": peer_inode,
                    "wayland_socket": local,
                    "gnome_shell_server_fds": server_fds,
                    "cmdline": proc_cmdline(pid, proc_root=proc_root, max_len=240),
                })
    clients.sort(key=lambda item: (str(item.get("comm") or ""), int(item.get("pid") or 0), str(item.get("socket_inode") or "")))
    counts: collections.Counter[str] = collections.Counter(str(item.get("comm") or "unknown") for item in clients)
    data.update({
        "ok": bool(out.get("ok")),
        "returncode": out.get("returncode"),
        "count": len(clients),
        "clients": clients[:40],
        "counts_by_comm": dict(counts.most_common()),
        "stderr": (out.get("stderr") or "").strip() or None,
        "non_claim": "Wayland socket peers show connected clients, not proof that a client caused a redraw or title-change signal.",
    })
    return data


def process_desktop_process_candidates(
    *,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "source": "ps read-only GUI/desktop process candidate snapshot",
        "read_only": True,
        "mutates_desktop_state": False,
        "ps_available": command_exists("ps"),
        "candidates": [],
    }
    if not data["ps_available"]:
        data["error"] = "ps_missing"
        return data
    out = runner(["ps", "-eo", "pid,ppid,comm,pcpu,pmem,rss,etime,args", "--sort=-pcpu"], timeout=3.0)
    exact_comms = {
        "gnome-shell",
        "steamwebhelper",
        "steam",
        "gamescope",
        "xwayland",
        "code",
        "electron",
        "kitty",
        "nautilus",
        "gnome-software",
        "firefox",
        "chrome",
        "chromium",
    }
    prefix_comms = (
        "xdg-desktop-por",
        "ibus",
        "kdeconnect",
        "evolution",
        "gsd-",
    )

    def is_desktop_candidate(comm: str, args: str) -> bool:
        lower_comm = comm.lower()
        lower_args = args.lower()
        if lower_comm in exact_comms or lower_comm.startswith(prefix_comms):
            return True
        if re.search(r"(?<![a-z0-9_-])code(?![a-z0-9_-])", lower_args):
            return True
        return any(token in lower_args for token in ("/steam/", "steamwebhelper", "gamescope", "xwayland", "gnome-software", "xdg-desktop-portal"))

    candidates: list[dict[str, Any]] = []
    for line in (out.get("stdout") or "").splitlines()[1:]:
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid_text, ppid_text, comm, pcpu_text, pmem_text, rss_text, etime, args = parts
        if not is_desktop_candidate(comm, args):
            continue
        try:
            pcpu = float(pcpu_text)
        except ValueError:
            pcpu = 0.0
        try:
            pmem = float(pmem_text)
        except ValueError:
            pmem = 0.0
        try:
            pid = int(pid_text)
            ppid = int(ppid_text)
            rss_kib = int(rss_text)
        except ValueError:
            continue
        candidates.append({
            "pid": pid,
            "ppid": ppid,
            "comm": comm,
            "cpu_percent_ps": pcpu,
            "mem_percent_ps": pmem,
            "rss_kib": rss_kib,
            "etime": etime,
            "cmdline": args[:320],
        })
        if len(candidates) >= 30:
            break
    data.update({
        "ok": bool(out.get("ok")),
        "returncode": out.get("returncode"),
        "candidates": candidates,
        "top": candidates[:10],
        "stderr": (out.get("stderr") or "").strip() or None,
        "non_claim": "ps CPU is a candidate pressure hint and not exclusive compositor attribution.",
    })
    return data


def process_desktop_compositor_command_probes(
    *,
    seconds: float,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
    proc_root: Path = Path("/proc"),
    home_path: Path | None = None,
    system_extension_root: Path = Path("/usr/share/gnome-shell/extensions"),
) -> dict[str, Any]:
    shell_bus = process_gnome_shell_bus_status(command_exists=command_exists, runner=runner)
    return {
        "shell_bus": shell_bus,
        "display": process_gnome_display_state(command_exists=command_exists, runner=runner),
        "status_notifiers": process_status_notifier_items(
            command_exists=command_exists,
            runner=runner,
            proc_root=proc_root,
        ),
        "screencast": process_mutter_session_paths("org.gnome.Mutter.ScreenCast", command_exists=command_exists, runner=runner),
        "remote_desktop": process_mutter_session_paths("org.gnome.Mutter.RemoteDesktop", command_exists=command_exists, runner=runner),
        "vitals": process_vitals_extension_state(
            command_exists=command_exists,
            runner=runner,
            home_path=home_path,
            system_extension_root=system_extension_root,
        ),
        "gnome_extensions": process_gnome_shell_extensions_state(
            command_exists=command_exists,
            runner=runner,
            home_path=home_path,
            system_extension_root=system_extension_root,
        ),
        "x11_windows": process_x11_window_snapshot(command_exists=command_exists, runner=runner),
        "wayland_clients": process_wayland_client_snapshot(command_exists=command_exists, runner=runner, proc_root=proc_root),
        "desktop_processes": process_desktop_process_candidates(command_exists=command_exists, runner=runner),
        "shell_signals": process_gnome_shell_introspect_signals(
            seconds,
            shell_bus.get("unique_name") if isinstance(shell_bus, dict) else None,
            command_exists=command_exists,
            runner=runner,
        ),
    }


def process_desktop_compositor_assessment(
    samples: list[dict[str, Any]],
    display: dict[str, Any],
    status_notifiers: dict[str, Any],
    screen_cast: dict[str, Any],
    remote_desktop: dict[str, Any],
    shell_signals: dict[str, Any],
    panel_telemetry: dict[str, Any],
    vitals: dict[str, Any],
    gnome_extensions: dict[str, Any],
    atspi_windows: dict[str, Any],
    x11_windows: dict[str, Any],
    wayland_clients: dict[str, Any],
    desktop_processes: dict[str, Any],
) -> dict[str, Any]:
    cpu_values = [float(item.get("cpu_one_core_percent") or 0.0) for item in samples]
    avg_cpu = round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else None
    max_cpu = round(max(cpu_values), 2) if cpu_values else None
    current_mode = _nested_get(display, ["display", "current_mode"]) or {}
    refresh = current_mode.get("refresh_hz") if isinstance(current_mode, dict) else None
    high_refresh = isinstance(refresh, (int, float)) and float(refresh) >= 90.0
    notifier_count = int(status_notifiers.get("count") or 0)
    session_paths = int(screen_cast.get("active_session_like_paths") or 0) + int(remote_desktop.get("active_session_like_paths") or 0)
    pidfd_values = [int(_nested_get(item, ["fd", "pidfd"]) or 0) for item in samples]
    dmabuf_values = [int(_nested_get(item, ["fd", "dmabuf"]) or 0) for item in samples]
    windows_changed_rate = float(_nested_get(shell_signals, ["signal_rates_hz", "WindowsChanged"]) or 0.0)
    running_apps_changed_rate = float(_nested_get(shell_signals, ["signal_rates_hz", "RunningApplicationsChanged"]) or 0.0)
    metric_label_rate = float(panel_telemetry.get("gnome_shell_metric_label_rate_hz") or 0.0)
    vitals_enabled = bool(vitals.get("enabled"))
    enabled_extension_count = int(gnome_extensions.get("enabled_count") or 0)
    atspi_window_count = int(atspi_windows.get("count") or 0)
    x11_window_count = int(x11_windows.get("count") or 0)
    wayland_client_count = int(wayland_clients.get("count") or 0)
    desktop_cpu_candidates = desktop_processes.get("top") if isinstance(desktop_processes.get("top"), list) else []
    top_desktop_cpu = desktop_cpu_candidates[0] if desktop_cpu_candidates else None
    top_desktop_cpu_comm = str(top_desktop_cpu.get("comm") or "") if isinstance(top_desktop_cpu, dict) else None
    top_desktop_cpu_percent = float(top_desktop_cpu.get("cpu_percent_ps") or 0.0) if isinstance(top_desktop_cpu, dict) else 0.0
    steam_window_present = any(
        "steam" in str(item.get("wm_class") or "").lower() or "steam" in str(item.get("title") or "").lower()
        for item in x11_windows.get("windows", [])
        if isinstance(item, dict)
    )
    findings: list[str] = []
    if high_refresh:
        findings.append("high_refresh_display_active")
    if windows_changed_rate >= 2.0:
        findings.append("shell_introspect_windows_changed_churn")
    if running_apps_changed_rate >= 0.5:
        findings.append("shell_introspect_running_applications_changed_churn")
    if metric_label_rate >= 5.0:
        findings.append("panel_telemetry_metric_label_churn")
    if vitals_enabled:
        findings.append("vitals_extension_active")
    if enabled_extension_count:
        findings.append("gnome_shell_extensions_enabled")
    if atspi_window_count:
        findings.append("atspi_accessible_windows_present")
    atspi_window_items = atspi_windows.get("windows") if isinstance(atspi_windows.get("windows"), list) else []
    atspi_apps = {
        str(item.get("app") or "")
        for item in atspi_window_items
        if isinstance(item, dict)
    }
    if "org.gnome.Nautilus" in atspi_apps:
        findings.append("nautilus_atspi_frame_present")
    if "mutter-x11-frames" in atspi_apps:
        findings.append("mutter_x11_frames_atspi_present")
    if x11_window_count:
        findings.append("x11_top_level_windows_present")
    if wayland_client_count:
        findings.append("wayland_clients_present")
    if steam_window_present:
        findings.append("steam_x11_window_present")
    if top_desktop_cpu_percent >= 10.0:
        findings.append("desktop_process_cpu_candidate_present")
    if top_desktop_cpu_percent >= 10.0 and top_desktop_cpu_comm and "steamwebhelper" in top_desktop_cpu_comm.lower():
        findings.append("steamwebhelper_cpu_candidate_present")
    if avg_cpu is not None and avg_cpu >= 15.0 and high_refresh:
        findings.append("gnome_shell_high_refresh_compositor_cpu_pressure")
    elif avg_cpu is not None and avg_cpu >= 20.0:
        findings.append("gnome_shell_sustained_compositor_cpu_pressure")
    elif max_cpu is not None and max_cpu >= 35.0:
        findings.append("gnome_shell_bursty_compositor_cpu_pressure")
    if pidfd_values and max(pidfd_values) == min(pidfd_values):
        findings.append("pidfd_count_stable")
    if dmabuf_values and max(dmabuf_values) == min(dmabuf_values):
        findings.append("dmabuf_count_stable")
    if notifier_count:
        findings.append("status_notifier_items_present")
    if session_paths:
        findings.append("screencast_or_remote_session_paths_present")

    if metric_label_rate >= 5.0 and avg_cpu is not None and avg_cpu >= 8.0:
        classification = "panel_telemetry_compositor_churn"
    elif windows_changed_rate >= 2.0 and avg_cpu is not None and avg_cpu >= 8.0:
        classification = "window_state_churn_compositor_pressure"
    elif high_refresh and avg_cpu is not None and avg_cpu >= 15.0:
        classification = "high_refresh_compositor_pressure"
    elif avg_cpu is not None and avg_cpu >= 20.0:
        classification = "compositor_cpu_pressure"
    elif max_cpu is not None and max_cpu >= 35.0:
        classification = "bursty_compositor_redraw"
    else:
        classification = "baseline_or_light_compositor_activity"
    if metric_label_rate >= 5.0:
        route_guidance = "treat as panel telemetry churn evidence, not as proof that Vitals or any extension is the CPU cause; preserve best display quality/high refresh, route new CPU work around GNOME Shell when needed, and only change panel telemetry cadence/sensors with explicit operator approval"
        non_claim = "This identifies GNOME Shell metric-label churn during the sample, but prior low-cost extension measurements and a controlled operator-visible A/B step are still required before attributing CPU cost to Vitals or changing desktop settings."
    else:
        route_guidance = "treat as desktop compositor pressure; preserve display quality/high refresh by default, route new CPU work around it, and investigate redraw sources before considering any visible desktop-quality tradeoff"
        non_claim = "This does not prove a specific visible window or extension caused the redraw without a controlled operator-visible isolation step."
    return {
        "classification": classification,
        "findings": findings,
        "cpu_avg_one_core_percent": avg_cpu,
        "cpu_max_one_core_percent": max_cpu,
        "refresh_hz": refresh,
        "high_refresh_active": high_refresh,
        "windows_changed_rate_hz": round(windows_changed_rate, 3),
        "running_applications_changed_rate_hz": round(running_apps_changed_rate, 3),
        "panel_metric_label_rate_hz": round(metric_label_rate, 3),
        "status_notifier_count": notifier_count,
        "enabled_extension_count": enabled_extension_count,
        "atspi_window_count": atspi_window_count,
        "atspi_window_apps": dict((atspi_windows.get("counts_by_app") or {})) if isinstance(atspi_windows.get("counts_by_app"), dict) else {},
        "x11_window_count": x11_window_count,
        "wayland_client_count": wayland_client_count,
        "top_desktop_cpu_candidate": top_desktop_cpu,
        "screencast_or_remote_session_like_paths": session_paths,
        "route_guidance": route_guidance,
        "non_claim": non_claim,
    }


def process_desktop_compositor_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    seconds: float,
    interval: float,
    pid: int | None,
    process_info_data: dict[str, Any] | None,
    samples: list[dict[str, Any]],
    display: dict[str, Any],
    shell_bus: dict[str, Any],
    shell_signals: dict[str, Any],
    panel_telemetry: dict[str, Any],
    atspi_windows: dict[str, Any],
    vitals: dict[str, Any],
    gnome_extensions: dict[str, Any],
    x11_windows: dict[str, Any],
    wayland_clients: dict[str, Any],
    desktop_processes: dict[str, Any],
    status_notifiers: dict[str, Any],
    screen_cast: dict[str, Any],
    remote_desktop: dict[str, Any],
) -> dict[str, Any]:
    fd_values = [item.get("fd", {}) for item in samples if isinstance(item.get("fd"), dict)]
    cpu_values = [float(item.get("cpu_one_core_percent") or 0.0) for item in samples]
    top_thread_counts: dict[str, int] = {}
    for sample in samples:
        top_threads = sample.get("top_threads") if isinstance(sample.get("top_threads"), list) else []
        if top_threads:
            top = top_threads[0]
            key = f"{top.get('tid')}:{top.get('comm')}"
            top_thread_counts[key] = top_thread_counts.get(key, 0) + 1
    dominant_thread = None
    if top_thread_counts:
        dominant_key = sorted(top_thread_counts.items(), key=lambda item: item[1], reverse=True)[0][0]
        tid_text, _, comm = dominant_key.partition(":")
        try:
            tid_value: int | None = int(tid_text)
        except ValueError:
            tid_value = None
        dominant_thread = {"tid": tid_value, "comm": comm, "top_sample_count": top_thread_counts[dominant_key]}
    assessment = process_desktop_compositor_assessment(
        samples,
        display,
        status_notifiers,
        screen_cast,
        remote_desktop,
        shell_signals,
        panel_telemetry,
        vitals,
        gnome_extensions,
        atspi_windows,
        x11_windows,
        wayland_clients,
        desktop_processes,
    )
    return {
        "schema": f"{schema_prefix}_process_desktop_compositor_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": pid is not None and bool(samples),
        "paths": paths,
        "capture": {
            "source": "/proc gnome-shell + GNOME/Mutter DBus read-only state + GNOME Shell signal sample + AT-SPI panel/window samples + GNOME extension preference snapshot + X11/Wayland/client CPU context",
            "seconds_requested": seconds,
            "interval_seconds": interval,
            "samples": len(samples),
            "facts_only": True,
            "mutates_desktop_state": False,
            "does_not_toggle_extensions": True,
        },
        "gnome_shell": {
            "pid": pid,
            "process": process_info_data,
            "bus": shell_bus,
            "cpu": {
                "avg_one_core_percent": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else None,
                "min_one_core_percent": round(min(cpu_values), 2) if cpu_values else None,
                "max_one_core_percent": round(max(cpu_values), 2) if cpu_values else None,
                "dominant_thread": dominant_thread,
            },
            "fd": {
                "first": fd_values[0] if fd_values else None,
                "last": fd_values[-1] if fd_values else None,
                "pidfd_delta": int(fd_values[-1].get("pidfd", 0)) - int(fd_values[0].get("pidfd", 0)) if len(fd_values) >= 2 else None,
                "dmabuf_delta": int(fd_values[-1].get("dmabuf", 0)) - int(fd_values[0].get("dmabuf", 0)) if len(fd_values) >= 2 else None,
                "total_min": min(int(item.get("total") or 0) for item in fd_values) if fd_values else None,
                "total_max": max(int(item.get("total") or 0) for item in fd_values) if fd_values else None,
            },
        },
        "display": display,
        "shell_introspect_signals": shell_signals,
        "panel_telemetry_churn": panel_telemetry,
        "atspi_windows": atspi_windows,
        "vitals_extension": vitals,
        "gnome_shell_extensions": gnome_extensions,
        "x11_windows": x11_windows,
        "wayland_clients": wayland_clients,
        "desktop_processes": desktop_processes,
        "status_notifiers": status_notifiers,
        "screencast": screen_cast,
        "remote_desktop": remote_desktop,
        "summary": assessment,
        "samples": samples,
        "policy": {
            "automation": "observe_only",
            "do_not_kill_or_throttle_from_this_result": True,
            "do_not_disable_autocapture_from_this_result": True,
            "do_not_toggle_gnome_extensions_from_this_result": True,
            "safe_next_step": "Use repeated samples and operator-visible context to find redraw sources; do not lower display refresh/quality, toggle extensions, or change Steam/GUI state unless the operator explicitly requests that tradeoff.",
        },
        "non_claims": [
            "This does not identify a specific visible window on Wayland when GNOME Introspect denies window access.",
            "Status notifier presence is a candidate context, not proof of redraw spam.",
            "A high-refresh display amplifies compositor work but is not by itself a bug.",
            "AT-SPI application/window objects are context for hidden desktop state, not proof of WindowsChanged causality.",
            "X11/Wayland/client CPU evidence is candidate context, not proof of compositor causality without a controlled operator-visible isolation step.",
        ],
    }


def container_name_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).lstrip("/") for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip().lstrip("/")]
    return []


def sanitized_container_labels(labels: Any) -> dict[str, str]:
    if not isinstance(labels, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in labels.items()
        if key in CONTAINER_LABEL_ALLOWLIST and isinstance(value, (str, int, float, bool))
    }


def redact_container_mount(mount: dict[str, Any]) -> dict[str, Any]:
    source = str(mount.get("Source") or "")
    destination = str(mount.get("Destination") or "")
    return {
        "type": mount.get("Type"),
        "name": mount.get("Name"),
        "source": source,
        "destination": destination,
        "rw": bool(mount.get("RW")),
        "work_mount": source.startswith("/srv/work/") or source.startswith("/work/") or destination.startswith("/work/"),
        "graphroot_volume": "/containers/storage/volumes/" in source or "/.local/share/containers/storage/volumes/" in source,
    }


def read_container_ports(container: dict[str, Any]) -> dict[str, Any]:
    network = container.get("NetworkSettings", {}) if isinstance(container.get("NetworkSettings"), dict) else {}
    ports = network.get("Ports", {}) if isinstance(network.get("Ports"), dict) else {}
    redacted: dict[str, Any] = {}
    for container_port, bindings in ports.items():
        if not isinstance(bindings, list):
            redacted[container_port] = bindings
            continue
        redacted[container_port] = [
            {"host_ip": item.get("HostIp"), "host_port": item.get("HostPort")}
            for item in bindings
            if isinstance(item, dict)
        ]
    return redacted


def safe_container_summary(container: dict[str, Any]) -> dict[str, Any]:
    state = container.get("State", {}) if isinstance(container.get("State"), dict) else {}
    host_config = container.get("HostConfig", {}) if isinstance(container.get("HostConfig"), dict) else {}
    mounts = [redact_container_mount(item) for item in container.get("Mounts", []) if isinstance(item, dict)]
    return {
        "id": str(container.get("Id") or "")[:12],
        "name": container.get("Name"),
        "image": container.get("ImageName"),
        "status": state.get("Status"),
        "running": bool(state.get("Running")),
        "pid": state.get("Pid"),
        "restart_policy": host_config.get("RestartPolicy"),
        "network_mode": host_config.get("NetworkMode"),
        "ports": read_container_ports(container),
        "mounts": mounts,
        "work_mounts": [item for item in mounts if item.get("work_mount")],
        "named_volumes": [item for item in mounts if item.get("type") == "volume" or item.get("name")],
        "graph_paths": {
            "static_dir": container.get("StaticDir"),
            "oci_config": container.get("OCIConfigPath"),
        },
        "redaction": {
            "env_omitted": True,
            "create_command_omitted": True,
        },
    }


def _container_health_base(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: str,
    daily_glob: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_process_container_health_v1",
        "version": version,
        "generated_at": generated_at,
        "paths": {
            "latest": latest_path,
            "daily_glob": daily_glob,
        },
    }


def process_container_health_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: str,
    daily_glob: str,
    command_exists: CommandExistsPort = default_command_exists,
    runner: CommandRunnerPort,
) -> dict[str, Any]:
    data = _container_health_base(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        latest_path=latest_path,
        daily_glob=daily_glob,
    )
    if not command_exists("podman"):
        return {
            **data,
            "ok": False,
            "error": "podman is not installed",
            "summary": {"status": "unavailable"},
        }

    ps_run = runner(["podman", "ps", "-a", "--format", "json"], timeout=10.0)
    if not ps_run.get("ok"):
        return {
            **data,
            "ok": False,
            "error": ps_run.get("stderr") or ps_run.get("stdout") or "podman ps failed",
            "returncode": ps_run.get("returncode"),
            "summary": {"status": "unavailable"},
        }
    try:
        raw_containers = json.loads(str(ps_run.get("stdout") or "[]"))
    except json.JSONDecodeError as exc:
        return {
            **data,
            "ok": False,
            "error": f"invalid podman ps JSON: {exc}",
            "summary": {"status": "unavailable"},
        }
    if not isinstance(raw_containers, list):
        raw_containers = []

    inspect_by_id: dict[str, dict[str, Any]] = {}
    ids = [str(item.get("Id")) for item in raw_containers if isinstance(item, dict) and item.get("Id")]
    if ids:
        inspect_run = runner(["podman", "inspect", *ids], timeout=20.0)
        if inspect_run.get("ok"):
            try:
                inspected = json.loads(str(inspect_run.get("stdout") or "[]"))
                if isinstance(inspected, list):
                    inspect_by_id = {
                        str(item.get("Id")): item
                        for item in inspected
                        if isinstance(item, dict) and item.get("Id")
                    }
            except json.JSONDecodeError:
                inspect_by_id = {}

    containers: list[dict[str, Any]] = []
    attention: list[dict[str, Any]] = []
    for raw in raw_containers:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("Id") or "")
        inspected = inspect_by_id.get(cid, {})
        state_info = inspected.get("State", {}) if isinstance(inspected.get("State"), dict) else {}
        config = inspected.get("Config", {}) if isinstance(inspected.get("Config"), dict) else {}
        host_config = inspected.get("HostConfig", {}) if isinstance(inspected.get("HostConfig"), dict) else {}
        restart_policy = host_config.get("RestartPolicy", {}) if isinstance(host_config.get("RestartPolicy"), dict) else {}
        labels = sanitized_container_labels(config.get("Labels") or raw.get("Labels"))
        names = container_name_list(raw.get("Names"))
        if not names and isinstance(inspected.get("Name"), str):
            names = [str(inspected.get("Name")).lstrip("/")]
        name = names[0] if names else cid[:12]
        status_text = str(raw.get("Status") or state_info.get("Status") or "")
        status_lower = status_text.lower()
        state = str(raw.get("State") or state_info.get("Status") or "").lower()
        running = bool(state_info.get("Running")) if "Running" in state_info else state == "running"
        restarting = bool(state_info.get("Restarting")) or "restarting" in status_lower
        dead = bool(state_info.get("Dead")) or state == "dead"
        stopped_by_user = state_info.get("StoppedByUser")
        exit_code = safe_int(state_info.get("ExitCode", raw.get("ExitCode")), 0)
        intentional_user_stop = bool(stopped_by_user) and not running and exit_code in (0, 143)
        restart_count = safe_int(inspected.get("RestartCount", raw.get("Restarts")), 0)
        health_info = state_info.get("Health", {}) if isinstance(state_info.get("Health"), dict) else {}
        health_status = health_info.get("Status")
        if not health_status:
            if "(healthy)" in status_lower:
                health_status = "healthy"
            elif "(unhealthy)" in status_lower:
                health_status = "unhealthy"
        compose_project = labels.get("io.podman.compose.project") or labels.get("com.docker.compose.project")
        compose_service = labels.get("io.podman.compose.service") or labels.get("com.docker.compose.service")
        systemd_unit = labels.get("PODMAN_SYSTEMD_UNIT")
        stack_managed = (
            compose_project == "abyss"
            or systemd_unit == "podman-compose@abyss.service"
            or any(item.startswith("abyss_") for item in names)
        )
        policy_name = str(restart_policy.get("Name") or "").lower()
        reasons: list[str] = []
        if dead:
            reasons.append("dead")
        if restarting:
            reasons.append("restarting")
        if health_status == "unhealthy":
            reasons.append("unhealthy")
        if restart_count > 0 and not intentional_user_stop:
            reasons.append("restart_count_nonzero")
        if not running and exit_code not in (0, 143):
            reasons.append("exited_nonzero")
        if not running and policy_name in {"always", "unless-stopped", "on-failure"} and not stopped_by_user:
            reasons.append("restart_policy_not_running")
        if stack_managed and not running and not stopped_by_user:
            reasons.append("abyss_stack_not_running")

        item = {
            "id": cid[:12],
            "name": name,
            "names": names,
            "image": raw.get("Image"),
            "image_id": str(raw.get("ImageID") or "")[:12] if raw.get("ImageID") else None,
            "state": state,
            "status": status_text,
            "running": running,
            "restarting": restarting,
            "dead": dead,
            "pid": state_info.get("Pid") or raw.get("Pid"),
            "exit_code": exit_code,
            "oom_killed": bool(state_info.get("OOMKilled")),
            "stopped_by_user": stopped_by_user,
            "intentional_user_stop": intentional_user_stop,
            "restart_count": restart_count,
            "restart_policy": restart_policy,
            "health": health_status,
            "started_at": state_info.get("StartedAt") or raw.get("StartedAt"),
            "finished_at": state_info.get("FinishedAt") or raw.get("ExitedAt"),
            "ports": raw.get("Ports"),
            "compose": {
                "project": compose_project,
                "service": compose_service,
                "systemd_unit": systemd_unit,
                "stack_managed": stack_managed,
            },
            "labels": labels,
            "attention_reasons": reasons,
        }
        containers.append(item)
        if reasons:
            attention.append({
                "name": name,
                "state": state,
                "status": status_text,
                "restart_count": restart_count,
                "exit_code": exit_code,
                "compose": item["compose"],
                "reasons": reasons,
            })

    return {
        **data,
        "ok": True,
        "summary": {
            "status": "attention" if attention else "ok",
            "containers": len(containers),
            "running": sum(1 for item in containers if item.get("running")),
            "exited": sum(1 for item in containers if not item.get("running")),
            "restarting": sum(1 for item in containers if item.get("restarting")),
            "unhealthy": sum(1 for item in containers if item.get("health") == "unhealthy"),
            "restart_count_nonzero": sum(1 for item in containers if safe_int(item.get("restart_count"), 0) > 0),
            "abyss_stack_managed": sum(1 for item in containers if item.get("compose", {}).get("stack_managed")),
            "attention": len(attention),
        },
        "capture": {
            "source": "podman ps -a plus sanitized podman inspect state",
            "facts_only": True,
            "includes_env": False,
            "includes_create_command": False,
            "includes_mount_contents": False,
        },
        "attention": attention,
        "containers": sorted(containers, key=lambda item: str(item.get("name") or "")),
        "non_claims": [
            "Stopped containers may be intentional; attention reasons are routing hints for agents, not an automatic stop/start policy.",
            "This report intentionally excludes container environment variables, create commands, and mount contents.",
            "This command does not mutate containers.",
        ],
    }
