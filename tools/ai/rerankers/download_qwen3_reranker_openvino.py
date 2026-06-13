#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="OpenVINO/Qwen3-Reranker-0.6B-int8-ov")
    parser.add_argument("--local-dir", default="/srv/abyss-machine/cache/ai/qwen3-reranker-0.6b-int8-ov")
    parser.add_argument("--manifest", default="/var/lib/abyss-machine/ai/rerankers/qwen3-openvino/download-manifest.json")
    args = parser.parse_args()

    local_dir = Path(args.local_dir)
    manifest_path = Path(args.manifest)
    local_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    from huggingface_hub import snapshot_download

    snapshot_path = snapshot_download(
        repo_id=args.repo_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    root = Path(snapshot_path)
    files = []
    total_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        total_bytes += stat.st_size
        entry = {
            "path": rel,
            "size_bytes": stat.st_size,
        }
        if rel in {
            "config.json",
            "openvino_model.xml",
            "openvino_model.bin",
            "openvino_tokenizer.xml",
            "openvino_tokenizer.bin",
            "tokenizer.json",
            "tokenizer_config.json",
        }:
            entry["sha256"] = file_sha256(path)
        files.append(entry)

    required = [
        "config.json",
        "openvino_model.xml",
        "openvino_model.bin",
        "tokenizer.json",
        "tokenizer_config.json",
    ]
    missing = [name for name in required if not (root / name).exists()]
    data = {
        "schema": "abyss_machine_qwen3_reranker_openvino_download_v1",
        "ok": not missing,
        "repo_id": args.repo_id,
        "local_dir": str(root),
        "manifest": str(manifest_path),
        "missing_required": missing,
        "total_bytes": total_bytes,
        "files": files,
        "environment": {
            "HF_HOME": os.environ.get("HF_HOME"),
            "HUGGINGFACE_HUB_CACHE": os.environ.get("HUGGINGFACE_HUB_CACHE"),
            "TRANSFORMERS_CACHE": os.environ.get("TRANSFORMERS_CACHE"),
            "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME"),
        },
    }
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False))
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
