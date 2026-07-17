from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATORS = ROOT / "scripts" / "validators"
sys.path.insert(0, str(VALIDATORS))

from public_boundary import (  # noqa: E402
    has_forbidden_tracked_suffix_class,
    is_repo_self_index,
)


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


def test_portable_kag_jsonl_shards_are_the_only_jsonl_exception() -> None:
    suffixes = [".jsonl", ".sqlite"]

    assert not has_forbidden_tracked_suffix_class(
        "kag/indexes/shards/source/0.jsonl",
        suffixes,
    )
    assert has_forbidden_tracked_suffix_class("artifacts/events.jsonl", suffixes)
    assert has_forbidden_tracked_suffix_class(
        "kag/indexes/shards/source/nested/0.jsonl",
        suffixes,
    )


def test_portable_kag_shard_is_recognized_as_a_derived_self_index() -> None:
    path = "kag/indexes/shards/source/0.jsonl"
    legacy_route = "templates" + "/etc"
    valid = (
        '{"_key":"source:one","_kind":"source","label":"'
        + legacy_route
        + '"}\n'
    )

    assert is_repo_self_index(path, valid)
    assert not is_repo_self_index(path, '{"label":"' + legacy_route + '"}\n')
    assert not is_repo_self_index(path, "not-json\n")
