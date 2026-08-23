#!/usr/bin/env python3
"""Run a bounded, evidence-preserving validation slice for a source candidate.

This route is intentionally contextual.  It selects only owner-mapped checks,
records what it selected and skipped, and keeps the unchanged source-fast gate
as the fail-closed escalation.  Dirty inputs, policy/runner/test surfaces,
ambiguous identities, incomplete resource decisions, and incomplete execution
receipts never become a contextual success.
"""

from __future__ import annotations

import argparse
import codecs
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "abyss_machine_validation_fastpath_v1"
VERSION = "0.1.0"
MAX_OUTPUT_CHARS = 2000
FULL_GATE_ID = "owner-source-fast-gate"
RECEIPT_ROOT_ENV = "ABYSS_MACHINE_VALIDATION_RECEIPT_ROOT"
RESOURCE_FIELDS = ("admission", "class", "kind", "latency", "activity")
RESOURCE_ADMISSIONS = {"allow", "deny", "not-provided"}
ENVIRONMENT_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONNOUSERSITE",
    "PYTEST_ADDOPTS",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
    "PYTEST_PLUGINS",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
)
RECEIPT_TEMP_ATTEMPTS = 8
PROCESS_CLEANUP_WINDOW_SEC = 0.05
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37


class ValidationInputError(ValueError):
    """Raised when a receipt would otherwise make an unbound claim."""


class ReceiptPathError(ValueError):
    """Raised when receipt output is outside the approved task-local boundary."""


def _validate_timeout_sec(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationInputError("timeout_sec must be a finite positive number")
    timeout_sec = float(value)
    if not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ValidationInputError("timeout_sec must be a finite positive number")
    return timeout_sec


def _valid_elapsed_sec(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        elapsed_sec = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(elapsed_sec) and elapsed_sec >= 0


def _owner_python_executable() -> str:
    """Return the interpreter that owns this validation runner."""

    try:
        executable = Path(sys.executable).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValidationInputError(f"owner full-gate interpreter is unavailable: {_short_error(str(exc))}") from exc
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValidationInputError("owner full-gate interpreter is not executable")
    return str(executable)


def _validate_owner_python_executable(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationInputError("full-gate executable is not bound")
    try:
        supplied = Path(value).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValidationInputError(f"full-gate executable is invalid: {_short_error(str(exc))}") from exc
    expected = Path(_owner_python_executable())
    if supplied != expected:
        raise ValidationInputError("full-gate executable must be the current owner interpreter")
    supplied_sha256 = _sha256(supplied)
    expected_sha256 = _sha256(expected)
    if supplied_sha256 is None or supplied_sha256 != expected_sha256:
        raise ValidationInputError("full-gate executable identity is not bound")
    return str(expected)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_value(value: Any) -> str:
    return _digest_bytes(_canonical_json(value).encode("utf-8"))


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_bytes(repo_root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip() or "git command failed"
        raise RuntimeError(f"git {' '.join(args)}: {detail}")
    return result.stdout


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    return _git_bytes(repo_root, *args, check=check).decode("utf-8", "strict").strip()


def _split_nul_paths(value: bytes) -> list[str]:
    return [part.decode("utf-8", "surrogateescape") for part in value.split(b"\0") if part]


def _update_labeled(digest: Any, label: str, value: bytes) -> None:
    label_bytes = label.encode("utf-8")
    digest.update(len(label_bytes).to_bytes(8, "big"))
    digest.update(label_bytes)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _digest_path_inputs(repo_root: Path, paths: Iterable[str]) -> str:
    """Hash path names, types, modes and bytes without publishing their content."""

    digest = hashlib.sha256()
    for raw_path in sorted(set(paths)):
        path_bytes = raw_path.encode("utf-8", "surrogateescape")
        _update_labeled(digest, "path", path_bytes)
        path = repo_root / raw_path
        try:
            info = path.lstat()
        except FileNotFoundError:
            _update_labeled(digest, "missing", b"1")
            continue
        _update_labeled(digest, "mode", str(info.st_mode).encode("ascii"))
        if stat.S_ISREG(info.st_mode):
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    _update_labeled(digest, "bytes", chunk)
        elif stat.S_ISLNK(info.st_mode):
            _update_labeled(digest, "symlink", os.readlink(path).encode("utf-8", "surrogateescape"))
        else:
            _update_labeled(digest, "special", str(info.st_size).encode("ascii"))
    return digest.hexdigest()


def _combine_digests(parts: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for label in sorted(parts):
        _update_labeled(digest, label, parts[label].encode("ascii"))
    return digest.hexdigest()


def _worktree_snapshot(repo_root: Path, candidate_ref: str) -> dict[str, Any]:
    normal_status = _git_bytes(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    ignored_status = _git_bytes(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
    )
    index = _git_bytes(repo_root, "ls-files", "--stage", "-z")
    staged_diff = _git_bytes(
        repo_root,
        "diff",
        "--binary",
        "--no-renames",
        "--cached",
        candidate_ref,
    )
    unstaged_diff = _git_bytes(
        repo_root,
        "diff",
        "--binary",
        "--no-renames",
    )
    staged_paths_bytes = _git_bytes(
        repo_root,
        "diff",
        "--name-only",
        "--no-renames",
        "--cached",
        "-z",
        candidate_ref,
    )
    unstaged_paths = _split_nul_paths(
        _git_bytes(
            repo_root,
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
        )
    )
    untracked_paths = _split_nul_paths(
        _git_bytes(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    )
    ignored_paths = _split_nul_paths(
        _git_bytes(repo_root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    )
    parts = {
        "index": _digest_bytes(index),
        "staged_diff": _digest_bytes(staged_diff),
        "unstaged_diff": _digest_bytes(unstaged_diff),
        # The index is authoritative for staged content.  Reading these paths
        # from the worktree here would silently fold a later unstaged edit into
        # the staged identity.
        "staged_paths": _digest_bytes(staged_paths_bytes),
        "unstaged_paths": _digest_path_inputs(repo_root, unstaged_paths),
        "untracked_paths": _digest_path_inputs(repo_root, untracked_paths),
        "ignored_paths": _digest_path_inputs(repo_root, ignored_paths),
    }
    return {
        "dirty": bool(normal_status or ignored_status),
        "normal_status_sha256": _digest_bytes(normal_status),
        "ignored_status_sha256": _digest_bytes(ignored_status),
        "index_sha256": parts["index"],
        "staged_content_sha256": _combine_digests(
            {"diff": parts["staged_diff"], "paths": parts["staged_paths"]}
        ),
        "unstaged_content_sha256": _combine_digests(
            {"diff": parts["unstaged_diff"], "paths": parts["unstaged_paths"]}
        ),
        "untracked_content_sha256": parts["untracked_paths"],
        "ignored_content_sha256": parts["ignored_paths"],
        "overall_sha256": _combine_digests(
            {
                "normal_status": _digest_bytes(normal_status),
                "ignored_status": _digest_bytes(ignored_status),
                **parts,
            }
        ),
    }


def _worktree_digest(repo_root: Path, candidate_ref: str) -> str:
    """Return the exact combined index/worktree/untracked/ignored digest."""

    return _worktree_snapshot(repo_root, candidate_ref)["overall_sha256"]


def _ref(repo_root: Path, value: str, suffix: str = "") -> str:
    return _git(repo_root, "rev-parse", f"{value}{suffix}")


def candidate_identity(repo_root: Path, base_ref: str, candidate_ref: str) -> dict[str, Any]:
    """Return exact Git identity plus all source inputs that can affect routing."""

    snapshot = _worktree_snapshot(repo_root, candidate_ref)
    return {
        "workspace": str(repo_root.resolve()),
        "base_ref": base_ref,
        "base_sha": _ref(repo_root, base_ref, "^{commit}"),
        "base_tree": _ref(repo_root, base_ref, "^{tree}"),
        "candidate_ref": candidate_ref,
        "candidate_sha": _ref(repo_root, candidate_ref, "^{commit}"),
        "candidate_tree": _ref(repo_root, candidate_ref, "^{tree}"),
        "worktree_state": "dirty" if snapshot["dirty"] else "clean",
        "worktree_status_sha256": snapshot["normal_status_sha256"],
        "worktree_ignored_status_sha256": snapshot["ignored_status_sha256"],
        "index_sha256": snapshot["index_sha256"],
        "staged_content_sha256": snapshot["staged_content_sha256"],
        "unstaged_content_sha256": snapshot["unstaged_content_sha256"],
        "untracked_content_sha256": snapshot["untracked_content_sha256"],
        "ignored_content_sha256": snapshot["ignored_content_sha256"],
        "worktree_content_sha256": snapshot["overall_sha256"],
    }


def changed_paths(
    repo_root: Path,
    base_ref: str,
    candidate_ref: str,
    *,
    include_worktree: bool = False,
) -> list[str]:
    """List candidate paths, including every requested dirty input category."""

    names = set(
        _split_nul_paths(
            _git_bytes(
                repo_root,
                "diff",
                "--name-only",
                "--no-renames",
                "-z",
                base_ref,
                candidate_ref,
            )
        )
    )
    if include_worktree:
        names.update(
            _split_nul_paths(
                _git_bytes(
                    repo_root,
                    "diff",
                    "--name-only",
                    "--no-renames",
                    "-z",
                )
            )
        )
        names.update(
            _split_nul_paths(
                _git_bytes(
                    repo_root,
                    "diff",
                    "--name-only",
                    "--no-renames",
                    "--cached",
                    "-z",
                    candidate_ref,
                )
            )
        )
        names.update(_split_nul_paths(_git_bytes(repo_root, "ls-files", "--others", "--exclude-standard", "-z")))
        names.update(
            _split_nul_paths(
                _git_bytes(repo_root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
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
    del repo_root
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


def _high_risk_reason(path_text: str) -> str | None:
    if path_text.startswith("tests/"):
        return "changed tests require the unchanged owner full gate"
    if path_text.startswith("scripts/"):
        return "changed validator/runner scripts require the unchanged owner full gate"
    if path_text.startswith("docs/validation/"):
        return "changed validation policy requires the unchanged owner full gate"
    return None


def _plan_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    full_gate = dict(plan["full_gate"])
    full_gate.pop("status", None)
    return {
        "python_executable": plan["python_executable"],
        "python_executable_sha256": plan["python_executable_sha256"],
        "changed_paths": list(plan["changed_paths"]),
        "selected": list(plan["selected"]),
        "skipped": list(plan["skipped"]),
        "fallback": dict(plan["fallback"]),
        "full_gate": full_gate,
        "unmapped_paths": list(plan["unmapped_paths"]),
        "unmapped_reasons": dict(plan["unmapped_reasons"]),
    }


def _plan_digest(plan: Mapping[str, Any]) -> str:
    return _digest_value(_plan_payload(plan))


def build_plan(
    changed: Sequence[str],
    repo_root: Path,
    *,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Map changed source surfaces to bounded checks; unknown surfaces expand."""

    python_executable = _validate_owner_python_executable(python_executable)
    python_executable_sha256 = _sha256(Path(python_executable))
    if python_executable_sha256 is None:
        raise ValidationInputError("full-gate executable identity is not bound")

    selected: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    unmapped: list[str] = []
    unmapped_reasons: dict[str, str] = {}

    def add(node: dict[str, Any]) -> None:
        previous = selected.get(node["node_id"])
        if previous is None:
            selected[node["node_id"]] = node
        else:
            previous["matched_paths"] = sorted(
                set(previous["matched_paths"]) | set(node["matched_paths"])
            )

    def mark_unmapped(path_text: str, reason: str) -> None:
        unmapped.append(path_text)
        unmapped_reasons[path_text] = reason

    for raw_path in sorted(set(changed)):
        path = Path(raw_path)
        path_text = path.as_posix()
        high_risk_reason = _high_risk_reason(path_text)
        if high_risk_reason:
            mark_unmapped(path_text, high_risk_reason)
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
                mark_unmapped(path_text, "source module has no owner-mapped contextual check")
            continue

        mark_unmapped(path_text, "unknown or unmapped surface requires the unchanged owner full gate")

    if not changed:
        skipped.append(
            {
                "surface": "candidate",
                "reason": "no_changed_paths_requires_full_gate",
                "action": "expand_to_full_gate",
            }
        )
    if unmapped:
        skipped.append(
            {
                "surface": "unmapped_changed_paths",
                "paths": sorted(unmapped),
                "reasons": {path: unmapped_reasons[path] for path in sorted(unmapped)},
                "reason": "unknown_or_high_risk_surface_requires_full_gate",
                "action": "expand_to_full_gate",
            }
        )

    full_gate = _full_gate_node(python_executable)
    plan: dict[str, Any] = {
        "python_executable": python_executable,
        "python_executable_sha256": python_executable_sha256,
        "changed_paths": sorted(set(changed)),
        "selected": list(selected.values()),
        "skipped": skipped,
        "fallback": {
            "required": bool(unmapped) or not changed,
            "reason": (
                "unmapped_or_high_risk_changed_surface"
                if unmapped
                else "no_changed_paths_requires_full_gate"
                if not changed
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
        "unmapped_reasons": {path: unmapped_reasons[path] for path in sorted(unmapped_reasons)},
    }
    plan["plan_sha256"] = _plan_digest(plan)
    return plan


def _execution_environment(repo_root: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_ADDOPTS"] = "-p no:cacheprovider"
    source_path = str(repo_root / "src")
    env["PYTHONPATH"] = source_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _package_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _module_identity(module_name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        spec = None
    origin = None if spec is None else spec.origin
    path = Path(origin) if origin and origin not in {"built-in", "frozen"} else None
    return {
        "module": module_name,
        "path": str(path.resolve()) if path and path.exists() else origin,
        "sha256": _sha256(path) if path else None,
        "version": _package_version(module_name),
    }


def _environment_identity(
    repo_root: Path,
    env: Mapping[str, str] | None = None,
    *,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    effective = {
        str(key): str(value)
        for key, value in dict(_execution_environment(repo_root) if env is None else env).items()
    }
    projection = {key: effective.get(key, "") for key in ENVIRONMENT_KEYS}
    effective_environment_sha256 = _digest_value(effective)
    effective_projection_sha256 = _digest_value(projection)
    executable = Path(python_executable).resolve()
    dependency_files = [_module_identity("pytest")]
    identity_payload = {
        "python_executable": str(executable),
        "python_executable_sha256": _sha256(executable),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pytest_ini_sha256": _sha256(repo_root / "pytest.ini"),
        "validation_lane_manifest_sha256": _sha256(
            repo_root / "docs" / "validation" / "validation_lanes.json"
        ),
        "effective_environment": projection,
        "effective_environment_keys": sorted(effective),
        "effective_environment_sha256": effective_environment_sha256,
        "dependencies": dependency_files,
    }
    return {
        **identity_payload,
        "effective_environment_projection_sha256": effective_projection_sha256,
        "identity_sha256": _digest_value(identity_payload),
    }


class _OutputCapture:
    def __init__(self) -> None:
        self.digest = hashlib.sha256()
        self.bytes_seen = 0
        self.tail = ""
        self.decode_error: str | None = None
        self.transport_error: str | None = None
        self._decoder = codecs.getincrementaldecoder("utf-8")()

    def feed(self, chunk: bytes) -> None:
        self.digest.update(chunk)
        self.bytes_seen += len(chunk)
        try:
            decoded = self._decoder.decode(chunk)
        except UnicodeDecodeError as exc:
            self.decode_error = self.decode_error or str(exc)[:240]
            decoded = chunk.decode("utf-8", "replace")
            self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.tail = (self.tail + decoded)[-MAX_OUTPUT_CHARS:]

    def finish(self) -> None:
        try:
            decoded = self._decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            self.decode_error = self.decode_error or str(exc)[:240]
            decoded = ""
        self.tail = (self.tail + decoded)[-MAX_OUTPUT_CHARS:]

    def result(self) -> dict[str, Any]:
        return {
            "sha256": self.digest.hexdigest(),
            "tail": self.tail,
            "bytes": self.bytes_seen,
            "decode_error": self.decode_error,
            "transport_error": self.transport_error,
        }


def _drain_pipe(pipe: Any, capture: _OutputCapture) -> None:
    try:
        for chunk in iter(lambda: pipe.read(64 * 1024), b""):
            capture.feed(chunk)
    except (OSError, ValueError) as exc:
        capture.transport_error = str(exc)[:240]
    finally:
        capture.finish()
        try:
            pipe.close()
        except (OSError, ValueError) as exc:
            capture.transport_error = capture.transport_error or str(exc)[:240]


def _process_group_alive(pid: int) -> bool:
    if os.name != "posix":
        return False
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _process_snapshot() -> dict[int, tuple[int, int]]:
    """Return Linux child-parent and start-time identities for safe cleanup."""

    if os.name != "posix":
        return {}
    snapshot: dict[int, tuple[int, int]] = {}
    proc_root = Path("/proc")
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return snapshot
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            stat_text = (entry / "stat").read_text(encoding="ascii", errors="replace")
            closing = stat_text.rfind(")")
            fields = stat_text[closing + 2 :].split()
            if len(fields) <= 19:
                continue
            snapshot[int(entry.name)] = (int(fields[1]), int(fields[19]))
        except (FileNotFoundError, OSError, ValueError):
            continue
    return snapshot


def _descendant_processes_from_roots(
    root_pids: set[int],
    snapshot: Mapping[int, tuple[int, int]],
    *,
    excluded: set[int] | None = None,
) -> dict[int, int]:
    excluded = set() if excluded is None else excluded
    descendants: dict[int, int] = {}
    frontier = set(root_pids)
    while frontier:
        children = {
            pid
            for pid, (parent_pid, _start_ticks) in snapshot.items()
            if parent_pid in frontier and pid not in excluded and pid not in descendants
        }
        descendants.update({pid: snapshot[pid][1] for pid in children})
        frontier = children
    return descendants


def _descendant_processes(root_pid: int, *, excluded: set[int] | None = None) -> dict[int, int]:
    return _descendant_processes_from_roots(
        {root_pid},
        _process_snapshot(),
        excluded=excluded,
    )


def _child_subreaper_state() -> bool | None:
    if os.name != "posix":
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        value = ctypes.c_int()
        result = libc.prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(value), 0, 0, 0)
        if result != 0:
            return None
        return bool(value.value)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _set_child_subreaper(enabled: bool) -> str | None:
    if os.name != "posix":
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        result = libc.prctl(PR_SET_CHILD_SUBREAPER, int(enabled), 0, 0, 0)
        if result != 0:
            error_number = ctypes.get_errno()
            detail = os.strerror(error_number) if error_number else "prctl failed"
            return _short_error(detail)
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        return _short_error(str(exc))
    return None


def _reap_adopted_children(child_pids: Iterable[int]) -> None:
    if os.name != "posix":
        return
    for child_pid in child_pids:
        try:
            os.waitpid(child_pid, os.WNOHANG)
        except (ChildProcessError, OSError):
            continue


def _terminate_process_group(pid: int, process: Any) -> list[str]:
    errors: list[str] = []
    if os.name == "posix":
        for value in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pid, value)
            except ProcessLookupError:
                break
            except OSError as exc:
                errors.append(f"process group signal failed: {_short_error(str(exc))}")
    else:
        try:
            process.kill()
        except OSError as exc:
            errors.append(f"process termination failed: {_short_error(str(exc))}")
    return errors


def _terminate_descendants(
    *,
    tracked: Mapping[int, int],
    timeout_sec: float,
) -> tuple[list[str], list[int]]:
    """Terminate node descendants, including setsid() children adopted by us."""

    if os.name != "posix":
        return [], []
    deadline = time.perf_counter() + timeout_sec
    errors: list[str] = []
    tracked = dict(tracked)
    while time.perf_counter() < deadline:
        snapshot = _process_snapshot()
        active = {
            pid: start_ticks
            for pid, start_ticks in tracked.items()
            if pid in snapshot and snapshot[pid][1] == start_ticks
        }
        descendants = _descendant_processes_from_roots(set(active), snapshot)
        candidates = {**active, **descendants}
        if not candidates:
            return errors, []
        for descendant_pid, start_ticks in candidates.items():
            current = _process_snapshot().get(descendant_pid)
            if current is None or current[1] != start_ticks:
                continue
            try:
                os.kill(descendant_pid, signal.SIGTERM)
            except ProcessLookupError:
                continue
            except OSError as exc:
                errors.append(f"descendant termination failed: {_short_error(str(exc))}")
        time.sleep(0.005)
        _reap_adopted_children(candidates)
        snapshot = _process_snapshot()
        active = {
            pid: start_ticks
            for pid, start_ticks in tracked.items()
            if pid in snapshot and snapshot[pid][1] == start_ticks
        }
        remaining = _descendant_processes_from_roots(set(active), snapshot)
        remaining.update(active)
        for descendant_pid, start_ticks in remaining.items():
            current = _process_snapshot().get(descendant_pid)
            if current is None or current[1] != start_ticks:
                continue
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                continue
            except OSError as exc:
                errors.append(f"descendant kill failed: {_short_error(str(exc))}")
        _reap_adopted_children(remaining)
    snapshot = _process_snapshot()
    active = {
        pid: start_ticks
        for pid, start_ticks in tracked.items()
        if pid in snapshot and snapshot[pid][1] == start_ticks
    }
    remaining = _descendant_processes_from_roots(set(active), snapshot)
    remaining.update(active)
    _reap_adopted_children(set(tracked) | set(remaining))
    snapshot = _process_snapshot()
    active = {
        pid: start_ticks
        for pid, start_ticks in tracked.items()
        if pid in snapshot and snapshot[pid][1] == start_ticks
    }
    remaining = _descendant_processes_from_roots(set(active), snapshot)
    remaining.update(active)
    return errors, sorted(remaining)


def _wait_for_process_group_exit(pid: int, timeout_sec: float) -> bool:
    deadline = time.perf_counter() + timeout_sec
    while _process_group_alive(pid) and time.perf_counter() < deadline:
        time.sleep(0.005)
    return _process_group_alive(pid)


def _close_pipe(pipe: Any) -> str | None:
    """Close a pipe fd without waiting on a reader blocked in buffered read."""

    try:
        file_descriptor = pipe.fileno()
        os.close(file_descriptor)
    except (OSError, ValueError) as exc:
        return _short_error(str(exc))
    return None


def _join_readers(readers: Sequence[threading.Thread], timeout_sec: float) -> list[str]:
    """Join all readers against one deadline, never one full timeout per reader."""

    deadline = time.perf_counter() + timeout_sec
    for reader in readers:
        remaining = max(0.0, deadline - time.perf_counter())
        reader.join(timeout=remaining)
    return [reader.name for reader in readers if reader.is_alive()]


def _read_proc_rss_kib(pid: int) -> int | None:
    if os.name != "posix":
        return None
    try:
        status_path = Path(f"/proc/{pid}/status")
        for line in status_path.read_text(encoding="ascii", errors="replace").splitlines():
            if line.startswith("VmHWM:"):
                fields = line.split()
                return int(fields[1]) if len(fields) >= 2 else None
            if line.startswith("VmRSS:"):
                fields = line.split()
                return int(fields[1]) if len(fields) >= 2 else None
    except (FileNotFoundError, OSError, ValueError):
        return None
    return None


def _short_error(value: str) -> str:
    return value.replace("\x00", "")[:400]


def _run_node(
    repo_root: Path,
    node: Mapping[str, Any],
    timeout_sec: float,
    *,
    env: Mapping[str, str] | None = None,
    environment_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    timeout_sec = _validate_timeout_sec(timeout_sec)
    command = list(node.get("command", ()))
    stdout_capture = _OutputCapture()
    stderr_capture = _OutputCapture()
    launch_started = time.perf_counter()
    popen_options: dict[str, Any] = {}
    if os.name == "posix":
        popen_options["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    previous_subreaper = _child_subreaper_state()
    subreaper_error: str | None = None
    if previous_subreaper is False:
        subreaper_error = _set_child_subreaper(True)
    try:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=dict(_execution_environment(repo_root) if env is None else env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_options,
        )
    except (IndexError, OSError, TypeError, ValueError) as exc:
        elapsed = time.perf_counter() - launch_started
        cleanup_errors = [] if subreaper_error is None else [f"descendant cleanup control unavailable: {subreaper_error}"]
        if previous_subreaper is False:
            restore_error = _set_child_subreaper(False)
            if restore_error:
                cleanup_errors.append(f"child subreaper restore failed: {restore_error}")
        return {
            "node_id": node.get("node_id"),
            "command": command,
            "ok": False,
            "returncode": None,
            "timed_out": False,
            "elapsed_sec": round(elapsed, 6),
            "children_max_rss_kib": None,
            "rss_measurement": {
                "method": "proc_status_vm_hwm",
                "scope": "direct_child_pid",
                "status": "unavailable_spawn_failed",
                "peak_rss_kib": None,
            },
            "stdout_sha256": stdout_capture.digest.hexdigest(),
            "stderr_sha256": stderr_capture.digest.hexdigest(),
            "stdout_tail": "",
            "stderr_tail": "",
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "error": {"type": "spawn_error", "detail": _short_error(str(exc))},
            "environment_sha256": None if environment_identity is None else environment_identity.get("identity_sha256"),
            "cleanup": {
                "process_group": "not_started",
                "process_group_termination_attempted": False,
                "process_group_alive": False,
                "process_terminated": True,
                "reader_threads_alive": [],
                "descendant_processes_alive": [],
                "descendant_cleanup_attempted": previous_subreaper is not None,
                "errors": cleanup_errors,
            },
            "cleanup_errors": cleanup_errors,
        }

    assert process.stdout is not None
    assert process.stderr is not None
    tracked_descendants = _descendant_processes(process.pid)
    # Exclude process-tree discovery from the node timeout.  The bound applies
    # to execution and cleanup, not to the local identity snapshot itself.
    started = time.perf_counter()
    readers = [
        threading.Thread(target=_drain_pipe, args=(process.stdout, stdout_capture), daemon=True),
        threading.Thread(target=_drain_pipe, args=(process.stderr, stderr_capture), daemon=True),
    ]
    for reader in readers:
        reader.start()

    peak_rss: int | None = _read_proc_rss_kib(process.pid)
    timed_out = False
    cleanup_errors: list[str] = []
    group_termination_attempted = False
    while process.poll() is None:
        # Keep only descendants observed below this node.  A detached child
        # can be reparented to this runner when the node is killed; retaining
        # its identity here lets the subreaper cleanup find it without ever
        # sweeping unrelated runner children.
        tracked_descendants.update(_descendant_processes(process.pid))
        observed = _read_proc_rss_kib(process.pid)
        if observed is not None:
            peak_rss = observed if peak_rss is None else max(peak_rss, observed)
        if time.perf_counter() - started >= timeout_sec:
            timed_out = True
            group_termination_attempted = True
            tracked_descendants.update(_descendant_processes(process.pid))
            cleanup_errors.extend(_terminate_process_group(process.pid, process))
            break
        time.sleep(min(0.01, max(timeout_sec / 100.0, 0.001)))

    try:
        returncode = process.wait(timeout=PROCESS_CLEANUP_WINDOW_SEC)
    except subprocess.TimeoutExpired:
        timed_out = True
        group_termination_attempted = True
        cleanup_errors.extend(_terminate_process_group(process.pid, process))
        try:
            returncode = process.wait(timeout=PROCESS_CLEANUP_WINDOW_SEC)
        except subprocess.TimeoutExpired:
            returncode = process.poll()
            cleanup_errors.append("direct validation process did not terminate within cleanup window")

    if not timed_out and _process_group_alive(process.pid):
        group_termination_attempted = True
        cleanup_errors.append("validation process group retained descendants after direct exit")
        cleanup_errors.extend(_terminate_process_group(process.pid, process))
        try:
            process.wait(timeout=PROCESS_CLEANUP_WINDOW_SEC)
        except subprocess.TimeoutExpired:
            cleanup_errors.append("descendant process group did not terminate within cleanup window")

    tracked_snapshot = _process_snapshot()
    live_tracked_descendants = {
        pid: start_ticks
        for pid, start_ticks in tracked_descendants.items()
        if pid in tracked_snapshot and tracked_snapshot[pid][1] == start_ticks
    }
    if live_tracked_descendants and not group_termination_attempted:
        group_termination_attempted = True
        cleanup_errors.append("validation process tree retained descendants after direct exit")

    if timed_out or group_termination_attempted:
        descendant_cleanup_errors, descendant_processes_alive = _terminate_descendants(
            tracked=tracked_descendants,
            timeout_sec=PROCESS_CLEANUP_WINDOW_SEC,
        )
    else:
        descendant_cleanup_errors, descendant_processes_alive = [], []
    cleanup_errors.extend(descendant_cleanup_errors)
    if subreaper_error:
        cleanup_errors.append(f"descendant cleanup control unavailable: {subreaper_error}")
    if descendant_processes_alive:
        cleanup_errors.append(
            "validation descendants remained alive after cleanup: "
            + ",".join(str(pid) for pid in descendant_processes_alive)
        )
    if process.poll() is None:
        try:
            process.wait(timeout=PROCESS_CLEANUP_WINDOW_SEC)
        except subprocess.TimeoutExpired:
            cleanup_errors.append("direct validation process did not terminate after descendant cleanup")

    reader_threads_alive = _join_readers(readers, PROCESS_CLEANUP_WINDOW_SEC)
    if reader_threads_alive:
        for pipe in (process.stdout, process.stderr):
            close_error = _close_pipe(pipe)
            if close_error:
                cleanup_errors.append(f"pipe close failed: {close_error}")
        reader_threads_alive = _join_readers(readers, PROCESS_CLEANUP_WINDOW_SEC)
    if reader_threads_alive:
        cleanup_errors.append(
            "reader threads remained alive: " + ",".join(reader_threads_alive)
        )

    process_group_alive = _wait_for_process_group_exit(process.pid, PROCESS_CLEANUP_WINDOW_SEC)
    if process_group_alive:
        cleanup_errors.append("validation process group remained alive after cleanup")
    process_terminated = process.poll() is not None
    if not process_terminated:
        cleanup_errors.append("validation process remained alive after cleanup")
    if previous_subreaper is False:
        restore_error = _set_child_subreaper(False)
        if restore_error:
            cleanup_errors.append(f"child subreaper restore failed: {restore_error}")
    elapsed = time.perf_counter() - started
    stdout = stdout_capture.result()
    stderr = stderr_capture.result()
    errors: list[tuple[str, str]] = []
    if timed_out:
        errors.append(("timeout", "node exceeded timeout_sec"))
    if stdout["decode_error"]:
        errors.append(("decode_error", f"stdout: {stdout['decode_error']}"))
    if stderr["decode_error"]:
        errors.append(("decode_error", f"stderr: {stderr['decode_error']}"))
    if stdout["transport_error"]:
        errors.append(("transport_error", f"stdout: {stdout['transport_error']}"))
    if stderr["transport_error"]:
        errors.append(("transport_error", f"stderr: {stderr['transport_error']}"))
    if cleanup_errors:
        errors.append(("cleanup_error", "; ".join(cleanup_errors)))
    error = None if not errors else {"type": errors[0][0], "detail": _short_error(errors[0][1])}
    return {
        "node_id": node.get("node_id"),
        "command": command,
        "ok": returncode == 0 and not timed_out and not errors,
        "returncode": 124 if timed_out else returncode,
        "timed_out": timed_out,
        "elapsed_sec": round(elapsed, 6),
        "children_max_rss_kib": peak_rss,
        "rss_measurement": {
            "method": "proc_status_vm_hwm",
            "scope": "direct_child_pid",
            "status": "measured" if peak_rss is not None else "unavailable",
            "peak_rss_kib": peak_rss,
        },
        "stdout_sha256": stdout["sha256"],
        "stderr_sha256": stderr["sha256"],
        "stdout_tail": stdout["tail"],
        "stderr_tail": stderr["tail"],
        "stdout_bytes": stdout["bytes"],
        "stderr_bytes": stderr["bytes"],
        "error": error,
        "environment_sha256": None if environment_identity is None else environment_identity.get("identity_sha256"),
        "cleanup": {
            "process_group": "isolated" if os.name == "posix" or hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else "direct_process",
            "process_group_termination_attempted": group_termination_attempted,
            "process_group_alive": process_group_alive,
            "process_terminated": process_terminated,
            "reader_threads_alive": reader_threads_alive,
            "descendant_processes_alive": descendant_processes_alive,
            "descendant_cleanup_attempted": previous_subreaper is not None,
            "errors": cleanup_errors[:8],
        },
        "cleanup_errors": cleanup_errors[:8],
    }


def _normalize_resource_decision(value: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, Mapping):
        return None, ["resource_decision must be a JSON object"]
    if not all(isinstance(key, str) for key in value):
        return None, ["resource_decision keys must be strings"]
    try:
        normalized = json.loads(_canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        return None, [f"resource_decision is not JSON-safe: {_short_error(str(exc))}"]
    errors = [
        f"resource_decision missing {field}"
        for field in RESOURCE_FIELDS
        if not isinstance(normalized.get(field), str) or not normalized[field]
    ]
    if normalized.get("admission") not in RESOURCE_ADMISSIONS:
        errors.append("resource_decision admission must be allow, deny, or not-provided")
    return (normalized, errors) if errors else (normalized, [])


def _command_graph_digest(nodes: Sequence[Mapping[str, Any]]) -> str:
    return _digest_value(
        [{"node_id": node.get("node_id"), "command": list(node.get("command", ()))} for node in nodes]
    )


def _resource_input(
    resource_admission: str | None,
    resource_decision: Mapping[str, Any] | None,
) -> Any:
    if resource_decision is not None:
        if resource_admission is not None and resource_decision.get("admission") != resource_admission:
            return {"_error": "resource_admission and resource_decision admission disagree"}
        return resource_decision
    if resource_admission is None:
        return None
    return {"admission": resource_admission}


def execute_plan(
    repo_root: Path,
    plan: Mapping[str, Any],
    *,
    resource_admission: str | None = None,
    run_full: bool = False,
    timeout_sec: float = 300.0,
    resource_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute serially only after a complete caller-owned resource decision."""

    timeout_sec = _validate_timeout_sec(timeout_sec)
    resource_input = _resource_input(resource_admission, resource_decision)
    normalized_resource, resource_errors = _normalize_resource_decision(resource_input)
    if normalized_resource is None or resource_errors:
        admission = None if normalized_resource is None else normalized_resource.get("admission")
        status = "not_run_resource_admission" if admission in {"deny", "not-provided"} else "not_run_resource_decision"
        return {
            "status": status,
            "resource_admission": admission,
            "resource_decision": normalized_resource,
            "resource_decision_input": resource_input,
            "resource_decision_errors": resource_errors,
            "timeout_sec": timeout_sec,
            "steps": [],
            "ok": False,
            "reason": "complete_resource_decision_required",
        }
    if normalized_resource["admission"] != "allow":
        return {
            "status": "not_run_resource_admission",
            "resource_admission": normalized_resource["admission"],
            "resource_decision": normalized_resource,
            "resource_decision_sha256": _digest_value(normalized_resource),
            "timeout_sec": timeout_sec,
            "steps": [],
            "ok": False,
            "reason": "resource_admission_must_be_allow",
        }

    env = _execution_environment(repo_root)
    python_executable = _validate_owner_python_executable(plan.get("python_executable"))
    if plan.get("python_executable_sha256") != _sha256(Path(python_executable)):
        raise ValidationInputError("full-gate executable identity does not match the owner interpreter")
    environment_identity = _environment_identity(repo_root, env, python_executable=python_executable)
    nodes = list(plan["selected"])
    if bool(plan["fallback"]["required"]) or run_full:
        nodes.append(plan["full_gate"]["node"])
    steps: list[dict[str, Any]] = []
    for node in nodes:
        step = _run_node(
            repo_root,
            node,
            timeout_sec,
            env=env,
            environment_identity=environment_identity,
        )
        step.setdefault("environment_sha256", environment_identity["identity_sha256"])
        steps.append(step)
    full_step = next((step for step in steps if step["node_id"] == FULL_GATE_ID), None)
    if full_step is not None:
        plan["full_gate"]["status"] = "passed" if full_step["ok"] else "failed"
    return {
        "status": "completed",
        "resource_admission": normalized_resource["admission"],
        "resource_decision": normalized_resource,
        "resource_decision_sha256": _digest_value(normalized_resource),
        "timeout_sec": timeout_sec,
        "environment": environment_identity,
        "command_graph_sha256": _command_graph_digest(nodes),
        "steps": steps,
        "ok": bool(steps) and all(step["ok"] for step in steps),
        "reason": None,
    }


def _validate_identity(repo_root: Path, identity: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "workspace",
        "base_ref",
        "base_sha",
        "base_tree",
        "candidate_ref",
        "candidate_sha",
        "candidate_tree",
        "worktree_state",
        "worktree_status_sha256",
        "worktree_ignored_status_sha256",
        "index_sha256",
        "staged_content_sha256",
        "unstaged_content_sha256",
        "untracked_content_sha256",
        "ignored_content_sha256",
        "worktree_content_sha256",
    }
    missing = sorted(key for key in required if key not in identity)
    if missing:
        raise ValidationInputError(f"candidate identity missing: {', '.join(missing)}")
    try:
        workspace = Path(str(identity["workspace"])).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValidationInputError(f"candidate workspace is invalid: {_short_error(str(exc))}") from exc
    if workspace != repo_root.resolve():
        raise ValidationInputError("candidate workspace identity does not match receipt repository")
    expected = candidate_identity(repo_root, str(identity["base_ref"]), str(identity["candidate_ref"]))
    actual_head = _ref(repo_root, "HEAD", "^{commit}")
    actual_tree = _ref(repo_root, "HEAD", "^{tree}")
    if expected["candidate_sha"] != actual_head:
        raise ValidationInputError("candidate ref does not match the executed worktree HEAD")
    if expected["candidate_tree"] != actual_tree:
        raise ValidationInputError("candidate ref does not match the executed worktree tree")
    for key, expected_value in expected.items():
        if identity.get(key) != expected_value:
            raise ValidationInputError(f"candidate identity mismatch: {key}")
    return expected


def _validate_plan(
    repo_root: Path,
    plan: Mapping[str, Any],
    identity: Mapping[str, Any],
) -> None:
    required = {
        "plan_sha256",
        "python_executable",
        "python_executable_sha256",
        "changed_paths",
        "selected",
        "skipped",
        "fallback",
        "full_gate",
        "unmapped_paths",
        "unmapped_reasons",
    }
    missing = sorted(key for key in required if key not in plan)
    if missing:
        raise ValidationInputError(f"validation plan missing: {', '.join(missing)}")
    if not isinstance(plan["changed_paths"], list):
        raise ValidationInputError("validation plan changed_paths must be a list")
    if not isinstance(plan["selected"], list) or not isinstance(plan["skipped"], list):
        raise ValidationInputError("validation plan selection fields must be lists")
    if not isinstance(plan["full_gate"], Mapping) or not isinstance(plan["fallback"], Mapping):
        raise ValidationInputError("validation plan gate fields must be mappings")
    if plan["plan_sha256"] != _plan_digest(plan):
        raise ValidationInputError("validation plan digest mismatch")
    if plan["full_gate"]["required"] is not True or plan["fallback"]["node_id"] != FULL_GATE_ID:
        raise ValidationInputError("validation plan full-gate boundary is invalid")
    python_executable = _validate_owner_python_executable(plan["python_executable"])
    actual_executable_sha256 = _sha256(Path(python_executable))
    if plan["python_executable_sha256"] != actual_executable_sha256:
        raise ValidationInputError("full-gate executable identity does not match the owner interpreter")
    expected_changed_paths = changed_paths(
        repo_root,
        str(identity["base_ref"]),
        str(identity["candidate_ref"]),
    )
    if plan["changed_paths"] != expected_changed_paths:
        raise ValidationInputError("validation plan changed_paths do not match the exact base/candidate Git diff")
    expected = build_plan(
        expected_changed_paths,
        repo_root,
        python_executable=python_executable,
    )
    if identity.get("worktree_state") != "clean":
        _force_full_gate_for_dirty_worktree(expected, identity)
    if _plan_payload(expected) != _plan_payload(plan):
        raise ValidationInputError("validation plan routing or command binding does not match source")


def _is_sha256_text(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _step_validation_errors(index: int, step: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = f"step[{index}]"
    returncode = step.get("returncode")
    if returncode is not None and (not isinstance(returncode, int) or isinstance(returncode, bool)):
        errors.append(f"{prefix} returncode is invalid")
    timed_out = step.get("timed_out")
    if not isinstance(timed_out, bool):
        errors.append(f"{prefix} timed_out must be boolean")
    for field in ("stdout_sha256", "stderr_sha256"):
        if not _is_sha256_text(step.get(field)):
            errors.append(f"{prefix} {field} is invalid")
    for field in ("stdout_tail", "stderr_tail"):
        value = step.get(field)
        if not isinstance(value, str) or len(value) > MAX_OUTPUT_CHARS:
            errors.append(f"{prefix} {field} is not bounded")
    for field in ("stdout_bytes", "stderr_bytes"):
        value = step.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{prefix} {field} is invalid")
    if not _valid_elapsed_sec(step.get("elapsed_sec")):
        errors.append(f"{prefix} elapsed_sec is invalid")
    error = step.get("error")
    if error is not None and (
        not isinstance(error, Mapping)
        or not isinstance(error.get("type"), str)
        or not error.get("type")
        or not isinstance(error.get("detail"), str)
    ):
        errors.append(f"{prefix} error envelope is invalid")
    error_type = error.get("type") if isinstance(error, Mapping) else None
    if (
        isinstance(timed_out, bool)
        and (returncode is None or (isinstance(returncode, int) and not isinstance(returncode, bool)))
    ):
        expected_ok = returncode == 0 and not timed_out and error is None
        if isinstance(step.get("ok"), bool) and step["ok"] != expected_ok:
            errors.append(f"{prefix} ok is inconsistent with returncode, timeout, and error")
    if returncode is None and error is None:
        errors.append(f"{prefix} missing returncode requires an error envelope")
    if timed_out is True:
        if returncode != 124:
            errors.append(f"{prefix} timeout must use returncode 124")
        if error_type != "timeout":
            errors.append(f"{prefix} timeout requires a timeout error envelope")
    elif error_type == "timeout":
        errors.append(f"{prefix} timeout error requires timed_out=true")
    if error_type == "spawn_error" and returncode is not None:
        errors.append(f"{prefix} spawn error must not have a returncode")
    rss = step.get("rss_measurement")
    if not isinstance(rss, Mapping):
        errors.append(f"{prefix} rss_measurement is not bound")
    else:
        if rss.get("scope") != "direct_child_pid":
            errors.append(f"{prefix} rss_measurement scope is not direct_child_pid")
        if not isinstance(rss.get("method"), str) or not isinstance(rss.get("status"), str):
            errors.append(f"{prefix} rss_measurement metadata is invalid")
        peak = rss.get("peak_rss_kib")
        if peak is not None and (not isinstance(peak, int) or isinstance(peak, bool) or peak < 0):
            errors.append(f"{prefix} rss_measurement peak is invalid")
    legacy_peak = step.get("children_max_rss_kib")
    if legacy_peak is not None and (
        not isinstance(legacy_peak, int) or isinstance(legacy_peak, bool) or legacy_peak < 0
    ):
        errors.append(f"{prefix} children_max_rss_kib is invalid")
    if not _is_sha256_text(step.get("environment_sha256")):
        errors.append(f"{prefix} environment identity is not bound")
    cleanup_errors = step.get("cleanup_errors")
    if not isinstance(cleanup_errors, list) or (
        any(not isinstance(value, str) or len(value) > 400 for value in cleanup_errors)
    ):
        errors.append(f"{prefix} cleanup error list is invalid")
    cleanup = step.get("cleanup")
    if not isinstance(cleanup, Mapping):
        errors.append(f"{prefix} cleanup envelope is required")
    else:
        if cleanup.get("process_group") not in {"isolated", "direct_process", "not_started"}:
            errors.append(f"{prefix} process group cleanup mode is invalid")
        for field in ("process_group_termination_attempted", "process_group_alive", "process_terminated"):
            if not isinstance(cleanup.get(field), bool):
                errors.append(f"{prefix} cleanup field {field} is invalid")
        if cleanup.get("process_terminated") is not True:
            errors.append(f"{prefix} process cleanup is incomplete")
        if cleanup.get("process_group_alive") is True:
            errors.append(f"{prefix} process group cleanup is incomplete")
        reader_threads = cleanup.get("reader_threads_alive")
        if not isinstance(reader_threads, list) or any(not isinstance(value, str) for value in reader_threads):
            errors.append(f"{prefix} reader cleanup state is invalid")
        elif reader_threads:
            errors.append(f"{prefix} reader cleanup is incomplete")
        reported_errors = cleanup.get("errors")
        if not isinstance(reported_errors, list) or any(
            not isinstance(value, str) or len(value) > 400 for value in reported_errors
        ):
            errors.append(f"{prefix} cleanup envelope errors are invalid")
        else:
            if isinstance(cleanup_errors, list) and cleanup_errors != reported_errors:
                errors.append(f"{prefix} cleanup error channels do not match")
            if reported_errors:
                errors.append(f"{prefix} cleanup envelope reports failure")
        descendant_processes_alive = cleanup.get("descendant_processes_alive")
        if not isinstance(descendant_processes_alive, list) or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in descendant_processes_alive
        ):
            errors.append(f"{prefix} descendant cleanup state is invalid")
        elif descendant_processes_alive:
            errors.append(f"{prefix} descendant cleanup is incomplete")
        if not isinstance(cleanup.get("descendant_cleanup_attempted"), bool):
            errors.append(f"{prefix} descendant cleanup attempt is not bound")
        elif cleanup.get("descendant_cleanup_attempted") is not True:
            errors.append(f"{prefix} descendant cleanup was not attempted")
    if isinstance(cleanup_errors, list) and cleanup_errors:
        errors.append(f"{prefix} cleanup error list reports failure")
    return errors


def _normalize_execution(
    plan: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str], dict[str, Any] | None, list[str]]:
    if not isinstance(execution, Mapping):
        raise ValidationInputError("execution must be a mapping")
    status = execution.get("status")
    allowed_statuses = {"completed", "plan_only", "not_run_resource_admission", "not_run_resource_decision"}
    if status not in allowed_statuses:
        raise ValidationInputError("execution status is not recognized")
    raw_steps = execution.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValidationInputError("execution steps must be a list")
    expected_nodes = {
        node["node_id"]: node
        for node in list(plan["selected"]) + [plan["full_gate"]["node"]]
    }
    normalized_steps: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, Mapping):
            errors.append(f"step[{index}] is not an object")
            continue
        node_id = raw_step.get("node_id")
        if node_id not in expected_nodes:
            errors.append(f"step[{index}] node is not in the plan")
        elif node_id in seen:
            errors.append(f"step[{index}] node is duplicated")
        else:
            seen.add(node_id)
        step = dict(raw_step)
        expected_command = expected_nodes.get(node_id, {}).get("command")
        if "command" not in step:
            errors.append(f"step[{index}] command is not bound")
        elif step["command"] != expected_command:
            errors.append(f"step[{index}] command does not match the plan")
        if not isinstance(step.get("ok"), bool):
            errors.append(f"step[{index}] ok must be boolean")
        if not _valid_elapsed_sec(step.get("elapsed_sec")):
            errors.append(f"step[{index}] elapsed_sec is invalid")
        errors.extend(_step_validation_errors(index, step))
        normalized_steps.append(step)

    actual_ids = [step.get("node_id") for step in normalized_steps]
    required_ids = [node["node_id"] for node in plan["selected"]]
    if plan["fallback"]["required"]:
        allowed_sequences = [required_ids + [FULL_GATE_ID]]
    else:
        allowed_sequences = [required_ids, required_ids + [FULL_GATE_ID]]
    if status == "completed":
        if actual_ids not in allowed_sequences:
            errors.append("completed execution does not contain the exact planned node sequence")
    elif actual_ids:
        errors.append("non-completed execution must not contain validation steps")

    normalized_resource, resource_errors = _normalize_resource_decision(execution.get("resource_decision"))
    errors.extend(resource_errors)
    if normalized_resource is None:
        errors.append("execution resource decision is not bound")
    else:
        if execution.get("resource_admission") != normalized_resource["admission"]:
            errors.append("execution resource admission does not match its decision")
        supplied_resource_hash = execution.get("resource_decision_sha256")
        expected_resource_hash = _digest_value(normalized_resource)
        if supplied_resource_hash != expected_resource_hash:
            errors.append("execution resource decision digest does not match its decision")
    supplied_timeout = execution.get("timeout_sec")
    if supplied_timeout is not None:
        try:
            normalized_timeout = _validate_timeout_sec(supplied_timeout)
        except ValidationInputError as exc:
            errors.append(str(exc))
        else:
            normalized_timeout = float(normalized_timeout)
    else:
        normalized_timeout = None
        errors.append("execution timeout_sec is required")
    if status == "completed" and (
        normalized_resource is None
        or normalized_resource.get("admission") != "allow"
        or execution.get("resource_admission") != "allow"
    ):
        errors.append("completed execution requires resource admission=allow")
    expected_ok = status == "completed" and bool(normalized_steps) and not errors and all(
        step.get("ok") is True for step in normalized_steps
    )
    claimed_ok = execution.get("ok")
    if not isinstance(claimed_ok, bool):
        errors.append("execution ok must be boolean")
    elif claimed_ok != expected_ok:
        errors.append("execution ok does not match step aggregate")
    normalized = dict(execution)
    normalized["steps"] = normalized_steps
    if normalized_timeout is not None:
        normalized["timeout_sec"] = normalized_timeout
    normalized["ok"] = expected_ok
    normalized["claimed_ok"] = claimed_ok
    normalized["validation_errors"] = errors
    return normalized, errors, normalized_resource, resource_errors


def make_receipt(
    repo_root: Path,
    identity: Mapping[str, Any],
    plan: dict[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    validated_identity = _validate_identity(repo_root, identity)
    _validate_plan(repo_root, plan, validated_identity)
    normalized_execution, execution_errors, resource_decision, resource_errors = _normalize_execution(plan, execution)
    expected_environment = _environment_identity(
        repo_root,
        _execution_environment(repo_root),
        python_executable=str(plan["python_executable"]),
    )
    supplied_environment = normalized_execution.get("environment")
    if supplied_environment is not None and supplied_environment != expected_environment:
        execution_errors.append("execution environment identity does not match current environment")
    normalized_execution["environment"] = expected_environment
    for index, step in enumerate(normalized_execution.get("steps", [])):
        if step.get("environment_sha256") != expected_environment["identity_sha256"]:
            execution_errors.append(f"step[{index}] environment identity does not match current environment")
    if normalized_execution.get("status") == "completed":
        expected_by_id = {
            node["node_id"]: node
            for node in list(plan["selected"]) + [plan["full_gate"]["node"]]
        }
        expected_nodes = [expected_by_id[step["node_id"]] for step in normalized_execution["steps"] if step.get("node_id") in expected_by_id]
        expected_graph = _command_graph_digest(expected_nodes)
        supplied_graph = normalized_execution.get("command_graph_sha256")
        if supplied_graph is not None and supplied_graph != expected_graph:
            execution_errors.append("execution command graph does not match the plan")
        normalized_execution["command_graph_sha256"] = expected_graph
    normalized_execution["validation_errors"] = execution_errors
    normalized_execution["ok"] = (
        normalized_execution.get("status") == "completed"
        and bool(normalized_execution.get("steps"))
        and not execution_errors
        and all(step.get("ok") is True for step in normalized_execution["steps"])
    )

    steps = list(normalized_execution.get("steps", []))
    failed_steps = [step.get("node_id") for step in steps if step.get("ok") is not True]
    full_step = next((step for step in steps if step.get("node_id") == FULL_GATE_ID), None)
    selected_failures = [node_id for node_id in failed_steps if node_id != FULL_GATE_ID]
    if full_step is None:
        full_gate_status = "not_run"
    else:
        full_gate_status = "passed" if full_step.get("ok") is True else "failed"
    if normalized_execution.get("status") == "plan_only":
        proof_status = "plan_only"
    elif normalized_execution.get("status") == "not_run_resource_admission":
        proof_status = "not_run_resource_admission"
    elif normalized_execution.get("status") == "not_run_resource_decision":
        proof_status = "not_run_resource_decision"
    elif execution_errors:
        proof_status = "incomplete_execution"
    elif failed_steps:
        proof_status = "required_step_failed"
    elif full_step is not None:
        proof_status = "full_gate_passed"
    elif steps:
        proof_status = "contextual_candidate_passed"
    else:
        proof_status = "not_run"

    resource_payload: dict[str, Any] = {
        "decision": resource_decision,
        "decision_sha256": None if resource_decision is None else _digest_value(resource_decision),
        "validation": "passed" if resource_decision is not None and not resource_errors else "failed",
        "validation_errors": resource_errors,
        "mutation_scope": "isolated_source_checkout_only",
    }
    if resource_decision is not None and not resource_errors:
        for field in RESOURCE_FIELDS:
            resource_payload[field] = resource_decision[field]
        if "source" in resource_decision:
            resource_payload["source"] = resource_decision["source"]

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route": {
            "kind": "contextual_changed_surface",
            "serial_execution": True,
            "selection_is_not_sufficiency": True,
            "dirty_worktree_is_fail_closed": True,
            "changed_tests_and_validators_require_full_gate": True,
        },
        "candidate": validated_identity,
        "environment": expected_environment,
        "selection": {
            "plan_sha256": plan["plan_sha256"],
            "changed_paths": plan["changed_paths"],
            "selected": plan["selected"],
            "skipped": plan["skipped"],
            "fallback": plan["fallback"],
            "unmapped_paths": plan["unmapped_paths"],
            "unmapped_reasons": plan["unmapped_reasons"],
        },
        "cache": {
            "pytest_cache": "disabled",
            "bytecode": "disabled",
            "receipt_reuse": "not_implemented",
            "reuse_decision": "not_used; exact sealed receipt reuse is outside this bounded slice",
        },
        "resource": resource_payload,
        "execution": normalized_execution,
        "proof": {
            "status": proof_status,
            "full_gate_required": True,
            "full_gate_status": full_gate_status,
            "failed_steps": failed_steps,
            "selected_failures": selected_failures,
            "execution_validation_errors": execution_errors,
            "owner_acceptance": False,
            "unvalidated_claims": [
                "owner-wide coverage outside selected changed surfaces",
                "artifact, portability, integration, live, adversarial, and E2E evidence",
                "freshness/trust of any external or generated evidence",
            ],
        },
        "ok": bool(normalized_execution["ok"]),
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _approved_receipt_path(repo_root: Path, receipt_path: Path) -> Path:
    root_text = os.environ.get(RECEIPT_ROOT_ENV)
    if not root_text:
        raise ReceiptPathError(f"{RECEIPT_ROOT_ENV} must name the approved task-local root")
    root = Path(root_text)
    if not root.is_absolute():
        raise ReceiptPathError("approved receipt root must be absolute")
    try:
        root = root.resolve(strict=True)
        repo = repo_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ReceiptPathError(f"receipt root cannot be resolved: {_short_error(str(exc))}") from exc
    if root == Path(root.anchor) or root == repo or _is_relative_to(root, repo) or _is_relative_to(repo, root):
        raise ReceiptPathError("receipt root must be a narrow task-local root outside the source checkout")
    try:
        root_info = root.stat()
    except OSError as exc:
        raise ReceiptPathError(f"approved receipt root cannot be inspected: {_short_error(str(exc))}") from exc
    if not stat.S_ISDIR(root_info.st_mode):
        raise ReceiptPathError("approved receipt root must be a directory")
    target = receipt_path if receipt_path.is_absolute() else root / receipt_path
    target = target.resolve(strict=False)
    if _is_relative_to(target, repo):
        raise ReceiptPathError("receipt path may not target the source checkout")
    if not _is_relative_to(target, root):
        raise ReceiptPathError("receipt path escapes the approved task-local root")
    parent = target.parent
    try:
        parent_is_dir = parent.is_dir()
    except OSError as exc:
        raise ReceiptPathError(f"receipt parent cannot be inspected: {_short_error(str(exc))}") from exc
    if not parent_is_dir:
        raise ReceiptPathError("receipt parent must already exist")
    if os.path.lexists(target):
        raise ReceiptPathError("receipt path already exists; refusing overwrite")
    return target


def _receipt_open_flags(*, directory: bool = False) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


def _same_directory(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(left.st_mode)
        and stat.S_ISDIR(right.st_mode)
        and left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
    )


def _fd_realpath(fd: int) -> Path | None:
    if os.name != "posix":
        return None
    try:
        return Path(os.path.realpath(f"/proc/self/fd/{fd}"))
    except OSError:
        return None


def _receipt_binding_errors(
    root_fd: int,
    parent_fd: int,
    root: Path,
    expected_root: os.stat_result,
    expected_parent: os.stat_result,
) -> list[str]:
    errors: list[str] = []
    try:
        actual_root = os.fstat(root_fd)
        actual_parent = os.fstat(parent_fd)
    except OSError as exc:
        return [f"receipt directory identity could not be checked: {_short_error(str(exc))}"]
    if not _same_directory(actual_root, expected_root):
        errors.append("approved receipt root changed during delivery")
    if not _same_directory(actual_parent, expected_parent):
        errors.append("receipt parent changed during delivery")
    root_path = _fd_realpath(root_fd)
    if root_path is not None and root_path != root:
        errors.append("approved receipt root moved outside its validated path")
    parent_path = _fd_realpath(parent_fd)
    if parent_path is not None and not (parent_path == root or _is_relative_to(parent_path, root)):
        errors.append("receipt parent moved outside the approved root")
    return errors


def _receipt_path_binding_errors(root: Path, parts: Sequence[str], expected_root: os.stat_result, expected_parent: os.stat_result) -> list[str]:
    """Re-check the approved path, not only the directory fds, before commit."""

    errors: list[str] = []
    try:
        actual_root = root.lstat()
    except OSError as exc:
        return [f"approved receipt root path could not be checked: {_short_error(str(exc))}"]
    if not _same_directory(actual_root, expected_root):
        errors.append("approved receipt root path changed during delivery")
    current = root
    for component in parts[:-1]:
        current = current / component
        try:
            info = current.lstat()
        except OSError as exc:
            errors.append(f"receipt parent path could not be checked: {_short_error(str(exc))}")
            break
        if not stat.S_ISDIR(info.st_mode):
            errors.append("receipt parent path is no longer a directory")
            break
    else:
        try:
            actual_parent = current.lstat()
        except OSError as exc:
            errors.append(f"receipt parent path could not be checked: {_short_error(str(exc))}")
        else:
            if not _same_directory(actual_parent, expected_parent):
                errors.append("receipt parent path changed during delivery")
        try:
            target_info = (current / parts[-1]).lstat()
        except OSError as exc:
            errors.append(f"receipt target path could not be checked: {_short_error(str(exc))}")
        else:
            if not stat.S_ISREG(target_info.st_mode):
                errors.append("receipt target path is not a regular file")
    return errors


def _open_receipt_directory(name: str, *, dir_fd: int | None = None) -> int:
    flags = _receipt_open_flags(directory=True)
    if dir_fd is None:
        return os.open(name, flags)
    return os.open(name, flags, dir_fd=dir_fd)


def _receipt_context(
    repo_root: Path,
    receipt_path: Path,
) -> tuple[Path, Path, tuple[str, ...], os.stat_result, os.stat_result]:
    target = _approved_receipt_path(repo_root, receipt_path)
    root_text = os.environ.get(RECEIPT_ROOT_ENV)
    if not root_text:
        raise ReceiptPathError(f"{RECEIPT_ROOT_ENV} must name the approved task-local root")
    root = Path(root_text).resolve(strict=True)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ReceiptPathError("receipt path escapes the approved task-local root") from exc
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ReceiptPathError("receipt path must name a file below the approved task-local root")
    try:
        expected_root = root.stat()
        expected_parent = target.parent.stat()
    except OSError as exc:
        raise ReceiptPathError(f"receipt directory identity could not be captured: {_short_error(str(exc))}") from exc
    if not stat.S_ISDIR(expected_root.st_mode) or not stat.S_ISDIR(expected_parent.st_mode):
        raise ReceiptPathError("receipt root and parent must be directories")
    return root, target, parts, expected_root, expected_parent


def _open_receipt_temp(parent_fd: int) -> tuple[int, str]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    for _ in range(RECEIPT_TEMP_ATTEMPTS):
        name = f".validation-receipt.{secrets.token_hex(12)}"
        try:
            return os.open(name, flags, 0o600, dir_fd=parent_fd), name
        except FileExistsError:
            continue
    raise ReceiptPathError("could not allocate a unique receipt temporary file")


def write_receipt_atomic(repo_root: Path, receipt_path: Path, rendered: str) -> Path:
    """Write a new task-local receipt atomically without replacing an existing file."""

    try:
        root, target, parts, expected_root, expected_parent = _receipt_context(repo_root, receipt_path)
    except ReceiptPathError:
        raise
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise ReceiptPathError(f"receipt delivery failed: {_short_error(str(exc))}") from exc
    root_fd: int | None = None
    parent_fd: int | None = None
    temporary_name: str | None = None
    target_name = parts[-1]
    linked = False
    committed = False
    delivery_error: ReceiptPathError | None = None
    cleanup_errors: list[str] = []
    try:
        root_fd = _open_receipt_directory(str(root))
        parent_fd = root_fd
        for component in parts[:-1]:
            next_fd = _open_receipt_directory(component, dir_fd=parent_fd)
            if parent_fd != root_fd:
                os.close(parent_fd)
            parent_fd = next_fd
        binding_errors = _receipt_binding_errors(
            root_fd,
            parent_fd,
            root,
            expected_root,
            expected_parent,
        )
        if binding_errors:
            raise ReceiptPathError("; ".join(binding_errors))

        try:
            os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ReceiptPathError("receipt path already exists; refusing overwrite")

        temporary_fd, temporary_name = _open_receipt_temp(parent_fd)
        payload = rendered.encode("utf-8")
        with os.fdopen(temporary_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        binding_errors = _receipt_binding_errors(
            root_fd,
            parent_fd,
            root,
            expected_root,
            expected_parent,
        )
        if binding_errors:
            raise ReceiptPathError("; ".join(binding_errors))
        try:
            os.link(
                temporary_name,
                target_name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
            linked = True
        except FileExistsError as exc:
            raise ReceiptPathError("receipt path appeared during atomic create; refusing overwrite") from exc

        binding_errors = _receipt_binding_errors(
            root_fd,
            parent_fd,
            root,
            expected_root,
            expected_parent,
        )
        if binding_errors:
            raise ReceiptPathError("; ".join(binding_errors))

        os.unlink(temporary_name, dir_fd=parent_fd)
        temporary_name = None
        os.fsync(parent_fd)
        binding_errors = _receipt_binding_errors(
            root_fd,
            parent_fd,
            root,
            expected_root,
            expected_parent,
        )
        if binding_errors:
            raise ReceiptPathError("; ".join(binding_errors))
        path_binding_errors = _receipt_path_binding_errors(root, parts, expected_root, expected_parent)
        if path_binding_errors:
            raise ReceiptPathError("; ".join(path_binding_errors))
        committed = True
    except ReceiptPathError as exc:
        delivery_error = exc
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        delivery_error = ReceiptPathError(f"receipt delivery failed: {_short_error(str(exc))}")
    finally:
        if not committed and linked and parent_fd is not None:
            try:
                os.unlink(target_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            except OSError as exc:
                cleanup_errors.append(f"receipt target cleanup failed: {_short_error(str(exc))}")
        if temporary_name is not None and parent_fd is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            except OSError as exc:
                cleanup_errors.append(f"receipt temporary unlink failed: {_short_error(str(exc))}")
        if parent_fd is not None and parent_fd != root_fd:
            try:
                os.close(parent_fd)
            except OSError as exc:
                cleanup_errors.append(f"receipt parent fd close failed: {_short_error(str(exc))}")
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError as exc:
                cleanup_errors.append(f"receipt root fd close failed: {_short_error(str(exc))}")
    if cleanup_errors:
        cleanup_detail = "; ".join(cleanup_errors)
        if delivery_error is None:
            raise ReceiptPathError(f"receipt delivery cleanup failed: {cleanup_detail}")
        raise ReceiptPathError(f"{delivery_error}; cleanup failure: {cleanup_detail}") from delivery_error
    if delivery_error is not None:
        raise delivery_error
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base commit/ref for changed-surface diff")
    parser.add_argument("--candidate", default="HEAD", help="candidate commit/ref (default: HEAD)")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="isolated repository root")
    parser.add_argument(
        "--include-worktree",
        action="store_true",
        help="compatibility flag; dirty inputs are already bound by identity and fail closed",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="compatibility flag; dirty worktrees still fail closed to the full gate",
    )
    parser.add_argument(
        "--resource-admission",
        choices=("allow", "deny", "not-provided"),
        default="not-provided",
        help="compatibility admission value; allow still requires --resource-decision",
    )
    parser.add_argument(
        "--resource-decision",
        help="complete caller-owned resource decision as a JSON object",
    )
    parser.add_argument("--run-full", action="store_true", help="append the unchanged source-fast gate")
    parser.add_argument("--plan-only", action="store_true", help="emit selection without executing commands")
    parser.add_argument("--timeout-sec", type=float, default=300.0)
    parser.add_argument("--receipt", type=Path, help="task-local JSON receipt path under the approved root")
    return parser


def _resource_decision_argument(args: argparse.Namespace) -> Any:
    if args.resource_decision is None:
        return {"admission": args.resource_admission}
    try:
        value = json.loads(args.resource_decision)
    except json.JSONDecodeError as exc:
        return {"admission": args.resource_admission, "_parse_error": _short_error(str(exc))}
    if args.resource_admission != "not-provided" and isinstance(value, Mapping):
        if value.get("admission") != args.resource_admission:
            return {"admission": args.resource_admission, "_error": "CLI admission disagrees with JSON decision"}
    return value


def _plan_only_execution(
    repo_root: Path,
    plan: Mapping[str, Any],
    resource_input: Any,
    *,
    timeout_sec: float,
) -> dict[str, Any]:
    timeout_sec = _validate_timeout_sec(timeout_sec)
    normalized, errors = _normalize_resource_decision(resource_input)
    return {
        "status": "plan_only",
        "resource_admission": None if normalized is None else normalized.get("admission"),
        "resource_decision": normalized,
        "resource_decision_sha256": None if normalized is None else _digest_value(normalized),
        "resource_decision_input": resource_input,
        "resource_decision_errors": errors,
        "timeout_sec": timeout_sec,
        "environment": _environment_identity(
            repo_root,
            _execution_environment(repo_root),
            python_executable=str(plan["python_executable"]),
        ),
        "steps": [],
        "ok": False,
        "reason": "plan_only_does_not_execute_validation",
    }


def _force_full_gate_for_dirty_worktree(plan: dict[str, Any], identity: Mapping[str, Any]) -> None:
    if identity.get("worktree_state") == "clean":
        return
    plan["selected"] = []
    plan["skipped"].append(
        {
            "surface": "worktree",
            "reason": "dirty_index_staged_unstaged_untracked_or_ignored_inputs_require_full_gate",
            "action": "expand_to_full_gate",
            "identity_fields": [
                "index_sha256",
                "staged_content_sha256",
                "unstaged_content_sha256",
                "untracked_content_sha256",
                "ignored_content_sha256",
            ],
        }
    )
    plan["fallback"] = {
        "required": True,
        "reason": "dirty_worktree_requires_unchanged_full_gate",
        "command": plan["full_gate"]["node"]["command"],
        "node_id": FULL_GATE_ID,
    }
    plan["plan_sha256"] = _plan_digest(plan)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo.resolve()
    try:
        timeout_sec = _validate_timeout_sec(args.timeout_sec)
        identity = candidate_identity(repo_root, args.base, args.candidate)
        # Routing is always derived from the immutable base/candidate diff.
        # Dirty index/worktree inputs remain bound in candidate_identity and
        # force the unchanged full gate; they must not become caller-selected
        # changed paths.
        paths = changed_paths(repo_root, args.base, args.candidate)
        plan = build_plan(paths, repo_root)
        _force_full_gate_for_dirty_worktree(plan, identity)
        resource_input = _resource_decision_argument(args)
        if args.plan_only:
            execution = _plan_only_execution(
                repo_root,
                plan,
                resource_input,
                timeout_sec=timeout_sec,
            )
        else:
            normalized, errors = _normalize_resource_decision(resource_input)
            if errors:
                execution = execute_plan(
                    repo_root,
                    plan,
                    run_full=args.run_full,
                    timeout_sec=timeout_sec,
                    resource_decision=resource_input if isinstance(resource_input, Mapping) else None,
                )
            else:
                execution = execute_plan(
                    repo_root,
                    plan,
                    run_full=args.run_full,
                    timeout_sec=timeout_sec,
                    resource_decision=normalized,
                )
        receipt = make_receipt(repo_root, identity, plan, execution)
    except (RuntimeError, ValidationInputError) as exc:
        print(json.dumps({"schema": SCHEMA, "ok": False, "error": str(exc)}, sort_keys=True))
        return 1

    if args.receipt:
        try:
            write_receipt_atomic(repo_root, args.receipt, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        except ReceiptPathError as exc:
            receipt["ok"] = False
            receipt["proof"]["status"] = "receipt_delivery_failed"
            receipt["proof"]["execution_validation_errors"].append(str(exc))
            receipt["execution"]["ok"] = False
            receipt["execution"]["validation_errors"].append(str(exc))

    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
