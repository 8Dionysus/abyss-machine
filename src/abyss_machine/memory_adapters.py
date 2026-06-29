from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Sequence
import urllib.error
import urllib.request

from . import process_adapters


CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[[Sequence[str], float], dict[str, Any]]
HttpJsonPort = Callable[[str, float, int, str], dict[str, Any]]
HttpStatusPort = Callable[[str, float, int, str], dict[str, Any]]
MonotonicPort = Callable[[], float]
SleepPort = Callable[[float], None]
NowIsoPort = Callable[[], str]
PidPort = Callable[[], int]
ProcessInfoPort = Callable[[int], dict[str, Any] | None]
SystemdPropertiesPort = Callable[[str, list[str], bool, float], dict[str, Any]]
ControlValuePort = Callable[[Any], dict[str, Any]]
KibToMibPort = Callable[[Any], float | None]


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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def nested_get(data: Any, path: Sequence[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_key_value_file(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in _read_text(path).splitlines():
        key, sep, value = line.partition(" ")
        if not sep:
            continue
        try:
            result[key.strip()] = int(value.strip())
        except ValueError:
            pass
    return result


def podman_id_from_target(target: dict[str, Any]) -> str | None:
    haystack = " ".join(
        str(value or "")
        for value in (
            target.get("label"),
            target.get("unit"),
            target.get("cgroup"),
        )
    )
    match = re.search(r"\blibpod-([0-9a-f]{12,64})(?:\.scope|/|\b)", haystack)
    if match:
        return match.group(1)
    match = re.search(r"\b([0-9a-f]{64})\b", haystack)
    if match:
        return match.group(1)
    return None


def podman_snapshot(
    target: dict[str, Any],
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
    container_summary: Callable[[dict[str, Any]], dict[str, Any]] = process_adapters.safe_container_summary,
) -> dict[str, Any]:
    container_id = podman_id_from_target(target)
    if not container_id:
        return {"available": False, "reason": "no_libpod_container_id_detected"}
    data: dict[str, Any] = {
        "available": True,
        "container_id": container_id[:12],
        "source": "podman inspect read-only",
    }
    if not command_exists("podman"):
        data.update({"ok": False, "error": "podman_not_installed"})
        return data
    out = dict(runner(["podman", "inspect", container_id], 8.0))
    data["ok"] = bool(out.get("ok"))
    data["returncode"] = out.get("returncode")
    if not out.get("ok"):
        data["error"] = out.get("stderr") or out.get("stdout") or "podman inspect failed"
        return data
    try:
        raw = json.loads(str(out.get("stdout") or "[]"))
    except json.JSONDecodeError as exc:
        data.update({"ok": False, "error": f"invalid podman inspect JSON: {exc}"})
        return data
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        data["container"] = container_summary(raw[0])
    return data


def target_snapshot(
    candidate: dict[str, Any],
    *,
    cgroup_snapshot: Callable[[str | None], dict[str, Any]],
    process_info: ProcessInfoPort,
    systemd_unit_properties: SystemdPropertiesPort,
    memory_control_value: ControlValuePort,
    kib_to_mib: KibToMibPort,
    proc_root: Path = Path("/proc"),
    podman_snapshot_port: Callable[[dict[str, Any]], dict[str, Any]] = podman_snapshot,
) -> dict[str, Any]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    cgroup = str(target.get("cgroup") or "")
    cgroup_data = cgroup_snapshot(cgroup)
    raw_pids: list[int] = []
    for source in (target.get("pids"), cgroup_data.get("pids")):
        if not isinstance(source, list):
            continue
        for pid in source:
            try:
                value = int(pid)
            except (TypeError, ValueError):
                continue
            if value > 0 and value not in raw_pids:
                raw_pids.append(value)
    alive_pids = [pid for pid in raw_pids if (proc_root / str(pid)).exists()]
    processes: list[dict[str, Any]] = []
    for pid in alive_pids[:8]:
        info = process_info(pid)
        if not info:
            continue
        processes.append(
            {
                "pid": pid,
                "name": info.get("name"),
                "workload_hint": info.get("workload_hint"),
                "capability_role": info.get("capability_role"),
                "rss_mib": kib_to_mib(int(info.get("vmrss_kib") or info.get("rss_kib") or 0)),
                "cmdline_preview": str(info.get("cmdline") or "")[:180],
            }
        )

    unit = str(target.get("unit") or "")
    systemd: dict[str, Any] = {"available": False, "reason": "target_has_no_unit_hint"}
    if unit:
        properties = [
            "Id",
            "ActiveState",
            "SubState",
            "MainPID",
            "ControlGroup",
            "Slice",
            "MemoryCurrent",
            "MemorySwapCurrent",
            "MemoryHigh",
            "MemoryMax",
            "MemorySwapMax",
        ]
        user_scope = cgroup.startswith("/user.slice/")
        shown = systemd_unit_properties(unit, properties, user_scope, 2.0)
        props = shown.get("properties", {}) if isinstance(shown.get("properties"), dict) else {}
        systemd = {
            "available": bool(shown.get("ok")),
            "scope": "user" if user_scope else "system",
            "unit": unit,
            "active_state": props.get("ActiveState"),
            "sub_state": props.get("SubState"),
            "main_pid": props.get("MainPID"),
            "control_group": props.get("ControlGroup"),
            "memory_current": memory_control_value(props.get("MemoryCurrent")),
            "memory_swap_current": memory_control_value(props.get("MemorySwapCurrent")),
            "memory_high": memory_control_value(props.get("MemoryHigh")),
            "memory_max": memory_control_value(props.get("MemoryMax")),
            "memory_swap_max": memory_control_value(props.get("MemorySwapMax")),
            "error": shown.get("error"),
            "returncode": shown.get("returncode"),
        }

    return {
        "target": target,
        "cgroup": cgroup_data,
        "systemd": systemd,
        "podman": podman_snapshot_port(target),
        "pids": {
            "seen": raw_pids[:64],
            "alive": alive_pids[:64],
            "alive_count": len(alive_pids),
            "sampled_processes": processes,
        },
    }


def http_json(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 262144,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "url": url,
                    "status_code": getattr(response, "status", None),
                    "content_type": response.headers.get("content-type"),
                    "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                    "error": f"invalid JSON: {exc}",
                    "truncated": truncated,
                    "text_preview": text[:400],
                }
            return {
                "ok": True,
                "url": url,
                "status_code": getattr(response, "status", None),
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "json": parsed,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }


def http_status(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 65536,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            status_code = getattr(response, "status", None)
            return {
                "ok": bool(status_code is not None and 200 <= int(status_code) < 300),
                "url": url,
                "status_code": status_code,
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "text_preview": text[:400],
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }


def podman_http_endpoint(snapshot: dict[str, Any]) -> dict[str, Any]:
    ports = nested_get(snapshot, ["podman", "container", "ports"])
    if not isinstance(ports, dict):
        return {"available": False, "reason": "podman_ports_unavailable"}
    preferred = ["5405/tcp", "8080/tcp", "8000/tcp", "11434/tcp", "11435/tcp"]
    keys = [key for key in preferred if key in ports] + [key for key in ports if key not in preferred]
    for key in keys:
        bindings = ports.get(key)
        if not isinstance(bindings, list):
            continue
        for item in bindings:
            if not isinstance(item, dict):
                continue
            host_port = str(item.get("host_port") or "").strip()
            if not host_port:
                continue
            host_ip = str(item.get("host_ip") or "127.0.0.1").strip()
            if host_ip in {"", "0.0.0.0", "::", "[::]"}:
                host_ip = "127.0.0.1"
            if ":" in host_ip and not host_ip.startswith("["):
                host_ip = f"[{host_ip}]"
            return {
                "available": True,
                "source": "podman_inspect_ports",
                "container_port": key,
                "host_ip": host_ip,
                "host_port": host_port,
                "base_url": f"http://{host_ip}:{host_port}",
            }
    return {"available": False, "reason": "no_host_port_binding"}


def cgroup_cpu_sample(
    control_group: str | None,
    sample_sec: float = 0.5,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    sleep: SleepPort = time.sleep,
    monotonic: MonotonicPort = time.monotonic,
    cpu_count: Callable[[], int | None] = os.cpu_count,
) -> dict[str, Any]:
    sample_sec = max(0.1, min(float(sample_sec or 0.5), 3.0))
    if not control_group:
        return {"available": False, "reason": "missing_control_group"}
    path = cgroup_root / str(control_group).lstrip("/")
    if not path.exists():
        return {"available": False, "reason": "cgroup_missing", "path": str(path)}
    before = parse_key_value_file(path / "cpu.stat")
    started = monotonic()
    sleep(sample_sec)
    elapsed = max(0.001, monotonic() - started)
    after = parse_key_value_file(path / "cpu.stat")
    usage_before = before.get("usage_usec")
    usage_after = after.get("usage_usec")
    if usage_before is None or usage_after is None:
        return {"available": False, "reason": "cpu_usage_counter_missing", "path": str(path)}
    usage_delta_usec = max(0, int(usage_after) - int(usage_before))
    cpu_cores = usage_delta_usec / (elapsed * 1_000_000.0)
    total_cpus = cpu_count() or 1
    return {
        "available": True,
        "path": str(path),
        "sample_sec": round(elapsed, 3),
        "usage_delta_usec": usage_delta_usec,
        "cpu_cores": round(cpu_cores, 4),
        "cpu_percent_of_one_core": round(cpu_cores * 100.0, 2),
        "cpu_percent_of_system": round((cpu_cores / total_cpus) * 100.0, 2),
        "threshold_cpu_cores_idle_at_or_below": 0.15,
        "idle": cpu_cores <= 0.15,
        "before": {key: before.get(key) for key in ("usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec")},
        "after": {key: after.get(key) for key in ("usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec")},
    }


def llama_http_idle(endpoint: dict[str, Any], *, http_json_port: HttpJsonPort = http_json) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    health = http_json_port(f"{base_url}/health", 1.5, 65536, "GET")
    slots = http_json_port(f"{base_url}/slots", 1.5, 262144, "GET")
    models = http_json_port(f"{base_url}/v1/models", 1.5, 262144, "GET")
    slot_items = slots.get("json") if isinstance(slots.get("json"), list) else []
    processing_slots = []
    decoded_slots = []
    for item in slot_items if isinstance(slot_items, list) else []:
        if not isinstance(item, dict):
            continue
        next_token = item.get("next_token")
        has_next_token = False
        n_remain = None
        n_decoded = None
        if isinstance(next_token, list) and next_token and isinstance(next_token[0], dict):
            has_next_token = bool(next_token[0].get("has_next_token"))
            n_remain = next_token[0].get("n_remain")
            n_decoded = next_token[0].get("n_decoded")
        busy = bool(item.get("is_processing")) or bool(has_next_token)
        stale_remaining_ignored = bool(
            isinstance(n_remain, int)
            and n_remain > 0
            and not bool(item.get("is_processing"))
            and not bool(has_next_token)
        )
        slot_summary = {
            "id": item.get("id"),
            "is_processing": bool(item.get("is_processing")),
            "id_task": item.get("id_task"),
            "n_ctx": item.get("n_ctx"),
            "has_next_token": has_next_token,
            "n_remain": n_remain,
            "n_decoded": n_decoded,
            "stale_n_remain_ignored": stale_remaining_ignored,
            "busy": busy,
        }
        decoded_slots.append(slot_summary)
        if busy:
            processing_slots.append(slot_summary)
    model_ids: list[str] = []
    model_data = models.get("json")
    if isinstance(model_data, dict):
        data_items = model_data.get("data") if isinstance(model_data.get("data"), list) else []
        for item in data_items:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item.get("id")))
    health_payload = health.get("json") if isinstance(health.get("json"), dict) else {}
    health_ok = bool(health.get("ok")) and str(health_payload.get("status") or "").lower() in {"ok", "ready", "healthy"}
    slots_available = bool(slots.get("ok")) and isinstance(slot_items, list)
    slots_idle = slots_available and len(slot_items) > 0 and len(processing_slots) == 0
    return {
        "available": bool(health.get("ok") or slots.get("ok")),
        "kind": "llama_cpp_http",
        "endpoint": endpoint,
        "health": {
            "ok": bool(health.get("ok")),
            "status": health_payload.get("status") if isinstance(health_payload, dict) else None,
            "elapsed_ms": health.get("elapsed_ms"),
            "error": health.get("error"),
        },
        "slots": {
            "ok": bool(slots.get("ok")),
            "count": len(slot_items) if isinstance(slot_items, list) else None,
            "processing_count": len(processing_slots),
            "idle": slots_idle,
            "items": decoded_slots[:16],
            "error": slots.get("error"),
        },
        "models": {
            "ok": bool(models.get("ok")),
            "ids": model_ids[:8],
            "error": models.get("error"),
        },
        "idle": bool(health_ok and slots_idle),
        "confidence": "high" if bool(health.get("ok") and slots.get("ok")) else "low",
    }


def rerank_http_idle(endpoint: dict[str, Any], *, http_json_port: HttpJsonPort = http_json) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    health = http_json_port(f"{base_url}/health", 1.5, 65536, "GET")
    payload = health.get("json") if isinstance(health.get("json"), dict) else {}
    service = str(payload.get("service") or "").lower() if isinstance(payload, dict) else ""
    health_ok = bool(health.get("ok")) and service == "rerank-api" and bool(payload.get("ok"))
    active_requests = _safe_int(payload.get("active_requests"), 0) if isinstance(payload, dict) else 0
    loaded = bool(payload.get("loaded")) if isinstance(payload, dict) else False
    idle = bool(health_ok and active_requests == 0)
    return {
        "available": bool(health.get("ok")),
        "kind": "rerank_api_http",
        "endpoint": endpoint,
        "health": {
            "ok": bool(health.get("ok")),
            "service": payload.get("service") if isinstance(payload, dict) else None,
            "loaded": loaded,
            "active_requests": active_requests,
            "idle_for_sec": payload.get("idle_for_sec") if isinstance(payload, dict) else None,
            "exit_after_idle_unload": payload.get("exit_after_idle_unload") if isinstance(payload, dict) else None,
            "elapsed_ms": health.get("elapsed_ms"),
            "error": health.get("error"),
        },
        "idle": idle,
        "confidence": "high" if health_ok and "active_requests" in payload else "medium" if health_ok else "low",
    }


def ovms_http_idle(
    endpoint: dict[str, Any],
    *,
    http_json_port: HttpJsonPort = http_json,
    http_status_port: HttpStatusPort = http_status,
) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    live = http_status_port(f"{base_url}/v2/health/live", 1.5, 65536, "GET")
    ready = http_status_port(f"{base_url}/v2/health/ready", 1.5, 65536, "GET")
    config = http_json_port(f"{base_url}/v1/config", 1.5, 262144, "GET")
    payload = config.get("json") if isinstance(config.get("json"), dict) else {}
    models: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for model_name, model_payload in payload.items():
            if not isinstance(model_payload, dict):
                continue
            statuses = model_payload.get("model_version_status")
            status_items = statuses if isinstance(statuses, list) else []
            available_versions = []
            for item in status_items:
                if not isinstance(item, dict):
                    continue
                state = str(item.get("state") or "").upper()
                status = item.get("status") if isinstance(item.get("status"), dict) else {}
                ok_status = str(status.get("error_code") or "").upper() in {"", "OK"}
                if state == "AVAILABLE" and ok_status:
                    available_versions.append(str(item.get("version") or ""))
            models.append(
                {
                    "name": str(model_name),
                    "version_count": len(status_items),
                    "available_versions": [version for version in available_versions if version][:8],
                    "available": bool(available_versions),
                }
            )
    health_ok = bool(live.get("ok")) and bool(ready.get("ok"))
    config_ok = bool(config.get("ok")) and bool(models) and all(bool(item.get("available")) for item in models)
    return {
        "available": bool(health_ok or config.get("ok")),
        "kind": "ovms_http",
        "endpoint": endpoint,
        "health": {
            "ok": health_ok,
            "live_ok": bool(live.get("ok")),
            "ready_ok": bool(ready.get("ok")),
            "live_status_code": live.get("status_code"),
            "ready_status_code": ready.get("status_code"),
            "elapsed_ms": max(
                _safe_float(live.get("elapsed_ms"), 0.0) or 0.0,
                _safe_float(ready.get("elapsed_ms"), 0.0) or 0.0,
            ),
            "live_error": live.get("error"),
            "ready_error": ready.get("error"),
        },
        "models": {
            "ok": config_ok,
            "count": len(models),
            "available_count": sum(1 for item in models if item.get("available")),
            "items": models[:16],
            "error": config.get("error"),
        },
        "idle": bool(health_ok and config_ok),
        "confidence": "medium" if health_ok and config_ok else "low",
    }


def executor_lock_status(
    *,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    root = runtime_dir or Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid if uid is not None else os.getuid()}"))
    lock_path = root / "abyss-machine" / "memory" / "orchestrate" / "executor.lock"
    exists = lock_path.exists()
    data: dict[str, Any] = {
        "path": str(lock_path),
        "exists": exists,
        "available": not exists,
    }
    if exists:
        data["content_preview"] = _read_text(lock_path)[:400]
    return data


def live_lock_path(*, runtime_dir: Path | None = None, uid: int | None = None) -> Path:
    root = runtime_dir or Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid if uid is not None else os.getuid()}"))
    return root / "abyss-machine" / "memory" / "orchestrate" / "live.lock"


def live_lock_acquire(
    candidate_id: str,
    operator: str,
    *,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    pid: PidPort = os.getpid,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    lock_path = live_lock_path(runtime_dir=runtime_dir, uid=uid)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": f"{schema_prefix}_memory_orchestrate_live_lock_v1",
        "version": version,
        "created_at": now_iso(),
        "pid": pid(),
        "candidate_id": str(candidate_id or ""),
        "operator": str(operator or "").strip() or None,
    }
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, (json.dumps(payload, sort_keys=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        return {"acquired": True, "path": str(lock_path), "payload": payload}
    except FileExistsError:
        return {
            "acquired": False,
            "path": str(lock_path),
            "reason": "live_executor_lock_exists",
            "content_preview": _read_text(lock_path)[:400],
        }
    except OSError as exc:
        return {"acquired": False, "path": str(lock_path), "reason": str(exc)}


def live_lock_release(
    lock_status: dict[str, Any],
    *,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    lock_path = Path(str(lock_status.get("path") or live_lock_path(runtime_dir=runtime_dir, uid=uid)))
    if not lock_status.get("acquired"):
        return {"released": False, "path": str(lock_path), "reason": "lock_not_acquired_by_this_process"}
    try:
        lock_path.unlink()
        return {"released": True, "path": str(lock_path)}
    except FileNotFoundError:
        return {"released": False, "path": str(lock_path), "reason": "already_missing"}
    except OSError as exc:
        return {"released": False, "path": str(lock_path), "reason": str(exc)}


def live_execute_command(
    future_executor: dict[str, Any],
    timeout_sec: int,
    *,
    runner: CommandRunnerPort = run_tool_process,
    http_json_port: HttpJsonPort = http_json,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    command_template = future_executor.get("command_template") if isinstance(future_executor.get("command_template"), list) else []
    command = [str(item) for item in command_template]
    if len(command) == 2 and command[0] == "http_post_json" and command[1].startswith("http://"):
        started = monotonic()
        result = http_json_port(command[1], float(timeout_sec), 262144, "POST")
        result["ok"] = bool(result.get("ok")) and bool(nested_get(result, ["json", "ok"]))
        result["returncode"] = 0 if result.get("ok") else 1
        result["command"] = command
        result["elapsed_sec"] = round(monotonic() - started, 3)
        return result
    if len(command) != 3 or command[:2] != ["podman", "restart"] or not command[2]:
        return {
            "ok": False,
            "returncode": None,
            "command": command,
            "error": "unsupported_live_executor_command",
        }
    started = monotonic()
    result = dict(runner(command, float(timeout_sec)))
    result["command"] = command
    result["elapsed_sec"] = round(monotonic() - started, 3)
    return result


def live_wait_rehydrate(
    candidate: dict[str, Any],
    timeout_sec: int,
    *,
    target_snapshot: Callable[[dict[str, Any]], dict[str, Any]],
    idle_probe: Callable[[dict[str, Any], dict[str, Any], float], dict[str, Any]],
    health_summary: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    monotonic: MonotonicPort = time.monotonic,
    sleep: SleepPort = time.sleep,
) -> dict[str, Any]:
    timeout_sec = max(30, min(int(timeout_sec or 180), 600))
    started = monotonic()
    deadline = started + float(timeout_sec)
    attempts: list[dict[str, Any]] = []
    final_snapshot: dict[str, Any] = {}
    final_idle_gate: dict[str, Any] = {}
    final_summary: dict[str, Any] = {}
    attempt = 0
    while True:
        attempt += 1
        final_snapshot = target_snapshot(candidate)
        final_idle_gate = idle_probe(candidate, final_snapshot, 0.2)
        final_summary = health_summary(final_snapshot, final_idle_gate)
        attempts.append(
            {
                "attempt": attempt,
                "elapsed_sec": round(monotonic() - started, 3),
                "ready": final_summary.get("ready"),
                "podman_running": final_summary.get("podman_running"),
                "pid": final_summary.get("pid"),
                "http_health_ok": final_summary.get("http_health_ok"),
                "slots_ok": final_summary.get("slots_ok"),
                "slots_idle": final_summary.get("slots_idle"),
                "ovms_models_ok": final_summary.get("ovms_models_ok"),
                "ovms_model_count": final_summary.get("ovms_model_count"),
                "idle": final_summary.get("idle"),
                "idle_status": final_summary.get("idle_status"),
            }
        )
        if final_summary.get("ready"):
            break
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(2.0, max(0.2, remaining)))
    elapsed = round(monotonic() - started, 3)
    ok = bool(final_summary.get("ready"))
    return {
        "ok": ok,
        "status": "ready" if ok else "timeout_waiting_for_ready",
        "timeout_sec": timeout_sec,
        "elapsed_sec": elapsed,
        "attempt_count": attempt,
        "attempts_tail": attempts[-20:],
        "final_health_summary": final_summary,
        "final_snapshot": final_snapshot,
        "final_idle_gate": final_idle_gate,
    }
