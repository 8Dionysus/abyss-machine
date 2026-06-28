from __future__ import annotations

from pathlib import Path
from typing import Any

from abyss_machine import doctor_adapters


def _paths() -> doctor_adapters.DoctorValidatePaths:
    root = Path("/var/lib/abyss-machine/doctor")
    return doctor_adapters.DoctorValidatePaths(
        root=root,
        agent_entrypoint=root / "AGENTS.md",
        policy=Path("/etc/abyss-machine/doctor-policy.json"),
        latest=root / "latest.json",
        report_latest=root / "reports/latest.md",
        machine_report_latest=root / "machine-report/latest.json",
        machine_report_markdown_latest=root / "machine-report/latest.md",
        service_path=Path("/usr/local/lib/systemd/user/abyss-machine-doctor.service"),
        timer_path=Path("/usr/local/lib/systemd/user/abyss-machine-doctor.timer"),
    )


def _fake_port(
    *,
    exists: set[Path],
    latest_docs: dict[Path, dict[str, Any]],
    timer: dict[str, Any],
    bridge: dict[str, Any],
) -> doctor_adapters.DoctorValidateProbePort:
    return doctor_adapters.DoctorValidateProbePort(
        path_exists=lambda path: path in exists,
        load_latest_json=lambda path, schema: latest_docs.get(path, {"schema": schema, "ok": False, "error": "missing"}),
        user_systemd_unit=lambda name: dict(timer, name=name),
        bridge_manifest=lambda: bridge,
    )


def _by_key(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(check["key"]): check for check in checks}


def test_doctor_validate_probe_adapter_collects_clean_checks_without_live_host() -> None:
    paths = _paths()
    exists = {
        paths.root,
        paths.agent_entrypoint,
        paths.policy,
        paths.report_latest,
        paths.machine_report_markdown_latest,
        paths.service_path,
        paths.timer_path,
    }
    latest_docs = {
        paths.latest: {"schema": "abyss_machine_doctor_v1", "ok": True},
        paths.machine_report_latest: {
            "schema": "abyss_machine_doctor_machine_report_v1",
            "generated_at": "2026-06-28T08:30:00Z",
            "ok": True,
            "status": "ok",
        },
    }
    bridge = {"commands": {key: {} for key in doctor_adapters.REQUIRED_DOCTOR_BRIDGE_COMMANDS}}

    checks = doctor_adapters.collect_doctor_validate_checks(
        schema_prefix="abyss_machine",
        paths=paths,
        policy_doc={"_load_error": None},
        timer_name="abyss-machine-doctor.timer",
        port=_fake_port(
            exists=exists,
            latest_docs=latest_docs,
            timer={"active": "active", "enabled": "enabled", "is_active": True, "is_enabled": True},
            bridge=bridge,
        ),
    )

    by_key = _by_key(checks)
    assert by_key["root"]["level"] == "ok"
    assert by_key["policy"]["level"] == "ok"
    assert by_key["machine_report_json"]["level"] == "ok"
    assert by_key["systemd_timer_state"]["level"] == "ok"
    assert by_key["bridge_commands"]["data"]["missing"] == []


def test_doctor_validate_probe_adapter_preserves_warning_and_failure_shape() -> None:
    paths = _paths()
    exists = {paths.root, paths.agent_entrypoint, paths.policy, paths.timer_path}
    bridge = {"commands": {"doctor_json": {}, "doctor_paths_json": {}}}

    checks = doctor_adapters.collect_doctor_validate_checks(
        schema_prefix="abyss_machine",
        paths=paths,
        policy_doc={"_load_error": "invalid json"},
        timer_name="abyss-machine-doctor.timer",
        port=_fake_port(
            exists=exists,
            latest_docs={paths.latest: {"schema": "abyss_machine_doctor_v1", "ok": False, "error": "bad"}},
            timer={"active": "inactive", "enabled": "disabled", "is_active": False, "is_enabled": False},
            bridge=bridge,
        ),
    )

    by_key = _by_key(checks)
    assert by_key["policy"]["level"] == "fail"
    assert by_key["latest"]["level"] == "warn"
    assert by_key["report"]["level"] == "warn"
    assert by_key["systemd_service_file"]["level"] == "fail"
    assert by_key["systemd_timer_state"]["level"] == "warn"
    assert by_key["bridge_commands"]["level"] == "fail"
    assert "doctor_machine_report_json" in by_key["bridge_commands"]["data"]["missing"]
