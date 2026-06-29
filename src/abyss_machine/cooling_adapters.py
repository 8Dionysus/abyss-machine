from __future__ import annotations

import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Mapping, Sequence


CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[[Sequence[str], float], Mapping[str, Any]]
PathExistsPort = Callable[[Path], bool]
PathGlobPort = Callable[[Path, str], Sequence[Path]]
ReadTextPort = Callable[[Path], str | None]
ReadTextResultPort = Callable[[Path], Mapping[str, Any]]
ReadIntPort = Callable[[Path], int | None]
WriteTextResultPort = Callable[[Path, str], Mapping[str, Any]]
AccessPort = Callable[[Path, int], bool]
EuidPort = Callable[[], int]
CoolingConfigPort = Callable[[], Mapping[str, Any]]
HwmonReadingsPort = Callable[[], Mapping[str, Any]]
ClassifyTemperaturePort = Callable[[float | None, float, float, float], str]
BatterySummaryPort = Callable[[], Mapping[str, Any]]
FanStatusPort = Callable[[], Mapping[str, Any]]
PlatformProfilePort = Callable[[], Mapping[str, Any]]
TemperatureSamplePort = Callable[[], Mapping[str, Any]]
SleepPort = Callable[[float], None]
MonotonicPort = Callable[[], float]


PLATFORM_PROFILE_PATH = Path("/sys/firmware/acpi/platform_profile")
PLATFORM_PROFILE_CHOICES_PATH = Path("/sys/firmware/acpi/platform_profile_choices")
LENOVO_VPC_ROOT_PATTERNS: tuple[tuple[Path, str], ...] = (
    (Path("/sys/bus/platform/devices"), "VPC2004:*"),
    (Path("/sys/bus/platform/drivers/ideapad_acpi"), "VPC2004:*"),
    (Path("/sys/devices"), "**/VPC2004:*"),
)
RAPL_MMIO_PREFERRED_ROOT = Path("/sys/devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0")
RAPL_MMIO_ROOT = Path("/sys/devices/virtual/powercap")
RAPL_MMIO_PATTERN = "intel-rapl-mmio/intel-rapl-mmio:*"
CPU_THROTTLE_ROOT = Path("/sys/devices/system/cpu")
CPU_PACKAGE_THROTTLE_PATTERN = "cpu*/thermal_throttle/package_throttle_count"
KERNEL_FAN_ERROR_PATTERN = re.compile(
    r"TFN1|_FSL|FAN0|FAN1|FAN2|FAN3|FAN4|VFAN|UPFS|FANL|ACPI (?:BIOS )?Error",
    re.IGNORECASE,
)


def current_euid() -> int:
    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid):
        return int(geteuid())
    return 0


def tool_available(command: str) -> bool:
    return shutil.which(command) is not None


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
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout"}
    except OSError as exc:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(exc)}


def path_exists(path: Path) -> bool:
    return path.exists()


def path_glob(root: Path, pattern: str) -> Sequence[Path]:
    return sorted(root.glob(pattern), key=lambda item: str(item))


def path_writable(path: Path, mode: int = os.W_OK) -> bool:
    return os.access(path, mode)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def read_int(path: Path) -> int | None:
    value = read_text(path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def classify_temperature_value(value: float | None, warm: float, hot: float, critical: float) -> str:
    if value is None:
        return "unknown"
    if value >= critical:
        return "critical"
    if value >= hot:
        return "hot"
    if value >= warm:
        return "warm"
    return "green"


def read_text_result(path: Path) -> dict[str, Any]:
    try:
        value = path.read_text(encoding="utf-8", errors="replace").strip()
        return {"ok": True, "path": str(path), "value": value}
    except OSError as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}


def write_text_result(path: Path, value: str) -> dict[str, Any]:
    try:
        path.write_text(value, encoding="utf-8")
        return {"ok": True, "path": str(path), "value": value.strip(), "changed": True}
    except OSError as exc:
        return {"ok": False, "path": str(path), "value": value.strip(), "error": str(exc)}


def write_permission_required(
    path: Path,
    *,
    euid: EuidPort = current_euid,
    access: AccessPort = path_writable,
) -> bool:
    return euid() != 0 and not access(path, os.W_OK)


def find_lenovo_vpc(
    *,
    glob_paths: PathGlobPort = path_glob,
    exists: PathExistsPort = path_exists,
) -> Path | None:
    candidates: list[Path] = []
    for root, pattern in LENOVO_VPC_ROOT_PATTERNS:
        candidates.extend(glob_paths(root, pattern))
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = str(candidate.resolve())
        except OSError:
            resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if exists(candidate / "fan_mode"):
            return candidate
    return None


def platform_profile_status(
    *,
    profile_path: Path = PLATFORM_PROFILE_PATH,
    choices_path: Path = PLATFORM_PROFILE_CHOICES_PATH,
    exists: PathExistsPort = path_exists,
    read_result: ReadTextResultPort = read_text_result,
    read_text_value: ReadTextPort = read_text,
    access: AccessPort = path_writable,
) -> dict[str, Any]:
    current = dict(read_result(profile_path))
    choices_raw = read_text_value(choices_path)
    return {
        "available": exists(profile_path),
        "path": str(profile_path),
        "choices_path": str(choices_path),
        "current": current.get("value") if current.get("ok") else None,
        "choices": str(choices_raw).split() if choices_raw else [],
        "read_error": current.get("error"),
        "writable_by_current_user": access(profile_path, os.W_OK),
    }


def lenovo_fan_status(
    *,
    mode_labels: Mapping[int, str],
    find_vpc: Callable[[], Path | None] = find_lenovo_vpc,
    read_result: ReadTextResultPort = read_text_result,
    access: AccessPort = path_writable,
) -> dict[str, Any]:
    vpc = find_vpc()
    if vpc is None:
        return {
            "available": False,
            "driver": "ideapad_laptop",
            "fan_mode": None,
            "fan_mode_label": None,
            "policy": "No VPC2004 fan_mode sysfs backend found; leave fan control to firmware.",
        }
    path = vpc / "fan_mode"
    current = dict(read_result(path))
    value: int | None = None
    if current.get("ok"):
        try:
            value = int(str(current.get("value")))
        except ValueError:
            value = None
    return {
        "available": True,
        "driver": "ideapad_laptop",
        "device": str(vpc),
        "fan_mode_path": str(path),
        "fan_mode": value,
        "fan_mode_raw": current.get("value"),
        "fan_mode_label": mode_labels.get(value, "unknown") if value is not None else None,
        "read_error": current.get("error"),
        "writable_by_current_user": access(path, os.W_OK),
        "documented_modes": dict(mode_labels),
        "rpm_reading": "skipped_acpi_fan_broken_on_this_bios",
    }


def set_platform_profile(
    target: str,
    platform_profile_data: Mapping[str, Any],
    *,
    euid: EuidPort = current_euid,
    access: AccessPort = path_writable,
    write_text: WriteTextResultPort = write_text_result,
) -> dict[str, Any]:
    choices = list(platform_profile_data.get("choices") or [])
    current = platform_profile_data.get("current")
    path_text = platform_profile_data.get("path")
    if target not in choices:
        return {
            "action": "set_platform_profile",
            "ok": False,
            "target": target,
            "error": "target platform_profile not in choices",
            "choices": choices,
        }
    if current == target:
        return {"action": "set_platform_profile", "ok": True, "changed": False, "target": target}
    if not path_text:
        return {"action": "set_platform_profile", "ok": False, "target": target, "error": "platform_profile backend unavailable"}
    path = Path(str(path_text))
    if euid() != 0 and not access(path, os.W_OK):
        return {"action": "set_platform_profile", "ok": False, "target": target, "error": "root permission required"}
    result = dict(write_text(path, f"{target}\n"))
    return {"action": "set_platform_profile", "target": target, **result}


def set_lenovo_fan_mode(
    target: Any,
    fan_data: Mapping[str, Any],
    *,
    euid: EuidPort = current_euid,
    access: AccessPort = path_writable,
    write_text: WriteTextResultPort = write_text_result,
) -> dict[str, Any]:
    fan_path = fan_data.get("fan_mode_path")
    if not fan_path:
        return {"action": "set_fan_mode", "ok": False, "target": target, "error": "fan_mode backend unavailable"}
    try:
        target_int = int(target)
    except (TypeError, ValueError):
        return {"action": "set_fan_mode", "ok": False, "target": target, "error": "invalid fan_mode target"}
    if fan_data.get("fan_mode") == target_int:
        return {"action": "set_fan_mode", "ok": True, "changed": False, "target": target_int}
    path = Path(str(fan_path))
    if euid() != 0 and not access(path, os.W_OK):
        return {"action": "set_fan_mode", "ok": False, "target": target_int, "error": "root permission required"}
    result = dict(write_text(path, f"{target_int}\n"))
    return {"action": "set_fan_mode", "target": target_int, **result}


def rapl_mmio_path(
    *,
    preferred: Path = RAPL_MMIO_PREFERRED_ROOT,
    root: Path = RAPL_MMIO_ROOT,
    exists: PathExistsPort = path_exists,
    glob_paths: PathGlobPort = path_glob,
) -> Path | None:
    if exists(preferred):
        return preferred
    candidates = sorted(glob_paths(root, RAPL_MMIO_PATTERN), key=lambda item: str(item))
    return candidates[0] if candidates else None


def rapl_mmio_status(
    *,
    root: Path | None = None,
    path_resolver: Callable[[], Path | None] = rapl_mmio_path,
    access: AccessPort = path_writable,
    read_int_value: ReadIntPort = read_int,
) -> dict[str, Any]:
    resolved_root = root if root is not None else path_resolver()
    data: dict[str, Any] = {
        "available": bool(resolved_root),
        "backend": "intel-rapl-mmio",
        "root": str(resolved_root) if resolved_root else None,
    }
    if not resolved_root:
        return data
    paths = {
        "pl1": resolved_root / "constraint_0_power_limit_uw",
        "pl1_window": resolved_root / "constraint_0_time_window_us",
        "pl2": resolved_root / "constraint_1_power_limit_uw",
        "pl2_window": resolved_root / "constraint_1_time_window_us",
    }
    data["paths"] = {key: str(path) for key, path in paths.items()}
    data["writable_by_current_user"] = access(paths["pl1"], os.W_OK)
    data["pl1_uw"] = read_int_value(paths["pl1"])
    data["pl1_window_us"] = read_int_value(paths["pl1_window"])
    data["pl2_uw"] = read_int_value(paths["pl2"])
    data["pl2_window_us"] = read_int_value(paths["pl2_window"])
    return data


def package_throttle_count(
    *,
    root: Path = CPU_THROTTLE_ROOT,
    glob_paths: PathGlobPort = path_glob,
    read_int_value: ReadIntPort = read_int,
) -> int | None:
    total = 0
    seen = False
    for path in sorted(glob_paths(root, CPU_PACKAGE_THROTTLE_PATTERN), key=lambda item: str(item)):
        value = read_int_value(path)
        if value is None:
            continue
        total += value
        seen = True
    return total if seen else None


def thermal_zones(
    *,
    root: Path = Path("/sys/class/thermal"),
    glob_paths: PathGlobPort = path_glob,
    read_text_value: ReadTextPort = read_text,
    read_int_value: ReadIntPort = read_int,
) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for zone in sorted(glob_paths(root, "thermal_zone*"), key=lambda item: item.name):
        zone_type = read_text_value(zone / "type")
        if zone_type is None:
            continue
        temp_raw = read_int_value(zone / "temp")
        trips: list[dict[str, Any]] = []
        for trip_temp_path in sorted(glob_paths(zone, "trip_point_*_temp"), key=lambda item: item.name):
            match = re.match(r"trip_point_(\d+)_temp$", trip_temp_path.name)
            if not match:
                continue
            index = match.group(1)
            trip_raw = read_int_value(trip_temp_path)
            trips.append(
                {
                    "index": int(index),
                    "type": read_text_value(zone / f"trip_point_{index}_type"),
                    "temperature_c": round(float(trip_raw) / 1000.0, 1) if trip_raw is not None else None,
                }
            )
        zones.append(
            {
                "name": zone.name,
                "type": zone_type,
                "path": str(zone),
                "temperature_c": round(float(temp_raw) / 1000.0, 1) if temp_raw is not None else None,
                "trips": trips,
            }
        )
    zones.sort(key=lambda item: (-(item.get("temperature_c") or -999.0), str(item.get("name"))))
    return zones


def device_acpi_metadata(
    device: Path,
    *,
    acpi_root: Path = Path("/sys/bus/acpi/devices"),
    exists: PathExistsPort = path_exists,
    read_text_value: ReadTextPort = read_text,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    link = device / "device"
    try:
        resolved = link.resolve()
    except OSError:
        resolved = None
    if resolved is not None:
        metadata["kernel_device"] = str(resolved)
        acpi_name = resolved.name
        metadata["acpi_device"] = acpi_name
        acpi_device_root = acpi_root / acpi_name
        if exists(acpi_device_root):
            metadata["acpi_sysfs"] = str(acpi_device_root)
            metadata["acpi_path"] = read_text_value(acpi_device_root / "path")
            metadata["acpi_hid"] = read_text_value(acpi_device_root / "hid")
            metadata["acpi_uid"] = read_text_value(acpi_device_root / "uid")
    return metadata


def acpi_fan_performance_states(
    acpi_device: str | None,
    *,
    acpi_root: Path = Path("/sys/bus/acpi/devices"),
    exists: PathExistsPort = path_exists,
    glob_paths: PathGlobPort = path_glob,
    read_text_value: ReadTextPort = read_text,
) -> list[dict[str, Any]]:
    if not acpi_device:
        return []
    root = acpi_root / acpi_device
    if not exists(root):
        return []
    states: list[dict[str, Any]] = []
    for path in sorted(glob_paths(root, "state*"), key=lambda item: (len(item.name), item.name)):
        match = re.match(r"state(\d+)$", path.name)
        if not match:
            continue
        raw = read_text_value(path)
        if raw is None:
            continue
        parts = raw.split(":")
        parsed: dict[str, Any] = {
            "index": int(match.group(1)),
            "raw": raw,
        }
        if len(parts) >= 5:
            parsed.update(
                {
                    "control_percent": int(parts[0]) if parts[0].isdigit() else parts[0],
                    "trip_point": parts[1],
                    "speed_rpm": int(parts[2]) if parts[2].isdigit() else parts[2],
                    "power_mw": int(parts[3]) if parts[3].isdigit() else parts[3],
                    "noise_level": int(parts[4]) if parts[4].isdigit() else parts[4],
                }
            )
        states.append(parsed)
    return states


def cooling_devices(
    *,
    root: Path = Path("/sys/class/thermal"),
    acpi_root: Path = Path("/sys/bus/acpi/devices"),
    broken_acpi_paths: set[str] | frozenset[str] = frozenset(),
    glob_paths: PathGlobPort = path_glob,
    read_text_value: ReadTextPort = read_text,
    read_int_value: ReadIntPort = read_int,
    read_result: ReadTextResultPort = read_text_result,
    exists: PathExistsPort = path_exists,
    metadata_port: Callable[..., dict[str, Any]] = device_acpi_metadata,
    performance_states_port: Callable[..., list[dict[str, Any]]] = acpi_fan_performance_states,
) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for device in sorted(glob_paths(root, "cooling_device*"), key=lambda item: item.name):
        device_type = read_text_value(device / "type")
        if not device_type:
            continue
        if not (device_type == "Fan" or str(device_type).startswith("TFN")):
            continue
        metadata = metadata_port(
            device,
            acpi_root=acpi_root,
            exists=exists,
            read_text_value=read_text_value,
        )
        acpi_path = metadata.get("acpi_path")
        item = {
            "name": device.name,
            "type": device_type,
            "path": str(device),
            **metadata,
            "max_state": read_int_value(device / "max_state"),
        }
        if acpi_path in broken_acpi_paths:
            item.update(
                {
                    "cur_state": None,
                    "read_error": "skipped_broken_acpi_cooling_device_on_this_bios",
                    "control_policy": "blocked",
                }
            )
            devices.append(item)
            continue
        if str(device_type).startswith("TFN"):
            item.update(
                {
                    "cur_state": None,
                    "read_error": "skipped_tfn_cur_state_read_returns_invalid_argument_on_this_bios",
                    "control_policy": "candidate_write_only_manual_guard_required",
                    "performance_states": performance_states_port(
                        str(metadata.get("acpi_device") or ""),
                        acpi_root=acpi_root,
                        exists=exists,
                        glob_paths=glob_paths,
                        read_text_value=read_text_value,
                    ),
                }
            )
            devices.append(item)
            continue
        current = dict(read_result(device / "cur_state"))
        item.update(
            {
                "cur_state": current.get("value") if current.get("ok") else None,
                "read_error": current.get("error"),
            }
        )
        devices.append(item)
    return devices


def tfn1_candidate(cooling_devices_port: Callable[[], list[dict[str, Any]]] = cooling_devices) -> dict[str, Any] | None:
    for device in cooling_devices_port():
        if device.get("type") == "TFN1" and device.get("acpi_path") == r"\_SB_.IETM.TFN1":
            return device
    return None


def cpu_hotspot_summary(
    hwmon: Mapping[str, Any],
    warm: float,
    hot: float,
    critical: float,
    *,
    classify_temperature: ClassifyTemperaturePort = classify_temperature_value,
) -> dict[str, Any]:
    core_entries: list[dict[str, Any]] = []
    package_entries: list[dict[str, Any]] = []
    for item in hwmon.get("readings", []):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("adapter") or "").lower() != "coretemp":
            continue
        temp = item.get("temperature_c")
        if not isinstance(temp, (int, float)):
            continue
        label = str(item.get("label") or "")
        rounded = round(float(temp), 1)
        entry = {
            "label": label,
            "path": item.get("path"),
            "temperature_c": rounded,
            "class": classify_temperature(rounded, warm, hot, critical),
        }
        if re.match(r"Core\s+\d+$", label, flags=re.IGNORECASE):
            core_entries.append(entry)
        elif "package" in label.lower():
            package_entries.append(entry)

    core_entries.sort(key=lambda item: (-float(item.get("temperature_c") or 0.0), str(item.get("label") or "")))
    package_entries.sort(key=lambda item: (-float(item.get("temperature_c") or 0.0), str(item.get("label") or "")))
    core_temps = [float(item["temperature_c"]) for item in core_entries if isinstance(item.get("temperature_c"), (int, float))]
    package_temps = [float(item["temperature_c"]) for item in package_entries if isinstance(item.get("temperature_c"), (int, float))]
    hot_cores = [item for item in core_entries if isinstance(item.get("temperature_c"), (int, float)) and float(item["temperature_c"]) >= hot]
    critical_cores = [item for item in core_entries if isinstance(item.get("temperature_c"), (int, float)) and float(item["temperature_c"]) >= critical]

    distribution = "unknown"
    if core_temps:
        if critical_cores and len(critical_cores) <= max(1, math.ceil(len(core_entries) * 0.15)):
            distribution = "localized_critical_core_hotspot"
        elif hot_cores and len(hot_cores) <= max(1, math.ceil(len(core_entries) * 0.25)):
            distribution = "localized_hot_core_hotspot"
        elif hot_cores:
            distribution = "broad_core_heat"
        else:
            distribution = "no_hot_core"

    return {
        "distribution": distribution,
        "hottest_core": core_entries[0] if core_entries else None,
        "hottest_package": package_entries[0] if package_entries else None,
        "core_readings_count": len(core_entries),
        "hot_core_count": len(hot_cores),
        "critical_core_count": len(critical_cores),
        "hot_core_labels": [str(item.get("label")) for item in hot_cores],
        "critical_core_labels": [str(item.get("label")) for item in critical_cores],
        "hottest_core_temperature_c": round(max(core_temps), 1) if core_temps else None,
        "coolest_core_temperature_c": round(min(core_temps), 1) if core_temps else None,
        "core_temperature_spread_c": round(max(core_temps) - min(core_temps), 1) if core_temps else None,
        "package_temperature_c_max": round(max(package_temps), 1) if package_temps else None,
        "workload_routing_hint": "Use per-core CPU thermal-map to avoid only hot mapped CPUs; keep conservative max as a safety signal for fan/power policy.",
    }


def trusted_sensor_map(hwmon: Mapping[str, Any], zones: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cpu_hwmon: list[dict[str, Any]] = []
    component_hwmon: list[dict[str, Any]] = []
    supporting_hwmon: list[dict[str, Any]] = []
    for item in hwmon.get("readings", []):
        if not isinstance(item, Mapping):
            continue
        adapter = str(item.get("adapter") or "").lower()
        label = str(item.get("label") or "").lower()
        entry = {
            "path": item.get("path"),
            "adapter": item.get("adapter"),
            "label": item.get("label"),
            "temperature_c": item.get("temperature_c"),
        }
        if adapter == "coretemp":
            role = "cpu_execution_temperature"
            if "package" in label:
                role = "cpu_package_temperature"
            cpu_hwmon.append({**entry, "role": role, "trust": "high"})
        elif adapter in {"nvme", "iwlwifi_1", "bat1"}:
            component_hwmon.append({**entry, "role": "component_temperature", "trust": "high"})
        else:
            supporting_hwmon.append({**entry, "role": "supporting_temperature", "trust": "medium"})

    firmware_zones: list[dict[str, Any]] = []
    supporting_zones: list[dict[str, Any]] = []
    for zone in zones:
        zone_type = str(zone.get("type") or "")
        entry = {
            "path": zone.get("path"),
            "name": zone.get("name"),
            "type": zone_type,
            "temperature_c": zone.get("temperature_c"),
            "trips": zone.get("trips", []),
        }
        if zone_type.startswith("TCPU") or zone_type.startswith("SEN") or zone_type == "x86_pkg_temp":
            firmware_zones.append({**entry, "role": "firmware_thermal_policy_signal", "trust": "high_for_policy_medium_for_user_display"})
        else:
            supporting_zones.append({**entry, "role": "supporting_thermal_zone", "trust": "medium"})

    return {
        "cpu_hwmon": cpu_hwmon,
        "component_hwmon": component_hwmon,
        "supporting_hwmon": supporting_hwmon,
        "firmware_zones": firmware_zones,
        "supporting_zones": supporting_zones,
        "skipped": hwmon.get("skipped", []),
        "blocked": {
            "acpi_fan_rpm": "blocked; emits VFAN/FANL ACPI errors on this BIOS",
            "fan_cur_state": "blocked for FAN0..FAN4/VFAN; TFN1 readback skipped because cur_state returns Invalid argument",
        },
    }


def temperature_summary(
    *,
    hwmon_readings: HwmonReadingsPort,
    cooling_config: CoolingConfigPort,
    thermal_zones_port: Callable[[], list[dict[str, Any]]] = thermal_zones,
    classify_temperature: ClassifyTemperaturePort = classify_temperature_value,
    cpu_hotspot_summary_port: Callable[..., dict[str, Any]] = cpu_hotspot_summary,
) -> dict[str, Any]:
    hwmon = dict(hwmon_readings())
    temps = [float(item["temperature_c"]) for item in hwmon.get("readings", []) if isinstance(item, Mapping) and isinstance(item.get("temperature_c"), (int, float))]
    package = [
        float(item["temperature_c"])
        for item in hwmon.get("readings", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("temperature_c"), (int, float))
        and "package" in str(item.get("label", "")).lower()
    ]
    zones = thermal_zones_port()
    zone_temps = [float(item["temperature_c"]) for item in zones if isinstance(item.get("temperature_c"), (int, float))]
    sensor_max = max(temps + zone_temps, default=None)
    config = cooling_config()
    auto = config.get("auto", {}) if isinstance(config.get("auto"), Mapping) else {}
    warm = 80.0
    hot = float(auto.get("hot_temperature_c", 106.0))
    critical = float(auto.get("critical_temperature_c", 109.0))
    hotspot = cpu_hotspot_summary_port(hwmon, warm, hot, critical, classify_temperature=classify_temperature)
    return {
        "class": classify_temperature(round(sensor_max, 1) if sensor_max is not None else None, warm, hot, critical),
        "temperature_c_max": round(sensor_max, 1) if sensor_max is not None else None,
        "package_temperature_c_max": round(max(package), 1) if package else None,
        "hwmon_temperature_c_max": round(max(temps), 1) if temps else None,
        "thermal_zone_temperature_c_max": round(max(zone_temps), 1) if zone_temps else None,
        "cpu_hotspot": hotspot,
        "thresholds": {
            "warm_temperature_c": warm,
            "hot_temperature_c": hot,
            "critical_temperature_c": critical,
            "recovery_temperature_c": float(auto.get("recovery_temperature_c", 82.0)),
            "hold_emergency_above_c": float(auto.get("hold_emergency_above_c", 86.0)),
        },
        "hwmon": hwmon,
        "thermal_zones": zones,
    }


def temperature_sample(
    *,
    temperature_summary_port: Callable[[], dict[str, Any]],
    fan_status: FanStatusPort,
    platform_profile_status: PlatformProfilePort,
    battery_summary: BatterySummaryPort,
    now_iso: Callable[[], str],
    trusted_sensor_map_port: Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]]], dict[str, Any]] = trusted_sensor_map,
) -> dict[str, Any]:
    temperature = temperature_summary_port()
    return {
        "at": now_iso(),
        "summary": {key: value for key, value in temperature.items() if key not in {"hwmon", "thermal_zones"}},
        "fan": dict(fan_status()),
        "platform_profile": dict(platform_profile_status()),
        "battery": dict(battery_summary()),
        "trusted_sensor_map": trusted_sensor_map_port(temperature.get("hwmon", {}), temperature.get("thermal_zones", [])),
    }


def sample_series(
    seconds: float,
    interval: float,
    *,
    temperature_sample_port: TemperatureSamplePort,
    monotonic: MonotonicPort = time.monotonic,
    sleep: SleepPort = time.sleep,
) -> list[dict[str, Any]]:
    seconds = max(0.0, min(float(seconds), 120.0))
    interval = max(0.5, min(float(interval), 10.0))
    deadline = monotonic() + seconds
    samples = [dict(temperature_sample_port())]
    while monotonic() < deadline:
        sleep(min(interval, max(0.0, deadline - monotonic())))
        samples.append(dict(temperature_sample_port()))
    return samples


def series_metric(samples: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    values = [
        float(sample.get("summary", {}).get(key))
        for sample in samples
        if isinstance(sample.get("summary"), Mapping) and isinstance(sample.get("summary", {}).get(key), (int, float))
    ]
    if not values:
        return {"count": 0, "first": None, "last": None, "min": None, "max": None, "delta": None}
    return {
        "count": len(values),
        "first": round(values[0], 1),
        "last": round(values[-1], 1),
        "min": round(min(values), 1),
        "max": round(max(values), 1),
        "delta": round(values[-1] - values[0], 1),
    }


def series_summary(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    classes = [
        sample.get("summary", {}).get("class")
        for sample in samples
        if isinstance(sample.get("summary"), Mapping) and sample.get("summary", {}).get("class")
    ]
    return {
        "samples": len(samples),
        "temperature_c_max": series_metric(samples, "temperature_c_max"),
        "package_temperature_c_max": series_metric(samples, "package_temperature_c_max"),
        "hwmon_temperature_c_max": series_metric(samples, "hwmon_temperature_c_max"),
        "thermal_zone_temperature_c_max": series_metric(samples, "thermal_zone_temperature_c_max"),
        "classes": sorted(set(str(item) for item in classes)),
    }


def write_rapl_pl1(
    rapl: Mapping[str, Any],
    target_uw: int,
    *,
    euid: EuidPort = current_euid,
    access: AccessPort = path_writable,
    write_text: WriteTextResultPort = write_text_result,
    pkexec_hint: Sequence[str] | None = None,
) -> dict[str, Any]:
    paths = rapl.get("paths") if isinstance(rapl.get("paths"), Mapping) else {}
    path_text = paths.get("pl1") if isinstance(paths, Mapping) else None
    target = int(target_uw)
    if not path_text:
        return {"ok": False, "target_pl1_uw": target, "error": "RAPL-MMIO PL1 path unavailable"}
    path = Path(str(path_text))
    if euid() != 0 and not access(path, os.W_OK):
        return {
            "ok": False,
            "permission_required": True,
            "target_pl1_uw": target,
            "error": "root permission required",
            "pkexec_hint": list(pkexec_hint)
            if pkexec_hint is not None
            else ["pkexec", "/usr/local/bin/abyss-machine", "cooling", "rapl-smoothing", "--apply", "--json"],
        }
    result = dict(write_text(path, f"{target}\n"))
    result["target_pl1_uw"] = target
    return result


def kernel_fan_errors(
    since: str,
    *,
    limit: int = 50,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
) -> dict[str, Any]:
    if not command_exists("journalctl"):
        return {
            "ok": False,
            "since": since,
            "matches": [],
            "journal_error": "journalctl not found",
        }
    out = dict(runner(["journalctl", "-k", "-b", "--since", since, "--no-pager"], 4.0))
    lines = [line for line in str(out.get("stdout") or "").splitlines() if KERNEL_FAN_ERROR_PATTERN.search(line)]
    return {
        "ok": bool(out.get("ok")) and not lines,
        "since": since,
        "matches": lines[-max(1, int(limit)):],
        "journal_error": out.get("stderr"),
    }
