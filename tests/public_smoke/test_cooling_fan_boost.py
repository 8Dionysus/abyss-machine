from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cooling_adapters, cooling_contracts


ENABLED = cooling_contracts.fan_boost_config(
    {"schema": "abyss_machine_cooling_config_v1", "fan_boost": {"enabled": True}}
)

# Tick = (seconds since previous sample, resolved profile, max temperature C,
#         package throttle events per second, CPU busy fraction).
# HEAVY_QUIET / HEAVY_BOOST mirror the 2026-11-21 ProRes render benchmark: the
# same load at fan_mode 1 throttles hard, at fan_mode 4 throttling drops while
# CPU load stays high. Release must follow the load, not the throttle rate.
IDLE = (120.0, "performance", 82.0, 134.0, 0.12)
HEAVY_QUIET = (120.0, "performance", 101.0, 1340.0, 0.85)
HEAVY_BOOST = (120.0, "performance", 99.0, 264.0, 0.85)

Tick = tuple[float, str, float | None, float, float]


def _run(
    ticks: Sequence[Tick],
    *,
    config: dict[str, Any] = ENABLED,
    state: dict[str, Any] | None = None,
    start: float = 1000.0,
) -> tuple[list[tuple[str, int | None]], dict[str, Any], list[dict[str, Any]]]:
    """Feed cumulative counters through fan_boost_decision the way the reconcile timer does."""
    current = dict(state or {})
    now = start
    throttle = 0
    cpu_total = 0
    cpu_idle = 0
    steps: list[tuple[str, int | None]] = []
    decisions: list[dict[str, Any]] = []
    for seconds, profile, temperature, rate, busy in ticks:
        now += seconds
        throttle += int(rate * seconds)
        cpu_total += int(1600 * seconds)
        cpu_idle += int((1.0 - busy) * 1600 * seconds)
        fan, current, decision = cooling_contracts.fan_boost_decision(
            config=config,
            state=current,
            now_epoch=now,
            profile=profile,
            temperature_c=temperature,
            package_throttle_count=throttle,
            cpu_counters=(cpu_total, cpu_idle),
        )
        steps.append((decision["action"], fan))
        decisions.append(decision)
    return steps, current, decisions


def _at(tick: Tick, seconds: float) -> Tick:
    return (seconds, *tick[1:])


def test_fan_boost_config_defaults_disabled_and_merges_overrides() -> None:
    defaults = cooling_contracts.default_config("abyss_machine", "test")["fan_boost"]
    assert defaults["enabled"] is False
    assert defaults["apply_profiles"] == ["performance"]
    assert defaults["boost_fan_mode"] == 4

    merged = cooling_contracts.fan_boost_config(
        {"schema": "abyss_machine_cooling_config_v1", "fan_boost": {"enabled": True, "engage_temperature_c": 102.0}}
    )
    assert merged["enabled"] is True
    assert merged["engage_temperature_c"] == 102.0
    assert merged["release_temperature_c"] == 95.0
    assert merged["min_boost_seconds"] == 300.0

    malformed = cooling_contracts.fan_boost_config({"fan_boost": "on"})
    assert malformed == defaults

    steps, state, _ = _run([HEAVY_QUIET] * 4, config=defaults)
    assert steps == [("disabled", None)] * 4
    assert state["active"] is False


def test_sustained_heat_engages_holds_through_lower_throttle_and_releases_on_idle() -> None:
    steps, state, decisions = _run(
        [IDLE, HEAVY_QUIET, HEAVY_QUIET, HEAVY_BOOST, HEAVY_BOOST, HEAVY_BOOST, IDLE, IDLE, IDLE]
    )

    assert steps == [
        ("sample_seed", None),
        ("quiet_ready", None),
        ("engage_boost", 4),
        # Boosted fan cuts throttle to ~264/s, far below the 800/s engage gate,
        # but the render is still running, so the boost must hold (no flapping).
        ("hold_boost", 4),
        ("hold_boost", 4),
        ("hold_boost", 4),
        ("hold_boost", 4),
        ("release_boost", None),
        ("quiet", None),
    ]
    assert decisions[1]["sample"]["package_throttle_per_s"] == 1340.0
    assert decisions[3]["sample"]["cpu_busy_fraction"] == 0.85
    assert decisions[6]["release_count"] == 1
    assert state["active"] is False
    assert state["boost_since_epoch"] is None


def test_short_burst_never_engages() -> None:
    steps, state, _ = _run([IDLE, IDLE, HEAVY_QUIET, IDLE, IDLE])

    assert steps == [
        ("sample_seed", None),
        ("quiet", None),
        ("quiet_ready", None),
        ("quiet", None),
        ("quiet", None),
    ]
    assert state["engage_count"] == 0
    assert state["active"] is False


def test_release_waits_for_min_boost_hold() -> None:
    heavy = _at(HEAVY_QUIET, 60.0)
    idle = _at(IDLE, 60.0)
    steps, state, decisions = _run([idle, heavy, heavy, idle, idle, idle, idle, idle])

    assert steps[:3] == [("sample_seed", None), ("quiet_ready", None), ("engage_boost", 4)]
    # Load ended right away: release samples accumulate, but the boost holds
    # until 300 s have passed since it engaged (engaged at t=1180).
    assert steps[3:7] == [("hold_boost", 4)] * 4
    assert [item["release_count"] for item in decisions[3:7]] == [1, 2, 3, 4]
    assert steps[7] == ("release_boost", None)
    assert state["active"] is False


def test_emergency_hands_off_and_boost_holds_after_recovery_until_load_ends() -> None:
    emergency = (120.0, "emergency", 107.0, 2000.0, 0.9)
    recovered_hot = (120.0, "performance", 97.0, 300.0, 0.9)
    steps, state, decisions = _run([IDLE, emergency, recovered_hot, HEAVY_BOOST, IDLE, IDLE, IDLE])

    assert steps == [
        ("sample_seed", None),
        # Emergency profile already forces fan_mode 4; no override, but boost is armed.
        ("emergency_handoff", None),
        ("hold_boost", 4),
        ("hold_boost", 4),
        ("hold_boost", 4),
        ("release_boost", None),
        ("quiet", None),
    ]
    assert decisions[1]["active"] is True
    assert state["active"] is False

    _, armed, _ = _run([IDLE, emergency])
    assert armed["boost_since_epoch"] == 1240.0
    _, still_armed, _ = _run([_at(emergency, 120.0)], state=armed, start=1240.0)
    assert still_armed["boost_since_epoch"] == 1240.0


def test_close_manual_applies_keep_the_sample_window_open() -> None:
    manual = _at(HEAVY_QUIET, 2.0)
    steps, state, _ = _run([IDLE, HEAVY_QUIET, manual, HEAVY_QUIET, HEAVY_BOOST])

    assert steps == [
        ("sample_seed", None),
        ("quiet_ready", None),
        # A manual apply 2 s after the timer tick neither advances nor resets the
        # engage counter; the next timer tick measures across the full window.
        ("window_open_quiet", None),
        ("engage_boost", 4),
        ("hold_boost", 4),
    ]
    assert state["active"] is True

    before = dict(state)
    held_steps, after, _ = _run([_at(HEAVY_BOOST, 1.0)], state=state, start=float(state["last_sample_epoch"]))
    assert held_steps == [("window_open_hold", 4)]
    assert after["last_sample_epoch"] == before["last_sample_epoch"]
    assert after["release_count"] == before["release_count"]


def test_profile_switch_releases_boost_and_resets_counters() -> None:
    balanced_hot = (120.0, "balanced", 101.0, 1340.0, 0.9)
    steps, state, _ = _run(
        [IDLE, HEAVY_QUIET, HEAVY_QUIET, balanced_hot, balanced_hot, HEAVY_QUIET, HEAVY_QUIET]
    )

    assert steps == [
        ("sample_seed", None),
        ("quiet_ready", None),
        ("engage_boost", 4),
        ("released_not_applicable", None),
        ("not_applicable", None),
        # Back in performance the engage evidence starts over from one sample.
        ("quiet_ready", None),
        ("engage_boost", 4),
    ]
    assert state["active"] is True

    only_balanced, _, _ = _run([balanced_hot] * 3)
    assert only_balanced == [("not_applicable", None)] * 3


def test_missing_temperature_or_stale_samples_stay_quiet() -> None:
    no_sensor = (120.0, "performance", None, 1340.0, 0.9)
    steps, _, _ = _run([no_sensor] * 3)
    assert steps == [("sample_seed", None), ("quiet", None), ("quiet", None)]

    after_suspend = _at(HEAVY_QUIET, 900.0)
    steps, state, decisions = _run([IDLE, HEAVY_QUIET, after_suspend, HEAVY_QUIET])
    assert steps == [
        ("sample_seed", None),
        ("quiet_ready", None),
        # A gap longer than max_sample_seconds reseeds instead of averaging
        # throttle over the suspend window.
        ("sample_seed", None),
        ("quiet_ready", None),
    ]
    assert decisions[2]["sample"]["package_throttle_per_s"] is None
    assert state["engage_count"] == 1


def _apply_with_boost(
    profile: str,
    boost_decision: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    calls: list[tuple[str, Any]] = []

    def fan_boost_port(normalized: str) -> dict[str, Any]:
        calls.append(("boost", normalized))
        return dict(boost_decision or {})

    data = cooling_adapters.apply_cooling_profile(
        profile,
        schema_prefix="abyss_machine",
        version="test",
        updated_by="test",
        now_iso=lambda: "2026-11-21T12:00:00Z",
        status_port=lambda: {
            "fan": {"fan_mode": 1, "fan_mode_path": "/fake/fan_mode"},
            "power": {"platform_profile": {"current": "performance", "path": "/fake/platform_profile"}},
        },
        profile_targets_port=lambda requested, status_before: (
            "performance",
            {"platform_profile": "performance", "fan_mode": 1},
            {"recommended_profile": "performance"} if requested == "auto" else None,
        ),
        rapl_smoothing_apply_port=lambda updated_by: calls.append(("rapl", updated_by))
        or {"ok": True, "action": "not_applicable"},
        temperature_summary_port=lambda: {"temperature_c_max": 101.0},
        fan_status_port=lambda: {"fan_mode": 4},
        platform_profile_port=lambda: {"current": "performance"},
        paths_port=lambda: {"latest": "/fake/latest.json"},
        set_platform_profile_port=lambda target, current: calls.append(("platform", target))
        or {"action": "set_platform_profile", "ok": True, "target": target, "changed": False},
        set_fan_mode_port=lambda target, current: calls.append(("fan", target))
        or {"action": "set_fan_mode", "ok": True, "target": target, "changed": True},
        fan_boost_port=fan_boost_port if boost_decision is not None else None,
    )
    return data, calls


def test_apply_cooling_profile_auto_applies_fan_boost_override_before_rapl() -> None:
    data, calls = _apply_with_boost("auto", {"action": "engage_boost", "active": True, "fan_mode_override": 4})

    assert calls == [("boost", "performance"), ("platform", "performance"), ("fan", 4), ("rapl", "test")]
    assert [action["action"] for action in data["actions"]] == [
        "set_platform_profile",
        "fan_boost",
        "set_fan_mode",
        "rapl_smoothing",
    ]
    boost_action = data["actions"][1]
    assert boost_action["ok"] is True
    assert boost_action["decision"]["action"] == "engage_boost"
    assert data["applied_profile"] == "performance"


def test_apply_cooling_profile_auto_without_override_keeps_quiet_profile_fan() -> None:
    _, calls = _apply_with_boost("auto", {"action": "quiet", "active": False, "fan_mode_override": None})
    assert ("fan", 1) in calls
    assert ("fan", 4) not in calls


def test_apply_cooling_profile_manual_profile_does_not_consult_fan_boost() -> None:
    data, calls = _apply_with_boost("performance", {"action": "engage_boost", "fan_mode_override": 4})
    assert ("boost", "performance") not in calls
    assert ("fan", 1) in calls
    assert "fan_boost" not in [action["action"] for action in data["actions"]]


def test_cli_fan_boost_decide_persists_state_latest_and_daily_log(tmp_path: Path, monkeypatch: Any) -> None:
    from abyss_machine import cli

    root = tmp_path / "fan-boost"
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_ROOT", root)
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_LATEST_PATH", root / "latest.json")
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_STATE_PATH", root / "state.json")
    config: dict[str, Any] = {"schema": "abyss_machine_cooling_config_v1", "fan_boost": {"enabled": True}}
    monkeypatch.setattr(cli, "cooling_config", lambda: config)
    monkeypatch.setattr(cli, "cooling_temperature_summary", lambda: {"temperature_c_max": 101.0})
    clock = {"now": 1000.0, "throttle": 0, "cpu": (0, 0)}
    monkeypatch.setattr(cli.time, "time", lambda: clock["now"])
    monkeypatch.setattr(cli, "cooling_package_throttle_count", lambda: clock["throttle"])
    monkeypatch.setattr(cli, "cooling_cpu_counters", lambda: clock["cpu"])

    first = cli.cooling_fan_boost_decide("performance", updated_by="test")
    clock.update(now=1120.0, throttle=1340 * 120, cpu=(192000, 28800))
    second = cli.cooling_fan_boost_decide("performance", updated_by="test")

    assert first["action"] == "sample_seed"
    assert second["action"] == "quiet_ready"
    assert second["schema"] == "abyss_machine_cooling_fan_boost_v1"
    assert second["enabled"] is True
    assert "write_errors" not in second
    latest = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    assert latest["action"] == "quiet_ready"
    state_doc = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state_doc["schema"] == "abyss_machine_cooling_fan_boost_state_v1"
    assert state_doc["state"]["engage_count"] == 1
    assert state_doc["state"]["last_sample_epoch"] == 1120.0
    daily = sorted(root.rglob("*.jsonl"))
    assert len(daily) == 1
    assert [json.loads(line)["action"] for line in daily[0].read_text(encoding="utf-8").splitlines()] == [
        "sample_seed",
        "quiet_ready",
    ]

    config["fan_boost"] = {"enabled": False}
    clock.update(now=1240.0)
    disabled = cli.cooling_fan_boost_decide("performance", updated_by="test")
    assert disabled["action"] == "disabled"
    assert json.loads((root / "latest.json").read_text(encoding="utf-8"))["action"] == "disabled"
    assert len(daily[0].read_text(encoding="utf-8").splitlines()) == 2


def test_cli_fan_boost_decide_publishes_nothing_when_state_write_fails(tmp_path: Path, monkeypatch: Any) -> None:
    """A caller that cannot persist state (non-root `mode set`) must not leave a phantom history row."""
    from abyss_machine import cli

    root = tmp_path / "fan-boost"
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_ROOT", root)
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_LATEST_PATH", root / "latest.json")
    monkeypatch.setattr(cli, "COOLING_FAN_BOOST_STATE_PATH", root / "state.json")
    config: dict[str, Any] = {"schema": "abyss_machine_cooling_config_v1", "fan_boost": {"enabled": True}}
    monkeypatch.setattr(cli, "cooling_config", lambda: config)
    monkeypatch.setattr(cli, "cooling_temperature_summary", lambda: {"temperature_c_max": 101.0})
    clock = {"now": 1000.0, "throttle": 0, "cpu": (0, 0)}
    monkeypatch.setattr(cli.time, "time", lambda: clock["now"])
    monkeypatch.setattr(cli, "cooling_package_throttle_count", lambda: clock["throttle"])
    monkeypatch.setattr(cli, "cooling_cpu_counters", lambda: clock["cpu"])
    assert cli.cooling_fan_boost_decide("performance", updated_by="reconcile")["action"] == "sample_seed"

    real_write = cli.safe_atomic_write_json
    denied = {"path": str(root / "state.json"), "error": "[Errno 13] Permission denied"}

    def state_dir_not_writable(path: Path, data: dict[str, Any], mode: int = 0o664) -> dict[str, Any] | None:
        return dict(denied) if path == root / "state.json" else real_write(path, data, mode)

    monkeypatch.setattr(cli, "safe_atomic_write_json", state_dir_not_writable)
    clock.update(now=1120.0, throttle=1340 * 120, cpu=(192000, 28800))
    phantom = cli.cooling_fan_boost_decide("performance", updated_by="set:performance")

    assert phantom["action"] == "quiet_ready"
    assert phantom["write_skipped"] == "state_write_failed"
    assert phantom["write_errors"] == [denied]
    assert json.loads((root / "latest.json").read_text(encoding="utf-8"))["action"] == "sample_seed"
    state_doc = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state_doc["state"]["last_sample_epoch"] == 1000.0
    daily = sorted(root.rglob("*.jsonl"))
    assert [json.loads(line)["updated_by"] for line in daily[0].read_text(encoding="utf-8").splitlines()] == [
        "reconcile"
    ]

    # The next persisted tick recomputes from the last state it actually stored.
    monkeypatch.setattr(cli, "safe_atomic_write_json", real_write)
    clock.update(now=1180.0, throttle=1340 * 180, cpu=(288000, 43200))
    recomputed = cli.cooling_fan_boost_decide("performance", updated_by="reconcile")
    assert recomputed["action"] == "quiet_ready"
    assert "write_skipped" not in recomputed
    assert json.loads((root / "state.json").read_text(encoding="utf-8"))["state"]["engage_count"] == 1
    assert [json.loads(line)["action"] for line in daily[0].read_text(encoding="utf-8").splitlines()] == [
        "sample_seed",
        "quiet_ready",
    ]


def test_cli_cpu_counters_reads_aggregate_proc_stat_line() -> None:
    from abyss_machine import cli

    counters = cli.cooling_cpu_counters()
    if not Path("/proc/stat").exists():
        assert counters is None
        return
    assert counters is not None
    total, idle = counters
    assert total >= idle >= 0
