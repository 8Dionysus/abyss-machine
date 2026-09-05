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
