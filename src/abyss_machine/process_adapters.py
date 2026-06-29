from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Sequence

from . import process_contracts


SysconfPort = Callable[[str | int], int]
SleepPort = Callable[[float], None]
MonotonicPort = Callable[[], float]
CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[..., dict[str, Any]]

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
