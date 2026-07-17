#!/usr/bin/env python3
from __future__ import annotations

import json
import re

from _common import REPO_ROOT, fail, load_json, ok, tracked_files


MANIFEST = REPO_ROOT / "manifests" / "public_boundary.manifest.json"


def is_portable_kag_shard_path(path_text: str) -> bool:
    return (
        path_text.startswith("kag/indexes/shards/")
        and path_text.endswith(".jsonl")
        and len(path_text.split("/")) == 5
    )


def has_forbidden_tracked_suffix_class(
    path_text: str,
    suffixes: list[str],
) -> bool:
    for suffix in suffixes:
        if not (path_text.endswith(suffix) or suffix in path_text):
            continue
        if suffix == ".jsonl" and is_portable_kag_shard_path(path_text):
            continue
        return True
    return False


def is_repo_self_index(path_text: str, text: str) -> bool:
    if is_portable_kag_shard_path(path_text):
        try:
            records = [
                json.loads(line)
                for line in text.splitlines()
                if line.strip()
            ]
        except json.JSONDecodeError:
            return False
        return bool(records) and all(
            isinstance(record, dict)
            and isinstance(record.get("_key"), str)
            and isinstance(record.get("_kind"), str)
            for record in records
        )
    if not path_text.startswith("kag/indexes/") or not path_text.endswith(".json"):
        return False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("schema_version") in {
        "aoa-repo-local-kag-index-v2",
        "aoa-repo-local-kag-repository-index-v2",
    }


def main() -> int:
    manifest = load_json(MANIFEST)
    prefixes = [str(item) for item in manifest.get("forbidden_tracked_path_prefixes", [])]
    suffixes = [str(item) for item in manifest.get("forbidden_tracked_path_suffixes", [])]
    patterns = [re.compile(str(item)) for item in manifest.get("forbidden_text_patterns", [])]
    allowed_legacy_mentions = set(str(item) for item in manifest.get("allowed_legacy_template_mentions", []))
    legacy_template_ref = re.compile(r"(?<![A-Za-z0-9_-])templates/(?:etc|systemd)")

    failures: list[str] = []
    for path_text in tracked_files():
        if any(path_text.startswith(prefix) for prefix in prefixes):
            failures.append(f"forbidden tracked path prefix: {path_text}")
        if has_forbidden_tracked_suffix_class(path_text, suffixes):
            failures.append(f"forbidden tracked path suffix/class: {path_text}")
        path = REPO_ROOT / path_text
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            if pattern.search(text):
                failures.append(f"forbidden text pattern {pattern.pattern!r}: {path_text}")
        if legacy_template_ref.search(text) and not is_repo_self_index(path_text, text):
            if path_text not in allowed_legacy_mentions:
                failures.append(f"legacy templates reference outside allowlist: {path_text}")

    if failures:
        return fail("public boundary validation failed", failures)
    return ok("public boundary validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
