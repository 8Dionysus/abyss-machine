from contextlib import contextmanager
from copy import deepcopy

import pytest

from abyss_machine import cli


@pytest.fixture
def scheduled_refresh(monkeypatch):
    document = {
        "ok": True, "generated_at": "2026-09-05T12:00:00Z",
        "last_deep_at": "2026-09-05T11:00:00Z", "candidates": [],
        "coverage": {"runtime_errors": []},
    }
    calls = []
    locked = False

    @contextmanager
    def lock():
        nonlocal locked
        assert not locked
        locked = True
        try:
            yield
        finally:
            locked = False

    def read(path):
        assert locked
        return deepcopy(document), None

    def refresh(**kwargs):
        assert locked
        calls.append(kwargs)
        return {"ok": False, "partial": True, "new_results": 12}

    monkeypatch.setattr(cli, "storage_candidates_refresh_lock", lock)
    monkeypatch.setattr(cli, "load_json_document", read)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-09-05T12:00:00Z")
    monkeypatch.setattr(cli, "_storage_candidates_refresh_unlocked", refresh)
    return document, calls


def test_fresh_complete_snapshot_is_not_rewritten(scheduled_refresh):
    document, calls = scheduled_refresh
    before = deepcopy(document)
    result = cli.storage_candidates_refresh_if_due()
    assert result["ok"] is True and result["mutates"] is False
    assert result["refresh_result"]["status"] == "not_due"
    assert calls == [] and document == before


@pytest.mark.parametrize("change", [
    {"partial": True},
    {"deep_progress": {"status": "partial", "cursor": 4096}},
    {"coverage": {"runtime_errors": [{"surface": "process_refs"}]}},
    {"last_deep_at": "2026-09-04T12:00:00Z"},
    {"last_deep_at": "2026-09-06T12:00:00Z"},
    {"last_deep_at": None},
    {"ok": False},
])
def test_partial_invalid_or_old_snapshot_continues_under_lock(scheduled_refresh, change):
    document, calls = scheduled_refresh
    document.update(change)
    result = cli.storage_candidates_refresh_if_due()
    assert result["partial"] is True and result["ok"] is False
    assert calls == [{"deep": True, "write_latest": True}]


def test_completed_blocked_sweep_keeps_stale_evidence_without_repeating_full_scan(scheduled_refresh):
    document, calls = scheduled_refresh
    document.update({
        "ok": False,
        "partial": True,
        "last_deep_at": "2026-09-04T12:00:00Z",
        "freshness": {"status": "stale", "complete": False, "partial": True},
        "coverage": {"partial": True, "complete": False, "runtime_error_count": 1},
        "deep_progress": {
            "status": "complete_with_errors",
            "full_pass_finished": True,
            "continuation_required": False,
            "total": 40000,
            "cursor": 17,
            "last_full_attempt_at": "2026-09-05T11:00:00Z",
        },
    })

    result = cli.storage_candidates_refresh_if_due()

    assert result["ok"] is False
    assert result["partial"] is True and result["complete"] is False
    assert result["freshness"]["status"] == "stale"
    assert result["refresh_result"]["status"] == "complete_with_errors_not_due"
    assert result["deep_progress"]["continuation_required"] is False
    assert result["mutates"] is False
    assert calls == []


def test_completed_blocked_sweep_is_retried_after_daily_attempt_boundary(scheduled_refresh, monkeypatch):
    document, calls = scheduled_refresh
    document.update({
        "ok": False,
        "partial": True,
        "deep_progress": {
            "status": "complete_with_errors",
            "full_pass_finished": True,
            "last_full_attempt_at": "2026-09-04T11:00:00Z",
        },
    })
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-09-05T12:00:00Z")

    result = cli.storage_candidates_refresh_if_due()

    assert result["partial"] is True and result["ok"] is False
    assert calls == [{"deep": True, "write_latest": True}]


def test_candidate_refresh_summary_omits_full_candidate_and_diagnostic_arrays():
    latest_path = "/var/lib/abyss-machine/storage/candidates/latest.json"
    summary = cli._storage_candidate_refresh_summary({
        "ok": False,
        "partial": True,
        "snapshot_id": "snapshot-1",
        "last_deep_at": "2026-09-04T11:00:00Z",
        "paths": {"latest": latest_path},
        "summary": {"candidates": 38000, "ready": 5},
        "coverage": {
            "partial": True,
            "complete": False,
            "runtime_error_count": 1221,
            "runtime_errors_full": [{"path": "/private/example"}],
            "pressure_findings": [{"path": "/private/example"}],
        },
        "runtime_errors": [{"path": "/private/example"}],
        "pressure_findings": [{"path": "/private/example"}],
        "candidates": [{"candidate_id": f"reclaim-{index}"} for index in range(38000)],
        "deep_progress": {"status": "partial", "total": 38000, "cursor": 4096, "remaining": 33904},
        "refresh_result": {"status": "deep_partial_batch", "continuation_required": True},
    })

    assert summary["schema"].endswith("storage_candidates_refresh_receipt_v1")
    assert summary["summary"]["candidates"] == 38000
    assert summary["coverage"]["runtime_error_count"] == 1221
    assert summary["deep_progress"]["remaining"] == 33904
    assert summary["paths"]["latest"] == latest_path
    assert "candidates" not in summary
    assert "runtime_errors" not in summary["coverage"]
    assert "pressure_findings" not in summary["coverage"]
