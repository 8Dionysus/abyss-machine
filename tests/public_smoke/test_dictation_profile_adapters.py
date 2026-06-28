from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import dictation_profile_adapters
from abyss_machine import cli


def _paths(tmp_path: Path) -> dictation_profile_adapters.DictationConfigPaths:
    return dictation_profile_adapters.DictationConfigPaths(
        config_dir=tmp_path / "etc" / "abyss-machine" / "dictation",
        config_path=tmp_path / "etc" / "abyss-machine" / "dictation" / "config.json",
    )


def test_config_adapter_loads_defaults_and_overlay(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    data = dictation_profile_adapters.load_config(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: (
            {
                "default_profile": "quality",
                "runtime": {"vad_segments": False},
                "profiles": {"quality": {"num_beams": 2}},
            },
            None,
        ),
    )

    assert data["schema"] == "abyss_machine_dictation_config_v1"
    assert data["default_profile"] == "quality"
    assert data["runtime"]["vad_segments"] is False
    assert data["profiles"]["quality"]["num_beams"] == 2
    assert "_load_error" not in data


def test_config_adapter_falls_back_on_invalid_loaded_config(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    data = dictation_profile_adapters.load_config(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: ({"default_profile": "not-a-profile"}, None),
    )

    assert data["default_profile"] == "auto"
    assert "default_profile" in data["_load_error"]
    assert data["_invalid_config_path"] == str(paths.config_path)


def test_config_adapter_save_validates_and_writes_metadata(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def write_json(path: Path, data: dict[str, object], mode: int) -> None:
        captured["path"] = path
        captured["data"] = data
        captured["mode"] = mode

    dictation_profile_adapters.save_config(
        paths,
        {"default_profile": "quality"},
        updated_by="unit",
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        write_json_document=write_json,
    )

    assert captured["path"] == paths.config_path
    assert captured["mode"] == 0o664
    data = captured["data"]
    assert data["schema"] == "abyss_machine_dictation_config_v1"
    assert data["updated_by"] == "unit"
    assert data["updated_at"] == "2026-06-28T12:00:00+00:00"


def test_profile_adapter_selects_profile_with_fake_audio_stats(tmp_path: Path) -> None:
    config = dictation_profile_adapters.default_config("abyss_machine", "test")
    config["default_profile"] = "auto"
    audio = tmp_path / "long.wav"
    env = {"ABYSS_DICTATION_TARGET_RMS_DBFS": "-35"}

    profile, selection = dictation_profile_adapters.select_profile(
        None,
        str(audio),
        config=config,
        model_root=tmp_path / "models",
        env=env,
        default_profile="auto",
        wav_stats_fn=lambda path: {"ok": True, "duration_sec": 120.0, "dbfs": -22.0, "peak": 0.4, "clip_percent": 0.0},
    )

    assert selection["selected_profile"] == "long"
    assert selection["reason"] == "long-recording"
    assert profile["name"] == "long"
    assert profile["runtime"]["target_rms_dbfs"] == -35.0


def test_profile_adapter_documents_are_stable_and_fakeable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    config = {"default_profile": "quality", "profile_policy": {"fallback_profile": "quality"}}
    profiles = {"quality": {"name": "quality", "enabled": True}}

    read_doc = dictation_profile_adapters.config_read_document(
        paths=paths,
        config=config,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        path_exists=lambda path: path == paths.config_dir,
        path_writable=lambda path: path == paths.config_dir,
    )
    list_doc = dictation_profile_adapters.profile_list_document(
        config=config,
        profiles=profiles,
        requested_default_profile="quality",
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )
    get_doc = dictation_profile_adapters.profile_get_document(
        requested="quality",
        profile=profiles["quality"],
        selection={"selected_profile": "quality"},
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
    )

    assert read_doc["schema"] == "abyss_machine_dictation_config_read_v1"
    assert read_doc["writable"] is True
    assert list_doc["schema"] == "abyss_machine_dictation_profiles_v1"
    assert list_doc["profiles"]["quality"]["enabled"] is True
    assert get_doc["schema"] == "abyss_machine_dictation_profile_v1"
    assert get_doc["selection"]["selected_profile"] == "quality"


def test_cli_dictation_config_wrappers_bind_profile_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_load_config(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["load_paths"] = paths_arg
        captured["load_kwargs"] = kwargs
        return {"default_profile": "quality"}

    def fake_save_config(paths_arg: object, config: dict[str, object], **kwargs: object) -> None:
        captured["save_paths"] = paths_arg
        captured["save_config"] = config
        captured["save_kwargs"] = kwargs

    monkeypatch.setattr(cli, "dictation_config_paths", lambda: paths)
    monkeypatch.setattr(dictation_profile_adapters, "load_config", fake_load_config)
    monkeypatch.setattr(dictation_profile_adapters, "save_config", fake_save_config)

    assert cli.dictation_config() == {"default_profile": "quality"}
    cli.save_dictation_config({"default_profile": "quality"}, "unit")

    assert captured["load_paths"] == paths
    assert captured["load_kwargs"]["load_json_document"] is cli.load_json_document
    assert captured["save_paths"] == paths
    assert captured["save_config"] == {"default_profile": "quality"}
    assert captured["save_kwargs"]["write_json_document"] is cli.atomic_write_json
    assert captured["save_kwargs"]["updated_by"] == "unit"


def test_cli_dictation_profile_selection_binds_profile_adapter(monkeypatch, tmp_path: Path) -> None:
    config = {"default_profile": "auto"}
    captured: dict[str, object] = {}

    def fake_select_profile(name: object, audio: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        captured["name"] = name
        captured["audio"] = audio
        captured.update(kwargs)
        return {"name": "quality"}, {"selected_profile": "quality"}

    monkeypatch.setattr(cli, "dictation_config", lambda: config)
    monkeypatch.setattr(dictation_profile_adapters, "select_profile", fake_select_profile)

    profile, selection = cli.dictation_profile("auto", str(tmp_path / "audio.wav"))

    assert profile == {"name": "quality"}
    assert selection == {"selected_profile": "quality"}
    assert captured["config"] == config
    assert captured["model_root"] == cli.DICTATION_MODEL_ROOT
    assert captured["env"] is cli.os.environ
    assert captured["default_profile"] == cli.DICTATION_DEFAULT_PROFILE
    assert captured["wav_stats_fn"] is cli.wav_stats
