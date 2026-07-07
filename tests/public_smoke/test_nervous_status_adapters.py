from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import nervous_status_adapters as adapters  # noqa: E402


READ_AT = "2026-07-07T12:00:00+00:00"


def _paths(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    status_paths = {
        "design": tmp_path / "docs" / "nervous-design.md",
        "agents": tmp_path / "AGENTS.md",
        "policy_config": tmp_path / "etc" / "policy.json",
        "sources_config": tmp_path / "etc" / "sources.json",
        "privacy_config": tmp_path / "etc" / "privacy.json",
        "sources_state": tmp_path / "var" / "sources-state.json",
        "privacy_state": tmp_path / "var" / "privacy-state.json",
        "facts_latest": tmp_path / "var" / "facts-latest.json",
        "events_latest": tmp_path / "var" / "events-latest.json",
        "episodes_latest": tmp_path / "var" / "episodes-latest.json",
        "retrieval_latest": tmp_path / "var" / "retrieval-latest.json",
        "synthesis_latest": tmp_path / "var" / "synthesis-latest.json",
        "evals_latest": tmp_path / "var" / "evals-latest.json",
        "retention_latest": tmp_path / "var" / "retention-latest.json",
        "capture_latest": tmp_path / "var" / "capture-latest.json",
        "private_capture_root": tmp_path / "srv" / "captures",
        "screenshot_root": tmp_path / "srv" / "screenshots",
        "browser_content_latest": tmp_path / "var" / "browser-latest.json",
        "browser_content_root": tmp_path / "srv" / "browser-content",
        "search_index_db": tmp_path / "srv" / "index.db",
        "search_index_latest": tmp_path / "var" / "index-latest.json",
        "storage_latest": tmp_path / "var" / "storage-latest.json",
        "observability_latest": tmp_path / "var" / "thermal-latest.json",
        "ai_capabilities_latest": tmp_path / "var" / "ai-latest.json",
    }
    today_paths = {
        "events": {"today": str(tmp_path / "var" / "events.jsonl")},
        "facts": {"today": str(tmp_path / "var" / "facts.jsonl")},
        "episodes": {"today": str(tmp_path / "var" / "episodes.jsonl")},
        "retrieval": {"today": str(tmp_path / "var" / "retrieval.jsonl")},
        "evals": {"today": str(tmp_path / "var" / "evals.jsonl")},
        "retention": {"today": str(tmp_path / "var" / "retention.jsonl")},
    }
    return status_paths, today_paths


def test_status_document_from_ports_builds_nervous_readmodel_without_live_io(tmp_path: Path) -> None:
    status_paths, paths = _paths(tmp_path)
    for path in status_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix:
            path.write_text("{}", encoding="utf-8")
    latest_docs = {
        status_paths["events_latest"]: ({"ok": True, "summary": {"events": 3, "by_category": {"machine": 3}}}, None),
        status_paths["episodes_latest"]: ({"ok": True, "summary": {"episodes": 2, "by_category": {"machine": 2}}}, None),
        status_paths["retrieval_latest"]: ({"ok": True, "pack_id": "pack-1", "summary": {"evidence_items": 7}}, None),
        status_paths["synthesis_latest"]: ({"ok": True, "candidate_id": "syn-1", "scope": "daily", "summary": {"episodes": 2}}, None),
        status_paths["evals_latest"]: ({"ok": True, "summary": {"checks": 4}}, None),
        status_paths["retention_latest"]: ({"ok": True, "summary": {"candidates": 0}}, None),
        status_paths["capture_latest"]: ({"ok": True, "summary": {"facts": 5}, "sources": ["filesystem_metadata"]}, None),
        status_paths["browser_content_latest"]: ({"ok": True, "summary": {"records": 1}}, None),
    }
    reads: list[Path] = []
    units: list[str] = []

    def latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        reads.append(path)
        return latest_docs[path]

    def systemd_unit(unit: str) -> dict[str, Any]:
        units.append(unit)
        return {"name": unit, "is_active": unit.endswith(".timer")}

    data = adapters.status_document_from_ports(
        paths=paths,
        policy={"mode": "local", "active_daemon": False, "activation": {"watcher_enabled": False}},
        sources={
            "mode": "local",
            "safe_now": {
                "filesystem_metadata": {"enabled": True, "allowed": True},
                "disabled_safe": {"enabled": False, "allowed": True},
            },
            "deferred_until_privacy_controls": {
                "browser_active_tab": {"enabled": True, "allowed": True},
                "blocked_private": {"enabled": True, "allowed": False},
            },
            "state": {"overrides": {}},
        },
        privacy={"mode": "local", "global_pause": False, "private_mode": False, "state": {"paused": False}},
        status_paths=status_paths,
        unit_names={
            "daemon_service": "abyss-nervous.service",
            "daemon_timer": "abyss-nervous.timer",
            "passive_chronicle_service": "abyss-nervous-passive-chronicle.service",
            "passive_chronicle_timer": "abyss-nervous-passive-chronicle.timer",
            "browser_content_capture_service": "abyss-nervous-browser-content-capture.service",
            "browser_content_capture_timer": "abyss-nervous-browser-content-capture.timer",
            "search_index_service": "abyss-nervous-index-build.service",
            "search_index_timer": "abyss-nervous-index-build.timer",
        },
        index_counts=lambda: {"documents": 9, "chunks": 30},
        latest_reader=latest_reader,
        path_exists=lambda path: path.exists(),
        line_counter=lambda path: {"events.jsonl": 3, "facts.jsonl": 5}.get(path.name, 0),
        systemd_unit=systemd_unit,
        process_latest=lambda: {"path": "/var/lib/abyss-machine/process/latest.json", "exists": True},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )

    assert data["schema"] == "abyss_machine_nervous_status_v1"
    assert data["ok"] is True
    assert data["warnings"] == []
    assert data["sources"]["enabled_safe_sources"] == ["filesystem_metadata"]
    assert data["sources"]["enabled_private_connector_sources"] == ["browser_active_tab"]
    assert data["sources"]["deferred"] == ["browser_active_tab", "blocked_private"]
    assert data["browser_content_capture"]["summary"] == {"records": 1}
    assert data["local_index"]["documents"] == 9
    assert data["derived_events"]["events"] == 3
    assert data["derived_episodes"]["episodes"] == 2
    assert data["retrieval"]["pack_id"] == "pack-1"
    assert data["retrieval"]["evidence_items"] == 7
    assert data["synthesis"]["candidate_id"] == "syn-1"
    assert data["evals"]["summary"] == {"checks": 4}
    assert data["retention"]["summary"] == {"candidates": 0}
    assert data["today"]["events"] == 3
    assert data["today"]["facts"] == 5
    assert data["existing_bridges"]["process_latest"]["exists"] is True
    assert reads == [
        status_paths["events_latest"],
        status_paths["episodes_latest"],
        status_paths["retrieval_latest"],
        status_paths["synthesis_latest"],
        status_paths["evals_latest"],
        status_paths["retention_latest"],
        status_paths["capture_latest"],
        status_paths["browser_content_latest"],
    ]
    assert units == [
        "abyss-nervous-browser-content-capture.service",
        "abyss-nervous-browser-content-capture.timer",
        "abyss-nervous-index-build.service",
        "abyss-nervous-index-build.timer",
        "abyss-nervous.service",
        "abyss-nervous.timer",
        "abyss-nervous-passive-chronicle.service",
        "abyss-nervous-passive-chronicle.timer",
    ]


def test_status_warnings_and_write_outputs_are_adapter_owned(tmp_path: Path) -> None:
    status_paths, paths = _paths(tmp_path)
    for key, path in status_paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if key not in {"design", "agents"} and path.suffix:
            path.write_text("{}", encoding="utf-8")

    data = adapters.status_document_from_ports(
        paths=paths,
        policy={"mode": "local", "active_daemon": True, "activation": {"watcher_enabled": True}},
        sources={},
        privacy={},
        status_paths=status_paths,
        unit_names={
            "daemon_service": "daemon.service",
            "daemon_timer": "daemon.timer",
            "passive_chronicle_service": "passive.service",
            "passive_chronicle_timer": "passive.timer",
            "browser_content_capture_service": "browser.service",
            "browser_content_capture_timer": "browser.timer",
            "search_index_service": "index.service",
            "search_index_timer": "index.timer",
        },
        index_counts=lambda: {},
        latest_reader=lambda path: (None, "missing"),
        path_exists=lambda path: path.exists(),
        line_counter=lambda path: None,
        systemd_unit=lambda unit: {"name": unit, "is_active": False},
        process_latest=lambda: {"exists": False},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=READ_AT,
    )
    writes: list[tuple[Path, dict[str, Any], int]] = []
    latest_path = tmp_path / "latest.json"
    index_path = tmp_path / "index.json"

    def writer(path: Path, payload: dict[str, Any], mode: int) -> dict[str, Any] | None:
        writes.append((path, payload, mode))
        return {"path": str(path), "error": "permission denied"} if path == index_path else None

    written = adapters.write_status_outputs(
        data,
        latest_path=latest_path,
        index_path=index_path,
        index_document=lambda status: {"schema": "index", "status_ok": status["ok"]},
        writer=writer,
    )

    assert data["ok"] is False
    assert data["warnings"] == [
        "design artifact missing",
        "agent entrypoint missing",
        "policy claims active daemon; verify service before capture",
    ]
    assert written["write_errors"] == [{"path": str(index_path), "error": "permission denied"}]
    assert writes == [
        (latest_path, data, 0o664),
        (index_path, {"schema": "index", "status_ok": False}, 0o664),
    ]
