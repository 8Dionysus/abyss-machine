"""Cheap capacity sampling for the recurring storage monitor."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence

from . import storage_forecast
from .path_policy import DEFAULT_PATH_POLICY


SCHEMA = "abyss_machine_storage_capacity_v1"
VERSION = "0.8.93"
CAPACITY_PATHS = (Path("/"), Path("/srv"))
CAPACITY_STATE_PATH = DEFAULT_PATH_POLICY.state_path("storage", "monitor", "capacity.json")
CODE_GENERATIONS_ROOT = Path("/usr/local/libexec/.abyss-machine-code-generations")
CODE_GENERATION_RE = re.compile(r"^[0-9a-f]{64}$")


def expected_code_generation_guard(
    expected_generation: str | None,
    *,
    module_path: str | Path | None = None,
) -> dict[str, object]:
    """Verify an optional generation pin before touching capacity state."""
    if expected_generation is None:
        return {"checked": False, "ok": True}
    normalized = str(expected_generation).strip()
    if not CODE_GENERATION_RE.fullmatch(normalized):
        return {
            "checked": True,
            "ok": False,
            "error": "expected_code_generation_invalid",
        }
    expected_module = (
        CODE_GENERATIONS_ROOT
        / normalized
        / "abyss_machine"
        / "storage_capacity.py"
    )
    resolved_module = Path(
        module_path if module_path is not None else __file__
    ).resolve()
    if resolved_module != expected_module:
        return {
            "checked": True,
            "ok": False,
            "error": "expected_code_generation_mismatch",
            "expected_generation": normalized,
            "expected_module_path": str(expected_module),
            "resolved_module_path": str(resolved_module),
        }
    return {
        "checked": True,
        "ok": True,
        "expected_generation": normalized,
        "module_path": str(resolved_module),
    }


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


def _generation_failure_document(guard: dict[str, object]) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "command": "storage capacity",
        "ok": False,
        "error": guard.get("error") or "expected_code_generation_failed",
        "code_generation_guard": guard,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--expected-code-generation",
        metavar="HEX",
        help="require the loaded module from the installed 64-hex generation directory",
    )
    args = parser.parse_args(argv)
    generation_guard = expected_code_generation_guard(args.expected_code_generation)
    if generation_guard.get("ok") is not True:
        print(
            json.dumps(
                _generation_failure_document(generation_guard),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    document = capacity_observation()
    if generation_guard.get("checked"):
        document["code_generation_guard"] = generation_guard
    if args.json:
        print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(document)
    return 0 if document.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
