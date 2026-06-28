from __future__ import annotations

import datetime as dt
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


def test_daily_markdown_path_uses_local_calendar_route() -> None:
    path = doctor_adapters.daily_markdown_path(
        Path("/var/lib/abyss-machine/doctor/reports"),
        dt.datetime(2026, 6, 28, 8, 45, tzinfo=dt.timezone.utc),
    )

    assert path.as_posix().endswith("/2026/06/2026-06-28.md")


def test_doctor_report_writer_uses_latest_and_daily_paths_without_live_host() -> None:
    writes: list[tuple[Path, str, int]] = []

    def write_text(path: Path, text: str, mode: int) -> dict[str, Any] | None:
        writes.append((path, text, mode))
        return None

    result = doctor_adapters.write_doctor_report(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-28T08:45:00Z",
        data={
            "generated_at": "2026-06-28T08:44:00Z",
            "state": "watch",
            "readiness_score": 88,
            "summary": {"status": "warn", "checks": 1, "fails": 0, "warnings": 1},
            "checks": [{"level": "warn", "key": "latest", "message": "missing"}],
        },
        paths=doctor_adapters.DoctorReportWritePaths(
            latest_markdown=Path("/var/lib/abyss-machine/doctor/reports/latest.md"),
            daily_markdown=Path("/var/lib/abyss-machine/doctor/reports/2026/06/2026-06-28.md"),
        ),
        port=doctor_adapters.DoctorReportWritePort(write_text=write_text),
    )

    assert result["schema"] == "abyss_machine_doctor_report_v1"
    assert result["ok"] is True
    assert [item[0].name for item in writes] == ["latest.md", "2026-06-28.md"]
    assert all(item[2] == 0o664 for item in writes)
    assert "# Abyss Machine Doctor" in writes[0][1]


def test_machine_report_artifact_reader_compacts_json_without_raw_payload() -> None:
    path = Path("/var/lib/abyss-machine/doctor/latest.json")
    port = doctor_adapters.DoctorArtifactReadPort(
        load_json_document=lambda candidate: (
            {
                "schema": "abyss_machine_doctor_v1",
                "generated_at": "2026-06-28T08:44:00Z",
                "ok": True,
                "summary": {"status": "warn", "warnings": 1, "private_field": "not copied"},
                "checks": [{"data": {"large": "payload"}}],
            },
            None,
        ),
        path_exists=lambda candidate: candidate == path,
    )

    artifact = doctor_adapters.read_machine_report_artifact(
        label="doctor_latest",
        path=path,
        port=port,
    )

    assert artifact["label"] == "doctor_latest"
    assert artifact["exists"] is True
    assert artifact["status"] == "warn"
    assert artifact["summary"] == {"status": "warn", "warnings": 1}
    assert "checks" not in artifact


def test_machine_report_writer_marks_document_failed_on_write_error() -> None:
    text_writes: list[Path] = []

    def write_latest_and_history(data: dict[str, Any], latest: Path, root: Path) -> list[dict[str, Any]]:
        assert latest.name == "latest.json"
        assert root.name == "machine-report"
        return []

    def write_text(path: Path, text: str, mode: int) -> dict[str, Any] | None:
        text_writes.append(path)
        if path.name == "latest.md":
            return {"path": str(path), "error": "permission denied"}
        return None

    data = {
        "schema": "abyss_machine_doctor_machine_report_v1",
        "generated_at": "2026-06-28T08:44:00Z",
        "ok": True,
        "status": "ok",
        "summary": {"doctor_status": "ok"},
        "memory": {"summary": {}},
        "nervous": {},
        "ai_policy": {},
        "protected_services": [],
        "guardrails": [],
    }

    result = doctor_adapters.write_machine_report_outputs(
        data=data,
        paths=doctor_adapters.DoctorMachineReportWritePaths(
            latest_json=Path("/var/lib/abyss-machine/doctor/machine-report/latest.json"),
            history_root=Path("/var/lib/abyss-machine/doctor/machine-report"),
            latest_markdown=Path("/var/lib/abyss-machine/doctor/machine-report/latest.md"),
            daily_markdown=Path("/var/lib/abyss-machine/doctor/machine-report/2026/06/2026-06-28.md"),
        ),
        port=doctor_adapters.DoctorMachineReportWritePort(
            write_latest_and_history=write_latest_and_history,
            write_text=write_text,
        ),
    )

    assert result["ok"] is False
    assert result["write_errors"] == [{"path": "/var/lib/abyss-machine/doctor/machine-report/latest.md", "error": "permission denied"}]
    assert [path.name for path in text_writes] == ["latest.md", "2026-06-28.md"]
