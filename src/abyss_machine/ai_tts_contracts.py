from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


VALID_WORKLOAD_CLASSES = {"probe", "light", "medium", "heavy", "sustained"}
TTS_MODEL_REQUIRED_FILES = (
    "config.json",
    "model.safetensors",
    "speech_tokenizer/config.json",
    "speech_tokenizer/model.safetensors",
)
TTS_OPENVINO_REQUIRED_FILES = (
    "talker.xml",
    "talker.bin",
    "code_predictor.xml",
    "code_predictor.bin",
    "text_model.xml",
    "text_model.bin",
    "codec_embedding.xml",
    "codec_embedding.bin",
    "cp_codec_embedding.xml",
    "cp_codec_embedding.bin",
    "speech_tokenizer/speech_decoder.xml",
    "speech_tokenizer/speech_decoder.bin",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
)
TTS_RUNTIME_PARAMETER_KEYS = (
    "use_kv_cache",
    "use_cp_kv_cache",
    "max_kv_len",
    "max_speaker_frames",
    "max_decoder_frames",
    "max_new_tokens",
    "temperature",
    "top_k",
    "top_p",
    "repetition_penalty",
    "model_type",
    "ov_dir",
    "adapter_src",
    "cp_device",
    "instruct",
    "no_sample",
)
TTS_SYNTH_OPTION_KEYS = (
    "max_new_tokens",
    "temperature",
    "top_k",
    "top_p",
    "repetition_penalty",
    "no_sample",
)
TTS_BABELVOX_OPTION_KEYS = (
    "use_kv_cache",
    "use_cp_kv_cache",
    "max_kv_len",
    "max_speaker_frames",
    "max_decoder_frames",
    "max_talker_seq",
    "max_cp_seq",
    "max_new_tokens",
    "temperature",
    "top_k",
    "top_p",
    "repetition_penalty",
)


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def profile_python(profile: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    config = config or {}
    return str(profile.get("python") or config.get("python") or "")


def profile_slug(profile_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", profile_name).strip("-") or "default"


def profile_declared_class(profile: dict[str, Any], valid_classes: set[str] | None = None) -> str:
    declared = str(profile.get("declared_class") or "heavy")
    return declared if declared in (valid_classes or VALID_WORKLOAD_CLASSES) else "heavy"


def model_artifacts(
    model_path: Any,
    *,
    exists: bool = False,
    required_files: dict[str, bool] | None = None,
    file_summary: dict[str, Any] | None = None,
    read_only_source: bool = False,
) -> dict[str, Any]:
    if model_path is None:
        return {"path": None, "exists": False, "complete": False, "read_only_source": False}
    if str(model_path) == "host-managed":
        return {"path": "host-managed", "exists": False, "complete": False, "read_only_source": False, "host_managed": True}
    path = Path(str(model_path)).expanduser()
    lowered = path.name.lower()
    model_type = None
    if "customvoice" in lowered:
        model_type = "custom_voice"
    elif "voicedesign" in lowered:
        model_type = "voice_design"
    elif "base" in lowered:
        model_type = "base"
    size_class = "1.7B" if "1.7b" in lowered else "0.6B" if "0.6b" in lowered else None
    files = required_files if isinstance(required_files, dict) else {item: False for item in TTS_MODEL_REQUIRED_FILES}
    return {
        "path": str(path),
        "exists": exists,
        "complete": exists and all(files.values()),
        "model_type": model_type,
        "size_class": size_class,
        "required_files": files,
        "file_summary": file_summary or {},
        "read_only_source": read_only_source,
    }


def openvino_artifacts(
    ov_dir: Any,
    *,
    exists: bool = False,
    required_files: dict[str, bool] | None = None,
    file_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if ov_dir is None:
        return {"path": None, "exists": False, "complete": False}
    path = Path(str(ov_dir)).expanduser()
    files = required_files if isinstance(required_files, dict) else {item: False for item in TTS_OPENVINO_REQUIRED_FILES}
    return {
        "path": str(path),
        "exists": exists,
        "complete": exists and all(files.values()),
        "required_files": files,
        "file_summary": file_summary or {},
        "host_managed": True,
        "read_only_source": False,
    }


def module_present(modules: dict[str, Any], module: str) -> bool:
    item = modules.get(module)
    return bool(item.get("present")) if isinstance(item, dict) else False


def profile_status(
    *,
    name: str,
    profile: dict[str, Any],
    inventory: dict[str, Any],
    config: dict[str, Any],
    model: dict[str, Any],
    openvino_model: dict[str, Any] | None,
    adapter_ready: bool,
    runtime_python: str,
    valid_workload_classes: set[str] | None = None,
) -> dict[str, Any]:
    profile_module_statuses = inventory.get("runtime", {}).get("profile_python_modules", {})
    profile_module_status = profile_module_statuses.get(name) if isinstance(profile_module_statuses, dict) else None
    if not isinstance(profile_module_status, dict):
        profile_module_status = inventory.get("runtime", {}).get("python_modules", {})
    modules = profile_module_status.get("modules", {}) if isinstance(profile_module_status, dict) else {}
    binaries = inventory.get("runtime", {}).get("binaries", {})
    engine = str(profile.get("engine") or "unknown")
    enabled = bool(profile.get("enabled", True))
    runtime_ready = False
    synth_supported = False
    runtime_reason = None

    if engine == "babelvox":
        runtime_ready = module_present(modules, "babelvox")
        synth_supported = runtime_ready
        runtime_reason = None if runtime_ready else "python module babelvox is not installed"
    elif engine == "piper":
        runtime_ready = bool(binaries.get("piper"))
        synth_supported = runtime_ready and bool(model.get("exists"))
        runtime_reason = None if runtime_ready else "piper binary is not installed"
    elif engine == "qwen3_tts_openvino":
        runtime_ready = bool(
            module_present(modules, "openvino")
            and module_present(modules, "transformers")
            and module_present(modules, "pydantic")
            and module_present(modules, "soundfile")
            and module_present(modules, "numpy")
            and adapter_ready
        )
        synth_supported = bool(runtime_ready and openvino_model and openvino_model.get("complete"))
        if not module_present(modules, "openvino"):
            runtime_reason = "python module openvino is not installed"
        elif not module_present(modules, "transformers"):
            runtime_reason = "python module transformers is not installed"
        elif not module_present(modules, "pydantic"):
            runtime_reason = "python module pydantic is not installed"
        elif not module_present(modules, "soundfile"):
            runtime_reason = "python module soundfile is not installed"
        elif not module_present(modules, "numpy"):
            runtime_reason = "python module numpy is not installed"
        elif not adapter_ready:
            runtime_reason = "OpenVINO Qwen3-TTS adapter source is missing"
        elif not (openvino_model and openvino_model.get("complete")):
            runtime_reason = "OpenVINO Qwen3-TTS IR is incomplete"
        else:
            runtime_reason = None
    elif engine == "qwen_tts_reference":
        runtime_ready = module_present(modules, "qwen_tts")
        synth_supported = runtime_ready
        runtime_reason = None if runtime_ready else "python module qwen_tts is not installed"
    else:
        runtime_reason = f"unknown TTS engine: {engine}"

    if not enabled:
        status = "disabled"
    elif engine in {"qwen3_tts_openvino", "qwen_tts_reference", "piper"} and not model.get("complete") and not model.get("exists"):
        status = "model-missing"
    elif engine == "qwen3_tts_openvino" and model.get("complete") and not (openvino_model and openvino_model.get("exists")):
        status = "model-ready-adapter-missing"
    elif not runtime_ready:
        status = "runtime-missing"
    elif not synth_supported:
        status = "adapter-missing"
    else:
        status = "executable"

    return {
        "profile": name,
        "enabled": enabled,
        "status": status,
        "engine": engine,
        "description": profile.get("description"),
        "declared_class": profile_declared_class(profile, valid_workload_classes),
        "device": profile.get("device"),
        "language": profile.get("language") or config.get("language"),
        "speaker": profile.get("speaker"),
        "precision": profile.get("precision"),
        "talker_buckets": profile.get("talker_buckets"),
        "runtime_parameters": {
            key: profile.get(key)
            for key in TTS_RUNTIME_PARAMETER_KEYS
            if key in profile
        },
        "model": model,
        "openvino": openvino_model,
        "runtime": {
            "ready": runtime_ready,
            "synth_supported": synth_supported,
            "reason": runtime_reason,
            "python": runtime_python,
            "python_ok": profile_module_status.get("ok") if isinstance(profile_module_status, dict) else None,
        },
        "policy": {
            "read_only_source": bool(model.get("read_only_source")),
            "host_layer_mutates_stack": False,
        },
    }


def denied_result(base_result: dict[str, Any], profile: str) -> dict[str, Any]:
    result = dict(base_result)
    result["profile"] = profile
    result["non_claims"] = [
        "Policy-denied TTS commands do not execute model inference.",
        "When wrapped by ai tts eval, the denial may be recorded as eval evidence with policy_denied=true.",
        "Use --force only for explicit operator-controlled validation.",
    ]
    return result


def result_error(result: dict[str, Any]) -> str | None:
    error = result.get("error")
    if error:
        return str(error)
    if result.get("policy_denied"):
        reasons = result.get("reasons") if isinstance(result.get("reasons"), list) else []
        reason_text = ",".join(str(item) for item in reasons if item)
        return f"policy_denied:{reason_text}" if reason_text else "policy_denied"
    if result.get("ok") is False:
        return "synthesis_failed"
    return None


def success_index_entry(data: dict[str, Any], path: Path) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    return {
        "profile": data.get("profile"),
        "generated_at": data.get("generated_at"),
        "path": str(path),
        "summary": summary,
        "result_output": result.get("output"),
        "schema": data.get("schema"),
    }


def server_socket_missing_result(socket_path: Any) -> dict[str, Any]:
    return {"ok": False, "error": "server socket missing", "socket": str(socket_path)}


def server_transport_error_result(error: Any, socket_path: Any) -> dict[str, Any]:
    return {"ok": False, "error": str(error), "socket": str(socket_path)}


def parse_server_response(raw: str, socket_path: Any) -> dict[str, Any]:
    raw = str(raw or "").strip()
    if not raw:
        return {"ok": False, "error": "server returned empty response", "socket": str(socket_path)}
    try:
        data = json.loads(raw.splitlines()[-1])
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"invalid server JSON: {exc}",
            "stdout_tail": raw[-1000:],
            "socket": str(socket_path),
        }
    if isinstance(data, dict):
        return data
    return {"ok": False, "error": "server response is not an object", "socket": str(socket_path)}


def parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = str(stdout or "").strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            return data if isinstance(data, dict) else None
        marker = stdout.rfind("\n{")
        if marker < 0:
            return None
        try:
            data = json.loads(stdout[marker + 1 :])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def server_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    socket_path: Any,
    socket_exists: bool,
    ping: dict[str, Any],
    service: str,
    latest_path: Any,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_server_status_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(ping.get("ok")),
        "socket": str(socket_path),
        "socket_exists": bool(socket_exists),
        "ping": ping,
        "service": service,
        "paths": {
            "latest": str(latest_path),
        },
        "policy": {
            "transport": "unix_socket_json_line",
            "host_layer_mutates_stack": False,
        },
    }


def server_stop_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    socket_path: Any,
    socket_exists_after: bool,
    response: dict[str, Any],
    service: str,
    latest_path: Any,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_server_stop_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(response.get("ok")),
        "socket": str(socket_path),
        "socket_exists_after": bool(socket_exists_after),
        "response": response,
        "service": service,
        "paths": {
            "latest": str(latest_path),
        },
        "policy": {
            "transport": "unix_socket_json_line",
            "host_layer_mutates_stack": False,
        },
    }


def voices_from_profiles(profiles: dict[str, Any]) -> list[dict[str, Any]]:
    voices: list[dict[str, Any]] = []
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        voices.append({
            "profile": name,
            "status": profile.get("status"),
            "engine": profile.get("engine"),
            "speaker": profile.get("speaker"),
            "language": profile.get("language"),
            "device": profile.get("device"),
            "precision": profile.get("precision"),
            "declared_class": profile.get("declared_class"),
            "description": profile.get("description"),
        })
    return voices


def voices_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    default_profile: Any,
    voices: list[dict[str, Any]],
    server: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_voices_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(voices),
        "default_profile": default_profile,
        "voices": voices,
        "server": server,
        "policy": {
            "facts_only": True,
            "voice_list_is_profile_contract": True,
        },
    }


def server_state_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
    socket_path: Any,
    pid: int,
    load_sec: float,
    status: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_server_state_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "profile": profile,
        "engine": "qwen3_tts_openvino",
        "socket": str(socket_path),
        "pid": pid,
        "load_sec": load_sec,
        "model": status.get("model"),
        "openvino": status.get("openvino"),
        "device": status.get("device"),
        "precision": status.get("precision"),
        "policy": {
            "host_layer_mutates_stack": False,
            "transport": "unix_socket_json_line",
        },
    }


def server_synth_error_result(error: str, profile: str, **extra: Any) -> dict[str, Any]:
    result = {"ok": False, "error": error, "profile": profile}
    result.update(extra)
    return result


def server_synth_success_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
    server_pid: int,
    server_started_at: str,
    server_load_sec: float,
    device: Any,
    precision: Any,
    output: Any,
    text_chars: int,
    synth_sec: float,
    sample_rate: int,
    samples: int,
    audio_sec: float | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema": _schema(schema_prefix, "ai_tts_server_synth_v1"),
        "version": version,
        "generated_at": generated_at,
        "profile": profile,
        "engine": "qwen3_tts_openvino",
        "server_pid": server_pid,
        "server_started_at": server_started_at,
        "server_load_sec": server_load_sec,
        "warm": True,
        "device": device,
        "precision": precision,
        "output": str(output),
        "text_chars": int(text_chars),
        "synth_sec": synth_sec,
        "wall_sec": synth_sec,
        "sample_rate": int(sample_rate),
        "samples": int(samples),
        "audio_sec": audio_sec,
        "rtf": round(float(synth_sec) / float(audio_sec), 4) if audio_sec else None,
    }


def synth_unknown_profile_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_synth_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "profile": profile,
        "error": "unknown TTS profile",
    }


def synth_empty_text_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_synth_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "profile": profile,
        "error": "text is empty",
    }


def synth_base_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
    engine: str,
    declared_class: str,
    device: Any,
    model: Any,
    text_chars: int,
    output: Any,
    cache_dir: Any,
    allow_download: bool,
    policy_gate: dict[str, Any],
    profile_status: dict[str, Any],
    output_under_host_state: bool,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_synth_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "profile": profile,
        "engine": engine,
        "declared_class": declared_class,
        "device": device,
        "model": model,
        "text_chars": int(text_chars),
        "output": str(output),
        "cache_dir": str(cache_dir),
        "allow_download": bool(allow_download),
        "policy_gate": policy_gate,
        "profile_status": profile_status,
        "policy": {
            "host_layer_mutates_stack": False,
            "output_under_host_state": bool(output_under_host_state),
        },
    }


def synth_options(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: profile.get(key) for key in TTS_SYNTH_OPTION_KEYS if key in profile}


def babelvox_synth_options(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: profile.get(key) for key in TTS_BABELVOX_OPTION_KEYS if key in profile}


def babelvox_synth_script() -> str:
    return r'''
import json
import os
import sys
import time

saved_stdout = os.dup(1)
os.dup2(2, 1)

def emit(data):
    os.write(saved_stdout, json.dumps(data, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")
    os.close(saved_stdout)

text, output, device, precision, buckets_json, cache_dir, language, options_json = sys.argv[1:9]
try:
    import soundfile as sf
    from babelvox import BabelVox
    buckets = json.loads(buckets_json) if buckets_json else None
    options = json.loads(options_json) if options_json else {}
    kwargs = {
        "device": device,
        "precision": precision,
        "cache_dir": cache_dir,
        "use_kv_cache": bool(options.get("use_kv_cache", False)),
        "use_cp_kv_cache": bool(options.get("use_cp_kv_cache", True)),
    }
    if buckets:
        kwargs["talker_buckets"] = buckets
    for key in ("max_kv_len", "max_speaker_frames", "max_decoder_frames", "max_talker_seq", "max_cp_seq"):
        if options.get(key) is not None:
            kwargs[key] = int(options[key])
    load_started = time.perf_counter()
    tts = BabelVox(**kwargs)
    load_sec = time.perf_counter() - load_started
    synth_started = time.perf_counter()
    generate_kwargs = {"language": language}
    for key in ("max_new_tokens", "temperature", "top_k", "top_p", "repetition_penalty"):
        if options.get(key) is not None:
            generate_kwargs[key] = options[key]
    wav, sr = tts.generate(text, **generate_kwargs)
    synth_sec = time.perf_counter() - synth_started
    sf.write(output, wav, sr)
    emit({
        "ok": True,
        "engine": "babelvox",
        "options": options,
        "load_sec": round(load_sec, 3),
        "synth_sec": round(synth_sec, 3),
        "sample_rate": int(sr),
        "samples": int(len(wav)),
        "audio_sec": round(float(len(wav)) / float(sr), 3) if sr else None,
    })
except Exception as exc:
    emit({"ok": False, "engine": "babelvox", "error": repr(exc)})
    raise SystemExit(1)
'''


def babelvox_synth_command(
    *,
    python: str,
    profile: dict[str, Any],
    config: dict[str, Any],
    text: str,
    output: Any,
    cache_dir: Any,
) -> list[str]:
    return [
        python,
        "-c",
        babelvox_synth_script(),
        text,
        str(output),
        str(profile.get("device") or "CPU"),
        str(profile.get("precision") or "int8"),
        json.dumps(profile.get("talker_buckets") or []),
        str(cache_dir),
        str(profile.get("language") or config.get("language") or "Russian"),
        json.dumps(babelvox_synth_options(profile), sort_keys=True),
    ]


def qwen3_openvino_synth_script() -> str:
    return r'''
import asyncio
import json
import os
import sys
import time
from pathlib import Path

saved_stdout = os.dup(1)
os.dup2(2, 1)

def emit(data):
    os.write(saved_stdout, json.dumps(data, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")
    os.close(saved_stdout)

(
    adapter_src,
    ov_dir,
    mode,
    text,
    output,
    device,
    cp_device,
    speaker,
    language,
    instruct,
    options_json,
) = sys.argv[1:12]

try:
    sys.path.insert(0, adapter_src)
    import soundfile as sf
    from openvino.ov_infer import (
        CustomVoiceRequest,
        Language,
        ModelLoadConfig,
        ModelType,
        OVQwen3TTS,
        SamplingParams,
        Speaker,
    )

    options = json.loads(options_json) if options_json else {}
    model_type = ModelType(mode)
    sampling = SamplingParams(
        max_new_tokens=int(options.get("max_new_tokens", 512)),
        do_sample=not bool(options.get("no_sample", False)),
        temperature=float(options.get("temperature", 0.8)),
        top_k=int(options.get("top_k", 30)),
        top_p=float(options.get("top_p", 1.0)),
        repetition_penalty=float(options.get("repetition_penalty", 1.05)),
    )

    if model_type != ModelType.CUSTOM_VOICE:
        raise ValueError(f"unsupported OpenVINO TTS mode for host adapter: {model_type}")

    req_language = None
    if language and language.lower() not in {"auto", "none", "null"}:
        req_language = Language(language.lower())
    request = CustomVoiceRequest(
        text=text,
        speaker=Speaker(speaker.lower()),
        language=req_language,
        instruct=instruct or None,
        sampling=sampling,
    )

    engine = OVQwen3TTS()
    load_started = time.perf_counter()
    engine.load_model(ModelLoadConfig(
        ov_dir=ov_dir,
        device=device,
        cp_device=cp_device or None,
        model_type=model_type,
    ))
    load_sec = time.perf_counter() - load_started
    synth_started = time.perf_counter()
    wav, sr = engine.generate(request)
    synth_sec = time.perf_counter() - synth_started
    asyncio.run(engine.unload_model())
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, wav, sr)
    emit({
        "ok": True,
        "engine": "qwen3_tts_openvino",
        "mode": str(model_type),
        "ov_dir": ov_dir,
        "device": device,
        "cp_device": cp_device or None,
        "speaker": speaker,
        "language": language,
        "options": options,
        "load_sec": round(load_sec, 3),
        "synth_sec": round(synth_sec, 3),
        "sample_rate": int(sr),
        "samples": int(len(wav)),
        "audio_sec": round(float(len(wav)) / float(sr), 3) if sr else None,
    })
except Exception as exc:
    emit({"ok": False, "engine": "qwen3_tts_openvino", "error": repr(exc)})
    raise SystemExit(1)
'''


def qwen3_openvino_synth_command(
    *,
    python: str,
    profile: dict[str, Any],
    config: dict[str, Any],
    text: str,
    output: Any,
) -> list[str]:
    return [
        python,
        "-c",
        qwen3_openvino_synth_script(),
        str(profile.get("adapter_src") or ""),
        str(profile.get("ov_dir") or ""),
        str(profile.get("model_type") or "custom_voice"),
        text,
        str(output),
        str(profile.get("device") or "GPU"),
        str(profile.get("cp_device") or ""),
        str(profile.get("speaker") or "ryan"),
        str(profile.get("language") or config.get("language") or "russian"),
        str(profile.get("instruct") or ""),
        json.dumps(synth_options(profile), sort_keys=True),
    ]


def synth_subprocess_result(
    run_result: dict[str, Any],
    *,
    output_exists: bool,
    stdout_tail_limit: int = 1000,
    stderr_tail_limit: int = 3000,
) -> dict[str, Any]:
    stdout = str(run_result.get("stdout") or "")
    stderr = str(run_result.get("stderr") or "")
    subprocess_data = parse_json_stdout(stdout) or {
        "ok": False,
        "error": "TTS subprocess returned invalid JSON",
        "stdout_tail": stdout[-stdout_tail_limit:],
    }
    result: dict[str, Any] = {
        "subprocess": subprocess_data,
        "returncode": run_result.get("returncode"),
        "stderr_tail": stderr[-stderr_tail_limit:],
        "ok": bool(run_result.get("ok") and subprocess_data.get("ok") and output_exists),
    }
    if subprocess_data.get("error"):
        result["error"] = subprocess_data.get("error")
    return result


def synth_server_request_payload(
    *,
    profile: str,
    text: str,
    output: Any,
    speaker: Any,
    language: Any,
    instruct: Any,
    options: dict[str, Any],
) -> dict[str, Any]:
    return {
        "command": "synth",
        "profile": profile,
        "text": text,
        "output": str(output),
        "speaker": speaker,
        "language": language,
        "instruct": instruct,
        "options": options,
    }


def synth_server_attempt(
    *,
    socket_path: Any,
    elapsed_sec: float,
    response: dict[str, Any],
) -> dict[str, Any]:
    return {
        "socket": str(socket_path),
        "elapsed_sec": round(float(elapsed_sec), 3),
        "ok": bool(response.get("ok")),
        "error": response.get("error"),
        "server_profile": response.get("profile") or response.get("server_profile"),
        "warm": response.get("warm"),
    }


def audio_summary(
    *,
    exists: bool,
    duration_sec: float | None,
    sample_rate: int | None,
    size_bytes: int | None,
) -> dict[str, Any]:
    return {
        "exists": bool(exists),
        "duration_sec": duration_sec,
        "sample_rate": sample_rate,
        "size_bytes": size_bytes,
    }


def rtf(wall_sec: float | None, audio_sec: float | None) -> float | None:
    if wall_sec is None or not audio_sec:
        return None
    return round(float(wall_sec) / float(audio_sec), 4)


def _nested_get(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def eval_summary(synth: dict[str, Any]) -> dict[str, Any]:
    audio = synth.get("audio") if isinstance(synth.get("audio"), dict) else {}
    return {
        "wall_sec": synth.get("wall_sec"),
        "audio_sec": audio.get("duration_sec"),
        "rtf": synth.get("rtf"),
        "load_sec": _nested_get(synth, ("subprocess", "load_sec")) or _nested_get(synth, ("server", "server_load_sec")),
        "synth_sec": _nested_get(synth, ("subprocess", "synth_sec")) or _nested_get(synth, ("server", "synth_sec")),
        "server_used": bool(synth.get("server")),
        "device": synth.get("device"),
        "sample_rate": audio.get("sample_rate"),
        "text_chars": synth.get("text_chars"),
        "output": synth.get("output"),
        "error": result_error(synth),
        "policy_denied": bool(synth.get("policy_denied")),
        "policy_class": synth.get("policy_class") or _nested_get(synth, ("policy_gate", "policy_class")),
        "reasons": synth.get("reasons") if isinstance(synth.get("reasons"), list) else [],
    }


def eval_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile: str,
    declared_class: str,
    text: str,
    synth: dict[str, Any],
    latest_path: Any,
    latest_success_path: Any,
    daily_path: Any,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_eval_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": bool(synth.get("ok")),
        "profile": profile,
        "declared_class": declared_class,
        "text": text,
        "result": synth,
        "summary": eval_summary(synth),
        "paths": {
            "latest": str(latest_path),
            "latest_success": str(latest_success_path),
            "daily": str(daily_path),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "non_claim": "TTS host eval is executable-path evidence, not an abyss-stack promotion verdict.",
        },
    }


def compare_latency_key(item: dict[str, Any]) -> tuple[float, float, float]:
    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    wall_sec = float(summary.get("wall_sec") or 999999.0)
    synth_sec = float(summary.get("synth_sec") or 999999.0)
    item_rtf = float(summary.get("rtf") or 999999.0)
    return (wall_sec, synth_sec, item_rtf)


def compare_selection(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok_results = [item for item in results if item.get("ok")]
    ranked = sorted(ok_results, key=compare_latency_key)
    preferred_quality = "quality" if any(item.get("profile") == "quality" and item.get("ok") for item in results) else None
    preferred_interactive = ranked[0].get("profile") if ranked else None
    return {
        "default_quality": preferred_quality,
        "default_fast": preferred_interactive,
        "default_system_voice": preferred_interactive,
        "basis": "quality remains the explicit high-quality profile when it succeeds; fast/system choose lowest measured wall time, then synth time, then RTF among successful candidates",
        "quality_note": "Automatic comparison measures speed and executable health only; final pronunciation quality still needs human listening.",
    }


def compare_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    requested_profiles: list[str],
    evidence_source: str,
    results: list[dict[str, Any]],
    latest_path: Any,
    daily_path: Any,
    latest_success_path: Any,
    latest_success_by_profile_path: Any,
    success_by_profile_root: Any,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "ai_tts_compare_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": any(item.get("ok") for item in results),
        "requested_profiles": requested_profiles,
        "evidence_source": evidence_source,
        "results": results,
        "selection": compare_selection(results),
        "paths": {
            "latest": str(latest_path),
            "daily": str(daily_path),
            "latest_success": str(latest_success_path),
            "latest_success_by_profile": str(latest_success_by_profile_path),
            "success_by_profile_root": str(success_by_profile_root),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "facts_only": True,
            "default_compare_runs_no_model_execution": True,
        },
    }
