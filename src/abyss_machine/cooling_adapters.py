from __future__ import annotations

import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Mapping, Sequence

from . import cooling_contracts


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
TemperatureSummaryPort = Callable[[], Mapping[str, Any]]
SleepPort = Callable[[float], None]
MonotonicPort = Callable[[], float]
NowIsoPort = Callable[[], str]
SinceStampPort = Callable[[], str]
StatusPort = Callable[[], Mapping[str, Any]]
PathsPort = Callable[[], Mapping[str, Any]]
ProfileTargetsPort = Callable[[str, Mapping[str, Any]], tuple[str, Mapping[str, Any], Mapping[str, Any] | None]]
RaplSmoothingApplyPort = Callable[[str], Mapping[str, Any]]
SetPlatformProfilePort = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]
SetFanModePort = Callable[[Any, Mapping[str, Any]], Mapping[str, Any]]
WritePermissionPort = Callable[[Path], bool]
FanValidateRunPort = Callable[..., Mapping[str, Any]]
StatePort = Callable[[], Mapping[str, Any]]
SaveStatePort = Callable[[dict[str, Any], str], Mapping[str, Any] | None]
ModeStatePort = Callable[[], Mapping[str, Any]]
TargetProfilePort = Callable[[str, bool], tuple[str, str, str | None]]
RaplStatusPort = Callable[[], Mapping[str, Any]]
PackageThrottlePort = Callable[[], int | None]
WriteRaplPort = Callable[[Mapping[str, Any], int], Mapping[str, Any]]
EpochPort = Callable[[], float]


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


def nested_get(data: Any, path: Sequence[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


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


def rapl_smoothing_apply_document(
    updated_by: str = "auto",
    *,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    now_epoch: EpochPort,
    config_port: CoolingConfigPort,
    state_port: StatePort,
    save_state_port: SaveStatePort,
    fan_status_port: FanStatusPort,
    mode_state_port: ModeStatePort,
    battery_summary_port: BatterySummaryPort,
    target_profile_port: TargetProfilePort,
    rapl_status_port: RaplStatusPort,
    package_throttle_port: PackageThrottlePort,
    temperature_summary_port: TemperatureSummaryPort,
    write_rapl_port: WriteRaplPort = write_rapl_pl1,
    paths_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(config_port())
    state = dict(state_port())
    now_epoch_value = float(now_epoch())
    fan_mode = dict(fan_status_port()).get("fan_mode")
    mode_state = dict(mode_state_port())
    selected_mode = str(mode_state.get("selected_mode", "balanced"))
    ac_online = bool(dict(battery_summary_port()).get("ac_online"))
    effective_mode, _, _ = target_profile_port(selected_mode, ac_online)
    refs = dict(paths_refs or {})

    normal_pl1 = cooling_contracts.int_config(config, "normal_pl1_uw", 35000000)
    cap_pl1 = cooling_contracts.int_config(config, "cap_pl1_uw", 28000000)
    engage_temp = cooling_contracts.float_config(config, "engage_temperature_c", 98.0)
    engage_rate = cooling_contracts.float_config(config, "engage_package_throttle_per_s", 1200.0)
    engage_samples = max(1, cooling_contracts.int_config(config, "engage_sample_count", 1))
    release_temp = cooling_contracts.float_config(config, "release_temperature_c", 92.0)
    release_rate = cooling_contracts.float_config(config, "release_package_throttle_per_s", 250.0)
    release_samples = max(1, cooling_contracts.int_config(config, "release_sample_count", 2))
    min_sample_seconds = max(1.0, cooling_contracts.float_config(config, "min_sample_seconds", 5.0))
    max_sample_seconds = max(min_sample_seconds, cooling_contracts.float_config(config, "max_sample_seconds", 180.0))
    apply_modes = config.get("apply_modes") if isinstance(config.get("apply_modes"), list) else ["performance", "ai"]
    applicable = bool(config.get("enabled", False)) and effective_mode in {str(item) for item in apply_modes} and ac_online and fan_mode == 4

    action = "observe"
    write_result: dict[str, Any] | None = None
    reasons: list[str] = []
    permission_required = False
    active = bool(state.get("active", False))
    paths = {
        "latest": str(refs.get("latest")),
        "state": str(refs.get("state")),
        "daily_glob": str(Path(str(refs.get("root", ""))) / "YYYY" / "MM" / "YYYY-MM-DD.jsonl")
        if refs.get("root")
        else None,
    }

    if not bool(config.get("enabled", False)) and not active:
        action = "disabled"
        reasons.append("config_disabled")
        return {
            "schema": f"{schema_prefix}_cooling_rapl_smoothing_apply_v1",
            "version": version,
            "generated_at": now_iso(),
            "ok": True,
            "enabled": False,
            "action": action,
            "active": active,
            "permission_required": False,
            "reasons": reasons,
            "selected_mode": selected_mode,
            "effective_mode": effective_mode,
            "ac_online": ac_online,
            "fan_mode": fan_mode,
            "temperature": {
                "class": None,
                "max_c": None,
                "package_c": None,
                "skipped": True,
                "reason": "smoothing_disabled_inactive",
            },
            "throttle": {
                "package_count": None,
                "previous_package_count": state.get("last_package_throttle_count"),
                "elapsed_seconds": None,
                "package_delta": None,
                "package_rate_per_s": None,
                "skipped": True,
                "reason": "smoothing_disabled_inactive",
            },
            "thresholds": {
                "engage_temperature_c": engage_temp,
                "engage_package_throttle_per_s": engage_rate,
                "engage_sample_count": engage_samples,
                "release_temperature_c": release_temp,
                "release_package_throttle_per_s": release_rate,
                "release_sample_count": release_samples,
                "cap_pl1_uw": cap_pl1,
                "normal_pl1_uw": normal_pl1,
            },
            "rapl_mmio": {
                "skipped": True,
                "reason": "smoothing_disabled_inactive",
            },
            "write_result": None,
            "state": state,
            "paths": paths,
            "write_skipped": "disabled_inactive",
        }
    if not applicable and not active:
        action = "not_applicable"
        reasons.append("not_applicable")
        return {
            "schema": f"{schema_prefix}_cooling_rapl_smoothing_apply_v1",
            "version": version,
            "generated_at": now_iso(),
            "ok": True,
            "enabled": bool(config.get("enabled", False)),
            "action": action,
            "active": active,
            "permission_required": False,
            "reasons": reasons,
            "selected_mode": selected_mode,
            "effective_mode": effective_mode,
            "ac_online": ac_online,
            "fan_mode": fan_mode,
            "temperature": {
                "class": None,
                "max_c": None,
                "package_c": None,
                "skipped": True,
                "reason": "smoothing_not_applicable_inactive",
            },
            "throttle": {
                "package_count": None,
                "previous_package_count": state.get("last_package_throttle_count"),
                "elapsed_seconds": None,
                "package_delta": None,
                "package_rate_per_s": None,
                "skipped": True,
                "reason": "smoothing_not_applicable_inactive",
            },
            "thresholds": {
                "engage_temperature_c": engage_temp,
                "engage_package_throttle_per_s": engage_rate,
                "engage_sample_count": engage_samples,
                "release_temperature_c": release_temp,
                "release_package_throttle_per_s": release_rate,
                "release_sample_count": release_samples,
                "cap_pl1_uw": cap_pl1,
                "normal_pl1_uw": normal_pl1,
            },
            "rapl_mmio": {
                "skipped": True,
                "reason": "smoothing_not_applicable_inactive",
            },
            "write_result": None,
            "state": state,
            "paths": paths,
            "write_skipped": "not_applicable_inactive",
        }

    rapl = dict(rapl_status_port())
    package_count = package_throttle_port()
    temperature = dict(temperature_summary_port())
    max_temp = temperature.get("temperature_c_max")
    package_temp = temperature.get("package_temperature_c_max")

    previous_epoch = state.get("last_sample_epoch")
    previous_count = state.get("last_package_throttle_count")
    elapsed: float | None = None
    package_delta: int | None = None
    package_rate: float | None = None
    if isinstance(previous_epoch, (int, float)) and isinstance(previous_count, int) and isinstance(package_count, int):
        elapsed = max(0.0, now_epoch_value - float(previous_epoch))
        package_delta = max(0, package_count - previous_count)
        if min_sample_seconds <= elapsed <= max_sample_seconds:
            package_rate = package_delta / elapsed

    if not rapl.get("available"):
        action = "unavailable"
        reasons.append("rapl_mmio_unavailable")
    elif not bool(config.get("enabled", False)):
        action = "disabled"
        reasons.append("config_disabled")
    elif not applicable:
        reasons.append("not_applicable")
        if active and bool(config.get("restore_when_not_applicable", True)):
            write_result = dict(write_rapl_port(rapl, int(state.get("baseline_pl1_uw") or normal_pl1)))
            permission_required = bool(write_result.get("permission_required"))
            if write_result.get("ok"):
                action = "restore_not_applicable"
                active = False
                state["engage_count"] = 0
                state["release_count"] = 0
            else:
                action = "restore_not_applicable_failed"
        else:
            action = "not_applicable"
    elif package_rate is None:
        action = "sample_seed"
        reasons.append("need_previous_throttle_sample")
    else:
        temp_value = max_temp if isinstance(max_temp, (int, float)) else package_temp
        if active:
            write_result = dict(write_rapl_port(rapl, cap_pl1))
            permission_required = bool(write_result.get("permission_required"))
            release_ready = (
                isinstance(temp_value, (int, float))
                and temp_value <= release_temp
                and package_rate <= release_rate
            )
            if release_ready:
                state["release_count"] = int(state.get("release_count") or 0) + 1
            else:
                state["release_count"] = 0
            state["engage_count"] = 0
            if int(state.get("release_count") or 0) >= release_samples:
                write_result = dict(write_rapl_port(rapl, int(state.get("baseline_pl1_uw") or normal_pl1)))
                permission_required = bool(write_result.get("permission_required"))
                if write_result.get("ok"):
                    action = "release_cap"
                    active = False
                    state["release_count"] = 0
                else:
                    action = "release_cap_failed"
            else:
                action = "hold_cap"
        else:
            engage_ready = (
                isinstance(temp_value, (int, float))
                and temp_value >= engage_temp
                and package_rate >= engage_rate
            )
            if engage_ready:
                state["engage_count"] = int(state.get("engage_count") or 0) + 1
            else:
                state["engage_count"] = 0
            state["release_count"] = 0
            if int(state.get("engage_count") or 0) >= engage_samples:
                baseline = rapl.get("pl1_uw") if isinstance(rapl.get("pl1_uw"), int) else normal_pl1
                state["baseline_pl1_uw"] = baseline if baseline and baseline > cap_pl1 else normal_pl1
                write_result = dict(write_rapl_port(rapl, cap_pl1))
                permission_required = bool(write_result.get("permission_required"))
                if write_result.get("ok"):
                    action = "engage_cap"
                    active = True
                else:
                    action = "engage_cap_failed"
            else:
                action = "observe_ready" if engage_ready else "observe"

    state["active"] = active
    state["last_sample_epoch"] = now_epoch_value
    state["last_package_throttle_count"] = package_count
    state["last_action"] = action
    state_error = save_state_port(state, updated_by)
    data = {
        "schema": f"{schema_prefix}_cooling_rapl_smoothing_apply_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": not (write_result and not write_result.get("ok")) and state_error is None,
        "enabled": bool(config.get("enabled", False)),
        "action": action,
        "active": active,
        "permission_required": permission_required,
        "reasons": reasons,
        "selected_mode": selected_mode,
        "effective_mode": effective_mode,
        "ac_online": ac_online,
        "fan_mode": fan_mode,
        "temperature": {
            "class": temperature.get("class"),
            "max_c": max_temp,
            "package_c": package_temp,
        },
        "throttle": {
            "package_count": package_count,
            "previous_package_count": previous_count,
            "elapsed_seconds": round(elapsed, 3) if isinstance(elapsed, (int, float)) else None,
            "package_delta": package_delta,
            "package_rate_per_s": round(package_rate, 3) if isinstance(package_rate, (int, float)) else None,
        },
        "thresholds": {
            "engage_temperature_c": engage_temp,
            "engage_package_throttle_per_s": engage_rate,
            "engage_sample_count": engage_samples,
            "release_temperature_c": release_temp,
            "release_package_throttle_per_s": release_rate,
            "release_sample_count": release_samples,
            "cap_pl1_uw": cap_pl1,
            "normal_pl1_uw": normal_pl1,
        },
        "rapl_mmio": dict(rapl_status_port()),
        "write_result": write_result,
        "state": state,
        "paths": paths,
    }
    if state_error:
        data["write_errors"] = [state_error]
    return data


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


def apply_cooling_profile(
    profile: str = "auto",
    *,
    schema_prefix: str,
    version: str,
    updated_by: str,
    now_iso: NowIsoPort,
    status_port: StatusPort,
    profile_targets_port: ProfileTargetsPort,
    rapl_smoothing_apply_port: RaplSmoothingApplyPort,
    temperature_summary_port: TemperatureSummaryPort,
    fan_status_port: FanStatusPort,
    platform_profile_port: PlatformProfilePort,
    paths_port: PathsPort,
    set_platform_profile_port: SetPlatformProfilePort = set_platform_profile,
    set_fan_mode_port: SetFanModePort = set_lenovo_fan_mode,
) -> dict[str, Any]:
    status_before = dict(status_port())
    normalized, target, recommendation = profile_targets_port(profile, status_before)
    fan = status_before.get("fan", {}) if isinstance(status_before.get("fan"), Mapping) else {}
    platform_profile_data = nested_get(status_before, ["power", "platform_profile"])
    if not isinstance(platform_profile_data, Mapping):
        platform_profile_data = {}
    actions: list[dict[str, Any]] = []
    permission_required = False

    target_platform = target.get("platform_profile")
    if target_platform:
        action = dict(set_platform_profile_port(str(target_platform), platform_profile_data))
        if action.get("error") == "root permission required":
            permission_required = True
        actions.append(action)

    target_fan = target.get("fan_mode")
    if target_fan is not None:
        action = dict(set_fan_mode_port(target_fan, fan))
        if action.get("error") == "root permission required":
            permission_required = True
        actions.append(action)

    if str(profile or "").strip().lower() == "auto":
        rapl_action = dict(rapl_smoothing_apply_port(updated_by))
        if rapl_action.get("permission_required"):
            permission_required = True
        actions.append(
            {
                "action": "rapl_smoothing",
                "ok": bool(rapl_action.get("ok")),
                "permission_required": bool(rapl_action.get("permission_required")),
                "decision_action": rapl_action.get("action"),
                "active": bool(rapl_action.get("active")),
                "decision": rapl_action,
            }
        )

    data = cooling_contracts.apply_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        requested_profile=profile,
        applied_profile=normalized,
        updated_by=updated_by,
        permission_required=permission_required,
        actions=actions,
        recommendation=dict(recommendation) if isinstance(recommendation, Mapping) else None,
        status_before=status_before,
        status_after={
            "temperature": dict(temperature_summary_port()),
            "fan": dict(fan_status_port()),
            "platform_profile": dict(platform_profile_port()),
        },
        paths=dict(paths_port()),
    )
    if permission_required:
        data["pkexec_hint"] = ["pkexec", "/usr/local/bin/abyss-machine", "cooling", "apply", "--profile", str(profile), "--json"]
    return data


def tfn1_write_document(
    level: int = 50,
    seconds: float = 5.0,
    *,
    schema_prefix: str,
    version: str,
    updated_by: str,
    now_iso: NowIsoPort,
    since_stamp: SinceStampPort,
    status_port: StatusPort,
    tfn1_candidate_port: Callable[[], Mapping[str, Any] | None],
    temperature_summary_port: TemperatureSummaryPort,
    fan_status_port: FanStatusPort,
    platform_profile_port: PlatformProfilePort,
    paths_port: PathsPort,
    write_permission: WritePermissionPort = write_permission_required,
    write_text: WriteTextResultPort = write_text_result,
    kernel_errors_port: Callable[..., Mapping[str, Any]] = kernel_fan_errors,
    sleep: SleepPort = time.sleep,
) -> dict[str, Any]:
    candidate = tfn1_candidate_port()
    status_before = dict(status_port())
    seconds = max(0.0, min(float(seconds), 30.0))
    level = int(level)
    actions: list[dict[str, Any]] = []
    permission_required = False
    ok = True
    if candidate is None:
        ok = False
        actions.append({"action": "find_tfn1", "ok": False, "error": "TFN1 candidate not found"})
    else:
        max_state = candidate.get("max_state")
        path = Path(str(candidate.get("path"))) / "cur_state"
        if not isinstance(max_state, int):
            ok = False
            actions.append({"action": "validate_level", "ok": False, "target": level, "error": "TFN1 max_state unavailable"})
        elif level < 25 or level > max_state:
            ok = False
            actions.append(
                {
                    "action": "validate_level",
                    "ok": False,
                    "target": level,
                    "min": 25,
                    "max": max_state,
                    "error": "manual TFN1 writes are restricted to the tested non-zero range",
                }
            )
        elif write_permission(path):
            ok = False
            permission_required = True
            actions.append({"action": "write_tfn1_cur_state", "ok": False, "target": level, "path": str(path), "error": "root permission required"})
        else:
            since = since_stamp()
            result = dict(write_text(path, f"{level}\n"))
            actions.append({"action": "write_tfn1_cur_state", "target": level, **result})
            if seconds > 0:
                sleep(seconds)
            kernel = dict(kernel_errors_port(since, limit=20))
            actions.append(
                {
                    "action": "check_recent_kernel_fan_errors",
                    "ok": kernel.get("ok"),
                    "since": since,
                    "matches": kernel.get("matches", []),
                    "journal_error": kernel.get("journal_error"),
                }
            )
            ok = bool(result.get("ok")) and not kernel.get("matches")

    data = {
        "schema": f"{schema_prefix}_cooling_tfn1_write_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": ok,
        "permission_required": permission_required,
        "updated_by": updated_by,
        "requested_level": level,
        "monitor_seconds": seconds,
        "candidate": dict(candidate) if isinstance(candidate, Mapping) else None,
        "policy": {
            "automation": "disabled",
            "safe_range": "25..max_state only; no zero/off writes from this command",
            "reason": "TFN1 accepted one guarded write, but cur_state/RPM feedback is not reliable on this BIOS.",
        },
        "actions": actions,
        "status_before": {
            "temperature": status_before.get("temperature", {}).get("summary", {}) if isinstance(status_before.get("temperature"), Mapping) else {},
            "fan": status_before.get("fan", {}),
            "power": status_before.get("power", {}),
        },
        "status_after": {
            "temperature": dict(temperature_summary_port()),
            "fan": dict(fan_status_port()),
            "platform_profile": dict(platform_profile_port()),
        },
        "paths": dict(paths_port()),
    }
    if permission_required:
        data["pkexec_hint"] = [
            "pkexec",
            "/usr/local/bin/abyss-machine",
            "cooling",
            "tfn1-write",
            "--level",
            str(level),
            "--seconds",
            str(seconds),
            "--json",
        ]
    return data


def fan_validate_document(
    levels: str | Sequence[int] | None = None,
    seconds: float = 8.0,
    interval: float = 2.0,
    allow_lower: bool = False,
    *,
    schema_prefix: str,
    version: str,
    updated_by: str,
    now_iso: NowIsoPort,
    since_stamp: SinceStampPort,
    status_port: StatusPort,
    tfn1_candidate_port: Callable[[], Mapping[str, Any] | None],
    temperature_summary_port: TemperatureSummaryPort,
    temperature_sample_port: TemperatureSamplePort,
    sample_series_port: Callable[[float, float], Sequence[Mapping[str, Any]]],
    series_summary_port: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]] = series_summary,
    fan_status_port: FanStatusPort = lambda: {},
    platform_profile_port: PlatformProfilePort = lambda: {},
    paths_port: PathsPort = lambda: {},
    write_permission: WritePermissionPort = write_permission_required,
    write_text: WriteTextResultPort = write_text_result,
    kernel_errors_port: Callable[..., Mapping[str, Any]] = kernel_fan_errors,
) -> dict[str, Any]:
    candidate = tfn1_candidate_port()
    requested_levels = cooling_contracts.parse_levels(levels)  # type: ignore[arg-type]
    seconds = max(1.0, min(float(seconds), 60.0))
    interval = max(0.5, min(float(interval), 10.0))
    status_before = dict(status_port())
    thermal_class = str(nested_get(status_before, ["temperature", "class"]) or "unknown")
    temp_before = nested_get(status_before, ["temperature", "summary", "temperature_c_max"])
    actions: list[dict[str, Any]] = []
    permission_required = False
    ok = True

    if candidate is None:
        ok = False
        actions.append({"action": "find_tfn1", "ok": False, "error": "TFN1 candidate not found"})
    else:
        max_state = candidate.get("max_state")
        path = Path(str(candidate.get("path"))) / "cur_state"
        if not isinstance(max_state, int):
            ok = False
            actions.append({"action": "validate_levels", "ok": False, "error": "TFN1 max_state unavailable", "levels": requested_levels})
        else:
            invalid = [level for level in requested_levels if level < 25 or level > max_state]
            if invalid:
                ok = False
                actions.append(
                    {
                        "action": "validate_levels",
                        "ok": False,
                        "levels": requested_levels,
                        "invalid": invalid,
                        "min": 25,
                        "max": max_state,
                        "error": "TFN1 validation levels must stay inside tested non-zero range",
                    }
                )
            lower = [level for level in requested_levels if level < max_state]
            if lower and thermal_class in {"hot", "critical"} and not allow_lower:
                ok = False
                actions.append(
                    {
                        "action": "validate_levels",
                        "ok": False,
                        "levels": requested_levels,
                        "refused": lower,
                        "thermal_class": thermal_class,
                        "temperature_c_max": temp_before,
                        "error": "refusing lower-than-max TFN1 levels while system is hot/critical",
                    }
                )
            if ok and write_permission(path):
                ok = False
                permission_required = True
                actions.append({"action": "write_tfn1_cur_state", "ok": False, "path": str(path), "levels": requested_levels, "error": "root permission required"})
            if ok and not permission_required:
                for level in requested_levels:
                    before = dict(temperature_sample_port())
                    since = since_stamp()
                    write_result = dict(write_text(path, f"{level}\n"))
                    samples = [dict(item) for item in sample_series_port(seconds, interval)]
                    all_samples = [before] + samples
                    kernel = dict(kernel_errors_port(since))
                    series = dict(series_summary_port(all_samples))
                    temp_delta = nested_get(series, ["temperature_c_max", "delta"])
                    if write_result.get("ok") and kernel.get("ok"):
                        verdict = "write_path_ok_effect_unproven"
                        if isinstance(temp_delta, (int, float)) and float(temp_delta) <= -2.0:
                            verdict = "write_path_ok_possible_cooling_effect"
                    else:
                        verdict = "write_path_failed_or_kernel_error"
                    action = {
                        "action": "validate_tfn1_level",
                        "ok": bool(write_result.get("ok")) and bool(kernel.get("ok")),
                        "level": level,
                        "write": write_result,
                        "kernel": kernel,
                        "series": series,
                        "samples": all_samples,
                        "verdict": verdict,
                    }
                    actions.append(action)
                    if not action["ok"]:
                        ok = False
                        break

    data = {
        "schema": f"{schema_prefix}_cooling_fan_validate_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": ok,
        "permission_required": permission_required,
        "updated_by": updated_by,
        "candidate": dict(candidate) if isinstance(candidate, Mapping) else None,
        "requested_levels": requested_levels,
        "duration_seconds_per_level": seconds,
        "interval_seconds": interval,
        "allow_lower": allow_lower,
        "status_before": {
            "temperature": status_before.get("temperature", {}).get("summary", {}) if isinstance(status_before.get("temperature"), Mapping) else {},
            "fan": status_before.get("fan", {}),
            "power": status_before.get("power", {}),
        },
        "actions": actions,
        "status_after": {
            "temperature": dict(temperature_summary_port()),
            "fan": dict(fan_status_port()),
            "platform_profile": dict(platform_profile_port()),
        },
        "decision": {
            "production_ready": False,
            "automation_allowed": False,
            "reason": "TFN1 writes can be validated manually, but RPM/readback is unavailable and effective fan response is not yet independently measurable.",
        },
        "paths": dict(paths_port()),
    }
    if permission_required:
        data["pkexec_hint"] = [
            "pkexec",
            "/usr/local/bin/abyss-machine",
            "cooling",
            "fan-validate",
            "--levels",
            ",".join(str(level) for level in requested_levels),
            "--seconds",
            str(seconds),
            "--interval",
            str(interval),
            "--json",
        ]
    return data


def fan_series_document(
    level: int = 50,
    repeats: int = 3,
    seconds: float = 8.0,
    interval: float = 2.0,
    cooldown: float = 5.0,
    state_label: str = "current",
    allow_lower: bool = False,
    *,
    schema_prefix: str,
    version: str,
    updated_by: str,
    now_iso: NowIsoPort,
    status_port: StatusPort,
    fan_validate_port: FanValidateRunPort,
    temperature_summary_port: TemperatureSummaryPort,
    fan_status_port: FanStatusPort,
    platform_profile_port: PlatformProfilePort,
    paths_port: PathsPort,
    sleep: SleepPort = time.sleep,
) -> dict[str, Any]:
    normalized_inputs = cooling_contracts.normalize_fan_series_inputs(
        level=level,
        repeats=repeats,
        seconds=seconds,
        interval=interval,
        cooldown=cooldown,
        state_label=state_label,
    )
    level = normalized_inputs["level"]
    repeats = normalized_inputs["repeats"]
    seconds = normalized_inputs["seconds"]
    interval = normalized_inputs["interval"]
    cooldown = normalized_inputs["cooldown"]
    state_label = normalized_inputs["state_label"]
    status_before = dict(status_port())
    results: list[dict[str, Any]] = []
    ok = True
    permission_required = False

    for index in range(repeats):
        run_data = dict(
            fan_validate_port(
                [level],
                seconds=seconds,
                interval=interval,
                allow_lower=allow_lower,
                updated_by=f"{updated_by}:fan-series:{state_label}:{index + 1}",
            )
        )
        action = next((item for item in run_data.get("actions", []) if isinstance(item, Mapping) and item.get("action") == "validate_tfn1_level"), None)
        compact = {
            "index": index + 1,
            "ok": run_data.get("ok"),
            "permission_required": run_data.get("permission_required"),
            "level": level,
            "generated_at": run_data.get("generated_at"),
            "status_before": run_data.get("status_before", {}).get("temperature", {}) if isinstance(run_data.get("status_before"), Mapping) else {},
            "status_after": run_data.get("status_after", {}).get("temperature", {}) if isinstance(run_data.get("status_after"), Mapping) else {},
            "cpu_hotspot_before": nested_get(run_data, ["status_before", "temperature", "cpu_hotspot"]),
            "cpu_hotspot_after": nested_get(run_data, ["status_after", "temperature", "cpu_hotspot"]),
            "action": {
                "ok": action.get("ok") if isinstance(action, Mapping) else None,
                "verdict": action.get("verdict") if isinstance(action, Mapping) else None,
                "kernel_ok": nested_get(action, ["kernel", "ok"]) if isinstance(action, Mapping) else None,
                "temperature_c_max_delta": nested_get(action, ["series", "temperature_c_max", "delta"]) if isinstance(action, Mapping) else None,
                "temperature_c_max_first": nested_get(action, ["series", "temperature_c_max", "first"]) if isinstance(action, Mapping) else None,
                "temperature_c_max_last": nested_get(action, ["series", "temperature_c_max", "last"]) if isinstance(action, Mapping) else None,
                "temperature_c_max_max": nested_get(action, ["series", "temperature_c_max", "max"]) if isinstance(action, Mapping) else None,
            },
        }
        results.append(
            {
                "summary": compact,
                "data": run_data,
            }
        )
        if run_data.get("permission_required"):
            permission_required = True
        if not run_data.get("ok"):
            ok = False
            break
        if index < repeats - 1 and cooldown > 0:
            sleep(cooldown)

    compact_results = [item["summary"] for item in results]
    series_decision = cooling_contracts.fan_series_decision(
        compact_results=compact_results,
        repeats=repeats,
        permission_required=permission_required,
    )

    data = {
        "schema": f"{schema_prefix}_cooling_fan_series_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": ok,
        "permission_required": permission_required,
        "updated_by": updated_by,
        "state_label": state_label,
        "level": level,
        "repeats": repeats,
        "duration_seconds_per_repeat": seconds,
        "interval_seconds": interval,
        "cooldown_seconds": cooldown,
        "allow_lower": allow_lower,
        "status_before": {
            "temperature": status_before.get("temperature", {}).get("summary", {}) if isinstance(status_before.get("temperature"), Mapping) else {},
            "fan": status_before.get("fan", {}),
            "power": status_before.get("power", {}),
        },
        "summary": series_decision["summary"],
        "decision": series_decision["decision"],
        "results": results,
        "status_after": {
            "temperature": dict(temperature_summary_port()),
            "fan": dict(fan_status_port()),
            "platform_profile": dict(platform_profile_port()),
        },
        "paths": dict(paths_port()),
    }
    if permission_required:
        data["pkexec_hint"] = [
            "pkexec",
            "/usr/local/bin/abyss-machine",
            "cooling",
            "fan-series",
            "--level",
            str(level),
            "--repeats",
            str(repeats),
            "--seconds",
            str(seconds),
            "--interval",
            str(interval),
            "--cooldown",
            str(cooldown),
            "--state-label",
            state_label,
            "--json",
        ]
    return data
