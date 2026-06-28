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


def _core_paths() -> doctor_adapters.DoctorCoreProbePaths:
    change_root = Path("/var/lib/abyss-machine/changes")
    return doctor_adapters.DoctorCoreProbePaths(
        manifest=Path("/etc/abyss-machine/manifest.json"),
        topology_doc=Path("/etc/abyss-machine/TOPOLOGY.md"),
        change_root=change_root,
        change_agent_entrypoint=change_root / "AGENTS.md",
        change_index=change_root / "index.json",
        topology_validate_latest=Path("/var/lib/abyss-machine/topology/validate/latest.json"),
        stack_bridge_validate_latest=Path("/var/lib/abyss-machine/stack-bridge/validate/latest.json"),
        binary=Path("/usr/local/bin/abyss-machine"),
    )


def _power_cooling_paths() -> doctor_adapters.DoctorPowerCoolingProbePaths:
    return doctor_adapters.DoctorPowerCoolingProbePaths(
        cooling_latest=Path("/var/lib/abyss-machine/cooling/latest.json"),
    )


def _storage_process_paths() -> doctor_adapters.DoctorStorageProcessProbePaths:
    return doctor_adapters.DoctorStorageProcessProbePaths(
        storage_policy=Path("/etc/abyss-machine/storage-policy.json"),
        process_latest=Path("/var/lib/abyss-machine/process/latest.json"),
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


def test_doctor_core_probe_adapter_collects_clean_checks_without_live_host() -> None:
    paths = _core_paths()
    exists = {
        paths.manifest,
        paths.topology_doc,
        paths.change_agent_entrypoint,
        paths.change_index,
        paths.binary,
    }
    port = doctor_adapters.DoctorCoreProbePort(
        platform_system=lambda: "Linux",
        path_exists=lambda path: path in exists,
        topology_validate=lambda: {"summary": {"status": "ok", "fails": 0, "warnings": 0}},
        stack_bridge_validate=lambda: {"summary": {"status": "ok", "fails": 0, "warnings": 0}},
    )

    checks = doctor_adapters.collect_doctor_core_checks(
        paths=paths,
        commands={"podman": True, "rsync": True, "curl": True},
        port=port,
    )

    by_key = _by_key(checks)
    assert len(checks) == 10
    assert by_key["platform"]["message"] == "Linux host"
    assert by_key["bridge_manifest"]["level"] == "ok"
    assert by_key["machine_change_ledger"]["level"] == "ok"
    assert by_key["machine_topology_validate"]["data"]["latest"] == str(paths.topology_validate_latest)
    assert by_key["stack_bridge_validate"]["data"]["command"] == "abyss-machine stack-bridge validate --json"
    assert by_key["binary"]["level"] == "ok"
    assert by_key["cmd_podman"]["level"] == "ok"
    assert by_key["cmd_rsync"]["level"] == "ok"
    assert by_key["cmd_curl"]["level"] == "ok"


def test_doctor_power_cooling_probe_adapter_collects_clean_checks_without_live_host() -> None:
    paths = _power_cooling_paths()
    power = {
        "power_profiles_daemon": {"active": "active", "is_active": True},
        "auto_timer": {"active": "active", "is_active": True},
    }
    thermal = {"thermald": {"active": "active", "is_active": True}}
    cooling = {
        "ok": True,
        "fan": {"available": True, "fan_mode": "auto"},
        "power": {"platform_profile": {"current": "balanced"}},
    }
    timer = {"active": "active", "enabled": "enabled", "is_active": True, "is_enabled": True}
    port = doctor_adapters.DoctorPowerCoolingProbePort(
        power_status=lambda: power,
        thermal_status=lambda: thermal,
        cooling_status=lambda: cooling,
        systemd_unit=lambda name: dict(timer, name=name),
    )

    checks = doctor_adapters.collect_doctor_power_cooling_checks(
        paths=paths,
        cooling_timer_name="abyss-cooling-reconcile.timer",
        port=port,
    )

    by_key = _by_key(checks)
    assert len(checks) == 5
    assert by_key["power_profiles_daemon"]["level"] == "ok"
    assert by_key["abyss_power_auto"]["message"] == "abyss-power-profile-auto.timer active"
    assert by_key["thermald"]["level"] == "ok"
    assert by_key["cooling_backend"]["message"] == "cooling backend fan_mode=auto platform=balanced"
    assert by_key["cooling_backend"]["data"]["latest"] == str(paths.cooling_latest)
    assert by_key["cooling_reconcile_timer"]["message"] == "abyss-cooling-reconcile.timer active/enabled"


def test_doctor_power_cooling_probe_adapter_preserves_degraded_status_shape() -> None:
    paths = _power_cooling_paths()
    power = {
        "power_profiles_daemon": {"active": "inactive", "is_active": False},
        "auto_timer": {"active": "inactive", "is_active": False},
    }
    thermal = {"thermald": {"active": "failed", "is_active": False}}
    cooling = {"ok": False, "fan": {"available": False}, "power": {"platform_profile": {}}}
    timer = {"active": "inactive", "enabled": "disabled", "is_active": False, "is_enabled": False}
    port = doctor_adapters.DoctorPowerCoolingProbePort(
        power_status=lambda: power,
        thermal_status=lambda: thermal,
        cooling_status=lambda: cooling,
        systemd_unit=lambda name: dict(timer, name=name),
    )

    checks = doctor_adapters.collect_doctor_power_cooling_checks(
        paths=paths,
        cooling_timer_name="abyss-cooling-reconcile.timer",
        port=port,
    )

    by_key = _by_key(checks)
    assert by_key["power_profiles_daemon"]["level"] == "warn"
    assert by_key["abyss_power_auto"]["level"] == "warn"
    assert by_key["thermald"]["message"] == "thermald failed"
    assert by_key["cooling_backend"]["level"] == "warn"
    assert by_key["cooling_backend"]["message"] == "cooling backend unavailable"
    assert by_key["cooling_backend"]["data"] == {
        "fan": {"available": False},
        "platform_profile": {},
        "latest": str(paths.cooling_latest),
    }
    assert by_key["cooling_reconcile_timer"]["level"] == "warn"
    assert by_key["cooling_reconcile_timer"]["data"]["name"] == "abyss-cooling-reconcile.timer"


def test_doctor_storage_process_probe_adapter_collects_clean_checks_without_live_host() -> None:
    paths = _storage_process_paths()
    filesystems = [
        {"target": "/", "fstype": "btrfs", "size": 100},
        {"target": "/srv", "fstype": "xfs", "size": 200},
    ]
    hooks = {
        "directories": {
            "source": [{"path": "/srv/abyss-machine/storage/source", "exists": True}],
            "target": [{"path": "/srv/abyss-machine/storage/target", "exists": True}],
        },
        "summary": {"directories": 2, "missing": 0},
    }
    process_summary = {
        "ok": True,
        "generated_at": "2026-06-28T10:40:00Z",
        "summary": {"processes": 128, "containers": 2},
    }
    port = doctor_adapters.DoctorStorageProcessProbePort(
        storage_filesystems=lambda: filesystems,
        storage_policy_document=lambda: {"ok": True, "load_error": None},
        storage_hooks_status=lambda: hooks,
        process_latest_summary=lambda: process_summary,
    )

    checks = doctor_adapters.collect_doctor_storage_process_checks(
        paths=paths,
        port=port,
    )

    by_key = _by_key(checks)
    assert len(checks) == 5
    assert by_key["root_btrfs"]["level"] == "ok"
    assert by_key["srv_mount"]["message"] == "/srv mounted as xfs"
    assert by_key["storage_policy"]["data"] == {"path": str(paths.storage_policy), "load_error": None}
    assert by_key["storage_hooks"]["level"] == "ok"
    assert by_key["storage_hooks"]["data"] == {"directories": 2, "missing": 0}
    assert by_key["process_snapshot_latest"]["message"] == "process snapshot latest: 2026-06-28T10:40:00Z"
    assert by_key["process_snapshot_latest"]["data"] == {
        "path": str(paths.process_latest),
        "summary": {"processes": 128, "containers": 2},
    }


def test_doctor_storage_process_probe_adapter_preserves_degraded_status_shape() -> None:
    paths = _storage_process_paths()
    hooks = {
        "directories": {
            "source": [{"path": "/srv/abyss-machine/storage/source", "exists": True}],
            "target": [{"path": "/srv/abyss-machine/storage/target", "exists": False}],
        },
        "summary": {"directories": 2, "missing": 1},
    }
    port = doctor_adapters.DoctorStorageProcessProbePort(
        storage_filesystems=lambda: [{"target": "/", "fstype": "ext4"}],
        storage_policy_document=lambda: {"ok": False, "load_error": "missing"},
        storage_hooks_status=lambda: hooks,
        process_latest_summary=lambda: {"ok": False, "summary": None},
    )

    checks = doctor_adapters.collect_doctor_storage_process_checks(
        paths=paths,
        port=port,
    )

    by_key = _by_key(checks)
    assert by_key["root_btrfs"]["level"] == "warn"
    assert by_key["root_btrfs"]["data"] == {"target": "/", "fstype": "ext4"}
    assert by_key["srv_mount"] == {"level": "warn", "key": "srv_mount", "message": "/srv mount not detected"}
    assert by_key["storage_policy"]["level"] == "warn"
    assert by_key["storage_policy"]["message"] == f"{paths.storage_policy} missing or invalid"
    assert by_key["storage_hooks"]["level"] == "warn"
    assert by_key["storage_hooks"]["message"] == "storage hook directories incomplete"
    assert by_key["storage_hooks"]["data"] == {"directories": 2, "missing": 1}
    assert by_key["process_snapshot_latest"]["level"] == "warn"
    assert by_key["process_snapshot_latest"]["message"] == "process snapshot latest missing"
    assert by_key["process_snapshot_latest"]["data"] == {"path": str(paths.process_latest), "summary": None}


def test_doctor_core_probe_adapter_preserves_degraded_status_shape() -> None:
    paths = _core_paths()
    exists = {paths.change_agent_entrypoint}
    port = doctor_adapters.DoctorCoreProbePort(
        platform_system=lambda: "Darwin",
        path_exists=lambda path: path in exists,
        topology_validate=lambda: {"summary": {"status": "fail", "fails": 1, "warnings": 0}},
        stack_bridge_validate=lambda: {"summary": {"status": "warn", "fails": 0, "warnings": 2}},
    )

    checks = doctor_adapters.collect_doctor_core_checks(
        paths=paths,
        commands={"curl": True},
        port=port,
    )

    by_key = _by_key(checks)
    assert by_key["platform"] == {"level": "fail", "key": "platform", "message": "unsupported platform Darwin"}
    assert by_key["bridge_manifest"]["level"] == "warn"
    assert by_key["machine_topology_doc"]["level"] == "warn"
    assert by_key["machine_change_ledger"]["data"] == {
        "agent_entrypoint": str(paths.change_agent_entrypoint),
        "agent_entrypoint_exists": True,
        "index": str(paths.change_index),
        "index_exists": False,
    }
    assert by_key["machine_topology_validate"]["level"] == "fail"
    assert by_key["machine_topology_validate"]["data"]["summary"]["fails"] == 1
    assert by_key["stack_bridge_validate"]["level"] == "warn"
    assert by_key["binary"]["message"] == f"{paths.binary} missing"
    assert by_key["cmd_podman"]["level"] == "warn"
    assert by_key["cmd_rsync"]["level"] == "warn"
    assert by_key["cmd_curl"]["level"] == "ok"


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


def test_machine_report_input_adapter_uses_latest_ai_policy_without_thermal_sample() -> None:
    root = Path("/var/lib/abyss-machine/doctor/machine-report")
    calls: list[str] = []
    paths = doctor_adapters.DoctorMachineReportInputPaths(
        root=root,
        latest_json=root / "latest.json",
        latest_markdown=root / "latest.md",
        artifacts=(
            doctor_adapters.DoctorMachineReportArtifactPath("doctor_latest", Path("/var/lib/abyss-machine/doctor/latest.json")),
            doctor_adapters.DoctorMachineReportArtifactPath("ai_policy_latest", Path("/var/lib/abyss-machine/ai/policy/latest.json")),
        ),
    )

    def collect_doctor() -> dict[str, Any]:
        calls.append("doctor")
        return {"ok": True, "summary": {"status": "ok", "checks": 2, "fails": 0, "warnings": 0}}

    def collect_memory() -> dict[str, Any]:
        calls.append("memory")
        return {
            "ok": True,
            "status": "observed_clean",
            "summary": {"swap_used_percent": 3.0, "psi_some_avg10": 0.0},
            "services": [
                {
                    "unit": "abyss-dictation-server.service",
                    "capability": "dictation",
                    "class": "resident",
                    "protected": True,
                    "systemd": {"active_state": "active", "main_pid": 4242},
                    "controls": {"memory_current": {"mib": 512}},
                    "issues": [{"code": "warmup"}],
                },
                {"unit": "unprotected.service", "protected": False},
            ],
        }

    def collect_nervous() -> dict[str, Any]:
        calls.append("nervous")
        return {
            "ok": True,
            "readiness": {
                "status": "ready",
                "semantic_ready": True,
                "semantic_stale": False,
                "semantic_maintenance_needed": False,
            },
        }

    port = doctor_adapters.DoctorMachineReportInputPort(
        collect_doctor=collect_doctor,
        collect_memory_residency=collect_memory,
        collect_nervous_brief=collect_nervous,
        read_ai_policy_latest=lambda: calls.append("ai_latest") or {
            "ok": True,
            "generated_at": "2026-06-28T09:20:00Z",
            "class": "light",
            "heavy_policy": "allowed",
            "can_run_heavy": True,
        },
        collect_ai_policy=lambda: calls.append("ai_live") or {
            "ok": True,
            "class": "warm",
            "heavy_policy": "sampled",
        },
        read_artifact=lambda label, path: {
            "label": label,
            "path": str(path),
            "exists": True,
            "load_error": None,
            "ok": True,
            "status": "ok",
        },
    )

    report = doctor_adapters.build_machine_report_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-28T09:21:00Z",
        no_thermal_sample=True,
        paths=paths,
        port=port,
    )

    assert calls == ["doctor", "memory", "nervous", "ai_latest"]
    assert report["status"] == "ok"
    assert report["policy"]["no_thermal_sample"] is True
    assert report["ai_policy"]["class"] == "light"
    assert [service["unit"] for service in report["protected_services"]] == ["abyss-dictation-server.service"]
    assert report["protected_services"][0]["issue_codes"] == ["warmup"]
    assert [artifact["label"] for artifact in report["artifacts"]] == ["doctor_latest", "ai_policy_latest"]
    assert report["paths"]["daily_jsonl_glob"].endswith("/YYYY/MM/YYYY-MM-DD.jsonl")


def test_machine_report_input_adapter_refreshes_ai_policy_when_latest_missing() -> None:
    root = Path("/var/lib/abyss-machine/doctor/machine-report")
    calls: list[str] = []
    paths = doctor_adapters.DoctorMachineReportInputPaths(
        root=root,
        latest_json=root / "latest.json",
        latest_markdown=root / "latest.md",
        artifacts=(),
    )
    port = doctor_adapters.DoctorMachineReportInputPort(
        collect_doctor=lambda: {"ok": True, "summary": {"status": "ok", "checks": 1, "fails": 0, "warnings": 0}},
        collect_memory_residency=lambda: {"ok": True, "status": "observed_clean", "summary": {}, "services": []},
        collect_nervous_brief=lambda: {
            "ok": True,
            "readiness": {
                "status": "ready",
                "semantic_ready": True,
                "semantic_stale": False,
                "semantic_maintenance_needed": False,
            },
        },
        read_ai_policy_latest=lambda: calls.append("ai_latest") or {"ok": False, "error": "missing"},
        collect_ai_policy=lambda: calls.append("ai_live") or {
            "ok": True,
            "generated_at": "2026-06-28T09:25:00Z",
            "class": "warm",
            "heavy_policy": "unrestricted",
            "can_run_heavy": True,
        },
        read_artifact=lambda label, path: {"label": label, "path": str(path), "exists": False, "load_error": None},
    )

    report = doctor_adapters.build_machine_report_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-28T09:26:00Z",
        no_thermal_sample=True,
        paths=paths,
        port=port,
    )

    assert calls == ["ai_latest", "ai_live"]
    assert report["status"] == "ok"
    assert report["ai_policy"]["class"] == "warm"


def test_safe_repair_adapter_runs_only_automatic_allowed_actions() -> None:
    calls: list[tuple[str, Any]] = []
    safe_actions = [
        {"action": "semantic_maintain", "automatic": True, "command": "abyss-machine nervous semantic-maintain --json"},
        {"action": "docs_mesh", "automatic": True, "command": "abyss-machine docs mesh --json"},
        {"action": "unknown_safe_action", "automatic": True},
        {"action": "semantic_maintain", "automatic": False},
    ]
    port = doctor_adapters.DoctorSafeRepairPort(
        semantic_maintain=lambda no_thermal_sample: calls.append(("semantic", no_thermal_sample)) or {
            "ok": True,
            "decision": "built",
            "summary": {"chunks": 12},
            "assessment": {"needed": True},
            "raw_private_payload": {"not": "copied"},
        },
        docs_mesh_build=lambda: calls.append(("docs", None)) or {
            "ok": True,
            "summary": {"status": "ok"},
            "path": "/var/lib/abyss-machine/docs/mesh/latest.json",
            "raw_private_payload": {"not": "copied"},
        },
    )

    results = doctor_adapters.collect_safe_repair_results(
        repair=True,
        safe_only=True,
        repair_policy={"enabled": True},
        safe_actions=safe_actions,
        no_thermal_sample=True,
        port=port,
    )

    assert calls == [("semantic", True), ("docs", None)]
    assert results == [
        {
            "action": "semantic_maintain",
            "ok": True,
            "decision": "built",
            "summary": {"chunks": 12},
            "assessment": {"needed": True},
        },
        {
            "action": "docs_mesh",
            "ok": True,
            "summary": {"status": "ok"},
            "path": "/var/lib/abyss-machine/docs/mesh/latest.json",
        },
    ]


def test_safe_repair_adapter_respects_repair_safe_only_and_policy_gates() -> None:
    calls: list[str] = []
    safe_actions = [{"action": "semantic_maintain", "automatic": True}]
    port = doctor_adapters.DoctorSafeRepairPort(
        semantic_maintain=lambda no_thermal_sample: calls.append("semantic") or {"ok": True},
        docs_mesh_build=lambda: calls.append("docs") or {"ok": True},
    )

    for repair, safe_only, policy in (
        (False, True, {"enabled": True}),
        (True, False, {"enabled": True}),
        (True, True, {"enabled": False}),
    ):
        assert doctor_adapters.collect_safe_repair_results(
            repair=repair,
            safe_only=safe_only,
            repair_policy=policy,
            safe_actions=safe_actions,
            no_thermal_sample=False,
            port=port,
        ) == []

    assert calls == []


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
