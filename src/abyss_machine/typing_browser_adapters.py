from __future__ import annotations

import hashlib
from typing import Any, Mapping

from . import typing_capture_contracts


BROWSER_EXTENSION_SOURCE = "browser_extension_explicit"
BROWSER_AI_TRANSCRIPT_SOURCE = "browser_ai_transcript"
BROWSER_EXTENSION_MESSAGE_SCHEMA = "abyss_machine_browser_extension_message_v1"
BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA = "abyss_machine_browser_ai_transcript_message_v1"


def _nested_get(data: Mapping[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def browser_selftest_run_id(seed: str) -> str:
    return hashlib.sha256(str(seed or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def browser_extension_message_metadata(
    message: Mapping[str, Any],
    *,
    extension_id: str,
    native_host: str,
) -> dict[str, Any]:
    return typing_capture_contracts.browser_extension_message_metadata(
        dict(message),
        extension_id=extension_id,
        native_host=native_host,
    )


def browser_ai_transcript_message_metadata(
    message: Mapping[str, Any],
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    page_identity = typing_capture_contracts.browser_ai_counterpart_identity(
        str(message.get("url") or ""),
        str(message.get("title") or ""),
        schema_prefix=schema_prefix,
    )
    return typing_capture_contracts.browser_ai_transcript_message_metadata(
        dict(message),
        extension_id=extension_id,
        native_host=native_host,
        page_identity=page_identity,
    )


def invalid_browser_message_status_document(
    *,
    schema_name: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_{schema_name}_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "invalid_message",
        "error": "message must be an object",
    }


def browser_extension_ingest_plan(
    message: Any,
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        return {
            "valid": False,
            "route": BROWSER_EXTENSION_SOURCE,
            "status_document": invalid_browser_message_status_document(
                schema_name="typing_browser_extension_status",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ),
        }
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    url = str(message.get("url") or "")
    metadata = browser_extension_message_metadata(
        message,
        extension_id=extension_id,
        native_host=native_host,
    )
    context = (
        f"browser_extension event_kind={event_kind} "
        f"field_safe={bool(_nested_get(metadata, ['browser', 'field_safe']))} "
        f"url={url}"
    )
    return {
        "valid": True,
        "route": BROWSER_EXTENSION_SOURCE,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "extension_id": extension_id,
        "native_host": native_host,
        "ingest": {
            "text": str(message.get("text") or ""),
            "source": BROWSER_EXTENSION_SOURCE,
            "app": str(message.get("browser_name") or "firefox"),
            "window_title": str(message.get("title") or ""),
            "context": context,
            "url": url,
            "skip_duplicate": True,
            "metadata": metadata,
            "include_text_in_context_probe": True,
        },
    }


def browser_extension_status_document(
    plan: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_browser_extension_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(event.get("ok")),
        "status": "sent",
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "extension_id": plan.get("extension_id"),
        "native_host": plan.get("native_host"),
        "event": {
            "event_id": event.get("event_id"),
            "generated_at": event.get("generated_at"),
            "status": event.get("status"),
            "capture_gate_decision": _nested_get(event, ["capture_gate", "decision"]),
            "capture_gate_confidence": _nested_get(event, ["capture_gate", "confidence"]),
            "text_length": _nested_get(event, ["text", "text_length"]),
            "text_chars_stored": _nested_get(event, ["text", "text_chars_stored"]),
            "duplicate": event.get("duplicate"),
        },
        "policy": {
            "raw_keylogging": False,
            "keydown_keyup_keypress_captured": False,
            "password_fields_captured": False,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "automatic_action": False,
            "capture_gate_required": True,
        },
        "non_claims": [
            "Browser extension intake receives debounced committed text messages, not raw key events.",
            "Content scripts skip sensitive URLs and fields before native host handoff; host capture-gate is the second line of defense.",
        ],
    }


def browser_ai_transcript_ingest_plan(
    message: Any,
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        return {
            "valid": False,
            "route": BROWSER_AI_TRANSCRIPT_SOURCE,
            "status_document": invalid_browser_message_status_document(
                schema_name="typing_browser_ai_transcript_status",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ),
        }
    text_cleanup = typing_capture_contracts.browser_ai_transcript_clean_text(str(message.get("text") or ""))
    text = str(text_cleanup.get("text") or "")
    url = str(message.get("url") or "")
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    metadata = browser_ai_transcript_message_metadata(
        message,
        extension_id=extension_id,
        native_host=native_host,
        schema_prefix=schema_prefix,
    )
    metadata["text_cleanup"] = text_cleanup
    transcript_meta = metadata.get("ai_transcript") if isinstance(metadata.get("ai_transcript"), dict) else {}
    context = (
        f"browser_ai_transcript event_kind={event_kind} "
        f"transcript_safe={bool(_nested_get(metadata, ['browser', 'transcript_safe']))} "
        f"message_role={transcript_meta.get('message_role') or 'unknown'} "
        f"message_index={transcript_meta.get('message_index')} "
        f"partial={bool(transcript_meta.get('partial'))} "
        f"url={url}"
    )
    return {
        "valid": True,
        "route": BROWSER_AI_TRANSCRIPT_SOURCE,
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "extension_id": extension_id,
        "native_host": native_host,
        "text_cleanup": text_cleanup,
        "transcript_meta": transcript_meta,
        "ingest": {
            "text": text,
            "source": BROWSER_AI_TRANSCRIPT_SOURCE,
            "app": str(message.get("browser_name") or "firefox"),
            "window_title": str(message.get("title") or ""),
            "context": context,
            "url": url,
            "skip_duplicate": True,
            "metadata": metadata,
            "include_text_in_context_probe": True,
        },
    }


def browser_ai_transcript_status_document(
    plan: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    transcript_meta = plan.get("transcript_meta") if isinstance(plan.get("transcript_meta"), Mapping) else {}
    return {
        "schema": f"{schema_prefix}_typing_browser_ai_transcript_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(event.get("ok")),
        "status": "sent",
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "extension_id": plan.get("extension_id"),
        "native_host": plan.get("native_host"),
        "event": {
            "event_id": event.get("event_id"),
            "generated_at": event.get("generated_at"),
            "status": event.get("status"),
            "source_adapter": event.get("source_adapter"),
            "capture_gate_decision": _nested_get(event, ["capture_gate", "decision"]),
            "capture_gate_confidence": _nested_get(event, ["capture_gate", "confidence"]),
            "text_length": _nested_get(event, ["text", "text_length"]),
            "text_chars_stored": _nested_get(event, ["text", "text_chars_stored"]),
            "text_truncated": _nested_get(event, ["text", "truncated"]),
            "text_cleanup": plan.get("text_cleanup"),
            "duplicate": event.get("duplicate"),
            "recipient": _nested_get(event, ["causal_context", "recipient"]),
            "context_anchor": _nested_get(event, ["causal_context", "where", "context_anchor"]),
            "interaction": _nested_get(event, ["causal_context", "where", "interaction"]),
            "project_binding": _nested_get(event, ["causal_context", "where", "binding_signals", "project_binding"]),
            "message_role": transcript_meta.get("message_role"),
            "message_index": transcript_meta.get("message_index"),
            "partial": transcript_meta.get("partial"),
            "completeness": transcript_meta.get("completeness"),
        },
        "policy": {
            "raw_keylogging": False,
            "keydown_keyup_keypress_captured": False,
            "password_fields_captured": False,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "automatic_action": False,
            "capture_gate_required": True,
            "known_ai_counterpart_required": True,
            "transcript_safe_marker_required": True,
        },
        "non_claims": [
            "Browser AI transcript intake records visible AI-chat message text from known AI pages; it is not raw keylogging.",
            "Message completeness is explicit metadata and must not be treated as a full transcript proof when partial or unknown.",
            "AT-SPI browser content remains a fallback context route, not transcript authority.",
        ],
    }


def browser_extension_selftest_messages(test_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_message = {
        "schema": BROWSER_EXTENSION_MESSAGE_SCHEMA,
        "event_kind": "selftest",
        "browser_name": "firefox",
        "title": "Abyss browser typing selftest",
        "url": "https://example.com/abyss-input-selftest",
        "text": f"abyss browser explicit committed text selftest {test_run_id}",
        "field": {"safe": True, "kind": "textarea", "type": "textarea"},
    }
    sensitive_message = {
        "schema": BROWSER_EXTENSION_MESSAGE_SCHEMA,
        "event_kind": "selftest",
        "browser_name": "firefox",
        "title": "Login selftest",
        "url": "https://example.com/login",
        "text": f"should remain metadata only browser login probe {test_run_id}",
        "field": {"safe": True, "kind": "input", "type": "text"},
    }
    return safe_message, sensitive_message


def browser_extension_selftest_document(
    *,
    safe: Mapping[str, Any],
    sensitive: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    test_run_id: str,
) -> dict[str, Any]:
    safe_event = safe.get("event") if isinstance(safe.get("event"), Mapping) else {}
    sensitive_event = sensitive.get("event") if isinstance(sensitive.get("event"), Mapping) else {}
    return {
        "schema": f"{schema_prefix}_typing_browser_extension_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(safe.get("ok"))
        and bool(sensitive.get("ok"))
        and safe_event.get("capture_gate_decision") == "allow_text"
        and sensitive_event.get("capture_gate_decision") == "metadata_only",
        "status": "passed",
        "test_run_id": test_run_id,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "safe": safe_event,
        "sensitive": sensitive_event,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "safe_route_allows_text": safe_event.get("capture_gate_decision") == "allow_text",
            "login_route_metadata_only": sensitive_event.get("capture_gate_decision") == "metadata_only",
        },
    }


def browser_ai_transcript_selftest_messages(test_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_message = {
        "schema": BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA,
        "event_kind": "ai_transcript_selftest",
        "browser_name": "firefox",
        "title": "Gemini transcript selftest",
        "url": "https://gemini.google.com/app/abyss-transcript-selftest",
        "text": f"Gemini assistant transcript selftest message {test_run_id}",
        "browser": {"transcript_safe": True, "event_kind": "ai_transcript_selftest"},
        "ai_transcript": {
            "safe": True,
            "message_role": "assistant",
            "message_index": 1,
            "message_order": 1,
            "partial": False,
            "selector_basis": "selftest",
            "reason": "selftest",
        },
    }
    sensitive_message = {
        **safe_message,
        "title": "Gemini login transcript selftest",
        "url": "https://gemini.google.com/login",
        "text": f"Gemini transcript login probe should stay metadata only {test_run_id}",
        "ai_transcript": {
            **safe_message["ai_transcript"],
            "message_index": 2,
            "message_order": 2,
        },
    }
    return safe_message, sensitive_message


def browser_ai_transcript_selftest_document(
    *,
    safe: Mapping[str, Any],
    sensitive: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    test_run_id: str,
) -> dict[str, Any]:
    safe_event = safe.get("event") if isinstance(safe.get("event"), Mapping) else {}
    sensitive_event = sensitive.get("event") if isinstance(sensitive.get("event"), Mapping) else {}
    data = {
        "schema": f"{schema_prefix}_typing_browser_ai_transcript_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(safe.get("ok"))
        and bool(sensitive.get("ok"))
        and safe_event.get("source_adapter") == BROWSER_AI_TRANSCRIPT_SOURCE
        and safe_event.get("capture_gate_decision") == "allow_text"
        and _nested_get(safe_event, ["recipient", "id"]) == "ai:google:gemini"
        and safe_event.get("message_role") == "assistant"
        and sensitive_event.get("capture_gate_decision") == "metadata_only"
        and _safe_int(sensitive_event.get("text_chars_stored"), 0) == 0,
        "status": "passed",
        "test_run_id": test_run_id,
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "safe": safe_event,
        "sensitive": sensitive_event,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "safe_known_ai_route_allows_text": safe_event.get("capture_gate_decision") == "allow_text",
            "login_route_metadata_only": sensitive_event.get("capture_gate_decision") == "metadata_only",
            "recipient_is_ai_counterpart": _nested_get(safe_event, ["recipient", "id"]) == "ai:google:gemini",
            "automatic_action": False,
        },
    }
    if data["ok"] is not True:
        data["status"] = "failed"
    return data


def native_host_message_route(message: Mapping[str, Any]) -> str:
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    if message.get("schema") == BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA or event_kind.startswith("ai_transcript_"):
        return BROWSER_AI_TRANSCRIPT_SOURCE
    return BROWSER_EXTENSION_SOURCE


def native_host_response(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "event": result.get("event"),
        "policy": result.get("policy"),
    }


def native_host_error_response(error: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "native_host_error",
        "error": repr(error)[:240],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }
