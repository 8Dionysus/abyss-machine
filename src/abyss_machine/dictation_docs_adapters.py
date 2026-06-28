from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import fcntl
import grp
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable


DEFAULT_STATE_GROUP = "wheel"

Now = Callable[[], str]
NowDateTime = Callable[[], dt.datetime]
PathExists = Callable[[Path], bool]
ReadText = Callable[[Path], str]
EnsureDir = Callable[[Path], dict[str, Any] | None]
AppendText = Callable[[Path, str, int], dict[str, Any] | None]
WriteText = Callable[[Path, str, int], dict[str, Any] | None]
WriteJson = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]


@dataclass(frozen=True)
class DictationDocsPaths:
    root: Path
    agent_entrypoint: Path
    index: Path
    config: Path
    replacements: Path
    helper: Path
    server: Path
    runtime_dir: Path
    server_audio_dir: Path
    transcript_root: Path
    transcript_jsonl_root: Path
    transcript_readable_root: Path
    transcript_latest: Path
    today_jsonl: Path
    today_markdown: Path
    validate_latest: Path


def current_datetime() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone()


def today_path(root: Path, suffix: str, *, now_datetime: NowDateTime = current_datetime) -> Path:
    today = now_datetime()
    return root / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.strftime('%Y-%m-%d')}{suffix}"


def paths_document(
    paths: DictationDocsPaths,
    *,
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_paths_v1",
        "version": version,
        "generated_at": now(),
        "root": str(paths.root),
        "agent_entrypoint": str(paths.agent_entrypoint),
        "index": str(paths.index),
        "config": str(paths.config),
        "replacements": str(paths.replacements),
        "helper": str(paths.helper),
        "server": str(paths.server),
        "runtime_dir": str(paths.runtime_dir),
        "server_audio_dir": str(paths.server_audio_dir),
        "transcripts": {
            "root": str(paths.transcript_root),
            "latest": str(paths.transcript_latest),
            "today_jsonl": str(paths.today_jsonl),
            "today_readable": str(paths.today_markdown),
            "jsonl_daily_glob": str(paths.transcript_jsonl_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "readable_daily_glob": str(paths.transcript_readable_root / "YYYY" / "MM" / "YYYY-MM-DD.md"),
        },
        "validate_latest": str(paths.validate_latest),
    }


def index_document(
    paths: DictationDocsPaths,
    *,
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_dictation_index_v1",
        "version": version,
        "generated_at": now(),
        "paths": paths_document(paths, schema_prefix=schema_prefix, version=version, now=now),
        "contracts": {
            "desktop_notifications": "disabled by default; GNOME microphone privacy indicator remains the recording signal",
            "journal": "successful and failed toggle transcriptions are persisted as JSONL plus readable Markdown",
            "audio": "recordings remain runtime-scoped under XDG_RUNTIME_DIR; durable journal stores text and metadata, not audio copies",
            "warm_server_file_transcribe": "explicit-file transcription preserves the caller audio path and may send a 16 kHz runtime copy to the warm server",
            "future_stack_bridge": "abyss-stack may read these host-layer paths without importing or mutating abyss-machine code",
        },
        "commands": {
            "status": ["abyss-machine", "dictation", "status", "--json"],
            "paths": ["abyss-machine", "dictation", "journal", "paths", "--json"],
            "latest": ["abyss-machine", "dictation", "journal", "latest", "--json"],
            "tail": ["abyss-machine", "dictation", "journal", "tail", "--lines", "20"],
            "transcribe": ["abyss-machine", "dictation", "transcribe", "AUDIO.wav", "--json"],
            "validate": ["abyss-machine", "dictation", "validate", "--json"],
        },
    }


def agents_doc(paths: DictationDocsPaths) -> str:
    return f"""# Abyss Machine Dictation

This is the host-layer entrypoint for local speech-to-text dictation state.

Read this file before changing dictation routing, transcript cleanup, hotkeys,
or journal retention. Keep project repositories read-only from this layer unless
the operator explicitly asks otherwise.

## Stable Commands

- `abyss-machine dictation status --json` - live STT, hotkey, model, and insertion readiness.
- `abyss-machine dictation journal paths --json` - durable transcript journal topology.
- `abyss-machine dictation journal latest --json` - latest persisted voice transcript event.
- `abyss-machine dictation journal tail --lines 20` - recent readable transcript entries.
- `abyss-machine dictation replacements list --json` - host-side vocabulary fixes.
- `abyss-machine dictation audio-doctor --json` - microphone/source diagnostics.
- `abyss-machine dictation transcribe AUDIO.wav --json` - transcribe an explicit audio file through the warm server when available.
- `abyss-machine dictation validate --json` - contract validation.

## Paths

- Config: `{paths.config}`
- Replacements: `{paths.replacements}`
- Runtime recordings/socket: `{paths.runtime_dir}`
- Runtime warm-server audio preprocessed for Whisper: `{paths.server_audio_dir}`
- Durable journal latest: `{paths.transcript_latest}`
- Durable journal JSONL: `{paths.transcript_jsonl_root}/YYYY/MM/YYYY-MM-DD.jsonl`
- Durable readable journal: `{paths.transcript_readable_root}/YYYY/MM/YYYY-MM-DD.md`
- Index: `{paths.index}`

## Contracts

- Desktop notifications are off by default. The GNOME orange microphone privacy
  indicator is the visible recording signal.
- The durable journal stores transcript text, raw text when available,
  postprocessing markers, profile/runtime metadata, insertion result, and audio
  runtime path metadata. It does not copy WAV files into persistent storage.
- Warm-server file transcription keeps the caller's original audio path as the
  transcript `audio` field. When the source WAV is not 16 kHz and profile
  `audio_preprocess` is enabled, the CLI creates a 16 kHz mono PCM runtime copy
  under `{paths.server_audio_dir}` before sending it to the
  resident server, and records the runtime copy in `client_audio_preprocess` /
  `server_audio`.
- The journal is append-only by day. Use it later to update
  `{paths.replacements}` after reviewing real recognition errors.
- This layer exposes host facts and state for future abyss-stack bridges; it is
  not an abyss-stack runtime component.
"""


def _ensure_state_dir(path: Path, *, group: str = DEFAULT_STATE_GROUP) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o2775)
    except PermissionError:
        pass
    try:
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, PermissionError):
        pass


def safe_ensure_dir(path: Path) -> dict[str, Any] | None:
    try:
        _ensure_state_dir(path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_atomic_write_json(path: Path, data: dict[str, Any], mode: int = 0o664) -> dict[str, Any] | None:
    try:
        _ensure_state_dir(path.parent)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=False)
            tmp.write("\n")
            tmp_name = tmp.name
        os.chmod(tmp_name, mode)
        try:
            os.chown(tmp_name, -1, grp.getgrnam(DEFAULT_STATE_GROUP).gr_gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_atomic_write_text(path: Path, text: str, mode: int = 0o664) -> dict[str, Any] | None:
    try:
        _ensure_state_dir(path.parent)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            delete=False,
        ) as tmp:
            tmp.write(text)
            tmp_name = tmp.name
        os.chmod(tmp_name, mode)
        try:
            os.chown(tmp_name, -1, grp.getgrnam(DEFAULT_STATE_GROUP).gr_gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_append_text(path: Path, text: str, mode: int = 0o664) -> dict[str, Any] | None:
    try:
        _ensure_state_dir(path.parent)
        payload = text.encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        fd = os.open(path, flags, mode)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("short append write")
                view = view[written:]
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
        try:
            os.chmod(path, mode)
        except PermissionError:
            pass
        try:
            os.chown(path, -1, grp.getgrnam(DEFAULT_STATE_GROUP).gr_gid)
        except (KeyError, PermissionError):
            pass
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_docs(
    paths: DictationDocsPaths,
    *,
    schema_prefix: str,
    version: str,
    now: Now,
    ensure_dir: EnsureDir = safe_ensure_dir,
    append_text: AppendText = safe_append_text,
    write_text: WriteText = safe_atomic_write_text,
    write_json: WriteJson = safe_atomic_write_json,
    read_text_fn: ReadText = read_text,
    path_exists: PathExists = Path.exists,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for path in (paths.root, paths.transcript_root, paths.transcript_jsonl_root, paths.transcript_readable_root):
        error = ensure_dir(path)
        if error:
            errors.append(error)
    agent_error = append_text(paths.agent_entrypoint, "", 0o664)
    if agent_error:
        errors.append(agent_error)
    else:
        try:
            current = read_text_fn(paths.agent_entrypoint) if path_exists(paths.agent_entrypoint) else ""
        except OSError as exc:
            current = ""
            errors.append({"path": str(paths.agent_entrypoint), "error": str(exc)})
        desired = agents_doc(paths)
        if current != desired:
            write_error = write_text(paths.agent_entrypoint, desired, 0o664)
            if write_error:
                errors.append(write_error)
    index_error = write_json(paths.index, index_document(paths, schema_prefix=schema_prefix, version=version, now=now), 0o664)
    if index_error:
        errors.append(index_error)
    return errors
