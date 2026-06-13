from __future__ import annotations

from typing import Any


def _heartbeat_latest(machine: Any, *, include_all_fields: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": f"{machine.SCHEMA_PREFIX}_heartbeat_pulse_v1",
        "version": machine.VERSION,
        "ok": True,
        "policy": {
            "read_model": True,
            "automatic_action": False,
            "automatic_repo_write": False,
            "executes_reaction_commands": False,
            "executes_response_commands": False,
        },
    }
    if include_all_fields:
        for field in machine.HEARTBEAT_BRIDGE_STABLE_FIELDS:
            payload[field] = {"schema": f"{machine.SCHEMA_PREFIX}_heartbeat_{field}_v1"}
    return payload


def _heartbeat_validation(machine: Any, *, ok: bool = True, missing_check: str | None = None) -> dict[str, Any]:
    checks = [
        {"key": key, "level": "ok"}
        for key in machine.HEARTBEAT_BRIDGE_REQUIRED_VALIDATE_CHECKS
        if key != missing_check
    ]
    return {
        "schema": f"{machine.SCHEMA_PREFIX}_heartbeats_validate_v1",
        "version": machine.VERSION,
        "ok": ok,
        "summary": {"status": "ok" if ok else "fail", "fails": 0 if ok else 1, "warnings": 0, "checks": len(checks)},
        "checks": checks,
    }


def test_stack_bridge_artifact_routes_expose_heartbeats_read_only(abyss_machine_module) -> None:
    machine = abyss_machine_module
    routes = machine.stack_bridge_artifact_routes()

    heartbeats = routes.get("heartbeats")
    assert isinstance(heartbeats, dict)
    assert heartbeats["latest"]["path"] == str(machine.HEARTBEATS_LATEST_PATH)
    assert heartbeats["latest"]["schema"] == "abyss_machine_heartbeat_pulse_v1"
    assert heartbeats["validate"]["path"] == str(machine.HEARTBEATS_VALIDATE_LATEST_PATH)
    assert heartbeats["validate"]["schema"] == "abyss_machine_heartbeats_validate_v1"
    assert all(route.get("write") is not True for route in heartbeats.values())


def test_stack_bridge_heartbeat_readiness_requires_fields_and_validator_gate(abyss_machine_module) -> None:
    machine = abyss_machine_module
    artifacts = machine.stack_bridge_artifact_routes()["heartbeats"]
    assert "rhythm_recurring_timer" in machine.HEARTBEAT_BRIDGE_REQUIRED_VALIDATE_CHECKS
    assert "rhythm_no_missed_beats" in machine.HEARTBEAT_BRIDGE_REQUIRED_VALIDATE_CHECKS

    missing_fields = machine.stack_bridge_heartbeat_readiness(
        _heartbeat_latest(machine, include_all_fields=False),
        _heartbeat_validation(machine),
        artifacts,
    )
    assert missing_fields["ok"] is False
    assert set(missing_fields["missing_fields"]) == set(machine.HEARTBEAT_BRIDGE_STABLE_FIELDS)

    missing_validate_check = machine.stack_bridge_heartbeat_readiness(
        _heartbeat_latest(machine),
        _heartbeat_validation(machine, missing_check="ai_hygiene_non_executing"),
        artifacts,
    )
    assert missing_validate_check["ok"] is False
    assert missing_validate_check["missing_validate_checks"] == ["ai_hygiene_non_executing"]

    missing_timer_gate = machine.stack_bridge_heartbeat_readiness(
        _heartbeat_latest(machine),
        _heartbeat_validation(machine, missing_check="rhythm_recurring_timer"),
        artifacts,
    )
    assert missing_timer_gate["ok"] is False
    assert missing_timer_gate["missing_validate_checks"] == ["rhythm_recurring_timer"]

    ready = machine.stack_bridge_heartbeat_readiness(
        _heartbeat_latest(machine),
        _heartbeat_validation(machine),
        artifacts,
    )
    assert ready["ok"] is True
    assert ready["status"] == "ready"


def test_stack_bridge_export_contains_heartbeat_bridge_contract(abyss_machine_module) -> None:
    machine = abyss_machine_module
    export = machine.stack_bridge_export(write_latest=False)

    assert "heartbeats" in export["artifacts"]
    assert "heartbeats" in export["refs"]
    assert "latest" in export["refs"]["heartbeats"]
    assert "validate" in export["refs"]["heartbeats"]
    assert "heartbeat_bridge" in export["bridges"]
    assert export["bridges"]["heartbeat_bridge"]["stable_fields"] == list(machine.HEARTBEAT_BRIDGE_STABLE_FIELDS)
    assert any("heartbeats validate" in rule for rule in export["handoff_rules"])
