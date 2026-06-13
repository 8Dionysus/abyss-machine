from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def iter_repo_text() -> list[Path]:
    skipped_parts = {".git", "__pycache__", ".pytest_cache"}
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skipped_parts for part in path.parts):
            continue
        if path.suffix in {".pyc", ".xpi", ".zip"}:
            continue
        paths.append(path)
    return paths


def test_no_private_vault_secret_path_is_published() -> None:
    forbidden = "/abyss/Backups/" + "secrets"
    offenders = []
    for path in iter_repo_text():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if forbidden in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_generated_planes_are_ignored_not_vendored() -> None:
    assert not (ROOT / "var" / "lib" / "abyss-machine").exists()
    assert not (ROOT / "srv" / "abyss-machine" / "cache").exists()
    assert not (ROOT / "srv" / "abyss-machine" / "runtimes").exists()
