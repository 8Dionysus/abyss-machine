from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_quality_adapters as adapters  # noqa: E402


GENERATED_AT = "2026-06-26T12:00:00+00:00"


def _ok_doc(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "summary": summary or {"fails": 0, "warnings": 0, "checks": 1}, "checks": [{"level": "ok"}]}


def test_run_quality_audit_collects_refresh_validation_and_write_ports(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    writes: list[tuple[str, str]] = []
    quality_root = tmp_path / "quality"
    latest_path = quality_root / "latest.json"
    daily_path = quality_root / "2026" / "06" / "2026-06-26.jsonl"
    browser_latest_path = tmp_path / "browser" / "latest.json"
    index_db_path = tmp_path / "missing.db"
    validation = _ok_doc()

    def mapping_port(name: str, result: dict[str, Any]):
        def _port(**kwargs: Any) -> dict[str, Any]:
            calls.append((name, kwargs))
            return result
        return _port

    def noarg_port(name: str, result: dict[str, Any]):
        def _port() -> dict[str, Any]:
            calls.append((name,))
            return result
        return _port

    def latest_reader(path: Path):
        calls.append(("latest_reader", path))
        return {"ok": True, "summary": {"records": 1}}, None

    def redaction(text: str):
        calls.append(("redaction", "CorrectHorseBatteryStaple" in text, "ghp_" in text))
        return {"summary": {"matches": 2}}

    def systemd(unit: str):
        calls.append(("systemd", unit))
        return {"name": unit, "is_active": True}

    def latest_writer(path: Path, data: dict[str, Any], mode: int):
        writes.append((str(path), data["schema"]))
        assert mode == 0o664
        return None

    def jsonl_append(path: Path, data: dict[str, Any], mode: int):
        writes.append((str(path), data["schema"]))
        assert mode == 0o664
        return None

    data = adapters.run_quality_audit(
        refresh=True,
        refresh_index=False,
        write_latest_enabled=True,
        deep_index_validate=True,
        search_index_db_path=index_db_path,
        browser_content_latest_path=browser_latest_path,
        privacy_state_path=tmp_path / "privacy.json",
        quality_latest_path=latest_path,
        quality_root=quality_root,
        semantic_maintain_latest_path=tmp_path / "semantic" / "latest.json",
        passive_chronicle_timer="passive.timer",
        browser_content_capture_timer="browser.timer",
        search_index_timer="index.timer",
        semantic_maintain_timer="semantic.timer",
        semantic_maintain_service="semantic.service",
        commands={"audit": "quality"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        index_build=mapping_port("index_build", _ok_doc({"chunks": 1})),
        events_build=mapping_port("events_build", _ok_doc({"events": 1})),
        episodes_build=mapping_port("episodes_build", _ok_doc({"episodes": 1})),
        synthesis_build=mapping_port("synthesis_build", {"ok": True, "candidate_id": "syn-test", "summary": {"episodes": 1}}),
        eval_run=mapping_port("eval_run", _ok_doc({"checks": 6})),
        status=mapping_port("status", {"ok": True, "phase": "ready", "sources": {"enabled_safe_sources": ["facts"]}}),
        capture_status=noarg_port("capture", {"ok": True, "storage": {"root": "/srv/abyss-machine/nervous"}}),
        derived_refresh_status=noarg_port("derived", {"ok": True}),
        privacy_status=mapping_port("privacy", {"global_pause": False, "private_mode": False}),
        effective_sources=mapping_port("sources", {"safe_now": {"facts": {}}, "deferred_until_privacy_controls": {}}),
        facts_validate=noarg_port("facts_validate", validation),
        events_validate=mapping_port("events_validate", validation),
        episodes_validate=mapping_port("episodes_validate", validation),
        synthesis_validate=mapping_port("synthesis_validate", validation),
        eval_validate=mapping_port("eval_validate", validation),
        retention_validate=mapping_port("retention_validate", validation),
        index_status=mapping_port("index_status", {"ok": True, "ready": False}),
        index_validate=mapping_port("index_validate", validation),
        bounded_index_validate_from_status=lambda status: calls.append(("bounded_index", status)) or validation,
        latest_reader=latest_reader,
        redaction_smoke=redaction,
        systemd_unit=systemd,
        latest_writer=latest_writer,
        jsonl_append=jsonl_append,
        today_path=lambda root: daily_path,
        path_exists_port=lambda path: False,
    )

    assert data["schema"] == "abyss_machine_nervous_quality_audit_v1"
    assert data["refresh"]["results"]["events_build"]["summary"] == {"events": 1}
    assert data["refresh"]["results"]["episodes_build"]["summary"] == {"episodes": 1}
    assert data["refresh"]["results"]["synthesis_build"]["candidate_id"] == "syn-test"
    assert data["validations"]["index"]["summary"]["fails"] == 1
    assert data["capture"]["browser_content_latest"]["summary"] == {"records": 1}
    assert writes == [
        (str(latest_path), "abyss_machine_nervous_quality_audit_v1"),
        (str(daily_path), "abyss_machine_nervous_quality_audit_v1"),
    ]
    assert calls[:4] == [
        ("events_build", {"write_latest": True}),
        ("episodes_build", {"write_latest": True, "refresh_events": False}),
        ("synthesis_build", {"scope": "daily", "write_latest": True}),
        ("eval_run", {"write_latest": True}),
    ]
    assert ("latest_reader", browser_latest_path) in calls
    assert ("redaction", True, True) in calls
    assert ("systemd", "semantic.service") in calls
    assert "CorrectHorseBatteryStaple" not in str(data)


def test_run_quality_audit_refresh_index_uses_index_build_and_bounded_validation(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    quality_root = tmp_path / "quality"
    index_db_path = tmp_path / "index.db"
    validation = _ok_doc()
    index_status_doc = {"ok": True, "ready": True, "summary": {"documents": 10}}

    def mapping_port(name: str, result: dict[str, Any]):
        def _port(**kwargs: Any) -> dict[str, Any]:
            calls.append((name, kwargs))
            return result

        return _port

    def noarg_port(name: str, result: dict[str, Any]):
        def _port() -> dict[str, Any]:
            calls.append((name,))
            return result

        return _port

    def forbidden_port(name: str):
        def _port(**kwargs: Any) -> dict[str, Any]:
            raise AssertionError(f"{name} should not be called")

        return _port

    data = adapters.run_quality_audit(
        refresh=True,
        refresh_index=True,
        write_latest_enabled=False,
        deep_index_validate=False,
        search_index_db_path=index_db_path,
        browser_content_latest_path=tmp_path / "browser" / "latest.json",
        privacy_state_path=tmp_path / "privacy.json",
        quality_latest_path=quality_root / "latest.json",
        quality_root=quality_root,
        semantic_maintain_latest_path=tmp_path / "semantic" / "latest.json",
        passive_chronicle_timer="passive.timer",
        browser_content_capture_timer="browser.timer",
        search_index_timer="index.timer",
        semantic_maintain_timer="semantic.timer",
        semantic_maintain_service="semantic.service",
        commands={"audit": "quality"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        index_build=mapping_port("index_build", {"ok": True, "summary": {"documents": 10}, "derived_refresh": {"ok": True}}),
        events_build=forbidden_port("events_build"),
        episodes_build=forbidden_port("episodes_build"),
        synthesis_build=mapping_port("synthesis_build", {"ok": True, "candidate_id": "syn-index", "summary": {"episodes": 1}}),
        eval_run=mapping_port("eval_run", validation),
        status=mapping_port("status", {"ok": True}),
        capture_status=noarg_port("capture", {"ok": True}),
        derived_refresh_status=noarg_port("derived", {"ok": True}),
        privacy_status=mapping_port("privacy", {"global_pause": False}),
        effective_sources=mapping_port("sources", {"safe_now": {}, "deferred_until_privacy_controls": {}}),
        facts_validate=noarg_port("facts_validate", validation),
        events_validate=mapping_port("events_validate", validation),
        episodes_validate=mapping_port("episodes_validate", validation),
        synthesis_validate=mapping_port("synthesis_validate", validation),
        eval_validate=mapping_port("eval_validate", validation),
        retention_validate=mapping_port("retention_validate", validation),
        index_status=mapping_port("index_status", index_status_doc),
        index_validate=forbidden_port("index_validate"),
        bounded_index_validate_from_status=lambda status: calls.append(("bounded_index", status)) or validation,
        latest_reader=lambda path: (None, "missing"),
        redaction_smoke=lambda text: {"summary": {"matches": 2}},
        systemd_unit=lambda unit: {"name": unit},
        path_exists_port=lambda path: path == index_db_path,
    )

    assert data["refresh"]["results"]["index_build"]["summary"] == {"documents": 10}
    assert data["refresh"]["results"]["index_build"]["derived_refresh"] == {"ok": True}
    assert data["refresh"]["results"]["synthesis_build"]["candidate_id"] == "syn-index"
    assert data["validations"]["index"]["ok"] is True
    assert data["validations"]["index"]["summary"] == {"fails": 0, "warnings": 0, "checks": 1}
    assert ("index_build", {"write_latest": True, "refresh_derived": True}) in calls
    assert ("bounded_index", index_status_doc) in calls
    assert not any(call[0] == "events_build" for call in calls)
    assert "write_errors" not in data


def test_cli_quality_audit_binds_concrete_ports_to_adapter(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def fake_run_quality_audit(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "schema": "fixture_quality"}

    monkeypatch.setattr(cli.nervous_quality_adapters, "run_quality_audit", fake_run_quality_audit)
    monkeypatch.setattr(cli, "NERVOUS_SEARCH_INDEX_DB_PATH", tmp_path / "index.db")
    monkeypatch.setattr(cli, "now_iso", lambda: GENERATED_AT)

    assert cli.nervous_quality_audit(refresh=True, refresh_index=True, write_latest=False, deep_index_validate=False) == {
        "ok": True,
        "schema": "fixture_quality",
    }

    assert captured["refresh"] is True
    assert captured["refresh_index"] is True
    assert captured["write_latest_enabled"] is False
    assert captured["deep_index_validate"] is False
    assert captured["search_index_db_path"] == tmp_path / "index.db"
    assert captured["index_build"] is cli.nervous_index_build
    assert captured["events_build"] is cli.nervous_events_build
    assert captured["episodes_build"] is cli.nervous_episodes_build
    assert captured["synthesis_build"] is cli.nervous_synthesis_build
    assert captured["eval_run"] is cli.nervous_eval_run
    assert captured["latest_reader"] is cli.load_json_document
    assert captured["redaction_smoke"] is cli.nervous_redact_text
    assert captured["systemd_unit"] is cli.user_systemd_unit
    assert captured["latest_writer"] is cli.safe_atomic_write_json
    assert captured["jsonl_append"] is cli.safe_append_jsonl
    assert captured["today_path"] is cli.nervous_today_path
