from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cooling_adapters


def test_platform_profile_status_and_set_use_fake_ports() -> None:
    profile_path = Path("/fake/sys/firmware/acpi/platform_profile")
    choices_path = Path("/fake/sys/firmware/acpi/platform_profile_choices")
    writes: list[tuple[Path, str]] = []

    status = cooling_adapters.platform_profile_status(
        profile_path=profile_path,
        choices_path=choices_path,
        exists=lambda path: path == profile_path,
        read_result=lambda path: {"ok": True, "path": str(path), "value": "balanced"},
        read_text_value=lambda path: "low-power balanced performance" if path == choices_path else None,
        access=lambda path, mode: False,
    )
    permission = cooling_adapters.set_platform_profile(
        "performance",
        status,
        euid=lambda: 1000,
        access=lambda path, mode: False,
        write_text=lambda path, value: writes.append((path, value)) or {"ok": True},
    )
    applied = cooling_adapters.set_platform_profile(
        "performance",
        status,
        euid=lambda: 0,
        access=lambda path, mode: False,
        write_text=lambda path, value: writes.append((path, value))
        or {"ok": True, "path": str(path), "value": value.strip(), "changed": True},
    )

    assert status["available"] is True
    assert status["current"] == "balanced"
    assert status["choices"] == ["low-power", "balanced", "performance"]
    assert permission == {
        "action": "set_platform_profile",
        "ok": False,
        "target": "performance",
        "error": "root permission required",
    }
    assert applied["ok"] is True
    assert applied["action"] == "set_platform_profile"
    assert writes == [(profile_path, "performance\n")]


def test_lenovo_fan_status_and_set_use_fake_ports() -> None:
    vpc = Path("/fake/sys/devices/platform/VPC2004:00")
    writes: list[tuple[Path, str]] = []

    status = cooling_adapters.lenovo_fan_status(
        mode_labels={0: "super silent", 1: "standard", 4: "efficient thermal dissipation"},
        find_vpc=lambda: vpc,
        read_result=lambda path: {"ok": True, "path": str(path), "value": "1"},
        access=lambda path, mode: True,
    )
    noop = cooling_adapters.set_lenovo_fan_mode(1, status)
    invalid = cooling_adapters.set_lenovo_fan_mode("bad", status)
    applied = cooling_adapters.set_lenovo_fan_mode(
        4,
        status,
        euid=lambda: 0,
        access=lambda path, mode: False,
        write_text=lambda path, value: writes.append((path, value))
        or {"ok": True, "path": str(path), "value": value.strip(), "changed": True},
    )

    assert status["available"] is True
    assert status["fan_mode_path"] == str(vpc / "fan_mode")
    assert status["fan_mode"] == 1
    assert status["fan_mode_label"] == "standard"
    assert noop == {"action": "set_fan_mode", "ok": True, "changed": False, "target": 1}
    assert invalid == {"action": "set_fan_mode", "ok": False, "target": "bad", "error": "invalid fan_mode target"}
    assert applied["ok"] is True
    assert applied["target"] == 4
    assert writes == [(vpc / "fan_mode", "4\n")]


def test_lenovo_vpc_discovery_requires_fan_mode_backend() -> None:
    missing = Path("/fake/VPC2004:missing")
    present = Path("/fake/VPC2004:present")

    discovered = cooling_adapters.find_lenovo_vpc(
        glob_paths=lambda root, pattern: [missing, present] if pattern == "VPC2004:*" else [],
        exists=lambda path: path == present / "fan_mode",
    )

    assert discovered == present


def test_rapl_status_write_and_throttle_count_use_fake_ports() -> None:
    root = Path("/fake/sys/devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0")
    values = {
        root / "constraint_0_power_limit_uw": 35000000,
        root / "constraint_0_time_window_us": 28000000,
        root / "constraint_1_power_limit_uw": 64000000,
        root / "constraint_1_time_window_us": 2440,
    }
    writes: list[tuple[Path, str]] = []

    status = cooling_adapters.rapl_mmio_status(
        root=root,
        read_int_value=lambda path: values.get(path),
        access=lambda path, mode: path.name == "constraint_0_power_limit_uw",
    )
    permission = cooling_adapters.write_rapl_pl1(
        status,
        28000000,
        euid=lambda: 1000,
        access=lambda path, mode: False,
    )
    applied = cooling_adapters.write_rapl_pl1(
        status,
        28000000,
        euid=lambda: 0,
        access=lambda path, mode: False,
        write_text=lambda path, value: writes.append((path, value))
        or {"ok": True, "path": str(path), "value": value.strip(), "changed": True},
    )
    throttle = cooling_adapters.package_throttle_count(
        root=Path("/fake/sys/devices/system/cpu"),
        glob_paths=lambda root_path, pattern: [
            root_path / "cpu0/thermal_throttle/package_throttle_count",
            root_path / "cpu1/thermal_throttle/package_throttle_count",
        ],
        read_int_value=lambda path: 7 if "cpu0" in str(path) else 11,
    )

    assert status["available"] is True
    assert status["pl1_uw"] == 35000000
    assert status["pl2_uw"] == 64000000
    assert permission["permission_required"] is True
    assert permission["pkexec_hint"][-2:] == ["--apply", "--json"]
    assert applied["ok"] is True
    assert applied["target_pl1_uw"] == 28000000
    assert writes == [(root / "constraint_0_power_limit_uw", "28000000\n")]
    assert throttle == 18


def test_kernel_fan_errors_filter_journal_through_fake_runner() -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(command: Sequence[str], timeout: float) -> dict[str, Any]:
        calls.append((list(command), timeout))
        return {
            "ok": True,
            "returncode": 0,
            "stdout": "noise\nACPI BIOS Error: broken\nTFN1 _FSL failed\n",
            "stderr": "",
        }

    data = cooling_adapters.kernel_fan_errors(
        "2026-06-29 12:00:00",
        limit=1,
        command_exists=lambda name: name == "journalctl",
        runner=runner,
    )
    missing = cooling_adapters.kernel_fan_errors(
        "2026-06-29 12:00:00",
        command_exists=lambda name: False,
        runner=runner,
    )

    assert data["ok"] is False
    assert data["matches"] == ["TFN1 _FSL failed"]
    assert calls == [
        (
            ["journalctl", "-k", "-b", "--since", "2026-06-29 12:00:00", "--no-pager"],
            4.0,
        )
    ]
    assert missing["journal_error"] == "journalctl not found"
