from __future__ import annotations

import ctypes
import http.client
import json
import math
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import tempfile
import time
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

try:
    from . import memory_adapters, resource_adapters
except ImportError:  # Supports bootstrap-installed direct module copies.
    from abyss_machine import memory_adapters, resource_adapters


EpochPort = Callable[[], float]
MonotonicPort = Callable[[], float]
ReservationsPort = Callable[[], dict[str, Any]]
HttpRoutePort = Callable[[Mapping[str, Any]], dict[str, Any]]


IN_ACCESS = 0x00000001
IN_MODIFY = 0x00000002
IN_ATTRIB = 0x00000004
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_IGNORED = 0x00008000
DEFAULT_INOTIFY_MASK = (
    IN_MODIFY
    | IN_ATTRIB
    | IN_CLOSE_WRITE
    | IN_MOVED_FROM
    | IN_MOVED_TO
    | IN_CREATE
    | IN_DELETE
    | IN_DELETE_SELF
    | IN_MOVE_SELF
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bytes_mib(value: Any) -> float:
    return round(max(0.0, _number(value)) / 1024.0 / 1024.0, 3)


def _kib_mib(value: Any) -> float:
    return round(max(0.0, _number(value)) / 1024.0, 3)


def parse_meminfo(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in _read_text(path).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        token = value.strip().split(maxsplit=1)[0] if value.strip() else ""
        try:
            result[key.strip()] = int(token)
        except ValueError:
            continue
    return result


def parse_proc_swaps(path: Path) -> dict[str, Any]:
    devices: list[dict[str, Any]] = []
    for line in _read_text(path).splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            size_kib = int(parts[2])
            used_kib = int(parts[3])
            priority = int(parts[4])
        except ValueError:
            continue
        devices.append({"name": parts[0], "type": parts[1], "size_kib": size_kib, "used_kib": used_kib, "priority": priority})
    total_kib = sum(item["size_kib"] for item in devices)
    used_kib = sum(item["used_kib"] for item in devices)
    return {
        "devices": devices,
        "total_mib": _kib_mib(total_kib),
        "used_mib": _kib_mib(used_kib),
        "free_mib": _kib_mib(max(0, total_kib - used_kib)),
    }


def zram_snapshot(*, sys_root: Path = Path("/sys"), page_size: int | None = None) -> dict[str, Any]:
    if page_size is None:
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError):
            page_size = 4096
    resolved_page_size = max(1, int(page_size))
    devices: list[dict[str, Any]] = []
    for root in sorted((sys_root / "block").glob("zram*")) if (sys_root / "block").is_dir() else []:
        mm_values = _read_text(root / "mm_stat").split()
        try:
            values = [int(value) for value in mm_values]
        except ValueError:
            values = []
        try:
            disk_bytes = int(_read_text(root / "disksize").strip() or "0")
        except ValueError:
            disk_bytes = 0
        bd_values = [_number(item) for item in _read_text(root / "bd_stat").split()]
        io_values = [_number(item) for item in _read_text(root / "io_stat").split()]
        data_bytes = values[0] if len(values) > 0 else 0
        compressed_bytes = values[1] if len(values) > 1 else 0
        resident_bytes = values[2] if len(values) > 2 else 0
        incompressible_pages = values[7] if len(values) > 7 else 0
        algorithm_text = _read_text(root / "comp_algorithm").strip()
        selected_algorithm = (re.search(r"\[([^\]]+)\]", algorithm_text) or [None, None])[1]
        devices.append({
            "name": root.name,
            "disk_bytes": disk_bytes,
            "data_bytes": data_bytes,
            "compressed_bytes": compressed_bytes,
            "resident_bytes": resident_bytes,
            "allocator_metadata_overhead_bytes": max(0, resident_bytes - compressed_bytes),
            "physical_savings_bytes": max(0, data_bytes - resident_bytes),
            "peak_resident_bytes": values[4] if len(values) > 4 else 0,
            "same_pages": values[5] if len(values) > 5 else 0,
            "pages_compacted": values[6] if len(values) > 6 else 0,
            "incompressible_pages": incompressible_pages,
            "incompressible_since_pages": values[8] if len(values) > 8 else 0,
            "incompressible_bytes": incompressible_pages * resolved_page_size,
            "backing_bytes": int(bd_values[0] * resolved_page_size) if len(bd_values) > 0 else 0,
            "backing_read_bytes": int(bd_values[1] * resolved_page_size) if len(bd_values) > 1 else 0,
            "backing_write_bytes": int(bd_values[2] * resolved_page_size) if len(bd_values) > 2 else 0,
            "failed_reads": int(io_values[0]) if len(io_values) > 0 else 0,
            "failed_writes": int(io_values[1]) if len(io_values) > 1 else 0,
            "invalid_io": int(io_values[2]) if len(io_values) > 2 else 0,
            "notify_free": int(io_values[3]) if len(io_values) > 3 else 0,
            "algorithm": selected_algorithm,
            "backing_device": _read_text(root / "backing_dev").strip(),
            "compressed_writeback": _read_text(root / "compressed_writeback").strip(),
        })
    total_data = sum(item["data_bytes"] for item in devices)
    total_compressed = sum(item["compressed_bytes"] for item in devices)
    total_resident = sum(item["resident_bytes"] for item in devices)
    return {
        "devices": devices,
        "disk_mib": _bytes_mib(sum(item["disk_bytes"] for item in devices)),
        "data_mib": _bytes_mib(total_data),
        "compressed_mib": _bytes_mib(total_compressed),
        "resident_mib": _bytes_mib(total_resident),
        "allocator_metadata_overhead_mib": _bytes_mib(sum(item["allocator_metadata_overhead_bytes"] for item in devices)),
        "physical_savings_mib": _bytes_mib(sum(item["physical_savings_bytes"] for item in devices)),
        "incompressible_mib": _bytes_mib(sum(item["incompressible_bytes"] for item in devices)),
        "backing_mib": _bytes_mib(sum(item["backing_bytes"] for item in devices)),
        "backing_read_mib": _bytes_mib(sum(item["backing_read_bytes"] for item in devices)),
        "backing_write_mib": _bytes_mib(sum(item["backing_write_bytes"] for item in devices)),
        "logical_to_resident_ratio": None if total_resident <= 0 else round(total_data / total_resident, 3),
        "allocator_efficiency_ratio": None if total_resident <= 0 else round(total_compressed / total_resident, 3),
    }


def default_user_cgroup_path(*, cgroup_root: Path = Path("/sys/fs/cgroup"), uid: int | None = None) -> Path:
    resolved_uid = os.getuid() if uid is None else int(uid)
    return cgroup_root / "user.slice" / f"user-{resolved_uid}.slice" / f"user@{resolved_uid}.service"


def cgroup_memory_snapshot(path: Path) -> dict[str, Any]:
    def read_int(name: str) -> int:
        try:
            return int(_read_text(path / name).strip() or "0")
        except ValueError:
            return 0

    return {
        "path": str(path),
        "exists": path.is_dir(),
        "memory_mib": _bytes_mib(read_int("memory.current")),
        "swap_mib": _bytes_mib(read_int("memory.swap.current")),
        "events": memory_adapters.parse_key_value_file(path / "memory.events"),
    }


def safe_user_cgroup_snapshot(measurement: Mapping[str, Any]) -> dict[str, Any]:
    try:
        uid = int(measurement.get("uid"))
    except (TypeError, ValueError):
        return {"ok": False, "status": "measurement_uid_invalid"}
    if uid != os.getuid():
        return {"ok": False, "status": "measurement_uid_not_controller_uid", "uid": uid}
    requested = Path(str(measurement.get("path") or ""))
    allowed_root = Path("/sys/fs/cgroup") / "user.slice" / f"user-{uid}.slice"
    try:
        resolved_root = allowed_root.resolve(strict=True)
        resolved = requested.resolve(strict=True)
    except OSError as exc:
        return {"ok": False, "status": "measurement_cgroup_unavailable", "error": str(exc), "path": str(requested)}
    if not resolved.is_relative_to(resolved_root) or not resolved.is_dir():
        return {"ok": False, "status": "measurement_cgroup_outside_user_slice", "path": str(resolved)}
    snapshot = cgroup_memory_snapshot(resolved)
    return {"ok": snapshot.get("exists") is True, "status": "measurement_ready", **snapshot}


def collect_memory_sample(
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
    cgroup_path: Path | None = None,
    reservations_port: ReservationsPort | None = None,
    queued_demand_mib: float = 0.0,
    epoch_port: EpochPort = time.time,
    monotonic_port: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    meminfo = parse_meminfo(proc_root / "meminfo")
    pressure = memory_adapters.parse_pressure_file(proc_root / "pressure" / "memory")
    vmstat = memory_adapters.vmstat_snapshot(proc_root=proc_root)
    swaps = parse_proc_swaps(proc_root / "swaps")
    zram = zram_snapshot(sys_root=sys_root)
    resolved_cgroup = cgroup_path or default_user_cgroup_path(cgroup_root=sys_root / "fs" / "cgroup")
    cgroup = cgroup_memory_snapshot(resolved_cgroup)
    reservations = reservations_port() if reservations_port is not None else {"summary": {}}
    reservation_summary = reservations.get("summary") if isinstance(reservations.get("summary"), Mapping) else {}
    total_mib = _kib_mib(meminfo.get("MemTotal", 0))
    available_mib = _kib_mib(meminfo.get("MemAvailable", 0))
    swap_total_mib = swaps["total_mib"] or _kib_mib(meminfo.get("SwapTotal", 0))
    swap_free_mib = swaps["free_mib"] if swaps["devices"] else _kib_mib(meminfo.get("SwapFree", 0))
    swap_used_mib = max(0.0, swap_total_mib - swap_free_mib)
    some = pressure.get("some") if isinstance(pressure.get("some"), Mapping) else {}
    full = pressure.get("full") if isinstance(pressure.get("full"), Mapping) else {}
    commit_limit = _kib_mib(meminfo.get("CommitLimit", 0))
    committed = _kib_mib(meminfo.get("Committed_AS", 0))
    required_paths = [proc_root / "meminfo", proc_root / "pressure" / "memory", proc_root / "vmstat"]
    missing = [str(path) for path in required_paths if not path.exists()]
    return {
        "schema": "abyss_machine_memory_controller_sample_v1",
        "ok": not missing,
        "epoch": float(epoch_port()),
        "monotonic": float(monotonic_port()),
        "mem_total_mib": total_mib,
        "mem_available_mib": available_mib,
        "mem_available_percent": 0.0 if total_mib <= 0 else round(available_mib / total_mib * 100.0, 3),
        "cached_mib": _kib_mib(meminfo.get("Cached", 0)),
        "sreclaimable_mib": _kib_mib(meminfo.get("SReclaimable", 0)),
        "commit_percent": 0.0 if commit_limit <= 0 else round(committed / commit_limit * 100.0, 3),
        "swap_total_mib": swap_total_mib,
        "swap_used_mib": round(swap_used_mib, 3),
        "swap_free_mib": swap_free_mib,
        "zram_disk_mib": zram["disk_mib"],
        "zram_data_mib": zram["data_mib"],
        "zram_compressed_mib": zram["compressed_mib"],
        "zram_resident_mib": zram["resident_mib"],
        "zram_allocator_metadata_overhead_mib": zram["allocator_metadata_overhead_mib"],
        "zram_physical_savings_mib": zram["physical_savings_mib"],
        "zram_incompressible_mib": zram["incompressible_mib"],
        "zram_backing_mib": zram["backing_mib"],
        "zram_backing_read_mib": zram["backing_read_mib"],
        "zram_backing_write_mib": zram["backing_write_mib"],
        "zram_logical_to_resident_ratio": zram["logical_to_resident_ratio"],
        "zram_allocator_efficiency_ratio": zram["allocator_efficiency_ratio"],
        "psi_some_avg10": _number(some.get("avg10")),
        "psi_full_avg10": _number(full.get("avg10")),
        "psi_some_total_usec": int(_number(some.get("total"))),
        "psi_full_total_usec": int(_number(full.get("total"))),
        "pgmajfault": int(_number(vmstat.get("pgmajfault"))),
        "pswpin": int(_number(vmstat.get("pswpin"))),
        "pswpout": int(_number(vmstat.get("pswpout"))),
        "oom_kill": int(_number(vmstat.get("oom_kill"))),
        "cgroup_memory_mib": cgroup["memory_mib"],
        "cgroup_swap_mib": cgroup["swap_mib"],
        "cgroup_memory_events": cgroup["events"],
        "reservation_count": int(_number(reservation_summary.get("active_count"))),
        "reservation_outstanding_mib": round(max(0.0, _number(reservation_summary.get("outstanding_mib"))), 3),
        "queued_demand_mib": round(max(0.0, _number(queued_demand_mib)), 3),
        "missing_inputs": missing,
        "policy": {"direct_proc_sysfs_sample": True, "no_process_scan": True, "no_mutation": True},
    }


def open_psi_trigger(
    path: Path,
    *,
    kind: str,
    threshold_usec: int,
    window_usec: int,
    open_port: Callable[[str, int], int] = os.open,
    write_port: Callable[[int, bytes], int] = os.write,
    close_port: Callable[[int], None] = os.close,
) -> dict[str, Any]:
    if kind not in {"some", "full"}:
        return {"ok": False, "status": "invalid_kind", "error": "PSI kind must be some or full"}
    if window_usec <= 0 or window_usec % 2_000_000 != 0:
        return {
            "ok": False,
            "status": "invalid_unprivileged_window",
            "error": "unprivileged PSI windows must be a positive multiple of 2000000 usec",
        }
    if threshold_usec <= 0 or threshold_usec > window_usec:
        return {"ok": False, "status": "invalid_threshold", "error": "PSI threshold must be positive and not exceed the window"}
    fd: int | None = None
    try:
        fd = open_port(str(path), os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        payload = f"{kind} {int(threshold_usec)} {int(window_usec)}".encode("ascii") + b"\0"
        written = write_port(fd, payload)
        if written != len(payload):
            raise OSError(f"short PSI trigger write: {written}/{len(payload)}")
    except OSError as exc:
        if fd is not None:
            try:
                close_port(fd)
            except OSError:
                pass
        return {"ok": False, "status": "trigger_registration_failed", "error": str(exc), "path": str(path)}
    return {
        "ok": True,
        "status": "trigger_registered",
        "fd": fd,
        "path": str(path),
        "kind": kind,
        "threshold_usec": int(threshold_usec),
        "window_usec": int(window_usec),
    }


def parse_systemd_monitor_line(line: str) -> dict[str, Any] | None:
    try:
        document = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, Mapping) or document.get("type") != "signal":
        return None
    if document.get("interface") != "org.freedesktop.systemd1.Manager":
        return None
    member = str(document.get("member") or "")
    if member not in {"UnitNew", "UnitRemoved", "JobNew", "JobRemoved"}:
        return None
    payload = document.get("payload") if isinstance(document.get("payload"), Mapping) else {}
    data = payload.get("data") if isinstance(payload.get("data"), list) else []
    if member in {"UnitNew", "UnitRemoved"}:
        unit = str(data[0]) if data else ""
        result = None
    else:
        unit = str(data[2]) if len(data) > 2 else ""
        result = str(data[3]) if member == "JobRemoved" and len(data) > 3 else None
    if not unit:
        return None
    return {
        "source": "systemd",
        "kind": {"UnitNew": "unit_new", "UnitRemoved": "unit_removed", "JobNew": "job_new", "JobRemoved": "job_removed"}[member],
        "unit": unit,
        "result": result,
        "realtime_usec": int(_number(document.get("timestamp-realtime"))),
    }


def systemd_monitor_argv(units: list[str] | set[str]) -> list[str]:
    argv = ["dbus-monitor", "--session"]
    for unit in sorted({str(item).strip() for item in units if str(item).strip()}):
        if not re.fullmatch(r"[A-Za-z0-9_.:@-]+", unit):
            raise ValueError(f"invalid exact systemd unit identity: {unit}")
        common = "type='signal',sender='org.freedesktop.systemd1',interface='org.freedesktop.systemd1.Manager'"
        argv.append(f"{common},arg0='{unit}'")
        argv.append(f"{common},arg2='{unit}'")
    return argv


def start_systemd_monitor(units: list[str] | set[str]) -> subprocess.Popen[str]:
    if not units:
        raise ValueError("at least one exact systemd unit is required")
    return subprocess.Popen(
        systemd_monitor_argv(units),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=1,
    )


class DbusSystemdMonitorParser:
    _header = re.compile(
        r"^signal time=(?P<epoch>[0-9.]+).*interface=org\.freedesktop\.systemd1\.Manager; member=(?P<member>[A-Za-z]+)$"
    )
    _kinds = {
        "UnitNew": "unit_new",
        "UnitRemoved": "unit_removed",
        "JobNew": "job_new",
        "JobRemoved": "job_removed",
    }

    def __init__(self) -> None:
        self.buffer = ""
        self.member = ""
        self.epoch = 0.0
        self.strings: list[str] = []
        self.emitted = False

    def feed(self, text: str) -> list[dict[str, Any]]:
        self.buffer += text
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()
        events: list[dict[str, Any]] = []
        for line in lines:
            header = self._header.match(line)
            if header:
                self.member = header.group("member")
                self.epoch = _number(header.group("epoch"))
                self.strings = []
                self.emitted = False
                continue
            stripped = line.strip()
            if not stripped.startswith("string ") or self.member not in self._kinds:
                continue
            quoted = stripped.removeprefix("string ").strip()
            try:
                value = json.loads(quoted)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, str):
                continue
            self.strings.append(value)
            if self.member in {"UnitNew", "UnitRemoved", "JobNew"} and not self.emitted:
                events.append({
                    "source": "systemd",
                    "kind": self._kinds[self.member],
                    "unit": value,
                    "result": None,
                    "epoch": self.epoch,
                })
                self.emitted = True
            elif self.member == "JobRemoved" and len(self.strings) >= 2 and not self.emitted:
                events.append({
                    "source": "systemd",
                    "kind": "job_removed",
                    "unit": self.strings[0],
                    "result": self.strings[1],
                    "epoch": self.epoch,
                })
                self.emitted = True
        return events


class InotifyWatcher:
    def __init__(self) -> None:
        libc = ctypes.CDLL(None, use_errno=True)
        init = libc.inotify_init1
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        add_watch = libc.inotify_add_watch
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        fd = init(os.O_NONBLOCK | os.O_CLOEXEC)
        if fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        self.fd = fd
        self._add_watch = add_watch
        self._watches: dict[int, dict[str, str]] = {}

    def add(self, path: Path, *, source: str, mask: int = DEFAULT_INOTIFY_MASK) -> int:
        encoded = os.fsencode(path)
        wd = self._add_watch(self.fd, encoded, ctypes.c_uint32(mask))
        if wd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(path))
        self._watches[int(wd)] = {"path": str(path), "source": str(source)}
        return int(wd)

    def read_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while True:
            try:
                payload = os.read(self.fd, 64 * 1024)
            except BlockingIOError:
                break
            if not payload:
                break
            offset = 0
            header_size = struct.calcsize("iIII")
            while offset + header_size <= len(payload):
                wd, mask, cookie, name_length = struct.unpack_from("iIII", payload, offset)
                offset += header_size
                name_bytes = payload[offset:offset + name_length]
                offset += name_length
                watch = self._watches.get(wd, {"path": "", "source": "unknown"})
                name = name_bytes.rstrip(b"\0").decode("utf-8", errors="replace")
                events.append({
                    "source": watch["source"],
                    "path": watch["path"],
                    "name": name,
                    "mask": int(mask),
                    "cookie": int(cookie),
                })
                if mask & IN_IGNORED:
                    self._watches.pop(wd, None)
        return events

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def open_event_socket(path: Path) -> socket.socket:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        metadata = None
    if metadata is not None:
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise OSError(f"refusing to replace non-owned event socket path: {path}")
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        server.setblocking(False)
        server.bind(str(path))
        path.chmod(0o600)
    except Exception:
        server.close()
        path.unlink(missing_ok=True)
        raise
    return server


def read_event_socket(server: socket.socket, *, expected_uid: int, maximum_bytes: int = 16_384) -> dict[str, Any]:
    credential_size = struct.calcsize("3i")
    try:
        payload, ancillary, flags, _address = server.recvmsg(maximum_bytes, socket.CMSG_SPACE(credential_size))
    except BlockingIOError:
        return {"ok": False, "status": "no_event"}
    if flags & socket.MSG_TRUNC:
        return {"ok": False, "status": "event_too_large"}
    credentials: tuple[int, int, int] | None = None
    for level, kind, data in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) >= credential_size:
            credentials = struct.unpack("3i", data[:credential_size])
            break
    if credentials is None:
        return {"ok": False, "status": "missing_peer_credentials"}
    pid, uid, gid = credentials
    if uid != int(expected_uid):
        return {"ok": False, "status": "peer_uid_mismatch", "uid": uid}
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "status": "invalid_event_json", "uid": uid, "pid": pid}
    if not isinstance(document, Mapping) or document.get("schema") != "abyss_machine_memory_controller_event_v1":
        return {"ok": False, "status": "invalid_event_schema", "uid": uid, "pid": pid}
    kind_value = str(document.get("kind") or "").strip()
    identifier = str(document.get("event_id") or "").strip()
    if not kind_value or not identifier:
        return {"ok": False, "status": "event_identity_required", "uid": uid, "pid": pid}
    details = document.get("details") if isinstance(document.get("details"), Mapping) else {}
    return {
        "ok": True,
        "status": "event_received",
        "uid": uid,
        "gid": gid,
        "pid": pid,
        "event": {"kind": kind_value, "event_id": identifier, "details": dict(details)},
    }


def send_event_socket(path: Path, document: Mapping[str, Any]) -> None:
    payload = json.dumps(dict(document), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > 16_384:
        raise ValueError("event exceeds 16384-byte controller socket limit")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.settimeout(1.0)
        client.sendto(payload, str(path))
    finally:
        client.close()


def atomic_write_json(path: Path, document: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    return (dict(document), None) if isinstance(document, Mapping) else (None, "document is not an object")


def local_http_json(route: Mapping[str, Any], *, monotonic_port: MonotonicPort = time.monotonic) -> dict[str, Any]:
    url = str(route.get("url") or "")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError:
        return {"ok": False, "status": "route_rejected_by_transport"}
    try:
        port = parsed.port
    except ValueError:
        port = None
    method = str(route.get("method") or "").upper()
    if (
        parsed.scheme != "http"
        or hostname not in {"127.0.0.1", "::1"}
        or port is None
        or method not in {"GET", "POST"}
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        return {"ok": False, "status": "route_rejected_by_transport"}
    timeout = max(0.05, min(5.0, float(route.get("timeout_ms") or 2_000) / 1_000.0))
    maximum_bytes = max(256, min(262_144, int(route.get("maximum_response_bytes") or 65_536)))
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    started = float(monotonic_port())
    connection = http.client.HTTPConnection(hostname, port, timeout=timeout)
    try:
        body = b"" if method == "POST" else None
        connection.request(method, target, body=body, headers={"Accept": "application/json", "Content-Length": "0"})
        response = connection.getresponse()
        payload = response.read(maximum_bytes + 1)
        status_code = int(response.status)
        content_type = str(response.getheader("Content-Type") or "")
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        return {
            "ok": False,
            "status": "transport_error",
            "error": str(exc),
            "elapsed_ms": round(max(0.0, float(monotonic_port()) - started) * 1_000.0, 3),
        }
    finally:
        connection.close()
    elapsed_ms = round(max(0.0, float(monotonic_port()) - started) * 1_000.0, 3)
    if len(payload) > maximum_bytes:
        return {"ok": False, "status": "response_too_large", "http_status": status_code, "elapsed_ms": elapsed_ms}
    if not 200 <= status_code < 300:
        return {"ok": False, "status": "http_error", "http_status": status_code, "elapsed_ms": elapsed_ms}
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "status": "response_not_json",
            "http_status": status_code,
            "content_type": content_type,
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
        }
    if not isinstance(document, Mapping):
        return {
            "ok": False,
            "status": "response_not_object",
            "http_status": status_code,
            "elapsed_ms": elapsed_ms,
        }
    return {
        "ok": True,
        "status": "response_ready",
        "http_status": status_code,
        "content_type": content_type,
        "document": dict(document),
        "elapsed_ms": elapsed_ms,
    }


def append_bounded_window(path: Path, item: Mapping[str, Any], *, limit: int) -> dict[str, Any]:
    current, _error = load_json(path)
    existing = current.get("items") if isinstance(current, Mapping) and isinstance(current.get("items"), list) else []
    resolved_limit = max(1, int(limit))
    items = [*existing, deepcopy_mapping(item)][-resolved_limit:]
    document = {"schema": "abyss_machine_memory_controller_window_v1", "limit": resolved_limit, "items": items}
    atomic_write_json(path, document)
    return document


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(1.0, percentile))
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


class EvidenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=5.0)
        path.chmod(0o600)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA wal_autocheckpoint=100")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epoch REAL NOT NULL,
                document TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS samples_epoch_idx ON samples(epoch);
            CREATE TABLE IF NOT EXISTS decisions (
                sequence INTEGER PRIMARY KEY,
                epoch REAL NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                event_source TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                within_target INTEGER NOT NULL,
                pressure_band TEXT NOT NULL,
                action TEXT NOT NULL,
                execution TEXT NOT NULL,
                document TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS decisions_epoch_idx ON decisions(epoch);
            CREATE TABLE IF NOT EXISTS action_outcomes (
                nonce TEXT PRIMARY KEY,
                epoch REAL NOT NULL,
                workload_id TEXT NOT NULL,
                action TEXT NOT NULL,
                ok INTEGER NOT NULL,
                status TEXT NOT NULL,
                predicted_freed_mib REAL NOT NULL,
                observed_freed_mib REAL NOT NULL,
                rollback_status TEXT NOT NULL,
                document TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS action_outcomes_epoch_idx ON action_outcomes(epoch);
            CREATE TABLE IF NOT EXISTS launch_outcomes (
                event_id TEXT PRIMARY KEY,
                epoch REAL NOT NULL,
                workload_id TEXT NOT NULL,
                ok INTEGER NOT NULL,
                requested_mib REAL NOT NULL,
                observed_peak_mib REAL,
                queue_delay_sec REAL NOT NULL,
                elapsed_sec REAL NOT NULL,
                classification TEXT NOT NULL,
                document TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS launch_outcomes_epoch_idx ON launch_outcomes(epoch);
            CREATE TABLE IF NOT EXISTS forecast_outcomes (
                decision_sequence INTEGER NOT NULL,
                horizon_sec INTEGER NOT NULL,
                target_epoch REAL NOT NULL,
                evaluated_epoch REAL NOT NULL,
                predicted_available_mib REAL,
                actual_available_mib REAL,
                prediction_error_mib REAL,
                classification TEXT NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY(decision_sequence, horizon_sec)
            );
            CREATE INDEX IF NOT EXISTS forecast_outcomes_epoch_idx ON forecast_outcomes(evaluated_epoch);
            """
        )
        self.connection.execute("PRAGMA user_version=4")
        self.connection.commit()

    def append_sample(self, sample: Mapping[str, Any], *, limit: int, retention_hours: float) -> None:
        epoch = float(sample.get("epoch") or time.time())
        document = json.dumps(dict(sample), sort_keys=True, separators=(",", ":"), allow_nan=False)
        resolved_limit = max(3, int(limit))
        cutoff = epoch - max(6.0, float(retention_hours)) * 3600.0
        with self.connection:
            self.connection.execute("INSERT INTO samples(epoch, document) VALUES (?, ?)", (epoch, document))
            self.connection.execute("DELETE FROM samples WHERE epoch < ?", (cutoff,))
            self.connection.execute(
                "DELETE FROM samples WHERE id NOT IN (SELECT id FROM samples ORDER BY id DESC LIMIT ?)",
                (resolved_limit,),
            )

    def append_decision(self, packet: Mapping[str, Any], *, limit: int, retention_hours: float) -> bool:
        event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
        timing = packet.get("timing") if isinstance(packet.get("timing"), Mapping) else {}
        forecast = packet.get("forecast") if isinstance(packet.get("forecast"), Mapping) else {}
        decision = packet.get("decision") if isinstance(packet.get("decision"), Mapping) else {}
        selected = decision.get("selected") if isinstance(decision.get("selected"), Mapping) else {}
        sequence = int(packet.get("sequence") or 0)
        epoch = float(packet.get("epoch") or time.time())
        event_id = str(event.get("event_id") or "")
        if sequence <= 0 or not event_id:
            raise ValueError("decision sequence and event_id are required")
        compact = {key: value for key, value in packet.items() if key != "sample"}
        if isinstance(compact.get("queue"), Mapping):
            compact["queue"] = {key: compact["queue"].get(key) for key in ("schema", "ok", "summary", "errors")}
        document = json.dumps(compact, sort_keys=True, separators=(",", ":"), allow_nan=False)
        resolved_limit = max(3, int(limit))
        cutoff = epoch - max(6.0, float(retention_hours)) * 3600.0
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO decisions(
                    sequence, epoch, event_id, event_source, event_kind, latency_ms,
                    within_target, pressure_band, action, execution, document
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence,
                    epoch,
                    event_id,
                    str(event.get("source") or "unknown"),
                    str(event.get("kind") or "unknown"),
                    float(timing.get("event_to_decision_ms") or 0.0),
                    1 if timing.get("within_target") is True else 0,
                    str(forecast.get("pressure_band") or "unknown"),
                    str(selected.get("action") or "observe"),
                    str(selected.get("execution") or "observe_only"),
                    document,
                ),
            )
            self.connection.execute("DELETE FROM decisions WHERE epoch < ?", (cutoff,))
            self.connection.execute(
                "DELETE FROM decisions WHERE sequence NOT IN (SELECT sequence FROM decisions ORDER BY sequence DESC LIMIT ?)",
                (resolved_limit,),
            )
        return cursor.rowcount == 1

    def reconcile_forecasts(
        self,
        actual_packet: Mapping[str, Any],
        *,
        limit: int,
        retention_hours: float,
        maximum_new: int = 128,
        maximum_lookback_sec: float = 300.0,
    ) -> list[dict[str, Any]]:
        actual_epoch = float(actual_packet.get("epoch") or time.time())
        actual_forecast = actual_packet.get("forecast") if isinstance(actual_packet.get("forecast"), Mapping) else {}
        actual_current = actual_forecast.get("current") if isinstance(actual_forecast.get("current"), Mapping) else {}
        actual_sample = actual_packet.get("sample") if isinstance(actual_packet.get("sample"), Mapping) else {}

        def optional_number(value: Any) -> float | None:
            if isinstance(value, bool) or value is None:
                return None
            try:
                result = float(value)
            except (TypeError, ValueError):
                return None
            return result if math.isfinite(result) else None

        pressure_rank = {"unknown": -1, "healthy": 0, "watch": 1, "warm": 2, "hot": 3, "critical": 4}
        actual_available = optional_number(actual_current.get("mem_available_mib"))
        if actual_available is None:
            actual_available = optional_number(actual_sample.get("mem_available_mib"))
        actual_swap_used = optional_number(actual_current.get("swap_used_mib"))
        if actual_swap_used is None:
            actual_swap_used = optional_number(actual_sample.get("swap_used_mib"))
        actual_zram = actual_forecast.get("zram") if isinstance(actual_forecast.get("zram"), Mapping) else {}
        actual_zram_resident = optional_number(actual_zram.get("resident_mib"))
        if actual_zram_resident is None:
            actual_zram_resident = optional_number(actual_sample.get("zram_resident_mib"))
        actual_band = str(actual_current.get("pressure_band") or "unknown")
        actual_pressure = (
            pressure_rank.get(actual_band, -1) >= pressure_rank["warm"]
            or actual_forecast.get("active_memory_relief_needed") is True
        )
        resolved_limit = max(3, int(limit))
        lookback_sec = max(60.0, min(3_600.0, float(maximum_lookback_sec)))
        scan_limit = min(resolved_limit, 1_024)
        rows = self.connection.execute(
            "SELECT sequence, epoch, document FROM decisions WHERE epoch BETWEEN ? AND ? ORDER BY epoch DESC LIMIT ?",
            (actual_epoch - lookback_sec, actual_epoch, scan_limit),
        ).fetchall()
        existing = {
            (int(sequence), int(horizon))
            for sequence, horizon in self.connection.execute(
                "SELECT decision_sequence, horizon_sec FROM forecast_outcomes WHERE evaluated_epoch >= ?",
                (actual_epoch - lookback_sec,),
            )
        }
        candidates: list[dict[str, Any]] = []
        for raw_sequence, decision_epoch, raw_document in rows:
            try:
                prior = json.loads(raw_document)
            except json.JSONDecodeError:
                continue
            if not isinstance(prior, Mapping):
                continue
            prior_forecast = prior.get("forecast") if isinstance(prior.get("forecast"), Mapping) else {}
            projections = prior_forecast.get("projections") if isinstance(prior_forecast.get("projections"), Mapping) else {}
            for raw_horizon, raw_projection in projections.items():
                if not isinstance(raw_projection, Mapping):
                    continue
                try:
                    horizon = int(raw_horizon)
                except (TypeError, ValueError):
                    continue
                if horizon <= 0 or (int(raw_sequence), horizon) in existing:
                    continue
                target_epoch = float(decision_epoch) + horizon
                lateness = actual_epoch - target_epoch
                tolerance = max(15.0, min(60.0, horizon * 0.25))
                if lateness < 0.0 or lateness > tolerance:
                    continue
                predicted_available = optional_number(raw_projection.get("mem_available_mib"))
                predicted_band = str(raw_projection.get("pressure_band") or "unknown")
                explicit_pressure = raw_projection.get("pressure_expected")
                predicted_pressure = (
                    explicit_pressure
                    if isinstance(explicit_pressure, bool)
                    else pressure_rank.get(predicted_band, -1) >= pressure_rank["warm"]
                )
                prior_current = prior_forecast.get("current") if isinstance(prior_forecast.get("current"), Mapping) else {}
                prior_slopes = prior_forecast.get("slopes") if isinstance(prior_forecast.get("slopes"), Mapping) else {}
                prior_zram = prior_forecast.get("zram") if isinstance(prior_forecast.get("zram"), Mapping) else {}
                prior_swap_used = optional_number(prior_current.get("swap_used_mib"))
                swap_slope = optional_number(prior_slopes.get("swap_used_mib_per_sec"))
                predicted_swap_used = None
                if prior_swap_used is not None and swap_slope is not None:
                    predicted_swap_used = max(0.0, prior_swap_used + swap_slope * horizon)
                prior_zram_resident = optional_number(prior_zram.get("resident_mib"))
                zram_slope = optional_number(prior_slopes.get("zram_resident_mib_per_sec"))
                predicted_zram_resident = None
                if prior_zram_resident is not None and zram_slope is not None:
                    predicted_zram_resident = max(0.0, prior_zram_resident + zram_slope * horizon)
                if str(prior_forecast.get("confidence") or "none") != "high":
                    classification = "prediction_confidence_insufficient"
                elif actual_available is None or actual_band == "unknown":
                    classification = "actual_evidence_missing"
                elif predicted_pressure and actual_pressure:
                    classification = "true_positive"
                elif predicted_pressure:
                    classification = "false_positive"
                elif actual_pressure:
                    classification = "false_negative"
                else:
                    classification = "true_negative"
                error_mib = None
                if predicted_available is not None and actual_available is not None:
                    error_mib = round(actual_available - predicted_available, 3)
                swap_error_mib = None
                if predicted_swap_used is not None and actual_swap_used is not None:
                    swap_error_mib = round(actual_swap_used - predicted_swap_used, 3)
                zram_error_mib = None
                if predicted_zram_resident is not None and actual_zram_resident is not None:
                    zram_error_mib = round(actual_zram_resident - predicted_zram_resident, 3)
                outcome = {
                    "schema": "abyss_machine_memory_controller_forecast_outcome_v1",
                    "decision_sequence": int(raw_sequence),
                    "horizon_sec": horizon,
                    "target_epoch": round(target_epoch, 6),
                    "evaluated_epoch": actual_epoch,
                    "evaluation_lateness_sec": round(lateness, 3),
                    "classification": classification,
                    "predicted": {
                        "confidence": prior_forecast.get("confidence"),
                        "mem_available_mib": predicted_available,
                        "pressure_band": predicted_band,
                        "pressure_expected": predicted_pressure,
                        "pressure_reasons": (
                            list(raw_projection.get("pressure_reasons"))
                            if isinstance(raw_projection.get("pressure_reasons"), list)
                            else []
                        ),
                        "swap_used_mib": None if predicted_swap_used is None else round(predicted_swap_used, 3),
                        "zram_resident_mib": None if predicted_zram_resident is None else round(predicted_zram_resident, 3),
                    },
                    "actual": {
                        "mem_available_mib": actual_available,
                        "pressure_band": actual_band,
                        "active_memory_relief_needed": actual_forecast.get("active_memory_relief_needed") is True,
                        "pressure_observed": actual_pressure,
                        "psi_some_percent": (actual_forecast.get("stall_rates") or {}).get("some_percent") if isinstance(actual_forecast.get("stall_rates"), Mapping) else None,
                        "psi_full_percent": (actual_forecast.get("stall_rates") or {}).get("full_percent") if isinstance(actual_forecast.get("stall_rates"), Mapping) else None,
                        "major_faults_per_sec": (actual_forecast.get("stall_rates") or {}).get("major_faults_per_sec") if isinstance(actual_forecast.get("stall_rates"), Mapping) else None,
                        "oom_kills_per_sec": (actual_forecast.get("stall_rates") or {}).get("oom_kills_per_sec") if isinstance(actual_forecast.get("stall_rates"), Mapping) else None,
                        "swap_used_mib": actual_swap_used,
                        "zram_resident_mib": actual_zram_resident,
                        "zram_logical_data_mib": optional_number(actual_zram.get("logical_data_mib")),
                        "zram_physical_savings_mib": optional_number(actual_zram.get("physical_savings_mib")),
                    },
                    "prediction_error_mib": error_mib,
                    "swap_prediction_error_mib": swap_error_mib,
                    "zram_resident_prediction_error_mib": zram_error_mib,
                    "policy": {
                        "outcome_is_calibration_evidence_only": True,
                        "safety_invariants_not_modified": True,
                        "owner_contracts_not_modified": True,
                    },
                }
                candidates.append(outcome)
                existing.add((int(raw_sequence), horizon))
                if len(candidates) >= max(1, int(maximum_new)):
                    break
            if len(candidates) >= max(1, int(maximum_new)):
                break

        if not candidates:
            return []
        cutoff = actual_epoch - max(6.0, float(retention_hours)) * 3600.0
        inserted: list[dict[str, Any]] = []
        with self.connection:
            for outcome in candidates:
                document = json.dumps(outcome, sort_keys=True, separators=(",", ":"), allow_nan=False)
                cursor = self.connection.execute(
                    """
                    INSERT OR IGNORE INTO forecast_outcomes(
                        decision_sequence, horizon_sec, target_epoch, evaluated_epoch,
                        predicted_available_mib, actual_available_mib, prediction_error_mib,
                        classification, document
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        outcome["decision_sequence"],
                        outcome["horizon_sec"],
                        outcome["target_epoch"],
                        outcome["evaluated_epoch"],
                        outcome["predicted"]["mem_available_mib"],
                        outcome["actual"]["mem_available_mib"],
                        outcome["prediction_error_mib"],
                        outcome["classification"],
                        document,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted.append(outcome)
            self.connection.execute("DELETE FROM forecast_outcomes WHERE evaluated_epoch < ?", (cutoff,))
            row_count = int(self.connection.execute("SELECT COUNT(*) FROM forecast_outcomes").fetchone()[0])
            if row_count > resolved_limit:
                self.connection.execute(
                    "DELETE FROM forecast_outcomes WHERE rowid IN (SELECT rowid FROM forecast_outcomes ORDER BY evaluated_epoch ASC LIMIT ?)",
                    (row_count - resolved_limit,),
                )
        return inserted

    def load_samples(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT document FROM samples ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for (document,) in reversed(rows):
            try:
                item = json.loads(document)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                result.append(dict(item))
        return result

    def has_event(self, event_id: str) -> bool:
        return self.connection.execute("SELECT 1 FROM decisions WHERE event_id = ?", (str(event_id),)).fetchone() is not None

    def latest_sequence(self) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(sequence), 0) FROM decisions").fetchone()
        return int(row[0]) if row else 0

    def recent_event_ids(self, limit: int) -> list[str]:
        rows = self.connection.execute(
            "SELECT event_id FROM decisions ORDER BY sequence DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        return [str(row[0]) for row in reversed(rows)]

    def has_action_nonce(self, nonce: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM action_outcomes WHERE nonce = ?",
            (str(nonce),),
        ).fetchone() is not None

    def action_outcome(self, nonce: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT document FROM action_outcomes WHERE nonce = ?",
            (str(nonce),),
        ).fetchone()
        if row is None:
            return None
        try:
            document = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return dict(document) if isinstance(document, Mapping) else None

    def append_action_outcome(self, outcome: Mapping[str, Any], *, limit: int, retention_hours: float) -> bool:
        nonce = str(outcome.get("nonce") or "")
        workload_id = str(outcome.get("workload_id") or "")
        action = str(outcome.get("action") or "")
        if not nonce or not workload_id or not action:
            raise ValueError("action outcome nonce, workload_id, and action are required")
        epoch = float(outcome.get("epoch") or time.time())
        rollback = outcome.get("rollback") if isinstance(outcome.get("rollback"), Mapping) else {}
        document = json.dumps(dict(outcome), sort_keys=True, separators=(",", ":"), allow_nan=False)
        cutoff = epoch - max(6.0, float(retention_hours)) * 3600.0
        resolved_limit = max(3, int(limit))
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO action_outcomes(
                    nonce, epoch, workload_id, action, ok, status,
                    predicted_freed_mib, observed_freed_mib, rollback_status, document
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(nonce) DO UPDATE SET
                    epoch = excluded.epoch,
                    workload_id = excluded.workload_id,
                    action = excluded.action,
                    ok = excluded.ok,
                    status = excluded.status,
                    predicted_freed_mib = excluded.predicted_freed_mib,
                    observed_freed_mib = excluded.observed_freed_mib,
                    rollback_status = excluded.rollback_status,
                    document = excluded.document
                """,
                (
                    nonce,
                    epoch,
                    workload_id,
                    action,
                    1 if outcome.get("ok") is True else 0,
                    str(outcome.get("status") or "unknown"),
                    float(outcome.get("predicted_freed_mib") or 0.0),
                    float(outcome.get("observed_freed_mib") or 0.0),
                    str(rollback.get("status") or "not_needed"),
                    document,
                ),
            )
            self.connection.execute("DELETE FROM action_outcomes WHERE epoch < ?", (cutoff,))
            self.connection.execute(
                "DELETE FROM action_outcomes WHERE nonce NOT IN (SELECT nonce FROM action_outcomes ORDER BY epoch DESC LIMIT ?)",
                (resolved_limit,),
            )
        return cursor.rowcount == 1

    def action_outcomes(self, *, limit: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT document FROM action_outcomes ORDER BY epoch DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        outcomes: list[dict[str, Any]] = []
        for (document,) in rows:
            try:
                item = json.loads(document)
            except json.JSONDecodeError:
                continue
            if isinstance(item, Mapping):
                outcomes.append(dict(item))
        return outcomes

    def append_launch_outcome(self, outcome: Mapping[str, Any], *, limit: int, retention_hours: float) -> bool:
        event_id = str(outcome.get("event_id") or "")
        workload_id = str(outcome.get("workload_id") or "")
        if not event_id or not workload_id:
            raise ValueError("launch outcome event_id and workload_id are required")
        epoch = float(outcome.get("epoch") or time.time())
        document = json.dumps(dict(outcome), sort_keys=True, separators=(",", ":"), allow_nan=False)
        cutoff = epoch - max(6.0, float(retention_hours)) * 3600.0
        resolved_limit = max(3, int(limit))
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO launch_outcomes(
                    event_id, epoch, workload_id, ok, requested_mib, observed_peak_mib,
                    queue_delay_sec, elapsed_sec, classification, document
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    epoch,
                    workload_id,
                    1 if outcome.get("ok") is True else 0,
                    float(outcome.get("requested_mib") or 0.0),
                    outcome.get("observed_peak_mib"),
                    float(outcome.get("queue_delay_sec") or 0.0),
                    float(outcome.get("elapsed_sec") or 0.0),
                    str(outcome.get("classification") or "unknown"),
                    document,
                ),
            )
            self.connection.execute("DELETE FROM launch_outcomes WHERE epoch < ?", (cutoff,))
            self.connection.execute(
                "DELETE FROM launch_outcomes WHERE event_id NOT IN (SELECT event_id FROM launch_outcomes ORDER BY epoch DESC LIMIT ?)",
                (resolved_limit,),
            )
        return cursor.rowcount == 1

    def summary(self) -> dict[str, Any]:
        sample_row = self.connection.execute(
            "SELECT COUNT(*), MIN(epoch), MAX(epoch) FROM samples"
        ).fetchone() or (0, None, None)
        decision_row = self.connection.execute(
            "SELECT COUNT(*), MIN(epoch), MAX(epoch), COALESCE(SUM(within_target), 0) FROM decisions"
        ).fetchone() or (0, None, None, 0)
        latencies = [float(row[0]) for row in self.connection.execute("SELECT latency_ms FROM decisions")]
        decision_count = int(decision_row[0])
        action_counts = {
            str(action): int(count)
            for action, count in self.connection.execute("SELECT action, COUNT(*) FROM decisions GROUP BY action")
        }
        outcome_row = self.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(ok), 0), COALESCE(SUM(observed_freed_mib), 0) FROM action_outcomes"
        ).fetchone() or (0, 0, 0.0)
        outcome_counts = {
            str(action): int(count)
            for action, count in self.connection.execute("SELECT action, COUNT(*) FROM action_outcomes GROUP BY action")
        }
        launch_row = self.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(ok), 0) FROM launch_outcomes"
        ).fetchone() or (0, 0)
        queue_delays = [float(row[0]) for row in self.connection.execute("SELECT queue_delay_sec FROM launch_outcomes")]
        envelope_counts = {
            str(classification): int(count)
            for classification, count in self.connection.execute(
                "SELECT classification, COUNT(*) FROM launch_outcomes GROUP BY classification"
            )
        }
        forecast_row = self.connection.execute(
            "SELECT COUNT(*), AVG(ABS(prediction_error_mib)) FROM forecast_outcomes"
        ).fetchone() or (0, None)
        forecast_classifications = {
            str(classification): int(count)
            for classification, count in self.connection.execute(
                "SELECT classification, COUNT(*) FROM forecast_outcomes GROUP BY classification"
            )
        }
        forecast_horizons = {
            str(horizon): int(count)
            for horizon, count in self.connection.execute(
                "SELECT horizon_sec, COUNT(*) FROM forecast_outcomes GROUP BY horizon_sec"
            )
        }
        first_epoch = float(decision_row[1]) if decision_row[1] is not None else None
        last_epoch = float(decision_row[2]) if decision_row[2] is not None else None
        return {
            "schema": "abyss_machine_memory_controller_evidence_summary_v1",
            "database": str(self.path),
            "samples": {
                "count": int(sample_row[0]),
                "first_epoch": sample_row[1],
                "last_epoch": sample_row[2],
            },
            "decisions": {
                "count": decision_count,
                "first_epoch": first_epoch,
                "last_epoch": last_epoch,
                "span_hours": 0.0 if first_epoch is None or last_epoch is None else round(max(0.0, last_epoch - first_epoch) / 3600.0, 6),
                "within_target_percent": 0.0 if not decision_count else round(float(decision_row[3]) / decision_count * 100.0, 3),
                "latency_ms": {
                    "p50": _percentile(latencies, 0.50),
                    "p95": _percentile(latencies, 0.95),
                    "p99": _percentile(latencies, 0.99),
                    "max": None if not latencies else round(max(latencies), 3),
                },
                "actions": action_counts,
            },
            "action_outcomes": {
                "count": int(outcome_row[0]),
                "successful_count": int(outcome_row[1]),
                "observed_freed_mib_total": round(float(outcome_row[2]), 3),
                "actions": outcome_counts,
            },
            "launch_outcomes": {
                "count": int(launch_row[0]),
                "successful_count": int(launch_row[1]),
                "queue_delay_sec": {
                    "p50": _percentile(queue_delays, 0.50),
                    "p95": _percentile(queue_delays, 0.95),
                    "p99": _percentile(queue_delays, 0.99),
                    "max": None if not queue_delays else round(max(queue_delays), 3),
                },
                "envelope_classifications": envelope_counts,
            },
            "forecast_outcomes": {
                "count": int(forecast_row[0]),
                "mean_absolute_error_mib": None if forecast_row[1] is None else round(float(forecast_row[1]), 3),
                "classifications": forecast_classifications,
                "horizons_sec": forecast_horizons,
                "policy": {
                    "calibration_evidence_only": True,
                    "safety_and_owner_contracts_not_self_modified": True,
                },
            },
        }

    def close(self) -> None:
        if self.connection is None:
            return
        try:
            self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            self.connection.close()
            self.connection = None


def deepcopy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), allow_nan=False))


def load_registry(static_path: Path, runtime_root: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    static, static_error = load_json(static_path)
    if static_error:
        errors.append({"path": str(static_path), "error": static_error})
    static_trusted = False
    try:
        metadata = static_path.lstat()
        static_trusted = stat.S_ISREG(metadata.st_mode) and metadata.st_uid == 0 and metadata.st_mode & 0o022 == 0
    except OSError:
        pass
    raw_workloads = list(static.get("workloads", [])) if isinstance(static, Mapping) and isinstance(static.get("workloads"), list) else []
    workloads: list[dict[str, Any]] = []
    for raw in raw_workloads:
        if not isinstance(raw, Mapping):
            errors.append({"path": str(static_path), "error": "static_workload_not_an_object"})
            continue
        workload = deepcopy_mapping(raw)
        workload_metadata = workload.get("metadata") if isinstance(workload.get("metadata"), Mapping) else {}
        workload["registry_status"] = "exact"
        workload["metadata"] = {
            **workload_metadata,
            "registry_source": "static",
            "registry_trusted_for_lifecycle": static_trusted,
        }
        workloads.append(workload)
    rules = list(static.get("rules", [])) if isinstance(static, Mapping) and isinstance(static.get("rules"), list) else []
    runtime_count = 0
    if runtime_root.is_dir():
        for path in sorted(runtime_root.glob("*.json")):
            document, error = load_json(path)
            if error:
                errors.append({"path": str(path), "error": error})
                continue
            runtime = deepcopy_mapping(document)
            runtime_metadata = runtime.get("metadata") if isinstance(runtime.get("metadata"), Mapping) else {}
            runtime["registry_status"] = "runtime"
            runtime["metadata"] = {
                **runtime_metadata,
                "registry_source": "runtime",
                "registry_trusted_for_lifecycle": False,
            }
            workloads.append(runtime)
            runtime_count += 1
    return {
        "schema": "abyss_machine_memory_controller_registry_v1",
        "ok": not errors,
        "workloads": workloads,
        "rules": rules,
        "runtime_count": runtime_count,
        "static_trusted_for_lifecycle": static_trusted,
        "error_count": len(errors),
        "errors": errors,
        "policy": {"unknown_preserved": True, "runtime_contracts_do_not_override_safety": True},
    }


def default_reservations_port(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    root = resource_adapters.reservations_root(environ, uid=os.getuid())
    return resource_adapters.reservation_snapshot(root, cleanup=False)


def default_reservations_root(environ: Mapping[str, str] | None = None) -> Path:
    return resource_adapters.reservations_root(environ, uid=os.getuid())
