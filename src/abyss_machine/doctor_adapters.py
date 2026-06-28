from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


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
