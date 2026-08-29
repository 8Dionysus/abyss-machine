#!/usr/bin/env python3
"""Build the exact offline adjacent-provider candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine.code_intelligence_adjacent_provider import (  # noqa: E402
    build_adjacent_provider_archive,
)
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
    parser.add_argument("--lock", default=str(ROOT / "manifests/code_intelligence_adjacent_providers.lock.json"))
    parser.add_argument("--wheelhouse", default="", help="use a prepared wheelhouse instead of downloading")
    parser.add_argument("--binary-root", default="", help="use prepared locked provider binaries instead of downloading")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--platform", default="manylinux_2_34_x86_64")
    parser.add_argument(
        "--artifact-root",
        default=str(DEFAULT_ARTIFACT_ROOT),
        help="exact root allowed to receive the artifact (CI may use its dist directory)",
    )
    parser.add_argument(
        "--temporary-root",
        default="/srv/abyss-machine/tmp",
        help="existing root for temporary wheel downloads",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    temporary_root = Path(args.temporary_root).resolve()
    if not artifact_root.is_dir() or not temporary_root.is_dir():
        print(json.dumps({"ok": False, "status": "blocked", "reason": "artifact and temporary roots must already exist"}, sort_keys=True))
        return 1
    if not _within(output, artifact_root):
        print(json.dumps({"ok": False, "status": "blocked", "reason": "output must remain under the exact code-intelligence artifact root"}, sort_keys=True))
        return 1
    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    packages = [f"{item['name']}=={item['version']}" for item in lock.get("packages", [])]
    temporary: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.wheelhouse:
            wheelhouse = Path(args.wheelhouse).resolve()
        else:
            temporary = tempfile.TemporaryDirectory(prefix="adjacent-provider-wheelhouse-", dir=str(temporary_root))
            wheelhouse = Path(temporary.name)
            env = os.environ.copy()
            env["PIP_CACHE_DIR"] = "/srv/abyss-machine/cache/code-intelligence/pip"
            subprocess.run(
                [args.python, "-m", "pip", "download", "--only-binary=:all:", "--dest", str(wheelhouse), *packages],
                check=True, timeout=900, env=env, stdout=subprocess.DEVNULL,
            )
        if args.binary_root:
            binary_root = Path(args.binary_root).resolve()
        else:
            if temporary is None:
                temporary = tempfile.TemporaryDirectory(prefix="adjacent-provider-payload-", dir=str(temporary_root))
            binary_root = Path(temporary.name) / "bin"
            binary_root.mkdir(parents=True, exist_ok=True)
            for item in lock.get("binaries", []):
                archive_path = Path(temporary.name) / str(item["archive_filename"])
                urllib.request.urlretrieve(str(item["download_url"]), archive_path)
                if __import__("hashlib").sha256(archive_path.read_bytes()).hexdigest() != str(item["archive_sha256"]):
                    raise ValueError(f"locked binary archive digest mismatch: {item['provider']}")
                with tarfile.open(archive_path, mode="r:gz") as archive:
                    member = archive.getmember(str(item["archive_member"]))
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"locked binary archive member missing: {item['provider']}")
                    (binary_root / str(item["executable"])).write_bytes(stream.read())
        result = build_adjacent_provider_archive(
            wheelhouse, binary_root, output, lock_path=args.lock, source_ref=args.source_ref, platform=args.platform,
        )
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
