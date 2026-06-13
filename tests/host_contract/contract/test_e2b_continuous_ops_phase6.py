from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


RESIDENT_PATH = Path("/srv/abyss-machine/tools/abyss-gemma4-spark-resident")


def load_resident() -> Any:
    loader = importlib.machinery.SourceFileLoader("gemma4_spark_resident_under_test", str(RESIDENT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"unable to load spec for {RESIDENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_phase6_lane_quality_and_score_only_readiness() -> None:
    resident = load_resident()
    candidates = [
        {
            "candidate_id": "cand-1",
            "source_job": "dictation_quality",
            "source_ids": ["src-1"],
            "utility_score": 0.8,
            "heartbeat_priority": 4,
            "review_required": True,
            "e4b_review_eligible": True,
            "freshness_class": "fresh",
            "correctness_risk": "medium",
        },
        {
            "candidate_id": "cand-2",
            "source_job": "browser_reading",
            "source_ids": ["src-2"],
            "utility_score": 0.5,
            "heartbeat_priority": 0,
            "review_required": False,
            "e4b_review_eligible": False,
            "freshness_class": "stale",
            "correctness_risk": "low",
        },
    ]
    lane_quality = resident.lane_quality_summary(candidates)
    trend = resident.quality_trend_summary(
        {
            "overall_score": 0.99,
            "families": {"schema_eval": {"score": 1.0}, "utility_eval": {"score": 0.9}},
        },
        lane_quality,
    )
    readiness = resident.readiness_recommendation(
        {"overall_score": 0.99},
        {"schema_pass_ratio": {"passed": True}, "utility_score": {"passed": True}},
        trend,
    )

    assert lane_quality["dictation_quality"]["heartbeat_candidates"] == 1
    assert lane_quality["dictation_quality"]["e4b_review_eligible"] == 1
    assert lane_quality["browser_reading"]["stale_candidates"] == 1
    assert trend["schema"] == "abyss_machine_gemma4_spark_resident_quality_trend_v1"
    assert trend["lane_quality"] == lane_quality
    assert readiness["score_only"] is True
    assert readiness["automatic_promotion"] is False
    assert readiness["requires_operator_review"] is True


def test_phase6_failed_cases_become_fixture_candidates(tmp_path: Path) -> None:
    resident = load_resident()
    resident.EVALS_FIXTURE_CANDIDATES_LATEST = tmp_path / "fixture-candidates" / "latest.json"
    checks = [
        {
            "family": "semantic_eval",
            "level": "fail",
            "key": "candidate_source_ids_grounded",
            "message": "candidate source ids are present",
            "details": {"bad": [{"candidate_id": "cand-bad"}]},
        }
    ]
    candidates = [
        {
            "candidate_id": "cand-bad",
            "kind": "review_note",
            "source_job": "risk_sentinel",
            "source_ids": ["src-1"],
            "route": "human_review",
            "risk": "medium",
            "review_required": True,
        }
    ]

    result = resident.failed_case_fixture_candidates(checks, candidates, degraded_jobs=[])

    assert result["schema"] == "abyss_machine_gemma4_spark_resident_fixture_candidates_v1"
    assert result["summary"]["non_ok_checks"] == 1
    assert result["summary"]["candidate_cases"] == 1
    assert result["candidate_cases"][0]["candidate_id"] == "cand-bad"
    assert result["policy"]["does_not_rewrite_eval_fixtures"] is True
    assert resident.EVALS_FIXTURE_CANDIDATES_LATEST.exists()


def test_phase7_selection_promotes_operator_value_over_source_quality() -> None:
    resident = load_resident()
    source_quality = {
        "candidate_id": "cand-source-quality",
        "kind": "source_quality",
        "source_job": "source_quality_scorer",
        "source_ids": ["src-quality"],
        "route": "model_input_candidate",
        "risk": "none",
        "review_required": False,
        "utility_score": 0.98,
        "correctness_risk": "low",
        "freshness_class": "fresh",
        "heartbeat_priority": 4,
        "e4b_review_eligible": False,
        "payload": {"classification": "usable", "allowed_use": "model_input"},
    }
    action_card = {
        "candidate_id": "cand-action",
        "kind": "action_card",
        "source_job": "action_card_compiler",
        "source_ids": ["src-action"],
        "route": "operator_needed",
        "risk": "medium",
        "review_required": True,
        "utility_score": 0.52,
        "correctness_risk": "medium",
        "freshness_class": "fresh",
        "heartbeat_priority": 3,
        "e4b_review_eligible": True,
        "payload": {"confirm_required": True},
    }
    source_quality.update(resident.candidate_selection_fields(source_quality))
    action_card.update(resident.candidate_selection_fields(action_card))

    ordered = sorted([source_quality, action_card], key=resident.candidate_selection_sort_key)
    selection = resident.candidate_selection_summary(ordered)

    assert ordered[0]["candidate_id"] == "cand-action"
    assert action_card["selection_tier"] == "operator_attention"
    assert action_card["selection_lane"] == "operator_action"
    assert source_quality["selection_tier"] == "model_input_support"
    assert source_quality["selection_lane"] == "quality_monitor"
    assert action_card["selection_score"] > source_quality["selection_score"]
    assert selection["top"][0]["candidate_id"] == "cand-action"
    assert selection["suppressed_background_count"] == 1


def test_phase7_selection_pick_is_lane_balanced() -> None:
    resident = load_resident()

    def candidate(candidate_id: str, kind: str, source_job: str, lane: str, score: float) -> dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "kind": kind,
            "source_job": source_job,
            "source_ids": [f"src-{candidate_id}"],
            "title": candidate_id,
            "text": candidate_id,
            "route": "human_review",
            "risk": "low",
            "review_required": True,
            "utility_score": score,
            "selection_score": score,
            "selection_tier": "operator_attention",
            "selection_lane": lane,
            "selection_reasons": ["review_required"],
            "heartbeat_priority": 4,
            "e4b_review_eligible": True,
            "freshness_class": "fresh",
            "correctness_risk": "low",
            "action_execution": False,
        }

    candidates = [
        candidate("storage-1", "storage_review_item", "storage_classifier", "storage_review", 0.95),
        candidate("storage-2", "storage_review_item", "storage_classifier", "storage_review", 0.94),
        candidate("storage-3", "storage_review_item", "storage_classifier", "storage_review", 0.93),
        candidate("action-1", "action_card", "action_card_compiler", "operator_action", 0.8),
        candidate("intent-1", "intent_open_question", "intent_candidates", "operator_intent", 0.79),
        candidate("risk-1", "risk_route", "risk_sentinel", "risk_watch", 0.78),
    ]

    picked = resident.pick_selected_candidates(candidates, 4, per_source_job=4, per_kind=4, per_lane=2)

    assert [item["selection_lane"] for item in picked] == [
        "operator_action",
        "operator_intent",
        "risk_watch",
        "storage_review",
    ]


def test_phase7_append_candidate_preserves_text_separate_from_source_ids() -> None:
    resident = load_resident()
    candidates: list[dict[str, Any]] = []
    source_item = {
        "generated_at": resident.now_iso(),
        "status": "ok",
        "source": {"freshness": {"max_age_sec": 86400.0, "newest_age_sec": 1.0}},
        "model": {"fallback_used": False},
    }

    resident.append_candidate(
        candidates,
        source_job="intent_candidates",
        kind="intent_open_question",
        source_id="src-1",
        source_ids=["src-1", "src-2"],
        title="open_question",
        text="actual operator question text",
        score=0.6,
        route="human_review",
        review_required=True,
        source_generated_at=source_item["generated_at"],
        source_item=source_item,
    )

    assert candidates[0]["text"] == "actual operator question text"
    assert candidates[0]["source_ids"] == ["src-1", "src-2"]
    assert candidates[0]["selection_reasons"]
