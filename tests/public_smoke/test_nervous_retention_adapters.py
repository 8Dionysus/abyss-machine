from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import nervous_retention_adapters


def _touch(path: Path, when: dt.datetime, text: str = "{}\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (when.timestamp(), when.timestamp()))
    return path


def _routes(base: Path) -> list[dict[str, object]]:
    return [
        {
            "layer": "retrieval",
            "root": str(base / "retrieval"),
            "days": 10,
            "apply_allowed": True,
            "reason": "operator recall packs are reproducible from the index",
        },
        {
            "layer": "facts",
            "root": str(base / "facts"),
            "days": 90,
            "apply_allowed": False,
            "reason": "facts require explicit forget",
        },
        {
            "layer": "missing",
            "root": str(base / "missing"),
            "days": 10,
            "apply_allowed": True,
            "reason": "missing root is reported, not created",
        },
    ]


def _paths(base: Path) -> dict[str, str]:
    return {
        "latest": str(base / "retention" / "latest.json"),
        "daily_glob": str(base / "retention" / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
    }


def test_retention_adapter_scans_candidates_and_protects_latest(tmp_path: Path) -> None:
    now = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)
    old = now - dt.timedelta(days=40)
    recent = now - dt.timedelta(days=1)
    old_candidate = _touch(tmp_path / "retrieval" / "2026" / "05" / "old.jsonl", old)
    old_latest = _touch(tmp_path / "retrieval" / "latest.json", old)
    _touch(tmp_path / "retrieval" / "recent.jsonl", recent)
    _touch(tmp_path / "facts" / "old.jsonl", old)

    files, route_errors = nervous_retention_adapters.collect_file_candidates(
        _routes(tmp_path),
        now_time=now,
        stop_at=tmp_path,
    )
    by_path = {item.get("path"): item for item in files if item.get("exists")}
    missing = [item for item in files if item.get("reason") == "root_missing"]

    assert route_errors == []
    assert by_path[str(old_candidate)]["candidate"] is True
    assert by_path[str(old_candidate)]["age_days"] == 40.0
    assert by_path[str(old_latest)]["protected"] is True
    assert by_path[str(old_latest)]["candidate"] is False
    assert missing[0]["layer"] == "missing"


def test_retention_adapter_apply_is_dry_run_first_and_writes_receipts(tmp_path: Path) -> None:
    now = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)
    candidate = _touch(tmp_path / "retrieval" / "old.jsonl", now - dt.timedelta(days=40))
    writes: list[tuple[str, str, int]] = []

    def writer(data: dict[str, object], latest_path: Path, daily_root: Path) -> list[dict[str, object]]:
        writes.append((str(latest_path), str(daily_root), int(data.get("summary", {}).get("candidate_files", 0))))
        return []

    plan = nervous_retention_adapters.plan(
        routes=_routes(tmp_path),
        paths=_paths(tmp_path),
        latest_path=tmp_path / "retention" / "latest.json",
        daily_root=tmp_path / "retention",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        now_time=now,
        stop_at=tmp_path,
        write_latest=False,
    )
    dry_run = nervous_retention_adapters.apply(
        plan_document=plan,
        dry_run=True,
        confirm=False,
        paths=_paths(tmp_path),
        latest_path=tmp_path / "retention" / "latest.json",
        daily_root=tmp_path / "retention",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        latest_history_writer=writer,
    )
    assert dry_run["applied"] is False
    assert dry_run["summary"]["removed_files"] == 0
    assert candidate.exists()

    applied = nervous_retention_adapters.apply(
        plan_document=plan,
        dry_run=False,
        confirm=True,
        paths=_paths(tmp_path),
        latest_path=tmp_path / "retention" / "latest.json",
        daily_root=tmp_path / "retention",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        latest_history_writer=writer,
    )

    assert applied["applied"] is True
    assert applied["summary"]["removed_files"] == 1
    assert "restore from operator backup" in applied["removed"][0]["restore_hint"]
    assert not candidate.exists()
    assert len(writes) == 2


def test_retention_adapter_route_error_blocks_confirmed_unlink(tmp_path: Path) -> None:
    now = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)
    target_root = tmp_path / "target-retrieval"
    candidate = _touch(target_root / "old.jsonl", now - dt.timedelta(days=40))
    symlink_root = tmp_path / "linked-retrieval"
    try:
        symlink_root.symlink_to(target_root, target_is_directory=True)
    except OSError:
        return

    routes = [
        {
            "layer": "retrieval",
            "root": str(symlink_root),
            "days": 10,
            "apply_allowed": True,
            "reason": "operator recall packs are reproducible from the index",
        }
    ]
    plan = nervous_retention_adapters.plan(
        routes=routes,
        paths=_paths(tmp_path),
        latest_path=tmp_path / "retention" / "latest.json",
        daily_root=tmp_path / "retention",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        now_time=now,
        stop_at=tmp_path,
        write_latest=False,
    )
    applied = nervous_retention_adapters.apply(
        plan_document=plan,
        dry_run=False,
        confirm=True,
        paths=_paths(tmp_path),
        latest_path=tmp_path / "retention" / "latest.json",
        daily_root=tmp_path / "retention",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        write_latest=False,
    )

    assert plan["ok"] is False
    assert plan["route_errors"][0]["error"] == "symlink_tail"
    assert applied["applied"] is False
    assert applied["ok"] is False
    assert applied["errors"][0]["error"] == "plan_not_ok"
    assert candidate.exists()


def test_retention_adapter_validate_uses_fakeable_latest_ports(tmp_path: Path) -> None:
    now = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)
    written: list[tuple[str, str]] = []
    plan = {
        "ok": True,
        "summary": {"candidates": 0, "candidate_bytes": 0, "by_layer": {}},
        "policy": {"facts_delete_behavior": "explicit forget only"},
        "candidates": [],
    }

    def reader(path: Path) -> tuple[dict[str, object] | None, str | None]:
        return {"schema": "abyss_machine_nervous_retention_plan_v1", "path": str(path)}, None

    def writer(path: Path, data: dict[str, object], mode: int) -> dict[str, object] | None:
        written.append((str(path), str(data.get("schema"))))
        assert mode == 0o664
        return None

    data = nervous_retention_adapters.validate(
        plan_document=plan,
        latest_path=tmp_path / "retention" / "latest.json",
        validate_latest_path=tmp_path / "retention" / "validate" / "latest.json",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=now.isoformat(),
        latest_reader=reader,
        latest_writer=writer,
    )

    assert data["ok"] is True
    assert written == [(str(tmp_path / "retention" / "validate" / "latest.json"), "abyss_machine_nervous_retention_validate_v1")]
