from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli  # noqa: E402
from abyss_machine import nervous_privacy_adapters as adapters  # noqa: E402


GENERATED_AT = "2026-07-07T12:00:00+00:00"


def test_privacy_config_document_and_latest_write_use_ports(tmp_path: Path) -> None:
    config_path = tmp_path / "privacy.json"
    latest_path = tmp_path / "latest.json"
    defaults = {
        "schema": "abyss_machine_nervous_privacy_v1",
        "global_pause": False,
        "browser_content": {"form_values_captured": False},
    }
    calls: list[dict[str, Any]] = []

    def fake_load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        calls.append({"load": path})
        return {"browser_content": {"raw_storage_root": "/srv/abyss-machine/storage/nervous/captures"}}, None

    def fake_write(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        calls.append({"write": path, "raw_storage_root": data["browser_content"]["raw_storage_root"], "mode": mode})
        return None

    data = adapters.config_document_from_path(
        config_path,
        defaults,
        generated_at=GENERATED_AT,
        load_json=fake_load,
    )
    written = adapters.write_latest(data, latest_path, writer=fake_write)

    assert data["_config_path"] == str(config_path)
    assert data["_config_exists"] is True
    assert data["generated_at"] == GENERATED_AT
    assert data["ok"] is True
    assert data["browser_content"]["form_values_captured"] is False
    assert written == data
    assert calls == [
        {"load": config_path},
        {"write": latest_path, "raw_storage_root": "/srv/abyss-machine/storage/nervous/captures", "mode": 0o664},
    ]


def test_privacy_state_save_and_audit_use_ports(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    audit_root = tmp_path / "audit"
    daily_path = audit_root / "2026" / "07" / "2026-07-07.jsonl"
    writes: list[dict[str, Any]] = []

    state = adapters.state_document_from_path(
        state_path,
        {
            "schema": "abyss_machine_nervous_privacy_state_v1",
            "global_pause": False,
            "private_mode": False,
        },
        load_json=lambda path: ({"global_pause": True, "reason": "operator"}, None),
        path_exists_port=lambda path: True,
    )

    def fake_write(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        writes.append({"write": path, "data": data, "mode": mode})
        return None

    def fake_append(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        writes.append({"append": path, "data": data, "mode": mode})
        return None

    saved = adapters.save_state_document(
        state,
        state_path,
        updated_by="privacy-set:pause",
        reason="pause on",
        change_id="privacy-change-1",
        updated_at=GENERATED_AT,
        schema_prefix="abyss_machine",
        version="test",
        writer=fake_write,
    )
    audit = adapters.audit_record_from_event(
        {"event": "privacy_state_changed", "change_id": "privacy-change-1"},
        audit_root=audit_root,
        write_enabled=True,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=GENERATED_AT,
        jsonl_append=fake_append,
        today_path=lambda root: daily_path,
    )

    assert state["global_pause"] is True
    assert state["exists"] is True
    assert saved["last_change_id"] == "privacy-change-1"
    assert saved["reason"] == "pause on"
    assert audit["ok"] is True
    assert writes == [
        {"write": state_path, "data": saved, "mode": 0o664},
        {"append": daily_path, "data": audit, "mode": 0o664},
    ]


def test_privacy_set_orchestrates_state_and_audit_ports() -> None:
    state = {
        "schema": "abyss_machine_nervous_privacy_state_v1",
        "global_pause": False,
        "private_mode": False,
    }
    calls: list[dict[str, Any]] = []

    def state_writer(next_state: dict[str, Any], updated_by: str, reason: str | None) -> dict[str, Any]:
        calls.append({"state_writer": updated_by, "reason": reason, "global_pause": next_state["global_pause"]})
        return {
            **next_state,
            "last_change_id": "privacy-change-1",
            "updated_by": updated_by,
            "reason": reason,
        }

    def audit_writer(event: dict[str, Any]) -> dict[str, Any]:
        calls.append({"audit": event})
        return {"schema": "abyss_machine_nervous_privacy_audit_v1", **event, "ok": True}

    result = adapters.privacy_set_from_ports(
        "pause",
        True,
        reason="operator pause",
        state_reader=lambda: state,
        state_writer=state_writer,
        audit_writer=audit_writer,
        now_iso=lambda: GENERATED_AT,
        schema_prefix="abyss_machine",
        version="test",
    )

    assert result["schema"] == "abyss_machine_nervous_privacy_set_v1"
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["state"]["last_change_id"] == "privacy-change-1"
    assert result["audit"]["event"] == "privacy_state_changed"
    assert result["audit"]["target"] == "pause"
    assert calls == [
        {"state_writer": "privacy-set:pause", "reason": "operator pause", "global_pause": True},
        {
            "audit": {
                "event": "privacy_state_changed",
                "change_id": "privacy-change-1",
                "target": "pause",
                "field": "global_pause",
                "before": False,
                "after": True,
                "reason": "operator pause",
            }
        },
    ]


def test_privacy_set_write_failure_skips_audit() -> None:
    result = adapters.privacy_set_from_ports(
        "private-mode",
        True,
        reason="privacy",
        state_reader=lambda: {"global_pause": False, "private_mode": False},
        state_writer=lambda state, updated_by, reason: {
            **state,
            "ok": False,
            "write_errors": [{"path": "/var/lib/abyss-machine/nervous/privacy/state.json", "error": "permission denied"}],
        },
        audit_writer=lambda event: (_ for _ in ()).throw(AssertionError("audit must not be written")),
        now_iso=lambda: GENERATED_AT,
        schema_prefix="abyss_machine",
        version="test",
    )

    assert result["schema"] == "abyss_machine_nervous_privacy_set_v1"
    assert result["ok"] is False
    assert result["error"] == "state write failed"
    assert result["attempted_change"] is True
    assert result["changed"] is False
    assert result["write_errors"][0]["error"] == "permission denied"


def test_cli_privacy_set_binds_concrete_ports_to_adapter(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_privacy_set_from_ports(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured.update(kwargs)
        return {"ok": True, "schema": "fixture_privacy_set"}

    monkeypatch.setattr(cli.nervous_privacy_adapters, "privacy_set_from_ports", fake_privacy_set_from_ports)

    assert cli.nervous_privacy_set("pause", True, reason="operator pause") == {
        "ok": True,
        "schema": "fixture_privacy_set",
    }

    assert captured["args"] == ("pause", True)
    assert captured["reason"] == "operator pause"
    assert captured["state_reader"] is cli.nervous_privacy_state
    assert captured["audit_writer"] is cli.nervous_privacy_audit
    assert captured["now_iso"] is cli.now_iso
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
