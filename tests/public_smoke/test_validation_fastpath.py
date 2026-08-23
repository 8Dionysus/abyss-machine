from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import scripts.validation_fastpath as fastpath
from scripts.validation_fastpath import FULL_GATE_ID, build_plan, candidate_identity, make_receipt


REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_RESOURCE = {
    "admission": "allow",
    "class": "light",
    "kind": "agent",
    "latency": "interactive",
    "activity": "foreground",
    "source": "test-fixture",
}


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True, text=True)


def _fixture_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "fixture-repo"
    (repo_root / "src/abyss_machine").mkdir(parents=True)
    (repo_root / "tests/public_smoke").mkdir(parents=True)
    (repo_root / "docs/validation").mkdir(parents=True)
    (repo_root / "src/abyss_machine/module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "tests/public_smoke/test_module.py").write_text("def test_module():\n    assert True\n", encoding="utf-8")
    (repo_root / "pytest.ini").write_text("[pytest]\ntestpaths = tests/public_smoke\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text("ignored-input.txt\n", encoding="utf-8")
    (repo_root / "docs/validation/validation_lanes.json").write_text("{}\n", encoding="utf-8")
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "fastpath@example.invalid")
    _git(repo_root, "config", "user.name", "fastpath-test")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-qm", "fixture")
    return repo_root


def _step(node: dict[str, object], *, ok: bool) -> dict[str, object]:
    empty_hash = hashlib.sha256(b"").hexdigest()
    return {
        "node_id": node["node_id"],
        "command": list(node["command"]),
        "ok": ok,
        "returncode": 0 if ok else 1,
        "timed_out": False,
        "elapsed_sec": 0.01,
        "children_max_rss_kib": 1,
        "rss_measurement": {
            "method": "test",
            "scope": "direct_child_pid",
            "status": "measured",
            "peak_rss_kib": 1,
        },
        "stdout_sha256": empty_hash,
        "stderr_sha256": empty_hash,
        "stdout_tail": "",
        "stderr_tail": "",
        "stdout_bytes": 0,
        "stderr_bytes": 0,
        "error": None,
    }


def _execution(repo_root: Path, plan: dict[str, object], steps: list[dict[str, object]], *, ok: bool) -> dict[str, object]:
    environment = fastpath._environment_identity(
        repo_root,
        fastpath._execution_environment(repo_root),
        python_executable=str(plan["python_executable"]),
    )
    for step in steps:
        step["environment_sha256"] = environment["identity_sha256"]
    nodes = [
        plan["selected"][0] if step["node_id"] != FULL_GATE_ID else plan["full_gate"]["node"]
        for step in steps
    ]
    return {
        "status": "completed",
        "resource_admission": "allow",
        "resource_decision": dict(VALID_RESOURCE),
        "resource_decision_sha256": fastpath._digest_value(VALID_RESOURCE),
        "environment": environment,
        "command_graph_sha256": fastpath._command_graph_digest(nodes),
        "steps": steps,
        "ok": ok,
        "reason": None,
    }


def test_mapped_source_surface_selects_contextual_node_and_keeps_full_gate_required(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)

    assert [node["node_id"] for node in plan["selected"]] == [
        "public-smoke:tests/public_smoke/test_module.py"
    ]
    assert plan["fallback"]["required"] is False
    assert plan["full_gate"]["required"] is True
    assert plan["full_gate"]["status"] == "not_run"


@pytest.mark.parametrize(
    "path",
    [
        "tests/public_smoke/test_validation_fastpath.py",
        "scripts/validation_fastpath.py",
        "scripts/validation_lanes.py",
        "scripts/validators/public_boundary.py",
        "docs/validation/validation_lanes.json",
    ],
)
def test_tests_validators_policy_and_runner_surfaces_expand_to_full_gate(path: str) -> None:
    plan = build_plan([path], REPO_ROOT)

    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True
    assert plan["fallback"]["node_id"] == FULL_GATE_ID
    assert plan["unmapped_reasons"][path]


def test_unknown_surface_expands_instead_of_being_silently_skipped() -> None:
    plan = build_plan(["schemas/new_validation_schema.json"], REPO_ROOT)

    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True
    assert plan["unmapped_paths"] == ["schemas/new_validation_schema.json"]
    assert "unknown_or_high_risk_surface" in plan["skipped"][0]["reason"]


def test_empty_plan_is_non_success_and_requires_full_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan([], repo_root)
    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True

    monkeypatch.setattr(fastpath, "_run_node", lambda repo, node, timeout, **kwargs: _step(node, ok=True))
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    assert [step["node_id"] for step in execution["steps"]] == [FULL_GATE_ID]
    assert execution["ok"] is True

    identity = candidate_identity(repo_root, "HEAD", "HEAD")
    plan_only = {
        "status": "plan_only",
        "resource_admission": "allow",
        "resource_decision": dict(VALID_RESOURCE),
        "resource_decision_sha256": fastpath._digest_value(VALID_RESOURCE),
        "steps": [],
        "ok": False,
        "reason": "plan_only_does_not_execute_validation",
    }
    receipt = make_receipt(repo_root, identity, plan, plan_only)
    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "plan_only"


def test_fastpath_receipt_is_candidate_only_when_contextual_steps_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    monkeypatch.setattr(fastpath, "_run_node", lambda repo, node, timeout, **kwargs: _step(node, ok=True))
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    receipt = make_receipt(repo_root, candidate_identity(repo_root, "HEAD", "HEAD"), plan, execution)

    assert receipt["ok"] is True
    assert receipt["proof"]["status"] == "contextual_candidate_passed"
    assert receipt["proof"]["full_gate_required"] is True
    assert receipt["proof"]["owner_acceptance"] is False
    assert receipt["cache"]["receipt_reuse"] == "not_implemented"
    assert receipt["resource"]["decision"] == VALID_RESOURCE
    assert receipt["resource"]["decision_sha256"] == fastpath._digest_value(VALID_RESOURCE)


def test_mixed_contextual_failure_is_not_masked_by_passing_full_gate(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    selected_step = _step(plan["selected"][0], ok=False)
    full_step = _step(plan["full_gate"]["node"], ok=True)
    execution = _execution(repo_root, plan, [selected_step, full_step], ok=False)
    receipt = make_receipt(repo_root, candidate_identity(repo_root, "HEAD", "HEAD"), plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "required_step_failed"
    assert receipt["proof"]["full_gate_status"] == "passed"
    assert receipt["proof"]["selected_failures"] == [selected_step["node_id"]]


def test_dirty_index_and_worktree_inputs_are_bound_and_force_full_gate(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    tracked = repo_root / "src/abyss_machine/module.py"
    tracked.write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo_root, "add", str(tracked.relative_to(repo_root)))
    staged_identity = candidate_identity(repo_root, "HEAD", "HEAD")
    tracked.write_text("VALUE = 3\n", encoding="utf-8")
    combined_identity = candidate_identity(repo_root, "HEAD", "HEAD")

    assert staged_identity["worktree_state"] == "dirty"
    assert staged_identity["staged_content_sha256"] != staged_identity["unstaged_content_sha256"]
    assert combined_identity["staged_content_sha256"] == staged_identity["staged_content_sha256"]
    assert combined_identity["unstaged_content_sha256"] != staged_identity["unstaged_content_sha256"]
    assert combined_identity["worktree_content_sha256"] != staged_identity["worktree_content_sha256"]

    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    fastpath._force_full_gate_for_dirty_worktree(plan, combined_identity)
    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True
    assert "staged_content_sha256" in plan["skipped"][-1]["identity_fields"]


def test_untracked_and_ignored_inputs_change_the_bound_identity(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    clean_identity = candidate_identity(repo_root, "HEAD", "HEAD")
    (repo_root / "untracked-input.txt").write_text("untracked\n", encoding="utf-8")
    (repo_root / "ignored-input.txt").write_text("ignored\n", encoding="utf-8")
    dirty_identity = candidate_identity(repo_root, "HEAD", "HEAD")

    assert clean_identity["worktree_state"] == "clean"
    assert dirty_identity["worktree_state"] == "dirty"
    assert dirty_identity["untracked_content_sha256"] != clean_identity["untracked_content_sha256"]
    assert dirty_identity["ignored_content_sha256"] != clean_identity["ignored_content_sha256"]


def test_incomplete_resource_admission_cannot_execute(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_admission="allow")

    assert execution["status"] == "not_run_resource_decision"
    assert execution["steps"] == []
    assert execution["ok"] is False


def test_resource_receipt_binds_complete_caller_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    monkeypatch.setattr(fastpath, "_run_node", lambda repo, node, timeout, **kwargs: _step(node, ok=True))
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    receipt = make_receipt(repo_root, candidate_identity(repo_root, "HEAD", "HEAD"), plan, execution)

    assert receipt["resource"]["validation"] == "passed"
    assert receipt["resource"]["class"] == VALID_RESOURCE["class"]
    assert receipt["resource"]["kind"] == VALID_RESOURCE["kind"]
    assert receipt["resource"]["latency"] == VALID_RESOURCE["latency"]
    assert receipt["resource"]["activity"] == VALID_RESOURCE["activity"]


def test_identity_plan_and_environment_substitution_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    monkeypatch.setattr(fastpath, "_run_node", lambda repo, node, timeout, **kwargs: _step(node, ok=True))
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    identity = candidate_identity(repo_root, "HEAD", "HEAD")

    tampered_identity = dict(identity)
    tampered_identity["candidate_tree"] = "tree-substitution"
    with pytest.raises(fastpath.ValidationInputError):
        make_receipt(repo_root, tampered_identity, plan, execution)

    tampered_plan = deepcopy(plan)
    tampered_plan["selected"][0]["claims"] = ["unrelated claim"]
    with pytest.raises(fastpath.ValidationInputError):
        make_receipt(repo_root, identity, tampered_plan, execution)

    tampered_execution = deepcopy(execution)
    tampered_execution["environment"] = dict(tampered_execution["environment"])
    tampered_execution["environment"]["effective_environment_sha256"] = "environment-substitution"
    receipt = make_receipt(repo_root, identity, plan, tampered_execution)
    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"

    tampered_resource = deepcopy(execution)
    tampered_resource["resource_decision_sha256"] = "resource-substitution"
    receipt = make_receipt(repo_root, identity, plan, tampered_resource)
    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"

    tampered_plan = deepcopy(plan)
    tampered_plan["full_gate"]["node"]["command"] = ["false"]
    tampered_plan["plan_sha256"] = fastpath._plan_digest(tampered_plan)
    with pytest.raises(fastpath.ValidationInputError, match="routing or command binding"):
        make_receipt(repo_root, identity, tampered_plan, execution)


def test_receipt_rejects_a_completed_execution_that_omits_a_planned_step(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)
    execution = _execution(repo_root, plan, [], ok=False)
    receipt = make_receipt(repo_root, candidate_identity(repo_root, "HEAD", "HEAD"), plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any("exact planned node sequence" in error for error in receipt["proof"]["execution_validation_errors"])


def test_receipt_output_is_task_local_atomic_and_non_overwriting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    target = fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "{}\n")
    assert target == receipt_root / "result.json"
    assert json.loads(target.read_text(encoding="utf-8")) == {}

    with pytest.raises(fastpath.ReceiptPathError, match="already exists"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "tampered\n")
    with pytest.raises(fastpath.ReceiptPathError, match="escapes"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("../escape.json"), "{}\n")
    with pytest.raises(fastpath.ReceiptPathError, match="source checkout"):
        fastpath.write_receipt_atomic(REPO_ROOT, REPO_ROOT / "pytest.ini", "tampered\n")
    assert (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8").startswith("[pytest]")


def test_run_node_bounds_output_and_measures_one_child() -> None:
    output_node = {
        "node_id": "large-output",
        "command": [sys.executable, "-c", "print('x' * 10000)"],
    }
    result = fastpath._run_node(REPO_ROOT, output_node, timeout_sec=3.0)

    assert result["ok"] is True
    assert len(result["stdout_tail"]) <= fastpath.MAX_OUTPUT_CHARS
    assert result["stdout_bytes"] > fastpath.MAX_OUTPUT_CHARS
    assert result["rss_measurement"]["scope"] == "direct_child_pid"
    assert result["stdout_sha256"] == hashlib.sha256(("x" * 10000 + "\n").encode()).hexdigest()


@pytest.mark.parametrize(
    ("node_id", "command", "error_type"),
    [
        ("spawn-failure", ["/path/that/does/not/exist"], "spawn_error"),
        ("decode-failure", [sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([255]))"], "decode_error"),
        ("timeout-failure", [sys.executable, "-c", "import time; time.sleep(1)"], "timeout"),
    ],
)
def test_run_node_converts_launch_decode_and_timeout_failures_to_receipts(
    node_id: str,
    command: list[str],
    error_type: str,
) -> None:
    result = fastpath._run_node(REPO_ROOT, {"node_id": node_id, "command": command}, timeout_sec=0.05)

    assert result["ok"] is False
    assert result["error"]["type"] == error_type
    assert len(result["stdout_tail"]) <= fastpath.MAX_OUTPUT_CHARS
