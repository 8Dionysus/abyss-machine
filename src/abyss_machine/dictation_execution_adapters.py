from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from typing import Any, Callable, Mapping

from . import dictation_contracts


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


@dataclass(frozen=True)
class DictationTranscriptionPaths:
    helper: Path
    server_socket: Path
    server_audio_dir: Path


@dataclass(frozen=True)
class DictationRecordingPaths:
    runtime_dir: Path
    state_file: Path


def current_datetime() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone()


def filename_timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


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
