from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Sequence
import urllib.error
import urllib.request

from . import process_adapters


CommandExistsPort = Callable[[str], bool]
CommandRunnerPort = Callable[[Sequence[str], float], dict[str, Any]]
HttpJsonPort = Callable[[str, float, int, str], dict[str, Any]]
HttpStatusPort = Callable[[str, float, int, str], dict[str, Any]]
MonotonicPort = Callable[[], float]
SleepPort = Callable[[float], None]
NowIsoPort = Callable[[], str]
PidPort = Callable[[], int]
ProcessInfoPort = Callable[[int], dict[str, Any] | None]
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
ParseTimePort = Callable[[Any], dt.datetime | None]
DateTimePort = Callable[[], dt.datetime]


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
    root = Path(str(paths_refs.get("root", ""))) if paths_refs.get("root") else None
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
            "daily_glob": str(root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl") if root else None,
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
    podman_index_port: Callable[[], dict[str, Any]] = podman_container_index,
    protected_roles: set[str] | frozenset[str],
) -> dict[str, Any]:
    top = max(5, min(int(top), 200))
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


def orchestrate_cgroup_entry(
    item: dict[str, Any],
    *,
    protected_roles: set[str] | frozenset[str],
) -> dict[str, Any]:
    cgroup = str(item.get("cgroup") or "")
    unit = item.get("unit") or cgroup_unit_hint(cgroup)
    names = item.get("names") if isinstance(item.get("names"), list) else []
    label = str(unit or (names[0] if names else "") or (cgroup.rsplit("/", 1)[-1] if cgroup else "unknown"))
    role = str(item.get("capability_role") or "none")
    workload = str(item.get("workload_hint") or "normal")
    protected = bool(item.get("protected")) or role in protected_roles or workload == "game"
    podman = item.get("podman") if isinstance(item.get("podman"), dict) else {}
    container_name = item.get("container_name") or podman.get("name")
    compose_service = item.get("compose_service") or podman.get("compose_service")
    return {
        "label": label,
        "cgroup": cgroup,
        "unit": unit,
        "container_name": container_name,
        "compose_service": compose_service,
        "podman_id": podman.get("id"),
        "pids": item.get("pids"),
        "names": names,
        "workload_hint": workload,
        "capability_role": role,
        "protected": protected,
        "route": item.get("route") or ("route_new_work_around_protected_capability" if protected else "operator_review_candidate"),
        "memory_current_mib": item.get("memory_current_mib", _kib_to_mib(item.get("memory_current_kib"))),
        "swap_current_mib": item.get("swap_current_mib", _kib_to_mib(item.get("swap_current_kib"))),
        "process_pss_rollup_mib": item.get("process_pss_rollup_mib"),
        "process_swap_rollup_mib": item.get("process_swap_rollup_mib"),
    }


def is_rerank_api_target(target: dict[str, Any]) -> bool:
    if not isinstance(target, dict):
        return False
    names = " ".join(str(name or "") for name in target.get("names", []) if isinstance(target.get("names"), list))
    haystack = " ".join(
        str(value or "")
        for value in (
            target.get("label"),
            target.get("unit"),
            target.get("container_name"),
            target.get("compose_service"),
            target.get("cgroup"),
            names,
        )
    ).lower()
    return "rerank-api" in haystack


def is_ovms_target(target: dict[str, Any]) -> bool:
    if not isinstance(target, dict):
        return False
    names = " ".join(str(name or "") for name in target.get("names", []) if isinstance(target.get("names"), list))
    haystack = " ".join(
        str(value or "")
        for value in (
            target.get("label"),
            target.get("unit"),
            target.get("container_name"),
            target.get("compose_service"),
            target.get("cgroup"),
            names,
        )
    ).lower()
    return (
        "ovms" in haystack
        or "openvino/model_server" in haystack
        or "openvino_model_server" in haystack
        or "openvino-model-server" in haystack
    )


def orchestrate_action_candidates(
    cgroup_memory_top: list[dict[str, Any]],
    cgroup_swap_top: list[dict[str, Any]],
    *,
    protected_roles: set[str] | frozenset[str],
    limit: int = 12,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source, items in (("memory", cgroup_memory_top), ("swap", cgroup_swap_top)):
        for raw in items:
            if not isinstance(raw, dict):
                continue
            entry = orchestrate_cgroup_entry(raw, protected_roles=protected_roles)
            key = str(entry.get("cgroup") or entry.get("label") or "")
            if not key:
                continue
            current = merged.setdefault(key, entry)
            current.setdefault("sources", [])
            current["sources"].append(source)
            for field in ("memory_current_mib", "swap_current_mib", "process_pss_rollup_mib", "process_swap_rollup_mib"):
                value = _safe_float(entry.get(field), None)
                if value is not None and value > float(current.get(field) or 0.0):
                    current[field] = round(value, 1)
            current["protected"] = bool(current.get("protected")) or bool(entry.get("protected"))
            if entry.get("capability_role") != "none":
                current["capability_role"] = entry.get("capability_role")
            if entry.get("workload_hint") != "normal":
                current["workload_hint"] = entry.get("workload_hint")

    candidates: list[dict[str, Any]] = []
    for entry in merged.values():
        mem_mib = _safe_float(entry.get("memory_current_mib"), 0.0) or 0.0
        swap_mib = _safe_float(entry.get("swap_current_mib"), 0.0) or 0.0
        role = str(entry.get("capability_role") or "none")
        workload = str(entry.get("workload_hint") or "normal")
        protected = bool(entry.get("protected"))
        if mem_mib < 256 and swap_mib < 512:
            continue
        if is_rerank_api_target(entry):
            entry["capability_role"] = "persistent_model"
            entry["workload_hint"] = "ai_runtime"
            entry["protected"] = True
            entry["route"] = "route_new_work_around_protected_capability"
            role = "persistent_model"
            workload = "ai_runtime"
            protected = True
            kind = "managed_model_dehydrate_rehydrate_candidate"
            reason = "rerank-api OpenVINO model runtime has material RAM and can use its registered idle unload/recycle route"
        elif role in {"persistent_ai_service", "operator_dictation"}:
            kind = "protected_capability_residency_candidate"
            reason = "operator-facing warm capability is material in RAM/zram and needs idle-aware handling"
        elif role == "persistent_model" or (workload == "ai_runtime" and mem_mib >= 1024):
            kind = "managed_model_dehydrate_rehydrate_candidate"
            reason = "persistent model runtime has material RAM and/or zram footprint"
        elif workload in {"development", "browser", "game_platform"}:
            kind = "operator_session_app_review"
            reason = "interactive session workload has material footprint; only operator can decide tradeoff"
        elif protected:
            kind = "protected_workload_review"
            reason = "protected workload must be routed around, not mutated automatically"
        else:
            kind = "observe_or_gate_new_work"
            reason = "workload is material but not enough evidence for a safe mutation route"
        priority_score = max(mem_mib, swap_mib * 0.75)
        candidates.append(
            {
                "id": "candidate_" + re.sub(r"[^a-z0-9]+", "_", str(entry.get("label") or "unknown").lower()).strip("_")[:80],
                "kind": kind,
                "status": "plan_only_requires_operator_confirmation",
                "priority_score": round(priority_score, 1),
                "reason": reason,
                "target": entry,
                "possible_effect": {
                    "ram_reduction_requires_process_restart": mem_mib >= 512,
                    "zram_reduction_requires_restart_or_page_reclaim": swap_mib >= 512,
                    "cold_start_or_latency_risk": protected or workload == "ai_runtime",
                },
                "guards": [
                    "must_be_idle_or_explicit_timeout",
                    "one_heavy_service_at_a_time",
                    "capture_before_after_memory_orchestrate_plan",
                    "verify_health_and_latency_after_rehydrate",
                ],
                "apply_from_this_command": False,
            }
        )
    candidates.sort(key=lambda item: float(item.get("priority_score") or 0.0), reverse=True)
    return candidates[: max(3, min(int(limit), 40))]


def orchestrate_find_candidate(plan: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    wanted = str(candidate_id or "").strip()
    if not wanted:
        return None
    for item in plan.get("candidates", []) if isinstance(plan.get("candidates"), list) else []:
        if isinstance(item, dict) and str(item.get("id") or "") == wanted:
            return item
    return None


def confirmation_artifact_status(
    candidate_id: str,
    *,
    confirm_latest_path: Path,
    load_json_document: LoadJsonDocumentPort,
    parse_time: ParseTimePort,
    now: DateTimePort,
) -> dict[str, Any]:
    data, error = load_json_document(confirm_latest_path)
    if not isinstance(data, dict):
        return {
            "available": False,
            "status": "missing",
            "reason": error or "latest confirmation artifact missing",
            "path": str(confirm_latest_path),
        }
    requested = data.get("requested", {}) if isinstance(data.get("requested"), dict) else {}
    contract = data.get("confirmation_contract", {}) if isinstance(data.get("confirmation_contract"), dict) else {}
    subject = contract.get("subject", {}) if isinstance(contract.get("subject"), dict) else {}
    artifact_candidate = str(requested.get("candidate_id") or subject.get("candidate_id") or "")
    expires_at = parse_time(contract.get("expires_at"))
    expired = bool(expires_at and expires_at < now())
    candidate_match = artifact_candidate == str(candidate_id or "")
    checks = data.get("checks", []) if isinstance(data.get("checks"), list) else []
    blockers = [
        item.get("id")
        for item in checks
        if isinstance(item, dict) and str(item.get("status") or "").startswith("block")
    ]
    ready = bool(data.get("ok")) and str(data.get("status") or "") == "contract_ready" and candidate_match and not expired and not blockers
    return {
        "available": True,
        "ready": ready,
        "status": data.get("status"),
        "decision": data.get("decision"),
        "path": str(confirm_latest_path),
        "generated_at": data.get("generated_at"),
        "expires_at": contract.get("expires_at"),
        "expired": expired,
        "candidate_match": candidate_match,
        "candidate_id": artifact_candidate,
        "operator": nested_get(contract, ["operator", "name"]),
        "reason": contract.get("reason"),
        "blockers": blockers,
        "target_snapshot_digest": contract.get("current_target_snapshot_digest"),
        "effective_confirmation": bool(nested_get(data, ["policy", "effective_confirmation"])),
        "grant_valid_for_confirm": bool(nested_get(data, ["policy", "grant_valid_for_confirm"])),
    }


def confirmation_checks(
    candidate: dict[str, Any],
    idle_gate: dict[str, Any],
    health: dict[str, Any],
    operator: str,
    reason: str,
    acknowledge_protected: bool,
) -> list[dict[str, Any]]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    protected = bool(target.get("protected"))
    operator_clean = str(operator or "").strip()
    reason_clean = str(reason or "").strip()
    health_status = str(health.get("status") or "missing")
    return [
        {
            "id": "candidate_known",
            "status": "pass",
            "required": True,
            "reason": "Candidate was selected from a fresh memory orchestrate plan.",
            "evidence": {"candidate_id": candidate.get("id")},
        },
        {
            "id": "protected_candidate_identified",
            "status": "pass" if protected else "warn",
            "required": False,
            "reason": "Confirmation contract is mainly needed for protected capabilities.",
            "evidence": {"protected": protected, "capability_role": target.get("capability_role")},
        },
        {
            "id": "operator_identity_declared",
            "status": "pass" if operator_clean else "block_confirm",
            "required": True,
            "reason": "The contract must state who is requesting the protected lifecycle operation.",
            "evidence": {"operator": operator_clean or None},
        },
        {
            "id": "reason_declared",
            "status": "pass" if len(reason_clean) >= 8 else "block_confirm",
            "required": True,
            "reason": "The contract must state why dehydration/rehydration is being considered.",
            "evidence": {"reason_chars": len(reason_clean)},
        },
        {
            "id": "protected_acknowledgement",
            "status": "pass" if (acknowledge_protected or not protected) else "block_confirm",
            "required": protected,
            "reason": "Protected candidates require an explicit acknowledgement that the route may cause cold-start or latency risk.",
            "evidence": {"acknowledge_protected": bool(acknowledge_protected), "protected": protected},
        },
        {
            "id": "idle_gate_passed",
            "status": "pass" if bool(idle_gate.get("registered")) and bool(idle_gate.get("idle")) else "block_confirm",
            "required": True,
            "reason": idle_gate.get("reason") or "Target-specific idle gate must pass before protected lifecycle work.",
            "evidence": {
                "registered": bool(idle_gate.get("registered")),
                "idle": bool(idle_gate.get("idle")),
                "status": idle_gate.get("status"),
                "confidence": idle_gate.get("confidence"),
            },
        },
        {
            "id": "health_probe_route_registered",
            "status": "pass" if health_status == "available" else ("warn" if health_status == "partial" else "block_confirm"),
            "required": True,
            "reason": health.get("reason"),
            "evidence": {"status": health_status, "command": health.get("command")},
        },
        {
            "id": "before_after_probe_contract_declared",
            "status": "pass",
            "required": True,
            "reason": "Confirmed lifecycle work must be bracketed by pre/post health and memory evidence.",
            "evidence": {
                "before": ["memory orchestrate plan", "memory orchestrate idle", "health route"],
                "after": ["health route", "memory orchestrate plan"],
            },
        },
        {
            "id": "rollback_rehydrate_contract_declared",
            "status": "pass",
            "required": True,
            "reason": "The future route is rehydrate-and-prove-health, not disable-and-forget.",
            "evidence": {"required": ["executor return code", "target alive", "health probe", "memory plan compare"]},
        },
        {
            "id": "no_mutation_from_confirmation_contract",
            "status": "pass",
            "required": True,
            "reason": "This confirmation contract is dry-run evidence only and cannot mutate live services.",
            "evidence": {"effective_confirmation": False, "grant_valid_for_confirm": False},
        },
    ]


def target_identity_payload(candidate: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    return {
        "candidate_id": candidate.get("id"),
        "kind": candidate.get("kind"),
        "target": {
            "label": target.get("label"),
            "cgroup": target.get("cgroup"),
            "unit": target.get("unit"),
            "container_name": target.get("container_name"),
            "compose_service": target.get("compose_service"),
            "capability_role": target.get("capability_role"),
            "workload_hint": target.get("workload_hint"),
        },
        "podman": {
            "id": nested_get(snapshot, ["podman", "container", "id"]),
            "name": nested_get(snapshot, ["podman", "container", "name"]),
        },
        "systemd": {
            "unit": nested_get(snapshot, ["systemd", "unit"]),
            "scope": nested_get(snapshot, ["systemd", "scope"]),
            "control_group": nested_get(snapshot, ["systemd", "control_group"]),
        },
    }


def target_identity_digest(candidate: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return _stable_hash_json(target_identity_payload(candidate, snapshot))


def confirmation_contract(
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    idle_gate: dict[str, Any],
    health: dict[str, Any],
    future_executor: dict[str, Any],
    operator: str,
    reason: str,
    window_sec: int,
    *,
    now: DateTimePort,
) -> dict[str, Any]:
    current = now()
    window_sec = max(60, min(int(window_sec or 300), 3600))
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    return {
        "subject": {
            "candidate_id": candidate.get("id"),
            "kind": candidate.get("kind"),
            "target_label": target.get("label"),
            "target_cgroup": target.get("cgroup"),
            "unit": target.get("unit"),
            "protected": bool(target.get("protected")),
            "capability_role": target.get("capability_role"),
            "workload_hint": target.get("workload_hint"),
        },
        "operator": {
            "name": str(operator or "").strip() or None,
            "source": "cli_flag",
            "confirmed_at": current.isoformat(timespec="seconds"),
        },
        "reason": str(reason or "").strip() or None,
        "expires_at": (current + dt.timedelta(seconds=window_sec)).isoformat(timespec="seconds"),
        "window_sec": window_sec,
        "required_before": [
            {
                "id": "fresh_memory_orchestrate_plan",
                "command": "abyss-machine memory orchestrate plan --json",
                "evidence": "same candidate id remains present and target is still alive",
            },
            {
                "id": "idle_gate",
                "command": "abyss-machine memory orchestrate idle --candidate ID --json",
                "evidence": {
                    "status": idle_gate.get("status"),
                    "idle": bool(idle_gate.get("idle")),
                    "confidence": idle_gate.get("confidence"),
                },
            },
            {
                "id": "pre_health_probe",
                "command": health.get("command"),
                "evidence": health.get("kind"),
            },
        ],
        "future_executor": future_executor,
        "required_after": [
            {
                "id": "post_health_probe",
                "command": health.get("command"),
                "evidence": "same route succeeds after rehydrate",
            },
            {
                "id": "post_memory_plan_compare",
                "command": "abyss-machine memory orchestrate plan --json",
                "evidence": "RAM/zram/cgroup deltas captured after rehydrate",
            },
            {
                "id": "target_alive_after_rehydrate",
                "evidence": "cgroup/systemd/podman target exists and health route is available",
            },
        ],
        "rollback_or_rehydrate_proof": {
            "required": True,
            "proof_items": [
                "executor return code",
                "target alive",
                "health probe success",
                "memory plan after-state",
                "no new PSI stall",
            ],
        },
        "current_target_snapshot_digest": target_identity_digest(candidate, snapshot),
        "current_target_snapshot_digest_basis": "stable target label/cgroup/unit plus podman container identity; excludes dynamic memory counters and PID list",
        "invariants": [
            "do not stop or restart protected capability without explicit operator route",
            "do not disable, demote, throttle, re-affinitize, cap, swapoff, drop caches, tune sysctl, or reconfigure zram",
            "one heavy model/service lifecycle operation at a time",
            "confirmed apply must re-check idle and health immediately before mutation",
        ],
    }


def health_route(candidate: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    unit = str(target.get("unit") or "")
    role = str(target.get("capability_role") or "")
    kind = str(candidate.get("kind") or "")
    names = " ".join(str(name or "") for name in target.get("names", []) if isinstance(target.get("names"), list))
    haystack = f"{unit} {role} {kind} {names}".lower()
    if is_rerank_api_target(target):
        endpoint = podman_http_endpoint(snapshot)
        command = None
        if endpoint.get("available"):
            command = f"curl -fsS {str(endpoint.get('base_url')).rstrip('/')}/health"
        return {
            "status": "available" if endpoint.get("available") else "missing",
            "kind": "rerank_api_probe",
            "command": command,
            "reason": "rerank-api health exposes loaded state and active request count for before/after recycle proof.",
        }
    if is_ovms_target(target):
        endpoint = podman_http_endpoint(snapshot)
        command = None
        if endpoint.get("available"):
            command = f"curl -fsS {str(endpoint.get('base_url')).rstrip('/')}/v2/health/ready"
        return {
            "status": "available" if endpoint.get("available") else "missing",
            "kind": "ovms_probe",
            "command": command,
            "reason": "OVMS live/ready health plus /v1/config model status expose enough before/after proof when combined with cgroup CPU idle gating.",
        }
    if "dictation" in haystack or "tts" in haystack:
        return {
            "status": "available",
            "kind": "protected_hotpath",
            "command": "abyss-machine memory hotpath-probe --json",
            "reason": "TTS/dictation health must be bracketed by the synthetic hot-path probe.",
        }
    if "gemma" in haystack or "llama" in haystack or role == "persistent_model":
        return {
            "status": "available",
            "kind": "resident_llm_probe",
            "command": "abyss-machine memory hotpath-probe --include-llm --llm-limit 4 --json",
            "reason": "Resident LLM model changes need before/after model micro evidence plus protected hot-path evidence.",
        }
    if nested_get(snapshot, ["podman", "container"]):
        return {
            "status": "partial",
            "kind": "container_state_probe",
            "command": "podman inspect CONTAINER_ID",
            "reason": "Container state is observable, but no workload-specific idle and latency probe is registered yet.",
        }
    return {
        "status": "missing",
        "kind": "unknown_target_probe",
        "command": None,
        "reason": "No target-specific health route is known for confirmed apply.",
    }


def future_executor(candidate: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    kind = str(candidate.get("kind") or "")
    unit = str(target.get("unit") or "")
    podman_id = podman_id_from_target(target)
    if kind == "managed_model_dehydrate_rehydrate_candidate" and is_rerank_api_target(target):
        endpoint = podman_http_endpoint(snapshot)
        base_url = str(endpoint.get("base_url") or "").rstrip("/")
        if endpoint.get("available") and base_url:
            return {
                "enabled": True,
                "kind": "rerank_api_idle_unload",
                "container": nested_get(snapshot, ["podman", "container", "name"]) or target.get("container_name") or (podman_id[:12] if podman_id else None),
                "command_template": ["http_post_json", f"{base_url}/admin/unload?exit_process=true"],
                "reason": "Confirmed live apply may ask rerank-api to unload and recycle its process; container restart policy returns the lightweight API.",
            }
        return {
            "enabled": False,
            "kind": "rerank_api_idle_unload",
            "container": target.get("container_name") or (podman_id[:12] if podman_id else None),
            "command_template": None,
            "reason": "rerank-api target detected, but no localhost HTTP endpoint is available from podman inspect.",
        }
    if kind == "protected_capability_residency_candidate":
        return {
            "enabled": False,
            "kind": "protected_capability_manual_route",
            "reason": "Protected TTS/dictation-style capabilities need an explicit operator opt-in, idle gate, and before/after hot-path proof.",
            "command_template": None,
        }
    if kind == "managed_model_dehydrate_rehydrate_candidate" and unit.endswith(".service"):
        return {
            "enabled": False,
            "kind": "systemd_user_service_rehydrate",
            "unit": unit,
            "command_template": ["systemctl", "--user", "restart", unit],
            "reason": "Future confirmed apply may restart a managed model service only after idle and health guards pass.",
        }
    if kind == "managed_model_dehydrate_rehydrate_candidate" and podman_id:
        name = nested_get(snapshot, ["podman", "container", "name"])
        container_ref = str(name or podman_id[:12]).lstrip("/")
        return {
            "enabled": True,
            "kind": "podman_container_rehydrate",
            "container": container_ref,
            "command_template": ["podman", "restart", container_ref],
            "reason": "Confirmed live apply may restart this managed model container only after all idle, health, confirmation, and live acknowledgement guards pass.",
        }
    return {
        "enabled": False,
        "kind": "operator_review_only",
        "reason": "This target is not a managed-model executor candidate.",
        "command_template": None,
    }


def idle_gate_current_health(idle_gate: dict[str, Any]) -> dict[str, Any]:
    signals = idle_gate.get("signals") if isinstance(idle_gate.get("signals"), dict) else {}
    for key in ("rerank_http", "ovms_http", "llama_http"):
        health = nested_get(signals, [key, "health"])
        if isinstance(health, dict) and health:
            return health
    return {}


def guard_summary(guards: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for guard in guards:
        status = str(guard.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "counts": dict(sorted(counts.items())),
        "confirm_blockers": [guard.get("id") for guard in guards if str(guard.get("status") or "").startswith("block")],
        "warnings": [guard.get("id") for guard in guards if guard.get("status") == "warn"],
    }


def executor_preflight_checks(
    plan: dict[str, Any],
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    idle_gate: dict[str, Any],
    health: dict[str, Any],
    confirmation_status: dict[str, Any],
    future_executor_doc: dict[str, Any],
    lock_status: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}
    psi_some = _safe_float(summary.get("psi_some_avg10"), 0.0) or 0.0
    psi_full = _safe_float(summary.get("psi_full_avg10"), 0.0) or 0.0
    alive_count = int(nested_get(snapshot, ["pids", "alive_count"]) or 0)
    cgroup_exists = bool(nested_get(snapshot, ["cgroup", "exists"]))
    health_status = str(health.get("status") or "missing")
    current_digest = target_identity_digest(candidate, snapshot)
    contract_digest = str(confirmation_status.get("target_snapshot_digest") or "")
    current_health = idle_gate_current_health(idle_gate)
    current_health_ok = bool(current_health.get("ok")) if isinstance(current_health, dict) else health_status == "available"
    command_template = future_executor_doc.get("command_template") if isinstance(future_executor_doc.get("command_template"), list) else None
    return [
        {
            "id": "confirmation_contract_current",
            "status": "pass" if bool(confirmation_status.get("ready")) else "block_live_stage",
            "required": True,
            "reason": "A current, matching, non-expired confirmation contract must exist before executor preflight can proceed.",
            "evidence": {
                "available": confirmation_status.get("available"),
                "ready": confirmation_status.get("ready"),
                "expired": confirmation_status.get("expired"),
                "candidate_match": confirmation_status.get("candidate_match"),
                "expires_at": confirmation_status.get("expires_at"),
                "operator": confirmation_status.get("operator"),
            },
        },
        {
            "id": "confirmation_contract_non_grant",
            "status": "pass" if not confirmation_status.get("effective_confirmation") and not confirmation_status.get("grant_valid_for_confirm") else "block_live_stage",
            "required": True,
            "reason": "The current layer records confirmation evidence but still must not treat it as live mutation authority.",
            "evidence": {
                "effective_confirmation": confirmation_status.get("effective_confirmation"),
                "grant_valid_for_confirm": confirmation_status.get("grant_valid_for_confirm"),
            },
        },
        {
            "id": "target_identity_rechecked",
            "status": "pass" if contract_digest and contract_digest == current_digest else "block_live_stage",
            "required": True,
            "reason": "The target identity must match the confirmation contract immediately before any lifecycle executor.",
            "evidence": {
                "contract_digest": contract_digest or None,
                "current_digest": current_digest,
            },
        },
        {
            "id": "target_still_alive",
            "status": "pass" if alive_count > 0 or cgroup_exists else "block_live_stage",
            "required": True,
            "reason": "The target must still exist immediately before any lifecycle executor.",
            "evidence": {"alive_pids": alive_count, "cgroup_exists": cgroup_exists},
        },
        {
            "id": "idle_rechecked_immediately_before",
            "status": "pass" if bool(idle_gate.get("registered")) and bool(idle_gate.get("idle")) else "block_live_stage",
            "required": True,
            "reason": idle_gate.get("reason") or "Idle gate must pass immediately before any lifecycle executor.",
            "evidence": {
                "registered": idle_gate.get("registered"),
                "idle": idle_gate.get("idle"),
                "status": idle_gate.get("status"),
                "confidence": idle_gate.get("confidence"),
            },
        },
        {
            "id": "current_health_signal_rechecked",
            "status": "pass" if current_health_ok and health_status == "available" else "block_live_stage",
            "required": True,
            "reason": "The health route or embedded model health signal must be available immediately before mutation.",
            "evidence": {
                "health_route_status": health_status,
                "health_route_command": health.get("command"),
                "embedded_current_health": current_health if isinstance(current_health, dict) else None,
            },
        },
        {
            "id": "no_active_memory_stalls",
            "status": "pass" if psi_some <= 2.0 and psi_full <= 0.5 else "block_live_stage",
            "required": True,
            "reason": "Executor preflight must not proceed while PSI indicates active memory stalls.",
            "evidence": {"psi_some_avg10": psi_some, "psi_full_avg10": psi_full},
        },
        {
            "id": "one_heavy_service_lock_available",
            "status": "pass" if bool(lock_status.get("available")) else "block_live_stage",
            "required": True,
            "reason": "Future live executor must serialize heavy model/service lifecycle work.",
            "evidence": lock_status,
        },
        {
            "id": "executor_command_declared",
            "status": "pass" if command_template else "block_live_stage",
            "required": True,
            "reason": "The future executor command must be explicit and target-specific.",
            "evidence": {
                "kind": future_executor_doc.get("kind"),
                "command_template": command_template,
                "enabled": future_executor_doc.get("enabled"),
            },
        },
        {
            "id": "before_after_probe_contract_present",
            "status": "pass" if health.get("command") else "block_live_stage",
            "required": True,
            "reason": "Executor preflight requires before/after health and memory evidence routes.",
            "evidence": {
                "before": ["memory orchestrate plan", "memory orchestrate idle", health.get("command")],
                "after": [health.get("command"), "memory orchestrate plan"],
            },
        },
        {
            "id": "live_executor_stage_disabled",
            "status": "block_live_stage",
            "required": True,
            "reason": "This invocation stops at confirmed executor preflight unless the separate live executor interlock is explicitly requested.",
            "evidence": {
                "live_executor_supported": True,
                "requires_execute_live": True,
                "requires_acknowledge_live_restart": True,
                "existing_process_mutation": False,
                "live_command": "abyss-machine memory orchestrate apply --candidate ID --confirm --execute-live --acknowledge-live-restart --operator NAME --reason TEXT --json",
            },
        },
    ]


def apply_guard_rows(
    plan: dict[str, Any],
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    idle_gate: dict[str, Any],
    health: dict[str, Any],
    confirmation_status: dict[str, Any],
    dry_run: bool,
    confirm: bool,
) -> list[dict[str, Any]]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    summary = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}
    protected = bool(target.get("protected"))
    psi_some = _safe_float(summary.get("psi_some_avg10"), 0.0) or 0.0
    psi_full = _safe_float(summary.get("psi_full_avg10"), 0.0) or 0.0
    alive_count = int(nested_get(snapshot, ["pids", "alive_count"]) or 0)
    cgroup_exists = bool(nested_get(snapshot, ["cgroup", "exists"]))
    health_status = str(health.get("status") or "missing")
    idle_registered = bool(idle_gate.get("registered"))
    idle_status = str(idle_gate.get("status") or "not_registered")
    idle_now = bool(idle_gate.get("idle"))
    confirmation_ready = bool(confirmation_status.get("ready"))
    return [
        {
            "id": "dry_run_mode",
            "status": "pass" if (dry_run or confirm) else "block",
            "required": True,
            "reason": "Apply is dry-run by default; confirmed apply is still non-mutating unless the separate live executor interlock is requested.",
            "evidence": {"dry_run": dry_run, "confirm": confirm},
        },
        {
            "id": "candidate_known",
            "status": "pass",
            "required": True,
            "reason": "Candidate was selected from a fresh memory orchestrate plan.",
            "evidence": {"candidate_id": candidate.get("id")},
        },
        {
            "id": "target_still_alive",
            "status": "pass" if alive_count > 0 or cgroup_exists else "warn",
            "required": False,
            "reason": "The target should still exist before any confirmed lifecycle operation.",
            "evidence": {"alive_pids": alive_count, "cgroup_exists": cgroup_exists},
        },
        {
            "id": "no_active_memory_stalls",
            "status": "pass" if psi_some <= 2.0 and psi_full <= 0.5 else "block_confirm",
            "required": True,
            "reason": "Confirmed lifecycle changes should not start while PSI indicates active memory stalls.",
            "evidence": {"psi_some_avg10": psi_some, "psi_full_avg10": psi_full},
        },
        {
            "id": "idle_detection_registered",
            "status": "pass" if idle_registered else "block_confirm",
            "required": True,
            "reason": idle_gate.get("reason") or "Confirmed apply needs target-specific idle/in-flight detection.",
            "evidence": {
                "implemented": idle_registered,
                "status": idle_status,
                "confidence": idle_gate.get("confidence"),
            },
        },
        {
            "id": "target_idle_now",
            "status": "pass" if idle_registered and idle_now else "block_confirm",
            "required": True,
            "reason": "Confirmed apply may only proceed when the target-specific idle gate says the model is idle now.",
            "evidence": {
                "idle": idle_now,
                "status": idle_status,
                "confidence": idle_gate.get("confidence"),
            },
        },
        {
            "id": "health_probe_route_registered",
            "status": "pass" if health_status == "available" else ("warn" if health_status == "partial" else "block_confirm"),
            "required": True,
            "reason": health.get("reason"),
            "evidence": {"status": health_status, "command": health.get("command")},
        },
        {
            "id": "protected_capability_confirmation",
            "status": "pass" if (not protected or confirmation_ready) else "block_confirm",
            "required": protected,
            "reason": "Protected capabilities require an explicit, current confirmation contract before any future mutation.",
            "evidence": {
                "protected": protected,
                "capability_role": target.get("capability_role"),
                "confirmation_ready": confirmation_ready,
                "confirmation_status": confirmation_status.get("status"),
                "confirmation_operator": confirmation_status.get("operator"),
                "confirmation_expires_at": confirmation_status.get("expires_at"),
                "effective_confirmation": confirmation_status.get("effective_confirmation"),
                "grant_valid_for_confirm": confirmation_status.get("grant_valid_for_confirm"),
            },
        },
        {
            "id": "one_heavy_service_at_a_time",
            "status": "pass",
            "required": True,
            "reason": "A confirmed executor must serialize model/service lifecycle operations.",
            "evidence": {"planned": True},
        },
        {
            "id": "rollback_route_declared",
            "status": "pass",
            "required": True,
            "reason": "The future route is rehydrate-and-verify, not disable-and-forget.",
            "evidence": {"rollback_kind": "restart_or_rehydrate_then_hotpath_probe"},
        },
    ]


def apply_steps(
    candidate: dict[str, Any],
    health: dict[str, Any],
    idle_gate: dict[str, Any],
    future_executor_doc: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "id": "capture_fresh_plan",
            "status": "completed",
            "command": "abyss-machine memory orchestrate plan --json",
            "mutates_existing_processes": False,
        },
        {
            "order": 2,
            "id": "select_candidate",
            "status": "completed",
            "candidate_id": candidate.get("id"),
            "mutates_existing_processes": False,
        },
        {
            "order": 3,
            "id": "pre_hotpath_probe",
            "status": "available" if health.get("command") else "missing_for_confirm",
            "command": health.get("command"),
            "mutates_existing_processes": False,
        },
        {
            "order": 4,
            "id": "idle_gate",
            "status": idle_gate.get("status") or "not_registered",
            "idle": bool(idle_gate.get("idle")),
            "confidence": idle_gate.get("confidence"),
            "mutates_existing_processes": False,
        },
        {
            "order": 5,
            "id": "dehydrate_rehydrate",
            "status": "not_executed_dry_run",
            "future_executor": future_executor_doc,
            "mutates_existing_processes": False,
        },
        {
            "order": 6,
            "id": "post_hotpath_probe",
            "status": "available" if health.get("command") else "missing_for_confirm",
            "command": health.get("command"),
            "mutates_existing_processes": False,
        },
        {
            "order": 7,
            "id": "post_memory_plan_compare",
            "status": "planned_for_confirmed_apply",
            "command": "abyss-machine memory orchestrate plan --json",
            "mutates_existing_processes": False,
        },
    ]


def live_authorization_checks(
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    idle_gate: dict[str, Any],
    health: dict[str, Any],
    future_executor_doc: dict[str, Any],
    executor_preflight: dict[str, Any] | None,
    confirm: bool,
    execute_live: bool,
    acknowledge_live_restart: bool,
    operator: str,
    reason: str,
) -> list[dict[str, Any]]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    kind = str(candidate.get("kind") or "")
    role = str(target.get("capability_role") or "")
    operator_clean = str(operator or "").strip()
    reason_clean = str(reason or "").strip()
    executor_kind = str(future_executor_doc.get("kind") or "")
    command_template = future_executor_doc.get("command_template") if isinstance(future_executor_doc.get("command_template"), list) else None
    names = " ".join(str(name or "") for name in target.get("names", []) if isinstance(target.get("names"), list))
    haystack = f"{target.get('label') or ''} {target.get('unit') or ''} {target.get('cgroup') or ''} {role} {kind} {names}".lower()
    rerank_api = is_rerank_api_target(target)
    protected_hotpath = "tts" in haystack or "dictation" in haystack
    preflight_ready = bool((executor_preflight or {}).get("preflight_ready_except_live_stage"))
    preflight_live_only = bool((executor_preflight or {}).get("blocked_only_by_live_stage_disabled"))
    podman_running = bool(nested_get(snapshot, ["podman", "container", "running"]))
    idle_ok = bool(idle_gate.get("registered")) and bool(idle_gate.get("idle"))
    health_status = str(health.get("status") or "missing")
    return [
        {
            "id": "execute_live_flag_present",
            "status": "pass" if execute_live else "block_live",
            "required": True,
            "reason": "Live restart is a separate explicit interlock, not implied by confirmation preflight.",
            "evidence": {"execute_live": bool(execute_live)},
        },
        {
            "id": "confirm_mode_required",
            "status": "pass" if confirm else "block_live",
            "required": True,
            "reason": "Live executor can only run after the confirmed executor preflight route.",
            "evidence": {"confirm": bool(confirm)},
        },
        {
            "id": "live_restart_acknowledged",
            "status": "pass" if acknowledge_live_restart else "block_live",
            "required": True,
            "reason": "The operator must explicitly acknowledge that this can restart the selected resident model.",
            "evidence": {"acknowledge_live_restart": bool(acknowledge_live_restart)},
        },
        {
            "id": "operator_identity_declared",
            "status": "pass" if operator_clean else "block_live",
            "required": True,
            "reason": "The live executor audit trail must state who requested the mutation.",
            "evidence": {"operator": operator_clean or None},
        },
        {
            "id": "reason_declared",
            "status": "pass" if len(reason_clean) >= 8 else "block_live",
            "required": True,
            "reason": "The live executor audit trail must state why the restart/rehydrate is being run.",
            "evidence": {"reason_chars": len(reason_clean)},
        },
        {
            "id": "managed_model_candidate_only",
            "status": "pass" if kind == "managed_model_dehydrate_rehydrate_candidate" else "block_live",
            "required": True,
            "reason": "The current live executor is intentionally limited to managed model candidates.",
            "evidence": {"candidate_kind": kind},
        },
        {
            "id": "protected_hotpath_excluded",
            "status": "pass" if not protected_hotpath else "block_live",
            "required": True,
            "reason": "TTS and dictation are protected operator-facing capabilities and are not live-executor targets here.",
            "evidence": {"haystack_contains_tts_or_dictation": protected_hotpath},
        },
        {
            "id": "persistent_model_target",
            "status": "pass" if role == "persistent_model" else "block_live",
            "required": True,
            "reason": "Live executor support is scoped to resident persistent model runtimes.",
            "evidence": {"capability_role": role},
        },
        {
            "id": "confirmed_executor_preflight_ready",
            "status": "pass" if preflight_ready and preflight_live_only else "block_live",
            "required": True,
            "reason": "All immediate preflight checks must pass, with only the invocation-level live-stage blocker remaining.",
            "evidence": {
                "preflight_ready_except_live_stage": preflight_ready,
                "blocked_only_by_live_stage_disabled": preflight_live_only,
            },
        },
        {
            "id": "executor_supported",
            "status": "pass" if executor_kind in {"podman_container_rehydrate", "rerank_api_idle_unload"} else "block_live",
            "required": True,
            "reason": "Live implementation supports podman managed-model restarts and rerank-api idle unload/recycle.",
            "evidence": {"executor_kind": executor_kind, "command_template": command_template},
        },
        {
            "id": "target_running_now",
            "status": "pass" if podman_running else "block_live",
            "required": True,
            "reason": "The target container must be running before a restart/rehydrate operation.",
            "evidence": {"podman_running": podman_running, "pid": nested_get(snapshot, ["podman", "container", "pid"])},
        },
        {
            "id": "idle_and_health_current",
            "status": "pass" if idle_ok and health_status == "available" else "block_live",
            "required": True,
            "reason": "Idle and health must be rechecked immediately before the live restart.",
            "evidence": {
                "idle_registered": bool(idle_gate.get("registered")),
                "idle": bool(idle_gate.get("idle")),
                "idle_status": idle_gate.get("status"),
                "health_route_status": health_status,
            },
        },
        {
            "id": "command_template_sane",
            "status": "pass" if (
                (
                    command_template
                    and len(command_template) == 3
                    and command_template[:2] == ["podman", "restart"]
                    and bool(command_template[2])
                )
                or (
                    rerank_api
                    and command_template
                    and len(command_template) == 2
                    and command_template[0] == "http_post_json"
                    and str(command_template[1]).endswith("/admin/unload?exit_process=true")
                )
            ) else "block_live",
            "required": True,
            "reason": "The executor command must be a narrow podman restart or the registered rerank-api unload endpoint.",
            "evidence": {"command_template": command_template},
        },
    ]


def podman_id_from_target(target: dict[str, Any]) -> str | None:
    haystack = " ".join(
        str(value or "")
        for value in (
            target.get("label"),
            target.get("unit"),
            target.get("cgroup"),
        )
    )
    match = re.search(r"\blibpod-([0-9a-f]{12,64})(?:\.scope|/|\b)", haystack)
    if match:
        return match.group(1)
    match = re.search(r"\b([0-9a-f]{64})\b", haystack)
    if match:
        return match.group(1)
    return None


def podman_snapshot(
    target: dict[str, Any],
    *,
    command_exists: CommandExistsPort = tool_available,
    runner: CommandRunnerPort = run_tool_process,
    container_summary: Callable[[dict[str, Any]], dict[str, Any]] = process_adapters.safe_container_summary,
) -> dict[str, Any]:
    container_id = podman_id_from_target(target)
    if not container_id:
        return {"available": False, "reason": "no_libpod_container_id_detected"}
    data: dict[str, Any] = {
        "available": True,
        "container_id": container_id[:12],
        "source": "podman inspect read-only",
    }
    if not command_exists("podman"):
        data.update({"ok": False, "error": "podman_not_installed"})
        return data
    out = dict(runner(["podman", "inspect", container_id], 8.0))
    data["ok"] = bool(out.get("ok"))
    data["returncode"] = out.get("returncode")
    if not out.get("ok"):
        data["error"] = out.get("stderr") or out.get("stdout") or "podman inspect failed"
        return data
    try:
        raw = json.loads(str(out.get("stdout") or "[]"))
    except json.JSONDecodeError as exc:
        data.update({"ok": False, "error": f"invalid podman inspect JSON: {exc}"})
        return data
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        data["container"] = container_summary(raw[0])
    return data


def target_snapshot(
    candidate: dict[str, Any],
    *,
    cgroup_snapshot: Callable[[str | None], dict[str, Any]],
    process_info: ProcessInfoPort,
    systemd_unit_properties: SystemdPropertiesPort,
    memory_control_value: ControlValuePort,
    kib_to_mib: KibToMibPort,
    proc_root: Path = Path("/proc"),
    podman_snapshot_port: Callable[[dict[str, Any]], dict[str, Any]] = podman_snapshot,
) -> dict[str, Any]:
    target = candidate.get("target", {}) if isinstance(candidate.get("target"), dict) else {}
    cgroup = str(target.get("cgroup") or "")
    cgroup_data = cgroup_snapshot(cgroup)
    raw_pids: list[int] = []
    for source in (target.get("pids"), cgroup_data.get("pids")):
        if not isinstance(source, list):
            continue
        for pid in source:
            try:
                value = int(pid)
            except (TypeError, ValueError):
                continue
            if value > 0 and value not in raw_pids:
                raw_pids.append(value)
    alive_pids = [pid for pid in raw_pids if (proc_root / str(pid)).exists()]
    processes: list[dict[str, Any]] = []
    for pid in alive_pids[:8]:
        info = process_info(pid)
        if not info:
            continue
        processes.append(
            {
                "pid": pid,
                "name": info.get("name"),
                "workload_hint": info.get("workload_hint"),
                "capability_role": info.get("capability_role"),
                "rss_mib": kib_to_mib(int(info.get("vmrss_kib") or info.get("rss_kib") or 0)),
                "cmdline_preview": str(info.get("cmdline") or "")[:180],
            }
        )

    unit = str(target.get("unit") or "")
    systemd: dict[str, Any] = {"available": False, "reason": "target_has_no_unit_hint"}
    if unit:
        properties = [
            "Id",
            "ActiveState",
            "SubState",
            "MainPID",
            "ControlGroup",
            "Slice",
            "MemoryCurrent",
            "MemorySwapCurrent",
            "MemoryHigh",
            "MemoryMax",
            "MemorySwapMax",
        ]
        user_scope = cgroup.startswith("/user.slice/")
        shown = systemd_unit_properties(unit, properties, user_scope, 2.0)
        props = shown.get("properties", {}) if isinstance(shown.get("properties"), dict) else {}
        systemd = {
            "available": bool(shown.get("ok")),
            "scope": "user" if user_scope else "system",
            "unit": unit,
            "active_state": props.get("ActiveState"),
            "sub_state": props.get("SubState"),
            "main_pid": props.get("MainPID"),
            "control_group": props.get("ControlGroup"),
            "memory_current": memory_control_value(props.get("MemoryCurrent")),
            "memory_swap_current": memory_control_value(props.get("MemorySwapCurrent")),
            "memory_high": memory_control_value(props.get("MemoryHigh")),
            "memory_max": memory_control_value(props.get("MemoryMax")),
            "memory_swap_max": memory_control_value(props.get("MemorySwapMax")),
            "error": shown.get("error"),
            "returncode": shown.get("returncode"),
        }

    return {
        "target": target,
        "cgroup": cgroup_data,
        "systemd": systemd,
        "podman": podman_snapshot_port(target),
        "pids": {
            "seen": raw_pids[:64],
            "alive": alive_pids[:64],
            "alive_count": len(alive_pids),
            "sampled_processes": processes,
        },
    }


def http_json(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 262144,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "url": url,
                    "status_code": getattr(response, "status", None),
                    "content_type": response.headers.get("content-type"),
                    "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                    "error": f"invalid JSON: {exc}",
                    "truncated": truncated,
                    "text_preview": text[:400],
                }
            return {
                "ok": True,
                "url": url,
                "status_code": getattr(response, "status", None),
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "json": parsed,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }


def http_status(
    url: str,
    timeout: float = 1.5,
    max_bytes: int = 65536,
    method: str = "GET",
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    started = monotonic()
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method=str(method or "GET").upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            text = raw.decode("utf-8", errors="replace")
            status_code = getattr(response, "status", None)
            return {
                "ok": bool(status_code is not None and 200 <= int(status_code) < 300),
                "url": url,
                "status_code": status_code,
                "content_type": response.headers.get("content-type"),
                "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
                "truncated": truncated,
                "text_preview": text[:400],
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": exc.code,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "elapsed_ms": round((monotonic() - started) * 1000.0, 1),
            "error": str(exc),
        }


def podman_http_endpoint(snapshot: dict[str, Any]) -> dict[str, Any]:
    ports = nested_get(snapshot, ["podman", "container", "ports"])
    if not isinstance(ports, dict):
        return {"available": False, "reason": "podman_ports_unavailable"}
    preferred = ["5405/tcp", "8080/tcp", "8000/tcp", "11434/tcp", "11435/tcp"]
    keys = [key for key in preferred if key in ports] + [key for key in ports if key not in preferred]
    for key in keys:
        bindings = ports.get(key)
        if not isinstance(bindings, list):
            continue
        for item in bindings:
            if not isinstance(item, dict):
                continue
            host_port = str(item.get("host_port") or "").strip()
            if not host_port:
                continue
            host_ip = str(item.get("host_ip") or "127.0.0.1").strip()
            if host_ip in {"", "0.0.0.0", "::", "[::]"}:
                host_ip = "127.0.0.1"
            if ":" in host_ip and not host_ip.startswith("["):
                host_ip = f"[{host_ip}]"
            return {
                "available": True,
                "source": "podman_inspect_ports",
                "container_port": key,
                "host_ip": host_ip,
                "host_port": host_port,
                "base_url": f"http://{host_ip}:{host_port}",
            }
    return {"available": False, "reason": "no_host_port_binding"}


def cgroup_cpu_sample(
    control_group: str | None,
    sample_sec: float = 0.5,
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    sleep: SleepPort = time.sleep,
    monotonic: MonotonicPort = time.monotonic,
    cpu_count: Callable[[], int | None] = os.cpu_count,
) -> dict[str, Any]:
    sample_sec = max(0.1, min(float(sample_sec or 0.5), 3.0))
    if not control_group:
        return {"available": False, "reason": "missing_control_group"}
    path = cgroup_root / str(control_group).lstrip("/")
    if not path.exists():
        return {"available": False, "reason": "cgroup_missing", "path": str(path)}
    before = parse_key_value_file(path / "cpu.stat")
    started = monotonic()
    sleep(sample_sec)
    elapsed = max(0.001, monotonic() - started)
    after = parse_key_value_file(path / "cpu.stat")
    usage_before = before.get("usage_usec")
    usage_after = after.get("usage_usec")
    if usage_before is None or usage_after is None:
        return {"available": False, "reason": "cpu_usage_counter_missing", "path": str(path)}
    usage_delta_usec = max(0, int(usage_after) - int(usage_before))
    cpu_cores = usage_delta_usec / (elapsed * 1_000_000.0)
    total_cpus = cpu_count() or 1
    return {
        "available": True,
        "path": str(path),
        "sample_sec": round(elapsed, 3),
        "usage_delta_usec": usage_delta_usec,
        "cpu_cores": round(cpu_cores, 4),
        "cpu_percent_of_one_core": round(cpu_cores * 100.0, 2),
        "cpu_percent_of_system": round((cpu_cores / total_cpus) * 100.0, 2),
        "threshold_cpu_cores_idle_at_or_below": 0.15,
        "idle": cpu_cores <= 0.15,
        "before": {key: before.get(key) for key in ("usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec")},
        "after": {key: after.get(key) for key in ("usage_usec", "user_usec", "system_usec", "nr_periods", "nr_throttled", "throttled_usec")},
    }


def llama_http_idle(endpoint: dict[str, Any], *, http_json_port: HttpJsonPort = http_json) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    health = http_json_port(f"{base_url}/health", 1.5, 65536, "GET")
    slots = http_json_port(f"{base_url}/slots", 1.5, 262144, "GET")
    models = http_json_port(f"{base_url}/v1/models", 1.5, 262144, "GET")
    slot_items = slots.get("json") if isinstance(slots.get("json"), list) else []
    processing_slots = []
    decoded_slots = []
    for item in slot_items if isinstance(slot_items, list) else []:
        if not isinstance(item, dict):
            continue
        next_token = item.get("next_token")
        has_next_token = False
        n_remain = None
        n_decoded = None
        if isinstance(next_token, list) and next_token and isinstance(next_token[0], dict):
            has_next_token = bool(next_token[0].get("has_next_token"))
            n_remain = next_token[0].get("n_remain")
            n_decoded = next_token[0].get("n_decoded")
        busy = bool(item.get("is_processing")) or bool(has_next_token)
        stale_remaining_ignored = bool(
            isinstance(n_remain, int)
            and n_remain > 0
            and not bool(item.get("is_processing"))
            and not bool(has_next_token)
        )
        slot_summary = {
            "id": item.get("id"),
            "is_processing": bool(item.get("is_processing")),
            "id_task": item.get("id_task"),
            "n_ctx": item.get("n_ctx"),
            "has_next_token": has_next_token,
            "n_remain": n_remain,
            "n_decoded": n_decoded,
            "stale_n_remain_ignored": stale_remaining_ignored,
            "busy": busy,
        }
        decoded_slots.append(slot_summary)
        if busy:
            processing_slots.append(slot_summary)
    model_ids: list[str] = []
    model_data = models.get("json")
    if isinstance(model_data, dict):
        data_items = model_data.get("data") if isinstance(model_data.get("data"), list) else []
        for item in data_items:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item.get("id")))
    health_payload = health.get("json") if isinstance(health.get("json"), dict) else {}
    health_ok = bool(health.get("ok")) and str(health_payload.get("status") or "").lower() in {"ok", "ready", "healthy"}
    slots_available = bool(slots.get("ok")) and isinstance(slot_items, list)
    slots_idle = slots_available and len(slot_items) > 0 and len(processing_slots) == 0
    return {
        "available": bool(health.get("ok") or slots.get("ok")),
        "kind": "llama_cpp_http",
        "endpoint": endpoint,
        "health": {
            "ok": bool(health.get("ok")),
            "status": health_payload.get("status") if isinstance(health_payload, dict) else None,
            "elapsed_ms": health.get("elapsed_ms"),
            "error": health.get("error"),
        },
        "slots": {
            "ok": bool(slots.get("ok")),
            "count": len(slot_items) if isinstance(slot_items, list) else None,
            "processing_count": len(processing_slots),
            "idle": slots_idle,
            "items": decoded_slots[:16],
            "error": slots.get("error"),
        },
        "models": {
            "ok": bool(models.get("ok")),
            "ids": model_ids[:8],
            "error": models.get("error"),
        },
        "idle": bool(health_ok and slots_idle),
        "confidence": "high" if bool(health.get("ok") and slots.get("ok")) else "low",
    }


def rerank_http_idle(endpoint: dict[str, Any], *, http_json_port: HttpJsonPort = http_json) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    health = http_json_port(f"{base_url}/health", 1.5, 65536, "GET")
    payload = health.get("json") if isinstance(health.get("json"), dict) else {}
    service = str(payload.get("service") or "").lower() if isinstance(payload, dict) else ""
    health_ok = bool(health.get("ok")) and service == "rerank-api" and bool(payload.get("ok"))
    active_requests = _safe_int(payload.get("active_requests"), 0) if isinstance(payload, dict) else 0
    loaded = bool(payload.get("loaded")) if isinstance(payload, dict) else False
    idle = bool(health_ok and active_requests == 0)
    return {
        "available": bool(health.get("ok")),
        "kind": "rerank_api_http",
        "endpoint": endpoint,
        "health": {
            "ok": bool(health.get("ok")),
            "service": payload.get("service") if isinstance(payload, dict) else None,
            "loaded": loaded,
            "active_requests": active_requests,
            "idle_for_sec": payload.get("idle_for_sec") if isinstance(payload, dict) else None,
            "exit_after_idle_unload": payload.get("exit_after_idle_unload") if isinstance(payload, dict) else None,
            "elapsed_ms": health.get("elapsed_ms"),
            "error": health.get("error"),
        },
        "idle": idle,
        "confidence": "high" if health_ok and "active_requests" in payload else "medium" if health_ok else "low",
    }


def ovms_http_idle(
    endpoint: dict[str, Any],
    *,
    http_json_port: HttpJsonPort = http_json,
    http_status_port: HttpStatusPort = http_status,
) -> dict[str, Any]:
    if not endpoint.get("available"):
        return {"available": False, "reason": endpoint.get("reason") or "endpoint_unavailable"}
    base_url = str(endpoint.get("base_url") or "").rstrip("/")
    live = http_status_port(f"{base_url}/v2/health/live", 1.5, 65536, "GET")
    ready = http_status_port(f"{base_url}/v2/health/ready", 1.5, 65536, "GET")
    config = http_json_port(f"{base_url}/v1/config", 1.5, 262144, "GET")
    payload = config.get("json") if isinstance(config.get("json"), dict) else {}
    models: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for model_name, model_payload in payload.items():
            if not isinstance(model_payload, dict):
                continue
            statuses = model_payload.get("model_version_status")
            status_items = statuses if isinstance(statuses, list) else []
            available_versions = []
            for item in status_items:
                if not isinstance(item, dict):
                    continue
                state = str(item.get("state") or "").upper()
                status = item.get("status") if isinstance(item.get("status"), dict) else {}
                ok_status = str(status.get("error_code") or "").upper() in {"", "OK"}
                if state == "AVAILABLE" and ok_status:
                    available_versions.append(str(item.get("version") or ""))
            models.append(
                {
                    "name": str(model_name),
                    "version_count": len(status_items),
                    "available_versions": [version for version in available_versions if version][:8],
                    "available": bool(available_versions),
                }
            )
    health_ok = bool(live.get("ok")) and bool(ready.get("ok"))
    config_ok = bool(config.get("ok")) and bool(models) and all(bool(item.get("available")) for item in models)
    return {
        "available": bool(health_ok or config.get("ok")),
        "kind": "ovms_http",
        "endpoint": endpoint,
        "health": {
            "ok": health_ok,
            "live_ok": bool(live.get("ok")),
            "ready_ok": bool(ready.get("ok")),
            "live_status_code": live.get("status_code"),
            "ready_status_code": ready.get("status_code"),
            "elapsed_ms": max(
                _safe_float(live.get("elapsed_ms"), 0.0) or 0.0,
                _safe_float(ready.get("elapsed_ms"), 0.0) or 0.0,
            ),
            "live_error": live.get("error"),
            "ready_error": ready.get("error"),
        },
        "models": {
            "ok": config_ok,
            "count": len(models),
            "available_count": sum(1 for item in models if item.get("available")),
            "items": models[:16],
            "error": config.get("error"),
        },
        "idle": bool(health_ok and config_ok),
        "confidence": "medium" if health_ok and config_ok else "low",
    }


def executor_lock_status(
    *,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    root = runtime_dir or Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid if uid is not None else os.getuid()}"))
    lock_path = root / "abyss-machine" / "memory" / "orchestrate" / "executor.lock"
    exists = lock_path.exists()
    data: dict[str, Any] = {
        "path": str(lock_path),
        "exists": exists,
        "available": not exists,
    }
    if exists:
        data["content_preview"] = _read_text(lock_path)[:400]
    return data


def live_lock_path(*, runtime_dir: Path | None = None, uid: int | None = None) -> Path:
    root = runtime_dir or Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid if uid is not None else os.getuid()}"))
    return root / "abyss-machine" / "memory" / "orchestrate" / "live.lock"


def live_lock_acquire(
    candidate_id: str,
    operator: str,
    *,
    schema_prefix: str,
    version: str,
    now_iso: NowIsoPort,
    pid: PidPort = os.getpid,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    lock_path = live_lock_path(runtime_dir=runtime_dir, uid=uid)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": f"{schema_prefix}_memory_orchestrate_live_lock_v1",
        "version": version,
        "created_at": now_iso(),
        "pid": pid(),
        "candidate_id": str(candidate_id or ""),
        "operator": str(operator or "").strip() or None,
    }
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, (json.dumps(payload, sort_keys=False) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        return {"acquired": True, "path": str(lock_path), "payload": payload}
    except FileExistsError:
        return {
            "acquired": False,
            "path": str(lock_path),
            "reason": "live_executor_lock_exists",
            "content_preview": _read_text(lock_path)[:400],
        }
    except OSError as exc:
        return {"acquired": False, "path": str(lock_path), "reason": str(exc)}


def live_lock_release(
    lock_status: dict[str, Any],
    *,
    runtime_dir: Path | None = None,
    uid: int | None = None,
) -> dict[str, Any]:
    lock_path = Path(str(lock_status.get("path") or live_lock_path(runtime_dir=runtime_dir, uid=uid)))
    if not lock_status.get("acquired"):
        return {"released": False, "path": str(lock_path), "reason": "lock_not_acquired_by_this_process"}
    try:
        lock_path.unlink()
        return {"released": True, "path": str(lock_path)}
    except FileNotFoundError:
        return {"released": False, "path": str(lock_path), "reason": "already_missing"}
    except OSError as exc:
        return {"released": False, "path": str(lock_path), "reason": str(exc)}


def live_execute_command(
    future_executor: dict[str, Any],
    timeout_sec: int,
    *,
    runner: CommandRunnerPort = run_tool_process,
    http_json_port: HttpJsonPort = http_json,
    monotonic: MonotonicPort = time.monotonic,
) -> dict[str, Any]:
    command_template = future_executor.get("command_template") if isinstance(future_executor.get("command_template"), list) else []
    command = [str(item) for item in command_template]
    if len(command) == 2 and command[0] == "http_post_json" and command[1].startswith("http://"):
        started = monotonic()
        result = http_json_port(command[1], float(timeout_sec), 262144, "POST")
        result["ok"] = bool(result.get("ok")) and bool(nested_get(result, ["json", "ok"]))
        result["returncode"] = 0 if result.get("ok") else 1
        result["command"] = command
        result["elapsed_sec"] = round(monotonic() - started, 3)
        return result
    if len(command) != 3 or command[:2] != ["podman", "restart"] or not command[2]:
        return {
            "ok": False,
            "returncode": None,
            "command": command,
            "error": "unsupported_live_executor_command",
        }
    started = monotonic()
    result = dict(runner(command, float(timeout_sec)))
    result["command"] = command
    result["elapsed_sec"] = round(monotonic() - started, 3)
    return result


def live_wait_rehydrate(
    candidate: dict[str, Any],
    timeout_sec: int,
    *,
    target_snapshot: Callable[[dict[str, Any]], dict[str, Any]],
    idle_probe: Callable[[dict[str, Any], dict[str, Any], float], dict[str, Any]],
    health_summary: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    monotonic: MonotonicPort = time.monotonic,
    sleep: SleepPort = time.sleep,
) -> dict[str, Any]:
    timeout_sec = max(30, min(int(timeout_sec or 180), 600))
    started = monotonic()
    deadline = started + float(timeout_sec)
    attempts: list[dict[str, Any]] = []
    final_snapshot: dict[str, Any] = {}
    final_idle_gate: dict[str, Any] = {}
    final_summary: dict[str, Any] = {}
    attempt = 0
    while True:
        attempt += 1
        final_snapshot = target_snapshot(candidate)
        final_idle_gate = idle_probe(candidate, final_snapshot, 0.2)
        final_summary = health_summary(final_snapshot, final_idle_gate)
        attempts.append(
            {
                "attempt": attempt,
                "elapsed_sec": round(monotonic() - started, 3),
                "ready": final_summary.get("ready"),
                "podman_running": final_summary.get("podman_running"),
                "pid": final_summary.get("pid"),
                "http_health_ok": final_summary.get("http_health_ok"),
                "slots_ok": final_summary.get("slots_ok"),
                "slots_idle": final_summary.get("slots_idle"),
                "ovms_models_ok": final_summary.get("ovms_models_ok"),
                "ovms_model_count": final_summary.get("ovms_model_count"),
                "idle": final_summary.get("idle"),
                "idle_status": final_summary.get("idle_status"),
            }
        )
        if final_summary.get("ready"):
            break
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(2.0, max(0.2, remaining)))
    elapsed = round(monotonic() - started, 3)
    ok = bool(final_summary.get("ready"))
    return {
        "ok": ok,
        "status": "ready" if ok else "timeout_waiting_for_ready",
        "timeout_sec": timeout_sec,
        "elapsed_sec": elapsed,
        "attempt_count": attempt,
        "attempts_tail": attempts[-20:],
        "final_health_summary": final_summary,
        "final_snapshot": final_snapshot,
        "final_idle_gate": final_idle_gate,
    }
