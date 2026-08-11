#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
METHODS = ("serial", "xdist-2", "xdist-4", "static-2")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    return completed.stdout if completed.returncode == 0 else b""


def repository_identity() -> dict[str, Any]:
    status = _git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {
        "git_commit": _git("rev-parse", "HEAD").decode().strip() or None,
        "git_tree": _git("rev-parse", "HEAD^{tree}").decode().strip() or None,
        "status_sha256": _sha256(status),
        "dirty": bool(status),
    }


def public_test_files() -> list[Path]:
    return sorted((REPO_ROOT / "tests" / "public_smoke").glob("test_*.py"))


def static_shards(files: Sequence[Path], count: int = 2) -> list[list[Path]]:
    shards: list[list[Path]] = [[] for _ in range(count)]
    weights = [0] * count
    for path in sorted(files, key=lambda item: (-item.stat().st_size, item.as_posix())):
        target = min(range(count), key=lambda index: (weights[index], index))
        shards[target].append(path)
        weights[target] += path.stat().st_size
    return [sorted(shard) for shard in shards]


def method_commands(method: str) -> tuple[list[list[str]], list[list[str]]]:
    base = [sys.executable, "-m", "pytest", "-q"]
    if method == "serial":
        return ([base], [])
    if method.startswith("xdist-"):
        workers = method.removeprefix("xdist-")
        return ([base + ["-n", workers]], [])
    if method == "static-2":
        shards = static_shards(public_test_files())
        commands = [
            base + [path.relative_to(REPO_ROOT).as_posix() for path in shard]
            for shard in shards
        ]
        shard_paths = [
            [path.relative_to(REPO_ROOT).as_posix() for path in shard]
            for shard in shards
        ]
        return commands, shard_paths
    raise ValueError(f"unknown method: {method}")


def _run_commands(commands: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    def run_one(index: int, command: Sequence[str]) -> dict[str, Any]:
        started = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "index": index,
            "argv": list(command),
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 6),
            "stdout_sha256": _sha256(completed.stdout.encode()),
            "stderr_sha256": _sha256(completed.stderr.encode()),
            "stdout_tail": completed.stdout[-8000:],
            "stderr_tail": completed.stderr[-8000:],
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
        futures = [executor.submit(run_one, index, command) for index, command in enumerate(commands)]
        results = sorted((future.result() for future in futures), key=lambda result: result["index"])

    for result in results:
        index = result["index"]
        print(f"[method-process {index + 1}] {' '.join(commands[index])}", flush=True)
        stdout = result["stdout_tail"]
        stderr = result["stderr_tail"]
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    return results


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare public pytest schedulers without authorizing an owner gate."
    )
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    commands, shards = method_commands(args.method)
    before = repository_identity()
    started_at = dt.datetime.now(dt.UTC)
    started = time.monotonic()
    results = _run_commands(commands)
    elapsed = time.monotonic() - started
    after = repository_identity()
    passed = all(result["returncode"] == 0 for result in results)
    receipt = {
        "schema_version": "abyss_machine_pytest_scheduler_experiment_v1",
        "owner_repo": "abyss-machine",
        "method": args.method,
        "authority": "shadow comparison only; never sufficient for the owner gate",
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "repository_identity": {
            "before": before,
            "after": after,
            "stable": before == after,
        },
        "test_file_count": len(public_test_files()),
        "static_shards": shards,
        "process_results": results,
        "decision": {
            "passed": passed,
            "authoritative_for_owner_gate": False,
        },
    }
    _write_receipt(args.receipt, receipt)
    print(
        f"[comparison] method={args.method} passed={str(passed).lower()} "
        f"elapsed={elapsed:.3f}s receipt={args.receipt}",
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
