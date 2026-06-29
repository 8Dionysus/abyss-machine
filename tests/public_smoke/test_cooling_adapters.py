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


def test_thermal_zones_use_fake_sysfs_ports() -> None:
    root = Path("/fake/sys/class/thermal")
    zone0 = root / "thermal_zone0"
    zone1 = root / "thermal_zone1"
    values = {
        zone0 / "type": "TCPU",
        zone0 / "temp": 88500,
        zone0 / "trip_point_0_temp": 95000,
        zone0 / "trip_point_0_type": "passive",
        zone1 / "type": "BAT1",
        zone1 / "temp": 42000,
    }

    zones = cooling_adapters.thermal_zones(
        root=root,
        glob_paths=lambda base, pattern: {
            (root, "thermal_zone*"): [zone1, zone0],
            (zone0, "trip_point_*_temp"): [zone0 / "trip_point_0_temp"],
            (zone1, "trip_point_*_temp"): [],
        }.get((base, pattern), []),
        read_text_value=lambda path: values.get(path) if isinstance(values.get(path), str) else None,
        read_int_value=lambda path: values.get(path) if isinstance(values.get(path), int) else None,
    )

    assert zones[0]["name"] == "thermal_zone0"
    assert zones[0]["temperature_c"] == 88.5
    assert zones[0]["trips"] == [{"index": 0, "type": "passive", "temperature_c": 95.0}]
    assert zones[1]["type"] == "BAT1"


def test_cooling_devices_project_fan_tfn_and_blocked_acpi_with_fake_ports() -> None:
    root = Path("/fake/sys/class/thermal")
    fan = root / "cooling_device0"
    tfn = root / "cooling_device1"
    blocked = root / "cooling_device2"
    metadata = {
        fan: {"acpi_device": "FANX", "acpi_path": r"\_SB_.FANX"},
        tfn: {"acpi_device": "TFN1", "acpi_path": r"\_SB_.IETM.TFN1"},
        blocked: {"acpi_device": "FAN0", "acpi_path": r"\_TZ_.FAN0"},
    }
    text_values = {
        fan / "type": "Fan",
        tfn / "type": "TFN1",
        blocked / "type": "Fan",
    }
    int_values = {
        fan / "max_state": 5,
        tfn / "max_state": 100,
        blocked / "max_state": 1,
    }

    devices = cooling_adapters.cooling_devices(
        root=root,
        broken_acpi_paths={r"\_TZ_.FAN0"},
        glob_paths=lambda base, pattern: [fan, tfn, blocked] if (base, pattern) == (root, "cooling_device*") else [],
        read_text_value=lambda path: text_values.get(path),
        read_int_value=lambda path: int_values.get(path),
        read_result=lambda path: {"ok": True, "path": str(path), "value": "3"},
        metadata_port=lambda device, **kwargs: metadata[device],
        performance_states_port=lambda acpi_device, **kwargs: [{"index": 0, "raw": f"{acpi_device}:state"}],
    )

    assert devices[0]["cur_state"] == "3"
    assert devices[1]["control_policy"] == "candidate_write_only_manual_guard_required"
    assert devices[1]["performance_states"] == [{"index": 0, "raw": "TFN1:state"}]
    assert devices[2]["read_error"] == "skipped_broken_acpi_cooling_device_on_this_bios"
    assert cooling_adapters.tfn1_candidate(lambda: devices) == devices[1]


def test_temperature_summary_and_sample_use_fake_live_ports() -> None:
    hwmon = {
        "readings": [
            {"adapter": "coretemp", "label": "Package id 0", "temperature_c": 94.0, "path": "/fake/package"},
            {"adapter": "coretemp", "label": "Core 0", "temperature_c": 107.2, "path": "/fake/core0"},
            {"adapter": "coretemp", "label": "Core 1", "temperature_c": 72.0, "path": "/fake/core1"},
            {"adapter": "nvme", "label": "Composite", "temperature_c": 43.0, "path": "/fake/nvme"},
        ],
        "skipped": [{"path": "/fake/bad"}],
    }
    zones = [
        {"type": "TCPU", "path": "/fake/tcpu", "name": "thermal_zone0", "temperature_c": 101.0, "trips": []},
        {"type": "wifi", "path": "/fake/wifi", "name": "thermal_zone1", "temperature_c": 44.0, "trips": []},
    ]

    summary = cooling_adapters.temperature_summary(
        hwmon_readings=lambda: hwmon,
        cooling_config=lambda: {"auto": {"hot_temperature_c": 106.0, "critical_temperature_c": 109.0, "recovery_temperature_c": 96.0}},
        thermal_zones_port=lambda: zones,
    )
    sample = cooling_adapters.temperature_sample(
        temperature_summary_port=lambda: summary,
        fan_status=lambda: {"fan_mode": 4},
        platform_profile_status=lambda: {"current": "performance"},
        battery_summary=lambda: {"ac_online": True},
        now_iso=lambda: "2026-06-29T12:00:00Z",
    )

    assert summary["class"] == "hot"
    assert summary["temperature_c_max"] == 107.2
    assert summary["thermal_zone_temperature_c_max"] == 101.0
    assert summary["cpu_hotspot"]["distribution"] == "localized_hot_core_hotspot"
    assert summary["cpu_hotspot"]["hot_core_labels"] == ["Core 0"]
    assert sample["summary"]["hwmon_temperature_c_max"] == 107.2
    assert sample["trusted_sensor_map"]["cpu_hwmon"][0]["role"] == "cpu_package_temperature"
    assert sample["trusted_sensor_map"]["component_hwmon"][0]["role"] == "component_temperature"
    assert sample["trusted_sensor_map"]["blocked"]["fan_cur_state"].startswith("blocked")


def test_sample_series_and_summary_use_fake_clock_and_sleep() -> None:
    samples = [
        {"summary": {"class": "warm", "temperature_c_max": 90.0, "package_temperature_c_max": 88.0}},
        {"summary": {"class": "hot", "temperature_c_max": 96.0, "package_temperature_c_max": 94.0}},
    ]
    monotonic_values = iter([0.0, 0.0, 0.6, 1.1])
    sleep_calls: list[float] = []
    sample_calls = 0

    def temperature_sample() -> dict[str, Any]:
        nonlocal sample_calls
        item = samples[min(sample_calls, len(samples) - 1)]
        sample_calls += 1
        return item

    series = cooling_adapters.sample_series(
        1.0,
        0.5,
        temperature_sample_port=temperature_sample,
        monotonic=lambda: next(monotonic_values),
        sleep=lambda value: sleep_calls.append(round(value, 1)),
    )
    summary = cooling_adapters.series_summary(series)

    assert len(series) == 2
    assert sleep_calls == [0.4]
    assert summary["samples"] == 2
    assert summary["classes"] == ["hot", "warm"]
    assert summary["temperature_c_max"]["delta"] == 6.0
