#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import validation_evidence_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
METHODS = ("xdist-2", "xdist-4", "static-2")
CANONICAL_PYTEST_ARGV = ["{python}", "-m", "pytest", "-q"]


class ExperimentError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _artifact_path(receipt: Path, label: str) -> Path:
    suffix = receipt.suffix or ".json"
    stem = receipt.name[: -len(suffix)] if receipt.suffix else receipt.name
    return receipt.with_name(f"{stem}.{label}{suffix}")


def experimental_pytest_argv(method: str, static_receipt: Path) -> list[str]:
    if method.startswith("xdist-"):
        return [*CANONICAL_PYTEST_ARGV, "-n", method.removeprefix("xdist-")]
    if method == "static-2":
        return [
            "{python}",
            "scripts/pytest_scheduler_experiment.py",
            "--method",
            method,
            "--receipt",
            static_receipt.relative_to(REPO_ROOT).as_posix(),
        ]
    raise ExperimentError(f"unknown scheduler method: {method}")


def build_experimental_manifest(method: str, static_receipt: Path) -> dict[str, Any]:
    validation_evidence_graph.require_exact_serial_inventory()
    payload = json.loads(validation_evidence_graph.MANIFEST_PATH.read_text(encoding="utf-8"))
    pytest_node = next(
        (node for node in payload["nodes"] if node["id"] == "public-smoke-tests"),
        None,
    )
    if pytest_node is None or len(pytest_node["steps"]) != 1:
        raise ExperimentError("canonical public-smoke-tests node is unavailable or ambiguous")
    actual = pytest_node["steps"][0]["argv"]
    if actual != CANONICAL_PYTEST_ARGV:
        raise ExperimentError(
            "canonical pytest command changed; refusing an unreviewed scheduler comparison: "
            + json.dumps(actual)
        )
    pytest_node["steps"][0]["argv"] = experimental_pytest_argv(method, static_receipt)
    payload["graph_id"] = f"abyss-machine-repo-validation-{method}-shadow-v1"
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare one pytest scheduler inside the complete owner DAG without authorizing "
            "the owner gate."
        )
    )
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--graph-workers", required=True, type=int, choices=(2, 3))
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--sdk-root",
        type=Path,
        default=Path(
            os.environ.get(
                validation_evidence_graph.SDK_ROOT_ENV,
                REPO_ROOT / ".deps" / "aoa-sdk",
            )
        ),
    )
    return parser


def _graph_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "elapsed_seconds": receipt.get("elapsed_seconds"),
        "routing": receipt.get("routing"),
        "repository_identity": receipt.get("repository_identity"),
        "runner_identity": receipt.get("runner_identity"),
        "evidence": receipt.get("evidence"),
        "decision": receipt.get("decision"),
        "node_results": [
            {
                "id": node.get("id"),
                "status": node.get("status"),
                "duration_seconds": node.get("duration_seconds"),
            }
            for node in receipt.get("node_results", [])
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started_at = dt.datetime.now(dt.UTC)
    receipt_path = args.receipt.resolve()
    graph_receipt_path = _artifact_path(receipt_path, "graph")
    manifest_artifact_path = _artifact_path(receipt_path, "manifest")
    pytest_artifact_path = _artifact_path(receipt_path, "pytest")
    temporary_root: Path | None = None
    graph_receipt: dict[str, Any] | None = None
    pytest_receipt: dict[str, Any] | None = None
    runner_exit_code = 2
    error: str | None = None

    try:
        runner = validation_evidence_graph.require_pinned_sdk_runner(args.sdk_root)
        experiment_parent = REPO_ROOT / "tmp"
        experiment_parent.mkdir(parents=True, exist_ok=True)
        temporary_root = Path(
            tempfile.mkdtemp(prefix="validation-scheduler-", dir=experiment_parent)
        )
        temporary_manifest = temporary_root / "manifest.json"
        temporary_pytest_receipt = temporary_root / "pytest.json"
        manifest = build_experimental_manifest(args.method, temporary_pytest_receipt)
        _write_json(temporary_manifest, manifest)

        command = [
            sys.executable,
            str(runner),
            "--repo-root",
            str(REPO_ROOT),
            "--manifest",
            str(temporary_manifest),
            "--shadow-route",
            "--changed-path",
            "__validation_scheduler_experiment__/full",
            "--max-workers",
            str(args.graph_workers),
            "--receipt",
            str(graph_receipt_path),
        ]
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=validation_evidence_graph.runner_environment(args.sdk_root),
            check=False,
        )
        runner_exit_code = completed.returncode
        if graph_receipt_path.is_file():
            graph_receipt = json.loads(graph_receipt_path.read_text(encoding="utf-8"))
        if temporary_pytest_receipt.is_file():
            pytest_receipt = json.loads(temporary_pytest_receipt.read_text(encoding="utf-8"))
            _write_json(pytest_artifact_path, pytest_receipt)
        _write_json(manifest_artifact_path, manifest)
    except (
        ExperimentError,
        validation_evidence_graph.AdapterError,
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        error = str(exc)
    finally:
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)

    graph_decision = graph_receipt.get("decision", {}) if graph_receipt else {}
    graph_routing = graph_receipt.get("routing", {}) if graph_receipt else {}
    pytest_decision = pytest_receipt.get("decision", {}) if pytest_receipt else {}
    static_ok = args.method != "static-2" or (
        pytest_decision.get("passed") is True
        and pytest_decision.get("authoritative_for_owner_gate") is False
    )
    passed = (
        error is None
        and runner_exit_code == 0
        and graph_decision.get("sufficient") is True
        and graph_decision.get("authoritative_for_owner_gate") is False
        and graph_decision.get("shadow_routing_never_authoritative") is True
        and graph_routing.get("fallback_to_full") is True
        and static_ok
    )
    receipt = {
        "schema_version": "abyss_machine_validation_scheduler_experiment_v1",
        "owner_repo": "abyss-machine",
        "method": args.method,
        "graph_workers": args.graph_workers,
        "authority": "shadow comparison only; never sufficient for the owner gate",
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.UTC).isoformat(),
        "runner_exit_code": runner_exit_code,
        "error": error,
        "artifacts": {
            "manifest": {
                "path": manifest_artifact_path.as_posix(),
                "sha256": _sha256(manifest_artifact_path)
                if manifest_artifact_path.is_file()
                else None,
            },
            "graph_receipt": {
                "path": graph_receipt_path.as_posix(),
                "sha256": _sha256(graph_receipt_path)
                if graph_receipt_path.is_file()
                else None,
            },
            "pytest_receipt": {
                "path": pytest_artifact_path.as_posix()
                if pytest_artifact_path.is_file()
                else None,
                "sha256": _sha256(pytest_artifact_path)
                if pytest_artifact_path.is_file()
                else None,
            },
        },
        "graph": _graph_summary(graph_receipt) if graph_receipt else None,
        "pytest": {
            "elapsed_seconds": pytest_receipt.get("elapsed_seconds"),
            "repository_identity": pytest_receipt.get("repository_identity"),
            "decision": pytest_decision,
            "process_results": [
                {
                    "index": process.get("index"),
                    "argv": process.get("argv"),
                    "returncode": process.get("returncode"),
                    "duration_seconds": process.get("duration_seconds"),
                }
                for process in pytest_receipt.get("process_results", [])
            ],
        }
        if pytest_receipt
        else None,
        "decision": {
            "passed": passed,
            "authoritative_for_owner_gate": False,
        },
    }
    _write_json(receipt_path, receipt)
    elapsed = graph_receipt.get("elapsed_seconds") if graph_receipt else None
    print(
        f"[combined-comparison] method={args.method} workers={args.graph_workers} "
        f"passed={str(passed).lower()} elapsed={elapsed} receipt={receipt_path}",
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
