from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_browser_web_context_skips_login_sensitive_text_and_sanitizes_url(abyss_machine_module) -> None:
    record = abyss_machine_module.nervous_browser_content_record_from_page(
        {
            "captured_at": "2026-05-19T10:00:00+00:00",
            "url": "https://example.test/login?token=secret#otp",
            "title": "Account login",
            "text": "password token secret body that must not be stored",
            "has_sensitive_fields": True,
            "atspi": {"focused": True, "showing": True, "visible": True},
        },
        "fixture",
    )

    assert record["skipped_text"] is True
    assert record["text"] is None
    assert record["url"]["url"] == "https://example.test/login"
    assert record["url"]["query_present"] is True
    assert record["url"]["fragment_present"] is True
    assert record["web_context_quality"]["class"] == "login_sensitive"
    assert record["web_context_quality"]["sensitive_skip_preserved"] is True
    assert record["web_context_quality"]["attention"]["priority"] == "focused"


def test_browser_web_context_prioritizes_focused_project_context(abyss_machine_module) -> None:
    text = "\n".join([f"Implementation note {index} for abyss-machine heartbeat project context" for index in range(40)])
    record = abyss_machine_module.nervous_browser_content_record_from_page(
        {
            "captured_at": "2026-05-19T10:00:00+00:00",
            "url": "https://github.com/Agents-of-Abyss/abyss-machine/pull/1",
            "title": "Agents of Abyss heartbeat implementation",
            "text": text,
            "atspi": {"focused": True, "showing": True, "visible": True},
        },
        "fixture",
    )

    assert record["content_quality"]["classification"] == "usable"
    assert record["web_context_quality"]["class"] == "project"
    assert record["web_context_quality"]["attention"]["priority"] == "focused"
    assert record["web_context_quality"]["raw_url_omitted"] is True


def test_browser_capture_web_context_summary_counts_low_signal_and_duplicates(abyss_machine_module) -> None:
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

    summary = abyss_machine_module.nervous_browser_capture_web_context_summary(captures)

    assert summary["schema"] == "abyss_machine_nervous_web_context_summary_v1"
    assert summary["classes"] == {"browser_internal": 1, "project": 1}
    assert summary["duplicate_ratio"] == 0.5
    assert summary["low_signal_ratio"] == 0.5
    assert summary["attention_priorities"]["focused"] == 1


def test_web_performance_diagnostic_bounds_entries_and_sanitizes_urls(abyss_machine_module) -> None:
    entries = [
        {"entryType": "navigation", "name": "https://example.test/app?secret=1#top", "duration": 123.4, "domContentLoadedEventEnd": 80.0},
        {"entryType": "paint", "name": "first-contentful-paint", "startTime": 90.0},
    ]
    entries.extend(
        {
            "entryType": "resource",
            "name": f"https://cdn.example.test/asset-{index}.js?token=secret#frag",
            "duration": float(index),
            "transferSize": 1024,
        }
        for index in range(200)
    )

    diagnostic = abyss_machine_module.nervous_web_performance_diagnostic_from_capture(
        {
            "url": "https://example.test/app?session=secret#frag",
            "title": "Performance fixture",
            "visibility_state": "visible",
            "entries": entries,
        },
        reason="fixture",
        source="test",
        write_latest=False,
    )

    assert diagnostic["schema"] == "abyss_machine_nervous_web_performance_diagnostic_v1"
    assert diagnostic["ok"] is True
    assert diagnostic["opt_in"] is True
    assert diagnostic["page"]["url"]["url"] == "https://example.test/app"
    assert diagnostic["page"]["url"]["query_present"] is True
    assert diagnostic["entries"]["count"] == 160
    assert len(diagnostic["entries"]["samples"]) == 80
    assert "?" not in diagnostic["entries"]["samples"][2]["name"]["url"]
    assert diagnostic["metrics"]["resource_count"] == 158
    assert diagnostic["policy"]["does_not_keep_persistent_cdp_or_bidi_session"] is True


def test_web_performance_diagnostic_response_profile_is_owner_gated(abyss_machine_module) -> None:
    profile = abyss_machine_module.response_command_profile("abyss-machine nervous web-performance-diagnostic --dry-run --json")

    assert profile["kind"] == "owner_gated_web_performance_diagnostic"
    assert profile["scope"] == "web_diagnostic"
    assert profile["mutating_if_run"] is False
    assert profile["requires_operator"] is True
