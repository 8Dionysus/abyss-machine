#!/usr/bin/env python3
"""Inspect, install, or exercise the admitted Universal Ctags provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.code_intelligence_provider import (  # noqa: E402
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_REGISTRY_DIR,
    DEFAULT_RUNTIME_ROOT,
    DEFAULT_SOURCE_ROOT,
    exercise_provider,
    inspect_provider_artifact,
    install_provider,
)
from abyss_machine.path_policy import AbyssMachinePathPolicy  # noqa: E402


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--archive", required=True, help="exact Universal Ctags archive")
    parser.add_argument("--bundle-dir", required=True, help="sidecar bundle for the exact archive")
    parser.add_argument("--subject-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--registry-dir", default=str(DEFAULT_REGISTRY_DIR))
    parser.add_argument("--source-root", default=str(DEFAULT_SOURCE_ROOT))
    parser.add_argument("--source-ref", default="", help="optional source identity pin")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable result")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    inspect_parser = commands.add_parser("inspect")
    _common(inspect_parser)
    install_parser = commands.add_parser("install")
    _common(install_parser)
    install_parser.add_argument(
        "--runtime-root",
        default=str(
            AbyssMachinePathPolicy.from_environment().runtimes_root
            / "code-intelligence"
        ),
    )
    install_parser.add_argument("--apply", action="store_true", help="write only after trust-gate and owner preflights allow")
    exercise_parser = commands.add_parser("exercise")
    _common(exercise_parser)
    exercise_parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    exercise_parser.add_argument("--source-file", default="src/abyss_machine/code_intelligence_contracts.py")
    args = parser.parse_args(argv)
    try:
        if args.operation == "inspect":
            result = inspect_provider_artifact(
                args.archive,
                args.bundle_dir,
                subject_root=args.subject_root,
                registry_dir=args.registry_dir,
                source_root=args.source_root,
                expected_source_ref=args.source_ref,
            )
        elif args.operation == "install":
            result = install_provider(
                args.archive,
                args.bundle_dir,
                subject_root=args.subject_root,
                runtime_root=args.runtime_root,
                registry_dir=args.registry_dir,
                source_root=args.source_root,
                expected_source_ref=args.source_ref,
                apply=args.apply,
            )
        else:
            result = exercise_provider(
                args.bundle_dir,
                archive_path=args.archive,
                subject_root=args.subject_root,
                runtime_root=args.runtime_root,
                registry_dir=args.registry_dir,
                source_root=args.source_root,
                source_file=args.source_file,
                expected_source_ref=args.source_ref,
            )
    except Exception as exc:
        result = {
            "schema": "abyss_machine_code_intelligence_provider_command_error_v1",
            "operation": args.operation,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "reason": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"admitted", "healthy", "healthy_not_owner_admitted", "ready_to_install", "already_installed", "installed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
