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
PathExists = Callable[[Path], bool]


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
