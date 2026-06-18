#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "manifests" / "artifact_signature_policy.manifest.json"
OUTPUT = REPO_ROOT / "generated" / "contract_abi_signatures.min.json"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return {line for line in result.stdout.splitlines() if line}


def collect_source_files(source_paths: list[str], tracked: set[str]) -> list[str]:
    files: set[str] = set()
    for source in source_paths:
        path = REPO_ROOT / source
        if path.is_file():
            files.add(source)
            continue
        if path.is_dir():
            prefix = source.rstrip("/") + "/"
            files.update(item for item in tracked if item.startswith(prefix))
            continue
        raise FileNotFoundError(f"contract source path is missing: {source}")
    return sorted(files)


def file_digest(path_text: str) -> str:
    data = (REPO_ROOT / path_text).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def stable_digest(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_signatures() -> dict[str, Any]:
    policy = load_json(POLICY_PATH)
    tracked = tracked_files()
    surfaces = []
    for surface in policy.get("contract_surfaces", []):
        source_paths = [str(item) for item in surface.get("source_paths", [])]
        files = collect_source_files(source_paths, tracked)
        file_entries = [{"path": item, "sha256": file_digest(item)} for item in files]
        surfaces.append(
            {
                "id": surface.get("id"),
                "epoch": surface.get("epoch"),
                "artifact_class": surface.get("artifact_class"),
                "hash_algorithm": policy["abi_signature"]["algorithm"],
                "source_paths": source_paths,
                "source_file_count": len(file_entries),
                "source_tree_hash": stable_digest(file_entries),
                "source_files": file_entries,
            }
        )

    return {
        "schema": "abyss_machine_contract_abi_signatures_v1",
        "source": {
            "repo": "abyss-machine",
            "policy": "manifests/artifact_signature_policy.manifest.json",
            "policy_hash": stable_digest(policy),
        },
        "artifact_classes": sorted(policy.get("artifact_classes", {})),
        "contract_surfaces": surfaces,
    }


def encoded(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate/check abyss-machine contract ABI signatures.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content = encoded(build_signatures())
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content, encoding="utf-8")
        print(f"[ok] wrote {OUTPUT.relative_to(REPO_ROOT)}")
        return 0
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"[fail] {OUTPUT.relative_to(REPO_ROOT)} is stale; run scripts/generate_contract_abi_signatures.py --write")
            return 1
        print(f"[ok] {OUTPUT.relative_to(REPO_ROOT)} is current")
        return 0
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
