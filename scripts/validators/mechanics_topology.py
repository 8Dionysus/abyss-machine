#!/usr/bin/env python3
from __future__ import annotations

from _common import REPO_ROOT, fail, load_json, ok, rel, require


MANIFEST = REPO_ROOT / "manifests" / "repo_scaffold.manifest.json"


def main() -> int:
    manifest = load_json(MANIFEST)
    packages = manifest.get("mechanics_packages")
    required_files = manifest.get("mechanic_required_files")
    required_sections = manifest.get("mechanic_readme_sections")
    if not isinstance(packages, list) or not isinstance(required_files, list) or not isinstance(required_sections, list):
        return fail("mechanics manifest entries must be lists")

    failures: list[str] = []
    actual_packages = sorted(path.name for path in (REPO_ROOT / "mechanics").iterdir() if path.is_dir())
    expected_packages = sorted(str(item) for item in packages)
    require(actual_packages == expected_packages, f"mechanics packages mismatch: expected {expected_packages}, got {actual_packages}", failures)

    for package in expected_packages:
        package_root = REPO_ROOT / "mechanics" / package
        for item in required_files:
            path = package_root / str(item)
            require(path.is_file(), f"missing mechanics file: {rel(path)}", failures)
        readme = package_root / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.exists() else ""
        for section in required_sections:
            require(str(section) in text, f"{rel(readme)} missing section {section!r}", failures)

    if failures:
        return fail("mechanics topology validation failed", failures)
    return ok("mechanics topology validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
