from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_recall import (  # noqa: E402
    evidence_from_results,
    evidence_summary,
    normalize_mode,
    pack_document,
    pack_execution_plan,
    pack_id,
    refused_result,
)


def test_recall_refusal_and_mode_contracts_are_module_owned() -> None:
    refused = refused_result("abyss_machine", "test", "2026-06-26T12:00:00+00:00")

    assert refused["schema"] == "abyss_machine_nervous_retrieval_pack_v1"
    assert refused["ok"] is False
    assert refused["refused"] is True
    assert "global_pause" in refused["error"]
    assert normalize_mode("hybrid") == "hybrid"
    assert normalize_mode("unknown") == "lexical"


def test_recall_execution_plan_selects_search_adapter_and_flags() -> None:
    lexical = pack_execution_plan(query="thermal", limit=5, mode="unknown", source="facts")
    hybrid = pack_execution_plan(
        query="thermal",
        limit=7,
        mode="hybrid",
        force_policy=True,
        source="facts",
        schema="events",
        since="2026-06-25T00:00:00+00:00",
        until="2026-06-26T00:00:00+00:00",
        severity="warning",
        sensitivity="internal",
    )

    assert lexical == {
        "schema": "abyss_machine_nervous_recall_pack_execution_plan_v1",
        "query": "thermal",
        "mode": "lexical",
        "filters": {
            "source": "facts",
            "schema": None,
            "since": None,
            "until": None,
            "severity": None,
            "sensitivity": None,
        },
        "search": {
            "adapter": "nervous_index_search",
            "kwargs": {
                "query": "thermal",
                "limit": 5,
                "source": "facts",
                "schema": None,
                "since": None,
                "until": None,
                "severity": None,
                "sensitivity": None,
                "dedupe": True,
                "order": "latest",
            },
        },
        "policy": {
            "raw_private_content": False,
            "automatic_action": False,
            "model_used": False,
            "repo_mutation": False,
            "live_execution_at_cli_edge": True,
        },
    }
    assert hybrid["mode"] == "hybrid"
    assert hybrid["search"]["adapter"] == "nervous_rerank_search"
    assert hybrid["search"]["kwargs"] == {
        "query": "thermal",
        "limit": 7,
        "source": "facts",
        "schema": "events",
        "since": "2026-06-25T00:00:00+00:00",
        "until": "2026-06-26T00:00:00+00:00",
        "severity": "warning",
        "sensitivity": "internal",
        "use_semantic": True,
        "force_policy": True,
        "write_latest": True,
    }
    assert hybrid["policy"]["model_used"] is True


def test_recall_evidence_projection_counts_and_pack_identity_are_stable() -> None:
    results = [
        {
            "chunk_id": "c1",
            "doc_id": "d1",
            "source_id": "abyss_machine_facts",
            "document_schema": "facts",
            "title": "Thermal",
            "snippet": "RAPL smoothing",
            "score": 0.9,
            "severity": "warning",
            "provenance": {"category": "thermal"},
            "rerank": {"score": 0.91},
            "sources_used": ["lexical", "semantic"],
            "raw_private": "drop me",
        },
        {
            "chunk_id": "c2",
            "source_id": "browser_active_tab",
            "document_schema": "browser",
            "severity": "info",
            "provenance": {"category": "desktop"},
        },
    ]
    evidence = evidence_from_results(results)
    search = {
        "ok": True,
        "schema": "abyss_machine_nervous_search_v1",
        "warnings": ["bounded"],
        "summary": {"index_run_id": "idx-1", "semantic_used": True},
    }
    filters = {"source": None, "schema": None, "since": None, "until": None, "severity": None, "sensitivity": None}
    identity = pack_id("thermal", filters, evidence, "idx-1")
    doc = pack_document(
        query="thermal",
        mode="hybrid",
        filters=filters,
        search=search,
        evidence=evidence,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
        latest_path="/var/lib/abyss-machine/nervous/retrieval/latest.json",
        daily_glob="/var/lib/abyss-machine/nervous/retrieval/YYYY/MM/YYYY-MM-DD.jsonl",
    )

    assert identity == doc["pack_id"]
    assert evidence[0]["chunk_id"] == "c1"
    assert "raw_private" not in evidence[0]
    assert evidence_summary(evidence, search)["source_counts"] == {"abyss_machine_facts": 1, "browser_active_tab": 1}
    assert doc["ok"] is True
    assert doc["mode"] == "hybrid"
    assert doc["summary"]["category_counts"] == {"desktop": 1, "thermal": 1}
    assert doc["policy"]["raw_private_content"] is False
    assert doc["policy"]["model_used"] is True
    assert doc["claims"][0]["supporting_chunk_ids"] == ["c1", "c2"]


def test_recall_failed_search_envelope_and_cli_import_delegate_to_module() -> None:
    doc = pack_document(
        query="missing",
        mode="bad-mode",
        filters={},
        search={"ok": False, "error": "index unavailable"},
        evidence=[],
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
        latest_path="/tmp/latest.json",
        daily_glob="/tmp/YYYY-MM-DD.jsonl",
    )
    from abyss_machine import cli

    assert doc["ok"] is False
    assert doc["mode"] == "lexical"
    assert doc["error"] == "index unavailable"
    assert cli.nervous_recall_contracts.normalize_mode("hybrid") == "hybrid"


def test_cli_recall_pack_executes_module_plan_at_edge(monkeypatch) -> None:
    from abyss_machine import cli

    lexical_search = {
        "ok": True,
        "schema": "abyss_machine_nervous_search_v1",
        "results": [{"chunk_id": "c1", "doc_id": "d1", "source_id": "facts"}],
        "summary": {"index_run_id": "idx-cli"},
    }
    hybrid_search = {
        "ok": True,
        "schema": "abyss_machine_nervous_rerank_v1",
        "results": [{"chunk_id": "c2", "doc_id": "d2", "source_id": "facts", "sources_used": ["lexical", "semantic"]}],
        "summary": {"index_run_id": "idx-cli", "semantic_used": True},
    }
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_index_search(**kwargs):
        calls.append(("index", kwargs))
        return lexical_search

    def fake_rerank_search(**kwargs):
        calls.append(("rerank", kwargs))
        return hybrid_search

    monkeypatch.setattr(cli, "nervous_effective_privacy", lambda write_latest=False: {"global_pause": False})
    monkeypatch.setattr(cli, "nervous_index_search", fake_index_search)
    monkeypatch.setattr(cli, "nervous_rerank_search", fake_rerank_search)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T12:00:00+00:00")

    lexical = cli.nervous_recall_pack("thermal", limit=3, source="facts", write_latest=False)
    hybrid = cli.nervous_recall_pack("thermal", limit=4, mode="hybrid", force_policy=True, source="facts", write_latest=False)

    assert lexical == pack_document(
        query="thermal",
        mode="lexical",
        filters={
            "source": "facts",
            "schema": None,
            "since": None,
            "until": None,
            "severity": None,
            "sensitivity": None,
        },
        search=lexical_search,
        evidence=evidence_from_results(lexical_search["results"]),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T12:00:00+00:00",
        latest_path=str(cli.NERVOUS_RETRIEVAL_LATEST_PATH),
        daily_glob=str(cli.NERVOUS_RETRIEVAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
    )
    assert hybrid["mode"] == "hybrid"
    assert hybrid["source"]["search_schema"] == "abyss_machine_nervous_rerank_v1"
    assert hybrid["policy"]["model_used"] is True
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
