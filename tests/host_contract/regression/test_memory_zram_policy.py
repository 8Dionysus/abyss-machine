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


def test_zram_only_high_swap_with_headroom_stays_out_of_pressure_class(abyss_machine_module) -> None:
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

    reserve = abyss_machine_module.memory_swap_reserve_status(swap, policy)
    assert memory_class == "green"
    assert reasons == ["no_active_memory_pressure_observed"]
    assert reserve["state"] == "within_target"
    assert reserve["pressure_authority"] is False


def test_non_zram_high_swap_also_does_not_assign_pressure_or_importance(abyss_machine_module) -> None:
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

    assert memory_class == "green"
    assert reasons == ["no_active_memory_pressure_observed"]


def test_psi_stalls_drive_pressure_independently_of_zram_occupancy(abyss_machine_module) -> None:
    policy = abyss_machine_module.memory_default_policy()
    mem, psi, swap = pressure_inputs(
        mem_available=34.0,
        swap_used=82.0,
        swap_free_mib=4096.0,
        zram=True,
        psi_some=9.0,
        psi_full=0.0,
    )

    memory_class, reasons = abyss_machine_module.memory_pressure_class(mem, psi, swap, policy)

    assert memory_class == "hot"
    assert reasons == ["psi_some_avg10=9.0>hot"]


def test_memory_plan_is_not_a_zram_or_sysctl_mutation_plan(abyss_machine_module) -> None:
    pressure = {
        "ok": True,
        "class": "warm",
        "reasons": ["fixture_pressure"],
        "summary": {"class": "warm", "psi_some_avg10": 0.0, "psi_full_avg10": 0.0},
        "status": {"swap": {"summary": {"free_mib": 4096.0}}},
    }

    plan = abyss_machine_module.memory_plan(write_latest=False, pressure_input=pressure)

    assert plan["ok"] is True
    assert plan["policy"]["automation"] == "advisory_machine_pressure_only"
    assert plan["policy"]["numeric_workload_gating"] is False
    assert plan["policy"]["do_not_kill_existing_processes"] is True
    assert plan["policy"]["do_not_tune_zram_or_sysctl_from_plan"] is True
    assert "recommended_new_work" not in plan


def test_memory_pressure_read_only_does_not_promote_child_writes(
    monkeypatch: pytest.MonkeyPatch,
    abyss_machine_module,
) -> None:
    calls: dict[str, list[dict[str, object]]] = {"status": [], "processes": []}

    def status(**kwargs):
        calls["status"].append(dict(kwargs))
        return {
            "ok": True,
            "class": "green",
            "reasons": [],
            "meminfo": {"summary": {}},
            "psi": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
            "swap": {},
            "zram": {"summary": {}},
            "zswap": {},
            "oomd": {},
        }

    def processes(**kwargs):
        calls["processes"].append(dict(kwargs))
        return {"ok": True, "summary": {}, "top": {}}

    monkeypatch.setattr(abyss_machine_module, "memory_status", status)
    monkeypatch.setattr(abyss_machine_module, "memory_process_snapshot", processes)

    result = abyss_machine_module.memory_pressure(top=7, write_latest=False)

    assert result["ok"] is True
    assert calls == {
        "status": [{"write_latest": False}],
        "processes": [{"top": 7, "smaps": True, "write_latest": False}],
    }


def test_memory_pressure_bounded_plan_skips_process_attribution(
    monkeypatch: pytest.MonkeyPatch,
    abyss_machine_module,
) -> None:
    monkeypatch.setattr(
        abyss_machine_module,
        "memory_status",
        lambda write_latest=False: {
            "ok": True,
            "class": "green",
            "reasons": [],
            "meminfo": {"summary": {}},
            "psi": {"some": {"avg10": 0.0}, "full": {"avg10": 0.0}},
            "swap": {},
            "swap_reserve": {},
            "zram": {"summary": {}},
            "zswap": {},
            "oomd": {},
        },
    )
    monkeypatch.setattr(
        abyss_machine_module,
        "memory_process_snapshot",
        lambda **kwargs: pytest.fail(
            "bounded memory plan pressure must not scan process attribution"
        ),
    )

    result = abyss_machine_module.memory_pressure(
        top=30,
        write_latest=False,
        include_processes=False,
    )

    assert result["ok"] is True
    assert result["summary"]["processes"] is None
    assert result["processes"]["summary"]["collection_basis"] == (
        "omitted_for_bounded_plan"
    )
    assert result["policy"]["process_attribution_collected"] is False


def test_memory_plan_read_only_keeps_live_pressure_and_game_guard_read_only(
    monkeypatch: pytest.MonkeyPatch,
    abyss_machine_module,
) -> None:
    calls: dict[str, list[dict[str, object]]] = {"pressure": [], "game_guard": []}

    def pressure(**kwargs):
        calls["pressure"].append(dict(kwargs))
        return {"ok": True, "class": "green", "reasons": [], "summary": {"class": "green"}}

    def game_guard(**kwargs):
        calls["game_guard"].append(dict(kwargs))
        return {"active": False, "platform_present": False, "summary": {"games": 0}}

    monkeypatch.setattr(abyss_machine_module, "memory_pressure", pressure)
    monkeypatch.setattr(abyss_machine_module, "process_game_guard", game_guard)
    monkeypatch.setattr(
        abyss_machine_module,
        "memory_plan_mode_snapshot",
        lambda: (
            {"selected_mode": "balanced", "effective_mode": "balanced"},
            {"status": "fresh_latest_reused"},
        ),
    )

    result = abyss_machine_module.memory_plan(write_latest=False)

    assert result["ok"] is True
    assert calls == {
        "pressure": [
            {"top": 30, "write_latest": False, "include_processes": False}
        ],
        "game_guard": [{"write_latest": False}],
    }
    assert result["input_freshness"]["pressure"]["process_attribution"] == (
        "omitted_for_bounded_plan"
    )
    assert result["input_freshness"]["mode"]["status"] == "fresh_latest_reused"


@pytest.mark.parametrize(
    ("argv", "target", "expected"),
    [
        (["memory", "status", "--json"], "memory_status", {"write_latest": False}),
        (["memory", "pressure", "--json"], "memory_pressure", {"top": 30, "write_latest": False}),
        (
            ["memory", "processes", "--json"],
            "memory_process_snapshot",
            {"top": 40, "smaps": True, "write_latest": False},
        ),
        (["memory", "plan", "--json"], "memory_plan", {"write_latest": False}),
        (["memory", "headroom", "--json"], "memory_headroom", {"top": 40, "write_latest": False}),
        (["memory", "residency", "--json"], "memory_residency", {"top": 40, "write_latest": False}),
    ],
)
def test_memory_read_commands_do_not_write_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    abyss_machine_module,
    argv: list[str],
    target: str,
    expected: dict[str, object],
) -> None:
    calls: list[dict[str, object]] = []

    def read_model(**kwargs):
        calls.append(dict(kwargs))
        return {"ok": True}

    monkeypatch.setattr(abyss_machine_module, target, read_model)

    assert abyss_machine_module.main(argv) == 0
    assert calls == [expected]
    assert '"ok": true' in capsys.readouterr().out
