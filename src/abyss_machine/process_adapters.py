from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Callable, Sequence

from . import process_contracts


SysconfPort = Callable[[str | int], int]
SleepPort = Callable[[float], None]
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
