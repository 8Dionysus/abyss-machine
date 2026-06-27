from __future__ import annotations

from pathlib import Path
from typing import Any

from . import validation_contracts


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def _nested_get(data: Any, path: list[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def default_policy(
    *,
    schema_prefix: str,
    version: str,
    doctor_service: str,
    doctor_timer: str,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "doctor_policy_v1"),
        "version": version,
        "automation": {
            "scope": "user",
            "service": doctor_service,
            "timer": doctor_timer,
            "interval": "2h",
            "command": "abyss-machine doctor --repair --safe-only --json --no-thermal-sample",
            "machine_report_command": "abyss-machine doctor machine-report --json --no-thermal-sample",
            "stdout": "null",
            "priority": "nice+ionice",
        },
        "repair": {
            "enabled": True,
            "safe_only": True,
            "semantic_maintain": True,
            "docs_mesh": True,
            "privileged_actions": False,
            "project_repo_mutation": False,
            "large_downloads": False,
        },
        "status": {
            "active_change_records_are_watch": True,
            "doctor_timer_inactive_is_watch": True,
            "ai_quick_benchmark_missing_is_watch": True,
        },
        "non_claims": [
            "Doctor is a oneshot orchestrator, not a resident daemon.",
            "Doctor never performs privileged actions or project-repo mutations.",
            "Safe repair is limited to host-owned generated/read-model refresh routes.",
        ],
    }


def merge_policy(default: dict[str, Any], loaded: Any, *, path: Any, load_error: Any = None) -> dict[str, Any]:
    if not isinstance(loaded, dict):
        result = dict(default)
        result["_load_error"] = load_error
        result["_path"] = str(path)
        return result
    merged = dict(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            current = dict(merged.get(key) or {})
            current.update(value)
            merged[key] = current
        else:
            merged[key] = value
    merged["_path"] = str(path)
    merged["_load_error"] = load_error
    return merged


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
) -> dict[str, Any]:
    report_root = Path(str(refs["report_root"]))
    machine_report_root = Path(str(refs["machine_report_root"]))
    validate_root = Path(str(refs["validate_root"]))
    return {
        "schema": _schema(schema_prefix, "doctor_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(refs["root"]),
        "agent_entrypoint": str(refs["agent_entrypoint"]),
        "latest": str(refs["latest"]),
        "reports": {
            "root": str(report_root),
            "latest_markdown": str(refs["report_latest"]),
            "daily_glob": str(report_root / "YYYY" / "MM" / "YYYY-MM-DD.md"),
        },
        "machine_report": {
            "root": str(machine_report_root),
            "latest_json": str(refs["machine_report_latest"]),
            "latest_markdown": str(refs["machine_report_markdown_latest"]),
            "daily_jsonl_glob": str(machine_report_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "daily_markdown_glob": str(machine_report_root / "YYYY" / "MM" / "YYYY-MM-DD.md"),
        },
        "validate": {
            "root": str(validate_root),
            "latest": str(refs["validate_latest"]),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "policy": str(refs["policy"]),
        "systemd": {
            "scope": "user",
            "service": str(refs["service"]),
            "service_path": str(refs["service_path"]),
            "timer": str(refs["timer"]),
            "timer_path": str(refs["timer_path"]),
        },
        "commands": {
            "status": "abyss-machine doctor --json",
            "repair": "abyss-machine doctor --repair --safe-only --json",
            "report": "abyss-machine doctor report --markdown",
            "machine_report_json": "abyss-machine doctor machine-report --json",
            "machine_report_markdown": "abyss-machine doctor machine-report --markdown",
            "paths": "abyss-machine doctor paths --json",
            "validate": "abyss-machine doctor validate --json",
        },
        "policy_contract": {
            "raw_private_content": False,
            "resident_daemon": False,
            "privileged_actions": False,
            "repo_mutation": False,
        },
    }


def summary_from_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fails = sum(1 for check in checks if check.get("level") == "fail")
    warns = sum(1 for check in checks if check.get("level") == "warn")
    return {
        "status": "fail" if fails else "warn" if warns else "ok",
        "fails": fails,
        "warnings": warns,
        "checks": len(checks),
    }


def state(summary: dict[str, Any], checks: list[dict[str, Any]], safe_actions: list[dict[str, Any]]) -> str:
    if _safe_int(summary.get("fails")) > 0:
        return "blocked"
    if any(action.get("needed") for action in safe_actions):
        return "needs-maintenance"
    warn_keys = {str(item.get("key") or "") for item in checks if item.get("level") == "warn"}
    if warn_keys:
        return "watch"
    return "ok"


def readiness_score(summary: dict[str, Any]) -> int:
    checks = max(1, _safe_int(summary.get("checks"), 1))
    fails = _safe_int(summary.get("fails"))
    warnings_count = _safe_int(summary.get("warnings"))
    raw = 100 - fails * 25 - warnings_count * max(1, int(12 / checks * 10))
    return max(0, min(100, raw))


def document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    safe_actions: list[dict[str, Any]],
    repair_requested: bool,
    safe_only: bool,
    repair_results: list[dict[str, Any]],
    paths: dict[str, Any],
    policy_path: Any,
    policy_load_error: Any,
    repair_policy: Any,
) -> dict[str, Any]:
    summary = summary_from_checks(checks)
    return {
        "schema": _schema(schema_prefix, "doctor_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0,
        "state": state(summary, checks, safe_actions),
        "readiness_score": readiness_score(summary),
        "summary": summary,
        "checks": checks,
        "safe_actions": safe_actions,
        "repair": {
            "requested": repair_requested,
            "safe_only": safe_only,
            "performed": repair_results,
            "privileged_actions": False,
            "project_repo_mutation": False,
        },
        "paths": paths,
        "policy": {
            "path": str(policy_path),
            "load_error": policy_load_error,
            "repair": repair_policy,
        },
    }


def doctor_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, "doctor_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="Abyss Machine doctor/self-maintenance route",
        extra={"paths": dict(paths) if isinstance(paths, dict) else {}},
    )


def report_markdown(data: dict[str, Any]) -> str:
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    lines = [
        f"# Abyss Machine Doctor {data.get('generated_at')}",
        "",
        f"- state: `{data.get('state')}`",
        f"- status: `{summary.get('status')}`",
        f"- readiness_score: `{data.get('readiness_score')}`",
        f"- checks: `{summary.get('checks')}`",
        f"- fails: `{summary.get('fails')}`",
        f"- warnings: `{summary.get('warnings')}`",
        "",
        "## Non-OK Checks",
        "",
    ]
    non_ok = [item for item in data.get("checks", []) if isinstance(item, dict) and item.get("level") != "ok"]
    if non_ok:
        for item in non_ok:
            lines.append(f"- `{item.get('level')}` `{item.get('key')}`: {item.get('message')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Safe Actions", ""])
    actions = data.get("safe_actions") if isinstance(data.get("safe_actions"), list) else []
    if actions:
        for action in actions:
            lines.append(
                f"- `{action.get('action')}` needed=`{action.get('needed')}` automatic=`{action.get('automatic')}` command=`{action.get('command')}`"
            )
            if action.get("reason"):
                lines.append(f"  - reason: {action.get('reason')}")
    else:
        lines.append("- none")
    repair = data.get("repair") if isinstance(data.get("repair"), dict) else {}
    lines.extend(["", "## Repair", ""])
    lines.append(f"- requested: `{repair.get('requested')}`")
    lines.append(f"- safe_only: `{repair.get('safe_only')}`")
    performed = repair.get("performed") if isinstance(repair.get("performed"), list) else []
    if performed:
        for item in performed:
            lines.append(f"- `{item.get('action')}` ok=`{item.get('ok')}` decision=`{item.get('decision')}`")
    else:
        lines.append("- performed: none")
    lines.extend(["", "## Policy", ""])
    lines.append("- privileged_actions: `false`")
    lines.append("- project_repo_mutation: `false`")
    lines.append("- resident_daemon: `false`")
    lines.append("")
    return "\n".join(lines)


def report_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: Any,
    daily_path: Any,
    write_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "doctor_report_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": not write_errors,
        "path": str(latest_path),
        "daily": str(daily_path),
        "write_errors": write_errors,
    }


def artifact_entry(
    *,
    label: str,
    path: Any,
    exists: bool,
    load_error: Any,
    data: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "exists": bool(exists),
        "load_error": load_error,
    }
    if isinstance(data, dict):
        raw_status = (
            data.get("status")
            or data.get("state")
            or _nested_get(data, ["summary", "status"])
            or _nested_get(data, ["readiness", "status"])
        )
        if isinstance(raw_status, dict):
            raw_status = (
                raw_status.get("state")
                or raw_status.get("class")
                or _nested_get(raw_status, ["summary", "status"])
                or _nested_get(raw_status, ["readiness", "status"])
            )
        if isinstance(raw_status, list):
            raw_status = None
        item.update({
            "schema": data.get("schema"),
            "generated_at": data.get("generated_at"),
            "ok": data.get("ok"),
            "status": raw_status,
        })
        if isinstance(data.get("summary"), dict):
            summary = data.get("summary", {})
            item["summary"] = {
                key: summary.get(key)
                for key in (
                    "status",
                    "checks",
                    "fails",
                    "warnings",
                    "service_issues",
                    "environment_issues",
                    "memory_class",
                    "swap_used_percent",
                    "zram_logical_to_memory_ratio",
                    "psi_some_avg10",
                    "psi_full_avg10",
                )
                if key in summary
            }
    return item


def machine_report_service_summary(item: dict[str, Any]) -> dict[str, Any]:
    controls = item.get("controls") if isinstance(item.get("controls"), dict) else {}
    return {
        "unit": item.get("unit"),
        "capability": item.get("capability"),
        "class": item.get("class"),
        "protected": bool(item.get("protected")),
        "active_state": _nested_get(item, ["systemd", "active_state"]),
        "sub_state": _nested_get(item, ["systemd", "sub_state"]),
        "main_pid": _nested_get(item, ["systemd", "main_pid"]),
        "memory_current_mib": _nested_get(controls, ["memory_current", "mib"]),
        "memory_peak_mib": _nested_get(controls, ["memory_peak", "mib"]),
        "memory_swap_current_mib": _nested_get(controls, ["memory_swap_current", "mib"]),
        "memory_low_mib": _nested_get(controls, ["memory_low", "mib"]),
        "memory_high_mib": _nested_get(controls, ["memory_high", "mib"]),
        "memory_swap_max": _nested_get(controls, ["memory_swap_max", "raw"]),
        "sampled_pss_mib": _nested_get(item, ["process_rollup", "totals", "pss_mib"]),
        "sampled_swap_mib": _nested_get(item, ["process_rollup", "totals", "swap_mib"]),
        "cgroup_swap_to_sampled_pss_ratio": _nested_get(item, ["derived", "cgroup_swap_to_sampled_pss_ratio"]),
        "psi_some_avg10": _nested_get(item, ["cgroup", "pressure", "some", "avg10"]),
        "psi_full_avg10": _nested_get(item, ["cgroup", "pressure", "full", "avg10"]),
        "memory_events": _nested_get(item, ["cgroup", "events"]),
        "runtime_pilot_status": _nested_get(item, ["target", "runtime_pilot_status"]),
        "runtime_pilot_active": _nested_get(item, ["target", "runtime_pilot_active"]),
        "issue_codes": [
            issue.get("code")
            for issue in item.get("issues", [])
            if isinstance(issue, dict) and issue.get("code")
        ],
    }


def machine_report_status(
    doctor_data: dict[str, Any],
    memory_data: dict[str, Any],
    nervous_data: dict[str, Any],
    ai_policy_data: dict[str, Any],
) -> str:
    if not doctor_data.get("ok") or not memory_data.get("ok") or not nervous_data.get("ok") or not ai_policy_data.get("ok", True):
        return "blocked"
    if bool(_nested_get(nervous_data, ["readiness", "semantic_maintenance_needed"])):
        return "needs-maintenance"
    if str(memory_data.get("status") or "") != "observed_clean":
        return "watch"
    if bool(_nested_get(nervous_data, ["readiness", "semantic_stale"])):
        return "watch"
    return "ok"


def machine_report_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    doctor_data: dict[str, Any],
    memory_data: dict[str, Any],
    nervous_data: dict[str, Any],
    ai_policy_data: dict[str, Any],
    protected_services: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    paths: dict[str, Any],
    no_thermal_sample: bool,
) -> dict[str, Any]:
    mem_summary = memory_data.get("summary", {}) if isinstance(memory_data.get("summary"), dict) else {}
    doctor_summary = doctor_data.get("summary", {}) if isinstance(doctor_data.get("summary"), dict) else {}
    semantic_maintenance = _nested_get(nervous_data, ["current", "semantic", "maintenance"]) or {}
    ai_thermal = ai_policy_data.get("current", {}).get("thermal", {}) if isinstance(ai_policy_data.get("current"), dict) else {}
    status_value = machine_report_status(doctor_data, memory_data, nervous_data, ai_policy_data)
    return {
        "schema": _schema(schema_prefix, "doctor_machine_report_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": status_value != "blocked",
        "status": status_value,
        "summary": {
            "doctor_status": doctor_summary.get("status"),
            "doctor_checks": doctor_summary.get("checks"),
            "doctor_fails": doctor_summary.get("fails"),
            "doctor_warnings": doctor_summary.get("warnings"),
            "memory_residency_status": memory_data.get("status"),
            "zram_disk_mib": mem_summary.get("zram_disk_mib"),
            "zram_data_mib": mem_summary.get("zram_data_mib"),
            "zram_resident_mib": mem_summary.get("zram_resident_mib"),
            "zram_logical_free_mib": mem_summary.get("zram_logical_free_mib"),
            "zram_logical_to_memory_ratio": mem_summary.get("zram_logical_to_memory_ratio"),
            "swap_used_percent": mem_summary.get("swap_used_percent"),
            "psi_some_avg10": mem_summary.get("psi_some_avg10"),
            "psi_full_avg10": mem_summary.get("psi_full_avg10"),
            "protected_high_swap_units": mem_summary.get("protected_high_swap_units"),
            "runtime_pilot_active_units": mem_summary.get("runtime_pilot_active_units"),
            "runtime_pilot_missing_units": mem_summary.get("runtime_pilot_missing_units"),
            "nervous_readiness": _nested_get(nervous_data, ["readiness", "status"]),
            "semantic_ready": _nested_get(nervous_data, ["readiness", "semantic_ready"]),
            "semantic_stale": _nested_get(nervous_data, ["readiness", "semantic_stale"]),
            "semantic_maintenance_needed": _nested_get(nervous_data, ["readiness", "semantic_maintenance_needed"]),
            "ai_policy_class": ai_policy_data.get("class"),
            "ai_heavy_policy": ai_policy_data.get("heavy_policy"),
            "ai_can_run_heavy": ai_policy_data.get("can_run_heavy"),
            "ai_can_run_routed_heavy": ai_policy_data.get("can_run_routed_heavy"),
        },
        "memory": {
            "status": memory_data.get("status"),
            "summary": mem_summary,
            "environment_issues": memory_data.get("environment_issues"),
            "next_actions": memory_data.get("next_actions"),
            "non_claims": memory_data.get("non_claims"),
        },
        "nervous": {
            "readiness": nervous_data.get("readiness"),
            "semantic_maintenance": semantic_maintenance,
            "gaps": nervous_data.get("gaps"),
            "next_actions": nervous_data.get("next_actions"),
        },
        "ai_policy": {
            "class": ai_policy_data.get("class"),
            "heavy_policy": ai_policy_data.get("heavy_policy"),
            "can_run_heavy": ai_policy_data.get("can_run_heavy"),
            "can_run_routed_heavy": ai_policy_data.get("can_run_routed_heavy"),
            "reasons": ai_policy_data.get("reasons"),
            "thermal": {
                "current_temperature_c": ai_thermal.get("current_temperature_c"),
                "rolling_avg_temperature_c": ai_thermal.get("rolling_avg_temperature_c"),
                "recent_peak_temperature_c": ai_thermal.get("recent_peak_temperature_c"),
                "trend": ai_thermal.get("trend"),
                "hot_temperature_c": _nested_get(ai_policy_data, ["thresholds", "hot_temperature_c"]),
                "balanced_warm_heavy_max_c": _nested_get(ai_policy_data, ["thresholds", "balanced_warm_heavy_max_c"]),
                "episode_thresholds": _nested_get(ai_policy_data, ["thresholds", "episode"]),
            },
        },
        "protected_services": protected_services,
        "artifacts": artifacts,
        "guardrails": [
            "This report does not stop, disable, restart, throttle, re-affinitize, or cap live services.",
            "High protected-service swap is a warmup/measurement signal, not a stop recommendation.",
            "Do not set MemorySwapMax on currently high-swap live services before restart/warmup measurement.",
            "zram size is logical capacity; report resident memory, compression ratio, logical free space, and PSI before any sizing change.",
            "Thermal hot for this host begins above the configured hot threshold, not below the monitored active range.",
        ],
        "external_basis": [
            {
                "source": "Linux kernel zram documentation",
                "url": "https://www.kernel.org/doc/html/latest/admin-guide/blockdev/zram.html",
                "used_for": "Treat zram disksize as logical capacity and resident memory/compression stats as sizing evidence.",
            },
            {
                "source": "systemd resource control documentation",
                "url": "https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html",
                "used_for": "Use MemoryLow/MemoryHigh/MemorySwapMax as cgroup controls with service-level measurement.",
            },
            {
                "source": "Linux PSI documentation",
                "url": "https://docs.kernel.org/accounting/psi.html",
                "used_for": "Use PSI stall averages to distinguish occupied zram from active memory pressure.",
            },
        ],
        "paths": paths,
        "policy": {
            "facts_only": True,
            "resident_daemon": False,
            "heavy_probes": False,
            "no_thermal_sample": bool(no_thermal_sample),
        },
    }


def machine_report_markdown(data: dict[str, Any]) -> str:
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    memory = data.get("memory", {}) if isinstance(data.get("memory"), dict) else {}
    mem_summary = memory.get("summary", {}) if isinstance(memory.get("summary"), dict) else {}
    nervous = data.get("nervous", {}) if isinstance(data.get("nervous"), dict) else {}
    semantic = nervous.get("semantic_maintenance", {}) if isinstance(nervous.get("semantic_maintenance"), dict) else {}
    ai_policy_data = data.get("ai_policy", {}) if isinstance(data.get("ai_policy"), dict) else {}
    thermal = ai_policy_data.get("thermal", {}) if isinstance(ai_policy_data.get("thermal"), dict) else {}
    lines = [
        f"# Abyss Machine Report {data.get('generated_at')}",
        "",
        f"- status: `{data.get('status')}`",
        f"- doctor: `{summary.get('doctor_status')}` checks=`{summary.get('doctor_checks')}` warnings=`{summary.get('doctor_warnings')}`",
        f"- memory residency: `{summary.get('memory_residency_status')}` zram_used=`{mem_summary.get('swap_used_percent')}` psi_some=`{mem_summary.get('psi_some_avg10')}` psi_full=`{mem_summary.get('psi_full_avg10')}`",
        f"- nervous: `{summary.get('nervous_readiness')}` semantic_needed=`{summary.get('semantic_maintenance_needed')}` semantic_delta=`{semantic.get('delta_chunks')}`",
        f"- AI policy: `{summary.get('ai_policy_class')}` heavy=`{summary.get('ai_heavy_policy')}` temp=`{thermal.get('current_temperature_c')}` hot=`{thermal.get('hot_temperature_c')}`",
        "",
        "## Protected Services",
        "",
    ]
    services = data.get("protected_services") if isinstance(data.get("protected_services"), list) else []
    if services:
        for service in services:
            lines.append(
                "- "
                f"`{service.get('unit')}` active=`{service.get('active_state')}` "
                f"pid=`{service.get('main_pid')}` mem=`{service.get('memory_current_mib')}`MiB "
                f"swap=`{service.get('memory_swap_current_mib')}`MiB "
                f"pss=`{service.get('sampled_pss_mib')}`MiB "
                f"pilot=`{service.get('runtime_pilot_status')}` "
                f"issues=`{','.join(service.get('issue_codes') or [])}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Guardrails", ""])
    for item in data.get("guardrails", []):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## Paths", ""])
    paths = data.get("paths", {}) if isinstance(data.get("paths"), dict) else {}
    for key in ("latest_json", "latest_markdown", "daily_jsonl_glob", "daily_markdown_glob"):
        lines.append(f"- {key}: `{paths.get(key)}`")
    lines.append("")
    return "\n".join(lines)
