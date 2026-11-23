from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
import wave

from . import dictation_contracts


LoadJsonDocument = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
WriteJsonDocument = Callable[[Path, dict[str, Any], int], None]
Now = Callable[[], str]
PathExists = Callable[[Path], bool]
PathWritable = Callable[[Path], bool]
WavStats = Callable[[Path], dict[str, Any]]


@dataclass(frozen=True)
class DictationConfigPaths:
    config_dir: Path
    config_path: Path


def default_config(schema_prefix: str, version: str) -> dict[str, Any]:
    return dictation_contracts.default_config(schema_prefix, version)


def validate_config(config: dict[str, Any]) -> list[str]:
    return dictation_contracts.validate_config(config)


def load_config(
    paths: DictationConfigPaths,
    *,
    schema_prefix: str,
    version: str,
    load_json_document: LoadJsonDocument,
) -> dict[str, Any]:
    defaults = default_config(schema_prefix, version)
    loaded, error = load_json_document(paths.config_path)
    if loaded is None:
        config = defaults
        if error != "missing":
            config["_load_error"] = error
    else:
        config = dictation_contracts.deep_merge(defaults, loaded)
    errors = validate_config(config)
    if errors:
        fallback = defaults
        fallback["_load_error"] = "; ".join(errors)
        fallback["_invalid_config_path"] = str(paths.config_path)
        return fallback
    return config


def save_config(
    paths: DictationConfigPaths,
    config: dict[str, Any],
    *,
    updated_by: str,
    schema_prefix: str,
    version: str,
    now: Now,
    write_json_document: WriteJsonDocument,
) -> None:
    clean = dictation_contracts.deep_merge(default_config(schema_prefix, version), config)
    errors = validate_config(clean)
    if errors:
        raise ValueError("; ".join(errors))
    clean["schema"] = f"{schema_prefix}_dictation_config_v1"
    clean["version"] = version
    clean["updated_at"] = now()
    clean["updated_by"] = updated_by
    write_json_document(paths.config_path, clean, 0o664)


def concrete_profile_defaults(model_root: Path) -> dict[str, dict[str, Any]]:
    quality_model = str(model_root / "openvino" / "whisper-large-v3-turbo")
    return {
        "fast": {
            "name": "fast",
            "model_id": "openai/whisper-tiny",
            "model_dir": str(model_root / "openvino" / "whisper-tiny"),
            "device": "CPU",
            "language": "ru",
            "num_beams": 1,
            "max_new_tokens": 96,
            "description": "lowest-latency manual validation profile",
            "runtime": {},
            "postprocess": {},
        },
        "quality": {
            "name": "quality",
            "model_id": "openai/whisper-large-v3-turbo",
            "model_dir": quality_model,
            "device": "AUTO:GPU,CPU",
            "language": "ru",
            "num_beams": 3,
            "max_new_tokens": 192,
            "description": "high-quality local Whisper profile",
            "runtime": {},
            "postprocess": {},
        },
        "long": {
            "name": "long",
            "model_id": "openai/whisper-large-v3-turbo",
            "model_dir": quality_model,
            "device": "AUTO:GPU,CPU",
            "language": "ru",
            "num_beams": 3,
            "max_new_tokens": 384,
            "description": "long-form local Whisper profile",
            "runtime": {},
            "postprocess": {},
        },
        "command": {
            "name": "command",
            "model_id": "openai/whisper-large-v3-turbo",
            "model_dir": quality_model,
            "device": "AUTO:GPU,CPU",
            "language": "ru",
            "num_beams": 1,
            "max_new_tokens": 96,
            "description": "short command phrase local Whisper profile",
            "runtime": {},
            "postprocess": {},
        },
    }


def bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"0", "false", "no", "off"}
    if value is None:
        return default
    return bool(value)


def runtime_options(profile: Mapping[str, Any], config: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    return dictation_contracts.runtime_options(profile, config, env)


def postprocess_options(profile: Mapping[str, Any], config: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    return dictation_contracts.postprocess_options(profile, config, env)


def profile_map(
    *,
    config: Mapping[str, Any],
    model_root: Path,
    env: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    configured_profiles = config.get("profiles", {})
    for name, base in concrete_profile_defaults(model_root).items():
        configured = configured_profiles.get(name, {}) if isinstance(configured_profiles, dict) else {}
        profile = dictation_contracts.deep_merge(base, configured if isinstance(configured, dict) else {})
        profile["name"] = name
        profile["enabled"] = bool_value(profile.get("enabled"), True)
        profile["runtime"] = runtime_options(profile, config, env)
        profile["postprocess"] = postprocess_options(profile, config, env)
        profiles[name] = profile
    return profiles


def requested_profile_name(
    name: str | None,
    *,
    config: Mapping[str, Any],
    env: Mapping[str, str],
    default_profile: str,
) -> str:
    return dictation_contracts.requested_profile_name(name, config, env, default_profile)


def auto_select_profile(
    audio: str | None,
    *,
    config: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    env: Mapping[str, str],
    wav_stats_fn: WavStats,
) -> tuple[str, dict[str, Any]]:
    stats: dict[str, Any] | None = None
    audio_error: str | None = None
    if audio:
        try:
            stats = wav_stats_fn(Path(audio))
        except (OSError, wave.Error, ValueError) as exc:
            audio_error = str(exc)
    return dictation_contracts.auto_select_profile(stats, config, profiles, env, audio_error)


def select_profile(
    name: str | None,
    audio: str | None,
    *,
    config: Mapping[str, Any],
    model_root: Path,
    env: Mapping[str, str],
    default_profile: str,
    wav_stats_fn: WavStats,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profiles = profile_map(config=config, model_root=model_root, env=env)
    requested = requested_profile_name(name, config=config, env=env, default_profile=default_profile)
    selection: dict[str, Any] = {"requested_profile": requested}
    if requested == "auto":
        selected, auto_selection = auto_select_profile(
            audio,
            config=config,
            profiles=profiles,
            env=env,
            wav_stats_fn=wav_stats_fn,
        )
        selection.update(auto_selection)
        selection["selected_profile"] = selected
    else:
        selected = requested
        selection["mode"] = "manual"
        selection["selected_profile"] = selected

    profile = profiles.get(selected) or profiles.get("quality") or next(iter(profiles.values()))
    if not profile.get("enabled", True):
        fallback = profiles.get("quality") or next(iter(profiles.values()))
        selection["disabled_profile"] = selected
        selection["selected_profile"] = fallback["name"]
        profile = fallback
    return dict(profile), selection


def runtime_env(runtime: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, str]:
    return dictation_contracts.runtime_env(runtime, env)


def config_read_document(
    *,
    paths: DictationConfigPaths,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now: Now,
    path_exists: PathExists,
    path_writable: PathWritable,
) -> dict[str, Any]:
    writable_target = paths.config_dir if path_exists(paths.config_dir) else paths.config_path.parent
    return {
        "schema": f"{schema_prefix}_dictation_config_read_v1",
        "version": version,
        "generated_at": now(),
        "path": str(paths.config_path),
        "exists": path_exists(paths.config_path),
        "writable": path_writable(writable_target),
        "load_error": config.get("_load_error"),
        "config": dict(config),
    }


def profile_list_document(
    *,
    config: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    requested_default_profile: str,
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_profiles_v1",
        "version": version,
        "generated_at": now(),
        "default_profile": requested_default_profile,
        "profile_policy": config.get("profile_policy", {}),
        "profiles": {name: dict(profile) for name, profile in profiles.items()},
    }


def profile_get_document(
    *,
    requested: str,
    profile: Mapping[str, Any],
    selection: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_profile_v1",
        "version": version,
        "generated_at": now(),
        "requested": requested,
        "selection": dict(selection),
        "profile": dict(profile),
    }
