from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_sources import (
    browser_capture_web_context_summary,
    browser_content_dedupe_key,
    browser_content_quality,
    browser_content_record_from_page,
    browser_line_is_noise,
    browser_sensitive_reasons,
    browser_text_clean,
    browser_web_context_quality,
    default_state,
    effective_sources,
    file_source,
    saved_state_document,
    source_catalog,
    source_lookup,
    source_set_audit_event,
    source_set_blocked_result,
    source_set_result,
    source_set_transition,
    source_set_unknown_result,
    state_document,
    text_payload,
    url_payload,
    virtual_source,
)


READ_AT = "2026-06-25T12:00:00+00:00"
FAKE_GITHUB_TOKEN = "ghp_" + "1" * 24


def test_nervous_file_source_metadata_hash_and_skip_are_module_owned(tmp_path: Path) -> None:
    path = tmp_path / "source.jsonl"
    raw = b'{"schema":"abyss_machine_fact"}\n'
    path.write_bytes(raw)

    result = file_source(path, read_at=READ_AT, max_hash_bytes=1024)

    assert result["path"] == str(path)
    assert result["exists"] is True
    assert result["read_at"] == READ_AT
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["stat"]["size_bytes"] == len(raw)
    assert result["stat"]["mode"].startswith("0o")

    skipped = file_source(path, read_at=READ_AT, max_hash_bytes=3)
    assert skipped["sha256"] is None
    assert skipped["hash_skipped_reason"] == "too_large_or_not_regular_file"

    missing = file_source(tmp_path / "missing.jsonl", read_at=READ_AT)
    assert missing["exists"] is False
    assert "stat_error" in missing


def test_nervous_virtual_source_contract_is_deterministic_without_private_payload() -> None:
    payload = {"b": 2, "a": 1}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8", errors="replace")

    result = virtual_source("browser_active_tab", payload, read_at=READ_AT, uid=1000, gid=1000, label="snapshot")

    assert result["path"] == "virtual://abyss-machine/nervous/browser_active_tab/snapshot"
    assert result["exists"] is True
    assert result["virtual"] is True
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["stat"] == {
        "size_bytes": len(raw),
        "mtime": READ_AT,
        "mode": "virtual",
        "uid": 1000,
        "gid": 1000,
    }


def test_nervous_text_and_url_payloads_omit_raw_private_material() -> None:
    raw_secret_text = f"password=CorrectHorseBatteryStaple {FAKE_GITHUB_TOKEN}"

    payload = text_payload(
        raw_secret_text + " long-tail",
        max_chars=64,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )

    assert payload["text_length"] == len(raw_secret_text + " long-tail")
    assert payload["text_sha256"] == hashlib.sha256((raw_secret_text + " long-tail").encode("utf-8")).hexdigest()
    assert payload["raw_omitted"] is True
    assert payload["redaction"]["matches"] >= 2
    assert "CorrectHorseBatteryStaple" not in payload["text"]
    assert FAKE_GITHUB_TOKEN not in payload["text"]

    raw_url = "https://example.test/path?token=CorrectHorseBatteryStaple#fragment"
    url = url_payload(raw_url, schema_prefix="abyss_machine", version="test", generated_at=READ_AT)

    assert url["url"] == "https://example.test/path"
    assert url["url_sha256"] == hashlib.sha256(raw_url.encode("utf-8", errors="replace")).hexdigest()
    assert url["query_present"] is True
    assert url["fragment_present"] is True
    assert url["raw_omitted"] is True
    assert "CorrectHorseBatteryStaple" not in url["url"]


def test_browser_sensitive_reasons_and_quality_are_module_owned() -> None:
    assert browser_sensitive_reasons(
        "https://example.test/login?token=secret",
        "Account login",
        ["sensitive_form_field"],
        True,
    ) == ["sensitive_form_field", "url_or_title_sensitive"]

    assert browser_sensitive_reasons(
        "https://chatgpt.com/c/123",
        "ChatGPT",
        ["sensitive_form_field"],
        True,
        allow_form_field_text=True,
    ) == []

    assert browser_text_clean("  alpha  \n\n\n beta  ") == "alpha\n\nbeta"
    assert browser_line_is_noise("Skip to content") == (True, "boilerplate")

    usable = browser_content_quality(
        "\n".join([f"Implementation detail {index} for abyss-machine command contracts" for index in range(40)]),
        title="Agents of Abyss command contract",
        url="https://github.com/Agents-of-Abyss/abyss-machine/pull/1",
        schema_prefix="abyss_machine",
    )
    noise = browser_content_quality(
        "Skip to content\nRepository navigation\n1\n2\nOverview",
        title="Repository navigation",
        url="about:preferences",
        schema_prefix="abyss_machine",
    )

    assert usable["schema"] == "abyss_machine_nervous_browser_content_quality_v1"
    assert usable["classification"] == "usable"
    assert usable["clean_text_length"] >= 600
    assert noise["classification"] == "noise"
    assert "browser_internal_url" in noise["flags"]


def test_browser_content_record_redacts_private_page_material_and_classifies_context() -> None:
    text = "\n".join([f"Implementation note {index} for abyss-machine heartbeat project context" for index in range(40)])
    record = browser_content_record_from_page(
        {
            "url": "https://example.test/project?ref=docs#frag",
            "title": "Agents of Abyss heartbeat implementation",
            "text": text,
            "atspi": {"focused": True, "showing": True, "visible": True, "path": "/fixture/browser"},
            "visibility_state": "visible",
        },
        "fixture",
        context_id="ctx-1",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
        captured_at="2026-06-25T11:59:59+00:00",
        source_read_at="2026-06-25T12:00:01+00:00",
        max_text_chars=12000,
        uid=1000,
        gid=1000,
    )

    assert record["schema"] == "abyss_machine_nervous_browser_content_v1"
    assert record["context_id"] == "ctx-1"
    assert record["url"]["url"] == "https://example.test/project"
    assert record["url"]["query_present"] is True
    assert record["url"]["fragment_present"] is True
    assert record["content_quality"]["classification"] == "usable"
    assert record["web_context_quality"]["class"] == "project"
    assert record["web_context_quality"]["attention"]["priority"] == "focused"
    assert record["atspi_context"]["path"] == "/fixture/browser"
    assert record["source"]["path"] == "virtual://abyss-machine/nervous/browser_active_tab/browser-content"
    assert record["source"]["stat"]["uid"] == 1000
    assert record["source"]["stat"]["gid"] == 1000
    assert "ref=docs" not in json.dumps(record, ensure_ascii=False)

    dedupe_key = browser_content_dedupe_key(record)
    assert record["url"]["url_sha256"] in dedupe_key
    assert record["title_sha256"] in dedupe_key


def test_browser_content_record_preserves_ai_text_and_skips_login_text() -> None:
    ai_record = browser_content_record_from_page(
        {
            "url": "https://chatgpt.com/c/123",
            "title": "ChatGPT",
            "text": "User asks about portable abyss-machine subsystem command glue.",
            "has_sensitive_fields": True,
            "sensitive_reason": ["sensitive_form_field"],
            "atspi": {"focused": True},
        },
        "fixture",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
        uid=1000,
        gid=1000,
    )
    login_record = browser_content_record_from_page(
        {
            "url": "https://example.test/login?token=secret#otp",
            "title": "Account login",
            "text": "password token secret body that must not be stored",
            "has_sensitive_fields": True,
            "atspi": {"focused": True},
        },
        "fixture",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
        uid=1000,
        gid=1000,
    )

    assert ai_record["skipped_text"] is False
    assert ai_record["page_identity"]["is_ai"] is True
    assert ai_record["web_context_quality"]["class"] == "ai_interaction"
    assert ai_record["text"]

    assert login_record["skipped_text"] is True
    assert login_record["text"] is None
    assert login_record["web_context_quality"]["class"] == "login_sensitive"
    assert login_record["web_context_quality"]["sensitive_skip_preserved"] is True


def test_browser_web_context_summary_and_cli_record_wrapper_are_contract_seams(monkeypatch) -> None:
    captures = [
        {
            "dedupe": {"duplicate": False},
            "record": {
                "skipped_text": False,
                "content_quality": {"classification": "usable"},
                "web_context_quality": {"class": "project", "attention": {"priority": "focused"}},
            },
        },
        {
            "dedupe": {"duplicate": True},
            "record": {
                "skipped_text": False,
                "content_quality": {"classification": "noise"},
                "web_context_quality": {"class": "browser_internal", "attention": {"priority": "background"}},
            },
        },
    ]
    summary = browser_capture_web_context_summary(captures, schema_prefix="abyss_machine")
    web_quality = browser_web_context_quality(
        url="https://docs.python.org/3/library/argparse.html?x=1#top",
        title="argparse documentation",
        content_quality={"classification": "usable", "score": 0.9, "noise_ratio": 0.0, "flags": []},
        atspi={"showing": True},
        visibility_state="visible",
        schema_prefix="abyss_machine",
    )

    assert summary["schema"] == "abyss_machine_nervous_web_context_summary_v1"
    assert summary["classes"] == {"browser_internal": 1, "project": 1}
    assert summary["duplicate_ratio"] == 0.5
    assert summary["low_signal_ratio"] == 0.5
    assert web_quality["class"] == "docs"
    assert web_quality["query_present"] is True
    assert web_quality["fragment_present"] is True

    from abyss_machine import cli

    page = {
        "url": "https://github.com/Agents-of-Abyss/abyss-machine",
        "title": "abyss-machine",
        "text": "Portable command glue contract record",
    }
    times = iter([
        "2026-06-25T12:00:00+00:00",
        "2026-06-25T12:00:01+00:00",
        "2026-06-25T12:00:02+00:00",
    ])
    monkeypatch.setattr(cli, "now_iso", lambda: next(times))

    actual = cli.nervous_browser_content_record_from_page(page, "fixture", context_id="ctx-cli")
    expected = browser_content_record_from_page(
        page,
        "fixture",
        context_id="ctx-cli",
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
        captured_at="2026-06-25T12:00:01+00:00",
        source_read_at="2026-06-25T12:00:02+00:00",
        max_text_chars=cli.NERVOUS_BROWSER_CONTENT_MAX_CHARS,
        uid=os.getuid(),
        gid=os.getgid(),
    )

    assert actual == expected
    assert cli.nervous_browser_capture_web_context_summary(captures) == summary


def test_nervous_source_state_effective_catalog_and_lookup_are_module_owned() -> None:
    defaults = default_state("abyss_machine", "test")
    state = state_document(
        defaults=defaults,
        loaded={
            "overrides": {
                "typing_saved_text": {
                    "enabled": False,
                    "updated_at": READ_AT,
                    "updated_by": "source-disable",
                    "reason": "operator",
                }
            }
        },
        load_error=None,
        path="/var/lib/abyss-machine/nervous/sources/state.json",
        exists=True,
    )
    config = {
        "schema": "abyss_machine_nervous_sources_v1",
        "safe_now": {
            "typing_saved_text": {"enabled": True, "allowed": True, "content": "redacted-text", "notes": "safe"},
            "browser_active_tab": {"enabled": True, "allowed": False, "content": "browser", "notes": "blocked"},
        },
        "deferred_until_privacy_controls": {
            "screenshot_capture": {"enabled": False, "allowed": True, "content": "png", "notes": "deferred"}
        },
    }
    effective = effective_sources(config, state, state_path=state["path"])
    catalog = source_catalog(
        effective,
        config_path="/etc/abyss-machine/nervous/sources.json",
        state_path=state["path"],
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )

    typing_item = source_lookup(catalog, "typing_saved_text")
    blocked_item = source_lookup(catalog, "browser_active_tab")

    assert state["schema"] == "abyss_machine_nervous_sources_state_v1"
    assert effective["safe_now"]["typing_saved_text"]["enabled"] is False
    assert effective["safe_now"]["typing_saved_text"]["state_override"]["reason"] == "operator"
    assert catalog["schema"] == "abyss_machine_nervous_sources_list_v1"
    assert catalog["ok"] is True
    assert [item["id"] for item in catalog["items"]] == ["screenshot_capture", "browser_active_tab", "typing_saved_text"]
    assert typing_item["enabled"] is False
    assert typing_item["can_enable_now"] is True
    assert blocked_item["can_enable_now"] is False
    assert blocked_item["enable_blocker"] == "source is not allowed by policy"


def test_nervous_source_set_contracts_cover_transitions_errors_and_cli_delegation() -> None:
    state = default_state("abyss_machine", "test")
    item = {
        "id": "typing_saved_text",
        "enabled": True,
        "can_enable_now": True,
    }
    transition = source_set_transition(
        source_id="typing_saved_text",
        enabled=False,
        source_status=item,
        state=state,
        updated_at=READ_AT,
        reason="operator disable",
    )
    saved = saved_state_document(
        transition["state"],
        updated_by="source-disable:typing_saved_text",
        change_id="source-123",
        updated_at="2026-06-25T12:00:01+00:00",
        schema_prefix="abyss_machine",
        version="test",
    )
    audit_event = source_set_audit_event(
        change_id=saved["last_change_id"],
        source_id="typing_saved_text",
        before=transition["before"],
        after=transition["after"],
        reason="operator disable",
    )
    result = source_set_result(
        source_id="typing_saved_text",
        before=transition["before"],
        after=transition["after"],
        state=saved,
        audit={"schema": "abyss_machine_nervous_privacy_audit_v1", **audit_event},
        effective={"id": "typing_saved_text", "enabled": False},
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:02+00:00",
    )
    blocked = source_set_blocked_result(
        "browser_active_tab",
        {"id": "browser_active_tab", "enable_blocker": "source is not allowed by policy"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )
    unknown = source_set_unknown_result(
        "missing",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )

    assert transition["before"] is True
    assert transition["after"] is False
    assert transition["state"]["overrides"]["typing_saved_text"]["enabled"] is False
    assert transition["state"]["overrides"]["typing_saved_text"]["reason"] == "operator disable"
    assert saved["last_change_id"] == "source-123"
    assert audit_event["event"] == "source_state_changed"
    assert result["schema"] == "abyss_machine_nervous_source_set_v1"
    assert result["changed"] is True
    assert result["effective"]["enabled"] is False
    assert blocked["ok"] is False
    assert blocked["error"] == "source is not allowed by policy"
    assert unknown["error"] == "unknown source"

    from abyss_machine import cli

    assert cli.nervous_source_contracts.source_lookup({"items": [item]}, "typing_saved_text") == item
