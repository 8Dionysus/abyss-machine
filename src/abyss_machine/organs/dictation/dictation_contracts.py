from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


VALID_PROFILES = {"auto", "fast", "quality", "long", "command"}
CONCRETE_PROFILES = {"fast", "quality", "long", "command"}
PUNCTUATION_STYLES = {"normal", "soft", "off"}
RUNTIME_NUMERIC_LIMITS = {
    "target_rms_dbfs": (-36.0, -14.0),
    "max_gain": (1.0, 12.0),
    "peak_limit": (0.25, 0.98),
    "trim_pad_seconds": (0.0, 0.5),
    "vad_min_seconds": (1.0, 60.0),
    "vad_min_pause_seconds": (0.15, 2.0),
    "vad_target_segment_seconds": (4.0, 30.0),
    "vad_min_segment_seconds": (1.0, 12.0),
    "vad_pad_seconds": (0.0, 0.4),
}
RUNTIME_ENV_MAPPING = {
    "audio_preprocess": "ABYSS_DICTATION_AUDIO_PREPROCESS",
    "target_rms_dbfs": "ABYSS_DICTATION_TARGET_RMS_DBFS",
    "max_gain": "ABYSS_DICTATION_MAX_GAIN",
    "peak_limit": "ABYSS_DICTATION_PEAK_LIMIT",
    "trim_edges": "ABYSS_DICTATION_TRIM_EDGES",
    "trim_pad_seconds": "ABYSS_DICTATION_TRIM_PAD_SECONDS",
    "vad_segments": "ABYSS_DICTATION_VAD_SEGMENTS",
    "vad_min_seconds": "ABYSS_DICTATION_VAD_MIN_SECONDS",
    "vad_min_pause_seconds": "ABYSS_DICTATION_VAD_MIN_PAUSE_SECONDS",
    "vad_target_segment_seconds": "ABYSS_DICTATION_VAD_TARGET_SEGMENT_SECONDS",
    "vad_min_segment_seconds": "ABYSS_DICTATION_VAD_MIN_SEGMENT_SECONDS",
    "vad_pad_seconds": "ABYSS_DICTATION_VAD_PAD_SECONDS",
    "adaptive_decoding": "ABYSS_DICTATION_ADAPTIVE_DECODING",
}


def bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"0", "false", "no", "off"}
    if value is None:
        return default
    return bool(value)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def env_override_bool(env: Mapping[str, str] | None, name: str, default: bool) -> bool:
    raw = (env or {}).get(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


def env_override_float(env: Mapping[str, str] | None, name: str, default: float, lower: float, upper: float) -> float:
    raw = (env or {}).get(name)
    if raw is None:
        return max(lower, min(upper, default))
    try:
        value = float(raw)
    except ValueError:
        return max(lower, min(upper, default))
    return max(lower, min(upper, value))


def env_override_int(env: Mapping[str, str] | None, name: str, default: int, lower: int, upper: int) -> int:
    raw = (env or {}).get(name)
    if raw is None:
        return max(lower, min(upper, default))
    try:
        value = int(raw)
    except ValueError:
        return max(lower, min(upper, default))
    return max(lower, min(upper, value))


def default_config(schema_prefix: str = "abyss_machine", version: str = "") -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_config_v1",
        "version": version,
        "default_profile": "auto",
        "notifications": {
            "enabled": False,
            "desktop": False,
        },
        "journal": {
            "enabled": True,
            "include_failed": True,
            "copy_audio_to_persistent_storage": False,
        },
        "profile_policy": {
            "auto_enabled": True,
            "long_min_sec": 45.0,
            "fallback_profile": "quality",
        },
        "command_intent": {
            "enabled": True,
            "requires_prefix": True,
            "trigger_phrases": ["команда"],
            "strip_trigger": True,
            "execution": "detect-only",
        },
        "runtime": {
            "audio_preprocess": True,
            "target_rms_dbfs": -24.0,
            "max_gain": 4.0,
            "peak_limit": 0.92,
            "trim_edges": True,
            "trim_pad_seconds": 0.12,
            "vad_segments": True,
            "vad_min_seconds": 16.0,
            "vad_min_pause_seconds": 0.65,
            "vad_target_segment_seconds": 14.0,
            "vad_min_segment_seconds": 5.0,
            "vad_pad_seconds": 0.08,
            "adaptive_decoding": True,
        },
        "postprocess": {
            "text_fixes": True,
            "smart_punctuation": True,
            "punctuation_style": "normal",
            "final_punctuation": True,
            "final_space": True,
        },
        "profiles": {
            "fast": {
                "enabled": True,
                "description": "lowest-latency manual validation profile",
                "runtime": {
                    "vad_segments": False,
                    "adaptive_decoding": True,
                },
                "postprocess": {
                    "punctuation_style": "normal",
                },
            },
            "quality": {
                "enabled": True,
                "description": "default high-quality dictation profile",
                "runtime": {},
                "postprocess": {
                    "punctuation_style": "normal",
                },
            },
            "long": {
                "enabled": True,
                "description": "long-form speech profile with softer segmentation and punctuation",
                "runtime": {
                    "vad_min_seconds": 20.0,
                    "vad_min_pause_seconds": 0.85,
                    "vad_target_segment_seconds": 18.0,
                    "vad_min_segment_seconds": 7.0,
                    "vad_pad_seconds": 0.10,
                },
                "postprocess": {
                    "punctuation_style": "soft",
                },
            },
            "command": {
                "enabled": True,
                "description": "short command phrase profile; minimal punctuation",
                "runtime": {
                    "vad_segments": False,
                },
                "postprocess": {
                    "smart_punctuation": False,
                    "final_punctuation": False,
                    "final_space": True,
                },
            },
        },
        "calibration": {
            "enabled": True,
            "source": None,
            "updated_at": None,
        },
    }


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    default_profile = str(config.get("default_profile", "auto"))
    if default_profile not in VALID_PROFILES:
        errors.append(f"default_profile must be one of {sorted(VALID_PROFILES)}")

    if not isinstance(config.get("notifications"), dict):
        errors.append("notifications must be an object")
    if not isinstance(config.get("journal"), dict):
        errors.append("journal must be an object")

    policy = config.get("profile_policy")
    if not isinstance(policy, dict):
        errors.append("profile_policy must be an object")
    else:
        try:
            value = float(policy.get("long_min_sec"))
        except (TypeError, ValueError):
            errors.append("profile_policy.long_min_sec must be a number")
        else:
            if value <= 0:
                errors.append("profile_policy.long_min_sec must be positive")
        fallback = str(policy.get("fallback_profile", "quality"))
        if fallback not in CONCRETE_PROFILES:
            errors.append("profile_policy.fallback_profile must be a concrete profile")

    runtime = config.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime must be an object")
    else:
        for key, (lower, upper) in RUNTIME_NUMERIC_LIMITS.items():
            try:
                value = float(runtime.get(key))
            except (TypeError, ValueError):
                errors.append(f"runtime.{key} must be a number")
                continue
            if value < lower or value > upper:
                errors.append(f"runtime.{key} must be between {lower} and {upper}")

    postprocess = config.get("postprocess")
    if not isinstance(postprocess, dict):
        errors.append("postprocess must be an object")
    elif str(postprocess.get("punctuation_style", "normal")) not in PUNCTUATION_STYLES:
        errors.append("postprocess.punctuation_style must be normal, soft, or off")

    command_intent = config.get("command_intent")
    if not isinstance(command_intent, dict):
        errors.append("command_intent must be an object")
    else:
        triggers = command_intent.get("trigger_phrases")
        if not isinstance(triggers, list) or not all(isinstance(item, str) and item.strip() for item in triggers):
            errors.append("command_intent.trigger_phrases must be a non-empty string list")

    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        errors.append("profiles must be an object")
    else:
        for name in ("fast", "quality", "long", "command"):
            if not isinstance(profiles.get(name), dict):
                errors.append(f"profiles.{name} must be an object")
    return errors


def runtime_options(profile: dict[str, Any], config: dict[str, Any], env: Mapping[str, str] | None = None) -> dict[str, Any]:
    runtime = deep_merge(dict(config.get("runtime", {})), dict(profile.get("runtime", {})))
    return {
        "audio_preprocess": env_override_bool(env, "ABYSS_DICTATION_AUDIO_PREPROCESS", bool_value(runtime.get("audio_preprocess"), True)),
        "target_rms_dbfs": env_override_float(env, "ABYSS_DICTATION_TARGET_RMS_DBFS", float(runtime.get("target_rms_dbfs", -24.0)), -36.0, -14.0),
        "max_gain": env_override_float(env, "ABYSS_DICTATION_MAX_GAIN", float(runtime.get("max_gain", 4.0)), 1.0, 12.0),
        "peak_limit": env_override_float(env, "ABYSS_DICTATION_PEAK_LIMIT", float(runtime.get("peak_limit", 0.92)), 0.25, 0.98),
        "trim_edges": env_override_bool(env, "ABYSS_DICTATION_TRIM_EDGES", bool_value(runtime.get("trim_edges"), True)),
        "trim_pad_seconds": env_override_float(env, "ABYSS_DICTATION_TRIM_PAD_SECONDS", float(runtime.get("trim_pad_seconds", 0.12)), 0.0, 0.5),
        "vad_segments": env_override_bool(env, "ABYSS_DICTATION_VAD_SEGMENTS", bool_value(runtime.get("vad_segments"), True)),
        "vad_min_seconds": env_override_float(env, "ABYSS_DICTATION_VAD_MIN_SECONDS", float(runtime.get("vad_min_seconds", 16.0)), 1.0, 60.0),
        "vad_min_pause_seconds": env_override_float(env, "ABYSS_DICTATION_VAD_MIN_PAUSE_SECONDS", float(runtime.get("vad_min_pause_seconds", 0.65)), 0.15, 2.0),
        "vad_target_segment_seconds": env_override_float(env, "ABYSS_DICTATION_VAD_TARGET_SEGMENT_SECONDS", float(runtime.get("vad_target_segment_seconds", 14.0)), 4.0, 30.0),
        "vad_min_segment_seconds": env_override_float(env, "ABYSS_DICTATION_VAD_MIN_SEGMENT_SECONDS", float(runtime.get("vad_min_segment_seconds", 5.0)), 1.0, 12.0),
        "vad_pad_seconds": env_override_float(env, "ABYSS_DICTATION_VAD_PAD_SECONDS", float(runtime.get("vad_pad_seconds", 0.08)), 0.0, 0.4),
        "adaptive_decoding": env_override_bool(env, "ABYSS_DICTATION_ADAPTIVE_DECODING", bool_value(runtime.get("adaptive_decoding"), True)),
    }


def postprocess_options(profile: dict[str, Any], config: dict[str, Any], env: Mapping[str, str] | None = None) -> dict[str, Any]:
    postprocess = deep_merge(dict(config.get("postprocess", {})), dict(profile.get("postprocess", {})))
    style = str(postprocess.get("punctuation_style", "normal")).lower()
    if style not in PUNCTUATION_STYLES:
        style = "normal"
    smart_default = bool_value(postprocess.get("smart_punctuation"), True) and style != "off"
    return {
        "text_fixes": env_override_bool(env, "ABYSS_DICTATION_TEXT_FIXES", bool_value(postprocess.get("text_fixes"), True)),
        "smart_punctuation": env_override_bool(env, "ABYSS_DICTATION_SMART_PUNCTUATION", smart_default),
        "punctuation_style": (env or {}).get("ABYSS_DICTATION_PUNCTUATION_STYLE", style).lower(),
        "final_punctuation": env_override_bool(env, "ABYSS_DICTATION_FINAL_PUNCTUATION", bool_value(postprocess.get("final_punctuation"), True)),
        "final_space": env_override_bool(env, "ABYSS_DICTATION_FINAL_SPACE", bool_value(postprocess.get("final_space"), True)),
    }


def requested_profile_name(
    name: str | None,
    config: dict[str, Any],
    env: Mapping[str, str] | None = None,
    default_profile: str = "auto",
) -> str:
    selected = name or (env or {}).get("ABYSS_DICTATION_PROFILE") or str(config.get("default_profile") or default_profile)
    if selected not in VALID_PROFILES:
        selected = str(config.get("profile_policy", {}).get("fallback_profile") or "quality")
    if selected not in VALID_PROFILES:
        selected = "quality"
    return selected


def auto_select_profile(
    audio_stats: dict[str, Any] | None,
    config: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    env: Mapping[str, str] | None = None,
    audio_error: str | None = None,
) -> tuple[str, dict[str, Any]]:
    policy = config.get("profile_policy", {}) if isinstance(config.get("profile_policy"), dict) else {}
    fallback = str(policy.get("fallback_profile") or "quality")
    if fallback not in profiles:
        fallback = "quality"
    long_min_sec = float(policy.get("long_min_sec", 45.0))
    selection: dict[str, Any] = {
        "mode": "auto",
        "fallback_profile": fallback,
        "rules": {
            "long_min_sec": long_min_sec,
        },
        "command_intent": "detected after transcription by configured trigger phrases",
    }
    if audio_error:
        selection["audio_error"] = audio_error
    if not bool_value(policy.get("auto_enabled"), True) or env_override_bool(env, "ABYSS_DICTATION_AUTO_PROFILE", True) is False:
        selection["reason"] = "auto-disabled"
        return fallback, selection
    if audio_stats and audio_stats.get("ok"):
        duration = float(audio_stats.get("duration_sec") or 0.0)
        selection["audio"] = {
            "duration_sec": duration,
            "dbfs": audio_stats.get("dbfs"),
            "peak": audio_stats.get("peak"),
            "clip_percent": audio_stats.get("clip_percent"),
        }
        if duration >= long_min_sec and profiles.get("long", {}).get("enabled"):
            selection["reason"] = "long-recording"
            return "long", selection
    selection["reason"] = "default-quality"
    return fallback, selection


def summarize_audio_stats(stats: list[dict[str, Any]]) -> dict[str, Any]:
    ok_stats = [item for item in stats if item.get("ok")]
    avg_dbfs = round(sum(float(item["dbfs"]) for item in ok_stats) / len(ok_stats), 1) if ok_stats else None
    max_peak = max((float(item["peak"]) for item in ok_stats), default=None)
    max_clip = max((float(item["clip_percent"]) for item in ok_stats), default=None)
    p10_values = [float(item["frame_dbfs_p10"]) for item in ok_stats if item.get("frame_dbfs_p10") is not None]
    p50_values = [float(item["frame_dbfs_p50"]) for item in ok_stats if item.get("frame_dbfs_p50") is not None]
    p90_values = [float(item["frame_dbfs_p90"]) for item in ok_stats if item.get("frame_dbfs_p90") is not None]
    noise_floor = round(sum(p10_values) / len(p10_values), 1) if p10_values else None
    median_frame = round(sum(p50_values) / len(p50_values), 1) if p50_values else None
    speech_frame = round(sum(p90_values) / len(p90_values), 1) if p90_values else None
    recommendation = "no recent dictation wav files"
    if ok_stats:
        if max_clip and max_clip > 0.05:
            recommendation = "input clips; lower microphone/source gain"
        elif avg_dbfs is not None and avg_dbfs < -36:
            recommendation = "input is very quiet; move closer or raise source gain carefully"
        elif avg_dbfs is not None and avg_dbfs < -28:
            recommendation = "input is clean but quiet; digital normalization before Whisper is useful"
        elif max_peak is not None and max_peak < 0.12:
            recommendation = "input has large headroom; normalization is useful"
        else:
            recommendation = "input level looks healthy"
    return {
        "files_analyzed": len(ok_stats),
        "avg_dbfs": avg_dbfs,
        "max_peak": max_peak,
        "max_clip_percent": max_clip,
        "noise_floor_dbfs": noise_floor,
        "median_frame_dbfs": median_frame,
        "speech_frame_dbfs": speech_frame,
        "recommendation": recommendation,
    }


def recommended_audio_runtime(summary: dict[str, Any]) -> dict[str, Any]:
    avg_dbfs = summary.get("avg_dbfs")
    max_clip = float(summary.get("max_clip_percent") or 0.0)
    noise_floor = summary.get("noise_floor_dbfs")
    target = -24.0
    max_gain = 4.0
    if isinstance(avg_dbfs, (int, float)):
        if avg_dbfs < -36:
            max_gain = 8.0
        elif avg_dbfs < -28:
            max_gain = 5.0
    if max_clip > 0.05:
        max_gain = 2.0
        target = -26.0
    if isinstance(noise_floor, (int, float)) and noise_floor > -42:
        target = min(target, -26.0)
    return {
        "audio_preprocess": True,
        "target_rms_dbfs": target,
        "max_gain": max_gain,
        "peak_limit": 0.92,
        "trim_edges": True,
    }


def runtime_env(runtime: dict[str, Any], base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or {})
    for key, env_name in RUNTIME_ENV_MAPPING.items():
        if key in runtime:
            value = runtime[key]
            env[env_name] = "1" if isinstance(value, bool) and value else "0" if isinstance(value, bool) else str(value)
    return env


def busy_result(action: str, schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_toggle_v1",
        "version": version,
        "generated_at": generated_at,
        "action": action,
        "ok": False,
        "error": "dictation is busy",
    }


def transcript_error_result(
    error: str,
    *,
    profile: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile_selection: dict[str, Any] | None = None,
    stdout_tail: str | None = None,
    stderr_tail: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": f"{schema_prefix}_dictation_transcript_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": error,
        "profile": profile,
    }
    if profile_selection is not None:
        result["profile_selection"] = profile_selection
    if stdout_tail is not None:
        result["stdout_tail"] = stdout_tail[-1000:]
    if stderr_tail is not None:
        result["stderr_tail"] = stderr_tail[-1000:]
    return result


def server_transcript_request(
    *,
    audio: str,
    profile: dict[str, Any],
    runtime_options: dict[str, Any],
    max_new_tokens: int,
    num_beams: int,
) -> dict[str, Any]:
    return {
        "audio": audio,
        "model_dir": profile["model_dir"],
        "device": profile["device"],
        "language": profile["language"],
        "task": "transcribe",
        "max_new_tokens": int(max_new_tokens),
        "num_beams": int(num_beams),
        "runtime": runtime_options,
        "profile_name": profile.get("name"),
    }


def parse_transcript_json(stdout: str) -> dict[str, Any] | None:
    stdout = str(stdout or "").strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        marker = stdout.rfind("\n{")
        if marker < 0:
            return None
        try:
            data = json.loads(stdout[marker + 1 :])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def server_transcript_result_from_raw(
    raw: str,
    *,
    profile: dict[str, Any],
    socket_path: Any,
    client_elapsed_sec: float,
    client_preprocess: dict[str, Any] | None,
    original_audio: str,
    server_audio: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any] | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    data = parse_transcript_json(raw)
    if data is None:
        return transcript_error_result(
            "dictation server returned invalid JSON",
            profile=profile,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
            stdout_tail=raw,
        )
    data.setdefault("schema", f"{schema_prefix}_dictation_transcript_v1")
    data["ok"] = bool(data.get("ok"))
    if client_preprocess is not None:
        data["client_audio_preprocess"] = client_preprocess
        if data.get("audio") == server_audio:
            data["server_audio"] = server_audio
            data["audio"] = original_audio
    data["profile"] = profile
    data["server_socket"] = str(socket_path)
    data["client_elapsed_sec"] = round(float(client_elapsed_sec), 3)
    return data


def helper_transcript_command(
    *,
    helper: Any,
    audio: str,
    model_dir: Any,
    profile: dict[str, Any],
    max_new_tokens: int,
    num_beams: int,
) -> list[str]:
    return [
        str(helper),
        audio,
        "--model-dir",
        str(model_dir),
        "--device",
        profile["device"],
        "--language",
        profile["language"],
        "--max-new-tokens",
        str(int(max_new_tokens)),
        "--num-beams",
        str(int(num_beams)),
        "--json",
    ]


def helper_failure_result(
    run_result: dict[str, Any],
    *,
    profile: dict[str, Any],
    profile_selection: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return transcript_error_result(
        str(run_result.get("stderr") or run_result.get("stdout") or ""),
        profile=profile,
        profile_selection=profile_selection,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def helper_invalid_json_result(
    stdout: str,
    stderr: str,
    *,
    profile: dict[str, Any],
    profile_selection: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return transcript_error_result(
        "helper returned invalid transcript JSON",
        profile=profile,
        profile_selection=profile_selection,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        stdout_tail=stdout,
        stderr_tail=stderr,
    )


def helper_success_result(
    data: dict[str, Any],
    *,
    profile: dict[str, Any],
    profile_selection: dict[str, Any],
    client_elapsed_sec: float,
) -> dict[str, Any]:
    result = dict(data)
    result["ok"] = True
    result["profile"] = profile
    result["profile_selection"] = profile_selection
    result["via"] = result.get("via") or "helper"
    result["client_elapsed_sec"] = round(float(client_elapsed_sec), 3)
    return result


INSERT_COMBOS = {
    "ctrl-v": ["29:1", "47:1", "47:0", "29:0"],
    "ctrl-shift-v": ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"],
}
INSERT_MODIFIER_CLEANUP = ["47:0", "29:0", "42:0", "54:0", "97:0", "100:0", "191:0", "193:0", "194:0", "585:0"]


def normalize_clipboard_provider(value: str | None) -> str:
    provider = str(value or "foreground").lower()
    return provider if provider in {"daemon", "foreground"} else "foreground"


def normalize_paste_combo(value: str | None) -> str:
    combo = str(value or "ctrl-v").lower()
    if combo == "auto":
        return "auto"
    return combo if combo in INSERT_COMBOS else "ctrl-v"


def paste_combo_order(value: str | None) -> list[str]:
    combo = normalize_paste_combo(value)
    return ["ctrl-v"] if combo == "auto" else [combo]


def paste_key_sequence(combo: str) -> list[str]:
    normalized = normalize_paste_combo(combo)
    if normalized == "auto":
        normalized = "ctrl-v"
    return [*INSERT_MODIFIER_CLEANUP, *INSERT_COMBOS[normalized], *INSERT_MODIFIER_CLEANUP]


def insert_empty_result(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_insert_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": "empty text",
    }


def insert_error_result(error: str, schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_insert_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": error,
    }


def insert_wtype_success_result(text: str, schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_insert_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "text": text,
        "method": "wtype",
        "fallback": None,
        "stderr": "",
    }


def insert_final_result(
    *,
    text: str,
    clipboard_provider: str,
    copy_returncode: int | None,
    attempts: list[dict[str, Any]],
    fallback: dict[str, Any] | None,
    copy_stderr: str,
    combo_name: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    normalized_combo = normalize_paste_combo(combo_name)
    paste_sent = any(bool(item.get("paste_sent")) for item in attempts)
    method = f"wl-copy+ydotool-{normalized_combo}"
    return {
        "schema": f"{schema_prefix}_dictation_insert_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": paste_sent,
        "text": text,
        "method": method,
        "clipboard_provider": normalize_clipboard_provider(clipboard_provider),
        "paste_sent": paste_sent,
        "clipboard_provider_returncode": copy_returncode,
        "attempts": attempts,
        "fallback": fallback,
        "stderr": copy_stderr or next((str(item.get("stderr") or "") for item in attempts if item.get("stderr")), ""),
    }


def max_seconds(env: Mapping[str, str] | None, default: int) -> int:
    raw = (env or {}).get("ABYSS_DICTATION_MAX_SECONDS", str(default))
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return 0
    return max(10, min(value, 3600))


def recording_command(audio_path: Any, *, max_seconds_value: int, timeout_available: bool) -> list[str]:
    command = [
        "pw-record",
        "--rate",
        "16000",
        "--channels",
        "1",
        "--format",
        "s16",
        str(audio_path),
    ]
    if max_seconds_value and timeout_available:
        return [
            "timeout",
            "--signal=INT",
            "--kill-after=5s",
            f"{int(max_seconds_value)}s",
            *command,
        ]
    return command


def calibration_recording_command(audio_path: Any, *, seconds: int, timeout_available: bool) -> list[str]:
    command = [
        "pw-record",
        "--rate",
        "16000",
        "--channels",
        "1",
        "--format",
        "s16",
        str(audio_path),
    ]
    if timeout_available:
        return [
            "timeout",
            "--signal=INT",
            "--kill-after=3s",
            f"{int(seconds)}s",
            *command,
        ]
    return command


def mic_calibration_error_result(
    *,
    error: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_mic_calibration_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": error,
    }


def mic_calibration_result(
    *,
    source: str,
    recorded_path: Any | None,
    summary: dict[str, Any],
    recommended_runtime: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_mic_calibration_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": summary.get("files_analyzed", 0) > 0,
        "source": source,
        "recorded_path": str(recorded_path) if recorded_path else None,
        "summary": summary,
        "recommended_runtime": recommended_runtime,
        "applied": False,
    }


def recording_state(
    *,
    pid: int,
    audio_path: Any,
    log_path: Any,
    profile: str,
    started_at: str,
    max_seconds_value: int,
    schema_prefix: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_recording_v1",
        "pid": int(pid),
        "audio": str(audio_path),
        "log": str(log_path),
        "profile": profile,
        "started_at": started_at,
        "max_seconds": int(max_seconds_value),
    }


def stop_inactive_result(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_stop_v1",
        "version": version,
        "generated_at": generated_at,
        "stopped": False,
        "message": "recording was not active",
    }


def stopped_recording_result(
    state: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    result = dict(state)
    result.update({
        "schema": f"{schema_prefix}_dictation_stop_v1",
        "version": version,
        "generated_at": generated_at,
        "stopped": True,
    })
    return result


def toggle_result(
    *,
    action: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
    recording: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    insert: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
    journal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": f"{schema_prefix}_dictation_toggle_v1",
        "version": version,
        "generated_at": generated_at,
        "action": action,
    }
    if recording is not None:
        result["recording"] = recording
    if transcript is not None:
        result["transcript"] = transcript
    if insert is not None:
        result["insert"] = insert
    if status is not None:
        result["status"] = status
    if journal is not None:
        result["journal"] = journal
    return result


def stale_missing_audio_transcript(schema_prefix: str, version: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_transcript_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "error": "stale recording has no audio path",
    }


def default_replacements() -> list[dict[str, Any]]:
    return [
        {
            "id": "agents-md-compact",
            "enabled": True,
            "type": "regex",
            "pattern": r"\bagents[.,]\s*(?:amd|мд|md)\b",
            "to": "AGENTS.md",
            "flags": ["ignorecase"],
            "description": "Normalize common Whisper variants of AGENTS.md",
        },
        {
            "id": "agents-md-spaced",
            "enabled": True,
            "type": "regex",
            "pattern": r"\bagents\s+(?:мд|md)\b",
            "to": "AGENTS.md",
            "flags": ["ignorecase"],
            "description": "Normalize spaced AGENTS.md",
        },
        {
            "id": "russian-punctuation-term",
            "enabled": True,
            "type": "regex",
            "pattern": r"\b(знак(?:и|ов|ами|ах)?\s+)припинани(я|й|ям|ями|ях)\b",
            "to": r"\1препинани\2",
            "flags": ["ignorecase"],
            "description": "Fix common Russian STT error for punctuation term",
        },
        {
            "id": "abyss-machine-name",
            "enabled": True,
            "type": "regex",
            "pattern": r"\b(?:аббис|абис|эббис|эбис)\s+машин(?:а|ы|е|ой|у|ом)?\b",
            "to": "abyss-machine",
            "flags": ["ignorecase"],
            "description": "Normalize common Russian STT variants of abyss-machine",
        },
        {
            "id": "neuroprocessor",
            "enabled": True,
            "type": "regex",
            "pattern": r"\bнейро\s+процессор(а|е|ом|ы|ов|ам|ами|ах)?\b",
            "to": r"нейропроцессор\1",
            "flags": ["ignorecase"],
            "description": "Keep нейропроцессор as one word",
        },
        {
            "id": "otladka",
            "enabled": True,
            "type": "regex",
            "pattern": r"\bоткладк(а|и|ой|е|у|ами|ах)\b",
            "to": r"отладк\1",
            "flags": ["ignorecase"],
            "description": "Fix отладка/отладками when Whisper hears откладка",
        },
    ]


def default_replacements_document(schema_prefix: str = "abyss_machine", version: str = "") -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_replacements_v1",
        "version": version,
        "items": default_replacements(),
    }


def replacement_flags(item: dict[str, Any]) -> int:
    flags = 0
    if "ignorecase" in item.get("flags", []):
        flags |= re.IGNORECASE
    return flags


def validate_replacements_document(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    items = doc.get("items")
    if not isinstance(items, list):
        return ["items must be a list"]
    for item in items:
        if not isinstance(item, dict):
            errors.append("replacement item must be an object")
            continue
        kind = item.get("type")
        if kind not in {"literal", "regex"}:
            errors.append("replacement type must be literal or regex")
        if not item.get("id"):
            errors.append("replacement id is required")
        if kind == "regex":
            try:
                re.compile(str(item.get("pattern", "")), replacement_flags(item))
            except re.error as exc:
                errors.append(f"replacement regex {item.get('id') or '<unknown>'} is invalid: {exc}")
    return errors


def normalize_replacements_document(
    doc: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    updated_at: str,
    updated_by: str,
) -> dict[str, Any]:
    errors = validate_replacements_document(doc)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "schema": f"{schema_prefix}_dictation_replacements_v1",
        "version": version,
        "updated_at": updated_at,
        "updated_by": updated_by,
        "items": doc.get("items", []),
    }


def apply_replacements(text: str, items: list[Any]) -> tuple[str, list[str]]:
    fixed = text
    applied: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not bool_value(item.get("enabled"), True):
            continue
        kind = item.get("type")
        before = fixed
        if kind == "literal":
            source = str(item.get("from", ""))
            target = str(item.get("to", ""))
            if not source:
                continue
            if bool_value(item.get("case_sensitive"), False):
                fixed = fixed.replace(source, target)
            else:
                fixed = re.sub(re.escape(source), target, fixed, flags=re.IGNORECASE)
        elif kind == "regex":
            pattern = str(item.get("pattern", ""))
            target = str(item.get("to", ""))
            if not pattern:
                continue
            fixed = re.sub(pattern, target, fixed, flags=replacement_flags(item))
        if fixed != before:
            applied.append(str(item.get("id", "unnamed")))
    return fixed, applied


def replacements_list_document(
    doc: dict[str, Any],
    *,
    path: str,
    exists: bool,
    generated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_replacements_v1",
        "version": version,
        "generated_at": generated_at,
        "path": path,
        "exists": exists,
        "load_error": doc.get("_load_error"),
        "items": doc.get("items", []),
    }


def replacements_test_document(
    text: str,
    doc: dict[str, Any],
    *,
    generated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    fixed, applied = apply_replacements(text, list(doc.get("items", [])))
    return {
        "schema": f"{schema_prefix}_dictation_replacements_test_v1",
        "version": version,
        "generated_at": generated_at,
        "input": text,
        "output": fixed,
        "changed": fixed != text,
        "applied": applied,
    }


def replacement_id_from_text(text: str, fallback_token: Any = None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ._-]+", "-", text.strip().lower()).strip("-")
    fallback = f"replacement-{fallback_token}" if fallback_token is not None else "replacement"
    return slug[:48] or fallback


def build_replacement_item(kind: str, source: str, target: str, item_id: str, ignore_case: bool = True) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": item_id,
        "enabled": True,
        "type": kind,
        "to": target,
    }
    if kind == "literal":
        item["from"] = source
        item["case_sensitive"] = not ignore_case
    elif kind == "regex":
        re.compile(source, re.IGNORECASE if ignore_case else 0)
        item["pattern"] = source
        item["flags"] = ["ignorecase"] if ignore_case else []
    else:
        raise ValueError("kind must be literal or regex")
    return item


def apply_common_transcript_fixes(
    text: str,
    options: dict[str, Any],
    replacements_doc: dict[str, Any] | None = None,
) -> tuple[str, bool, list[str]]:
    if not bool_value(options.get("text_fixes"), True):
        return text, False, []
    fixed, applied = apply_replacements(text, list((replacements_doc or {}).get("items", [])))
    return fixed, fixed != text, applied


def capitalize_sentence_starts(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return match.group(1) + match.group(2).upper()

    return re.sub(r"(^|[.!?]\s+)([а-яё])", repl, text)


def restore_sparse_russian_punctuation(text: str, options: dict[str, Any]) -> tuple[str, bool]:
    style = str(options.get("punctuation_style", "normal")).lower()
    if style not in PUNCTUATION_STYLES:
        style = "normal"
    if style == "off" or not bool_value(options.get("smart_punctuation"), True):
        return text, False

    stripped = text.strip()
    if len(stripped) < 120:
        return text, False
    if len(re.findall(r"[,.!?;:]", stripped)) >= 2:
        return text, False

    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    body = re.sub(r"\s+", " ", stripped)
    body = re.sub(
        r"\s+(котор(?:ый|ая|ое|ые|ую|ого|ому|ым|ых|ыми|ой|ою)\b)",
        r", \1",
        body,
        flags=re.IGNORECASE,
    )

    def marker_repl(match: re.Match[str]) -> str:
        marker = match.group(1)
        prefix = body[: match.start()]
        last_sentence = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"))
        since_sentence = len(prefix) - last_sentence - 1
        low = marker.lower()
        if low == "но" and since_sentence >= 25:
            return ", " + marker
        if style == "soft":
            if low in {"поэтому", "хотя", "если"} and since_sentence >= 35:
                return ", " + marker
            if low in {"при этом", "то есть"} and since_sentence >= 30:
                return ", " + marker
            if low.startswith("вот") and since_sentence >= 45:
                return ", " + marker
            return match.group(0)
        if low.startswith("вот") and since_sentence >= 30:
            return ". " + marker[0].upper() + marker[1:]
        if low == "прям" and since_sentence >= 55:
            return ". " + marker[0].upper() + marker[1:]
        if since_sentence >= 55:
            return ". " + marker[0].upper() + marker[1:]
        return match.group(0)

    markers = r"\s+(сейчас|поэтому|хотя|при этом|то есть|если|но|прям(?=\s+вот)|вот\s+(?:она|это|так))\b"
    if style == "soft":
        markers = r"\s+(поэтому|хотя|при этом|то есть|если|но|вот\s+(?:она|это|так))\b"
    body = re.sub(markers, marker_repl, body, flags=re.IGNORECASE)
    body = capitalize_sentence_starts(body)
    return leading + body + trailing, body != stripped


def restore_russian_dash_punctuation(text: str, options: dict[str, Any]) -> tuple[str, bool]:
    style = str(options.get("punctuation_style", "normal")).lower()
    if style not in PUNCTUATION_STYLES:
        style = "normal"
    if style == "off" or not bool_value(options.get("smart_punctuation"), True):
        return text, False

    stripped = text.strip()
    if len(stripped) < 24:
        return text, False

    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    body = text[len(leading) : len(text) - len(trailing)]
    summary_markers = (
        r"это\s+(?:ключ|важно|главное|критично|основа|центр|приоритет|риск|проблема|цель|необходимо|нужно|нормально|плохо|хорошо)"
    )
    comma_before_summary = re.compile(r",\s+(?=" + summary_markers + r"\b)", flags=re.IGNORECASE)
    intro_tail = re.compile(r"\b(?:думаю|считаю|кажется|вижу|знаю|понимаю|помню|ощущаю|говорю|скажу)$", flags=re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        prefix = body[: match.start()]
        last_boundary = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"), prefix.rfind(";"), prefix.rfind(":"))
        current_clause = prefix[last_boundary + 1 :].strip()
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", current_clause)
        if len(words) < 4 or len(current_clause) < 18:
            return match.group(0)
        if len(words) <= 6 and intro_tail.search(current_clause):
            return match.group(0)
        return " - "

    fixed = comma_before_summary.sub(repl, body)
    return leading + fixed + trailing, fixed != body


def ensure_final_punctuation(text: str, options: dict[str, Any]) -> tuple[str, bool]:
    if not bool_value(options.get("final_punctuation"), True):
        return text, False
    stripped = text.rstrip()
    if not stripped:
        return text, False
    trailing_ws = text[len(stripped) :]
    closing = "\"')]}»”’"
    index = len(stripped) - 1
    while index >= 0 and stripped[index] in closing:
        index -= 1
    if index < 0:
        return text, False
    terminal = ".!?…:;"
    if stripped[index] in terminal:
        return text, False
    if stripped[index] == ",":
        normalized = f"{stripped[:index]}.{stripped[index + 1:]}"
        return normalized + trailing_ws, True
    return stripped + "." + trailing_ws, True


def ensure_final_space(text: str, options: dict[str, Any]) -> tuple[str, bool]:
    if not bool_value(options.get("final_space"), True):
        return text, False
    if not text:
        return text, False
    if text.endswith((" ", "\n", "\t")):
        return text, False
    return text + " ", True


def detect_intent(text: str, config: dict[str, Any], schema_prefix: str = "abyss_machine") -> dict[str, Any]:
    settings = config.get("command_intent", {}) if isinstance(config.get("command_intent"), dict) else {}
    result: dict[str, Any] = {
        "schema": f"{schema_prefix}_dictation_intent_v1",
        "type": "dictation",
        "triggered": False,
        "execution": "none",
    }
    if not bool_value(settings.get("enabled"), True):
        result["reason"] = "disabled"
        return result

    stripped = text.strip()
    triggers = settings.get("trigger_phrases")
    if not isinstance(triggers, list):
        triggers = ["команда"]
    triggers = sorted([str(item).strip() for item in triggers if str(item).strip()], key=len, reverse=True)
    if not triggers:
        result["reason"] = "no-triggers"
        return result

    requires_prefix = bool_value(settings.get("requires_prefix"), True)
    if not requires_prefix:
        result["reason"] = "non-prefix-intent-disabled"
        return result

    for trigger in triggers:
        pattern = r"^\s*(?P<trigger>" + re.escape(trigger) + r")\s*(?:[,.:;!?]\s*)?(?P<payload>.+?)\s*$"
        match = re.match(pattern, stripped, flags=re.IGNORECASE)
        if not match:
            continue
        payload = match.group("payload").strip()
        if not payload:
            continue
        return {
            "schema": f"{schema_prefix}_dictation_intent_v1",
            "type": "command",
            "triggered": True,
            "trigger": match.group("trigger"),
            "payload": payload,
            "strip_trigger": bool_value(settings.get("strip_trigger"), True),
            "execution": str(settings.get("execution") or "detect-only"),
        }

    result["reason"] = "no-trigger-prefix"
    return result


def intent_test_document(
    text: str,
    config: dict[str, Any],
    *,
    generated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_intent_test_v1",
        "version": version,
        "generated_at": generated_at,
        "input": text,
        "intent": detect_intent(text, config, schema_prefix),
    }


def postprocess_transcript_data(
    data: dict[str, Any],
    profile: dict[str, Any],
    *,
    config: dict[str, Any],
    replacements_doc: dict[str, Any],
    schema_prefix: str,
) -> dict[str, Any]:
    if not data.get("ok") or not isinstance(data.get("text"), str):
        return data
    result = dict(data)
    options = dict(profile.get("postprocess", {}))
    original = str(result["text"])
    processed, fixes_changed, applied_replacements = apply_common_transcript_fixes(original, options, replacements_doc)
    processed, smart_changed = restore_sparse_russian_punctuation(processed, options)
    processed, dash_changed = restore_russian_dash_punctuation(processed, options)
    capitalized = capitalize_sentence_starts(processed)
    capitalization_changed = capitalized != processed
    processed = capitalized
    processed, punctuation_changed = ensure_final_punctuation(processed, options)
    processed, space_changed = ensure_final_space(processed, options)
    if fixes_changed or smart_changed or dash_changed or capitalization_changed or punctuation_changed or space_changed:
        result["raw_text"] = original
        result["text"] = processed
        postprocess = result.get("postprocess") or {}
        if fixes_changed:
            postprocess["text_fixes"] = True
            postprocess["replacements"] = applied_replacements
        if smart_changed:
            postprocess["smart_punctuation"] = True
        if dash_changed:
            postprocess["dash_punctuation"] = True
        if capitalization_changed:
            postprocess["capitalization"] = True
        if punctuation_changed:
            postprocess["final_punctuation"] = True
        if space_changed:
            postprocess["final_space"] = True
        result["postprocess"] = postprocess
    result["intent"] = detect_intent(str(result.get("text", "")), config, schema_prefix)
    return result


def journal_entry_id(result: dict[str, Any], audio: Any, generated_at: str) -> str:
    generated = str(result.get("generated_at") or generated_at)
    stamp = re.sub(r"[^0-9T+-]", "", generated)[:20] or dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    audio_name = Path(str(audio)).stem if audio else "no-audio"
    digest_src = json.dumps(
        {
            "generated_at": generated,
            "action": result.get("action"),
            "audio": str(audio or ""),
            "text": (result.get("transcript") or {}).get("text") if isinstance(result.get("transcript"), dict) else "",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha1(digest_src.encode("utf-8")).hexdigest()[:10]
    return f"{stamp}-{audio_name}-{digest}"


def journal_event(
    result: dict[str, Any],
    *,
    include_failed: bool,
    audio_metadata: dict[str, Any],
    event_id: str,
    generated_at: str,
    paths: dict[str, str],
    schema_prefix: str,
    version: str,
) -> dict[str, Any] | None:
    transcript = result.get("transcript")
    if not isinstance(transcript, dict):
        return None
    if not transcript.get("ok") and not include_failed:
        return None
    recording = result.get("recording") if isinstance(result.get("recording"), dict) else {}
    insert = result.get("insert") if isinstance(result.get("insert"), dict) else None
    profile = transcript.get("profile") if isinstance(transcript.get("profile"), dict) else {}
    postprocess = transcript.get("postprocess") if isinstance(transcript.get("postprocess"), dict) else {}
    return {
        "schema": f"{schema_prefix}_dictation_transcript_event_v1",
        "version": version,
        "id": event_id,
        "generated_at": generated_at,
        "source_result_generated_at": result.get("generated_at"),
        "action": result.get("action"),
        "ok": bool(transcript.get("ok")),
        "text": transcript.get("text") if isinstance(transcript.get("text"), str) else "",
        "raw_text": transcript.get("raw_text") if isinstance(transcript.get("raw_text"), str) else None,
        "error": transcript.get("error"),
        "profile": {
            "requested": recording.get("profile") if isinstance(recording, dict) else None,
            "selected": profile.get("name"),
            "device": profile.get("device"),
            "model_id": profile.get("model_id"),
            "model_dir": profile.get("model_dir"),
            "num_beams": transcript.get("num_beams"),
            "via": transcript.get("via"),
        },
        "timing": {
            "stt_elapsed_sec": transcript.get("elapsed_sec"),
            "client_elapsed_sec": transcript.get("client_elapsed_sec"),
            "server_timings": transcript.get("timings") if isinstance(transcript.get("timings"), dict) else None,
        },
        "postprocess": postprocess,
        "intent": transcript.get("intent") if isinstance(transcript.get("intent"), dict) else None,
        "audio": audio_metadata,
        "recording": {
            "started_at": recording.get("started_at") if isinstance(recording, dict) else None,
            "stopped_at": recording.get("generated_at") if isinstance(recording, dict) else None,
            "max_seconds": recording.get("max_seconds") if isinstance(recording, dict) else None,
            "log": recording.get("log") if isinstance(recording, dict) else None,
        },
        "insert": {
            "requested": bool(insert is not None),
            "ok": insert.get("ok") if isinstance(insert, dict) else None,
            "method": insert.get("method") if isinstance(insert, dict) else None,
            "stderr": insert.get("stderr") if isinstance(insert, dict) else None,
            "attempts": insert.get("attempts") if isinstance(insert, dict) else None,
        },
        "paths": paths,
    }


def journal_markdown(event: dict[str, Any], include_header: bool, day: str | None = None) -> str:
    generated = str(event.get("generated_at", ""))
    action = str(event.get("action", "dictation"))
    status = "ok" if event.get("ok") else "error"
    profile = event.get("profile") if isinstance(event.get("profile"), dict) else {}
    timing = event.get("timing") if isinstance(event.get("timing"), dict) else {}
    audio = event.get("audio") if isinstance(event.get("audio"), dict) else {}
    insert = event.get("insert") if isinstance(event.get("insert"), dict) else {}
    postprocess = event.get("postprocess") if isinstance(event.get("postprocess"), dict) else {}

    parts: list[str] = []
    if include_header:
        day = day or dt.datetime.now(dt.timezone.utc).astimezone().strftime("%Y-%m-%d")
        parts.append(f"# Dictation Journal - {day}\n\n")
    parts.append(f"## {generated} - {action} - {status}\n\n")
    parts.append(f"- id: `{event.get('id')}`\n")
    parts.append(f"- profile: `{profile.get('selected') or profile.get('requested')}` on `{profile.get('device')}` via `{profile.get('via')}`\n")
    parts.append(f"- timing: stt=`{timing.get('stt_elapsed_sec')}`s client=`{timing.get('client_elapsed_sec')}`s\n")
    parts.append(f"- insert: requested=`{insert.get('requested')}` ok=`{insert.get('ok')}` method=`{insert.get('method')}`\n")
    parts.append(f"- audio: `{audio.get('path')}` duration=`{audio.get('duration_sec')}`s size=`{audio.get('size_bytes')}`\n")
    if postprocess:
        parts.append(f"- postprocess: `{', '.join(sorted(str(key) for key in postprocess.keys()))}`\n")
    if event.get("error"):
        parts.append(f"- error: `{event.get('error')}`\n")
    text = str(event.get("text") or "")
    parts.append("\nText:\n\n")
    parts.append(text.rstrip() + "\n\n")
    raw = event.get("raw_text")
    if isinstance(raw, str) and raw.strip() and raw.strip() != text.strip():
        parts.append("Raw:\n\n")
        parts.append(raw.rstrip() + "\n\n")
    return "".join(parts)
