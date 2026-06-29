from __future__ import annotations

import json
import os
import socket
import time
import wave
from pathlib import Path
from typing import Any, Callable, Mapping

from . import ai_tts_contracts


PathExistsPort = Callable[[Path], bool]
RunPort = Callable[..., Mapping[str, Any]]
ServerRequestPort = Callable[..., Mapping[str, Any]]
SocketFactoryPort = Callable[[int, int], Any]
SubprocessEnvPort = Callable[[Mapping[str, str]], Mapping[str, str]]
ResourceSnapshotPort = Callable[[], Mapping[str, Any]]
ResourceProfilePort = Callable[[Mapping[str, Any], Mapping[str, Any], str, str], Mapping[str, Any]]
TimePort = Callable[[], float]
SleepPort = Callable[[float], None]


def _path_exists(path: Path, path_exists: PathExistsPort) -> bool:
    try:
        return bool(path_exists(path))
    except OSError:
        return False


def server_socket_path(env: Mapping[str, str], user_id: int) -> Path:
    runtime_root = env.get("XDG_RUNTIME_DIR") or f"/run/user/{user_id}"
    default_socket = Path(runtime_root) / "abyss-machine" / "tts" / "server.sock"
    return Path(env.get("ABYSS_TTS_SERVER_SOCKET", str(default_socket)))


def server_request(
    *,
    payload: Mapping[str, Any],
    socket_path: Path,
    timeout: float = 2.0,
    path_exists: PathExistsPort | None = None,
    socket_factory: SocketFactoryPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    socket_factory = socket_factory or socket.socket
    if not _path_exists(socket_path, path_exists):
        return ai_tts_contracts.server_socket_missing_result(socket_path)
    try:
        with socket_factory(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(socket_path))
            client.sendall(json.dumps(dict(payload), ensure_ascii=False).encode("utf-8") + b"\n")
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except OSError as exc:
        return ai_tts_contracts.server_transport_error_result(exc, socket_path)
    raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
    return ai_tts_contracts.parse_server_response(raw, socket_path)


def server_status_probe(
    *,
    socket_path: Path,
    request: ServerRequestPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    return {
        "socket_exists": _path_exists(socket_path, path_exists),
        "ping": dict(request({"command": "ping"}, timeout=1.0)),
    }


def server_stop_probe(
    *,
    socket_path: Path,
    request: ServerRequestPort,
    timeout_sec: float = 3.0,
    wait_sec: float = 5.0,
    path_exists: PathExistsPort | None = None,
    time_now: TimePort | None = None,
    sleep: SleepPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    time_now = time_now or time.time
    sleep = sleep or time.sleep
    response = dict(request({"command": "shutdown"}, timeout=timeout_sec))
    deadline = time_now() + wait_sec
    while response.get("ok") and _path_exists(socket_path, path_exists) and time_now() < deadline:
        sleep(0.1)
    return {
        "response": response,
        "socket_exists_after": _path_exists(socket_path, path_exists),
    }


def synth_subprocess_env(
    *,
    cache_root: Path,
    allow_download: bool,
    build_env: SubprocessEnvPort,
) -> dict[str, str]:
    env = dict(
        build_env(
            {
                "HF_HOME": str(cache_root / "huggingface"),
                "HUGGINGFACE_HUB_CACHE": str(cache_root / "huggingface/hub"),
                "TRANSFORMERS_CACHE": str(cache_root / "huggingface/transformers"),
                "HF_XET_CACHE": str(cache_root / "huggingface/xet"),
                "XDG_CACHE_HOME": str(cache_root / "xdg"),
                "OPENVINO_LOG_LEVEL": "2",
            }
        )
    )
    if allow_download:
        env["HF_HUB_OFFLINE"] = "0"
        env["TRANSFORMERS_OFFLINE"] = "0"
    return env


def synth_subprocess(
    *,
    engine: str,
    python: str,
    profile: Mapping[str, Any],
    config: Mapping[str, Any],
    text: str,
    output: Path,
    cache_dir: Path,
    timeout_sec: float,
    subprocess_env: Mapping[str, str],
    run_command: RunPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    env = dict(subprocess_env)
    if engine == "babelvox":
        out = dict(
            run_command(
                ai_tts_contracts.babelvox_synth_command(
                    python=python,
                    profile=dict(profile),
                    config=dict(config),
                    text=text,
                    output=output,
                    cache_dir=cache_dir,
                ),
                timeout=timeout_sec,
                env=env,
            )
        )
        return ai_tts_contracts.synth_subprocess_result(out, output_exists=_path_exists(output, path_exists))
    if engine == "qwen3_tts_openvino":
        adapter_src = str(profile.get("adapter_src") or "")
        env["PYTHONPATH"] = adapter_src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        out = dict(
            run_command(
                ai_tts_contracts.qwen3_openvino_synth_command(
                    python=python,
                    profile=dict(profile),
                    config=dict(config),
                    text=text,
                    output=output,
                ),
                timeout=timeout_sec,
                env=env,
            )
        )
        return ai_tts_contracts.synth_subprocess_result(
            out,
            output_exists=_path_exists(output, path_exists),
            stderr_tail_limit=5000,
        )
    if engine == "piper":
        return {"error": "piper synthesis is not configured with a voice model"}
    return {"error": f"TTS engine is not executable by this host adapter: {engine}"}


def audio_file_summary(
    output: Path,
    *,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    exists = _path_exists(output, path_exists)
    duration_sec: float | None = None
    sample_rate: int | None = None
    size_bytes: int | None = None
    if exists:
        try:
            size_bytes = output.stat().st_size
        except OSError:
            size_bytes = None
        try:
            with wave.open(str(output), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
            sample_rate = int(rate) if rate else None
            duration_sec = round(frames / rate, 3) if rate else None
        except (OSError, wave.Error):
            duration_sec = None
            sample_rate = None
    return ai_tts_contracts.audio_summary(
        exists=exists,
        duration_sec=duration_sec,
        sample_rate=sample_rate,
        size_bytes=size_bytes,
    )


def synth_runtime_report(
    *,
    result: Mapping[str, Any],
    output: Path,
    started_at: float,
    time_now: TimePort,
    resources_before: Mapping[str, Any],
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    scope: str,
    basis: str,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    data = dict(result)
    data["wall_sec"] = round(float(time_now()) - float(started_at), 3)
    audio = audio_file_summary(output, path_exists=path_exists)
    data["audio"] = audio
    data["rtf"] = ai_tts_contracts.rtf(data.get("wall_sec"), audio.get("duration_sec"))
    data["resource_profile"] = dict(
        resource_profile(
            dict(resources_before),
            dict(resource_snapshot()),
            scope,
            basis,
        )
    )
    return data
