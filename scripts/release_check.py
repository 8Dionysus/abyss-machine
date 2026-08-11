#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import validation_lanes


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_MODE_ENV = "ABYSS_MACHINE_VALIDATION_MODE"
GRAPH_ADAPTER = "scripts/validation_evidence_graph.py"


def run_step(label: str, command: tuple[str, ...]) -> int:
    print(f"[run] {label}: {subprocess.list2cmdline(command)}", flush=True)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=os.environ.copy(), check=False)
    if completed.returncode != 0:
        print(f"[fail] {label} exited {completed.returncode}", flush=True)
        return completed.returncode
    print(f"[ok] {label}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run abyss-machine release checks.")
    parser.add_argument(
        "--mode",
        choices=("graph", "serial"),
        default=os.environ.get(VALIDATION_MODE_ENV, "serial"),
        help=(
            "serial remains the authoritative completeness oracle during shadow admission; "
            f"graph uses the pinned scheduler ABI (default: ${VALIDATION_MODE_ENV} or serial)"
        ),
    )
    parser.add_argument(
        "--include-host-contracts",
        action="store_true",
        help="include fixture-backed host contract quick tests after the public release gate",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="atomic graph receipt path; serial mode emits the existing step logs",
    )
    parser.add_argument("--max-workers", type=int, help="explicit graph worker comparison override")
    parser.add_argument("--sdk-root", type=Path, help="explicit pinned aoa-sdk source checkout")
    return parser


def run_lane(lane: str) -> int:
    try:
        steps = validation_lanes.lane_command_sequence(lane)
    except validation_lanes.ManifestError as exc:
        print(f"[fail] release lane failed to load: {exc}", flush=True)
        return 1
    for step in steps:
        exit_code = run_step(step.label, step.command)
        if exit_code != 0:
            return exit_code
    return 0


def run_graph(args: argparse.Namespace) -> int:
    command = [sys.executable, GRAPH_ADAPTER, "--profile", "full"]
    if args.receipt is not None:
        command.extend(("--receipt", str(args.receipt)))
    if args.max_workers is not None:
        command.extend(("--max-workers", str(args.max_workers)))
    if args.sdk_root is not None:
        command.extend(("--sdk-root", str(args.sdk_root)))
    exit_code = run_step("full owner claim/evidence validation graph", tuple(command))
    if exit_code != 0 or not args.include_host_contracts:
        return exit_code
    return run_lane("host-contract")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"[mode] {args.mode}", flush=True)
    if args.mode == "graph":
        return run_graph(args)
    if args.receipt is not None:
        print("[receipt] serial oracle emits no graph receipt", flush=True)
    if args.max_workers is not None:
        print("[workers] serial oracle ignores graph worker overrides", flush=True)
    if args.sdk_root is not None:
        print("[sdk-root] serial oracle does not use the scheduler checkout", flush=True)
    lane = "release-full" if args.include_host_contracts else "release-public"
    return run_lane(lane)


if __name__ == "__main__":
    raise SystemExit(main())
