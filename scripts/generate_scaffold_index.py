#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "generated" / "scaffold_index.min.json"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def build_index() -> dict[str, Any]:
    scaffold = load_json(REPO_ROOT / "manifests" / "repo_scaffold.manifest.json")
    profiles = load_json(REPO_ROOT / "manifests" / "bootstrap_profiles.manifest.json")
    schemas = load_json(REPO_ROOT / "manifests" / "schema_inventory.manifest.json")
    mechanics = sorted(path.name for path in (REPO_ROOT / "mechanics").iterdir() if path.is_dir())
    system_units = sorted(path.name for path in (REPO_ROOT / "systemd" / "system").iterdir() if path.is_file())
    user_units = sorted(path.name for path in (REPO_ROOT / "systemd" / "user").iterdir() if path.is_file())
    docs_sections = sorted(path.name for path in (REPO_ROOT / "docs").iterdir() if path.is_dir())
    return {
        "schema": "abyss_machine_scaffold_index_v1",
        "source": {
            "repo": "abyss-machine",
            "role": "public host-organ scaffold",
            "generated_from": [
                "manifests/repo_scaffold.manifest.json",
                "manifests/bootstrap_profiles.manifest.json",
                "manifests/schema_inventory.manifest.json"
            ]
        },
        "roots": {
            "config_templates": "config-templates/etc/abyss-machine",
            "systemd_system": "systemd/system",
            "systemd_user": "systemd/user",
            "mechanics": "mechanics",
            "schemas": "schemas",
            "validation_lanes": "docs/validation/validation_lanes.json"
        },
        "counts": {
            "mechanics": len(mechanics),
            "docs_sections": len(docs_sections),
            "schemas": len(schemas.get("schemas", [])),
            "bootstrap_profiles": len(profiles.get("profiles", {})),
            "system_units": len(system_units),
            "user_units": len(user_units)
        },
        "mechanics_packages": mechanics,
        "docs_sections": docs_sections,
        "bootstrap_profiles": sorted(profiles.get("profiles", {})),
        "schema_files": sorted(schemas.get("schemas", [])),
        "root_files": sorted(scaffold.get("root_files", []))
    }


def encoded(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate/check the abyss-machine scaffold index.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    content = encoded(build_index())
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(content, encoding="utf-8")
        print(f"[ok] wrote {OUTPUT.relative_to(REPO_ROOT)}")
        return 0
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"[fail] {OUTPUT.relative_to(REPO_ROOT)} is stale; run scripts/generate_scaffold_index.py --write")
            return 1
        print(f"[ok] {OUTPUT.relative_to(REPO_ROOT)} is current")
        return 0
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
