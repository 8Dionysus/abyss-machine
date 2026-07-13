from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli


def _spec(latest: Path, history: Path, *, retention: str | None = None) -> dict[str, object]:
    spec: dict[str, object] = {
        "latest": latest,
        "history": history,
        "paths": lambda: {"schema": "paths"},
        "docs": [],
        "dirs": [],
        "executables": [],
        "json": [],
        "timers": [],
        "bridge_commands": [],
    }
    if retention is not None:
        spec["validation_retention"] = retention
    return spec


@pytest.mark.parametrize("name", ["memory", "resource"])
def test_memory_and_resource_validation_write_latest_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
) -> None:
    latest = tmp_path / name / "validate" / "latest.json"
    history = tmp_path / name / "validate"
    writes: list[tuple[Path, dict[str, object], int]] = []

    monkeypatch.setattr(cli, "subsystem_specs", lambda: {name: _spec(latest, history, retention="latest_only")})
    monkeypatch.setattr(cli, "bridge_manifest", lambda: {"commands": {}})
    monkeypatch.setattr(cli, "resource_gate_regression_cases", lambda: [])
    monkeypatch.setattr(
        cli,
        "safe_atomic_write_json",
        lambda path, data, mode: writes.append((path, data, mode)),
    )
    monkeypatch.setattr(
        cli,
        "write_latest_and_history",
        lambda *_args, **_kwargs: pytest.fail("latest-only validation appended history"),
    )

    document = cli.subsystem_validate(name, write_latest=True)

    assert document["ok"] is True
    assert writes == [(latest, document, 0o664)]


def test_other_subsystem_validation_keeps_latest_and_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    latest = tmp_path / "maps" / "validate" / "latest.json"
    history = tmp_path / "maps" / "validate"
    writes: list[tuple[dict[str, object], Path, Path]] = []

    monkeypatch.setattr(cli, "subsystem_specs", lambda: {"maps": _spec(latest, history)})
    monkeypatch.setattr(cli, "bridge_manifest", lambda: {"commands": {}})
    monkeypatch.setattr(
        cli,
        "write_latest_and_history",
        lambda data, latest_path, history_root: writes.append((data, latest_path, history_root)) or [],
    )

    document = cli.subsystem_validate("maps", write_latest=True)

    assert document["ok"] is True
    assert writes == [(document, latest, history)]


def test_owner_specs_declare_latest_only_validation_retention() -> None:
    specs = cli.subsystem_specs()

    assert specs["memory"]["validation_retention"] == "latest_only"
    assert specs["resource"]["validation_retention"] == "latest_only"
