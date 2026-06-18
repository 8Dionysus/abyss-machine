from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


class ValidationError(RuntimeError):
    pass


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing JSON file: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{rel(path)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{rel(path)} must contain a JSON object")
    return payload


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValidationError(result.stderr.strip() or "git ls-files failed")
    return [line for line in result.stdout.splitlines() if line and (REPO_ROOT / line).is_file()]


def fail(message: str, details: list[str] | None = None) -> int:
    print(f"[fail] {message}")
    for item in details or []:
        print(f"- {item}")
    return 1


def ok(message: str) -> int:
    print(f"[ok] {message}")
    return 0


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)
