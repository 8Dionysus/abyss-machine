from copy import deepcopy
import tracemalloc

import pytest

from abyss_machine import cli


@pytest.mark.parametrize("partial", [False, True])
def test_light_refresh_does_not_duplicate_evidence_payload_or_mutate_source(monkeypatch, partial):
    """Frequent light checks must not allocate another full evidence snapshot."""
    previous = {
        "generated_at": "2026-09-05T11:00:00Z",
        "last_deep_at": "2026-09-05T11:00:00Z",
        "partial": partial,
        "summary": {"changed": 7, "retired": 2},
        "policy": {"automatic_deletion": True},
        "coverage": {"partial": partial, "discovered": 1, "observed": 1},
        "deep_progress": {"status": "partial" if partial else "complete", "remaining": 0},
        "candidates": [{
            "candidate_id": "fixture", "source_adapter": "fixture",
            "evidence": {"retained_payload": "x" * (4 * 1024 * 1024)},
        }],
    }
    before = deepcopy(previous)
    monkeypatch.setattr(cli.storage_candidate_adapters, "load_json_records", lambda _: [])
    monkeypatch.setattr(cli, "storage_candidate_policy", lambda: {"deep_max_age_seconds": 172800})
    monkeypatch.setattr(cli, "storage_candidate_paths", lambda: {})
    tracemalloc.start()
    try:
        result = cli.storage_candidate_light_refresh(previous, "2026-09-05T12:00:00Z")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 2 * 1024 * 1024, "light refresh copied the retained evidence payload"
    assert previous == before
    assert result["candidates"] == previous["candidates"]
    assert result["summary"]["changed"] == 0
    assert result["policy"]["automatic_deletion"] is False
    assert result["last_deep_at"] == previous["last_deep_at"]
    if partial:
        assert result["ok"] is False
        assert result["coverage"]["complete"] is False
        assert result["freshness"]["partial"] is True
