from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_events
from abyss_machine import nervous_events_adapters
from abyss_machine import nervous_index


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


def _fact_snapshot(generated_at: str, root_used_percent: float) -> dict[str, object]:
    return {
        "schema": "abyss_machine_nervous_fact_snapshot_v1",
        "version": "test",
        "generated_at": generated_at,
        "capture": {
            "sources": ["abyss_machine_facts"],
            "trigger": "test",
            "raw_private_content": False,
        },
        "privacy": {"global_pause": False, "private_mode": False},
        "summary": {"facts": 1, "skipped": 0},
        "facts": [
            {
                "name": "storage_latest",
                "summary": {
                    "root_used_percent": root_used_percent,
                    "srv_used_percent": 40.0,
                    "root_warning": root_used_percent >= 85.0,
                    "root_critical": root_used_percent >= 95.0,
                    "podman_migration_status": "not_started",
                },
            }
        ],
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


def test_write_derived_records_keeps_exact_fixed_point_without_rewrite(tmp_path: Path) -> None:
    root = tmp_path / "events"
    day = root / "2026" / "06" / "2026-06-25.jsonl"
    day.parent.mkdir(parents=True)
    event = _event("evt-stable")
    day.write_text(json.dumps(event) + "\n", encoding="utf-8")

    def forbidden_writer(path: Path, records: list[dict[str, object]]) -> str | None:
        raise AssertionError("an exact derived fixed point must not be rewritten")

    report = nervous_events_adapters.write_derived_records(
        root,
        [event],
        "nervous_events_build_v1",
        writer=forbidden_writer,
    )

    assert report["error_count"] == 0
    assert report["files"] == [
        {
            "path": str(day),
            "kept_existing": 0,
            "derived_written": 1,
            "records_written": 1,
            "parse_errors": 0,
            "status": "unchanged",
        }
    ]


def test_append_derived_records_attests_only_an_exact_append_prefix(tmp_path: Path) -> None:
    root = tmp_path / "events"
    day = root / "2026" / "06" / "2026-06-25.jsonl"
    day.parent.mkdir(parents=True)
    day.write_text(json.dumps(_event("evt-old")) + "\n", encoding="utf-8")

    exact = nervous_events_adapters.append_derived_records(
        root,
        [
            {
                **_event("evt-new"),
                "generated_at": "2026-06-25T06:01:00-06:00",
                "observed_at": "2026-06-25T11:00:00+00:00",
            }
        ],
        "nervous_events_build_v1",
    )
    assert exact["error_count"] == 0
    assert len(exact["delta_attestations"]) == 1
    assert exact["delta_attestations"][0]["basis"] == "append_only"

    interleaved_observation = nervous_events_adapters.append_derived_records(
        root,
        [
            {
                **_event("evt-generated-later"),
                "generated_at": "2026-06-25T06:02:00-06:00",
                "observed_at": "2026-06-25T09:59:00+00:00",
            }
        ],
        "nervous_events_build_v1",
    )
    assert interleaved_observation["error_count"] == 0
    assert len(interleaved_observation["delta_attestations"]) == 1
    assert _read_jsonl(day)[-1]["event_id"] == "evt-generated-later"

    def prefix_changing_writer(path: Path, records: list[dict[str, object]]) -> str | None:
        path.write_text(
            json.dumps({"schema": "foreign-prefix"})
            + "\n"
            + "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return None

    rejected = nervous_events_adapters.append_derived_records(
        root,
        [
            {
                **_event("evt-later"),
                "generated_at": "2026-06-25T06:03:00-06:00",
                "observed_at": "2026-06-25T12:00:00+00:00",
            }
        ],
        "nervous_events_build_v1",
        writer=prefix_changing_writer,
    )
    assert rejected["error_count"] == 0
    assert rejected["delta_attestations"] == []


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


def test_incremental_events_append_state_matches_full_oracle(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    fact_path = facts_root / "2026" / "06" / "2026-06-25.jsonl"
    fact_path.parent.mkdir(parents=True)
    first_fact = _fact_snapshot("2026-06-25T10:00:00+00:00", 84.0)
    second_fact = _fact_snapshot("2026-06-25T10:05:00+00:00", 91.0)
    fact_path.write_text(json.dumps(first_fact) + "\n", encoding="utf-8")

    def stateful_builder(items, initial_state=None):
        return nervous_events.events_from_fact_records_with_state(
            items,
            initial_state=initial_state,
            version="test",
        )

    events_root = tmp_path / "events-delta"
    latest_path = events_root / "latest.json"
    seed = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
    )
    assert seed["ok"] is True
    assert seed["incremental"]["strategy"] == "full_rebuild"
    assert seed["incremental"]["valid"] is True

    with fact_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(second_fact) + "\n")
    delta = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:06:00+00:00",
    )
    assert delta["ok"] is True
    assert delta["incremental"]["strategy"] == "append_state_delta"
    assert delta["incremental"]["delta"]["source_records"] == 1
    assert delta["incremental"]["delta"]["admitted"] is True
    attestations = delta["incremental"]["delta_attestations"]
    event_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    assert {item["path"] for item in attestations} == {str(fact_path), str(event_path)}
    for attestation in attestations:
        core = {
            key: attestation[key]
            for key in ("schema", "path", "basis", "base", "current")
        }
        assert attestation["proof_sha256"] == nervous_index.stable_json_sha256(core)

    oracle_root = tmp_path / "events-oracle"
    oracle = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=oracle_root,
        latest_path=oracle_root / "latest.json",
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:07:00+00:00",
    )
    assert oracle["incremental"]["strategy"] == "full_rebuild"
    assert delta["summary"] == oracle["summary"]
    delta_records = _read_jsonl(events_root / "2026" / "06" / "2026-06-25.jsonl")
    oracle_records = _read_jsonl(oracle_root / "2026" / "06" / "2026-06-25.jsonl")
    assert delta_records == oracle_records

    def forbidden_content_read(path: Path) -> bytes:
        raise AssertionError(f"unchanged fact partition must not be read: {path}")

    fixed_point = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:08:00+00:00",
        source_bytes_reader=forbidden_content_read,
    )
    assert fixed_point["ok"] is True
    assert fixed_point["incremental"]["strategy"] == "append_state_delta"
    assert fixed_point["incremental"]["delta"] == {
        "source_records": 0,
        "events": 0,
        "admitted": True,
    }
    assert fixed_point["incremental"]["source_scan"] == {
        "partitions_reused_by_observation": 1,
        "content_bytes_reused": fact_path.stat().st_size,
        "content_bytes_hashed": 0,
        "observation_fields": ["device", "inode", "size_bytes", "mtime_ns", "ctime_ns"],
    }
    forced = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:09:00+00:00",
        force_full=True,
    )
    assert forced["ok"] is True
    assert forced["incremental"]["strategy"] == "full_rebuild"
    assert "full_rebuild_forced" in forced["incremental"]["fallback_reasons"]


def test_incremental_events_forces_full_oracle_when_derivation_policy_changes(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    fact_path = facts_root / "2026" / "06" / "2026-06-25.jsonl"
    fact_path.parent.mkdir(parents=True)
    fact_path.write_text(
        json.dumps(_fact_snapshot("2026-06-25T10:00:00+00:00", 84.0)) + "\n",
        encoding="utf-8",
    )
    events_root = tmp_path / "events"

    def stateful_builder(items, initial_state=None):
        return nervous_events.events_from_fact_records_with_state(
            items,
            initial_state=initial_state,
            version="test",
        )

    seed = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=events_root / "latest.json",
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
        derivation_identity="policy-v1",
    )
    assert seed["ok"] is True

    changed = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=events_root / "latest.json",
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:02:00+00:00",
        derivation_identity="policy-v2",
    )

    assert changed["ok"] is True
    assert changed["incremental"]["strategy"] == "full_rebuild"
    assert changed["incremental"]["derivation_identity"] == "policy-v2"
    assert "derivation_identity_mismatch" in changed["incremental"]["fallback_reasons"]


def test_incremental_events_falls_back_for_historical_partition_change(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    old_path = facts_root / "2026" / "06" / "2026-06-24.jsonl"
    current_path = facts_root / "2026" / "06" / "2026-06-25.jsonl"
    old_path.parent.mkdir(parents=True)
    old_path.write_text(json.dumps(_fact_snapshot("2026-06-24T10:00:00+00:00", 80.0)) + "\n", encoding="utf-8")
    current_path.write_text(json.dumps(_fact_snapshot("2026-06-25T10:00:00+00:00", 81.0)) + "\n", encoding="utf-8")

    def stateful_builder(items, initial_state=None):
        return nervous_events.events_from_fact_records_with_state(items, initial_state=initial_state, version="test")

    events_root = tmp_path / "events"
    latest_path = events_root / "latest.json"
    nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
    )
    old_path.write_text(json.dumps(_fact_snapshot("2026-06-24T10:00:00+00:00", 95.0)) + "\n", encoding="utf-8")
    rebuilt = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=latest_path,
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:02:00+00:00",
    )
    assert rebuilt["incremental"]["strategy"] == "full_rebuild"
    assert any(
        reason.startswith("historical_partition_changed:")
        for reason in rebuilt["incremental"]["fallback_reasons"]
    )


def test_incremental_events_refuses_source_race_before_derived_write(tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    fact_path = facts_root / "2026" / "06" / "2026-06-25.jsonl"
    fact_path.parent.mkdir(parents=True)
    fact_path.write_text(
        json.dumps(_fact_snapshot("2026-06-25T10:00:00+00:00", 91.0)) + "\n",
        encoding="utf-8",
    )

    def stateful_builder(items, initial_state=None):
        return nervous_events.events_from_fact_records_with_state(
            items,
            initial_state=initial_state,
            version="test",
        )

    def forbidden_writer(*_args, **_kwargs):
        raise AssertionError("source race must refuse before a derived write")

    events_root = tmp_path / "events"
    result = nervous_events_adapters.build_events_incremental(
        facts_root=facts_root,
        events_root=events_root,
        latest_path=events_root / "latest.json",
        events_from_fact_records_with_state=stateful_builder,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
        write_latest_enabled=False,
        source_snapshot_validator=lambda *_args, **_kwargs: "facts changed after planning",
        full_derived_writer=forbidden_writer,
        append_derived_writer=forbidden_writer,
    )

    assert result["ok"] is False
    assert result["refused"] is True
    assert result["decision"] == "source_snapshot_changed"
    assert result["error"] == "facts changed after planning"
    assert not nervous_events_adapters.jsonl_files(events_root)


def test_run_events_build_refuses_before_file_ports_when_paused(tmp_path: Path) -> None:
    writes: list[tuple[str, str]] = []

    def fail_port(*_args, **_kwargs):
        raise AssertionError("global pause should refuse before file/build ports")

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_events_adapters.run_events_build(
        privacy={"global_pause": True},
        facts_root=tmp_path / "facts",
        events_root=tmp_path / "events",
        latest_path=tmp_path / "events" / "latest.json",
        events_from_fact_records=fail_port,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        records_reader=fail_port,
        derived_writer=fail_port,
        latest_writer=latest_writer,
    )

    assert data == {
        "schema": "abyss_machine_nervous_events_build_v1",
        "version": "test",
        "generated_at": GENERATED_AT,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; event build did not touch derived event files",
    }
    assert writes == [(str(tmp_path / "events" / "latest.json"), "abyss_machine_nervous_events_build_v1")]


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


def test_incremental_episodes_partition_delta_matches_full_oracle_and_fixed_point(tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    old_path = events_root / "2026" / "06" / "2026-06-24.jsonl"
    current_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    old_path.parent.mkdir(parents=True)

    def event(event_id: str, observed_at: str, category: str) -> dict[str, object]:
        return {
            **_event(event_id),
            "generated_at": observed_at,
            "observed_at": observed_at,
            "category": category,
            "event_type": f"{category}.test",
            "title": f"{category} {event_id}",
        }

    old_path.write_text(
        json.dumps(event("evt-old", "2026-06-24T10:00:00+00:00", "storage")) + "\n",
        encoding="utf-8",
    )
    current_path.write_text(
        json.dumps(event("evt-current-1", "2026-06-25T10:00:00+00:00", "thermal")) + "\n",
        encoding="utf-8",
    )

    def episodes_builder(events):
        return nervous_events.episodes_from_events(events, version="test")

    def event_records(items):
        return nervous_events.event_records_from_items(items)

    delta_root = tmp_path / "episodes-delta"
    delta_latest = delta_root / "latest.json"
    seed = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=delta_root,
        latest_path=delta_latest,
        episodes_from_events=episodes_builder,
        event_records_from_items=event_records,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
    )
    assert seed["ok"] is True
    assert seed["incremental"]["strategy"] == "full_rebuild"
    assert seed["incremental"]["partition_local"] is True

    with current_path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(event("evt-current-2", "2026-06-25T10:05:00+00:00", "thermal"))
            + "\n"
        )
    delta = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=delta_root,
        latest_path=delta_latest,
        episodes_from_events=episodes_builder,
        event_records_from_items=event_records,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:06:00+00:00",
    )
    assert delta["ok"] is True
    assert delta["incremental"]["strategy"] == "file_partition_delta"
    assert delta["incremental"]["source_partitions"] == {
        "total": 2,
        "changed": 1,
        "unchanged": 1,
        "removed": 0,
        "metadata_refreshed": 0,
        "episode_partitions_replaced": 1,
    }
    assert delta["incremental"]["delta"] == {"source_events": 2, "episodes": 1}

    oracle_root = tmp_path / "episodes-oracle"
    oracle = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=oracle_root,
        latest_path=oracle_root / "latest.json",
        episodes_from_events=episodes_builder,
        event_records_from_items=event_records,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:07:00+00:00",
    )
    assert oracle["ok"] is True
    assert oracle["incremental"]["strategy"] == "full_rebuild"
    assert delta["summary"] == oracle["summary"]
    delta_records, delta_errors = nervous_events_adapters.read_records(delta_root)
    oracle_records, oracle_errors = nervous_events_adapters.read_records(oracle_root)
    assert delta_errors == oracle_errors == []
    assert [item["record"] for item in delta_records] == [
        item["record"] for item in oracle_records
    ]

    def forbidden_content_read(path: Path) -> bytes:
        raise AssertionError(f"unchanged event partition must not be read: {path}")

    fixed_point = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=delta_root,
        latest_path=delta_latest,
        episodes_from_events=episodes_builder,
        event_records_from_items=event_records,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:08:00+00:00",
        source_bytes_reader=forbidden_content_read,
    )
    assert fixed_point["ok"] is True
    assert fixed_point["incremental"]["strategy"] == "file_partition_delta"
    assert fixed_point["incremental"]["delta"] == {"source_events": 0, "episodes": 0}
    assert fixed_point["incremental"]["source_scan"]["partitions_reused_by_observation"] == 2
    assert fixed_point["incremental"]["source_scan"]["content_bytes_hashed"] == 0
    forced = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=delta_root,
        latest_path=delta_latest,
        episodes_from_events=episodes_builder,
        event_records_from_items=event_records,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:09:00+00:00",
        force_full=True,
    )
    assert forced["ok"] is True
    assert forced["incremental"]["strategy"] == "full_rebuild"
    assert "full_rebuild_forced" in forced["incremental"]["fallback_reasons"]


def test_incremental_episodes_forces_full_oracle_when_output_version_changes(tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    event_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    event_path.parent.mkdir(parents=True)
    event_path.write_text(json.dumps(_event()) + "\n", encoding="utf-8")
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"

    seed = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=lambda events: nervous_events.episodes_from_events(
            events,
            version="v1",
        ),
        event_records_from_items=nervous_events.event_records_from_items,
        schema_prefix="abyss_machine",
        version="v1",
        generated_at="2026-06-25T10:01:00+00:00",
    )
    assert seed["ok"] is True

    changed = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=lambda events: nervous_events.episodes_from_events(
            events,
            version="v2",
        ),
        event_records_from_items=nervous_events.event_records_from_items,
        schema_prefix="abyss_machine",
        version="v2",
        generated_at="2026-06-25T10:02:00+00:00",
    )

    assert changed["ok"] is True
    assert changed["incremental"]["strategy"] == "full_rebuild"
    assert "derivation_identity_mismatch" in changed["incremental"]["fallback_reasons"]
    records, errors = nervous_events_adapters.read_records(episodes_root)
    assert errors == []
    assert {item["record"]["version"] for item in records} == {"v2"}


def test_incremental_episodes_automatically_uses_full_oracle_when_group_ownership_crosses_partitions(
    tmp_path: Path,
) -> None:
    events_root = tmp_path / "events"
    old_path = events_root / "2026" / "06" / "2026-06-24.jsonl"
    current_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    old_path.parent.mkdir(parents=True)

    def event(event_id: str, observed_at: str, category: str) -> dict[str, object]:
        return {
            **_event(event_id),
            "generated_at": observed_at,
            "observed_at": observed_at,
            "category": category,
            "event_type": f"{category}.test",
            "title": f"{category} {event_id}",
        }

    old_path.write_text(
        json.dumps(event("evt-old", "2026-06-24T10:00:00+00:00", "storage")) + "\n",
        encoding="utf-8",
    )
    current_path.write_text(
        json.dumps(event("evt-current", "2026-06-25T10:00:00+00:00", "thermal")) + "\n",
        encoding="utf-8",
    )
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"
    seed = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=lambda events: nervous_events.episodes_from_events(
            events,
            version="test",
        ),
        event_records_from_items=nervous_events.event_records_from_items,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
    )
    assert seed["incremental"]["valid"] is True

    with current_path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(event("evt-cross-day", "2026-06-24T11:00:00+00:00", "storage"))
            + "\n"
        )
    result = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=lambda events: nervous_events.episodes_from_events(
            events,
            version="test",
        ),
        event_records_from_items=nervous_events.event_records_from_items,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:02:00+00:00",
    )

    assert result["ok"] is True
    assert result["incremental"]["strategy"] == "full_rebuild"
    assert result["incremental"]["partition_local"] is False
    assert result["incremental"]["valid"] is False
    assert "episode_group_ownership_conflict" in result["incremental"]["fallback_reasons"]
    records, errors = nervous_events_adapters.read_records(episodes_root)
    assert errors == []
    storage = [
        item["record"]
        for item in records
        if item["record"].get("day") == "2026-06-24"
        and item["record"].get("category") == "storage"
    ]
    assert len(storage) == 1
    assert storage[0]["event_count"] == 2


def test_incremental_episodes_refuses_source_race_before_derived_write(tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    event_path = events_root / "2026" / "06" / "2026-06-25.jsonl"
    event_path.parent.mkdir(parents=True)
    event_path.write_text(json.dumps(_event()) + "\n", encoding="utf-8")

    def forbidden_writer(*_args, **_kwargs):
        raise AssertionError("source race must refuse before an episode write")

    episodes_root = tmp_path / "episodes"
    result = nervous_events_adapters.build_episodes_incremental(
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=episodes_root / "latest.json",
        episodes_from_events=lambda events: nervous_events.episodes_from_events(
            events,
            version="test",
        ),
        event_records_from_items=nervous_events.event_records_from_items,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T10:01:00+00:00",
        write_latest_enabled=False,
        source_snapshot_validator=lambda *_args, **_kwargs: "events changed after planning",
        full_derived_writer=forbidden_writer,
        partition_derived_writer=forbidden_writer,
    )

    assert result["ok"] is False
    assert result["refused"] is True
    assert result["decision"] == "source_snapshot_changed"
    assert result["error"] == "events changed after planning"
    assert not nervous_events_adapters.jsonl_files(episodes_root)


def test_run_episodes_build_refreshes_events_inside_adapter(tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"
    writes: list[tuple[str, str]] = []
    refresh_calls: list[bool] = []
    refresh_document = {"ok": True, "summary": {"events": 1}}

    def records_reader(root: Path):
        if root == events_root:
            return [{"record": _event(), "path": "events.jsonl", "line": 1}], []
        raise AssertionError(root)

    def episodes_builder(events):
        assert [event["event_id"] for event in events] == ["evt-new"]
        return [_episode("eps-run")], {"input_events": 1, "episodes": 1}

    def events_builder(write_latest: bool = True):
        refresh_calls.append(write_latest)
        return refresh_document

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_events_adapters.run_episodes_build(
        privacy={"global_pause": False},
        events_root=events_root,
        episodes_root=episodes_root,
        latest_path=latest_path,
        episodes_from_events=episodes_builder,
        event_records_from_items=lambda items: [item["record"] for item in items],
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        events_builder=events_builder,
        refresh_events=True,
        records_reader=records_reader,
        latest_writer=latest_writer,
    )

    day = episodes_root / "2026" / "06" / "2026-06-25.jsonl"
    assert data["ok"] is True
    assert data["source"]["events_refresh"] == {"ok": True, "events": 1}
    assert _read_jsonl(day)[0]["episode_id"] == "eps-run"
    assert refresh_calls == [True]
    assert writes == [(str(latest_path), "abyss_machine_nervous_episodes_build_v1")]


def test_run_episodes_build_refuses_before_refresh_when_paused(tmp_path: Path) -> None:
    writes: list[tuple[str, str]] = []

    def fail_port(*_args, **_kwargs):
        raise AssertionError("global pause should refuse before refresh/build ports")

    def latest_writer(path: Path, data: dict[str, object], mode: int):
        writes.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_events_adapters.run_episodes_build(
        privacy={"global_pause": True},
        events_root=tmp_path / "events",
        episodes_root=tmp_path / "episodes",
        latest_path=tmp_path / "episodes" / "latest.json",
        episodes_from_events=fail_port,
        event_records_from_items=fail_port,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        events_builder=fail_port,
        records_reader=fail_port,
        derived_writer=fail_port,
        latest_writer=latest_writer,
    )

    assert data == {
        "schema": "abyss_machine_nervous_episodes_build_v1",
        "version": "test",
        "generated_at": GENERATED_AT,
        "ok": False,
        "refused": True,
        "error": "global_pause is active; episode build did not touch derived episode files",
    }
    assert writes == [(str(tmp_path / "episodes" / "latest.json"), "abyss_machine_nervous_episodes_build_v1")]


def test_cli_events_build_binds_file_work_to_adapter(monkeypatch, tmp_path: Path) -> None:
    facts_root = tmp_path / "facts"
    events_root = tmp_path / "events"
    latest_path = events_root / "latest.json"
    captured: dict[str, object] = {}
    privacy_doc = {"global_pause": False}
    sources_doc = {
        "safe_now": {"abyss_machine_facts": {"enabled": True, "allowed": True}},
        "deferred_until_privacy_controls": {},
    }
    thresholds = {"watch_c": 105.0, "hot_c": 106.0}

    def fake_run_events_build(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(cli, "NERVOUS_FACTS_ROOT", facts_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EVENTS_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy_doc)
    monkeypatch.setattr(cli, "nervous_effective_sources", lambda write_latest=False: sources_doc)
    monkeypatch.setattr(cli, "nervous_thermal_event_thresholds", lambda: thresholds)
    monkeypatch.setattr(cli.nervous_events_adapters, "run_events_build", fake_run_events_build)

    data = cli.nervous_events_build(write_latest=False)

    assert data == {"ok": True, "from_adapter": True}
    assert captured["privacy"] is privacy_doc
    assert captured["facts_root"] == facts_root
    assert captured["events_root"] == events_root
    assert captured["latest_path"] == latest_path
    assert captured["events_from_fact_records"] is cli.nervous_events_from_fact_records
    assert callable(captured["events_from_fact_records_with_state"])
    assert captured["derivation_identity"] == nervous_events.event_derivation_identity(
        thresholds=thresholds,
        deferred_source_ids=set(),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
    )
    assert captured["write_latest_enabled"] is False
    assert captured["latest_writer"] is cli.safe_atomic_write_json
    assert captured["force_full"] is False


def test_cli_episodes_build_binds_refresh_port_to_adapter(monkeypatch, tmp_path: Path) -> None:
    events_root = tmp_path / "events"
    episodes_root = tmp_path / "episodes"
    latest_path = episodes_root / "latest.json"
    captured: dict[str, object] = {}
    privacy_doc = {"global_pause": False}

    def fake_run_episodes_build(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "from_adapter": True}

    monkeypatch.setattr(cli, "NERVOUS_EVENTS_ROOT", events_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_ROOT", episodes_root)
    monkeypatch.setattr(cli, "NERVOUS_EPISODES_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: privacy_doc)
    monkeypatch.setattr(cli.nervous_events_adapters, "run_episodes_build", fake_run_episodes_build)

    data = cli.nervous_episodes_build(write_latest=True, refresh_events=True)

    assert data == {"ok": True, "from_adapter": True}
    assert captured["privacy"] is privacy_doc
    assert captured["events_root"] == events_root
    assert captured["episodes_root"] == episodes_root
    assert captured["latest_path"] == latest_path
    assert captured["episodes_from_events"] is cli.nervous_episodes_from_events
    assert captured["events_builder"] is cli.nervous_events_build
    assert captured["refresh_events"] is True
    assert captured["incremental_enabled"] is True
    assert captured["force_full"] is False
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
