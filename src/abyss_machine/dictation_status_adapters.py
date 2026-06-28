from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


Now = Callable[[], str]
CommandExists = Callable[[str], bool]
PathExists = Callable[[Path], bool]


@dataclass(frozen=True)
class DictationStatusPaths:
    runtime_dir: Path
    config_path: Path
    replacements_path: Path
    model_root: Path
    helper: Path
    server: Path
    server_socket: Path
    ydotool_socket: Path
    transcript_latest: Path
    today_readable: Path
    today_jsonl: Path


def _profile_status(profile: Mapping[str, Any], *, path_exists: PathExists) -> dict[str, Any]:
    data = dict(profile)
    model_dir = data.get("model_dir")
    data["model_dir_exists"] = path_exists(Path(str(model_dir))) if model_dir else False
    return data


def status_document(
    *,
    paths: DictationStatusPaths,
    config: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    recording: Mapping[str, Any] | None,
    stale_recording: Mapping[str, Any] | None,
    replacements: Mapping[str, Any],
    requested_default_profile: str,
    journal_enabled: bool,
    command_exists: CommandExists,
    path_exists: PathExists,
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_status_v1",
        "version": version,
        "generated_at": now(),
        "runtime_dir": str(paths.runtime_dir),
        "config": {
            "path": str(paths.config_path),
            "exists": path_exists(paths.config_path),
            "load_error": config.get("_load_error"),
            "default_profile": requested_default_profile,
            "profile_policy": config.get("profile_policy", {}),
            "command_intent": config.get("command_intent", {}),
            "runtime": config.get("runtime", {}),
            "postprocess": config.get("postprocess", {}),
            "notifications": config.get("notifications", {}),
            "journal": config.get("journal", {}),
            "calibration": config.get("calibration", {}),
        },
        "replacements": {
            "path": str(paths.replacements_path),
            "exists": path_exists(paths.replacements_path),
            "load_error": replacements.get("_load_error"),
            "count": len(replacements.get("items", [])) if isinstance(replacements.get("items"), list) else 0,
        },
        "model_root": str(paths.model_root),
        "helper": str(paths.helper),
        "server": str(paths.server),
        "server_socket": str(paths.server_socket),
        "server_socket_exists": path_exists(paths.server_socket),
        "default_profile": requested_default_profile,
        "profiles": {
            name: _profile_status(profile, path_exists=path_exists)
            for name, profile in profiles.items()
        },
        "recording": dict(recording) if recording is not None else None,
        "recording_active": recording is not None,
        "stale_recording": dict(stale_recording) if stale_recording is not None else None,
        "commands": {
            "pw_record": command_exists("pw-record"),
            "wl_copy": command_exists("wl-copy"),
            "ydotool": command_exists("ydotool"),
            "ydotool_socket": path_exists(paths.ydotool_socket),
            "wev": command_exists("wev"),
            "wtype": command_exists("wtype"),
        },
        "audio": {
            "default_source_known": command_exists("wpctl"),
        },
        "journal": {
            "enabled": journal_enabled,
            "latest": str(paths.transcript_latest),
            "latest_exists": path_exists(paths.transcript_latest),
            "today_readable": str(paths.today_readable),
            "today_jsonl": str(paths.today_jsonl),
        },
    }
