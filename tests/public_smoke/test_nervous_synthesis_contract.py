from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine.nervous_synthesis import (
    build_candidate,
    build_candidate_from_items,
    candidate_refused_result,
    eval_refused_result,
    eval_run_execution_plan,
    eval_run_document,
    eval_validate_document,
    markdown,
    paths_document,
    records_from_items,
    select_events_for_episode_ids,
    select_period_episodes,
    validate_records,
    with_write_results,
    write_paths,
)


def test_nervous_synthesis_candidate_contract_is_deterministic_and_public_safe() -> None:
    episodes = [
        {
            "episode_id": "eps-1",
            "start_at": "2026-06-25T09:10:00+00:00",
            "end_at": "2026-06-25T09:20:00+00:00",
            "category": "resource",
            "severity": "warning",
            "title": "Resource pressure",
            "event_count": 2,
            "event_ids": ["evt-1", "evt-2"],
        },
        {
            "episode_id": "eps-2",
            "start_at": "2026-06-25T10:05:00+00:00",
            "end_at": "2026-06-25T10:08:00+00:00",
            "category": "storage",
            "severity": "critical",
            "title": "Storage pressure",
            "event_count": 1,
            "event_ids": ["evt-3"],
        },
    ]
    events = [
        {"event_id": "evt-1", "observed_at": "2026-06-25T09:11:00+00:00", "event_type": "psi", "category": "resource", "severity": "warning", "title": "PSI"},
        {"event_id": "evt-2", "observed_at": "2026-06-25T09:12:00+00:00", "event_type": "swap", "category": "resource", "severity": "notice", "title": "Swap"},
        {"event_id": "evt-3", "observed_at": "2026-06-25T10:07:00+00:00", "event_type": "disk", "category": "storage", "severity": "critical", "title": "Disk"},
    ]
    selected, parse_errors, period = select_period_episodes(
        episodes,
        [],
        scope="daily",
        now=dt.datetime.fromisoformat("2026-06-25T12:00:00+00:00"),
    )
    selected_events = select_events_for_episode_ids(episodes, events, ["eps-1", "eps-2"])

    assert selected == episodes
    assert parse_errors == []
    assert period == {"scope": "daily", "date": "2026-06-25", "hour": None}
    assert [event["event_id"] for event in selected_events] == ["evt-1", "evt-2", "evt-3"]

    first = build_candidate(
        scope="daily",
        period=period,
        episodes=selected,
        events=selected_events,
        parse_errors=[],
        paths={"latest": "/state/nervous/synthesis/latest.json"},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    second = build_candidate(
        scope="daily",
        period=period,
        episodes=selected,
        events=selected_events,
        parse_errors=[],
        paths={"latest": "/state/nervous/synthesis/latest.json"},
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert first["candidate_id"] == second["candidate_id"]
    assert first["schema"] == "abyss_machine_nervous_synthesis_candidate_v1"
    assert first["summary"]["episodes"] == 2
    assert first["summary"]["events"] == 3
    assert first["summary"]["highest_severity"] == "critical"
    assert first["policy"] == {
        "candidate_only": True,
        "model_used": False,
        "raw_private_content": False,
        "automatic_action": False,
        "automatic_repo_write": False,
    }
    assert "Candidate only. No model call." in markdown(first)


def test_nervous_synthesis_validate_warns_for_stale_missing_latest_refs() -> None:
    latest = {
        "schema": "abyss_machine_nervous_synthesis_candidate_v1",
        "candidate_id": "syn-fixture",
        "generated_at": "2026-06-25T09:00:00+00:00",
        "scope": "daily",
        "period": {"scope": "daily", "date": "2026-06-25", "hour": None},
        "summary": {},
        "claims": [],
        "policy": {"raw_private_content": False, "automatic_repo_write": False},
        "evidence": {"episodes": [{"episode_id": "missing", "event_ids": ["evt-missing"]}]},
    }
    data = validate_records(
        latest=latest,
        latest_error=None,
        episodes_latest={"generated_at": "2026-06-25T10:00:00+00:00"},
        candidate_items=[{"record": latest, "path": "fixture.jsonl", "line": 1}],
        candidate_parse_errors=[],
        episode_items=[{"record": {"episode_id": "eps-current"}}],
        event_items=[{"record": {"event_id": "evt-current"}}],
        latest_path="/state/nervous/synthesis/latest.json",
        validate_latest_path="/state/nervous/synthesis/validate/latest.json",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data["ok"] is True
    assert data["summary"]["warnings"] == 1
    assert any(check["key"] == "evidence_refs_stale" and check["level"] == "warn" for check in data["checks"])


def test_nervous_synthesis_build_orchestration_contract_is_module_owned() -> None:
    episodes = [
        {
            "episode_id": "eps-1",
            "start_at": "2026-06-25T09:10:00+00:00",
            "end_at": "2026-06-25T09:20:00+00:00",
            "category": "resource",
            "severity": "warning",
            "title": "Resource pressure",
            "event_count": 2,
            "event_ids": ["evt-1", "evt-2"],
        },
        {
            "episode_id": "eps-old",
            "start_at": "2026-06-24T09:10:00+00:00",
            "end_at": "2026-06-24T09:20:00+00:00",
            "category": "storage",
            "severity": "critical",
            "title": "Old storage pressure",
            "event_count": 1,
            "event_ids": ["evt-old"],
        },
    ]
    events = [
        {"event_id": "evt-1", "observed_at": "2026-06-25T09:11:00+00:00", "event_type": "psi", "category": "resource", "severity": "warning", "title": "PSI"},
        {"event_id": "evt-2", "observed_at": "2026-06-25T09:12:00+00:00", "event_type": "swap", "category": "resource", "severity": "notice", "title": "Swap"},
        {"event_id": "evt-old", "observed_at": "2026-06-24T09:12:00+00:00", "event_type": "disk", "category": "storage", "severity": "critical", "title": "Disk"},
    ]
    paths = paths_document(
        latest_path="/state/nervous/synthesis/latest.json",
        hourly_glob="/state/nervous/synthesis/hourly/YYYY/MM/YYYY-MM-DD.jsonl",
        daily_jsonl_glob="/state/nervous/synthesis/daily/YYYY/MM/YYYY-MM-DD.jsonl",
        daily_markdown_glob="/state/nervous/synthesis/daily/YYYY/MM/YYYY-MM-DD.md",
    )

    candidate = build_candidate_from_items(
        episode_items=[{"record": item} for item in episodes],
        episode_parse_errors=[],
        event_items=[{"record": item} for item in events],
        scope="daily",
        date_value="2026-06-25",
        paths=paths,
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert records_from_items([{"record": episodes[0]}, {"record": "bad"}]) == [episodes[0]]
    assert candidate["summary"]["episodes"] == 1
    assert candidate["summary"]["events"] == 2
    assert candidate["period"] == {"scope": "daily", "date": "2026-06-25", "hour": None}
    assert candidate["paths"] == paths
    assert candidate["policy"]["candidate_only"] is True

    daily_write_paths = write_paths(
        "daily",
        candidate["period"],
        hourly_root=Path("/state/nervous/synthesis/hourly"),
        daily_root=Path("/state/nervous/synthesis/daily"),
    )
    written = with_write_results(
        candidate,
        write_paths=daily_write_paths,
        write_errors=[{"path": "/state/nervous/synthesis/latest.json", "error": "denied"}],
    )

    assert str(daily_write_paths["period_jsonl"]) == "/state/nervous/synthesis/daily/2026/06/2026-06-25.jsonl"
    assert str(daily_write_paths["daily_markdown"]) == "/state/nervous/synthesis/daily/2026/06/2026-06-25.md"
    assert written["ok"] is False
    assert written["paths"]["period_jsonl"].endswith("2026-06-25.jsonl")
    assert written["write_errors"][0]["error"] == "denied"

    refused = candidate_refused_result(version="test", generated_at="2026-06-25T12:00:00+00:00")
    assert refused["schema"] == "abyss_machine_nervous_synthesis_candidate_v1"
    assert refused["refused"] is True
    assert refused["ok"] is False


def test_nervous_eval_run_and_validate_documents_are_module_owned() -> None:
    events_validation = {"ok": True, "summary": {"events": 2}}
    episodes_validation = {"ok": True, "summary": {"episodes": 1}}
    index_validation = {"ok": True, "summary": {"chunks": 3}}
    recall = {"ok": True, "pack_id": "pack-1", "summary": {"evidence_items": 4}}
    synthesis = {"ok": True, "candidate_id": "syn-1", "scope": "daily", "summary": {"episodes": 1}}
    synthesis_validation = {"ok": True, "summary": {"checks": 4}}
    plan = eval_run_execution_plan()
    data = eval_run_document(
        events_validation=events_validation,
        episodes_validation=episodes_validation,
        index_validation=index_validation,
        recall=recall,
        synthesis=synthesis,
        synthesis_validation=synthesis_validation,
        latest_path="/state/nervous/evals/latest.json",
        daily_glob="/state/nervous/evals/YYYY/MM/YYYY-MM-DD.jsonl",
        recall_latest_path="/state/nervous/retrieval/latest.json",
        synthesis_latest_path="/state/nervous/synthesis/latest.json",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    validate = eval_validate_document(
        latest=data,
        latest_error=None,
        latest_path="/state/nervous/evals/latest.json",
        validate_latest_path="/state/nervous/evals/validate/latest.json",
        version="test",
        generated_at="2026-06-25T12:01:00+00:00",
    )
    failed_validate = eval_validate_document(
        latest=None,
        latest_error="missing",
        latest_path="/state/nervous/evals/latest.json",
        validate_latest_path="/state/nervous/evals/validate/latest.json",
        version="test",
        generated_at="2026-06-25T12:01:00+00:00",
    )
    refused = eval_refused_result(version="test", generated_at="2026-06-25T12:00:00+00:00")

    assert plan == {
        "schema": "abyss_machine_nervous_eval_run_execution_plan_v1",
        "step_order": [
            "events_validation",
            "episodes_validation",
            "index_validation",
            "recall",
            "synthesis",
            "synthesis_validation",
        ],
        "events_validation": {"adapter": "nervous_events_validate", "write_latest": False},
        "episodes_validation": {"adapter": "nervous_episodes_validate", "write_latest": False},
        "index_validation": {"adapter": "nervous_index_validate", "write_latest": False},
        "recall": {
            "adapter": "nervous_recall_pack",
            "query": "thermal storage power nervous",
            "limit": 16,
            "write_latest": True,
        },
        "synthesis": {
            "adapter": "nervous_synthesis_build",
            "scope": "daily",
            "write_latest": True,
        },
        "synthesis_validation": {"adapter": "nervous_synthesis_validate", "write_latest": False},
        "policy": {
            "model_used": False,
            "local_only": True,
            "live_execution_at_cli_edge": True,
            "automatic_repo_write": False,
        },
    }
    assert data["schema"] == "abyss_machine_nervous_eval_v1"
    assert data["ok"] is True
    assert data["summary"] == {"status": "ok", "fails": 0, "warnings": 0, "checks": 6}
    assert [item["key"] for item in data["checks"]] == [
        "events_validate",
        "episodes_validate",
        "index_validate",
        "recall_pack",
        "synthesis_build",
        "synthesis_validate",
    ]
    assert data["artifacts"]["recall_pack"] == {
        "ok": True,
        "pack_id": "pack-1",
        "evidence_items": 4,
        "latest": "/state/nervous/retrieval/latest.json",
    }
    assert data["artifacts"]["synthesis"]["latest"] == "/state/nervous/synthesis/latest.json"
    assert data["policy"] == {"model_used": False, "local_only": True, "repo_mutation": False}
    assert validate["schema"] == "abyss_machine_nervous_eval_validate_v1"
    assert validate["ok"] is True
    assert validate["summary"]["checks"] == 4
    assert failed_validate["ok"] is False
    assert failed_validate["checks"][0]["details"] == {"path": "/state/nervous/evals/latest.json", "error": "missing"}
    assert refused == {
        "schema": "abyss_machine_nervous_eval_v1",
        "version": "test",
        "generated_at": "2026-06-25T12:00:00+00:00",
        "ok": False,
        "refused": True,
        "error": "global_pause is active; eval run did not touch recall, synthesis, or eval files",
    }


def test_nervous_eval_run_document_reports_failed_dependencies() -> None:
    data = eval_run_document(
        events_validation={"ok": False, "summary": {"fails": 1}},
        episodes_validation={"ok": True, "summary": {}},
        index_validation={"ok": False, "summary": {"fails": 1}},
        recall={"ok": True, "pack_id": "pack-empty", "summary": {"evidence_items": 0}},
        synthesis={"ok": False, "candidate_id": "syn-failed", "scope": "daily", "summary": {}},
        synthesis_validation={"ok": False, "summary": {"fails": 1}},
        latest_path="/state/nervous/evals/latest.json",
        daily_glob="/state/nervous/evals/YYYY/MM/YYYY-MM-DD.jsonl",
        recall_latest_path="/state/nervous/retrieval/latest.json",
        synthesis_latest_path="/state/nervous/synthesis/latest.json",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    fail_keys = [item["key"] for item in data["checks"] if item["level"] == "fail"]
    assert data["ok"] is False
    assert data["summary"]["status"] == "fail"
    assert fail_keys == ["events_validate", "index_validate", "recall_pack", "synthesis_build", "synthesis_validate"]


def test_cli_synthesis_build_uses_fixture_records_without_host_state(monkeypatch) -> None:
    episode = {
        "episode_id": "eps-cli",
        "start_at": "2026-06-25T09:10:00+00:00",
        "end_at": "2026-06-25T09:20:00+00:00",
        "category": "resource",
        "severity": "warning",
        "title": "Resource pressure",
        "event_count": 1,
        "event_ids": ["evt-cli"],
    }
    event = {
        "event_id": "evt-cli",
        "observed_at": "2026-06-25T09:11:00+00:00",
        "event_type": "psi",
        "category": "resource",
        "severity": "warning",
        "title": "PSI",
    }

    def fake_records_from_root(root):
        if root == cli.NERVOUS_EPISODES_ROOT:
            return [{"record": episode}], []
        if root == cli.NERVOUS_EVENTS_ROOT:
            return [{"record": event}], []
        raise AssertionError(f"unexpected root {root}")

    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_records_from_jsonl_root", fake_records_from_root)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")

    data = cli.nervous_synthesis_build(scope="daily", date_value="2026-06-25", write_latest=False)

    assert data["ok"] is True
    assert data["schema"] == "abyss_machine_nervous_synthesis_candidate_v1"
    assert data["summary"]["episodes"] == 1
    assert data["summary"]["events"] == 1
    assert data["evidence"]["episodes"][0]["episode_id"] == "eps-cli"


def test_cli_nervous_eval_run_delegates_document_shape_to_module(monkeypatch) -> None:
    events_validation = {"ok": True, "summary": {"events": 2}}
    episodes_validation = {"ok": True, "summary": {"episodes": 1}}
    index_validation = {"ok": True, "summary": {"chunks": 3}}
    recall = {"ok": True, "pack_id": "pack-cli", "summary": {"evidence_items": 2}}
    synthesis = {"ok": True, "candidate_id": "syn-cli", "scope": "daily", "summary": {"episodes": 1}}
    synthesis_validation = {"ok": True, "summary": {"checks": 4}}
    calls: list[tuple[object, ...]] = []

    def fake_events_validate(write_latest=False):
        calls.append(("events_validation", write_latest))
        return events_validation

    def fake_episodes_validate(write_latest=False):
        calls.append(("episodes_validation", write_latest))
        return episodes_validation

    def fake_index_validate(write_latest=False):
        calls.append(("index_validation", write_latest))
        return index_validation

    def fake_recall_pack(query, limit, write_latest=True):
        calls.append(("recall", query, limit, write_latest))
        return recall

    def fake_synthesis_build(scope="daily", write_latest=True):
        calls.append(("synthesis", scope, write_latest))
        return synthesis

    def fake_synthesis_validate(write_latest=False):
        calls.append(("synthesis_validation", write_latest))
        return synthesis_validation

    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_events_validate", fake_events_validate)
    monkeypatch.setattr(cli, "nervous_episodes_validate", fake_episodes_validate)
    monkeypatch.setattr(cli, "nervous_index_validate", fake_index_validate)
    monkeypatch.setattr(cli, "nervous_recall_pack", fake_recall_pack)
    monkeypatch.setattr(cli, "nervous_synthesis_build", fake_synthesis_build)
    monkeypatch.setattr(cli, "nervous_synthesis_validate", fake_synthesis_validate)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")

    data = cli.nervous_eval_run(write_latest=False)
    expected = eval_run_document(
        events_validation=events_validation,
        episodes_validation=episodes_validation,
        index_validation=index_validation,
        recall=recall,
        synthesis=synthesis,
        synthesis_validation=synthesis_validation,
        latest_path=str(cli.NERVOUS_EVALS_LATEST_PATH),
        daily_glob=str(cli.NERVOUS_EVALS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        recall_latest_path=str(cli.NERVOUS_RETRIEVAL_LATEST_PATH),
        synthesis_latest_path=str(cli.NERVOUS_SYNTHESIS_LATEST_PATH),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert data == expected
    assert calls == [
        ("events_validation", False),
        ("episodes_validation", False),
        ("index_validation", False),
        ("recall", "thermal storage power nervous", 16, True),
        ("synthesis", "daily", True),
        ("synthesis_validation", False),
    ]


def test_cli_nervous_eval_run_refuses_before_live_work_when_paused(monkeypatch) -> None:
    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": True})
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:00:00+00:00")
    monkeypatch.setattr(
        cli,
        "nervous_events_validate",
        lambda write_latest=False: (_ for _ in ()).throw(AssertionError("pause should refuse before eval dependencies")),
    )

    assert cli.nervous_eval_run(write_latest=False) == eval_refused_result(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:00:00+00:00",
    )


def test_cli_nervous_eval_validate_delegates_document_shape_to_module(monkeypatch) -> None:
    latest = {
        "schema": "abyss_machine_nervous_eval_v1",
        "ok": True,
        "summary": {"status": "ok"},
        "policy": {"repo_mutation": False},
    }

    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-25T12:01:00+00:00")

    assert cli.nervous_eval_validate(write_latest=False) == eval_validate_document(
        latest=latest,
        latest_error=None,
        latest_path=str(cli.NERVOUS_EVALS_LATEST_PATH),
        validate_latest_path=str(cli.NERVOUS_EVALS_VALIDATE_LATEST_PATH),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-25T12:01:00+00:00",
    )
