#!/usr/bin/env python3
"""Build or inspect a SCIP Python candidate without executing or installing it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine.code_intelligence_python_provider import (  # noqa: E402
    build_python_provider_archive,
    inspect_python_provider_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument(
        "--runtime", required=True, help="prepared script-free npm-ci prefix"
    )
    build.add_argument("--output", required=True)
    build.add_argument("--source-ref", required=True)
    build.add_argument("--platform", default="linux-x86_64")
    build.add_argument(
        "--artifact-root", default="/srv/abyss-machine/artifacts/code-intelligence"
    )
    build.add_argument(
        "--lock",
        default=str(ROOT / "manifests/code_intelligence_python_provider.lock.json"),
    )
    build.add_argument(
        "--inputs", default=str(ROOT / "mechanics/code-intelligence/parts/scip-python")
    )
    build.add_argument("--json", action="store_true")
    inspect = commands.add_parser("inspect")
    for argument in (
        "archive",
        "bundle-dir",
        "subject-root",
        "registry-dir",
        "source-ref",
    ):
        inspect.add_argument("--" + argument, required=True)
    inspect.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            output, artifact_root = (
                Path(args.output).absolute(),
                Path(args.artifact_root).resolve(),
            )
            if not artifact_root.is_dir() or not output.resolve().is_relative_to(
                artifact_root
            ):
                raise ValueError(
                    "output must be inside an existing bounded artifact root"
                )
            inputs = Path(args.inputs)
            result = build_python_provider_archive(
                args.runtime,
                output,
                lock_path=args.lock,
                package_manifest_path=inputs / "package.json",
                package_lock_path=inputs / "package-lock.json",
                source_ref=args.source_ref,
                platform=args.platform,
            )
            result["metadata"]["file_count"] = len(result["metadata"].pop("files"))
            result["ok"] = True
        else:
            result = inspect_python_provider_artifact(
                args.archive,
                args.bundle_dir,
                subject_root=args.subject_root,
                registry_dir=args.registry_dir,
                source_root=ROOT,
                expected_source_ref=args.source_ref,
            )
            result["ok"] = result["status"] == "admitted"
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = {
            "ok": False,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "reason": str(exc),
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
