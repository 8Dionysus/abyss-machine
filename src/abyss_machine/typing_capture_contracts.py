from __future__ import annotations

import collections
import datetime as dt
import hashlib
import re
import urllib.parse
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import nervous_redaction


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def nested_get(data: Mapping[str, Any], path: list[str]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(key)
    return cursor


def browser_extension_policy(policy: dict[str, Any], default_policy: dict[str, Any]) -> dict[str, Any]:
    browser = policy.get("browser_extension") if isinstance(policy.get("browser_extension"), dict) else {}
    default_browser = default_policy.get("browser_extension", {})
    return deep_merge(default_browser, browser) if isinstance(default_browser, dict) else browser


def browser_ai_transcript_policy(policy: dict[str, Any], default_policy: dict[str, Any]) -> dict[str, Any]:
    transcript = policy.get("browser_ai_transcript") if isinstance(policy.get("browser_ai_transcript"), dict) else {}
    default_transcript = default_policy.get("browser_ai_transcript", {})
    return deep_merge(default_transcript, transcript) if isinstance(default_transcript, dict) else transcript


def typing_atspi_text_events_policy(
    *,
    policy: Mapping[str, Any] | None,
    default_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    policy_data = policy if isinstance(policy, Mapping) else {}
    default_data = default_policy if isinstance(default_policy, Mapping) else {}
    events = policy_data.get("atspi_text_events") if isinstance(policy_data.get("atspi_text_events"), Mapping) else {}
    default_events = (
        default_data.get("atspi_text_events")
        if isinstance(default_data.get("atspi_text_events"), Mapping)
        else {}
    )
    return deep_merge(dict(default_events), dict(events))


def browser_url_scheme_allowed(url: str, browser_policy: dict[str, Any]) -> bool:
    raw = str(url or "").strip().lower()
    if not raw:
        return False
    allowed = [str(item).lower() for item in browser_policy.get("allowed_url_schemes", []) if str(item).strip()]
    if not allowed:
        allowed = ["http:", "https:"]
    return any(raw.startswith(scheme) for scheme in allowed)


def browser_normalized_title(title: str | None) -> str:
    text = " ".join(str(title or "").split()).strip()
    if not text:
        return ""
    suffix_patterns = [
        r"\s+[\u2014-]\s+Mozilla Firefox$",
        r"\s+[\u2014-]\s+Firefox$",
        r"\s+[\u2014-]\s+Исходный файл$",
        r"\s+[\u2014-]\s+Source File$",
        r"\s+[\u2014-]\s+View Source$",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in suffix_patterns:
            cleaned = re.sub(pattern, "", text, flags=re.I).strip()
            if cleaned != text:
                text = cleaned
                changed = True
    return text[:240]


def browser_title_fingerprint(title: str | None) -> dict[str, Any]:
    normalized = browser_normalized_title(title)
    if not normalized:
        return {"title_present": False, "title_stored": False}
    return {
        "title_present": True,
        "title_sha256": hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest(),
        "title_stored": False,
    }


AI_COUNTERPART_RULES = [
    {"entity_id": "ai:openai:chatgpt", "provider": "OpenAI", "product": "ChatGPT", "family": "gpt", "hosts": ["chatgpt.com", "chat.openai.com"], "aliases": ["chatgpt", "gpt"], "surface": "ai_chat"},
    {"entity_id": "ai:google:gemini", "provider": "Google", "product": "Gemini", "family": "gemini", "hosts": ["gemini.google.com", "bard.google.com"], "aliases": ["gemini", "bard"], "surface": "ai_chat"},
    {"entity_id": "ai:google:ai-studio", "provider": "Google", "product": "Google AI Studio", "family": "gemini", "hosts": ["aistudio.google.com"], "aliases": ["ai studio", "google ai studio"], "surface": "ai_tool"},
    {"entity_id": "ai:google:notebooklm", "provider": "Google", "product": "NotebookLM", "family": "notebooklm", "hosts": ["notebooklm.google.com"], "aliases": ["notebooklm"], "surface": "ai_tool"},
    {"entity_id": "ai:anthropic:claude", "provider": "Anthropic", "product": "Claude", "family": "claude", "hosts": ["claude.ai"], "aliases": ["claude"], "surface": "ai_chat"},
    {"entity_id": "ai:perplexity:perplexity", "provider": "Perplexity", "product": "Perplexity", "family": "perplexity", "hosts": ["perplexity.ai"], "aliases": ["perplexity"], "surface": "ai_chat"},
    {"entity_id": "ai:microsoft:copilot", "provider": "Microsoft", "product": "Copilot", "family": "copilot", "hosts": ["copilot.microsoft.com"], "aliases": ["copilot", "bing chat"], "surface": "ai_chat"},
    {"entity_id": "ai:poe:poe", "provider": "Quora", "product": "Poe", "family": "poe", "hosts": ["poe.com"], "aliases": ["poe"], "surface": "ai_router"},
    {"entity_id": "ai:xai:grok", "provider": "xAI", "product": "Grok", "family": "grok", "hosts": ["grok.com"], "aliases": ["grok"], "surface": "ai_chat"},
    {"entity_id": "ai:deepseek:deepseek", "provider": "DeepSeek", "product": "DeepSeek", "family": "deepseek", "hosts": ["chat.deepseek.com", "deepseek.com"], "aliases": ["deepseek"], "surface": "ai_chat"},
    {"entity_id": "ai:mistral:le-chat", "provider": "Mistral AI", "product": "Le Chat", "family": "mistral", "hosts": ["chat.mistral.ai", "lechat.mistral.ai"], "aliases": ["le chat", "mistral"], "surface": "ai_chat"},
    {"entity_id": "ai:alibaba:qwen", "provider": "Alibaba Cloud", "product": "Qwen Chat", "family": "qwen", "hosts": ["chat.qwen.ai", "qwen.ai"], "aliases": ["qwen"], "surface": "ai_chat"},
    {"entity_id": "ai:moonshot:kimi", "provider": "Moonshot AI", "product": "Kimi", "family": "kimi", "hosts": ["kimi.com", "kimi.moonshot.cn"], "aliases": ["kimi"], "surface": "ai_chat"},
    {"entity_id": "ai:huggingface:huggingchat", "provider": "Hugging Face", "product": "HuggingChat", "family": "huggingchat", "hosts": ["huggingface.co"], "path_prefixes": ["/chat"], "aliases": ["huggingchat"], "surface": "ai_chat"},
    {"entity_id": "ai:openrouter:openrouter", "provider": "OpenRouter", "product": "OpenRouter", "family": "openrouter", "hosts": ["openrouter.ai"], "aliases": ["openrouter"], "surface": "ai_router"},
    {"entity_id": "ai:you:you", "provider": "You.com", "product": "You.com AI", "family": "you", "hosts": ["you.com"], "aliases": ["you.com", "you ai"], "surface": "ai_chat"},
    {"entity_id": "ai:phind:phind", "provider": "Phind", "product": "Phind", "family": "phind", "hosts": ["phind.com"], "aliases": ["phind"], "surface": "ai_search"},
    {"entity_id": "ai:characterai:character-ai", "provider": "Character.AI", "product": "Character.AI", "family": "character-ai", "hosts": ["character.ai"], "aliases": ["character.ai"], "surface": "ai_chat"},
    {"entity_id": "ai:meta:meta-ai", "provider": "Meta", "product": "Meta AI", "family": "meta-ai", "hosts": ["meta.ai"], "aliases": ["meta ai"], "surface": "ai_chat"},
]


def url_origin(url: str | None) -> dict[str, str] | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return None
    scheme = str(parsed.scheme or "").lower()
    host = str(parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    port = f":{parsed.port}" if parsed.port else ""
    origin = f"{scheme}://{host}{port}"
    return {
        "origin": origin,
        "scheme": scheme,
        "host": host,
        "id": f"url:{origin}",
    }


def browser_ai_normalized_title(title: str | None) -> str:
    return browser_normalized_title(title)


def browser_ai_title_rule_basis(rule: dict[str, Any], title: str | None) -> str | None:
    normalized = browser_ai_normalized_title(title).lower()
    if not normalized:
        return None
    provider = str(rule.get("provider") or "").strip().lower()
    product = str(rule.get("product") or "").strip().lower()
    markers = [str(item or "").strip().lower() for item in rule.get("title_markers", []) if str(item or "").strip()]
    if provider and product:
        markers.extend([
            f"{provider} {product}",
            f"{product} - {provider}",
            f"{product} | {provider}",
            f"{product} \u2014 {provider}",
        ])
    for marker in markers:
        if marker and marker in normalized:
            return "title_provider_product"
    return None


def browser_ai_counterpart_identity(
    url: str | None,
    title: str | None = None,
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    raw_url = str(url or "")
    raw_title = str(title or "")
    origin = url_origin(raw_url)
    host = str((origin or {}).get("host") or "").lower()
    try:
        path = urllib.parse.urlsplit(raw_url).path.lower()
    except Exception:
        path = ""
    title_low = raw_title.lower()
    for rule in AI_COUNTERPART_RULES:
        rule_hosts = [str(item).lower() for item in rule.get("hosts", []) if str(item).strip()]
        host_match = any(host == item or host.endswith(f".{item}") for item in rule_hosts)
        path_prefixes = [str(item).lower() for item in rule.get("path_prefixes", []) if str(item).strip()]
        path_match = not path_prefixes or any(path.startswith(prefix) for prefix in path_prefixes)
        alias_match = any(str(alias).lower() in title_low for alias in rule.get("aliases", []) if str(alias).strip())
        if not ((host_match and path_match) or (host_match and alias_match)):
            continue
        basis = "host_path" if host_match and path_prefixes else ("host_title" if alias_match else "host")
        return {
            "schema": f"{schema_prefix}_browser_ai_counterpart_identity_v1",
            "is_ai": True,
            "kind": "ai_counterpart",
            "entity_id": rule.get("entity_id"),
            "label": rule.get("product") or rule.get("provider") or "AI",
            "provider": rule.get("provider"),
            "product": rule.get("product"),
            "family": rule.get("family"),
            "surface": rule.get("surface") or "ai_chat",
            "origin": origin.get("origin") if origin else None,
            "host": host or None,
            "confidence": basis,
            "basis": basis,
            "stores_extra_text": False,
        }
    if not origin:
        for rule in AI_COUNTERPART_RULES:
            basis = browser_ai_title_rule_basis(rule, raw_title)
            if not basis:
                continue
            return {
                "schema": f"{schema_prefix}_browser_ai_counterpart_identity_v1",
                "is_ai": True,
                "kind": "ai_counterpart",
                "entity_id": rule.get("entity_id"),
                "label": rule.get("product") or rule.get("provider") or "AI",
                "provider": rule.get("provider"),
                "product": rule.get("product"),
                "family": rule.get("family"),
                "surface": rule.get("surface") or "ai_chat",
                "origin": None,
                "host": None,
                "confidence": basis,
                "basis": basis,
                "title_only": True,
                "title_stored": False,
                "stores_extra_text": False,
            }
    return {
        "schema": f"{schema_prefix}_browser_ai_counterpart_identity_v1",
        "is_ai": False,
        "kind": "web_page",
        "entity_id": None,
        "label": host or None,
        "provider": None,
        "product": None,
        "family": None,
        "surface": "web_page",
        "origin": origin.get("origin") if origin else None,
        "host": host or None,
        "confidence": "no_ai_counterpart_signal",
        "basis": "url_host_title",
        "stores_extra_text": False,
    }


def parse_iso_datetime(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed.astimezone(dt.timezone.utc)


def age_seconds(value: Any, reference_at: Any | None = None) -> float | None:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return None
    reference = parse_iso_datetime(reference_at) or dt.datetime.now(dt.timezone.utc)
    return round(max(0.0, (reference - parsed).total_seconds()), 1)


def atspi_paths_match(source_path: str | None, document_path: str | None, capture_path: str | None) -> bool:
    capture = str(capture_path or "").strip(".")
    if not capture:
        return False
    candidates = [str(source_path or "").strip("."), str(document_path or "").strip(".")]
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == capture:
            return True
        if candidate.startswith(capture + "."):
            return True
        if candidate.endswith("." + capture):
            return True
    return False


def browser_content_record_url(record: Mapping[str, Any]) -> str:
    url_payload = record.get("url") if isinstance(record.get("url"), Mapping) else {}
    return str(url_payload.get("url") or "")


def browser_context_max_age_sec(events_policy: Mapping[str, Any] | None = None) -> int:
    raw_value = (events_policy or {}).get("browser_context_inference_max_age_sec")
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = 900
    return max(30, min(value, 3600))


def browser_context_safe_candidate(
    item: Mapping[str, Any],
    latest: Mapping[str, Any],
    *,
    captured_at: Any = None,
    source_path: str | None = None,
    document_path: str | None = None,
    capture_path: str | None = None,
    age_sec: float | None = None,
    basis: str,
    reference_at: Any | None = None,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any] | None:
    record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
    url = browser_content_record_url(record)
    origin = url_origin(url)
    if not origin:
        return None
    web_quality = record.get("web_context_quality") if isinstance(record.get("web_context_quality"), Mapping) else {}
    content_quality = record.get("content_quality") if isinstance(record.get("content_quality"), Mapping) else {}
    page_identity = record.get("page_identity") if isinstance(record.get("page_identity"), Mapping) else browser_ai_counterpart_identity(
        url,
        str(record.get("title") or ""),
        schema_prefix=schema_prefix,
    )
    if record.get("skipped_text") is True or web_quality.get("sensitive_skip_preserved") is True:
        return None
    if str(web_quality.get("class") or "") in {"login_sensitive", "browser_internal"}:
        return None
    if str(content_quality.get("classification") or "") in {"skipped", "noise"}:
        return None
    captured = captured_at or record.get("captured_at") or item.get("generated_at") or latest.get("generated_at")
    candidate_age = age_sec if isinstance(age_sec, (int, float)) else age_seconds(captured, reference_at)
    return {
        "ok": True,
        "status": "matched" if basis == "recent_nervous_browser_content_atspi_path" else "fallback_matched",
        "url": url,
        "title": record.get("title"),
        "content_type": record.get("content_type"),
        "captured_at": captured,
        "age_sec": candidate_age,
        "capture_path": capture_path,
        "source_path": source_path,
        "document_path": document_path,
        "context_id": item.get("context") or record.get("context_id"),
        "web_context_class": web_quality.get("class"),
        "content_quality_class": content_quality.get("classification"),
        "page_identity": page_identity if page_identity.get("is_ai") is True else None,
        "query_present": nested_get(record, ["url", "query_present"]),
        "fragment_present": nested_get(record, ["url", "fragment_present"]),
        "raw_url_omitted": nested_get(record, ["url", "raw_omitted"]),
        "basis": basis,
        "attention": web_quality.get("attention") if isinstance(web_quality.get("attention"), Mapping) else {},
    }


def browser_context_from_recent_captures(
    latest: Mapping[str, Any],
    source_path: str | None,
    document_path: str | None,
    *,
    max_age_sec: int,
    reference_at: Any | None = None,
    allow_attention_fallback: bool = False,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    captures = latest.get("captures") if isinstance(latest.get("captures"), list) else []
    candidates: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    for item in captures:
        if not isinstance(item, Mapping):
            continue
        record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
        atspi = item.get("atspi") if isinstance(item.get("atspi"), Mapping) else {}
        if not atspi and isinstance(record.get("atspi_context"), Mapping):
            atspi = record["atspi_context"]
        capture_path = str(atspi.get("path") or "")
        if not atspi_paths_match(source_path, document_path, capture_path):
            continue
        captured_at = record.get("captured_at") or item.get("generated_at") or latest.get("generated_at")
        item_age_sec = age_seconds(captured_at, reference_at)
        if not isinstance(item_age_sec, (int, float)) or item_age_sec > max_age_sec:
            continue
        candidate = browser_context_safe_candidate(
            item,
            latest,
            captured_at=captured_at,
            source_path=source_path,
            document_path=document_path,
            capture_path=capture_path,
            age_sec=item_age_sec,
            basis="recent_nervous_browser_content_atspi_path",
            reference_at=reference_at,
            schema_prefix=schema_prefix,
        )
        if candidate:
            candidates.append(candidate)
    if not candidates and allow_attention_fallback:
        for item in captures:
            if not isinstance(item, Mapping):
                continue
            record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
            captured_at = record.get("captured_at") or item.get("generated_at") or latest.get("generated_at")
            item_age_sec = age_seconds(captured_at, reference_at)
            if not isinstance(item_age_sec, (int, float)) or item_age_sec > max_age_sec:
                continue
            atspi = item.get("atspi") if isinstance(item.get("atspi"), Mapping) else {}
            web_quality = record.get("web_context_quality") if isinstance(record.get("web_context_quality"), Mapping) else {}
            attention = web_quality.get("attention") if isinstance(web_quality.get("attention"), Mapping) else {}
            focused_or_showing = bool(atspi.get("focused") or atspi.get("showing") or attention.get("focused") or attention.get("showing"))
            usable = str(nested_get(record, ["content_quality", "classification"]) or "") == "usable"
            if not focused_or_showing and not usable:
                continue
            capture_path = str(atspi.get("path") or "")
            candidate = browser_context_safe_candidate(
                item,
                latest,
                captured_at=captured_at,
                source_path=source_path,
                document_path=document_path,
                capture_path=capture_path,
                age_sec=item_age_sec,
                basis="recent_nervous_browser_content_attention_fallback",
                reference_at=reference_at,
                schema_prefix=schema_prefix,
            )
            if not candidate:
                continue
            candidate["attention_fallback"] = {
                "focused_or_showing": focused_or_showing,
                "usable": usable,
            }
            fallback_candidates.append(candidate)
        high_confidence = [
            item
            for item in fallback_candidates
            if nested_get(item, ["attention_fallback", "focused_or_showing"]) is True
        ]
        fallback_pool = high_confidence if high_confidence else fallback_candidates
        if len(fallback_pool) == 1:
            candidates.append(fallback_pool[0])
    if not candidates:
        return {
            "ok": False,
            "status": "no_safe_recent_match",
            "source_path": source_path,
            "document_path": document_path,
            "max_age_sec": max_age_sec,
            "latest_generated_at": latest.get("generated_at"),
            "attention_fallback_enabled": allow_attention_fallback,
            "attention_fallback_candidates": len(fallback_candidates),
            "attention_fallback_status": "ambiguous_or_absent" if allow_attention_fallback else "disabled",
        }
    candidates.sort(
        key=lambda item: (
            1 if str(item.get("content_quality_class") or "") == "usable" else 0,
            len(str(item.get("capture_path") or "")),
            -float(item.get("age_sec") or 0),
        ),
        reverse=True,
    )
    best = candidates[0]
    best["candidate_count"] = len(candidates)
    best["max_age_sec"] = max_age_sec
    return best


def focused_browser_event_summary(event: Any) -> dict[str, Any] | None:
    if not isinstance(event, Mapping):
        return None
    return {
        "event_id": event.get("event_id"),
        "generated_at": event.get("generated_at"),
        "status": event.get("status"),
        "source_adapter": event.get("source_adapter"),
        "capture_gate_decision": nested_get(event, ["capture_gate", "decision"]),
        "capture_gate_confidence": nested_get(event, ["capture_gate", "confidence"]),
        "text_length": nested_get(event, ["text", "text_length"]),
        "text_chars_stored": nested_get(event, ["text", "text_chars_stored"]),
        "text_sha256": nested_get(event, ["text", "text_sha256"]),
        "app": nested_get(event, ["context", "app", "text"]),
        "window_title": nested_get(event, ["context", "window_title", "text"]),
        "url": nested_get(event, ["context", "url", "text"]),
        "safe_route": nested_get(event, ["metadata", "atspi", "safe_route"]),
        "browser_safe_url": nested_get(event, ["metadata", "atspi", "browser_safe_url"]),
        "recipient_kind": nested_get(event, ["causal_context", "recipient", "kind"]),
        "task_binding": nested_get(event, ["causal_context", "task", "binding"]),
    }


def focused_browser_candidate_summary(candidate: Any, expected_sha: str | None = None) -> dict[str, Any] | None:
    if not isinstance(candidate, Mapping):
        return None
    text = str(candidate.get("text") or "")
    text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest() if text else None
    return {
        "app": candidate.get("app"),
        "window_title": candidate.get("window_title"),
        "role": candidate.get("role"),
        "url": candidate.get("url"),
        "document_title": candidate.get("document_title"),
        "content_type": candidate.get("content_type"),
        "atspi_path": candidate.get("atspi_path"),
        "document_path": candidate.get("document_path"),
        "text_role": candidate.get("text_role"),
        "text_read_allowed": candidate.get("text_read_allowed"),
        "text_length": candidate.get("text_length"),
        "text_sha256": text_sha,
        "expected_text_match": bool(expected_sha and text_sha == expected_sha),
        "capture_gate_decision": candidate.get("capture_gate_decision"),
        "capture_gate_confidence": nested_get(candidate, ["capture_gate", "confidence"]),
        "safe_route": candidate.get("safe_route"),
        "safe_route_allowed": candidate.get("safe_route_allowed"),
        "browser_safe_url": candidate.get("browser_safe_url"),
        "sensitive_context": candidate.get("sensitive_context"),
        "sensitive_state_override": (
            candidate.get("sensitive_state_override")
            if isinstance(candidate.get("sensitive_state_override"), Mapping)
            else None
        ),
        "sensitive_matches": (
            candidate.get("sensitive_matches")
            if isinstance(candidate.get("sensitive_matches"), list)
            else []
        ),
    }


def browser_privacy_record_summary(record: Any, probe_text_sha256: str | None = None) -> dict[str, Any] | None:
    if not isinstance(record, Mapping):
        return None
    text_payload = record.get("text") if isinstance(record.get("text"), Mapping) else {}
    atspi_meta = nested_get(record, ["metadata", "atspi"])
    atspi_meta = atspi_meta if isinstance(atspi_meta, Mapping) else {}
    text_sha = text_payload.get("text_sha256")
    return {
        "event_id": record.get("event_id"),
        "generated_at": record.get("generated_at"),
        "status": record.get("status"),
        "source_adapter": record.get("source_adapter"),
        "capture_gate_decision": nested_get(record, ["capture_gate", "decision"]),
        "capture_gate_confidence": nested_get(record, ["capture_gate", "confidence"]),
        "metadata_only_reason": text_payload.get("metadata_only_reason"),
        "text_length": text_payload.get("text_length"),
        "text_chars_stored": text_payload.get("text_chars_stored"),
        "text_sha256": text_sha,
        "text_value_present": text_payload.get("text") is not None,
        "text_sha256_matches_probe": bool(probe_text_sha256 and text_sha == probe_text_sha256),
        "app": nested_get(record, ["context", "app", "text"]),
        "window_title": nested_get(record, ["context", "window_title", "text"]),
        "url": nested_get(record, ["context", "url", "text"]),
        "recipient_kind": nested_get(record, ["causal_context", "recipient", "kind"]),
        "task_binding": nested_get(record, ["causal_context", "task", "binding"]),
        "atspi": {
            "role": atspi_meta.get("role"),
            "name": atspi_meta.get("name"),
            "source_path": atspi_meta.get("source_path"),
            "document_path": atspi_meta.get("document_path"),
            "content_type": atspi_meta.get("content_type"),
            "gate_decision": atspi_meta.get("gate_decision"),
            "text_read": atspi_meta.get("text_read"),
            "safe_route": atspi_meta.get("safe_route"),
            "browser_safe_url": atspi_meta.get("browser_safe_url"),
        },
    }


def codex_record_is_selftest(record: Any) -> bool:
    if not isinstance(record, Mapping):
        return False
    codex_meta = nested_get(record, ["metadata", "codex"])
    codex_meta = codex_meta if isinstance(codex_meta, Mapping) else {}
    session_id = str(codex_meta.get("session_id") or record.get("session_id") or "")
    turn_id = str(codex_meta.get("turn_id") or record.get("turn_id") or "")
    model = str(codex_meta.get("model") or "")
    permission_mode = str(codex_meta.get("permission_mode") or "")
    context_text = str(
        nested_get(record, ["context", "context", "text"])
        or nested_get(record, ["causal_context", "where", "context"])
        or ""
    )
    return (
        session_id == "codex-hook-selftest"
        or turn_id == "codex-hook-selftest-turn"
        or model == "selftest"
        or permission_mode == "selftest"
        or "codex-hook-selftest" in context_text
    )


def codex_prompt_event_summary(record: Any, reference_at: Any | None = None) -> dict[str, Any] | None:
    if not isinstance(record, Mapping):
        return None
    codex_meta = nested_get(record, ["metadata", "codex"])
    codex_meta = codex_meta if isinstance(codex_meta, Mapping) else {}
    text_payload = record.get("text") if isinstance(record.get("text"), Mapping) else {}
    raw_timestamp = codex_meta.get("raw_timestamp")
    prompt_at = raw_timestamp or record.get("generated_at")
    return {
        "event_id": record.get("event_id"),
        "generated_at": record.get("generated_at"),
        "observed_at": record.get("generated_at"),
        "raw_timestamp": raw_timestamp,
        "prompt_at": prompt_at,
        "prompt_age_sec": age_seconds(prompt_at, reference_at),
        "status": record.get("status"),
        "capture_gate_decision": nested_get(record, ["capture_gate", "decision"]),
        "session_id": codex_meta.get("session_id") or record.get("session_id"),
        "turn_id": codex_meta.get("turn_id") or record.get("turn_id"),
        "cwd": nested_get(record, ["metadata", "file", "path"]),
        "text_length": text_payload.get("text_length"),
        "text_chars_stored": text_payload.get("text_chars_stored"),
        "selftest": codex_record_is_selftest(record),
    }


def codex_prompt_time(record: Any) -> dt.datetime | None:
    if not isinstance(record, Mapping):
        return None
    codex_meta = nested_get(record, ["metadata", "codex"])
    codex_meta = codex_meta if isinstance(codex_meta, Mapping) else {}
    raw_timestamp = codex_meta.get("raw_timestamp")
    return parse_iso_datetime(raw_timestamp) or parse_iso_datetime(record.get("generated_at"))


def codex_recent_prompt_summary(records: list[dict[str, Any]], reference_at: Any | None = None) -> dict[str, Any]:
    codex_records = [
        record
        for record in records
        if isinstance(record, Mapping) and record.get("source_adapter") == "codex_user_prompt_submit"
    ]
    selftest_records = [record for record in codex_records if codex_record_is_selftest(record)]
    live_records = [record for record in codex_records if not codex_record_is_selftest(record)]
    latest_live = max(live_records, key=lambda item: str(item.get("generated_at") or "")) if live_records else None
    latest_selftest = max(selftest_records, key=lambda item: str(item.get("generated_at") or "")) if selftest_records else None
    return {
        "recent_records": len(codex_records),
        "live_prompt_records": len(live_records),
        "selftest_records": len(selftest_records),
        "live_prompt_observed": bool(live_records),
        "selftest_only": bool(codex_records and not live_records),
        "latest_live_prompt": codex_prompt_event_summary(latest_live, reference_at),
        "latest_selftest_prompt": codex_prompt_event_summary(latest_selftest, reference_at),
    }


def codex_session_tail_recent_prompt_summary(
    records: list[dict[str, Any]],
    reference_at: Any | None = None,
    raw_recent_max_age_sec: int = 21600,
) -> dict[str, Any]:
    tail_records = [
        record
        for record in records
        if isinstance(record, Mapping) and record.get("source_adapter") == "codex_session_jsonl_prompt_tail"
    ]
    fresh_tail_records = [
        record
        for record in tail_records
        if (
            age_seconds(
                nested_get(record, ["metadata", "codex", "raw_timestamp"]) or record.get("generated_at"),
                reference_at,
            )
            or 10**9
        )
        <= raw_recent_max_age_sec
    ]
    latest_pool = fresh_tail_records if fresh_tail_records else tail_records
    latest_tail = (
        max(latest_pool, key=lambda item: codex_prompt_time(item) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
        if latest_pool
        else None
    )
    return {
        "recent_records": len(tail_records),
        "live_prompt_records": len(fresh_tail_records),
        "backfilled_or_stale_records": max(0, len(tail_records) - len(fresh_tail_records)),
        "raw_recent_max_age_sec": raw_recent_max_age_sec,
        "live_prompt_observed": bool(fresh_tail_records),
        "latest_live_prompt": codex_prompt_event_summary(latest_tail, reference_at),
    }


def codex_prompt_submit_coverage(
    *,
    codex_prompt_summary: Mapping[str, Any] | None,
    codex_session_tail_summary: Mapping[str, Any] | None,
    codex_selftest_ok: bool,
    codex_session_tail_latest: Mapping[str, Any] | None = None,
    native_recent_records_default: int = 0,
    fallback_recent_records_default: int = 0,
) -> dict[str, Any]:
    prompt_summary = codex_prompt_summary if isinstance(codex_prompt_summary, Mapping) else {}
    tail_summary = codex_session_tail_summary if isinstance(codex_session_tail_summary, Mapping) else {}
    tail_latest = codex_session_tail_latest if isinstance(codex_session_tail_latest, Mapping) else {}
    native_live_observed = bool(prompt_summary.get("live_prompt_observed"))
    tail_live_observed = bool(tail_summary.get("live_prompt_observed"))
    native_recent_records = _safe_int(prompt_summary.get("recent_records"), native_recent_records_default)
    tail_recent_records = _safe_int(tail_summary.get("recent_records"), fallback_recent_records_default)
    return {
        "covered": native_live_observed and bool(codex_selftest_ok),
        "effective_covered": bool((native_live_observed and bool(codex_selftest_ok)) or tail_live_observed),
        "recent_records": native_recent_records,
        "live_prompt_records": prompt_summary.get("live_prompt_records"),
        "selftest_records": prompt_summary.get("selftest_records"),
        "live_prompt_observed": native_live_observed,
        "selftest_only": bool(prompt_summary.get("selftest_only")),
        "selftest_ok": bool(codex_selftest_ok),
        "latest_live_prompt": prompt_summary.get("latest_live_prompt"),
        "latest_selftest_prompt": prompt_summary.get("latest_selftest_prompt"),
        "fallback_adapter": "codex_session_jsonl_prompt_tail",
        "fallback_observed": tail_live_observed,
        "fallback_recent_records": tail_recent_records,
        "fallback_latest_prompt": tail_summary.get("latest_live_prompt"),
        "fallback_latest_status": tail_latest.get("status"),
    }


def codex_prompt_submit_route_assessment(
    *,
    configured_adapters: list[str],
    by_adapter: Mapping[str, int],
    codex_prompt_summary: Mapping[str, Any] | None,
    codex_session_tail_summary: Mapping[str, Any] | None,
    codex_selftest_ok: bool,
    codex_hook_selftest_error: str | None,
    codex_session_tail_latest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = codex_prompt_submit_coverage(
        codex_prompt_summary=codex_prompt_summary,
        codex_session_tail_summary=codex_session_tail_summary,
        codex_selftest_ok=codex_selftest_ok,
        codex_session_tail_latest=codex_session_tail_latest,
        native_recent_records_default=_safe_int(by_adapter.get("codex_user_prompt_submit"), 0),
        fallback_recent_records_default=_safe_int(by_adapter.get("codex_session_jsonl_prompt_tail"), 0),
    )
    adapter_set = set(configured_adapters)
    native_live_observed = bool(coverage.get("live_prompt_observed"))
    tail_live_observed = bool(coverage.get("fallback_observed"))
    tail_latest = codex_session_tail_latest if isinstance(codex_session_tail_latest, Mapping) else {}
    route_notes: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    if tail_live_observed and not native_live_observed:
        route_notes.append({
            "key": "codex_native_hook_not_observed_using_session_tail",
            "level": "info",
            "message": "native Codex UserPromptSubmit has no non-selftest prompt in the recent window; Codex input is covered by raw JSONL near-live tail fallback",
            "native_selftest_ok": bool(codex_selftest_ok),
            "fallback_recent_records": coverage.get("fallback_recent_records"),
            "fallback_latest_prompt": coverage.get("fallback_latest_prompt"),
            "fallback_latest_status": tail_latest.get("status"),
        })
    if (
        "codex_user_prompt_submit" in adapter_set
        and "codex_user_prompt_submit" not in by_adapter
        and not native_live_observed
    ):
        gaps.append({
            "key": "codex_user_prompt_submit_not_observed_recently",
            "level": "info" if codex_selftest_ok else "watch",
            "message": "Codex UserPromptSubmit adapter has not produced recent event records",
            "latest_selftest_ok": bool(codex_selftest_ok),
            "latest_selftest_error": codex_hook_selftest_error,
        })
    elif "codex_user_prompt_submit" in adapter_set and not native_live_observed and not tail_live_observed:
        gaps.append({
            "key": "codex_user_prompt_submit_selftest_only",
            "level": "watch",
            "message": "recent Codex UserPromptSubmit evidence is selftest-only; no non-selftest Codex prompt was observed in the coverage window",
            "recent_records": _safe_int(by_adapter.get("codex_user_prompt_submit"), 0),
            "selftest_records": coverage.get("selftest_records"),
            "latest_selftest_prompt": coverage.get("latest_selftest_prompt"),
            "latest_selftest_error": codex_hook_selftest_error,
        })
    return {
        "coverage": coverage,
        "route_notes": route_notes,
        "gaps": gaps,
    }


def typing_coverage_status_decision(
    *,
    record_count: int,
    coverage_routes: Mapping[str, Any],
    gaps: list[dict[str, Any]],
    observed_adapters: list[str],
    dominant_adapter: str | None,
    dominant_ratio: float,
    live_input_count: int,
    browser_release_gap: bool,
    browser_temporary_proof_ok: bool,
    browser_atspi_fallback_ok: bool,
) -> dict[str, Any]:
    route_coverage_count = sum(
        1 for item in coverage_routes.values() if isinstance(item, Mapping) and item.get("covered") is True
    )
    route_effective_coverage_count = sum(
        1
        for item in coverage_routes.values()
        if isinstance(item, Mapping) and (item.get("covered") is True or item.get("effective_covered") is True)
    )
    route_coverage_total = len(coverage_routes)
    watch_gaps = any(isinstance(item, Mapping) and item.get("level") == "watch" for item in gaps)
    browser_release_fallback_ok = bool(browser_release_gap and browser_temporary_proof_ok and browser_atspi_fallback_ok)
    if record_count == 0:
        status = "empty"
    elif route_coverage_count == route_coverage_total and not watch_gaps:
        status = "covered"
    elif route_effective_coverage_count >= max(1, route_coverage_total - 1) and not watch_gaps:
        status = "covered_with_fallbacks"
    elif browser_release_fallback_ok and route_coverage_count >= max(1, route_coverage_total - 1) and not watch_gaps:
        status = "covered_with_fallbacks"
    elif route_coverage_count >= max(1, route_coverage_total - 1) and browser_atspi_fallback_ok:
        status = "covered_with_fallbacks"
    elif (dominant_adapter != "saved_text_snapshot" and dominant_ratio >= 0.8) or (
        len(observed_adapters) <= 1 and live_input_count == 0
    ):
        status = "narrow"
    elif route_coverage_count >= 3:
        status = "broad_partial"
    else:
        status = "manual_only"
    return {
        "status": status,
        "coverage_routes": route_coverage_count,
        "effective_coverage_routes": route_effective_coverage_count,
        "coverage_route_total": route_coverage_total,
        "watch_gaps": watch_gaps,
        "browser_release_fallback_ok": browser_release_fallback_ok,
    }


def _age_recent(value: Any, max_age_sec: int) -> bool:
    return isinstance(value, (int, float)) and value <= max_age_sec


def _proof_time(value: Mapping[str, Any]) -> dt.datetime:
    return parse_iso_datetime(value.get("generated_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def _browser_input_proof_candidate(
    route: str,
    latest: Mapping[str, Any],
    *,
    reference_at: Any | None = None,
    profile_kind: Any = None,
) -> dict[str, Any]:
    proof_at = nested_get(latest, ["event", "generated_at"]) or latest.get("generated_at")
    candidate = {
        "route": route,
        "generated_at": proof_at,
        "age_sec": age_seconds(proof_at, reference_at),
        "status": latest.get("status"),
    }
    if profile_kind is not None:
        candidate["profile_kind"] = profile_kind
    return candidate


def typing_browser_input_proof_summary(
    *,
    browser_webextension_selftest_latest: Mapping[str, Any] | None,
    browser_atspi_selftest_latest: Mapping[str, Any] | None,
    browser_atspi_release_selftest_latest: Mapping[str, Any] | None,
    reference_at: Any | None = None,
) -> dict[str, Any]:
    webextension_latest = browser_webextension_selftest_latest if isinstance(browser_webextension_selftest_latest, Mapping) else {}
    atspi_latest = browser_atspi_selftest_latest if isinstance(browser_atspi_selftest_latest, Mapping) else {}
    release_latest = browser_atspi_release_selftest_latest if isinstance(browser_atspi_release_selftest_latest, Mapping) else {}
    temporary_profile_selftest_ok = bool(webextension_latest.get("ok") is True)
    atspi_selftest_ok = bool(atspi_latest.get("ok") is True)
    release_profile_kind = nested_get(release_latest, ["firefox", "profile_kind"])
    atspi_release_selftest_ok = bool(
        release_latest.get("ok") is True
        and release_profile_kind == "release_profile"
        and nested_get(release_latest, ["policy", "release_profile_mutated"]) is True
    )

    proof_routes: list[dict[str, Any]] = []
    if temporary_profile_selftest_ok:
        proof_routes.append(
            _browser_input_proof_candidate(
                "browser_webextension_selftest",
                webextension_latest,
                reference_at=reference_at,
            )
        )
    if atspi_selftest_ok:
        proof_routes.append(
            _browser_input_proof_candidate(
                "browser_atspi_selftest",
                atspi_latest,
                reference_at=reference_at,
            )
        )
    if atspi_release_selftest_ok:
        proof_routes.append(
            _browser_input_proof_candidate(
                "browser_atspi_release_selftest",
                release_latest,
                reference_at=reference_at,
                profile_kind=release_profile_kind,
            )
        )
    proof_routes.sort(key=_proof_time, reverse=True)

    return {
        "temporary_profile_selftest_ok": temporary_profile_selftest_ok,
        "atspi_selftest_ok": atspi_selftest_ok,
        "atspi_release_selftest_ok": atspi_release_selftest_ok,
        "proof_routes": proof_routes,
        "latest_proof": proof_routes[0] if proof_routes else None,
    }


def typing_browser_webextension_selftest_validation_status(
    latest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    event = latest_data.get("event") if isinstance(latest_data.get("event"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "event_source_adapter": event.get("source_adapter") == "browser_extension_explicit",
        "event_status_captured": event.get("status") == "captured",
        "event_capture_gate": event.get("capture_gate_decision") == "allow_text",
        "event_capture_confidence": event.get("capture_gate_confidence") == "browser_url_and_field_allowed",
        "event_text_stored": event.get("text_length") == event.get("text_chars_stored"),
        "recipient_kind": nested_get(event, ["recipient", "kind"]) == "browser_extension",
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
        "policy_temporary_firefox_profile": policy.get("temporary_firefox_profile") is True,
        "policy_release_profile_not_mutated": policy.get("release_profile_mutated") is False,
    }
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "checks": checks,
    }


def typing_browser_atspi_selftest_validation_status(
    latest: Mapping[str, Any] | None,
    *,
    release_profile: bool = False,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    event = latest_data.get("event") if isinstance(latest_data.get("event"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "event_source_adapter": event.get("source_adapter") == "atspi_text_changed_event",
        "event_status_captured": event.get("status") == "captured",
        "event_capture_gate": event.get("capture_gate_decision") == "allow_text",
        "event_capture_confidence": event.get("capture_gate_confidence") == "atspi_browser_url_allowed",
        "event_browser_app": event.get("browser_app") is True,
        "event_url_allowed": event.get("url_allowed") is True,
        "event_text_stored": event.get("text_length") == event.get("text_chars_stored"),
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
    }
    if release_profile:
        checks["firefox_release_profile"] = nested_get(latest_data, ["firefox", "profile_kind"]) == "release_profile"
        checks["policy_release_profile_mutated"] = policy.get("release_profile_mutated") is True
    else:
        checks["policy_internet_access_disabled"] = policy.get("internet_access") is False
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "release_profile": release_profile,
        "checks": checks,
    }


def typing_generic_gui_selftest_validation_status(
    latest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    event = latest_data.get("event") if isinstance(latest_data.get("event"), Mapping) else {}
    sensitive = latest_data.get("sensitive_probe") if isinstance(latest_data.get("sensitive_probe"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "event_source_adapter": event.get("source_adapter") == "atspi_text_changed_event",
        "event_status_captured": event.get("status") == "captured",
        "event_capture_gate": event.get("capture_gate_decision") == "allow_text",
        "event_capture_confidence": event.get("capture_gate_confidence") == "atspi_generic_editable_text_allowed",
        "event_text_stored": event.get("text_length") == event.get("text_chars_stored"),
        "recipient_kind": nested_get(event, ["recipient", "kind"]) == "focused_application",
        "sensitive_status_metadata_only": sensitive.get("status") == "metadata_only",
        "sensitive_capture_gate_metadata_only": sensitive.get("capture_gate_decision") == "metadata_only",
        "sensitive_text_omitted": _safe_int(sensitive.get("text_chars_stored"), 0) == 0,
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
        "policy_network_access_disabled": policy.get("network_access") is False,
    }
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "checks": checks,
    }


def typing_focused_browser_selftest_validation_status(
    latest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    event = latest_data.get("event") if isinstance(latest_data.get("event"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "event_source_adapter": event.get("source_adapter") == "atspi_focused_text_snapshot",
        "event_status_captured": event.get("status") == "captured",
        "event_capture_gate": event.get("capture_gate_decision") == "allow_text",
        "event_capture_confidence": event.get("capture_gate_confidence") == "focused_browser_safe_url_allowed",
        "event_safe_route": event.get("safe_route") == "browser_safe_url",
        "event_browser_safe_url": event.get("browser_safe_url") is True,
        "event_text_stored": event.get("text_length") == event.get("text_chars_stored"),
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
        "policy_temporary_firefox_profile": policy.get("temporary_firefox_profile") is True,
        "policy_release_profile_not_mutated": policy.get("release_profile_mutated") is False,
    }
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "checks": checks,
    }


def typing_browser_privacy_selftest_validation_status(
    latest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    checks_data = latest_data.get("checks") if isinstance(latest_data.get("checks"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    atspi_event = (
        latest_data.get("atspi_text_event")
        if isinstance(latest_data.get("atspi_text_event"), Mapping)
        else {}
    )
    focused_event = (
        latest_data.get("focused_event")
        if isinstance(latest_data.get("focused_event"), Mapping)
        else {}
    )
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "atspi_metadata_only_before_text_read": checks_data.get("atspi_metadata_only_before_text_read") is True,
        "focused_candidate_no_text_read": checks_data.get("focused_candidate_no_text_read") is True,
        "focused_metadata_only_before_text_read": checks_data.get("focused_metadata_only_before_text_read") is True,
        "probe_text_sha256_absent_from_recent_events": checks_data.get("probe_text_sha256_absent_from_recent_events") is True,
        "atspi_text_omitted": atspi_event.get("text_chars_stored") == 0,
        "focused_text_omitted": focused_event.get("text_chars_stored") == 0,
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
        "policy_login_url_text_not_persisted": policy.get("login_url_text_persisted") is False,
    }
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "checks": checks,
    }


def typing_browser_context_fallback_status(
    *,
    browser_context_inference: Mapping[str, Any] | None,
    browser_context_selftest_latest: Mapping[str, Any] | None,
    browser_atspi_selftest_ok: bool,
    browser_atspi_release_selftest_ok: bool,
) -> dict[str, Any]:
    inference = browser_context_inference if isinstance(browser_context_inference, Mapping) else {}
    selftest = browser_context_selftest_latest if isinstance(browser_context_selftest_latest, Mapping) else {}
    selftest_policy = selftest.get("policy") if isinstance(selftest.get("policy"), Mapping) else {}
    context_selftest_ok = bool(
        selftest.get("ok") is True
        and selftest.get("status") == "passed"
        and selftest_policy.get("raw_keylogging") is False
        and selftest_policy.get("password_fields_captured") is False
        and selftest_policy.get("form_values_captured") is False
        and selftest_policy.get("uses_browser_content_capture") is True
        and selftest_policy.get("uses_atspi_document_path_inference") is True
    )
    inference_passed = bool(inference.get("ok") is True and inference.get("status") == "passed")
    effective_ok = bool(inference_passed or context_selftest_ok)
    if inference_passed:
        effective_status = "passed"
    elif context_selftest_ok:
        effective_status = "passed_via_browser_context_selftest"
    else:
        effective_status = inference.get("status")
    atspi_fallback_ok = bool((browser_atspi_selftest_ok or browser_atspi_release_selftest_ok) and effective_ok)
    return {
        "context_selftest_ok": context_selftest_ok,
        "context_inference_passed": inference_passed,
        "context_inference_effective_ok": effective_ok,
        "context_inference_effective_status": effective_status,
        "context_inference_raw_status": inference.get("status"),
        "atspi_fallback_ok": atspi_fallback_ok,
    }


def typing_browser_ai_transcript_selftest_status(
    latest: Mapping[str, Any] | None,
    *,
    expected_recipient_id: str = "ai:google:gemini",
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    safe_event = latest_data.get("safe") if isinstance(latest_data.get("safe"), Mapping) else {}
    selftest_ok = bool(
        latest_data.get("ok") is True
        and latest_data.get("status") == "passed"
        and safe_event.get("source_adapter") == "browser_ai_transcript"
        and safe_event.get("capture_gate_decision") == "allow_text"
        and nested_get(safe_event, ["recipient", "id"]) == expected_recipient_id
    )
    return {
        "selftest_ok": selftest_ok,
        "status": latest_data.get("status"),
        "expected_recipient_id": expected_recipient_id,
        "safe_event": {
            "source_adapter": safe_event.get("source_adapter"),
            "capture_gate_decision": safe_event.get("capture_gate_decision"),
            "recipient_id": nested_get(safe_event, ["recipient", "id"]),
        },
    }


def typing_browser_ai_transcript_selftest_validation_status(
    latest: Mapping[str, Any] | None,
    *,
    expected_recipient_id: str = "ai:google:gemini",
) -> dict[str, Any]:
    latest_data = latest if isinstance(latest, Mapping) else {}
    safe_event = latest_data.get("safe") if isinstance(latest_data.get("safe"), Mapping) else {}
    sensitive_event = latest_data.get("sensitive") if isinstance(latest_data.get("sensitive"), Mapping) else {}
    policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    checks = {
        "document_passed": latest_data.get("ok") is True and latest_data.get("status") == "passed",
        "safe_source_adapter": safe_event.get("source_adapter") == "browser_ai_transcript",
        "safe_status_captured": safe_event.get("status") == "captured",
        "safe_capture_gate": safe_event.get("capture_gate_decision") == "allow_text",
        "safe_capture_confidence": safe_event.get("capture_gate_confidence") == "browser_ai_transcript_known_ai_page_allowed",
        "safe_recipient_kind": nested_get(safe_event, ["recipient", "kind"]) == "ai_counterpart",
        "safe_recipient_id": nested_get(safe_event, ["recipient", "id"]) == expected_recipient_id,
        "safe_message_role": safe_event.get("message_role") == "assistant",
        "sensitive_metadata_only": sensitive_event.get("capture_gate_decision") == "metadata_only",
        "sensitive_text_omitted": _safe_int(sensitive_event.get("text_chars_stored"), 0) == 0,
        "policy_raw_keylogging_disabled": policy.get("raw_keylogging") is False,
        "policy_password_fields_not_captured": policy.get("password_fields_captured") is False,
        "policy_automatic_action_disabled": policy.get("automatic_action") is False,
    }
    return {
        "selftest_ok": all(checks.values()),
        "status": latest_data.get("status"),
        "expected_recipient_id": expected_recipient_id,
        "checks": checks,
    }


def typing_browser_input_recency_status(
    *,
    browser_input_recency: Mapping[str, Any],
    browser_latest_proof: Mapping[str, Any] | None,
    max_age_sec: int,
) -> dict[str, Any]:
    input_data = browser_input_recency if isinstance(browser_input_recency, Mapping) else {}
    latest_any_age = nested_get(input_data, ["latest_any", "age_sec"])
    latest_natural_age = nested_get(input_data, ["latest_natural", "age_sec"])
    latest_natural_text_age = nested_get(input_data, ["latest_natural_text", "age_sec"])
    latest_controlled_text_age = nested_get(input_data, ["latest_controlled_text", "age_sec"])

    natural_recent = _age_recent(latest_natural_age, max_age_sec)
    natural_text_recent = _age_recent(latest_natural_text_age, max_age_sec)
    controlled_text_recent = _age_recent(latest_controlled_text_age, max_age_sec)
    any_recent = _age_recent(latest_any_age, max_age_sec)
    latest_proof = browser_latest_proof if isinstance(browser_latest_proof, Mapping) else {}
    proof_recent = bool(latest_proof and _age_recent(latest_proof.get("age_sec"), max_age_sec))

    if natural_text_recent:
        effective_status = "live_browser_text_recent"
    elif natural_recent and controlled_text_recent:
        effective_status = "live_browser_metadata_controlled_text_recent"
    elif natural_recent:
        effective_status = "live_browser_metadata_recent"
    elif controlled_text_recent:
        effective_status = "controlled_browser_text_recent"
    elif any_recent:
        effective_status = "controlled_browser_metadata_recent"
    elif proof_recent:
        effective_status = "selftest_proof_recent"
    elif latest_proof:
        effective_status = "browser_proof_stale"
    else:
        effective_status = "browser_evidence_missing"

    return {
        "effective_status": effective_status,
        "max_age_sec": max_age_sec,
        "latest_any_recent": any_recent,
        "latest_natural_recent": natural_recent,
        "latest_natural_text_recent": natural_text_recent,
        "latest_controlled_text_recent": controlled_text_recent,
        "latest_proof_recent": proof_recent,
        "latest_proof_present": bool(latest_proof),
    }


TYPING_BROWSER_INPUT_RECENCY_ACCEPTED_STATUSES = {
    "live_browser_text_recent",
    "live_browser_metadata_controlled_text_recent",
    "live_browser_metadata_recent",
    "controlled_browser_text_recent",
    "controlled_browser_metadata_recent",
    "selftest_proof_recent",
}


def typing_browser_input_recency_validation_status(
    browser_input_recency: Mapping[str, Any] | None,
) -> dict[str, Any]:
    input_data = browser_input_recency if isinstance(browser_input_recency, Mapping) else {}
    effective_status = str(input_data.get("effective_status") or "browser_evidence_missing")
    return {
        "ok": effective_status in TYPING_BROWSER_INPUT_RECENCY_ACCEPTED_STATUSES,
        "effective_status": effective_status,
        "accepted_statuses": sorted(TYPING_BROWSER_INPUT_RECENCY_ACCEPTED_STATUSES),
    }


def typing_atspi_text_events_heartbeat_status(
    atspi_latest: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    latest_data = atspi_latest if isinstance(atspi_latest, Mapping) else {}
    policy_data = policy if isinstance(policy, Mapping) else {}
    heartbeat_age = latest_data.get("heartbeat_age_sec")
    heartbeat_interval = _safe_int(latest_data.get("heartbeat_interval_sec"), _safe_int(policy_data.get("heartbeat_interval_sec"), 60))
    max_age_sec = max(180, heartbeat_interval * 3)
    latest_status = str(latest_data.get("status") or "missing")
    heartbeat_age_numeric = isinstance(heartbeat_age, (int, float))
    ok = bool(
        latest_status in {"running", "running_with_errors", "sample_complete"}
        and heartbeat_age_numeric
        and float(heartbeat_age) <= max_age_sec
    )
    return {
        "ok": ok,
        "status": "fresh" if ok else "stale_or_missing",
        "latest_status": latest_status,
        "heartbeat_age_sec": heartbeat_age if heartbeat_age_numeric else None,
        "heartbeat_interval_sec": heartbeat_interval,
        "max_age_sec": max_age_sec,
        "accepted_latest_statuses": ["running", "running_with_errors", "sample_complete"],
    }


def _typing_atspi_safe_string(value: Any, limit: int = 240) -> str:
    try:
        text = "" if value is None else str(value)
    except Exception:
        return "<unreadable>"
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def typing_atspi_text_events_compact_history_record(
    *,
    data: Mapping[str, Any],
    sample: Mapping[str, Any] | None,
    listener_status: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
    error: str | None = None,
) -> dict[str, Any]:
    data_mapping = data if isinstance(data, Mapping) else {}
    summary = data_mapping.get("summary") if isinstance(data_mapping.get("summary"), Mapping) else {}
    event_index = _safe_int(summary.get("events_seen"), 0)
    if not isinstance(sample, Mapping):
        return {
            "schema": f"{schema_prefix}_typing_atspi_text_event_compact_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "listener_error" if error else listener_status,
            "source_adapter": "atspi_text_changed_event",
            "listener_status": listener_status,
            "event_index": event_index,
            "summary": dict(summary),
            "error": error,
            "policy": {
                "compact_history": True,
                "raw_keylogging": False,
                "password_fields_captured": False,
                "automatic_action": False,
            },
        }

    gate = sample.get("capture_gate") if isinstance(sample.get("capture_gate"), Mapping) else {}
    typing_event = sample.get("typing_event") if isinstance(sample.get("typing_event"), Mapping) else {}
    states = sample.get("states") if isinstance(sample.get("states"), Mapping) else {}
    browser_context_inference = (
        sample.get("browser_context_inference")
        if isinstance(sample.get("browser_context_inference"), Mapping)
        else {}
    )
    return {
        "schema": f"{schema_prefix}_typing_atspi_text_event_compact_v1",
        "version": version,
        "generated_at": sample.get("generated_at") or generated_at,
        "ok": bool(sample.get("ok", True)),
        "status": sample.get("status") or "unknown",
        "source_adapter": sample.get("source_adapter") or "atspi_text_changed_event",
        "listener_status": listener_status,
        "event_index": event_index,
        "event_type": sample.get("event_type"),
        "detail1": sample.get("detail1"),
        "detail2": sample.get("detail2"),
        "any_data_type": sample.get("any_data_type"),
        "app": _typing_atspi_safe_string(sample.get("app"), 120),
        "app_process_id": sample.get("app_process_id"),
        "window_title": _typing_atspi_safe_string(sample.get("window_title"), 240),
        "url": sample.get("url"),
        "document_title": _typing_atspi_safe_string(sample.get("document_title"), 240),
        "content_type": sample.get("content_type"),
        "role": sample.get("role"),
        "name": _typing_atspi_safe_string(sample.get("name"), 160),
        "atspi_path": sample.get("atspi_path"),
        "document_path": sample.get("document_path"),
        "states": {
            key: bool(states.get(key))
            for key in ("editable", "focused", "showing", "visible", "enabled", "sensitive")
        },
        "text_role": bool(sample.get("text_role")),
        "sensitive_context": bool(sample.get("sensitive_context")),
        "capture_gate": {
            "decision": gate.get("decision"),
            "confidence": gate.get("confidence"),
            "matched_policy": gate.get("matched_policy"),
        } if gate else None,
        "typing_event": {
            "event_id": typing_event.get("event_id"),
            "status": typing_event.get("status"),
            "text_length": typing_event.get("text_length"),
            "text_chars_stored": typing_event.get("text_chars_stored"),
            "capture_gate_decision": typing_event.get("capture_gate_decision"),
            "duplicate": typing_event.get("duplicate"),
        } if typing_event else None,
        "text_probe": {
            "text_length": sample.get("text_length"),
            "caret_offset": sample.get("caret_offset"),
            "text_read": bool(sample.get("text_length") is not None),
        },
        "browser_context_inference": {
            key: browser_context_inference.get(key)
            for key in ("ok", "status", "basis", "context_id", "max_age_sec")
            if key in browser_context_inference
        } if browser_context_inference else None,
        "summary": dict(summary),
        "policy": {
            "compact_history": True,
            "full_listener_state_in_latest": True,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "text_omitted_from_compact_record": True,
        },
    }


def typing_atspi_compact_history_contract_document(
    *,
    records: Iterable[Any],
    parse_errors: Iterable[Any],
    path: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
    lines_scanned: int | None = None,
) -> dict[str, Any]:
    record_items = [item for item in records if isinstance(item, Mapping)]
    parse_error_items = [
        dict(item) if isinstance(item, Mapping) else {"error": str(item)[:240]}
        for item in parse_errors
    ]
    compact_schema = f"{schema_prefix}_typing_atspi_text_event_compact_v1"
    full_snapshot_schema = f"{schema_prefix}_typing_atspi_text_events_v1"
    compact_records = [item for item in record_items if item.get("schema") == compact_schema]
    full_snapshot_records = [item for item in record_items if item.get("schema") == full_snapshot_schema]
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    decision_values = {"allow_text", "metadata_only", "skip", "needs_review"}
    required_state_keys = ("editable", "focused", "showing", "visible", "enabled", "sensitive")

    for offset, item in enumerate(compact_records, start=1):
        row = {
            "offset": offset,
            "event_index": item.get("event_index"),
            "generated_at": item.get("generated_at"),
            "status": item.get("status"),
        }
        policy = item.get("policy") if isinstance(item.get("policy"), Mapping) else {}
        states = item.get("states") if isinstance(item.get("states"), Mapping) else {}
        gate = item.get("capture_gate") if isinstance(item.get("capture_gate"), Mapping) else {}
        typing_event = item.get("typing_event") if isinstance(item.get("typing_event"), Mapping) else {}
        text_probe = item.get("text_probe") if isinstance(item.get("text_probe"), Mapping) else {}
        browser_context = (
            item.get("browser_context_inference")
            if isinstance(item.get("browser_context_inference"), Mapping)
            else {}
        )
        missing_core = [
            key
            for key in ("generated_at", "status", "source_adapter", "listener_status", "event_index", "event_type")
            if item.get(key) in (None, "")
        ]
        bad_policy = [
            key
            for key, expected in (
                ("compact_history", True),
                ("full_listener_state_in_latest", True),
                ("raw_keylogging", False),
                ("password_fields_captured", False),
                ("automatic_action", False),
                ("text_omitted_from_compact_record", True),
            )
            if policy.get(key) is not expected
        ]
        has_surface_identity = any(
            item.get(key) not in (None, "")
            for key in ("app", "window_title", "url", "document_title", "role", "name")
        )
        has_accessibility_identity = any(
            item.get(key) not in (None, "")
            for key in ("role", "atspi_path", "document_path")
        )
        has_context_identity = bool(has_surface_identity or has_accessibility_identity or browser_context.get("context_id"))
        state_gaps = [key for key in required_state_keys if not isinstance(states.get(key), bool)]
        gate_decision = gate.get("decision")
        gate_gap = bool(gate and gate_decision not in decision_values)
        status = str(item.get("status") or "")
        text_event_requires_link = bool(
            status in {"captured", "metadata_only", "metadata_only_or_skipped_before_text_read"}
            or bool(typing_event)
        )
        missing_typing_link = bool(text_event_requires_link and not typing_event.get("event_id"))
        text_policy_gap = bool(
            "text" in item
            or "text_raw" in item
            or policy.get("text_omitted_from_compact_record") is not True
        )
        if (
            missing_core
            or item.get("source_adapter") != "atspi_text_changed_event"
            or bad_policy
            or not has_context_identity
            or state_gaps
            or gate_gap
            or missing_typing_link
            or not isinstance(text_probe, Mapping)
            or text_policy_gap
        ):
            violations.append({
                **row,
                "missing_core": missing_core,
                "bad_policy": bad_policy,
                "source_adapter": item.get("source_adapter"),
                "has_surface_identity": has_surface_identity,
                "has_accessibility_identity": has_accessibility_identity,
                "state_gaps": state_gaps,
                "capture_gate_decision": gate_decision,
                "missing_typing_event_link": missing_typing_link,
                "text_policy_gap": text_policy_gap,
            })

    if not compact_records:
        warnings.append({"key": "no_recent_compact_rows", "message": "no compact AT-SPI rows found in recent history"})
    if compact_records and len(full_snapshot_records) > max(5, len(compact_records) // 5 + 2):
        warnings.append({
            "key": "full_snapshot_ratio",
            "message": "full listener snapshots are high relative to compact rows",
            "compact_records": len(compact_records),
            "full_snapshot_records": len(full_snapshot_records),
        })

    ok = not parse_error_items and not violations and bool(compact_records)
    status = "passed" if ok else "warn" if warnings and not parse_error_items and not violations else "failed"
    return {
        "schema": f"{schema_prefix}_typing_atspi_compact_history_contract_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": status,
        "path": path,
        "summary": {
            "lines_scanned": _safe_int(lines_scanned, len(record_items) + len(parse_error_items)),
            "records_scanned": len(record_items),
            "compact_records": len(compact_records),
            "full_snapshot_records": len(full_snapshot_records),
            "parse_errors": len(parse_error_items),
            "violations": len(violations),
            "warnings": len(warnings),
            "required_core_fields": ["generated_at", "status", "source_adapter", "listener_status", "event_index", "event_type"],
            "required_search_identity_any": ["app", "window_title", "url", "document_title", "role", "name", "atspi_path", "document_path"],
            "required_link_when_text_role": "typing_event.event_id",
        },
        "violations": violations[:20],
        "warnings": warnings[:20],
        "parse_errors": parse_error_items[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "compact_rows_store_extra_text": False,
            "full_listener_state_sparse_only": True,
            "search_binding_keys_required": True,
        },
    }


def typing_coverage_route_notes_and_gaps(
    *,
    configured_adapters: list[str],
    by_adapter: Mapping[str, int],
    by_gate: Mapping[str, int],
    record_count: int,
    dominant_adapter: str | None,
    dominant_ratio: float,
    saved_text_count: int,
    live_input_count: int,
    live_observed_adapters: list[str],
    live_dominant_adapter: str | None,
    live_dominant_ratio: float,
    browser_release_gap: bool,
    browser_release_status: str | None,
    browser_release_active: bool,
    browser_activation: Mapping[str, Any] | None,
    browser_temporary_proof_ok: bool,
    browser_atspi_fallback_ok: bool,
    browser_effective_recency_status: str,
    browser_recency_max_age_sec: int,
    browser_input_recency: Mapping[str, Any],
    browser_latest_proof: Mapping[str, Any] | None,
    codex_prompt_route_assessment: Mapping[str, Any],
    focused_policy: Mapping[str, Any],
    focused_latest: Mapping[str, Any] | None,
    focused_latest_error: str | None,
    atspi_events_latest: Mapping[str, Any] | None,
    atspi_events_latest_error: str | None,
    generic_gui_selftest_ok: bool,
    zsh_selftest_ok: bool,
    zsh_hook_selftest_error: str | None,
    editor_extension_latest: Mapping[str, Any] | None,
    editor_extension_latest_error: str | None,
    editor_callback_selftest_ok: bool,
    browser_extension_latest: Mapping[str, Any] | None,
    browser_extension_latest_error: str | None,
    browser_ai_transcript_latest: Mapping[str, Any] | None,
    browser_ai_transcript_latest_error: str | None,
    browser_ai_transcript_selftest_ok: bool,
    browser_ai_transcript_selftest_error: str | None,
    missing_gate_records: int,
) -> dict[str, list[dict[str, Any]]]:
    configured = set(configured_adapters)
    adapter_counts = dict(by_adapter)
    route_notes: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    browser_activation_data = browser_activation if isinstance(browser_activation, Mapping) else {}
    browser_input_data = browser_input_recency if isinstance(browser_input_recency, Mapping) else {}
    if browser_release_gap:
        route_notes.append({
            "key": "browser_release_webextension_not_active",
            "level": "info" if browser_atspi_fallback_ok and browser_temporary_proof_ok else "watch",
            "message": "release Firefox WebExtension is not active in the running profile; browser input is covered by temporary-profile proof and/or AT-SPI fallback",
            "release_status": browser_release_status,
            "release_profile_active": browser_release_active,
            "temporary_profile_selftest_ok": browser_temporary_proof_ok,
            "atspi_fallback_ok": browser_atspi_fallback_ok,
            "passwordless_next": nested_get(browser_activation_data, ["passwordless_next_routes"]),
        })
    if browser_effective_recency_status != "live_browser_text_recent":
        route_notes.append({
            "key": "browser_input_recency",
            "level": "watch" if browser_effective_recency_status in {"browser_proof_stale", "browser_evidence_missing"} else "info",
            "message": "browser typed-input recency is explicit; release-profile input, controlled probes, and AT-SPI fallback are reported separately",
            "effective_status": browser_effective_recency_status,
            "max_age_sec": browser_recency_max_age_sec,
            "records": browser_input_data.get("records"),
            "natural_records": browser_input_data.get("natural_records"),
            "controlled_probe_records": browser_input_data.get("controlled_probe_records"),
            "latest_any": browser_input_data.get("latest_any"),
            "latest_proof": browser_latest_proof,
            "release_profile_active": browser_release_active,
        })
    route_notes.extend(codex_prompt_route_assessment.get("route_notes") or [])
    if record_count == 0:
        gaps.append({"key": "no_recent_records", "level": "watch", "message": "no recent typed-text records in coverage window"})
    if dominant_adapter == "saved_text_snapshot" and dominant_ratio >= 0.8 and record_count >= 10:
        saved_dominance_note = {
            "key": "saved_text_dominates_recent_window",
            "level": "info" if live_input_count > 0 else "watch",
            "message": "recent typed-text evidence is dominated by saved files; live input is tracked in a separate coverage lane",
            "ratio": dominant_ratio,
            "saved_text_records": saved_text_count,
            "live_input_records": live_input_count,
            "live_observed_adapters": live_observed_adapters,
            "live_dominant_adapter": live_dominant_adapter,
            "live_dominant_ratio": live_dominant_ratio,
        }
        if live_input_count > 0:
            route_notes.append(saved_dominance_note)
        else:
            gaps.append(saved_dominance_note)
    focused_required = (
        "atspi_focused_text_snapshot" in configured
        and focused_policy.get("enabled") is not False
        and focused_policy.get("text_capture_enabled") is not False
        and str(focused_policy.get("mode") or "").lower() != "diagnostic"
    )
    if focused_required and "atspi_focused_text_snapshot" not in adapter_counts:
        focused_latest_status = focused_latest.get("status") if isinstance(focused_latest, Mapping) else None
        focused_attempt_healthy = focused_latest_status in {
            "skipped_non_text_focus",
            "skipped_no_focused_editable_text",
            "metadata_only_or_skipped_before_text_read",
        }
        focused_idle_note = {
            "key": "focused_snapshot_not_observed_recently",
            "level": "info" if focused_attempt_healthy else "watch",
            "message": "focused safe-browser fallback has not produced recent text records; latest attempt is reported separately",
            "latest_status": focused_latest_status,
            "latest_error": focused_latest_error,
        }
        if focused_attempt_healthy:
            route_notes.append(focused_idle_note)
        else:
            gaps.append(focused_idle_note)
    if "atspi_text_changed_event" in configured and "atspi_text_changed_event" not in adapter_counts:
        atspi_events_summary = atspi_events_latest.get("summary") if isinstance(atspi_events_latest, Mapping) else {}
        if not isinstance(atspi_events_summary, Mapping):
            atspi_events_summary = {}
        atspi_events_attempt_healthy = bool(
            isinstance(atspi_events_latest, Mapping)
            and atspi_events_latest.get("status") in {"running", "sample_complete", "stopped"}
            and _safe_int(atspi_events_summary.get("errors"), 0) == 0
            and (browser_atspi_fallback_ok or generic_gui_selftest_ok)
        )
        atspi_idle_note = {
            "key": "atspi_text_events_not_observed_recently",
            "level": "info" if atspi_events_attempt_healthy else "watch",
            "message": "live AT-SPI text-change events have not produced recent event records",
            "latest_status": atspi_events_latest.get("status") if isinstance(atspi_events_latest, Mapping) else None,
            "latest_summary": atspi_events_summary if atspi_events_summary else None,
            "latest_error": atspi_events_latest_error,
        }
        if atspi_events_attempt_healthy:
            route_notes.append(atspi_idle_note)
        else:
            gaps.append(atspi_idle_note)
    if "zsh_preexec" not in adapter_counts:
        zsh_idle_note = {
            "key": "zsh_preexec_not_observed_recently",
            "level": "info" if zsh_selftest_ok else "watch",
            "message": "zsh committed-command adapter has not produced recent event records",
            "latest_selftest_ok": zsh_selftest_ok,
            "latest_selftest_error": zsh_hook_selftest_error,
        }
        if zsh_selftest_ok:
            route_notes.append(zsh_idle_note)
        else:
            gaps.append(zsh_idle_note)
    gaps.extend(codex_prompt_route_assessment.get("gaps") or [])
    if not isinstance(focused_latest, Mapping):
        gaps.append({
            "key": "focused_snapshot_attempt_latest_missing",
            "level": "info",
            "message": "focused snapshot attempts have no persisted latest readmodel yet",
            "error": focused_latest_error,
        })
    if "editor_extension_explicit" in configured and "editor_extension_explicit" not in adapter_counts:
        editor_idle_ready = bool(
            isinstance(editor_extension_latest, Mapping)
            and editor_extension_latest.get("ok") is True
            and editor_callback_selftest_ok
        )
        editor_idle_note = {
            "key": "editor_extension_not_observed_recently",
            "level": "info" if editor_idle_ready else "watch",
            "message": "explicit editor-extension adapter is configured but has not produced recent records",
            "latest_status": editor_extension_latest.get("status") if isinstance(editor_extension_latest, Mapping) else None,
            "latest_error": editor_extension_latest_error,
            "callback_selftest_ok": editor_callback_selftest_ok,
        }
        if editor_idle_ready:
            route_notes.append(editor_idle_note)
        else:
            gaps.append(editor_idle_note)
    if "browser_extension_explicit" in configured and "browser_extension_explicit" not in adapter_counts:
        browser_extension_idle_ready = bool(
            isinstance(browser_extension_latest, Mapping)
            and browser_extension_latest.get("ok") is True
            and (browser_temporary_proof_ok or browser_atspi_fallback_ok)
        )
        browser_extension_idle_note = {
            "key": "browser_extension_not_observed_recently",
            "level": "info" if browser_extension_idle_ready else "watch",
            "message": "explicit browser-extension adapter is configured but has not produced recent records",
            "latest_status": browser_extension_latest.get("status") if isinstance(browser_extension_latest, Mapping) else None,
            "latest_error": browser_extension_latest_error,
            "temporary_profile_selftest_ok": browser_temporary_proof_ok,
            "atspi_fallback_ok": browser_atspi_fallback_ok,
        }
        if browser_extension_idle_ready:
            route_notes.append(browser_extension_idle_note)
        else:
            gaps.append(browser_extension_idle_note)
    if "browser_ai_transcript" in configured and "browser_ai_transcript" not in adapter_counts:
        browser_ai_transcript_idle_note = {
            "key": "browser_ai_transcript_not_observed_recently",
            "level": "info" if browser_ai_transcript_selftest_ok else "watch",
            "message": "browser AI transcript adapter is configured but has not produced recent transcript records",
            "latest_status": browser_ai_transcript_latest.get("status") if isinstance(browser_ai_transcript_latest, Mapping) else None,
            "latest_error": browser_ai_transcript_latest_error,
            "latest_selftest_ok": browser_ai_transcript_selftest_ok,
            "latest_selftest_error": browser_ai_transcript_selftest_error,
        }
        if browser_ai_transcript_selftest_ok:
            route_notes.append(browser_ai_transcript_idle_note)
        else:
            gaps.append(browser_ai_transcript_idle_note)
    if browser_effective_recency_status in {"browser_proof_stale", "browser_evidence_missing"}:
        gaps.append({
            "key": "browser_input_recency_not_fresh",
            "level": "watch",
            "message": "browser typed-input route has no fresh live event or controlled proof inside the configured recency window",
            "effective_status": browser_effective_recency_status,
            "max_age_sec": browser_recency_max_age_sec,
            "latest_any": browser_input_data.get("latest_any"),
            "latest_proof": browser_latest_proof,
            "release_profile_active": browser_release_active,
        })
    if by_gate.get("metadata_only", 0) == 0 and by_gate.get("skip", 0) == 0 and record_count:
        gaps.append({
            "key": "capture_gate_deny_routes_not_observed_recently",
            "level": "info",
            "message": "recent event window has no metadata_only or skip gate decisions; deterministic probes still validate the deny routes",
        })
    if missing_gate_records:
        gaps.append({
            "key": "legacy_or_missing_capture_gate_records",
            "level": "info",
            "message": "some recent records predate capture_gate or lack a capture_gate object",
            "records": missing_gate_records,
        })
    return {
        "route_notes": route_notes,
        "gaps": gaps,
    }


def codex_session_tail_latest_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest: Any,
    latest_error: str | None,
    latest_path: str,
    service: Mapping[str, Any] | None,
    timer: Mapping[str, Any] | None,
    service_path_exists: bool,
    timer_path_exists: bool,
    max_age_sec: float = 120.0,
    reference_at: Any | None = None,
) -> dict[str, Any]:
    latest_exists = isinstance(latest, Mapping)
    latest_data = latest if latest_exists else {}
    latest_summary = latest_data.get("summary") if isinstance(latest_data.get("summary"), Mapping) else {}
    latest_policy = latest_data.get("policy") if isinstance(latest_data.get("policy"), Mapping) else {}
    service_data = dict(service) if isinstance(service, Mapping) else {}
    timer_data = dict(timer) if isinstance(timer, Mapping) else {}
    recurring_ok = bool(
        (service_path_exists and service_data.get("is_active") and service_data.get("is_enabled"))
        or (timer_path_exists and timer_data.get("is_active") and timer_data.get("is_enabled"))
    )
    latest_age_sec = age_seconds(latest_data.get("generated_at"), reference_at)
    latest_status = str(latest_data.get("status") or "missing")
    healthy_statuses = {"processed", "primed"}
    policy_ok = bool(
        latest_policy.get("raw_keylogging") is False
        and latest_policy.get("session_jsonl_tail_fallback") is True
        and latest_policy.get("committed_user_messages_only") is True
        and latest_policy.get("normalizes_codex_context_envelopes") is True
        and latest_policy.get("password_fields_captured") is False
        and latest_policy.get("capture_gate_required") is True
        and latest_policy.get("session_postprocessing") is False
    )
    latest_ok = bool(
        latest_exists
        and latest_data.get("ok") is True
        and latest_status in healthy_statuses
        and _safe_int(latest_summary.get("parse_errors"), 0) == 0
    )
    latest_fresh = bool(latest_age_sec is not None and latest_age_sec <= float(max_age_sec))
    if not latest_exists:
        status = "missing"
    elif latest_error:
        status = "unreadable"
    elif not recurring_ok:
        status = "recurring_inactive"
    elif not policy_ok:
        status = "policy_violation"
    elif not latest_ok:
        status = latest_status if latest_status != "missing" else "degraded"
    elif not latest_fresh:
        status = "stale"
    else:
        status = latest_status
    return {
        "schema": f"{schema_prefix}_typing_codex_session_tail_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(status in healthy_statuses),
        "status": status,
        "summary": {
            "latest_exists": latest_exists,
            "latest_error": latest_error,
            "latest_ok": latest_data.get("ok") if latest_exists else None,
            "latest_status": latest_data.get("status") if latest_exists else None,
            "latest_generated_at": latest_data.get("generated_at") if latest_exists else None,
            "latest_age_sec": latest_age_sec,
            "max_age_sec": float(max_age_sec),
            "service_active": service_data.get("is_active"),
            "service_enabled": service_data.get("is_enabled"),
            "timer_active": timer_data.get("is_active"),
            "timer_enabled": timer_data.get("is_enabled"),
            "recurring_ok": recurring_ok,
            "files": latest_summary.get("files"),
            "events": latest_summary.get("events"),
            "captured": latest_summary.get("captured"),
            "metadata_only": latest_summary.get("metadata_only"),
            "duplicate_skipped": latest_summary.get("duplicate_skipped"),
            "raw_user_candidates": latest_summary.get("raw_user_candidates"),
            "normalized_skipped": latest_summary.get("normalized_skipped"),
            "raw_route_duplicates_skipped": latest_summary.get("raw_route_duplicates_skipped"),
            "response_item_route_migration": latest_summary.get("response_item_route_migration"),
            "parse_errors": latest_summary.get("parse_errors"),
            "prime_state": latest_summary.get("prime_state"),
        },
        "latest": {
            "path": str(latest_path),
            "generated_at": latest_data.get("generated_at") if latest_exists else None,
            "status": latest_data.get("status") if latest_exists else None,
            "ok": latest_data.get("ok") if latest_exists else None,
            "summary": latest_summary,
            "files": latest_data.get("files") if isinstance(latest_data.get("files"), list) else [],
            "events": latest_data.get("events") if isinstance(latest_data.get("events"), list) else [],
            "parse_errors": latest_data.get("parse_errors") if isinstance(latest_data.get("parse_errors"), list) else [],
        },
        "service": service_data,
        "timer": timer_data,
        "policy": {
            "raw_keylogging": latest_policy.get("raw_keylogging"),
            "native_codex_submit_hook": latest_policy.get("native_codex_submit_hook"),
            "session_jsonl_tail_fallback": latest_policy.get("session_jsonl_tail_fallback"),
            "raw_record_routes": latest_policy.get("raw_record_routes"),
            "committed_user_messages_only": latest_policy.get("committed_user_messages_only"),
            "normalizes_codex_context_envelopes": latest_policy.get("normalizes_codex_context_envelopes"),
            "password_fields_captured": latest_policy.get("password_fields_captured"),
            "capture_gate_required": latest_policy.get("capture_gate_required"),
            "session_postprocessing": latest_policy.get("session_postprocessing"),
        },
    }


def saved_text_policy(policy: dict[str, Any], default_policy: dict[str, Any]) -> dict[str, Any]:
    saved = policy.get("saved_text_scan") if isinstance(policy.get("saved_text_scan"), dict) else {}
    default_saved = default_policy.get("saved_text_scan", {})
    return deep_merge(default_saved, saved) if isinstance(default_saved, dict) else saved


def typing_saved_text_scan_policy_status(
    *,
    allowed_adapters: Iterable[Any],
    saved_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    policy = saved_policy if isinstance(saved_policy, Mapping) else {}
    adapter_names = {str(item) for item in allowed_adapters}
    checks = {
        "saved_text_adapter_allowed": "saved_text_snapshot" in adapter_names,
        "policy_enabled": policy.get("enabled") is not False,
        "max_file_bytes_positive": _safe_int(policy.get("max_file_bytes"), 0) > 0,
        "deny_path_tokens_present": bool(policy.get("deny_path_tokens")),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
    }


def saved_text_path_denied(path: Path | str, saved_policy: dict[str, Any]) -> list[dict[str, Any]]:
    probe = str(path).lower()
    matches: list[dict[str, Any]] = []
    for token in saved_policy.get("deny_path_tokens", []):
        token_text = str(token or "").lower().strip()
        if token_text and token_text in probe:
            matches.append({"kind": "deny_path_token", "token": token_text})
    return matches


def saved_text_path_excluded(path: Path | str, saved_policy: dict[str, Any]) -> list[dict[str, Any]]:
    probe = str(path).replace("\\", "/")
    matches: list[dict[str, Any]] = []
    for token in saved_policy.get("exclude_path_tokens", []):
        token_text = str(token or "").strip()
        if token_text and token_text in probe:
            matches.append({"kind": "exclude_path_token", "token": token_text})
    return matches


def saved_text_low_signal_artifact(path: Path | str, saved_policy: dict[str, Any]) -> list[dict[str, Any]]:
    probe = str(path).replace("\\", "/")
    matches: list[dict[str, Any]] = []
    for token in saved_policy.get("low_signal_artifact_path_tokens", []):
        token_text = str(token or "").strip()
        if token_text and token_text in probe:
            matches.append({"kind": "low_signal_artifact_path_token", "token": token_text})
    return matches


def saved_text_file_allowed(path: Path | str, saved_policy: dict[str, Any]) -> bool:
    source_path = Path(path)
    suffixes = {str(item).lower() for item in saved_policy.get("include_extensions", []) if str(item).strip()}
    names = {str(item) for item in saved_policy.get("include_names", []) if str(item).strip()}
    return source_path.name in names or source_path.suffix.lower() in suffixes


def typing_saved_text_recent_records_status(
    *,
    records: Iterable[Any],
    saved_policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    policy = dict(saved_policy) if isinstance(saved_policy, Mapping) else {}
    excluded_saved_events: list[dict[str, Any]] = []
    bad_saved_task_bindings: list[dict[str, Any]] = []
    saved_text_records = 0

    for record in records:
        if not isinstance(record, Mapping) or record.get("source_adapter") != "saved_text_snapshot":
            continue
        saved_text_records += 1
        file_meta = nested_get(record, ["metadata", "file"])
        path_text = str(file_meta.get("path") or "") if isinstance(file_meta, Mapping) else ""
        if not path_text:
            continue
        excluded = saved_text_path_excluded(Path(path_text), policy)
        denied = saved_text_path_denied(Path(path_text), policy)
        if excluded or denied:
            excluded_saved_events.append({
                "event_id": record.get("event_id"),
                "path": path_text,
                "excluded": excluded[:5],
                "denied": denied[:5],
            })
        active_changes = nested_get(record, ["causal_context", "task", "active_changes"])
        if (
            isinstance(active_changes, list)
            and active_changes
            and not any(
                item.get("match") == "surface_match"
                for item in active_changes
                if isinstance(item, Mapping)
            )
        ):
            bad_saved_task_bindings.append({
                "event_id": record.get("event_id"),
                "path": path_text,
                "active_changes": active_changes[:5],
            })

    return {
        "ok": bool(not excluded_saved_events and not bad_saved_task_bindings),
        "saved_text_records": saved_text_records,
        "excluded_path_violations": excluded_saved_events,
        "excluded_path_violation_count": len(excluded_saved_events),
        "task_binding_violations": bad_saved_task_bindings,
        "task_binding_violation_count": len(bad_saved_task_bindings),
    }


def typing_recent_records_shape_status(
    records: Iterable[Any],
) -> dict[str, Any]:
    policy_violations: list[Any] = []
    missing_causal_context: list[Any] = []
    record_count = 0

    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_count += 1
        if (
            nested_get(record, ["policy", "raw_keylogging"]) is not False
            or nested_get(record, ["policy", "password_fields_captured"]) is not False
            or nested_get(record, ["policy", "raw_private_content"]) is not False
        ):
            policy_violations.append(record.get("event_id"))
        if not isinstance(record.get("causal_context"), Mapping):
            missing_causal_context.append(record.get("event_id"))

    return {
        "ok": not policy_violations,
        "records_checked": record_count,
        "policy_violations": policy_violations,
        "policy_violation_count": len(policy_violations),
        "missing_causal_context": missing_causal_context,
        "missing_causal_context_count": len(missing_causal_context),
    }


def typing_process_readmodel_status(
    process: Mapping[str, Any] | None,
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    process_data = process if isinstance(process, Mapping) else {}
    summary = process_data.get("summary") if isinstance(process_data.get("summary"), Mapping) else {}
    policy = process_data.get("policy") if isinstance(process_data.get("policy"), Mapping) else {}
    awareness = process_data.get("awareness") if isinstance(process_data.get("awareness"), Mapping) else {}
    checks = {
        "schema": process_data.get("schema") == f"{schema_prefix}_typing_process_v1",
        "ok": process_data.get("ok") is True,
        "records_processed": _safe_int(summary.get("records_processed"), 0) > 0,
        "lanes": _safe_int(summary.get("lanes"), 0) > 0,
        "fail_gaps": _safe_int(summary.get("fail_gaps"), 0) == 0,
        "awareness_schema": awareness.get("schema") == f"{schema_prefix}_typing_causal_awareness_summary_v1",
        "stores_extra_text": policy.get("stores_extra_text") is False,
        "widens_capture": policy.get("widens_capture") is False,
        "raw_keylogging": policy.get("raw_keylogging") is False,
    }
    core_ok = all(checks.values())
    missing_context_anchor = _safe_int(summary.get("missing_context_anchor"), 0)
    level = "ok" if core_ok and missing_context_anchor == 0 else "warn" if core_ok else "fail"
    return {
        "ok": bool(core_ok and level == "ok"),
        "level": level,
        "core_ok": core_ok,
        "checks": checks,
        "missing_context_anchor": missing_context_anchor,
    }


def typing_causal_awareness_readmodel_status(
    process: Mapping[str, Any] | None,
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    process_data = process if isinstance(process, Mapping) else {}
    summary = process_data.get("summary") if isinstance(process_data.get("summary"), Mapping) else {}
    awareness = process_data.get("awareness") if isinstance(process_data.get("awareness"), Mapping) else {}
    axis_states = awareness.get("axis_states") if isinstance(awareness.get("axis_states"), Mapping) else {}
    records_processed = _safe_int(summary.get("records_processed"), 0)
    checks = {
        "schema": awareness.get("schema") == f"{schema_prefix}_typing_causal_awareness_summary_v1",
        "records_match": _safe_int(awareness.get("records"), 0) == records_processed,
        "privacy_gate_known": nested_get(axis_states, ["privacy_gate", "known"]) == records_processed,
        "where_entered_known": nested_get(axis_states, ["where_entered", "known"]) == records_processed,
        "who_received_known": nested_get(axis_states, ["who_received", "known"]) == records_processed,
        "task_context_known": nested_get(axis_states, ["task_context", "known"]) == records_processed,
        "top_gaps": isinstance(awareness.get("top_gaps"), Mapping),
        "stores_extra_text": nested_get(awareness, ["policy", "stores_extra_text"]) is False,
        "widens_capture": nested_get(awareness, ["policy", "widens_capture"]) is False,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "records_processed": records_processed,
    }


def capture_gate_policy(policy: dict[str, Any], default_policy: dict[str, Any]) -> dict[str, Any]:
    gate = policy.get("capture_gate") if isinstance(policy.get("capture_gate"), dict) else {}
    default_gate = default_policy.get("capture_gate", {})
    return deep_merge(default_gate, gate) if isinstance(default_gate, dict) else gate


def capture_gate_token_matches(kind: str, probe: str, tokens: list[Any]) -> list[dict[str, Any]]:
    lowered = str(probe or "").lower()
    matches: list[dict[str, Any]] = []
    for token in tokens:
        token_text = str(token or "").lower().strip()
        if token_text and token_text in lowered:
            matches.append({"kind": kind, "token": token_text})
    return matches


def deny_context_matches(probe: str, policy: dict[str, Any]) -> list[dict[str, Any]]:
    lowered = str(probe or "").lower()
    matches: list[dict[str, Any]] = []
    for token in policy.get("deny_context_tokens", []):
        token_text = str(token).lower().strip()
        if token_text and token_text in lowered:
            matches.append({"kind": "deny_context_token", "token": token_text})
    return matches


def context_payload_text(context_payload: dict[str, Any], key: str) -> str:
    item = context_payload.get(key) if isinstance(context_payload, dict) else None
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return ""


def causal_extract_context_value(context_text: str, key: str) -> str | None:
    pattern = rf"(?:^|\s){re.escape(key)}=([^\s]+)"
    match = re.search(pattern, str(context_text or ""))
    return match.group(1).rstrip(".,;)") if match else None


def typing_causal_project_for_path(path: str, policy: Mapping[str, Any]) -> dict[str, Any] | None:
    policy_data = policy if isinstance(policy, Mapping) else {}
    causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}
    roots = causal_policy.get("project_roots") if isinstance(causal_policy.get("project_roots"), list) else []
    candidates = [item for item in roots if isinstance(item, Mapping) and item.get("root")]
    candidates.sort(key=lambda item: len(str(item.get("root") or "")), reverse=True)
    for item in candidates:
        root = str(item.get("root") or "")
        if path_under(path, root):
            return {
                "id": str(item.get("id") or root),
                "kind": str(item.get("kind") or "path_root"),
                "root": root,
                "matched_path": str(path),
            }
    return None


def typing_causal_project_for_paths(paths: list[str], policy: Mapping[str, Any]) -> dict[str, Any] | None:
    for path in paths:
        project = typing_causal_project_for_path(path, policy)
        if isinstance(project, dict):
            project["basis"] = "explicit_path"
            return project
    return None


def typing_causal_topic_project_for_text(text: str, policy: Mapping[str, Any]) -> dict[str, Any] | None:
    policy_data = policy if isinstance(policy, Mapping) else {}
    causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}
    hints = causal_policy.get("topic_hints") if isinstance(causal_policy.get("topic_hints"), list) else []
    haystack = str(text or "").lower()
    if not haystack:
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for hint in hints:
        if not isinstance(hint, Mapping):
            continue
        keywords = [str(item or "").strip() for item in hint.get("keywords", []) if str(item or "").strip()]
        matched = [keyword for keyword in keywords if keyword.lower() in haystack]
        if not matched:
            continue
        score = max(len(keyword) for keyword in matched) + len(matched) * 3
        if score <= best_score:
            continue
        best_score = score
        root = str(hint.get("root") or "")
        best = {
            "id": str(hint.get("id") or root or "topic"),
            "kind": str(hint.get("kind") or "topic_hint"),
            "root": root or None,
            "matched_path": root or None,
            "basis": "topic_hint",
            "confidence": "topic_keyword_match",
            "matched_keywords": matched[:6],
            "stores_extra_text": False,
        }
    return best


def typing_causal_resolve_project(
    path_project: dict[str, Any] | None,
    topic_project: dict[str, Any] | None,
    policy: Mapping[str, Any],
    source_id: str,
) -> dict[str, Any] | None:
    if not isinstance(path_project, dict) or not path_project.get("id"):
        return topic_project if isinstance(topic_project, dict) and topic_project.get("id") else None
    if not isinstance(topic_project, dict) or not topic_project.get("id"):
        return path_project
    if str(path_project.get("id")) == str(topic_project.get("id")):
        return path_project
    policy_data = policy if isinstance(policy, Mapping) else {}
    causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}
    broad_ids = {
        str(item)
        for item in (causal_policy.get("broad_context_project_ids") or [])
        if str(item or "").strip()
    }
    matched_path = str(path_project.get("matched_path") or "").rstrip("/")
    root = str(path_project.get("root") or "").rstrip("/")
    path_is_broad_context = (
        str(path_project.get("id")) in broad_ids
        and matched_path
        and root
        and matched_path == root
        and source_id in {"codex_user_prompt_submit", "codex_session_jsonl_prompt_tail", "manual_cli_args", "manual_cli_stdin"}
    )
    if path_is_broad_context:
        resolved = dict(topic_project)
        resolved["basis"] = "topic_over_broad_workspace"
        resolved["workspace_project"] = {
            key: path_project.get(key)
            for key in ("id", "kind", "root", "matched_path", "basis")
            if path_project.get(key) is not None
        }
        resolved["stores_extra_text"] = False
        return resolved
    return path_project


def typing_causal_project_binding_summary(project: dict[str, Any] | None, reason: str | None = None) -> dict[str, Any]:
    if isinstance(project, dict) and project.get("id"):
        return {
            "id": project.get("id"),
            "kind": project.get("kind"),
            "root": project.get("root"),
            "basis": project.get("basis") or "path_root",
            "confidence": project.get("confidence") or (
                "topic_keyword_match" if str(project.get("basis") or "").startswith("topic") else "project_root_match"
            ),
            "readmodel_promoted_from": project.get("readmodel_promoted_from"),
            "source_event_id": project.get("source_event_id"),
            "source_age_sec": project.get("source_age_sec"),
            "source_interaction_key": project.get("source_interaction_key"),
            "stores_extra_text": False,
        }
    return {
        "id": "unknown",
        "basis": "none",
        "confidence": reason or "no_project_path_or_topic_signal",
        "stores_extra_text": False,
    }


def typing_causal_controlled_probe_project(
    source_id: str,
    context_payload: Mapping[str, Any] | None,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    meta = metadata if isinstance(metadata, Mapping) else {}
    browser_meta = meta.get("browser") if isinstance(meta.get("browser"), Mapping) else {}
    transcript_meta = meta.get("ai_transcript") if isinstance(meta.get("ai_transcript"), Mapping) else {}
    context_data = context_payload if isinstance(context_payload, dict) else {}
    probe_text = "\n".join(
        item
        for item in (
            str(source_id or ""),
            context_payload_text(context_data, "app"),
            context_payload_text(context_data, "window_title"),
            context_payload_text(context_data, "context"),
            context_payload_text(context_data, "url"),
            str(browser_meta.get("event_kind") or ""),
            str(browser_meta.get("field_kind") or ""),
            str(transcript_meta.get("event_kind") or ""),
            str(transcript_meta.get("completeness") or ""),
        )
        if item
    ).lower()
    event_kind_markers: list[str] = []
    if "selftest" in str(browser_meta.get("event_kind") or "").lower():
        event_kind_markers.append("browser_event_kind:selftest")
    if "selftest" in str(transcript_meta.get("event_kind") or "").lower():
        event_kind_markers.append("ai_transcript_event_kind:selftest")
    markers = [
        "typing_end_to_end",
        "typing end-to-end",
        "browser_privacy_run",
        "generic-gui-selftest",
        "callback-selftest",
        "transcript selftest",
        "ai_transcript_selftest",
        "abyss safe browser probe",
        "abyss browser at-spi safe input probe",
        "abyss browser webextension safe input probe",
        "abyss writing context",
    ]
    matched = event_kind_markers + [marker for marker in markers if marker in probe_text]
    if not matched:
        return None
    return {
        "id": "abyss-machine",
        "kind": "host_machine_layer",
        "root": "/var/lib/abyss-machine",
        "matched_path": "/var/lib/abyss-machine",
        "basis": "controlled_probe",
        "confidence": "abyss_machine_controlled_probe",
        "matched_keywords": matched[:6],
        "stores_extra_text": False,
    }


def url_origin_path(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return None
    scheme = str(parsed.scheme or "").lower()
    host = str(parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        return None
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return f"{scheme}://{host}{port}{path}"


def url_path_hash(url: str | None) -> dict[str, Any]:
    raw = str(url or "").strip()
    if not raw:
        return {"url_path_present": False}
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        return {"url_path_present": False}
    path_query = urllib.parse.urlunsplit(("", "", parsed.path or "", parsed.query or "", ""))
    if not path_query:
        return {"url_path_present": False}
    return {
        "url_path_present": True,
        "url_path_sha256": hashlib.sha256(path_query.encode("utf-8", errors="replace")).hexdigest(),
        "url_path_stored": False,
    }


def ai_counterpart_context_anchor(ai_counterpart: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "ai_counterpart",
        "id": ai_counterpart.get("entity_id"),
        "label": ai_counterpart.get("label"),
        "provider": ai_counterpart.get("provider"),
        "product": ai_counterpart.get("product"),
        "family": ai_counterpart.get("family"),
        "surface": ai_counterpart.get("surface"),
        "origin": ai_counterpart.get("origin"),
        "host": ai_counterpart.get("host"),
        "confidence": ai_counterpart.get("confidence"),
        "url_path_stored": False,
        "stores_extra_text": False,
    }


def context_anchor_from_parts(
    source_id: str,
    app_text: str | None,
    window_title: str | None,
    url: str | None,
    primary_path: str | None,
    project: Mapping[str, Any] | None,
    *,
    home_path: str | None = None,
) -> dict[str, Any]:
    if isinstance(project, Mapping) and project.get("id"):
        return {
            "kind": "project_root",
            "id": f"project:{project.get('id')}",
            "label": project.get("id"),
            "project": dict(project),
            "confidence": "project_root_match",
            "stores_extra_text": False,
        }
    ai_counterpart = browser_ai_counterpart_identity(url, window_title)
    if ai_counterpart.get("is_ai") is True:
        return ai_counterpart_context_anchor(ai_counterpart)
    origin = url_origin(url)
    if origin:
        host = origin.get("host") or origin.get("origin")
        return {
            "kind": "url_origin",
            "id": origin.get("id"),
            "label": host,
            "origin": origin.get("origin"),
            "scheme": origin.get("scheme"),
            "host": origin.get("host"),
            "confidence": "observed_url_origin",
            "url_path_stored": False,
            "stores_extra_text": False,
        }
    path_text = str(primary_path or "").strip()
    if path_text:
        home = str(home_path or "").strip()
        if home and path_under(path_text, home):
            return {
                "kind": "operator_home_path",
                "id": f"path:{home}",
                "label": f"home-{Path(home).name or 'operator'}",
                "root": home,
                "matched_path": path_text,
                "confidence": "observed_home_path",
                "stores_extra_text": False,
            }
        return {
            "kind": "path",
            "id": f"path:{path_text}",
            "label": Path(path_text).name or path_text,
            "matched_path": path_text,
            "confidence": "observed_path",
            "stores_extra_text": False,
        }
    app = str(app_text or "").strip()
    title = str(window_title or "").strip()
    if app or title:
        label = app or title
        raw_id = f"app:{app or 'unknown'}:{title or ''}"
        return {
            "kind": "application_surface",
            "id": "surface:" + hashlib.sha256(raw_id.encode("utf-8", errors="replace")).hexdigest()[:16],
            "label": label[:80],
            "app": app or None,
            "window_title_sha256": hashlib.sha256(title.encode("utf-8", errors="replace")).hexdigest() if title else None,
            "confidence": "observed_application_surface",
            "stores_extra_text": False,
        }
    return {
        "kind": "unknown",
        "id": "unknown",
        "label": "unknown",
        "confidence": "missing_observable_context",
        "stores_extra_text": False,
    }


def typing_process_lane_id(parts: Iterable[str]) -> str:
    part_texts = [str(item or "unknown") for item in parts]
    raw = "|".join(part_texts)
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    label = re.sub(r"[^A-Za-z0-9_.:-]+", "-", "-".join(part_texts)).strip("-").lower()[:80]
    return f"{label or 'typing-lane'}-{digest}"


def typing_process_context_anchor(
    source_adapter: str,
    where: Mapping[str, Any] | None,
    project: Mapping[str, Any] | None,
    *,
    home_path: str | None = None,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    where_data = where if isinstance(where, Mapping) else {}
    anchor = where_data.get("context_anchor") if isinstance(where_data.get("context_anchor"), Mapping) else {}
    interaction = where_data.get("interaction") if isinstance(where_data.get("interaction"), Mapping) else {}
    if interaction.get("ai_counterpart_id"):
        return {
            "kind": "ai_counterpart",
            "id": interaction.get("ai_counterpart_id"),
            "label": interaction.get("product") or interaction.get("provider") or interaction.get("ai_counterpart_id"),
            "provider": interaction.get("provider"),
            "product": interaction.get("product"),
            "family": interaction.get("family"),
            "surface": interaction.get("surface"),
            "origin": interaction.get("origin"),
            "host": interaction.get("host"),
            "confidence": interaction.get("confidence") or "interaction_ai_counterpart",
            "url_path_stored": False,
            "stores_extra_text": False,
            "readmodel_promoted_from": anchor.get("kind") or "missing",
        }
    if source_adapter in {"atspi_focused_text_snapshot", "atspi_text_changed_event"}:
        ai_counterpart = browser_ai_counterpart_identity(
            str(where_data.get("url") or ""),
            str(where_data.get("window_title") or ""),
            schema_prefix=schema_prefix,
        )
        if ai_counterpart.get("is_ai") is True:
            return {
                "kind": "ai_counterpart",
                "id": ai_counterpart.get("entity_id"),
                "label": ai_counterpart.get("label"),
                "provider": ai_counterpart.get("provider"),
                "product": ai_counterpart.get("product"),
                "family": ai_counterpart.get("family"),
                "surface": ai_counterpart.get("surface"),
                "origin": ai_counterpart.get("origin"),
                "host": ai_counterpart.get("host"),
                "confidence": ai_counterpart.get("confidence"),
                "url_path_stored": False,
                "stores_extra_text": False,
                "readmodel_promoted_from": anchor.get("kind") or "missing",
            }
    if anchor.get("id") and anchor.get("id") != "unknown":
        return dict(anchor)
    where_context = str(where_data.get("context") or "")
    if source_adapter.startswith("atspi_") and re.search(
        r"(?i)(password|passwd|login|auth|otp|2fa|mfa|username|user name|имя пользователя|пароль)",
        where_context,
    ):
        return {
            "kind": "privacy_guarded",
            "id": "privacy:atspi-sensitive-field",
            "label": "AT-SPI privacy-guarded field",
            "confidence": "metadata_only_sensitive_context",
            "stores_extra_text": False,
        }
    return context_anchor_from_parts(
        source_adapter,
        str(where_data.get("app") or ""),
        str(where_data.get("window_title") or ""),
        str(where_data.get("url") or ""),
        str(where_data.get("path") or ""),
        project if project else None,
        home_path=home_path,
    )


def typing_process_recipient_for_context(
    source_adapter: str,
    recipient: Mapping[str, Any] | None,
    where: Mapping[str, Any] | None,
    context_anchor: Mapping[str, Any] | None,
) -> dict[str, Any]:
    recipient_data = recipient if isinstance(recipient, Mapping) else {}
    where_data = where if isinstance(where, Mapping) else {}
    context_anchor_data = context_anchor if isinstance(context_anchor, Mapping) else {}
    if (
        source_adapter in {
            "atspi_focused_text_snapshot",
            "atspi_text_changed_event",
            "browser_ai_transcript",
            "browser_extension_explicit",
        }
        and context_anchor_data.get("kind") == "ai_counterpart"
        and context_anchor_data.get("id")
        and str(recipient_data.get("kind") or "") in {"focused_application", "browser_extension", "missing", ""}
    ):
        return {
            "kind": "ai_counterpart",
            "route": "browser_ai_interaction",
            "id": context_anchor_data.get("id"),
            "name": context_anchor_data.get("label"),
            "provider": context_anchor_data.get("provider"),
            "product": context_anchor_data.get("product"),
            "family": context_anchor_data.get("family"),
            "surface": context_anchor_data.get("surface"),
            "origin": context_anchor_data.get("origin"),
            "browser_app": where_data.get("app"),
            "confidence": context_anchor_data.get("confidence"),
            "readmodel_promoted_from": recipient_data.get("kind") or "missing",
        }
    return dict(recipient_data)


def typing_process_interaction_keys(
    interaction: Mapping[str, Any] | None,
    recipient: Mapping[str, Any] | None,
    context_anchor: Mapping[str, Any] | None,
) -> list[str]:
    interaction_data = interaction if isinstance(interaction, Mapping) else {}
    recipient_data = recipient if isinstance(recipient, Mapping) else {}
    context_anchor_data = context_anchor if isinstance(context_anchor, Mapping) else {}
    keys: list[str] = []

    def add_key(key: str | None) -> None:
        key_text = str(key or "").strip()
        if key_text and key_text not in keys:
            keys.append(key_text)

    if interaction_data.get("id"):
        kind = str(interaction_data.get("kind") or "")
        if kind in {"codex_session", "browser_ai_conversation", "browser_ai_page", "browser_page"}:
            add_key(f"{kind}:{interaction_data.get('id')}")
        if kind in {"browser_ai_conversation", "browser_ai_page"}:
            counterpart_id = str(
                interaction_data.get("ai_counterpart_id")
                or recipient_data.get("id")
                or context_anchor_data.get("id")
                or ""
            )
            title_sha = str(interaction_data.get("title_sha256") or "")
            if counterpart_id and title_sha:
                add_key(f"browser_ai_title:{counterpart_id}:{title_sha[:16]}")
    recipient_kind = str(recipient_data.get("kind") or "")
    recipient_id = str(recipient_data.get("id") or "")
    if not keys and recipient_kind in {"codex_session", "ai_counterpart"} and recipient_id:
        add_key(f"recipient:{recipient_kind}:{recipient_id}")
    anchor_kind = str(context_anchor_data.get("kind") or "")
    anchor_id = str(context_anchor_data.get("id") or "")
    if not keys and anchor_kind in {"ai_counterpart", "url_origin"} and anchor_id:
        add_key(f"anchor:{anchor_kind}:{anchor_id}")
    return keys


def typing_process_interaction_key(
    interaction: Mapping[str, Any] | None,
    recipient: Mapping[str, Any] | None,
    context_anchor: Mapping[str, Any] | None,
) -> str | None:
    keys = typing_process_interaction_keys(interaction, recipient, context_anchor)
    return keys[0] if keys else None


def typing_process_project_for_record(
    record: Mapping[str, Any] | None,
    where: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record_data = record if isinstance(record, Mapping) else {}
    where_data = where if isinstance(where, Mapping) else {}
    project = where_data.get("project") if isinstance(where_data.get("project"), Mapping) else {}
    if project.get("id"):
        return dict(project)
    text_payload = record_data.get("text") if isinstance(record_data.get("text"), Mapping) else {}
    stored_text = str(text_payload.get("text") or "")
    metadata = record_data.get("metadata") if isinstance(record_data.get("metadata"), Mapping) else {}
    context_payload = {
        "app": {"text": str(where_data.get("app") or "")},
        "window_title": {"text": str(where_data.get("window_title") or "")},
        "context": {"text": str(where_data.get("context") or "")},
        "url": {"text": str(where_data.get("url") or "")},
    }
    signal_text = "\n".join(
        item
        for item in (
            stored_text,
            str(where_data.get("app") or ""),
            str(where_data.get("window_title") or ""),
            str(where_data.get("context") or ""),
            str(where_data.get("path") or ""),
        )
        if item
    )
    topic_signal_text = "\n".join(
        item
        for item in (
            stored_text,
            str(where_data.get("app") or ""),
            str(where_data.get("window_title") or ""),
        )
        if item
    )
    paths = causal_surface_paths(context_payload, metadata, signal_text)
    if where_data.get("path") and str(where_data.get("path")) not in paths:
        paths.insert(0, str(where_data.get("path")))
    path_project = typing_causal_project_for_paths(paths, policy or {})
    topic_project = typing_causal_topic_project_for_text(topic_signal_text, policy or {})
    source_adapter = str(record_data.get("source_adapter") or "")
    controlled_project = typing_causal_controlled_probe_project(source_adapter, context_payload, metadata)
    inferred = controlled_project or typing_causal_resolve_project(path_project, topic_project, policy or {}, source_adapter)
    if isinstance(inferred, dict) and inferred.get("id"):
        promoted = dict(inferred)
        promoted["readmodel_promoted_from"] = "stored_safe_text_or_context"
        promoted["stores_extra_text"] = False
        return promoted
    return {}


def typing_process_unique_records(records: Iterable[Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    raw_record_count = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        raw_record_count += 1
        event_id = str(record.get("event_id") or "").strip()
        if event_id:
            key = f"event:{event_id}"
        else:
            text_payload = record.get("text") if isinstance(record.get("text"), dict) else {}
            key = "synthetic:" + hashlib.sha256(
                "\n".join([
                    str(record.get("source_adapter") or ""),
                    str(record.get("generated_at") or ""),
                    str(text_payload.get("text_sha256") or ""),
                    str(record.get("context_sha256") or ""),
                    str(index),
                ]).encode("utf-8", errors="replace")
            ).hexdigest()[:24]
        if key in seen:
            if event_id and len(duplicate_ids) < 20:
                duplicate_ids.append(event_id)
            continue
        seen.add(key)
        unique.append(record)
    return unique, {
        "raw_records": raw_record_count,
        "unique_records": len(unique),
        "duplicate_event_rows_collapsed": max(0, raw_record_count - len(unique)),
        "duplicate_event_ids": duplicate_ids,
    }


def typing_process_interaction_for_record(
    record: Mapping[str, Any] | None,
    where: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record_data = record if isinstance(record, Mapping) else {}
    where_data = where if isinstance(where, Mapping) else {}
    interaction = where_data.get("interaction") if isinstance(where_data.get("interaction"), Mapping) else {}
    if interaction.get("id"):
        return dict(interaction)
    metadata = record_data.get("metadata") if isinstance(record_data.get("metadata"), Mapping) else {}
    context_payload = {
        "app": {"text": str(where_data.get("app") or "")},
        "window_title": {"text": str(where_data.get("window_title") or "")},
        "context": {"text": str(where_data.get("context") or "")},
        "url": {"text": str(where_data.get("url") or "")},
    }
    return causal_interaction_identity(str(record_data.get("source_adapter") or ""), context_payload, metadata)


def _typing_process_parse_iso(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed.astimezone(dt.timezone.utc)


def typing_process_generated_epoch(record: Mapping[str, Any] | None) -> float:
    record_data = record if isinstance(record, Mapping) else {}
    timestamp = _typing_process_parse_iso(record_data.get("generated_at"))
    if timestamp is None:
        return 0.0
    try:
        return timestamp.timestamp()
    except Exception:
        return 0.0


def typing_parse_iso(value: Any) -> dt.datetime | None:
    return _typing_process_parse_iso(value)


def typing_age_seconds(value: Any, reference_at: Any | None = None) -> float | None:
    parsed = typing_parse_iso(value)
    if parsed is None:
        return None
    reference = typing_parse_iso(reference_at) or dt.datetime.now(dt.timezone.utc)
    return round(max(0.0, (reference - parsed).total_seconds()), 1)


def typing_record_context_text(record: Mapping[str, Any] | None, key: str) -> str:
    record_data = record if isinstance(record, Mapping) else {}
    value = nested_get(record_data, ["context", key, "text"])
    return str(value or "")


def typing_record_url_origin(record: Mapping[str, Any] | None) -> dict[str, str] | None:
    return url_origin(typing_record_context_text(record, "url"))


def typing_controlled_probe_record(record: Mapping[str, Any] | None) -> bool:
    record_data = record if isinstance(record, Mapping) else {}
    probe_parts = [
        typing_record_context_text(record_data, "app"),
        typing_record_context_text(record_data, "window_title"),
        typing_record_context_text(record_data, "url"),
        str(nested_get(record_data, ["causal_context", "recipient", "name"]) or ""),
    ]
    probe_text = " ".join(probe_parts).lower()
    url = typing_record_context_text(record_data, "url").lower()
    return (
        "abyss browser" in probe_text
        or "selftest" in probe_text
        or "probe" in probe_text
        or url.startswith("http://127.0.0.1:")
        or url.startswith("http://localhost:")
    )


def typing_browser_like_record(record: Mapping[str, Any] | None) -> bool:
    record_data = record if isinstance(record, Mapping) else {}
    source = str(record_data.get("source_adapter") or "")
    if source == "browser_extension_explicit":
        return True
    if source != "atspi_text_changed_event":
        return False
    app = typing_record_context_text(record_data, "app").lower()
    window_title = typing_record_context_text(record_data, "window_title").lower()
    url = typing_record_context_text(record_data, "url").lower()
    recipient = " ".join(
        [
            str(nested_get(record_data, ["causal_context", "recipient", "id"]) or ""),
            str(nested_get(record_data, ["causal_context", "recipient", "name"]) or ""),
        ]
    ).lower()
    return bool(
        url.startswith(("http://", "https://"))
        or "firefox" in app
        or "firefox" in window_title
        or "mozilla firefox" in recipient
    )


def typing_process_entry_index(process: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    process_data = process if isinstance(process, Mapping) else {}
    entries = process_data.get("recent_entries") if isinstance(process_data.get("recent_entries"), list) else []
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event_id = str(entry.get("event_id") or "")
        if event_id:
            indexed[event_id] = entry
    return indexed


def typing_recent_record_brief(
    record: Mapping[str, Any] | None,
    reference_at: Any | None = None,
    effective_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record_data = record if isinstance(record, Mapping) else {}
    text_payload = record_data.get("text") if isinstance(record_data.get("text"), Mapping) else {}
    origin = typing_record_url_origin(record_data)
    page_identity = browser_ai_counterpart_identity(
        typing_record_context_text(record_data, "url"),
        typing_record_context_text(record_data, "window_title"),
    )
    effective = effective_entry if isinstance(effective_entry, Mapping) else {}
    effective_where = effective.get("where") if isinstance(effective.get("where"), Mapping) else {}
    effective_recipient = effective.get("recipient") if isinstance(effective.get("recipient"), Mapping) else {}
    effective_task = effective.get("task") if isinstance(effective.get("task"), Mapping) else {}
    effective_anchor = effective_where.get("context_anchor") if isinstance(effective_where.get("context_anchor"), Mapping) else {}
    effective_project = effective_where.get("project") if isinstance(effective_where.get("project"), Mapping) else {}
    effective_interaction = effective_where.get("interaction") if isinstance(effective_where.get("interaction"), Mapping) else {}
    awareness = effective.get("awareness") if isinstance(effective.get("awareness"), Mapping) else {}
    raw_recipient_kind = nested_get(record_data, ["causal_context", "recipient", "kind"])
    raw_project_id = nested_get(record_data, ["causal_context", "where", "project", "id"])
    raw_context_anchor_kind = nested_get(record_data, ["causal_context", "where", "context_anchor", "kind"])
    raw_task_binding = nested_get(record_data, ["causal_context", "task", "binding"])
    recipient_kind = effective_recipient.get("kind") or raw_recipient_kind
    project_id = effective_project.get("id") or raw_project_id
    context_anchor_kind = effective_anchor.get("kind") or raw_context_anchor_kind
    task_binding = effective_task.get("binding") or raw_task_binding
    promoted_fields = [
        name for name, raw_value, effective_value in (
            ("recipient", raw_recipient_kind, recipient_kind),
            ("project", raw_project_id, project_id),
            ("context_anchor", raw_context_anchor_kind, context_anchor_kind),
            ("task_binding", raw_task_binding, task_binding),
        )
        if str(raw_value or "") != str(effective_value or "")
    ]
    return {
        "event_id": record_data.get("event_id"),
        "generated_at": record_data.get("generated_at"),
        "age_sec": typing_age_seconds(record_data.get("generated_at"), reference_at),
        "status": record_data.get("status"),
        "source_adapter": record_data.get("source_adapter"),
        "capture_gate_decision": nested_get(record_data, ["capture_gate", "decision"]),
        "capture_gate_confidence": nested_get(record_data, ["capture_gate", "confidence"]),
        "text_length": text_payload.get("text_length"),
        "text_captured": bool(text_payload.get("captured")),
        "text_omitted": True,
        "recipient_kind": recipient_kind,
        "recipient_id": effective_recipient.get("id") or nested_get(record_data, ["causal_context", "recipient", "id"]),
        "recipient_name": effective_recipient.get("name") or nested_get(record_data, ["causal_context", "recipient", "name"]),
        "recipient_confidence": effective_recipient.get("confidence") or nested_get(record_data, ["causal_context", "recipient", "confidence"]),
        "context_anchor_kind": context_anchor_kind,
        "context_anchor_id": effective_anchor.get("id") or nested_get(record_data, ["causal_context", "where", "context_anchor", "id"]),
        "project_id": project_id,
        "project_binding_basis": nested_get(effective_where, ["project_binding", "basis"]) or nested_get(record_data, ["causal_context", "where", "binding_signals", "project_binding", "basis"]),
        "task_binding": task_binding,
        "interaction_kind": effective_interaction.get("kind") or nested_get(record_data, ["causal_context", "where", "interaction", "kind"]),
        "interaction_id": effective_interaction.get("id") or nested_get(record_data, ["causal_context", "where", "interaction", "id"]),
        "raw_recipient_kind": raw_recipient_kind,
        "raw_context_anchor_kind": raw_context_anchor_kind,
        "raw_project_id": raw_project_id,
        "raw_task_binding": raw_task_binding,
        "effective_causal_promoted": bool(promoted_fields),
        "effective_causal_promoted_fields": promoted_fields,
        "effective_causal_basis": "typing_process_readmodel" if effective else "raw_event_causal_context",
        "awareness_state": awareness.get("state"),
        "awareness_score": awareness.get("score"),
        "app": typing_record_context_text(record_data, "app") or None,
        "window_title": typing_record_context_text(record_data, "window_title") or None,
        "url_origin": origin.get("origin") if isinstance(origin, dict) else None,
        "page_identity": page_identity if page_identity.get("is_ai") is True else None,
        "controlled_probe": typing_controlled_probe_record(record_data),
    }


def typing_latest_record(records: Iterable[Any]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_time: dt.datetime | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        parsed = typing_parse_iso(record.get("generated_at"))
        if parsed is None:
            continue
        if latest_time is None or parsed > latest_time:
            latest = record
            latest_time = parsed
    return latest


def typing_browser_input_recency(
    records: Iterable[Any],
    reference_at: Any | None = None,
    effective_entries: Mapping[str, dict[str, Any]] | None = None,
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    record_items = [record for record in records if isinstance(record, dict)]
    effective_index = effective_entries if isinstance(effective_entries, Mapping) else {}

    def brief(record: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        event_id = str(record.get("event_id") or "")
        return typing_recent_record_brief(record, reference_at, effective_index.get(event_id))

    browser_records = [record for record in record_items if typing_browser_like_record(record)]
    explicit_records = [record for record in browser_records if record.get("source_adapter") == "browser_extension_explicit"]
    atspi_browser_records = [record for record in browser_records if record.get("source_adapter") == "atspi_text_changed_event"]
    controlled_records = [record for record in browser_records if typing_controlled_probe_record(record)]
    natural_records = [record for record in browser_records if not typing_controlled_probe_record(record)]
    text_records = [
        record for record in browser_records
        if record.get("status") in {"captured", "redacted"} and bool(nested_get(record, ["text", "captured"]))
    ]
    natural_text_records = [record for record in natural_records if record in text_records]
    controlled_text_records = [record for record in controlled_records if record in text_records]

    latest_any = typing_latest_record(browser_records)
    latest_explicit = typing_latest_record(explicit_records)
    latest_atspi = typing_latest_record(atspi_browser_records)
    latest_natural = typing_latest_record(natural_records)
    latest_natural_text = typing_latest_record(natural_text_records)
    latest_controlled = typing_latest_record(controlled_records)
    latest_controlled_text = typing_latest_record(controlled_text_records)
    if latest_natural_text:
        status = "natural_browser_text_observed"
    elif latest_natural:
        status = "natural_browser_metadata_observed"
    elif latest_controlled_text:
        status = "controlled_browser_text_probe_observed"
    elif latest_controlled:
        status = "controlled_browser_probe_observed"
    else:
        status = "no_browser_records"

    return {
        "schema": f"{schema_prefix}_typing_browser_input_recency_v1",
        "status": status,
        "records": len(browser_records),
        "text_records": len(text_records),
        "natural_records": len(natural_records),
        "natural_text_records": len(natural_text_records),
        "controlled_probe_records": len(controlled_records),
        "controlled_text_records": len(controlled_text_records),
        "explicit_webextension_records": len(explicit_records),
        "atspi_browser_fallback_records": len(atspi_browser_records),
        "latest_any": brief(latest_any),
        "latest_natural": brief(latest_natural),
        "latest_natural_text": brief(latest_natural_text),
        "latest_controlled_probe": brief(latest_controlled),
        "latest_controlled_text": brief(latest_controlled_text),
        "latest_explicit_webextension": brief(latest_explicit),
        "latest_atspi_browser_fallback": brief(latest_atspi),
        "policy": {
            "text_omitted": True,
            "url_query_fragment_omitted": True,
            "facts_only": True,
            "raw_keylogging": False,
            "effective_causal_from_process_readmodel": True,
        },
    }


def typing_process_continuity_projects(
    records: list[dict[str, Any]],
    policy: Mapping[str, Any] | None,
    *,
    home_path: str | None = None,
    schema_prefix: str = "abyss_machine",
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    policy_data = policy if isinstance(policy, Mapping) else {}
    causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}
    max_age = max(60.0, float(causal_policy.get("max_interaction_continuity_age_sec") or 7200.0))
    continuity: dict[str, dict[str, Any]] = {}
    last_by_interaction: dict[str, dict[str, Any]] = {}
    promoted = 0
    backfilled = 0
    blocked_age = 0
    interaction_records = 0
    chronological = sorted(
        enumerate(records),
        key=lambda item: (typing_process_generated_epoch(item[1]), -item[0]),
    )
    for _, record in chronological:
        if not isinstance(record, dict):
            continue
        event_id = str(record.get("event_id") or "")
        source_adapter = str(record.get("source_adapter") or "unknown")
        causal = record.get("causal_context") if isinstance(record.get("causal_context"), dict) else {}
        where = causal.get("where") if isinstance(causal.get("where"), dict) else {}
        recipient = causal.get("recipient") if isinstance(causal.get("recipient"), dict) else {}
        base_project = typing_process_project_for_record(record, where, policy_data)
        context_anchor = typing_process_context_anchor(
            source_adapter,
            where,
            base_project,
            home_path=home_path,
            schema_prefix=schema_prefix,
        )
        recipient = typing_process_recipient_for_context(source_adapter, recipient, where, context_anchor)
        interaction = typing_process_interaction_for_record(record, where)
        keys = typing_process_interaction_keys(interaction, recipient, context_anchor)
        if keys:
            interaction_records += 1
        event_ts = typing_process_generated_epoch(record)
        if base_project.get("id"):
            if event_id:
                continuity[event_id] = base_project
            for key in keys:
                last_by_interaction[key] = {
                    "project": base_project,
                    "event_id": event_id,
                    "generated_at": record.get("generated_at"),
                    "timestamp": event_ts,
                    "interaction": interaction,
                    "interaction_key": key,
                }
            continue
        if not keys:
            continue
        previous = None
        for key in keys:
            previous = last_by_interaction.get(key)
            if previous:
                break
        if not previous:
            continue
        age = max(0.0, event_ts - float(previous.get("timestamp") or 0.0)) if event_ts else 0.0
        if event_ts and age > max_age:
            blocked_age += 1
            continue
        previous_project = previous.get("project") if isinstance(previous.get("project"), dict) else {}
        if not previous_project.get("id"):
            continue
        inherited = dict(previous_project)
        inherited["basis"] = "interaction_continuity"
        inherited["confidence"] = "recent_same_interaction_project_context"
        inherited["readmodel_promoted_from"] = "same_interaction_recent_project"
        inherited["source_event_id"] = previous.get("event_id")
        inherited["source_generated_at"] = previous.get("generated_at")
        inherited["source_age_sec"] = round(age, 3) if event_ts else None
        inherited["source_interaction_key"] = previous.get("interaction_key")
        inherited["stores_extra_text"] = False
        if event_id:
            continuity[event_id] = inherited
            promoted += 1
    next_by_interaction: dict[str, dict[str, Any]] = {}
    for _, record in reversed(chronological):
        if not isinstance(record, dict):
            continue
        event_id = str(record.get("event_id") or "")
        source_adapter = str(record.get("source_adapter") or "unknown")
        causal = record.get("causal_context") if isinstance(record.get("causal_context"), dict) else {}
        where = causal.get("where") if isinstance(causal.get("where"), dict) else {}
        recipient = causal.get("recipient") if isinstance(causal.get("recipient"), dict) else {}
        base_project = typing_process_project_for_record(record, where, policy_data)
        context_anchor = typing_process_context_anchor(
            source_adapter,
            where,
            base_project,
            home_path=home_path,
            schema_prefix=schema_prefix,
        )
        recipient = typing_process_recipient_for_context(source_adapter, recipient, where, context_anchor)
        interaction = typing_process_interaction_for_record(record, where)
        keys = typing_process_interaction_keys(interaction, recipient, context_anchor)
        event_ts = typing_process_generated_epoch(record)
        if base_project.get("id"):
            for key in keys:
                next_by_interaction[key] = {
                    "project": base_project,
                    "event_id": event_id,
                    "generated_at": record.get("generated_at"),
                    "timestamp": event_ts,
                    "interaction": interaction,
                    "interaction_key": key,
                }
            continue
        if event_id and event_id in continuity:
            continue
        if not keys:
            continue
        next_item = None
        for key in keys:
            next_item = next_by_interaction.get(key)
            if next_item:
                break
        if not next_item:
            continue
        age = max(0.0, float(next_item.get("timestamp") or 0.0) - event_ts) if event_ts else 0.0
        if event_ts and age > max_age:
            blocked_age += 1
            continue
        next_project = next_item.get("project") if isinstance(next_item.get("project"), dict) else {}
        if not next_project.get("id"):
            continue
        inherited = dict(next_project)
        inherited["basis"] = "interaction_continuity"
        inherited["confidence"] = "nearby_same_interaction_project_context"
        inherited["readmodel_promoted_from"] = "same_interaction_future_project"
        inherited["source_event_id"] = next_item.get("event_id")
        inherited["source_generated_at"] = next_item.get("generated_at")
        inherited["source_age_sec"] = round(age, 3) if event_ts else None
        inherited["source_interaction_key"] = next_item.get("interaction_key")
        inherited["stores_extra_text"] = False
        if event_id:
            continuity[event_id] = inherited
            promoted += 1
            backfilled += 1
    return continuity, {
        "interaction_records": interaction_records,
        "continuity_promoted": promoted,
        "continuity_backfilled": backfilled,
        "continuity_blocked_by_age": blocked_age,
        "continuity_max_age_sec": max_age,
    }


def typing_causal_awareness_for_event(
    *,
    source_adapter: str,
    status: str,
    gate: Mapping[str, Any] | None,
    text_payload: Mapping[str, Any] | None,
    project_id: str,
    project_binding: Mapping[str, Any] | None,
    recipient: Mapping[str, Any] | None,
    task_binding: str,
    context_anchor: Mapping[str, Any] | None,
    interaction: Mapping[str, Any] | None,
    surface_kind: str,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    gate_data = gate if isinstance(gate, Mapping) else {}
    text_data = text_payload if isinstance(text_payload, Mapping) else {}
    project_binding_data = project_binding if isinstance(project_binding, Mapping) else {}
    recipient_data = recipient if isinstance(recipient, Mapping) else {}
    context_anchor_data = context_anchor if isinstance(context_anchor, Mapping) else {}
    interaction_data = interaction if isinstance(interaction, Mapping) else {}
    axes: dict[str, dict[str, Any]] = {}
    gaps: list[dict[str, Any]] = []

    def axis(name: str, state: str, basis: str, evidence: dict[str, Any] | None = None) -> None:
        axes[name] = {
            "state": state,
            "basis": basis,
            "evidence": evidence or {},
            "stores_extra_text": False,
        }
        if state in {"missing", "partial"}:
            gaps.append({
                "axis": name,
                "state": state,
                "basis": basis,
            })

    text_captured = bool(text_data.get("captured"))
    text_length = _safe_int(text_data.get("text_length"), 0)
    gate_decision = str(gate_data.get("decision") or "missing")
    privacy_guarded_context = bool(
        source_adapter.startswith("atspi_")
        and (
            status in {"metadata_only", "skipped", "skipped_by_capture_gate"}
            or gate_decision in {"metadata_only", "skip", "hard_skip"}
        )
    )
    if text_captured and text_data.get("text_sha256"):
        axis("what_written", "known", "safe_committed_text_captured", {"text_length": text_length, "text_sha256": text_data.get("text_sha256")})
    elif status in {"metadata_only", "skipped_by_capture_gate"} or gate_decision in {"metadata_only", "skip"}:
        axis("what_written", "guarded", str(text_data.get("metadata_only_reason") or gate_data.get("confidence") or "metadata_only_privacy_gate"), {"text_length": text_length})
    else:
        axis("what_written", "missing", "text_not_captured_or_hashed", {"status": status})

    if context_anchor_data.get("id") and context_anchor_data.get("id") != "unknown":
        axis("where_entered", "known", str(context_anchor_data.get("confidence") or "context_anchor"), {"kind": context_anchor_data.get("kind"), "id": context_anchor_data.get("id")})
    elif surface_kind and surface_kind != "missing":
        axis("where_entered", "partial", "surface_kind_only", {"kind": surface_kind})
    else:
        axis("where_entered", "missing", "missing_context_anchor")

    recipient_kind = str(recipient_data.get("kind") or "missing")
    recipient_id = str(recipient_data.get("id") or recipient_data.get("name") or "")
    if recipient_kind != "missing" and recipient_id:
        axis("who_received", "known", str(recipient_data.get("confidence") or "recipient_identity"), {"kind": recipient_kind, "id": recipient_data.get("id"), "route": recipient_data.get("route")})
    elif recipient_kind != "missing":
        axis("who_received", "partial", "recipient_kind_only", {"kind": recipient_kind})
    else:
        axis("who_received", "missing", "missing_recipient")

    if recipient_kind == "ai_counterpart" and recipient_data.get("id") and (recipient_data.get("provider") or recipient_data.get("product")):
        axis("who_is_who", "known", "known_ai_counterpart", {"id": recipient_data.get("id"), "provider": recipient_data.get("provider"), "product": recipient_data.get("product")})
    elif recipient_kind in {"codex_session", "file", "shell", "editor_extension", "browser_extension", "typing_cli"} and recipient_id:
        axis("who_is_who", "known", f"{recipient_kind}_identity", {"kind": recipient_kind, "id": recipient_data.get("id")})
    elif recipient_kind == "focused_application" and context_anchor_data.get("kind") in {"project_root", "url_origin", "privacy_guarded"} and context_anchor_data.get("id"):
        axis(
            "who_is_who",
            "known",
            f"focused_application_{context_anchor_data.get('kind')}_identity",
            {"id": recipient_data.get("id"), "context_anchor_kind": context_anchor_data.get("kind"), "context_anchor_id": context_anchor_data.get("id")},
        )
    elif recipient_kind == "focused_application" and recipient_id and privacy_guarded_context:
        axis(
            "who_is_who",
            "guarded",
            "metadata_only_focused_application_identity",
            {
                "id": recipient_data.get("id"),
                "context_anchor_kind": context_anchor_data.get("kind"),
                "gate_decision": gate_decision,
            },
        )
    elif recipient_kind == "focused_application" and recipient_id:
        axis("who_is_who", "partial", "focused_application_not_entity_identity", {"id": recipient_data.get("id")})
    else:
        axis("who_is_who", "missing", "recipient_entity_identity_missing")

    if task_binding and task_binding != "unbound":
        axis("task_context", "known", task_binding, {"binding": task_binding})
    else:
        axis("task_context", "missing", "unbound_task")

    if project_id and project_id != "unknown":
        axis("project_context", "known", str(project_binding_data.get("basis") or "project_bound"), {"id": project_id, "confidence": project_binding_data.get("confidence")})
    elif privacy_guarded_context:
        axis(
            "project_context",
            "guarded",
            "metadata_only_context_does_not_widen_project_binding",
            {
                "gate_decision": gate_decision,
                "gate_confidence": gate_data.get("confidence"),
                "context_anchor_kind": context_anchor_data.get("kind"),
                "context_anchor_id": context_anchor_data.get("id"),
            },
        )
    else:
        axis("project_context", "missing", str(project_binding_data.get("confidence") or "no_project_path_topic_or_continuity_signal"))

    if interaction_data.get("id") and str(interaction_data.get("kind") or "missing") != "missing":
        axis("interaction_context", "known", str(interaction_data.get("confidence") or "interaction_identity"), {"kind": interaction_data.get("kind"), "id": interaction_data.get("id")})
    else:
        axis("interaction_context", "missing", "missing_interaction_identity")

    if gate_decision != "missing":
        axis("privacy_gate", "known", gate_decision, {"decision": gate_decision, "confidence": gate_data.get("confidence")})
    else:
        axis("privacy_gate", "missing", "missing_capture_gate")

    states = [str(item.get("state") or "missing") for item in axes.values()]
    known = states.count("known")
    guarded = states.count("guarded")
    partial = states.count("partial")
    missing = states.count("missing")
    score_denominator = max(1, len(states) - guarded)
    score = round((known + partial * 0.5) / score_denominator, 4)
    return {
        "schema": f"{schema_prefix}_typing_causal_awareness_event_v1",
        "state": "complete" if missing == 0 and partial == 0 else ("guarded" if missing == 0 else "incomplete"),
        "score": score,
        "known_axes": known,
        "guarded_axes": guarded,
        "partial_axes": partial,
        "missing_axes": missing,
        "axes": axes,
        "gaps": gaps,
        "stores_extra_text": False,
    }


def typing_causal_context_readmodel_from_records(
    records: Iterable[Any],
    parse_errors: list[dict[str, Any]],
    policy: Mapping[str, Any] | None,
    *,
    generated_at: str,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
    home_path: str | None = None,
) -> dict[str, Any]:
    raw_valid_records = [item for item in records if isinstance(item, dict)]
    valid_records, dedupe_summary = typing_process_unique_records(raw_valid_records)
    policy_data = policy if isinstance(policy, Mapping) else {}
    parse_error_items = [item for item in parse_errors if isinstance(item, dict)]
    continuity_projects, continuity_summary = typing_process_continuity_projects(
        valid_records,
        policy_data,
        home_path=home_path,
        schema_prefix=schema_prefix,
    )
    entries: list[dict[str, Any]] = []
    by_recipient = collections.Counter()
    by_project = collections.Counter()
    by_project_basis = collections.Counter()
    by_interaction_kind = collections.Counter()
    by_context_anchor_kind = collections.Counter()
    task_bound = 0
    context_bound = 0
    task_anchor_bound = 0
    correlation_bound = 0
    missing = 0
    missing_context_anchor = 0
    missing_task_anchor = 0
    causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}

    for record in reversed(valid_records):
        causal = record.get("causal_context") if isinstance(record.get("causal_context"), Mapping) else {}
        if not causal:
            missing += 1
        correlation = causal.get("correlation") if isinstance(causal.get("correlation"), Mapping) else {}
        recipient = causal.get("recipient") if isinstance(causal.get("recipient"), Mapping) else {}
        task = causal.get("task") if isinstance(causal.get("task"), Mapping) else {}
        where = causal.get("where") if isinstance(causal.get("where"), Mapping) else {}
        base_project = typing_process_project_for_record(record, where, policy_data)
        event_id = str(record.get("event_id") or "")
        project = continuity_projects.get(event_id) if event_id in continuity_projects else base_project
        project_binding = typing_causal_project_binding_summary(project, "no_project_path_topic_or_continuity_signal")
        source_adapter = str(record.get("source_adapter") or "unknown")
        context_anchor = typing_process_context_anchor(
            source_adapter,
            where,
            project,
            home_path=home_path,
            schema_prefix=schema_prefix,
        )
        recipient = typing_process_recipient_for_context(source_adapter, recipient, where, context_anchor)
        interaction = typing_process_interaction_for_record(record, where)
        where_with_anchor = {**where, "context_anchor": context_anchor}
        recipient_kind = str(recipient.get("kind") or "missing")
        project_id = str(project.get("id") or "unknown")
        context_anchor_id = str(context_anchor.get("id") or "unknown")
        context_anchor_kind = str(context_anchor.get("kind") or "unknown")
        interaction_kind = str(interaction.get("kind") or "missing")
        by_recipient[recipient_kind] += 1
        by_project[project_id] += 1
        by_project_basis[str(project_binding.get("basis") or "unknown")] += 1
        by_interaction_kind[interaction_kind] += 1
        by_context_anchor_kind[context_anchor_kind] += 1
        source_active_changes = task.get("active_changes") if isinstance(task.get("active_changes"), list) else []
        active_changes = (
            source_active_changes
            if causal_policy.get("contextual_active_change_task_binding") is True
            else [item for item in source_active_changes if isinstance(item, dict) and item.get("match") == "surface_match"]
        )
        task_anchor = task.get("context_anchor") if isinstance(task.get("context_anchor"), Mapping) else {}
        if not task_anchor.get("id") or (
            str(task_anchor.get("kind") or "") == "active_change"
            and causal_policy.get("contextual_active_change_task_binding") is not True
            and not active_changes
        ):
            if active_changes and isinstance(active_changes[0], dict):
                first_change = active_changes[0]
                task_anchor = {
                    "kind": "active_change",
                    "id": str(first_change.get("id") or "active_change"),
                    "label": first_change.get("title") or first_change.get("id"),
                    "confidence": first_change.get("match") or "active_machine_change",
                    "stores_extra_text": False,
                }
            elif project_id != "unknown":
                task_anchor = {
                    "kind": "project_root",
                    "id": f"project:{project_id}",
                    "label": project_id,
                    "confidence": "project_root_match",
                    "stores_extra_text": False,
                }
            elif context_anchor_id != "unknown":
                task_anchor = {
                    "kind": context_anchor.get("kind"),
                    "id": context_anchor.get("id"),
                    "label": context_anchor.get("label"),
                    "confidence": context_anchor.get("confidence"),
                    "stores_extra_text": False,
                }
            else:
                task_anchor = {
                    "kind": "unknown",
                    "id": "unknown",
                    "label": "unknown",
                    "confidence": "missing_observable_context",
                    "stores_extra_text": False,
                }
        task_with_anchor = {**task, "context_anchor": task_anchor}
        if not active_changes:
            task_with_anchor["active_changes"] = []
        if project.get("id"):
            task_with_anchor["project"] = project
            if str(task_with_anchor.get("binding") or "") in {"", "missing", "unbound", "active_change", "context_anchor"}:
                task_with_anchor["binding"] = "project_or_surface_context"
        if active_changes or project_id != "unknown" or context_anchor_id != "unknown":
            task_bound += 1
        if context_anchor_id != "unknown":
            context_bound += 1
        else:
            missing_context_anchor += 1
        if task_anchor.get("id") and task_anchor.get("id") != "unknown":
            task_anchor_bound += 1
        else:
            missing_task_anchor += 1
        if not correlation:
            correlation = {
                "id": f"typing-causal-readmodel:{event_id}" if event_id else None,
                "timeline_key": f"{record.get('generated_at')}|{event_id}",
                "event_id": event_id or None,
                "source_adapter": record.get("source_adapter"),
                "recipient_id": recipient.get("id"),
                "recipient_kind": recipient.get("kind"),
                "interaction_id": interaction.get("id"),
                "context_anchor_id": context_anchor_id,
                "task_anchor_id": task_anchor.get("id"),
                "project_id": project_id if project_id != "unknown" else None,
                "time_basis": "event_generated_at",
                "stores_text": False,
                "readmodel_backfill": True,
            }
        if correlation.get("id"):
            correlation_bound += 1
        entries.append({
            "event_id": record.get("event_id"),
            "generated_at": record.get("generated_at"),
            "status": record.get("status"),
            "source_adapter": record.get("source_adapter"),
            "correlation": correlation,
            "where": {**where_with_anchor, "project": project if project else None, "project_binding": project_binding, "interaction": interaction},
            "recipient": recipient,
            "task": task_with_anchor,
            "policy": causal.get("policy") if isinstance(causal.get("policy"), Mapping) else {},
        })

    return {
        "schema": f"{schema_prefix}_typing_causal_context_readmodel_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not parse_error_items,
        "summary": {
            "returned": len(entries),
            "raw_records_scanned": len(raw_valid_records),
            "duplicate_event_rows_collapsed": dedupe_summary.get("duplicate_event_rows_collapsed"),
            "parse_errors": len(parse_error_items),
            "missing_causal_context": missing,
            "task_bound": task_bound,
            "context_bound": context_bound,
            "task_anchor_bound": task_anchor_bound,
            "correlation_bound": correlation_bound,
            "missing_context_anchor": missing_context_anchor,
            "missing_task_anchor": missing_task_anchor,
            "by_recipient": dict(sorted(by_recipient.items())),
            "by_project": dict(sorted(by_project.items())),
            "by_project_basis": dict(sorted(by_project_basis.items())),
            "by_interaction_kind": dict(sorted(by_interaction_kind.items())),
            "by_context_anchor_kind": dict(sorted(by_context_anchor_kind.items())),
            "continuity_promoted": continuity_summary.get("continuity_promoted"),
        },
        "entries": entries,
        "dedupe": dedupe_summary,
        "continuity": continuity_summary,
        "parse_errors": parse_error_items[:20],
        "policy": {
            "facts_only": True,
            "stores_text": False,
            "automatic_action": False,
            "intent_claim": False,
        },
    }


def typing_process_from_records(
    records: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    policy: Mapping[str, Any],
    *,
    generated_at: str,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
    home_path: str | None = None,
) -> dict[str, Any]:
    raw_valid_records = [item for item in records if isinstance(item, dict)]
    valid_records, dedupe_summary = typing_process_unique_records(raw_valid_records)
    continuity_projects, continuity_summary = typing_process_continuity_projects(
        valid_records,
        policy,
        home_path=home_path,
        schema_prefix=schema_prefix,
    )
    lanes_by_key: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    by_adapter = collections.Counter()
    by_status = collections.Counter()
    by_gate = collections.Counter()
    by_project = collections.Counter()
    by_project_basis = collections.Counter()
    by_recipient = collections.Counter()
    by_surface = collections.Counter()
    by_task_binding = collections.Counter()
    by_context_anchor = collections.Counter()
    by_context_anchor_kind = collections.Counter()
    by_interaction_kind = collections.Counter()
    by_awareness_state = collections.Counter()
    awareness_axis_states: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    awareness_gap_counter = collections.Counter()
    awareness_gap_by_adapter: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    awareness_score_total = 0.0
    missing_causal: list[str] = []
    missing_gate: list[str] = []
    missing_recipient: list[str] = []
    missing_surface: list[str] = []
    missing_context_anchor: list[str] = []
    unbound_task: list[str] = []
    unknown_project: list[str] = []
    context_anchor_without_project: list[str] = []
    policy_violations: list[str] = []
    task_bound_events = 0
    active_change_bound_events = 0
    policy_data = policy if isinstance(policy, Mapping) else {}

    for record in valid_records:
        event_id = str(record.get("event_id") or "")
        source_adapter = str(record.get("source_adapter") or "unknown")
        status = str(record.get("status") or "unknown")
        gate = record.get("capture_gate") if isinstance(record.get("capture_gate"), dict) else {}
        causal = record.get("causal_context") if isinstance(record.get("causal_context"), dict) else {}
        where = causal.get("where") if isinstance(causal.get("where"), dict) else {}
        recipient = causal.get("recipient") if isinstance(causal.get("recipient"), dict) else {}
        task = causal.get("task") if isinstance(causal.get("task"), dict) else {}
        base_project = typing_process_project_for_record(record, where, policy_data)
        project = continuity_projects.get(event_id) if event_id in continuity_projects else base_project
        text_payload = record.get("text") if isinstance(record.get("text"), dict) else {}
        event_policy = record.get("policy") if isinstance(record.get("policy"), dict) else {}

        project_id = str(project.get("id") or "unknown")
        project_binding = typing_causal_project_binding_summary(project, "no_project_path_topic_or_continuity_signal")
        surface_kind = str(where.get("kind") or "missing")
        source_task_binding = str(task.get("binding") or "missing")
        source_active_changes = task.get("active_changes") if isinstance(task.get("active_changes"), list) else []
        causal_policy = policy_data.get("causal_context") if isinstance(policy_data.get("causal_context"), Mapping) else {}
        if causal_policy.get("contextual_active_change_task_binding") is True:
            active_changes = source_active_changes
        else:
            active_changes = [
                item for item in source_active_changes
                if isinstance(item, dict) and item.get("match") == "surface_match"
            ]
        active_ids = [str(item.get("id")) for item in active_changes if isinstance(item, dict) and item.get("id")]
        context_anchor = typing_process_context_anchor(
            source_adapter,
            where,
            project,
            home_path=home_path,
            schema_prefix=schema_prefix,
        )
        recipient = typing_process_recipient_for_context(source_adapter, recipient, where, context_anchor)
        interaction = typing_process_interaction_for_record(record, where)
        context_anchor_id = str(context_anchor.get("id") or "unknown")
        context_anchor_kind = str(context_anchor.get("kind") or "unknown")
        context_bound = context_anchor_id != "unknown"
        recipient_kind = str(recipient.get("kind") or "missing")
        recipient_id = str(recipient.get("id") or recipient.get("name") or recipient_kind)
        interaction_kind = str(interaction.get("kind") or "missing")
        if active_ids:
            task_binding = "active_change"
        elif project_id != "unknown":
            task_binding = source_task_binding if source_task_binding not in {"missing", "unbound", "active_change", "context_anchor"} else "project_or_surface_context"
        elif context_bound:
            task_binding = "context_anchor"
        else:
            task_binding = "unbound"
        task_bound = task_binding != "unbound"
        task_key = active_ids[0] if active_ids else (project_id if project_id != "unknown" else (context_anchor_id if context_bound else task_binding))
        lane_id = typing_process_lane_id([project_id, task_key, context_anchor_id, recipient_kind, recipient_id, surface_kind])
        awareness = typing_causal_awareness_for_event(
            source_adapter=source_adapter,
            status=status,
            gate=gate,
            text_payload=text_payload,
            project_id=project_id,
            project_binding=project_binding,
            recipient=recipient,
            task_binding=task_binding,
            context_anchor=context_anchor,
            interaction=interaction,
            surface_kind=surface_kind,
            schema_prefix=schema_prefix,
        )

        by_adapter[source_adapter] += 1
        by_status[status] += 1
        by_gate[str(gate.get("decision") or "missing")] += 1
        by_project[project_id] += 1
        by_project_basis[str(project_binding.get("basis") or "unknown")] += 1
        by_recipient[recipient_kind] += 1
        by_surface[surface_kind] += 1
        by_task_binding[task_binding] += 1
        by_context_anchor[context_anchor_id] += 1
        by_context_anchor_kind[context_anchor_kind] += 1
        by_interaction_kind[interaction_kind] += 1
        by_awareness_state[str(awareness.get("state") or "missing")] += 1
        awareness_score_total += float(awareness.get("score") or 0.0)
        axes = awareness.get("axes") if isinstance(awareness.get("axes"), dict) else {}
        for axis_name, axis_data in axes.items():
            if isinstance(axis_data, dict):
                awareness_axis_states[str(axis_name)][str(axis_data.get("state") or "missing")] += 1
        for gap in awareness.get("gaps") if isinstance(awareness.get("gaps"), list) else []:
            if not isinstance(gap, dict):
                continue
            gap_key = f"{gap.get('axis')}:{gap.get('state')}"
            awareness_gap_counter[gap_key] += 1
            awareness_gap_by_adapter[source_adapter][gap_key] += 1
        if active_ids:
            active_change_bound_events += 1
        if task_bound:
            task_bound_events += 1

        if not causal:
            missing_causal.append(event_id)
        if not gate:
            missing_gate.append(event_id)
        if recipient_kind == "missing":
            missing_recipient.append(event_id)
        if surface_kind == "missing":
            missing_surface.append(event_id)
        if not context_bound:
            missing_context_anchor.append(event_id)
        if project_id == "unknown":
            unknown_project.append(event_id)
            if context_bound:
                context_anchor_without_project.append(event_id)
        if not task_bound:
            unbound_task.append(event_id)
        if (
            event_policy.get("raw_keylogging") is not False
            or event_policy.get("password_fields_captured") is not False
            or event_policy.get("automatic_action") is not False
        ):
            policy_violations.append(event_id)

        entry = {
            "event_id": event_id,
            "generated_at": record.get("generated_at"),
            "source_adapter": source_adapter,
            "status": status,
            "capture_gate_decision": gate.get("decision"),
            "capture_gate_confidence": gate.get("confidence"),
            "text_sha256": text_payload.get("text_sha256"),
            "text_length": text_payload.get("text_length"),
            "text_captured": bool(text_payload.get("captured")),
            "text_omitted": True,
            "lane_id": lane_id,
            "where": {
                "kind": surface_kind,
                "app": where.get("app"),
                "window_title": where.get("window_title"),
                "url": where.get("url"),
                "path": where.get("path"),
                "project": project if project else None,
                "project_binding": project_binding,
                "context_anchor": context_anchor,
                "interaction": interaction,
            },
            "recipient": {
                "kind": recipient_kind,
                "route": recipient.get("route"),
                "id": recipient.get("id"),
                "name": recipient.get("name"),
                "confidence": recipient.get("confidence"),
            },
            "task": {
                "binding": task_binding,
                "source_binding": source_task_binding,
                "active_change_ids": active_ids,
                "project_id": project_id,
                "project_binding": project_binding,
                "context_anchor_id": context_anchor_id,
                "context_anchor_kind": context_anchor_kind,
                "interaction_id": interaction.get("id"),
                "interaction_kind": interaction_kind,
                "context_bound": context_bound,
                "task_bound": task_bound,
                "confidence": task.get("confidence"),
            },
            "awareness": awareness,
        }
        entries.append(entry)

        lane = lanes_by_key.setdefault(
            lane_id,
            {
                "lane_id": lane_id,
                "project_id": project_id,
                "task_key": task_key,
                "task_binding": task_binding,
                "context_anchor": context_anchor,
                "interaction": interaction,
                "recipient": entry["recipient"],
                "surface_kind": surface_kind,
                "records": 0,
                "captured": 0,
                "metadata_only": 0,
                "skipped": 0,
                "adapters": collections.Counter(),
                "statuses": collections.Counter(),
                "capture_gate_decisions": collections.Counter(),
                "active_change_ids": set(),
                "first_event_at": record.get("generated_at"),
                "latest_event_at": record.get("generated_at"),
                "latest_event_id": event_id,
                "sample_event_ids": [],
            },
        )
        lane["records"] += 1
        if status == "captured":
            lane["captured"] += 1
        elif status == "metadata_only":
            lane["metadata_only"] += 1
        elif status == "skipped_by_capture_gate":
            lane["skipped"] += 1
        lane["adapters"][source_adapter] += 1
        lane["statuses"][status] += 1
        lane["capture_gate_decisions"][str(gate.get("decision") or "missing")] += 1
        event_time = str(record.get("generated_at") or "")
        if event_time and (not lane.get("first_event_at") or event_time < str(lane.get("first_event_at") or "")):
            lane["first_event_at"] = record.get("generated_at")
        if event_time and (not lane.get("latest_event_at") or event_time > str(lane.get("latest_event_at") or "")):
            lane["latest_event_at"] = record.get("generated_at")
            lane["latest_event_id"] = event_id
        if len(lane["sample_event_ids"]) < 5 and event_id:
            lane["sample_event_ids"].append(event_id)
        for active_id in active_ids:
            lane["active_change_ids"].add(active_id)

    quality_gaps: list[dict[str, Any]] = []
    if parse_errors:
        quality_gaps.append({"level": "fail", "key": "jsonl_parse_errors", "count": len(parse_errors)})
    if missing_causal:
        quality_gaps.append({"level": "fail", "key": "missing_causal_context", "count": len(missing_causal), "event_ids": missing_causal[:20]})
    if missing_gate:
        quality_gaps.append({"level": "fail", "key": "missing_capture_gate", "count": len(missing_gate), "event_ids": missing_gate[:20]})
    if policy_violations:
        quality_gaps.append({"level": "fail", "key": "policy_shape_violations", "count": len(policy_violations), "event_ids": policy_violations[:20]})
    if missing_recipient:
        quality_gaps.append({"level": "watch", "key": "missing_recipient", "count": len(missing_recipient), "event_ids": missing_recipient[:20]})
    if missing_surface:
        quality_gaps.append({"level": "watch", "key": "missing_surface", "count": len(missing_surface), "event_ids": missing_surface[:20]})
    if missing_context_anchor:
        quality_gaps.append({"level": "watch", "key": "missing_context_anchor", "count": len(missing_context_anchor), "event_ids": missing_context_anchor[:20]})
    if unbound_task:
        quality_gaps.append({"level": "info", "key": "unbound_task_context", "count": len(unbound_task), "event_ids": unbound_task[:20]})
    context_notes: list[dict[str, Any]] = []
    if context_anchor_without_project:
        context_notes.append({
            "level": "info",
            "key": "context_anchor_without_project",
            "count": len(context_anchor_without_project),
            "event_ids": context_anchor_without_project[:20],
        })

    lanes: list[dict[str, Any]] = []
    for lane in lanes_by_key.values():
        lanes.append({
            **{key: value for key, value in lane.items() if key not in {"adapters", "statuses", "capture_gate_decisions", "active_change_ids"}},
            "adapters": dict(sorted(lane["adapters"].items())),
            "statuses": dict(sorted(lane["statuses"].items())),
            "capture_gate_decisions": dict(sorted(lane["capture_gate_decisions"].items())),
            "active_change_ids": sorted(lane["active_change_ids"]),
        })
    lanes.sort(key=lambda item: str(item.get("latest_event_at") or ""), reverse=True)

    fail_gaps = [item for item in quality_gaps if item.get("level") == "fail"]
    watch_gaps = [item for item in quality_gaps if item.get("level") == "watch"]
    status = "failed" if fail_gaps else ("processed_with_context_gaps" if watch_gaps or unbound_task else "processed")
    awareness_axis_summary = {
        axis: dict(sorted(counter.items()))
        for axis, counter in sorted(awareness_axis_states.items())
    }
    awareness_gap_by_adapter_summary = {
        adapter: dict(counter.most_common(12))
        for adapter, counter in sorted(awareness_gap_by_adapter.items())
    }
    awareness_average_score = round(awareness_score_total / len(valid_records), 4) if valid_records else 0.0
    return {
        "schema": f"{schema_prefix}_typing_process_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not fail_gaps and policy_data.get("ok") is True,
        "status": status,
        "summary": {
            "raw_records_scanned": len(raw_valid_records),
            "records_processed": len(valid_records),
            "duplicate_event_rows_collapsed": dedupe_summary.get("duplicate_event_rows_collapsed"),
            "lanes": len(lanes),
            "captured": sum(1 for item in valid_records if item.get("status") == "captured"),
            "metadata_only": sum(1 for item in valid_records if item.get("status") == "metadata_only"),
            "skipped": sum(1 for item in valid_records if item.get("status") == "skipped_by_capture_gate"),
            "task_bound": task_bound_events,
            "active_change_bound": active_change_bound_events,
            "project_bound": len(valid_records) - len(unknown_project),
            "context_bound": len(valid_records) - len(missing_context_anchor),
            "missing_context_anchor": len(missing_context_anchor),
            "unknown_project": len(unknown_project),
            "context_anchor_without_project": len(context_anchor_without_project),
            "unbound_task": len(unbound_task),
            "quality_gaps": len(quality_gaps),
            "context_notes": len(context_notes),
            "fail_gaps": len(fail_gaps),
            "watch_gaps": len(watch_gaps),
            "interaction_records": continuity_summary.get("interaction_records"),
            "continuity_promoted": continuity_summary.get("continuity_promoted"),
            "awareness_average_score": awareness_average_score,
            "awareness_complete": int(by_awareness_state.get("complete", 0)),
            "awareness_guarded": int(by_awareness_state.get("guarded", 0)),
            "awareness_incomplete": int(by_awareness_state.get("incomplete", 0)),
        },
        "by_adapter": dict(sorted(by_adapter.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_capture_gate_decision": dict(sorted(by_gate.items())),
        "by_project": dict(sorted(by_project.items())),
        "by_project_basis": dict(sorted(by_project_basis.items())),
        "by_recipient": dict(sorted(by_recipient.items())),
        "by_surface_kind": dict(sorted(by_surface.items())),
        "by_task_binding": dict(sorted(by_task_binding.items())),
        "by_interaction_kind": dict(sorted(by_interaction_kind.items())),
        "by_awareness_state": dict(sorted(by_awareness_state.items())),
        "by_context_anchor_kind": dict(sorted(by_context_anchor_kind.items())),
        "by_context_anchor": dict(by_context_anchor.most_common(40)),
        "awareness": {
            "schema": f"{schema_prefix}_typing_causal_awareness_summary_v1",
            "records": len(valid_records),
            "average_score": awareness_average_score,
            "by_state": dict(sorted(by_awareness_state.items())),
            "axis_states": awareness_axis_summary,
            "top_gaps": dict(awareness_gap_counter.most_common(20)),
            "gaps_by_adapter": awareness_gap_by_adapter_summary,
            "policy": {
                "stores_extra_text": False,
                "facts_only": True,
                "intent_claim": False,
                "widens_capture": False,
            },
            "non_claims": [
                "Awareness scores describe available evidence axes, not final intent.",
                "Guarded content is intentionally omitted by privacy policy and is counted separately from missing evidence.",
            ],
        },
        "lanes": lanes[:80],
        "recent_entries": entries[:80],
        "quality_gaps": quality_gaps,
        "context_notes": context_notes,
        "dedupe": dedupe_summary,
        "continuity": continuity_summary,
        "parse_errors": parse_errors[:20],
        "policy": {
            "facts_only": True,
            "stores_extra_text": False,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "widens_capture": False,
            "internet_access": False,
        },
        "non_claims": [
            "This process readmodel sorts already-stored committed-text events; it does not capture new text.",
            "URL origins, operator-home paths, and application surfaces are context anchors, not project claims.",
            "Unknown project context is exposed separately when a context anchor exists; missing anchors remain quality gaps.",
            "The readmodel omits raw event text and does not authorize action.",
        ],
    }


def _coverage_snapshot_document(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = snapshot.get(key)
    return value if isinstance(value, Mapping) else None


def _coverage_snapshot_error(snapshot: Mapping[str, Any], key: str) -> str | None:
    value = snapshot.get(key)
    return str(value) if value is not None else None


def typing_coverage_document_from_records(
    records: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    policy: Mapping[str, Any],
    *,
    latest: Mapping[str, Any] | None = None,
    generated_at: str,
    coverage_snapshot: Mapping[str, Any] | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
    home_path: str | None = None,
) -> dict[str, Any]:
    snapshot = coverage_snapshot if isinstance(coverage_snapshot, Mapping) else {}
    policy_data = policy if isinstance(policy, Mapping) else {}
    latest_data = latest if isinstance(latest, Mapping) else {}
    valid_records = [item for item in records if isinstance(item, dict)]
    record_count = len(valid_records)
    capture_policy = policy_data.get("capture") if isinstance(policy_data.get("capture"), Mapping) else {}
    gate_policy = _coverage_snapshot_document(snapshot, "capture_gate_policy")
    if gate_policy is None:
        gate_policy = policy_data.get("capture_gate") if isinstance(policy_data.get("capture_gate"), Mapping) else {}
    focused_policy = policy_data.get("focused_snapshot") if isinstance(policy_data.get("focused_snapshot"), Mapping) else {}
    atspi_events_policy = _coverage_snapshot_document(snapshot, "atspi_text_events_policy")
    if atspi_events_policy is None:
        atspi_events_policy = (
            policy_data.get("atspi_text_events")
            if isinstance(policy_data.get("atspi_text_events"), Mapping)
            else {}
        )
    browser_context_inference = _coverage_snapshot_document(snapshot, "browser_context_inference") or {}
    configured_adapters = sorted({str(item) for item in capture_policy.get("allowed_adapters", []) if str(item or "").strip()})
    diagnostic_adapters = sorted({str(item) for item in capture_policy.get("diagnostic_adapters", []) if str(item or "").strip()})
    gate_allow_adapters = sorted({str(item) for item in gate_policy.get("allow_text_source_adapters", []) if str(item or "").strip()})
    by_adapter = collections.Counter(str(item.get("source_adapter") or "unknown") for item in valid_records)
    by_status = collections.Counter(str(item.get("status") or "unknown") for item in valid_records)
    by_gate = collections.Counter(str(nested_get(item, ["capture_gate", "decision"]) or "missing") for item in valid_records)
    by_recipient = collections.Counter(str(nested_get(item, ["causal_context", "recipient", "kind"]) or "missing") for item in valid_records)
    by_project = collections.Counter(str(nested_get(item, ["causal_context", "where", "project", "id"]) or "unknown") for item in valid_records)
    process_readmodel = typing_process_from_records(
        valid_records,
        parse_errors,
        policy_data,
        generated_at=generated_at,
        schema_prefix=schema_prefix,
        version=version,
        home_path=home_path,
    )
    effective_entry_index = typing_process_entry_index(process_readmodel)
    effective_by_recipient = process_readmodel.get("by_recipient") if isinstance(process_readmodel.get("by_recipient"), Mapping) else {}
    effective_by_project = process_readmodel.get("by_project") if isinstance(process_readmodel.get("by_project"), Mapping) else {}
    effective_by_project_basis = process_readmodel.get("by_project_basis") if isinstance(process_readmodel.get("by_project_basis"), Mapping) else {}
    effective_by_interaction_kind = process_readmodel.get("by_interaction_kind") if isinstance(process_readmodel.get("by_interaction_kind"), Mapping) else {}
    saved_text_records = [item for item in valid_records if item.get("source_adapter") == "saved_text_snapshot"]
    live_input_records = [item for item in valid_records if item.get("source_adapter") != "saved_text_snapshot"]
    saved_text_count = len(saved_text_records)
    live_input_count = len(live_input_records)
    saved_text_ratio = round(saved_text_count / record_count, 3) if record_count else 0.0
    live_by_adapter = collections.Counter(str(item.get("source_adapter") or "unknown") for item in live_input_records)
    live_observed_adapters = sorted(live_by_adapter)
    live_dominant_adapter = None
    live_dominant_ratio = 0.0
    if live_by_adapter and live_input_count:
        live_dominant_adapter, live_dominant_count = live_by_adapter.most_common(1)[0]
        live_dominant_ratio = round(live_dominant_count / live_input_count, 3)
    capture_gate_required = sum(1 for item in valid_records if nested_get(item, ["policy", "capture_gate_required"]) is True)
    missing_gate_records = sum(1 for item in valid_records if not isinstance(item.get("capture_gate"), dict))
    focused_latest = _coverage_snapshot_document(snapshot, "focused_latest")
    focused_latest_error = _coverage_snapshot_error(snapshot, "focused_latest_error")
    focused_candidate = focused_latest.get("candidate") if isinstance(focused_latest, Mapping) and isinstance(focused_latest.get("candidate"), Mapping) else {}
    atspi_events_latest = _coverage_snapshot_document(snapshot, "atspi_events_latest")
    atspi_events_latest_error = _coverage_snapshot_error(snapshot, "atspi_events_latest_error")
    editor_extension_latest = _coverage_snapshot_document(snapshot, "editor_extension_latest")
    editor_extension_latest_error = _coverage_snapshot_error(snapshot, "editor_extension_latest_error")
    editor_extension_selftest_latest = _coverage_snapshot_document(snapshot, "editor_extension_selftest_latest")
    editor_extension_selftest_error = _coverage_snapshot_error(snapshot, "editor_extension_selftest_error")
    editor_callback_selftest_latest = _coverage_snapshot_document(snapshot, "editor_callback_selftest_latest")
    editor_callback_selftest_error = _coverage_snapshot_error(snapshot, "editor_callback_selftest_error")
    browser_extension_latest = _coverage_snapshot_document(snapshot, "browser_extension_latest")
    browser_extension_latest_error = _coverage_snapshot_error(snapshot, "browser_extension_latest_error")
    browser_ai_transcript_latest = _coverage_snapshot_document(snapshot, "browser_ai_transcript_latest")
    browser_ai_transcript_latest_error = _coverage_snapshot_error(snapshot, "browser_ai_transcript_latest_error")
    browser_ai_transcript_selftest_latest = _coverage_snapshot_document(snapshot, "browser_ai_transcript_selftest_latest")
    browser_ai_transcript_selftest_error = _coverage_snapshot_error(snapshot, "browser_ai_transcript_selftest_error")
    browser_webextension_selftest_latest = _coverage_snapshot_document(snapshot, "browser_webextension_selftest_latest")
    browser_webextension_selftest_error = _coverage_snapshot_error(snapshot, "browser_webextension_selftest_error")
    browser_atspi_selftest_latest = _coverage_snapshot_document(snapshot, "browser_atspi_selftest_latest")
    browser_atspi_selftest_error = _coverage_snapshot_error(snapshot, "browser_atspi_selftest_error")
    browser_context_selftest_latest = _coverage_snapshot_document(snapshot, "browser_context_selftest_latest")
    browser_context_selftest_error = _coverage_snapshot_error(snapshot, "browser_context_selftest_error")
    browser_atspi_release_selftest_latest = _coverage_snapshot_document(snapshot, "browser_atspi_release_selftest_latest")
    browser_atspi_release_selftest_error = _coverage_snapshot_error(snapshot, "browser_atspi_release_selftest_error")
    generic_gui_selftest_latest = _coverage_snapshot_document(snapshot, "generic_gui_selftest_latest")
    generic_gui_selftest_error = _coverage_snapshot_error(snapshot, "generic_gui_selftest_error")
    browser_privacy_selftest_latest = _coverage_snapshot_document(snapshot, "browser_privacy_selftest_latest")
    browser_privacy_selftest_error = _coverage_snapshot_error(snapshot, "browser_privacy_selftest_error")
    privacy_selftest_latest = _coverage_snapshot_document(snapshot, "privacy_selftest_latest")
    privacy_selftest_error = _coverage_snapshot_error(snapshot, "privacy_selftest_error")
    zsh_hook_status = _coverage_snapshot_document(snapshot, "zsh_hook_status")
    zsh_hook_status_error = _coverage_snapshot_error(snapshot, "zsh_hook_status_error")
    zsh_hook_selftest = _coverage_snapshot_document(snapshot, "zsh_hook_selftest")
    zsh_hook_selftest_error = _coverage_snapshot_error(snapshot, "zsh_hook_selftest_error")
    zsh_selftest_ok = bool(zsh_hook_selftest and zsh_hook_selftest.get("ok"))
    codex_hook_status = _coverage_snapshot_document(snapshot, "codex_hook_status") or {}
    codex_hook_status_error = _coverage_snapshot_error(snapshot, "codex_hook_status_error")
    codex_hook_selftest = _coverage_snapshot_document(snapshot, "codex_hook_selftest")
    codex_hook_selftest_error = _coverage_snapshot_error(snapshot, "codex_hook_selftest_error")
    codex_session_tail_latest = _coverage_snapshot_document(snapshot, "codex_session_tail_latest")
    codex_session_tail_error = _coverage_snapshot_error(snapshot, "codex_session_tail_error")
    codex_selftest_ok = bool(codex_hook_selftest and codex_hook_selftest.get("ok"))
    codex_prompt_summary = (
        codex_hook_status.get("recent_prompt_evidence")
        if isinstance(codex_hook_status.get("recent_prompt_evidence"), Mapping)
        else codex_recent_prompt_summary(valid_records)
    )
    codex_session_tail_summary = (
        codex_hook_status.get("fallback_prompt_evidence")
        if isinstance(codex_hook_status.get("fallback_prompt_evidence"), Mapping)
        else codex_session_tail_recent_prompt_summary(valid_records)
    )
    codex_prompt_route_assessment = codex_prompt_submit_route_assessment(
        configured_adapters=configured_adapters,
        by_adapter=by_adapter,
        codex_prompt_summary=codex_prompt_summary,
        codex_session_tail_summary=codex_session_tail_summary,
        codex_selftest_ok=codex_selftest_ok,
        codex_hook_selftest_error=codex_hook_selftest_error,
        codex_session_tail_latest=codex_session_tail_latest,
    )
    codex_prompt_coverage = codex_prompt_route_assessment.get("coverage") if isinstance(codex_prompt_route_assessment.get("coverage"), Mapping) else {}
    codex_live_prompt_observed = bool(codex_prompt_coverage.get("live_prompt_observed"))
    codex_session_tail_observed = bool(codex_prompt_coverage.get("fallback_observed"))
    dominant_adapter = None
    dominant_ratio = 0.0
    if by_adapter and record_count:
        dominant_adapter, dominant_count = by_adapter.most_common(1)[0]
        dominant_ratio = round(dominant_count / record_count, 3)
    observed_adapters = sorted(by_adapter)
    missing_configured = [item for item in configured_adapters if item not in by_adapter]
    browser_release_probe = _coverage_snapshot_document(snapshot, "browser_release_probe") or {}
    browser_activation = browser_release_probe.get("activation") if isinstance(browser_release_probe.get("activation"), Mapping) else {}
    browser_release_status = browser_release_probe.get("status")
    browser_release_active = _safe_int(browser_activation.get("active_profiles"), 0) > 0 or browser_release_status == "active"
    browser_explicit_recent = by_adapter.get("browser_extension_explicit", 0) > 0
    browser_ai_transcript_records = [item for item in valid_records if item.get("source_adapter") == "browser_ai_transcript"]
    browser_ai_transcript_latest_record = typing_latest_record(browser_ai_transcript_records)
    browser_ai_transcript_recent = by_adapter.get("browser_ai_transcript", 0) > 0
    browser_ai_transcript_selftest_status = typing_browser_ai_transcript_selftest_status(browser_ai_transcript_selftest_latest)
    browser_ai_transcript_selftest_ok = bool(browser_ai_transcript_selftest_status.get("selftest_ok"))
    browser_proof_summary = typing_browser_input_proof_summary(
        browser_webextension_selftest_latest=browser_webextension_selftest_latest,
        browser_atspi_selftest_latest=browser_atspi_selftest_latest,
        browser_atspi_release_selftest_latest=browser_atspi_release_selftest_latest,
        reference_at=generated_at,
    )
    browser_temporary_proof_ok = bool(browser_proof_summary.get("temporary_profile_selftest_ok"))
    browser_atspi_selftest_ok = bool(browser_proof_summary.get("atspi_selftest_ok"))
    browser_atspi_release_selftest_ok = bool(browser_proof_summary.get("atspi_release_selftest_ok"))
    browser_context_fallback = typing_browser_context_fallback_status(
        browser_context_inference=browser_context_inference,
        browser_context_selftest_latest=browser_context_selftest_latest,
        browser_atspi_selftest_ok=browser_atspi_selftest_ok,
        browser_atspi_release_selftest_ok=browser_atspi_release_selftest_ok,
    )
    browser_context_selftest_ok = bool(browser_context_fallback.get("context_selftest_ok"))
    browser_context_inference_effective_ok = bool(browser_context_fallback.get("context_inference_effective_ok"))
    browser_context_inference_effective_status = browser_context_fallback.get("context_inference_effective_status")
    browser_atspi_recent_observed = by_adapter.get("atspi_text_changed_event", 0) > 0
    browser_atspi_fallback_ok = bool(browser_context_fallback.get("atspi_fallback_ok"))
    browser_release_gap = bool(browser_explicit_recent and not browser_release_active)
    generic_gui_records = [
        record for record in valid_records
        if record.get("source_adapter") in {"atspi_text_changed_event", "atspi_focused_text_snapshot"}
        and nested_get(record, ["capture_gate", "confidence"]) in {
            "atspi_generic_editable_text_allowed",
            "focused_generic_editable_text_allowed",
        }
    ]
    generic_gui_latest = typing_latest_record(generic_gui_records)
    generic_gui_selftest_ok = bool(generic_gui_selftest_latest and generic_gui_selftest_latest.get("ok") is True)
    editor_callback_selftest_ok = bool(editor_callback_selftest_latest and editor_callback_selftest_latest.get("ok") is True)
    browser_recency_max_age_sec = max(300, min(_safe_int(atspi_events_policy.get("browser_recency_max_age_sec"), 21600), 86400))
    browser_input_recency = typing_browser_input_recency(
        valid_records,
        generated_at,
        effective_entry_index,
        schema_prefix=schema_prefix,
    )
    browser_input_recency["max_age_sec"] = browser_recency_max_age_sec
    browser_latest_any_age = nested_get(browser_input_recency, ["latest_any", "age_sec"])
    browser_proof_candidates = [
        dict(item) for item in browser_proof_summary.get("proof_routes", []) if isinstance(item, Mapping)
    ]
    browser_latest_proof_raw = browser_proof_summary.get("latest_proof")
    browser_latest_proof = dict(browser_latest_proof_raw) if isinstance(browser_latest_proof_raw, Mapping) else None
    browser_recency_status = typing_browser_input_recency_status(
        browser_input_recency=browser_input_recency,
        browser_latest_proof=browser_latest_proof,
        max_age_sec=browser_recency_max_age_sec,
    )
    browser_effective_recency_status = str(browser_recency_status.get("effective_status") or "browser_evidence_missing")
    browser_input_recency["effective_status"] = browser_effective_recency_status
    browser_input_recency["latest_proof"] = browser_latest_proof
    browser_input_recency["proof_routes"] = browser_proof_candidates
    browser_input_recency["release_profile_active"] = browser_release_active
    browser_input_recency["release_status"] = browser_release_status
    privacy_selftest_ok = bool(privacy_selftest_latest and privacy_selftest_latest.get("ok") is True)
    browser_privacy_selftest_ok = bool(browser_privacy_selftest_latest and browser_privacy_selftest_latest.get("ok") is True)
    coverage_routes = {
        "manual_cli": {
            "covered": by_adapter.get("manual_cli_stdin", 0) > 0 or by_adapter.get("manual_cli_args", 0) > 0,
            "recent_records": by_adapter.get("manual_cli_stdin", 0) + by_adapter.get("manual_cli_args", 0),
        },
        "shell_committed_commands": {
            "covered": zsh_selftest_ok,
            "recent_observed": by_adapter.get("zsh_preexec", 0) > 0,
            "recent_records": by_adapter.get("zsh_preexec", 0),
            "selftest_ok": zsh_selftest_ok,
        },
        "codex_prompt_submit": codex_prompt_coverage,
        "editor_committed_text": {
            "covered": editor_callback_selftest_ok,
            "recent_observed": by_adapter.get("editor_extension_explicit", 0) > 0,
            "recent_records": by_adapter.get("editor_extension_explicit", 0),
            "callback_selftest_ok": editor_callback_selftest_ok,
        },
        "browser_explicit_webextension": {
            "covered": bool(browser_explicit_recent and browser_release_active),
            "effective_covered": bool(
                (browser_explicit_recent and (browser_release_active or browser_temporary_proof_ok))
                or browser_temporary_proof_ok
            ),
            "recent_observed": browser_explicit_recent,
            "recent_records": by_adapter.get("browser_extension_explicit", 0),
            "latest_record": browser_input_recency.get("latest_explicit_webextension"),
            "release_profile_active": browser_release_active,
            "release_route_ready": browser_release_active,
            "temporary_profile_selftest_ok": browser_temporary_proof_ok,
            "latest_proof": browser_latest_proof,
            "recency_status": browser_effective_recency_status,
            "fallback_required": bool(browser_release_gap and browser_temporary_proof_ok),
            "status": browser_release_status,
            "route_note": "release_profile_blocked_but_temporary_profile_proof_exists" if browser_explicit_recent and not browser_release_active and browser_temporary_proof_ok else None,
        },
        "browser_ai_transcript": {
            "covered": browser_ai_transcript_recent,
            "effective_covered": bool(browser_ai_transcript_recent or browser_ai_transcript_selftest_ok),
            "recent_observed": browser_ai_transcript_recent,
            "recent_records": by_adapter.get("browser_ai_transcript", 0),
            "latest_record": typing_recent_record_brief(
                browser_ai_transcript_latest_record,
                generated_at,
                effective_entry_index.get(str(browser_ai_transcript_latest_record.get("event_id") or "")),
            ) if browser_ai_transcript_latest_record else None,
            "latest_status": browser_ai_transcript_latest.get("status") if browser_ai_transcript_latest else None,
            "latest_error": browser_ai_transcript_latest_error,
            "selftest_ok": browser_ai_transcript_selftest_ok,
            "latest_selftest_status": browser_ai_transcript_selftest_latest.get("status") if browser_ai_transcript_selftest_latest else None,
            "latest_selftest_error": browser_ai_transcript_selftest_error,
            "policy": {
                "known_ai_counterpart_required": True,
                "transcript_safe_marker_required": True,
                "password_fields_captured": False,
                "form_values_captured": False,
                "cookies_captured": False,
                "local_storage_captured": False,
                "automatic_action": False,
            },
        },
        "browser_atspi_fallback": {
            "covered": browser_atspi_fallback_ok,
            "recent_observed": browser_atspi_recent_observed,
            "recent_records": by_adapter.get("atspi_text_changed_event", 0),
            "browser_records": browser_input_recency.get("atspi_browser_fallback_records"),
            "latest_browser_record": browser_input_recency.get("latest_atspi_browser_fallback"),
            "selftest_ok": browser_atspi_selftest_ok,
            "recency_status": browser_effective_recency_status,
            "context_inference_ok": browser_context_inference_effective_ok,
            "context_inference_status": browser_context_inference_effective_status,
            "context_inference_raw_status": browser_context_inference.get("status"),
            "context_selftest_ok": browser_context_selftest_ok,
        },
        "generic_gui_committed_text": {
            "covered": generic_gui_selftest_ok,
            "recent_observed": bool(generic_gui_records),
            "recent_records": len(generic_gui_records),
            "latest_record": typing_recent_record_brief(
                generic_gui_latest,
                generated_at,
                effective_entry_index.get(str(generic_gui_latest.get("event_id") or "")),
            ) if generic_gui_latest else None,
            "selftest_ok": generic_gui_selftest_ok,
            "latest_selftest_status": generic_gui_selftest_latest.get("status") if generic_gui_selftest_latest else None,
            "latest_selftest_error": generic_gui_selftest_error,
            "policy": {
                "raw_keylogging": False,
                "requires_editable_text_role": True,
                "password_fields_captured": False,
            },
        },
        "saved_text_scan": {
            "covered": by_adapter.get("saved_text_snapshot", 0) > 0,
            "recent_records": by_adapter.get("saved_text_snapshot", 0),
        },
        "privacy_exclusions": {
            "covered": privacy_selftest_ok and browser_privacy_selftest_ok,
            "latest_status": privacy_selftest_latest.get("status") if privacy_selftest_latest else None,
            "latest_error": privacy_selftest_error,
            "browser_runtime_latest_status": browser_privacy_selftest_latest.get("status") if browser_privacy_selftest_latest else None,
            "browser_runtime_ok": browser_privacy_selftest_ok,
            "browser_runtime_latest_error": browser_privacy_selftest_error,
        },
    }
    coverage_route_assessment = typing_coverage_route_notes_and_gaps(
        configured_adapters=configured_adapters,
        by_adapter=by_adapter,
        by_gate=by_gate,
        record_count=record_count,
        dominant_adapter=dominant_adapter,
        dominant_ratio=dominant_ratio,
        saved_text_count=saved_text_count,
        live_input_count=live_input_count,
        live_observed_adapters=live_observed_adapters,
        live_dominant_adapter=live_dominant_adapter,
        live_dominant_ratio=live_dominant_ratio,
        browser_release_gap=browser_release_gap,
        browser_release_status=browser_release_status,
        browser_release_active=browser_release_active,
        browser_activation=browser_activation,
        browser_temporary_proof_ok=browser_temporary_proof_ok,
        browser_atspi_fallback_ok=browser_atspi_fallback_ok,
        browser_effective_recency_status=browser_effective_recency_status,
        browser_recency_max_age_sec=browser_recency_max_age_sec,
        browser_input_recency=browser_input_recency,
        browser_latest_proof=browser_latest_proof,
        codex_prompt_route_assessment=codex_prompt_route_assessment,
        focused_policy=focused_policy,
        focused_latest=focused_latest,
        focused_latest_error=focused_latest_error,
        atspi_events_latest=atspi_events_latest,
        atspi_events_latest_error=atspi_events_latest_error,
        generic_gui_selftest_ok=generic_gui_selftest_ok,
        zsh_selftest_ok=zsh_selftest_ok,
        zsh_hook_selftest_error=zsh_hook_selftest_error,
        editor_extension_latest=editor_extension_latest,
        editor_extension_latest_error=editor_extension_latest_error,
        editor_callback_selftest_ok=editor_callback_selftest_ok,
        browser_extension_latest=browser_extension_latest,
        browser_extension_latest_error=browser_extension_latest_error,
        browser_ai_transcript_latest=browser_ai_transcript_latest,
        browser_ai_transcript_latest_error=browser_ai_transcript_latest_error,
        browser_ai_transcript_selftest_ok=browser_ai_transcript_selftest_ok,
        browser_ai_transcript_selftest_error=browser_ai_transcript_selftest_error,
        missing_gate_records=missing_gate_records,
    )
    route_notes = coverage_route_assessment.get("route_notes") or []
    gaps = coverage_route_assessment.get("gaps") or []
    coverage_decision = typing_coverage_status_decision(
        record_count=record_count,
        coverage_routes=coverage_routes,
        gaps=gaps,
        observed_adapters=observed_adapters,
        dominant_adapter=dominant_adapter,
        dominant_ratio=dominant_ratio,
        live_input_count=live_input_count,
        browser_release_gap=browser_release_gap,
        browser_temporary_proof_ok=browser_temporary_proof_ok,
        browser_atspi_fallback_ok=browser_atspi_fallback_ok,
    )
    coverage_status = str(coverage_decision.get("status") or "manual_only")
    route_coverage_count = _safe_int(coverage_decision.get("coverage_routes"), 0)
    route_effective_coverage_count = _safe_int(coverage_decision.get("effective_coverage_routes"), 0)
    route_coverage_total = _safe_int(coverage_decision.get("coverage_route_total"), len(coverage_routes))
    latest_gate = latest_data.get("capture_gate") if isinstance(latest_data.get("capture_gate"), Mapping) else {}
    return {
        "schema": f"{schema_prefix}_typing_coverage_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not parse_errors and policy_data.get("ok") is True,
        "status": coverage_status,
        "summary": {
            "recent_records": record_count,
            "observed_adapters": observed_adapters,
            "missing_configured_adapters": missing_configured,
            "dominant_adapter": dominant_adapter,
            "dominant_ratio": dominant_ratio,
            "saved_text_records": saved_text_count,
            "saved_text_ratio": saved_text_ratio,
            "live_input_records": live_input_count,
            "live_observed_adapters": live_observed_adapters,
            "live_dominant_adapter": live_dominant_adapter,
            "live_dominant_ratio": live_dominant_ratio,
            "capture_gate_required_records": capture_gate_required,
            "missing_capture_gate_records": missing_gate_records,
            "gaps": len(gaps),
            "coverage_routes": route_coverage_count,
            "effective_coverage_routes": route_effective_coverage_count,
            "coverage_route_total": route_coverage_total,
            "route_notes": len(route_notes),
            "browser_input_recency_status": browser_effective_recency_status,
            "browser_input_records": browser_input_recency.get("records"),
            "browser_input_natural_records": browser_input_recency.get("natural_records"),
            "browser_input_natural_text_records": browser_input_recency.get("natural_text_records"),
            "browser_input_latest_age_sec": browser_latest_any_age,
            "browser_context_inference_status": browser_context_inference_effective_status,
            "browser_context_inference_raw_status": browser_context_inference.get("status"),
            "browser_ai_transcript_records": by_adapter.get("browser_ai_transcript", 0),
            "browser_ai_transcript_selftest_ok": browser_ai_transcript_selftest_ok,
            "generic_gui_text_records": len(generic_gui_records),
            "generic_gui_selftest_ok": generic_gui_selftest_ok,
            "effective_causal_records": nested_get(process_readmodel, ["summary", "records_processed"]),
            "effective_causal_promoted": nested_get(process_readmodel, ["summary", "continuity_promoted"]),
            "effective_causal_awareness_score": nested_get(process_readmodel, ["summary", "awareness_average_score"]),
        },
        "by_adapter": dict(sorted(by_adapter.items())),
        "live_by_adapter": dict(sorted(live_by_adapter.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_capture_gate_decision": dict(sorted(by_gate.items())),
        "by_recipient": dict(sorted(effective_by_recipient.items())) if effective_by_recipient else dict(sorted(by_recipient.items())),
        "by_project": dict(sorted(effective_by_project.items())) if effective_by_project else dict(sorted(by_project.items())),
        "by_project_basis": dict(sorted(effective_by_project_basis.items())) if effective_by_project_basis else {},
        "by_interaction_kind": dict(sorted(effective_by_interaction_kind.items())) if effective_by_interaction_kind else {},
        "raw_by_recipient": dict(sorted(by_recipient.items())),
        "raw_by_project": dict(sorted(by_project.items())),
        "effective_causal_readmodel": {
            "ok": process_readmodel.get("ok"),
            "status": process_readmodel.get("status"),
            "generated_at": process_readmodel.get("generated_at"),
            "summary": process_readmodel.get("summary") if isinstance(process_readmodel.get("summary"), Mapping) else {},
            "policy": {
                "stores_extra_text": False,
                "widens_capture": False,
                "facts_only": True,
            },
        },
        "configured_adapters": configured_adapters,
        "diagnostic_adapters": diagnostic_adapters,
        "gate_allow_text_adapters": gate_allow_adapters,
        "coverage_routes": coverage_routes,
        "route_notes": route_notes,
        "gaps": gaps,
        "browser_input_recency": browser_input_recency,
        "browser_ai_transcript_latest": {
            "status": browser_ai_transcript_latest.get("status") if browser_ai_transcript_latest else None,
            "source_adapter": browser_ai_transcript_latest.get("source_adapter") if browser_ai_transcript_latest else None,
            "ok": browser_ai_transcript_latest.get("ok") if browser_ai_transcript_latest else None,
            "error": browser_ai_transcript_latest_error,
        },
        "browser_context_inference": browser_context_inference,
        "latest": {
            "status": latest_data.get("status"),
            "source_adapter": latest_data.get("source_adapter"),
            "capture_gate_decision": latest_gate.get("decision"),
            "capture_gate_confidence": latest_gate.get("confidence"),
        },
        "focused_snapshot_latest": {
            "exists": focused_latest is not None,
            "generated_at": focused_latest.get("generated_at") if focused_latest else None,
            "status": focused_latest.get("status") if focused_latest else None,
            "app": focused_candidate.get("app"),
            "role": focused_candidate.get("role"),
            "text_role": focused_candidate.get("text_role"),
            "text_read_allowed": focused_candidate.get("text_read_allowed"),
            "diagnostic_only": focused_candidate.get("diagnostic_only"),
            "mode": focused_policy.get("mode"),
            "text_capture_enabled": focused_policy.get("text_capture_enabled"),
            "error": focused_latest_error,
        },
        "atspi_text_events_latest": {
            "exists": atspi_events_latest is not None,
            "generated_at": atspi_events_latest.get("generated_at") if atspi_events_latest else None,
            "started_at": atspi_events_latest.get("started_at") if atspi_events_latest else None,
            "heartbeat_at": atspi_events_latest.get("heartbeat_at") if atspi_events_latest else None,
            "heartbeat_age_sec": typing_age_seconds(
                (atspi_events_latest.get("heartbeat_at") or atspi_events_latest.get("generated_at")) if atspi_events_latest else None,
                generated_at,
            ),
            "last_event_at": atspi_events_latest.get("last_event_at") if atspi_events_latest else None,
            "last_event_age_sec": typing_age_seconds(
                atspi_events_latest.get("last_event_at") if atspi_events_latest else None,
                generated_at,
            ),
            "heartbeat_interval_sec": atspi_events_latest.get("heartbeat_interval_sec") if atspi_events_latest else None,
            "status": atspi_events_latest.get("status") if atspi_events_latest else None,
            "summary": atspi_events_latest.get("summary") if atspi_events_latest else None,
            "error": atspi_events_latest_error,
        },
        "editor_extension_latest": {
            "exists": editor_extension_latest is not None,
            "generated_at": editor_extension_latest.get("generated_at") if editor_extension_latest else None,
            "status": editor_extension_latest.get("status") if editor_extension_latest else None,
            "ok": editor_extension_latest.get("ok") if editor_extension_latest else None,
            "error": editor_extension_latest_error,
        },
        "editor_extension_selftest_latest": {
            "exists": editor_extension_selftest_latest is not None,
            "generated_at": editor_extension_selftest_latest.get("generated_at") if editor_extension_selftest_latest else None,
            "status": editor_extension_selftest_latest.get("status") if editor_extension_selftest_latest else None,
            "ok": editor_extension_selftest_latest.get("ok") if editor_extension_selftest_latest else None,
            "event": editor_extension_selftest_latest.get("event") if editor_extension_selftest_latest else None,
            "error": editor_extension_selftest_error,
        },
        "editor_callback_selftest_latest": {
            "exists": editor_callback_selftest_latest is not None,
            "generated_at": editor_callback_selftest_latest.get("generated_at") if editor_callback_selftest_latest else None,
            "status": editor_callback_selftest_latest.get("status") if editor_callback_selftest_latest else None,
            "ok": editor_callback_selftest_latest.get("ok") if editor_callback_selftest_latest else None,
            "event": editor_callback_selftest_latest.get("event") if editor_callback_selftest_latest else None,
            "error": editor_callback_selftest_error,
        },
        "browser_extension_latest": {
            "exists": browser_extension_latest is not None,
            "generated_at": browser_extension_latest.get("generated_at") if browser_extension_latest else None,
            "status": browser_extension_latest.get("status") if browser_extension_latest else None,
            "ok": browser_extension_latest.get("ok") if browser_extension_latest else None,
            "event": browser_extension_latest.get("event") if browser_extension_latest else None,
            "error": browser_extension_latest_error,
        },
        "browser_release_profile_status": {
            "generated_at": browser_release_probe.get("generated_at"),
            "status": browser_release_status,
            "ok": browser_release_probe.get("ok"),
            "active": browser_release_active,
            "activation": browser_activation,
            "profiles": browser_release_probe.get("profiles") if isinstance(browser_release_probe, Mapping) else [],
        },
        "browser_webextension_selftest_latest": {
            "exists": browser_webextension_selftest_latest is not None,
            "generated_at": browser_webextension_selftest_latest.get("generated_at") if browser_webextension_selftest_latest else None,
            "status": browser_webextension_selftest_latest.get("status") if browser_webextension_selftest_latest else None,
            "ok": browser_webextension_selftest_latest.get("ok") if browser_webextension_selftest_latest else None,
            "event": browser_webextension_selftest_latest.get("event") if browser_webextension_selftest_latest else None,
            "error": browser_webextension_selftest_error,
        },
        "browser_atspi_selftest_latest": {
            "exists": browser_atspi_selftest_latest is not None,
            "generated_at": browser_atspi_selftest_latest.get("generated_at") if browser_atspi_selftest_latest else None,
            "status": browser_atspi_selftest_latest.get("status") if browser_atspi_selftest_latest else None,
            "ok": browser_atspi_selftest_latest.get("ok") if browser_atspi_selftest_latest else None,
            "event": browser_atspi_selftest_latest.get("event") if browser_atspi_selftest_latest else None,
            "firefox": browser_atspi_selftest_latest.get("firefox") if browser_atspi_selftest_latest and isinstance(browser_atspi_selftest_latest.get("firefox"), Mapping) else None,
            "policy": browser_atspi_selftest_latest.get("policy") if browser_atspi_selftest_latest and isinstance(browser_atspi_selftest_latest.get("policy"), Mapping) else None,
            "error": browser_atspi_selftest_error,
        },
        "browser_context_selftest_latest": {
            "exists": browser_context_selftest_latest is not None,
            "generated_at": browser_context_selftest_latest.get("generated_at") if browser_context_selftest_latest else None,
            "status": browser_context_selftest_latest.get("status") if browser_context_selftest_latest else None,
            "ok": browser_context_selftest_latest.get("ok") if browser_context_selftest_latest else None,
            "capture": browser_context_selftest_latest.get("capture") if browser_context_selftest_latest and isinstance(browser_context_selftest_latest.get("capture"), Mapping) else None,
            "inference": browser_context_selftest_latest.get("inference") if browser_context_selftest_latest and isinstance(browser_context_selftest_latest.get("inference"), Mapping) else None,
            "policy": browser_context_selftest_latest.get("policy") if browser_context_selftest_latest and isinstance(browser_context_selftest_latest.get("policy"), Mapping) else None,
            "error": browser_context_selftest_error,
        },
        "browser_atspi_release_selftest_latest": {
            "exists": browser_atspi_release_selftest_latest is not None,
            "generated_at": browser_atspi_release_selftest_latest.get("generated_at") if browser_atspi_release_selftest_latest else None,
            "status": browser_atspi_release_selftest_latest.get("status") if browser_atspi_release_selftest_latest else None,
            "ok": browser_atspi_release_selftest_latest.get("ok") if browser_atspi_release_selftest_latest else None,
            "event": browser_atspi_release_selftest_latest.get("event") if browser_atspi_release_selftest_latest else None,
            "firefox": browser_atspi_release_selftest_latest.get("firefox") if browser_atspi_release_selftest_latest and isinstance(browser_atspi_release_selftest_latest.get("firefox"), Mapping) else None,
            "policy": browser_atspi_release_selftest_latest.get("policy") if browser_atspi_release_selftest_latest and isinstance(browser_atspi_release_selftest_latest.get("policy"), Mapping) else None,
            "error": browser_atspi_release_selftest_error,
        },
        "generic_gui_selftest_latest": {
            "exists": generic_gui_selftest_latest is not None,
            "generated_at": generic_gui_selftest_latest.get("generated_at") if generic_gui_selftest_latest else None,
            "status": generic_gui_selftest_latest.get("status") if generic_gui_selftest_latest else None,
            "ok": generic_gui_selftest_latest.get("ok") if generic_gui_selftest_latest else None,
            "event": generic_gui_selftest_latest.get("event") if generic_gui_selftest_latest else None,
            "sensitive_probe": generic_gui_selftest_latest.get("sensitive_probe") if generic_gui_selftest_latest else None,
            "error": generic_gui_selftest_error,
        },
        "zsh_hook": {
            "status_exists": zsh_hook_status is not None,
            "status": zsh_hook_status.get("status") if zsh_hook_status else None,
            "status_ok": zsh_hook_status.get("ok") if zsh_hook_status else None,
            "status_generated_at": zsh_hook_status.get("generated_at") if zsh_hook_status else None,
            "status_error": zsh_hook_status_error,
            "selftest_exists": zsh_hook_selftest is not None,
            "selftest_ok": zsh_hook_selftest.get("ok") if zsh_hook_selftest else None,
            "selftest_generated_at": zsh_hook_selftest.get("generated_at") if zsh_hook_selftest else None,
            "selftest_event_detected": nested_get(zsh_hook_selftest, ["summary", "event_detected"]) if zsh_hook_selftest else None,
            "selftest_error": zsh_hook_selftest_error,
        },
        "codex_hook": {
            "status_exists": bool(codex_hook_status),
            "status": codex_hook_status.get("status"),
            "status_ok": codex_hook_status.get("ok"),
            "status_generated_at": codex_hook_status.get("generated_at"),
            "status_error": codex_hook_status_error,
            "selftest_exists": codex_hook_selftest is not None,
            "selftest_ok": codex_hook_selftest.get("ok") if codex_hook_selftest else None,
            "selftest_generated_at": codex_hook_selftest.get("generated_at") if codex_hook_selftest else None,
            "selftest_event_detected": nested_get(codex_hook_selftest, ["summary", "event_detected"]) if codex_hook_selftest else None,
            "live_prompt_observed": codex_live_prompt_observed,
            "recent_prompt_evidence": codex_prompt_summary,
            "fallback_prompt_observed": codex_session_tail_observed,
            "fallback_prompt_evidence": codex_session_tail_summary,
            "fallback_latest_status": codex_session_tail_latest.get("status") if codex_session_tail_latest else None,
            "fallback_error": codex_session_tail_error,
            "selftest_error": codex_hook_selftest_error,
        },
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "capture_gate_required": True,
            "capture_gate_network_access": False,
            "unknown_surfaces_text_capture": False,
        },
        "non_claims": [
            "coverage is a readmodel over recent typing events; it does not install a wider capture adapter.",
            "coverage gaps identify source visibility limits; they do not authorize raw keylogging.",
        ],
    }


def typing_status_document(
    records: list[dict[str, Any]],
    parse_errors: list[dict[str, Any]],
    ensure_errors: list[dict[str, Any]],
    policy: Mapping[str, Any],
    latest: Mapping[str, Any],
    coverage: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    generated_at: str,
    coverage_limit: int,
    latest_exists: bool,
    gnome_accessibility: Mapping[str, Any] | None,
    nervous_processing: Mapping[str, Any] | None,
    focused_snapshot: Mapping[str, Any] | None,
    saved_text_scan: Mapping[str, Any] | None,
    codex_session_tail: Mapping[str, Any] | None,
    editor_extension: Mapping[str, Any] | None,
    nervous_refresh: Mapping[str, Any] | None,
    browser_content_latest: Mapping[str, Any] | None,
    browser_content_error: str | None,
    browser_content_latest_path: str,
    paths: Mapping[str, Any],
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
) -> dict[str, Any]:
    record_items = [item for item in records if isinstance(item, dict)]
    parse_error_items = [item for item in parse_errors if isinstance(item, dict)]
    ensure_error_items = [item for item in ensure_errors if isinstance(item, dict)]
    policy_data = policy if isinstance(policy, Mapping) else {}
    latest_data = latest if isinstance(latest, Mapping) else {}
    coverage_data = coverage if isinstance(coverage, Mapping) else {}
    process_data = process if isinstance(process, Mapping) else {}
    gnome_data = gnome_accessibility if isinstance(gnome_accessibility, Mapping) else {}
    nervous_processing_data = nervous_processing if isinstance(nervous_processing, Mapping) else {}
    focused_snapshot_data = focused_snapshot if isinstance(focused_snapshot, Mapping) else {}
    saved_text_scan_data = saved_text_scan if isinstance(saved_text_scan, Mapping) else {}
    codex_session_tail_data = codex_session_tail if isinstance(codex_session_tail, Mapping) else {}
    editor_extension_data = editor_extension if isinstance(editor_extension, Mapping) else {}
    nervous_refresh_data = nervous_refresh if isinstance(nervous_refresh, Mapping) else {}
    browser_content_data = browser_content_latest if isinstance(browser_content_latest, Mapping) else {}
    browser_content_summary = browser_content_data.get("summary") if isinstance(browser_content_data.get("summary"), Mapping) else {}
    by_status = collections.Counter(str(item.get("status") or "unknown") for item in record_items)
    by_recipient = collections.Counter(
        str(nested_get(item, ["causal_context", "recipient", "kind"]) or "missing")
        for item in record_items
    )
    by_project = collections.Counter(
        str(nested_get(item, ["causal_context", "where", "project", "id"]) or "unknown")
        for item in record_items
    )
    return {
        "schema": f"{schema_prefix}_typing_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": not ensure_error_items and policy_data.get("ok") is True and not parse_error_items,
        "summary": {
            "recent_records": len(record_items),
            "coverage_window_records": coverage_limit,
            "latest_exists": latest_exists,
            "by_status": dict(sorted(by_status.items())),
            "by_recipient": dict(sorted(by_recipient.items())),
            "by_project": dict(sorted(by_project.items())),
            "coverage_status": coverage_data.get("status"),
            "coverage_gaps": nested_get(coverage_data, ["summary", "gaps"]),
            "coverage_route_notes": nested_get(coverage_data, ["summary", "route_notes"]),
            "saved_text_records": nested_get(coverage_data, ["summary", "saved_text_records"]),
            "saved_text_ratio": nested_get(coverage_data, ["summary", "saved_text_ratio"]),
            "live_input_records": nested_get(coverage_data, ["summary", "live_input_records"]),
            "live_observed_adapters": nested_get(coverage_data, ["summary", "live_observed_adapters"]),
            "live_dominant_adapter": nested_get(coverage_data, ["summary", "live_dominant_adapter"]),
            "live_dominant_ratio": nested_get(coverage_data, ["summary", "live_dominant_ratio"]),
            "process_status": process_data.get("status"),
            "process_lanes": nested_get(process_data, ["summary", "lanes"]),
            "process_context_bound": nested_get(process_data, ["summary", "context_bound"]),
            "process_missing_context_anchor": nested_get(process_data, ["summary", "missing_context_anchor"]),
            "process_quality_gaps": nested_get(process_data, ["summary", "quality_gaps"]),
            "process_fail_gaps": nested_get(process_data, ["summary", "fail_gaps"]),
            "causal_awareness_average_score": nested_get(process_data, ["summary", "awareness_average_score"]),
            "causal_awareness_complete": nested_get(process_data, ["summary", "awareness_complete"]),
            "causal_awareness_guarded": nested_get(process_data, ["summary", "awareness_guarded"]),
            "causal_awareness_incomplete": nested_get(process_data, ["summary", "awareness_incomplete"]),
            "causal_awareness_top_gaps": nested_get(process_data, ["awareness", "top_gaps"]),
            "causal_awareness_axis_states": nested_get(process_data, ["awareness", "axis_states"]),
            "by_context_anchor_kind": process_data.get("by_context_anchor_kind"),
            "by_capture_gate_decision": coverage_data.get("by_capture_gate_decision"),
            "zsh_hook_status": nested_get(coverage_data, ["zsh_hook", "status"]),
            "zsh_hook_selftest_ok": nested_get(coverage_data, ["zsh_hook", "selftest_ok"]),
            "codex_hook_status": nested_get(coverage_data, ["codex_hook", "status"]),
            "codex_hook_selftest_ok": nested_get(coverage_data, ["codex_hook", "selftest_ok"]),
            "codex_hook_live_prompt_observed": nested_get(coverage_data, ["codex_hook", "live_prompt_observed"]),
            "codex_hook_live_prompt_records": nested_get(coverage_data, ["codex_hook", "recent_prompt_evidence", "live_prompt_records"]),
            "codex_hook_selftest_records": nested_get(coverage_data, ["codex_hook", "recent_prompt_evidence", "selftest_records"]),
            "codex_session_tail_prompt_observed": nested_get(coverage_data, ["codex_hook", "fallback_prompt_observed"]),
            "codex_session_tail_prompt_records": nested_get(coverage_data, ["codex_hook", "fallback_prompt_evidence", "recent_records"]),
            "codex_session_tail_ok": codex_session_tail_data.get("ok"),
            "codex_session_tail_status": codex_session_tail_data.get("status"),
            "codex_session_tail_latest_generated_at": nested_get(codex_session_tail_data, ["summary", "latest_generated_at"]),
            "codex_session_tail_latest_age_sec": nested_get(codex_session_tail_data, ["summary", "latest_age_sec"]),
            "codex_session_tail_service_active": nested_get(codex_session_tail_data, ["summary", "service_active"]),
            "codex_session_tail_service_enabled": nested_get(codex_session_tail_data, ["summary", "service_enabled"]),
            "codex_session_tail_recurring_ok": nested_get(codex_session_tail_data, ["summary", "recurring_ok"]),
            "codex_session_tail_events": nested_get(codex_session_tail_data, ["summary", "events"]),
            "codex_session_tail_raw_user_candidates": nested_get(codex_session_tail_data, ["summary", "raw_user_candidates"]),
            "codex_session_tail_parse_errors": nested_get(codex_session_tail_data, ["summary", "parse_errors"]),
            "browser_extension_status": nested_get(coverage_data, ["browser_release_profile_status", "status"]),
            "browser_extension_event_latest_status": nested_get(coverage_data, ["browser_extension_latest", "status"]),
            "browser_input_recency_status": nested_get(coverage_data, ["browser_input_recency", "effective_status"]),
            "browser_input_records": nested_get(coverage_data, ["browser_input_recency", "records"]),
            "browser_input_natural_records": nested_get(coverage_data, ["browser_input_recency", "natural_records"]),
            "browser_input_natural_text_records": nested_get(coverage_data, ["browser_input_recency", "natural_text_records"]),
            "browser_input_latest_age_sec": nested_get(coverage_data, ["browser_input_recency", "latest_any", "age_sec"]),
            "browser_context_inference_status": nested_get(coverage_data, ["summary", "browser_context_inference_status"]),
            "browser_context_selftest_ok": nested_get(coverage_data, ["browser_context_selftest_latest", "ok"]),
            "browser_context_selftest_status": nested_get(coverage_data, ["browser_context_selftest_latest", "status"]),
            "browser_content_capture_ok": browser_content_data.get("ok") if browser_content_data else None,
            "browser_content_capture_generated_at": browser_content_data.get("generated_at") if browser_content_data else None,
            "browser_content_capture_skipped": browser_content_data.get("skipped") if browser_content_data else None,
            "browser_content_capture_skip_reason": browser_content_data.get("skip_reason") if browser_content_data else None,
            "browser_content_capture_captures": browser_content_summary.get("captures"),
            "browser_content_capture_text_records": browser_content_summary.get("text_records"),
            "browser_content_capture_error": browser_content_error,
            "generic_gui_text_records": nested_get(coverage_data, ["summary", "generic_gui_text_records"]),
            "generic_gui_selftest_ok": nested_get(coverage_data, ["summary", "generic_gui_selftest_ok"]),
            "generic_gui_latest_confidence": nested_get(coverage_data, ["coverage_routes", "generic_gui_committed_text", "latest_record", "capture_gate_confidence"]),
            "atspi_text_events_heartbeat_age_sec": nested_get(coverage_data, ["atspi_text_events_latest", "heartbeat_age_sec"]),
            "atspi_text_events_last_event_age_sec": nested_get(coverage_data, ["atspi_text_events_latest", "last_event_age_sec"]),
            "editor_extension_selftest_ok": nested_get(coverage_data, ["editor_extension_selftest_latest", "ok"]),
            "editor_extension_selftest_status": nested_get(coverage_data, ["editor_extension_selftest_latest", "status"]),
            "editor_callback_selftest_ok": nested_get(coverage_data, ["editor_callback_selftest_latest", "ok"]),
            "editor_callback_selftest_status": nested_get(coverage_data, ["editor_callback_selftest_latest", "status"]),
            "editor_extension_ok": editor_extension_data.get("ok"),
            "editor_extension_status": editor_extension_data.get("status"),
            "editor_extension_activation_status": nested_get(editor_extension_data, ["summary", "activation_status"]),
            "editor_extension_activation_age_sec": nested_get(editor_extension_data, ["summary", "activation_age_sec"]),
            "editor_extension_selftest_age_sec": nested_get(editor_extension_data, ["summary", "selftest_age_sec"]),
            "editor_extension_callback_age_sec": nested_get(editor_extension_data, ["summary", "callback_age_sec"]),
            "editor_extension_proof_age_sec": nested_get(editor_extension_data, ["summary", "proof_age_sec"]),
            "browser_atspi_selftest_ok": nested_get(coverage_data, ["browser_atspi_selftest_latest", "ok"]),
            "browser_atspi_selftest_status": nested_get(coverage_data, ["browser_atspi_selftest_latest", "status"]),
            "browser_atspi_selftest_profile_kind": nested_get(coverage_data, ["browser_atspi_selftest_latest", "firefox", "profile_kind"]),
            "browser_atspi_selftest_release_profile_mutated": nested_get(coverage_data, ["browser_atspi_selftest_latest", "policy", "release_profile_mutated"]),
            "browser_atspi_release_selftest_ok": nested_get(coverage_data, ["browser_atspi_release_selftest_latest", "ok"]),
            "browser_atspi_release_selftest_status": nested_get(coverage_data, ["browser_atspi_release_selftest_latest", "status"]),
            "browser_atspi_release_selftest_profile_kind": nested_get(coverage_data, ["browser_atspi_release_selftest_latest", "firefox", "profile_kind"]),
            "browser_atspi_release_selftest_event_age_sec": typing_age_seconds(
                nested_get(coverage_data, ["browser_atspi_release_selftest_latest", "event", "generated_at"]),
                generated_at,
            ),
            "gnome_toolkit_accessibility": gnome_data.get("enabled"),
            "nervous_processing_ok": nervous_processing_data.get("ok"),
            "nervous_processing_status": nervous_processing_data.get("status"),
            "nervous_processing_facts_ready": nested_get(nervous_processing_data, ["summary", "facts_ready"]),
            "nervous_processing_index_ready": nested_get(nervous_processing_data, ["summary", "index_ready"]),
            "focused_snapshot_ok": focused_snapshot_data.get("ok"),
            "focused_snapshot_status": focused_snapshot_data.get("status"),
            "focused_snapshot_latest_generated_at": nested_get(focused_snapshot_data, ["summary", "latest_generated_at"]),
            "focused_snapshot_latest_age_sec": nested_get(focused_snapshot_data, ["summary", "latest_age_sec"]),
            "focused_snapshot_timer_active": nested_get(focused_snapshot_data, ["summary", "timer_active"]),
            "focused_snapshot_timer_enabled": nested_get(focused_snapshot_data, ["summary", "timer_enabled"]),
            "focused_snapshot_candidate_text_read_allowed": nested_get(focused_snapshot_data, ["summary", "candidate_text_read_allowed"]),
            "focused_snapshot_candidate_capture_gate_decision": nested_get(focused_snapshot_data, ["summary", "candidate_capture_gate_decision"]),
            "focused_snapshot_candidate_safe_route": nested_get(focused_snapshot_data, ["summary", "candidate_safe_route"]),
            "saved_text_scan_ok": saved_text_scan_data.get("ok"),
            "saved_text_scan_status": saved_text_scan_data.get("status"),
            "saved_text_scan_latest_generated_at": nested_get(saved_text_scan_data, ["summary", "latest_generated_at"]),
            "saved_text_scan_latest_age_sec": nested_get(saved_text_scan_data, ["summary", "latest_age_sec"]),
            "saved_text_scan_timer_active": nested_get(saved_text_scan_data, ["summary", "timer_active"]),
            "saved_text_scan_timer_enabled": nested_get(saved_text_scan_data, ["summary", "timer_enabled"]),
            "saved_text_scan_candidates": nested_get(saved_text_scan_data, ["summary", "candidates"]),
            "saved_text_scan_events": nested_get(saved_text_scan_data, ["summary", "events"]),
            "saved_text_scan_skips": nested_get(saved_text_scan_data, ["summary", "skips"]),
            "saved_text_scan_state_error": nested_get(saved_text_scan_data, ["summary", "state_error"]),
            "nervous_refresh_ok": nervous_refresh_data.get("ok"),
            "nervous_refresh_status": nervous_refresh_data.get("status"),
            "nervous_refresh_latest_generated_at": nested_get(nervous_refresh_data, ["summary", "latest_generated_at"]),
            "nervous_refresh_latest_finished_at": nested_get(nervous_refresh_data, ["summary", "latest_finished_at"]),
            "nervous_refresh_latest_age_sec": nested_get(nervous_refresh_data, ["summary", "latest_age_sec"]),
            "nervous_refresh_timer_active": nested_get(nervous_refresh_data, ["summary", "timer_active"]),
            "nervous_refresh_timer_enabled": nested_get(nervous_refresh_data, ["summary", "timer_enabled"]),
            "nervous_refresh_snapshot_needed": nested_get(nervous_refresh_data, ["summary", "snapshot_needed"]),
            "nervous_refresh_index_needed": nested_get(nervous_refresh_data, ["summary", "index_needed"]),
            "nervous_refresh_index_resource_launch_attempted": nested_get(nervous_refresh_data, ["summary", "index_resource_launch_attempted"]),
            "nervous_refresh_index_resource_launch_ok": nested_get(nervous_refresh_data, ["summary", "index_resource_launch_ok"]),
            "nervous_refresh_index_resource_allowed": nested_get(nervous_refresh_data, ["summary", "index_resource_allowed"]),
            "nervous_refresh_index_resource_blocked": nested_get(nervous_refresh_data, ["summary", "index_resource_blocked"]),
            "nervous_refresh_index_resource_denied": nested_get(nervous_refresh_data, ["summary", "index_resource_denied"]),
            "nervous_refresh_index_resource_soft_gated": nested_get(nervous_refresh_data, ["summary", "index_resource_soft_gated"]),
            "nervous_refresh_index_resource_decision": nested_get(nervous_refresh_data, ["summary", "index_resource_decision"]),
            "nervous_refresh_index_resource_sample_thermal": nested_get(nervous_refresh_data, ["summary", "index_resource_sample_thermal"]),
            "nervous_refresh_index_resource_gated": nested_get(nervous_refresh_data, ["summary", "index_resource_gated"]),
            "nervous_refresh_index_launch_blocked_reasons": nested_get(nervous_refresh_data, ["summary", "index_launch_blocked_reasons"]),
            "nervous_refresh_index_records_lag": nested_get(nervous_refresh_data, ["summary", "index_records_lag"]),
            "nervous_refresh_index_stale": nested_get(nervous_refresh_data, ["summary", "index_stale"]),
            "causal_context_records": sum(1 for item in record_items if isinstance(item.get("causal_context"), Mapping)),
            "parse_errors": len(parse_error_items),
            "ensure_errors": len(ensure_error_items),
        },
        "policy": {
            "mode": policy_data.get("mode"),
            "enabled": bool(policy_data.get("enabled")),
            "raw_keylogging": nested_get(policy_data, ["capture", "raw_keylogging"]),
            "requires_committed_text": nested_get(policy_data, ["capture", "requires_committed_text"]),
            "password_fields_captured": nested_get(policy_data, ["capture", "password_fields_captured"]),
        },
        "latest": {
            "ok": latest_data.get("ok"),
            "generated_at": latest_data.get("generated_at"),
            "status": latest_data.get("status"),
            "source_adapter": latest_data.get("source_adapter"),
            "capture_gate": latest_data.get("capture_gate") if isinstance(latest_data.get("capture_gate"), Mapping) else None,
            "causal_context": latest_data.get("causal_context") if isinstance(latest_data.get("causal_context"), Mapping) else None,
        },
        "coverage": dict(coverage_data),
        "process": dict(process_data),
        "gnome_accessibility": dict(gnome_data),
        "processing": dict(nervous_processing_data),
        "focused_snapshot": dict(focused_snapshot_data),
        "saved_text_scan": dict(saved_text_scan_data),
        "codex_session_tail": dict(codex_session_tail_data),
        "editor_extension": dict(editor_extension_data),
        "nervous_refresh": dict(nervous_refresh_data),
        "browser_content_capture": {
            "latest": browser_content_latest_path,
            "exists": bool(browser_content_data),
            "error": browser_content_error,
            "ok": browser_content_data.get("ok") if browser_content_data else None,
            "generated_at": browser_content_data.get("generated_at") if browser_content_data else None,
            "skipped": browser_content_data.get("skipped") if browser_content_data else None,
            "skip_reason": browser_content_data.get("skip_reason") if browser_content_data else None,
            "summary": browser_content_summary,
        },
        "paths": dict(paths),
        "errors": ensure_error_items + parse_error_items[:20],
    }


def _typing_validation_summary(checks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    check_items = [item for item in checks if isinstance(item, Mapping)]
    fails = sum(1 for item in check_items if item.get("level") == "fail")
    warnings = sum(1 for item in check_items if item.get("level") == "warn")
    return {
        "status": "fail" if fails else "warn" if warnings else "ok",
        "fails": fails,
        "warnings": warnings,
        "checks": len(check_items),
    }


def typing_validate_document(
    checks: Iterable[Mapping[str, Any]],
    *,
    strict: bool,
    generated_at: str,
    records_checked: int,
    paths: Mapping[str, Any],
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
) -> dict[str, Any]:
    check_items = [dict(item) for item in checks if isinstance(item, Mapping)]
    summary = _typing_validation_summary(check_items)
    return {
        "schema": f"{schema_prefix}_typing_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0 and (not strict or summary["warnings"] == 0),
        "strict": strict,
        "scope": "typing subsystem",
        "summary": summary,
        "checks": check_items,
        "policy": {
            "read_only": True,
            "future_safe": True,
            "severity_rule": "fail only for broken contracts or protected-boundary violations; warn for stale, missing optional, or future-expandable evidence",
        },
        "paths": dict(paths) if isinstance(paths, Mapping) else {},
        "records_checked": records_checked,
        "non_claims": [
            "This validates the safe intake surface; it does not prove every future source adapter is safe.",
            "Global typed-text capture still requires explicit safe adapters and must not use a raw keylogger.",
        ],
    }


def typing_end_to_end_document(
    checks: Iterable[Mapping[str, Any]],
    *,
    strict: bool,
    generated_at: str,
    artifacts: Mapping[str, Any],
    latest_path: str,
    history_path: str,
    skip_browser_atspi: bool,
    skip_browser_webextension: bool,
    skip_focused_browser: bool,
    skip_browser_privacy: bool,
    skip_editor_callback: bool,
    refresh_nervous: bool,
    schema_prefix: str = "abyss_machine",
    version: str = "0.0.0",
) -> dict[str, Any]:
    check_items = [dict(item) for item in checks if isinstance(item, Mapping)]
    summary = _typing_validation_summary(check_items)
    return {
        "schema": f"{schema_prefix}_typing_end_to_end_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0 and (not strict or summary["warnings"] == 0),
        "strict": strict,
        "scope": "typing end-to-end proof",
        "summary": summary,
        "checks": check_items,
        "artifacts": dict(artifacts) if isinstance(artifacts, Mapping) else {},
        "paths": {
            "latest": latest_path,
            "history": history_path,
        },
        "commands": {
            "self": "abyss-machine typing end-to-end --json",
            "without_live_browser_probe": "abyss-machine typing end-to-end --skip-browser-atspi --json",
            "without_browser_webextension_probe": "abyss-machine typing end-to-end --skip-browser-webextension --json",
            "without_focused_browser_probe": "abyss-machine typing end-to-end --skip-focused-browser --json",
            "without_browser_privacy_probe": "abyss-machine typing end-to-end --skip-browser-privacy --json",
            "without_live_editor_callback": "abyss-machine typing end-to-end --skip-editor-callback --json",
            "without_nervous_refresh": "abyss-machine typing end-to-end --no-refresh-nervous --json",
        },
        "policy": {
            "read_only": False,
            "future_safe": True,
            "password_required": False,
            "privileged_access_required": False,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "widens_capture": False,
            "automatic_action": False,
            "internet_access": False,
            "loopback_browser_probe_only": not skip_browser_atspi,
            "temporary_browser_webextension_probe": not skip_browser_webextension,
            "focused_browser_loopback_probe": not skip_focused_browser,
            "browser_privacy_loopback_probe": not skip_browser_privacy,
            "live_editor_callback_probe": not skip_editor_callback,
            "refreshes_nervous_snapshot_index": refresh_nervous,
        },
        "non_claims": [
            "This command proves the configured safe typing routes and processing chain now; it does not authorize raw keylogging.",
            "Firefox release-profile WebExtension activation remains separate from the temporary-profile WebExtension proof.",
            "The command may open a disposable VS Code window unless --skip-editor-callback is used.",
            "The command may open a temporary Firefox WebExtension selftest unless --skip-browser-webextension is used.",
            "The command may open a temporary Firefox loopback selftest unless --skip-browser-atspi is used.",
            "The command may open a temporary Firefox focused-browser selftest unless --skip-focused-browser is used.",
            "The command may open a temporary Firefox login/private privacy selftest unless --skip-browser-privacy is used.",
        ],
    }


def causal_browser_metadata_context(metadata: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(metadata, Mapping):
        return {}
    contexts = [
        metadata.get("browser") if isinstance(metadata.get("browser"), Mapping) else {},
        metadata.get("atspi") if isinstance(metadata.get("atspi"), Mapping) else {},
    ]
    for context in contexts:
        url = str(context.get("url") or "").strip()
        title = str(context.get("title") or context.get("document_title") or "").strip()
        if url or title:
            return {"url": url, "title": title}
    return {}


def ai_counterpart_recipient(ai_counterpart: Mapping[str, Any], app_text: str | None) -> dict[str, Any]:
    return {
        "kind": "ai_counterpart",
        "route": "browser_ai_interaction",
        "id": ai_counterpart.get("entity_id"),
        "name": ai_counterpart.get("label"),
        "provider": ai_counterpart.get("provider"),
        "product": ai_counterpart.get("product"),
        "family": ai_counterpart.get("family"),
        "surface": ai_counterpart.get("surface"),
        "origin": ai_counterpart.get("origin"),
        "browser_app": app_text or None,
        "confidence": ai_counterpart.get("confidence"),
    }


def causal_surface_kind(source_id: str) -> str:
    if source_id == "saved_text_snapshot":
        return "file"
    if source_id == "zsh_preexec":
        return "shell"
    if source_id in {"codex_user_prompt_submit", "codex_session_jsonl_prompt_tail"}:
        return "codex_session"
    if source_id == "browser_ai_transcript":
        return "browser_ai_transcript"
    if source_id == "atspi_focused_text_snapshot":
        return "focused_accessible"
    if source_id == "atspi_text_changed_event":
        return "accessibility_text_event"
    if source_id.startswith("manual_cli"):
        return "manual_cli"
    if "browser" in source_id:
        return "browser"
    if "editor" in source_id:
        return "editor"
    return "committed_text_adapter"


def causal_interaction_identity(
    source_id: str,
    context_payload: dict[str, Any],
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    app_text = context_payload_text(context_payload, "app")
    window_title = context_payload_text(context_payload, "window_title")
    context_text = context_payload_text(context_payload, "context")
    url_text = context_payload_text(context_payload, "url")
    meta = metadata if isinstance(metadata, Mapping) else {}
    codex_meta = meta.get("codex") if isinstance(meta.get("codex"), Mapping) else {}
    transcript_meta = meta.get("ai_transcript") if isinstance(meta.get("ai_transcript"), Mapping) else {}
    browser_metadata = causal_browser_metadata_context(meta)
    if not url_text:
        url_text = browser_metadata.get("url") or ""
    if not window_title:
        window_title = browser_metadata.get("title") or ""
    if source_id in {"codex_user_prompt_submit", "codex_session_jsonl_prompt_tail"}:
        session_id = str(codex_meta.get("session_id") or causal_extract_context_value(context_text, "session_id") or "").strip()
        turn_id = str(codex_meta.get("turn_id") or causal_extract_context_value(context_text, "turn_id") or "").strip()
        raw_route = str(codex_meta.get("raw_record_route") or "")
        fallback = bool(codex_meta.get("fallback") is True or source_id == "codex_session_jsonl_prompt_tail")
        if session_id:
            interaction_id = f"codex:{session_id}"
        else:
            basis = app_text + window_title + context_text
            interaction_id = f"codex:{hashlib.sha256(basis.encode('utf-8', errors='replace')).hexdigest()[:16]}"
        return {
            "kind": "codex_session",
            "id": interaction_id,
            "session_id": session_id or None,
            "turn_id": turn_id or None,
            "message_role": "user",
            "route": "native_user_prompt_submit_hook" if source_id == "codex_user_prompt_submit" else "codex_raw_jsonl_prompt_tail",
            "raw_record_route": raw_route or None,
            "fallback": fallback,
            "confidence": "native_codex_hook" if source_id == "codex_user_prompt_submit" else "raw_session_tail_fallback",
            "stores_extra_text": False,
        }
    page_identity = (
        transcript_meta.get("page_identity")
        if isinstance(transcript_meta.get("page_identity"), Mapping)
        else browser_ai_counterpart_identity(url_text, window_title)
    )
    if source_id == "browser_ai_transcript" or page_identity.get("is_ai") is True:
        origin = url_origin(url_text) or {}
        path_hash = url_path_hash(url_text) if origin.get("id") else {"url_path_present": False, "url_path_stored": False}
        title_hash = browser_title_fingerprint(window_title)
        counterpart_id = page_identity.get("entity_id") or origin.get("id") or "unknown_ai_page"
        thread_suffix = str(path_hash.get("url_path_sha256") or "")[:16]
        title_suffix = str(title_hash.get("title_sha256") or "")[:16]
        if thread_suffix:
            interaction_id = f"browser-ai:{counterpart_id}:{thread_suffix}"
        elif title_suffix:
            interaction_id = f"browser-ai:{counterpart_id}:title:{title_suffix}"
        else:
            interaction_id = f"browser-ai:{counterpart_id}"
        return {
            "kind": "browser_ai_conversation" if source_id == "browser_ai_transcript" else "browser_ai_page",
            "id": interaction_id,
            "ai_counterpart_id": counterpart_id,
            "provider": page_identity.get("provider"),
            "product": page_identity.get("product"),
            "family": page_identity.get("family"),
            "surface": page_identity.get("surface"),
            "origin": origin.get("origin") or page_identity.get("origin"),
            "host": origin.get("host") or page_identity.get("host"),
            "message_role": transcript_meta.get("message_role"),
            "message_index": transcript_meta.get("message_index"),
            "message_fingerprint": transcript_meta.get("message_fingerprint"),
            "completeness": transcript_meta.get("completeness"),
            **path_hash,
            **title_hash,
            "confidence": page_identity.get("confidence") or "browser_ai_page_identity",
            "stores_extra_text": False,
        }
    if "browser" in source_id:
        origin = url_origin(url_text) or {}
        if origin.get("id"):
            return {
                "kind": "browser_page",
                "id": origin.get("id"),
                "origin": origin.get("origin"),
                "host": origin.get("host"),
                "confidence": "observed_url_origin",
                "url_path_stored": False,
                "stores_extra_text": False,
            }
    surface_kind = causal_surface_kind(source_id)
    basis = app_text + window_title + context_text
    return {
        "kind": surface_kind,
        "id": f"{surface_kind}:{hashlib.sha256(basis.encode('utf-8', errors='replace')).hexdigest()[:16]}",
        "confidence": "adapter_surface_context",
        "stores_extra_text": False,
    }


def causal_recipient(source_id: str, context_payload: dict[str, Any], metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    app_text = context_payload_text(context_payload, "app")
    window_title = context_payload_text(context_payload, "window_title")
    url_text = context_payload_text(context_payload, "url")
    browser_metadata = causal_browser_metadata_context(metadata)
    if not url_text:
        url_text = browser_metadata.get("url") or ""
    if not window_title:
        window_title = browser_metadata.get("title") or ""
    metadata_payload = metadata if isinstance(metadata, Mapping) else {}
    transcript_meta = (
        metadata_payload.get("ai_transcript")
        if isinstance(metadata_payload.get("ai_transcript"), Mapping)
        else {}
    )
    transcript_identity = (
        transcript_meta.get("page_identity")
        if isinstance(transcript_meta.get("page_identity"), Mapping)
        else {}
    )
    ai_counterpart = (
        transcript_identity
        if transcript_identity.get("is_ai") is True
        else browser_ai_counterpart_identity(url_text, window_title)
    )
    file_meta = metadata_payload.get("file") if isinstance(metadata_payload.get("file"), Mapping) else {}
    if source_id == "saved_text_snapshot":
        return {
            "kind": "file",
            "route": "filesystem_saved_text",
            "id": str(file_meta.get("path") or window_title or "saved_text_file"),
            "name": str(file_meta.get("name") or window_title or ""),
            "confidence": "observed_file_path" if file_meta.get("path") else "adapter_inferred",
        }
    if source_id == "zsh_preexec":
        return {
            "kind": "shell",
            "route": "submitted_shell_command",
            "id": "zsh",
            "name": "zsh",
            "confidence": "adapter_contract",
        }
    if source_id in {"codex_user_prompt_submit", "codex_session_jsonl_prompt_tail"}:
        codex_meta = metadata_payload.get("codex") if isinstance(metadata_payload.get("codex"), Mapping) else {}
        session_id = str(codex_meta.get("session_id") or app_text or source_id)
        return {
            "kind": "codex_session",
            "route": "native_user_prompt_submit_hook" if source_id == "codex_user_prompt_submit" else "codex_raw_jsonl_prompt_tail",
            "id": session_id,
            "name": window_title or app_text or "codex",
            "confidence": "native_codex_hook" if source_id == "codex_user_prompt_submit" else "raw_session_tail_fallback",
        }
    if ai_counterpart.get("is_ai") is True and (
        source_id in {"atspi_focused_text_snapshot", "atspi_text_changed_event", "browser_extension_explicit"}
        or "browser" in source_id
    ):
        return ai_counterpart_recipient(ai_counterpart, app_text)
    if source_id in {"atspi_focused_text_snapshot", "atspi_text_changed_event"}:
        return {
            "kind": "focused_application",
            "route": "accessibility_committed_text_event" if source_id == "atspi_text_changed_event" else "focused_accessibility_text_node",
            "id": app_text or window_title or "focused_application",
            "name": window_title or app_text,
            "confidence": "focused_accessibility_node",
        }
    if source_id.startswith("manual_cli"):
        return {
            "kind": "typing_cli",
            "route": "manual_committed_text_ingest",
            "id": app_text or "abyss-machine typing ingest",
            "name": app_text or "abyss-machine typing ingest",
            "confidence": "explicit_cli",
        }
    if "browser" in source_id:
        return {
            "kind": "browser_extension",
            "route": "explicit_browser_adapter",
            "id": app_text or window_title or source_id,
            "name": window_title or app_text,
            "confidence": "adapter_inferred",
        }
    if "editor" in source_id:
        return {
            "kind": "editor_extension",
            "route": "explicit_editor_adapter",
            "id": app_text or window_title or source_id,
            "name": window_title or app_text,
            "confidence": "adapter_inferred",
        }
    return {
        "kind": "unknown_committed_text_adapter",
        "route": source_id,
        "id": app_text or source_id,
        "name": window_title or app_text,
        "confidence": "source_adapter_only",
    }


def extract_context_paths(context_text: str) -> list[str]:
    text = str(context_text or "")
    paths: list[str] = []
    for match in re.findall(r"(?:^|\s)(?:cwd|path|root|file)=(/[^\s]+)", text):
        cleaned = match.rstrip(".,;)")
        if cleaned and cleaned not in paths:
            paths.append(cleaned)
    for match in re.findall(r"(?:^|\s)(/[^\s]+)", text):
        cleaned = match.rstrip(".,;)")
        if cleaned and cleaned not in paths:
            paths.append(cleaned)
    return paths


def causal_surface_paths(
    context_payload: dict[str, Any],
    metadata: dict[str, Any] | None,
    signal_text: str | None = None,
) -> list[str]:
    paths: list[str] = []
    file_meta = metadata.get("file") if isinstance(metadata, dict) and isinstance(metadata.get("file"), dict) else {}
    for value in (file_meta.get("path"), file_meta.get("root")):
        if value:
            paths.append(str(value))
    context_text = context_payload_text(context_payload, "context")
    for cleaned in extract_context_paths(context_text):
        if cleaned not in paths:
            paths.append(cleaned)
    for cleaned in extract_context_paths(str(signal_text or "")):
        if cleaned not in paths:
            paths.append(cleaned)
    return paths[:8]


def capture_gate_paths(context: str | None, metadata: dict[str, Any] | None, paths: list[str] | None = None) -> list[str]:
    context_payload = {"context": {"text": str(context or "")}}
    merged: list[str] = []
    for path in causal_surface_paths(context_payload, metadata):
        if path not in merged:
            merged.append(path)
    for path in paths or []:
        path_text = str(path or "").strip()
        if path_text and path_text not in merged:
            merged.append(path_text)
    return merged[:12]


def path_under(path: str, root: str) -> bool:
    path_text = str(path or "").replace("\\", "/").rstrip("/")
    root_text = str(root or "").replace("\\", "/").rstrip("/")
    return bool(path_text and root_text and (path_text == root_text or path_text.startswith(root_text + "/")))


def capture_gate_path_allowed(path: str, roots: list[Any]) -> bool:
    return any(path_under(path, str(root or "")) for root in roots if str(root or "").strip())


def capture_gate_context_flag(probe: str, key: str) -> bool:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(true|1|yes)\b", str(probe or ""), re.I)
    return bool(match)


def capture_gate_context_field(probe: str, key: str) -> str:
    match = re.search(rf"(?:^|\s){re.escape(key)}=([^\s]+)", str(probe or ""), re.I)
    return match.group(1) if match else ""


def capture_gate_atspi_shape(
    source_id: str,
    app_probe: str,
    metadata_payload: dict[str, Any],
    policy_data: dict[str, Any],
) -> dict[str, Any]:
    atspi_meta = metadata_payload.get("atspi") if isinstance(metadata_payload.get("atspi"), dict) else {}
    states = atspi_meta.get("states") if isinstance(atspi_meta.get("states"), dict) else {}
    route_policy = (
        policy_data.get("focused_snapshot")
        if source_id == "atspi_focused_text_snapshot" and isinstance(policy_data.get("focused_snapshot"), dict)
        else policy_data.get("atspi_text_events")
    )
    route_policy = route_policy if isinstance(route_policy, dict) else {}
    role = str(atspi_meta.get("role") or capture_gate_context_field(app_probe, "role") or "")
    role_lower = role.lower()
    text_roles = {str(item).lower() for item in route_policy.get("text_roles", []) if str(item).strip()}
    sensitive_roles = {str(item).lower() for item in route_policy.get("sensitive_roles", []) if str(item).strip()}
    editable = bool(states.get("editable")) or capture_gate_context_flag(app_probe, "editable")
    focused = bool(states.get("focused")) or capture_gate_context_flag(app_probe, "focused")
    showing = bool(states.get("showing")) or capture_gate_context_flag(app_probe, "showing")
    visible = bool(states.get("visible")) or capture_gate_context_flag(app_probe, "visible")
    enabled = bool(states.get("enabled")) or capture_gate_context_flag(app_probe, "enabled")
    sensitive_state = bool(states.get("sensitive")) or capture_gate_context_flag(app_probe, "sensitive")
    text_role = bool(role_lower in text_roles or editable or role_lower in {"entry", "text"})
    role_sensitive = bool(role_lower in sensitive_roles or "password" in role_lower or sensitive_state)
    return {
        "role": role,
        "text_role": text_role,
        "editable": editable,
        "focused": focused,
        "showing": showing,
        "visible": visible,
        "enabled": enabled,
        "sensitive_state": sensitive_state,
        "role_sensitive": role_sensitive,
    }


def sanitize_context_value(
    value: str | None,
    max_chars: int,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    raw = str(value or "").strip()
    redacted = nervous_redaction.redact_text(
        raw,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    text = str(redacted.get("redacted_text") or "")
    truncated = len(text) > max_chars
    return {
        "text": text[:max_chars] if truncated else text,
        "sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest() if raw else None,
        "length": len(raw),
        "truncated": truncated,
        "redaction": redacted.get("summary"),
    }


def capture_gate_decision_document(
    *,
    source: str,
    app: str | None = None,
    window_title: str | None = None,
    context: str | None = None,
    url: str | None = None,
    metadata: dict[str, Any] | None = None,
    paths: list[str] | None = None,
    policy: dict[str, Any],
    default_policy: dict[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    policy_data = policy if isinstance(policy, dict) else {}
    gate = capture_gate_policy(policy_data, default_policy)
    source_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(source or "manual_cli_stdin")).strip("_")[:80] or "manual_cli_stdin"
    metadata_payload = metadata if isinstance(metadata, dict) else {}
    surface_paths = capture_gate_paths(context, metadata_payload, paths)
    app_probe = " ".join(str(item or "") for item in (app, window_title, context))
    url_text = str(url or metadata_payload.get("url") or "")
    matches: list[dict[str, Any]] = []
    reasons: list[str] = []
    decision = str(gate.get("default_decision") or "metadata_only")
    confidence = "default"
    enabled = gate.get("enabled") is not False
    saved_policy_data = saved_text_policy(policy_data, default_policy)
    if not enabled:
        decision = "allow_text"
        confidence = "gate_disabled"
        reasons.append("capture_gate_disabled")
    else:
        hard_app = capture_gate_token_matches("hard_skip_app_token", app_probe, gate.get("hard_skip_app_tokens", []))
        hard_url = capture_gate_token_matches("hard_skip_url_token", url_text, gate.get("hard_skip_url_tokens", []))
        metadata_url = capture_gate_token_matches("metadata_only_url_token", url_text, gate.get("metadata_only_url_tokens", []))
        metadata_app = capture_gate_token_matches("metadata_only_app_token", app_probe, gate.get("metadata_only_app_tokens", []))
        deny_context = deny_context_matches("\n".join([source_id, app_probe, url_text]), policy_data)
        excluded_paths: list[dict[str, Any]] = []
        denied_paths: list[dict[str, Any]] = []
        for path in surface_paths:
            excluded_paths.extend({"path": path, **item} for item in saved_text_path_excluded(Path(path), saved_policy_data))
            denied_paths.extend({"path": path, **item} for item in saved_text_path_denied(Path(path), saved_policy_data))
        matches.extend(hard_app + hard_url + metadata_url + metadata_app + deny_context + excluded_paths + denied_paths)
        if hard_app or hard_url:
            decision = "skip"
            confidence = "hard_skip"
            reasons.append("hard_skip_private_or_messenger_context")
        elif denied_paths:
            decision = "metadata_only"
            confidence = "sensitive_path"
            reasons.append("sensitive_path_denied_before_text_persistence")
        elif metadata_url:
            decision = "metadata_only"
            confidence = "sensitive_url"
            reasons.append("url_contains_login_auth_payment_or_secret_token")
        elif deny_context:
            decision = "metadata_only"
            confidence = "sensitive_context"
            reasons.append("context_contains_sensitive_token")
        elif excluded_paths:
            decision = "skip"
            confidence = "excluded_path"
            reasons.append("path_is_excluded_from_text_capture")
        elif source_id == "browser_extension_explicit":
            browser_policy = browser_extension_policy(policy_data, default_policy)
            browser_meta = metadata_payload.get("browser") if isinstance(metadata_payload.get("browser"), dict) else {}
            context_text = str(context or "")
            field_safe = browser_meta.get("field_safe") is True or bool(re.search(r"\bfield_safe=(true|1|yes)\b", context_text, re.I))
            event_kind_match = re.search(r"\bevent_kind=([A-Za-z0-9_.:-]+)", context_text)
            event_kind = str(browser_meta.get("event_kind") or (event_kind_match.group(1) if event_kind_match else ""))
            allowed_event_kinds = {str(item) for item in browser_policy.get("allowed_event_kinds", []) if str(item).strip()}
            event_kind_allowed = not allowed_event_kinds or event_kind in allowed_event_kinds
            url_present = bool(str(url_text or "").strip())
            url_scheme_allowed = browser_url_scheme_allowed(url_text, browser_policy)
            if not url_present:
                decision = "metadata_only"
                confidence = "browser_url_missing"
                reasons.append("browser_extension_requires_url_before_text_capture")
            elif not url_scheme_allowed:
                decision = "metadata_only"
                confidence = "browser_url_scheme_not_allowed"
                reasons.append("browser_extension_url_scheme_not_allowed")
            elif not field_safe:
                decision = "metadata_only"
                confidence = "browser_field_not_safe"
                reasons.append("browser_extension_field_safety_not_proven")
            elif not event_kind_allowed:
                decision = "metadata_only"
                confidence = "browser_event_kind_not_allowed"
                reasons.append("browser_extension_event_kind_not_allowed")
            else:
                decision = "allow_text"
                confidence = "browser_url_and_field_allowed"
                reasons.append("browser_extension_url_and_field_passed_safe_contract")
        elif source_id == "browser_ai_transcript":
            transcript_policy = browser_ai_transcript_policy(policy_data, default_policy)
            browser_meta = metadata_payload.get("browser") if isinstance(metadata_payload.get("browser"), dict) else {}
            transcript_meta = metadata_payload.get("ai_transcript") if isinstance(metadata_payload.get("ai_transcript"), dict) else {}
            context_text = str(context or "")
            transcript_safe = (
                transcript_meta.get("safe") is True
                or browser_meta.get("transcript_safe") is True
                or bool(re.search(r"\btranscript_safe=(true|1|yes)\b", context_text, re.I))
            )
            event_kind_match = re.search(r"\bevent_kind=([A-Za-z0-9_.:-]+)", context_text)
            role_match = re.search(r"\bmessage_role=([A-Za-z0-9_.:-]+)", context_text)
            event_kind = str(browser_meta.get("event_kind") or transcript_meta.get("event_kind") or (event_kind_match.group(1) if event_kind_match else ""))
            message_role = str(transcript_meta.get("message_role") or (role_match.group(1) if role_match else "unknown")).lower()
            allowed_event_kinds = {str(item) for item in transcript_policy.get("allowed_event_kinds", []) if str(item).strip()}
            event_kind_allowed = not allowed_event_kinds or event_kind in allowed_event_kinds
            allowed_roles = {str(item).lower() for item in transcript_policy.get("allowed_message_roles", []) if str(item).strip()}
            role_allowed = not allowed_roles or message_role in allowed_roles
            url_present = bool(str(url_text or "").strip())
            url_scheme_allowed = browser_url_scheme_allowed(url_text, transcript_policy)
            ai_identity = browser_ai_counterpart_identity(url_text, window_title, schema_prefix=schema_prefix)
            known_ai = ai_identity.get("is_ai") is True
            if not url_present:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_url_missing"
                reasons.append("browser_ai_transcript_requires_url_before_text_capture")
            elif not url_scheme_allowed:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_url_scheme_not_allowed"
                reasons.append("browser_ai_transcript_url_scheme_not_allowed")
            elif not known_ai:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_unknown_ai_counterpart"
                reasons.append("browser_ai_transcript_requires_known_ai_counterpart")
            elif not transcript_safe:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_safe_marker_missing"
                reasons.append("browser_ai_transcript_safe_marker_missing")
            elif not event_kind_allowed:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_event_kind_not_allowed"
                reasons.append("browser_ai_transcript_event_kind_not_allowed")
            elif not role_allowed:
                decision = "metadata_only"
                confidence = "browser_ai_transcript_role_not_allowed"
                reasons.append("browser_ai_transcript_message_role_not_allowed")
            else:
                decision = "allow_text"
                confidence = "browser_ai_transcript_known_ai_page_allowed"
                reasons.append("browser_ai_transcript_known_ai_page_and_role_allowed")
        elif source_id not in set(gate.get("allow_text_source_adapters") or []):
            decision = str(gate.get("unknown_decision") or "metadata_only")
            confidence = "unknown_adapter"
            reasons.append("source_adapter_not_in_allow_text_set")
        elif source_id == "saved_text_snapshot":
            roots = saved_policy_data.get("roots") if isinstance(saved_policy_data.get("roots"), list) else gate.get("allow_text_path_roots", [])
            allowed = any(capture_gate_path_allowed(path, roots) for path in surface_paths)
            decision = "allow_text" if allowed else "metadata_only"
            confidence = "safe_saved_text_root" if allowed else "saved_text_root_not_allowed"
            reasons.append("saved_text_path_under_allowed_root" if allowed else "saved_text_path_outside_allowed_roots")
        elif source_id in {"manual_cli_stdin", "manual_cli_args", "zsh_preexec", "codex_user_prompt_submit", "codex_session_jsonl_prompt_tail"}:
            decision = "allow_text"
            confidence = "explicit_committed_text_adapter"
            reasons.append("explicit_committed_text_adapter")
        elif source_id == "atspi_focused_text_snapshot":
            focused_policy = policy_data.get("focused_snapshot") if isinstance(policy_data.get("focused_snapshot"), dict) else {}
            safe_routes = {
                str(item).strip()
                for item in (focused_policy.get("safe_text_routes") or ["browser_safe_url"])
                if str(item).strip()
            }
            atspi_shape = capture_gate_atspi_shape(source_id, app_probe, metadata_payload, policy_data)
            generic_policy = focused_policy.get("generic_editable_text") if isinstance(focused_policy.get("generic_editable_text"), dict) else {}
            browser_policy = browser_extension_policy(policy_data, default_policy)
            browser_app = bool(capture_gate_token_matches("browser_app_token", app_probe, ["firefox", "chrome", "chromium"]))
            terminal_surface = bool(
                capture_gate_token_matches("terminal_app_token", app_probe, ["terminal", "gnome-terminal", "kitty", "alacritty", "wezterm"])
                or str(atspi_shape.get("role") or "").lower() == "terminal"
            )
            browser_url_allowed = bool(browser_app and browser_url_scheme_allowed(url_text, browser_policy) and url_origin(url_text))
            if "browser_safe_url" in safe_routes and browser_url_allowed:
                decision = "allow_text"
                confidence = "focused_browser_safe_url_allowed"
                reasons.append("focused_snapshot_browser_url_passed_safe_contract")
            elif (
                "generic_editable_text" in safe_routes
                and generic_policy.get("enabled") is not False
                and not browser_app
                and not terminal_surface
                and atspi_shape.get("text_role") is True
                and (atspi_shape.get("editable") is True or generic_policy.get("requires_editable") is False)
                and (atspi_shape.get("focused") is True or generic_policy.get("requires_focused") is False)
                and atspi_shape.get("role_sensitive") is not True
            ):
                decision = "allow_text"
                confidence = "focused_generic_editable_text_allowed"
                reasons.append("focused_snapshot_generic_text_role_passed_local_exclusion_gate")
            else:
                decision = "metadata_only"
                confidence = "focused_snapshot_no_safe_route"
                reasons.append("focused_snapshot_requires_safe_browser_url_or_generic_editable_text")
        elif source_id == "atspi_text_changed_event":
            app_allowed = bool(capture_gate_token_matches("focused_allow_app_token", app_probe, gate.get("focused_allow_app_tokens", [])))
            path_allowed = any(capture_gate_path_allowed(path, gate.get("allow_text_path_roots", [])) for path in surface_paths)
            atspi_shape = capture_gate_atspi_shape(source_id, app_probe, metadata_payload, policy_data)
            events_policy = policy_data.get("atspi_text_events") if isinstance(policy_data.get("atspi_text_events"), dict) else {}
            generic_policy = events_policy.get("generic_editable_text") if isinstance(events_policy.get("generic_editable_text"), dict) else {}
            browser_policy = browser_extension_policy(policy_data, default_policy)
            browser_app = bool(capture_gate_token_matches("browser_app_token", app_probe, ["firefox", "chrome", "chromium"]))
            browser_url_allowed = browser_app and browser_url_scheme_allowed(url_text, browser_policy)
            if app_allowed or path_allowed or browser_url_allowed:
                decision = "allow_text"
                confidence = "atspi_browser_url_allowed" if browser_url_allowed and not (app_allowed or path_allowed) else "atspi_app_or_path_allowed"
                reasons.append("atspi_context_matches_allowed_app_path_or_safe_browser_url")
            elif (
                generic_policy.get("enabled") is not False
                and not browser_app
                and atspi_shape.get("text_role") is True
                and (atspi_shape.get("editable") is True or generic_policy.get("requires_editable") is False)
                and (
                    atspi_shape.get("focused") is True
                    or atspi_shape.get("visible") is True
                    or atspi_shape.get("showing") is True
                    or generic_policy.get("requires_focus_or_visible") is False
                )
                and atspi_shape.get("role_sensitive") is not True
            ):
                decision = "allow_text"
                confidence = "atspi_generic_editable_text_allowed"
                reasons.append("atspi_generic_text_role_passed_local_exclusion_gate")
            else:
                decision = "metadata_only"
                confidence = "atspi_unknown_app"
                reasons.append("atspi_text_from_unknown_app_defaults_metadata_only")
        elif source_id == "editor_extension_explicit":
            path_allowed = any(capture_gate_path_allowed(path, gate.get("allow_text_path_roots", [])) for path in surface_paths)
            decision = "allow_text" if path_allowed else "metadata_only"
            confidence = "editor_path_allowed" if path_allowed else "editor_path_missing_or_unknown"
            reasons.append("editor_path_under_allowed_root" if path_allowed else "editor_adapter_without_allowed_path")
        else:
            decision = str(gate.get("unknown_decision") or "metadata_only")
            confidence = "unknown_adapter"
            reasons.append("default_unknown_context")
    if decision not in {"allow_text", "metadata_only", "skip", "needs_review"}:
        decision = "metadata_only"
        reasons.append("invalid_policy_decision_normalized")
    return {
        "schema": f"{schema_prefix}_typing_capture_gate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "source_adapter": source_id,
        "decision": decision,
        "confidence": confidence,
        "reasons": reasons,
        "matches": matches[:24],
        "context": {
            "app": sanitize_context_value(app, 160, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
            "window_title": sanitize_context_value(window_title, 160, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
            "context": sanitize_context_value(context, 240, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
            "url": sanitize_context_value(url_text, 240, schema_prefix=schema_prefix, version=version, generated_at=generated_at),
            "paths": surface_paths,
        },
        "agent": {
            "id": nested_get(gate, ["offline_agent", "id"]) or "typing_capture_gate_agent",
            "kind": nested_get(gate, ["offline_agent", "kind"]) or "local_rule_engine",
            "network_access": False,
            "subprocess_access": False,
            "may_promote_unknown_to_allow_text": False,
            "may_promote_safe_generic_text_role": nested_get(gate, ["offline_agent", "may_promote_safe_generic_text_role"]) is not False,
        },
        "policy": {
            "default_decision": gate.get("default_decision"),
            "unknown_decision": gate.get("unknown_decision"),
            "metadata_everywhere": True,
            "text_requires_high_confidence": True,
            "automatic_action": False,
            "internet_access": False,
        },
        "non_claims": [
            "capture_gate classifies observable context only; it does not infer final intent.",
            "allow_text is limited to high-confidence adapters and safe surfaces.",
            "skip means text is not persisted; with store_skip_events enabled only bounded metadata may be recorded by the caller.",
        ],
    }


def browser_extension_message_metadata(
    message: dict[str, Any],
    *,
    extension_id: str,
    native_host: str,
) -> dict[str, Any]:
    field = message.get("field") if isinstance(message.get("field"), dict) else {}
    browser = message.get("browser") if isinstance(message.get("browser"), dict) else {}
    event_kind = str(message.get("event_kind") or browser.get("event_kind") or "")
    field_safe = field.get("safe") is True or browser.get("field_safe") is True
    return {
        "browser": {
            "adapter": "browser_extension_explicit",
            "extension_id": extension_id,
            "native_host": native_host,
            "browser": str(message.get("browser_name") or browser.get("name") or "firefox")[:80],
            "event_kind": event_kind,
            "field_safe": bool(field_safe),
            "field_kind": str(field.get("kind") or "")[:80],
            "field_type": str(field.get("type") or "")[:80],
            "frame_kind": str(message.get("frame_kind") or "")[:80],
            "url_present": bool(str(message.get("url") or "").strip()),
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "key_events_captured": False,
        }
    }


def browser_ai_transcript_clean_text(text: str) -> dict[str, Any]:
    raw = str(text or "")
    cleaned = raw.replace("\u00a0", " ").strip()
    exact_ui_labels = {
        "развернуть",
        "свернуть",
        "expand",
        "collapse",
        "show more",
        "show less",
        "read more",
        "show original",
        "hide",
    }
    lines = []
    removed_lines = 0
    for line in cleaned.splitlines():
        compact = re.sub(r"\s+", " ", line).strip()
        if compact.lower() in exact_ui_labels:
            removed_lines += 1
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    removed_suffixes: list[str] = []
    suffixes = (
        "РазвернутьСвернуть",
        "СвернутьРазвернуть",
        "Развернуть",
        "Свернуть",
        "ExpandCollapse",
        "CollapseExpand",
        "Show moreShow less",
        "Show lessShow more",
        "Show more",
        "Show less",
        "Read more",
        "Collapse",
        "Expand",
    )
    changed = True
    while changed and cleaned:
        changed = False
        stripped = cleaned.rstrip()
        for suffix in suffixes:
            if stripped.endswith(suffix):
                cleaned = stripped[: -len(suffix)].rstrip()
                removed_suffixes.append(suffix)
                changed = True
                break
    return {
        "text": cleaned,
        "changed": cleaned != raw.strip(),
        "raw_length": len(raw),
        "cleaned_length": len(cleaned),
        "removed_line_count": removed_lines,
        "removed_suffixes": removed_suffixes[:12],
        "stores_extra_text": False,
    }


def browser_ai_transcript_normalize_role(role: str, text: str, page_identity: dict[str, Any]) -> dict[str, Any]:
    raw_role = str(role or "unknown").lower()[:40] or "unknown"
    if raw_role in {"user", "assistant", "system"}:
        return {"role": raw_role, "raw_role": raw_role, "basis": "extension_role"}
    compact = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    product = str(page_identity.get("product") or "").lower()
    provider = str(page_identity.get("provider") or "").lower()
    if compact.startswith(("ваш запрос", "your prompt", "your query", "user prompt")):
        return {"role": "user", "raw_role": raw_role, "basis": "visible_transcript_label"}
    if compact.startswith(("ответ gemini", "gemini ответ", "gemini says", "response from gemini")):
        return {"role": "assistant", "raw_role": raw_role, "basis": "visible_transcript_label"}
    if product == "gemini" and compact.startswith(("ответ", "response")):
        return {"role": "assistant", "raw_role": raw_role, "basis": "provider_visible_label"}
    if provider == "openai" and compact.startswith(("chatgpt", "ответ chatgpt", "chatgpt said")):
        return {"role": "assistant", "raw_role": raw_role, "basis": "provider_visible_label"}
    return {"role": raw_role, "raw_role": raw_role, "basis": "extension_unknown"}


def browser_ai_transcript_message_metadata(
    message: dict[str, Any],
    *,
    extension_id: str,
    native_host: str,
    page_identity: dict[str, Any],
) -> dict[str, Any]:
    browser = message.get("browser") if isinstance(message.get("browser"), dict) else {}
    transcript = message.get("ai_transcript") if isinstance(message.get("ai_transcript"), dict) else {}
    event_kind = str(message.get("event_kind") or browser.get("event_kind") or transcript.get("event_kind") or "")
    role_normalization = browser_ai_transcript_normalize_role(
        str(transcript.get("message_role") or "unknown"),
        str(message.get("text") or ""),
        page_identity,
    )
    message_role = str(role_normalization.get("role") or "unknown").lower()[:40]
    message_index = _safe_int(transcript.get("message_index"), 0)
    fingerprint_basis = "\n".join([
        str(message.get("url") or ""),
        str(message.get("title") or ""),
        message_role,
        str(message_index),
        str(message.get("text") or ""),
    ])
    return {
        "browser": {
            "adapter": "browser_ai_transcript",
            "extension_id": extension_id,
            "native_host": native_host,
            "browser": str(message.get("browser_name") or browser.get("name") or "firefox")[:80],
            "event_kind": event_kind,
            "transcript_safe": bool(transcript.get("safe") is True or browser.get("transcript_safe") is True),
            "frame_kind": str(message.get("frame_kind") or "")[:80],
            "url_present": bool(str(message.get("url") or "").strip()),
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "key_events_captured": False,
        },
        "ai_transcript": {
            "safe": bool(transcript.get("safe") is True or browser.get("transcript_safe") is True),
            "message_role": message_role,
            "message_role_raw": role_normalization.get("raw_role"),
            "message_role_basis": role_normalization.get("basis"),
            "message_index": message_index,
            "message_order": _safe_int(transcript.get("message_order"), message_index),
            "partial": bool(transcript.get("partial")),
            "selector_basis": str(transcript.get("selector_basis") or "")[:120] or None,
            "reason": str(transcript.get("reason") or "")[:120] or None,
            "message_fingerprint": hashlib.sha256(fingerprint_basis.encode("utf-8", errors="replace")).hexdigest(),
            "page_identity": page_identity if page_identity.get("is_ai") is True else None,
            "completeness": "partial" if bool(transcript.get("partial")) else "message_visible_dom",
            "stores_extra_text": False,
        },
    }
