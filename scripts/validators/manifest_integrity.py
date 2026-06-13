#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from _common import REPO_ROOT, fail, load_json, ok, rel, require


MANIFEST_ROOT = REPO_ROOT / "manifests"
EXPECTED_SCHEMAS = {
    "repo_scaffold.manifest.json": "abyss_machine_repo_scaffold_manifest_v1",
    "bootstrap_profiles.manifest.json": "abyss_machine_bootstrap_profiles_manifest_v1",
    "public_boundary.manifest.json": "abyss_machine_public_boundary_manifest_v1",
    "schema_inventory.manifest.json": "abyss_machine_schema_inventory_manifest_v1",
}


def main() -> int:
    failures: list[str] = []
    for name, expected_schema in EXPECTED_SCHEMAS.items():
        path = MANIFEST_ROOT / name
        payload = load_json(path)
        require(payload.get("schema") == expected_schema, f"{rel(path)} schema mismatch", failures)

    scaffold = load_json(MANIFEST_ROOT / "repo_scaffold.manifest.json")
    profiles = load_json(MANIFEST_ROOT / "bootstrap_profiles.manifest.json")
    boundary = load_json(MANIFEST_ROOT / "public_boundary.manifest.json")
    inventory = load_json(MANIFEST_ROOT / "schema_inventory.manifest.json")

    require(bool(scaffold.get("mechanics_packages")), "repo scaffold manifest must name mechanics packages", failures)
    require(isinstance(profiles.get("profiles"), dict) and bool(profiles["profiles"]), "bootstrap profiles manifest must name profiles", failures)
    require(bool(boundary.get("forbidden_tracked_path_prefixes")), "public boundary manifest must name forbidden prefixes", failures)
    require(bool(inventory.get("schemas")), "schema inventory manifest must name schemas", failures)

    for path in sorted(MANIFEST_ROOT.glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{rel(path)} invalid JSON: {exc}")

    if failures:
        return fail("manifest integrity validation failed", failures)
    return ok("manifest integrity validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
