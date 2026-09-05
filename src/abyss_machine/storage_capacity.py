"""Cheap capacity sampling for the recurring storage monitor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import storage_forecast
from .path_policy import DEFAULT_PATH_POLICY


SCHEMA = "abyss_machine_storage_capacity_v1"
VERSION = "0.8.93"
CAPACITY_PATHS = (Path("/"), Path("/srv"))
CAPACITY_STATE_PATH = DEFAULT_PATH_POLICY.state_path("storage", "monitor", "capacity.json")


def capacity_observation() -> dict[str, object]:
    """Record the bounded capacity observation used by ``storage monitor``."""
    observation = storage_forecast.observe(
        CAPACITY_STATE_PATH,
        paths=CAPACITY_PATHS,
        write=True,
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "command": "storage capacity",
        "state_path": str(CAPACITY_STATE_PATH),
        "paths": [str(path) for path in CAPACITY_PATHS],
        **observation,
    }


def _print_text(document: dict[str, object]) -> None:
    print(
        "storage capacity: "
        f"ok={document.get('ok')} "
        f"state={document.get('state_path')}"
    )
    roots = document.get("roots")
    if not isinstance(roots, list):
        return
    for root in roots:
        if isinstance(root, dict):
            print(
                f"{root.get('path')}: "
                f"available={root.get('available_to_user_bytes')} "
                f"status={root.get('status')}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    document = capacity_observation()
    if args.json:
        print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(document)
    return 0 if document.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
