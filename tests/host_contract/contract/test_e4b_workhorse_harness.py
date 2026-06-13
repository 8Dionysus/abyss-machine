from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


HARNESS_PATH = Path("/srv/abyss-machine/tools/abyss-gemma4-e4b-harness")


def load_harness() -> Any:
    loader = importlib.machinery.SourceFileLoader("e4b_workhorse_harness_under_test", str(HARNESS_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"unable to load spec for {HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_workhorse_harness_rejects_hollow_and_nested_partial_json() -> None:
    harness = load_harness()

    result = harness.self_test(write_latest=False)

    assert result["ok"] is True
    assert "source_ids_required" in result["hollow_fixture"]["failed_keys"]
    assert "no_hollow_action_card" in result["hollow_fixture"]["failed_keys"]
    assert result["nested_partial_fixture"]["parsed"] is False
    assert result["nested_partial_fixture"]["failed_keys"] == []


def test_workhorse_harness_paths_are_non_resident_and_non_executing() -> None:
    harness = load_harness()

    result = harness.paths_payload()

    assert result["ok"] is True
    assert result["profile"] == "gemma4.workhorse"
    assert result["policy"]["resident_service"] is False
    assert result["policy"]["starts_llama_server"] is False
    assert result["policy"]["default_model_execution"] is False
    assert result["policy"]["action_execution"] is False


def test_workhorse_builds_source_linked_e4b_review_pack_v2() -> None:
    harness = load_harness()

    pack = harness.build_pack_from_resident(
        resident={
            "generated_at": "2026-05-19T10:00:00Z",
            "summary": {"candidates": 2, "action_execution": False},
            "candidates": [
                {
                    "candidate_id": "cand-review",
                    "kind": "action_card",
                    "source_job": "action_card_compiler",
                    "source_ids": ["src-1"],
                    "title": "review protected service",
                    "text": "restart protected service only after operator approval",
                    "route": "human_review",
                    "risk": "medium",
                    "review_required": True,
                    "utility_score": 0.92,
                    "selection_score": 0.95,
                    "selection_tier": "operator_attention",
                    "selection_lane": "operator_action",
                    "selection_reasons": ["review_required", "operator_value"],
                    "correctness_risk": "medium",
                    "freshness_class": "fresh",
                    "heartbeat_priority": 5,
                    "e4b_review_eligible": True,
                    "payload": {"excerpt": "restart protected service only after operator approval"},
                },
                {
                    "candidate_id": "cand-reject",
                    "kind": "review_note",
                    "source_job": "risk_sentinel",
                    "source_ids": [],
                    "title": "missing evidence",
                    "text": "unsupported candidate",
                    "route": "execute",
                    "risk": "low",
                    "review_required": False,
                    "utility_score": 0.1,
                    "selection_score": 0.05,
                    "selection_tier": "archive",
                    "selection_lane": "risk_watch",
                    "selection_reasons": ["freshness=stale"],
                    "correctness_risk": "high",
                    "freshness_class": "stale",
                    "heartbeat_priority": 1,
                    "e4b_review_eligible": True,
                    "payload": {"source_refs_missing": True},
                },
            ],
        },
        evals_latest={
            "generated_at": "2026-05-19T10:01:00Z",
            "scorecard": {
                "degraded_jobs": [
                    {"job": "daily_work_blocks", "status": "ok_degraded", "model": {"used": True, "policy": {"decision": "degraded", "primary_reason": "memory_watch"}}}
                ],
                "hollow_candidates": [{"candidate_id": "hollow-1"}],
            },
        },
        policy_latest={
            "generated_at": "2026-05-19T10:02:00Z",
            "decision": "allow",
            "primary_reason": "policy_allow",
            "request": {"class": "job"},
        },
        limit=2,
    )

    checks = harness.pack_checks(pack)
    failed = [item["key"] for item in checks if item.get("level") == "fail"]

    assert failed == []
    assert pack["schema"] == "abyss_machine_gemma4_workhorse_harness_e4b_review_pack_v2"
    assert pack["summary"]["items"] == 1
    assert pack["summary"]["source_excerpts"] >= 1
    assert pack["summary"]["rejected_candidates"] == 1
    assert pack["summary"]["hollow_candidates"] == 1
    assert pack["summary"]["selected_candidates"] == 1
    assert pack["runtime_degradation_context"]["current_status"] == "historical_not_current"
    assert pack["allowed_source_ids"] == ["src-1"]
    assert pack["evidence_items"][0]["candidate_id"] == "cand-review"
    assert pack["evidence_items"][0]["source_excerpts"][0]["source_id"] == "src-1"


def test_workhorse_pack_prefers_selection_score_over_raw_utility() -> None:
    harness = load_harness()
    pack = harness.build_pack_from_resident(
        resident={
            "generated_at": "2026-05-19T10:00:00Z",
            "summary": {"candidates": 2, "action_execution": False},
            "selection": {"schema": "abyss_machine_gemma4_spark_resident_candidate_selection_v1"},
            "candidates": [
                {
                    "candidate_id": "cand-source-quality",
                    "kind": "source_quality",
                    "source_job": "source_quality_scorer",
                    "source_ids": ["src-quality"],
                    "title": "usable",
                    "text": "usable support context",
                    "route": "model_input_candidate",
                    "risk": "none",
                    "review_required": False,
                    "utility_score": 0.98,
                    "selection_score": 0.42,
                    "selection_tier": "model_input_support",
                    "selection_lane": "quality_monitor",
                    "selection_reasons": ["source_quality_support"],
                    "correctness_risk": "low",
                    "freshness_class": "fresh",
                    "heartbeat_priority": 4,
                    "e4b_review_eligible": False,
                    "payload": {"classification": "usable", "allowed_use": "model_input"},
                },
                {
                    "candidate_id": "cand-action",
                    "kind": "action_card",
                    "source_job": "action_card_compiler",
                    "source_ids": ["src-action"],
                    "title": "review action",
                    "text": "operator should review a bounded action card",
                    "route": "operator_needed",
                    "risk": "medium",
                    "review_required": True,
                    "utility_score": 0.52,
                    "selection_score": 0.88,
                    "selection_tier": "operator_attention",
                    "selection_lane": "operator_action",
                    "selection_reasons": ["review_required", "operator_value"],
                    "correctness_risk": "medium",
                    "freshness_class": "fresh",
                    "heartbeat_priority": 3,
                    "e4b_review_eligible": True,
                    "payload": {"confirm_required": True},
                },
            ],
        },
        evals_latest={"generated_at": "2026-05-19T10:01:00Z", "scorecard": {}},
        policy_latest={"generated_at": "2026-05-19T10:02:00Z", "decision": "allow"},
        limit=2,
    )

    assert pack["evidence_items"][0]["candidate_id"] == "cand-action"
    assert pack["evidence_items"][0]["selection_tier"] == "operator_attention"
    assert pack["summary"]["selected_candidates"] == 1


def test_workhorse_pack_preserves_resident_selected_e4b_order() -> None:
    harness = load_harness()
    storage_item = {
        "candidate_id": "cand-storage",
        "kind": "storage_review_item",
        "source_job": "storage_classifier",
        "source_ids": ["src-storage"],
        "title": "safe_regenerable",
        "text": "routine storage review",
        "route": "human_review",
        "risk": "low",
        "review_required": True,
        "utility_score": 0.8,
        "selection_score": 0.9,
        "selection_tier": "operator_attention",
        "selection_lane": "storage_review",
        "selection_reasons": ["review_required"],
        "correctness_risk": "medium",
        "freshness_class": "fresh",
        "heartbeat_priority": 4,
        "e4b_review_eligible": True,
        "payload": {},
    }
    action_item = {
        "candidate_id": "cand-action",
        "kind": "action_card",
        "source_job": "action_card_compiler",
        "source_ids": ["src-action"],
        "title": "review action",
        "text": "operator selected action review",
        "route": "operator_needed",
        "risk": "medium",
        "review_required": True,
        "utility_score": 0.55,
        "selection_score": 0.82,
        "selection_tier": "operator_attention",
        "selection_lane": "operator_action",
        "selection_reasons": ["review_required", "operator_value"],
        "correctness_risk": "medium",
        "freshness_class": "fresh",
        "heartbeat_priority": 3,
        "e4b_review_eligible": True,
        "payload": {"confirm_required": True},
    }

    pack = harness.build_pack_from_resident(
        resident={
            "generated_at": "2026-05-19T10:00:00Z",
            "summary": {"candidates": 2, "action_execution": False},
            "selection": {"schema": "abyss_machine_gemma4_spark_resident_candidate_selection_v1"},
            "candidates": [storage_item, action_item],
            "queues": {"selected_for_e4b_review": [action_item, storage_item]},
        },
        evals_latest={"generated_at": "2026-05-19T10:01:00Z", "scorecard": {}},
        policy_latest={"generated_at": "2026-05-19T10:02:00Z", "decision": "allow"},
        limit=2,
    )

    assert pack["source"]["resident_selected_for_e4b_review"] == 2
    assert [item["candidate_id"] for item in pack["evidence_items"]] == ["cand-action", "cand-storage"]


def test_workhorse_review_requires_candidate_judgements_and_operator_summary() -> None:
    harness = load_harness()
    pack = {
        "summary": {"items": 1, "action_candidates": 0},
        "allowed_source_ids": ["src-1"],
        "evidence_items": [{"candidate_id": "cand-1", "source_id": "src-1", "source_ids": ["src-1"]}],
    }
    hollow_review = {
        "source_ids": ["src-1"],
        "review_items": [{"source_id": "src-1", "candidate_id": "cand-1", "decision": "review_candidate", "reason": "ok"}],
        "candidate_judgements": [],
        "operator_summary": "",
        "action_cards": [],
        "risk_routes": [],
        "safe_next_checks": [],
        "verdict": "candidate_review_ready",
        "action_execution": False,
    }

    failed = {item["key"] for item in harness.review_checks(hollow_review, pack) if item.get("level") == "fail"}

    assert "candidate_judgements_required" in failed
    assert "operator_summary" in failed
