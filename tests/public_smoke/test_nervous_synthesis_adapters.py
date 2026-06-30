from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_synthesis_adapters as adapters


def _jsonl_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_replace_period_record_preserves_other_periods_and_replaces_same_period(tmp_path: Path) -> None:
    path = tmp_path / "synthesis" / "daily" / "2026" / "06" / "2026-06-25.jsonl"
    path.parent.mkdir(parents=True)
    old_same = {"candidate_id": "old", "scope": "daily", "period": {"scope": "daily", "date": "2026-06-25", "hour": None}}
    other = {"candidate_id": "other", "scope": "daily", "period": {"scope": "daily", "date": "2026-06-24", "hour": None}}
    path.write_text(json.dumps(old_same) + "\n" + json.dumps(other) + "\n", encoding="utf-8")

    new = {"candidate_id": "new", "scope": "daily", "period": {"scope": "daily", "date": "2026-06-25", "hour": None}}

    assert adapters.replace_period_record(path, new, group="missing-test-group") is None

    records = _jsonl_records(path)
    assert records == [other, new]


def test_build_synthesis_reads_records_and_writes_latest_period_and_markdown(tmp_path: Path) -> None:
    roots = {
        "episodes": tmp_path / "episodes",
        "events": tmp_path / "events",
    }
    latest_path = tmp_path / "synthesis" / "latest.json"
    hourly_root = tmp_path / "synthesis" / "hourly"
    daily_root = tmp_path / "synthesis" / "daily"
    episode = {
        "episode_id": "eps-1",
        "start_at": "2026-06-25T09:10:00+00:00",
        "end_at": "2026-06-25T09:20:00+00:00",
        "category": "resource",
        "severity": "warning",
        "title": "Resource pressure",
        "event_count": 1,
        "event_ids": ["evt-1"],
    }
    event = {
        "event_id": "evt-1",
        "observed_at": "2026-06-25T09:11:00+00:00",
        "event_type": "psi",
        "category": "resource",
        "severity": "warning",
        "title": "PSI",
    }
    latest_writes: list[tuple[Path, str]] = []

    def records_reader(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if root == roots["episodes"]:
            return [{"record": episode}], []
        if root == roots["events"]:
            return [{"record": event}], []
        raise AssertionError(f"unexpected root {root}")

    def latest_writer(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        latest_writes.append((path, data["candidate_id"]))
        return None

    data = adapters.build_synthesis(
        episodes_root=roots["episodes"],
        events_root=roots["events"],
        latest_path=latest_path,
        hourly_root=hourly_root,
        daily_root=daily_root,
        scope="daily",
        date_value="2026-06-25",
        hour=None,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        records_reader=records_reader,
        latest_writer=latest_writer,
    )

    period_jsonl = daily_root / "2026" / "06" / "2026-06-25.jsonl"
    daily_markdown = daily_root / "2026" / "06" / "2026-06-25.md"
    period_records = _jsonl_records(period_jsonl)
    assert data["ok"] is True
    assert data["summary"]["episodes"] == 1
    assert data["summary"]["events"] == 1
    assert data["summary"]["highest_severity"] == "warning"
    assert data["summary"]["by_category"] == {"resource": 1}
    assert data["summary"]["by_severity"] == {"warning": 1}
    assert data["summary"]["event_types"] == {"psi": 1}
    assert data["summary"]["parse_errors"] == 0
    assert len(data["claims"]) == 2
    assert latest_writes == [(latest_path, data["candidate_id"])]
    assert len(period_records) == 1
    assert period_records[0]["candidate_id"] == data["candidate_id"]
    assert period_records[0]["paths"]["latest"] == str(latest_path)
    assert "Abyss Nervous daily Synthesis 2026-06-25" in daily_markdown.read_text(encoding="utf-8")


def test_validate_synthesis_uses_fakeable_latest_and_record_ports(tmp_path: Path) -> None:
    latest_path = tmp_path / "synthesis" / "latest.json"
    episodes_latest_path = tmp_path / "episodes" / "latest.json"
    validate_latest_path = tmp_path / "synthesis" / "validate" / "latest.json"
    hourly_root = tmp_path / "synthesis" / "hourly"
    daily_root = tmp_path / "synthesis" / "daily"
    episodes_root = tmp_path / "episodes"
    events_root = tmp_path / "events"
    episode = {"episode_id": "eps-1", "event_ids": ["evt-1"]}
    event = {"event_id": "evt-1"}
    candidate = {
        "schema": "abyss_machine_nervous_synthesis_candidate_v1",
        "candidate_id": "syn-1",
        "generated_at": "2026-06-25T12:00:00+00:00",
        "scope": "daily",
        "period": {"scope": "daily", "date": "2026-06-25", "hour": None},
        "summary": {},
        "evidence": {"episodes": [{"episode_id": "eps-1", "event_ids": ["evt-1"]}]},
        "claims": [],
        "policy": {"raw_private_content": False, "automatic_repo_write": False},
    }
    writes: list[Path] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        if path == latest_path:
            return candidate, None
        if path == episodes_latest_path:
            return {"generated_at": "2026-06-25T11:00:00+00:00"}, None
        raise AssertionError(f"unexpected latest path {path}")

    def records_reader(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if root in {hourly_root, daily_root}:
            return ([{"record": candidate, "path": str(root / "file.jsonl"), "line": 1}], []) if root == daily_root else ([], [])
        if root == episodes_root:
            return [{"record": episode}], []
        if root == events_root:
            return [{"record": event}], []
        raise AssertionError(f"unexpected root {root}")

    def latest_writer(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        writes.append(path)
        return None

    data = adapters.validate_synthesis(
        latest_path=latest_path,
        episodes_latest_path=episodes_latest_path,
        validate_latest_path=validate_latest_path,
        hourly_root=hourly_root,
        daily_root=daily_root,
        episodes_root=episodes_root,
        events_root=events_root,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:01:00+00:00",
        records_reader=records_reader,
        latest_reader=latest_reader,
        latest_writer=latest_writer,
    )

    assert data["ok"] is True
    assert data["summary"]["checks"] == 5
    assert writes == [validate_latest_path]


def test_eval_run_and_validate_write_routes_are_fakeable(tmp_path: Path) -> None:
    latest_path = tmp_path / "evals" / "latest.json"
    daily_root = tmp_path / "evals" / "daily"
    validate_latest_path = tmp_path / "evals" / "validate" / "latest.json"
    latest_history_writes: list[tuple[Path, Path, str]] = []
    latest_writes: list[Path] = []

    def latest_history_writer(data: dict[str, Any], latest: Path, daily: Path) -> list[dict[str, Any]]:
        latest_history_writes.append((latest, daily, data["schema"]))
        return []

    data = adapters.build_eval_run(
        events_validation={"ok": True, "summary": {"events": 1}},
        episodes_validation={"ok": True, "summary": {"episodes": 1}},
        index_validation={"ok": True, "summary": {"chunks": 1}},
        recall={"ok": True, "pack_id": "pack-1", "summary": {"evidence_items": 1}},
        synthesis={"ok": True, "candidate_id": "syn-1", "scope": "daily", "summary": {"episodes": 1}},
        synthesis_validation={"ok": True, "summary": {"checks": 5}},
        latest_path=latest_path,
        daily_root=daily_root,
        recall_latest_path=tmp_path / "retrieval" / "latest.json",
        synthesis_latest_path=tmp_path / "synthesis" / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
        latest_history_writer=latest_history_writer,
    )

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        assert path == latest_path
        return data, None

    def latest_writer(path: Path, payload: dict[str, Any], mode: int) -> dict[str, Any] | None:
        latest_writes.append(path)
        return None

    validate = adapters.validate_eval(
        latest_path=latest_path,
        validate_latest_path=validate_latest_path,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:01:00+00:00",
        latest_reader=latest_reader,
        latest_writer=latest_writer,
    )

    assert data["schema"] == "abyss_machine_nervous_eval_v1"
    assert data["ok"] is True
    assert latest_history_writes == [(latest_path, daily_root, "abyss_machine_nervous_eval_v1")]
    assert validate["schema"] == "abyss_machine_nervous_eval_validate_v1"
    assert validate["ok"] is True
    assert latest_writes == [validate_latest_path]


def test_cli_synthesis_and_eval_validate_bind_adapter_ports(monkeypatch) -> None:
    build_calls: list[dict[str, Any]] = []
    validate_calls: list[dict[str, Any]] = []
    eval_validate_calls: list[dict[str, Any]] = []

    def fake_build_synthesis(**kwargs):
        build_calls.append(kwargs)
        return {"ok": True, "schema": "fixture_synthesis"}

    def fake_validate_synthesis(**kwargs):
        validate_calls.append(kwargs)
        return {"ok": True, "schema": "fixture_synthesis_validate"}

    def fake_validate_eval(**kwargs):
        eval_validate_calls.append(kwargs)
        return {"ok": True, "schema": "fixture_eval_validate"}

    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli.nervous_synthesis_adapters, "build_synthesis", fake_build_synthesis)
    monkeypatch.setattr(cli.nervous_synthesis_adapters, "validate_synthesis", fake_validate_synthesis)
    monkeypatch.setattr(cli.nervous_synthesis_adapters, "validate_eval", fake_validate_eval)

    assert cli.nervous_synthesis_build(scope="hourly", date_value="2026-06-25", hour=9, write_latest=False)["schema"] == "fixture_synthesis"
    assert cli.nervous_synthesis_validate(write_latest=False)["schema"] == "fixture_synthesis_validate"
    assert cli.nervous_eval_validate(write_latest=False)["schema"] == "fixture_eval_validate"

    assert build_calls[0]["episodes_root"] == cli.NERVOUS_EPISODES_ROOT
    assert build_calls[0]["events_root"] == cli.NERVOUS_EVENTS_ROOT
    assert build_calls[0]["write_latest_enabled"] is False
    assert build_calls[0]["records_reader"] is cli.nervous_records_from_jsonl_root
    assert build_calls[0]["latest_writer"] is cli.safe_atomic_write_json
    assert validate_calls[0]["latest_reader"] is cli.load_json_document
    assert validate_calls[0]["latest_writer"] is cli.safe_atomic_write_json
    assert eval_validate_calls[0]["latest_reader"] is cli.load_json_document


def test_cli_eval_run_keeps_dependency_orchestration_and_routes_persistence_to_adapter(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    adapter_calls: list[dict[str, Any]] = []
    docs = {
        "events": {"ok": True, "summary": {"events": 2}},
        "episodes": {"ok": True, "summary": {"episodes": 1}},
        "index": {"ok": True, "summary": {"chunks": 3}},
        "recall": {"ok": True, "pack_id": "pack-cli", "summary": {"evidence_items": 2}},
        "synthesis": {"ok": True, "candidate_id": "syn-cli", "scope": "daily", "summary": {"episodes": 1}},
        "synthesis_validate": {"ok": True, "summary": {"checks": 4}},
    }

    def fake_build_eval_run(**kwargs):
        adapter_calls.append(kwargs)
        return {"ok": True, "schema": "fixture_eval"}

    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_events_validate", lambda write_latest=False: calls.append(("events", write_latest)) or docs["events"])
    monkeypatch.setattr(cli, "nervous_episodes_validate", lambda write_latest=False: calls.append(("episodes", write_latest)) or docs["episodes"])
    monkeypatch.setattr(cli, "nervous_index_validate", lambda write_latest=False: calls.append(("index", write_latest)) or docs["index"])
    monkeypatch.setattr(cli, "nervous_recall_pack", lambda query, limit, write_latest=True: calls.append(("recall", query, limit, write_latest)) or docs["recall"])
    monkeypatch.setattr(cli, "nervous_synthesis_build", lambda scope="daily", write_latest=True: calls.append(("synthesis", scope, write_latest)) or docs["synthesis"])
    monkeypatch.setattr(cli, "nervous_synthesis_validate", lambda write_latest=False: calls.append(("synthesis_validate", write_latest)) or docs["synthesis_validate"])
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(cli.nervous_synthesis_adapters, "build_eval_run", fake_build_eval_run)

    assert cli.nervous_eval_run(write_latest=False)["schema"] == "fixture_eval"

    assert calls == [
        ("events", False),
        ("episodes", False),
        ("index", False),
        ("recall", "thermal storage power nervous", 16, True),
        ("synthesis", "daily", True),
        ("synthesis_validate", False),
    ]
    assert adapter_calls[0]["events_validation"] == docs["events"]
    assert adapter_calls[0]["latest_path"] == cli.NERVOUS_EVALS_LATEST_PATH
    assert adapter_calls[0]["write_latest_enabled"] is False
