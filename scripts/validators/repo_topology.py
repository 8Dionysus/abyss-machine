#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _common import REPO_ROOT, fail, load_json, ok, rel, require


MANIFEST = REPO_ROOT / "manifests" / "repo_scaffold.manifest.json"


def main() -> int:
    manifest = load_json(MANIFEST)
    failures: list[str] = []

    for name in manifest.get("root_files", []):
        path = REPO_ROOT / str(name)
        require(path.is_file(), f"missing root file: {name}", failures)

    districts = manifest.get("districts")
    if not isinstance(districts, dict):
        return fail("repo scaffold manifest districts must be an object")
    for district, required_files in districts.items():
        root = REPO_ROOT / str(district)
        require(root.is_dir(), f"missing district: {district}", failures)
        if not isinstance(required_files, list):
            failures.append(f"{district}: required files must be a list")
            continue
        for item in required_files:
            path = root / str(item)
            require(path.is_file(), f"missing district file: {rel(path)}", failures)

    for section in manifest.get("docs_sections", []):
        root = REPO_ROOT / "docs" / str(section)
        require(root.is_dir(), f"missing docs section: docs/{section}", failures)
        require((root / "README.md").is_file(), f"missing docs section README: docs/{section}/README.md", failures)

    for legacy_root in manifest.get("forbidden_legacy_roots", []):
        path = REPO_ROOT / str(legacy_root)
        require(not path.exists(), f"legacy root must not exist: {legacy_root}", failures)

    require((REPO_ROOT / "config-templates" / "etc" / "abyss-machine").is_dir(), "missing config-template etc root", failures)
    require((REPO_ROOT / "systemd" / "system").is_dir(), "missing systemd/system root", failures)
    require((REPO_ROOT / "systemd" / "user").is_dir(), "missing systemd/user root", failures)

    if failures:
        return fail("repo topology validation failed", failures)
    return ok("repo topology validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
