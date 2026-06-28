from __future__ import annotations

import json
import os
import signal
import stat
import struct
from pathlib import Path
import sys
import wave

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


def _recording_paths(tmp_path: Path) -> dictation_execution_adapters.DictationRecordingPaths:
    runtime_dir = tmp_path / "runtime"
    return dictation_execution_adapters.DictationRecordingPaths(
        runtime_dir=runtime_dir,
        state_file=runtime_dir / "recording.json",
    )


def _audio_paths(tmp_path: Path) -> dictation_execution_adapters.DictationAudioPaths:
    return dictation_execution_adapters.DictationAudioPaths(runtime_dir=tmp_path / "runtime")


def _journal_paths(tmp_path: Path) -> dictation_execution_adapters.DictationJournalPaths:
    return dictation_execution_adapters.DictationJournalPaths(
        jsonl_root=tmp_path / "transcripts" / "jsonl",
        jsonl_path=tmp_path / "transcripts" / "jsonl" / "2026" / "06" / "2026-06-28.jsonl",
        markdown_path=tmp_path / "transcripts" / "readable" / "2026" / "06" / "2026-06-28.md",
        latest_path=tmp_path / "transcripts" / "latest.json",
        index_path=tmp_path / "index.json",
    )


def _write_wav(path: Path, samples: list[int], *, sample_rate: int = 16000, channels: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_values: list[int] = []
    for sample in samples:
        frame_values.extend([sample] * channels)
    frames = struct.pack("<" + "h" * len(frame_values), *frame_values)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)


def test_audio_adapter_reads_wav_stats_from_synthetic_runtime_file(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    _write_wav(audio, [0, 1200, -1200, 2400, -2400] * 320)

    stats = dictation_execution_adapters.wav_stats(audio)

    assert stats["ok"] is True
    assert stats["path"] == str(audio)
    assert stats["sample_rate"] == 16000
    assert stats["channels"] == 1
    assert stats["duration_sec"] == 0.1
    assert stats["peak"] > 0
    assert stats["dbfs"] < 0
    assert stats["frame_dbfs_p50"] is not None


def test_audio_adapter_lists_recent_runtime_wavs(tmp_path: Path) -> None:
    paths = _audio_paths(tmp_path)
    old_audio = paths.runtime_dir / "old.wav"
    new_audio = paths.runtime_dir / "new.wav"
    ignored = paths.runtime_dir / "ignored.txt"
    _write_wav(old_audio, [100] * 16)
    _write_wav(new_audio, [200] * 16)
    ignored.write_text("not audio", encoding="utf-8")
    os.utime(old_audio, (100.0, 100.0))
    os.utime(new_audio, (200.0, 200.0))

    assert dictation_execution_adapters.recent_wavs(paths, limit=1) == [new_audio]
    assert dictation_execution_adapters.recent_wavs(paths, limit=5) == [new_audio, old_audio]


def test_audio_doctor_uses_fakeable_audio_probe_ports(tmp_path: Path) -> None:
    paths = _audio_paths(tmp_path)
    good_audio = paths.runtime_dir / "good.wav"
    bad_audio = paths.runtime_dir / "bad.wav"
    _write_wav(good_audio, [600] * 160)
    bad_audio.write_text("not a wav", encoding="utf-8")
    calls: list[tuple[list[str], float, object]] = []

    def fake_run(command: list[str], timeout: float, run_env: object) -> dict[str, object]:
        calls.append((command, timeout, run_env))
        if command == ["pactl", "get-default-source"]:
            return {"ok": True, "stdout": "alsa_input.test", "stderr": "", "returncode": 0}
        if command == ["wpctl", "status"]:
            return {"ok": True, "stdout": "PipeWire status", "stderr": "", "returncode": 0}
        if command == ["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"]:
            return {"ok": True, "stdout": "node.name = alsa_input.test", "stderr": "", "returncode": 0}
        raise AssertionError(command)

    data = dictation_execution_adapters.audio_doctor(
        paths=paths,
        config={"calibration": {"enabled": True}},
        limit=2,
        run_command=fake_run,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        recent_wavs_fn=lambda limit: [good_audio, bad_audio][:limit],
    )

    assert data["schema"] == "abyss_machine_dictation_audio_doctor_v1"
    assert data["default_source"] == "alsa_input.test"
    assert data["wpctl_status_ok"] is True
    assert data["wpctl_default_source"] == "node.name = alsa_input.test"
    assert data["calibration"] == {"enabled": True}
    assert data["summary"]["files_analyzed"] == 1
    assert data["recent_files"][0]["ok"] is True
    assert data["recent_files"][1]["ok"] is False
    assert calls == [
        (["pactl", "get-default-source"], 2.0, None),
        (["wpctl", "status"], 2.0, None),
        (["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"], 2.0, None),
    ]


def test_cli_dictation_audio_doctor_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _audio_paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_audio_doctor(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "schema": "abyss_machine_dictation_audio_doctor_v1"}

    monkeypatch.setattr(cli, "dictation_audio_paths", lambda: paths)
    monkeypatch.setattr(cli, "dictation_config", lambda: {"calibration": {"source": "test"}})
    monkeypatch.setattr(dictation_execution_adapters, "audio_doctor", fake_audio_doctor)

    data = cli.dictation_audio_doctor(7)

    assert data["ok"] is True
    assert captured["paths"] == paths
    assert captured["config"] == {"calibration": {"source": "test"}}
    assert captured["limit"] == 7
    assert captured["run_command"] is cli.run
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert callable(captured["now"])


def _journal_result(audio: Path) -> dict[str, object]:
    return {
        "generated_at": "2026-06-28T11:59:58+00:00",
        "action": "insert",
        "recording": {
            "profile": "auto",
            "audio": str(audio),
            "started_at": "2026-06-28T11:59:56+00:00",
            "generated_at": "2026-06-28T11:59:58+00:00",
            "max_seconds": 180,
            "log": "/tmp/dictation.log",
        },
        "transcript": {
            "ok": True,
            "text": "Abyss online. ",
            "raw_text": "abyss online",
            "profile": {"name": "quality", "device": "CPU", "model_id": "test", "model_dir": "/tmp/model"},
            "num_beams": 3,
            "via": "server",
            "elapsed_sec": 1.2,
            "client_elapsed_sec": 1.4,
            "postprocess": {"capitalization": True},
            "intent": {"type": "dictation", "triggered": False},
        },
        "insert": {"ok": True, "method": "wtype", "stderr": "", "attempts": []},
    }


def test_journal_adapter_writes_transcript_files_without_live_clipboard(tmp_path: Path) -> None:
    paths = _journal_paths(tmp_path)
    audio = tmp_path / "runtime" / "dictation.wav"
    _write_wav(audio, [500] * 160)
    ensure_calls = 0

    def ensure_docs() -> list[dict[str, object]]:
        nonlocal ensure_calls
        ensure_calls += 1
        return []

    data = dictation_execution_adapters.journal_write(
        _journal_result(audio),
        paths=paths,
        enabled=True,
        include_failed=True,
        ensure_docs=ensure_docs,
        index_document=lambda: {"schema": "abyss_machine_dictation_index_v1", "ok": True},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )

    assert data["ok"] is True
    assert data["written"] is True
    assert ensure_calls == 1
    latest = json.loads(paths.latest_path.read_text(encoding="utf-8"))
    assert latest["schema"] == "abyss_machine_dictation_transcript_event_v1"
    assert latest["text"] == "Abyss online. "
    assert latest["audio"]["exists"] is True
    assert latest["audio"]["duration_sec"] == 0.01
    assert json.loads(paths.index_path.read_text(encoding="utf-8"))["schema"] == "abyss_machine_dictation_index_v1"
    jsonl_entries = [json.loads(line) for line in paths.jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert jsonl_entries == [latest]
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert "Abyss online." in markdown
    assert "Raw:" in markdown


def test_journal_adapter_reads_latest_and_tail_from_transcript_store(tmp_path: Path) -> None:
    paths = _journal_paths(tmp_path)
    audio = tmp_path / "runtime" / "dictation.wav"
    _write_wav(audio, [500] * 160)
    times = iter(
        [
            "2026-06-28T12:00:00+00:00",
            "2026-06-28T12:00:01+00:00",
            "2026-06-28T12:00:02+00:00",
            "2026-06-28T12:00:03+00:00",
        ]
    )

    def now() -> str:
        return next(times)

    first = _journal_result(audio)
    second = _journal_result(audio)
    second["transcript"] = {**second["transcript"], "text": "Second entry. "}
    for result in (first, second):
        data = dictation_execution_adapters.journal_write(
            result,
            paths=paths,
            enabled=True,
            include_failed=True,
            ensure_docs=lambda: [],
            index_document=lambda: {"schema": "abyss_machine_dictation_index_v1"},
            schema_prefix="abyss_machine",
            version="test",
            now=now,
        )
        assert data["ok"] is True

    latest = dictation_execution_adapters.journal_latest(
        paths=paths,
        ensure_docs=lambda: [],
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:03+00:00",
    )
    assert latest["ok"] is True
    assert latest["entry"]["text"] == "Second entry. "

    tail = dictation_execution_adapters.journal_tail(
        paths=paths,
        lines=1,
        ensure_docs=lambda: [],
        paths_document=lambda: {"schema": "abyss_machine_dictation_paths_v1"},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:04+00:00",
    )
    assert tail["ok"] is True
    assert tail["lines"] == 1
    assert tail["entries"][0]["text"] == "Second entry. "
    assert tail["entries"][0]["_source_path"] == str(paths.jsonl_path)


def test_journal_adapter_handles_disabled_or_missing_transcript_without_writing(tmp_path: Path) -> None:
    paths = _journal_paths(tmp_path)
    ensure_calls = 0

    def ensure_docs() -> list[dict[str, object]]:
        nonlocal ensure_calls
        ensure_calls += 1
        return []

    disabled = dictation_execution_adapters.journal_write(
        {},
        paths=paths,
        enabled=False,
        include_failed=True,
        ensure_docs=ensure_docs,
        index_document=lambda: {},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )
    assert disabled["ok"] is True
    assert disabled["enabled"] is False
    assert ensure_calls == 0

    missing = dictation_execution_adapters.journal_write(
        {},
        paths=paths,
        enabled=True,
        include_failed=True,
        ensure_docs=ensure_docs,
        index_document=lambda: {},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )
    assert missing["ok"] is True
    assert missing["written"] is False
    assert ensure_calls == 1
    assert not paths.latest_path.exists()


def test_cli_dictation_journal_write_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _journal_paths(tmp_path)
    result = {"transcript": {"ok": True, "text": "hello"}}
    captured: dict[str, object] = {}

    def fake_journal_write(result_arg: object, **kwargs: object) -> dict[str, object]:
        captured["result"] = result_arg
        captured.update(kwargs)
        return {"ok": True, "schema": "abyss_machine_dictation_journal_write_v1"}

    monkeypatch.setattr(cli, "dictation_journal_paths", lambda: paths)
    monkeypatch.setattr(cli, "dictation_journal_enabled", lambda: True)
    monkeypatch.setattr(cli, "dictation_journal_include_failed", lambda: False)
    monkeypatch.setattr(dictation_execution_adapters, "journal_write", fake_journal_write)

    data = cli.dictation_journal_write(result)

    assert data["ok"] is True
    assert captured["result"] == result
    assert captured["paths"] == paths
    assert captured["enabled"] is True
    assert captured["include_failed"] is False
    assert captured["ensure_docs"] is cli.ensure_dictation_docs
    assert captured["index_document"] is cli.dictation_index_document
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert callable(captured["now"])
    assert captured["wav_duration_fn"] is cli.wav_duration


def test_insert_adapter_prefers_wtype_success_without_clipboard() -> None:
    calls: list[tuple[str, object]] = []

    def fake_wtype(text: str, timeout: float) -> dict[str, object]:
        calls.append(("wtype", {"text": text, "timeout": timeout}))
        return {"returncode": 0, "stderr": ""}

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError((args, kwargs))

    data = dictation_execution_adapters.insert_text(
        "hello",
        env={},
        command_exists=lambda command: command == "wtype",
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        run_wtype_fn=fake_wtype,
        start_foreground_clipboard_fn=forbidden,
        copy_clipboard_fn=forbidden,
        send_key_sequence_fn=forbidden,
    )

    assert data["ok"] is True
    assert data["method"] == "wtype"
    assert calls == [("wtype", {"text": "hello", "timeout": 5.0})]


def test_insert_adapter_falls_back_to_clipboard_and_ydotool_without_live_tools() -> None:
    sleeps: list[float] = []
    captured: dict[str, object] = {}

    def fake_copy(text: str) -> dict[str, object]:
        captured["copy_text"] = text
        return {"returncode": 0, "stderr": ""}

    def fake_send(sequence: list[str], env: dict[str, str], timeout: float) -> dict[str, object]:
        captured["sequence"] = sequence
        captured["ydotool_env"] = dict(env)
        captured["timeout"] = timeout
        return {"returncode": 0, "stderr": ""}

    data = dictation_execution_adapters.insert_text(
        "hello",
        env={
            "ABYSS_DICTATION_INSERT_METHOD": "clipboard",
            "ABYSS_DICTATION_CLIPBOARD_PROVIDER": "daemon",
            "ABYSS_DICTATION_PASTE_COMBO": "ctrl-shift-v",
            "ABYSS_DICTATION_CLIPBOARD_SETTLE_SECONDS": "0.08",
            "ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS": "77",
            "YDOTOOL_SOCKET": "/tmp/ydotool.sock",
        },
        command_exists=lambda command: False,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        copy_clipboard_fn=fake_copy,
        send_key_sequence_fn=fake_send,
        sleep_fn=sleeps.append,
    )

    assert data["ok"] is True
    assert data["method"] == "wl-copy+ydotool-ctrl-shift-v"
    assert data["clipboard_provider"] == "daemon"
    assert data["clipboard_provider_returncode"] == 0
    assert data["attempts"][0]["combo"] == "ctrl-shift-v"
    assert data["attempts"][0]["paste_sent"] is True
    assert captured["copy_text"] == "hello"
    assert captured["timeout"] == 3.0
    assert captured["ydotool_env"]["ABYSS_DICTATION_YDOTOOL_KEY_DELAY_MS"] == "77"
    assert captured["ydotool_env"]["YDOTOOL_SOCKET"] == "/tmp/ydotool.sock"
    assert sleeps == [0.08]


def test_insert_adapter_stops_foreground_clipboard_session_after_paste() -> None:
    sleeps: list[float] = []
    stopped: list[float] = []
    state = {"returncode": None}

    def fake_start(text: str) -> dictation_execution_adapters.ForegroundClipboardSession:
        assert text == "hello"

        def stop(timeout: float) -> None:
            stopped.append(timeout)
            state["returncode"] = -15

        return dictation_execution_adapters.ForegroundClipboardSession(
            poll=lambda: state["returncode"],
            read_stderr=lambda: "terminated",
            stop=stop,
        )

    data = dictation_execution_adapters.insert_text(
        "hello",
        env={
            "ABYSS_DICTATION_INSERT_METHOD": "clipboard",
            "ABYSS_DICTATION_CLIPBOARD_PROVIDER": "foreground",
            "ABYSS_DICTATION_CLIPBOARD_SETTLE_SECONDS": "0",
            "ABYSS_DICTATION_CLIPBOARD_HOLD_SECONDS": "0.2",
        },
        command_exists=lambda command: False,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        start_foreground_clipboard_fn=fake_start,
        send_key_sequence_fn=lambda sequence, env, timeout: {"returncode": 0, "stderr": ""},
        sleep_fn=sleeps.append,
    )

    assert data["ok"] is True
    assert data["clipboard_provider"] == "foreground"
    assert data["clipboard_provider_returncode"] == -15
    assert data["stderr"] == "terminated"
    assert sleeps == [0.0, 0.2]
    assert stopped == [0.5]


def test_insert_adapter_reports_missing_ydotool_as_failed_attempt() -> None:
    def missing_ydotool(sequence: list[str], env: dict[str, str], timeout: float) -> dict[str, object]:
        raise FileNotFoundError("ydotool")

    data = dictation_execution_adapters.insert_text(
        "hello",
        env={
            "ABYSS_DICTATION_INSERT_METHOD": "clipboard",
            "ABYSS_DICTATION_CLIPBOARD_PROVIDER": "daemon",
        },
        command_exists=lambda command: False,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        copy_clipboard_fn=lambda text: {"returncode": 0, "stderr": ""},
        send_key_sequence_fn=missing_ydotool,
        sleep_fn=lambda seconds: None,
    )

    assert data["ok"] is False
    assert data["attempts"][0]["returncode"] == 127
    assert data["attempts"][0]["paste_sent"] is False
    assert "ydotool" in data["stderr"]


def test_cli_dictation_insert_binds_live_adapter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_insert_text(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "schema": "abyss_machine_dictation_insert_v1"}

    monkeypatch.setattr(dictation_execution_adapters, "insert_text", fake_insert_text)

    data = cli.dictation_insert("hello")

    assert data["ok"] is True
    assert captured["text"] == "hello"
    assert captured["env"] is os.environ
    assert captured["command_exists"] is cli.command_exists
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert callable(captured["now"])


def test_recording_adapter_starts_process_and_writes_state_without_live_audio(tmp_path: Path) -> None:
    paths = _recording_paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_start_process(command: list[str], log_path: Path) -> int:
        captured["command"] = command
        captured["log_path"] = log_path
        return 4321

    state = dictation_execution_adapters.start_recording(
        paths=paths,
        profile="quality",
        max_seconds_value=180,
        timeout_available=True,
        schema_prefix="abyss_machine",
        now=lambda: "2026-06-28T12:00:00+00:00",
        timestamp=lambda: "20260628-120000",
        start_process=fake_start_process,
    )

    audio_path = paths.runtime_dir / "dictation-20260628-120000.wav"
    log_path = paths.runtime_dir / "dictation-20260628-120000.log"
    assert state["schema"] == "abyss_machine_dictation_recording_v1"
    assert state["pid"] == 4321
    assert state["audio"] == str(audio_path)
    assert state["log"] == str(log_path)
    assert state["profile"] == "quality"
    assert state["max_seconds"] == 180
    assert captured["log_path"] == log_path
    assert captured["command"] == [
        "timeout",
        "--signal=INT",
        "--kill-after=5s",
        "180s",
        "pw-record",
        "--rate",
        "16000",
        "--channels",
        "1",
        "--format",
        "s16",
        str(audio_path),
    ]
    assert json.loads(paths.state_file.read_text(encoding="utf-8")) == state
    assert stat.S_IMODE(paths.state_file.stat().st_mode) == 0o600


def test_recording_adapter_reads_active_and_stale_state(tmp_path: Path) -> None:
    paths = _recording_paths(tmp_path)
    audio_path = paths.runtime_dir / "dictation.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_text("synthetic wav placeholder", encoding="utf-8")
    state = {
        "schema": "abyss_machine_dictation_recording_v1",
        "pid": 777,
        "audio": str(audio_path),
        "log": str(paths.runtime_dir / "dictation.log"),
        "profile": "quality",
        "started_at": "2026-06-28T12:00:00+00:00",
        "max_seconds": 180,
    }
    dictation_execution_adapters.write_recording_state(paths.state_file, state)

    active = dictation_execution_adapters.load_active_recording(paths, alive=lambda pid: pid == 777)
    assert active == state
    assert dictation_execution_adapters.recording_is_active(active, alive=lambda _pid: True) is True
    assert dictation_execution_adapters.recording_age_seconds(
        state,
        now_datetime=lambda: cli.dt.datetime.fromisoformat("2026-06-28T12:00:03+00:00"),
    ) == 3.0

    stale = dictation_execution_adapters.load_stale_recording(paths, alive=lambda _pid: False)
    assert stale is not None
    assert stale["stale"] is True
    assert paths.state_file.exists()

    audio_path.unlink()
    assert dictation_execution_adapters.load_stale_recording(paths, alive=lambda _pid: False) is None
    assert not paths.state_file.exists()


def test_recording_adapter_stops_process_and_unlinks_state(tmp_path: Path) -> None:
    paths = _recording_paths(tmp_path)
    state = {
        "schema": "abyss_machine_dictation_recording_v1",
        "pid": 777,
        "audio": str(paths.runtime_dir / "dictation.wav"),
        "log": str(paths.runtime_dir / "dictation.log"),
        "profile": "quality",
        "started_at": "2026-06-28T12:00:00+00:00",
        "max_seconds": 180,
    }
    dictation_execution_adapters.write_recording_state(paths.state_file, state)
    signals: list[tuple[int, int]] = []
    ticks = iter([0.0, 10.0])

    result = dictation_execution_adapters.stop_recording(
        state,
        paths=paths,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:05+00:00",
        alive=lambda _pid: True,
        signal_process=lambda pid, sig: signals.append((pid, sig)),
        monotonic=lambda: next(ticks),
        sleep=lambda _seconds: None,
    )

    assert signals == [(777, int(signal.SIGINT)), (777, int(signal.SIGTERM))]
    assert result["schema"] == "abyss_machine_dictation_stop_v1"
    assert result["stopped"] is True
    assert result["audio"] == state["audio"]
    assert not paths.state_file.exists()


def test_cli_dictation_recording_lifecycle_binds_live_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _recording_paths(tmp_path)
    started: dict[str, object] = {}
    stopped: dict[str, object] = {}

    monkeypatch.setattr(cli, "load_dictation_recording", lambda: None)
    monkeypatch.setattr(cli, "dictation_recording_paths", lambda: paths)
    monkeypatch.setattr(cli, "requested_dictation_profile_name", lambda _profile_name: "quality")
    monkeypatch.setattr(cli, "dictation_max_seconds", lambda: 180)
    monkeypatch.setattr(cli, "command_exists", lambda name: name == "timeout")
    monkeypatch.setattr(cli, "dictation_status", lambda: {"recording": {"pid": 4321}})

    def fake_start_recording(**kwargs: object) -> dict[str, object]:
        started.update(kwargs)
        return {"pid": 4321}

    def fake_stop_recording(state: dict[str, object] | None = None, **kwargs: object) -> dict[str, object]:
        stopped["state"] = state
        stopped.update(kwargs)
        return {"stopped": True}

    monkeypatch.setattr(dictation_execution_adapters, "start_recording", fake_start_recording)
    monkeypatch.setattr(dictation_execution_adapters, "stop_recording", fake_stop_recording)

    data = cli._dictation_start_unlocked("fast")
    assert data["message"] == "recording started"
    assert started["paths"] == paths
    assert started["profile"] == "quality"
    assert started["max_seconds_value"] == 180
    assert started["timeout_available"] is True
    assert started["schema_prefix"] == cli.SCHEMA_PREFIX
    assert callable(started["now"])

    stop_data = cli._dictation_stop_unlocked({"pid": 777})
    assert stop_data["stopped"] is True
    assert stopped["state"] == {"pid": 777}
    assert stopped["paths"] == paths
    assert stopped["schema_prefix"] == cli.SCHEMA_PREFIX
    assert stopped["version"] == cli.VERSION
    assert callable(stopped["now"])


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
