from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_validation_adapters


def _paths(tmp_path: Path) -> dictation_validation_adapters.DictationValidationPaths:
    return dictation_validation_adapters.DictationValidationPaths(
        validate_latest=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "validate" / "latest.json",
        validate_history=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "validate",
        transcript_latest=tmp_path / "var" / "lib" / "abyss-machine" / "dictation" / "transcripts" / "latest.json",
    )


def test_validation_adapter_accepts_valid_transcript_latest(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    checks = dictation_validation_adapters.validation_checks(
        paths=paths,
        ensure_docs=lambda: [],
        load_json_document=lambda path: ({"schema": "abyss_machine_dictation_transcript_event_v1"}, None),
        path_exists=lambda path: path == paths.transcript_latest,
        schema_prefix="abyss_machine",
    )

    assert [item["key"] for item in checks] == ["dictation_docs_index", "dictation_transcript_latest"]
    assert [item["level"] for item in checks] == ["ok", "ok"]
    assert checks[1]["data"]["expected_schema"] == "abyss_machine_dictation_transcript_event_v1"


def test_validation_adapter_allows_empty_transcript_latest(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    checks = dictation_validation_adapters.validation_checks(
        paths=paths,
        ensure_docs=lambda: [],
        load_json_document=lambda path: ({}, "should-not-read"),
        path_exists=lambda path: False,
        schema_prefix="abyss_machine",
    )

    assert checks[1]["level"] == "ok"
    assert checks[1]["key"] == "dictation_transcript_latest_empty"
    assert checks[1]["data"]["empty_state"] is True


def test_validation_adapter_reports_docs_and_latest_errors(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    checks = dictation_validation_adapters.validation_checks(
        paths=paths,
        ensure_docs=lambda: [{"path": "/tmp/index.json", "error": "denied"}],
        load_json_document=lambda path: ({"schema": "wrong"}, None),
        path_exists=lambda path: True,
        schema_prefix="abyss_machine",
    )

    assert checks[0]["level"] == "fail"
    assert checks[0]["data"]["errors"] == [{"path": "/tmp/index.json", "error": "denied"}]
    assert checks[1]["level"] == "fail"
    assert checks[1]["data"]["schema"] == "wrong"


def test_validation_adapter_writes_latest_through_fakeable_port(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}
    document = {"schema": "abyss_machine_dictation_validate_v1"}

    def fake_write(data: dict[str, object], latest: Path, history: Path) -> list[dict[str, object]]:
        captured["data"] = data
        captured["latest"] = latest
        captured["history"] = history
        return []

    errors = dictation_validation_adapters.write_validation_latest(
        document,
        paths=paths,
        write_latest_and_history=fake_write,
    )

    assert errors == []
    assert captured == {
        "data": document,
        "latest": paths.validate_latest,
        "history": paths.validate_history,
    }


def test_cli_dictation_validation_wrappers_bind_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def fake_validation_checks(**kwargs: object) -> list[dict[str, object]]:
        captured["checks_kwargs"] = kwargs
        return [{"level": "ok", "key": "unit", "message": "ok"}]

    def fake_write_latest(data: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        captured["write_data"] = data
        captured["write_kwargs"] = kwargs
        return []

    monkeypatch.setattr(cli, "dictation_validation_paths", lambda: paths)
    monkeypatch.setattr(dictation_validation_adapters, "validation_checks", fake_validation_checks)
    monkeypatch.setattr(dictation_validation_adapters, "write_validation_latest", fake_write_latest)

    assert cli.dictation_validation_checks() == [{"level": "ok", "key": "unit", "message": "ok"}]
    assert cli.write_dictation_validation_latest({"schema": "status"}) == []

    checks_kwargs = captured["checks_kwargs"]
    assert checks_kwargs["paths"] == paths
    assert checks_kwargs["ensure_docs"] is cli.ensure_dictation_docs
    assert checks_kwargs["load_json_document"] is cli.load_json_document
    assert checks_kwargs["path_exists"] is Path.exists
    assert checks_kwargs["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["write_data"] == {"schema": "status"}
    assert captured["write_kwargs"]["paths"] == paths
    assert captured["write_kwargs"]["write_latest_and_history"] is cli.write_latest_and_history


def test_subsystem_validate_routes_dictation_checks_and_writes(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli,
        "subsystem_specs",
        lambda: {
            "dictation": {
                "latest": paths.validate_latest,
                "history": paths.validate_history,
                "paths": lambda: {"schema": "paths"},
                "docs": [],
                "dirs": [],
                "executables": [],
                "json": [],
                "timers": [],
                "bridge_commands": [],
            }
        },
    )
    monkeypatch.setattr(cli, "bridge_manifest", lambda: {"commands": {}})
    monkeypatch.setattr(
        cli,
        "dictation_validation_checks",
        lambda: [{"level": "ok", "key": "dictation_docs_index", "message": "ok"}],
    )

    def fake_write(data: dict[str, object]) -> list[dict[str, object]]:
        captured["write_data"] = data
        return []

    monkeypatch.setattr(cli, "write_dictation_validation_latest", fake_write)

    document = cli.subsystem_validate("dictation", strict=False, write_latest=True)

    assert document["schema"] == "abyss_machine_dictation_validate_v1"
    assert document["summary"]["fails"] == 0
    assert captured["write_data"] is document
