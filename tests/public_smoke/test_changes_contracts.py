from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import changes_contracts


def test_change_id_and_decision_review_contracts(tmp_path: Path) -> None:
    assert changes_contracts.change_id_valid("host-change_01")
    assert not changes_contracts.change_id_valid("../bad")
    assert not changes_contracts.change_id_valid("x")

    payload, issues = changes_contracts.decision_review_payload(
        "existing",
        "0001-test.md",
        None,
        decisions_root=tmp_path / "decisions",
        reviewed_at="2026-06-25T00:00:00+00:00",
        decision_ref_exists=False,
    )
    assert payload is not None
    assert payload["decision_ref"].endswith("/decisions/0001-test.md")
    assert issues == [f"decision ref does not exist: {payload['decision_ref']}"]

    payload, issues = changes_contracts.decision_review_payload(
        "no-record-needed",
        None,
        "generated latest refresh only",
        decisions_root=tmp_path / "decisions",
        reviewed_at="2026-06-25T00:00:00+00:00",
    )
    assert issues == []
    assert payload == {
        "status": "no-record-needed",
        "decision_ref": None,
        "reason": "generated latest refresh only",
        "reviewed_at": "2026-06-25T00:00:00+00:00",
        "contract": "host change close requires explicit decision review",
    }
    assert "generated latest refresh only" in changes_contracts.decision_review_closeout_text(payload)


def test_change_surface_classification_and_preflight_are_owner_gated(tmp_path: Path) -> None:
    fallback = {
        "class": "protected_work_owned",
        "decision": "deny",
        "owner": "operator_work",
        "matched_root": "/srv/work",
        "reason": "work-owned",
    }
    allowed = changes_contracts.surface_path_class(
        "/etc/abyss-machine/storage-policy.json",
        state_dir=tmp_path / "state",
        machine_root=tmp_path / "srv" / "abyss-machine",
        user_systemd_dir=tmp_path / "user-systemd",
        fallback_protection=fallback,
    )
    protected = changes_contracts.surface_path_class(
        "/srv/work/client",
        state_dir=tmp_path / "state",
        machine_root=tmp_path / "srv" / "abyss-machine",
        user_systemd_dir=tmp_path / "user-systemd",
        fallback_protection=fallback,
    )
    assert allowed["class"] == "host_config"
    assert allowed["decision"] == "allow_candidate"
    assert protected["decision"] == "deny"
    assert protected["owner"] == "operator_work"

    denied = changes_contracts.preflight_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        surfaces=["/srv/work/client"],
        intent="test protected surface",
        change_id=None,
        rollback=None,
        owner_route=False,
        classified_surfaces=[protected],
        active_ids=[],
        topology_summary={"fails": 0, "warnings": 0, "checks": 10},
        latest_path=tmp_path / "preflight" / "latest.json",
        history_root=tmp_path / "preflight",
        change_index_path=tmp_path / "index.json",
        hooks_etc_dir=tmp_path / "hooks-etc",
        hooks_srv_dir=tmp_path / "hooks-srv",
        hard_deny_without_owner_route=["/srv/work"],
    )
    assert denied["decision"] == "deny"
    assert denied["ok"] is False
    assert denied["summary"]["fails"] == 1
    assert denied["checks"][0]["key"] == "surface_boundary:/srv/work/client"

    owner_routed = changes_contracts.preflight_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        surfaces=["/srv/work/client"],
        intent="test protected surface with owner route",
        change_id=None,
        rollback=None,
        owner_route=True,
        classified_surfaces=[protected],
        active_ids=[],
        topology_summary={"fails": 0, "warnings": 0, "checks": 10},
        latest_path=tmp_path / "preflight" / "latest.json",
        history_root=tmp_path / "preflight",
        change_index_path=tmp_path / "index.json",
        hooks_etc_dir=tmp_path / "hooks-etc",
        hooks_srv_dir=tmp_path / "hooks-srv",
        hard_deny_without_owner_route=["/srv/work"],
    )
    assert owner_routed["decision"] == "warn"
    assert owner_routed["ok"] is True
    assert owner_routed["checks"][0]["key"] == "surface_owner_route:/srv/work/client"


def test_change_paths_index_and_latest_read_models(tmp_path: Path) -> None:
    paths = changes_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        change_root=tmp_path / "changes",
        agents_path=tmp_path / "changes" / "AGENTS.md",
        index_path=tmp_path / "changes" / "index.json",
        latest_path=tmp_path / "changes" / "latest.json",
        active_root=tmp_path / "changes" / "active",
        closed_root=tmp_path / "changes" / "closed",
        history_root=tmp_path / "changes" / "history",
        history_today=tmp_path / "changes" / "history" / "2026" / "06" / "2026-06-25.jsonl",
        index_exists=True,
        indexed_summary={"active_records": 1},
    )
    assert paths["schema"] == "abyss_machine_changes_paths_v1"
    assert paths["indexed_summary"] == {"active_records": 1}
    assert paths["commands"]["preflight"] == "abyss-machine changes preflight --intent TEXT --surface SURFACE --json"

    index = changes_contracts.index_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        paths=paths,
        active_items=[{"id": "a"}],
        closed_items=[{"id": "c"}],
        latest={"ok": True},
        latest_error=None,
        history_file_count=2,
        recent_history_lines=3,
        latest_exists=True,
    )
    assert index["summary"]["active_records"] == 1
    assert changes_contracts.status_document(index, schema_prefix="abyss_machine")["schema"] == "abyss_machine_changes_status_v1"
    assert changes_contracts.latest_missing_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="now",
        latest_path=tmp_path / "latest.json",
        error=None,
    )["error"] == "missing"
    assert changes_contracts.latest_read_document({"ok": True}, read_at="now") == {"ok": True, "read_at": "now"}


def test_changes_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "changes", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_changes_paths_v1"
    assert payload["record_layout"]["change_json"] == "active/CHANGE_ID/change.json"
    assert payload["commands"]["close"].startswith("abyss-machine changes close")
