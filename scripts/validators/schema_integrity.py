#!/usr/bin/env python3
from __future__ import annotations

import json

from _common import REPO_ROOT, fail, load_json, ok, rel, require


INVENTORY = REPO_ROOT / "manifests" / "schema_inventory.manifest.json"
CONFIG_TEMPLATE_ROOT = REPO_ROOT / "config-templates" / "etc" / "abyss-machine"


def main() -> int:
    inventory = load_json(INVENTORY)
    failures: list[str] = []

    schemas = inventory.get("schemas")
    if not isinstance(schemas, list) or not schemas:
        return fail("schema inventory must contain a non-empty schemas list")
    for item in schemas:
        path = REPO_ROOT / str(item)
        require(path.is_file(), f"missing schema: {item}", failures)
        if not path.exists():
            continue
        payload = load_json(path)
        require(payload.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{rel(path)} must use draft 2020-12", failures)
        require(payload.get("$id"), f"{rel(path)} must define $id", failures)
        require(payload.get("title"), f"{rel(path)} must define title", failures)
        require(payload.get("type") == "object", f"{rel(path)} must describe an object", failures)

    for path in sorted(CONFIG_TEMPLATE_ROOT.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{rel(path)} invalid JSON: {exc}")
            continue
        if isinstance(payload, dict):
            require("schema" in payload, f"{rel(path)} must carry schema field", failures)

    if failures:
        return fail("schema integrity validation failed", failures)
    return ok("schema integrity validation passed")


if __name__ == "__main__":
    raise SystemExit(main())
