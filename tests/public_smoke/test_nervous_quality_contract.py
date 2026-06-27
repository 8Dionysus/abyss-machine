from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_quality  # noqa: E402


FAKE_GITHUB_TOKEN = "ghp_" + "1" * 24


def test_derived_refresh_status_document_is_module_owned_contract() -> None:
    passive_unit = {"name": "abyss-nervous-passive-chronicle.service", "is_enabled": True}
    derived_unit = {"name": "abyss-nervous-derived-refresh.service", "is_enabled": False}
    passive_show = {
        "ok": True,
        "properties": {
            "OnSuccess": "other.service abyss-nervous-derived-refresh.service",
            "FragmentPath": "/home/user/.config/systemd/user/passive.service",
        },
    }
    derived_show = {
        "ok": True,
        "properties": {
            "LoadState": "loaded",
            "FragmentPath": "/home/user/.config/systemd/user/derived.service",
            "ExecStart": (
                "/usr/bin/abyss-machine nervous quality-audit --refresh --json ; "
                "/usr/bin/abyss-machine resource launch --class medium --kind indexing -- "
                "abyss-machine nervous index-build --json"
            ),
        },
    }

    data = nervous_quality.derived_refresh_status_document(
        passive_unit=passive_unit,
        derived_unit=derived_unit,
        passive_show=passive_show,
        derived_show=derived_show,
        passive_service="abyss-nervous-passive-chronicle.service",
        derived_service="abyss-nervous-derived-refresh.service",
        dropin_path="/home/user/.config/systemd/user/passive.service.d/50-derived.conf",
        dropin_exists=True,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )
    failed = nervous_quality.derived_refresh_status_document(
        passive_unit=passive_unit,
        derived_unit={"name": "abyss-nervous-derived-refresh.service", "is_enabled": False},
        passive_show={"properties": {"OnSuccess": "other.service"}},
        derived_show={"properties": {"LoadState": "not-found", "ExecStart": "abyss-machine nervous status --json"}},
        passive_service="abyss-nervous-passive-chronicle.service",
        derived_service="abyss-nervous-derived-refresh.service",
        dropin_path="/dropin.conf",
        dropin_exists=False,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data["schema"] == "abyss_machine_nervous_derived_refresh_status_v1"
    assert data["ok"] is True
    assert data["dropin"] == {
        "path": "/home/user/.config/systemd/user/passive.service.d/50-derived.conf",
        "exists": True,
    }
    assert data["systemd"]["derived_show"] == {"ok": True}
    assert data["systemd"]["fragment_path"] == "/home/user/.config/systemd/user/derived.service"
    assert all(data["systemd"]["exec_fragments_present"].values())
    assert data["policy"] == {
        "deterministic_refresh_first": True,
        "index_refresh_resource_gated": True,
        "automatic_action": False,
        "repo_mutation": False,
    }
    assert failed["ok"] is False
    assert failed["systemd"]["exec_fragments_present"] == {
        "nervous quality-audit --refresh --json": False,
        "resource launch --class medium --kind indexing": False,
        "nervous index-build --json": False,
    }


def test_quality_audit_document_compacts_validations_and_preserves_public_policy() -> None:
    validations = {
        "facts": {"ok": True, "summary": {"fails": 0, "warnings": 0, "checks": 1}, "checks": [{"level": "ok"}]},
        "events": {
            "ok": True,
            "summary": {"fails": 0, "warnings": 1, "checks": 2},
            "checks": [{"level": "warn", "key": "stale", "message": "stale"}],
        },
        "episodes": {
            "ok": False,
            "summary": {"fails": 1, "warnings": 0, "checks": 2},
            "checks": [{"level": "fail", "key": "missing", "message": "missing"}],
        },
    }
    timers = {
        "passive_chronicle": {"name": "passive.timer", "is_active": True},
        "search_index": {"name": "index.timer", "is_active": False},
    }

    data = nervous_quality.audit_document(
        refresh_requested=True,
        refresh_index_requested=False,
        refresh_results={"events_build": {"ok": True}},
        validations=validations,
        timers=timers,
        status_data={"ok": True, "phase": "ready", "sources": {"enabled_safe_sources": ["facts"]}},
        capture_status={"ok": False, "storage": {"root": "/srv/abyss-machine/nervous"}},
        derived_refresh_status={"ok": True},
        privacy_status={"global_pause": False, "private_mode": False},
        sources={"safe_now": {"facts": {}}, "deferred_until_privacy_controls": {"browser": {}}},
        index_status={"ready": True},
        semantic_maintain={"latest": "/latest/semantic.json"},
        browser_latest=None,
        browser_error="missing",
        browser_path="/var/lib/abyss-machine/nervous/browser/latest.json",
        redaction_summary={"matches": 2, "classes": ["password", "token"]},
        privacy_state_path="/var/lib/abyss-machine/nervous/privacy/state.json",
        index_db_path="/srv/abyss-machine/nervous/indexes/sqlite/nervous.db",
        latest_path="/var/lib/abyss-machine/nervous/quality/latest.json",
        daily_glob="/var/lib/abyss-machine/nervous/quality/YYYY/MM/YYYY-MM-DD.jsonl",
        commands={"audit": "abyss-machine nervous quality-audit --json"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    checks = {item["key"]: item for item in data["checks"]}
    assert data["schema"] == "abyss_machine_nervous_quality_audit_v1"
    assert data["ok"] is False
    assert data["summary"] == {"status": "fail", "fails": 2, "warnings": 3, "checks": 11}
    assert checks["facts_validate"]["level"] == "ok"
    assert checks["events_validate"]["level"] == "warn"
    assert checks["episodes_validate"]["level"] == "fail"
    assert checks["timer:search_index"]["level"] == "fail"
    assert checks["browser_content_latest"]["level"] == "warn"
    assert checks["capture_status"]["level"] == "warn"
    assert data["validations"]["events"]["non_ok_checks"] == [{"level": "warn", "key": "stale", "message": "stale"}]
    assert data["status"]["enabled_safe_sources"] == ["facts"]
    assert data["sources"] == {"safe_now": ["facts"], "private_connectors": ["browser"]}
    assert data["policy"] == {
        "raw_private_content": False,
        "automatic_action": False,
        "automatic_repo_write": False,
        "refresh_rebuilds_derived_records_only": True,
        "redaction_smoke_omits_raw_secret_text": True,
    }
    assert "CorrectHorseBatteryStaple" not in str(data)
    assert FAKE_GITHUB_TOKEN not in str(data)


def test_cli_derived_refresh_status_delegates_shape_to_quality_module(monkeypatch, tmp_path: Path) -> None:
    dropin_path = tmp_path / "50-derived-refresh.conf"
    dropin_path.write_text("[Unit]\nOnSuccess=abyss-nervous-derived-refresh.service\n", encoding="utf-8")
    passive_unit = {"name": cli.NERVOUS_PASSIVE_CHRONICLE_SERVICE, "is_active": True}
    derived_unit = {"name": cli.NERVOUS_DERIVED_REFRESH_SERVICE, "is_enabled": True}
    passive_show = {"properties": {"OnSuccess": cli.NERVOUS_DERIVED_REFRESH_SERVICE}}
    derived_show = {
        "properties": {
            "LoadState": "loaded",
            "FragmentPath": "/derived.service",
            "ExecStart": (
                "abyss-machine nervous quality-audit --refresh --json "
                "abyss-machine resource launch --class medium --kind indexing "
                "abyss-machine nervous index-build --json"
            ),
        }
    }

    monkeypatch.setattr(cli, "NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH", dropin_path)
    monkeypatch.setattr(
        cli,
        "user_systemd_unit",
        lambda unit: passive_unit if unit == cli.NERVOUS_PASSIVE_CHRONICLE_SERVICE else derived_unit,
    )
    monkeypatch.setattr(
        cli,
        "systemd_unit_properties",
        lambda unit, props, user=True: passive_show if unit == cli.NERVOUS_PASSIVE_CHRONICLE_SERVICE else derived_show,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T12:00:00+00:00")

    data = cli.nervous_derived_refresh_status()
    expected = nervous_quality.derived_refresh_status_document(
        passive_unit=passive_unit,
        derived_unit=derived_unit,
        passive_show=passive_show,
        derived_show=derived_show,
        passive_service=cli.NERVOUS_PASSIVE_CHRONICLE_SERVICE,
        derived_service=cli.NERVOUS_DERIVED_REFRESH_SERVICE,
        dropin_path=str(dropin_path),
        dropin_exists=True,
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data == expected


def test_cli_quality_audit_delegates_document_shape_to_module(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing-nervous.db"
    status_data = {"ok": True, "phase": "ready", "sources": {"enabled_safe_sources": ["facts"]}}
    capture_status = {"ok": True, "storage": {"root": "/srv/abyss-machine/nervous"}}
    derived_refresh_status = {"ok": True}
    privacy_status = {"global_pause": False, "private_mode": False}
    sources = {"safe_now": {"facts": {}}, "deferred_until_privacy_controls": {"browser": {}}}
    validation_ok = {"ok": True, "summary": {"fails": 0, "warnings": 0, "checks": 1}, "checks": [{"level": "ok"}]}
    index_status = {"ok": True, "ready": False}
    refresh_events = {"ok": True, "summary": {"events": 1}, "error": None}
    refresh_episodes = {"ok": True, "summary": {"episodes": 1}, "error": None}
    refresh_synthesis = {"ok": True, "candidate_id": "syn-cli", "summary": {"episodes": 1}, "error": None}
    refresh_eval = {"ok": True, "summary": {"checks": 1}, "error": None}
    calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", db_path)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T12:00:00+00:00")
    monkeypatch.setattr(cli, "nervous_events_build", lambda **kwargs: calls.append(("events_build", kwargs)) or refresh_events)
    monkeypatch.setattr(cli, "nervous_episodes_build", lambda **kwargs: calls.append(("episodes_build", kwargs)) or refresh_episodes)
    monkeypatch.setattr(cli, "nervous_synthesis_build", lambda **kwargs: calls.append(("synthesis_build", kwargs)) or refresh_synthesis)
    monkeypatch.setattr(cli, "nervous_eval_run", lambda **kwargs: calls.append(("eval_run", kwargs)) or refresh_eval)
    monkeypatch.setattr(cli, "nervous_status", lambda **kwargs: calls.append(("status", kwargs)) or status_data)
    monkeypatch.setattr(cli, "nervous_capture_status", lambda: calls.append(("capture",)) or capture_status)
    monkeypatch.setattr(cli, "nervous_derived_refresh_status", lambda: calls.append(("derived",)) or derived_refresh_status)
    monkeypatch.setattr(cli, "nervous_privacy_status", lambda **kwargs: calls.append(("privacy", kwargs)) or privacy_status)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda **kwargs: calls.append(("sources", kwargs)) or sources)
    monkeypatch.setattr(cli, "nervous_validate_snapshot", lambda: calls.append(("facts_validate",)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_events_validate", lambda **kwargs: calls.append(("events_validate", kwargs)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_episodes_validate", lambda **kwargs: calls.append(("episodes_validate", kwargs)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_synthesis_validate", lambda **kwargs: calls.append(("synthesis_validate", kwargs)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_eval_validate", lambda **kwargs: calls.append(("eval_validate", kwargs)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_retention_validate", lambda **kwargs: calls.append(("retention_validate", kwargs)) or validation_ok)
    monkeypatch.setattr(cli, "nervous_index_status", lambda **kwargs: calls.append(("index_status", kwargs)) or index_status)
    monkeypatch.setattr(
        cli,
        "load_json_document",
        lambda path: calls.append(("load_json", str(path))) or ({"ok": True, "summary": {"records": 1}}, None),
    )
    monkeypatch.setattr(
        cli,
        "nervous_redact_text",
        lambda text: calls.append(("redact", "password=" in text and "token=" in text)) or {"summary": {"matches": 2}},
    )
    monkeypatch.setattr(cli, "user_systemd_unit", lambda unit: calls.append(("systemd", unit)) or {"name": unit, "is_active": True})

    data = cli.nervous_quality_audit(refresh=True, refresh_index=False, write_latest=False, deep_index_validate=True)
    refresh_results = {
        "events_build": {"ok": True, "summary": {"events": 1}, "error": None},
        "episodes_build": {"ok": True, "summary": {"episodes": 1}, "error": None},
        "synthesis_build": {"ok": True, "candidate_id": "syn-cli", "summary": {"episodes": 1}, "error": None},
        "eval_run": {"ok": True, "summary": {"checks": 1}, "error": None},
    }
    index_validate = {
        "ok": False,
        "summary": {"fails": 1, "warnings": 0, "checks": 0},
        "checks": [
            {
                "level": "fail",
                "key": "index_db",
                "message": "nervous search index database missing",
                "details": {"path": str(db_path)},
            }
        ],
    }
    timers = {
        "passive_chronicle": {"name": cli.NERVOUS_PASSIVE_CHRONICLE_TIMER, "is_active": True},
        "browser_content_capture": {"name": cli.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER, "is_active": True},
        "search_index": {"name": cli.NERVOUS_SEARCH_INDEX_TIMER, "is_active": True},
        "semantic_maintain": {"name": cli.NERVOUS_SEMANTIC_MAINTAIN_TIMER, "is_active": True},
    }
    semantic_maintain = {
        "service": {"name": cli.NERVOUS_SEMANTIC_MAINTAIN_SERVICE, "is_active": True},
        "timer": {"name": cli.NERVOUS_SEMANTIC_MAINTAIN_TIMER, "is_active": True},
        "latest": str(cli.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH),
    }
    expected = nervous_quality.audit_document(
        refresh_requested=True,
        refresh_index_requested=False,
        refresh_results=refresh_results,
        validations={
            "facts": validation_ok,
            "events": validation_ok,
            "episodes": validation_ok,
            "synthesis": validation_ok,
            "eval": validation_ok,
            "retention": validation_ok,
            "index": index_validate,
        },
        timers=timers,
        status_data=status_data,
        capture_status=capture_status,
        derived_refresh_status=derived_refresh_status,
        privacy_status=privacy_status,
        sources=sources,
        index_status=index_status,
        semantic_maintain=semantic_maintain,
        browser_latest={"ok": True, "summary": {"records": 1}},
        browser_error=None,
        browser_path=str(cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH),
        redaction_summary={"matches": 2},
        privacy_state_path=str(cli.NERVOUS_PRIVACY_STATE_PATH),
        index_db_path=str(db_path),
        latest_path=str(cli.NERVOUS_QUALITY_LATEST_PATH),
        daily_glob=str(cli.NERVOUS_QUALITY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        commands={
            "audit": "abyss-machine nervous quality-audit --json",
            "refresh": "abyss-machine nervous quality-audit --refresh --json",
            "refresh_index": "abyss-machine nervous quality-audit --refresh --refresh-index --json",
            "validate": "abyss-machine nervous validate --json",
        },
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data == expected
    assert calls == [
        ("events_build", {"write_latest": True}),
        ("episodes_build", {"write_latest": True, "refresh_events": False}),
        ("synthesis_build", {"scope": "daily", "write_latest": True}),
        ("eval_run", {"write_latest": True}),
        ("status", {"write_latest": True}),
        ("capture",),
        ("derived",),
        ("privacy", {"write_latest": True}),
        ("sources", {"write_latest": True}),
        ("facts_validate",),
        ("events_validate", {"write_latest": True}),
        ("episodes_validate", {"write_latest": True}),
        ("synthesis_validate", {"write_latest": True}),
        ("eval_validate", {"write_latest": True}),
        ("retention_validate", {"write_latest": True}),
        ("index_status", {"write_latest": True}),
        ("load_json", str(cli.NERVOUS_BROWSER_CONTENT_LATEST_PATH)),
        ("redact", True),
        ("systemd", cli.NERVOUS_PASSIVE_CHRONICLE_TIMER),
        ("systemd", cli.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER),
        ("systemd", cli.NERVOUS_SEARCH_INDEX_TIMER),
        ("systemd", cli.NERVOUS_SEMANTIC_MAINTAIN_TIMER),
        ("systemd", cli.NERVOUS_SEMANTIC_MAINTAIN_SERVICE),
        ("systemd", cli.NERVOUS_SEMANTIC_MAINTAIN_TIMER),
    ]
