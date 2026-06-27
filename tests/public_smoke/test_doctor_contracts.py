from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import doctor_contracts


def _path_refs(root: str = "/var/lib/abyss-machine/doctor") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "latest": f"{root}/latest.json",
        "report_root": f"{root}/reports",
        "report_latest": f"{root}/reports/latest.md",
        "machine_report_root": f"{root}/machine-report",
        "machine_report_latest": f"{root}/machine-report/latest.json",
        "machine_report_markdown_latest": f"{root}/machine-report/latest.md",
        "validate_root": f"{root}/validate",
        "validate_latest": f"{root}/validate/latest.json",
        "policy": "/etc/abyss-machine/doctor-policy.json",
        "service": "abyss-machine-doctor.service",
        "service_path": "/usr/local/lib/systemd/user/abyss-machine-doctor.service",
        "timer": "abyss-machine-doctor.timer",
        "timer_path": "/usr/local/lib/systemd/user/abyss-machine-doctor.timer",
    }


def test_doctor_policy_paths_and_status_document_contracts_are_module_owned() -> None:
    policy = doctor_contracts.default_policy(
        schema_prefix="abyss_machine",
        version="0.8.test",
        doctor_service="abyss-machine-doctor.service",
        doctor_timer="abyss-machine-doctor.timer",
    )
    merged = doctor_contracts.merge_policy(
        policy,
        {"repair": {"semantic_maintain": False}, "custom": True},
        path="/etc/abyss-machine/doctor-policy.json",
    )
    paths = doctor_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_path_refs(),
    )
    checks = [
        {"level": "ok", "key": "platform", "message": "Linux host"},
        {"level": "warn", "key": "doctor_timer", "message": "timer inactive"},
    ]
    data = doctor_contracts.document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        checks=checks,
        safe_actions=[{"action": "refresh", "needed": True, "automatic": False, "command": "abyss-machine doctor --json"}],
        repair_requested=False,
        safe_only=True,
        repair_results=[],
        paths=paths,
        policy_path="/etc/abyss-machine/doctor-policy.json",
        policy_load_error=None,
        repair_policy=merged["repair"],
    )
    markdown = doctor_contracts.report_markdown(data)

    assert policy["schema"] == "abyss_machine_doctor_policy_v1"
    assert policy["repair"]["privileged_actions"] is False
    assert merged["repair"]["semantic_maintain"] is False
    assert merged["_path"] == "/etc/abyss-machine/doctor-policy.json"
    assert paths["schema"] == "abyss_machine_doctor_paths_v1"
    assert paths["policy_contract"]["repo_mutation"] is False
    assert data["schema"] == "abyss_machine_doctor_v1"
    assert data["ok"] is True
    assert data["state"] == "needs-maintenance"
    assert data["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert data["readiness_score"] == 40
    assert "## Non-OK Checks" in markdown
    assert "`warn` `doctor_timer`" in markdown


def test_doctor_machine_report_contracts_are_module_owned() -> None:
    service = doctor_contracts.machine_report_service_summary(
        {
            "unit": "abyss-tts-server.service",
            "capability": "tts",
            "class": "resident",
            "protected": True,
            "systemd": {"active_state": "active", "sub_state": "running", "main_pid": 1234},
            "controls": {
                "memory_current": {"mib": 512},
                "memory_swap_current": {"mib": 128},
                "memory_swap_max": {"raw": "infinity"},
            },
            "process_rollup": {"totals": {"pss_mib": 400, "swap_mib": 100}},
            "issues": [{"code": "warmup"}],
        }
    )
    artifact = doctor_contracts.artifact_entry(
        label="doctor_latest",
        path="/var/lib/abyss-machine/doctor/latest.json",
        exists=True,
        load_error=None,
        data={
            "schema": "abyss_machine_doctor_v1",
            "generated_at": "2026-06-25T12:00:00+00:00",
            "ok": True,
            "summary": {"status": "warn", "checks": 2, "warnings": 1},
        },
    )
    doc = doctor_contracts.machine_report_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        doctor_data={"ok": True, "summary": {"status": "warn", "checks": 2, "fails": 0, "warnings": 1}},
        memory_data={"ok": True, "status": "observed_clean", "summary": {"swap_used_percent": 12, "psi_some_avg10": 0.0}},
        nervous_data={"ok": True, "readiness": {"status": "ready", "semantic_stale": False, "semantic_maintenance_needed": False}},
        ai_policy_data={"ok": True, "class": "light", "heavy_policy": "allowed", "can_run_heavy": True, "current": {"thermal": {"current_temperature_c": 52}}},
        protected_services=[service],
        artifacts=[artifact],
        paths={"latest_json": "/var/lib/abyss-machine/doctor/machine-report/latest.json"},
        no_thermal_sample=True,
    )
    markdown = doctor_contracts.machine_report_markdown(doc)

    assert service["protected"] is True
    assert service["memory_current_mib"] == 512
    assert service["issue_codes"] == ["warmup"]
    assert artifact["status"] == "warn"
    assert artifact["summary"]["warnings"] == 1
    assert doc["schema"] == "abyss_machine_doctor_machine_report_v1"
    assert doc["status"] == "ok"
    assert doc["summary"]["doctor_warnings"] == 1
    assert doc["policy"]["facts_only"] is True
    assert doc["policy"]["no_thermal_sample"] is True
    assert "does not stop, disable" in doc["guardrails"][0]
    assert "abyss-tts-server.service" in markdown


def test_doctor_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T14:55:00Z"
    checks = [
        {"level": "ok", "key": "root", "message": "doctor root present", "data": {"path": "/var/lib/abyss-machine/doctor"}},
        {"level": "warn", "key": "systemd_timer_state", "message": "doctor timer inactive", "data": {"is_active": False}},
    ]
    paths = {
        "schema": "abyss_machine_doctor_paths_v1",
        "commands": {"validate": "abyss-machine doctor validate --json"},
    }
    expected = doctor_contracts.doctor_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        paths=paths,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.doctor_validate_document_from_checks(
        checks,
        strict=True,
        paths=paths,
    ) == expected
    assert expected["schema"] == "abyss_machine_doctor_validate_v1"
    assert expected["scope"] == "Abyss Machine doctor/self-maintenance route"
    assert expected["ok"] is False
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["paths"]["commands"]["validate"] == "abyss-machine doctor validate --json"
    assert expected["policy"]["read_only"] is True


def test_doctor_paths_cli_uses_public_contract_shape_without_live_collection() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "doctor", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_doctor_paths_v1"
    assert payload["commands"]["validate"] == "abyss-machine doctor validate --json"
    assert payload["policy_contract"]["raw_private_content"] is False
