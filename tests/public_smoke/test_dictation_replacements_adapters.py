from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import dictation_replacements_adapters


def _paths(tmp_path: Path) -> dictation_replacements_adapters.DictationReplacementsPaths:
    return dictation_replacements_adapters.DictationReplacementsPaths(
        replacements_path=tmp_path / "etc" / "abyss-machine" / "dictation" / "replacements.json",
    )


def test_replacements_adapter_loads_default_on_missing_or_invalid(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    missing = dictation_replacements_adapters.load_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: (None, "missing"),
    )
    denied = dictation_replacements_adapters.load_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: (None, "permission denied"),
    )
    invalid = dictation_replacements_adapters.load_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: ({"items": "bad"}, None),
    )

    assert missing["schema"] == "abyss_machine_dictation_replacements_v1"
    assert "_load_error" not in missing
    assert denied["_load_error"] == "permission denied"
    assert invalid["_load_error"] == "items must be a list"


def test_replacements_adapter_loads_existing_document(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    loaded = dictation_replacements_adapters.load_document(
        paths,
        schema_prefix="abyss_machine",
        version="test",
        load_json_document=lambda path: ({"items": []}, None),
    )

    assert loaded["schema"] == "abyss_machine_dictation_replacements_v1"
    assert loaded["version"] == "test"
    assert loaded["items"] == []


def test_replacements_adapter_saves_normalized_document(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    def write_json(path: Path, data: dict[str, object], mode: int) -> None:
        captured["path"] = path
        captured["data"] = data
        captured["mode"] = mode

    dictation_replacements_adapters.save_document(
        paths,
        {"items": []},
        updated_by="unit",
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        write_json_document=write_json,
    )

    data = captured["data"]
    assert captured["path"] == paths.replacements_path
    assert captured["mode"] == 0o664
    assert data["schema"] == "abyss_machine_dictation_replacements_v1"
    assert data["updated_by"] == "unit"
    assert data["updated_at"] == "2026-06-28T12:00:00+00:00"


def test_replacements_adapter_documents_and_apply_are_stable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    doc = {
        "items": [
                {
                    "id": "hello",
                    "type": "literal",
                    "from": "абис",
                    "to": "Abyss",
                    "case_sensitive": False,
                    "enabled": True,
                }
        ]
    }

    fixed, applied = dictation_replacements_adapters.apply_text("абис machine", doc)
    listed = dictation_replacements_adapters.list_document(
        paths,
        doc,
        generated_at="2026-06-28T12:00:00+00:00",
        schema_prefix="abyss_machine",
        version="test",
        path_exists=lambda path: path == paths.replacements_path,
    )
    tested = dictation_replacements_adapters.test_document(
        "абис machine",
        doc,
        generated_at="2026-06-28T12:00:00+00:00",
        schema_prefix="abyss_machine",
        version="test",
    )

    assert fixed == "Abyss machine"
    assert applied == ["hello"]
    assert listed["path"] == str(paths.replacements_path)
    assert listed["exists"] is True
    assert tested["output"] == "Abyss machine"


def test_replacements_adapter_adds_and_removes_with_fakeable_ports(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    written: list[dict[str, object]] = []

    def write_json(path: Path, data: dict[str, object], mode: int) -> None:
        written.append({"path": path, "data": data, "mode": mode})

    added = dictation_replacements_adapters.add_replacement(
        paths,
        kind="literal",
        source="Tree of Sofia",
        target="Tree of Sophia",
        item_id=None,
        ignore_case=True,
        fallback_token=7,
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        load_json_document=lambda path: ({"items": []}, None),
        write_json_document=write_json,
        path_exists=lambda path: True,
    )
    assert added["items"][0]["id"] == "tree-of-sofia"
    assert written[-1]["data"]["updated_by"] == "add:tree-of-sofia"

    removed = dictation_replacements_adapters.remove_replacement(
        paths,
        item_id="tree-of-sofia",
        schema_prefix="abyss_machine",
        version="test",
        now=lambda: "2026-06-28T12:00:00+00:00",
        load_json_document=lambda path: ({"items": added["items"]}, None),
        write_json_document=write_json,
        path_exists=lambda path: True,
    )
    assert removed["items"] == []
    assert written[-1]["data"]["updated_by"] == "remove:tree-of-sofia"


def test_replacements_adapter_rejects_duplicate_and_missing_remove(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    doc = {"items": [{"id": "same", "type": "literal", "pattern": "a", "replacement": "b"}]}

    with pytest.raises(ValueError, match="already exists"):
        dictation_replacements_adapters.add_replacement(
            paths,
            kind="literal",
            source="a",
            target="b",
            item_id="same",
            ignore_case=True,
            fallback_token=1,
            schema_prefix="abyss_machine",
            version="test",
            now=lambda: "2026-06-28T12:00:00+00:00",
            load_json_document=lambda path: (doc, None),
            write_json_document=lambda path, data, mode: None,
            path_exists=lambda path: True,
        )

    with pytest.raises(ValueError, match="not found"):
        dictation_replacements_adapters.remove_replacement(
            paths,
            item_id="missing",
            schema_prefix="abyss_machine",
            version="test",
            now=lambda: "2026-06-28T12:00:00+00:00",
            load_json_document=lambda path: (doc, None),
            write_json_document=lambda path, data, mode: None,
            path_exists=lambda path: True,
        )


def test_cli_replacements_wrappers_bind_adapter(monkeypatch, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "dictation_replacements_paths", lambda: paths)
    monkeypatch.setattr(cli.time, "time", lambda: 123)

    def fake_load(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["load"] = (paths_arg, kwargs)
        return {"items": []}

    def fake_save(paths_arg: object, doc: dict[str, object], **kwargs: object) -> None:
        captured["save"] = (paths_arg, doc, kwargs)

    def fake_list(paths_arg: object, doc: dict[str, object], **kwargs: object) -> dict[str, object]:
        captured["list"] = (paths_arg, doc, kwargs)
        return {"items": []}

    def fake_test(text: str, doc: dict[str, object], **kwargs: object) -> dict[str, object]:
        captured["test"] = (text, doc, kwargs)
        return {"output": text}

    def fake_add(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["add"] = (paths_arg, kwargs)
        return {"items": [{"id": "new"}]}

    def fake_remove(paths_arg: object, **kwargs: object) -> dict[str, object]:
        captured["remove"] = (paths_arg, kwargs)
        return {"items": []}

    monkeypatch.setattr(dictation_replacements_adapters, "load_document", fake_load)
    monkeypatch.setattr(dictation_replacements_adapters, "save_document", fake_save)
    monkeypatch.setattr(dictation_replacements_adapters, "list_document", fake_list)
    monkeypatch.setattr(dictation_replacements_adapters, "test_document", fake_test)
    monkeypatch.setattr(dictation_replacements_adapters, "add_replacement", fake_add)
    monkeypatch.setattr(dictation_replacements_adapters, "remove_replacement", fake_remove)

    assert cli.dictation_replacements_document() == {"items": []}
    cli.save_dictation_replacements_document({"items": []}, "unit")
    assert cli.dictation_replacements_list() == {"items": []}
    assert cli.dictation_replacements_test("abc") == {"output": "abc"}
    assert cli.add_dictation_replacement("literal", "a", "b") == {"items": [{"id": "new"}]}
    assert cli.remove_dictation_replacement("new") == {"items": []}

    assert captured["load"][0] == paths
    assert captured["load"][1]["load_json_document"] is cli.load_json_document
    assert captured["save"][2]["write_json_document"] is cli.atomic_write_json
    assert captured["list"][2]["path_exists"] is Path.exists
    assert captured["test"][0] == "abc"
    assert captured["add"][1]["fallback_token"] == 123
    assert captured["add"][1]["write_json_document"] is cli.atomic_write_json
    assert captured["remove"][1]["item_id"] == "new"
