#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
XDIST_METHODS = {
    "xdist-2": (2, "load"),
    "xdist-3": (3, "load"),
    "xdist-4": (4, "load"),
    "xdist-2-loadfile": (2, "loadfile"),
    "xdist-2-loadscope": (2, "loadscope"),
    "xdist-2-worksteal": (2, "worksteal"),
}
METHODS = ("serial", *XDIST_METHODS, "static-2", "static-duration-2")
SUITES = ("public-smoke", "host-contract-quick")
HOST_CONTRACT_QUICK_MARKERS = "quick and not live and not long and not manual"
PROBE_MODULE = "scripts.pytest_scheduler_probe"
PROBE_LOG_ENV = "ABYSS_MACHINE_PYTEST_REPORT_LOG"
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_COLLECTION_TIMEOUT_SECONDS = 120.0


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


def suite_test_files(suite: str) -> list[Path]:
    if suite == "public-smoke":
        return public_test_files()
    if suite == "host-contract-quick":
        return sorted((REPO_ROOT / "tests" / "host_contract").rglob("test_*.py"))
    raise ValueError(f"unknown suite: {suite}")


def suite_pytest_args(suite: str) -> list[str]:
    if suite == "public-smoke":
        return []
    if suite == "host-contract-quick":
        return ["tests/host_contract", "-m", HOST_CONTRACT_QUICK_MARKERS]
    raise ValueError(f"unknown suite: {suite}")


def static_shards(files: Sequence[Path], count: int = 2) -> list[list[Path]]:
    shards: list[list[Path]] = [[] for _ in range(count)]
    weights = [0] * count
    for path in sorted(files, key=lambda item: (-item.stat().st_size, item.as_posix())):
        target = min(range(count), key=lambda index: (weights[index], index))
        shards[target].append(path)
        weights[target] += path.stat().st_size
    return [sorted(shard) for shard in shards]


def method_commands(
    method: str,
    suite: str = "public-smoke",
) -> tuple[list[list[str]], list[list[str]]]:
    base = [sys.executable, "-m", "pytest", "-q"]
    suite_args = suite_pytest_args(suite)
    if method == "serial":
        return ([base + suite_args], [])
    if method in XDIST_METHODS:
        workers, distribution = XDIST_METHODS[method]
        return (
            [base + ["-n", str(workers), "--dist", distribution, *suite_args]],
            [],
        )
    if method == "static-2":
        shards = static_shards(suite_test_files(suite))
        marker_args = (
            ["-m", HOST_CONTRACT_QUICK_MARKERS]
            if suite == "host-contract-quick"
            else []
        )
        commands = [
            base
            + [path.relative_to(REPO_ROOT).as_posix() for path in shard]
            + marker_args
            for shard in shards
        ]
        shard_paths = [
            [path.relative_to(REPO_ROOT).as_posix() for path in shard]
            for shard in shards
        ]
        return commands, shard_paths
    raise ValueError(f"unknown method: {method}")


def _collection_command(command: Sequence[str]) -> list[str]:
    if list(command[:3]) != [sys.executable, "-m", "pytest"]:
        raise ValueError(f"unsupported pytest command: {list(command)}")
    args: list[str] = []
    index = 3
    while index < len(command):
        value = command[index]
        if value == "-q":
            index += 1
            continue
        if value == "-n":
            index += 2
            continue
        if value == "--dist":
            index += 2
            continue
        args.append(value)
        index += 1
    return [sys.executable, "-m", "pytest", "--collect-only", "-q", *args]


def _test_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    source_root = str(REPO_ROOT / "src")
    current_pythonpath = env.get("PYTHONPATH", "")
    python_paths = [source_root, str(REPO_ROOT)]
    if current_pythonpath:
        python_paths.append(current_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    return env


def _run_captured_process(
    command: Sequence[str],
    *,
    env: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        stderr = (
            f"{stderr.rstrip()}\n"
            f"scheduler process group timed out after {timeout_seconds:.3f}s"
        ).lstrip()
    return {
        "returncode": 124 if timed_out else int(process.returncode or 0),
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
    }


def _parse_collected_nodeids(stdout: str) -> list[str]:
    return [
        line.strip()
        for line in stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    ]


def _nodeid_sha256(nodeids: Sequence[str]) -> str:
    return _sha256("\0".join(nodeids).encode())


def _collect(
    command: Sequence[str],
    *,
    timeout_seconds: float = DEFAULT_COLLECTION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    collection_command = _collection_command(command)
    started = time.monotonic()
    completed = _run_captured_process(
        collection_command,
        env=_test_environment(),
        timeout_seconds=timeout_seconds,
    )
    nodeids = _parse_collected_nodeids(completed["stdout"])
    return {
        "argv": collection_command,
        "returncode": completed["returncode"],
        "timed_out": completed["timed_out"],
        "timeout_seconds": completed["timeout_seconds"],
        "duration_seconds": round(time.monotonic() - started, 6),
        "nodeids": nodeids,
        "nodeid_count": len(nodeids),
        "nodeid_sha256": _nodeid_sha256(nodeids),
        "stdout_sha256": _sha256(completed["stdout"].encode()),
        "stderr_sha256": _sha256(completed["stderr"].encode()),
        "stdout_tail": completed["stdout"][-2000:],
        "stderr_tail": completed["stderr"][-2000:],
    }


def _inventory_comparison(
    expected: Sequence[str],
    process_nodeids: Sequence[Sequence[str]],
) -> dict[str, Any]:
    combined = [nodeid for nodeids in process_nodeids for nodeid in nodeids]
    expected_counter = Counter(expected)
    actual_counter = Counter(combined)
    duplicates = sorted(nodeid for nodeid, count in actual_counter.items() if count > 1)
    missing = sorted((expected_counter - actual_counter).elements())
    extra = sorted((actual_counter - expected_counter).elements())
    return {
        "exact": not duplicates and not missing and not extra,
        "expected_count": len(expected),
        "actual_count": len(combined),
        "expected_sha256": _nodeid_sha256(sorted(expected)),
        "actual_sha256": _nodeid_sha256(sorted(combined)),
        "duplicates": duplicates,
        "missing": missing,
        "extra": extra,
    }


def selection_evidence(
    suite: str,
    commands: Sequence[Sequence[str]],
    *,
    collection_timeout_seconds: float = DEFAULT_COLLECTION_TIMEOUT_SECONDS,
    canonical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_command = [sys.executable, "-m", "pytest", "-q", *suite_pytest_args(suite)]
    canonical_result = canonical or _collect(
        canonical_command,
        timeout_seconds=collection_timeout_seconds,
    )
    if len(commands) == 1 and _collection_command(commands[0]) == canonical_result["argv"]:
        processes = [canonical_result]
    else:
        processes = [
            _collect(command, timeout_seconds=collection_timeout_seconds)
            for command in commands
        ]
    comparison = _inventory_comparison(
        canonical_result["nodeids"],
        [process["nodeids"] for process in processes],
    )
    collection_ok = canonical_result["returncode"] == 0 and all(
        process["returncode"] == 0 for process in processes
    )
    return {
        "passed": bool(collection_ok and comparison["exact"]),
        "canonical": canonical_result,
        "processes": processes,
        "comparison": comparison,
    }


def _load_probe_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid scheduler probe event at {path}:{line_number}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"scheduler probe event at {path}:{line_number} is not an object")
        events.append(event)
    return events


def _duration_profile_from_events(
    events: Sequence[dict[str, Any]],
) -> dict[str, float]:
    durations: Counter[str] = Counter()
    for event in events:
        if event.get("event") != "report":
            continue
        nodeid = str(event.get("nodeid") or "")
        if nodeid:
            durations[nodeid] += float(event.get("duration_seconds") or 0.0)
    return {
        nodeid: round(duration, 9)
        for nodeid, duration in durations.items()
    }


def duration_node_shards(
    nodeids: Sequence[str],
    durations: Mapping[str, float],
    *,
    count: int = 2,
) -> tuple[list[list[str]], dict[str, Any]]:
    if count <= 0:
        raise ValueError("duration shard count must be positive")
    measured = [float(durations[nodeid]) for nodeid in nodeids if float(durations.get(nodeid, 0.0)) > 0]
    fallback = statistics.median(measured) if measured else 1.0
    expected = set(nodeids)
    weighted = [
        (nodeid, float(durations.get(nodeid) or fallback))
        for nodeid in nodeids
    ]
    shards: list[list[str]] = [[] for _ in range(count)]
    weights = [0.0] * count
    for nodeid, duration in sorted(weighted, key=lambda item: (-item[1], item[0])):
        target = min(range(count), key=lambda index: (weights[index], len(shards[index]), index))
        shards[target].append(nodeid)
        weights[target] += duration
    return (
        [sorted(shard) for shard in shards],
        {
            "source_nodeids": len(durations),
            "matching_nodeids": sum(1 for nodeid in nodeids if nodeid in durations),
            "missing_nodeids": sorted(nodeid for nodeid in nodeids if nodeid not in durations),
            "extra_nodeids": sorted(nodeid for nodeid in durations if nodeid not in expected),
            "fallback_duration_seconds": round(fallback, 9),
            "shard_estimated_seconds": [round(weight, 6) for weight in weights],
        },
    )


def duration_shard_commands(
    nodeids: Sequence[str],
    durations: Mapping[str, float],
) -> tuple[list[list[str]], list[list[str]], dict[str, Any]]:
    shards, profile = duration_node_shards(nodeids, durations, count=2)
    base = [sys.executable, "-m", "pytest", "-q"]
    return ([base + shard for shard in shards], shards, profile)


def _execution_inventory_from_events(
    expected_nodeids: Sequence[str],
    events: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    collections = [event for event in events if event.get("event") == "collection"]
    collection_mismatches: list[str] = []
    for event in collections:
        nodeids = event.get("nodeids")
        if not isinstance(nodeids, list) or [str(item) for item in nodeids] != list(expected_nodeids):
            collection_mismatches.append(str(event.get("worker") or "unknown"))

    reports_by_nodeid: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("event") != "report":
            continue
        nodeid = str(event.get("nodeid") or "")
        if nodeid:
            reports_by_nodeid.setdefault(nodeid, []).append(event)

    terminal_nodeids: list[str] = []
    ambiguous_terminal_nodeids: list[str] = []
    outcome_counts: Counter[str] = Counter()
    node_durations: list[dict[str, Any]] = []
    worker_duration_seconds: Counter[str] = Counter()
    for nodeid, reports in reports_by_nodeid.items():
        calls = [report for report in reports if report.get("when") == "call"]
        duration_seconds = round(
            sum(float(report.get("duration_seconds") or 0.0) for report in reports),
            9,
        )
        if len(calls) == 1:
            terminal_nodeids.append(nodeid)
            outcome_counts[str(calls[0].get("outcome") or "unknown")] += 1
            worker = str(calls[0].get("worker") or "unknown")
            node_durations.append(
                {
                    "nodeid": nodeid,
                    "duration_seconds": duration_seconds,
                    "worker": worker,
                }
            )
            worker_duration_seconds[worker] += duration_seconds
            continue
        if len(calls) > 1:
            terminal_nodeids.extend([nodeid] * len(calls))
            ambiguous_terminal_nodeids.append(nodeid)
            continue
        setup_terminals = [
            report
            for report in reports
            if report.get("when") == "setup" and report.get("outcome") != "passed"
        ]
        if len(setup_terminals) == 1:
            terminal_nodeids.append(nodeid)
            outcome_counts[str(setup_terminals[0].get("outcome") or "unknown")] += 1
            worker = str(setup_terminals[0].get("worker") or "unknown")
            node_durations.append(
                {
                    "nodeid": nodeid,
                    "duration_seconds": duration_seconds,
                    "worker": worker,
                }
            )
            worker_duration_seconds[worker] += duration_seconds
        else:
            ambiguous_terminal_nodeids.append(nodeid)

    comparison = _inventory_comparison(expected_nodeids, [terminal_nodeids])
    return {
        "passed": bool(
            collections
            and not collection_mismatches
            and not ambiguous_terminal_nodeids
            and comparison["exact"]
        ),
        "collection_workers": [str(event.get("worker") or "unknown") for event in collections],
        "collection_mismatches": collection_mismatches,
        "reported_nodeid_count": len(reports_by_nodeid),
        "terminal_outcomes": dict(sorted(outcome_counts.items())),
        "duration_summary": {
            "test_phase_total_seconds": round(
                sum(item["duration_seconds"] for item in node_durations),
                6,
            ),
            "worker_test_phase_seconds": {
                worker: round(duration, 6)
                for worker, duration in sorted(worker_duration_seconds.items())
            },
            "slowest": sorted(
                node_durations,
                key=lambda item: (-item["duration_seconds"], item["nodeid"]),
            )[:20],
        },
        "ambiguous_terminal_nodeids": sorted(ambiguous_terminal_nodeids),
        "comparison": comparison,
    }


def _instrumented_command(command: Sequence[str]) -> list[str]:
    if list(command[:3]) != [sys.executable, "-m", "pytest"]:
        raise ValueError(f"unsupported pytest command: {list(command)}")
    return [*command[:3], "-p", PROBE_MODULE, *command[3:]]


def _run_commands(
    commands: Sequence[Sequence[str]],
    expected_nodeids_by_process: Sequence[Sequence[str]],
    report_paths: Sequence[Path],
    *,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    def run_one(index: int, command: Sequence[str]) -> dict[str, Any]:
        actual_command = _instrumented_command(command)
        report_path = report_paths[index].resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.unlink(missing_ok=True)
        env = _test_environment()
        env[PROBE_LOG_ENV] = str(report_path)
        started = time.monotonic()
        completed = _run_captured_process(
            actual_command,
            env=env,
            timeout_seconds=timeout_seconds,
        )
        probe_error = None
        try:
            events = _load_probe_events(report_path)
            execution_inventory = _execution_inventory_from_events(
                expected_nodeids_by_process[index],
                events,
            )
        except (OSError, ValueError) as exc:
            execution_inventory = {"passed": False}
            probe_error = str(exc)
        return {
            "index": index,
            "argv": actual_command,
            "returncode": completed["returncode"],
            "timed_out": completed["timed_out"],
            "timeout_seconds": completed["timeout_seconds"],
            "duration_seconds": round(time.monotonic() - started, 6),
            "stdout_sha256": _sha256(completed["stdout"].encode()),
            "stderr_sha256": _sha256(completed["stderr"].encode()),
            "stdout_tail": completed["stdout"][-8000:],
            "stderr_tail": completed["stderr"][-8000:],
            "probe": {
                "path": str(report_path),
                "sha256": _sha256(report_path.read_bytes()) if report_path.is_file() else None,
                "error": probe_error,
            },
            "execution_inventory": execution_inventory,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
        futures = [executor.submit(run_one, index, command) for index, command in enumerate(commands)]
        results = sorted((future.result() for future in futures), key=lambda result: result["index"])

    for result in results:
        index = result["index"]
        print(f"[method-process {index + 1}] {' '.join(result['argv'])}", flush=True)
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
    parser.add_argument("--suite", choices=SUITES, default="public-smoke")
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--duration-profile",
        type=Path,
        help="serial scheduler probe JSONL used only by static-duration-2",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="terminate the experiment-owned pytest process group after this many seconds",
    )
    parser.add_argument(
        "--collection-timeout-seconds",
        type=float,
        default=DEFAULT_COLLECTION_TIMEOUT_SECONDS,
        help="terminate each experiment-owned collection process group after this many seconds",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0 or args.collection_timeout_seconds <= 0:
        raise SystemExit("scheduler timeouts must be positive")
    before = repository_identity()
    started_at = dt.datetime.now(dt.UTC)
    canonical_seed = None
    duration_profile = None
    if args.method == "static-duration-2":
        if args.duration_profile is None:
            raise SystemExit("static-duration-2 requires --duration-profile PROBE.jsonl")
        profile_path = args.duration_profile.resolve()
        try:
            profile_events = _load_probe_events(profile_path)
        except (OSError, ValueError) as exc:
            raise SystemExit(f"unable to read duration profile: {exc}") from exc
        durations = _duration_profile_from_events(profile_events)
        if not durations:
            raise SystemExit("duration profile contains no pytest reports")
        canonical_command = [sys.executable, "-m", "pytest", "-q", *suite_pytest_args(args.suite)]
        canonical_seed = _collect(
            canonical_command,
            timeout_seconds=args.collection_timeout_seconds,
        )
        if canonical_seed["returncode"] == 0:
            commands, shards, duration_profile = duration_shard_commands(
                canonical_seed["nodeids"],
                durations,
            )
        else:
            commands, shards = [canonical_command], []
            duration_profile = {
                "source_nodeids": len(durations),
                "matching_nodeids": 0,
                "missing_nodeids": [],
                "extra_nodeids": sorted(durations),
                "fallback_duration_seconds": None,
                "shard_estimated_seconds": [],
            }
        duration_profile.update(
            {
                "path": str(profile_path),
                "sha256": _sha256(profile_path.read_bytes()),
            }
        )
    else:
        if args.duration_profile is not None:
            raise SystemExit("--duration-profile is only valid with static-duration-2")
        commands, shards = method_commands(args.method, args.suite)
    selection = selection_evidence(
        args.suite,
        commands,
        collection_timeout_seconds=args.collection_timeout_seconds,
        canonical=canonical_seed,
    )
    if selection["passed"]:
        receipt_path = args.receipt.resolve()
        report_paths = [
            receipt_path.with_name(f"{receipt_path.stem}.process-{index + 1}.jsonl")
            for index in range(len(commands))
        ]
        started = time.monotonic()
        results = _run_commands(
            commands,
            [process["nodeids"] for process in selection["processes"]],
            report_paths,
            timeout_seconds=args.timeout_seconds,
        )
        elapsed = time.monotonic() - started
    else:
        results = []
        elapsed = 0.0
    after = repository_identity()
    passed = bool(
        selection["passed"]
        and results
        and all(result["returncode"] == 0 for result in results)
        and all(result["execution_inventory"]["passed"] for result in results)
    )
    receipt = {
        "schema_version": "abyss_machine_pytest_scheduler_experiment_v2",
        "owner_repo": "abyss-machine",
        "suite": args.suite,
        "method": args.method,
        "authority": "shadow comparison only; never sufficient for the owner gate",
        "started_at": started_at.isoformat(),
        "completed_at": dt.datetime.now(dt.UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "timeout_seconds": args.timeout_seconds,
        "collection_timeout_seconds": args.collection_timeout_seconds,
        "repository_identity": {
            "before": before,
            "after": after,
            "stable": before == after,
        },
        "test_file_count": len(suite_test_files(args.suite)),
        "selection": selection,
        "static_shards": shards,
        "duration_profile": duration_profile,
        "process_results": results,
        "decision": {
            "passed": passed,
            "authoritative_for_owner_gate": False,
        },
    }
    _write_receipt(args.receipt, receipt)
    print(
        f"[comparison] suite={args.suite} method={args.method} "
        f"selection={str(selection['passed']).lower()} passed={str(passed).lower()} "
        f"elapsed={elapsed:.3f}s receipt={args.receipt}",
        flush=True,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
