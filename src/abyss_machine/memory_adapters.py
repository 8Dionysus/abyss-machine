from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Sequence

from . import process_adapters


CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[[Sequence[str], float], dict[str, Any]]
MonotonicPort = Callable[[], float]
ProcessInfoPort = Callable[[int], dict[str, Any] | None]
ProcessOwnerIdentityPort = Callable[[int], dict[str, Any] | None]
SystemdPropertiesPort = Callable[[str, list[str], bool, float], dict[str, Any]]
ControlValuePort = Callable[[Any], dict[str, Any]]
KibToMibPort = Callable[[Any], float | None]
ResidencyPort = Callable[[int], dict[str, Any]]
TtsStatusPort = Callable[[], dict[str, Any]]
AiPolicyPort = Callable[[], dict[str, Any]]
TtsProbePort = Callable[[str, int], dict[str, Any]]
SttProbePort = Callable[[str, str], dict[str, Any]]
LlmProbePort = Callable[[bool, int], dict[str, Any]]
OutputExistsPort = Callable[[str], bool]
TtsSynthPort = Callable[..., dict[str, Any]]
DictationTranscribePort = Callable[[str, str], dict[str, Any]]
LoadJsonDocumentPort = Callable[[Path], tuple[Any, Any]]


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_tool_process(command: Sequence[str], timeout: float) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(command),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout"}
    except OSError as exc:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(exc)}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def nested_get(data: Any, path: Sequence[str]) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _stable_hash_json(payload: Any, length: int = 24) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[: max(8, min(int(length), 64))]


def _kib_to_mib(value: Any) -> float | None:
    parsed = _safe_int(value, -1)
    if parsed < 0:
        return None
    return round(parsed / 1024.0, 1)


def hotpath_residency_brief(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary", {}) if isinstance(data.get("summary"), dict) else {}
    services: dict[str, Any] = {}
    for item in data.get("services", []) if isinstance(data.get("services"), list) else []:
        if not isinstance(item, dict):
            continue
        unit = str(item.get("unit") or "")
        if not unit:
            continue
        services[unit] = {
            "active": nested_get(item, ["systemd", "active_state"]),
            "class": item.get("class"),
            "memory_current_mib": nested_get(item, ["controls", "memory_current", "mib"]),
            "memory_peak_mib": nested_get(item, ["controls", "memory_peak", "mib"]),
            "memory_swap_mib": nested_get(item, ["controls", "memory_swap_current", "mib"]),
            "memory_low_mib": nested_get(item, ["controls", "memory_low", "mib"]),
            "memory_high_mib": nested_get(item, ["controls", "memory_high", "mib"]),
            "memory_swap_max": nested_get(item, ["controls", "memory_swap_max", "raw"]),
            "pss_mib": nested_get(item, ["derived", "sampled_process_pss_mib"]),
            "process_swap_mib": nested_get(item, ["derived", "sampled_process_swap_mib"]),
            "swap_to_pss_ratio": nested_get(item, ["derived", "cgroup_swap_to_sampled_pss_ratio"]),
            "runtime_pilot_active": nested_get(item, ["target", "runtime_pilot_active"]),
            "issues": [issue.get("code") for issue in item.get("issues", []) if isinstance(issue, dict)],
        }
    return {
        "status": data.get("status"),
        "memory_class": summary.get("memory_class"),
        "zram_disk_mib": summary.get("zram_disk_mib"),
        "zram_data_mib": summary.get("zram_data_mib"),
        "zram_resident_mib": summary.get("zram_resident_mib"),
        "zram_logical_free_mib": summary.get("zram_logical_free_mib"),
        "zram_logical_to_memory_ratio": summary.get("zram_logical_to_memory_ratio"),
        "swap_used_percent": summary.get("swap_used_percent"),
        "psi_some_avg10": summary.get("psi_some_avg10"),
        "psi_full_avg10": summary.get("psi_full_avg10"),
        "protected_high_swap_units": summary.get("protected_high_swap_units"),
        "services": services,
    }

def hotpath_tts_probe(
    text: str,
    index: int,
    *,
    synth_port: TtsSynthPort,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    result = synth_port(
        "quality-compact",
        text,
        output=None,
        force=False,
        allow_download=False,
        use_server=True,
        write_latest=True,
    )
    wall = round(monotonic() - started, 3)
    audio = result.get("audio", {}) if isinstance(result.get("audio"), dict) else {}
    server = result.get("server", {}) if isinstance(result.get("server"), dict) else {}
    gate = result.get("policy_gate", {}) if isinstance(result.get("policy_gate"), dict) else {}
    return {
        "index": index,
        "ok": bool(result.get("ok")),
        "profile": result.get("profile"),
        "engine": result.get("engine"),
        "device": result.get("device"),
        "client_wall_sec": wall,
        "reported_wall_sec": result.get("wall_sec"),
        "server_synth_sec": server.get("synth_sec"),
        "audio_sec": audio.get("duration_sec"),
        "rtf": result.get("rtf"),
        "output": result.get("output"),
        "server_used": bool(result.get("server")),
        "server_warm": server.get("warm") if server else nested_get(result, ["server_attempt", "warm"]),
        "policy_class": gate.get("policy_class"),
        "policy_allowed": gate.get("allowed"),
        "policy_reasons": gate.get("reasons") if isinstance(gate.get("reasons"), list) else [],
        "error": result.get("error"),
    }


def hotpath_stt_probe(
    audio: str,
    profile: str,
    *,
    transcribe_port: DictationTranscribePort,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    result = transcribe_port(audio, profile)
    wall = round(monotonic() - started, 3)
    timings = result.get("timings", {}) if isinstance(result.get("timings"), dict) else {}
    return {
        "profile": profile,
        "ok": bool(result.get("ok")),
        "via": result.get("via"),
        "client_wall_sec": wall,
        "client_elapsed_sec": result.get("client_elapsed_sec"),
        "elapsed_sec": result.get("elapsed_sec"),
        "generate_sec": timings.get("generate_sec"),
        "cache_hit": timings.get("cache_hit"),
        "audio_sec": result.get("processed_audio_duration_sec") or result.get("raw_audio_duration_sec"),
        "segments": [
            {
                "duration_sec": item.get("duration_sec"),
                "elapsed_sec": item.get("elapsed_sec"),
                "num_beams": item.get("num_beams"),
            }
            for item in result.get("segments", [])
            if isinstance(item, dict)
        ],
        "recognized_text": result.get("raw_text") or result.get("text"),
        "error": result.get("error"),
    }


def hotpath_llm_probe(
    include_llm: bool,
    limit: int,
    *,
    latest_path: Path,
    controller_path: Path,
    load_json_document: LoadJsonDocumentPort,
    runner: CommandRunnerPort = run_tool_process,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    if not include_llm:
        latest, error = load_json_document(latest_path)
        summary = latest.get("summary") if isinstance(latest, dict) and isinstance(latest.get("summary"), dict) else {}
        return {
            "mode": "latest_only",
            "executed": False,
            "latest": str(latest_path),
            "latest_ok": bool(latest.get("ok")) if isinstance(latest, dict) else False,
            "latest_error": error,
            "selected_job": summary.get("selected_job"),
            "status": summary.get("status"),
            "elapsed_ms": summary.get("elapsed_ms"),
            "policy_decision": summary.get("policy_decision"),
            "fallback_used": summary.get("fallback_used"),
            "model_used": summary.get("model_used"),
        }
    cmd = [str(controller_path), "micro", "--limit", str(max(1, min(int(limit), 16))), "--json"]
    started = monotonic()
    out = runner(cmd, 360.0)
    wall = round(monotonic() - started, 3)
    raw = str(out.get("stdout") or "").strip()
    parsed: dict[str, Any] | None = None
    if raw:
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                parsed = loaded
        except json.JSONDecodeError:
            parsed = None
    summary = parsed.get("summary") if isinstance(parsed, dict) and isinstance(parsed.get("summary"), dict) else {}
    return {
        "mode": "executed",
        "executed": True,
        "ok": bool(parsed.get("ok")) if isinstance(parsed, dict) else False,
        "returncode": out.get("returncode"),
        "client_wall_sec": wall,
        "selected_job": summary.get("selected_job"),
        "next_job": summary.get("next_job"),
        "status": summary.get("status"),
        "elapsed_ms": summary.get("elapsed_ms"),
        "policy_decision": summary.get("policy_decision"),
        "fallback_used": summary.get("fallback_used"),
        "model_used": summary.get("model_used"),
        "latest": str(latest_path),
        "stderr_tail": str(out.get("stderr") or "")[-1000:] or None,
        "stdout_parse_error": None if parsed is not None else (raw[-1000:] if raw else "empty stdout"),
    }


def hotpath_probe_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    text: str,
    repeat_tts: int,
    stt_profiles: Sequence[str] | None,
    include_llm: bool,
    llm_limit: int,
    top: int,
    monotonic: MonotonicPort,
    residency_port: ResidencyPort,
    tts_status_port: TtsStatusPort,
    ai_policy_port: AiPolicyPort,
    tts_probe_port: TtsProbePort,
    stt_probe_port: SttProbePort,
    llm_probe_port: LlmProbePort,
    output_exists_port: OutputExistsPort,
    paths_refs: dict[str, Any],
) -> dict[str, Any]:
    text = str(text or "").strip()
    repeat_tts = max(1, min(int(repeat_tts), 3))
    profiles = [str(item).strip() for item in (stt_profiles or ["command", "quality"]) if str(item).strip()]
    if not profiles:
        profiles = ["command"]

    started = monotonic()
    before = residency_port(top)
    tts_status_before = tts_status_port()
    ai_policy_before = ai_policy_port()

    tts_runs: list[dict[str, Any]] = []
    audio_for_stt: str | None = None
    for index in range(1, repeat_tts + 1):
        probe = tts_probe_port(text, index)
        tts_runs.append(probe)
        if audio_for_stt is None and probe.get("ok") and probe.get("output"):
            output = str(probe.get("output"))
            if output_exists_port(output):
                audio_for_stt = output

    after_tts = residency_port(top)
    stt_runs = [stt_probe_port(audio_for_stt, profile) for profile in profiles] if audio_for_stt else []
    llm = llm_probe_port(include_llm, llm_limit)
    after = residency_port(top)
    ai_policy_after = ai_policy_port()

    before_brief = hotpath_residency_brief(before)
    after_tts_brief = hotpath_residency_brief(after_tts)
    after_brief = hotpath_residency_brief(after)

    first_tts = tts_runs[0] if tts_runs else {}
    last_tts = tts_runs[-1] if tts_runs else {}
    first_tts_wall = _safe_float(first_tts.get("reported_wall_sec") or first_tts.get("client_wall_sec"), None)
    last_tts_wall = _safe_float(last_tts.get("reported_wall_sec") or last_tts.get("client_wall_sec"), None)
    swap_before = _safe_float(before_brief.get("swap_used_percent"), None)
    swap_after_tts = _safe_float(after_tts_brief.get("swap_used_percent"), None)
    swap_after = _safe_float(after_brief.get("swap_used_percent"), None)

    findings: list[str] = []
    issues: list[str] = []
    if swap_before is not None and swap_after_tts is not None and swap_after_tts <= swap_before - 10.0:
        findings.append("tts_warmup_reclaimed_zram_headroom")
    if first_tts_wall is not None and last_tts_wall is not None and repeat_tts > 1 and last_tts_wall <= first_tts_wall * 0.75:
        findings.append("tts_second_run_faster_after_swapin")
    if first_tts_wall is not None and first_tts_wall > 15.0:
        issues.append("first_tts_slow")
    if last_tts_wall is not None and last_tts_wall > 8.0:
        issues.append("warm_tts_still_slow")
    for item in stt_runs:
        wall = _safe_float(item.get("client_elapsed_sec") or item.get("client_wall_sec"), None)
        if item.get("profile") == "command" and wall is not None and wall <= 2.0:
            findings.append("dictation_command_path_interactive")
        if item.get("profile") == "quality" and wall is not None and wall > 4.0:
            issues.append("dictation_quality_path_slow")
    if _safe_float(after_brief.get("psi_full_avg10"), 0.0) and float(after_brief.get("psi_full_avg10") or 0.0) > 0.5:
        issues.append("active_memory_stalls_after_probe")
    if include_llm:
        llm_elapsed = _safe_float(llm.get("elapsed_ms"), None)
        if llm_elapsed is not None and llm_elapsed > 30000.0:
            issues.append("resident_llm_micro_slow")
        if llm.get("fallback_used"):
            issues.append("resident_llm_fallback_used")

    probe_failed = any(not item.get("ok") for item in tts_runs) or any(not item.get("ok") for item in stt_runs)
    status = "failed" if probe_failed else ("watch" if issues else "ok")
    return {
        "schema": f"{schema_prefix}_memory_hotpath_probe_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not probe_failed,
        "status": status,
        "summary": {
            "status": status,
            "findings": sorted(set(findings)),
            "issues": sorted(set(issues)),
            "duration_sec": round(monotonic() - started, 3),
            "tts_runs": len(tts_runs),
            "stt_runs": len(stt_runs),
            "llm_executed": bool(include_llm),
            "first_tts_wall_sec": first_tts_wall,
            "last_tts_wall_sec": last_tts_wall,
            "command_stt_client_sec": next((item.get("client_elapsed_sec") for item in stt_runs if item.get("profile") == "command"), None),
            "quality_stt_client_sec": next((item.get("client_elapsed_sec") for item in stt_runs if item.get("profile") == "quality"), None),
            "llm_elapsed_ms": llm.get("elapsed_ms") if include_llm else None,
            "llm_latest_elapsed_ms": llm.get("elapsed_ms") if not include_llm else None,
            "swap_used_percent_before": swap_before,
            "swap_used_percent_after_tts": swap_after_tts,
            "swap_used_percent_after": swap_after,
        },
        "request": {
            "text_chars": len(text),
            "tts_profile": "quality-compact",
            "repeat_tts": repeat_tts,
            "stt_profiles": profiles,
            "include_llm": bool(include_llm),
            "llm_limit": int(llm_limit),
            "top": int(top),
        },
        "before": {
            "memory": before_brief,
            "tts_server": {
                "ok": tts_status_before.get("ok"),
                "active": nested_get(tts_status_before, ["service", "active"]),
                "enabled": nested_get(tts_status_before, ["service", "enabled"]),
                "profile": nested_get(tts_status_before, ["ping", "profile"]),
            },
            "ai_policy": {
                "class": ai_policy_before.get("class"),
                "heavy_policy": ai_policy_before.get("heavy_policy"),
                "can_run_heavy": ai_policy_before.get("can_run_heavy"),
                "temperature_c": nested_get(ai_policy_before, ["current", "thermal", "current_temperature_c"]),
                "hot_temperature_c": nested_get(ai_policy_before, ["thresholds", "hot_temperature_c"]),
            },
        },
        "probes": {
            "tts": tts_runs,
            "dictation": stt_runs,
            "resident_llm": llm,
        },
        "after_tts": {
            "memory": after_tts_brief,
        },
        "after": {
            "memory": after_brief,
            "ai_policy": {
                "class": ai_policy_after.get("class"),
                "heavy_policy": ai_policy_after.get("heavy_policy"),
                "can_run_heavy": ai_policy_after.get("can_run_heavy"),
                "temperature_c": nested_get(ai_policy_after, ["current", "thermal", "current_temperature_c"]),
                "hot_temperature_c": nested_get(ai_policy_after, ["thresholds", "hot_temperature_c"]),
            },
        },
        "paths": {
            "latest": str(paths_refs.get("latest")),
            "retention": "latest_only",
            "memory_residency_latest": str(paths_refs.get("memory_residency_latest")),
            "tts_latest": str(paths_refs.get("tts_latest")),
            "llm_micro_latest": str(paths_refs.get("llm_micro_latest")),
        },
        "policy": {
            "facts_only": True,
            "does_not_stop_disable_restart_or_throttle_services": True,
            "does_not_apply_cgroup_properties": True,
            "does_not_record_microphone": True,
            "synthetic_tts_audio_only": True,
            "memory_swapmax_deferred": True,
        },
        "non_claims": [
            "This probe measures synthetic hot-path latency and zram impact; it is not a full TTS or STT quality eval.",
            "Slow protected-service latency is evidence for warmup/cgroup/zram policy, not a recommendation to stop the service.",
            "The resident LLM probe is latest-only unless --include-llm is passed.",
        ],
    }


def parse_key_value_file(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in _read_text(path).splitlines():
        key, sep, value = line.partition(" ")
        if not sep:
            continue
        try:
            result[key.strip()] = int(value.strip())
        except ValueError:
            pass
    return result


def parse_pressure_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    text = _read_text(path)
    if not text:
        return result
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        key = parts[0]
        values: dict[str, Any] = {}
        for item in parts[1:]:
            name, sep, value = item.partition("=")
            if not sep:
                continue
            try:
                values[name] = float(value) if "." in value else int(value)
            except ValueError:
                values[name] = value
        result[key] = values
    return result


def _bytes_to_mib(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return round(float(value) / 1024.0 / 1024.0, 1)
    except (TypeError, ValueError):
        return None


def _kib_to_mib(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return round(float(value) / 1024.0, 1)
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any, digits: int = 3) -> float | None:
    if isinstance(numerator, bool) or isinstance(denominator, bool):
        return None
    try:
        numerator_f = float(numerator)
        denominator_f = float(denominator)
    except (TypeError, ValueError):
        return None
    if denominator_f <= 0:
        return None
    return round(numerator_f / denominator_f, digits)


def vmstat_snapshot(*, proc_root: Path = Path("/proc")) -> dict[str, Any]:
    wanted = {
        "pswpin",
        "pswpout",
        "pgmajfault",
        "pgfault",
        "oom_kill",
        "pgscan_kswapd",
        "pgscan_direct",
        "pgsteal_kswapd",
        "pgsteal_direct",
        "allocstall",
        "compact_stall",
    }
    values: dict[str, int] = {}
    text = _read_text(proc_root / "vmstat")
    if text:
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] in wanted:
                try:
                    values[parts[0]] = int(parts[1])
                except ValueError:
                    pass
    return values


def sysctl_snapshot(*, runner: CommandRunnerPort = run_tool_process) -> dict[str, Any]:
    keys = [
        "vm.swappiness",
        "vm.vfs_cache_pressure",
        "vm.watermark_scale_factor",
        "vm.min_free_kbytes",
        "vm.page-cluster",
        "vm.overcommit_memory",
        "vm.overcommit_ratio",
    ]
    out = runner(["sysctl", *keys], 2.0)
    values: dict[str, str] = {}
    if out.get("stdout"):
        for line in str(out["stdout"]).splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key.strip()] = value.strip()
    return {"ok": out.get("ok"), "values": values, "stderr": out.get("stderr")}


def swap_status(*, runner: CommandRunnerPort = run_tool_process) -> dict[str, Any]:
    out = runner(["swapon", "--show", "--raw", "--bytes"], 2.0)
    devices: list[dict[str, Any]] = []
    if out.get("stdout"):
        lines = str(out["stdout"]).splitlines()
        headers = lines[0].split() if lines else []
        for line in lines[1:]:
            values = line.split()
            if len(values) < len(headers):
                continue
            item = dict(zip(headers, values))
            for key in ("SIZE", "USED", "PRIO"):
                if key in item:
                    try:
                        item[key.lower()] = int(item.pop(key))
                    except ValueError:
                        item[key.lower()] = item.pop(key)
            for key in ("NAME", "TYPE"):
                if key in item:
                    item[key.lower()] = item.pop(key)
            devices.append(item)
    total = sum(int(item.get("size") or 0) for item in devices)
    used = sum(int(item.get("used") or 0) for item in devices)
    free = max(0, total - used)
    return {
        "ok": out.get("ok"),
        "devices": devices,
        "summary": {
            "devices": len(devices),
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "total_mib": _bytes_to_mib(total),
            "used_mib": _bytes_to_mib(used),
            "free_mib": _bytes_to_mib(free),
            "used_percent": round((used / total) * 100.0, 3) if total > 0 else None,
        },
        "stderr": out.get("stderr"),
    }


def zram_status(*, runner: CommandRunnerPort = run_tool_process) -> dict[str, Any]:
    out = runner(
        ["zramctl", "--raw", "--bytes", "--output", "NAME,ALGORITHM,DISKSIZE,DATA,COMPR,TOTAL,STREAMS"],
        2.0,
    )
    devices: list[dict[str, Any]] = []
    if out.get("stdout"):
        lines = str(out["stdout"]).splitlines()
        headers = lines[0].split() if lines else []
        for line in lines[1:]:
            values = line.split()
            if len(values) < len(headers):
                values.extend([""] * (len(headers) - len(values)))
            item = dict(zip(headers, values))
            clean: dict[str, Any] = {}
            for key, value in item.items():
                out_key = key.lower()
                if out_key in {"disksize", "data", "compr", "total", "streams"} and str(value).strip():
                    try:
                        clean[out_key] = int(value)
                    except ValueError:
                        clean[out_key] = value
                else:
                    clean[out_key] = value
            devices.append(clean)
    disk_bytes = sum(int(item.get("disksize") or 0) for item in devices if isinstance(item.get("disksize"), int))
    data_bytes = sum(int(item.get("data") or 0) for item in devices if isinstance(item.get("data"), int))
    compressed_bytes = sum(int(item.get("compr") or 0) for item in devices if isinstance(item.get("compr"), int))
    total_memory_bytes = sum(int(item.get("total") or 0) for item in devices if isinstance(item.get("total"), int))
    summary = {
        "devices": len(devices),
        "disk_bytes": disk_bytes,
        "data_bytes": data_bytes,
        "compressed_bytes": compressed_bytes,
        "total_memory_bytes": total_memory_bytes,
        "disk_mib": _bytes_to_mib(disk_bytes),
        "data_mib": _bytes_to_mib(data_bytes),
        "compressed_mib": _bytes_to_mib(compressed_bytes),
        "total_memory_mib": _bytes_to_mib(total_memory_bytes),
        "allocator_overhead_mib": _bytes_to_mib(max(0, total_memory_bytes - compressed_bytes)),
        "logical_to_compressed_ratio": _safe_ratio(data_bytes, compressed_bytes),
        "logical_to_memory_ratio": _safe_ratio(data_bytes, total_memory_bytes),
    }
    return {
        "ok": out.get("ok"),
        "devices": devices,
        "summary": summary,
        "stderr": out.get("stderr"),
    }


def zswap_status(*, module_root: Path = Path("/sys/module/zswap/parameters")) -> dict[str, Any]:
    params: dict[str, str] = {}
    if module_root.exists():
        try:
            for item in module_root.iterdir():
                if item.is_file():
                    params[item.name] = _read_text(item)
        except OSError:
            pass
    return {
        "available": module_root.exists(),
        "enabled": str(params.get("enabled", "")).strip().upper() in {"Y", "1", "TRUE"},
        "parameters": params,
    }


def cgroup_status(*, cgroup_root: Path = Path("/sys/fs/cgroup"), uid: int | None = None) -> dict[str, Any]:
    user_id = os.getuid() if uid is None else uid
    paths = {
        "root": cgroup_root,
        "user": cgroup_root / "user.slice" / f"user-{user_id}.slice",
    }
    scopes: dict[str, Any] = {}
    for name, path in paths.items():
        scopes[name] = {
            "path": str(path),
            "exists": path.exists(),
            "memory_current": _read_optional_int(path / "memory.current"),
            "memory_max": _read_text(path / "memory.max"),
            "memory_pressure": parse_pressure_file(path / "memory.pressure"),
            "memory_events": parse_key_value_file(path / "memory.events"),
        }
    return scopes


def _read_optional_int(path: Path) -> int | None:
    text = _read_text(path)
    if not text:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def meminfo_details(raw: dict[str, int]) -> dict[str, Any]:
    total = raw.get("MemTotal", 0)
    available = raw.get("MemAvailable", 0)
    free = raw.get("MemFree", 0)
    swap_total = raw.get("SwapTotal", 0)
    swap_free = raw.get("SwapFree", 0)
    swap_used = max(0, swap_total - swap_free)
    commit_limit = raw.get("CommitLimit", 0)
    committed = raw.get("Committed_AS", 0)
    return {
        "raw_kib": {
            key: raw.get(key)
            for key in sorted(raw)
            if key
            in {
                "MemTotal",
                "MemAvailable",
                "MemFree",
                "Buffers",
                "Cached",
                "SwapCached",
                "Active",
                "Inactive",
                "Shmem",
                "Slab",
                "SReclaimable",
                "SUnreclaim",
                "SwapTotal",
                "SwapFree",
                "Zswap",
                "CommitLimit",
                "Committed_AS",
                "AnonHugePages",
            }
        },
        "summary": {
            "mem_total_mib": _kib_to_mib(total),
            "mem_available_mib": _kib_to_mib(available),
            "mem_free_mib": _kib_to_mib(free),
            "mem_available_percent": round((available / total) * 100.0, 2) if total else None,
            "swap_total_mib": _kib_to_mib(swap_total),
            "swap_used_mib": _kib_to_mib(swap_used),
            "swap_free_mib": _kib_to_mib(swap_free),
            "swap_used_percent": round((swap_used / swap_total) * 100.0, 3) if swap_total else None,
            "shmem_mib": _kib_to_mib(raw.get("Shmem")),
            "slab_mib": _kib_to_mib(raw.get("Slab")),
            "sreclaimable_mib": _kib_to_mib(raw.get("SReclaimable")),
            "sunreclaim_mib": _kib_to_mib(raw.get("SUnreclaim")),
            "commit_limit_mib": _kib_to_mib(commit_limit),
            "committed_as_mib": _kib_to_mib(committed),
            "commit_percent": round((committed / commit_limit) * 100.0, 2) if commit_limit else None,
        },
    }


def process_rollup(pid: int, *, proc_root: Path = Path("/proc")) -> dict[str, Any]:
    data = _read_text(proc_root / str(pid) / "smaps_rollup")
    result: dict[str, Any] = {"available": bool(data)}
    if not data:
        return result
    wanted = {
        "Rss": "rss_kib",
        "Pss": "pss_kib",
        "Pss_Dirty": "pss_dirty_kib",
        "Shared_Clean": "shared_clean_kib",
        "Shared_Dirty": "shared_dirty_kib",
        "Private_Clean": "private_clean_kib",
        "Private_Dirty": "private_dirty_kib",
        "Referenced": "referenced_kib",
        "Anonymous": "anonymous_kib",
        "Swap": "swap_kib",
        "SwapPss": "swap_pss_kib",
    }
    for line in data.splitlines():
        key, sep, value = line.partition(":")
        if not sep or key not in wanted:
            continue
        parsed = process_adapters.parse_kib_field(value)
        if parsed is not None:
            result[wanted[key]] = parsed
    return result


_CODEX_SESSION_PATH_RE = re.compile(r"/(?:sessions|archived_sessions)/", re.IGNORECASE)
_CODEX_ROLLOUT_THREAD_RE = re.compile(
    r"(?P<thread>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
    re.IGNORECASE,
)


def codex_thread_identity(pid: int, *, proc_root: Path = Path("/proc")) -> dict[str, Any] | None:
    if pid <= 0:
        return None
    fd_root = proc_root / str(pid) / "fd"
    try:
        entries = list(fd_root.iterdir())
    except OSError:
        return None
    thread_ids: set[str] = set()
    for entry in entries:
        try:
            target = os.readlink(entry)
        except OSError:
            continue
        target = target.removesuffix(" (deleted)")
        if not _CODEX_SESSION_PATH_RE.search(target):
            continue
        match = _CODEX_ROLLOUT_THREAD_RE.search(target.rsplit("/", 1)[-1])
        if match:
            thread_ids.add(match.group("thread").lower())
    if not thread_ids:
        return None
    candidates = sorted(thread_ids)
    return {
        "owner": "codex",
        "identity_scope": "thread",
        "stable_id": candidates[0] if len(candidates) == 1 else None,
        "candidate_ids": candidates,
        "ambiguous": len(candidates) != 1,
        "evidence": "open_rollout_fd",
        "content_read": False,
    }


def _is_codex_process(item: dict[str, Any]) -> bool:
    for key in ("name", "comm", "exe"):
        value = str(item.get(key) or "").strip()
        if value and Path(value).name.casefold() == "codex":
            return True
    return False


def process_owner_identities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None, tuple[str, ...]]] = set()
    for item in items:
        identity = item.get("owner_identity")
        if not isinstance(identity, dict):
            continue
        candidates = tuple(str(value) for value in identity.get("candidate_ids", []) if value)
        key = (
            str(identity.get("owner") or ""),
            str(identity.get("identity_scope") or ""),
            str(identity.get("stable_id")) if identity.get("stable_id") else None,
            candidates,
        )
        if key in seen:
            continue
        seen.add(key)
        identities.append(dict(identity))
    return identities


def proc_cgroup_path(cgroup_lines: Any) -> str | None:
    if isinstance(cgroup_lines, str):
        lines = cgroup_lines.splitlines()
    elif isinstance(cgroup_lines, list):
        lines = [str(item) for item in cgroup_lines]
    else:
        return None
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[2].startswith("/"):
            return parts[2]
    return None


def cgroup_unit_hint(cgroup_path: str | None) -> str | None:
    if not cgroup_path:
        return None
    parts = [part for part in cgroup_path.split("/") if part]
    for part in reversed(parts):
        if part.endswith((".service", ".scope", ".slice")):
            return part
    return parts[-1] if parts else None


def cgroup_primary_bucket(
    items: list[dict[str, Any]],
    *,
    protected_roles: set[str] | frozenset[str],
) -> tuple[str, str, bool, str]:
    role_counts: collections.Counter[str] = collections.Counter()
    workload_counts: collections.Counter[str] = collections.Counter()
    for item in items:
        role = str(item.get("capability_role") or "none")
        workload = str(item.get("workload_hint") or "normal")
        role_counts[role] += 1
        workload_counts[workload] += 1
    role = role_counts.most_common(1)[0][0] if role_counts else "none"
    workload = workload_counts.most_common(1)[0][0] if workload_counts else "normal"
    protected = role in protected_roles or workload == "game"
    if protected:
        route = "route_new_work_around_protected_capability"
    elif workload == "game_platform":
        route = "operator_review_game_platform_only"
    elif workload in {"development", "browser", "normal"}:
        route = "operator_review_candidate"
    else:
        route = "observe"
    return workload, role, protected, route


def podman_container_index(
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "available": False,
        "containers": 0,
        "by_pid": {},
        "error": None,
    }
    if not command_exists("podman"):
        data["error"] = "podman_not_installed"
        return data
    out = runner(["podman", "ps", "--format", "json"], 8.0)
    if not out.get("ok"):
        data["error"] = out.get("stderr") or out.get("stdout") or "podman_ps_failed"
        return data
    try:
        raw = json.loads(str(out.get("stdout") or "[]"))
    except json.JSONDecodeError as exc:
        data["error"] = f"invalid_podman_json:{exc}"
        return data
    if not isinstance(raw, list):
        raw = []
    by_pid: dict[int, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = _safe_int(item.get("Pid"), 0)
        if pid <= 0:
            continue
        labels = process_adapters.sanitized_container_labels(item.get("Labels"))
        names = process_adapters.container_name_list(item.get("Names"))
        name = names[0] if names else str(item.get("Id") or "")[:12]
        by_pid[pid] = {
            "id": str(item.get("Id") or "")[:12],
            "name": name,
            "names": names,
            "image": item.get("Image"),
            "status": item.get("Status"),
            "compose_project": labels.get("io.podman.compose.project") or labels.get("com.docker.compose.project"),
            "compose_service": labels.get("io.podman.compose.service") or labels.get("com.docker.compose.service"),
            "systemd_unit": labels.get("PODMAN_SYSTEMD_UNIT"),
            "labels": labels,
        }
    data.update({"ok": True, "available": True, "containers": len(raw), "by_pid": by_pid})
    return data


def podman_container_for_pids(pids: list[int], podman_index: dict[str, Any] | None) -> dict[str, Any] | None:
    by_pid = podman_index.get("by_pid") if isinstance(podman_index, dict) else None
    if not isinstance(by_pid, dict):
        return None
    for pid in pids:
        item = by_pid.get(pid)
        if isinstance(item, dict):
            return item
    return None


def cgroup_swap_snapshot(
    processes: list[dict[str, Any]],
    top: int = 40,
    podman_index: dict[str, Any] | None = None,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    protected_roles: set[str] | frozenset[str],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in processes:
        cgroup_path = proc_cgroup_path(item.get("cgroup"))
        if not cgroup_path:
            continue
        grouped.setdefault(cgroup_path, []).append(item)

    entries: list[dict[str, Any]] = []
    read_count = 0
    missing_count = 0
    for cgroup_path, items in grouped.items():
        sys_path = cgroup_root / cgroup_path.lstrip("/")
        swap_current = _read_optional_int(sys_path / "memory.swap.current")
        memory_current = _read_optional_int(sys_path / "memory.current")
        if swap_current is None:
            missing_count += 1
            continue
        read_count += 1
        if swap_current <= 0:
            continue
        workload, role, protected, route = cgroup_primary_bucket(items, protected_roles=protected_roles)
        pids = [int(item["pid"]) for item in items if isinstance(item.get("pid"), int)]
        names = sorted({str(item.get("name") or item.get("comm") or "") for item in items if item.get("name") or item.get("comm")})[:8]
        swap_rollup_kib = sum(int(item.get("swap_kib") or 0) for item in items)
        pss_rollup_kib = sum(int(item.get("pss_kib") or 0) for item in items)
        podman_container = podman_container_for_pids(pids, podman_index)
        entries.append(
            {
                "cgroup": cgroup_path,
                "unit": cgroup_unit_hint(cgroup_path),
                "podman": podman_container,
                "container_name": podman_container.get("name") if isinstance(podman_container, dict) else None,
                "compose_service": podman_container.get("compose_service") if isinstance(podman_container, dict) else None,
                "processes": len(items),
                "pids": pids[:20],
                "names": names,
                "owner_identities": process_owner_identities(items),
                "workload_hint": workload,
                "capability_role": role,
                "protected": protected,
                "route": route,
                "memory_current_kib": int(memory_current / 1024) if isinstance(memory_current, int) else None,
                "memory_current_mib": _bytes_to_mib(memory_current) if isinstance(memory_current, int) else None,
                "swap_current_kib": int(swap_current / 1024),
                "swap_current_mib": _bytes_to_mib(swap_current),
                "process_swap_rollup_kib": swap_rollup_kib,
                "process_swap_rollup_mib": _kib_to_mib(swap_rollup_kib),
                "process_pss_rollup_kib": pss_rollup_kib,
                "process_pss_rollup_mib": _kib_to_mib(pss_rollup_kib),
            }
        )

    entries.sort(key=lambda item: int(item.get("swap_current_kib") or 0), reverse=True)
    selected = entries[: max(5, min(int(top), 200))]
    return {
        "coverage": "cgroup_memory_swap_current",
        "cgroups_seen": len(grouped),
        "cgroups_read": read_count,
        "cgroups_missing_swap_counter": missing_count,
        "podman_containers_indexed": podman_index.get("containers") if isinstance(podman_index, dict) else None,
        "podman_index_error": podman_index.get("error") if isinstance(podman_index, dict) else None,
        "top": selected,
        "top_swap_total_kib": sum(int(item.get("swap_current_kib") or 0) for item in selected),
    }


def cgroup_memory_snapshot(
    processes: list[dict[str, Any]],
    top: int = 40,
    podman_index: dict[str, Any] | None = None,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    protected_roles: set[str] | frozenset[str],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in processes:
        cgroup_path = proc_cgroup_path(item.get("cgroup"))
        if not cgroup_path:
            continue
        grouped.setdefault(cgroup_path, []).append(item)

    entries: list[dict[str, Any]] = []
    read_count = 0
    missing_count = 0
    for cgroup_path, items in grouped.items():
        sys_path = cgroup_root / cgroup_path.lstrip("/")
        memory_current = _read_optional_int(sys_path / "memory.current")
        swap_current = _read_optional_int(sys_path / "memory.swap.current")
        if memory_current is None:
            missing_count += 1
            continue
        read_count += 1
        if memory_current <= 0:
            continue
        workload, role, protected, route = cgroup_primary_bucket(items, protected_roles=protected_roles)
        pids = [int(item["pid"]) for item in items if isinstance(item.get("pid"), int)]
        names = sorted({str(item.get("name") or item.get("comm") or "") for item in items if item.get("name") or item.get("comm")})[:8]
        rss_rollup_kib = sum(int(item.get("vmrss_kib") or item.get("rss_kib") or 0) for item in items)
        pss_rollup_kib = sum(int(item.get("pss_kib") or 0) for item in items)
        swap_rollup_kib = sum(int(item.get("swap_kib") or 0) for item in items)
        podman_container = podman_container_for_pids(pids, podman_index)
        entries.append(
            {
                "cgroup": cgroup_path,
                "unit": cgroup_unit_hint(cgroup_path),
                "podman": podman_container,
                "container_name": podman_container.get("name") if isinstance(podman_container, dict) else None,
                "compose_service": podman_container.get("compose_service") if isinstance(podman_container, dict) else None,
                "processes": len(items),
                "pids": pids[:20],
                "names": names,
                "owner_identities": process_owner_identities(items),
                "workload_hint": workload,
                "capability_role": role,
                "protected": protected,
                "route": route,
                "memory_current_kib": int(memory_current / 1024),
                "memory_current_mib": _bytes_to_mib(memory_current),
                "swap_current_kib": int((swap_current or 0) / 1024),
                "swap_current_mib": _bytes_to_mib(swap_current or 0),
                "process_rss_rollup_kib": rss_rollup_kib,
                "process_rss_rollup_mib": _kib_to_mib(rss_rollup_kib),
                "process_pss_rollup_kib": pss_rollup_kib,
                "process_pss_rollup_mib": _kib_to_mib(pss_rollup_kib),
                "process_swap_rollup_kib": swap_rollup_kib,
                "process_swap_rollup_mib": _kib_to_mib(swap_rollup_kib),
            }
        )

    entries.sort(key=lambda item: int(item.get("memory_current_kib") or 0), reverse=True)
    selected = entries[: max(5, min(int(top), 200))]
    return {
        "coverage": "cgroup_memory_current",
        "cgroups_seen": len(grouped),
        "cgroups_read": read_count,
        "cgroups_missing_memory_counter": missing_count,
        "podman_containers_indexed": podman_index.get("containers") if isinstance(podman_index, dict) else None,
        "podman_index_error": podman_index.get("error") if isinstance(podman_index, dict) else None,
        "top": selected,
        "top_memory_total_kib": sum(int(item.get("memory_current_kib") or 0) for item in selected),
        "top_swap_total_kib": sum(int(item.get("swap_current_kib") or 0) for item in selected),
    }


def process_snapshot(
    top: int = 40,
    smaps: bool = True,
    *,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    process_info: ProcessInfoPort,
    owner_identity_port: ProcessOwnerIdentityPort | None = None,
    podman_index_port: Callable[[], dict[str, Any]] = podman_container_index,
    protected_roles: set[str] | frozenset[str],
) -> dict[str, Any]:
    top = max(5, min(int(top), 200))
    resolve_owner_identity = owner_identity_port or (lambda pid: codex_thread_identity(pid, proc_root=proc_root))
    processes: list[dict[str, Any]] = []
    inaccessible = 0
    try:
        proc_entries = list(proc_root.iterdir())
    except OSError:
        proc_entries = []
    for entry in proc_entries:
        if not entry.name.isdigit():
            continue
        info = process_info(int(entry.name))
        if info is None:
            inaccessible += 1
            continue
        if _is_codex_process(info):
            identity = resolve_owner_identity(int(entry.name))
            if identity:
                info["owner_identity"] = identity
        processes.append(info)

    candidates = sorted(processes, key=lambda item: int(item.get("vmrss_kib") or 0), reverse=True)[: max(top * 4, 80)]
    smaps_read = 0
    smaps_missing = 0
    if smaps:
        candidate_pids = {int(item["pid"]) for item in candidates if isinstance(item.get("pid"), int)}
        for item in processes:
            pid = item.get("pid")
            if not isinstance(pid, int) or pid not in candidate_pids:
                continue
            rollup = process_rollup(pid, proc_root=proc_root)
            item["memory_rollup"] = rollup
            if rollup.get("available"):
                smaps_read += 1
                for key in ("rss_kib", "pss_kib", "swap_kib", "swap_pss_kib", "private_dirty_kib", "shared_clean_kib"):
                    if key in rollup:
                        item[key] = rollup[key]
            else:
                smaps_missing += 1

    top_rss = sorted(processes, key=lambda item: int(item.get("vmrss_kib") or item.get("rss_kib") or 0), reverse=True)[:top]
    top_pss = sorted(
        [item for item in processes if isinstance(item.get("pss_kib"), int)],
        key=lambda item: int(item.get("pss_kib") or 0),
        reverse=True,
    )[:top]
    top_swap = sorted(
        [item for item in processes if int(item.get("swap_kib") or 0) > 0],
        key=lambda item: int(item.get("swap_kib") or 0),
        reverse=True,
    )[:top]
    top_oom = sorted(processes, key=lambda item: int(item.get("oom_score") or 0), reverse=True)[:top]
    podman_index = podman_index_port()
    cgroup_swap = cgroup_swap_snapshot(
        processes,
        top=top,
        podman_index=podman_index,
        cgroup_root=cgroup_root,
        protected_roles=protected_roles,
    )
    cgroup_memory = cgroup_memory_snapshot(
        processes,
        top=top,
        podman_index=podman_index,
        cgroup_root=cgroup_root,
        protected_roles=protected_roles,
    )
    return {
        "ok": True,
        "capture": {
            "source": "/proc plus smaps_rollup for largest RSS candidates",
            "facts_only": True,
            "top_limit": top,
            "smaps_rollup_enabled": bool(smaps),
            "smaps_rollup_read": smaps_read,
            "smaps_rollup_missing": smaps_missing,
        },
        "summary": {
            "processes": len(processes),
            "inaccessible_or_exited": inaccessible,
            "rss_total_kib": sum(int(item.get("vmrss_kib") or 0) for item in processes),
            "top_pss_total_kib": sum(int(item.get("pss_kib") or 0) for item in top_pss),
            "top_swap_total_kib": sum(int(item.get("swap_kib") or 0) for item in top_swap),
            "top_cgroup_memory_total_kib": cgroup_memory.get("top_memory_total_kib"),
            "top_cgroup_swap_total_kib": cgroup_swap.get("top_swap_total_kib"),
            "cgroup_memory_read": cgroup_memory.get("cgroups_read"),
            "cgroup_swap_read": cgroup_swap.get("cgroups_read"),
            "podman_containers_indexed": podman_index.get("containers"),
            "podman_index_error": podman_index.get("error"),
            "codex_thread_processes_identified": sum(
                1
                for item in processes
                if isinstance(item.get("owner_identity"), dict) and item["owner_identity"].get("stable_id")
            ),
            "codex_thread_processes_ambiguous": sum(
                1
                for item in processes
                if isinstance(item.get("owner_identity"), dict) and item["owner_identity"].get("ambiguous")
            ),
            "ai_runtime_processes": sum(1 for item in processes if item.get("workload_hint") == "ai_runtime"),
            "persistent_model_processes": sum(1 for item in processes if item.get("capability_role") == "persistent_model"),
            "persistent_ai_service_processes": sum(1 for item in processes if item.get("capability_role") == "persistent_ai_service"),
            "operator_dictation_processes": sum(1 for item in processes if item.get("capability_role") == "operator_dictation"),
            "protected_capability_processes": sum(1 for item in processes if item.get("capability_role") in protected_roles),
            "persistent_model_swap_kib": sum(int(item.get("swap_kib") or 0) for item in processes if item.get("capability_role") == "persistent_model"),
            "persistent_ai_service_swap_kib": sum(int(item.get("swap_kib") or 0) for item in processes if item.get("capability_role") == "persistent_ai_service"),
            "development_processes": sum(1 for item in processes if item.get("workload_hint") == "development"),
            "browser_processes": sum(1 for item in processes if item.get("workload_hint") == "browser"),
            "game_processes": sum(1 for item in processes if item.get("workload_hint") == "game"),
            "game_platform_processes": sum(1 for item in processes if item.get("workload_hint") == "game_platform"),
        },
        "top": {
            "rss": top_rss,
            "pss": top_pss,
            "swap": top_swap,
            "cgroup_memory": cgroup_memory.get("top"),
            "cgroup_swap": cgroup_swap.get("top"),
            "oom_score": top_oom,
        },
        "policy": {
            "facts_only": True,
            "do_not_kill_from_this_result": True,
            "pss_is_preferred_for_shared_memory": True,
        },
    }


def control_value(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    parsed: int | None
    if not text or text.lower() in {"max", "infinity", "[not set]", "none"}:
        parsed = None
    else:
        try:
            parsed = int(text)
        except ValueError:
            parsed = None
    return {
        "raw": text or None,
        "bytes": parsed,
        "mib": _bytes_to_mib(parsed) if parsed is not None else None,
        "unbounded": parsed is None and text.lower() in {"max", "infinity"},
    }


def cgroup_file_snapshot(
    control_group: str | None,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    memory_control_value: ControlValuePort = control_value,
) -> dict[str, Any]:
    if not control_group:
        return {"exists": False, "reason": "missing_control_group"}
    path = cgroup_root / control_group.lstrip("/")
    data: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return data
    controls: dict[str, Any] = {}
    for key in ("memory.current", "memory.swap.current", "memory.min", "memory.low", "memory.high", "memory.max", "memory.swap.max"):
        raw = _read_text(path / key)
        controls[key.replace(".", "_")] = memory_control_value(raw)
    events = parse_key_value_file(path / "memory.events")
    stat = parse_key_value_file(path / "memory.stat")
    selected_stat_keys = {
        "anon",
        "file",
        "kernel",
        "kernel_stack",
        "pagetables",
        "shmem",
        "inactive_anon",
        "active_anon",
        "workingset_refault_anon",
        "workingset_refault_file",
        "workingset_activate_anon",
        "workingset_activate_file",
        "pgfault",
        "pgmajfault",
        "swapcached",
    }
    pids: list[int] = []
    procs_text = _read_text(path / "cgroup.procs")
    if procs_text:
        for line in procs_text.splitlines():
            try:
                pids.append(int(line.strip()))
            except ValueError:
                pass
    data.update(
        {
            "controls": controls,
            "events": events,
            "stat": {key: value for key, value in stat.items() if key in selected_stat_keys},
            "pressure": parse_pressure_file(path / "memory.pressure"),
            "pids": pids[:64],
            "pid_count": len(pids),
        }
    )
    return data


def residency_service_rollup(
    pids: list[int],
    max_pids: int = 16,
    *,
    process_info: ProcessInfoPort,
    process_rollup_port: Callable[[int], dict[str, Any]],
) -> dict[str, Any]:
    rollups: list[dict[str, Any]] = []
    totals = {
        "rss_kib": 0,
        "pss_kib": 0,
        "swap_kib": 0,
        "swap_pss_kib": 0,
        "private_dirty_kib": 0,
    }
    for pid in pids[:max_pids]:
        info = process_info(pid)
        if info is None:
            continue
        rollup = process_rollup_port(pid)
        if rollup.get("available"):
            for key in totals:
                totals[key] += int(rollup.get(key) or 0)
        rollups.append(
            {
                "pid": pid,
                "name": info.get("name"),
                "workload_hint": info.get("workload_hint"),
                "capability_role": info.get("capability_role"),
                "rss_mib": _kib_to_mib(int(rollup.get("rss_kib") or info.get("vmrss_kib") or 0)),
                "pss_mib": _kib_to_mib(int(rollup.get("pss_kib") or 0)),
                "swap_mib": _kib_to_mib(int(rollup.get("swap_kib") or 0)),
                "cmdline_preview": str(info.get("cmdline") or "")[:180],
            }
        )
    return {
        "sampled_pids": len(rollups),
        "max_pids": max_pids,
        "totals": {
            "rss_mib": _kib_to_mib(totals["rss_kib"]),
            "pss_mib": _kib_to_mib(totals["pss_kib"]),
            "swap_mib": _kib_to_mib(totals["swap_kib"]),
            "swap_pss_mib": _kib_to_mib(totals["swap_pss_kib"]),
            "private_dirty_mib": _kib_to_mib(totals["private_dirty_kib"]),
        },
        "processes": rollups,
    }


def residency_service_status(
    service: dict[str, Any],
    residency_policy: dict[str, Any],
    *,
    systemd_unit_properties: SystemdPropertiesPort,
    process_info: ProcessInfoPort,
    process_rollup_port: Callable[[int], dict[str, Any]],
    cgroup_file_snapshot_port: Callable[[str | None], dict[str, Any]],
    memory_control_value: ControlValuePort = control_value,
) -> dict[str, Any]:
    unit = str(service.get("unit") or "")
    scope = str(service.get("scope") or "user")
    properties = [
        "Id",
        "ActiveState",
        "SubState",
        "MainPID",
        "ControlGroup",
        "Slice",
        "MemoryCurrent",
        "MemoryPeak",
        "MemorySwapCurrent",
        "MemoryMin",
        "MemoryLow",
        "MemoryHigh",
        "MemoryMax",
        "MemorySwapMax",
        "CPUWeight",
        "IOWeight",
    ]
    shown = systemd_unit_properties(unit, properties, scope == "user", 2.0)
    props = shown.get("properties", {}) if isinstance(shown.get("properties"), dict) else {}
    control_group = props.get("ControlGroup")
    cgroup = cgroup_file_snapshot_port(control_group)
    pids = list(cgroup.get("pids") or []) if isinstance(cgroup.get("pids"), list) else []
    try:
        main_pid = int(props.get("MainPID") or 0)
    except ValueError:
        main_pid = 0
    if main_pid > 0 and main_pid not in pids:
        pids.insert(0, main_pid)
    rollup = residency_service_rollup(
        pids,
        process_info=process_info,
        process_rollup_port=process_rollup_port,
    )

    thresholds = residency_policy.get("thresholds", {}) if isinstance(residency_policy.get("thresholds"), dict) else {}
    service_class = str(service.get("class") or "warm_resident")
    protected_swap_warn_mib = float(thresholds.get("protected_swap_warn_mib", 512))
    if service_class == "hot_interactive":
        protected_swap_warn_mib = float(thresholds.get("hot_interactive_swap_warn_mib", protected_swap_warn_mib))
    swap_to_pss_ratio_warn = float(thresholds.get("swap_to_pss_ratio_warn", 4.0))

    controls = cgroup.get("controls", {}) if isinstance(cgroup.get("controls"), dict) else {}
    memory_low_mib = nested_get(controls, ["memory_low", "mib"])
    memory_high_raw = nested_get(controls, ["memory_high", "raw"])
    memory_high_mib = nested_get(controls, ["memory_high", "mib"])
    memory_swap_max_raw = nested_get(controls, ["memory_swap_max", "raw"])
    cgroup_swap_mib = nested_get(controls, ["memory_swap_current", "mib"])
    pss_mib = nested_get(rollup, ["totals", "pss_mib"])
    process_swap_mib = nested_get(rollup, ["totals", "swap_mib"])
    swap_to_pss_ratio = _safe_ratio(float(cgroup_swap_mib or 0.0), float(pss_mib or 0.0), 2) if pss_mib else None

    issues: list[dict[str, Any]] = []
    active = props.get("ActiveState") == "active"
    if bool(service.get("protected", True)) and active and not memory_low_mib:
        issues.append(
            {
                "level": "warn",
                "code": "missing_memory_low",
                "message": "protected resident service has no cgroup MemoryLow protection",
            }
        )
    if bool(service.get("protected", True)) and active and str(memory_high_raw or "").lower() in {"max", "infinity", ""}:
        issues.append(
            {
                "level": "info",
                "code": "unbounded_memory_high",
                "message": "service has no soft MemoryHigh bound; use only after measuring peaks",
            }
        )
    if bool(service.get("protected", True)) and active and str(memory_swap_max_raw or "").lower() in {"max", "infinity", ""}:
        issues.append(
            {
                "level": "info",
                "code": "unbounded_memory_swap",
                "message": "service swap is unbounded; do not cap live high-swap services until restart/warmup measurement",
            }
        )
    if cgroup_swap_mib is not None and float(cgroup_swap_mib) >= protected_swap_warn_mib:
        issues.append(
            {
                "level": "warn",
                "code": "high_cgroup_swap",
                "message": "protected service has high cgroup swap charge",
                "threshold_mib": protected_swap_warn_mib,
            }
        )
    if swap_to_pss_ratio is not None and swap_to_pss_ratio >= swap_to_pss_ratio_warn:
        issues.append(
            {
                "level": "warn",
                "code": "cold_resident_pages",
                "message": "cgroup swap is high compared with sampled process PSS; hot-path warmup or MemoryLow pilot should be measured",
                "threshold_ratio": swap_to_pss_ratio_warn,
            }
        )

    class_policy = {}
    classes = residency_policy.get("classes", {}) if isinstance(residency_policy.get("classes"), dict) else {}
    if isinstance(classes.get(service_class), dict):
        class_policy = classes[service_class]
    runtime_pilot = class_policy.get("runtime_pilot", {}) if isinstance(class_policy.get("runtime_pilot"), dict) else {}
    target_memory_low_mib = _safe_float(runtime_pilot.get("memory_low_mib"), None)
    target_memory_high_mib = _safe_float(runtime_pilot.get("memory_high_mib"), None)
    pilot_low_active = bool(
        active
        and target_memory_low_mib is not None
        and float(memory_low_mib or 0.0) >= float(target_memory_low_mib)
    )
    pilot_high_active = bool(
        active
        and target_memory_high_mib is not None
        and memory_high_mib is not None
        and float(memory_high_mib) <= float(target_memory_high_mib)
    )
    runtime_pilot_active = pilot_low_active and pilot_high_active

    return {
        "unit": unit,
        "scope": scope,
        "class": service_class,
        "capability": service.get("capability"),
        "protected": bool(service.get("protected", True)),
        "reason": service.get("reason"),
        "systemd": {
            "ok": shown.get("ok"),
            "active_state": props.get("ActiveState"),
            "sub_state": props.get("SubState"),
            "main_pid": main_pid,
            "slice": props.get("Slice"),
            "control_group": control_group,
            "cpu_weight": props.get("CPUWeight"),
            "io_weight": props.get("IOWeight"),
            "error": shown.get("error"),
        },
        "controls": {
            "memory_current": memory_control_value(props.get("MemoryCurrent")),
            "memory_peak": memory_control_value(props.get("MemoryPeak")),
            "memory_swap_current": memory_control_value(props.get("MemorySwapCurrent")),
            "memory_min": memory_control_value(props.get("MemoryMin")),
            "memory_low": memory_control_value(props.get("MemoryLow")),
            "memory_high": memory_control_value(props.get("MemoryHigh")),
            "memory_max": memory_control_value(props.get("MemoryMax")),
            "memory_swap_max": memory_control_value(props.get("MemorySwapMax")),
        },
        "cgroup": cgroup,
        "process_rollup": rollup,
        "derived": {
            "cgroup_swap_mib": cgroup_swap_mib,
            "sampled_process_swap_mib": process_swap_mib,
            "sampled_process_pss_mib": pss_mib,
            "cgroup_swap_to_sampled_pss_ratio": swap_to_pss_ratio,
        },
        "target": {
            "slice": class_policy.get("target_slice"),
            "runtime_pilot": runtime_pilot,
            "runtime_pilot_status": "active_runtime_only" if runtime_pilot_active else "candidate_runtime_only_after_operator_approval",
            "runtime_pilot_active": runtime_pilot_active,
            "runtime_pilot_controls": {
                "memory_low_active": pilot_low_active,
                "memory_high_active": pilot_high_active,
                "target_memory_low_mib": target_memory_low_mib,
                "target_memory_high_mib": target_memory_high_mib,
            },
            "runtime_apply_default": False,
        },
        "issues": issues,
    }
