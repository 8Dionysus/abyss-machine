from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.regression]


def pressure_inputs(*, mem_available: float, swap_used: float, swap_free_mib: float, zram: bool, psi_some: float, psi_full: float):
    mem = {"summary": {"mem_available_percent": mem_available}}
    psi = {"some": {"avg10": psi_some}, "full": {"avg10": psi_full}}
    device = "/dev/zram0" if zram else "/dev/nvme0n1p9"
    swap = {
        "devices": [{"name": device}],
        "summary": {
            "used_percent": swap_used,
            "free_mib": swap_free_mib,
        },
    }
    return mem, psi, swap


def test_zram_only_high_swap_with_headroom_and_low_psi_gets_relief(abyss_machine_module) -> None:
    policy = abyss_machine_module.memory_default_policy()
    mem, psi, swap = pressure_inputs(
        mem_available=34.0,
        swap_used=82.0,
        swap_free_mib=4096.0,
        zram=True,
        psi_some=0.0,
        psi_full=0.0,
    )

    memory_class, reasons = abyss_machine_module.memory_pressure_class(mem, psi, swap, policy)

    assert memory_class == "warm"
    assert any("zram_only_relief_to_warm" in reason for reason in reasons)


def test_non_zram_high_swap_does_not_receive_zram_relief(abyss_machine_module) -> None:
    policy = abyss_machine_module.memory_default_policy()
    mem, psi, swap = pressure_inputs(
        mem_available=34.0,
        swap_used=82.0,
        swap_free_mib=4096.0,
        zram=False,
        psi_some=0.0,
        psi_full=0.0,
    )

    memory_class, reasons = abyss_machine_module.memory_pressure_class(mem, psi, swap, policy)

    assert memory_class == "critical"
    assert not any("zram_only_relief" in reason for reason in reasons)


def test_zram_relief_is_blocked_when_psi_reports_stalls(abyss_machine_module) -> None:
    policy = abyss_machine_module.memory_default_policy()
    mem, psi, swap = pressure_inputs(
        mem_available=34.0,
        swap_used=82.0,
        swap_free_mib=4096.0,
        zram=True,
        psi_some=3.0,
        psi_full=0.0,
    )

    memory_class, reasons = abyss_machine_module.memory_pressure_class(mem, psi, swap, policy)

    assert memory_class == "critical"
    assert not any("zram_only_relief" in reason for reason in reasons)


def test_memory_plan_is_not_a_zram_or_sysctl_mutation_plan(abyss_machine_module) -> None:
    pressure = {
        "ok": True,
        "class": "warm",
        "reasons": ["swap_used_percent=82>critical_but_zram_only_relief_to_warm"],
        "summary": {"class": "warm", "psi_some_avg10": 0.0, "psi_full_avg10": 0.0},
        "status": {"swap": {"summary": {"free_mib": 4096.0}}},
    }

    plan = abyss_machine_module.memory_plan(write_latest=False, pressure_input=pressure)

    assert plan["ok"] is True
    assert plan["policy"]["automation"] == "gate_new_work_only"
    assert plan["policy"]["do_not_kill_existing_processes"] is True
    assert plan["policy"]["do_not_tune_zram_or_sysctl_from_plan"] is True
    assert "recommended_new_work" in plan
