#!/usr/bin/env python3
"""Run a bounded, evidence-preserving validation slice for a source candidate.

This route is intentionally contextual.  It selects only owner-mapped checks,
records what it selected and skipped, and always states that the source-fast
gate remains required.  It never edits installed state, starts services, or
reuses a receipt without an explicit candidate/environment match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "abyss_machine_validation_fastpath_v1"
VERSION = "0.1.0"
MAX_OUTPUT_CHARS = 2000
FULL_GATE_ID = "owner-source-fast-gate"


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)}: {detail}")
    return result.stdout.strip()


def _worktree_digest(repo_root: Path, candidate_ref: str) -> str:
    """Bind dirty tracked and untracked source bytes without publishing them."""

    digest = hashlib.sha256()
    diff = subprocess.run(
        ["git", "diff", "--binary", candidate_ref],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    digest.update(diff.stdout)
    for raw_path in _git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines():
        path = repo_root / raw_path
        digest.update(raw_path.encode())
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"<missing>")
    return digest.hexdigest()


def _ref(repo_root: Path, value: str, suffix: str = "") -> str:
    return _git(repo_root, "rev-parse", f"{value}{suffix}")


def candidate_identity(repo_root: Path, base_ref: str, candidate_ref: str) -> dict[str, Any]:
    """Return exact Git identity plus a non-mutating worktree state."""

    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "workspace": str(repo_root),
        "base_ref": base_ref,
        "base_sha": _ref(repo_root, base_ref, "^{commit}"),
        "base_tree": _ref(repo_root, base_ref, "^{tree}"),
        "candidate_ref": candidate_ref,
        "candidate_sha": _ref(repo_root, candidate_ref, "^{commit}"),
        "candidate_tree": _ref(repo_root, candidate_ref, "^{tree}"),
        "worktree_state": "clean" if not status else "dirty",
        "worktree_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        "worktree_content_sha256": _worktree_digest(repo_root, candidate_ref),
    }


def changed_paths(
    repo_root: Path,
    base_ref: str,
    candidate_ref: str,
    *,
    include_worktree: bool = False,
) -> list[str]:
    """List candidate paths, optionally including explicitly requested worktree edits."""

    names = set(
        filter(
            None,
            _git(
                repo_root,
                "diff",
                "--name-only",
                "--no-renames",
                base_ref,
                candidate_ref,
            ).splitlines(),
        )
    )
    if include_worktree:
        names.update(
            filter(
                None,
                _git(repo_root, "diff", "--name-only", "--no-renames", candidate_ref).splitlines(),
            )
        )
        names.update(
            filter(
                None,
                _git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines(),
            )
        )
    return sorted(names)


def _command_for_test(
    repo_root: Path,
    test_path: str,
    *,
    marker_expression: str | None = None,
    python_executable: str,
) -> list[str]:
    command = [
        python_executable,
        "-m",
        "pytest",
        "-q",
        "-c",
        "pytest.ini",
        test_path,
        "-p",
        "no:cacheprovider",
    ]
    if marker_expression:
        command.extend(["-m", marker_expression])
    return command


def _node(
    node_id: str,
    reason: str,
    matched_paths: Iterable[str],
    command: Sequence[str],
    *,
    evidence_class: str,
    claims: Sequence[str],
    risk: str,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "reason": reason,
        "matched_paths": sorted(set(matched_paths)),
        "command": list(command),
        "evidence_class": evidence_class,
        "claims": list(claims),
        "risk": risk,
    }


def _full_gate_node(python_executable: str) -> dict[str, Any]:
    return _node(
        FULL_GATE_ID,
        "required escalation/final proof; never substituted by contextual selection",
        (),
        [python_executable, "scripts/ci_gate.py", "--mode", "source-fast"],
        evidence_class="owner-source-full-gate",
        claims=["source-fast manifest and all declared owner checks"],
        risk="high",
    )


def build_plan(
    changed: Sequence[str],
    repo_root: Path,
    *,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Map changed source surfaces to bounded checks; unknown surfaces expand."""

    selected: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    unmapped: list[str] = []

    def add(node: dict[str, Any]) -> None:
        previous = selected.get(node["node_id"])
        if previous is None:
            selected[node["node_id"]] = node
        else:
            previous["matched_paths"] = sorted(
                set(previous["matched_paths"]) | set(node["matched_paths"])
            )

    for raw_path in sorted(set(changed)):
        path = Path(raw_path)
        path_text = path.as_posix()

        if path_text.startswith("tests/public_smoke/") and path.suffix == ".py":
            if (repo_root / path).is_file():
                add(
                    _node(
                        f"public-smoke:{path_text}",
                        "changed public smoke test selected exactly",
                        [path_text],
                        _command_for_test(
                            repo_root,
                            path_text,
                            python_executable=python_executable,
                        ),
                        evidence_class="public-source-contextual",
                        claims=[f"the changed public smoke surface {path_text}"],
                        risk="bounded",
                    )
                )
            else:
                unmapped.append(path_text)
            continue

        if path_text.startswith("tests/host_contract/") and path.suffix == ".py":
            if (repo_root / path).is_file():
                add(
                    _node(
                        f"host-contract:{path_text}",
                        "changed host-contract test selected without live/manual/long markers",
                        [path_text],
                        _command_for_test(
                            repo_root,
                            path_text,
                            marker_expression="not live and not manual and not long",
                            python_executable=python_executable,
                        ),
                        evidence_class="host-contract-contextual",
                        claims=[f"the changed host contract surface {path_text}"],
                        risk="bounded; host-installed assumptions remain unproven",
                    )
                )
            else:
                unmapped.append(path_text)
            continue

        if path_text in {"scripts/validation_lanes.py", "docs/validation/validation_lanes.json"}:
            add(
                _node(
                    "validation-lane-manifest",
                    "lane manifest semantics are checked directly",
                    [path_text],
                    [python_executable, "scripts/validation_lanes.py"],
                    evidence_class="manifest-contextual",
                    claims=["validation lane manifest is internally valid"],
                    risk="bounded; declared checks are not executed by this node",
                )
            )
            continue

        if path_text.startswith("src/abyss_machine/") and path.suffix == ".py":
            smoke_path = Path("tests/public_smoke") / f"test_{path.stem}.py"
            if (repo_root / smoke_path).is_file():
                smoke_text = smoke_path.as_posix()
                add(
                    _node(
                        f"public-smoke:{smoke_text}",
                        "changed source module has an exact public smoke companion",
                        [path_text],
                        _command_for_test(
                            repo_root,
                            smoke_text,
                            python_executable=python_executable,
                        ),
                        evidence_class="public-source-contextual",
                        claims=[f"the mapped public contract for {path_text}"],
                        risk="bounded; cross-module and owner-wide coverage remains open",
                    )
                )
            else:
                unmapped.append(path_text)
            continue

        if path_text == "scripts/validation_fastpath.py":
            test_path = Path("tests/public_smoke/test_validation_fastpath.py")
            if (repo_root / test_path).is_file():
                test_text = test_path.as_posix()
                add(
                    _node(
                        f"public-smoke:{test_text}",
                        "fast-path implementation is checked by its focused contract tests",
                        [path_text],
                        _command_for_test(
                            repo_root,
                            test_text,
                            python_executable=python_executable,
                        ),
                        evidence_class="fastpath-contract",
                        claims=["selection, fallback, receipt, and full-gate boundary contracts"],
                        risk="bounded; this does not prove the selected owner checks themselves",
                    )
                )
            else:
                unmapped.append(path_text)
            continue

        # Runner, policy, schema, generated, build, and unknown surfaces must
        # expand to the full gate instead of receiving an optimistic shortcut.
        unmapped.append(path_text)

    if not changed:
        skipped.append(
            {
                "surface": "candidate",
                "reason": "no_changed_paths",
                "action": "no_contextual_node_selected",
            }
        )
    if unmapped:
        skipped.append(
            {
                "surface": "unmapped_changed_paths",
                "paths": sorted(unmapped),
                "reason": "unknown_or_high_risk_surface_requires_full_gate",
                "action": "expand_to_full_gate",
            }
        )

    full_gate = _full_gate_node(python_executable)
    return {
        "selected": list(selected.values()),
        "skipped": skipped,
        "fallback": {
            "required": bool(unmapped),
            "reason": (
                "unmapped_or_high_risk_changed_surface"
                if unmapped
                else "no_fallback_for_mapped_contextual_slice"
            ),
            "command": full_gate["command"],
            "node_id": FULL_GATE_ID,
        },
        "full_gate": {
            "required": True,
            "status": "not_run",
            "reason": "contextual route never establishes owner-wide sufficiency",
            "node": full_gate,
        },
        "unmapped_paths": sorted(unmapped),
    }


def _environment_identity(repo_root: Path) -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pytest_ini_sha256": _sha256(repo_root / "pytest.ini"),
        "validation_lane_manifest_sha256": _sha256(
            repo_root / "docs" / "validation" / "validation_lanes.json"
        ),
        "bytecode": "disabled",
        "pytest_cache": "disabled",
    }


def _tail(value: str) -> str:
    return value[-MAX_OUTPUT_CHARS:]


def _run_node(repo_root: Path, node: Mapping[str, Any], timeout_sec: float) -> dict[str, Any]:
    command = list(node["command"])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
    source_path = str(repo_root / "src")
    env["PYTHONPATH"] = source_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    started = time.perf_counter()
    before_children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        timed_out = False
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    elapsed = time.perf_counter() - started
    after_children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {
        "node_id": node["node_id"],
        "command": command,
        "ok": returncode == 0 and not timed_out,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_sec": round(elapsed, 6),
        "children_max_rss_kib": max(before_children, after_children),
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def execute_plan(
    repo_root: Path,
    plan: Mapping[str, Any],
    *,
    resource_admission: str,
    run_full: bool = False,
    timeout_sec: float = 300.0,
) -> dict[str, Any]:
    """Execute serially only after an explicit caller-owned admission."""

    if resource_admission != "allow":
        return {
            "status": "not_run_resource_admission",
            "resource_admission": resource_admission,
            "steps": [],
            "ok": False,
            "reason": "resource_admission_must_be_explicit_allow",
        }

    nodes = list(plan["selected"])
    fallback_required = bool(plan["fallback"]["required"])
    if fallback_required or run_full:
        nodes.append(plan["full_gate"]["node"])

    steps = [_run_node(repo_root, node, timeout_sec) for node in nodes]
    full_step = next((step for step in steps if step["node_id"] == FULL_GATE_ID), None)
    if full_step is not None:
        plan["full_gate"]["status"] = "passed" if full_step["ok"] else "failed"
    return {
        "status": "completed",
        "resource_admission": resource_admission,
        "steps": steps,
        "ok": all(step["ok"] for step in steps),
        "reason": None,
    }


def make_receipt(
    repo_root: Path,
    identity: Mapping[str, Any],
    plan: dict[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    selected_steps = list(execution.get("steps", []))
    full_step = next((step for step in selected_steps if step["node_id"] == FULL_GATE_ID), None)
    if execution.get("status") == "plan_only":
        proof_status = "plan_only"
    elif full_step is not None:
        proof_status = "full_gate_passed" if full_step["ok"] else "full_gate_failed"
    elif execution.get("status") == "not_run_resource_admission":
        proof_status = "not_run_resource_admission"
    elif execution.get("ok"):
        proof_status = "contextual_candidate_passed"
    else:
        proof_status = "contextual_candidate_failed"

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route": {
            "kind": "contextual_changed_surface",
            "serial_execution": True,
            "selection_is_not_sufficiency": True,
        },
        "candidate": dict(identity),
        "environment": _environment_identity(repo_root),
        "selection": {
            "selected": plan["selected"],
            "skipped": plan["skipped"],
            "fallback": plan["fallback"],
            "unmapped_paths": plan["unmapped_paths"],
        },
        "cache": {
            "pytest_cache": "disabled",
            "bytecode": "disabled",
            "receipt_reuse": "not_implemented",
            "reuse_decision": "not_used; exact sealed receipt reuse is outside this bounded slice",
        },
        "resource": {
            "admission": execution.get("resource_admission", "not_provided"),
            "admission_source": "caller_owned_and_recorded",
            "class": "light",
            "kind": "agent",
            "latency": "interactive",
            "activity": "foreground",
            "mutation_scope": "isolated_source_checkout_only",
        },
        "execution": dict(execution),
        "proof": {
            "status": proof_status,
            "full_gate_required": True,
            "owner_acceptance": False,
            "unvalidated_claims": [
                "owner-wide coverage outside selected changed surfaces",
                "artifact, portability, integration, live, adversarial, and E2E evidence",
                "freshness/trust of any external or generated evidence",
            ],
        },
        "ok": bool(execution.get("ok")),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit/ref for changed-surface diff")
    parser.add_argument("--candidate", default="HEAD", help="candidate commit/ref (default: HEAD)")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="isolated repository root")
    parser.add_argument(
        "--include-worktree",
        action="store_true",
        help="include staged/unstaged/untracked paths and require an explicit dirty candidate",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow execution against a worktree explicitly included with --include-worktree",
    )
    parser.add_argument(
        "--resource-admission",
        choices=("allow", "deny", "not-provided"),
        default="not-provided",
        help="caller-owned resource admission; only allow executes nodes",
    )
    parser.add_argument("--run-full", action="store_true", help="append the unchanged source-fast gate")
    parser.add_argument("--plan-only", action="store_true", help="emit selection without executing commands")
    parser.add_argument("--timeout-sec", type=float, default=300.0)
    parser.add_argument("--receipt", type=Path, help="optional task-local JSON receipt path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo.resolve()
    identity = candidate_identity(repo_root, args.base, args.candidate)
    dirty = identity["worktree_state"] == "dirty"
    include_worktree = bool(args.include_worktree)
    paths = changed_paths(
        repo_root,
        args.base,
        args.candidate,
        include_worktree=include_worktree,
    )
    plan = build_plan(paths, repo_root)
    if dirty and not (include_worktree and args.allow_dirty):
        plan["selected"] = []
        plan["skipped"].append(
            {
                "surface": "worktree",
                "reason": "dirty_worktree_requires_explicit_candidate_binding",
                "action": "expand_to_full_gate_or_clean_worktree",
            }
        )
        plan["fallback"] = {
            "required": True,
            "reason": "dirty_worktree_not_explicitly_allowed",
            "command": plan["full_gate"]["node"]["command"],
            "node_id": FULL_GATE_ID,
        }

    if args.plan_only:
        execution: dict[str, Any] = {
            "status": "plan_only",
            "resource_admission": args.resource_admission,
            "steps": [],
            "ok": True,
            "reason": None,
        }
    else:
        execution = execute_plan(
            repo_root,
            plan,
            resource_admission=args.resource_admission,
            run_full=args.run_full,
            timeout_sec=args.timeout_sec,
        )
    receipt = make_receipt(repo_root, identity, plan, execution)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
