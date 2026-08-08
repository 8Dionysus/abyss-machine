from __future__ import annotations

import os
from pathlib import Path
import select
import time
from typing import Any, Mapping


class PressureTrigger:
    def __init__(
        self,
        path: Path = Path("/proc/pressure/memory"),
        trigger: bytes = b"some 200000 2000000\0",
    ) -> None:
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        os.write(self.fd, trigger)
        self.poller = select.poll()
        self.poller.register(self.fd, select.POLLPRI)

    def event_pending(self) -> bool:
        return bool(self.poller.poll(0))

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


class MemoryCoordinator:
    def __init__(self, *, check_interval_sec: float = 30.0, recovery_cooldown_sec: float = 30.0) -> None:
        self.check_interval_sec = max(5.0, float(check_interval_sec))
        self.recovery_cooldown_sec = max(1.0, float(recovery_cooldown_sec))
        self.state = "NORMAL"
        self.last_checked_epoch: float | None = None
        self.next_check_epoch = 0.0
        self.recovery_until_epoch = 0.0
        self.last_facts: dict[str, Any] = {}
        self.last_action: dict[str, Any] | None = None
        self.psi_trigger_available = True

    def due(self, *, now_epoch: float, pressure_event: bool) -> bool:
        return pressure_event or now_epoch >= self.next_check_epoch

    def observe(
        self,
        facts: Mapping[str, Any],
        *,
        memory_class: str,
        pressure_event: bool,
        now_epoch: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if now_epoch is None else float(now_epoch)
        reserve_state = str(facts.get("swap_reserve_state") or "unavailable")
        try:
            psi_some = float(facts.get("psi_some_avg10") or 0.0)
            psi_full = float(facts.get("psi_full_avg10") or 0.0)
        except (TypeError, ValueError):
            psi_some = 0.0
            psi_full = 0.0
        active_stall = bool(pressure_event or memory_class in {"hot", "critical"} or psi_some >= 8.0 or psi_full >= 2.0)
        if now < self.recovery_until_epoch:
            state = "RECOVERY_COOLDOWN"
        elif active_stall:
            state = "ACTIVE_STALL"
        elif reserve_state == "below_target":
            state = "RESERVE_LOW"
        else:
            state = "NORMAL"
        self.state = state
        self.last_checked_epoch = now
        self.next_check_epoch = now + self.check_interval_sec
        self.last_facts = {
            "memory_class": memory_class,
            "swap_reserve_state": reserve_state,
            "swap_free_mib": facts.get("swap_free_mib"),
            "target_swap_free_mib": facts.get("target_swap_free_mib"),
            "swap_free_shortfall_mib": facts.get("swap_free_shortfall_mib"),
            "mem_available_mib": facts.get("mem_available_mib"),
            "psi_some_avg10": psi_some,
            "psi_full_avg10": psi_full,
            "pressure_event": bool(pressure_event),
        }
        return self.status()

    def relief_needed_mib(self) -> float:
        try:
            shortfall = max(0.0, float(self.last_facts.get("swap_free_shortfall_mib") or 0.0))
        except (TypeError, ValueError):
            shortfall = 0.0
        return round(max(shortfall, 512.0 if self.state == "ACTIVE_STALL" else 0.0), 3)

    def relief_allowed(self) -> bool:
        return self.state in {"RESERVE_LOW", "ACTIVE_STALL"} and self.relief_needed_mib() > 0.0

    def record_action(self, receipt: Mapping[str, Any], *, now_epoch: float | None = None) -> None:
        now = time.time() if now_epoch is None else float(now_epoch)
        self.last_action = {
            "at_epoch": round(now, 3),
            "ok": receipt.get("ok"),
            "action_executed": receipt.get("action_executed"),
            "adapter_id": receipt.get("adapter_id"),
            "owner": receipt.get("owner"),
            "workload_id": receipt.get("workload_id"),
            "action_id": receipt.get("action_id"),
        }
        if receipt.get("action_executed") is True:
            self.recovery_until_epoch = now + self.recovery_cooldown_sec
            self.state = "RECOVERY_COOLDOWN"

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "last_checked_epoch": self.last_checked_epoch,
            "next_check_epoch": self.next_check_epoch,
            "recovery_until_epoch": self.recovery_until_epoch,
            "psi_trigger_available": self.psi_trigger_available,
            "facts": dict(self.last_facts),
            "last_action": None if self.last_action is None else dict(self.last_action),
            "persistent_state_bytes": 0,
        }
