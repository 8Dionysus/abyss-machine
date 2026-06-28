from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import dictation_contracts
from abyss_machine import dictation_postprocess_adapters


def _config() -> dict[str, object]:
    return dictation_contracts.default_config("abyss_machine", "test")


def _replacements_doc() -> dict[str, object]:
    return dictation_contracts.default_replacements_document("abyss_machine", "test")


def test_postprocess_adapter_applies_replacements_from_port() -> None:
    calls: list[str] = []

    def replacements_document() -> dict[str, object]:
        calls.append("replacements")
        return _replacements_doc()

    fixed, changed, applied = dictation_postprocess_adapters.apply_common_transcript_fixes(
        "абис машина читает agents md",
        {"text_fixes": True},
        replacements_document=replacements_document,
    )

    assert calls == ["replacements"]
    assert fixed == "abyss-machine читает AGENTS.md"
    assert changed is True
    assert {"abyss-machine-name", "agents-md-spaced"}.issubset(set(applied))


def test_postprocess_adapter_detects_intent_from_config_port() -> None:
    calls: list[str] = []

    def config_document() -> dict[str, object]:
        calls.append("config")
        return _config()

    intent = dictation_postprocess_adapters.detect_intent(
        "команда открой AGENTS.md",
        config_document=config_document,
        schema_prefix="abyss_machine",
    )
    explicit_intent = dictation_postprocess_adapters.detect_intent(
        "команда открой AGENTS.md",
        config=_config(),
        config_document=lambda: {"command_intent": {"enabled": False}},
        schema_prefix="abyss_machine",
    )

    assert calls == ["config"]
    assert intent["type"] == "command"
    assert intent["payload"] == "открой AGENTS.md"
    assert explicit_intent["type"] == "command"


def test_postprocess_adapter_builds_intent_test_document_with_fakeable_clock() -> None:
    document = dictation_postprocess_adapters.intent_test_document(
        "просто текст",
        config_document=_config,
        generated_at="2026-06-28T12:00:00+00:00",
        schema_prefix="abyss_machine",
        version="test",
    )

    assert document["schema"] == "abyss_machine_dictation_intent_test_v1"
    assert document["version"] == "test"
    assert document["generated_at"] == "2026-06-28T12:00:00+00:00"
    assert document["intent"]["reason"] == "no-trigger-prefix"


def test_postprocess_adapter_processes_transcript_with_config_and_replacements_ports() -> None:
    calls: list[str] = []

    def config_document() -> dict[str, object]:
        calls.append("config")
        return _config()

    def replacements_document() -> dict[str, object]:
        calls.append("replacements")
        return _replacements_doc()

    transcript = dictation_postprocess_adapters.postprocess_transcript_data(
        {"ok": True, "text": "команда открой agents md"},
        {"postprocess": {"text_fixes": True, "final_punctuation": True, "final_space": True}},
        config_document=config_document,
        replacements_document=replacements_document,
        schema_prefix="abyss_machine",
    )

    assert calls == ["config", "replacements"]
    assert transcript["text"] == "Команда открой AGENTS.md. "
    assert transcript["raw_text"] == "команда открой agents md"
    assert transcript["postprocess"]["replacements"] == ["agents-md-spaced"]
    assert transcript["intent"]["type"] == "command"
    assert transcript["intent"]["payload"] == "открой AGENTS.md."
