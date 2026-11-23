"""Dictation application organ CLI, moved out of the abyss_machine core CLI.

`abyss_machine.cli` keeps the `dictation` command names and
delegates here lazily. Shared core helpers are reached as `_core.<name>`,
so callers and tests that patch `abyss_machine.cli` keep the same effect.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import fcntl
import fnmatch
import grp
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import secrets
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from abyss_machine import cli as _core

_ORGAN_PACKAGE = "abyss_machine.organs.dictation"
sys.dont_write_bytecode = True

globals().update(
    {
        "dictation_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_contracts"),
        "dictation_docs_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_docs_adapters"),
        "dictation_execution_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_execution_adapters"),
        "dictation_lock_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_lock_adapters"),
        "dictation_notifications_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_notifications_adapters"),
        "dictation_postprocess_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_postprocess_adapters"),
        "dictation_profile_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_profile_adapters"),
        "dictation_replacements_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_replacements_adapters"),
        "dictation_runtime_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_runtime_adapters"),
        "dictation_status_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_status_adapters"),
        "dictation_validation_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.dictation_validation_adapters"),
    }
)


DICTATION_MODEL_ROOT = Path("/srv/AbyssOS/abyss-stack/Models/stt/whisper")


DICTATION_DEFAULT_PROFILE = "auto"


DICTATION_DEBOUNCE_SECONDS = 1.25


DICTATION_DEFAULT_MAX_SECONDS = 300


VALID_DICTATION_PROFILES = {"auto", "fast", "quality", "long", "command"}


def parse_config_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false", "null"}:
        return json.loads(lowered)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def set_nested_value(data: dict[str, Any], dotted_key: str, value: Any) -> None:
    if not dotted_key or dotted_key.startswith(".") or dotted_key.endswith("."):
        raise ValueError("invalid dotted key")
    cursor = data
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        if not part:
            raise ValueError("invalid dotted key")
        existing = cursor.get(part)
        if existing is None:
            existing = {}
            cursor[part] = existing
        if not isinstance(existing, dict):
            raise ValueError(f"{part} is not an object")
        cursor = existing
    cursor[parts[-1]] = value


def dictation_runtime_dir() -> Path:
    return dictation_runtime_adapters.runtime_dir(os.environ, uid=os.getuid())


def dictation_server_socket() -> Path:
    return dictation_runtime_adapters.server_socket(os.environ, dictation_runtime_dir())


def dictation_config_paths() -> dictation_profile_adapters.DictationConfigPaths:
    return dictation_profile_adapters.DictationConfigPaths(
        config_dir=_core.DICTATION_CONFIG_DIR,
        config_path=_core.DICTATION_CONFIG_PATH,
    )


def dictation_transcription_paths() -> dictation_execution_adapters.DictationTranscriptionPaths:
    return dictation_execution_adapters.DictationTranscriptionPaths(
        helper=_core.DICTATION_HELPER,
        server_socket=dictation_server_socket(),
        server_audio_dir=dictation_runtime_dir() / "server-audio",
    )


def dictation_recording_paths() -> dictation_execution_adapters.DictationRecordingPaths:
    return dictation_execution_adapters.DictationRecordingPaths(
        runtime_dir=dictation_runtime_dir(),
        state_file=dictation_state_file(),
    )


def dictation_audio_paths() -> dictation_execution_adapters.DictationAudioPaths:
    return dictation_execution_adapters.DictationAudioPaths(
        runtime_dir=dictation_runtime_dir(),
    )


def dictation_calibration_paths() -> dictation_execution_adapters.DictationCalibrationPaths:
    return dictation_execution_adapters.DictationCalibrationPaths(
        runtime_dir=dictation_runtime_dir(),
        config_path=_core.DICTATION_CONFIG_PATH,
    )


def dictation_journal_paths() -> dictation_execution_adapters.DictationJournalPaths:
    return dictation_execution_adapters.DictationJournalPaths(
        jsonl_root=_core.DICTATION_TRANSCRIPT_JSONL_ROOT,
        jsonl_path=dictation_transcript_today_jsonl_path(),
        markdown_path=dictation_transcript_today_markdown_path(),
        latest_path=_core.DICTATION_TRANSCRIPT_LATEST_PATH,
        index_path=_core.DICTATION_INDEX_PATH,
    )


def dictation_docs_paths() -> dictation_docs_adapters.DictationDocsPaths:
    runtime = dictation_runtime_dir()
    return dictation_docs_adapters.DictationDocsPaths(
        root=_core.DICTATION_ROOT,
        agent_entrypoint=_core.DICTATION_AGENTS_PATH,
        index=_core.DICTATION_INDEX_PATH,
        config=_core.DICTATION_CONFIG_PATH,
        replacements=_core.DICTATION_REPLACEMENTS_PATH,
        helper=_core.DICTATION_HELPER,
        server=_core.DICTATION_SERVER,
        runtime_dir=runtime,
        server_audio_dir=runtime / "server-audio",
        transcript_root=_core.DICTATION_TRANSCRIPT_ROOT,
        transcript_jsonl_root=_core.DICTATION_TRANSCRIPT_JSONL_ROOT,
        transcript_readable_root=_core.DICTATION_TRANSCRIPT_READABLE_ROOT,
        transcript_latest=_core.DICTATION_TRANSCRIPT_LATEST_PATH,
        today_jsonl=dictation_transcript_today_jsonl_path(),
        today_markdown=dictation_transcript_today_markdown_path(),
        validate_latest=_core.DICTATION_VALIDATE_LATEST_PATH,
    )


def dictation_status_paths() -> dictation_status_adapters.DictationStatusPaths:
    runtime = dictation_runtime_dir()
    return dictation_status_adapters.DictationStatusPaths(
        runtime_dir=runtime,
        config_path=_core.DICTATION_CONFIG_PATH,
        replacements_path=_core.DICTATION_REPLACEMENTS_PATH,
        model_root=DICTATION_MODEL_ROOT,
        helper=_core.DICTATION_HELPER,
        server=_core.DICTATION_SERVER,
        server_socket=dictation_server_socket(),
        ydotool_socket=dictation_runtime_adapters.ydotool_socket(os.environ, uid=os.getuid()),
        transcript_latest=_core.DICTATION_TRANSCRIPT_LATEST_PATH,
        today_readable=dictation_transcript_today_markdown_path(),
        today_jsonl=dictation_transcript_today_jsonl_path(),
    )


def dictation_replacements_paths() -> dictation_replacements_adapters.DictationReplacementsPaths:
    return dictation_replacements_adapters.DictationReplacementsPaths(
        replacements_path=_core.DICTATION_REPLACEMENTS_PATH,
    )


def dictation_validation_paths() -> dictation_validation_adapters.DictationValidationPaths:
    return dictation_validation_adapters.DictationValidationPaths(
        validate_latest=_core.DICTATION_VALIDATE_LATEST_PATH,
        validate_history=_core.DICTATION_VALIDATE_ROOT,
        transcript_latest=_core.DICTATION_TRANSCRIPT_LATEST_PATH,
    )


def dictation_state_file() -> Path:
    return dictation_runtime_dir() / "recording.json"


def dictation_lock_file() -> Path:
    return dictation_runtime_dir() / "dictation.lock"


def dictation_completion_lock_file() -> Path:
    return dictation_runtime_dir() / "completion.lock"


def dictation_today_path(root: Path, suffix: str) -> Path:
    return dictation_docs_adapters.today_path(root, suffix)


def dictation_transcript_today_jsonl_path() -> Path:
    return dictation_today_path(_core.DICTATION_TRANSCRIPT_JSONL_ROOT, ".jsonl")


def dictation_transcript_today_markdown_path() -> Path:
    return dictation_today_path(_core.DICTATION_TRANSCRIPT_READABLE_ROOT, ".md")


def dictation_paths() -> dict[str, Any]:
    return dictation_docs_adapters.paths_document(
        dictation_docs_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_index_document() -> dict[str, Any]:
    return dictation_docs_adapters.index_document(
        dictation_docs_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_agents_doc() -> str:
    return dictation_docs_adapters.agents_doc(dictation_docs_paths())


def ensure_dictation_docs() -> list[dict[str, Any]]:
    return dictation_docs_adapters.ensure_docs(
        dictation_docs_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_notifications_enabled() -> bool:
    return dictation_notifications_adapters.notifications_enabled(os.environ, dictation_config)


def default_dictation_config() -> dict[str, Any]:
    return dictation_profile_adapters.default_config(_core.SCHEMA_PREFIX, _core.VERSION)


def dictation_config() -> dict[str, Any]:
    return dictation_profile_adapters.load_config(
        dictation_config_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        load_json_document=_core.load_json_document,
    )


def save_dictation_config(config: dict[str, Any], updated_by: str) -> None:
    dictation_profile_adapters.save_config(
        dictation_config_paths(),
        config,
        updated_by=updated_by,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        write_json_document=_core.atomic_write_json,
    )


def dictation_profiles() -> dict[str, dict[str, Any]]:
    config = dictation_config()
    return dictation_profile_adapters.profile_map(
        config=config,
        model_root=DICTATION_MODEL_ROOT,
        env=os.environ,
    )


def requested_dictation_profile_name(name: str | None = None) -> str:
    config = dictation_config()
    return dictation_profile_adapters.requested_profile_name(
        name,
        config=config,
        env=os.environ,
        default_profile=DICTATION_DEFAULT_PROFILE,
    )


def dictation_profile(name: str | None = None, audio: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    return dictation_profile_adapters.select_profile(
        name,
        audio,
        config=dictation_config(),
        model_root=DICTATION_MODEL_ROOT,
        env=os.environ,
        default_profile=DICTATION_DEFAULT_PROFILE,
        wav_stats_fn=wav_stats,
    )


@contextmanager
def dictation_lock(timeout_sec: float = 0.25):
    with dictation_lock_adapters.dictation_lock(dictation_lock_file(), timeout_sec):
        yield


@contextmanager
def dictation_completion_lock(timeout_sec: float = 900.0):
    with dictation_lock_adapters.completion_lock(dictation_completion_lock_file(), timeout_sec):
        yield


def dictation_busy_result(action: str = "busy") -> dict[str, Any]:
    _core.notify("Abyss Dictation", "Занято: диктовка уже обрабатывается", 2500)
    return dictation_contracts.busy_result(action, _core.SCHEMA_PREFIX, _core.VERSION, _core.now_iso())


def dictation_max_seconds() -> int:
    return dictation_runtime_adapters.max_seconds(os.environ, DICTATION_DEFAULT_MAX_SECONDS)


def recording_age_seconds(state: dict[str, Any]) -> float | None:
    return dictation_execution_adapters.recording_age_seconds(state)


def load_dictation_recording() -> dict[str, Any] | None:
    return dictation_execution_adapters.load_active_recording(dictation_recording_paths())


def load_stale_dictation_recording() -> dict[str, Any] | None:
    return dictation_execution_adapters.load_stale_recording(dictation_recording_paths())


def dictation_status() -> dict[str, Any]:
    config = dictation_config()
    recording = load_dictation_recording()
    return dictation_status_adapters.status_document(
        paths=dictation_status_paths(),
        config=config,
        profiles=dictation_profiles(),
        recording=recording,
        stale_recording=None if recording else load_stale_dictation_recording(),
        replacements=dictation_replacements_document(),
        requested_default_profile=requested_dictation_profile_name(None),
        journal_enabled=dictation_journal_enabled(),
        command_exists=_core.command_exists,
        path_exists=Path.exists,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_validation_checks() -> list[dict[str, Any]]:
    return dictation_validation_adapters.validation_checks(
        paths=dictation_validation_paths(),
        ensure_docs=ensure_dictation_docs,
        load_json_document=_core.load_json_document,
        path_exists=Path.exists,
        schema_prefix=_core.SCHEMA_PREFIX,
    )


def write_dictation_validation_latest(data: dict[str, Any]) -> list[dict[str, Any]]:
    return dictation_validation_adapters.write_validation_latest(
        data,
        paths=dictation_validation_paths(),
        write_latest_and_history=_core.write_latest_and_history,
    )


def wav_stats(path: Path) -> dict[str, Any]:
    return dictation_execution_adapters.wav_stats(path)


def recent_dictation_wavs(limit: int = 12) -> list[Path]:
    return dictation_execution_adapters.recent_wavs(dictation_audio_paths(), limit)


def dictation_replacements_document() -> dict[str, Any]:
    return dictation_replacements_adapters.load_document(
        dictation_replacements_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        load_json_document=_core.load_json_document,
    )


def save_dictation_replacements_document(doc: dict[str, Any], updated_by: str) -> None:
    dictation_replacements_adapters.save_document(
        dictation_replacements_paths(),
        doc,
        updated_by=updated_by,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        write_json_document=_core.atomic_write_json,
    )


def dictation_replacements_list() -> dict[str, Any]:
    return dictation_replacements_adapters.list_document(
        dictation_replacements_paths(),
        dictation_replacements_document(),
        generated_at=_core.now_iso(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        path_exists=Path.exists,
    )


def dictation_replacements_test(text: str) -> dict[str, Any]:
    return dictation_replacements_adapters.test_document(
        text,
        dictation_replacements_document(),
        generated_at=_core.now_iso(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
    )


def add_dictation_replacement(kind: str, source: str, target: str, item_id: str | None = None, ignore_case: bool = True) -> dict[str, Any]:
    return dictation_replacements_adapters.add_replacement(
        dictation_replacements_paths(),
        kind=kind,
        source=source,
        target=target,
        item_id=item_id,
        ignore_case=ignore_case,
        fallback_token=int(time.time()),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        load_json_document=_core.load_json_document,
        write_json_document=_core.atomic_write_json,
        path_exists=Path.exists,
    )


def remove_dictation_replacement(item_id: str) -> dict[str, Any]:
    return dictation_replacements_adapters.remove_replacement(
        dictation_replacements_paths(),
        item_id=item_id,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        load_json_document=_core.load_json_document,
        write_json_document=_core.atomic_write_json,
        path_exists=Path.exists,
    )


def dictation_audio_doctor(limit: int = 12) -> dict[str, Any]:
    return dictation_execution_adapters.audio_doctor(
        paths=dictation_audio_paths(),
        config=dictation_config(),
        limit=limit,
        run_command=_core.run,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_calibrate_mic(seconds: int = 8, from_recent: bool = False, limit: int = 12, apply: bool = False) -> dict[str, Any]:
    return dictation_execution_adapters.calibrate_mic(
        paths=dictation_calibration_paths(),
        config=dictation_config(),
        seconds=seconds,
        from_recent=from_recent,
        limit=limit,
        apply=apply,
        command_exists=_core.command_exists,
        run_command=_core.run,
        save_config=save_dictation_config,
        notify=_core.notify,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        wav_stats_fn=wav_stats,
        recent_wavs_fn=recent_dictation_wavs,
    )


def _dictation_start_unlocked(profile_name: str | None = None) -> dict[str, Any]:
    existing = load_dictation_recording()
    if existing:
        status_data = dictation_status()
        status_data["message"] = "recording already active"
        return status_data

    requested_profile = requested_dictation_profile_name(profile_name)
    max_seconds = dictation_max_seconds()
    dictation_execution_adapters.start_recording(
        paths=dictation_recording_paths(),
        profile=requested_profile,
        max_seconds_value=max_seconds,
        timeout_available=_core.command_exists("timeout"),
        schema_prefix=_core.SCHEMA_PREFIX,
        now=_core.now_iso,
    )
    status_data = dictation_status()
    status_data["message"] = "recording started"
    return status_data


def dictation_start(profile_name: str | None = None) -> dict[str, Any]:
    try:
        with dictation_lock():
            return _dictation_start_unlocked(profile_name)
    except TimeoutError:
        return dictation_busy_result("start-busy")


def _dictation_stop_unlocked(state: dict[str, Any] | None = None) -> dict[str, Any]:
    return dictation_execution_adapters.stop_recording(
        state,
        paths=dictation_recording_paths(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_stop() -> dict[str, Any]:
    try:
        with dictation_lock():
            return _dictation_stop_unlocked()
    except TimeoutError:
        return dictation_busy_result("stop-busy")


def dictation_intent_test(text: str) -> dict[str, Any]:
    return dictation_postprocess_adapters.intent_test_document(
        text,
        config_document=dictation_config,
        generated_at=_core.now_iso(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
    )


def postprocess_transcript(data: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    return dictation_postprocess_adapters.postprocess_transcript_data(
        data,
        profile,
        config_document=dictation_config,
        replacements_document=dictation_replacements_document,
        schema_prefix=_core.SCHEMA_PREFIX,
    )


def dictation_journal_enabled() -> bool:
    return dictation_execution_adapters.journal_enabled(dictation_config)


def dictation_journal_include_failed() -> bool:
    return dictation_execution_adapters.journal_include_failed(dictation_config)


def dictation_journal_write(result: dict[str, Any]) -> dict[str, Any]:
    return dictation_execution_adapters.journal_write(
        result,
        paths=dictation_journal_paths(),
        enabled=dictation_journal_enabled(),
        include_failed=dictation_journal_include_failed(),
        ensure_docs=ensure_dictation_docs,
        index_document=dictation_index_document,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        wav_duration_fn=wav_duration,
    )


def dictation_journal_latest() -> dict[str, Any]:
    return dictation_execution_adapters.journal_latest(
        paths=dictation_journal_paths(),
        ensure_docs=ensure_dictation_docs,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_journal_tail(lines: int = 20) -> dict[str, Any]:
    return dictation_execution_adapters.journal_tail(
        paths=dictation_journal_paths(),
        lines=lines,
        ensure_docs=ensure_dictation_docs,
        paths_document=dictation_paths,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_transcribe(audio: str, profile_name: str | None = None, json_output: bool = True) -> dict[str, Any]:
    profile, profile_selection = dictation_profile(profile_name, audio)
    transcript = dictation_execution_adapters.transcribe_audio(
        audio,
        profile,
        profile_selection,
        paths=dictation_transcription_paths(),
        run_command=_core.run,
        command_exists=_core.command_exists,
        wav_sample_rate=wav_sample_rate,
        wav_duration=wav_duration,
        env=os.environ,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )
    return postprocess_transcript(transcript, profile)


def dictation_insert(text: str) -> dict[str, Any]:
    return dictation_execution_adapters.insert_text(
        text=text,
        env=os.environ,
        command_exists=_core.command_exists,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_toggle(profile_name: str | None = None, insert: bool = True) -> dict[str, Any]:
    try:
        with dictation_lock():
            return _dictation_toggle_unlocked(profile_name, insert=insert)
    except TimeoutError:
        return dictation_busy_result()


def dictation_complete_stopped(stopped: dict[str, Any], profile_name: str | None = None, insert: bool = True) -> dict[str, Any]:
    with dictation_completion_lock():
        audio = stopped.get("audio")
        if not audio:
            _core.notify("Abyss Dictation", "Не удалось остановить запись", 4000)
            return stopped
        _core.notify("Abyss Dictation", "Распознаю речь...", 2500)
        transcript = dictation_transcribe(str(audio), profile_name or stopped.get("profile"))
        result = dictation_contracts.toggle_result(
            action="stop-transcribe-insert" if insert else "stop-transcribe",
            recording=stopped,
            transcript=transcript,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
        )
        if insert and transcript.get("ok"):
            result["insert"] = dictation_insert(str(transcript.get("text", "")))
            if result["insert"].get("ok"):
                _core.notify("Abyss Dictation", "Текст вставлен", 2500)
            else:
                _core.notify("Abyss Dictation", "Распознано, но вставка не сработала", 4500)
        elif transcript.get("ok"):
            _core.notify("Abyss Dictation", "Текст распознан", 2500)
        else:
            error = str(transcript.get("error", "ошибка распознавания"))[:160]
            _core.notify("Abyss Dictation", error, 4500)
        result["journal"] = dictation_journal_write(result)
        return result


def _dictation_toggle_unlocked(profile_name: str | None = None, insert: bool = True) -> dict[str, Any]:
    active = load_dictation_recording()
    if active:
        age = recording_age_seconds(active)
        debounce_result = dictation_execution_adapters.toggle_debounce_result(
            active,
            age_seconds=age,
            env=os.environ,
            status_document=dictation_status,
            debounce_seconds=DICTATION_DEBOUNCE_SECONDS,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            now=_core.now_iso,
        )
        if debounce_result is not None:
            return debounce_result

        stopped = _dictation_stop_unlocked(active)
        return dictation_complete_stopped(stopped, profile_name=profile_name, insert=insert)

    stale = load_stale_dictation_recording()
    if stale:
        dictation_execution_adapters.unlink_recording_state(dictation_recording_paths())
        audio = stale.get("audio")
        _core.notify("Abyss Dictation", "Распознаю завершённую запись...", 2500)
        transcript = dictation_transcribe(str(audio), profile_name or stale.get("profile")) if audio else dictation_contracts.stale_missing_audio_transcript(_core.SCHEMA_PREFIX, _core.VERSION, _core.now_iso())
        result = dictation_contracts.toggle_result(
            action="transcribe-stale-insert" if insert else "transcribe-stale",
            recording=stale,
            transcript=transcript,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
        )
        if insert and transcript.get("ok"):
            result["insert"] = dictation_insert(str(transcript.get("text", "")))
            if result["insert"].get("ok"):
                _core.notify("Abyss Dictation", "Текст вставлен", 2500)
            else:
                _core.notify("Abyss Dictation", "Распознано, но вставка не сработала", 4500)
        elif transcript.get("ok"):
            _core.notify("Abyss Dictation", "Текст распознан", 2500)
        else:
            _core.notify("Abyss Dictation", str(transcript.get("error", "ошибка распознавания"))[:160], 4500)
        result["journal"] = dictation_journal_write(result)
        return result

    started = _dictation_start_unlocked(profile_name)
    if started.get("recording"):
        profile = started["recording"].get("profile", DICTATION_DEFAULT_PROFILE)
        _core.notify("Abyss Dictation", f"Запись началась ({profile})", 2500)
    else:
        _core.notify("Abyss Dictation", str(started.get("message", "запись не началась"))[:160], 4500)
    return dictation_contracts.toggle_result(
        action="start",
        recording=started.get("recording"),
        status=started,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
        return round(frames / rate, 3) if rate else None
    except (OSError, wave.Error):
        return None


def wav_sample_rate(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as wav:
            return int(wav.getframerate())
    except (OSError, wave.Error):
        return None


def dictation_config_get() -> dict[str, Any]:
    return dictation_profile_adapters.config_read_document(
        paths=dictation_config_paths(),
        config=dictation_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
        path_exists=Path.exists,
        path_writable=lambda path: os.access(path, os.W_OK),
    )


def dictation_config_set(dotted_key: str, raw_value: str) -> dict[str, Any]:
    config = dictation_config()
    config.pop("_load_error", None)
    config.pop("_invalid_config_path", None)
    value = parse_config_value(raw_value)
    set_nested_value(config, dotted_key, value)
    save_dictation_config(config, f"set:{dotted_key}")
    return dictation_config_get()


def dictation_config_reset() -> dict[str, Any]:
    save_dictation_config(default_dictation_config(), "reset")
    return dictation_config_get()


def dictation_profile_list() -> dict[str, Any]:
    profiles = dictation_profiles()
    config = dictation_config()
    return dictation_profile_adapters.profile_list_document(
        config=config,
        profiles=profiles,
        requested_default_profile=requested_dictation_profile_name(None),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def dictation_profile_get(name: str) -> dict[str, Any]:
    profile, selection = dictation_profile(name, None)
    return dictation_profile_adapters.profile_get_document(
        requested=name,
        profile=profile,
        selection=selection,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now=_core.now_iso,
    )


def print_dictation_status_text(data: dict[str, Any]) -> None:
    print(f"recording: {data.get('recording_active')}")
    print(f"model root: {data.get('model_root')}")
    for name, profile in data.get("profiles", {}).items():
        marker = "*" if name == data.get("default_profile") else " "
        ready = "ready" if profile.get("model_dir_exists") else "missing"
        print(f"{marker} {name:<8} {ready:<7} {profile.get('device')} {profile.get('model_dir')}")


def print_dictation_audio_doctor_text(data: dict[str, Any]) -> None:
    summary = data["summary"]
    print(f"default source: {data.get('default_source') or 'unknown'}")
    print(
        "summary: "
        f"files={summary.get('files_analyzed')} "
        f"avg_dbfs={summary.get('avg_dbfs')} "
        f"max_peak={summary.get('max_peak')} "
        f"max_clip={summary.get('max_clip_percent')}%"
    )
    print(f"recommendation: {summary.get('recommendation')}")
    for item in data.get("recent_files", [])[:12]:
        name = Path(str(item.get("path", ""))).name
        if not item.get("ok"):
            print(f"{name:<32} error={item.get('error')}")
            continue
        print(
            f"{name:<32} "
            f"dur={item.get('duration_sec'):>5}s "
            f"dbfs={item.get('dbfs'):>6} "
            f"peak={item.get('peak'):<6} "
            f"p95={item.get('p95'):<7} "
            f"clip={item.get('clip_percent')}% "
            f"low={item.get('low_level_percent')}%"
        )


def add_dictation_parser(add_top_level_parser: Any, selected_parser_choices: Any) -> None:
    dictation_parser = add_top_level_parser("dictation", help="record, transcribe and insert local speech-to-text")
    dictation_sub = dictation_parser.add_subparsers(dest="dictation_command", required=True)
    dictation_status_parser = dictation_sub.add_parser("status")
    dictation_status_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_validate_parser = dictation_sub.add_parser("validate")
    dictation_validate_parser.add_argument("--strict", action="store_true", help="treat warnings as non-zero")
    dictation_validate_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_journal_parser = dictation_sub.add_parser("journal")
    dictation_journal_sub = dictation_journal_parser.add_subparsers(dest="dictation_journal_command", required=True)
    dictation_journal_paths_parser = dictation_journal_sub.add_parser("paths")
    dictation_journal_paths_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_journal_latest_parser = dictation_journal_sub.add_parser("latest")
    dictation_journal_latest_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_journal_tail_parser = dictation_journal_sub.add_parser("tail")
    dictation_journal_tail_parser.add_argument("--lines", type=int, default=20)
    dictation_journal_tail_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_start_parser = dictation_sub.add_parser("start")
    dictation_start_parser.add_argument("--profile", default=None)
    dictation_start_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_stop_parser = dictation_sub.add_parser("stop")
    dictation_stop_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_toggle_parser = dictation_sub.add_parser("toggle")
    dictation_toggle_parser.add_argument("--profile", default=None)
    dictation_toggle_parser.add_argument("--no-insert", action="store_true")
    dictation_toggle_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_transcribe_parser = dictation_sub.add_parser("transcribe")
    dictation_transcribe_parser.add_argument("audio")
    dictation_transcribe_parser.add_argument("--profile", default=None)
    dictation_transcribe_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_complete_parser = dictation_sub.add_parser("complete-stopped")
    dictation_complete_parser.add_argument("--recording-json", default="-")
    dictation_complete_parser.add_argument("--profile", default=None)
    dictation_complete_parser.add_argument("--no-insert", action="store_true")
    dictation_complete_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_insert_parser = dictation_sub.add_parser("insert")
    dictation_insert_parser.add_argument("text", nargs="*")
    dictation_insert_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_audio_parser = dictation_sub.add_parser("audio-doctor")
    dictation_audio_parser.add_argument("--limit", type=int, default=12)
    dictation_audio_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_calibrate_parser = dictation_sub.add_parser("calibrate-mic")
    dictation_calibrate_parser.add_argument("--seconds", type=int, default=8)
    dictation_calibrate_parser.add_argument("--from-recent", action="store_true")
    dictation_calibrate_parser.add_argument("--limit", type=int, default=12)
    dictation_calibrate_parser.add_argument("--apply", action="store_true")
    dictation_calibrate_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_config_parser = dictation_sub.add_parser("config")
    dictation_config_sub = dictation_config_parser.add_subparsers(dest="dictation_config_command", required=True)
    dictation_config_get_parser = dictation_config_sub.add_parser("get")
    dictation_config_get_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_config_set_parser = dictation_config_sub.add_parser("set")
    dictation_config_set_parser.add_argument("key")
    dictation_config_set_parser.add_argument("value")
    dictation_config_set_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_config_reset_parser = dictation_config_sub.add_parser("reset")
    dictation_config_reset_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_profile_parser = dictation_sub.add_parser("profile")
    dictation_profile_sub = dictation_profile_parser.add_subparsers(dest="dictation_profile_command", required=True)
    dictation_profile_list_parser = dictation_profile_sub.add_parser("list")
    dictation_profile_list_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_profile_get_parser = dictation_profile_sub.add_parser("get")
    dictation_profile_get_parser.add_argument("profile")
    dictation_profile_get_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_replacements_parser = dictation_sub.add_parser("replacements")
    dictation_replacements_sub = dictation_replacements_parser.add_subparsers(dest="dictation_replacements_command", required=True)
    dictation_replacements_list_parser = dictation_replacements_sub.add_parser("list")
    dictation_replacements_list_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_replacements_test_parser = dictation_replacements_sub.add_parser("test")
    dictation_replacements_test_parser.add_argument("text", nargs="*")
    dictation_replacements_test_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_replacements_add_literal = dictation_replacements_sub.add_parser("add-literal")
    dictation_replacements_add_literal.add_argument("source")
    dictation_replacements_add_literal.add_argument("target")
    dictation_replacements_add_literal.add_argument("--id", default=None)
    dictation_replacements_add_literal.add_argument("--case-sensitive", action="store_true")
    dictation_replacements_add_literal.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_replacements_add_regex = dictation_replacements_sub.add_parser("add-regex")
    dictation_replacements_add_regex.add_argument("pattern")
    dictation_replacements_add_regex.add_argument("target")
    dictation_replacements_add_regex.add_argument("--id", default=None)
    dictation_replacements_add_regex.add_argument("--case-sensitive", action="store_true")
    dictation_replacements_add_regex.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_replacements_remove = dictation_replacements_sub.add_parser("remove")
    dictation_replacements_remove.add_argument("id")
    dictation_replacements_remove.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    dictation_intent_parser = dictation_sub.add_parser("intent")
    dictation_intent_sub = dictation_intent_parser.add_subparsers(dest="dictation_intent_command", required=True)
    dictation_intent_test_parser = dictation_intent_sub.add_parser("test")
    dictation_intent_test_parser.add_argument("text", nargs="*")
    dictation_intent_test_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def dispatch_dictation(args: Any, parser: Any, argv: list[str]) -> int:
    if args.command == "dictation":
        if args.dictation_command == "status":
            data = dictation_status()
            if args.json:
                _core.print_json(data)
            else:
                print_dictation_status_text(data)
            return 0

        if args.dictation_command == "validate":
            data = _core.subsystem_validate("dictation", strict=bool(getattr(args, "strict", False)), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(f"dictation validate: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
            if data.get("summary", {}).get("fails"):
                return 1
            if getattr(args, "strict", False) and data.get("summary", {}).get("warnings"):
                return 2
            return 0

        if args.dictation_command == "journal":
            if args.dictation_journal_command == "paths":
                write_errors = ensure_dictation_docs()
                data = dictation_paths()
                data["ok"] = not write_errors
                data["write_errors"] = write_errors
                if args.json:
                    _core.print_json(data)
                else:
                    transcripts = data.get("transcripts", {})
                    print(f"dictation journal: {transcripts.get('today_readable')}")
                return 0 if data.get("ok") else 1
            if args.dictation_journal_command == "latest":
                data = dictation_journal_latest()
                if args.json:
                    _core.print_json(data)
                else:
                    entry = data.get("entry") or {}
                    print(entry.get("text") or data.get("load_error") or "no dictation journal entry")
                return 0 if data.get("ok") else 1
            if args.dictation_journal_command == "tail":
                data = dictation_journal_tail(args.lines)
                if args.json:
                    _core.print_json(data)
                else:
                    for item in data.get("entries", []):
                        text = str(item.get("text") or item.get("error") or "").strip()
                        print(f"{item.get('generated_at')} {item.get('action')} {text}")
                return 0 if data.get("ok") else 1
            parser.error("unknown dictation journal command")

        if args.dictation_command == "start":
            data = dictation_start(args.profile)
            if args.json:
                _core.print_json(data)
            else:
                print("recording started" if data.get("recording_active") else data.get("message", "not recording"))
            return 0

        if args.dictation_command == "stop":
            data = dictation_stop()
            if args.json:
                _core.print_json(data)
            else:
                print(data.get("audio", data.get("message", "")))
            return 0

        if args.dictation_command == "toggle":
            data = dictation_toggle(args.profile, insert=not args.no_insert)
            if args.json:
                _core.print_json(data)
            else:
                if data.get("action") == "start":
                    print("recording started")
                else:
                    transcript = data.get("transcript", {})
                    print(transcript.get("text", ""))
            return 0

        if args.dictation_command == "transcribe":
            data = dictation_transcribe(args.audio, args.profile)
            if args.json:
                _core.print_json(data)
            else:
                print(data.get("text", data.get("error", "")))
            return 0 if data.get("ok") else 1

        if args.dictation_command == "complete-stopped":
            try:
                if args.recording_json == "-":
                    stopped = json.loads(_core.sys.stdin.read())
                else:
                    stopped = json.loads(Path(args.recording_json).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                data = {
                    "schema": f"{_core.SCHEMA_PREFIX}_dictation_toggle_v1",
                    "version": _core.VERSION,
                    "generated_at": _core.now_iso(),
                    "ok": False,
                    "error": f"invalid stopped recording JSON: {exc}",
                }
            else:
                data = dictation_complete_stopped(stopped, profile_name=args.profile, insert=not args.no_insert)
            if args.json:
                _core.print_json(data)
            else:
                transcript = data.get("transcript", {}) if isinstance(data.get("transcript"), dict) else {}
                print(transcript.get("text", data.get("error", "")))
            return 0 if not data.get("error") else 1

        if args.dictation_command == "insert":
            text = " ".join(args.text)
            if not text and not _core.sys.stdin.isatty():
                text = _core.sys.stdin.read()
            data = dictation_insert(text)
            if args.json:
                _core.print_json(data)
            else:
                print("inserted" if data.get("ok") else data.get("error", "insert failed"))
            return 0 if data.get("ok") else 1

        if args.dictation_command == "audio-doctor":
            data = dictation_audio_doctor(max(1, min(int(args.limit), 100)))
            if args.json:
                _core.print_json(data)
            else:
                print_dictation_audio_doctor_text(data)
            return 0

        if args.dictation_command == "calibrate-mic":
            data = dictation_calibrate_mic(
                seconds=max(3, min(int(args.seconds), 60)),
                from_recent=bool(args.from_recent),
                limit=max(1, min(int(args.limit), 100)),
                apply=bool(args.apply),
            )
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(
                    "calibration: "
                    f"ok={data.get('ok')} "
                    f"files={summary.get('files_analyzed')} "
                    f"avg_dbfs={summary.get('avg_dbfs')} "
                    f"noise={summary.get('noise_floor_dbfs')} "
                    f"applied={data.get('applied')}"
                )
            return 0 if data.get("ok") else 1

        if args.dictation_command == "config":
            try:
                if args.dictation_config_command == "get":
                    data = dictation_config_get()
                elif args.dictation_config_command == "set":
                    data = dictation_config_set(args.key, args.value)
                elif args.dictation_config_command == "reset":
                    data = dictation_config_reset()
                else:
                    parser.error("unknown dictation config command")
            except (OSError, ValueError) as exc:
                data = {
                    "schema": f"{_core.SCHEMA_PREFIX}_dictation_config_write_v1",
                    "version": _core.VERSION,
                    "generated_at": _core.now_iso(),
                    "ok": False,
                    "error": str(exc),
                    "path": str(_core.DICTATION_CONFIG_PATH),
                }
                if args.json:
                    _core.print_json(data)
                else:
                    print(data["error"])
                return 1
            if args.json:
                _core.print_json(data)
            else:
                config = data.get("config", {})
                print(f"default_profile: {config.get('default_profile')}")
                print(f"path: {data.get('path')}")
            return 0

        if args.dictation_command == "profile":
            if args.dictation_profile_command == "list":
                data = dictation_profile_list()
            elif args.dictation_profile_command == "get":
                data = dictation_profile_get(args.profile)
            else:
                parser.error("unknown dictation profile command")
            if args.json:
                _core.print_json(data)
            else:
                if args.dictation_profile_command == "list":
                    for name, profile in data.get("profiles", {}).items():
                        marker = "*" if name == data.get("default_profile") else " "
                        print(f"{marker} {name:<8} {profile.get('device')} {profile.get('description')}")
                else:
                    profile = data.get("profile", {})
                    print(f"{profile.get('name')} {profile.get('device')} {profile.get('model_dir')}")
            return 0

        if args.dictation_command == "replacements":
            try:
                if args.dictation_replacements_command == "list":
                    data = dictation_replacements_list()
                elif args.dictation_replacements_command == "test":
                    text = " ".join(args.text)
                    if not text and not _core.sys.stdin.isatty():
                        text = _core.sys.stdin.read()
                    data = dictation_replacements_test(text)
                elif args.dictation_replacements_command == "add-literal":
                    data = add_dictation_replacement(
                        "literal",
                        args.source,
                        args.target,
                        item_id=args.id,
                        ignore_case=not args.case_sensitive,
                    )
                elif args.dictation_replacements_command == "add-regex":
                    data = add_dictation_replacement(
                        "regex",
                        args.pattern,
                        args.target,
                        item_id=args.id,
                        ignore_case=not args.case_sensitive,
                    )
                elif args.dictation_replacements_command == "remove":
                    data = remove_dictation_replacement(args.id)
                else:
                    parser.error("unknown dictation replacements command")
            except (OSError, ValueError, re.error) as exc:
                data = {
                    "schema": f"{_core.SCHEMA_PREFIX}_dictation_replacements_write_v1",
                    "version": _core.VERSION,
                    "generated_at": _core.now_iso(),
                    "ok": False,
                    "error": str(exc),
                    "path": str(_core.DICTATION_REPLACEMENTS_PATH),
                }
                if args.json:
                    _core.print_json(data)
                else:
                    print(data["error"])
                return 1
            if args.json:
                _core.print_json(data)
            else:
                if args.dictation_replacements_command == "test":
                    print(data.get("output", ""))
                else:
                    print(f"replacements: {len(data.get('items', []))}")
            return 0

        if args.dictation_command == "intent":
            if args.dictation_intent_command == "test":
                text = " ".join(args.text)
                if not text and not _core.sys.stdin.isatty():
                    text = _core.sys.stdin.read()
                data = dictation_intent_test(text)
            else:
                parser.error("unknown dictation intent command")
            if args.json:
                _core.print_json(data)
            else:
                intent = data.get("intent", {})
                print(intent.get("payload") if intent.get("triggered") else intent.get("type", "dictation"))
            return 0
    parser.error("unknown command")
    return 64
