from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

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
    (repo_root / "scripts").mkdir(parents=True)
    (repo_root / "src/abyss_machine/module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo_root / "tests/public_smoke/test_module.py").write_text("def test_module():\n    assert True\n", encoding="utf-8")
    (repo_root / "pytest.ini").write_text("[pytest]\ntestpaths = tests/public_smoke\n", encoding="utf-8")
    (repo_root / ".gitignore").write_text("ignored-input.txt\n", encoding="utf-8")
    (repo_root / "docs/validation/validation_lanes.json").write_text("{}\n", encoding="utf-8")
    (repo_root / "scripts/ci_gate.py").write_text(
        "print('full-gate-ran')\n",
        encoding="utf-8",
    )
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
        "timing": {
            "execution_timeout_sec": 1.0,
            "cleanup_safety_window_sec": fastpath.PROCESS_CLEANUP_WINDOW_SEC,
            "performance_target_sec": fastpath.FAST_NODE_BUDGET_SEC,
            "measurement_scope": "node_wall_including_launch_identity_and_cleanup",
            "excluded_intervals_sec": 0.0,
            "classification": "fast",
            "target_met": True,
        },
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
        "cleanup": {
            "process_group": "isolated",
            "process_group_termination_attempted": False,
            "process_group_alive": False,
            "process_terminated": True,
            "reader_threads_alive": [],
            "descendant_processes_alive": [],
            "descendant_cleanup_attempted": True,
            "errors": [],
        },
        "cleanup_errors": [],
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
        "timeout_sec": 1.0,
        "environment": environment,
        "command_graph_sha256": fastpath._command_graph_digest(nodes),
        "steps": steps,
        "ok": ok,
        "reason": None,
    }


def _executed_step(repo_root: Path, node: dict[str, object], *, timeout_sec: float = 1.0) -> dict[str, object]:
    environment = fastpath._environment_identity(
        repo_root,
        fastpath._execution_environment(repo_root),
        python_executable=str(fastpath._owner_python_executable()),
    )
    return fastpath._run_node(
        repo_root,
        node,
        timeout_sec=timeout_sec,
        env=fastpath._execution_environment(repo_root),
        environment_identity=environment,
    )


def _candidate_plan(repo_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    _commit_source_change(repo_root, "VALUE = 2\n")
    base_ref = "HEAD^"
    candidate_ref = "HEAD"
    paths = fastpath.changed_paths(repo_root, base_ref, candidate_ref)
    plan = build_plan(paths, repo_root)
    identity = candidate_identity(repo_root, base_ref, candidate_ref)
    return plan, identity


def _commit_source_change(repo_root: Path, content: str) -> None:
    (repo_root / "src/abyss_machine/module.py").write_text(content, encoding="utf-8")
    _git(repo_root, "add", "src/abyss_machine/module.py", "tests/public_smoke/test_module.py")
    _git(repo_root, "commit", "-qm", "candidate")


def _run_cli(repo_root: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/validation_fastpath.py"),
        "--repo",
        str(repo_root),
        "--base",
        "HEAD^",
        "--candidate",
        "HEAD",
        "--resource-decision",
        json.dumps(VALID_RESOURCE, sort_keys=True),
        *args,
    ]
    result = subprocess.run(command, cwd=repo_root, check=False, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return result, payload


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


def test_empty_plan_is_non_success_and_requires_full_gate(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan([], repo_root)
    assert plan["selected"] == []
    assert plan["fallback"]["required"] is True

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


def test_fastpath_receipt_is_candidate_only_when_contextual_steps_pass(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is True
    assert receipt["proof"]["status"] == "contextual_candidate_passed"
    assert receipt["proof"]["full_gate_required"] is True
    assert receipt["proof"]["owner_acceptance"] is False
    assert receipt["cache"]["receipt_reuse"] == "not_implemented"
    assert receipt["resource"]["decision"] == VALID_RESOURCE
    assert receipt["resource"]["decision_sha256"] == fastpath._digest_value(VALID_RESOURCE)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda step: step.update(returncode=7),
        lambda step: step.update(error={"type": "synthetic", "detail": "forged failure"}),
        lambda step: step.update(timed_out=True, returncode=124, error={"type": "timeout", "detail": "forged timeout"}),
    ],
)
def test_receipt_rejects_contradictory_step_outcomes(tmp_path: Path, mutate) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    step = _step(plan["selected"][0], ok=True)
    mutate(step)
    execution = _execution(repo_root, plan, [step], ok=True)

    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any("inconsistent" in error for error in receipt["proof"]["execution_validation_errors"])


@pytest.mark.parametrize("timeout_sec", [0, -1, float("nan"), float("inf")])
def test_execute_plan_rejects_nonfinite_or_nonpositive_timeout(tmp_path: Path, timeout_sec: float) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan = build_plan(["src/abyss_machine/module.py"], repo_root)

    with pytest.raises(fastpath.ValidationInputError, match="finite positive"):
        fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE, timeout_sec=timeout_sec)


def test_cli_run_full_is_forwarded_and_executed_end_to_end(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    _commit_source_change(repo_root, "VALUE = 2\n")

    result, receipt = _run_cli(repo_root, "--run-full", "--timeout-sec", "2")

    assert result.returncode == 0, result.stderr
    assert [step["node_id"] for step in receipt["execution"]["steps"]] == [
        "public-smoke:tests/public_smoke/test_module.py",
        FULL_GATE_ID,
    ]
    assert receipt["execution"]["timeout_sec"] == 2.0
    assert receipt["proof"]["full_gate_status"] == "passed"
    assert receipt["execution"]["steps"][1]["stdout_tail"].strip() == "full-gate-ran"


def test_cli_timeout_is_forwarded_and_bounds_selected_child(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    (repo_root / "tests/public_smoke/test_module.py").write_text(
        "import time\n\ndef test_module():\n    time.sleep(0.2)\n",
        encoding="utf-8",
    )
    _commit_source_change(repo_root, "VALUE = 2\n")

    result, receipt = _run_cli(repo_root, "--timeout-sec", "0.01")

    assert result.returncode == 1
    step = receipt["execution"]["steps"][0]
    assert step["timed_out"] is True
    assert step["returncode"] == 124
    assert step["error"]["type"] == "timeout"
    assert receipt["execution"]["timeout_sec"] == 0.01
    assert receipt["proof"]["status"] == "required_step_failed"


@pytest.mark.parametrize("timeout_text", ["0", "-1", "nan", "inf"])
def test_cli_rejects_invalid_timeout_before_plan_or_execution(tmp_path: Path, timeout_text: str) -> None:
    repo_root = _fixture_repo(tmp_path)

    result, payload = _run_cli(repo_root, "--plan-only", "--timeout-sec", timeout_text)

    assert result.returncode == 1
    assert payload["ok"] is False
    assert "finite positive" in payload["error"]


def test_mixed_contextual_failure_is_not_masked_by_passing_full_gate(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    selected_step = _step(plan["selected"][0], ok=False)
    full_step = _step(plan["full_gate"]["node"], ok=True)
    execution = _execution(repo_root, plan, [selected_step, full_step], ok=False)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert receipt["proof"]["full_gate_status"] == "failed"
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


def test_resource_receipt_binds_complete_caller_decision(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["resource"]["validation"] == "passed"
    assert receipt["resource"]["class"] == VALID_RESOURCE["class"]
    assert receipt["resource"]["kind"] == VALID_RESOURCE["kind"]
    assert receipt["resource"]["latency"] == VALID_RESOURCE["latency"]
    assert receipt["resource"]["activity"] == VALID_RESOURCE["activity"]


def test_identity_plan_and_environment_substitution_is_rejected(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
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
    plan, identity = _candidate_plan(repo_root)
    execution = _execution(repo_root, plan, [], ok=False)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any("exact planned node sequence" in error for error in receipt["proof"]["execution_validation_errors"])


def test_receipt_rejects_missing_timeout_and_cleanup_envelope(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [step], ok=True)
    execution.pop("timeout_sec")
    execution.pop("environment")
    step.pop("cleanup")
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any("timeout_sec is required" in error for error in receipt["proof"]["execution_validation_errors"])
    assert any("environment envelope is required" in error for error in receipt["proof"]["execution_validation_errors"])
    assert any("cleanup envelope is required" in error for error in receipt["proof"]["execution_validation_errors"])


def test_receipt_cross_binds_cleanup_error_channels(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    step = _step(plan["selected"][0], ok=True)
    step["cleanup_errors"] = ["synthetic cleanup failure"]
    execution = _execution(repo_root, plan, [step], ok=True)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert any("cleanup error channels do not match" in error for error in receipt["proof"]["execution_validation_errors"])


def test_completed_execution_with_denied_admission_cannot_be_green(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [step], ok=True)
    denied = dict(VALID_RESOURCE, admission="deny")
    execution["resource_admission"] = "deny"
    execution["resource_decision"] = denied
    execution["resource_decision_sha256"] = fastpath._digest_value(denied)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert any("requires resource admission=allow" in error for error in receipt["proof"]["execution_validation_errors"])


@pytest.mark.parametrize("elapsed_sec", [float("nan"), float("inf"), float("-inf")])
def test_receipt_rejects_nonfinite_step_timing(tmp_path: Path, elapsed_sec: float) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    step = _step(plan["selected"][0], ok=True)
    step["elapsed_sec"] = elapsed_sec
    execution = _execution(repo_root, plan, [step], ok=True)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert any("elapsed_sec is invalid" in error for error in receipt["proof"]["execution_validation_errors"])


def test_candidate_ref_must_match_executed_head(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    _commit_source_change(repo_root, "VALUE = 2\n")
    candidate_ref = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    base_ref = subprocess.run(
        ["git", "rev-parse", "HEAD^"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.strip()
    paths = fastpath.changed_paths(repo_root, base_ref, candidate_ref)
    plan = build_plan(paths, repo_root)
    identity = candidate_identity(repo_root, base_ref, candidate_ref)
    _git(repo_root, "checkout", "-q", "--detach", base_ref)
    step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [step], ok=True)

    with pytest.raises(fastpath.ValidationInputError, match="executed worktree HEAD"):
        make_receipt(repo_root, identity, plan, execution)


def test_plan_changed_paths_must_match_exact_candidate_diff(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    tampered_plan = deepcopy(plan)
    tampered_plan["changed_paths"] = ["src/abyss_machine/fake.py"]
    tampered_plan["plan_sha256"] = fastpath._plan_digest(tampered_plan)
    step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [step], ok=True)

    with pytest.raises(fastpath.ValidationInputError, match="exact base/candidate Git diff"):
        make_receipt(repo_root, identity, tampered_plan, execution)


def test_full_gate_rejects_interpreter_substitution(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    tampered_plan = deepcopy(plan)
    tampered_plan["python_executable"] = "/bin/true"
    tampered_plan["python_executable_sha256"] = fastpath._sha256(Path("/bin/true"))
    tampered_plan["full_gate"]["node"]["command"][0] = "/bin/true"
    tampered_plan["plan_sha256"] = fastpath._plan_digest(tampered_plan)
    step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [step], ok=True)

    with pytest.raises(fastpath.ValidationInputError, match="owner interpreter"):
        make_receipt(repo_root, identity, tampered_plan, execution)


@pytest.mark.parametrize("node_kind", ["selected", "full_gate"])
def test_successful_not_started_step_cannot_make_receipt_green(tmp_path: Path, node_kind: str) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    node = plan["full_gate"]["node"] if node_kind == "full_gate" else plan["selected"][0]
    step = _step(node, ok=True)
    step["cleanup"]["process_group"] = "not_started"
    steps = [step]
    if node_kind == "full_gate":
        steps.insert(0, _step(plan["selected"][0], ok=True))
    execution = _execution(repo_root, plan, steps, ok=True)

    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any(
        "successful step does not prove that a process started" in error
        for error in receipt["proof"]["execution_validation_errors"]
    )
    if node_kind == "full_gate":
        assert receipt["proof"]["full_gate_status"] == "failed"


def test_caller_constructed_isolated_success_cannot_make_receipt_green(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    forged_step = _step(plan["selected"][0], ok=True)
    execution = _execution(repo_root, plan, [forged_step], ok=True)

    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert any("not minted by _run_node" in error for error in receipt["proof"]["execution_validation_errors"])


def test_serialized_runner_result_cannot_be_reused_as_execution_authority(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    serialized_execution = json.loads(json.dumps(execution))

    receipt = make_receipt(repo_root, identity, plan, serialized_execution)

    assert receipt["ok"] is False
    assert any("not minted by _run_node" in error for error in receipt["proof"]["execution_validation_errors"])


def test_runner_result_is_single_use_and_replay_is_rejected(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)

    first = make_receipt(repo_root, identity, plan, execution)
    replay = make_receipt(repo_root, identity, plan, execution)

    assert first["ok"] is True
    assert replay["ok"] is False
    assert any("not minted by _run_node" in error for error in replay["proof"]["execution_validation_errors"])


def test_runner_origin_uses_atomic_snapshot_against_concurrent_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    execution = fastpath.execute_plan(repo_root, plan, resource_decision=VALID_RESOURCE)
    original_elapsed = execution["steps"][0]["elapsed_sec"]
    original_validate = fastpath._runner_origin_errors

    def validate_then_mutate(index: int, step: dict[str, object]) -> list[str]:
        errors = original_validate(index, step)

        def mutate() -> None:
            step["elapsed_sec"] = 0.000001
            timing = dict(step["timing"])
            timing["classification"] = "fast"
            timing["target_met"] = True
            step["timing"] = timing

        mutation = threading.Thread(target=mutate)
        mutation.start()
        mutation.join()
        return errors

    monkeypatch.setattr(fastpath, "_runner_origin_errors", validate_then_mutate)
    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is True
    assert receipt["execution"]["steps"][0]["elapsed_sec"] == original_elapsed


def test_low_level_runner_rejects_environment_label_forgery(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, _identity = _candidate_plan(repo_root)
    python_executable = str(plan["python_executable"])
    effective_env = fastpath._execution_environment(repo_root)
    forged_env = dict(effective_env)
    forged_env["FASTPATH_FORGED_ENVIRONMENT"] = "1"
    claimed_identity = fastpath._environment_identity(
        repo_root,
        effective_env,
        python_executable=python_executable,
    )

    result = fastpath._run_node(
        repo_root,
        plan["selected"][0],
        timeout_sec=2.0,
        env=forged_env,
        environment_identity=claimed_identity,
        python_executable=python_executable,
    )
    actual_identity = fastpath._environment_identity(
        repo_root,
        forged_env,
        python_executable=python_executable,
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "environment_identity"
    assert result["environment_sha256"] == actual_identity["identity_sha256"]
    assert result["environment_sha256"] != claimed_identity["identity_sha256"]


def test_full_gate_status_cannot_be_green_when_execution_identity_fails(tmp_path: Path) -> None:
    repo_root = _fixture_repo(tmp_path)
    plan, identity = _candidate_plan(repo_root)
    selected = _executed_step(repo_root, plan["selected"][0])
    full_gate = _executed_step(repo_root, plan["full_gate"]["node"])
    execution = _execution(repo_root, plan, [selected, full_gate], ok=True)
    execution["environment"] = dict(execution["environment"])
    execution["environment"]["identity_sha256"] = "0" * 64

    receipt = make_receipt(repo_root, identity, plan, execution)

    assert receipt["ok"] is False
    assert receipt["proof"]["status"] == "incomplete_execution"
    assert receipt["proof"]["full_gate_status"] == "failed"


def test_receipt_output_is_task_local_atomic_and_non_overwriting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    with fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "{}\n") as target:
        assert target == receipt_root / "result.json"
        assert target.binding == "fd_bound"
        assert json.loads(target.path.read_text(encoding="utf-8")) == {}
    (receipt_root / "nested").mkdir()
    with fastpath.write_receipt_atomic(REPO_ROOT, Path("nested/result.json"), "{\"nested\": true}\n") as nested_target:
        assert json.loads(nested_target.path.read_text(encoding="utf-8")) == {"nested": True}

    with pytest.raises(fastpath.ReceiptPathError, match="already exists"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "tampered\n")
    with pytest.raises(fastpath.ReceiptPathError, match="escapes"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("../escape.json"), "{}\n")
    with pytest.raises(fastpath.ReceiptPathError, match="source checkout"):
        fastpath.write_receipt_atomic(REPO_ROOT, REPO_ROOT / "pytest.ini", "tampered\n")
    assert (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8").startswith("[pytest]")


def test_receipt_parent_swap_cannot_redirect_fd_bound_delivery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    nested = receipt_root / "nested"
    outside = tmp_path / "outside"
    nested.mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_link = os.link

    def swap_parent_before_link(
        source: str,
        target: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        nested.rename(outside / "moved")
        nested.symlink_to(outside, target_is_directory=True)
        original_link(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(fastpath.os, "link", swap_parent_before_link)

    with fastpath.write_receipt_atomic(REPO_ROOT, Path("nested/result.json"), "{}\n") as placement:
        assert placement.binding == "fd_bound"
        assert os.pread(placement.target_fd, 3, 0) == b"{}\n"
        assert placement.descriptor()["path_authority"] == "display_only"

    assert (outside / "moved" / "result.json").read_text(encoding="utf-8") == "{}\n"


def test_receipt_parent_rename_after_final_check_stays_fd_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    nested = receipt_root / "nested"
    outside = tmp_path / "outside"
    nested.mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_binding = fastpath._receipt_binding_errors
    calls = 0

    def move_after_final_fd_check(root_fd, parent_fd, root, expected_root, expected_parent):
        nonlocal calls
        result = original_binding(root_fd, parent_fd, root, expected_root, expected_parent)
        calls += 1
        if calls == 2:
            nested.rename(outside / "moved")
            nested.symlink_to(outside / "moved", target_is_directory=True)
        return result

    monkeypatch.setattr(fastpath, "_receipt_binding_errors", move_after_final_fd_check)

    with fastpath.write_receipt_atomic(REPO_ROOT, Path("nested/result.json"), "{}\n") as placement:
        assert placement.binding == "fd_bound"
        assert os.pread(placement.target_fd, 3, 0) == b"{}\n"

    assert (outside / "moved" / "result.json").read_text(encoding="utf-8") == "{}\n"


def test_receipt_root_rename_after_final_check_stays_fd_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    nested = receipt_root / "nested"
    outside = tmp_path / "outside"
    nested.mkdir(parents=True)
    outside.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_binding = fastpath._receipt_binding_errors
    calls = 0

    def move_after_final_binding(root_fd, parent_fd, root, expected_root, expected_parent):
        nonlocal calls
        result = original_binding(root_fd, parent_fd, root, expected_root, expected_parent)
        calls += 1
        if calls == 2:
            receipt_root.rename(outside / "moved-root")
            receipt_root.symlink_to(outside / "moved-root", target_is_directory=True)
        return result

    monkeypatch.setattr(fastpath, "_receipt_binding_errors", move_after_final_binding)

    with fastpath.write_receipt_atomic(REPO_ROOT, Path("nested/result.json"), "{}\n") as placement:
        assert placement.binding == "fd_bound"
        assert os.pread(placement.target_fd, 3, 0) == b"{}\n"

    assert (outside / "moved-root" / "nested" / "result.json").read_text(encoding="utf-8") == "{}\n"


def test_receipt_target_fd_survives_post_publication_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    nested = receipt_root / "nested"
    nested.mkdir(parents=True)
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    with fastpath.write_receipt_atomic(REPO_ROOT, Path("nested/result.json"), "{}\n") as placement:
        os.unlink("result.json", dir_fd=placement.parent_fd)
        os.symlink("replacement", "result.json", dir_fd=placement.parent_fd)
        assert os.pread(placement.target_fd, 3, 0) == b"{}\n"
        assert placement.target_identity["st_ino"] != os.lstat(placement.path).st_ino

    assert (nested / "result.json").is_symlink()


def test_receipt_target_replacement_before_open_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_open = fastpath._open_receipt_target

    def replace_target_before_open(name: str, *, dir_fd: int) -> int:
        os.unlink(name, dir_fd=dir_fd)
        attacker_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=dir_fd,
        )
        try:
            os.write(attacker_fd, b"ATTACKER\n")
        finally:
            os.close(attacker_fd)
        return original_open(name, dir_fd=dir_fd)

    monkeypatch.setattr(fastpath, "_open_receipt_target", replace_target_before_open)

    with pytest.raises(fastpath.ReceiptPathError, match="inode|payload"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "{}\n")

    assert (receipt_root / "result.json").read_bytes() == b"ATTACKER\n"


def test_receipt_temp_unlink_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_unlink = fastpath.os.unlink

    def fail_temp_unlink(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith(".validation-receipt."):
            raise OSError("synthetic temp unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(fastpath.os, "unlink", fail_temp_unlink)

    with pytest.raises(fastpath.ReceiptPathError, match="temporary unlink failed"):
        fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "{}\n")

    assert list(receipt_root.glob(".validation-receipt.*"))


def test_receipt_directory_fd_close_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_open = fastpath._open_receipt_directory
    original_close = fastpath.os.close
    directory_fds: set[int] = set()

    def capture_directory_fd(name: str, *, dir_fd: int | None = None) -> int:
        file_descriptor = original_open(name, dir_fd=dir_fd)
        directory_fds.add(file_descriptor)
        return file_descriptor

    def fail_directory_close(file_descriptor: int) -> None:
        if file_descriptor in directory_fds:
            raise OSError("synthetic directory close failure")
        original_close(file_descriptor)

    monkeypatch.setattr(fastpath, "_open_receipt_directory", capture_directory_fd)
    monkeypatch.setattr(fastpath.os, "close", fail_directory_close)

    placement = fastpath.write_receipt_atomic(REPO_ROOT, Path("result.json"), "{}\n")
    with pytest.raises(fastpath.ReceiptPathError, match="fd close failed"):
        placement.close()

    published = json.loads((receipt_root / "result.json").read_text(encoding="utf-8"))
    assert published["ok"] is False
    assert published["receipt_finalization"]["status"] == "invalid"
    assert published["proof"]["status"] == "receipt_finalization_failed"


def test_cli_close_failure_cannot_leave_a_green_published_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _fixture_repo(tmp_path)
    _commit_source_change(repo_root, "VALUE = 2\n")
    receipt_root = tmp_path / "receipts"
    receipt_root.mkdir()
    monkeypatch.setenv(fastpath.RECEIPT_ROOT_ENV, str(receipt_root))
    original_open = fastpath._open_receipt_directory
    original_close = fastpath.os.close
    directory_fds: set[int] = set()

    def capture_directory_fd(name: str, *, dir_fd: int | None = None) -> int:
        file_descriptor = original_open(name, dir_fd=dir_fd)
        directory_fds.add(file_descriptor)
        return file_descriptor

    def fail_directory_close(file_descriptor: int) -> None:
        if file_descriptor in directory_fds:
            raise OSError("synthetic CLI directory close failure")
        original_close(file_descriptor)

    monkeypatch.setattr(fastpath, "_open_receipt_directory", capture_directory_fd)
    monkeypatch.setattr(fastpath.os, "close", fail_directory_close)
    return_code = fastpath.main(
        [
            "--repo",
            str(repo_root),
            "--base",
            "HEAD^",
            "--candidate",
            "HEAD",
            "--resource-decision",
            json.dumps(VALID_RESOURCE, sort_keys=True),
            "--receipt",
            "result.json",
        ]
    )

    published = json.loads((receipt_root / "result.json").read_text(encoding="utf-8"))
    assert return_code == 1
    assert published["ok"] is False
    assert published["receipt_finalization"]["status"] == "invalid"
    assert published["proof"]["status"] == "receipt_finalization_failed"


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


def test_node_elapsed_includes_launch_overhead(monkeypatch: pytest.MonkeyPatch) -> None:
    original_popen = fastpath.subprocess.Popen

    def delayed_popen(*args, **kwargs):
        time.sleep(fastpath.FAST_NODE_BUDGET_SEC + 0.05)
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(fastpath.subprocess, "Popen", delayed_popen)
    result = fastpath._run_node(
        REPO_ROOT,
        {"node_id": "launch-overhead", "command": [sys.executable, "-c", "pass"]},
        timeout_sec=3.0,
    )

    assert result["ok"] is True
    assert result["elapsed_sec"] > fastpath.FAST_NODE_BUDGET_SEC
    assert result["timing"]["measurement_scope"] == "node_wall_including_launch_identity_and_cleanup"
    assert result["timing"]["excluded_intervals_sec"] == 0.0
    assert result["timing"]["classification"] == "contextual"
    assert result["timing"]["target_met"] is False


@pytest.mark.skipif(os.name != "posix", reason="detached descendant cleanup is POSIX-specific")
def test_normal_success_quiet_detached_descendant_is_not_green(tmp_path: Path) -> None:
    marker = tmp_path / "quiet-detached.pid"
    child_code = (
        "import os,time; os.setsid(); "
        f"open({str(marker)!r}, 'w').write(str(os.getpid())); "
        "time.sleep(5)"
    )
    parent_code = (
        "import os,subprocess,sys; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "os._exit(0)"
    )
    result = fastpath._run_node(
        REPO_ROOT,
        {"node_id": "quiet-detached-normal-success", "command": [sys.executable, "-c", parent_code]},
        timeout_sec=2.0,
    )

    detached_pid = int(marker.read_text(encoding="utf-8")) if marker.exists() else None
    detached_alive = False
    if detached_pid is not None:
        try:
            os.kill(detached_pid, 0)
            detached_alive = True
        except OSError:
            pass
        if detached_alive:
            os.kill(detached_pid, signal.SIGKILL)

    assert result["ok"] is False
    assert result["timed_out"] is False
    assert result["error"]["type"] == "cleanup_error"
    assert any("retained descendants" in error for error in result["cleanup_errors"])
    assert result["cleanup"]["descendant_processes_alive"] == []
    assert detached_alive is False


def test_timeout_terminates_descendants_and_drains_readers_within_bound() -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import subprocess, sys, time; "
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)']); "
            "print(child.pid, flush=True); time.sleep(5)"
        ),
    ]

    result = fastpath._run_node(
        REPO_ROOT,
        {"node_id": "descendant-timeout", "command": command},
        timeout_sec=0.05,
    )

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["error"]["type"] == "timeout"
    assert result["timing"]["execution_timeout_sec"] == 0.05
    assert result["timing"]["cleanup_safety_window_sec"] == fastpath.PROCESS_CLEANUP_WINDOW_SEC
    assert result["timing"]["classification"] in {"fast", "contextual"}
    assert result["cleanup"]["process_group"] == "isolated"
    assert result["cleanup"]["process_group_alive"] is False
    assert result["cleanup"]["process_terminated"] is True
    assert result["cleanup"]["reader_threads_alive"] == []
    assert result["cleanup_errors"] == []


def test_timeout_cleanup_preserves_preexisting_runner_child() -> None:
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        result = fastpath._run_node(
            REPO_ROOT,
            {"node_id": "preserve-runner-child", "command": [sys.executable, "-c", "import time; time.sleep(5)"]},
            timeout_sec=0.05,
        )

        assert result["timed_out"] is True
        assert unrelated.poll() is None
    finally:
        if unrelated.poll() is None:
            unrelated.terminate()
        try:
            unrelated.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            unrelated.kill()
            unrelated.wait(timeout=1.0)


def test_timeout_bounds_setsid_descendant_with_inherited_pipes(tmp_path: Path) -> None:
    marker = tmp_path / "detached.pid"
    child_code = (
        f"import os,time; os.setsid(); open({str(marker)!r}, 'w').write(str(os.getpid())); time.sleep(5)"
    )
    parent_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); time.sleep(5)"
    )
    result = fastpath._run_node(
        REPO_ROOT,
        {"node_id": "setsid-descendant-timeout", "command": [sys.executable, "-c", parent_code]},
        timeout_sec=0.2,
    )
    detached_pid = int(marker.read_text(encoding="utf-8")) if marker.exists() else None
    detached_alive = False
    if detached_pid is not None:
        try:
            os.kill(detached_pid, 0)
            detached_alive = True
        except OSError:
            pass
        if detached_alive:
            os.kill(detached_pid, signal.SIGKILL)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["error"]["type"] == "timeout"
    assert result["timing"]["execution_timeout_sec"] == 0.2
    assert result["timing"]["classification"] in {"fast", "contextual"}
    assert result["cleanup"]["reader_threads_alive"] == []
    assert detached_alive is False


def test_timeout_timing_uses_repeated_numeric_classification() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(5)"]
    samples = [
        fastpath._run_node(
            REPO_ROOT,
            {"node_id": f"repeated-timeout-{index}", "command": command},
            timeout_sec=0.05,
        )
        for index in range(5)
    ]
    elapsed_samples = [float(result["elapsed_sec"]) for result in samples]
    p95 = sorted(elapsed_samples)[-1]

    assert all(result["timed_out"] is True for result in samples)
    assert all(
        result["timing"]["classification"]
        == ("fast" if result["elapsed_sec"] <= fastpath.FAST_NODE_BUDGET_SEC else "contextual")
        for result in samples
    )
    assert p95 >= 0


def test_timeout_teardown_catches_late_detached_descendant_with_inherited_pipes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "late-detached.pid"
    child_code = f"import os,time; os.setsid(); open({str(marker)!r}, 'w').write(str(os.getpid())); time.sleep(5)"
    parent_code = (
        "import signal,subprocess,sys,time\n"
        f"child_code={child_code!r}\n"
        "def handler(sig, frame):\n"
        "    subprocess.Popen([sys.executable, '-c', child_code])\n"
        "signal.signal(signal.SIGUSR1, handler)\n"
        "time.sleep(5)\n"
    )
    original_terminate = fastpath._terminate_process_group

    def create_descendant_after_final_snapshot(pid: int, process: object) -> list[str]:
        os.kill(pid, signal.SIGUSR1)
        deadline = time.perf_counter() + 1.0
        while time.perf_counter() < deadline and not marker.exists():
            time.sleep(0.001)
        assert marker.exists()
        return original_terminate(pid, process)

    monkeypatch.setattr(fastpath, "_terminate_process_group", create_descendant_after_final_snapshot)

    result = fastpath._run_node(
        REPO_ROOT,
        {"node_id": "late-detached-descendant", "command": [sys.executable, "-c", parent_code]},
        timeout_sec=0.2,
    )

    detached_pid = int(marker.read_text(encoding="utf-8")) if marker.exists() else None
    detached_alive = False
    if detached_pid is not None:
        try:
            os.kill(detached_pid, 0)
            detached_alive = True
        except OSError:
            pass
        if detached_alive:
            os.kill(detached_pid, signal.SIGKILL)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["error"]["type"] == "timeout"
    assert result["cleanup"]["descendant_processes_alive"] == []
    assert result["cleanup"]["reader_threads_alive"] == []
    assert result["cleanup_errors"] == []
    assert detached_alive is False
