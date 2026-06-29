from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import socket
import socketserver
import sys
import time
import wave
from pathlib import Path
from typing import Any, Callable, Mapping

from . import ai_tts_contracts


PathExistsPort = Callable[[Path], bool]
RunPort = Callable[..., Mapping[str, Any]]
ServerRequestPort = Callable[..., Mapping[str, Any]]
SocketFactoryPort = Callable[[int, int], Any]
ServerSynthPort = Callable[[Mapping[str, Any]], Mapping[str, Any]]
UnloadModelPort = Callable[[], Any]
ModuleImportPort = Callable[[str], Any]
PathInsertPort = Callable[[str], None]
DefaultOutputPathPort = Callable[[str], Path]
SubprocessEnvPort = Callable[[Mapping[str, str]], Mapping[str, str]]
ResourceSnapshotPort = Callable[[], Mapping[str, Any]]
ResourceProfilePort = Callable[[Mapping[str, Any], Mapping[str, Any], str, str], Mapping[str, Any]]
TimePort = Callable[[], float]
SleepPort = Callable[[float], None]
TimestampPort = Callable[[], str]


class Qwen3OpenVINOServerImportError(RuntimeError):
    def __init__(self, original: Exception) -> None:
        super().__init__(repr(original))
        self.original = original


class Qwen3OpenVINOServerRuntime:
    def __init__(
        self,
        *,
        profile_key: str,
        profile: Mapping[str, Any],
        config: Mapping[str, Any],
        schema_prefix: str,
        version: str,
        started_at: str,
        load_sec: float,
        server_pid: int,
        engine: Any,
        soundfile_module: Any,
        custom_voice_request: Any,
        language_type: Any,
        sampling_params: Any,
        speaker_type: Any,
        now_iso: TimestampPort,
        time_now: TimePort,
        default_output_path: DefaultOutputPathPort,
    ) -> None:
        self.profile_key = profile_key
        self.profile = dict(profile)
        self.config = dict(config)
        self.schema_prefix = schema_prefix
        self.version = version
        self.started_at = started_at
        self.load_sec = load_sec
        self.server_pid = server_pid
        self.engine = engine
        self.soundfile_module = soundfile_module
        self.CustomVoiceRequest = custom_voice_request
        self.Language = language_type
        self.SamplingParams = sampling_params
        self.Speaker = speaker_type
        self.now_iso = now_iso
        self.time_now = time_now
        self.default_output_path = default_output_path

    def unload_model(self) -> Any:
        return self.engine.unload_model()

    def synth_once(self, request: Mapping[str, Any]) -> dict[str, Any]:
        text = str(request.get("text") or "").strip()
        if not text:
            return ai_tts_contracts.server_synth_error_result("text is empty", self.profile_key)
        requested_profile = str(request.get("profile") or self.profile_key)
        if requested_profile != self.profile_key:
            return ai_tts_contracts.server_synth_error_result(
                "server profile mismatch",
                self.profile_key,
                server_profile=self.profile_key,
                requested_profile=requested_profile,
            )
        output = Path(str(request.get("output") or self.default_output_path(f"server-{self.profile_key}"))).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        options = dict(request.get("options") or {}) if isinstance(request.get("options"), dict) else {}
        for key in ai_tts_contracts.TTS_SYNTH_OPTION_KEYS:
            options.setdefault(key, self.profile.get(key))
        sampling = self.SamplingParams(
            max_new_tokens=int(options.get("max_new_tokens") or 512),
            do_sample=not bool(options.get("no_sample", False)),
            temperature=float(options.get("temperature") if options.get("temperature") is not None else 0.8),
            top_k=int(options.get("top_k") if options.get("top_k") is not None else 30),
            top_p=float(options.get("top_p") if options.get("top_p") is not None else 1.0),
            repetition_penalty=float(options.get("repetition_penalty") if options.get("repetition_penalty") is not None else 1.05),
        )
        language = str(request.get("language") or self.profile.get("language") or self.config.get("language") or "russian")
        req_language = None if language.lower() in {"auto", "none", "null"} else self.Language(language.lower())
        tts_request = self.CustomVoiceRequest(
            text=text,
            speaker=self.Speaker(str(request.get("speaker") or self.profile.get("speaker") or "ryan").lower()),
            language=req_language,
            instruct=str(request.get("instruct") or self.profile.get("instruct") or "") or None,
            sampling=sampling,
        )
        synth_started = self.time_now()
        wav, sr = self.engine.generate(tts_request)
        synth_sec = round(self.time_now() - synth_started, 3)
        self.soundfile_module.write(str(output), wav, sr)
        audio_sec = round(float(len(wav)) / float(sr), 3) if sr else None
        return ai_tts_contracts.server_synth_success_document(
            schema_prefix=self.schema_prefix,
            version=self.version,
            generated_at=self.now_iso(),
            profile=self.profile_key,
            server_pid=self.server_pid,
            server_started_at=self.started_at,
            server_load_sec=self.load_sec,
            device=self.profile.get("device"),
            precision=self.profile.get("precision"),
            output=output,
            text_chars=len(text),
            synth_sec=synth_sec,
            sample_rate=int(sr),
            samples=int(len(wav)),
            audio_sec=audio_sec,
        )


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


def server_loop_response(
    *,
    request: Mapping[str, Any],
    server_state: Mapping[str, Any],
    profile: str,
    synth_once: ServerSynthPort,
) -> tuple[dict[str, Any], bool]:
    command = str(request.get("command") or "status")
    if command == "ping":
        response = dict(server_state)
        response["command"] = "ping"
        return response, False
    if command == "status":
        response = dict(server_state)
        response["command"] = "status"
        return response, False
    if command == "synth":
        return dict(synth_once(dict(request))), False
    if command == "shutdown":
        return {"ok": True, "command": "shutdown", "profile": profile}, True
    return {"ok": False, "error": f"unknown command: {command}"}, False


def _unload_model(unload_model: UnloadModelPort | None) -> None:
    if unload_model is None:
        return
    try:
        unload_result = unload_model()
        if inspect.isawaitable(unload_result):
            asyncio.run(unload_result)
    except Exception:
        pass


def run_server_loop(
    *,
    socket_path: Path,
    server_state: Mapping[str, Any],
    profile: str,
    synth_once: ServerSynthPort,
    stopped_at: TimestampPort,
    unload_model: UnloadModelPort | None = None,
    chmod_mode: int = 0o660,
    read_limit: int = 2 * 1024 * 1024,
) -> dict[str, Any]:
    socket_path = Path(socket_path).expanduser()
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            should_shutdown = False
            try:
                raw = self.rfile.readline(read_limit).decode("utf-8", errors="replace")
                request = json.loads(raw) if raw.strip() else {}
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                response, should_shutdown = server_loop_response(
                    request=request,
                    server_state=server_state,
                    profile=profile,
                    synth_once=synth_once,
                )
            except Exception as exc:
                response = {"ok": False, "error": repr(exc)}
            if should_shutdown:
                self.server.should_shutdown = True  # type: ignore[attr-defined]
            self.wfile.write(json.dumps(response, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")

    class UnixServer(socketserver.UnixStreamServer):
        allow_reuse_address = True

    server: UnixServer | None = None
    try:
        server = UnixServer(str(socket_path), Handler)
        server.should_shutdown = False  # type: ignore[attr-defined]
        os.chmod(socket_path, chmod_mode)
        while not getattr(server, "should_shutdown", False):
            server.handle_request()
    finally:
        _unload_model(unload_model)
        if server is not None:
            server.server_close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass
    return {"ok": True, "profile": profile, "socket": str(socket_path), "stopped_at": stopped_at()}


def _insert_path(path: str) -> None:
    sys.path.insert(0, path)


def load_qwen3_openvino_server_runtime(
    *,
    profile_key: str,
    profile: Mapping[str, Any],
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    now_iso: TimestampPort,
    server_pid: int,
    default_output_path: DefaultOutputPathPort,
    time_now: TimePort | None = None,
    import_module: ModuleImportPort | None = None,
    path_insert: PathInsertPort | None = None,
) -> Qwen3OpenVINOServerRuntime:
    time_now = time_now or time.perf_counter
    import_module = import_module or importlib.import_module
    path_insert = path_insert or _insert_path
    adapter_src = str(profile.get("adapter_src") or "")
    if adapter_src:
        path_insert(adapter_src)
    try:
        soundfile_module = import_module("soundfile")
        ov_infer = import_module("openvino.ov_infer")
        CustomVoiceRequest = getattr(ov_infer, "CustomVoiceRequest")
        Language = getattr(ov_infer, "Language")
        ModelLoadConfig = getattr(ov_infer, "ModelLoadConfig")
        ModelType = getattr(ov_infer, "ModelType")
        OVQwen3TTS = getattr(ov_infer, "OVQwen3TTS")
        SamplingParams = getattr(ov_infer, "SamplingParams")
        Speaker = getattr(ov_infer, "Speaker")
    except Exception as exc:
        raise Qwen3OpenVINOServerImportError(exc) from exc

    model_type = ModelType(str(profile.get("model_type") or "custom_voice"))
    engine = OVQwen3TTS()
    load_started = time_now()
    engine.load_model(
        ModelLoadConfig(
            ov_dir=str(profile.get("ov_dir") or ""),
            device=str(profile.get("device") or "GPU"),
            cp_device=str(profile.get("cp_device") or "") or None,
            model_type=model_type,
        )
    )
    load_sec = round(time_now() - load_started, 3)
    return Qwen3OpenVINOServerRuntime(
        profile_key=profile_key,
        profile=profile,
        config=config,
        schema_prefix=schema_prefix,
        version=version,
        started_at=now_iso(),
        load_sec=load_sec,
        server_pid=server_pid,
        engine=engine,
        soundfile_module=soundfile_module,
        custom_voice_request=CustomVoiceRequest,
        language_type=Language,
        sampling_params=SamplingParams,
        speaker_type=Speaker,
        now_iso=now_iso,
        time_now=time_now,
        default_output_path=default_output_path,
    )


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
