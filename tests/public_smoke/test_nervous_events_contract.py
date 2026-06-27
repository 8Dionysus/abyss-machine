from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine.nervous_events import (
    episode_record,
    episodes_build_document,
    episodes_from_events,
    episodes_validate_document,
    event_record,
    events_build_document,
    events_from_fact_records,
    events_validate_document,
    private_capture_events,
    thermal_event_classification,
    thermal_event_thresholds,
)


GENERATED_AT = "2026-06-25T12:00:00+00:00"


def fixture_snapshot_item() -> dict[str, object]:
    return {
        "path": "/srv/abyss-machine/nervous/facts/2026/06/2026-06-25.jsonl",
        "line": 1,
        "record_sha256": "record-sha",
        "source_sha256": "source-sha",
        "record": {
            "schema": "abyss_machine_nervous_fact_snapshot_v1",
            "generated_at": "2026-06-25T10:00:00+00:00",
            "capture": {"sources": ["abyss_machine_facts"], "manual": True, "trigger": "test"},
            "privacy": {"global_pause": False, "private_mode": False},
            "summary": {"facts": 4, "skipped": 0},
            "facts": [
                {
                    "name": "storage_latest",
                    "source": {"path": "/var/lib/abyss-machine/storage/latest.json", "sha256": "storage-sha", "read_at": GENERATED_AT},
                    "summary": {
                        "root_used_percent": 91.5,
                        "srv_used_percent": 44.0,
                        "root_warning": True,
                        "root_critical": True,
                        "podman_migration_status": "not_started",
                    },
                },
                {
                    "name": "observability_thermal_battery_latest",
                    "class": {"thermal": "ok"},
                    "battery": {"capacity_percent": 24, "ac_online": False, "status": "Discharging", "power_w": 8.5, "health_percent": 97},
                    "thermal": {"temperature_c_max": 107.5, "hottest": [{"sensor": "Package", "temperature_c": 107.5}]},
                },
                {
                    "name": "systemd_unit",
                    "scope": "user",
                    "unit": "abyss-machine-doctor.timer",
                    "observed_at": "2026-06-25T10:01:00+00:00",
                    "state": {"name": "abyss-machine-doctor.timer", "active": "active", "enabled": "enabled", "is_active": True, "is_enabled": True},
                },
                {
                    "name": "browser_recent",
                    "source_id": "browser_active_tab",
                    "observed_at": "2026-06-25T10:02:00+00:00",
                    "ok": True,
                    "sensitivity": "machine_metadata",
                    "summary": {"title": "redacted title", "url_sha256": "url-sha"},
                },
            ],
        },
    }


def test_nervous_event_records_are_deterministic_and_public_safe() -> None:
    evidence = [{"kind": "fixture", "path": "/state/latest.json"}]
    first = event_record(
        event_type="storage.pressure",
        category="storage",
        observed_at="2026-06-25T10:00:00+00:00",
        title="root storage pressure 91.5%",
        summary="Root filesystem pressure.",
        severity="critical",
        confidence="high",
        source_ids=["abyss_machine_facts", "abyss_machine_facts"],
        evidence=evidence,
        subject="root_storage_pressure",
        version="test",
        generated_at=GENERATED_AT,
    )
    second = event_record(
        event_type="storage.pressure",
        category="storage",
        observed_at="2026-06-25T10:00:00+00:00",
        title="root storage pressure 91.5%",
        summary="Root filesystem pressure.",
        severity="critical",
        confidence="high",
        source_ids=["abyss_machine_facts"],
        evidence=evidence,
        subject="root_storage_pressure",
        version="test",
        generated_at=GENERATED_AT,
    )

    assert first["event_id"] == second["event_id"]
    assert first["schema"] == "abyss_machine_nervous_event_v1"
    assert first["source_ids"] == ["abyss_machine_facts"]
    assert first["raw_private_content"] is False
    assert first["automatic_action"] is False


def test_nervous_events_from_fact_records_derive_known_event_classes() -> None:
    events, summary = events_from_fact_records(
        [fixture_snapshot_item()],
        thresholds=thermal_event_thresholds({"watch_above_c": 100, "hot_temperature_c": 106, "critical_temperature_c": 109}),
        deferred_source_ids={"browser_active_tab"},
        version="test",
        generated_at=GENERATED_AT,
    )
    by_type = {event["event_type"]: event for event in events}

    assert summary["input_snapshots"] == 1
    assert summary["events"] >= 5
    assert by_type["nervous.snapshot_recorded"]["raw_private_content"] is False
    assert by_type["storage.pressure"]["severity"] == "critical"
    assert by_type["thermal.state"]["severity"] == "warning"
    assert by_type["systemd.unit_state"]["source_ids"] == ["systemd_metadata"]
    assert by_type["capture.browser_recent_history"]["sensitivity"] == "local_private_redacted"
    assert all(event["generated_at"] == GENERATED_AT for event in events)

    second, _ = events_from_fact_records(
        [fixture_snapshot_item()],
        thresholds=thermal_event_thresholds({"watch_above_c": 100, "hot_temperature_c": 106, "critical_temperature_c": 109}),
        deferred_source_ids={"browser_active_tab"},
        version="test",
        generated_at=GENERATED_AT,
    )
    assert [event["event_id"] for event in events] == [event["event_id"] for event in second]


def test_nervous_private_capture_events_omit_raw_private_content() -> None:
    item = fixture_snapshot_item()
    record = item["record"]
    assert isinstance(record, dict)

    events = private_capture_events(
        item,
        record,
        deferred_source_ids={"browser_active_tab"},
        version="test",
        generated_at=GENERATED_AT,
    )

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "capture.browser_recent_history"
    assert event["raw_private_content"] is False
    assert event["payload"]["summary"] == {"title": "redacted title", "url_sha256": "url-sha"}
    assert "raw" not in event["payload"]


def test_nervous_events_build_and_validate_documents_are_module_owned() -> None:
    events, event_summary = events_from_fact_records(
        [fixture_snapshot_item()],
        thresholds=thermal_event_thresholds({"watch_above_c": 100, "hot_temperature_c": 106, "critical_temperature_c": 109}),
        deferred_source_ids={"browser_active_tab"},
        version="test",
        generated_at=GENERATED_AT,
    )
    build = events_build_document(
        items=[fixture_snapshot_item()],
        parse_errors=[],
        events=events,
        event_summary=event_summary,
        write_report={"error_count": 0, "files": []},
        facts_root="/srv/abyss-machine/nervous/facts",
        latest_path="/srv/abyss-machine/nervous/events/latest.json",
        daily_glob="/srv/abyss-machine/nervous/events/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at=GENERATED_AT,
    )
    items = [{"record": event, "path": "events.jsonl", "line": index} for index, event in enumerate(events, start=1)]
    allowed = {"abyss_machine_facts", "systemd_metadata", "browser_active_tab"}
    validate = events_validate_document(
        latest=build,
        latest_error=None,
        items=items,
        parse_errors=[],
        allowed_sources=allowed,
        latest_path="/srv/abyss-machine/nervous/events/latest.json",
        daily_glob="/srv/abyss-machine/nervous/events/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at=GENERATED_AT,
    )

    assert build["ok"] is True
    assert build["latest_event"]["event_id"] == events[-1]["event_id"]
    assert build["policy"]["raw_private_content"] is False
    assert validate["ok"] is True
    assert validate["summary"]["events"] == len(events)

    bad_validate = events_validate_document(
        latest=build,
        latest_error=None,
        items=[{"record": {**events[0], "raw_private_content": True}, "path": "events.jsonl", "line": 1}],
        parse_errors=[],
        allowed_sources=allowed,
        latest_path="/srv/abyss-machine/nervous/events/latest.json",
        daily_glob="/srv/abyss-machine/nervous/events/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at=GENERATED_AT,
    )
    assert bad_validate["ok"] is False
    assert any(check["key"] == "privacy_sources" and check["level"] == "fail" for check in bad_validate["checks"])


def test_nervous_episode_build_and_validate_documents_are_module_owned() -> None:
    events = [
        {
            "event_id": "evt-storage",
            "observed_at": "2026-06-25T10:00:00+00:00",
            "event_type": "storage.pressure",
            "category": "storage",
            "severity": "critical",
            "sensitivity": "machine_metadata",
            "source_ids": ["abyss_machine_facts"],
            "title": "Storage pressure",
        },
        {
            "event_id": "evt-browser",
            "observed_at": "2026-06-25T10:04:00+00:00",
            "event_type": "capture.browser_recent_history",
            "category": "storage",
            "severity": "notice",
            "sensitivity": "local_private_redacted",
            "source_ids": ["browser_active_tab"],
            "title": "Browser context",
        },
    ]
    first = episode_record("storage", events, "2026-06-25", version="test", generated_at=GENERATED_AT)
    second = episode_record("storage", events, "2026-06-25", version="test", generated_at=GENERATED_AT)
    episodes, summary = episodes_from_events(events, version="test", generated_at=GENERATED_AT)
    build = episodes_build_document(
        event_items=[{"record": event} for event in events],
        parse_errors=[],
        events_refresh={"ok": True, "summary": {"events": len(events)}},
        episodes=episodes,
        episode_summary=summary,
        write_report={"error_count": 0, "files": []},
        events_root="/srv/abyss-machine/nervous/events",
        latest_path="/srv/abyss-machine/nervous/episodes/latest.json",
        daily_glob="/srv/abyss-machine/nervous/episodes/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at=GENERATED_AT,
    )
    validate = episodes_validate_document(
        latest=build,
        latest_error=None,
        items=[{"record": episode, "path": "episodes.jsonl", "line": index} for index, episode in enumerate(episodes, start=1)],
        parse_errors=[],
        allowed_sources={"abyss_machine_facts", "browser_active_tab"},
        latest_path="/srv/abyss-machine/nervous/episodes/latest.json",
        daily_glob="/srv/abyss-machine/nervous/episodes/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at=GENERATED_AT,
    )

    assert first["episode_id"] == second["episode_id"]
    assert episodes[0]["severity"] == "critical"
    assert episodes[0]["sensitivity"] == "mixed_machine_metadata"
    assert summary["episodes"] == 1
    assert build["ok"] is True
    assert build["source"]["events_refresh"] == {"ok": True, "events": 2}
    assert validate["ok"] is True


def test_nervous_thermal_classification_uses_module_threshold_contract() -> None:
    thresholds = thermal_event_thresholds({
        "thin_laptop_active_range_c": [96, 103],
        "watch_above_c": 101,
        "hot_temperature_c": 106,
        "critical_temperature_c": 109,
    })

    assert thermal_event_classification(107.0, "ok", thresholds)[:2] == ("hot", "warning")
    assert thermal_event_classification(None, "hot", thresholds)[:2] == ("hot", "notice")


def test_cli_event_helpers_delegate_to_contract_module(monkeypatch) -> None:
    def fake_severity_max(values: list[str]) -> str:
        assert values == ["info"]
        return "critical"

    monkeypatch.setattr(cli.nervous_events_contracts, "severity_max", fake_severity_max)

    assert cli.nervous_severity_max(["info"]) == "critical"
