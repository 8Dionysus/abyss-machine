#!/usr/bin/env python3
"""Inspect or install the admitted Tree-sitter/SCIP/LSP provider artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine.code_intelligence_node_provider import inspect_node_provider_artifact, install_node_provider_artifact  # noqa: E402
from abyss_machine.code_intelligence_provider import DEFAULT_ARTIFACT_ROOT, DEFAULT_REGISTRY_DIR, DEFAULT_RUNTIME_ROOT  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("inspect", "install"))
    parser.add_argument("--archive", required=True)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--subject-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--registry-dir", default=str(DEFAULT_REGISTRY_DIR))
    parser.add_argument("--runtime-root", default=str(DEFAULT_RUNTIME_ROOT))
    parser.add_argument("--source-ref", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "inspect":
            result = inspect_node_provider_artifact(args.archive, args.bundle_dir, subject_root=args.subject_root, registry_dir=args.registry_dir, expected_source_ref=args.source_ref)
        else:
            result = install_node_provider_artifact(args.archive, args.bundle_dir, subject_root=args.subject_root, registry_dir=args.registry_dir, runtime_root=args.runtime_root, expected_source_ref=args.source_ref, apply=args.apply)
    except Exception as exc:
        result = {"status": "blocked", "error_type": type(exc).__name__, "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"admitted", "ready_to_install", "already_installed", "installed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
