from __future__ import annotations

from pathlib import Path

from abyss_machine import cli
from abyss_machine import typing_codex_semantics


def test_prompt_hook_plan_extracts_content_list_and_metadata() -> None:
    event = {
        "session_id": "session-12345678",
        "turn_id": "turn-9",
        "cwd": "/work/abyss-machine",
        "transcript_path": "/tmp/session.jsonl",
        "hook_event_name": "UserPromptSubmit",
        "model": "gpt-test",
        "permission_mode": "test",
        "content": [{"type": "input_text", "text": "first"}, "second"],
    }

    plan = typing_codex_semantics.prompt_hook_ingest_plan(event)

    assert plan["prompt"] == "first\nsecond"
    assert plan["source"] == "codex_user_prompt_submit"
    assert plan["app"] == "codex"
    assert plan["window_title"] == "codex:session-"
    assert "cwd=/work/abyss-machine" in plan["context"]
    assert "session_id=session-12345678" in plan["context"]
    assert plan["metadata"]["codex"]["turn_id"] == "turn-9"
    assert plan["metadata"]["codex"]["transcript_path"] == "/tmp/session.jsonl"
    assert plan["metadata"]["file"] == {
        "root": "/work/abyss-machine",
        "path": "/work/abyss-machine",
        "name": "abyss-machine",
    }


def test_user_message_normalize_preserves_operator_text_and_skips_codex_envelopes() -> None:
    plain = typing_codex_semantics.user_message_normalize("  Сделай нормально  ")
    vscode = typing_codex_semantics.user_message_normalize(
        "Workspace context\n\n### My request for Codex:\n\nЗакрой seam\n"
    )
    goal = typing_codex_semantics.user_message_normalize("<goal_context>\nContinue\n</goal_context>")
    environment = typing_codex_semantics.user_message_normalize(
        "<environment_context>\n  <cwd>/srv/AbyssOS</cwd>\n</environment_context>"
    )
    aborted = typing_codex_semantics.user_message_normalize("<turn_aborted>\nInterrupted\n</turn_aborted>")

    assert plain["capture"] is True
    assert plain["text"] == "Сделай нормально"
    assert plain["envelope_kind"] == "plain_user_message"
    assert vscode["capture"] is True
    assert vscode["text"] == "Закрой seam"
    assert vscode["envelope_kind"] == "vscode_codex_context_envelope"
    assert vscode["request_marker"] == "My request for Codex"
    assert goal["capture"] is False
    assert goal["skip_reason"] == "goal_context_continuation_not_operator_typed_submit"
    assert environment["capture"] is False
    assert environment["envelope_kind"] == "codex_environment_context"
    assert aborted["capture"] is False
    assert aborted["envelope_kind"] == "codex_turn_aborted_marker"


def test_session_tail_user_messages_covers_codex_routes_and_ignores_assistant() -> None:
    event_msg = {
        "type": "event_msg",
        "payload": {"type": "user_message", "message": "operator event text"},
    }
    response_item = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "operator response text"}],
        },
    }
    assistant = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "assistant text"}],
        },
    }

    event_routes = typing_codex_semantics.session_tail_user_messages(event_msg)
    response_routes = typing_codex_semantics.session_tail_user_messages(response_item)

    assert event_routes == [{
        "raw_text": "operator event text",
        "raw_record_route": "event_msg.user_message",
        "raw_record_type": "event_msg",
        "raw_payload_type": "user_message",
        "raw_role": "",
        "content_types": [],
    }]
    assert response_routes[0]["raw_text"] == "operator response text"
    assert response_routes[0]["raw_record_route"] == "response_item.message.role_user"
    assert response_routes[0]["raw_role"] == "user"
    assert response_routes[0]["content_types"] == ["input_text"]
    assert typing_codex_semantics.session_tail_user_messages(assistant) == []


def test_session_tail_dedupe_only_skips_near_duplicate_lines() -> None:
    seen: dict[str, int] = {}
    key = typing_codex_semantics.session_tail_dedupe_key("session-a", "same text")

    assert typing_codex_semantics.session_tail_should_skip_duplicate(seen, key, 10) is False
    assert seen[key] == 10
    assert typing_codex_semantics.session_tail_should_skip_duplicate(seen, key, 12) is True
    assert seen[key] == 10
    assert typing_codex_semantics.session_tail_should_skip_duplicate(seen, key, 20) is False
    assert seen[key] == 20


def test_session_tail_plan_and_event_summary_are_public_safe() -> None:
    plan = typing_codex_semantics.session_tail_ingest_plan(
        session_id="session-abcdef12",
        transcript_path="/tmp/codex/session.jsonl",
        line_no=42,
        timestamp="2026-06-27T12:00:00+00:00",
        turn_context={"turn_id": "turn-1", "cwd": "/work/project"},
        user_message={
            "raw_record_route": "response_item.message.role_user",
            "raw_record_type": "response_item",
            "raw_payload_type": "message",
            "raw_role": "user",
            "content_types": ["input_text"],
        },
        normalized_message={
            "text": "operator request",
            "envelope_kind": "plain_user_message",
            "raw_text_length": 16,
            "normalized_text_length": 16,
            "stripped_prefix_chars": 0,
            "request_marker": None,
            "skip_reason": None,
        },
    )
    event_data = {
        "ok": True,
        "event_id": "typing-1",
        "status": "metadata_only",
        "source_adapter": "codex_session_jsonl_prompt_tail",
        "capture_gate": {"decision": "metadata_only"},
        "text": {"text_length": 16, "text_chars_stored": 0, "metadata_only_reason": "policy"},
    }

    summary = typing_codex_semantics.session_tail_event_summary(plan, event_data)

    assert plan["text"] == "operator request"
    assert plan["source"] == "codex_session_jsonl_prompt_tail"
    assert plan["window_title"] == "codex-session:session-"
    assert "raw_line=42" in plan["context"]
    assert plan["metadata"]["codex"]["message_normalization"]["envelope_kind"] == "plain_user_message"
    assert plan["metadata"]["file"] == {"root": "/work/project", "path": "/work/project", "name": "project"}
    assert summary["event_id"] == "typing-1"
    assert summary["text_chars_stored"] == 0
    assert summary["message_normalization"]["normalized_text_length"] == 16
    assert "text" not in summary


def test_cli_codex_prompt_hook_uses_semantic_plan(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_typing_ingest(text: str, **kwargs: object) -> dict[str, object]:
        captured["text"] = text
        captured.update(kwargs)
        return {
            "ok": True,
            "event_id": "typing-hook-1",
            "status": "captured",
            "source_adapter": kwargs["source"],
            "capture_gate": {"decision": "allow_text"},
            "text": {"text_length": len(text), "text_chars_stored": len(text)},
            "duplicate": False,
        }

    monkeypatch.setattr(cli, "typing_ingest", fake_typing_ingest)

    result = cli.typing_codex_prompt_hook_ingest_event(
        {
            "session_id": "session-12345678",
            "turn_id": "turn-9",
            "cwd": str(Path("/work/project")),
            "content": [{"text": "operator prompt"}],
        },
        write_latest=False,
    )

    assert result["ok"] is True
    assert result["status"] == "ingested"
    assert result["typing_event"]["event_id"] == "typing-hook-1"
    assert captured["text"] == "operator prompt"
    assert captured["source"] == "codex_user_prompt_submit"
    assert captured["app"] == "codex"
    assert captured["window_title"] == "codex:session-"
    assert captured["skip_duplicate"] is True
    assert captured["metadata"]["codex"]["session_id"] == "session-12345678"
