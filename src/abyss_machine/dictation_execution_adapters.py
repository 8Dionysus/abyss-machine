from __future__ import annotations

import array
from dataclasses import dataclass
import datetime as dt
import fcntl
import grp
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping
import wave

from . import dictation_contracts


DEFAULT_STATE_GROUP = "wheel"

RunCommand = Callable[[list[str], float, Mapping[str, str] | None], Mapping[str, Any]]
CommandExists = Callable[[str], bool]
WavSampleRate = Callable[[Path], int | None]
WavDuration = Callable[[Path], float | None]
Now = Callable[[], str]
NowDateTime = Callable[[], dt.datetime]
Monotonic = Callable[[], float]
SocketJsonLineRequest = Callable[[Path, Mapping[str, Any], float, float], str | None]
FilenameTimestamp = Callable[[], str]
ProcessAlive = Callable[[int], bool]
StartRecordingProcess = Callable[[list[str], Path], int]
SignalProcess = Callable[[int, int], None]
Sleep = Callable[[float], None]
WavStats = Callable[[Path], dict[str, Any]]
RecentWavs = Callable[[int], list[Path]]
EnsureDocs = Callable[[], list[dict[str, Any]]]
IndexDocument = Callable[[], dict[str, Any]]
PathsDocument = Callable[[], dict[str, Any]]
ConfigDocument = Callable[[], dict[str, Any]]
PathExists = Callable[[Path], bool]
RunWtypeText = Callable[[str, float], Mapping[str, Any]]
CopyClipboardText = Callable[[str], Mapping[str, Any]]
SendKeySequence = Callable[[list[str], Mapping[str, str], float], Mapping[str, Any]]
SaveConfig = Callable[[dict[str, Any], str], None]
Notify = Callable[[str, str, int], None]


@dataclass(frozen=True)
class DictationTranscriptionPaths:
    helper: Path
    server_socket: Path
    server_audio_dir: Path


@dataclass(frozen=True)
class DictationRecordingPaths:
    runtime_dir: Path
    state_file: Path


@dataclass(frozen=True)
class DictationAudioPaths:
    runtime_dir: Path


@dataclass(frozen=True)
class DictationJournalPaths:
    jsonl_root: Path
    jsonl_path: Path
    markdown_path: Path
    latest_path: Path
    index_path: Path


@dataclass(frozen=True)
class DictationCalibrationPaths:
    runtime_dir: Path
    config_path: Path


@dataclass(frozen=True)
class ForegroundClipboardSession:
    poll: Callable[[], int | None]
    read_stderr: Callable[[], str]
    stop: Callable[[float], None]


StartForegroundClipboard = Callable[[str], ForegroundClipboardSession]


def current_datetime() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone()


def filename_timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _ensure_state_history_dir(path: Path, *, group: str = DEFAULT_STATE_GROUP) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o2775)
    except PermissionError:
        pass
    try:
        os.chown(path, -1, grp.getgrnam(group).gr_gid)
    except (KeyError, PermissionError):
        pass


def safe_atomic_write_json(
    path: Path,
    data: dict[str, Any],
    mode: int = 0o664,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
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
            os.chown(tmp_name, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_append_jsonl(
    path: Path,
    data: dict[str, Any],
    mode: int = 0o664,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    try:
        _ensure_state_history_dir(path.parent, group=group)
        payload = (json.dumps(data, sort_keys=False) + "\n").encode("utf-8")
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
            os.chown(path, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def safe_append_text(
    path: Path,
    text: str,
    mode: int = 0o664,
    *,
    group: str = DEFAULT_STATE_GROUP,
) -> dict[str, Any] | None:
    try:
        _ensure_state_history_dir(path.parent, group=group)
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
            os.chown(path, -1, grp.getgrnam(group).gr_gid)
        except (KeyError, PermissionError):
            pass
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def load_json_document(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc}"
    if not isinstance(data, dict):
        return None, "document is not a JSON object"
    return data, None


def env_int(env: Mapping[str, str] | None, key: str, default: int, minimum: int, maximum: int) -> int:
    raw = (env or {}).get(key, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def run_wtype_text(text: str, timeout: float) -> Mapping[str, Any]:
    proc = subprocess.run(
        ["wtype", "-"],
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {"returncode": proc.returncode, "stderr": proc.stderr.strip()}


def copy_clipboard_text(text: str) -> Mapping[str, Any]:
    proc = subprocess.run(
        ["wl-copy", "--type", "text/plain"],
        input=text,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=3.0,
        check=False,
    )
    return {"returncode": proc.returncode, "stderr": proc.stderr.strip()}


def start_foreground_clipboard(text: str) -> ForegroundClipboardSession:
    proc = subprocess.Popen(
        ["wl-copy", "--foreground", "--type", "text/plain"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    if proc.stdin is None:
        raise OSError("wl-copy stdin unavailable")
    proc.stdin.write(text)
    proc.stdin.close()

    def poll() -> int | None:
        return proc.poll()

    def read_stderr() -> str:
        if proc.stderr is None or proc.poll() is None:
            return ""
        return proc.stderr.read().strip()

    def stop(timeout: float) -> None:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                pass

    return ForegroundClipboardSession(poll=poll, read_stderr=read_stderr, stop=stop)


def send_key_sequence(sequence: list[str], env: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
    proc = subprocess.run(
        ["ydotool", "key", "--key-delay", str(env.get("ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS", "45")), *sequence],
        env=dict(env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {"returncode": proc.returncode, "stderr": proc.stderr.strip()}


def wav_stats(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
        frame_count = wav.getnframes()

    if sample_width != 2:
        return {
            "path": str(path),
            "ok": False,
            "error": f"unsupported sample width {sample_width}",
            "sample_rate": sample_rate,
            "channels": channels,
            "duration_sec": round(frame_count / sample_rate, 3) if sample_rate else 0.0,
        }

    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    if channels > 1:
        mono: list[int] = []
        for idx in range(0, len(samples), channels):
            mono.append(int(sum(samples[idx : idx + channels]) / channels))
        values = mono
    else:
        values = list(samples)

    count = len(values)
    if not count:
        rms = 0.0
        peak = 0.0
        p95 = 0.0
        low_percent = 100.0
        clip_percent = 0.0
    else:
        abs_values = [abs(v) for v in values]
        peak_i = max(abs_values)
        rms_i = math.sqrt(sum(v * v for v in values) / count)
        sorted_abs = sorted(abs_values)
        p95_i = sorted_abs[min(count - 1, int(count * 0.95))]
        low_i = int(0.003 * 32768)
        clip_i = int(0.98 * 32768)
        low_percent = 100.0 * sum(1 for v in abs_values if v < low_i) / count
        clip_percent = 100.0 * sum(1 for v in abs_values if v > clip_i) / count
        rms = rms_i / 32768.0
        peak = peak_i / 32768.0
        p95 = p95_i / 32768.0

    dbfs = 20.0 * math.log10(max(rms, 1e-9))
    frame_dbfs: list[float] = []
    if sample_rate and values:
        frame_size = max(1, int(sample_rate * 0.03))
        for offset in range(0, len(values) - frame_size + 1, frame_size):
            frame = values[offset : offset + frame_size]
            if not frame:
                continue
            frame_rms = math.sqrt(sum(v * v for v in frame) / len(frame)) / 32768.0
            frame_dbfs.append(20.0 * math.log10(max(frame_rms, 1e-9)))
        frame_dbfs.sort()

    def percentile(values_f: list[float], ratio: float) -> float | None:
        if not values_f:
            return None
        idx = min(len(values_f) - 1, max(0, int(len(values_f) * ratio)))
        return round(values_f[idx], 1)

    return {
        "path": str(path),
        "ok": True,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_sec": round(frame_count / sample_rate, 3) if sample_rate else 0.0,
        "peak": round(peak, 4),
        "rms": round(rms, 5),
        "dbfs": round(dbfs, 1),
        "p95": round(p95, 5),
        "clip_percent": round(clip_percent, 4),
        "low_level_percent": round(low_percent, 1),
        "frame_dbfs_p10": percentile(frame_dbfs, 0.10),
        "frame_dbfs_p50": percentile(frame_dbfs, 0.50),
        "frame_dbfs_p90": percentile(frame_dbfs, 0.90),
    }


def wav_duration(path: Path) -> float | None:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        if not rate:
            return None
        return round(frames / rate, 3)


def recent_wavs(paths: DictationAudioPaths, limit: int = 12) -> list[Path]:
    if not paths.runtime_dir.exists():
        return []
    files = [p for p in paths.runtime_dir.glob("*.wav") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def inspect_wavs(
    files: Iterable[Path],
    *,
    wav_stats_fn: WavStats = wav_stats,
) -> list[dict[str, Any]]:
    stats: list[dict[str, Any]] = []
    for path in files:
        try:
            stats.append(wav_stats_fn(path))
        except (OSError, wave.Error, ValueError) as exc:
            stats.append({"path": str(path), "ok": False, "error": str(exc)})
    return stats


def audio_doctor(
    *,
    paths: DictationAudioPaths,
    config: Mapping[str, Any],
    limit: int,
    run_command: RunCommand,
    schema_prefix: str,
    version: str,
    now: Now,
    wav_stats_fn: WavStats = wav_stats,
    recent_wavs_fn: RecentWavs | None = None,
) -> dict[str, Any]:
    default_source = run_command(["pactl", "get-default-source"], 2.0, None)
    wpctl_status = run_command(["wpctl", "status"], 2.0, None)
    wpctl_source = run_command(["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"], 2.0, None)
    files = recent_wavs_fn(limit) if recent_wavs_fn is not None else recent_wavs(paths, limit)
    stats = inspect_wavs(files, wav_stats_fn=wav_stats_fn)
    summary = dictation_contracts.summarize_audio_stats(stats)
    return {
        "schema": f"{schema_prefix}_dictation_audio_doctor_v1",
        "version": version,
        "generated_at": now(),
        "default_source": default_source["stdout"] if default_source.get("ok") else "",
        "wpctl_status_ok": bool(wpctl_status.get("ok")),
        "wpctl_default_source": wpctl_source["stdout"] if wpctl_source.get("ok") else "",
        "recent_files": stats,
        "summary": summary,
        "calibration": config.get("calibration", {}) if isinstance(config.get("calibration"), dict) else {},
        "recommended_runtime": dictation_contracts.recommended_audio_runtime(summary),
    }


def calibrate_mic(
    *,
    paths: DictationCalibrationPaths,
    config: Mapping[str, Any],
    seconds: int,
    from_recent: bool,
    limit: int,
    apply: bool,
    command_exists: CommandExists,
    run_command: RunCommand,
    save_config: SaveConfig,
    notify: Notify,
    schema_prefix: str,
    version: str,
    now: Now,
    filename_timestamp_fn: FilenameTimestamp = filename_timestamp,
    wav_stats_fn: WavStats = wav_stats,
    recent_wavs_fn: RecentWavs | None = None,
    path_exists: PathExists = Path.exists,
) -> dict[str, Any]:
    stats: list[dict[str, Any]] = []
    recorded_path: Path | None = None
    if from_recent:
        files = recent_wavs_fn(limit) if recent_wavs_fn is not None else recent_wavs(DictationAudioPaths(paths.runtime_dir), limit)
    else:
        if not command_exists("pw-record"):
            return dictation_contracts.mic_calibration_error_result(
                error="pw-record not found",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=now(),
            )
        paths.runtime_dir.mkdir(parents=True, exist_ok=True)
        recorded_path = paths.runtime_dir / f"mic-calibration-{filename_timestamp_fn()}.wav"
        bounded_seconds = max(3, min(int(seconds), 60))
        notify("Abyss Dictation", f"Калибровка микрофона: говорите {bounded_seconds} с", 2500)
        record_cmd = dictation_contracts.calibration_recording_command(
            recorded_path,
            seconds=bounded_seconds,
            timeout_available=command_exists("timeout"),
        )
        out = run_command(record_cmd, bounded_seconds + 8.0, None)
        if not path_exists(recorded_path):
            return dictation_contracts.mic_calibration_error_result(
                error=str(out.get("stderr") or out.get("stdout") or "calibration recording was not created"),
                schema_prefix=schema_prefix,
                version=version,
                generated_at=now(),
            )
        files = [recorded_path]

    stats = inspect_wavs(files, wav_stats_fn=wav_stats_fn)
    summary = dictation_contracts.summarize_audio_stats(stats)
    recommended = dictation_contracts.recommended_audio_runtime(summary)
    result = dictation_contracts.mic_calibration_result(
        source="recent" if from_recent else "recorded",
        recorded_path=recorded_path,
        summary=summary,
        recommended_runtime=recommended,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now(),
    )
    if apply and result["ok"]:
        updated_config = dict(config)
        runtime = dict(updated_config.get("runtime", {})) if isinstance(updated_config.get("runtime"), dict) else {}
        runtime.update(recommended)
        updated_config["runtime"] = runtime
        updated_config["calibration"] = {
            "enabled": True,
            "source": result["source"],
            "updated_at": now(),
            "summary": summary,
            "recommended_runtime": recommended,
        }
        save_config(updated_config, "calibrate-mic")
        result["applied"] = True
        result["config_path"] = str(paths.config_path)
    return result


def insert_text(
    text: str,
    *,
    env: Mapping[str, str],
    command_exists: CommandExists,
    schema_prefix: str,
    version: str,
    now: Now,
    run_wtype_fn: RunWtypeText = run_wtype_text,
    start_foreground_clipboard_fn: StartForegroundClipboard = start_foreground_clipboard,
    copy_clipboard_fn: CopyClipboardText = copy_clipboard_text,
    send_key_sequence_fn: SendKeySequence = send_key_sequence,
    sleep_fn: Sleep = time.sleep,
) -> dict[str, Any]:
    if not text.strip():
        return dictation_contracts.insert_empty_result(schema_prefix, version, now())

    env_map = dict(env)
    method_preference = str(env_map.get("ABYSS_DICTATION_INSERT_METHOD", "wtype")).lower()
    wtype_result: dict[str, Any] | None = None
    if method_preference in {"wtype", "auto"} and command_exists("wtype"):
        timeout = max(5.0, min(30.0, len(text) / 12.0))
        try:
            wtype_proc = run_wtype_fn(text, timeout)
            returncode = int(wtype_proc.get("returncode", 1))
            stderr = str(wtype_proc.get("stderr") or "")
            wtype_result = {
                "method": "wtype",
                "returncode": returncode,
                "stderr": stderr,
            }
            if returncode == 0:
                return dictation_contracts.insert_wtype_success_result(text, schema_prefix, version, now())
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            wtype_result = {
                "method": "wtype",
                "returncode": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
                "stderr": str(exc),
            }

    clipboard_provider = dictation_contracts.normalize_clipboard_provider(env_map.get("ABYSS_DICTATION_CLIPBOARD_PROVIDER", "foreground"))

    foreground_session: ForegroundClipboardSession | None = None
    copy_returncode: int | None = None
    copy_stderr = ""
    try:
        if clipboard_provider == "foreground":
            foreground_session = start_foreground_clipboard_fn(text)
            sleep_fn(float(env_map.get("ABYSS_DICTATION_CLIPBOARD_SETTLE_SECONDS", "0.12")))
            copy_returncode = foreground_session.poll()
            if copy_returncode not in (None, 0):
                copy_stderr = foreground_session.read_stderr()
                return dictation_contracts.insert_error_result(copy_stderr.strip() or "wl-copy failed", schema_prefix, version, now())
        else:
            copy_run = copy_clipboard_fn(text)
            copy_returncode = int(copy_run.get("returncode", 1))
            copy_stderr = str(copy_run.get("stderr") or "")
            if copy_returncode != 0:
                return dictation_contracts.insert_error_result(copy_stderr or "wl-copy failed", schema_prefix, version, now())
            sleep_fn(float(env_map.get("ABYSS_DICTATION_CLIPBOARD_SETTLE_SECONDS", "0.08")))
    except FileNotFoundError:
        return dictation_contracts.insert_error_result("wl-copy not found", schema_prefix, version, now())
    except (OSError, subprocess.TimeoutExpired) as exc:
        if foreground_session is not None:
            foreground_session.stop(0.5)
        return dictation_contracts.insert_error_result(str(exc), schema_prefix, version, now())

    combo_name = dictation_contracts.normalize_paste_combo(env_map.get("ABYSS_DICTATION_PASTE_COMBO", "ctrl-v"))
    key_delay_ms = str(env_int(env_map, "ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS", 45, 10, 120))
    hold_seconds = float(env_map.get("ABYSS_DICTATION_CLIPBOARD_HOLD_SECONDS", "1.6"))
    attempts: list[dict[str, Any]] = []
    combo_order = dictation_contracts.paste_combo_order(combo_name)

    ydotool_env = dict(env_map)
    ydotool_env.setdefault("YDOTOOL_SOCKET", f"/run/user/{os.getuid()}/.ydotool_socket")
    ydotool_env["ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS"] = key_delay_ms

    paste_sent = False
    for index, name in enumerate(combo_order):
        if index:
            sleep_fn(0.18)
        sequence = dictation_contracts.paste_key_sequence(name)
        try:
            paste_proc = send_key_sequence_fn(sequence, ydotool_env, 3.0)
            returncode = int(paste_proc.get("returncode", 1))
            stderr = str(paste_proc.get("stderr") or "")
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            returncode = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
            stderr = str(exc)
        attempt = {
            "combo": name,
            "returncode": returncode,
            "stderr": stderr,
            "paste_sent": returncode == 0,
        }
        attempts.append(attempt)
        if returncode != 0:
            continue
        paste_sent = True
        if clipboard_provider == "foreground":
            sleep_fn(max(0.2, min(5.0, hold_seconds)))
        break

    if foreground_session is not None:
        foreground_session.stop(0.5)
        if foreground_session.poll() is not None:
            copy_stderr = foreground_session.read_stderr()
        copy_returncode = foreground_session.poll()

    fallback: dict[str, Any] | None = wtype_result
    return dictation_contracts.insert_final_result(
        text=text,
        clipboard_provider=clipboard_provider,
        copy_returncode=copy_returncode,
        attempts=attempts,
        fallback=fallback,
        copy_stderr=copy_stderr,
        combo_name=combo_name,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now(),
    )


def audio_metadata(audio: Any, *, wav_duration_fn: WavDuration = wav_duration) -> dict[str, Any]:
    if not audio:
        return {"path": None, "exists": False}
    path = Path(str(audio))
    data: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "persistent_copy": False,
    }
    if path.exists():
        try:
            stat = path.stat()
            data["size_bytes"] = stat.st_size
            data["mtime"] = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds")
        except OSError as exc:
            data["stat_error"] = str(exc)
        try:
            data["duration_sec"] = wav_duration_fn(path)
        except Exception as exc:
            data["duration_error"] = str(exc)
    return data


def journal_policy(config_document: ConfigDocument) -> dict[str, bool]:
    try:
        settings = config_document().get("journal", {})
    except Exception:
        return {"enabled": True, "include_failed": True}
    if not isinstance(settings, dict):
        return {"enabled": True, "include_failed": True}
    return {
        "enabled": dictation_contracts.bool_value(settings.get("enabled"), True),
        "include_failed": dictation_contracts.bool_value(settings.get("include_failed"), True),
    }


def journal_enabled(config_document: ConfigDocument) -> bool:
    return journal_policy(config_document)["enabled"]


def journal_include_failed(config_document: ConfigDocument) -> bool:
    return journal_policy(config_document)["include_failed"]


def journal_event(
    result: Mapping[str, Any],
    *,
    include_failed: bool,
    paths: DictationJournalPaths,
    schema_prefix: str,
    version: str,
    now: Now,
    wav_duration_fn: WavDuration = wav_duration,
) -> dict[str, Any] | None:
    transcript = result.get("transcript")
    if not isinstance(transcript, dict):
        return None
    if not transcript.get("ok") and not include_failed:
        return None
    recording = result.get("recording") if isinstance(result.get("recording"), dict) else {}
    audio = recording.get("audio") if isinstance(recording, dict) else None
    generated_at = now()
    event_id = dictation_contracts.journal_entry_id(dict(result), audio, generated_at)
    return dictation_contracts.journal_event(
        dict(result),
        include_failed=True,
        audio_metadata=audio_metadata(audio, wav_duration_fn=wav_duration_fn),
        event_id=event_id,
        generated_at=generated_at,
        paths={
            "jsonl": str(paths.jsonl_path),
            "readable": str(paths.markdown_path),
            "latest": str(paths.latest_path),
        },
        schema_prefix=schema_prefix,
        version=version,
    )


def journal_write(
    result: Mapping[str, Any],
    *,
    paths: DictationJournalPaths,
    enabled: bool,
    include_failed: bool,
    ensure_docs: EnsureDocs,
    index_document: IndexDocument,
    schema_prefix: str,
    version: str,
    now: Now,
    wav_duration_fn: WavDuration = wav_duration,
    path_exists: PathExists = Path.exists,
) -> dict[str, Any]:
    generated_at = now()
    if not enabled:
        return {
            "schema": f"{schema_prefix}_dictation_journal_write_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": True,
            "enabled": False,
            "message": "dictation journal disabled by config",
        }
    event = journal_event(
        result,
        include_failed=include_failed,
        paths=paths,
        schema_prefix=schema_prefix,
        version=version,
        now=now,
        wav_duration_fn=wav_duration_fn,
    )
    if event is None:
        ensure_errors = ensure_docs()
        return {
            "schema": f"{schema_prefix}_dictation_journal_write_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": not ensure_errors,
            "enabled": True,
            "written": False,
            "write_errors": ensure_errors,
        }

    include_header = not path_exists(paths.markdown_path)
    errors = ensure_docs()
    for error in (
        safe_append_jsonl(paths.jsonl_path, event, 0o664),
        safe_append_text(paths.markdown_path, dictation_contracts.journal_markdown(event, include_header), 0o664),
        safe_atomic_write_json(paths.latest_path, event, 0o664),
        safe_atomic_write_json(paths.index_path, index_document(), 0o664),
    ):
        if error:
            errors.append(error)
    return {
        "schema": f"{schema_prefix}_dictation_journal_write_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not errors,
        "enabled": True,
        "written": not errors,
        "event_id": event.get("id"),
        "paths": event.get("paths"),
        "write_errors": errors,
    }


def journal_latest(
    *,
    paths: DictationJournalPaths,
    ensure_docs: EnsureDocs,
    schema_prefix: str,
    version: str,
    now: Now,
    path_exists: PathExists = Path.exists,
) -> dict[str, Any]:
    ensure_errors = ensure_docs()
    latest, error = load_json_document(paths.latest_path)
    empty = latest is None and error == "missing"
    return {
        "schema": f"{schema_prefix}_dictation_journal_latest_v1",
        "version": version,
        "generated_at": now(),
        "ok": (bool(latest) or empty) and not ensure_errors,
        "path": str(paths.latest_path),
        "exists": path_exists(paths.latest_path),
        "empty": empty,
        "entry": latest if isinstance(latest, dict) else None,
        "load_error": None if empty else error,
        "write_errors": ensure_errors,
    }


def journal_tail(
    *,
    paths: DictationJournalPaths,
    lines: int,
    ensure_docs: EnsureDocs,
    paths_document: PathsDocument,
    schema_prefix: str,
    version: str,
    now: Now,
) -> dict[str, Any]:
    bounded_lines = max(1, min(int(lines), 200))
    ensure_errors = ensure_docs()
    entries: list[dict[str, Any]] = []
    files = sorted(paths.jsonl_root.glob("*/*/*.jsonl"))
    for path in files[-14:]:
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in raw_lines:
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                item["_source_path"] = str(path)
                entries.append(item)
    selected = entries[-bounded_lines:]
    return {
        "schema": f"{schema_prefix}_dictation_journal_tail_v1",
        "version": version,
        "generated_at": now(),
        "ok": not ensure_errors,
        "lines": bounded_lines,
        "entries": selected,
        "paths": paths_document(),
        "write_errors": ensure_errors,
    }


def write_recording_state(path: Path, state: Mapping[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as tmp:
        json.dump(dict(state), tmp, indent=2, sort_keys=False)
        tmp.write("\n")
        tmp_name = tmp.name
    os.chmod(tmp_name, mode)
    os.replace(tmp_name, path)


def read_recording_state(paths: DictationRecordingPaths) -> dict[str, Any] | None:
    if not paths.state_file.exists():
        return None
    try:
        data = json.loads(paths.state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def process_alive(pid: int) -> bool:
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        stat_text = proc_stat.read_text(encoding="utf-8", errors="replace")
        close = stat_text.rfind(")")
        if close != -1:
            fields = stat_text[close + 2 :].split()
            if fields and fields[0] == "Z":
                return False
    except OSError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def recording_is_active(state: Mapping[str, Any] | None, *, alive: ProcessAlive = process_alive) -> bool:
    if not state:
        return False
    pid = int(state.get("pid") or 0)
    return bool(pid and alive(pid))


def recording_age_seconds(
    state: Mapping[str, Any],
    *,
    now_datetime: NowDateTime = current_datetime,
) -> float | None:
    started_at = state.get("started_at")
    if not started_at:
        return None
    try:
        started = dt.datetime.fromisoformat(str(started_at))
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=now_datetime().tzinfo)
    return (now_datetime() - started).total_seconds()


def load_active_recording(
    paths: DictationRecordingPaths,
    *,
    alive: ProcessAlive = process_alive,
) -> dict[str, Any] | None:
    state = read_recording_state(paths)
    if recording_is_active(state, alive=alive):
        return state
    return None


def unlink_recording_state(paths: DictationRecordingPaths) -> None:
    try:
        paths.state_file.unlink()
    except OSError:
        pass


def load_stale_recording(
    paths: DictationRecordingPaths,
    *,
    alive: ProcessAlive = process_alive,
) -> dict[str, Any] | None:
    state = read_recording_state(paths)
    if not state or recording_is_active(state, alive=alive):
        return None
    audio = state.get("audio")
    if audio and Path(str(audio)).exists():
        state["stale"] = True
        return state
    unlink_recording_state(paths)
    return None


def start_recording_process(command: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            command,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    return int(proc.pid)


def signal_recording_process(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def start_recording(
    *,
    paths: DictationRecordingPaths,
    profile: str,
    max_seconds_value: int,
    timeout_available: bool,
    schema_prefix: str,
    now: Now,
    timestamp: FilenameTimestamp = filename_timestamp,
    start_process: StartRecordingProcess = start_recording_process,
) -> dict[str, Any]:
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp()
    audio_path = paths.runtime_dir / f"dictation-{stamp}.wav"
    log_path = paths.runtime_dir / f"dictation-{stamp}.log"
    command = dictation_contracts.recording_command(
        audio_path,
        max_seconds_value=max_seconds_value,
        timeout_available=timeout_available,
    )
    pid = start_process(command, log_path)
    state = dictation_contracts.recording_state(
        pid=pid,
        audio_path=audio_path,
        log_path=log_path,
        profile=profile,
        started_at=now(),
        max_seconds_value=max_seconds_value,
        schema_prefix=schema_prefix,
    )
    write_recording_state(paths.state_file, state, 0o600)
    return state


def stop_recording(
    state: Mapping[str, Any] | None = None,
    *,
    paths: DictationRecordingPaths,
    schema_prefix: str,
    version: str,
    now: Now,
    alive: ProcessAlive = process_alive,
    signal_process: SignalProcess = signal_recording_process,
    monotonic: Monotonic = time.time,
    sleep: Sleep = time.sleep,
    wait_timeout_sec: float = 5.0,
    poll_interval_sec: float = 0.1,
) -> dict[str, Any]:
    current = dict(state) if isinstance(state, Mapping) else load_active_recording(paths, alive=alive)
    if not current:
        return dictation_contracts.stop_inactive_result(schema_prefix, version, now())

    pid = int(current["pid"])
    signal_process(pid, int(signal.SIGINT))
    deadline = monotonic() + wait_timeout_sec
    while monotonic() < deadline and alive(pid):
        sleep(poll_interval_sec)
    if alive(pid):
        signal_process(pid, int(signal.SIGTERM))

    unlink_recording_state(paths)
    return dictation_contracts.stopped_recording_result(
        dict(current),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now(),
    )


def unix_socket_json_line_request(
    socket_path: Path,
    request: Mapping[str, Any],
    connect_timeout: float,
    response_timeout: float,
) -> str | None:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(connect_timeout)
        client.connect(str(socket_path))
        client.settimeout(response_timeout)
        client.sendall(json.dumps(dict(request)).encode("utf-8") + b"\n")
        client.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError:
        return None
    finally:
        client.close()
    return b"".join(chunks).decode("utf-8", errors="replace").strip()


def server_audio_input(
    audio: str,
    runtime_options: Mapping[str, Any],
    *,
    paths: DictationTranscriptionPaths,
    run_command: RunCommand,
    command_exists: CommandExists,
    wav_sample_rate: WavSampleRate,
    wav_duration: WavDuration,
) -> tuple[str, dict[str, Any] | None]:
    if not dictation_contracts.bool_value(runtime_options.get("audio_preprocess"), True):
        return audio, None

    audio_path = Path(audio)
    sample_rate = wav_sample_rate(audio_path)
    if sample_rate is None or sample_rate == 16000:
        return audio, None

    meta: dict[str, Any] = {
        "enabled": True,
        "kind": "client_resample_for_warm_server",
        "input": str(audio_path),
        "input_sample_rate": sample_rate,
        "target_sample_rate": 16000,
        "resampler": "ffmpeg" if command_exists("ffmpeg") else None,
    }
    if not command_exists("ffmpeg"):
        meta["ok"] = False
        meta["error"] = "ffmpeg not found; warm dictation server requires 16 kHz PCM input"
        return audio, meta

    paths.server_audio_dir.mkdir(parents=True, exist_ok=True)
    stamp = audio_path.stat().st_mtime_ns if audio_path.exists() else 0
    digest = hashlib.sha256(f"{audio_path}:{stamp}".encode("utf-8")).hexdigest()[:12]
    output = paths.server_audio_dir / f"{audio_path.stem}-{digest}-16k.wav"
    completed = run_command(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        30.0,
        None,
    )
    meta.update(
        {
            "ok": bool(completed.get("ok")) and output.exists() and wav_sample_rate(output) == 16000,
            "output": str(output),
            "stderr": str(completed.get("stderr") or "")[-1000:],
            "returncode": completed.get("returncode"),
        }
    )
    if meta["ok"]:
        meta["output_duration_sec"] = wav_duration(output)
        return str(output), meta
    return audio, meta


def server_transcribe(
    audio: str,
    profile: Mapping[str, Any],
    *,
    paths: DictationTranscriptionPaths,
    run_command: RunCommand,
    command_exists: CommandExists,
    wav_sample_rate: WavSampleRate,
    wav_duration: WavDuration,
    env: Mapping[str, str],
    schema_prefix: str,
    version: str,
    generated_at: str,
    monotonic: Monotonic = time.monotonic,
    socket_request: SocketJsonLineRequest = unix_socket_json_line_request,
) -> dict[str, Any] | None:
    if str(env.get("ABYSS_DICTATION_SERVER", "1")).lower() in {"0", "false", "no"}:
        return None
    if not paths.server_socket.exists():
        return None

    runtime_options = profile.get("runtime", {}) if isinstance(profile.get("runtime"), dict) else {}
    server_audio, client_preprocess = server_audio_input(
        audio,
        runtime_options,
        paths=paths,
        run_command=run_command,
        command_exists=command_exists,
        wav_sample_rate=wav_sample_rate,
        wav_duration=wav_duration,
    )
    request = dictation_contracts.server_transcript_request(
        audio=server_audio,
        profile=dict(profile),
        runtime_options=dict(runtime_options),
        max_new_tokens=dictation_contracts.env_override_int(
            env,
            "ABYSS_DICTATION_MAX_NEW_TOKENS",
            int(profile.get("max_new_tokens", 192)),
            16,
            1024,
        ),
        num_beams=int(str(env.get("ABYSS_DICTATION_NUM_BEAMS", str(profile.get("num_beams", 1))))),
    )
    started = monotonic()
    raw = socket_request(
        paths.server_socket,
        request,
        float(env.get("ABYSS_DICTATION_SERVER_CONNECT_TIMEOUT", "0.35")),
        float(env.get("ABYSS_DICTATION_SERVER_TIMEOUT", "600")),
    )
    if raw is None:
        return None
    return dictation_contracts.server_transcript_result_from_raw(
        raw,
        profile=dict(profile),
        socket_path=paths.server_socket,
        client_elapsed_sec=monotonic() - started,
        client_preprocess=client_preprocess,
        original_audio=audio,
        server_audio=server_audio,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def transcribe_audio(
    audio: str,
    profile: Mapping[str, Any],
    profile_selection: Mapping[str, Any],
    *,
    paths: DictationTranscriptionPaths,
    run_command: RunCommand,
    command_exists: CommandExists,
    wav_sample_rate: WavSampleRate,
    wav_duration: WavDuration,
    env: Mapping[str, str],
    schema_prefix: str,
    version: str,
    now: Now,
    monotonic: Monotonic = time.monotonic,
    socket_request: SocketJsonLineRequest = unix_socket_json_line_request,
) -> dict[str, Any]:
    model_dir = Path(str(profile["model_dir"]))
    if not model_dir.exists():
        return dictation_contracts.transcript_error_result(
            f"model directory missing: {model_dir}",
            profile=dict(profile),
            profile_selection=dict(profile_selection),
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now(),
        )
    if not paths.helper.exists():
        return dictation_contracts.transcript_error_result(
            f"helper missing: {paths.helper}",
            profile=dict(profile),
            profile_selection=dict(profile_selection),
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now(),
        )

    server_data = server_transcribe(
        audio,
        profile,
        paths=paths,
        run_command=run_command,
        command_exists=command_exists,
        wav_sample_rate=wav_sample_rate,
        wav_duration=wav_duration,
        env=env,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now(),
        monotonic=monotonic,
        socket_request=socket_request,
    )
    if server_data is not None:
        server_data["profile_selection"] = dict(profile_selection)
        return server_data

    runtime_options = profile.get("runtime", {}) if isinstance(profile.get("runtime"), dict) else {}
    command = dictation_contracts.helper_transcript_command(
        helper=paths.helper,
        audio=audio,
        model_dir=model_dir,
        profile=dict(profile),
        max_new_tokens=dictation_contracts.env_override_int(
            env,
            "ABYSS_DICTATION_MAX_NEW_TOKENS",
            int(profile.get("max_new_tokens", 192)),
            16,
            1024,
        ),
        num_beams=int(str(env.get("ABYSS_DICTATION_NUM_BEAMS", str(profile.get("num_beams", 1))))),
    )
    started = monotonic()
    completed = run_command(
        command,
        600.0,
        dictation_contracts.runtime_env(dict(runtime_options), env),
    )
    if not completed.get("ok"):
        return dictation_contracts.helper_failure_result(
            dict(completed),
            profile=dict(profile),
            profile_selection=dict(profile_selection),
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now(),
        )
    stdout = str(completed.get("stdout") or "").strip()
    data = dictation_contracts.parse_transcript_json(stdout)
    if data is None:
        return dictation_contracts.helper_invalid_json_result(
            stdout,
            str(completed.get("stderr") or ""),
            profile=dict(profile),
            profile_selection=dict(profile_selection),
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now(),
        )
    return dictation_contracts.helper_success_result(
        data,
        profile=dict(profile),
        profile_selection=dict(profile_selection),
        client_elapsed_sec=monotonic() - started,
    )
