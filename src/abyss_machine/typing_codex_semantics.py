from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping


CODEX_PROMPT_SUBMIT_SOURCE = "codex_user_prompt_submit"
CODEX_SESSION_TAIL_SOURCE = "codex_session_jsonl_prompt_tail"


def prompt_text_from_event(event: Mapping[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "message", "content", "text"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    content = event.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks)
    return ""


def prompt_hook_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    cwd = str(event.get("cwd") or "")
    transcript_path = str(event.get("transcript_path") or "")
    metadata: dict[str, Any] = {
        "codex": {
            "session_id": str(event.get("session_id") or ""),
            "turn_id": str(event.get("turn_id") or ""),
            "hook_event_name": str(event.get("hook_event_name") or "UserPromptSubmit"),
            "model": str(event.get("model") or ""),
            "permission_mode": str(event.get("permission_mode") or ""),
            "transcript_path": transcript_path,
        }
    }
    if cwd:
        metadata["file"] = {"root": cwd, "path": cwd, "name": Path(cwd).name or cwd}
    return metadata


def prompt_hook_ingest_plan(event: Mapping[str, Any]) -> dict[str, Any]:
    prompt = prompt_text_from_event(event)
    session_id = str(event.get("session_id") or "").strip()
    turn_id = str(event.get("turn_id") or "").strip()
    cwd = str(event.get("cwd") or "").strip()
    context_parts = ["codex_prompt_submit", "hook=UserPromptSubmit"]
    if cwd:
        context_parts.append(f"cwd={cwd}")
    if session_id:
        context_parts.append(f"session_id={session_id}")
    if turn_id:
        context_parts.append(f"turn_id={turn_id}")
    return {
        "prompt": prompt,
        "session_id": session_id,
        "turn_id": turn_id,
        "cwd": cwd,
        "source": CODEX_PROMPT_SUBMIT_SOURCE,
        "app": "codex",
        "window_title": f"codex:{session_id[:8]}" if session_id else "codex",
        "context": " ".join(context_parts),
        "metadata": prompt_hook_metadata(event),
    }


def message_text(payload: Mapping[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    chunks: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunk for chunk in chunks if chunk)


def user_message_normalize(raw_text: str) -> dict[str, Any]:
    raw = str(raw_text or "")
    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    data: dict[str, Any] = {
        "capture": bool(text),
        "text": text,
        "envelope_kind": "plain_user_message",
        "raw_text_length": len(raw),
        "normalized_text_length": len(text),
        "stripped_prefix_chars": 0,
        "skip_reason": None,
    }
    if not text:
        data["capture"] = False
        data["skip_reason"] = "empty_message"
        return data
    if text.startswith("<goal_context>") and "</goal_context>" in text[:12000]:
        data.update({
            "capture": False,
            "text": "",
            "envelope_kind": "codex_goal_context_continuation",
            "normalized_text_length": 0,
            "stripped_prefix_chars": len(raw),
            "skip_reason": "goal_context_continuation_not_operator_typed_submit",
        })
        return data
    for tag, kind in {
        "environment_context": "codex_environment_context",
        "turn_aborted": "codex_turn_aborted_marker",
    }.items():
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        if text.startswith(open_tag) and close_tag in text[:12000]:
            data.update({
                "capture": False,
                "text": "",
                "envelope_kind": kind,
                "normalized_text_length": 0,
                "stripped_prefix_chars": len(raw),
                "skip_reason": f"{kind}_not_operator_typed_submit",
            })
            return data
    request_match = re.search(r"(?ims)^#+\s*My request for Codex:\s*\n(?P<request>.*)$", text)
    if request_match:
        request_text = str(request_match.group("request") or "").strip()
        data.update({
            "capture": bool(request_text),
            "text": request_text,
            "envelope_kind": "vscode_codex_context_envelope",
            "normalized_text_length": len(request_text),
            "stripped_prefix_chars": request_match.start("request"),
            "request_marker": "My request for Codex",
            "skip_reason": None if request_text else "empty_request_after_context_envelope",
        })
    return data


def session_tail_user_messages(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    record_type = str(record.get("type") or "")
    if record_type == "event_msg" and payload.get("type") == "user_message":
        return [{
            "raw_text": str(payload.get("message") or ""),
            "raw_record_route": "event_msg.user_message",
            "raw_record_type": record_type,
            "raw_payload_type": str(payload.get("type") or ""),
            "raw_role": "",
            "content_types": [],
        }]
    if record_type == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
        content = payload.get("content")
        content_types: list[str] = []
        if isinstance(content, list):
            for item in content:
                if isinstance(item, Mapping):
                    content_types.append(str(item.get("type") or "dict"))
                else:
                    content_types.append(type(item).__name__)
        raw_text = message_text(payload)
        return [{
            "raw_text": raw_text,
            "raw_record_route": "response_item.message.role_user",
            "raw_record_type": record_type,
            "raw_payload_type": str(payload.get("type") or ""),
            "raw_role": str(payload.get("role") or ""),
            "content_types": content_types[:12],
        }]
    return []


def session_tail_dedupe_key(session_id: str, text: str) -> str:
    text_hash = hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()
    return f"{session_id}:{text_hash}"


def session_tail_should_skip_duplicate(
    seen_prompt_lines: dict[str, int],
    dedupe_key: str,
    line_no: int,
    *,
    max_line_gap: int = 3,
) -> bool:
    previous_prompt_line = seen_prompt_lines.get(dedupe_key)
    if previous_prompt_line is not None and abs(line_no - previous_prompt_line) <= max_line_gap:
        return True
    seen_prompt_lines[dedupe_key] = line_no
    return False


def session_tail_ingest_plan(
    *,
    session_id: str,
    transcript_path: str,
    line_no: int,
    timestamp: str,
    turn_context: Mapping[str, Any] | None,
    user_message: Mapping[str, Any],
    normalized_message: Mapping[str, Any],
) -> dict[str, Any]:
    turn = turn_context if isinstance(turn_context, Mapping) else {}
    turn_id = str(turn.get("turn_id") or "")
    cwd = str(turn.get("cwd") or "")
    path = Path(transcript_path)
    text = str(normalized_message.get("text") or "")
    metadata = {
        "codex": {
            "session_id": session_id,
            "turn_id": turn_id,
            "hook_event_name": "CodexSessionJsonlTail",
            "transcript_path": transcript_path,
            "raw_line": line_no,
            "raw_timestamp": timestamp,
            "raw_record_route": str(user_message.get("raw_record_route") or ""),
            "raw_record_type": str(user_message.get("raw_record_type") or ""),
            "raw_payload_type": str(user_message.get("raw_payload_type") or ""),
            "raw_role": str(user_message.get("raw_role") or ""),
            "raw_content_types": user_message.get("content_types") if isinstance(user_message.get("content_types"), list) else [],
            "message_normalization": {
                "envelope_kind": normalized_message.get("envelope_kind"),
                "raw_text_length": normalized_message.get("raw_text_length"),
                "normalized_text_length": normalized_message.get("normalized_text_length"),
                "stripped_prefix_chars": normalized_message.get("stripped_prefix_chars"),
                "request_marker": normalized_message.get("request_marker"),
                "skip_reason": normalized_message.get("skip_reason"),
            },
            "fallback": True,
            "native_hook_replacement": False,
        },
        "file": {
            "root": cwd or str(path.parent),
            "path": cwd or transcript_path,
            "name": Path(cwd).name if cwd else path.name,
        },
    }
    context_parts = [
        "codex_session_jsonl_tail",
        f"raw_line={line_no}",
        f"session_id={session_id}",
        f"raw_route={user_message.get('raw_record_route')}",
    ]
    if turn_id:
        context_parts.append(f"turn_id={turn_id}")
    if cwd:
        context_parts.append(f"cwd={cwd}")
    return {
        "text": text,
        "source": CODEX_SESSION_TAIL_SOURCE,
        "app": "codex",
        "window_title": f"codex-session:{session_id[:8]}",
        "context": " ".join(context_parts),
        "metadata": metadata,
        "raw_path": transcript_path,
        "raw_line": line_no,
        "raw_timestamp": timestamp,
        "raw_record_route": str(user_message.get("raw_record_route") or ""),
        "raw_record_type": str(user_message.get("raw_record_type") or ""),
        "raw_payload_type": str(user_message.get("raw_payload_type") or ""),
        "raw_role": str(user_message.get("raw_role") or ""),
        "raw_content_types": user_message.get("content_types") if isinstance(user_message.get("content_types"), list) else [],
    }


def _nested_get(payload: Mapping[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def typing_event_brief(event_data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": event_data.get("ok"),
        "event_id": event_data.get("event_id"),
        "status": event_data.get("status"),
        "source_adapter": event_data.get("source_adapter"),
        "capture_gate_decision": _nested_get(event_data, ["capture_gate", "decision"]),
        "text_length": _nested_get(event_data, ["text", "text_length"]),
        "text_chars_stored": _nested_get(event_data, ["text", "text_chars_stored"]),
        "metadata_only_reason": _nested_get(event_data, ["text", "metadata_only_reason"]),
        "duplicate": event_data.get("duplicate"),
    }


def session_tail_event_summary(plan: Mapping[str, Any], event_data: Mapping[str, Any]) -> dict[str, Any]:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), Mapping) else {}
    codex = metadata.get("codex") if isinstance(metadata.get("codex"), Mapping) else {}
    return {
        "raw_path": plan.get("raw_path"),
        "raw_line": plan.get("raw_line"),
        "raw_timestamp": plan.get("raw_timestamp"),
        "event_id": event_data.get("event_id"),
        "ok": event_data.get("ok"),
        "status": event_data.get("status"),
        "source_adapter": event_data.get("source_adapter"),
        "capture_gate_decision": _nested_get(event_data, ["capture_gate", "decision"]),
        "text_length": _nested_get(event_data, ["text", "text_length"]),
        "text_chars_stored": _nested_get(event_data, ["text", "text_chars_stored"]),
        "metadata_only_reason": _nested_get(event_data, ["text", "metadata_only_reason"]),
        "raw_record_route": plan.get("raw_record_route"),
        "raw_record_type": plan.get("raw_record_type"),
        "raw_payload_type": plan.get("raw_payload_type"),
        "raw_role": plan.get("raw_role"),
        "raw_content_types": plan.get("raw_content_types") if isinstance(plan.get("raw_content_types"), list) else [],
        "message_normalization": codex.get("message_normalization"),
    }
