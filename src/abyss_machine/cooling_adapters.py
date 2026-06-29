from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
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
