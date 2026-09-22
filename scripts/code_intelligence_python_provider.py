#!/usr/bin/env python3
"""Build, inspect, install or reverify a SCIP Python artifact; never execute it."""

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
from abyss_machine.code_intelligence_python_install import (  # noqa: E402
    install_python_provider_artifact,
    verify_python_provider_installation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument(
        "--runtime", required=True, help="prepared script-free npm-ci prefix"
    )
    build.add_argument("--output", required=True)
    build.add_argument(
        "--node-distribution", required=True, help="supplied pinned Node release tar.gz"
    )
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
    install = commands.add_parser("install")
    verify = commands.add_parser(
        "verify-installed",
        help="read-only check preserving historical installer identity",
    )
    for command in (install, verify):
        for argument in (
            "archive",
            "bundle-dir",
            "subject-root",
            "registry-dir",
            "source-ref",
            "producer-source-root",
        ):
            command.add_argument("--" + argument, required=True)
        command.add_argument(
            "--runtime-root", default="/srv/abyss-machine/runtimes/code-intelligence"
        )
        command.add_argument("--json", action="store_true")
    install.add_argument("--apply", action="store_true")
    verify.add_argument("--installer-source-root", required=True)
    verify.add_argument("--installer-source-ref", required=True)
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
                node_distribution_path=args.node_distribution,
                source_ref=args.source_ref,
                platform=args.platform,
            )
            result["metadata"]["file_count"] = len(result["metadata"].pop("files"))
            result["ok"] = True
        elif args.command in {"install", "verify-installed"}:
            operation = (
                install_python_provider_artifact
                if args.command == "install"
                else verify_python_provider_installation
            )
            operation_args = (
                {"apply": args.apply}
                if args.command == "install"
                else {
                    "installer_source_root": args.installer_source_root,
                    "expected_installer_source_ref": args.installer_source_ref,
                }
            )
            result = operation(
                args.archive,
                args.bundle_dir,
                subject_root=args.subject_root,
                registry_dir=args.registry_dir,
                producer_source_root=args.producer_source_root,
                expected_source_ref=args.source_ref,
                runtime_root=args.runtime_root,
                **operation_args,
            )
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
