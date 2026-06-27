from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_privacy import (  # noqa: E402
    audit_record,
    default_privacy,
    default_state,
    effective_privacy,
    saved_state_document,
    set_audit_event,
    set_error,
    set_result,
    set_transition,
    state_document,
    status_document,
    target_field,
)


def test_nervous_privacy_defaults_are_module_owned_contracts() -> None:
    privacy = default_privacy(
        "abyss_machine",
        "test",
        browser_raw_storage_root="/srv/abyss-machine/storage/nervous/browser-content",
    )
    state = default_state("abyss_machine", "test")
    audit = audit_record(
        {"event": "privacy_state_changed", "target": "pause"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert privacy["schema"] == "abyss_machine_nervous_privacy_v1"
    assert privacy["mode"] == "closed-by-default"
    assert privacy["global_pause"] is False
    assert privacy["private_mode"] is False
    assert "redaction dry-run" in privacy["controls_required_before_daemon"]
    assert privacy["retention"]["retrieval_packs_days"] == 30
    assert privacy["browser_content"]["raw_storage_root"].endswith("/browser-content")
    assert state["schema"] == "abyss_machine_nervous_privacy_state_v1"
    assert state["updated_by"] == "default"
    assert audit["schema"] == "abyss_machine_nervous_privacy_audit_v1"
    assert audit["event"] == "privacy_state_changed"


def test_nervous_privacy_state_merge_and_effective_status_are_contracts() -> None:
    defaults = default_state("abyss_machine", "test")
    state = state_document(
        defaults=defaults,
        loaded={"private_mode": True, "reason": "operator"},
        load_error=None,
        path="/var/lib/abyss-machine/nervous/privacy/state.json",
        exists=True,
    )
    missing = state_document(
        defaults=defaults,
        loaded=None,
        load_error="missing",
        path="/var/lib/abyss-machine/nervous/privacy/state.json",
        exists=False,
    )
    broken = state_document(
        defaults=defaults,
        loaded=None,
        load_error="invalid_json",
        path="/var/lib/abyss-machine/nervous/privacy/state.json",
        exists=True,
    )
    config = default_privacy("abyss_machine", "test", browser_raw_storage_root="/srv/browser")
    effective = effective_privacy(config, state, state_path=state["path"])
    status = status_document(
        effective=effective,
        config=config,
        config_path="/etc/abyss-machine/nervous/privacy.json",
        state_path=state["path"],
        audit_glob="/var/lib/abyss-machine/nervous/privacy/audit/YYYY/MM/YYYY-MM-DD.jsonl",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert state["private_mode"] is True
    assert state["global_pause"] is False
    assert state["reason"] == "operator"
    assert missing["exists"] is False
    assert "_load_error" not in missing
    assert broken["_load_error"] == "invalid_json"
    assert effective["effective_source"] == "config_or_state"
    assert effective["private_mode"] is True
    assert status["schema"] == "abyss_machine_nervous_privacy_status_v1"
    assert status["ok"] is True
    assert status["config"]["global_pause"] is False
    assert "snapshot writes" in status["behavior"]["global_pause"]


def test_nervous_privacy_set_transition_and_result_are_contracts() -> None:
    before = default_state("abyss_machine", "test")
    transition = set_transition(
        "pause",
        True,
        before,
        active_since="2026-06-26T12:00:00+00:00",
    )
    saved = saved_state_document(
        transition["state"],
        updated_by="privacy-set:pause",
        reason="operator pause",
        change_id="privacy-123",
        updated_at="2026-06-26T12:00:01+00:00",
        schema_prefix="abyss_machine",
        version="test",
    )
    audit = audit_record(
        set_audit_event(
            change_id=saved["last_change_id"],
            target="pause",
            field=transition["field"],
            before=transition["before"],
            after=transition["after"],
            reason="operator pause",
        ),
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:02+00:00",
    )
    result = set_result(
        target="pause",
        field=transition["field"],
        before=transition["before"],
        after=transition["after"],
        state=saved,
        audit=audit,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:03+00:00",
    )
    cleared = set_transition(
        "pause",
        False,
        {"global_pause": True, "private_mode": False, "active_since": "2026-06-26T12:00:00+00:00"},
        active_since="ignored",
    )

    assert target_field("pause") == "global_pause"
    assert target_field("private-mode") == "private_mode"
    assert target_field("unknown") is None
    assert transition["state"]["global_pause"] is True
    assert transition["state"]["active_since"] == "2026-06-26T12:00:00+00:00"
    assert saved["reason"] == "operator pause"
    assert audit["change_id"] == "privacy-123"
    assert result["schema"] == "abyss_machine_nervous_privacy_set_v1"
    assert result["changed"] is True
    assert cleared["state"]["active_since"] is None
    assert set_error("abyss_machine", "test", "now")["ok"] is False


def test_nervous_privacy_cli_delegates_to_contract_module() -> None:
    from abyss_machine import cli

    assert cli.nervous_privacy_contracts.target_field("pause") == "global_pause"
    assert cli.default_nervous_privacy()["schema"] == "abyss_machine_nervous_privacy_v1"
    assert cli.default_nervous_privacy_state()["schema"] == "abyss_machine_nervous_privacy_state_v1"
