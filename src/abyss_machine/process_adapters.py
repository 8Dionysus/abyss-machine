from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any, Callable, Sequence

from . import process_contracts


SysconfPort = Callable[[str | int], int]
SleepPort = Callable[[float], None]


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
