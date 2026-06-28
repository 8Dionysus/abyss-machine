from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_status_adapters


def _paths(tmp_path: Path) -> dictation_status_adapters.DictationStatusPaths:
    return dictation_status_adapters.DictationStatusPaths(
        runtime_dir=tmp_path / "run" / "dictation",
        config_path=tmp_path / "etc" / "abyss-machine" / "dictation" / "config.json",
        replacements_path=tmp_path / "etc" / "abyss-machine" / "dictation" / "replacements.json",
        model_root=tmp_path / "models",
        helper=tmp_path / "bin" / "transcribe",
        server=tmp_path / "bin" / "server",
        server_socket=tmp_path / "run" / "dictation" / "server.sock",
        ydotool_socket=tmp_path / "run" / "user" / "1000" / ".ydotool_socket",
        transcript_latest=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "latest.json",
        today_readable=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "readable" / "2026-06-28.md",
        today_jsonl=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "jsonl" / "2026-06-28.jsonl",
    )


def test_status_adapter_builds_public_safe_read_model(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    quality_model = tmp_path / "models" / "quality"
    fast_model = tmp_path / "models" / "fast"
    existing_paths = {
        paths.config_path,
        paths.replacements_path,
        paths.server_socket,
        paths.ydotool_socket,
        paths.transcript_latest,
        quality_model,
    }

    def path_exists(path: Path) -> bool:
        return path in existing_paths

    def command_exists(command: str) -> bool:
        return command in {"pw-record", "wl-copy", "wtype", "wpctl"}

    document = dictation_status_adapters.status_document(
        paths=paths,
        config={
            "_load_error": "fallback",
            "profile_policy": {"fallback_profile": "quality"},
            "command_intent": {"enabled": True},
            "runtime": {"vad_segments": True},
            "postprocess": {"normalize": True},
            "notifications": {"enabled": True},
            "journal": {"enabled": True},
            "calibration": {"target_rms_dbfs": -28.0},
        },
        profiles={
            "quality": {"name": "quality", "model_dir": str(quality_model)},
            "fast": {"name": "fast", "model_dir": str(fast_model)},
        },
        recording=None,
        stale_recording={"pid": 123, "state": "stale"},
        replacements={"_load_error": None, "items": [{"from": "foo", "to": "bar"}]},
        requested_default_profile="quality",
        journal_enabled=True,
        command_exists=command_exists,
        path_exists=path_exists,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )

    assert document["schema"] == "abyss_machine_dictation_status_v1"
    assert document["runtime_dir"] == str(paths.runtime_dir)
    assert document["config"]["exists"] is True
    assert document["config"]["load_error"] == "fallback"
    assert document["config"]["default_profile"] == "quality"
    assert document["replacements"]["count"] == 1
    assert document["server_socket_exists"] is True
    assert document["profiles"]["quality"]["model_dir_exists"] is True
    assert document["profiles"]["fast"]["model_dir_exists"] is False
    assert document["recording_active"] is False
    assert document["stale_recording"] == {"pid": 123, "state": "stale"}
    assert document["commands"]["pw_record"] is True
    assert document["commands"]["ydotool"] is False
    assert document["commands"]["ydotool_socket"] is True
    assert document["commands"]["wev"] is False
    assert document["audio"]["default_source_known"] is True
    assert document["journal"]["enabled"] is True
    assert document["journal"]["latest_exists"] is True


def test_status_adapter_handles_active_recording(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    document = dictation_status_adapters.status_document(
        paths=paths,
        config={},
        profiles={},
        recording={"pid": 456, "audio": "/tmp/live.wav"},
        stale_recording=None,
        replacements={"items": "invalid"},
        requested_default_profile="auto",
        journal_enabled=False,
        command_exists=lambda command: False,
        path_exists=lambda path: False,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )

    assert document["recording"] == {"pid": 456, "audio": "/tmp/live.wav"}
    assert document["recording_active"] is True
    assert document["stale_recording"] is None
    assert document["replacements"]["count"] == 0


def test_cli_dictation_status_binds_status_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = {"default_profile": "quality"}
    profiles = {"quality": {"name": "quality"}}
    replacements = {"items": []}
    recording = {"pid": 789}
    captured: dict[str, object] = {}

    def fake_status_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "status"}

    monkeypatch.setattr(cli, "dictation_status_paths", lambda: paths)
    monkeypatch.setattr(cli, "dictation_config", lambda: config)
    monkeypatch.setattr(cli, "dictation_profiles", lambda: profiles)
    monkeypatch.setattr(cli, "load_dictation_recording", lambda: recording)
    monkeypatch.setattr(cli, "load_stale_dictation_recording", lambda: {"pid": 999})
    monkeypatch.setattr(cli, "dictation_replacements_document", lambda: replacements)
    monkeypatch.setattr(cli, "requested_dictation_profile_name", lambda name: "quality")
    monkeypatch.setattr(cli, "dictation_journal_enabled", lambda: True)
    monkeypatch.setattr(dictation_status_adapters, "status_document", fake_status_document)

    assert cli.dictation_status() == {"schema": "status"}

    assert captured["paths"] == paths
    assert captured["config"] == config
    assert captured["profiles"] == profiles
    assert captured["recording"] == recording
    assert captured["stale_recording"] is None
    assert captured["replacements"] == replacements
    assert captured["requested_default_profile"] == "quality"
    assert captured["journal_enabled"] is True
    assert captured["command_exists"] is cli.command_exists
    assert captured["path_exists"] is Path.exists
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["now"] is cli.now_iso


def test_cli_dictation_status_reads_stale_only_when_not_recording(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_status_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "status"}

    monkeypatch.setattr(cli, "dictation_status_paths", lambda: paths)
    monkeypatch.setattr(cli, "dictation_config", lambda: {})
    monkeypatch.setattr(cli, "dictation_profiles", lambda: {})
    monkeypatch.setattr(cli, "load_dictation_recording", lambda: None)
    monkeypatch.setattr(cli, "load_stale_dictation_recording", lambda: {"pid": 999})
    monkeypatch.setattr(cli, "dictation_replacements_document", lambda: {"items": []})
    monkeypatch.setattr(cli, "requested_dictation_profile_name", lambda name: "auto")
    monkeypatch.setattr(cli, "dictation_journal_enabled", lambda: False)
    monkeypatch.setattr(dictation_status_adapters, "status_document", fake_status_document)

    assert cli.dictation_status() == {"schema": "status"}

    assert captured["recording"] is None
    assert captured["stale_recording"] == {"pid": 999}
