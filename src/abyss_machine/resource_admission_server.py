from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from . import memory_adapters, memory_contracts
from . import resource_adapters, resource_admission_adapters, resource_planning


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def resource_policy(environ: Mapping[str, str]) -> dict[str, Any]:
    defaults = resource_planning.default_policy()
    path = Path(environ.get("ABYSS_MACHINE_RESOURCE_POLICY", "/etc/abyss-machine/resource-policy.json"))
    loaded = _load_json(path) or {}
    for key in ("startup_admission", "runtime_admission"):
        configured = loaded.get(key) if isinstance(loaded.get(key), dict) else {}
        defaults[key] = {**dict(defaults.get(key) or {}), **configured}
    return defaults


def runtime_policy(environ: Mapping[str, str]) -> dict[str, Any]:
    return dict(resource_policy(environ).get("runtime_admission") or {})


def memory_policy(environ: Mapping[str, str]) -> dict[str, Any]:
    path = Path(environ.get("ABYSS_MACHINE_MEMORY_POLICY", "/etc/abyss-machine/memory-policy.json"))
    return memory_contracts.policy_document(
        schema_prefix="abyss_machine",
        version="",
        loaded=_load_json(path),
        config_error=None,
    )


def fresh_memory_facts(
    *,
    meminfo_path: Path = Path("/proc/meminfo"),
    pressure_path: Path = Path("/proc/pressure/memory"),
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    raw: dict[str, int] = {}
    try:
        lines = meminfo_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        parts = line.replace(":", "").split()
        if len(parts) >= 2 and parts[1].isdigit():
            raw[parts[0]] = int(parts[1])
    mem = memory_adapters.meminfo_details(raw)
    psi = memory_adapters.parse_pressure_file(pressure_path)
    current_class, _reasons = memory_contracts.pressure_class(mem, psi, {}, dict(policy))
    summary = dict(mem.get("summary") or {})
    summary["psi_some_avg10"] = psi.get("some", {}).get("avg10") if isinstance(psi.get("some"), dict) else None
    summary["psi_full_avg10"] = psi.get("full", {}).get("avg10") if isinstance(psi.get("full"), dict) else None
    return summary, current_class


def fresh_thermal_safety(
    *,
    hwmon_root: Path = Path("/sys/class/hwmon"),
    emergency_c: float = 109.0,
) -> dict[str, Any]:
    readings: list[dict[str, Any]] = []
    cpu_sensor_names = {"coretemp", "k10temp", "zenpower", "cpu_thermal"}
    for directory in sorted(hwmon_root.glob("hwmon*")):
        try:
            name = (directory / "name").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if name not in cpu_sensor_names:
            continue
        for input_path in sorted(directory.glob("temp*_input")):
            stem = input_path.name.removesuffix("_input")
            try:
                temperature_c = float(input_path.read_text(encoding="utf-8").strip()) / 1000.0
            except (OSError, ValueError):
                continue
            try:
                label = (directory / f"{stem}_label").read_text(encoding="utf-8").strip()
            except OSError:
                label = stem
            try:
                alarm = (directory / f"{stem}_crit_alarm").read_text(encoding="utf-8").strip() == "1"
            except OSError:
                alarm = False
            readings.append({"sensor": name, "label": label, "temperature_c": temperature_c, "critical_alarm": alarm})
    package = [item for item in readings if "package" in str(item.get("label") or "").lower() or str(item.get("label") or "").lower() in {"tctl", "tdie"}]
    decision_readings = package or readings
    maximum = max((float(item["temperature_c"]) for item in decision_readings), default=None)
    cpu_maximum = max((float(item["temperature_c"]) for item in readings), default=None)
    alarm = any(bool(item.get("critical_alarm")) for item in readings)
    return {
        "available": bool(decision_readings),
        "emergency": bool(alarm or (maximum is not None and maximum >= float(emergency_c))),
        "temperature_c_max": None if maximum is None else round(maximum, 3),
        "cpu_temperature_c_max": None if cpu_maximum is None else round(cpu_maximum, 3),
        "emergency_c": float(emergency_c),
        "critical_alarm": alarm,
        "source": "direct_cpu_hwmon",
    }


def collect_plan(
    request: Mapping[str, Any],
    reservations: dict[str, Any],
    *,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    resources = resource_policy(environ)
    memory = memory_policy(environ)
    memory_summary, current_class = fresh_memory_facts(policy=memory)
    runtime = resources.get("runtime_admission") if isinstance(resources.get("runtime_admission"), dict) else {}
    thermal = fresh_thermal_safety(emergency_c=float(runtime.get("thermal_emergency_c", 109.0)))
    return resource_planning.runtime_cold_load_plan(
        request=request,
        memory_summary=memory_summary,
        current_memory_class=current_class,
        memory_policy=memory,
        resource_policy=resources,
        reservations=reservations,
        thermal_safety=thermal,
        generated_at=now_iso(),
    )


def serve(
    *,
    path: Path,
    allow_shutdown: bool,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    if os.geteuid() == 0:
        return {
            "ok": False,
            "decision": "deny",
            "denied_reasons": ["runtime_admission_server_must_be_unprivileged"],
        }
    policy = runtime_policy(environ)
    reservation_root = resource_adapters.reservations_root(environ, uid=os.getuid())
    max_request_bytes = max(4096, min(int(policy.get("max_request_bytes") or 65536), 1024 * 1024))
    state = {
        "schema": "abyss_machine_resource_admission_server_v1",
        "pid": os.getpid(),
        "started_at": now_iso(),
        "socket": str(path),
        "policy": {
            "runtime_only": True,
            "unprivileged": True,
            "owner_activity_required": True,
            "no_process_mutation": True,
            "resident_cli_import": False,
        },
    }

    def reserve(request: Mapping[str, Any]) -> dict[str, Any]:
        return resource_admission_adapters.reserve_cold_load(
            request,
            reservation_root=reservation_root,
            runtime_policy=policy,
            plan_port=lambda normalized, reservations: collect_plan(
                normalized,
                reservations,
                environ=environ,
            ),
            timestamp=now_iso,
        )

    def release(request: Mapping[str, Any]) -> dict[str, Any]:
        return resource_admission_adapters.release_cold_load(
            request,
            reservation_root=reservation_root,
        )

    def status() -> dict[str, Any]:
        return resource_admission_adapters.status(reservation_root=reservation_root)

    def dispatch(payload: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        return resource_admission_adapters.dispatch(
            payload,
            server_state=state,
            reserve_port=reserve,
            release_port=release,
            status_port=status,
            allow_shutdown=allow_shutdown,
        )

    return resource_admission_adapters.run_server_loop(
        path=path,
        dispatch_port=dispatch,
        chmod_mode=0o600,
        max_request_bytes=max_request_bytes,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lightweight owner cold-load admission server")
    parser.add_argument("--socket", default=None)
    parser.add_argument("--allow-shutdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = resource_admission_adapters.socket_path(os.environ, uid=os.getuid()) if not args.socket else Path(args.socket).expanduser()
    result = serve(
        path=path,
        allow_shutdown=bool(args.allow_shutdown),
        environ=os.environ,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    elif not result.get("ok"):
        print(f"resource admission server: {result.get('decision')}", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
