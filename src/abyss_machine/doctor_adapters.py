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


@dataclass(frozen=True)
class DoctorSafeRepairPort:
    semantic_maintain: Callable[[bool], dict[str, Any]]
    docs_mesh_build: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DoctorCoreProbePaths:
    manifest: Path
    topology_doc: Path
    change_root: Path
    change_agent_entrypoint: Path
    change_index: Path
    topology_validate_latest: Path
    stack_bridge_validate_latest: Path
    binary: Path


@dataclass(frozen=True)
class DoctorCoreProbePort:
    platform_system: Callable[[], str]
    path_exists: Callable[[Path], bool]
    topology_validate: Callable[[], dict[str, Any]]
    stack_bridge_validate: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DoctorPowerCoolingProbePaths:
    cooling_latest: Path


@dataclass(frozen=True)
class DoctorPowerCoolingProbePort:
    power_status: Callable[[], dict[str, Any]]
    thermal_status: Callable[[], dict[str, Any]]
    cooling_status: Callable[[], dict[str, Any]]
    systemd_unit: Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class DoctorStorageProcessProbePaths:
    storage_policy: Path
    process_latest: Path


@dataclass(frozen=True)
class DoctorStorageProcessProbePort:
    storage_filesystems: Callable[[], list[dict[str, Any]]]
    storage_policy_document: Callable[[], dict[str, Any]]
    storage_hooks_status: Callable[[], dict[str, Any]]
    process_latest_summary: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DoctorSnapshotObservabilityProbePort:
    snapshots_status: Callable[[], dict[str, Any]]
    observability_status: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class DoctorDictationProbePaths:
    config: Path
    input_remapper_preset: Path


@dataclass(frozen=True)
class DoctorDictationProbePort:
    dictation_status: Callable[[], dict[str, Any]]
    systemd_unit: Callable[[str], dict[str, Any]]
    user_systemd_unit: Callable[[str], dict[str, Any]]
    path_exists: Callable[[Path], bool]


@dataclass(frozen=True)
class DoctorAiProbePaths:
    root: Path
    agent_entrypoint: Path
    index: Path
    config: Path
    tts_profiles_latest: Path
    report_latest: Path
    workload_latest: Path
    workload_stats_latest: Path


@dataclass(frozen=True)
class DoctorAiProbePort:
    path_exists: Callable[[Path], bool]
    ai_status: Callable[[], dict[str, Any]]
    ai_capabilities: Callable[[], dict[str, Any]]
    ai_tts_profiles: Callable[[], dict[str, Any]]
    ai_policy: Callable[[], dict[str, Any]]
    ai_storage_status: Callable[[], dict[str, Any]]
    ai_runtime_snapshot: Callable[[], dict[str, Any]]
    load_report_latest: Callable[[Path, str], dict[str, Any]]
    ai_workload_status: Callable[[], dict[str, Any]]
    systemd_unit: Callable[[str], dict[str, Any]]


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
    details: Any | None = None,
) -> None:
    item: dict[str, Any] = {"level": level, "key": key, "message": message}
    if details is not None:
        item["data"] = details
    checks.append(item)


def _validation_level(summary: dict[str, Any]) -> str:
    return "fail" if summary.get("fails") else "warn" if summary.get("warnings") else "ok"


def _nested_get(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
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


def collect_doctor_core_checks(
    *,
    paths: DoctorCoreProbePaths,
    commands: dict[str, Any],
    port: DoctorCoreProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    platform_name = port.platform_system()
    _add_check(
        checks,
        "ok" if platform_name == "Linux" else "fail",
        "platform",
        "Linux host" if platform_name == "Linux" else f"unsupported platform {platform_name}",
    )

    manifest_exists = port.path_exists(paths.manifest)
    _add_check(
        checks,
        "ok" if manifest_exists else "warn",
        "bridge_manifest",
        f"{paths.manifest} present" if manifest_exists else f"{paths.manifest} missing",
    )

    topology_doc_exists = port.path_exists(paths.topology_doc)
    _add_check(
        checks,
        "ok" if topology_doc_exists else "warn",
        "machine_topology_doc",
        f"{paths.topology_doc} present" if topology_doc_exists else f"{paths.topology_doc} missing",
    )

    change_agent_exists = port.path_exists(paths.change_agent_entrypoint)
    change_index_exists = port.path_exists(paths.change_index)
    if change_agent_exists and change_index_exists:
        _add_check(checks, "ok", "machine_change_ledger", f"{paths.change_root} ready")
    else:
        _add_check(
            checks,
            "warn",
            "machine_change_ledger",
            f"{paths.change_root} incomplete",
            {
                "agent_entrypoint": str(paths.change_agent_entrypoint),
                "agent_entrypoint_exists": change_agent_exists,
                "index": str(paths.change_index),
                "index_exists": change_index_exists,
            },
        )

    topology_validation = port.topology_validate()
    topology_summary = topology_validation.get("summary", {})
    _add_check(
        checks,
        _validation_level(topology_summary),
        "machine_topology_validate",
        f"topology validate {topology_summary.get('status')}",
        {
            "summary": topology_summary,
            "latest": str(paths.topology_validate_latest),
            "command": "abyss-machine topology validate --json",
        },
    )

    stack_bridge_validation = port.stack_bridge_validate()
    stack_bridge_summary = stack_bridge_validation.get("summary", {})
    _add_check(
        checks,
        _validation_level(stack_bridge_summary),
        "stack_bridge_validate",
        f"stack bridge validate {stack_bridge_summary.get('status')}",
        {
            "summary": stack_bridge_summary,
            "latest": str(paths.stack_bridge_validate_latest),
            "command": "abyss-machine stack-bridge validate --json",
        },
    )

    binary_exists = port.path_exists(paths.binary)
    _add_check(
        checks,
        "ok" if binary_exists else "warn",
        "binary",
        f"{paths.binary} present" if binary_exists else f"{paths.binary} missing",
    )

    for command in ("podman", "rsync", "curl"):
        if commands.get(command):
            _add_check(checks, "ok", f"cmd_{command}", f"cmd {command}")
        else:
            _add_check(checks, "warn", f"cmd_{command}", f"cmd {command} missing")

    return checks


def collect_doctor_power_cooling_checks(
    *,
    paths: DoctorPowerCoolingProbePaths,
    cooling_timer_name: str,
    port: DoctorPowerCoolingProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    power = port.power_status()
    power_unit = power["power_profiles_daemon"]
    _add_check(
        checks,
        "ok" if power_unit["is_active"] else "warn",
        "power_profiles_daemon",
        f"power-profiles-daemon {power_unit['active']}",
        power_unit,
    )

    auto_timer = power["auto_timer"]
    _add_check(
        checks,
        "ok" if auto_timer["is_active"] else "warn",
        "abyss_power_auto",
        f"abyss-power-profile-auto.timer {auto_timer['active']}",
        auto_timer,
    )

    thermal = port.thermal_status()
    thermald = thermal["thermald"]
    _add_check(
        checks,
        "ok" if thermald["is_active"] else "warn",
        "thermald",
        f"thermald {thermald['active']}",
        thermald,
    )

    cooling = port.cooling_status()
    cooling_fan = cooling.get("fan", {})
    _add_check(
        checks,
        "ok" if cooling_fan.get("available") and cooling.get("ok") else "warn",
        "cooling_backend",
        f"cooling backend fan_mode={cooling_fan.get('fan_mode')} platform={_nested_get(cooling, ['power', 'platform_profile', 'current'])}"
        if cooling_fan.get("available")
        else "cooling backend unavailable",
        {
            "fan": cooling_fan,
            "platform_profile": cooling.get("power", {}).get("platform_profile", {}),
            "latest": str(paths.cooling_latest),
        },
    )

    cooling_timer = port.systemd_unit(cooling_timer_name)
    _add_check(
        checks,
        "ok" if cooling_timer["is_active"] and cooling_timer["is_enabled"] else "warn",
        "cooling_reconcile_timer",
        f"{cooling_timer_name} {cooling_timer['active']}/{cooling_timer['enabled']}",
        cooling_timer,
    )

    return checks


def _storage_hook_dirs_ready(hooks_status: dict[str, Any]) -> bool:
    return all(
        directory.get("exists")
        for directory_list in hooks_status.get("directories", {}).values()
        for directory in directory_list
    )


def collect_doctor_storage_process_checks(
    *,
    paths: DoctorStorageProcessProbePaths,
    port: DoctorStorageProcessProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    storage = port.storage_filesystems()
    root_fs = next((item for item in storage if item.get("target") == "/"), None)
    srv_fs = next((item for item in storage if item.get("target") == "/srv"), None)
    if root_fs and root_fs.get("fstype") == "btrfs":
        _add_check(checks, "ok", "root_btrfs", "root filesystem is Btrfs", root_fs)
    else:
        _add_check(checks, "warn", "root_btrfs", "root filesystem is not detected as Btrfs", root_fs)
    if srv_fs:
        _add_check(checks, "ok", "srv_mount", f"/srv mounted as {srv_fs.get('fstype')}", srv_fs)
    else:
        _add_check(checks, "warn", "srv_mount", "/srv mount not detected")

    storage_policy = port.storage_policy_document()
    _add_check(
        checks,
        "ok" if storage_policy.get("ok") else "warn",
        "storage_policy",
        f"{paths.storage_policy} ready" if storage_policy.get("ok") else f"{paths.storage_policy} missing or invalid",
        {"path": str(paths.storage_policy), "load_error": storage_policy.get("load_error")},
    )

    hooks_status = port.storage_hooks_status()
    hook_dirs_ready = _storage_hook_dirs_ready(hooks_status)
    _add_check(
        checks,
        "ok" if hook_dirs_ready else "warn",
        "storage_hooks",
        "storage hook directories present" if hook_dirs_ready else "storage hook directories incomplete",
        hooks_status.get("summary"),
    )

    process_summary = port.process_latest_summary()
    _add_check(
        checks,
        "ok" if process_summary.get("ok") else "warn",
        "process_snapshot_latest",
        f"process snapshot latest: {process_summary.get('generated_at')}"
        if process_summary.get("ok")
        else "process snapshot latest missing",
        {"path": str(paths.process_latest), "summary": process_summary.get("summary")},
    )

    return checks


def collect_doctor_snapshot_observability_checks(
    *,
    observability_timer_name: str,
    latest_max_age_sec: int | float,
    port: DoctorSnapshotObservabilityProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    snapshots = port.snapshots_status()
    _add_check(
        checks,
        "ok" if snapshots["snapper_available"] else "warn",
        "snapper",
        "snapper available" if snapshots["snapper_available"] else "snapper missing",
    )
    _add_check(
        checks,
        "ok" if snapshots["root_config_exists"] else "warn",
        "snapper_root_config",
        "snapper root config present" if snapshots["root_config_exists"] else "snapper root config missing",
    )
    cleanup_timer = snapshots["timers"]["cleanup"]
    _add_check(
        checks,
        "ok" if cleanup_timer["is_active"] else "warn",
        "snapper_cleanup",
        f"snapper-cleanup.timer {cleanup_timer['active']}",
        cleanup_timer,
    )

    observability = port.observability_status()
    topology_ready = (
        observability["root_exists"]
        and observability["agent_entrypoint_exists"]
        and observability["index_exists"]
    )
    _add_check(
        checks,
        "ok" if topology_ready else "warn",
        "observability_topology",
        "observability topology present" if topology_ready else "observability topology incomplete",
        {
            "root_exists": observability["root_exists"],
            "agent_entrypoint_exists": observability["agent_entrypoint_exists"],
            "index_exists": observability["index_exists"],
        },
    )
    obs_timer = observability["timer"]
    _add_check(
        checks,
        "ok" if obs_timer["is_active"] and obs_timer["is_enabled"] else "warn",
        "observability_timer",
        f"{observability_timer_name} {obs_timer['active']}/{obs_timer['enabled']}",
        obs_timer,
    )
    latest = observability.get("latest")
    latest_age = latest.get("age_sec") if isinstance(latest, dict) else None
    latest_ok = isinstance(latest_age, (int, float)) and latest_age <= latest_max_age_sec
    _add_check(
        checks,
        "ok" if latest_ok else "warn",
        "observability_latest",
        f"observability latest sample age {latest_age}s" if latest_age is not None else "observability latest sample missing",
        latest,
    )

    return checks


def collect_doctor_dictation_checks(
    *,
    paths: DoctorDictationProbePaths,
    hotkey_service_name: str,
    server_service_name: str,
    input_remapper_service_name: str,
    port: DoctorDictationProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    dictation = port.dictation_status()
    dictation_commands = dictation["commands"]
    dictation_config_data = dictation.get("config", {})
    _add_check(
        checks,
        "ok" if dictation_config_data.get("exists") and not dictation_config_data.get("load_error") else "warn",
        "dictation_config",
        f"{paths.config} ready"
        if dictation_config_data.get("exists") and not dictation_config_data.get("load_error")
        else f"{paths.config} missing or invalid",
        dictation_config_data,
    )
    dictation_replacements_data = dictation.get("replacements", {})
    _add_check(
        checks,
        "ok" if dictation_replacements_data.get("exists") and int(dictation_replacements_data.get("count") or 0) > 0 else "warn",
        "dictation_replacements",
        "dictation replacements present"
        if dictation_replacements_data.get("exists") and int(dictation_replacements_data.get("count") or 0) > 0
        else "dictation replacements missing",
        dictation_replacements_data,
    )
    calibration = dictation_config_data.get("calibration", {}) if isinstance(dictation_config_data, dict) else {}
    _add_check(
        checks,
        "ok" if calibration.get("updated_at") else "warn",
        "dictation_mic_calibration",
        "dictation microphone calibration present"
        if calibration.get("updated_at")
        else "dictation microphone calibration not yet applied",
        calibration,
    )
    _add_check(
        checks,
        "ok" if dictation_commands["pw_record"] else "warn",
        "dictation_record",
        "pw-record available" if dictation_commands["pw_record"] else "pw-record missing",
    )
    _add_check(
        checks,
        "ok" if dictation_commands["wl_copy"] and dictation_commands["ydotool"] and dictation_commands["ydotool_socket"] else "warn",
        "dictation_insert",
        "clipboard + ydotool insertion ready"
        if dictation_commands["wl_copy"] and dictation_commands["ydotool"] and dictation_commands["ydotool_socket"]
        else "dictation insertion not fully ready",
        dictation_commands,
    )
    fast_profile = dictation["profiles"].get("fast", {})
    _add_check(
        checks,
        "ok" if fast_profile.get("model_dir_exists") else "warn",
        "dictation_fast_model",
        "dictation fast model present" if fast_profile.get("model_dir_exists") else "dictation fast model missing",
        fast_profile.get("model_dir"),
    )
    if dictation.get("default_profile") == "auto":
        policy = dictation_config_data.get("profile_policy", {})
        fallback_name = str(policy.get("fallback_profile", "quality")) if isinstance(policy, dict) else "quality"
        fallback_profile = dictation["profiles"].get(fallback_name, {})
        _add_check(
            checks,
            "ok" if fallback_profile.get("model_dir_exists") else "warn",
            "dictation_default_model",
            f"dictation auto profile ready (fallback {fallback_name})"
            if fallback_profile.get("model_dir_exists")
            else f"dictation auto fallback missing ({fallback_name})",
            {
                "default_profile": "auto",
                "fallback_profile": fallback_name,
                "fallback_model_dir": fallback_profile.get("model_dir"),
            },
        )
    else:
        default_profile = dictation["profiles"].get(dictation["default_profile"], {})
        _add_check(
            checks,
            "ok" if default_profile.get("model_dir_exists") else "warn",
            "dictation_default_model",
            f"dictation default model present ({dictation['default_profile']})"
            if default_profile.get("model_dir_exists")
            else f"dictation default model missing ({dictation['default_profile']})",
            default_profile.get("model_dir"),
        )

    hotkey_service = port.systemd_unit(hotkey_service_name)
    _add_check(
        checks,
        "ok" if hotkey_service["is_active"] and hotkey_service["is_enabled"] else "warn",
        "dictation_hotkey",
        f"{hotkey_service_name} {hotkey_service['active']}/{hotkey_service['enabled']}",
        hotkey_service,
    )
    server_service = port.user_systemd_unit(server_service_name)
    server_ready = server_service["is_active"] and dictation.get("server_socket_exists")
    _add_check(
        checks,
        "ok" if server_ready else "warn",
        "dictation_server",
        f"{server_service_name.removesuffix('.service')} warm model service ready"
        if server_ready
        else f"{server_service_name} {server_service['active']}/{server_service['enabled']}",
        {
            "service": server_service,
            "socket": dictation.get("server_socket"),
            "socket_exists": dictation.get("server_socket_exists"),
        },
    )
    input_remapper_service = port.systemd_unit(input_remapper_service_name)
    _add_check(
        checks,
        "ok" if input_remapper_service["is_active"] and input_remapper_service["is_enabled"] else "warn",
        "dictation_input_remapper",
        f"{input_remapper_service_name} {input_remapper_service['active']}/{input_remapper_service['enabled']}",
        input_remapper_service,
    )
    input_remapper_preset_exists = port.path_exists(paths.input_remapper_preset)
    _add_check(
        checks,
        "ok" if input_remapper_preset_exists else "warn",
        "dictation_input_remapper_preset",
        "input-remapper Copilot+/ preset present"
        if input_remapper_preset_exists
        else "input-remapper Copilot+/ preset missing",
        str(paths.input_remapper_preset),
    )

    return checks


def collect_doctor_ai_checks(
    *,
    ai_facts: dict[str, Any],
    paths: DoctorAiProbePaths,
    workload_timer_name: str,
    schema_prefix: str,
    port: DoctorAiProbePort,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    _add_check(
        checks,
        "ok" if ai_facts.get("dev_dri_present") else "warn",
        "gpu_dri",
        "/dev/dri present" if ai_facts.get("dev_dri_present") else "/dev/dri missing",
        ai_facts.get("dev_dri_nodes"),
    )
    _add_check(
        checks,
        "ok" if ai_facts.get("dev_accel_present") else "warn",
        "npu_accel",
        "/dev/accel present" if ai_facts.get("dev_accel_present") else "/dev/accel missing",
        ai_facts.get("dev_accel_nodes"),
    )
    _add_check(
        checks,
        "ok" if ai_facts.get("openvino_venv_exists") else "warn",
        "openvino_venv",
        "OpenVINO host venv present" if ai_facts.get("openvino_venv_exists") else "OpenVINO host venv missing",
        ai_facts.get("openvino_venv"),
    )

    ai_host = port.ai_status()
    ai_topology_ok = (
        port.path_exists(paths.root)
        and port.path_exists(paths.agent_entrypoint)
        and port.path_exists(paths.index)
        and port.path_exists(paths.config)
    )
    _add_check(
        checks,
        "ok" if ai_topology_ok else "warn",
        "ai_host_topology",
        "AI host topology present" if ai_topology_ok else "AI host topology incomplete",
        {
            "root": str(paths.root),
            "root_exists": port.path_exists(paths.root),
            "agent_entrypoint_exists": port.path_exists(paths.agent_entrypoint),
            "index_exists": port.path_exists(paths.index),
            "config_exists": port.path_exists(paths.config),
        },
    )

    devices = ai_host.get("devices") if isinstance(ai_host.get("devices"), dict) else {}
    ai_ready = devices.get("ready") if isinstance(devices.get("ready"), dict) else {}
    ai_available_devices = devices.get("available_devices") if isinstance(devices.get("available_devices"), list) else []
    _add_check(
        checks,
        "ok" if ai_ready.get("openvino") and ai_ready.get("gpu") else "warn",
        "ai_openvino_devices",
        f"OpenVINO devices available: {', '.join(str(item) for item in ai_available_devices)}"
        if ai_available_devices
        else "OpenVINO devices unavailable",
        ai_ready,
    )
    _add_check(
        checks,
        "ok" if ai_ready.get("npu") else "warn",
        "ai_npu_runtime",
        "OpenVINO NPU runtime ready" if ai_ready.get("npu") else "OpenVINO NPU runtime not ready",
        ai_ready,
    )

    models = ai_host.get("models") if isinstance(ai_host.get("models"), dict) else {}
    model_summary = models.get("summary") if isinstance(models.get("summary"), dict) else {}
    model_entries = _safe_int(model_summary.get("entries"))
    _add_check(
        checks,
        "ok" if model_entries > 0 else "warn",
        "ai_model_inventory",
        f"AI model inventory entries: {model_summary.get('entries')}"
        if model_entries > 0
        else "AI model inventory is empty",
        model_summary,
    )

    latest_benchmark = ai_host.get("benchmark") if isinstance(ai_host.get("benchmark"), dict) else {}
    _add_check(
        checks,
        "ok" if latest_benchmark.get("latest_ok") else "warn",
        "ai_benchmark_latest",
        f"AI quick benchmark latest: {latest_benchmark.get('latest_generated_at')}"
        if latest_benchmark.get("latest_ok")
        else "AI quick benchmark latest missing or failed",
        latest_benchmark,
    )
    latest_eval = ai_host.get("eval") if isinstance(ai_host.get("eval"), dict) else {}
    _add_check(
        checks,
        "ok" if latest_eval.get("latest_ok") else "warn",
        "ai_eval_latest",
        f"AI real eval latest: {latest_eval.get('latest_generated_at')}"
        if latest_eval.get("latest_ok")
        else "AI real eval latest missing or failed",
        latest_eval,
    )

    capabilities = port.ai_capabilities()
    capability_rows = capabilities.get("capabilities") if isinstance(capabilities.get("capabilities"), dict) else {}
    cap_statuses = {
        key: value.get("status")
        for key, value in capability_rows.items()
        if isinstance(value, dict)
    }
    _add_check(
        checks,
        "ok" if capabilities.get("ok") else "warn",
        "ai_capabilities",
        "AI capability registry ready" if capabilities.get("ok") else "AI capability registry degraded",
        cap_statuses,
    )

    tts_profiles = port.ai_tts_profiles()
    tts_summary = tts_profiles.get("summary") if isinstance(tts_profiles.get("summary"), dict) else {}
    tts_profile_count = _safe_int(tts_summary.get("profiles"))
    _add_check(
        checks,
        "ok" if tts_profile_count > 0 else "warn",
        "ai_tts_bridge",
        f"TTS profiles available: {tts_summary.get('profiles')} executable={tts_summary.get('executable')}"
        if tts_profile_count > 0
        else "TTS profiles missing",
        {
            "latest": str(paths.tts_profiles_latest),
            "summary": tts_summary,
        },
    )

    policy = port.ai_policy()
    _add_check(
        checks,
        "ok" if policy.get("ok") else "warn",
        "ai_policy",
        f"AI policy {policy.get('class')} heavy={policy.get('can_run_heavy')} routed={policy.get('can_run_routed_heavy')}",
        {"class": policy.get("class"), "heavy_policy": policy.get("heavy_policy"), "reasons": policy.get("reasons")},
    )

    storage_status_data = port.ai_storage_status()
    storage_summary = storage_status_data.get("summary") if isinstance(storage_status_data.get("summary"), dict) else {}
    stack_cache_dirs = _safe_int(storage_summary.get("stack_local_openvino_cache_dirs"))
    _add_check(
        checks,
        "ok" if stack_cache_dirs == 0 else "warn",
        "ai_storage_hygiene",
        "no stack-local OpenVINO model_cache dirs"
        if stack_cache_dirs == 0
        else f"{stack_cache_dirs} stack-local OpenVINO model_cache dirs present",
        storage_summary,
    )

    runtime_snapshot = port.ai_runtime_snapshot()
    current_runtime = runtime_snapshot.get("current") if isinstance(runtime_snapshot.get("current"), dict) else {}
    _add_check(
        checks,
        "ok" if runtime_snapshot.get("ok") else "warn",
        "ai_runtime_snapshot",
        "AI runtime lifecycle snapshot ready" if runtime_snapshot.get("ok") else "AI runtime lifecycle snapshot failed",
        {
            "openvino_version": current_runtime.get("openvino_version"),
            "devices": current_runtime.get("available_devices"),
            "drift": runtime_snapshot.get("drift_from_previous_latest"),
        },
    )

    report_latest = port.load_report_latest(paths.report_latest, f"{schema_prefix}_ai_report_latest_read_v1")
    _add_check(
        checks,
        "ok" if report_latest.get("ok") else "warn",
        "ai_report_latest",
        f"AI report latest: {report_latest.get('generated_at')}"
        if report_latest.get("ok")
        else "AI report latest missing or failed",
        {"path": str(paths.report_latest), "error": report_latest.get("error")},
    )

    workload_status = port.ai_workload_status()
    workload_summary = workload_status.get("summary") if isinstance(workload_status.get("summary"), dict) else {}
    workload_records = _safe_int(workload_summary.get("records"))
    _add_check(
        checks,
        "ok" if workload_records > 0 else "warn",
        "ai_workload_stats",
        f"AI workload stats records: {workload_summary.get('records')}"
        if workload_records > 0
        else "AI workload stats have no measured records yet",
        {
            "latest": str(paths.workload_latest),
            "stats_latest": str(paths.workload_stats_latest),
            "summary": workload_summary,
            "routing": workload_status.get("routing"),
        },
    )
    workload_timer = port.systemd_unit(workload_timer_name)
    _add_check(
        checks,
        "ok" if workload_timer.get("is_active") and workload_timer.get("is_enabled") else "warn",
        "ai_workload_refresh_timer",
        f"{workload_timer_name} {workload_timer.get('active')}/{workload_timer.get('enabled')}",
        workload_timer,
    )

    return checks


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


def _repair_policy_enabled(repair_policy: Any) -> bool:
    if not isinstance(repair_policy, dict):
        return True
    return bool(repair_policy.get("enabled", True))


def _semantic_maintain_repair_result(action: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action.get("action"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "summary": result.get("summary"),
        "assessment": result.get("assessment"),
    }


def _docs_mesh_repair_result(action: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action.get("action"),
        "ok": result.get("ok"),
        "summary": result.get("summary"),
        "path": result.get("path"),
    }


def collect_safe_repair_results(
    *,
    repair: bool,
    safe_only: bool,
    repair_policy: Any,
    safe_actions: list[dict[str, Any]],
    no_thermal_sample: bool,
    port: DoctorSafeRepairPort,
) -> list[dict[str, Any]]:
    if not repair or not safe_only or not _repair_policy_enabled(repair_policy):
        return []
    results: list[dict[str, Any]] = []
    for action in safe_actions:
        if not isinstance(action, dict) or not action.get("automatic"):
            continue
        action_name = action.get("action")
        if action_name == "semantic_maintain":
            result = port.semantic_maintain(no_thermal_sample)
            results.append(_semantic_maintain_repair_result(action, result))
        elif action_name == "docs_mesh":
            result = port.docs_mesh_build()
            results.append(_docs_mesh_repair_result(action, result))
    return results


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
