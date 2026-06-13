from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def _load_workhorse_harness() -> Any:
    path = Path("/srv/abyss-machine/tools/abyss-gemma4-e4b-harness")
    loader = importlib.machinery.SourceFileLoader("abyss_gemma4_e4b_harness_under_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_heartbeat_ai_hygiene_surfaces_source_and_hollow_failures(abyss_machine_module) -> None:
    result = abyss_machine_module.heartbeat_ai_hygiene_from(
        ai_llm_validate={"ok": True, "summary": {"fails": 0}, "checks": []},
        resident_candidates_validate={"ok": True, "summary": {"fails": 0}, "checks": []},
        workhorse_review={
            "ok": True,
            "generated_at": "2026-05-19T10:00:00+00:00",
            "summary": {"parsed": False, "model_used": False},
            "model": {"used": False, "reason": "default_no_model_execution", "run_model_flag": "--run-model"},
            "result": {"action_execution": False, "action_cards": [], "review_items": [{"source_id": "bad"}]},
        },
        workhorse_validate={
            "ok": False,
            "generated_at": "2026-05-19T10:01:00+00:00",
            "summary": {"fails": 3},
            "checks": [
                {"level": "fail", "key": "source_ids_allowed", "message": "output source IDs must come from pack"},
                {"level": "fail", "key": "review_items_sourceful", "message": "review items preserve allowed source IDs"},
                {"level": "fail", "key": "no_hollow_action_card", "message": "action/review candidates cannot yield a safe-shaped empty action card"},
            ],
        },
        generated_at="2026-05-19T10:02:00+00:00",
    )

    assert result["schema"] == "abyss_machine_heartbeat_ai_hygiene_v1"
    assert result["status"] == "watch"
    assert result["summary"]["workhorse_validate_fails"] == 3
    assert result["summary"]["source_id_failures"] == ["source_ids_allowed", "review_items_sourceful"]
    assert result["summary"]["hollow_action_card_fail"] is True
    assert result["policy"]["does_not_run_model_eval"] is True
    assert result["policy"]["does_not_run_workhorse_review_model"] is True
    assert result["owner_gated_routes"][0]["automatic"] is False


def test_heartbeat_ai_hygiene_clean_latest_stays_non_executing(abyss_machine_module) -> None:
    result = abyss_machine_module.heartbeat_ai_hygiene_from(
        ai_llm_validate={"ok": True, "summary": {"fails": 0}, "checks": []},
        resident_candidates_validate={"ok": True, "summary": {"fails": 0}, "checks": []},
        workhorse_validate={"ok": True, "summary": {"fails": 0}, "checks": []},
        workhorse_review={
            "ok": True,
            "summary": {"parsed": False, "model_used": False},
            "model": {"used": False, "reason": "default_no_model_execution"},
            "result": {"action_execution": False, "action_cards": [], "review_items": []},
        },
        generated_at="2026-05-19T10:02:00+00:00",
    )

    assert result["status"] == "ok"
    assert result["ok"] is True
    assert result["summary"]["workhorse_model_used"] is False
    assert result["policy"]["reads_latest_only"] is True
    assert all(route["executes_from_heartbeat"] is False for route in result["owner_gated_routes"])


def test_heartbeat_e2b_breath_tracks_candidate_motion_quality_and_review(abyss_machine_module) -> None:
    result = abyss_machine_module.heartbeat_e2b_breath_from(
        candidates_latest={
            "ok": True,
            "generated_at": "2026-05-19T10:02:00+00:00",
            "candidates": [
                {
                    "candidate_id": "cand-new",
                    "kind": "action_card",
                    "source_job": "thermal_performance",
                    "source_ids": ["thermal:1"],
                    "title": "Review thermal watch",
                    "route": "operator_review",
                    "risk": "medium",
                    "review_required": True,
                    "utility_score": 0.91,
                    "correctness_risk": "low",
                    "freshness_class": "fresh",
                    "heartbeat_priority": 4,
                    "e4b_review_eligible": True,
                    "source_generated_at": "2026-05-19T10:01:30+00:00",
                    "artifact_age_sec": 30,
                    "expires_at": "2026-05-19T16:00:00+00:00",
                },
                {
                    "candidate_id": "cand-persist",
                    "kind": "rank_hint",
                    "source_job": "query_expansion",
                    "source_ids": ["query:1"],
                    "title": "Keep query expansion hint",
                    "route": "search_hint",
                    "risk": "low",
                    "review_required": False,
                    "utility_score": 0.62,
                    "correctness_risk": "low",
                    "freshness_class": "fresh",
                    "heartbeat_priority": 2,
                    "e4b_review_eligible": False,
                    "source_generated_at": "2026-05-19T10:00:00+00:00",
                    "artifact_age_sec": 120,
                    "expires_at": "2026-05-19T16:00:00+00:00",
                },
            ],
            "source_jobs": [
                {"job": "thermal_performance", "status": "ok", "model": {"used": True}},
                {"job": "query_expansion", "status": "ok", "model": {"used": False}},
            ],
        },
        evals_latest={
            "ok": True,
            "status": "ok",
            "generated_at": "2026-05-19T10:02:00+00:00",
            "summary": {
                "overall_score": 1.0,
                "families": {"schema_eval": {"status": "ok", "score": 1.0}},
                "checks": 29,
                "fails": 0,
                "warnings": 0,
                "source_id_pass_ratio": 1.0,
                "average_candidate_utility": 0.76,
            },
            "scorecard": {
                "degraded_jobs": [
                    {
                        "job": "daily_work_blocks",
                        "status": "ok_degraded",
                        "model": {
                            "used": True,
                            "fallback_used": False,
                            "policy": {"decision": "degraded", "primary_reason": "memory_watch"},
                        },
                    }
                ]
            },
        },
        evals_validate={
            "ok": True,
            "generated_at": "2026-05-19T10:02:30+00:00",
            "summary": {"fails": 0, "warnings": 0, "checks": 5, "eval_status": "ok", "overall_score": 1.0},
        },
        policy_latest={
            "decision": "allow",
            "primary_reason": "policy_allow",
            "generated_at": "2026-05-19T10:02:10+00:00",
            "request": {"class": "job", "job": "thermal_performance"},
        },
        previous_latest={
            "e2b_breath": {
                "candidate_delta": {
                    "current": [
                        {"candidate_id": "cand-persist", "heartbeat_priority": 1},
                        {"candidate_id": "cand-cleared", "heartbeat_priority": 3},
                    ]
                }
            }
        },
        rhythm={"next_beat_at": "Tue 2026-05-19 10:17:00 CST"},
        generated_at="2026-05-19T10:02:30+00:00",
    )

    assert result["schema"] == "abyss_machine_heartbeat_e2b_breath_v1"
    assert result["pulse_state"] == "review_needed"
    assert result["candidate_delta"]["schema"] == "abyss_machine_heartbeat_e2b_candidate_delta_v1"
    assert result["candidate_delta"]["summary"]["current"] == 2
    assert result["candidate_delta"]["summary"]["new"] == 1
    assert result["candidate_delta"]["summary"]["cleared"] == 1
    assert result["candidate_delta"]["summary"]["persistent"] == 1
    assert result["candidate_delta"]["summary"]["escalated"] == 1
    assert result["operator_attention"]["count"] == 1
    assert result["operator_attention"]["e4b_review_candidates"] == 1
    assert result["resident_quality"]["overall_score"] == 1.0
    assert result["resident_quality"]["source_id_pass_ratio"] == 1.0
    assert result["degradation_reason"]["status"] == "historical_not_current"
    assert result["e2b_staleness"]["status"] == "fresh"
    assert result["state_flags"]["review_needed"] is True
    assert "new:1" in result["what_changed"]
    assert "cleared:1" in result["what_changed"]
    assert "operator_attention:1" in result["why_now"]
    assert result["policy"]["action_execution"] is False
    assert result["policy"]["does_not_run_model"] is True
    assert result["policy"]["does_not_run_jobs_batch"] is True


def test_heartbeat_e2b_breath_prefers_selected_candidate_queues(abyss_machine_module) -> None:
    selected = {
        "candidate_id": "cand-selected",
        "kind": "action_card",
        "source_job": "action_card_compiler",
        "source_ids": ["src-selected"],
        "title": "selected action",
        "route": "operator_review",
        "risk": "medium",
        "review_required": True,
        "utility_score": 0.55,
        "selection_score": 0.88,
        "selection_tier": "operator_attention",
        "selection_lane": "operator_action",
        "selection_reasons": ["review_required", "operator_value"],
        "correctness_risk": "medium",
        "freshness_class": "fresh",
        "heartbeat_priority": 3,
        "e4b_review_eligible": True,
        "source_generated_at": "2026-05-19T10:01:30+00:00",
        "artifact_age_sec": 30,
        "expires_at": "2026-05-19T16:00:00+00:00",
    }
    background = {
        "candidate_id": "cand-background",
        "kind": "source_quality",
        "source_job": "source_quality_scorer",
        "source_ids": ["src-background"],
        "title": "usable",
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
        "source_generated_at": "2026-05-19T10:01:30+00:00",
        "artifact_age_sec": 30,
        "expires_at": "2026-05-19T16:00:00+00:00",
    }

    result = abyss_machine_module.heartbeat_e2b_breath_from(
        candidates_latest={
            "ok": True,
            "generated_at": "2026-05-19T10:02:00+00:00",
            "selection": {"schema": "abyss_machine_gemma4_spark_resident_candidate_selection_v1"},
            "candidates": [background, selected],
            "queues": {"selected_for_heartbeat": [selected], "selected_for_e4b_review": [selected]},
            "source_jobs": [{"job": "action_card_compiler", "status": "ok", "model": {"used": True}}],
        },
        evals_latest={
            "ok": True,
            "status": "ok",
            "generated_at": "2026-05-19T10:02:00+00:00",
            "summary": {"overall_score": 1.0, "source_id_pass_ratio": 1.0, "average_candidate_selection": 0.65},
        },
        evals_validate={"ok": True, "generated_at": "2026-05-19T10:02:30+00:00", "summary": {"fails": 0}},
        policy_latest={"decision": "allow", "generated_at": "2026-05-19T10:02:10+00:00"},
        previous_latest=None,
        rhythm={"next_beat_at": "Tue 2026-05-19 10:17:00 CST"},
        generated_at="2026-05-19T10:02:30+00:00",
    )

    assert result["candidate_delta"]["summary"]["current"] == 1
    assert result["candidate_delta"]["summary"]["all_heartbeat_candidates"] == 2
    assert result["candidate_delta"]["summary"]["selected_for_heartbeat"] == 1
    assert result["candidate_delta"]["current"][0]["candidate_id"] == "cand-selected"
    assert result["candidate_delta"]["current"][0]["selection_tier"] == "operator_attention"
    assert result["candidate_delta"]["current"][0]["selection_lane"] == "operator_action"
    assert result["operator_attention"]["count"] == 1
    assert result["operator_attention"]["selected_for_e4b_review"] == 1
    assert result["operator_attention"]["top"][0]["candidate_id"] == "cand-selected"


def test_heartbeat_e2b_breath_marks_current_fallback_as_blocked(abyss_machine_module) -> None:
    result = abyss_machine_module.heartbeat_e2b_breath_from(
        candidates_latest={"ok": True, "candidates": [], "source_jobs": []},
        evals_latest={"ok": True, "status": "ok", "summary": {"overall_score": 1.0}},
        evals_validate={"ok": True, "summary": {"fails": 0}},
        policy_latest={
            "decision": "fallback",
            "primary_reason": "game_guard_active",
            "generated_at": "2026-05-19T10:02:10+00:00",
            "request": {"class": "job"},
        },
        previous_latest=None,
        rhythm={"next_beat_at": "Tue 2026-05-19 10:17:00 CST"},
        generated_at="2026-05-19T10:02:30+00:00",
    )

    assert result["pulse_state"] == "blocked"
    assert result["degradation_reason"]["status"] == "current"
    assert result["degradation_reason"]["reason"] == "game_guard_active"
    assert "current_degradation:fallback:game_guard_active" in result["what_changed"]
    assert result["policy"]["executes_candidates"] is False


def test_workhorse_harness_rejects_disallowed_source_ids() -> None:
    harness = _load_workhorse_harness()
    pack = {
        "summary": {"items": 1, "action_candidates": 0},
        "allowed_source_ids": ["src-1"],
    }
    review = {
        "source_ids": ["src-2"],
        "review_items": [{"source_id": "src-2", "candidate_id": "cand-1", "decision": "review_candidate", "reason": "bad source"}],
        "action_cards": [],
        "risk_routes": [],
        "verdict": "candidate_review_ready",
        "action_execution": False,
    }

    failed = {item["key"] for item in harness.review_checks(review, pack) if item.get("level") == "fail"}

    assert "source_ids_allowed" in failed
    assert "review_items_sourceful" in failed


def test_workhorse_harness_rejects_hollow_action_cards() -> None:
    harness = _load_workhorse_harness()
    pack = {
        "summary": {"items": 1, "action_candidates": 1},
        "allowed_source_ids": ["src-1"],
    }
    review = {
        "source_ids": ["src-1"],
        "review_items": [{"source_id": "src-1", "candidate_id": "cand-1", "decision": "review_candidate", "reason": "needs action card"}],
        "action_cards": [],
        "risk_routes": [],
        "verdict": "candidate_review_ready",
        "action_execution": False,
    }

    failed = {item["key"] for item in harness.review_checks(review, pack) if item.get("level") == "fail"}

    assert "no_hollow_action_card" in failed


def test_workhorse_review_response_profile_is_owner_gated(abyss_machine_module) -> None:
    profile = abyss_machine_module.response_command_profile("abyss-machine ai llm workhorse review --json")

    assert profile["kind"] == "owner_gated_ai_hygiene_review"
    assert profile["scope"] == "ai_hygiene"
    assert profile["mutating_if_run"] is False
    assert profile["requires_operator"] is True
