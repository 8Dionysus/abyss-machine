from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import socket
import time
from typing import Any, Callable, Mapping

from . import dictation_contracts


RunCommand = Callable[[list[str], float, Mapping[str, str] | None], Mapping[str, Any]]
CommandExists = Callable[[str], bool]
WavSampleRate = Callable[[Path], int | None]
WavDuration = Callable[[Path], float | None]
Now = Callable[[], str]
Monotonic = Callable[[], float]
SocketJsonLineRequest = Callable[[Path, Mapping[str, Any], float, float], str | None]


@dataclass(frozen=True)
class DictationTranscriptionPaths:
    helper: Path
    server_socket: Path
    server_audio_dir: Path


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
