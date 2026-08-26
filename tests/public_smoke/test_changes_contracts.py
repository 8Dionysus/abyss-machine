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
    systemd_dropin = changes_contracts.surface_path_class(
        "/etc/systemd/system/abyss-ai-workload-refresh.service.d/override.conf",
        state_dir=tmp_path / "state",
        machine_root=tmp_path / "srv" / "abyss-machine",
        user_systemd_dir=tmp_path / "user-systemd",
        fallback_protection=fallback,
    )
    escaped_systemd = changes_contracts.surface_path_class(
        "/etc/systemd/system/abyss-ai-workload-refresh.service.d/../sshd.service",
        state_dir=tmp_path / "state",
        machine_root=tmp_path / "srv" / "abyss-machine",
        user_systemd_dir=tmp_path / "user-systemd",
        fallback_protection=fallback,
    )
    assert allowed["class"] == "host_config"
    assert allowed["decision"] == "allow_candidate"
    assert systemd_dropin["class"] == "host_system_systemd"
    assert systemd_dropin["decision"] == "allow_candidate"
    assert escaped_systemd["decision"] == "deny"
    assert escaped_systemd["owner"] == "operator_work"
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


def test_recovery_envelope_keeps_provenance_and_gaps_visible(tmp_path: Path) -> None:
    payload = changes_contracts.recovery_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-08-26T00:00:00+00:00",
        ok=True,
        changed=True,
        target_id="foreign-record",
        target_state="closed",
        source_path=tmp_path / "closed" / "foreign-record",
        corrective_change_id="corrective-record",
        record={"id": "foreign-record", "status": "closed"},
        event={"event": "reconstructed"},
        provenance={"method": "evidence_bound_missing_canonical_lifecycle", "gaps": ["original title absent"]},
        before={"change_json": {"exists": False}},
        after={"change_json": {"exists": True, "sha256": "abc"}},
        paths={"latest": str(tmp_path / "latest.json")},
    )
    assert payload["schema"] == "abyss_machine_change_recovery_v1"
    assert payload["provenance"]["gaps"] == ["original title absent"]
    assert payload["before"]["change_json"]["exists"] is False
    assert payload["after"]["change_json"]["sha256"] == "abc"


def test_cli_recovery_is_exact_target_and_corrective_bound(tmp_path: Path, monkeypatch) -> None:
    from abyss_machine import cli

    change_root = tmp_path / "changes"
    active_root = change_root / "active"
    closed_root = change_root / "closed"
    monkeypatch.setattr(cli, "CHANGE_ROOT", change_root)
    monkeypatch.setattr(cli, "CHANGE_ACTIVE_ROOT", active_root)
    monkeypatch.setattr(cli, "CHANGE_CLOSED_ROOT", closed_root)
    monkeypatch.setattr(cli, "CHANGE_HISTORY_ROOT", change_root / "history")
    monkeypatch.setattr(cli, "CHANGE_LATEST_PATH", change_root / "latest.json")
    monkeypatch.setattr(cli, "CHANGE_INDEX_PATH", change_root / "index.json")
    monkeypatch.setattr(cli, "CHANGE_AGENTS_PATH", change_root / "AGENTS.md")

    corrective_id = "corrective-record"
    corrective = cli.change_record(
        change_id=corrective_id,
        title="Correct missing lifecycle records",
        intent="repair only missing canonical ledger files",
        surfaces=[str(change_root)],
        write_latest=False,
    )
    assert corrective["ok"] is True

    target_id = "foreign-record"
    target = active_root / target_id
    target.mkdir(parents=True)
    (target / "intent.md").write_text("# Intent\n\nPreserve the surviving producer evidence.\n", encoding="utf-8")
    (target / "rollback.md").write_text("# Rollback\n\nRestore from the recorded archive.\n", encoding="utf-8")
    producer = target / "producer.py"
    producer.write_text("# evidence-bound producer\n", encoding="utf-8")

    result = cli.change_recover(
        change_id=target_id,
        state="active",
        source_dir=str(target),
        corrective_change_id=corrective_id,
        title="surviving producer lifecycle",
        surfaces=["/srv/abyss-machine/tmp/ai/example"],
        evidence_paths=["intent.md", "rollback.md", "producer.py"],
        provenance_gaps=["original title was not persisted", "original validation artifact was absent"],
        write_latest=False,
    )
    assert result["ok"] is True
    assert result["record"]["reconstruction"]["gaps"] == [
        "original title was not persisted",
        "original validation artifact was absent",
    ]
    assert (target / "change.json").is_file()
    assert (target / "actions.jsonl").is_file()
    assert (target / "validation.md").is_file()
    assert (target / "closeout.md").is_file()
    assert json.loads((target / "actions.jsonl").read_text(encoding="utf-8").splitlines()[0])["event"] == "reconstructed"

    second = cli.change_recover(
        change_id=target_id,
        state="active",
        source_dir=str(target),
        corrective_change_id=corrective_id,
        title="must not overwrite",
        surfaces=["/srv/abyss-machine/tmp/ai/example"],
        evidence_paths=["intent.md"],
        provenance_gaps=["already reconstructed"],
        write_latest=False,
    )
    assert second["ok"] is False
    assert "refusing overwrite" in second["errors"][0]["message"]
