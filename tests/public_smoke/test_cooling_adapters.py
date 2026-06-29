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


def test_rapl_smoothing_apply_disabled_inactive_skips_state_and_live_ports() -> None:
    saved: list[dict[str, Any]] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("port should not be called for disabled inactive smoothing")

    data = cooling_adapters.rapl_smoothing_apply_document(
        "test",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        now_epoch=lambda: 100.0,
        config_port=lambda: {"enabled": False},
        state_port=lambda: {"active": False, "last_package_throttle_count": 3},
        save_state_port=lambda state, updated_by: saved.append(dict(state)) or None,
        fan_status_port=lambda: {"fan_mode": 4},
        mode_state_port=lambda: {"selected_mode": "performance"},
        battery_summary_port=lambda: {"ac_online": True},
        target_profile_port=lambda selected, ac_online: ("performance", "performance", None),
        rapl_status_port=forbidden,
        package_throttle_port=forbidden,
        temperature_summary_port=forbidden,
        paths_refs={"root": "/fake/rapl", "latest": "/fake/latest.json", "state": "/fake/state.json"},
    )

    assert data["action"] == "disabled"
    assert data["write_skipped"] == "disabled_inactive"
    assert data["rapl_mmio"]["skipped"] is True
    assert saved == []


def test_rapl_smoothing_apply_engages_cap_with_fake_ports() -> None:
    writes: list[int] = []
    saved: list[tuple[dict[str, Any], str]] = []

    data = cooling_adapters.rapl_smoothing_apply_document(
        "test",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        now_epoch=lambda: 110.0,
        config_port=lambda: {
            "enabled": True,
            "apply_modes": ["performance"],
            "normal_pl1_uw": 35000000,
            "cap_pl1_uw": 28000000,
            "engage_temperature_c": 100.0,
            "engage_package_throttle_per_s": 100.0,
            "engage_sample_count": 1,
            "release_temperature_c": 90.0,
            "release_package_throttle_per_s": 10.0,
            "release_sample_count": 2,
            "min_sample_seconds": 5.0,
            "max_sample_seconds": 60.0,
        },
        state_port=lambda: {"active": False, "last_sample_epoch": 100.0, "last_package_throttle_count": 100},
        save_state_port=lambda state, updated_by: saved.append((dict(state), updated_by)) or None,
        fan_status_port=lambda: {"fan_mode": 4},
        mode_state_port=lambda: {"selected_mode": "performance"},
        battery_summary_port=lambda: {"ac_online": True},
        target_profile_port=lambda selected, ac_online: ("performance", "performance", None),
        rapl_status_port=lambda: {
            "available": True,
            "pl1_uw": 35000000,
            "paths": {"pl1": "/fake/constraint_0_power_limit_uw"},
        },
        package_throttle_port=lambda: 1300,
        temperature_summary_port=lambda: {
            "class": "hot",
            "temperature_c_max": 106.0,
            "package_temperature_c_max": 104.0,
        },
        write_rapl_port=lambda rapl, target: writes.append(target)
        or {"ok": True, "target_pl1_uw": target, "changed": True},
        paths_refs={"root": "/fake/rapl", "latest": "/fake/latest.json", "state": "/fake/state.json"},
    )

    assert data["action"] == "engage_cap"
    assert data["active"] is True
    assert data["permission_required"] is False
    assert data["throttle"]["package_rate_per_s"] == 120.0
    assert data["write_result"]["target_pl1_uw"] == 28000000
    assert writes == [28000000]
    assert saved[0][0]["active"] is True
    assert saved[0][0]["baseline_pl1_uw"] == 35000000
    assert saved[0][0]["last_action"] == "engage_cap"
    assert saved[0][1] == "test"


def test_rapl_smoothing_apply_restores_active_cap_when_not_applicable() -> None:
    writes: list[int] = []
    saved: list[dict[str, Any]] = []

    data = cooling_adapters.rapl_smoothing_apply_document(
        "test",
        schema_prefix="abyss_machine",
        version="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        now_epoch=lambda: 130.0,
        config_port=lambda: {
            "enabled": True,
            "apply_modes": ["performance"],
            "normal_pl1_uw": 35000000,
            "cap_pl1_uw": 28000000,
            "restore_when_not_applicable": True,
        },
        state_port=lambda: {
            "active": True,
            "baseline_pl1_uw": 35000000,
            "last_sample_epoch": 120.0,
            "last_package_throttle_count": 10,
            "engage_count": 2,
            "release_count": 1,
        },
        save_state_port=lambda state, updated_by: saved.append(dict(state)) or None,
        fan_status_port=lambda: {"fan_mode": 4},
        mode_state_port=lambda: {"selected_mode": "balanced"},
        battery_summary_port=lambda: {"ac_online": True},
        target_profile_port=lambda selected, ac_online: ("balanced", "balanced", None),
        rapl_status_port=lambda: {
            "available": True,
            "pl1_uw": 28000000,
            "paths": {"pl1": "/fake/constraint_0_power_limit_uw"},
        },
        package_throttle_port=lambda: 12,
        temperature_summary_port=lambda: {
            "class": "green",
            "temperature_c_max": 72.0,
            "package_temperature_c_max": 70.0,
        },
        write_rapl_port=lambda rapl, target: writes.append(target)
        or {"ok": True, "target_pl1_uw": target, "changed": True},
        paths_refs={"root": "/fake/rapl", "latest": "/fake/latest.json", "state": "/fake/state.json"},
    )

    assert data["action"] == "restore_not_applicable"
    assert data["active"] is False
    assert data["reasons"] == ["not_applicable"]
    assert writes == [35000000]
    assert saved[0]["active"] is False
    assert saved[0]["engage_count"] == 0
    assert saved[0]["release_count"] == 0


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


def test_apply_cooling_profile_uses_fake_action_ports() -> None:
    calls: list[tuple[str, Any]] = []
    status = {
        "fan": {"fan_mode": 1, "fan_mode_path": "/fake/fan_mode"},
        "power": {"platform_profile": {"current": "balanced", "path": "/fake/platform_profile"}},
        "temperature": {"summary": {"temperature_c_max": 72.0}},
    }

    data = cooling_adapters.apply_cooling_profile(
        "performance",
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        status_port=lambda: status,
        profile_targets_port=lambda profile, status_before: (
            "performance",
            {"platform_profile": "performance", "fan_mode": 4},
            None,
        ),
        rapl_smoothing_apply_port=lambda updated_by: {"ok": True, "action": "skipped"},
        temperature_summary_port=lambda: {"temperature_c_max": 74.0},
        fan_status_port=lambda: {"fan_mode": 1},
        platform_profile_port=lambda: {"current": "balanced"},
        paths_port=lambda: {"latest": "/fake/latest.json"},
        set_platform_profile_port=lambda target, current: calls.append(("platform", target))
        or {"action": "set_platform_profile", "ok": False, "target": target, "error": "root permission required"},
        set_fan_mode_port=lambda target, current: calls.append(("fan", target))
        or {"action": "set_fan_mode", "ok": True, "target": target, "changed": True},
    )

    assert data["schema"] == "abyss_machine_cooling_apply_v1"
    assert data["ok"] is False
    assert data["permission_required"] is True
    assert data["pkexec_hint"] == [
        "pkexec",
        "/usr/local/bin/abyss-machine",
        "cooling",
        "apply",
        "--profile",
        "performance",
        "--json",
    ]
    assert [action["action"] for action in data["actions"]] == ["set_platform_profile", "set_fan_mode"]
    assert calls == [("platform", "performance"), ("fan", 4)]


def test_tfn1_write_document_uses_fake_write_and_kernel_ports() -> None:
    writes: list[tuple[Path, str]] = []
    sleeps: list[float] = []
    candidate = {"path": "/fake/tfn1", "max_state": 100, "type": "TFN1"}

    data = cooling_adapters.tfn1_write_document(
        50,
        1.5,
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        since_stamp=lambda: "2026-06-29 12:00:00",
        status_port=lambda: {"temperature": {"summary": {"temperature_c_max": 70.0}}},
        tfn1_candidate_port=lambda: candidate,
        temperature_summary_port=lambda: {"temperature_c_max": 68.0},
        fan_status_port=lambda: {"fan_mode": 4},
        platform_profile_port=lambda: {"current": "performance"},
        paths_port=lambda: {"actions": {"today": "/fake/actions.jsonl"}},
        write_permission=lambda path: False,
        write_text=lambda path, value: writes.append((path, value))
        or {"ok": True, "path": str(path), "value": value.strip(), "changed": True},
        kernel_errors_port=lambda since, limit=50: {"ok": True, "since": since, "matches": [], "journal_error": ""},
        sleep=lambda seconds: sleeps.append(seconds),
    )

    assert data["ok"] is True
    assert data["requested_level"] == 50
    assert data["actions"][0]["action"] == "write_tfn1_cur_state"
    assert data["actions"][1]["ok"] is True
    assert writes == [(Path("/fake/tfn1/cur_state"), "50\n")]
    assert sleeps == [1.5]


def test_fan_validate_document_refuses_lower_level_while_hot() -> None:
    writes: list[tuple[Path, str]] = []

    data = cooling_adapters.fan_validate_document(
        [50],
        8.0,
        2.0,
        False,
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        since_stamp=lambda: "2026-06-29 12:00:00",
        status_port=lambda: {
            "temperature": {"class": "hot", "summary": {"temperature_c_max": 108.0}},
            "fan": {"fan_mode": 4},
        },
        tfn1_candidate_port=lambda: {"path": "/fake/tfn1", "max_state": 100, "type": "TFN1"},
        temperature_summary_port=lambda: {"temperature_c_max": 108.0},
        temperature_sample_port=lambda: {"summary": {"temperature_c_max": 108.0}},
        sample_series_port=lambda seconds, interval: [],
        fan_status_port=lambda: {"fan_mode": 4},
        platform_profile_port=lambda: {"current": "performance"},
        paths_port=lambda: {"fan_validate": {"latest": "/fake/latest.json"}},
        write_text=lambda path, value: writes.append((path, value)) or {"ok": True},
    )

    assert data["ok"] is False
    assert data["permission_required"] is False
    assert data["actions"][0]["refused"] == [50]
    assert writes == []


def test_fan_validate_document_runs_fake_series() -> None:
    writes: list[tuple[Path, str]] = []

    data = cooling_adapters.fan_validate_document(
        [50],
        1.0,
        0.5,
        True,
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        since_stamp=lambda: "2026-06-29 12:00:00",
        status_port=lambda: {
            "temperature": {"class": "warm", "summary": {"temperature_c_max": 90.0}},
            "fan": {"fan_mode": 4},
        },
        tfn1_candidate_port=lambda: {"path": "/fake/tfn1", "max_state": 100, "type": "TFN1"},
        temperature_summary_port=lambda: {"temperature_c_max": 87.0},
        temperature_sample_port=lambda: {"summary": {"temperature_c_max": 90.0}},
        sample_series_port=lambda seconds, interval: [{"summary": {"temperature_c_max": 87.0}}],
        fan_status_port=lambda: {"fan_mode": 4},
        platform_profile_port=lambda: {"current": "performance"},
        paths_port=lambda: {"fan_validate": {"latest": "/fake/latest.json"}},
        write_permission=lambda path: False,
        write_text=lambda path, value: writes.append((path, value))
        or {"ok": True, "path": str(path), "value": value.strip(), "changed": True},
        kernel_errors_port=lambda since: {"ok": True, "since": since, "matches": [], "journal_error": ""},
    )

    action = data["actions"][0]
    assert data["ok"] is True
    assert action["action"] == "validate_tfn1_level"
    assert action["verdict"] == "write_path_ok_possible_cooling_effect"
    assert action["series"]["temperature_c_max"]["delta"] == -3.0
    assert writes == [(Path("/fake/tfn1/cur_state"), "50\n")]


def test_fan_series_document_uses_fake_validate_port_and_cooldown() -> None:
    sleeps: list[float] = []
    calls: list[str] = []

    def validate(levels: list[int], *, seconds: float, interval: float, allow_lower: bool, updated_by: str) -> dict[str, Any]:
        calls.append(updated_by)
        return {
            "ok": True,
            "permission_required": False,
            "generated_at": "2026-06-29T12:00:00Z",
            "status_before": {"temperature": {"temperature_c_max": 90.0}},
            "status_after": {"temperature": {"temperature_c_max": 87.0}},
            "actions": [
                {
                    "action": "validate_tfn1_level",
                    "ok": True,
                    "kernel": {"ok": True},
                    "series": {"temperature_c_max": {"delta": -3.0, "first": 90.0, "last": 87.0, "max": 90.0}},
                    "verdict": "write_path_ok_possible_cooling_effect",
                }
            ],
        }

    data = cooling_adapters.fan_series_document(
        50,
        2,
        1.0,
        0.5,
        3.0,
        "hot state",
        True,
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-06-29T12:00:00Z",
        status_port=lambda: {"temperature": {"summary": {"temperature_c_max": 90.0}}},
        fan_validate_port=validate,
        temperature_summary_port=lambda: {"temperature_c_max": 87.0},
        fan_status_port=lambda: {"fan_mode": 4},
        platform_profile_port=lambda: {"current": "performance"},
        paths_port=lambda: {"fan_series": {"latest": "/fake/latest.json"}},
        sleep=lambda seconds: sleeps.append(seconds),
    )

    assert data["ok"] is True
    assert data["state_label"] == "hot_state"
    assert data["summary"]["write_ok_count"] == 2
    assert data["decision"]["automation_candidate"] is True
    assert calls == ["test:fan-series:hot_state:1", "test:fan-series:hot_state:2"]
    assert sleeps == [3.0]
