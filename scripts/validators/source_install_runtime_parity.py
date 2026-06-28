#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, fail, ok

SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import host_lifecycle_parity


RUNTIME_COMMANDS = {
    "enter": ["abyss-machine", "enter", "--json"],
    "typing-validate": ["abyss-machine", "typing", "validate", "--json"],
    "nervous-validate": ["abyss-machine", "nervous", "validate", "--json"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_runtime_check(name: str, command: list[str], timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return host_lifecycle_parity.compact_command_result(
            name=name,
            command=command,
            returncode=int(result.returncode),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return host_lifecycle_parity.compact_command_result(
            name=name,
            command=command,
            returncode=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else f"timed out after {timeout}s",
            timed_out=True,
        )


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    runtime_checks = []
    selected_runtime_checks = args.runtime_check or ["enter"]
    for name in dict.fromkeys(selected_runtime_checks):
        command = RUNTIME_COMMANDS[name]
        runtime_checks.append(run_runtime_check(name, command, float(args.runtime_timeout)))
    return host_lifecycle_parity.build_parity_document(
        generated_at=now_iso(),
        repo_root=REPO_ROOT,
        installed_cli=Path(args.host_cli),
        installed_libexec_dir=Path(args.host_libexec_dir),
        installed_share_root=Path(args.host_share_root),
        runtime_checks=runtime_checks,
        sample_limit=int(args.sample_limit),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit a compact source/install/runtime parity summary.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--host-cli", default="/usr/local/bin/abyss-machine")
    parser.add_argument("--host-libexec-dir", default="/usr/local/libexec")
    parser.add_argument("--host-share-root", default="/usr/local/share/abyss-machine")
    parser.add_argument("--runtime-check", action="append", choices=sorted(RUNTIME_COMMANDS), default=None)
    parser.add_argument("--runtime-timeout", type=float, default=15.0)
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--advisory", action="store_true", help="return zero even when drift is reported")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report.get("ok") is True or args.advisory:
        if not args.json:
            return ok("source/install/runtime parity summary completed")
        return 0
    if args.json:
        return 1
    return fail("source/install/runtime parity drift detected", [str(item) for item in report.get("failures", [])])


if __name__ == "__main__":
    raise SystemExit(main())
