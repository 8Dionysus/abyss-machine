from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import resource_pressure_coordinator


def facts(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "swap_reserve_state": "within_target",
        "swap_free_mib": 4096,
        "target_swap_free_mib": 2048,
        "swap_free_shortfall_mib": 0,
        "mem_available_mib": 8192,
        "psi_some_avg10": 0.0,
        "psi_full_avg10": 0.0,
    }
    document.update(overrides)
    return document


def test_memory_coordinator_transitions_without_persistent_state() -> None:
    coordinator = resource_pressure_coordinator.MemoryCoordinator(
        check_interval_sec=30,
        recovery_cooldown_sec=20,
    )

    normal = coordinator.observe(facts(), memory_class="green", pressure_event=False, now_epoch=100)
    reserve_low = coordinator.observe(
        facts(swap_reserve_state="below_target", swap_free_shortfall_mib=640),
        memory_class="green",
        pressure_event=False,
        now_epoch=130,
    )
    active_stall = coordinator.observe(
        facts(),
        memory_class="green",
        pressure_event=True,
        now_epoch=160,
    )
    coordinator.record_action(
        {"ok": True, "action_executed": True, "adapter_id": "reranker", "action_id": "abc"},
        now_epoch=160,
    )
    cooldown = coordinator.status()
    recovered = coordinator.observe(facts(), memory_class="green", pressure_event=False, now_epoch=181)

    assert normal["state"] == "NORMAL"
    assert reserve_low["state"] == "RESERVE_LOW"
    assert active_stall["state"] == "ACTIVE_STALL"
    assert cooldown["state"] == "RECOVERY_COOLDOWN"
    assert recovered["state"] == "NORMAL"
    assert recovered["persistent_state_bytes"] == 0


def test_memory_coordinator_relief_is_exactly_shortfall_or_stall_floor() -> None:
    coordinator = resource_pressure_coordinator.MemoryCoordinator()
    coordinator.observe(
        facts(swap_reserve_state="below_target", swap_free_shortfall_mib=768),
        memory_class="green",
        pressure_event=False,
        now_epoch=100,
    )
    assert coordinator.relief_allowed() is True
    assert coordinator.relief_needed_mib() == 768.0

    coordinator.observe(facts(), memory_class="green", pressure_event=True, now_epoch=130)
    assert coordinator.relief_needed_mib() == 512.0


def test_memory_coordinator_poll_schedule_reacts_immediately_to_pressure() -> None:
    coordinator = resource_pressure_coordinator.MemoryCoordinator(check_interval_sec=30)
    coordinator.observe(facts(), memory_class="green", pressure_event=False, now_epoch=100)

    assert coordinator.due(now_epoch=110, pressure_event=False) is False
    assert coordinator.due(now_epoch=110, pressure_event=True) is True
    assert coordinator.due(now_epoch=130, pressure_event=False) is True
