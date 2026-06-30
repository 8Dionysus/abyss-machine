from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from . import nervous_redaction
from . import typing_capture_contracts


DEFAULT_MAX_HASH_BYTES = 8 * 1024 * 1024

BROWSER_BOILERPLATE_PATTERNS = [
    r"^skip to content$",
    r"^перейти к содержимому$",
    r"^type / to search$",
    r"^repository navigation$",
    r"^repository files navigation$",
    r"^footer navigation$",
    r"^footer ©",
    r"^terms privacy status community docs contact$",
    r"^terms privacy",
    r"^github profile guide$",
    r"^user navigation$",
    r"^overview$",
    r"^repositories$",
    r"^packages$",
    r"^watch(?:ers watching)?$",
    r"^stars?$",
    r"^forks?$",
    r"^branches?$",
    r"^tags?$",
    r"^settings$",
    r"^insights$",
    r"^security and quality$",
    r"^actions$",
    r"^projects$",
    r"^wiki$",
    r"^issues$",
    r"^pull requests$",
    r"^add file$",
    r"^folders and files$",
    r"^last commit (message|date)$",
    r"^latest commit$",
    r"^history$",
    r"^code of conduct$",
    r"^contributing$",
    r"^apache-2\.0 license$",
    r"^security$",
    r"^вход$",
    r"^регистрация$",
    r"^главная$",
    r"^новинки$",
    r"^топ (фильмов|сериалов|мультфильмов|мультсериалов|аниме)$",
    r"^панель навигации \|?$",
    r"^мои списки$",
    r"^все фильмы$",
    r"^созданные$",
    r"^сохраненные$",
    r"^создать$",
    r"^изменить профиль$",
]

BROWSER_MEDIA_PATTERNS = [
    r"\b(пауза|воспроизвести) \(space\)",
    r"\bпредыдущая серия\b",
    r"\bследующая серия\b",
    r"\bвыключить звук\b",
    r"\bвыключить субтитры\b",
    r"\bвыйти из полноэкранного режима\b",
    r"^\d{1,2}:\d{2}$",
    r"^/\d{1,2}:\d{2}$",
    r"^⁄\d{1,2}:\d{2}$",
]

WEB_CONTEXT_CLASSES = {
    "ai_interaction",
    "project",
    "docs",
    "research",
    "tooling",
    "admin",
    "login_sensitive",
    "entertainment",
    "browser_internal",
    "low_signal",
    "unknown",
}


def default_state(schema_prefix: str, version: str) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_sources_state_v1",
        "version": version,
        "overrides": {},
        "updated_at": None,
        "updated_by": "default",
        "last_change_id": None,
    }


def state_document(
    *,
    defaults: Mapping[str, Any],
    loaded: Mapping[str, Any] | None,
    load_error: str | None,
    path: str,
    exists: bool,
) -> dict[str, Any]:
    if loaded is None:
        state = dict(defaults)
        if load_error != "missing":
            state["_load_error"] = load_error
    else:
        state = _deep_merge(dict(defaults), dict(loaded))
    if not isinstance(state.get("overrides"), dict):
        state["overrides"] = {}
    state["path"] = path
    state["exists"] = exists
    return state


def saved_state_document(
    state: Mapping[str, Any],
    *,
    updated_by: str,
    change_id: str,
    updated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_sources_state_v1",
        "version": version,
        "overrides": state.get("overrides", {}) if isinstance(state.get("overrides"), dict) else {},
        "updated_at": updated_at,
        "updated_by": updated_by,
        "last_change_id": change_id,
    }


def effective_sources(config: Mapping[str, Any], state: Mapping[str, Any], *, state_path: str) -> dict[str, Any]:
    effective = _deep_merge({}, dict(config))
    overrides = state.get("overrides", {}) if isinstance(state.get("overrides"), dict) else {}
    for source_id, override in overrides.items():
        if not isinstance(override, dict):
            continue
        for group_name in ("safe_now", "deferred_until_privacy_controls"):
            group = effective.get(group_name)
            if isinstance(group, dict) and isinstance(group.get(source_id), dict):
                group[source_id] = _deep_merge(dict(group[source_id]), {
                    "enabled": bool(override.get("enabled")),
                    "state_override": dict(override),
                })
    effective["state"] = dict(state)
    effective["state_path"] = state_path
    return effective


def source_catalog(
    sources: Mapping[str, Any],
    *,
    config_path: str,
    state_path: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for group_name in ("safe_now", "deferred_until_privacy_controls"):
        group = sources.get(group_name)
        if not isinstance(group, dict):
            continue
        for source_id, data in group.items():
            if not isinstance(data, dict):
                continue
            allowed = bool(data.get("allowed", True))
            items.append({
                "id": source_id,
                "group": group_name,
                "enabled": bool(data.get("enabled")),
                "allowed": allowed,
                "content": data.get("content"),
                "notes": data.get("notes"),
                "state_override": data.get("state_override"),
                "can_enable_now": allowed,
                "enable_blocker": None if allowed else "source is not allowed by policy",
            })
    state = sources.get("state", {}) if isinstance(sources.get("state"), dict) else {}
    return {
        "schema": f"{schema_prefix}_nervous_sources_list_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": sources.get("_load_error") is None and state.get("_load_error") is None,
        "config_path": config_path,
        "state_path": state_path,
        "items": sorted(items, key=lambda item: (item["group"], item["id"])),
        "state": state,
    }


def source_lookup(catalog: Mapping[str, Any], source_id: str) -> dict[str, Any] | None:
    items = catalog.get("items") if isinstance(catalog.get("items"), list) else []
    for item in items:
        if isinstance(item, dict) and item.get("id") == source_id:
            return item
    return None


def source_set_unknown_result(
    source_id: str,
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_source_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "source": source_id,
        "error": "unknown source",
    }


def source_set_blocked_result(
    source_id: str,
    source_status: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_source_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "source": source_id,
        "error": source_status.get("enable_blocker") or "source cannot be enabled now",
        "source_status": dict(source_status),
    }


def source_set_write_failed_result(
    source_id: str,
    *,
    before: bool,
    after: bool,
    state: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_source_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "source": source_id,
        "changed": False,
        "attempted_change": before != after,
        "error": "state write failed",
        "state": dict(state),
        "write_errors": list(state.get("write_errors", [])) if isinstance(state.get("write_errors"), list) else [],
    }


def source_set_transition(
    *,
    source_id: str,
    enabled: bool,
    source_status: Mapping[str, Any],
    state: Mapping[str, Any],
    updated_at: str,
    reason: str | None,
) -> dict[str, Any]:
    overrides = dict(state.get("overrides", {})) if isinstance(state.get("overrides"), dict) else {}
    before = bool(source_status.get("enabled"))
    overrides[source_id] = {
        "enabled": enabled,
        "updated_at": updated_at,
        "updated_by": f"source-{'enable' if enabled else 'disable'}",
        "reason": reason or f"{source_id} {'enabled' if enabled else 'disabled'}",
    }
    next_state = dict(state)
    next_state["overrides"] = overrides
    return {
        "source": source_id,
        "before": before,
        "after": enabled,
        "state": next_state,
    }


def source_set_audit_event(
    *,
    change_id: Any,
    source_id: str,
    before: bool,
    after: bool,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "event": "source_state_changed",
        "change_id": change_id,
        "source": source_id,
        "before": before,
        "after": after,
        "reason": reason,
    }


def source_set_result(
    *,
    source_id: str,
    before: bool,
    after: bool,
    state: Mapping[str, Any],
    audit: Mapping[str, Any],
    effective: Mapping[str, Any] | None,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_nervous_source_set_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "source": source_id,
        "changed": before != after,
        "state": dict(state),
        "audit": dict(audit),
        "effective": dict(effective) if effective is not None else None,
    }


def file_source(
    path: Path | str,
    *,
    read_at: str,
    max_hash_bytes: int = DEFAULT_MAX_HASH_BYTES,
    hash_chunk_bytes: int = 1024 * 1024,
) -> dict[str, Any]:
    source_path = Path(path)
    source: dict[str, Any] = {
        "path": str(source_path),
        "exists": source_path.exists(),
        "read_at": read_at,
    }
    try:
        stat = source_path.stat()
    except OSError as exc:
        source["stat_error"] = str(exc)
        return source

    source["stat"] = {
        "size_bytes": stat.st_size,
        "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mode": oct(stat.st_mode & 0o777),
        "uid": stat.st_uid,
        "gid": stat.st_gid,
    }
    if stat.st_size <= max_hash_bytes and source_path.is_file():
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(hash_chunk_bytes), b""):
                    digest.update(chunk)
            source["sha256"] = digest.hexdigest()
        except OSError as exc:
            source["hash_error"] = str(exc)
    else:
        source["sha256"] = None
        source["hash_skipped_reason"] = "too_large_or_not_regular_file"
    return source


def virtual_source(
    source_id: str,
    payload: Any,
    *,
    read_at: str,
    uid: int | None = None,
    gid: int | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    raw_bytes = raw.encode("utf-8", errors="replace")
    return {
        "path": f"virtual://abyss-machine/nervous/{source_id}/{label or 'snapshot'}",
        "exists": True,
        "read_at": read_at,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "stat": {
            "size_bytes": len(raw_bytes),
            "mtime": read_at,
            "mode": "virtual",
            "uid": os.getuid() if uid is None else uid,
            "gid": os.getgid() if gid is None else gid,
        },
        "virtual": True,
    }


def text_payload(
    text: str,
    *,
    max_chars: int = 8000,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    raw = text or ""
    redacted = nervous_redaction.redact_text(
        raw,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    redacted_text = str(redacted.get("redacted_text", raw))
    truncated = False
    if len(redacted_text) > max_chars:
        redacted_text = redacted_text[:max_chars] + f" ... [truncated {len(redacted_text) - max_chars} chars]"
        truncated = True
    return {
        "text": redacted_text,
        "text_length": len(raw),
        "text_sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
        "truncated": truncated,
        "raw_omitted": True,
        "redaction": redacted.get("summary", {}),
    }


def url_payload(
    url: str,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    raw = str(url or "")
    without_fragment, fragment_sep, _fragment = raw.partition("#")
    without_query, query_sep, _query = without_fragment.partition("?")
    sanitized = without_query
    return {
        "url": text_payload(
            sanitized,
            max_chars=1600,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )["text"],
        "url_sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
        "query_present": bool(query_sep),
        "fragment_present": bool(fragment_sep),
        "raw_omitted": True,
    }


def browser_content_dedupe_key(record: Mapping[str, Any]) -> str:
    url = record.get("url") if isinstance(record.get("url"), Mapping) else {}
    return "|".join([
        str(url.get("url_sha256") or ""),
        str(record.get("title_sha256") or ""),
        str(record.get("text_sha256") or ""),
        str(record.get("skipped_text") or False),
    ])


def browser_sensitive_reasons(
    url: str,
    title: str,
    page_reasons: Any,
    has_sensitive_fields: bool,
    *,
    allow_form_field_text: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if has_sensitive_fields and not allow_form_field_text:
        reasons.append("sensitive_form_field")
    if isinstance(page_reasons, list):
        for item in page_reasons:
            value = str(item or "").strip()
            if value == "sensitive_form_field" and allow_form_field_text:
                continue
            if value and value not in reasons:
                reasons.append(value)
    sensitive = re.compile(
        r"(?i)(\b(login|log[\s_-]?in|sign[\s_-]?in|auth|oauth|password|passwd|"
        r"credential|credentials|passkey|webauthn|2fa|mfa|otp|checkout|billing|"
        r"bank|token|vault|bitwarden|1password|lastpass|dashlane|keeper)\b|"
        r"accounts\.google\.com|vault\.bitwarden\.com|авторизац|логин|парол)"
    )
    if sensitive.search(f"{url} {title}"):
        reasons.append("url_or_title_sensitive")
    return sorted(set(reasons))


def browser_text_clean(value: str) -> str:
    text = str(value or "").replace("\ufffc", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def browser_line_is_noise(line: str) -> tuple[bool, str | None]:
    text = browser_text_clean(line)
    if not text:
        return True, "blank"
    low = text.lower()
    if len(low) <= 2 and not re.search(r"[A-Za-zА-Яа-я]", low):
        return True, "short_symbol"
    if re.fullmatch(r"[\d\s.,+#()·-]{1,24}", low):
        return True, "numeric_or_counter"
    for pattern in BROWSER_BOILERPLATE_PATTERNS:
        if re.search(pattern, low):
            return True, "boilerplate"
    for pattern in BROWSER_MEDIA_PATTERNS:
        if re.search(pattern, low):
            return True, "media_control"
    return False, None


def browser_content_quality(
    text: str,
    title: str = "",
    url: str = "",
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    raw = str(text or "")
    lines = [browser_text_clean(line) for line in raw.splitlines()]
    lines = [line for line in lines if line]
    kept: list[str] = []
    reasons: dict[str, int] = {}
    for line in lines:
        is_noise, reason = browser_line_is_noise(line)
        if is_noise:
            reasons[reason or "noise"] = int(reasons.get(reason or "noise", 0)) + 1
            continue
        kept.append(line)
    clean_text = browser_text_clean("\n".join(kept))
    low_url = str(url or "").lower()
    flags: list[str] = []
    if low_url.startswith(("about:", "chrome:", "moz-extension:", "resource:")):
        flags.append("browser_internal_url")
    low_title = str(title or "").lower()
    if re.search(r"(смотреть онлайн|kinogo|films\.online|stravers\.live|player|онлайн бесплатно)", f"{low_url} {low_title}"):
        flags.append("entertainment_streaming_page")
    if reasons.get("media_control", 0) >= 3:
        flags.append("media_player_controls")
    line_count = len(lines)
    noise_count = line_count - len(kept)
    noise_ratio = round(noise_count / line_count, 3) if line_count else 0.0
    if line_count and noise_ratio >= 0.58:
        flags.append("navigation_heavy")
    if len(clean_text) < 180:
        flags.append("low_information")
    if len(clean_text) >= 600:
        classification = "usable"
    elif len(clean_text) >= 180 and "browser_internal_url" not in flags and "media_player_controls" not in flags:
        classification = "low_signal"
    else:
        classification = "noise"
    if "entertainment_streaming_page" in flags and classification == "usable":
        classification = "low_signal"
    if "browser_internal_url" in flags or ("media_player_controls" in flags and len(clean_text) < 400):
        classification = "noise"
    score = 1.0
    score -= min(0.55, noise_ratio * 0.55)
    if "low_information" in flags:
        score -= 0.25
    if "media_player_controls" in flags:
        score -= 0.25
    if "browser_internal_url" in flags:
        score -= 0.45
    if "entertainment_streaming_page" in flags:
        score -= 0.25
    return {
        "schema": f"{schema_prefix}_nervous_browser_content_quality_v1",
        "classification": classification,
        "score": round(max(0.0, min(1.0, score)), 3),
        "flags": sorted(set(flags)),
        "line_count": line_count,
        "kept_line_count": len(kept),
        "noise_line_count": noise_count,
        "noise_reasons": reasons,
        "noise_ratio": noise_ratio,
        "raw_text_length": len(raw),
        "clean_text_length": len(clean_text),
        "title": str(title or "")[:240],
        "url_class": "internal" if low_url.startswith(("about:", "chrome:", "moz-extension:", "resource:")) else "web",
        "clean_text": clean_text,
    }


def browser_attention_priority(atspi: Mapping[str, Any], visibility_state: str | None = None) -> dict[str, Any]:
    focused = bool(atspi.get("focused")) if isinstance(atspi, Mapping) else False
    showing = bool(atspi.get("showing")) if isinstance(atspi, Mapping) else False
    visible = bool(atspi.get("visible")) if isinstance(atspi, Mapping) else False
    state = str(visibility_state or "").lower()
    if focused:
        priority = "focused"
        weight = 1.0
    elif showing or visible or state == "visible":
        priority = "visible"
        weight = 0.7
    elif state in {"hidden", "prerender"}:
        priority = "background"
        weight = 0.25
    else:
        priority = "unknown"
        weight = 0.4
    return {
        "priority": priority,
        "weight": weight,
        "focused": focused,
        "showing": showing,
        "visible": visible,
        "visibility_state": visibility_state,
    }


def browser_web_context_quality(
    *,
    url: str,
    title: str,
    content_quality: Mapping[str, Any],
    skipped_text: bool = False,
    skipped_reason: list[str] | None = None,
    atspi: Mapping[str, Any] | None = None,
    visibility_state: str | None = None,
    page_identity: Mapping[str, Any] | None = None,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    low_url = str(url or "").lower()
    low_title = str(title or "").lower()
    combined = f"{low_url} {low_title}"
    reasons: list[str] = []
    flags = list(content_quality.get("flags") or []) if isinstance(content_quality.get("flags"), list) else []
    classification = str(content_quality.get("classification") or "unknown")
    skipped = [str(item) for item in (skipped_reason or []) if item]
    identity = dict(page_identity) if isinstance(page_identity, Mapping) else typing_capture_contracts.browser_ai_counterpart_identity(
        url,
        title,
        schema_prefix=schema_prefix,
    )
    if skipped_text and ("sensitive_form_field" in skipped or "url_or_title_sensitive" in skipped):
        context_class = "login_sensitive"
        reasons.append("sensitive_text_skipped")
    elif identity.get("is_ai") is True:
        context_class = "ai_interaction"
        reasons.append("ai_counterpart_signal")
    elif low_url.startswith(("about:", "chrome:", "moz-extension:", "resource:")) or "browser_internal_url" in flags:
        context_class = "browser_internal"
        reasons.append("browser_internal_url")
    elif re.search(r"(смотреть онлайн|kinogo|films\.online|stravers\.live|player|netflix|youtube|twitch|spotify|аниме|сериал)", combined) or "entertainment_streaming_page" in flags:
        context_class = "entertainment"
        reasons.append("entertainment_or_player_signal")
    elif classification in {"noise", "skipped"} or "low_information" in flags:
        context_class = "low_signal"
        reasons.append(f"content_quality_{classification}")
    elif re.search(r"(github\.com|gitlab\.com|localhost|127\.0\.0\.1|/srv/|abyss|aoa-|agents-of-abyss|tree of sophia|codex|pull request|issue)", combined):
        context_class = "project"
        reasons.append("project_or_repository_signal")
    elif re.search(r"(docs\.|documentation|developer\.mozilla\.org|developer\.chrome\.com|web\.dev|opentelemetry|kernel\.org|readthedocs|man7\.org|api reference)", combined):
        context_class = "docs"
        reasons.append("documentation_signal")
    elif re.search(r"(search|google\.com/search|duckduckgo|bing\.com/search|arxiv|paper|research|wikipedia|stack overflow|stackoverflow)", combined):
        context_class = "research"
        reasons.append("research_signal")
    elif re.search(r"(admin|dashboard|settings|console|cloudflare|vercel|grafana|prometheus|systemctl|localhost)", combined):
        context_class = "tooling"
        reasons.append("tooling_or_admin_signal")
    else:
        context_class = "unknown"
        reasons.append("no_strong_context_signal")
    if context_class not in WEB_CONTEXT_CLASSES:
        context_class = "unknown"
    attention = browser_attention_priority(atspi or {}, visibility_state=visibility_state)
    if attention["priority"] == "background" and context_class not in {"login_sensitive", "browser_internal"}:
        reasons.append("background_tab_deprioritized")
    return {
        "schema": f"{schema_prefix}_nervous_web_context_quality_v1",
        "class": context_class,
        "reasons": sorted(set(reasons)),
        "attention": attention,
        "content_quality_class": classification,
        "content_quality_score": content_quality.get("score"),
        "noise_ratio": content_quality.get("noise_ratio"),
        "query_present": "?" in str(url or ""),
        "fragment_present": "#" in str(url or ""),
        "raw_url_omitted": True,
        "sensitive_skip_preserved": bool(skipped_text and skipped),
        "page_identity": identity if identity.get("is_ai") is True else None,
    }


def browser_content_record_from_page(
    page: Mapping[str, Any],
    capture_source: str,
    *,
    context_id: str | None = None,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
    captured_at: str | None = None,
    source_read_at: str | None = None,
    max_text_chars: int = 12000,
    uid: int | None = None,
    gid: int | None = None,
) -> dict[str, Any]:
    record_captured_at = str(captured_at or page.get("captured_at") or generated_at)
    url = str(page.get("url") or "")
    title = str(page.get("title") or "")
    page_identity = typing_capture_contracts.browser_ai_counterpart_identity(
        url,
        title,
        schema_prefix=schema_prefix,
    )
    title_payload = text_payload(
        title,
        max_chars=1200,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    sanitized_url = url_payload(
        url,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    has_sensitive_fields = bool(page.get("has_sensitive_fields"))
    skipped_reason = browser_sensitive_reasons(
        url,
        title,
        page.get("sensitive_reason"),
        has_sensitive_fields,
        allow_form_field_text=bool(page_identity.get("is_ai")),
    )
    skip_text = bool(skipped_reason) or bool(page.get("skip_text"))
    record: dict[str, Any] = {
        "schema": f"{schema_prefix}_nervous_browser_content_v1",
        "version": version,
        "generated_at": generated_at,
        "captured_at": record_captured_at,
        "source_id": "browser_active_tab",
        "capture_source": capture_source,
        "browser": "firefox",
        "context_id": context_id,
        "title": title_payload["text"],
        "title_sha256": title_payload["text_sha256"],
        "url": sanitized_url,
        "lang": str(page.get("lang") or "")[:80] or None,
        "content_type": str(page.get("content_type") or "")[:120] or None,
        "visibility_state": str(page.get("visibility_state") or "")[:80] or None,
        "has_sensitive_fields": has_sensitive_fields,
        "skipped_text": skip_text,
        "skipped_reason": skipped_reason,
        "form_values_captured": False,
        "cookies_captured": False,
        "local_storage_captured": False,
        "raw_omitted": True,
        "page_identity": page_identity,
    }
    atspi = page.get("atspi") if isinstance(page.get("atspi"), Mapping) else {}
    if not skip_text:
        raw_text = str(page.get("text") or "")
        quality = browser_content_quality(raw_text, title=title, url=url, schema_prefix=schema_prefix)
        payload = text_payload(
            raw_text,
            max_chars=max_text_chars,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
        record["text"] = payload["text"]
        record["text_sha256"] = payload["text_sha256"]
        record["text_length"] = payload["text_length"]
        record["text_truncated"] = bool(page.get("text_truncated")) or bool(payload.get("truncated"))
        record["redaction"] = payload["redaction"]
        clean_text = str(quality.pop("clean_text", "") or "")
        clean_payload = text_payload(
            clean_text,
            max_chars=6000,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        ) if clean_text else {}
        record["content_quality"] = quality
        record["clean_text"] = clean_payload.get("text") if clean_payload else None
        record["clean_text_sha256"] = clean_payload.get("text_sha256") if clean_payload else None
        record["clean_text_length"] = clean_payload.get("text_length") if clean_payload else 0
        record["clean_text_truncated"] = bool(clean_payload.get("truncated")) if clean_payload else False
    else:
        raw_text = str(page.get("text") or "")
        record["text"] = None
        record["text_sha256"] = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()
        record["text_length"] = int(page.get("text_length") or len(raw_text))
        record["text_truncated"] = False
        record["redaction"] = {"matches": 0, "classes": []}
        record["content_quality"] = {
            "schema": f"{schema_prefix}_nervous_browser_content_quality_v1",
            "classification": "skipped",
            "score": 0.0,
            "flags": ["sensitive_or_policy_skipped"],
            "raw_text_length": record["text_length"],
            "clean_text_length": 0,
        }
        record["clean_text"] = None
        record["clean_text_sha256"] = None
        record["clean_text_length"] = 0
        record["clean_text_truncated"] = False
    record["atspi_context"] = {
        key: atspi.get(key)
        for key in ("role", "path", "showing", "visible", "focused", "nodes_seen", "chunks")
        if key in atspi
    }
    record["web_context_quality"] = browser_web_context_quality(
        url=url,
        title=title,
        content_quality=record["content_quality"],
        skipped_text=bool(record.get("skipped_text")),
        skipped_reason=list(record.get("skipped_reason") or []),
        atspi=record["atspi_context"],
        visibility_state=str(record.get("visibility_state") or ""),
        page_identity=page_identity,
        schema_prefix=schema_prefix,
    )
    source_payload = {key: value for key, value in record.items() if key != "source"}
    record["source"] = virtual_source(
        "browser_active_tab",
        source_payload,
        read_at=source_read_at or generated_at,
        uid=uid,
        gid=gid,
        label="browser-content",
    )
    return record


def browser_capture_web_context_summary(
    captures: list[dict[str, Any]],
    *,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    counts = {name: 0 for name in sorted(WEB_CONTEXT_CLASSES)}
    priority_counts: dict[str, int] = {}
    duplicate_count = 0
    low_signal_count = 0
    usable_count = 0
    sensitive_skips = 0
    total = 0
    for item in captures:
        if not isinstance(item, Mapping):
            continue
        record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
        web_context = record.get("web_context_quality") if isinstance(record.get("web_context_quality"), Mapping) else {}
        context_class = str(web_context.get("class") or "unknown")
        if context_class not in counts:
            context_class = "unknown"
        counts[context_class] += 1
        attention = web_context.get("attention") if isinstance(web_context.get("attention"), Mapping) else {}
        priority = str(attention.get("priority") or "unknown")
        priority_counts[priority] = int(priority_counts.get(priority, 0)) + 1
        dedupe = item.get("dedupe") if isinstance(item.get("dedupe"), Mapping) else {}
        if bool(dedupe.get("duplicate")):
            duplicate_count += 1
        content_quality = record.get("content_quality") if isinstance(record.get("content_quality"), Mapping) else {}
        content_class = str(content_quality.get("classification") or "")
        if context_class in {"low_signal", "browser_internal", "entertainment"} or content_class in {"noise", "low_signal", "skipped"}:
            low_signal_count += 1
        if content_class == "usable" and context_class not in {"browser_internal", "entertainment", "login_sensitive"}:
            usable_count += 1
        if bool(record.get("skipped_text")):
            sensitive_skips += 1
        total += 1
    return {
        "schema": f"{schema_prefix}_nervous_web_context_summary_v1",
        "captures": total,
        "classes": {key: value for key, value in counts.items() if value},
        "attention_priorities": priority_counts,
        "duplicate_count": duplicate_count,
        "duplicate_ratio": round(duplicate_count / total, 3) if total else 0.0,
        "low_signal_count": low_signal_count,
        "low_signal_ratio": round(low_signal_count / total, 3) if total else 0.0,
        "usable_count": usable_count,
        "sensitive_skips": sensitive_skips,
        "policy": {
            "raw_url_query_fragment_omitted": True,
            "sensitive_skips_are_positive_health_signal": True,
            "background_tabs_deprioritized": True,
        },
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
