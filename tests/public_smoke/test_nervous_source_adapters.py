from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import cli
from abyss_machine import nervous_source_adapters


READ_AT = "2026-06-30T12:00:00+00:00"


def test_source_adapter_config_document_and_latest_write_use_ports(tmp_path: Path) -> None:
    config_path = tmp_path / "sources.json"
    latest_path = tmp_path / "latest.json"
    defaults = {
        "schema": "abyss_machine_nervous_sources_v1",
        "safe_now": {
            "filesystem_metadata": {"enabled": True, "allowed": True, "content": "metadata"},
        },
    }
    calls: list[dict[str, Any]] = []

    def fake_load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
        calls.append({"load": path})
        return {"safe_now": {"filesystem_metadata": {"enabled": False}}}, None

    def fake_write(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        calls.append({"write": path, "enabled": data["safe_now"]["filesystem_metadata"]["enabled"], "mode": mode})
        return None

    data = nervous_source_adapters.config_document_from_path(
        config_path,
        defaults,
        generated_at=READ_AT,
        load_json=fake_load,
    )
    written = nervous_source_adapters.write_latest(data, latest_path, writer=fake_write)

    assert data["_config_path"] == str(config_path)
    assert data["_config_exists"] is True
    assert data["generated_at"] == READ_AT
    assert data["ok"] is True
    assert data["safe_now"]["filesystem_metadata"]["enabled"] is False
    assert written == data
    assert calls == [
        {"load": config_path},
        {"write": latest_path, "enabled": False, "mode": 0o664},
    ]


def test_source_adapter_state_read_and_save_use_ports(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    defaults = {
        "schema": "abyss_machine_nervous_sources_state_v1",
        "version": "test",
        "overrides": {},
    }
    writes: list[dict[str, Any]] = []

    state = nervous_source_adapters.state_document_from_path(
        state_path,
        defaults,
        load_json=lambda path: (
            {
                "overrides": {
                    "typing_saved_text": {
                        "enabled": False,
                        "updated_at": READ_AT,
                        "updated_by": "source-disable",
                    }
                }
            },
            None,
        ),
        path_exists=lambda path: True,
    )

    def fake_write(path: Path, data: dict[str, Any], mode: int) -> dict[str, Any] | None:
        writes.append({"path": path, "data": data, "mode": mode})
        return None

    saved = nervous_source_adapters.save_state_document(
        state,
        state_path,
        updated_by="source-disable:typing_saved_text",
        change_id="source-change-1",
        updated_at="2026-06-30T12:00:01+00:00",
        schema_prefix="abyss_machine",
        version="test",
        writer=fake_write,
    )

    assert state["path"] == str(state_path)
    assert state["exists"] is True
    assert state["overrides"]["typing_saved_text"]["enabled"] is False
    assert saved["last_change_id"] == "source-change-1"
    assert saved["updated_by"] == "source-disable:typing_saved_text"
    assert writes == [{"path": state_path, "data": saved, "mode": 0o664}]


def test_source_adapter_source_set_orchestrates_state_and_audit_ports() -> None:
    state = {
        "schema": "abyss_machine_nervous_sources_state_v1",
        "version": "test",
        "overrides": {},
    }
    calls: list[dict[str, Any]] = []

    def source_lookup(source_id: str) -> dict[str, Any] | None:
        calls.append({"lookup": source_id})
        return {
            "id": source_id,
            "enabled": True,
            "can_enable_now": True,
        }

    def state_writer(next_state: dict[str, Any], updated_by: str) -> dict[str, Any]:
        calls.append({"state_writer": updated_by, "enabled": next_state["overrides"]["typing_saved_text"]["enabled"]})
        return {
            "schema": "abyss_machine_nervous_sources_state_v1",
            "version": "test",
            "overrides": next_state["overrides"],
            "last_change_id": "source-change-1",
        }

    def audit_writer(event: dict[str, Any]) -> dict[str, Any]:
        calls.append({"audit": event})
        return {"schema": "abyss_machine_nervous_privacy_audit_v1", **event, "ok": True}

    result = nervous_source_adapters.source_set_from_ports(
        "typing_saved_text",
        False,
        reason="operator disable",
        source_lookup=source_lookup,
        state_reader=lambda: state,
        state_writer=state_writer,
        audit_writer=audit_writer,
        effective_lookup=lambda source_id: {"id": source_id, "enabled": False},
        now_iso=lambda: READ_AT,
        schema_prefix="abyss_machine",
        version="test",
    )

    assert result["schema"] == "abyss_machine_nervous_source_set_v1"
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["state"]["last_change_id"] == "source-change-1"
    assert result["audit"]["event"] == "source_state_changed"
    assert result["audit"]["source"] == "typing_saved_text"
    assert result["effective"] == {"id": "typing_saved_text", "enabled": False}
    assert calls == [
        {"lookup": "typing_saved_text"},
        {"state_writer": "source-disable:typing_saved_text", "enabled": False},
        {
            "audit": {
                "event": "source_state_changed",
                "change_id": "source-change-1",
                "source": "typing_saved_text",
                "before": True,
                "after": False,
                "reason": "operator disable",
            }
        },
    ]


def test_source_adapter_source_set_unknown_and_blocked_do_not_touch_state() -> None:
    blocked = nervous_source_adapters.source_set_from_ports(
        "browser_active_tab",
        True,
        reason=None,
        source_lookup=lambda source_id: {"id": source_id, "enabled": False, "can_enable_now": False, "enable_blocker": "source is not allowed by policy"},
        state_reader=lambda: (_ for _ in ()).throw(AssertionError("state must not be read")),
        state_writer=lambda state, updated_by: (_ for _ in ()).throw(AssertionError("state must not be written")),
        audit_writer=lambda event: (_ for _ in ()).throw(AssertionError("audit must not be written")),
        effective_lookup=lambda source_id: None,
        now_iso=lambda: READ_AT,
        schema_prefix="abyss_machine",
        version="test",
    )
    unknown = nervous_source_adapters.source_set_from_ports(
        "missing",
        False,
        reason=None,
        source_lookup=lambda source_id: None,
        state_reader=lambda: (_ for _ in ()).throw(AssertionError("state must not be read")),
        state_writer=lambda state, updated_by: (_ for _ in ()).throw(AssertionError("state must not be written")),
        audit_writer=lambda event: (_ for _ in ()).throw(AssertionError("audit must not be written")),
        effective_lookup=lambda source_id: None,
        now_iso=lambda: READ_AT,
        schema_prefix="abyss_machine",
        version="test",
    )

    assert blocked["ok"] is False
    assert blocked["error"] == "source is not allowed by policy"
    assert unknown["ok"] is False
    assert unknown["error"] == "unknown source"


def test_cli_nervous_source_policy_binds_source_adapter(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_config_document_from_path(path: Path, defaults: dict[str, Any], *, generated_at: str):
        captured["config"] = {"path": path, "defaults_schema": defaults["schema"], "generated_at": generated_at}
        return {"schema": defaults["schema"], "generated_at": generated_at, "ok": True}

    def fake_write_latest(data: dict[str, Any], latest_path: Path, *, writer):
        captured["latest"] = {"data": data, "latest_path": latest_path, "writer": writer}
        return {**data, "written": True}

    def fake_state_document_from_path(path: Path, defaults: dict[str, Any], *, load_json):
        captured["state"] = {"path": path, "defaults_schema": defaults["schema"], "load_json": load_json}
        return {"schema": defaults["schema"], "overrides": {}}

    def fake_save_state_document(state: dict[str, Any], state_path: Path, **kwargs):
        captured["save"] = {"state": state, "state_path": state_path, **kwargs}
        return {"schema": "saved-state", "last_change_id": kwargs["change_id"]}

    def fake_source_set_from_ports(source_id: str, enabled: bool, **kwargs):
        captured["set"] = {"source_id": source_id, "enabled": enabled, **kwargs}
        return {"schema": "set-result", "source": source_id, "enabled": enabled}

    monkeypatch.setattr(cli, "now_iso", lambda: READ_AT)
    monkeypatch.setattr(cli, "nervous_change_id", lambda prefix: f"{prefix}-change-1")
    monkeypatch.setattr(cli.nervous_source_adapters, "config_document_from_path", fake_config_document_from_path)
    monkeypatch.setattr(cli.nervous_source_adapters, "write_latest", fake_write_latest)
    monkeypatch.setattr(cli.nervous_source_adapters, "state_document_from_path", fake_state_document_from_path)
    monkeypatch.setattr(cli.nervous_source_adapters, "save_state_document", fake_save_state_document)
    monkeypatch.setattr(cli.nervous_source_adapters, "source_set_from_ports", fake_source_set_from_ports)

    assert cli.nervous_sources(write_latest=True)["written"] is True
    assert cli.nervous_sources_state()["schema"] == "abyss_machine_nervous_sources_state_v1"
    assert cli.nervous_save_sources_state({"overrides": {}}, "source-disable:typing_saved_text")["last_change_id"] == "source-change-1"
    assert cli.nervous_source_set("typing_saved_text", False, reason="operator") == {
        "schema": "set-result",
        "source": "typing_saved_text",
        "enabled": False,
    }

    assert captured["config"]["path"] == cli.NERVOUS_SOURCES_CONFIG_PATH
    assert captured["latest"]["latest_path"] == cli.NERVOUS_SOURCES_LATEST_PATH
    assert captured["latest"]["writer"] is cli.safe_atomic_write_json
    assert captured["state"]["path"] == cli.NERVOUS_SOURCES_STATE_PATH
    assert captured["state"]["load_json"] is cli.load_json_document
    assert captured["save"]["state_path"] == cli.NERVOUS_SOURCES_STATE_PATH
    assert captured["save"]["updated_by"] == "source-disable:typing_saved_text"
    assert captured["save"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["save"]["version"] == cli.VERSION
    assert captured["save"]["writer"] is cli.safe_atomic_write_json
    assert captured["set"]["source_lookup"] is cli.nervous_source_lookup
    assert captured["set"]["state_reader"] is cli.nervous_sources_state
    assert captured["set"]["state_writer"] is cli.nervous_save_sources_state
    assert captured["set"]["effective_lookup"] is cli.nervous_source_lookup
    assert captured["set"]["now_iso"] is cli.now_iso
    assert captured["set"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["set"]["version"] == cli.VERSION
