#!/usr/bin/env python3
from __future__ import annotations

import re

from _common import REPO_ROOT, fail, load_json, ok, tracked_files


MANIFEST = REPO_ROOT / "manifests" / "public_boundary.manifest.json"


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
        if any(path_text.endswith(suffix) or suffix in path_text for suffix in suffixes):
            failures.append(f"forbidden tracked path suffix/class: {path_text}")
        path = REPO_ROOT / path_text
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in patterns:
            if pattern.search(text):
                failures.append(f"forbidden text pattern {pattern.pattern!r}: {path_text}")
        if legacy_template_ref.search(text):
            if path_text not in allowed_legacy_mentions:
                failures.append(f"legacy templates reference outside allowlist: {path_text}")

    if failures:
        return fail("public boundary validation failed", failures)
    return ok("public boundary validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
