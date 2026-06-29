from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_retrieval_adapters  # noqa: E402
from abyss_machine.nervous_rerank import profile_from_config  # noqa: E402


GENERATED_AT = "2026-06-26T12:00:00+00:00"


def _host_result(**extra: object) -> dict[str, object]:
    item: dict[str, object] = {
        "chunk_id": "host-1",
        "doc_id": "doc-host",
        "source_id": "abyss_machine_facts",
        "document_schema": "facts",
        "title": "Thermal RAPL",
        "snippet": "thermal rapl smoothing gamemode guard",
        "score": 0.8,
        "severity": "warning",
        "chunk_generated_at": GENERATED_AT,
        "provenance": {"category": "thermal"},
    }
    item.update(extra)
    return item


def test_hybrid_rerank_adapter_merges_live_ports_without_writing(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def lexical_search(**kwargs: Any) -> dict[str, Any]:
        calls.append(("lexical", kwargs))
        return {
            "ok": True,
            "schema": "abyss_machine_nervous_search_v1",
            "results": [_host_result()],
            "summary": {"index_run_id": "idx-1", "built_at": GENERATED_AT, "freshness": {"stale": False}},
        }

    def semantic_search(**kwargs: Any) -> dict[str, Any]:
        calls.append(("semantic", kwargs))
        return {
            "ok": True,
            "schema": "abyss_machine_nervous_semantic_search_v1",
            "results": [_host_result(score=0.92, semantic_score=0.84)],
            "summary": {"semantic_run_id": "sem-1"},
        }

    def neural_apply(
        ranked: list[dict[str, Any]],
        query: str,
        query_tokens: set[str],
        rerank_profile: dict[str, Any],
        neural_config: dict[str, Any],
        force_policy: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
        calls.append((
            "neural",
            {
                "query": query,
                "tokens": sorted(query_tokens),
                "profile": rerank_profile["id"],
                "force_policy": force_policy,
                "items": len(ranked),
            },
        ))
        return ranked, {"ok": True, "timing": {"documents": len(ranked)}}, []

    data = nervous_retrieval_adapters.hybrid_rerank_search(
        query="thermal rapl smoothing",
        config={"search": {"max_limit": 50}},
        rerank_profile=profile_from_config({}),
        neural_config={"enabled": True, "model_dir": "/models/rerank", "backend": "test", "weight": 0.2},
        lexical_search=lexical_search,
        semantic_status=lambda: {"ready": True, "freshness": {"stale": True}, "warnings": []},
        semantic_config={"maintain": {"min_delta_chunks": 2, "max_stale_minutes": 15}},
        semantic_maintain_assess=lambda status, min_delta, max_stale: {"needed": False, "min_delta": min_delta, "max_stale": max_stale},
        semantic_search=semantic_search,
        neural_apply=neural_apply,
        latest_path=tmp_path / "rerank" / "latest.json",
        daily_root=tmp_path / "rerank" / "history",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        limit=5,
        write_latest=False,
        now=lambda: dt.datetime(2026, 6, 26, 12, tzinfo=dt.timezone.utc),
        path_exists=lambda _value: True,
    )

    assert data["schema"] == "abyss_machine_nervous_rerank_v1"
    assert data["ok"] is True
    assert data["summary"]["candidates"] == 1
    assert data["summary"]["lexical_results"] == 1
    assert data["summary"]["semantic_results"] == 1
    assert data["summary"]["semantic_used"] is True
    assert data["summary"]["semantic_stale"] is True
    assert data["summary"]["semantic_maintenance_needed"] is False
    assert data["summary"]["neural_used"] is True
    assert data["summary"]["neural_ready"] is True
    assert data["notices"] == ["semantic sidecar has bounded stale drift below maintenance thresholds"]
    assert data["results"][0]["sources_used"] == ["lexical", "semantic"]
    assert data["results"][0]["scores"]["semantic_norm"] == 0.92
    assert not (tmp_path / "rerank").exists()
    assert calls[0] == (
        "lexical",
        {
            "query": "thermal rapl smoothing",
            "limit": 24,
            "dedupe": False,
            "order": "ranked",
            "source": None,
            "schema": None,
            "since": None,
            "until": None,
            "severity": None,
            "sensitivity": None,
        },
    )
    assert calls[1][0] == "semantic"
    assert calls[2][0] == "neural"


def test_write_latest_history_marks_write_errors(tmp_path: Path) -> None:
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("not a directory\n", encoding="utf-8")
    data = nervous_retrieval_adapters.write_latest_history(
        {"ok": True, "schema": "test"},
        blocking_file / "latest.json",
        blocking_file / "history",
    )

    assert data["ok"] is False
    assert data["write_errors"]
    error_paths = {error["path"] for error in data["write_errors"]}
    assert str(blocking_file / "latest.json") in error_paths
    assert any(path.startswith(str(blocking_file / "history")) and path.endswith(".jsonl") for path in error_paths)


def test_build_recall_pack_dispatches_search_ports_without_cli_logic(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def index_search(**kwargs: Any) -> dict[str, Any]:
        calls.append(("index", kwargs))
        return {
            "ok": True,
            "schema": "abyss_machine_nervous_search_v1",
            "results": [_host_result()],
            "summary": {"index_run_id": "idx-1"},
        }

    def rerank_search(**kwargs: Any) -> dict[str, Any]:
        calls.append(("rerank", kwargs))
        return {
            "ok": True,
            "schema": "abyss_machine_nervous_rerank_v1",
            "results": [_host_result(sources_used=["lexical", "semantic"])],
            "summary": {"index_run_id": "idx-1", "semantic_used": True, "semantic_run_id": "sem-1"},
        }

    lexical = nervous_retrieval_adapters.build_recall_pack(
        query="thermal",
        index_search=index_search,
        rerank_search=rerank_search,
        latest_path=tmp_path / "retrieval" / "latest.json",
        daily_root=tmp_path / "retrieval" / "history",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        limit=3,
        source="facts",
        write_latest=False,
    )
    hybrid = nervous_retrieval_adapters.build_recall_pack(
        query="thermal",
        index_search=index_search,
        rerank_search=rerank_search,
        latest_path=tmp_path / "retrieval" / "latest.json",
        daily_root=tmp_path / "retrieval" / "history",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        limit=4,
        mode="hybrid",
        force_policy=True,
        source="facts",
        write_latest=False,
    )

    assert lexical["source"]["search_schema"] == "abyss_machine_nervous_search_v1"
    assert lexical["summary"]["source_counts"] == {"abyss_machine_facts": 1}
    assert hybrid["source"]["search_schema"] == "abyss_machine_nervous_rerank_v1"
    assert hybrid["policy"]["model_used"] is True
    assert hybrid["evidence"][0]["sources_used"] == ["lexical", "semantic"]
    assert calls == [
        (
            "index",
            {
                "query": "thermal",
                "limit": 3,
                "source": "facts",
                "schema": None,
                "since": None,
                "until": None,
                "severity": None,
                "sensitivity": None,
                "dedupe": True,
                "order": "latest",
            },
        ),
        (
            "rerank",
            {
                "query": "thermal",
                "limit": 4,
                "source": "facts",
                "schema": None,
                "since": None,
                "until": None,
                "severity": None,
                "sensitivity": None,
                "use_semantic": True,
                "force_policy": True,
                "write_latest": True,
            },
        ),
    ]


def test_cli_rerank_search_binds_retrieval_adapter(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_hybrid_rerank_search(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True, "schema": "abyss_machine_nervous_rerank_v1"}

    monkeypatch.setattr(cli.nervous_retrieval_adapters, "hybrid_rerank_search", fake_hybrid_rerank_search)
    monkeypatch.setattr(cli, "nervous_index_config", lambda: {"search": {"max_limit": 50}})
    monkeypatch.setattr(cli, "nervous_rerank_profile", lambda config=None: {"id": "test", "weights": {}, "weight_total": 1.0})
    monkeypatch.setattr(cli, "nervous_neural_rerank_config", lambda config=None: {"enabled": False})
    monkeypatch.setattr(cli, "nervous_semantic_config", lambda: {"maintain": {}})
    monkeypatch.setattr(cli, "now_iso", lambda: GENERATED_AT)

    data = cli.nervous_rerank_search("thermal", limit=2, source="facts", use_semantic=False, write_latest=False)

    assert data == {"ok": True, "schema": "abyss_machine_nervous_rerank_v1"}
    assert captured["query"] == "thermal"
    assert captured["config"] == {"search": {"max_limit": 50}}
    assert captured["lexical_search"] is cli.nervous_index_search
    assert captured["semantic_search"] is cli.nervous_semantic_search
    assert captured["neural_apply"] is cli.nervous_apply_neural_rerank_scores
    assert captured["latest_path"] == cli.NERVOUS_RERANK_LATEST_PATH
    assert captured["daily_root"] == cli.NERVOUS_RERANK_ROOT
    assert captured["limit"] == 2
    assert captured["source"] == "facts"
    assert captured["use_semantic"] is False
    assert captured["write_latest"] is False
