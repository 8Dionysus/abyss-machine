from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_events_adapters


GENERATED_AT = "2026-06-25T12:00:00+00:00"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event(event_id: str = "evt-new") -> dict[str, object]:
    return {
        "schema": "abyss_machine_nervous_event_v1",
        "version": "test",
        "event_id": event_id,
        "generated_at": GENERATED_AT,
        "observed_at": "2026-06-25T10:00:00+00:00",
        "event_type": "storage.pressure",
        "category": "storage",
        "subject": "root_storage_pressure",
        "severity": "warning",
        "confidence": "high",
        "sensitivity": "machine_metadata",
        "source_ids": ["abyss_machine_facts"],
        "title": "Storage pressure",
        "summary": "Root filesystem pressure.",
        "evidence": [],
        "payload": {},
        "derived_by": "nervous_events_build_v1",
        "raw_private_content": False,
        "automatic_action": False,
    }


def _episode(episode_id: str = "eps-new") -> dict[str, object]:
    return {
        "schema": "abyss_machine_nervous_episode_v1",
        "version": "test",
        "episode_id": episode_id,
        "generated_at": GENERATED_AT,
        "start_at": "2026-06-25T10:00:00+00:00",
        "end_at": "2026-06-25T10:00:00+00:00",
        "day": "2026-06-25",
        "category": "storage",
        "severity": "warning",
        "confidence": "medium",
        "sensitivity": "machine_metadata",
        "source_ids": ["abyss_machine_facts"],
        "title": "storage episode 2026-06-25",
        "summary": "Storage episode.",
        "event_count": 1,
        "event_ids": ["evt-new"],
        "event_types": ["storage.pressure"],
        "evidence": [],
        "derived_by": "nervous_episodes_build_v1",
        "raw_private_content": False,
        "automatic_action": False,
    }


def test_write_derived_records_preserves_foreign_records_and_replaces_owned_records(tmp_path: Path) -> None:
    root = tmp_path / "events"
    day = root / "2026" / "06" / "2026-06-25.jsonl"
    day.parent.mkdir(parents=True)
    kept = {"schema": "custom", "id": "kept", "derived_by": "manual"}
    stale = {**_event("evt-stale"), "derived_by": "nervous_events_build_v1"}
    day.write_text(json.dumps(kept) + "\n" + json.dumps(stale) + "\n", encoding="utf-8")

    report = nervous_events_adapters.write_derived_records(root, [_event("evt-new")], "nervous_events_build_v1")
    records = _read_jsonl(day)

    assert report["error_count"] == 0
    assert report["files"][0]["kept_existing"] == 1
    assert report["files"][0]["derived_written"] == 1
    assert [record.get("id") or record.get("event_id") for record in records] == ["kept", "evt-new"]


def test_build_events_reads_facts_writes_derived_records_and_routes_latest(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    latest_path = events_root / "latest.json"
    writes: list[tuple[str, str]] = []

    fact_items = [{"record": {"schema": "abyss_machine_nervous_fact_snapshot_v1"}, "path": "facts.jsonl", "line": 1}]

    def records_reader(root: Path):
        assert root == facts_root
        return fact_items, []

    def events_builder(items):
        assert items == fact_items
        return [_event("evt-build")], {"input_snapshots": 1, "events": 1}

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_events_adapters.build_events(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records=events_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        records_reader=records_reader,
        latest_writer=latest_writer,
    )

    day = events_root / "2026" / "06" / "2026-06-25.jsonl"
    assert data["ok"] is True
    assert data["summary"]["events"] == 1
    assert _read_jsonl(day)[0]["event_id"] == "evt-build"
    assert writes == [(str(latest_path), "abyss_machine_nervous_events_build_v1")]


def test_validate_events_uses_fakeable_latest_and_record_ports(tmp_path: Path) -> None:
    writes: list[tuple[str, str]] = []
    events_root = tmp_path / "events"
    latest_path = events_root / "latest.json"
    validate_path = events_root / "validate" / "latest.json"

    def latest_reader(path: Path):
        assert path == latest_path
        return {"schema": "abyss_machine_nervous_events_build_v1", "ok": True}, None

    def records_reader(root: Path):
        assert root == events_root
        return [{"record": _event(), "path": "events.jsonl", "line": 1}], []

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_events_adapters.validate_events(
        events_root=events_root,
        latest_path=latest_path,
        validate_latest_path=validate_path,
        allowed_sources={"abyss_machine_facts"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        records_reader=records_reader,
        latest_reader=latest_reader,
        latest_writer=latest_writer,
    )

    assert data["ok"] is True
    assert data["summary"]["events"] == 1
    assert writes == [(str(validate_path), "abyss_machine_nervous_events_validate_v1")]


def test_build_and_validate_episodes_route_files_and_latest(tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"
    validate_path = episodes_root / "validate" / "latest.json"
    writes: list[tuple[str, str]] = []

    def records_reader(root: Path):
        if root == events_root:
            return [{"record": _event(), "path": "events.jsonl", "line": 1}], []
        if root == episodes_root:
            return [{"record": _episode(), "path": "episodes.jsonl", "line": 1}], []
        raise AssertionError(root)

    def episodes_builder(events):
        assert [event["event_id"] for event in events] == ["evt-new"]
        return [_episode("eps-build")], {"input_events": 1, "episodes": 1}

    def latest_reader(path: Path):
        assert path == latest_path
        return {"schema": "abyss_machine_nervous_episodes_build_v1", "ok": True}, None

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    build = nervous_events_adapters.build_episodes(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=episodes_builder,
        event_records_from_items=lambda items: [item["record"] for item in items],
        events_refresh={"ok": True, "summary": {"events": 1}},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        records_reader=records_reader,
        latest_writer=latest_writer,
    )
    validate = nervous_events_adapters.validate_episodes(
        episodes_root=episodes_root,
        latest_path=latest_path,
        validate_latest_path=validate_path,
        allowed_sources={"abyss_machine_facts"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        records_reader=records_reader,
        latest_reader=latest_reader,
        latest_writer=latest_writer,
    )

    day = episodes_root / "2026" / "06" / "2026-06-25.jsonl"
    assert build["ok"] is True
    assert build["summary"]["episodes"] == 1
    assert _read_jsonl(day)[0]["episode_id"] == "eps-build"
    assert validate["ok"] is True
    assert writes == [
        (str(latest_path), "abyss_machine_nervous_episodes_build_v1"),
        (str(validate_path), "abyss_machine_nervous_episodes_validate_v1"),
    ]


def test_cli_events_build_binds_file_work_to_adapter(monkeypatch, tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    latest_path = events_root / "latest.json"
    captured: dict[str, object] = {}

    def fake_build_events(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(cli, "NERVOUS_FACTS_ROOT", facts_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli.nervous_events_adapters, "build_events", fake_build_events)

    data = cli.nervous_events_build(write_latest=False)

    assert data == {"ok": True, "from_adapter": True}
    assert captured["facts_root"] == facts_root
    assert captured["events_root"] == events_root
    assert captured["latest_path"] == latest_path
    assert captured["events_from_fact_records"] is cli.nervous_events_from_fact_records
    assert captured["write_latest_enabled"] is False
    assert captured["latest_writer"] is cli.safe_atomic_write_json


def test_cli_episodes_build_keeps_refresh_orchestration_at_edge(monkeypatch, tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"
    captured: dict[str, object] = {}
    refresh_calls: list[bool] = []
    refresh_document = {"ok": True, "summary": {"events": 1}}

    def fake_build_episodes(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    def fake_events_build(write_latest: bool = True):
        refresh_calls.append(write_latest)
        return refresh_document

    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_ROOT", episodes_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_events_build", fake_events_build)
    monkeypatch.setattr(cli.nervous_events_adapters, "build_episodes", fake_build_episodes)

    data = cli.nervous_episodes_build(write_latest=True, refresh_events=True)

    assert data == {"ok": True, "from_adapter": True}
    assert refresh_calls == [True]
    assert captured["events_root"] == events_root
    assert captured["episodes_root"] == episodes_root
    assert captured["latest_path"] == latest_path
    assert captured["episodes_from_events"] is cli.nervous_episodes_from_events
    assert captured["events_refresh"] == refresh_document
    assert captured["write_latest_enabled"] is True
    assert captured["latest_writer"] is cli.safe_atomic_write_json


def test_cli_event_episode_validate_binds_latest_writes_to_adapter(monkeypatch, tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    events_latest = events_root / "latest.json"
    episodes_latest = episodes_root / "latest.json"
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_validate_events(**kwargs):
        calls.append(("events", kwargs))
        return {"ok": True, "schema": "events"}

    def fake_validate_episodes(**kwargs):
        calls.append(("episodes", kwargs))
        return {"ok": True, "schema": "episodes"}

    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_ROOT", episodes_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_LATEST_PATH", events_latest)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_LATEST_PATH", episodes_latest)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: {"sources": {}})
    monkeypatch.setattr(cli, "nervous_allowed_source_ids", lambda sources: {"abyss_machine_facts"})
    monkeypatch.setattr(cli.nervous_events_adapters, "validate_events", fake_validate_events)
    monkeypatch.setattr(cli.nervous_events_adapters, "validate_episodes", fake_validate_episodes)

    assert cli.nervous_events_validate(write_latest=False) == {"ok": True, "schema": "events"}
    assert cli.nervous_episodes_validate(write_latest=True) == {"ok": True, "schema": "episodes"}

    assert calls[0][1]["events_root"] == events_root
    assert calls[0][1]["latest_path"] == events_latest
    assert calls[0][1]["validate_latest_path"] == events_root / "validate" / "latest.json"
    assert calls[0][1]["allowed_sources"] == {"abyss_machine_facts"}
    assert calls[0][1]["write_latest_enabled"] is False
    assert calls[0][1]["latest_reader"] is cli.load_json_document
    assert calls[0][1]["latest_writer"] is cli.safe_atomic_write_json
    assert calls[1][1]["episodes_root"] == episodes_root
    assert calls[1][1]["latest_path"] == episodes_latest
    assert calls[1][1]["validate_latest_path"] == episodes_root / "validate" / "latest.json"
    assert calls[1][1]["allowed_sources"] == {"abyss_machine_facts"}
    assert calls[1][1]["write_latest_enabled"] is True
    assert calls[1][1]["latest_reader"] is cli.load_json_document
    assert calls[1][1]["latest_writer"] is cli.safe_atomic_write_json
