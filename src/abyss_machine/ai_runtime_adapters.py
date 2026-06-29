from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Iterable, Mapping

from . import ai_runtime_contracts


RunPort = Callable[..., Mapping[str, Any]]
SubprocessRunPort = Callable[..., Any]
MonotonicPort = Callable[[], float]
CommandExistsPort = Callable[[str], bool]
WhichPort = Callable[[str], str | None]
PathExistsPort = Callable[[Path], bool]
PathAccessPort = Callable[[Path, int], bool]
ResourceSnapshotPort = Callable[[], Mapping[str, Any]]
ResourceProfilePort = Callable[[dict[str, Any], dict[str, Any], str, str], dict[str, Any]]
SystemdUnitPort = Callable[[str], Mapping[str, Any]]
StorageProtectionPort = Callable[[Path], Mapping[str, Any]]
RelativeToPort = Callable[[Path, Path], bool]
WalkPort = Callable[[Path], Iterable[tuple[str, list[str], list[str]]]]
TimestampPort = Callable[[], str]
RuntimeInfoPort = Callable[[], Mapping[str, Any]]
PolicyGatePort = Callable[[str, str, bool], Mapping[str, Any]]
OpenVINOSmokePort = Callable[[str, float], Mapping[str, Any]]
EvalSuiteRunnerPort = Callable[[], Mapping[str, Any]]
JsonWritePort = Callable[[Path, Mapping[str, Any], int], Any]
JsonlAppendPort = Callable[[Path, Mapping[str, Any], int], Any]
DailyPathPort = Callable[[], Path]
Sha256PathPort = Callable[[Path], str]
LatestHistoryWritePort = Callable[[dict[str, Any], Path, Path], list[dict[str, Any]]]
WorkloadUpdatePort = Callable[[Mapping[str, Any]], Mapping[str, Any]]
WorkloadAppendPort = Callable[[list[dict[str, Any]], bool], Mapping[str, Any]]
WorkloadExtractPort = Callable[[dict[str, Any]], list[dict[str, Any]]]
NoArgMappingPort = Callable[[], Mapping[str, Any]]
JsonReadPort = Callable[[Path], tuple[Any, str | None]]
TokenResolverPort = Callable[[Mapping[str, Any]], Mapping[str, Any]]
TokenCountSubprocessPort = Callable[..., Mapping[str, Any]]
LLMRuntimeStatusPort = Callable[[Mapping[str, Any], Mapping[str, Any] | None], Mapping[str, Any]]
LLMProfileStatusPort = Callable[[str, str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]
SttTranscribePort = Callable[[str, str], Mapping[str, Any]]


OPENVINO_RUNTIME_QUERY_SCRIPT = r'''
import json
try:
    import openvino as ov
    core = ov.Core()
    info = {
        "ok": True,
        "openvino_version": getattr(ov, "__version__", None),
        "available_devices": list(core.available_devices),
        "device_properties": {},
    }
    for device in core.available_devices:
        props = {}
        for key in ("FULL_DEVICE_NAME", "DEVICE_TYPE", "OPTIMIZATION_CAPABILITIES"):
            try:
                props[key] = core.get_property(device, key)
            except Exception as exc:
                props[key] = {"error": str(exc)}
        info["device_properties"][device] = props
except Exception as exc:
    info = {"ok": False, "error": repr(exc)}
print(json.dumps(info, default=str, sort_keys=False))
'''


PYTHON_RUNTIME_VERSION_SCRIPT = r'''
import json
import importlib.metadata as metadata
packages = ["openvino", "openvino-genai", "optimum-intel", "transformers", "numpy", "torch", "huggingface-hub", "qwen-tts", "babelvox", "soundfile", "librosa"]
versions = {}
for package in packages:
    try:
        versions[package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        versions[package] = None
print(json.dumps({"ok": True, "packages": versions}, sort_keys=False))
'''


def default_walk(root: Path) -> Iterable[tuple[str, list[str], list[str]]]:
    return os.walk(root)


def _path_exists(path: Path, path_exists: PathExistsPort) -> bool:
    try:
        return bool(path_exists(path))
    except OSError:
        return False


def _path_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _python_exists(python: str | None, path_exists: PathExistsPort) -> bool:
    if not python:
        return False
    return _path_exists(Path(str(python)), path_exists)


def model_roots(config: Mapping[str, Any]) -> list[Path]:
    roots: list[Path] = []
    raw_roots = config.get("model_roots", []) if isinstance(config, Mapping) else []
    for raw in raw_roots if isinstance(raw_roots, list) else []:
        if raw is None:
            continue
        try:
            path = Path(str(raw)).expanduser()
        except TypeError:
            continue
        if path not in roots:
            roots.append(path)
    return roots


def openvino_runtime_info(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_command: RunPort,
    which: WhichPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    openvino_config = config.get("openvino", {}) if isinstance(config.get("openvino"), Mapping) else {}
    python = which("abyss-openvino-python") or str(openvino_config.get("python", ""))
    if not python or not _path_exists(Path(python), path_exists):
        return {
            "schema": f"{schema_prefix}_ai_openvino_runtime_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "python": python or None,
            "error": "abyss-openvino-python not found",
        }

    out = dict(run_command([python, "-c", OPENVINO_RUNTIME_QUERY_SCRIPT], timeout=12.0))
    data = ai_runtime_contracts.parse_json_stdout(str(out.get("stdout") or ""))
    if data is None:
        return {
            "schema": f"{schema_prefix}_ai_openvino_runtime_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "python": python,
            "error": "OpenVINO query returned invalid JSON",
            "returncode": out.get("returncode"),
            "stderr": str(out.get("stderr") or "")[-1000:],
            "stdout_tail": str(out.get("stdout") or "")[-1000:],
        }
    data.setdefault("schema", f"{schema_prefix}_ai_openvino_runtime_v1")
    data["version"] = version
    data["generated_at"] = generated_at
    data["python"] = python
    data["returncode"] = out.get("returncode")
    data["stderr"] = out.get("stderr")
    return data


def openvino_smoke_device(
    *,
    device: str,
    timeout_sec: float,
    python: str | None,
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.openvino_smoke_missing_python(device)

    before = dict(resource_snapshot())
    out = dict(run_command(ai_runtime_contracts.openvino_smoke_command(str(python), device), timeout=timeout_sec))
    after = dict(resource_snapshot())
    return ai_runtime_contracts.openvino_smoke_result(
        device,
        out,
        resource_profile(before, after, "child_process", "OpenVINO smoke subprocess"),
    )


def openvino_embedding_eval(
    *,
    model_dir: Path,
    device: str,
    cache_dir: Path,
    timeout_sec: float,
    python: str | None,
    subprocess_env: Mapping[str, str],
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _path_exists(model_dir, path_exists):
        return ai_runtime_contracts.embedding_eval_missing_model(model_dir)
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.embedding_eval_missing_python()

    before = dict(resource_snapshot())
    out = dict(
        run_command(
            ai_runtime_contracts.embedding_eval_command(str(python), model_dir, device, cache_dir),
            timeout=timeout_sec,
            env=dict(subprocess_env),
        )
    )
    after = dict(resource_snapshot())
    return ai_runtime_contracts.embedding_eval_result(
        out,
        resource_profile(before, after, "child_process", "embedding eval subprocess"),
    )


def openvino_text_eval(
    *,
    model_dir: Path,
    device: str,
    cache_dir: Path,
    prompt: str,
    timeout_sec: float,
    python: str | None,
    subprocess_env: Mapping[str, str],
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _path_exists(model_dir, path_exists):
        return ai_runtime_contracts.text_eval_missing_model(model_dir)
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.text_eval_missing_python()

    before = dict(resource_snapshot())
    out = dict(
        run_command(
            ai_runtime_contracts.text_eval_command(str(python), model_dir, device, cache_dir, prompt),
            timeout=timeout_sec,
            env=dict(subprocess_env),
        )
    )
    after = dict(resource_snapshot())
    return ai_runtime_contracts.text_eval_result(
        out,
        resource_profile(before, after, "child_process", "OpenVINO GenAI text eval subprocess"),
    )


def run_openvino_benchmark_suite(
    *,
    devices: list[str] | None,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    policy_gate: PolicyGatePort,
    runtime_info: RuntimeInfoPort,
    smoke_device: OpenVINOSmokePort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
    workload_update: WorkloadUpdatePort | None = None,
) -> dict[str, Any]:
    resources_before = dict(resource_snapshot())
    benchmark_config = dict(config.get("benchmark", {})) if isinstance(config.get("benchmark"), Mapping) else {}
    requested = ai_runtime_contracts.openvino_benchmark_requested_devices(devices, benchmark_config)
    gate = dict(policy_gate("probe", "ai benchmark --quick", False))
    runtime = dict(runtime_info())
    available = runtime.get("available_devices") if isinstance(runtime.get("available_devices"), list) else []
    device_plan = ai_runtime_contracts.openvino_benchmark_device_plan(
        requested_devices=requested,
        available_devices=available,
        benchmark_config=benchmark_config,
    )
    results: list[dict[str, Any]] = []
    for item in device_plan:
        if not item.get("available"):
            skip_result = item.get("skip_result")
            if isinstance(skip_result, Mapping):
                results.append(dict(skip_result))
            else:
                results.append(ai_runtime_contracts.openvino_benchmark_skipped_device_result(str(item.get("device") or "")))
            continue
        results.append(dict(smoke_device(str(item["device"]), float(item["timeout_sec"]))))

    resources_after = dict(resource_snapshot())
    data = ai_runtime_contracts.openvino_benchmark_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        gate=gate,
        requested_devices=requested,
        available_devices=available,
        runtime=runtime,
        results=results,
        resource_profile=resource_profile(resources_before, resources_after, "child_process", "whole quick benchmark command"),
    )
    if write_latest:
        latest_error = write_json(latest_path, data, 0o664)
        daily_error = append_jsonl(daily_path(), data, 0o664)
        write_errors = [error for error in (latest_error, daily_error) if error]
        if write_errors:
            data["write_errors"] = write_errors
        if workload_update is not None:
            data["workload_update"] = dict(workload_update(data))
    return data


def run_eval_suite(
    *,
    requested_suite: str,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    class_levels: Mapping[str, int],
    policy_gate: PolicyGatePort,
    suite_runners: Mapping[str, EvalSuiteRunnerPort],
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    openvino_cache_root: Path,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
    workload_update: WorkloadUpdatePort | None = None,
    force: bool = False,
) -> dict[str, Any]:
    resources_before = dict(resource_snapshot())
    eval_config = dict(config.get("eval", {})) if isinstance(config.get("eval"), Mapping) else {}
    suites = ai_runtime_contracts.eval_suites_for_request(requested_suite, eval_config)
    declared_class = ai_runtime_contracts.highest_workload_class(
        [ai_runtime_contracts.eval_suite_declared_class(item) for item in suites],
        dict(class_levels),
    )
    gate = dict(policy_gate(declared_class, f"ai eval --suite {requested_suite}", force))
    if not gate.get("ok"):
        denied = ai_runtime_contracts.policy_denied_result(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now_iso(),
            command="ai eval",
            requested_suite=requested_suite,
            suites=suites,
            gate=gate,
        )
        denied["resource_profile"] = resource_profile(
            resources_before,
            dict(resource_snapshot()),
            "policy_check_only",
            "eval denied before model execution",
        )
        return denied

    results: list[dict[str, Any]] = []
    for item in ai_runtime_contracts.eval_suite_execution_plan(suites):
        suite_name = str(item.get("suite"))
        runner = suite_runners.get(suite_name)
        if runner is not None:
            results.append(dict(runner()))
            continue
        result = item.get("result") if isinstance(item.get("result"), Mapping) else ai_runtime_contracts.eval_unknown_suite_result(suite_name)
        results.append(dict(result))

    resources_after = dict(resource_snapshot())
    data = ai_runtime_contracts.eval_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        requested_suite=requested_suite,
        declared_class=declared_class,
        policy_gate=gate,
        results=results,
        resource_profile=resource_profile(resources_before, resources_after, "mixed_eval_command", "whole eval command"),
        openvino_cache_root=openvino_cache_root,
    )
    if write_latest:
        latest_error = write_json(latest_path, data, 0o664)
        daily_error = append_jsonl(daily_path(), data, 0o664)
        write_errors = [error for error in (latest_error, daily_error) if error]
        if write_errors:
            data["write_errors"] = write_errors
        if workload_update is not None:
            data["workload_update"] = dict(workload_update(data))
    return data


def _write_latest_if_requested(
    data: dict[str, Any],
    *,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> None:
    if not write_latest:
        return
    error = write_json(latest_path, data, 0o664)
    if error:
        data["write_error"] = error


def _write_latest_history_if_requested(
    data: dict[str, Any],
    *,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> None:
    if not write_latest:
        return
    latest_error = write_json(latest_path, data, 0o664)
    daily_error = append_jsonl(daily_path(), data, 0o664)
    errors = [error for error in (latest_error, daily_error) if error]
    if errors:
        data["write_errors"] = errors


def _write_latest_with_error_status(
    data: dict[str, Any],
    *,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> None:
    if not write_latest:
        return
    error = write_json(latest_path, data, 0o664)
    if error:
        data["ok"] = False
        data["write_errors"] = [error]


def _write_latest_history_with_error_status(
    data: dict[str, Any],
    *,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> None:
    if not write_latest:
        return
    latest_error = write_json(latest_path, data, 0o664)
    daily_error = append_jsonl(daily_path(), data, 0o664)
    errors = [error for error in (latest_error, daily_error) if error]
    if errors:
        data["ok"] = False
        data["write_errors"] = errors


def devices_status_readmodel(
    *,
    device_nodes: Mapping[str, Any],
    paths: Mapping[str, Any],
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    run_command: RunPort,
    command_exists: CommandExistsPort,
    which: WhichPort,
    user_systemd_unit: SystemdUnitPort,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
    path_exists: PathExistsPort | None = None,
    npu_driver_root: Path = Path("/opt/intel/linux-npu-driver"),
) -> dict[str, Any]:
    data = devices_status(
        device_nodes=device_nodes,
        paths=paths,
        config=config,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        run_command=run_command,
        command_exists=command_exists,
        which=which,
        user_systemd_unit=user_systemd_unit,
        path_exists=path_exists,
        npu_driver_root=npu_driver_root,
    )
    _write_latest_if_requested(data, write_latest=write_latest, latest_path=latest_path, write_json=write_json)
    return data


def models_inventory_readmodel(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = models_inventory(
        config=config,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
    )
    _write_latest_if_requested(data, write_latest=write_latest, latest_path=latest_path, write_json=write_json)
    return data


def resident_latest_readmodels(
    *,
    status_path: Path,
    digest_path: Path,
    micro_path: Path,
    jobs_path: Path,
    read_json: JsonReadPort,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key, path in (
        ("status", status_path),
        ("digest", digest_path),
        ("micro", micro_path),
        ("jobs", jobs_path),
    ):
        data, _error = read_json(path)
        result[key] = data if isinstance(data, dict) else {}
    return result


def token_accounting_aoa_registry_sessions(
    *,
    aoa_root: Path,
    read_json: JsonReadPort,
) -> tuple[list[dict[str, Any]], Path, str | None]:
    registry_path = aoa_root / "session-registry.json"
    data, error = read_json(registry_path)
    if error or not isinstance(data, Mapping):
        return [], registry_path, error or "registry_missing"
    sessions = data.get("sessions") if isinstance(data.get("sessions"), list) else []
    return [dict(item) for item in sessions if isinstance(item, Mapping)], registry_path, None


def token_accounting_aoa_generated_summary(
    *,
    record: Mapping[str, Any],
    aoa_root: Path,
    read_json: JsonReadPort,
    is_relative_to_path: RelativeToPort,
) -> tuple[dict[str, Any], str, list[str]]:
    diagnostics: list[str] = []
    registry_summary = ai_runtime_contracts.token_accounting_sanitize_summary(record.get("token_accounting"))
    registry_has_generated_counts = (
        registry_summary
        and (
            ai_runtime_contracts.token_accounting_summary_has_counts(registry_summary)
            or ai_runtime_contracts.token_accounting_int(registry_summary.get("schema_version"))
            == ai_runtime_contracts.TOKEN_ACCOUNTING_SCHEMA_VERSION
        )
    )
    if registry_has_generated_counts and ai_runtime_contracts.token_accounting_int(registry_summary.get("generator_version")) is not None:
        return registry_summary, "session_registry", diagnostics

    session_path_text = str(record.get("path") or "")
    session_path = Path(session_path_text) if session_path_text else Path()
    if not session_path_text:
        return {}, "missing", ["session_path_missing"]
    if not is_relative_to_path(session_path, aoa_root / "sessions"):
        return {}, "missing", ["session_path_outside_aoa_sessions"]

    for filename, source in (("session.manifest.json", "session_manifest"), ("session.index.json", "session_index")):
        payload, error = read_json(session_path / filename)
        if error:
            diagnostics.append(f"{source}_{error}")
            continue
        summary = ai_runtime_contracts.token_accounting_sanitize_summary(
            payload.get("token_accounting") if isinstance(payload, Mapping) else None
        )
        if summary:
            return summary, source, diagnostics
        diagnostics.append(f"{source}_missing_token_accounting")
    if registry_has_generated_counts:
        diagnostics.append("session_registry_token_accounting_generator_unknown")
        return registry_summary, "session_registry", diagnostics
    return {}, "missing", diagnostics or ["generated_token_accounting_missing"]


def token_accounting_aoa_summary_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    aoa_root: Path,
    target: str,
    since: str | None,
    since_days: int | None,
    until: str | None,
    limit: int | None,
    write_latest: bool,
    latest_path: Path,
    history_root: Path,
    read_json: JsonReadPort,
    sha256_path: Sha256PathPort,
    write_latest_history: LatestHistoryWritePort,
    is_relative_to_path: RelativeToPort,
) -> dict[str, Any]:
    generated_at = now_iso()
    sessions, registry_path, registry_error = token_accounting_aoa_registry_sessions(
        aoa_root=aoa_root,
        read_json=read_json,
    )
    diagnostics: list[str] = []
    if registry_error:
        diagnostics.append(f"session_registry_{registry_error}")
    selected, selection_diagnostics, effective_since = ai_runtime_contracts.token_accounting_aoa_select_records(
        sessions,
        target=target,
        since=since,
        since_days=since_days,
        until=until,
        limit=limit,
    )
    diagnostics.extend(selection_diagnostics)
    entries: list[dict[str, Any]] = []
    generated_summaries: list[dict[str, Any]] = []
    missing_generated = 0
    provider_sessions = 0
    estimated_only_sessions = 0
    source_counts: collections.Counter[str] = collections.Counter()
    for record in selected:
        summary, summary_source, record_diagnostics = token_accounting_aoa_generated_summary(
            record=record,
            aoa_root=aoa_root,
            read_json=read_json,
            is_relative_to_path=is_relative_to_path,
        )
        source_counts[summary_source] += 1
        if summary:
            generated_summaries.append(summary)
        else:
            missing_generated += 1
            record_diagnostics.append("generated_token_accounting_missing")
        provider_events = ai_runtime_contracts.token_accounting_int(summary.get("provider_reported_event_count")) if summary else 0
        estimated_events = ai_runtime_contracts.token_accounting_int(summary.get("estimated_event_count")) if summary else 0
        if provider_events and provider_events > 0:
            provider_sessions += 1
        elif estimated_events and estimated_events > 0:
            estimated_only_sessions += 1
        diagnostics.extend(record_diagnostics)
        entries.append(
            {
                "session_id": str(record.get("session_id") or ""),
                "date": ai_runtime_contracts.token_accounting_aoa_record_date(record) or None,
                "sequence": ai_runtime_contracts.token_accounting_aoa_record_sequence(record),
                "updated_at": record.get("updated_at"),
                "archive_status": record.get("archive_status"),
                "event_count": ai_runtime_contracts.token_accounting_int(record.get("event_count")),
                "segment_count": ai_runtime_contracts.token_accounting_int(record.get("segment_count")),
                "summary_source": summary_source,
                "token_accounting": summary,
                "context_pressure": ai_runtime_contracts.token_accounting_context_pressure(summary)
                if summary
                else {"available": False, "basis": None},
                "diagnostics": sorted(set(str(item) for item in record_diagnostics if item)),
            }
        )
    aggregate = ai_runtime_contracts.token_accounting_merge_summaries(
        generated_summaries,
        {"kind": "aoa_session_memory_session_set", "target": target, "session_count": len(entries)},
    )
    summary_payload = {
        "selected_sessions": len(entries),
        "available_sessions": len(sessions),
        "generated_token_accounting_sessions": len(generated_summaries),
        "missing_generated_token_accounting": missing_generated,
        "provider_reported_sessions": provider_sessions,
        "estimated_only_sessions": estimated_only_sessions,
        "source_counts": dict(sorted(source_counts.items())),
        "diagnostics": len(set(diagnostics)),
    }
    data = ai_runtime_contracts.token_accounting_aoa_summary_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        ok=registry_error is None,
        aoa_root=aoa_root,
        target=target,
        since=effective_since,
        until=until,
        limit=limit,
        summary=summary_payload,
        aggregate=aggregate,
        sessions=entries,
        diagnostics=diagnostics,
        session_registry_path=registry_path,
        session_registry_sha256=sha256_path(registry_path) if registry_path.exists() else None,
    )
    if write_latest:
        errors = write_latest_history(data, latest_path, history_root)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
    return data


def capabilities_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    devices: Mapping[str, Any],
    models: Mapping[str, Any],
    dictation: Mapping[str, Any],
    tts_profiles: Mapping[str, Any],
    latest_tts_eval: Mapping[str, Any],
    latest_tts_success: Mapping[str, Any],
    llm_registry: Mapping[str, Any],
    llm_resident_status: Mapping[str, Any],
    llm_resident_digest: Mapping[str, Any],
    llm_resident_micro: Mapping[str, Any],
    llm_resident_jobs: Mapping[str, Any],
    refs: Mapping[str, Any],
    resident_refs: Mapping[str, Any],
    resident_job_names: list[str],
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.ai_capabilities_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        devices=dict(devices),
        models=dict(models),
        dictation=dict(dictation),
        tts_profiles=dict(tts_profiles),
        latest_tts_eval=dict(latest_tts_eval),
        latest_tts_success=dict(latest_tts_success),
        llm_registry=dict(llm_registry),
        llm_resident_status=dict(llm_resident_status),
        llm_resident_digest=dict(llm_resident_digest),
        llm_resident_micro=dict(llm_resident_micro),
        llm_resident_jobs=dict(llm_resident_jobs),
        refs=dict(refs),
        resident_refs=dict(resident_refs),
        resident_job_names=list(resident_job_names),
    )
    _write_latest_if_requested(data, write_latest=write_latest, latest_path=latest_path, write_json=write_json)
    return data


def policy_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    config: Mapping[str, Any],
    telemetry_age_sec: Any,
    battery: Mapping[str, Any],
    mode: Mapping[str, Any],
    thermal: Mapping[str, Any],
    cpu_thermal_map: Mapping[str, Any],
    observability_latest_path: str,
    cpu_thermal_map_latest_path: str,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.ai_policy_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        config=dict(config),
        telemetry_age_sec=telemetry_age_sec,
        battery=dict(battery),
        mode=dict(mode),
        thermal=dict(thermal),
        cpu_thermal_map=dict(cpu_thermal_map),
        observability_latest_path=observability_latest_path,
        cpu_thermal_map_latest_path=cpu_thermal_map_latest_path,
    )
    _write_latest_if_requested(data, write_latest=write_latest, latest_path=latest_path, write_json=write_json)
    return data


def runtime_snapshot_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    kernel: str,
    os_release: Mapping[str, Any],
    devices: Mapping[str, Any],
    python_runtime: Mapping[str, Any],
    kernel_modules: Mapping[str, Any],
    previous_latest: Mapping[str, Any] | None,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> dict[str, Any]:
    device_data = dict(devices)
    openvino = device_data.get("openvino") if isinstance(device_data.get("openvino"), dict) else {}
    current = {
        "kernel": kernel,
        "os_release": dict(os_release),
        "openvino_version": openvino.get("openvino_version"),
        "available_devices": openvino.get("available_devices"),
        "python_packages": dict(python_runtime).get("packages", {}),
        "npu_user_driver": device_data.get("npu_user_driver", {}),
        "packages": device_data.get("packages", {}),
    }
    data = ai_runtime_contracts.ai_runtime_snapshot_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        current=current,
        devices=device_data,
        python_runtime=dict(python_runtime),
        kernel_modules=dict(kernel_modules),
        previous_latest=dict(previous_latest) if isinstance(previous_latest, Mapping) else None,
    )
    _write_latest_history_if_requested(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        daily_path=daily_path,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    return data


def status_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    paths: Mapping[str, Any],
    config_path: Path,
    config_exists: bool,
    config_load_error: Any,
    devices: Mapping[str, Any],
    models: Mapping[str, Any],
    llm_registry: Mapping[str, Any],
    latest_benchmark: Mapping[str, Any],
    latest_eval: Mapping[str, Any],
    latest_tts_eval: Mapping[str, Any],
    latest_tts_success: Mapping[str, Any],
    tts_profiles: Mapping[str, Any],
    tts_server: Mapping[str, Any],
    dictation: Mapping[str, Any],
    cpu_route_latest: Mapping[str, Any],
    cpu_thermal_latest: Mapping[str, Any],
    cooling_latest: Mapping[str, Any],
    refs: Mapping[str, Any],
    include_report: bool,
    report_latest_path: Path,
    report_exists: bool,
) -> dict[str, Any]:
    return ai_runtime_contracts.ai_status_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        paths=dict(paths),
        config_path=str(config_path),
        config_exists=config_exists,
        config_load_error=config_load_error,
        devices=dict(devices),
        models=dict(models),
        llm_registry=dict(llm_registry),
        latest_benchmark=dict(latest_benchmark),
        latest_eval=dict(latest_eval),
        latest_tts_eval=dict(latest_tts_eval),
        latest_tts_success=dict(latest_tts_success),
        tts_profiles=dict(tts_profiles),
        tts_server=dict(tts_server),
        dictation=dict(dictation),
        cpu_route_latest=dict(cpu_route_latest),
        cpu_thermal_latest=dict(cpu_thermal_latest),
        cooling_latest=dict(cooling_latest),
        refs=dict(refs),
        include_report=include_report,
        report_latest_path=str(report_latest_path),
        report_exists=report_exists,
    )


def report_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    paths: Mapping[str, Any],
    status_data: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    policy: Mapping[str, Any],
    runtime: Mapping[str, Any],
    storage: Mapping[str, Any],
    llm_registry: Mapping[str, Any],
    llm_validate: Mapping[str, Any],
    token_accounting_profiles: Mapping[str, Any],
    aoa_token_summary: Mapping[str, Any],
    latest_eval: Mapping[str, Any],
    latest_benchmark: Mapping[str, Any],
    latest_tts_eval: Mapping[str, Any],
    latest_tts_success: Mapping[str, Any],
    tts_profiles: Mapping[str, Any],
    tts_server: Mapping[str, Any],
    workload: Mapping[str, Any],
    cpu_route_latest: Mapping[str, Any],
    cpu_thermal_latest: Mapping[str, Any],
    cooling_latest: Mapping[str, Any],
    observability: Mapping[str, Any],
    dictation: Mapping[str, Any],
    refs: Mapping[str, Any],
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.ai_report_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        paths=dict(paths),
        status_data=dict(status_data),
        capabilities=dict(capabilities),
        policy=dict(policy),
        runtime=dict(runtime),
        storage=dict(storage),
        llm_registry=dict(llm_registry),
        llm_validate=dict(llm_validate),
        token_accounting_profiles=dict(token_accounting_profiles),
        aoa_token_summary=dict(aoa_token_summary),
        latest_eval=dict(latest_eval),
        latest_benchmark=dict(latest_benchmark),
        latest_tts_eval=dict(latest_tts_eval),
        latest_tts_success=dict(latest_tts_success),
        tts_profiles=dict(tts_profiles),
        tts_server=dict(tts_server),
        workload=dict(workload),
        cpu_route_latest=dict(cpu_route_latest),
        cpu_thermal_latest=dict(cpu_thermal_latest),
        cooling_latest=dict(cooling_latest),
        observability=dict(observability),
        dictation=dict(dictation),
        refs=dict(refs),
    )
    _write_latest_history_if_requested(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        daily_path=daily_path,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    return data


def workload_measurement_files(runs_root: Path) -> list[Path]:
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.rglob("*.jsonl") if path.is_file())


def workload_read_measurements(runs_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in workload_measurement_files(runs_root):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        records.append(item)
        except OSError:
            continue
    return records


def workload_append_measurements(
    records: list[dict[str, Any]],
    *,
    runs_root: Path,
    runs_daily_path: DailyPathPort,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    append_jsonl: JsonlAppendPort,
    stats_latest_path: Path,
    stats_update: NoArgMappingPort | None = None,
    write_stats: bool = True,
) -> dict[str, Any]:
    existing_ids = {str(item.get("record_id")) for item in workload_read_measurements(runs_root) if item.get("record_id")}
    appended = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    for record in records:
        record_id = str(record.get("record_id") or "")
        if not record_id:
            skipped += 1
            continue
        if record_id in existing_ids:
            skipped += 1
            continue
        error = append_jsonl(runs_daily_path(), record, 0o664)
        if error:
            errors.append(error)
            continue
        existing_ids.add(record_id)
        appended += 1
    result: dict[str, Any] = {
        "schema": f"{schema_prefix}_ai_workload_update_v1",
        "version": version,
        "generated_at": now_iso(),
        "ok": not errors,
        "records_seen": len(records),
        "records_appended": appended,
        "records_skipped_existing_or_invalid": skipped,
        "errors": errors,
    }
    if write_stats and stats_update is not None:
        result["stats"] = {
            "latest": str(stats_latest_path),
            "updated": dict(stats_update()).get("ok"),
        }
    return result


def workload_refresh_from_latest(
    *,
    latest_benchmark: Mapping[str, Any],
    latest_eval: Mapping[str, Any],
    latest_tts_eval: Mapping[str, Any],
    latest_resident_audit: Mapping[str, Any],
    schema_prefix: str,
    benchmark_measurements: WorkloadExtractPort,
    eval_measurements: WorkloadExtractPort,
    tts_eval_measurements: WorkloadExtractPort,
    resident_audit_measurements: WorkloadExtractPort,
    append_measurements: WorkloadAppendPort,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    benchmark_doc = dict(latest_benchmark)
    eval_doc = dict(latest_eval)
    tts_doc = dict(latest_tts_eval)
    resident_doc = dict(latest_resident_audit)
    if benchmark_doc.get("ok"):
        records.extend(benchmark_measurements(benchmark_doc))
    if eval_doc.get("ok"):
        records.extend(eval_measurements(eval_doc))
    if tts_doc.get("schema") == f"{schema_prefix}_ai_tts_eval_v1":
        records.extend(tts_eval_measurements(tts_doc))
    if resident_doc.get("schema") == f"{schema_prefix}_gemma4_spark_resident_audit_v1":
        records.extend(resident_audit_measurements(resident_doc))
    update = dict(append_measurements(records, True))
    update["sources"] = {
        "benchmark_generated_at": benchmark_doc.get("generated_at"),
        "eval_generated_at": eval_doc.get("generated_at"),
        "tts_eval_generated_at": tts_doc.get("generated_at"),
        "resident_audit_generated_at": resident_doc.get("generated_at"),
    }
    return update


def workload_taxonomy(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    class_levels: Mapping[str, int],
    write_latest: bool,
    taxonomy_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.workload_taxonomy_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        class_levels=dict(class_levels),
    )
    if write_latest:
        error = write_json(taxonomy_path, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def workload_stats(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    runs_root: Path,
    runs_daily_glob: str,
    latest_path: Path,
    write_latest: bool,
    write_json: JsonWritePort,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_records = records if records is not None else workload_read_measurements(runs_root)
    data = ai_runtime_contracts.workload_stats_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        records=source_records,
        config=dict(config),
        runs_daily_glob=runs_daily_glob,
        latest_path=str(latest_path),
    )
    if write_latest:
        error = write_json(latest_path, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def workload_refresh(
    *,
    config: Mapping[str, Any],
    policy: Mapping[str, Any],
    run_probe: bool | None,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    benchmark_runner: NoArgMappingPort,
    refresh_from_latest: NoArgMappingPort,
    stats: NoArgMappingPort,
    stats_latest_path: Path,
    write_latest: bool,
    refresh_daily_path: DailyPathPort,
    append_jsonl: JsonlAppendPort,
) -> dict[str, Any]:
    probe_plan = ai_runtime_contracts.workload_refresh_probe_plan(
        config=dict(config),
        policy=dict(policy),
        run_probe=run_probe,
    )
    benchmark_result: dict[str, Any] | None = None
    if probe_plan.get("quick_benchmark_requested") and not probe_plan.get("quick_benchmark_skip_reasons"):
        benchmark_result = dict(benchmark_runner())

    refresh = dict(refresh_from_latest())
    stats_doc = dict(stats())
    data = ai_runtime_contracts.workload_refresh_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        policy=dict(policy),
        probe_plan=probe_plan,
        benchmark_result=benchmark_result,
        refresh=refresh,
        stats=stats_doc,
        stats_latest_path=str(stats_latest_path),
    )
    if write_latest:
        error = append_jsonl(refresh_daily_path(), data, 0o664)
        if error:
            data["write_error"] = error
    return data


def workload_status(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    taxonomy: NoArgMappingPort,
    refresh_from_latest: NoArgMappingPort,
    stats: NoArgMappingPort,
    policy: NoArgMappingPort,
    refresh_from_latest_enabled: bool,
    paths: Mapping[str, Any],
    auto_refresh: Mapping[str, Any],
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.workload_status_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        taxonomy=dict(taxonomy()),
        refresh=dict(refresh_from_latest()) if refresh_from_latest_enabled else None,
        stats=dict(stats()),
        policy=dict(policy()),
        paths=dict(paths),
        auto_refresh=dict(auto_refresh),
    )
    if write_latest:
        error = write_json(latest_path, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def rpm_package_status(
    names: list[str],
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    result: dict[str, Any] = {"rpm_available": command_exists("rpm"), "packages": {}}
    if not result["rpm_available"]:
        return result
    for name in names:
        out = dict(run_command(["rpm", "-q", name], timeout=3.0))
        result["packages"][name] = {
            "installed": bool(out.get("ok")),
            "query": out.get("stdout") or out.get("stderr"),
        }
    return result


def ldconfig_libraries(
    patterns: list[str],
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    result: dict[str, Any] = {"ldconfig_available": command_exists("ldconfig"), "matches": []}
    if not result["ldconfig_available"]:
        return result
    out = dict(run_command(["ldconfig", "-p"], timeout=3.0))
    result["ok"] = bool(out.get("ok"))
    if not out.get("ok"):
        result["error"] = out.get("stderr")
        return result
    lowered_patterns = [item.lower() for item in patterns]
    for line in str(out.get("stdout") or "").splitlines():
        lowered = line.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            result["matches"].append(line.strip())
    return result


def npu_user_driver_status(
    *,
    root: Path = Path("/opt/intel/linux-npu-driver"),
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    exists = _path_exists(root, path_exists)
    versions: list[str] = []
    error = None
    if exists:
        try:
            versions = sorted(item.name for item in root.iterdir())
        except OSError as exc:
            error = str(exc)
    data = {
        "root": str(root),
        "exists": exists,
        "versions": versions,
        "preferred_version": versions[-1] if versions else None,
    }
    if error:
        data["error"] = error
    return data


def devices_status(
    *,
    device_nodes: Mapping[str, Any],
    paths: Mapping[str, Any],
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_command: RunPort,
    command_exists: CommandExistsPort,
    which: WhichPort,
    user_systemd_unit: SystemdUnitPort,
    path_exists: PathExistsPort | None = None,
    npu_driver_root: Path = Path("/opt/intel/linux-npu-driver"),
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    runtime = openvino_runtime_info(
        config=config,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        run_command=run_command,
        which=which,
        path_exists=path_exists,
    )
    available = runtime.get("available_devices") if isinstance(runtime.get("available_devices"), list) else []
    packages = rpm_package_status(
        [
            "intel-openvino-runtime",
            "intel-level-zero-gpu",
            "intel-npu-driver",
            "level-zero",
            "level-zero-devel",
        ],
        command_exists=command_exists,
        run_command=run_command,
    )
    return {
        "schema": f"{schema_prefix}_ai_devices_v1",
        "version": version,
        "generated_at": generated_at,
        "paths": dict(paths),
        "device_nodes": dict(device_nodes),
        "openvino": runtime,
        "packages": packages,
        "ldconfig": ldconfig_libraries(["npu", "level_zero", "ze_intel_gpu"], command_exists=command_exists, run_command=run_command),
        "npu_user_driver": npu_user_driver_status(root=npu_driver_root, path_exists=path_exists),
        "dictation_server": dict(user_systemd_unit("abyss-dictation-server.service")),
        "ready": {
            "openvino": bool(runtime.get("ok")),
            "cpu": "CPU" in available,
            "gpu": "GPU" in available and bool(device_nodes.get("dev_dri_present")),
            "npu": "NPU" in available and bool(device_nodes.get("dev_accel_present")),
        },
    }


def immediate_file_summary(path: Path, max_files: int = 1000) -> dict[str, Any]:
    files = 0
    size = 0
    extensions: dict[str, int] = {}
    truncated = False
    try:
        for item in path.iterdir():
            if not item.is_file():
                continue
            files += 1
            suffix = item.suffix.lower() or "[none]"
            extensions[suffix] = extensions.get(suffix, 0) + 1
            item_size = _path_size(item)
            if item_size is not None:
                size += item_size
            if files >= max_files:
                truncated = True
                break
    except OSError as exc:
        return {"error": str(exc)}
    return {
        "immediate_files": files,
        "immediate_file_bytes": size,
        "extensions": dict(sorted(extensions.items())),
        "truncated": truncated,
    }


def classify_model_dir(path: Path, root: Path, filenames: list[str]) -> dict[str, Any] | None:
    return ai_runtime_contracts.classify_model_dir(path, root, filenames, immediate_file_summary(path))


def models_inventory(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    path_exists: PathExistsPort | None = None,
    walk: WalkPort = default_walk,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    inventory = config.get("inventory", {}) if isinstance(config.get("inventory"), Mapping) else {}
    max_depth = int(inventory.get("max_depth", 9))
    max_entries = int(inventory.get("max_entries", 300))
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"}
    entries: list[dict[str, Any]] = []
    root_status: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    truncated = False

    for root in model_roots(config):
        status = {"path": str(root), "exists": _path_exists(root, path_exists), "entries_seen": 0}
        root_status.append(status)
        if not status["exists"]:
            continue
        try:
            for current, dirnames, filenames in walk(root):
                current_path = Path(current)
                try:
                    relative = current_path.relative_to(root)
                    depth = 0 if str(relative) == "." else len(relative.parts)
                except ValueError:
                    depth = 0
                if depth >= max_depth:
                    dirnames[:] = []
                else:
                    dirnames[:] = [name for name in dirnames if name not in skip_dirs]

                item = classify_model_dir(current_path, root, filenames)
                if item:
                    entries.append(item)
                    status["entries_seen"] = int(status["entries_seen"]) + 1

                for filename in sorted(filenames):
                    file_path = current_path / filename
                    file_entry = ai_runtime_contracts.model_file_entry(file_path, root, size_bytes=_path_size(file_path))
                    if not file_entry:
                        continue
                    entries.append(file_entry)
                    status["entries_seen"] = int(status["entries_seen"]) + 1

                if len(entries) >= max_entries:
                    truncated = True
                    break
        except OSError as exc:
            errors.append({"path": str(root), "error": str(exc)})
        if truncated:
            break

    return ai_runtime_contracts.build_models_inventory_document(
        entries=entries,
        roots=root_status,
        errors=errors,
        truncated=truncated,
        max_entries=max_entries,
        max_depth=max_depth,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def llm_runtime_status(
    config: Mapping[str, Any],
    *,
    runtime_override: Mapping[str, Any] | None = None,
    run_command: RunPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    runtime = dict(runtime_override) if isinstance(runtime_override, Mapping) else config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
    cli = Path(str(runtime.get("llama_cli") or ""))
    server = Path(str(runtime.get("llama_server") or ""))
    cli_exists = _path_exists(cli, path_exists)
    version_probe = None
    if cli_exists:
        version_probe = dict(run_command([str(cli), "--version"], timeout=5.0))
    return ai_runtime_contracts.llm_runtime_status(
        runtime,
        cli_exists=cli_exists,
        server_exists=_path_exists(server, path_exists),
        version_probe=version_probe,
    )


def llm_profile_status(
    *,
    family_name: str,
    profile_name: str,
    profile: Mapping[str, Any],
    runtime: Mapping[str, Any],
    cache_root: Path,
    storage_protection: StorageProtectionPort,
    is_relative_to_path: RelativeToPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    local_path = Path(str(profile.get("local_path") or ""))
    mmproj_raw = str(profile.get("mmproj_path") or "")
    mmproj_path = Path(mmproj_raw) if mmproj_raw else None
    exists = _path_exists(local_path, path_exists)
    mmproj_exists = bool(mmproj_path and _path_exists(mmproj_path, path_exists))
    protection = (
        dict(storage_protection(local_path))
        if str(local_path).startswith("/")
        else {"decision": "deny", "reason": "profile local path is not absolute"}
    )
    return ai_runtime_contracts.llm_profile_status(
        family_name=family_name,
        profile_name=profile_name,
        profile=dict(profile),
        runtime=dict(runtime),
        local_path=local_path,
        local_exists=exists,
        local_size_bytes=_path_size(local_path) if exists else None,
        mmproj_path=mmproj_path,
        mmproj_exists=mmproj_exists,
        mmproj_size_bytes=_path_size(mmproj_path) if mmproj_path and mmproj_exists else None,
        storage_protection=protection,
        under_host_cache=is_relative_to_path(local_path, cache_root),
    )


def llm_registry_readmodel(
    *,
    config: Mapping[str, Any],
    runtime_status: LLMRuntimeStatusPort,
    profile_status: LLMProfileStatusPort,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    registry_latest_path: Path,
    registry_daily_path: Path,
    validate_latest_path: Path,
    write_latest: bool,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> dict[str, Any]:
    config_doc = dict(config)
    runtime = dict(runtime_status(config_doc, None))
    family_runtimes: dict[str, dict[str, Any]] = {}
    profile_statuses: dict[str, dict[str, Any]] = {}
    families = config_doc.get("families") if isinstance(config_doc.get("families"), Mapping) else {}
    for family_name, family in families.items():
        if not isinstance(family, Mapping):
            continue
        family_key = str(family_name)
        family_runtime = (
            dict(runtime_status(config_doc, dict(family.get("runtime"))))
            if isinstance(family.get("runtime"), Mapping)
            else runtime
        )
        family_runtimes[family_key] = family_runtime
        profiles = family.get("profiles") if isinstance(family.get("profiles"), Mapping) else {}
        for profile_name, profile in profiles.items():
            if not isinstance(profile, Mapping):
                continue
            profile_key = str(profile_name)
            profile_runtime = (
                dict(runtime_status(config_doc, dict(profile.get("runtime"))))
                if isinstance(profile.get("runtime"), Mapping)
                else family_runtime
            )
            profile_statuses[f"{family_key}.{profile_key}"] = dict(
                profile_status(family_key, profile_key, dict(profile), profile_runtime)
            )
    data = ai_runtime_contracts.llm_registry_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        config=config_doc,
        runtime=runtime,
        family_runtimes=family_runtimes,
        profile_statuses=profile_statuses,
        registry_latest_path=registry_latest_path,
        registry_daily_path=registry_daily_path,
        validate_latest_path=validate_latest_path,
    )
    _write_latest_history_with_error_status(
        data,
        write_latest=write_latest,
        latest_path=registry_latest_path,
        daily_path=lambda: registry_daily_path,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    return data


def llm_latest_readmodel(
    *,
    latest_path: Path,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    read_json: JsonReadPort,
) -> dict[str, Any]:
    data, error = read_json(latest_path)
    if not isinstance(data, Mapping):
        return {
            "schema": f"{schema_prefix}_ai_llm_registry_latest_read_v1",
            "version": version,
            "generated_at": now_iso(),
            "ok": False,
            "path": str(latest_path),
            "error": error or "missing",
        }
    result = dict(data)
    result["read_at"] = now_iso()
    return result


def llm_validate_readmodel(
    *,
    base_checks: Iterable[Mapping[str, Any]],
    registry: Mapping[str, Any],
    token_profiles: Mapping[str, Any],
    config: Mapping[str, Any],
    protected_roots: Iterable[str],
    paths: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    write_latest: bool,
    latest_path: Path,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    checks = [dict(item) for item in base_checks]
    registry_doc = dict(registry)
    config_doc = dict(config)
    checks.extend(
        ai_runtime_contracts.llm_validate_contract_checks(
            registry=registry_doc,
            token_profiles=dict(token_profiles),
            config=config_doc,
            protected_roots=tuple(protected_roots),
        )
    )
    data = ai_runtime_contracts.llm_validate_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        checks=checks,
        registry=registry_doc,
        paths=dict(paths),
    )
    _write_latest_with_error_status(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        write_json=write_json,
    )
    return data


def llm_resident_controller_timeout(command: str | None, jobs_action: str | None = None) -> float:
    if command == "jobs" and jobs_action in {"run", "refresh"}:
        return 900.0
    if command in {"job", "micro"}:
        return 360.0
    if command in {"digest", "smoke", "audit", "start", "stop"}:
        return 180.0
    return 60.0


def llm_resident_controller_command(
    controller: Path,
    command: str | None,
    *,
    job_name: str | None = None,
    jobs_action: str | None = None,
    request_class: str = "job",
    force: bool = False,
    no_generation: bool = False,
    limit: int | None = None,
    json_output: bool = False,
) -> list[str]:
    command_text = str(command or "")
    argv = [str(controller), command_text]
    if command_text == "job":
        argv.append(str(job_name or ""))
    elif command_text == "jobs":
        argv.append(str(jobs_action or "latest"))
    elif command_text == "policy":
        if job_name:
            argv.append(str(job_name))
        argv += ["--request-class", str(request_class)]
    if force:
        argv.append("--force")
    if no_generation:
        argv.append("--no-generation")
    if limit is not None and command_text in {"digest", "job", "micro", "jobs", "candidates"}:
        argv += ["--limit", str(limit)]
    if json_output:
        argv.append("--json")
    return argv


def llm_resident_controller_run(
    *,
    controller: Path,
    command: str | None,
    run_command: RunPort,
    job_name: str | None = None,
    jobs_action: str | None = None,
    request_class: str = "job",
    force: bool = False,
    no_generation: bool = False,
    limit: int | None = None,
    json_output: bool = False,
) -> dict[str, Any]:
    argv = llm_resident_controller_command(
        controller,
        command,
        job_name=job_name,
        jobs_action=jobs_action,
        request_class=request_class,
        force=force,
        no_generation=no_generation,
        limit=limit,
        json_output=json_output,
    )
    timeout = llm_resident_controller_timeout(command, jobs_action)
    out = dict(run_command(argv, timeout=timeout))
    stdout = str(out.get("stdout") or "")
    stderr = str(out.get("stderr") or "")
    result = {
        "command": argv,
        "timeout": timeout,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": int(out.get("returncode") or 0),
    }
    if json_output and not stdout.strip():
        result["json_error"] = {
            "ok": False,
            "error": stderr or "resident command produced no output",
            "command": argv,
        }
    return result


def llm_workhorse_controller_timeout(
    command: str | None,
    *,
    run_model: bool = False,
    timeout: float | None = None,
) -> float:
    if command == "review" and run_model:
        return float(timeout if timeout is not None else 420.0) + 30.0
    return 120.0


def llm_workhorse_controller_command(
    controller: Path,
    command: str | None,
    *,
    limit: int | None = None,
    refresh_candidates: bool = False,
    run_model: bool = False,
    n_predict: int | None = None,
    timeout: float | None = None,
    json_output: bool = False,
) -> list[str]:
    command_text = str(command or "")
    argv = [str(controller), command_text]
    if limit is not None and command_text in {"pack", "review"}:
        argv += ["--limit", str(limit)]
    if refresh_candidates and command_text in {"pack", "review"}:
        argv.append("--refresh-candidates")
    if run_model and command_text == "review":
        argv.append("--run-model")
    if n_predict is not None and command_text == "review":
        argv += ["--n-predict", str(n_predict)]
    if timeout is not None and command_text == "review":
        argv += ["--timeout", str(timeout)]
    if json_output:
        argv.append("--json")
    return argv


def llm_workhorse_controller_run(
    *,
    controller: Path,
    command: str | None,
    run_command: RunPort,
    limit: int | None = None,
    refresh_candidates: bool = False,
    run_model: bool = False,
    n_predict: int | None = None,
    timeout: float | None = None,
    json_output: bool = False,
) -> dict[str, Any]:
    argv = llm_workhorse_controller_command(
        controller,
        command,
        limit=limit,
        refresh_candidates=refresh_candidates,
        run_model=run_model,
        n_predict=n_predict,
        timeout=timeout,
        json_output=json_output,
    )
    run_timeout = llm_workhorse_controller_timeout(
        command,
        run_model=run_model,
        timeout=timeout,
    )
    out = dict(run_command(argv, timeout=run_timeout))
    stdout = str(out.get("stdout") or "")
    stderr = str(out.get("stderr") or "")
    result = {
        "command": argv,
        "timeout": run_timeout,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": int(out.get("returncode") or 0),
    }
    if json_output and not stdout.strip():
        result["json_error"] = {
            "ok": False,
            "error": stderr or "workhorse command produced no output",
            "command": argv,
        }
    return result


def stt_eval_run(
    *,
    reference_text: str,
    fixture: Mapping[str, Any],
    profiles: Iterable[str],
    similarity_warn_below: float,
    transcribe_audio: SttTranscribePort,
    monotonic: MonotonicPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
) -> dict[str, Any]:
    fixture_doc = dict(fixture)
    if not fixture_doc.get("ok"):
        return ai_runtime_contracts.stt_eval_result(
            reference_text=reference_text,
            fixture=fixture_doc,
            profiles=[],
        )

    fixture_path = str(fixture_doc.get("path") or "")
    profile_results: list[dict[str, Any]] = []
    for profile in [str(item) for item in profiles]:
        resources_before = dict(resource_snapshot())
        started = float(monotonic())
        transcript = dict(transcribe_audio(fixture_path, profile))
        elapsed = round(float(monotonic()) - started, 3)
        resources_after = dict(resource_snapshot())
        profile_results.append(
            ai_runtime_contracts.stt_eval_profile_result(
                profile=profile,
                reference_text=reference_text,
                transcript=transcript,
                elapsed_sec=elapsed,
                similarity_warn_below=similarity_warn_below,
                resource_profile=dict(
                    resource_profile(
                        resources_before,
                        resources_after,
                        "client_wall_and_system_context",
                        "dictation client call around warm server; server CPU/RAM is not directly attributed",
                    )
                ),
            )
        )
    return ai_runtime_contracts.stt_eval_result(
        reference_text=reference_text,
        fixture=fixture_doc,
        profiles=profile_results,
    )


def token_accounting_library_paths(
    tokenizer: Path,
    profile: Mapping[str, Any],
    *,
    path_exists: PathExistsPort | None = None,
) -> list[Path]:
    path_exists = path_exists or Path.exists
    paths: list[Path] = []
    seen: set[str] = set()
    for child in ai_runtime_contracts.token_accounting_library_candidates(tokenizer, dict(profile)):
        if _path_exists(child, path_exists):
            key = str(child)
            if key not in seen:
                seen.add(key)
                paths.append(child)
    return paths


def token_accounting_resolve_tokenizer(
    profile: Mapping[str, Any],
    *,
    path_exists: PathExistsPort | None = None,
    access: PathAccessPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    access = access or os.access
    candidates = ai_runtime_contracts.token_accounting_tokenizer_candidates(dict(profile))
    found = next((candidate for candidate in candidates if _path_exists(candidate, path_exists) and access(candidate, os.X_OK)), None)
    library_paths = token_accounting_library_paths(found, profile, path_exists=path_exists) if found else []
    return ai_runtime_contracts.token_accounting_tokenizer_resolution(
        tokenizer=found,
        candidate_paths=candidates,
        library_paths=library_paths,
    )


def token_accounting_count_subprocess(
    *,
    profile: Mapping[str, Any],
    text: str,
    timeout: float,
    environ: Mapping[str, str],
    run_subprocess: SubprocessRunPort | None = None,
    monotonic: MonotonicPort | None = None,
) -> dict[str, Any]:
    run_subprocess = run_subprocess or subprocess.run
    monotonic = monotonic or time.monotonic
    text_value = str(text)
    input_bytes = text_value.encode("utf-8", errors="replace")
    env = dict(environ)
    env.update(ai_runtime_contracts.token_accounting_count_env_overlay(dict(profile), env.get("LD_LIBRARY_PATH")))

    started = monotonic()
    try:
        proc = run_subprocess(
            ai_runtime_contracts.token_accounting_count_command(dict(profile)),
            input=text_value,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=env,
        )
        outcome = ai_runtime_contracts.token_accounting_count_execution_result(
            stdout=str(getattr(proc, "stdout", "") or ""),
            stderr=str(getattr(proc, "stderr", "") or ""),
            returncode=int(getattr(proc, "returncode", 1)),
        )
    except subprocess.TimeoutExpired:
        outcome = {
            "ok": False,
            "total_tokens": None,
            "error": "tokenizer_timeout",
            "returncode": None,
            "stderr": None,
        }

    return {
        "elapsed_sec": round(monotonic() - started, 6),
        "input_bytes": input_bytes,
        "outcome": outcome,
    }


def token_accounting_contract_readmodel(
    *,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    root: Path,
    latest_path: Path,
    profiles_latest_path: Path,
    counts_latest_path: Path,
    write_latest: bool,
    write_json: JsonWritePort,
) -> dict[str, Any]:
    data = ai_runtime_contracts.token_accounting_contract_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        root=root,
        latest_path=latest_path,
        profiles_latest_path=profiles_latest_path,
        counts_latest_path=counts_latest_path,
    )
    _write_latest_with_error_status(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        write_json=write_json,
    )
    return data


def token_accounting_profiles_readmodel(
    *,
    registry: Mapping[str, Any],
    resolve_tokenizer: TokenResolverPort,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    root: Path,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
) -> dict[str, Any]:
    profiles = registry.get("profiles") if isinstance(registry.get("profiles"), Mapping) else {}
    profile_rows: dict[str, Any] = {}
    for name, profile in profiles.items():
        if not isinstance(profile, Mapping):
            continue
        profile_doc = dict(profile)
        tokenizer = dict(resolve_tokenizer(profile_doc))
        profile_rows[str(name)] = ai_runtime_contracts.token_accounting_profile_entry(str(name), profile_doc, tokenizer)
    data = ai_runtime_contracts.token_accounting_profiles_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
        root=root,
        profile_rows=profile_rows,
    )
    _write_latest_history_with_error_status(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        daily_path=daily_path,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    return data


def token_accounting_latest_readmodel(
    *,
    latest_path: Path,
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    read_json: JsonReadPort,
) -> dict[str, Any]:
    data, error = read_json(latest_path)
    if data is None:
        return {
            "schema": f"{schema_prefix}_ai_token_accounting_latest_read_v1",
            "version": version,
            "generated_at": now_iso(),
            "ok": False,
            "path": str(latest_path),
            "error": error or "missing",
        }
    if not isinstance(data, Mapping):
        return {
            "schema": f"{schema_prefix}_ai_token_accounting_latest_read_v1",
            "version": version,
            "generated_at": now_iso(),
            "ok": False,
            "path": str(latest_path),
            "error": "invalid_latest_json",
        }
    result = dict(data)
    result["read_at"] = now_iso()
    return result


def token_accounting_count_text_readmodel(
    *,
    profile_name: str,
    text: str,
    profiles_payload: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    write_latest: bool,
    latest_path: Path,
    daily_path: DailyPathPort,
    write_json: JsonWritePort,
    append_jsonl: JsonlAppendPort,
    timeout: float,
    environ: Mapping[str, str],
    count_subprocess: TokenCountSubprocessPort | None = None,
) -> dict[str, Any]:
    profiles = profiles_payload.get("profiles") if isinstance(profiles_payload.get("profiles"), Mapping) else {}
    profile = profiles.get(profile_name)
    generated_at = now_iso()
    if not isinstance(profile, Mapping):
        return ai_runtime_contracts.token_accounting_count_error_result(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            profile_name=profile_name,
            error="profile_not_found",
            known_profiles=sorted(str(name) for name in profiles),
        )
    profile_doc = dict(profile)
    if not profile_doc.get("exact_supported"):
        return ai_runtime_contracts.token_accounting_count_error_result(
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            profile_name=profile_name,
            error="exact_tokenizer_not_ready",
            profile_status=profile_doc,
        )

    runner = count_subprocess or token_accounting_count_subprocess
    execution = dict(runner(profile=profile_doc, text=text, timeout=timeout, environ=environ))
    outcome = dict(execution["outcome"])
    data = ai_runtime_contracts.token_accounting_count_document(
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        profile_name=profile_name,
        profile=profile_doc,
        input_bytes=execution["input_bytes"],
        elapsed_sec=execution["elapsed_sec"],
        total_tokens=outcome["total_tokens"],
        ok=bool(outcome["ok"]),
        error=outcome["error"],
        returncode=outcome["returncode"],
        stderr=outcome["stderr"],
    )
    _write_latest_history_with_error_status(
        data,
        write_latest=write_latest,
        latest_path=latest_path,
        daily_path=daily_path,
        write_json=write_json,
        append_jsonl=append_jsonl,
    )
    return data


def python_runtime_versions(
    *,
    config: Mapping[str, Any],
    run_command: RunPort,
    which: WhichPort,
    subprocess_env: Mapping[str, str],
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    openvino_config = config.get("openvino", {}) if isinstance(config.get("openvino"), Mapping) else {}
    python = which("abyss-openvino-python") or str(openvino_config.get("python", ""))
    if not python or not _path_exists(Path(python), path_exists):
        return {"ok": False, "python": python or None, "error": "abyss-openvino-python not found"}
    out = dict(run_command([python, "-c", PYTHON_RUNTIME_VERSION_SCRIPT], timeout=10.0, env=dict(subprocess_env)))
    data = ai_runtime_contracts.parse_json_stdout(str(out.get("stdout") or ""))
    if data is None:
        data = {"ok": False, "error": "invalid package version JSON", "stderr": out.get("stderr")}
    data["python"] = python
    return data


def kernel_module_snapshot(
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    modules = {}
    if command_exists("lsmod"):
        out = dict(run_command(["lsmod"], timeout=3.0))
        if out.get("ok"):
            interesting = {"i915", "xe", "intel_vpu", "intel_uncore", "drm_buddy", "drm_display_helper"}
            for line in str(out.get("stdout") or "").splitlines()[1:]:
                parts = line.split()
                if parts and parts[0] in interesting:
                    modules[parts[0]] = {"size": parts[1] if len(parts) > 1 else None, "used_by": parts[3:] if len(parts) > 3 else []}
    modinfo = {}
    if command_exists("modinfo"):
        for name in ("i915", "xe", "intel_vpu"):
            out = dict(run_command(["modinfo", name], timeout=3.0))
            modinfo[name] = {"ok": bool(out.get("ok")), "summary": "\n".join(str(out.get("stdout") or "").splitlines()[:20]) if out.get("ok") else out.get("stderr")}
    return {"loaded": modules, "modinfo": modinfo}
