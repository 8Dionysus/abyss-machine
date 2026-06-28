from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_execution_adapters


def _profile(model_dir: Path) -> dict[str, object]:
    return {
        "name": "quality",
        "model_dir": str(model_dir),
        "device": "CPU",
        "language": "ru",
        "max_new_tokens": 192,
        "num_beams": 3,
        "runtime": {"vad_segments": True, "audio_preprocess": True},
        "postprocess": {},
    }


def _ready_paths(tmp_path: Path) -> dictation_execution_adapters.DictationTranscriptionPaths:
    helper = tmp_path / "abyss-dictation-transcribe"
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    return dictation_execution_adapters.DictationTranscriptionPaths(
        helper=helper,
        server_socket=tmp_path / "server.sock",
        server_audio_dir=tmp_path / "server-audio",
    )


def test_dictation_adapter_reports_missing_model_before_runtime_calls(tmp_path: Path) -> None:
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("called")
        return {}

    data = dictation_execution_adapters.transcribe_audio(
        "/tmp/audio.wav",
        _profile(tmp_path / "missing-model"),
        {"selected_profile": "quality"},
        paths=_ready_paths(tmp_path),
        run_command=forbidden,
        command_exists=forbidden,
        wav_sample_rate=forbidden,
        wav_duration=forbidden,
        env={},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        socket_request=forbidden,
    )

    assert data["ok"] is False
    assert "model directory missing" in data["error"]
    assert called == []


def test_dictation_adapter_uses_warm_server_without_helper_subprocess(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    paths = _ready_paths(tmp_path)
    paths.server_socket.write_text("", encoding="utf-8")
    audio = tmp_path / "audio-16k.wav"
    audio.write_text("synthetic wav placeholder", encoding="utf-8")
    captured: dict[str, object] = {}
    ticks = iter([10.0, 11.2344])

    def forbidden_run(*_args: object, **_kwargs: object):
        raise AssertionError("helper subprocess should not run when warm server responds")

    def fake_socket(
        socket_path: Path,
        request: dict[str, object],
        connect_timeout: float,
        response_timeout: float,
    ) -> str:
        captured["socket_path"] = socket_path
        captured["request"] = request
        captured["connect_timeout"] = connect_timeout
        captured["response_timeout"] = response_timeout
        return json.dumps({"ok": True, "text": "abyss online", "audio": str(audio), "via": "server"})

    data = dictation_execution_adapters.transcribe_audio(
        str(audio),
        _profile(model_dir),
        {"selected_profile": "quality"},
        paths=paths,
        run_command=forbidden_run,
        command_exists=lambda _name: False,
        wav_sample_rate=lambda _path: 16000,
        wav_duration=lambda _path: 1.2,
        env={
            "ABYSS_DICTATION_MAX_NEW_TOKENS": "224",
            "ABYSS_DICTATION_NUM_BEAMS": "2",
            "ABYSS_DICTATION_SERVER_CONNECT_TIMEOUT": "0.5",
            "ABYSS_DICTATION_SERVER_TIMEOUT": "42",
        },
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        monotonic=lambda: next(ticks),
        socket_request=fake_socket,
    )

    assert data["ok"] is True
    assert data["via"] == "server"
    assert data["server_socket"] == str(paths.server_socket)
    assert data["client_elapsed_sec"] == 1.234
    assert data["profile_selection"] == {"selected_profile": "quality"}
    assert captured["connect_timeout"] == 0.5
    assert captured["response_timeout"] == 42.0
    request = captured["request"]
    assert isinstance(request, dict)
    assert request["audio"] == str(audio)
    assert request["max_new_tokens"] == 224
    assert request["num_beams"] == 2


def test_dictation_adapter_resamples_non_16k_audio_for_warm_server(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    paths = _ready_paths(tmp_path)
    paths.server_socket.write_text("", encoding="utf-8")
    audio = tmp_path / "audio-48k.wav"
    audio.write_text("synthetic wav placeholder", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_run(command: list[str], timeout: float, run_env: dict[str, str] | None) -> dict[str, object]:
        output = Path(command[-1])
        output.write_text("resampled", encoding="utf-8")
        calls.append({"command": command, "timeout": timeout, "env": run_env})
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": "ffmpeg note"}

    def sample_rate(path: Path) -> int:
        return 16000 if path.name.endswith("-16k.wav") else 48000

    def fake_socket(_socket_path: Path, request: dict[str, object], _connect_timeout: float, _response_timeout: float) -> str:
        return json.dumps({"ok": True, "text": "resampled", "audio": request["audio"]})

    data = dictation_execution_adapters.transcribe_audio(
        str(audio),
        _profile(model_dir),
        {"selected_profile": "quality"},
        paths=paths,
        run_command=fake_run,
        command_exists=lambda name: name == "ffmpeg",
        wav_sample_rate=sample_rate,
        wav_duration=lambda _path: 2.5,
        env={},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        monotonic=iter([1.0, 2.0]).__next__,
        socket_request=fake_socket,
    )

    assert data["ok"] is True
    assert data["audio"] == str(audio)
    assert data["server_audio"].endswith("-16k.wav")
    assert data["client_audio_preprocess"]["ok"] is True
    assert data["client_audio_preprocess"]["output_duration_sec"] == 2.5
    assert calls[0]["timeout"] == 30.0
    assert calls[0]["env"] is None
    assert calls[0]["command"][:4] == ["ffmpeg", "-y", "-hide_banner", "-loglevel"]


def test_dictation_adapter_falls_back_to_helper_with_runtime_env(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    paths = _ready_paths(tmp_path)
    audio = tmp_path / "audio.wav"
    audio.write_text("synthetic wav placeholder", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], timeout: float, run_env: dict[str, str] | None) -> dict[str, object]:
        captured["command"] = command
        captured["timeout"] = timeout
        captured["env"] = run_env
        return {"ok": True, "returncode": 0, "stdout": 'noise\n{"ok": true, "text": "helper ok"}', "stderr": ""}

    data = dictation_execution_adapters.transcribe_audio(
        str(audio),
        _profile(model_dir),
        {"selected_profile": "quality"},
        paths=paths,
        run_command=fake_run,
        command_exists=lambda _name: False,
        wav_sample_rate=lambda _path: 16000,
        wav_duration=lambda _path: 1.0,
        env={"BASE": "1", "ABYSS_DICTATION_SERVER": "0"},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        monotonic=iter([3.0, 5.3456]).__next__,
    )

    assert data["ok"] is True
    assert data["via"] == "helper"
    assert data["text"] == "helper ok"
    assert data["client_elapsed_sec"] == 2.346
    assert captured["timeout"] == 600.0
    assert captured["command"][:4] == [str(paths.helper), str(audio), "--model-dir", str(model_dir)]
    assert captured["env"]["BASE"] == "1"
    assert captured["env"]["ABYSS_DICTATION_VAD_SEGMENTS"] == "1"


def test_cli_dictation_transcribe_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    paths = _ready_paths(tmp_path)
    profile = _profile(model_dir)
    selection = {"selected_profile": "quality"}
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "dictation_profile", lambda profile_name, audio: (profile, selection))
    monkeypatch.setattr(cli, "dictation_transcription_paths", lambda: paths)
    monkeypatch.setattr(cli, "postprocess_transcript", lambda data, bound_profile: {**data, "postprocessed_with": bound_profile["name"]})
    monkeypatch.setenv("ABYSS_DICTATION_SERVER", "0")

    def fake_adapter(audio: str, adapter_profile: dict[str, object], adapter_selection: dict[str, object], **kwargs: object) -> dict[str, object]:
        captured["audio"] = audio
        captured["profile"] = adapter_profile
        captured["selection"] = adapter_selection
        captured.update(kwargs)
        return {"schema": "abyss_machine_dictation_transcript_v1", "ok": True, "text": "bound"}

    monkeypatch.setattr(dictation_execution_adapters, "transcribe_audio", fake_adapter)

    data = cli.dictation_transcribe("/tmp/audio.wav", "quality")

    assert data["ok"] is True
    assert data["postprocessed_with"] == "quality"
    assert captured["audio"] == "/tmp/audio.wav"
    assert captured["profile"] == profile
    assert captured["selection"] == selection
    assert captured["paths"] == paths
    assert captured["run_command"] is cli.run
    assert captured["command_exists"] is cli.command_exists
    assert captured["wav_sample_rate"] is cli.wav_sample_rate
    assert captured["wav_duration"] is cli.wav_duration
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert callable(captured["now"])
