from __future__ import annotations

from abyss_machine import cli
from abyss_machine import typing_browser_adapters


def test_browser_extension_plan_and_status_document_are_public_safe() -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "browser_name": "firefox",
        "title": "Writing",
        "url": "https://example.test/write",
        "text": "synthetic browser text",
        "field": {"safe": True, "kind": "textarea", "type": "textarea"},
    }

    plan = typing_browser_adapters.browser_extension_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_extension_explicit"
    assert plan["ingest"]["text"] == "synthetic browser text"
    assert plan["ingest"]["source"] == "browser_extension_explicit"
    assert plan["ingest"]["app"] == "firefox"
    assert "event_kind=committed_text" in plan["ingest"]["context"]
    assert "field_safe=True" in plan["ingest"]["context"]
    assert plan["ingest"]["metadata"]["browser"]["key_events_captured"] is False

    status = typing_browser_adapters.browser_extension_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-browser",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": 22, "text_chars_stored": 22},
            "duplicate": False,
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert status["ok"] is True
    assert status["event"]["event_id"] == "evt-browser"
    assert status["event"]["capture_gate_confidence"] == "browser_url_and_field_allowed"
    assert status["policy"]["raw_keylogging"] is False
    assert "text" not in status["event"]


def test_browser_ai_transcript_plan_cleans_text_and_preserves_counterpart_metadata() -> None:
    message = {
        "schema": "abyss_machine_browser_ai_transcript_message_v1",
        "event_kind": "ai_transcript_message",
        "browser_name": "firefox",
        "title": "ChatGPT",
        "url": "https://chatgpt.com/c/fixture",
        "text": "ChatGPT said hello\nShow more",
        "browser": {"transcript_safe": True},
        "ai_transcript": {"safe": True, "message_role": "bubble", "message_index": "3", "partial": False},
    }

    plan = typing_browser_adapters.browser_ai_transcript_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_ai_transcript"
    assert plan["ingest"]["text"] == "ChatGPT said hello"
    assert "transcript_safe=True" in plan["ingest"]["context"]
    assert "message_role=assistant" in plan["ingest"]["context"]
    assert plan["text_cleanup"]["removed_line_count"] == 1
    assert plan["transcript_meta"]["message_role"] == "assistant"
    assert plan["transcript_meta"]["page_identity"]["entity_id"] == "ai:openai:chatgpt"

    status = typing_browser_adapters.browser_ai_transcript_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-ai",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "source_adapter": "browser_ai_transcript",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_ai_transcript_known_ai_page_allowed"},
            "text": {"text_length": 18, "text_chars_stored": 18, "truncated": False},
            "causal_context": {
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
                "where": {"context_anchor": {"kind": "ai_chat"}, "interaction": {"id": "fixture"}},
            },
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_ai_transcript_status_v1"
    assert status["event"]["message_role"] == "assistant"
    assert status["event"]["message_index"] == 3
    assert status["event"]["recipient"]["id"] == "ai:openai:chatgpt"
    assert status["policy"]["known_ai_counterpart_required"] is True


def test_browser_selftest_documents_and_native_host_response_envelopes() -> None:
    run_id = typing_browser_adapters.browser_selftest_run_id("fixture-seed")
    safe_message, sensitive_message = typing_browser_adapters.browser_extension_selftest_messages(run_id)
    ai_message, ai_sensitive_message = typing_browser_adapters.browser_ai_transcript_selftest_messages(run_id)

    assert len(run_id) == 12
    assert safe_message["text"].endswith(run_id)
    assert sensitive_message["url"] == "https://example.com/login"
    assert typing_browser_adapters.native_host_message_route(safe_message) == "browser_extension_explicit"
    assert typing_browser_adapters.native_host_message_route(ai_message) == "browser_ai_transcript"
    assert typing_browser_adapters.native_host_message_route(ai_sensitive_message) == "browser_ai_transcript"

    safe = {
        "ok": True,
        "event": {
            "source_adapter": "browser_ai_transcript",
            "status": "captured",
            "capture_gate_decision": "allow_text",
            "recipient": {"id": "ai:google:gemini"},
            "message_role": "assistant",
        },
    }
    sensitive = {"ok": True, "event": {"capture_gate_decision": "metadata_only", "text_chars_stored": 0}}
    selftest = typing_browser_adapters.browser_ai_transcript_selftest_document(
        safe=safe,
        sensitive=sensitive,
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
        test_run_id=run_id,
    )
    response = typing_browser_adapters.native_host_response({"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}})
    error = typing_browser_adapters.native_host_error_response(ValueError("boom"))

    assert selftest["ok"] is True
    assert selftest["status"] == "passed"
    assert response == {"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}}
    assert error["ok"] is False
    assert error["status"] == "native_host_error"
    assert error["policy"]["automatic_action"] is False


def test_cli_browser_extension_ingest_executes_adapter_plan(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T00:00:00Z")
    monkeypatch.setattr(cli, "typing_browser_extension_store", lambda data, write_latest=True: data)

    def fake_ingest(text: str, **kwargs: object) -> dict[str, object]:
        captured["text"] = text
        captured.update(kwargs)
        return {
            "ok": True,
            "event_id": "evt-cli",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": len(text), "text_chars_stored": len(text)},
            "duplicate": False,
        }

    monkeypatch.setattr(cli, "typing_ingest", fake_ingest)

    result = cli.typing_browser_extension_ingest_message(
        {
            "event_kind": "committed_text",
            "browser_name": "firefox",
            "title": "Writing",
            "url": "https://example.test/write",
            "text": "cli fixture",
            "field": {"safe": True, "kind": "textarea", "type": "textarea"},
        },
        write_latest=False,
    )

    assert captured["text"] == "cli fixture"
    assert captured["source"] == "browser_extension_explicit"
    assert captured["write_latest"] is False
    assert captured["skip_duplicate"] is True
    assert result["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert result["event"]["event_id"] == "evt-cli"
