from __future__ import annotations

import subprocess


def test_resource_plan_caps_unattended_medium_indexing(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="indexing",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
            "class": "green",
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={},
    )

    props = plan["systemd"]["properties"]
    assert props["MemoryHigh"] == "4096M"
    assert props["MemoryMax"] == "6144M"
    assert plan["systemd"]["policy"]["memory_max_not_set"] is False
    assert plan["systemd"]["policy"]["memory_max_set_for_indexing"] is True
    assert plan["policy"]["memory_max_not_set_by_default"] is False
    assert plan["policy"]["memory_max_set_for_indexing"] is True


def test_resource_plan_blocks_unattended_medium_indexing_under_swap_pressure(abyss_machine_module):
    plan = abyss_machine_module.resource_plan(
        workload_class="medium",
        kind="indexing",
        unattended=True,
        sample_thermal=False,
        write_latest=False,
        mode_data={"effective_mode": "balanced", "launch_policy": {"max_unattended_class": "medium"}},
        memory_data={
            "class": "green",
            "pressure": {"summary": {"swap_used_percent": 46.0, "swap_free_mib": 8192}},
            "recommended_new_work": {
                "medium": {
                    "allowed": True,
                    "unattended_allowed": True,
                    "blocked_reasons": [],
                    "unattended_blocked_reasons": [],
                }
            },
        },
        storage_data={"summary": {}},
        game_guard_data={"active": False},
        route_data={
            "ok": True,
            "allowed": True,
            "unattended_allowed": True,
            "route": {"cpuset": "0-1", "env": {}},
        },
        thermal_plan_data={},
    )

    assert plan["ok"] is False
    assert plan["decision"] == "force_required"
    assert "indexing_unattended_swap_used_pressure" in plan["blocked_reasons"]
    assert plan["policy"]["unattended_indexing_blocks_on_swap_pressure"] is True


def test_resource_launch_timeout_stops_transient_unit(abyss_machine_module, monkeypatch):
    calls: list[list[str]] = []

    def fake_plan(**kwargs):
        return {
            "systemd": {
                "unit_type": kwargs.get("unit_type") or "service",
                "slice": "abyss-machine-ai.slice",
                "properties": {},
                "env": {},
            },
            "request": {
                "normalized_class": kwargs.get("workload_class") or "heavy",
                "normalized_kind": kwargs.get("kind") or "ai",
            },
            "blocked_reasons": [],
            "denied_reasons": [],
        }

    def fake_command_exists(name: str) -> bool:
        return name in {"systemd-run", "systemctl"}

    def fake_run(cmd, **kwargs):
        command = [str(item) for item in cmd]
        calls.append(command)
        if command[0] == "systemd-run":
            assert "--unit" in command
            unit = command[command.index("--unit") + 1]
            assert unit.startswith("abyss-machine-ai-heavy-")
            assert unit.endswith(".service")
            raise subprocess.TimeoutExpired(
                cmd=command,
                timeout=kwargs.get("timeout"),
                output=f"Running as unit: {unit}\n",
                stderr="",
            )
        if command[:3] == ["systemctl", "--user", "stop"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["systemctl", "--user", "is-active"]:
            return subprocess.CompletedProcess(command, 3, "inactive\n", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(abyss_machine_module, "resource_plan", fake_plan)
    monkeypatch.setattr(abyss_machine_module, "command_exists", fake_command_exists)
    monkeypatch.setattr(abyss_machine_module.subprocess, "run", fake_run)

    result = abyss_machine_module.resource_launch(
        ["/bin/sleep", "60"],
        workload_class="heavy",
        kind="ai",
        timeout_sec=0.1,
        write_latest=False,
    )

    cleanup = result["execution"]["timeout_cleanup"]
    assert result["ok"] is False
    assert result["execution"]["returncode"] == 124
    assert result["request"]["launch_unit"].startswith("abyss-machine-ai-heavy-")
    assert result["execution"]["systemd"]["unit"] == result["request"]["launch_unit"]
    assert cleanup["attempted"] is True
    assert cleanup["unit"] == result["request"]["launch_unit"]
    assert cleanup["stop"]["returncode"] == 0
    assert cleanup["state"]["value"] == "inactive"
    assert any(call[:3] == ["systemctl", "--user", "stop"] for call in calls)
