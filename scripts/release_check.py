#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import validation_lanes


REPO_ROOT = Path(__file__).resolve().parents[1]


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
        "--include-host-contracts",
        action="store_true",
        help="include fixture-backed host contract quick tests after the public release gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lane = "release-full" if args.include_host_contracts else "release-public"
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


if __name__ == "__main__":
    raise SystemExit(main())
