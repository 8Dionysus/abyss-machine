from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import time
import types
from typing import Any
import wave

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import ai_tts_adapters


STAMP = "2026-06-29T12:00:00+00:00"


def test_tts_server_socket_path_and_transport_are_fakeable() -> None:
    assert ai_tts_adapters.server_socket_path({}, 1000) == Path("/run/user/1000/abyss-machine/tts/server.sock")
    assert ai_tts_adapters.server_socket_path({"ABYSS_TTS_SERVER_SOCKET": "/tmp/tts.sock"}, 1000) == Path("/tmp/tts.sock")

    missing = ai_tts_adapters.server_request(
        payload={"command": "ping"},
        socket_path=Path("/missing.sock"),
        path_exists=lambda path: False,
    )
    assert missing == {"ok": False, "error": "server socket missing", "socket": "/missing.sock"}

    class FakeSocket:
        def __init__(self) -> None:
            self.sent = b""
            self.timeout = 0.0
            self.connected_to = ""
            self.chunks = [b"debug\n", b'{"ok": true, "profile": "quality"}\n', b""]

        def __enter__(self) -> "FakeSocket":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def connect(self, target: str) -> None:
            self.connected_to = target

        def sendall(self, payload: bytes) -> None:
            self.sent += payload

        def shutdown(self, _mode: int) -> None:
            return None

        def recv(self, _size: int) -> bytes:
            return self.chunks.pop(0)

    fake = FakeSocket()
    result = ai_tts_adapters.server_request(
        payload={"command": "ping", "profile": "quality"},
        socket_path=Path("/tmp/tts.sock"),
        timeout=1.5,
        path_exists=lambda path: True,
        socket_factory=lambda _family, _kind: fake,
    )

    assert result == {"ok": True, "profile": "quality"}
    assert fake.timeout == 1.5
    assert fake.connected_to == "/tmp/tts.sock"
    assert json.loads(fake.sent.decode("utf-8")) == {"command": "ping", "profile": "quality"}


def test_tts_server_status_and_stop_probes_keep_wait_loop_fakeable() -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        calls.append({"payload": payload, "timeout": timeout})
        return {"ok": True, "profile": "quality-compact"}

    status = ai_tts_adapters.server_status_probe(
        socket_path=Path("/tmp/tts.sock"),
        request=fake_request,
        path_exists=lambda path: True,
    )
    path_states = [True, False, False]
    sleeps: list[float] = []
    stop = ai_tts_adapters.server_stop_probe(
        socket_path=Path("/tmp/tts.sock"),
        request=fake_request,
        path_exists=lambda path: path_states.pop(0),
        time_now=lambda: 1.0,
        sleep=sleeps.append,
    )

    assert status == {"socket_exists": True, "ping": {"ok": True, "profile": "quality-compact"}}
    assert stop == {"response": {"ok": True, "profile": "quality-compact"}, "socket_exists_after": False}
    assert calls == [
        {"payload": {"command": "ping"}, "timeout": 1.0},
        {"payload": {"command": "shutdown"}, "timeout": 3.0},
    ]
    assert sleeps == [0.1]


def test_tts_server_loop_response_dispatch_is_fakeable() -> None:
    synth_calls: list[dict[str, Any]] = []

    def fake_synth(request: dict[str, Any]) -> dict[str, Any]:
        synth_calls.append(request)
        return {"ok": True, "command": "synth", "output": "/tmp/out.wav"}

    server_state = {"ok": True, "profile": "quality", "socket": "/tmp/tts.sock"}

    ping, stop_ping = ai_tts_adapters.server_loop_response(
        request={"command": "ping"},
        server_state=server_state,
        profile="quality",
        synth_once=fake_synth,
    )
    status, stop_status = ai_tts_adapters.server_loop_response(
        request={},
        server_state=server_state,
        profile="quality",
        synth_once=fake_synth,
    )
    synth, stop_synth = ai_tts_adapters.server_loop_response(
        request={"command": "synth", "text": "hello"},
        server_state=server_state,
        profile="quality",
        synth_once=fake_synth,
    )
    shutdown, stop_shutdown = ai_tts_adapters.server_loop_response(
        request={"command": "shutdown"},
        server_state=server_state,
        profile="quality",
        synth_once=fake_synth,
    )
    unknown, stop_unknown = ai_tts_adapters.server_loop_response(
        request={"command": "bad"},
        server_state=server_state,
        profile="quality",
        synth_once=fake_synth,
    )

    assert ping["command"] == "ping"
    assert ping["profile"] == "quality"
    assert stop_ping is False
    assert status["command"] == "status"
    assert stop_status is False
    assert synth == {"ok": True, "command": "synth", "output": "/tmp/out.wav"}
    assert synth_calls == [{"command": "synth", "text": "hello"}]
    assert stop_synth is False
    assert shutdown == {"ok": True, "command": "shutdown", "profile": "quality"}
    assert stop_shutdown is True
    assert unknown == {"ok": False, "error": "unknown command: bad"}
    assert stop_unknown is False


def test_tts_server_loop_handles_socket_requests_and_cleanup(tmp_path: Path) -> None:
    socket_path = tmp_path / "tts.sock"
    synth_calls: list[dict[str, Any]] = []
    unload_calls: list[str] = []
    thread_result: dict[str, Any] = {}

    def fake_synth(request: dict[str, Any]) -> dict[str, Any]:
        synth_calls.append(request)
        return {"ok": True, "command": "synth", "output": str(tmp_path / "out.wav")}

    def target() -> None:
        try:
            thread_result["result"] = ai_tts_adapters.run_server_loop(
                socket_path=socket_path,
                server_state={"ok": True, "profile": "quality", "socket": str(socket_path)},
                profile="quality",
                synth_once=fake_synth,
                stopped_at=lambda: STAMP,
                unload_model=lambda: unload_calls.append("unloaded"),
            )
        except BaseException as exc:  # pragma: no cover - surfaced after join.
            thread_result["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    deadline = time.time() + 2.0
    while not socket_path.exists() and thread.is_alive() and time.time() < deadline:
        time.sleep(0.01)

    assert socket_path.exists()

    ping = ai_tts_adapters.server_request(payload={"command": "ping"}, socket_path=socket_path, timeout=1.0)
    synth = ai_tts_adapters.server_request(
        payload={"command": "synth", "text": "hello", "profile": "quality"},
        socket_path=socket_path,
        timeout=1.0,
    )
    shutdown = ai_tts_adapters.server_request(payload={"command": "shutdown"}, socket_path=socket_path, timeout=1.0)

    thread.join(timeout=2.0)
    if "error" in thread_result:
        raise thread_result["error"]

    assert ping["command"] == "ping"
    assert ping["profile"] == "quality"
    assert synth == {"ok": True, "command": "synth", "output": str(tmp_path / "out.wav")}
    assert synth_calls == [{"command": "synth", "text": "hello", "profile": "quality"}]
    assert shutdown == {"ok": True, "command": "shutdown", "profile": "quality"}
    assert thread_result["result"] == {
        "ok": True,
        "profile": "quality",
        "socket": str(socket_path),
        "stopped_at": STAMP,
    }
    assert unload_calls == ["unloaded"]
    assert not socket_path.exists()


def test_tts_synth_subprocess_env_and_runner_are_fakeable(tmp_path: Path) -> None:
    profile = {
        "device": "GPU",
        "precision": "fp16",
        "adapter_src": "/srv/abyss-machine/tools/tts/qwen3",
        "ov_dir": "/srv/abyss-machine/runtimes/tts/qwen3",
        "model_type": "custom_voice",
        "cp_device": "",
        "speaker": "Ryan",
        "language": "Russian",
        "temperature": 0.7,
    }
    env = ai_tts_adapters.synth_subprocess_env(
        cache_root=tmp_path / "cache",
        allow_download=True,
        build_env=lambda extra: {"BASE": "1", **dict(extra)},
    )
    calls: list[dict[str, Any]] = []

    def fake_run(command: list[str], timeout: float, env: dict[str, str]) -> dict[str, Any]:
        calls.append({"command": command, "timeout": timeout, "env": env})
        return {"ok": True, "returncode": 0, "stdout": '{"ok": true, "engine": "qwen3_tts_openvino"}', "stderr": "minor"}

    result = ai_tts_adapters.synth_subprocess(
        engine="qwen3_tts_openvino",
        python="/venv/bin/python",
        profile=profile,
        config={"language": "Russian"},
        text="hello",
        output=tmp_path / "out.wav",
        cache_dir=tmp_path / "cache" / "quality",
        timeout_sec=17.0,
        subprocess_env=env,
        run_command=fake_run,
        path_exists=lambda path: True,
    )
    unsupported = ai_tts_adapters.synth_subprocess(
        engine="other",
        python="/venv/bin/python",
        profile=profile,
        config={},
        text="hello",
        output=tmp_path / "out.wav",
        cache_dir=tmp_path / "cache" / "quality",
        timeout_sec=17.0,
        subprocess_env={},
        run_command=fake_run,
    )

    assert env["HF_HOME"].endswith("/cache/huggingface")
    assert env["HF_HUB_OFFLINE"] == "0"
    assert env["TRANSFORMERS_OFFLINE"] == "0"
    assert result["ok"] is True
    assert result["subprocess"]["engine"] == "qwen3_tts_openvino"
    assert calls[0]["command"][3] == "/srv/abyss-machine/tools/tts/qwen3"
    assert calls[0]["timeout"] == 17.0
    assert calls[0]["env"]["PYTHONPATH"].split(":")[0] == "/srv/abyss-machine/tools/tts/qwen3"
    assert unsupported["error"] == "TTS engine is not executable by this host adapter: other"


def test_tts_audio_summary_and_runtime_report_are_fakeable(tmp_path: Path) -> None:
    output = tmp_path / "out.wav"
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 8000)

    missing = ai_tts_adapters.audio_file_summary(tmp_path / "missing.wav")
    assert missing == {"exists": False, "duration_sec": None, "sample_rate": None, "size_bytes": None}

    summary = ai_tts_adapters.audio_file_summary(output)
    assert summary["exists"] is True
    assert summary["duration_sec"] == 0.5
    assert summary["sample_rate"] == 16000
    assert summary["size_bytes"] and summary["size_bytes"] > 44

    profile_calls: list[dict[str, Any]] = []

    def fake_resource_profile(before: dict[str, Any], after: dict[str, Any], scope: str, basis: str) -> dict[str, Any]:
        profile_calls.append({"before": before, "after": after, "scope": scope, "basis": basis})
        return {"scope": scope, "basis": basis}

    report = ai_tts_adapters.synth_runtime_report(
        result={"ok": True},
        output=output,
        started_at=10.0,
        time_now=lambda: 11.0,
        resources_before={"cpu": "before"},
        resource_snapshot=lambda: {"cpu": "after"},
        resource_profile=fake_resource_profile,
        scope="child_process",
        basis="TTS synth subprocess",
    )

    assert report["wall_sec"] == 1.0
    assert report["audio"]["duration_sec"] == 0.5
    assert report["rtf"] == 2.0
    assert report["resource_profile"] == {"scope": "child_process", "basis": "TTS synth subprocess"}
    assert profile_calls == [
        {
            "before": {"cpu": "before"},
            "after": {"cpu": "after"},
            "scope": "child_process",
            "basis": "TTS synth subprocess",
        }
    ]


def test_cli_tts_server_wrappers_bind_adapter_ports(monkeypatch) -> None:
    from abyss_machine import cli

    calls: dict[str, Any] = {}

    def fake_socket_path(env: dict[str, str], user_id: int) -> Path:
        calls["socket_path"] = {"env": env, "user_id": user_id}
        return Path("/tmp/tts.sock")

    def fake_request(**kwargs: Any) -> dict[str, Any]:
        calls["request"] = kwargs
        return {"ok": True, "profile": "quality-compact"}

    def fake_status_probe(**kwargs: Any) -> dict[str, Any]:
        calls["status_probe"] = kwargs
        return {"socket_exists": True, "ping": {"ok": True, "profile": "quality-compact"}}

    def fake_stop_probe(**kwargs: Any) -> dict[str, Any]:
        calls["stop_probe"] = kwargs
        return {"socket_exists_after": False, "response": {"ok": True, "profile": "quality-compact"}}

    monkeypatch.setenv("ABYSS_TTS_SERVER_SOCKET", "/tmp/tts.sock")
    monkeypatch.setattr(cli.os, "getuid", lambda: 1000)
    monkeypatch.setattr(cli, "now_iso", lambda: STAMP)
    monkeypatch.setattr(cli, "user_systemd_unit", lambda name: name)
    monkeypatch.setattr(cli.ai_tts_adapters, "server_socket_path", fake_socket_path)
    monkeypatch.setattr(cli.ai_tts_adapters, "server_request", fake_request)
    monkeypatch.setattr(cli.ai_tts_adapters, "server_status_probe", fake_status_probe)
    monkeypatch.setattr(cli.ai_tts_adapters, "server_stop_probe", fake_stop_probe)

    request = cli.ai_tts_server_request({"command": "status"}, timeout=4.0)
    status = cli.ai_tts_server_status(write_latest=False)
    stop = cli.ai_tts_server_stop(write_latest=False)

    assert request == {"ok": True, "profile": "quality-compact"}
    assert calls["request"]["payload"] == {"command": "status"}
    assert calls["request"]["socket_path"] == Path("/tmp/tts.sock")
    assert calls["request"]["timeout"] == 4.0
    assert calls["request"]["path_exists"] is Path.exists
    assert calls["status_probe"]["request"] is cli.ai_tts_server_request
    assert calls["stop_probe"]["request"] is cli.ai_tts_server_request
    assert status["ok"] is True
    assert status["socket_exists"] is True
    assert stop["ok"] is True
    assert stop["socket_exists_after"] is False


def test_cli_tts_server_run_binds_loop_adapter_port(monkeypatch, tmp_path: Path) -> None:
    from abyss_machine import cli

    profile = {
        "engine": "qwen3_tts_openvino",
        "adapter_src": str(tmp_path / "adapter-src"),
        "ov_dir": str(tmp_path / "ov"),
        "model_type": "custom_voice",
        "device": "GPU",
        "cp_device": "",
        "precision": "fp16",
    }
    status = {
        "status": "executable",
        "model": {"complete": True},
        "openvino": {"complete": True},
        "device": "GPU",
        "precision": "fp16",
    }
    socket_path = tmp_path / "server.sock"
    calls: dict[str, Any] = {}
    writes: list[dict[str, Any]] = []

    class FakeValue:
        def __init__(self, value: Any = None, **kwargs: Any) -> None:
            self.value = value
            self.kwargs = kwargs

    class FakeEngine:
        instances: list["FakeEngine"] = []

        def __init__(self) -> None:
            self.loaded: list[Any] = []
            FakeEngine.instances.append(self)

        def load_model(self, config: Any) -> None:
            self.loaded.append(config)

        def unload_model(self) -> None:
            calls["engine_unloaded"] = True

        def generate(self, _request: Any) -> tuple[list[int], int]:
            return [0, 0, 0], 16000

    soundfile_module = types.ModuleType("soundfile")
    soundfile_module.write = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
    openvino_module = types.ModuleType("openvino")
    ov_infer_module = types.ModuleType("openvino.ov_infer")
    ov_infer_module.CustomVoiceRequest = FakeValue  # type: ignore[attr-defined]
    ov_infer_module.Language = FakeValue  # type: ignore[attr-defined]
    ov_infer_module.ModelLoadConfig = FakeValue  # type: ignore[attr-defined]
    ov_infer_module.ModelType = FakeValue  # type: ignore[attr-defined]
    ov_infer_module.OVQwen3TTS = FakeEngine  # type: ignore[attr-defined]
    ov_infer_module.SamplingParams = FakeValue  # type: ignore[attr-defined]
    ov_infer_module.Speaker = FakeValue  # type: ignore[attr-defined]

    def fake_run_server_loop(**kwargs: Any) -> dict[str, Any]:
        calls["run_server_loop"] = kwargs
        return {"ok": True, "profile": kwargs["profile"], "socket": str(kwargs["socket_path"]), "stopped_at": STAMP}

    perf_ticks = iter([10.0, 10.75])
    monkeypatch.setitem(sys.modules, "soundfile", soundfile_module)
    monkeypatch.setitem(sys.modules, "openvino", openvino_module)
    monkeypatch.setitem(sys.modules, "openvino.ov_infer", ov_infer_module)
    monkeypatch.setattr(cli.time, "perf_counter", lambda: next(perf_ticks))
    monkeypatch.setattr(cli, "now_iso", lambda: STAMP)
    monkeypatch.setattr(cli.os, "getpid", lambda: 4242)
    monkeypatch.setattr(cli, "ai_tts_profile_for_request", lambda name: ("quality", profile, {"language": "Russian"}))
    monkeypatch.setattr(cli, "ai_tts_profile_status", lambda name, profile: status)
    monkeypatch.setattr(cli, "safe_atomic_write_json", lambda path, data, mode: writes.append({"path": path, "data": data, "mode": mode}) or None)
    monkeypatch.setattr(cli.ai_tts_adapters, "run_server_loop", fake_run_server_loop)

    result = cli.ai_tts_server_run("quality", socket_path=str(socket_path))

    assert result == {"ok": True, "profile": "quality", "socket": str(socket_path), "stopped_at": STAMP}
    assert len(FakeEngine.instances) == 1
    assert FakeEngine.instances[0].loaded
    assert writes == [
        {
            "path": cli.AI_TTS_SERVER_LATEST_PATH,
            "data": calls["run_server_loop"]["server_state"],
            "mode": 0o664,
        }
    ]
    assert calls["run_server_loop"]["socket_path"] == socket_path
    assert calls["run_server_loop"]["server_state"]["profile"] == "quality"
    assert calls["run_server_loop"]["server_state"]["socket"] == str(socket_path)
    assert calls["run_server_loop"]["server_state"]["pid"] == 4242
    assert calls["run_server_loop"]["server_state"]["load_sec"] == 0.75
    assert calls["run_server_loop"]["profile"] == "quality"
    assert callable(calls["run_server_loop"]["synth_once"])
    assert calls["run_server_loop"]["stopped_at"] is cli.now_iso
    assert calls["run_server_loop"]["unload_model"].__self__ is FakeEngine.instances[0]


def test_cli_tts_synth_binds_subprocess_adapter_ports(monkeypatch, tmp_path: Path) -> None:
    from abyss_machine import cli

    output = tmp_path / "out.wav"
    profile = {"engine": "babelvox", "python": "/venv/bin/python", "device": "CPU", "precision": "int8"}
    config = {"language": "Russian", "timeout_sec": 19.0}
    calls: dict[str, Any] = {}

    def fake_synth_env(**kwargs: Any) -> dict[str, str]:
        calls["env"] = kwargs
        return {"ENV": "1"}

    def fake_synth_subprocess(**kwargs: Any) -> dict[str, Any]:
        calls["subprocess"] = kwargs
        return {"ok": True, "subprocess": {"ok": True, "engine": "babelvox", "synth_sec": 0.2}}

    def fake_runtime_report(**kwargs: Any) -> dict[str, Any]:
        calls["runtime_report"] = kwargs
        return {
            **dict(kwargs["result"]),
            "wall_sec": 1.0,
            "audio": {"exists": True, "duration_sec": 0.5, "sample_rate": 16000, "size_bytes": 123},
            "rtf": 2.0,
            "resource_profile": {"scope": kwargs["scope"], "basis": kwargs["basis"]},
        }

    monkeypatch.setattr(cli, "now_iso", lambda: STAMP)
    monkeypatch.setattr(cli, "ai_resource_snapshot", lambda: {"snapshot": "ok"})
    monkeypatch.setattr(cli, "ai_resource_profile", lambda before, after, scope, basis: {"scope": scope, "basis": basis})
    monkeypatch.setattr(cli, "ai_tts_profile_for_request", lambda name: ("quality", profile, config))
    monkeypatch.setattr(cli, "ai_tts_profile_declared_class", lambda profile: "probe")
    monkeypatch.setattr(cli, "ai_policy_gate_for_class", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(cli, "ai_tts_profiles", lambda write_latest=True: {"profiles": {"quality": {"status": "executable", "model": {"exists": True}}}})
    monkeypatch.setattr(cli, "ai_tts_profile_python", lambda profile, config=None: "/venv/bin/python")
    monkeypatch.setattr(cli, "ai_tts_cache_dir", lambda label="general": tmp_path / "cache" / str(label))
    monkeypatch.setattr(cli, "ai_subprocess_env", lambda extra=None: {"BASE": "1", **dict(extra or {})})
    monkeypatch.setattr(cli.ai_tts_adapters, "synth_subprocess_env", fake_synth_env)
    monkeypatch.setattr(cli.ai_tts_adapters, "synth_subprocess", fake_synth_subprocess)
    monkeypatch.setattr(cli.ai_tts_adapters, "synth_runtime_report", fake_runtime_report)

    result = cli.ai_tts_synth(
        "quality",
        "hello",
        str(output),
        force=False,
        allow_download=True,
        use_server=False,
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["resource_profile"]["scope"] == "child_process"
    assert calls["env"]["cache_root"] == cli.AI_TTS_CACHE_ROOT
    assert calls["env"]["allow_download"] is True
    assert calls["env"]["build_env"] is cli.ai_subprocess_env
    assert calls["subprocess"]["engine"] == "babelvox"
    assert calls["subprocess"]["python"] == "/venv/bin/python"
    assert calls["subprocess"]["profile"] == profile
    assert calls["subprocess"]["config"] == config
    assert calls["subprocess"]["output"] == output
    assert calls["subprocess"]["timeout_sec"] == 19.0
    assert calls["subprocess"]["subprocess_env"] == {"ENV": "1"}
    assert calls["subprocess"]["run_command"] is cli.run
    assert calls["subprocess"]["path_exists"] is Path.exists
    assert calls["runtime_report"]["result"]["ok"] is True
    assert calls["runtime_report"]["output"] == output
    assert calls["runtime_report"]["time_now"] is cli.time.monotonic
    assert calls["runtime_report"]["resource_snapshot"] is cli.ai_resource_snapshot
    assert calls["runtime_report"]["resource_profile"] is cli.ai_resource_profile
    assert calls["runtime_report"]["scope"] == "child_process"
    assert calls["runtime_report"]["basis"] == "TTS synth subprocess"
    assert calls["runtime_report"]["path_exists"] is Path.exists
