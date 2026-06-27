from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine.nervous_brief import (  # noqa: E402
    brief_document,
    cache_key,
    normalize_limit,
    normalize_scope,
    recent_episodes_document,
    semantic_maintenance_thresholds,
)


COMMANDS = {
    "quality": "abyss-machine nervous quality-audit --json",
    "quality_refresh": "abyss-machine nervous quality-audit --refresh --json",
    "quality_refresh_index_operator": "abyss-machine nervous quality-audit --refresh --refresh-index --json",
    "quality_recheck": "abyss-machine nervous quality-audit --json",
    "search": "abyss-machine nervous search --query TEXT --json",
    "rerank": "abyss-machine nervous rerank --query TEXT --json",
    "hybrid_recall": "abyss-machine nervous recall --mode hybrid --query TEXT --json",
    "semantic_status": "abyss-machine nervous semantic-status --json",
    "semantic_maintain_review": "abyss-machine nervous semantic-maintain --dry-run --json",
    "semantic_maintain_retry": "abyss-machine nervous semantic-maintain --json",
}


def test_brief_scope_limit_cache_and_semantic_thresholds_are_module_owned() -> None:
    assert normalize_scope("bad") == "now"
    assert normalize_scope("today") == "today"
    assert normalize_limit("0") == 1
    assert normalize_limit("12") == 12
    assert cache_key("session", "2", True) == "session:2:True"
    assert semantic_maintenance_thresholds({"maintain": {"min_delta_chunks": "64", "max_stale_minutes": "12.5"}}) == {
        "min_delta_chunks": 64,
        "max_stale_minutes": 12.5,
    }
    assert semantic_maintenance_thresholds({}) == {"min_delta_chunks": 128, "max_stale_minutes": 90.0}


def test_brief_document_preserves_readiness_gaps_actions_and_public_policy() -> None:
    data = brief_document(
        scope="unknown",
        quality={"summary": {"fails": 0, "warnings": 0}},
        privacy={"global_pause": False, "private_mode": False},
        capture={"ok": True, "latest": "/latest/capture.json", "browser_content_latest": None, "storage": {"items": 1}},
        index_status={"ready": True, "warnings": [], "freshness": {"stale": False}, "counts": {"chunks": 5}},
        semantic_status={"ready": False, "warnings": ["missing sidecar"], "freshness": {"stale": True}, "counts": {}},
        semantic_maintenance={"needed": False, "delta_chunks": 0},
        derived_refresh={"ok": True},
        synthesis={"ok": True, "candidate_id": "syn-1", "scope": "daily", "summary": {"episodes": 1}},
        observability={"timer": {"active": True}, "latest": {"ok": True}},
        memory={"summary": {"pressure": "low"}},
        storage={"summary": {"pressure": "low"}},
        processes={"summary": {"total": 3}},
        resource={"summary": {"mode": "balanced"}},
        recent_episodes={"items": [{"episode_id": "eps-1"}], "summary": {"returned": 1}},
        commands=COMMANDS,
        latest_path="/var/lib/abyss-machine/nervous/brief/latest.json",
        daily_glob="/var/lib/abyss-machine/nervous/brief/YYYY/MM/YYYY-MM-DD.jsonl",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data["schema"] == "abyss_machine_nervous_brief_v1"
    assert data["scope"] == "now"
    assert data["ok"] is True
    assert data["readiness"] == {
        "status": "ready",
        "quality_clean": True,
        "index_fresh": True,
        "privacy_open": True,
        "semantic_ready": False,
        "semantic_stale": True,
        "semantic_maintenance_needed": False,
        "derived_refresh_ok": True,
    }
    assert [item["layer"] for item in data["gaps"]] == ["semantic"]
    assert data["next_actions"] == [
        {
            "action": "semantic_maintain",
            "command": "abyss-machine nervous semantic-maintain --dry-run --json",
            "retry_command": "abyss-machine nervous semantic-maintain --json",
            "reason": "review stale SQLite/FTS and embedding sidecar drift through a dry-run resource gate before any maintainer retry",
        }
    ]
    assert data["policy"] == {
        "raw_private_content": False,
        "automatic_action": False,
        "model_used": False,
        "repo_mutation": False,
        "maintenance_review_before_retry": True,
    }
    assert "inputs" not in data


def test_brief_document_degraded_contract_keeps_action_order() -> None:
    data = brief_document(
        scope="today",
        quality={"summary": {"fails": 1, "warnings": 0}},
        privacy={"global_pause": True, "private_mode": False},
        capture={},
        index_status={"freshness": {"stale": True}},
        semantic_status={"ready": True, "freshness": {"stale": True}},
        semantic_maintenance={"needed": True},
        derived_refresh={"ok": False, "error": "timer missing"},
        synthesis={},
        observability={},
        memory={},
        storage={},
        processes={},
        resource={},
        recent_episodes={},
        commands=COMMANDS,
        latest_path="/latest.json",
        daily_glob="/YYYY-MM-DD.jsonl",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data["ok"] is False
    assert data["readiness"]["status"] == "degraded"
    assert [item["layer"] for item in data["gaps"]] == ["quality", "index", "privacy", "semantic", "automation"]
    assert [item["action"] for item in data["next_actions"]] == ["semantic_maintain", "quality_recheck", "automation_repair"]
    assert data["current"]["memory"] is None


def test_recent_episodes_document_filters_sorts_and_compacts_records() -> None:
    items = [
        {
            "record": {
                "episode_id": "old",
                "category": "storage",
                "severity": "info",
                "title": "Old",
                "start_at": "2026-06-25T23:50:00+00:00",
                "end_at": "2026-06-25T23:55:00+00:00",
                "event_count": 1,
                "private_field": "drop",
            }
        },
        {
            "record": {
                "episode_id": "late",
                "category": "resource",
                "severity": "warning",
                "title": "Late",
                "start_at": "2026-06-26T11:00:00+00:00",
                "end_at": "2026-06-26T11:05:00+00:00",
                "event_count": 2,
            }
        },
        {
            "record": {
                "episode_id": "early",
                "category": "desktop",
                "severity": "notice",
                "title": "Early",
                "start_at": "2026-06-26T09:00:00+00:00",
                "end_at": "2026-06-26T09:05:00+00:00",
                "event_count": 1,
            }
        },
        {"record": {}},
    ]

    data = recent_episodes_document(
        items,
        [{"line": 7, "error": "bad json"}],
        limit=1,
        scope="today",
        now=dt.datetime.fromisoformat("2026-06-26T12:00:00+00:00"),
    )

    assert data == {
        "items": [
            {
                "episode_id": "late",
                "category": "resource",
                "severity": "warning",
                "title": "Late",
                "start_at": "2026-06-26T11:00:00+00:00",
                "end_at": "2026-06-26T11:05:00+00:00",
                "event_count": 2,
            }
        ],
        "summary": {
            "returned": 1,
            "available": 2,
            "parse_errors": 1,
        },
    }


def test_cli_recent_episodes_delegates_projection_to_module(monkeypatch) -> None:
    items = [
        {
            "record": {
                "episode_id": "eps-cli",
                "category": "resource",
                "severity": "warning",
                "title": "CLI",
                "start_at": "2026-06-26T11:00:00+00:00",
                "end_at": "2026-06-26T11:05:00+00:00",
                "event_count": 2,
            }
        }
    ]
    parse_errors = [{"line": 1, "error": "bad"}]

    monkeypatch.setattr(cli, "nervous_episode_records", lambda: (items, parse_errors))

    assert cli.nervous_recent_episodes(limit=2, scope="now") == recent_episodes_document(
        items,
        parse_errors,
        limit=2,
        scope="now",
    )


def test_cli_nervous_brief_delegates_document_shape_to_module(monkeypatch) -> None:
    quality = {"summary": {"fails": 0, "warnings": 0}}
    privacy = {"global_pause": False, "private_mode": False}
    capture = {"ok": True, "latest": "/capture/latest.json", "browser_content_latest": "/browser/latest.json", "storage": {}}
    index_status = {"ready": True, "warnings": [], "freshness": {"stale": False}, "counts": {"chunks": 4}}
    semantic_status = {"ready": True, "warnings": [], "freshness": {"stale": False}, "counts": {"vectors": 4}}
    semantic_config = {"maintain": {"min_delta_chunks": 9, "max_stale_minutes": 22}}
    semantic_maintenance = {"needed": False, "delta_chunks": 0}
    derived_refresh = {"ok": True}
    synthesis = {"ok": True, "candidate_id": "syn-cli", "scope": "daily", "summary": {"episodes": 1}}
    observability = {"timer": {"active": True}, "latest": {"ok": True}}
    memory = {"summary": {"pressure": "low"}}
    storage = {"summary": {"pressure": "low"}}
    processes = {"summary": {"total": 7}}
    resource = {"summary": {"mode": "balanced"}}
    recent = {"items": [{"episode_id": "eps-cli"}], "summary": {"returned": 1}}
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(cli, "NERVOUS_BRIEF_CACHE", {})
    monkeypatch.setattr(cli, "nervous_quality_audit", lambda **kwargs: calls.append(("quality", kwargs)) or quality)
    monkeypatch.setattr(cli, "nervous_status", lambda **kwargs: calls.append(("status", kwargs)) or {"ok": True})
    monkeypatch.setattr(cli, "nervous_privacy_status", lambda **kwargs: calls.append(("privacy", kwargs)) or privacy)
    monkeypatch.setattr(cli, "nervous_capture_status", lambda: calls.append(("capture",)) or capture)
    monkeypatch.setattr(cli, "nervous_index_status", lambda **kwargs: calls.append(("index", kwargs)) or index_status)
    monkeypatch.setattr(cli, "nervous_semantic_status", lambda **kwargs: calls.append(("semantic", kwargs)) or semantic_status)
    monkeypatch.setattr(cli, "nervous_derived_refresh_status", lambda: calls.append(("derived",)) or derived_refresh)
    monkeypatch.setattr(cli, "nervous_synthesis_latest", lambda: calls.append(("synthesis",)) or synthesis)
    monkeypatch.setattr(cli, "observability_status", lambda: calls.append(("observability",)) or observability)
    monkeypatch.setattr(cli, "memory_plan", lambda **kwargs: calls.append(("memory", kwargs)) or memory)
    monkeypatch.setattr(cli, "storage_status", lambda **kwargs: calls.append(("storage", kwargs)) or storage)
    monkeypatch.setattr(cli, "process_latest", lambda: calls.append(("processes",)) or processes)
    monkeypatch.setattr(cli, "resource_status", lambda **kwargs: calls.append(("resource", kwargs)) or resource)
    monkeypatch.setattr(cli, "nervous_recent_episodes", lambda **kwargs: calls.append(("recent", kwargs)) or recent)
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: calls.append(("semantic_config",)) or semantic_config)

    def fake_maintain_assess(status, min_delta, max_stale, force_refresh=False):
        calls.append(("semantic_maintain", status, min_delta, max_stale, force_refresh))
        return semantic_maintenance

    monkeypatch.setattr(cli, "nervous_semantic_maintain_assess", fake_maintain_assess)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T12:00:00+00:00")

    data = cli.nervous_brief(scope="today", limit=3, refresh=True, write_latest=False)
    expected = brief_document(
        scope="today",
        quality=quality,
        privacy=privacy,
        capture=capture,
        index_status=index_status,
        semantic_status=semantic_status,
        semantic_maintenance=semantic_maintenance,
        derived_refresh=derived_refresh,
        synthesis=synthesis,
        observability=observability,
        memory=memory,
        storage=storage,
        processes=processes,
        resource=resource,
        recent_episodes=recent,
        commands={
            "quality": cli.NERVOUS_QUALITY_AUDIT_COMMAND,
            "quality_refresh": cli.NERVOUS_QUALITY_AUDIT_REFRESH_COMMAND,
            "quality_refresh_index_operator": cli.NERVOUS_QUALITY_AUDIT_REFRESH_INDEX_COMMAND,
            "quality_recheck": cli.NERVOUS_QUALITY_AUDIT_COMMAND,
            "search": "abyss-machine nervous search --query TEXT --json",
            "rerank": "abyss-machine nervous rerank --query TEXT --json",
            "hybrid_recall": "abyss-machine nervous recall --mode hybrid --query TEXT --json",
            "semantic_status": cli.NERVOUS_SEMANTIC_MAINTAIN_STATUS_COMMAND,
            "semantic_maintain_review": cli.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
            "semantic_maintain_retry": cli.NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
        },
        latest_path=str(cli.NERVOUS_BRIEF_LATEST_PATH),
        daily_glob=str(cli.NERVOUS_BRIEF_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data == expected
    assert calls == [
        ("quality", {"refresh": True, "refresh_index": False, "write_latest": True, "deep_index_validate": False}),
        ("status", {"write_latest": True}),
        ("privacy", {"write_latest": True}),
        ("capture",),
        ("index", {"write_latest": True}),
        ("semantic", {"write_latest": True}),
        ("derived",),
        ("synthesis",),
        ("observability",),
        ("memory", {"write_latest": True}),
        ("storage", {"write_latest": True, "full_ai_scan": False}),
        ("processes",),
        ("resource", {"write_latest": True}),
        ("recent", {"limit": 3, "scope": "today"}),
        ("semantic_config",),
        ("semantic_maintain", semantic_status, 9, 22.0, False),
    ]
