from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import doctor_contracts


@dataclass(frozen=True)
class DoctorValidatePaths:
    root: Path
    agent_entrypoint: Path
    policy: Path
    latest: Path
    report_latest: Path
    machine_report_latest: Path
    machine_report_markdown_latest: Path
    service_path: Path
    timer_path: Path


@dataclass(frozen=True)
class DoctorValidateProbePort:
    path_exists: Callable[[Path], bool]
    load_latest_json: Callable[[Path, str], dict[str, Any]]
    user_systemd_unit: Callable[[str], dict[str, Any]]
    bridge_manifest: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DoctorReportWritePaths:
    latest_markdown: Path
    daily_markdown: Path


@dataclass(frozen=True)
class DoctorMachineReportWritePaths:
    latest_json: Path
    history_root: Path
    latest_markdown: Path
    daily_markdown: Path


@dataclass(frozen=True)
class DoctorMachineReportArtifactPath:
    label: str
    path: Path


@dataclass(frozen=True)
class DoctorMachineReportInputPaths:
    root: Path
    latest_json: Path
    latest_markdown: Path
    artifacts: tuple[DoctorMachineReportArtifactPath, ...]


@dataclass(frozen=True)
class DoctorReportWritePort:
    write_text: Callable[[Path, str, int], dict[str, Any] | None]


@dataclass(frozen=True)
class DoctorMachineReportWritePort:
    write_latest_and_history: Callable[[dict[str, Any], Path, Path], list[dict[str, Any]]]
    write_text: Callable[[Path, str, int], dict[str, Any] | None]


@dataclass(frozen=True)
class DoctorArtifactReadPort:
    load_json_document: Callable[[Path], tuple[Any, Any]]
    path_exists: Callable[[Path], bool]


@dataclass(frozen=True)
class DoctorMachineReportInputPort:
    collect_doctor: Callable[[], dict[str, Any]]
    collect_memory_residency: Callable[[], dict[str, Any]]
    collect_nervous_brief: Callable[[], dict[str, Any]]
    read_ai_policy_latest: Callable[[], dict[str, Any]]
    collect_ai_policy: Callable[[], dict[str, Any]]
    read_artifact: Callable[[str, Path], dict[str, Any]]


REQUIRED_DOCTOR_BRIDGE_COMMANDS: tuple[str, ...] = (
    "doctor_json",
    "doctor_paths_json",
    "doctor_report_markdown",
    "doctor_machine_report_json",
    "doctor_machine_report_markdown",
    "doctor_validate_json",
    "doctor_repair_json",
)


def _add_check(
    checks: list[dict[str, Any]],
    level: str,
    key: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["data"] = details
    checks.append(item)


def collect_doctor_validate_checks(
    *,
    schema_prefix: str,
    paths: DoctorValidatePaths,
    policy_doc: dict[str, Any],
    timer_name: str,
    port: DoctorValidateProbePort,
    required_bridge_commands: tuple[str, ...] = REQUIRED_DOCTOR_BRIDGE_COMMANDS,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    root_exists = port.path_exists(paths.root)
    _add_check(
        checks,
        "ok" if root_exists else "fail",
        "root",
        f"{paths.root} present" if root_exists else f"{paths.root} missing",
        {"path": str(paths.root)},
    )

    agent_exists = port.path_exists(paths.agent_entrypoint)
    _add_check(
        checks,
        "ok" if agent_exists else "fail",
        "agent_card",
        f"{paths.agent_entrypoint} present" if agent_exists else f"{paths.agent_entrypoint} missing",
        {"path": str(paths.agent_entrypoint)},
    )

    policy_exists = port.path_exists(paths.policy)
    policy_level = "ok" if policy_exists and not policy_doc.get("_load_error") else ("fail" if policy_exists else "warn")
    _add_check(
        checks,
        policy_level,
        "policy",
        f"{paths.policy} valid" if policy_level == "ok" else (
            f"{paths.policy} invalid" if policy_exists else "doctor policy uses embedded defaults; /etc install requires operator auth"
        ),
        {"path": str(paths.policy), "load_error": policy_doc.get("_load_error")},
    )

    latest = port.load_latest_json(paths.latest, f"{schema_prefix}_doctor_v1")
    _add_check(
        checks,
        "ok" if latest.get("ok") else "warn",
        "latest",
        "doctor latest is readable" if latest.get("ok") else "doctor latest missing or invalid",
        {"path": str(paths.latest), "error": latest.get("error")},
    )

    report_exists = port.path_exists(paths.report_latest)
    _add_check(
        checks,
        "ok" if report_exists else "warn",
        "report",
        f"{paths.report_latest} present" if report_exists else "doctor markdown report missing",
        {"path": str(paths.report_latest)},
    )

    machine_latest = port.load_latest_json(paths.machine_report_latest, f"{schema_prefix}_doctor_machine_report_v1")
    machine_latest_readable = bool(
        machine_latest.get("schema") == f"{schema_prefix}_doctor_machine_report_v1"
        and machine_latest.get("generated_at")
        and not machine_latest.get("error")
    )
    _add_check(
        checks,
        "ok" if machine_latest_readable else "warn",
        "machine_report_json",
        "doctor machine report latest is readable"
        if machine_latest_readable
        else "doctor machine report latest missing or invalid",
        {
            "path": str(paths.machine_report_latest),
            "error": machine_latest.get("error"),
            "ok": machine_latest.get("ok"),
            "status": machine_latest.get("status"),
        },
    )

    machine_markdown_exists = port.path_exists(paths.machine_report_markdown_latest)
    _add_check(
        checks,
        "ok" if machine_markdown_exists else "warn",
        "machine_report_markdown",
        f"{paths.machine_report_markdown_latest} present"
        if machine_markdown_exists
        else "doctor machine report markdown missing",
        {"path": str(paths.machine_report_markdown_latest)},
    )

    service_exists = port.path_exists(paths.service_path)
    _add_check(
        checks,
        "ok" if service_exists else "fail",
        "systemd_service_file",
        f"{paths.service_path} present" if service_exists else f"{paths.service_path} missing",
        {"path": str(paths.service_path)},
    )

    timer_exists = port.path_exists(paths.timer_path)
    _add_check(
        checks,
        "ok" if timer_exists else "fail",
        "systemd_timer_file",
        f"{paths.timer_path} present" if timer_exists else f"{paths.timer_path} missing",
        {"path": str(paths.timer_path)},
    )

    timer = port.user_systemd_unit(timer_name)
    _add_check(
        checks,
        "ok" if timer.get("is_active") and timer.get("is_enabled") else "warn",
        "systemd_timer_state",
        f"{timer_name} {timer.get('active')}/{timer.get('enabled')}",
        timer,
    )

    bridge = port.bridge_manifest()
    commands = bridge.get("commands") if isinstance(bridge.get("commands"), dict) else {}
    missing_commands = [key for key in required_bridge_commands if key not in commands]
    _add_check(
        checks,
        "ok" if not missing_commands else "fail",
        "bridge_commands",
        "bridge exposes doctor commands" if not missing_commands else "bridge misses doctor commands",
        {"missing": missing_commands},
    )

    return checks


def daily_markdown_path(root: Path, now: dt.datetime) -> Path:
    local_now = now.astimezone() if now.tzinfo is not None else now
    return root / f"{local_now.year:04d}" / f"{local_now.month:02d}" / f"{local_now.strftime('%Y-%m-%d')}.md"


def write_doctor_report(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    data: dict[str, Any],
    paths: DoctorReportWritePaths,
    port: DoctorReportWritePort,
    mode: int = 0o664,
) -> dict[str, Any]:
    text = doctor_contracts.report_markdown(data)
    errors = [
        error
        for error in (
            port.write_text(paths.latest_markdown, text, mode),
            port.write_text(paths.daily_markdown, text, mode),
        )
        if error
    ]
    return doctor_contracts.report_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        latest_path=paths.latest_markdown,
        daily_path=paths.daily_markdown,
        write_errors=errors,
    )


def read_machine_report_artifact(
    *,
    label: str,
    path: Path,
    port: DoctorArtifactReadPort,
) -> dict[str, Any]:
    data, error = port.load_json_document(path)
    return doctor_contracts.artifact_entry(
        label=label,
        path=path,
        exists=port.path_exists(path),
        load_error=error,
        data=data,
    )


def machine_report_paths_document(paths: DoctorMachineReportInputPaths) -> dict[str, Any]:
    return {
        "root": str(paths.root),
        "latest_json": str(paths.latest_json),
        "latest_markdown": str(paths.latest_markdown),
        "daily_jsonl_glob": str(paths.root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "daily_markdown_glob": str(paths.root / "YYYY" / "MM" / "YYYY-MM-DD.md"),
    }


def _machine_report_ai_policy(no_thermal_sample: bool, port: DoctorMachineReportInputPort) -> dict[str, Any]:
    if no_thermal_sample:
        latest = port.read_ai_policy_latest()
        if latest.get("generated_at") and not latest.get("error"):
            return latest
    return port.collect_ai_policy()


def collect_machine_report_inputs(
    *,
    no_thermal_sample: bool,
    paths: DoctorMachineReportInputPaths,
    port: DoctorMachineReportInputPort,
) -> dict[str, Any]:
    doctor_data = port.collect_doctor()
    memory_data = port.collect_memory_residency()
    nervous_data = port.collect_nervous_brief()
    ai_policy_data = _machine_report_ai_policy(no_thermal_sample, port)
    services = memory_data.get("services") if isinstance(memory_data.get("services"), list) else []
    protected_services = [
        doctor_contracts.machine_report_service_summary(item)
        for item in services
        if isinstance(item, dict) and item.get("protected")
    ]
    artifacts = [
        port.read_artifact(artifact.label, artifact.path)
        for artifact in paths.artifacts
    ]
    return {
        "doctor_data": doctor_data,
        "memory_data": memory_data,
        "nervous_data": nervous_data,
        "ai_policy_data": ai_policy_data,
        "protected_services": protected_services,
        "artifacts": artifacts,
        "paths": machine_report_paths_document(paths),
    }


def build_machine_report_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    no_thermal_sample: bool,
    paths: DoctorMachineReportInputPaths,
    port: DoctorMachineReportInputPort,
) -> dict[str, Any]:
    inputs = collect_machine_report_inputs(
        no_thermal_sample=no_thermal_sample,
        paths=paths,
        port=port,
    )
    return doctor_contracts.machine_report_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        doctor_data=inputs["doctor_data"],
        memory_data=inputs["memory_data"],
        nervous_data=inputs["nervous_data"],
        ai_policy_data=inputs["ai_policy_data"],
        protected_services=inputs["protected_services"],
        artifacts=inputs["artifacts"],
        paths=inputs["paths"],
        no_thermal_sample=no_thermal_sample,
    )


def write_machine_report_outputs(
    *,
    data: dict[str, Any],
    paths: DoctorMachineReportWritePaths,
    port: DoctorMachineReportWritePort,
    mode: int = 0o664,
) -> dict[str, Any]:
    markdown = doctor_contracts.machine_report_markdown(data)
    errors = list(port.write_latest_and_history(data, paths.latest_json, paths.history_root))
    errors.extend(
        error
        for error in (
            port.write_text(paths.latest_markdown, markdown, mode),
            port.write_text(paths.daily_markdown, markdown, mode),
        )
        if error
    )
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data
