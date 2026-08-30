#!/usr/bin/env python3
"""Build the exact offline Tree-sitter/SCIP/LSP provider candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine.code_intelligence_node_provider import build_node_provider_archive  # noqa: E402
from abyss_machine.code_intelligence_provider import DEFAULT_ARTIFACT_ROOT  # noqa: E402


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--lock", default=str(ROOT / "manifests/code_intelligence_node_providers.lock.json"))
    parser.add_argument("--runtime", default="", help="use a prepared npm prefix instead of downloading")
    parser.add_argument("--npm", default="npm")
    parser.add_argument("--platform", default="linux-x86_64")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--temporary-root", default="/srv/abyss-machine/tmp")
    parser.add_argument("--npm-cache", default="/srv/abyss-machine/cache/code-intelligence/npm")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    temporary_root = Path(args.temporary_root).resolve()
    if not artifact_root.is_dir() or not temporary_root.is_dir() or not _within(output, artifact_root):
        print(json.dumps({"ok": False, "status": "blocked", "reason": "artifact output and temporary roots must be existing bounded paths"}, sort_keys=True))
        return 1
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.runtime:
            runtime = Path(args.runtime).resolve()
        else:
            temporary = tempfile.TemporaryDirectory(prefix="node-provider-runtime-", dir=str(temporary_root))
            runtime = Path(temporary.name)
            lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
            packages = [f"{item['name']}@{item['version']}" for item in lock.get("packages", [])]
            env = os.environ.copy()
            env["npm_config_cache"] = args.npm_cache
            subprocess.run([args.npm, "install", "--prefix", str(runtime), "--no-audit", "--no-fund", "--omit=dev", *packages], check=True, timeout=900, env=env, stdout=subprocess.DEVNULL)
        result = build_node_provider_archive(runtime, output, lock_path=args.lock, source_ref=args.source_ref, platform=args.platform)
        result["ok"] = True
    except Exception as exc:
        result = {"ok": False, "status": "blocked", "error_type": type(exc).__name__, "reason": str(exc)}
    finally:
        if temporary is not None:
            temporary.cleanup()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
