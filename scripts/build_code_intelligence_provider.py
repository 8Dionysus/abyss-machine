#!/usr/bin/env python3
"""Build the exact Universal Ctags provider candidate for abyss-machine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.code_intelligence_provider import (  # noqa: E402
    DEFAULT_ARTIFACT_ROOT,
    build_provider_archive,
)


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ctags", default="", help="already installed Universal Ctags executable")
    parser.add_argument("--output", required=True, help="candidate archive under /srv/abyss-machine/artifacts/code-intelligence")
    parser.add_argument("--source-ref", required=True, help="qualified source: or commit: identity for the provider candidate")
    parser.add_argument("--platform", default="", help="portable platform label stored in provider metadata")
    parser.add_argument("--json", action="store_true", help="emit the machine-readable result")
    args = parser.parse_args(argv)
    executable = args.ctags or shutil.which("ctags")
    output = Path(args.output).expanduser().resolve()
    if not executable:
        result = {"ok": False, "status": "blocked", "reason": "Universal Ctags executable was not found"}
        print(json.dumps(result, sort_keys=True))
        return 1
    if not _within(output, DEFAULT_ARTIFACT_ROOT):
        result = {"ok": False, "status": "blocked", "reason": "output must remain under the exact code-intelligence artifact root"}
        print(json.dumps(result, sort_keys=True))
        return 1
    try:
        result = build_provider_archive(
            executable,
            output,
            source_ref=args.source_ref,
            platform=args.platform or None,
        )
        result["ok"] = True
    except Exception as exc:
        result = {
            "ok": False,
            "status": "blocked",
            "error_type": type(exc).__name__,
            "reason": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
