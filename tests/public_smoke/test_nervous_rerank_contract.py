from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_rerank import (  # noqa: E402
    apply_neural_scores,
    default_profile,
    eval_document,
    merge_item,
    neural_config_from_config,
    neural_text,
    profile_from_config,
    result_source_score_detail,
    score_result_item,
)


def test_rerank_profile_and_source_prior_contracts_are_module_owned() -> None:
    profile = profile_from_config(
        {
            "search": {
                "rerank": {
                    "source_prior_profile": "operator_override",
                    "weights": {"semantic": "0.3", "source_prior": "0.11"},
                    "source_priors": {
                        "browser_active_tab": {
                            "default": 0.1,
                            "matched": 0.99,
                            "tokens": ["browser", "tab"],
                            "reason": "browser override",
                        }
                    },
                    "machine_query": {"unmatched_context_max_score": "0.25"},
                }
            }
        }
    )

    machine = result_source_score_detail({"source_id": "abyss_machine_facts"}, {"thermal", "machine"}, profile)
    browser_unmatched = result_source_score_detail({"source_id": "browser_active_tab"}, {"thermal", "machine"}, profile)
    browser_matched = result_source_score_detail({"source_id": "browser_active_tab"}, {"browser", "tab"}, profile)

    assert default_profile()["id"] == "host_machine_evidence_v1"
    assert profile["id"] == "operator_override"
    assert profile["weights"]["semantic"] == 0.3
    assert profile["weights"]["source_prior"] == 0.11
    assert profile["machine_query"]["unmatched_context_max_score"] == 0.25
    assert machine["score"] == 1.0
    assert browser_unmatched["score"] == 0.1
    assert browser_matched["score"] == 0.99
    assert browser_matched["matched_tokens"] == ["browser", "tab"]


def test_rerank_hybrid_score_caps_unmatched_context_for_machine_queries() -> None:
    profile = profile_from_config({})
    item = {
        "chunk_id": "browser-1",
        "source_id": "browser_active_tab",
        "scores": {"lexical_rank": 1.0, "semantic_norm": 1.0},
    }
    scored = score_result_item(
        item,
        query_tokens={"thermal", "machine"},
        text_tokens={"page", "unrelated"},
        recency_score=1.0,
        severity_score=1.0,
        profile=profile,
    )

    cap = scored["rerank"]["machine_query_cap"]
    assert cap["active"] is True
    assert cap["applied"] is True
    assert cap["score_after"] == 0.34
    assert scored["score"] == 0.34
    assert scored["rerank"]["source_matched_tokens"] == []


def test_rerank_merge_and_neural_blend_preserve_host_guard() -> None:
    existing = {
        "chunk_id": "host-1",
        "source_id": "abyss_machine_facts",
        "document_generated_at": "2026-06-26T10:00:00+00:00",
        "sources_used": ["lexical"],
        "scores": {"lexical_rank": 0.5},
    }
    incoming = {
        "chunk_id": "host-1",
        "source_id": "abyss_machine_facts",
        "document_generated_at": "2026-06-26T11:00:00+00:00",
        "sources_used": ["semantic"],
        "scores": {"semantic_norm": 0.9},
        "title": "newer",
    }
    merged = merge_item(existing, incoming)
    profile = profile_from_config({})
    ranked = [
        {
            "chunk_id": "host-1",
            "source_id": "abyss_machine_facts",
            "score": 0.7,
            "rerank": {"score": 0.7, "source_matched_tokens": ["thermal"]},
        },
        {
            "chunk_id": "browser-1",
            "source_id": "browser_active_tab",
            "score": 0.95,
            "rerank": {"score": 0.95, "source_matched_tokens": []},
        },
    ]
    neural_config = {"weight": 0.5, "machine_context_weight": 0.0}
    blended = apply_neural_scores(
        ranked,
        [{"id": "host-1", "score": 0.2}, {"id": "browser-1", "score": 1.0}],
        {"thermal", "machine"},
        profile,
        neural_config,
        candidate_limit=2,
    )

    assert merged["title"] == "newer"
    assert merged["sources_used"] == ["lexical", "semantic"]
    assert merged["scores"]["lexical_rank"] == 0.5
    assert merged["scores"]["semantic_norm"] == 0.9
    browser = next(item for item in blended if item["chunk_id"] == "browser-1")
    host = next(item for item in blended if item["chunk_id"] == "host-1")
    assert browser["rerank"]["neural_guard"]["unmatched_machine_context"] is True
    assert browser["rerank"]["neural_guard"]["preferred_host_guard"] is True
    assert browser["score"] < host["score"]


def test_rerank_neural_config_and_cli_import_delegate_to_module() -> None:
    cfg = neural_config_from_config(
        {"search": {"rerank": {"neural": {"enabled": True, "weight": "2.0", "machine_context_weight": "-1"}}}},
        default_model_dir="/models/rerank",
        default_cache_dir="/cache/rerank",
        default_scorer="/tools/rerank.py",
    )
    from abyss_machine import cli

    assert cfg["enabled"] is True
    assert cfg["weight"] == 1.0
    assert cfg["machine_context_weight"] == 0.0
    assert cfg["model_dir"] == "/models/rerank"
    assert neural_text({"source_id": "s", "document_schema": "schema", "title": "T", "snippet": "body"}).startswith("Source: s schema")
    assert cli.nervous_rerank_default_profile()["id"] == default_profile()["id"]
    assert cli.nervous_result_source_score({"source_id": "abyss_machine_facts"}, {"thermal"}) == 1.0


def _successful_rerank_search(profile: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "query": "thermal rapl smoothing gamemode guard",
        "warnings": [],
        "notices": [],
        "summary": {
            "semantic_used": True,
            "semantic_stale": False,
            "semantic_maintenance_needed": False,
        },
        "results": [
            {
                "chunk_id": "host-1",
                "source_id": "abyss_machine_facts",
                "rerank": {
                    "score": 0.99,
                    "source_profile": profile["id"],
                    "source_score": 1.0,
                    "source_matched_tokens": ["thermal"],
                },
            },
            {
                "chunk_id": "browser-1",
                "source_id": "browser_active_tab",
                "rerank": {
                    "score": 0.2,
                    "source_profile": profile["id"],
                    "source_score": 0.2,
                    "source_matched_tokens": [],
                    "machine_query_cap": {"active": True, "applied": True, "score_after": 0.2},
                },
            },
        ],
    }


def test_rerank_eval_document_contract_is_module_owned() -> None:
    profile = profile_from_config({})
    search = _successful_rerank_search(profile)

    data = eval_document(
        profile=profile,
        search=search,
        latest_path="/state/nervous/rerank/eval/latest.json",
        daily_glob="/state/nervous/rerank/eval/YYYY/MM/YYYY-MM-DD.jsonl",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data["schema"] == "abyss_machine_nervous_rerank_eval_v1"
    assert data["version"] == "test"
    assert data["ok"] is True
    assert data["status"] == "ok"
    assert data["summary"] == {"status": "ok", "fails": 0, "warnings": 0, "checks": 9}
    assert [item["key"] for item in data["checks"]] == [
        "weights_total",
        "machine_source_prior",
        "context_source_prior_unmatched",
        "context_source_prior_matched",
        "live_rerank_query",
        "explainable_source_prior",
        "machine_query_prefers_host_evidence",
        "machine_query_caps_unmatched_context",
        "threshold_aware_stale_warning",
    ]
    assert data["live_search"]["top_sources"] == ["abyss_machine_facts", "browser_active_tab"]
    assert data["policy"]["model_used"] is True
    assert data["paths"]["latest"] == "/state/nervous/rerank/eval/latest.json"


def test_rerank_eval_document_reports_bounded_stale_notice() -> None:
    profile = profile_from_config({})
    search = _successful_rerank_search(profile)
    search["summary"] = {
        "semantic_used": True,
        "semantic_stale": True,
        "semantic_maintenance_needed": False,
    }
    search["notices"] = ["semantic index bounded stale drift below maintenance thresholds"]
    search["sources"] = {"semantic": {"status": {"maintenance": {"needed": False}}}}

    data = eval_document(
        profile=profile,
        search=search,
        latest_path="/state/latest.json",
        daily_glob="/state/YYYY/MM/YYYY-MM-DD.jsonl",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert data["ok"] is True
    assert data["summary"]["checks"] == 10
    assert data["checks"][-1]["key"] == "bounded_stale_notice"
    assert data["checks"][-1]["level"] == "ok"


def test_rerank_eval_document_exposes_failures_without_live_adapters() -> None:
    profile = profile_from_config({})
    profile["weight_total"] = 0.5
    search = {
        "ok": False,
        "query": "thermal rapl smoothing gamemode guard",
        "warnings": ["semantic index is stale relative to lexical index"],
        "notices": [],
        "summary": {"semantic_used": False},
        "results": [{"source_id": "browser_active_tab", "rerank": {}}],
    }

    data = eval_document(
        profile=profile,
        search=search,
        latest_path="/state/latest.json",
        daily_glob="/state/YYYY/MM/YYYY-MM-DD.jsonl",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    failed_keys = {item["key"] for item in data["checks"] if item["level"] == "fail"}
    assert data["ok"] is False
    assert data["status"] == "fail"
    assert {
        "weights_total",
        "live_rerank_query",
        "explainable_source_prior",
        "machine_query_prefers_host_evidence",
        "threshold_aware_stale_warning",
    }.issubset(failed_keys)


def test_rerank_eval_cli_delegates_document_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    profile = profile_from_config({})
    search = _successful_rerank_search(profile)
    captured: dict[str, object] = {}

    def fake_profile() -> dict[str, object]:
        return profile

    def fake_search(query: str, **kwargs: object) -> dict[str, object]:
        captured["query"] = query
        captured["kwargs"] = kwargs
        return search

    monkeypatch.setattr(cli, "nervous_rerank_profile", fake_profile)
    monkeypatch.setattr(cli, "nervous_rerank_search", fake_search)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T12:00:00+00:00")

    result = cli.nervous_rerank_eval(force_policy=True, write_latest=False)
    expected = eval_document(
        profile=profile,
        search=search,
        latest_path=str(cli.NERVOUS_RERANK_EVAL_LATEST_PATH),
        daily_glob=str(cli.NERVOUS_RERANK_EVAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert result == expected
    assert captured == {
        "query": "thermal rapl smoothing gamemode guard",
        "kwargs": {"limit": 8, "candidate_limit": 24, "force_policy": True, "write_latest": True},
    }
