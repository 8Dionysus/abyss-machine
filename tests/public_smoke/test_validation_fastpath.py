from __future__ import annotations

from pathlib import Path

from scripts.validation_fastpath import FULL_GATE_ID, build_plan, make_receipt


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_mapped_surface_selects_exact_contextual_node_and_keeps_full_gate_required() -> None:
    plan = build_plan(["src/abyss_machine/validation_contracts.py"], REPO_ROOT)

    assert [node["node_id"] for node in plan["selected"]] == [
        "public-smoke:tests/public_smoke/test_validation_contracts.py"
    ]
    assert plan["fallback"]["required"] is False
    assert plan["full_gate"]["required"] is True
    assert plan["full_gate"]["status"] == "not_run"
    assert plan["selected"][0]["evidence_class"] == "public-source-contextual"


def test_unknown_surface_expands_instead_of_being_silently_skipped() -> None:
    plan = build_plan(["schemas/new_validation_schema.json"], REPO_ROOT)

    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True
    assert plan["fallback"]["node_id"] == FULL_GATE_ID
    assert plan["unmapped_paths"] == ["schemas/new_validation_schema.json"]
    assert "unknown_or_high_risk_surface" in plan["skipped"][0]["reason"]


def test_fastpath_receipt_is_candidate_only_even_when_contextual_steps_pass() -> None:
    plan = build_plan(["src/abyss_machine/validation_contracts.py"], REPO_ROOT)
    execution = {
        "status": "completed",
        "resource_admission": "allow",
        "steps": [
            {
                "node_id": plan["selected"][0]["node_id"],
                "ok": True,
                "returncode": 0,
                "elapsed_sec": 0.12,
            }
        ],
        "ok": True,
        "reason": None,
    }
    receipt = make_receipt(
        REPO_ROOT,
        {
            "base_ref": "base",
            "candidate_ref": "candidate",
            "candidate_sha": "sha-candidate",
            "candidate_tree": "tree-candidate",
            "worktree_state": "clean",
        },
        plan,
        execution,
    )

    assert receipt["ok"] is True
    assert receipt["proof"]["status"] == "contextual_candidate_passed"
    assert receipt["proof"]["full_gate_required"] is True
    assert receipt["proof"]["owner_acceptance"] is False
    assert receipt["cache"]["receipt_reuse"] == "not_implemented"
    assert receipt["resource"]["admission"] == "allow"


def test_no_resource_admission_never_starts_a_selected_node() -> None:
    plan = build_plan(["src/abyss_machine/validation_contracts.py"], REPO_ROOT)

    from scripts.validation_fastpath import execute_plan

    execution = execute_plan(REPO_ROOT, plan, resource_admission="not-provided")

    assert execution["status"] == "not_run_resource_admission"
    assert execution["steps"] == []
    assert execution["ok"] is False


def test_plan_only_receipt_does_not_claim_a_test_passed() -> None:
    plan = build_plan(["src/abyss_machine/validation_contracts.py"], REPO_ROOT)
    receipt = make_receipt(
        REPO_ROOT,
        {"worktree_state": "clean"},
        plan,
        {
            "status": "plan_only",
            "resource_admission": "allow",
            "steps": [],
            "ok": True,
            "reason": None,
        },
    )

    assert receipt["proof"]["status"] == "plan_only"
    assert receipt["proof"]["full_gate_required"] is True
