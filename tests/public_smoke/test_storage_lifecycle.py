from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
from pathlib import Path

import pytest

from abyss_machine import storage_lifecycle_adapters as adapters
from abyss_machine import resource_runner


_ORIGINAL_PATH_HAS_LIVE_REFS = adapters._path_has_live_refs


@pytest.fixture(autouse=True)
def _fixture_workspace_reference_probe(monkeypatch) -> None:
    """Keep lifecycle fixtures independent from unrelated host /proc users."""
    monkeypatch.setattr(
        adapters,
        "_path_has_live_refs",
        lambda _path: {"active": False, "checked": True, "errors": [], "process": {}, "mount": {}},
    )


def test_managed_launcher_delete_lifecycle_is_owner_released_and_receipted(tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture-owner", workspace=workspace, unit="fixture.service")
    assert opened["ok"] is True
    assert opened["record"]["launcher_created"] is True
    (workspace / "result.txt").write_text("derived\n", encoding="utf-8")
    Path(opened["record"]["callback_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(opened["record"]["callback_path"]).write_text(
        json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}, "owner_evidence_refs": ["result:exported"]}),
        encoding="utf-8",
    )

    sealed = adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])
    assert sealed["ok"] is True
    released = adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)
    assert released["released"] is True
    reaped = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))

    assert reaped["summary"]["applied"] == 1
    assert reaped["summary"]["reclaimed_bytes"] > 0
    assert not workspace.exists()
    assert len(list((root / "receipts").glob("*.json"))) == 1
    second = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2))
    assert second["summary"]["applied"] == 0


def test_existing_directory_cannot_become_automatic_delete_authority(tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "existing"
    workspace.mkdir()
    (workspace / "unique.txt").write_text("keep", encoding="utf-8")
    opened = adapters.register_workspace(root, owner="fixture-owner", workspace=workspace, unit=None)
    assert opened["record"]["launcher_created"] is False
    Path(opened["record"]["callback_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(opened["record"]["callback_path"]).write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"] is True
    released = adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)
    assert released["ok"] is False
    assert "workspace_not_created_by_managed_launcher" in released["errors"]
    assert workspace.exists()


def test_registered_lease_renewal_is_locked_and_capability_bound(tmp_path: Path) -> None:
    root = tmp_path / "state"
    opened = adapters.register_workspace(
        root,
        owner="fixture-owner",
        workspace=tmp_path / "work" / "renew",
        unit=None,
        now_time=dt.datetime(2026, 9, 4, tzinfo=dt.timezone.utc),
    )
    workspace_id = opened["record"]["workspace_id"]
    original = adapters.read_json(adapters.record_path(root, workspace_id))
    denied = adapters.renew_registered_workspace(
        root,
        workspace_id=workspace_id,
        lease_token="wrong-capability",
        lease_seconds=600,
        now_time=dt.datetime(2026, 9, 4, 0, 1, tzinfo=dt.timezone.utc),
    )
    unchanged = adapters.read_json(adapters.record_path(root, workspace_id))
    assert denied["ok"] is False
    assert "lease_capability_mismatch" in denied["errors"]
    assert unchanged == original

    renewed = adapters.renew_registered_workspace(
        root,
        workspace_id=workspace_id,
        lease_token=opened["lease_token"],
        lease_seconds=600,
        now_time=dt.datetime(2026, 9, 4, 0, 1, tzinfo=dt.timezone.utc),
    )
    assert renewed["ok"] is True
    assert renewed["record"]["lease"]["generation"] == 2


def test_keep_and_unknown_never_release(tmp_path: Path) -> None:
    for decision in ("KEEP", "UNKNOWN"):
        root = tmp_path / decision
        opened = adapters.register_workspace(root, owner="fixture", workspace=tmp_path / "work" / decision, unit=None)
        assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"] is True
        callback = Path(opened["record"]["callback_path"])
        callback.parent.mkdir(parents=True, exist_ok=True)
        callback.write_text(json.dumps({"decision": decision, "plan": {}}), encoding="utf-8")
        consumed = adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)
        assert consumed["released"] is False
        assert consumed["record"]["state"] == "sealed"


def test_resource_runner_finalizes_lifecycle_without_exposing_capability(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        resource_runner.resource_adapters,
        "execute_systemd_launch",
        lambda **_kwargs: {
            "elapsed_sec": 1.0,
            "execution": {"ok": True, "returncode": 0, "systemd": {}},
            "lease_released": True,
            "demand_observation": None,
        },
    )
    captured: dict[str, object] = {}

    def finalize(root: Path, lifecycle: dict, *, grace_seconds: int) -> dict:
        captured.update({"root": root, "lifecycle": lifecycle, "grace": grace_seconds})
        return {"ok": True, "workspace_id": lifecycle["workspace_id"], "sealed": True, "released": False}

    monkeypatch.setattr(resource_runner.storage_lifecycle_adapters, "finalize_managed_workspace", finalize)
    handoff = {
        "document": {
            "blocked_reasons": [],
            "denied_reasons": [],
            "planning": {"elapsed_sec": 0.1},
            "startup_admission": {},
            "policy": {},
            "request": {},
        },
        "execution": {
            "systemd_command": ["true"],
            "launch_attestation": {
                "required": False,
                "deadline_monotonic": None,
            },
            "request_started_monotonic": 0,
            "unit_type": "service",
            "timeout_sec": 1,
            "reservation_root": str(tmp_path / "reservations"),
            "demand_profile_path": str(tmp_path / "profiles"),
            "kind": "agent",
            "workspace_lifecycle": {
                "workspace_id": "workspace-fixture",
                "lease_token": "secret-capability",
                "root": str(tmp_path / "lifecycle"),
                "grace_seconds": 30,
                "path": str(tmp_path / "workspace"),
                "owner": "fixture-owner",
            },
        },
        "write_latest": False,
    }
    result = resource_runner.finish_document(handoff)
    assert captured["grace"] == 30
    assert result["execution"]["managed_workspace"]["sealed"] is True
    assert "lease_token" not in result["request"]["managed_workspace"]
    assert "root" not in result["request"]["managed_workspace"]


def test_reaper_recovers_expired_inactive_open_workspace_only_to_unknown(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    opened = adapters.register_workspace(
        root,
        owner="fixture",
        workspace=tmp_path / "work" / "abandoned",
        unit="fixture.service",
        lease_seconds=1,
    )
    (Path(opened["record"]["path"]) / "partial").write_text("not owner-approved", encoding="utf-8")
    monkeypatch.setattr(
        adapters.resource_adapters,
        "systemd_user_unit_state",
        lambda _unit: {"exists": False, "active": False, "state": "inactive"},
    )
    monkeypatch.setattr(adapters, "_path_has_live_refs", lambda _path: {"active": False, "checked": True})
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=1)
    result = adapters.reap(root, now_time=future)
    record = adapters.read_json(adapters.record_path(root, opened["record"]["workspace_id"]))
    assert result["summary"]["recovered"] == 1
    assert record["state"] == "sealed"
    assert record["disposition"]["decision"] == "UNKNOWN"
    assert Path(record["path"]).exists()


@pytest.mark.parametrize("self_link", [False, True])
def test_reaper_resumes_authorized_atomic_detach_after_crash(tmp_path: Path, self_link: bool) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    if self_link:
        (workspace / "z-dir").mkdir()
        (workspace / "a-link").symlink_to(workspace / "z-dir", target_is_directory=True)
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    tombstone = workspace.parent / f".abyss-released-{opened['record']['workspace_id']}"
    workspace.rename(tombstone)
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert result["summary"]["applied"] == 1
    assert not tombstone.exists()


@pytest.mark.parametrize("relative", [False, True])
def test_detached_self_link_preserves_old_seal_but_rejects_changed_entry(tmp_path: Path, relative: bool) -> None:
    workspace = tmp_path / "before"
    workspace.mkdir()
    (workspace / "z-dir").mkdir()
    (workspace / "m-file").write_text("payload", encoding="utf-8")
    target = Path("../before/z-dir") if relative else workspace / "z-dir"
    (workspace / "a-link").symlink_to(target, target_is_directory=True)
    before = adapters.workspace_identity_fingerprint(workspace)
    tombstone = tmp_path / "after"
    workspace.rename(tombstone)
    legacy_after = adapters.workspace_identity_fingerprint(tombstone)
    restored_order = adapters.workspace_identity_fingerprint(tombstone, original_root=workspace)
    assert before["complete"] and restored_order["complete"]
    assert legacy_after["digest"] != before["digest"]
    assert restored_order["digest"] == before["digest"]
    (tombstone / "m-file").write_text("changed", encoding="utf-8")
    assert adapters.workspace_identity_fingerprint(tombstone, original_root=workspace)["digest"] != before["digest"]


def test_reaper_scans_past_blocked_candidate_with_bounded_attempts(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    records: list[dict] = []
    for name in ("blocked", "eligible", "scan-limited"):
        workspace = tmp_path / "work" / name
        opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
        (workspace / "derived").write_text(name, encoding="utf-8")
        assert adapters.seal_registered_workspace(
            root,
            workspace_id=opened["record"]["workspace_id"],
            lease_token=opened["lease_token"],
        )["ok"]
        callback = Path(opened["record"]["callback_path"])
        callback.parent.mkdir(parents=True, exist_ok=True)
        callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
        assert adapters.consume_owner_callback(
            root,
            workspace_id=opened["record"]["workspace_id"],
            grace_seconds=0,
        )["released"]
        record = adapters.read_json(adapters.record_path(root, opened["record"]["workspace_id"]))
        assert record is not None
        records.append(record)

    blocked, eligible, scan_limited = records
    (Path(blocked["path"]) / "late-result").write_text("changed after seal", encoding="utf-8")
    monkeypatch.setattr(adapters, "load_records", lambda _root: records)

    result = adapters.reap(
        root,
        limit=1,
        scan_limit=2,
        now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1),
    )

    summary = result["summary"]
    assert summary["examined"] == 2
    assert summary["scan_limit"] == 2
    assert summary["mutations"] == 1
    assert summary["applied"] == 1
    assert summary["blocked"] == 1
    assert summary["recovered"] == 0
    assert summary["reclaimed_bytes"] > 0
    assert result["blocked"][0]["workspace_id"] == blocked["workspace_id"]
    assert "fingerprint_drift" in result["blocked"][0]["reasons"]
    assert result["applied"][0]["workspace_id"] == eligible["workspace_id"]
    assert not Path(eligible["path"]).exists()
    assert Path(blocked["path"]).exists()
    assert Path(scan_limited["path"]).exists()
    assert "execution" not in (adapters.read_json(adapters.record_path(root, scan_limited["workspace_id"])) or {})


def test_reaper_cursor_rotates_blocked_prefix_across_invocations(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    records: list[dict] = []
    for name in ("blocked-one", "blocked-two", "eligible-tail"):
        workspace = tmp_path / "work" / name
        opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
        (workspace / "derived").write_text(name, encoding="utf-8")
        assert adapters.seal_registered_workspace(
            root,
            workspace_id=opened["record"]["workspace_id"],
            lease_token=opened["lease_token"],
        )["ok"]
        callback = Path(opened["record"]["callback_path"])
        callback.parent.mkdir(parents=True, exist_ok=True)
        callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
        assert adapters.consume_owner_callback(
            root,
            workspace_id=opened["record"]["workspace_id"],
            grace_seconds=0,
        )["released"]
        record = adapters.read_json(adapters.record_path(root, opened["record"]["workspace_id"]))
        assert record is not None
        records.append(record)

    blocked_one, blocked_two, eligible = records
    for blocked in (blocked_one, blocked_two):
        (Path(blocked["path"]) / "late-result").write_text("changed after seal", encoding="utf-8")
    monkeypatch.setattr(adapters, "load_records", lambda _root: records)
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1)

    first = adapters.reap(root, limit=1, scan_limit=2, now_time=future)

    assert first["summary"]["scanned"] == 2
    assert first["summary"]["examined"] == 2
    assert first["summary"]["mutations"] == 0
    assert {item["workspace_id"] for item in first["blocked"]} == {
        blocked_one["workspace_id"],
        blocked_two["workspace_id"],
    }
    assert first["cursor"]["before"] is None
    assert first["cursor"]["after"] == blocked_two["workspace_id"]
    assert first["cursor"]["committed"] is True
    assert first["cursor"]["reset_reason"] == "state_missing"

    second = adapters.reap(root, limit=1, scan_limit=2, now_time=future + dt.timedelta(seconds=1))

    assert second["summary"]["scanned"] == 1
    assert second["summary"]["examined"] == 1
    assert second["summary"]["mutations"] == 1
    assert second["applied"][0]["workspace_id"] == eligible["workspace_id"]
    assert second["cursor"]["before"] == blocked_two["workspace_id"]
    assert second["cursor"]["after"] == eligible["workspace_id"]
    assert adapters.read_json(adapters.reaper_state_path(root))["cursor"] == eligible["workspace_id"]


def test_reaper_cursor_resets_when_saved_record_id_is_missing(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    records: list[dict] = []
    for name in ("blocked", "eligible"):
        workspace = tmp_path / "work" / name
        opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
        (workspace / "derived").write_text(name, encoding="utf-8")
        assert adapters.seal_registered_workspace(
            root,
            workspace_id=opened["record"]["workspace_id"],
            lease_token=opened["lease_token"],
        )["ok"]
        callback = Path(opened["record"]["callback_path"])
        callback.parent.mkdir(parents=True, exist_ok=True)
        callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
        assert adapters.consume_owner_callback(
            root,
            workspace_id=opened["record"]["workspace_id"],
            grace_seconds=0,
        )["released"]
        record = adapters.read_json(adapters.record_path(root, opened["record"]["workspace_id"]))
        assert record is not None
        records.append(record)

    blocked, eligible = records
    (Path(blocked["path"]) / "late-result").write_text("changed after seal", encoding="utf-8")
    adapters.atomic_write_json(
        adapters.reaper_state_path(root),
        {
            "schema": adapters.REAPER_STATE_SCHEMA,
            "cursor": "deleted-workspace-id",
            "revision": 4,
        },
    )
    monkeypatch.setattr(adapters, "load_records", lambda _root: records)

    result = adapters.reap(
        root,
        limit=1,
        scan_limit=2,
        now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1),
    )

    assert result["cursor"]["reset_reason"] == "cursor_missing"
    assert result["cursor"]["committed"] is True
    assert result["summary"]["scanned"] == 2
    assert result["applied"][0]["workspace_id"] == eligible["workspace_id"]


def test_reaper_reports_existing_state_without_cursor_field(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    adapters.atomic_write_json(
        adapters.reaper_state_path(root),
        {"schema": adapters.REAPER_STATE_SCHEMA, "revision": 4},
    )
    monkeypatch.setattr(adapters, "load_records", lambda _root: [])

    result = adapters.reap(root, limit=1, scan_limit=2)

    assert result["cursor"]["reset_reason"] == "state_cursor_missing"
    assert result["cursor"]["committed"] is False
    assert result["cursor"]["reason"] == "no_records_scanned"
    assert adapters.read_json(adapters.reaper_state_path(root)) == {
        "schema": adapters.REAPER_STATE_SCHEMA,
        "revision": 4,
    }


def test_reaper_resumes_from_detach_journal_after_cleanup_failure(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    assert adapters.seal_registered_workspace(
        root,
        workspace_id=opened["record"]["workspace_id"],
        lease_token=opened["lease_token"],
    )["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(
        json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}),
        encoding="utf-8",
    )
    assert adapters.consume_owner_callback(
        root,
        workspace_id=opened["record"]["workspace_id"],
        grace_seconds=0,
    )["released"]

    original_rmtree = adapters.shutil.rmtree
    monkeypatch.setattr(adapters.shutil, "rmtree", lambda _path: (_ for _ in ()).throw(OSError("fixture interruption")))
    first = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert first["summary"]["blocked"] == 1
    journal = adapters.read_json(adapters.execution_journal_path(root, opened["record"]["workspace_id"]))
    assert journal["phase"] == "detached"
    assert not workspace.exists()

    monkeypatch.setattr(adapters.shutil, "rmtree", original_rmtree)
    second = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2))
    assert second["summary"]["applied"] == 1
    assert adapters.read_json(adapters.execution_journal_path(root, opened["record"]["workspace_id"]))["phase"] == "applied"


def test_reaper_blocks_when_reference_probe_is_unchecked(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    monkeypatch.setattr(
        adapters,
        "_path_has_live_refs",
        lambda _path: {"active": False, "checked": False, "errors": [{"probe": "process"}]},
    )

    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))

    assert result["summary"]["blocked"] == 1
    assert "reference_probe_unavailable" in result["blocked"][0]["reasons"]
    assert workspace.exists()
    assert not (workspace.parent / f".abyss-released-{opened['record']['workspace_id']}").exists()


def test_reference_adapter_errors_are_not_authorized_as_clear(monkeypatch, tmp_path: Path) -> None:
    workspace = tmp_path / "work" / "job"
    workspace.mkdir(parents=True)
    monkeypatch.setattr(
        adapters.storage_process_probe,
        "owner_process_references",
        lambda _paths: {str(workspace): {"checked": False, "active": False, "errors": ["proc unavailable"]}},
    )
    monkeypatch.setattr(
        adapters.storage_candidate_adapters,
        "mount_references",
        lambda _path: {"checked": False, "active": False, "errors": ["mountinfo unavailable"]},
    )

    refs = _ORIGINAL_PATH_HAS_LIVE_REFS(workspace)

    assert refs["active"] is False
    assert refs["checked"] is False
    assert {item["probe"] for item in refs["errors"]} == {"process", "mount"}


def test_archive_resume_with_missing_target_does_not_close_journal(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "archive-job"
    archive = tmp_path / "vault" / "archive-job"
    archive.parent.mkdir()
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: f"42 1 0:99 / {archive.parent} rw - btrfs /dev/fixture rw\n")
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "result").write_text("preserve", encoding="utf-8")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "ARCHIVE", "plan": {"kind": "archive_workspace", "target": str(archive), "required_mount": str(archive.parent)}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]

    original_rmtree = adapters.shutil.rmtree
    monkeypatch.setattr(adapters.shutil, "rmtree", lambda _path: (_ for _ in ()).throw(OSError("fixture interruption")))
    first = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert first["summary"]["blocked"] == 1
    tombstone = workspace.parent / f".abyss-released-{opened['record']['workspace_id']}"
    assert tombstone.exists()
    original_rmtree(tombstone)
    original_rmtree(archive)
    monkeypatch.setattr(adapters.shutil, "rmtree", original_rmtree)

    second = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2))

    assert second["summary"]["blocked"] == 1
    assert "archive_target_missing" in second["blocked"][0]["reasons"]
    journal = adapters.read_json(adapters.execution_journal_path(root, opened["record"]["workspace_id"]))
    assert journal["phase"] == "detached"


def test_delete_resume_blocks_tombstone_identity_drift(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]

    original_rmtree = adapters.shutil.rmtree
    monkeypatch.setattr(adapters.shutil, "rmtree", lambda _path: (_ for _ in ()).throw(OSError("fixture interruption")))
    first = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert first["summary"]["blocked"] == 1
    tombstone = workspace.parent / f".abyss-released-{opened['record']['workspace_id']}"
    assert tombstone.exists()
    (tombstone / "late-result").write_text("changed", encoding="utf-8")
    monkeypatch.setattr(adapters.shutil, "rmtree", original_rmtree)

    second = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2))

    assert second["summary"]["blocked"] == 1
    assert "fingerprint_drift_before_detach" in second["blocked"][0]["reasons"]
    assert (tombstone / "late-result").exists()


def test_fingerprint_blocks_nested_mountpoint_even_when_device_matches(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "work" / "job"
    nested = workspace / "mounted"
    nested.mkdir(parents=True)
    (nested / "foreign").write_text("do not traverse", encoding="utf-8")
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: f"42 1 0:99 / {nested} rw - btrfs /dev/fixture rw\n")

    identity = adapters.workspace_identity_fingerprint(workspace)
    content = adapters.workspace_content_fingerprint(workspace)

    assert identity["complete"] is False
    assert content["complete"] is False
    assert any(error["error"] == "nested_mount_boundary" for error in identity["errors"])
    assert any(error["error"] == "nested_mount_boundary" for error in content["errors"])


def test_fingerprint_fails_closed_when_mountinfo_cannot_be_read(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "work" / "job"
    workspace.mkdir(parents=True)
    (workspace / "result").write_text("payload", encoding="utf-8")
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: (_ for _ in ()).throw(OSError("fixture mountinfo failure")))

    identity = adapters.workspace_identity_fingerprint(workspace)
    content = adapters.workspace_content_fingerprint(workspace)

    assert identity["complete"] is False
    assert content["complete"] is False
    assert "mountinfo_unavailable" in identity["errors"][0]["error"]
    assert "mountinfo_unavailable" in content["errors"][0]["error"]


def test_final_reference_probe_is_repeated_before_detach(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    calls = 0

    def refs(_path: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"active": False, "checked": calls < 2, "errors": []}

    monkeypatch.setattr(adapters, "_path_has_live_refs", refs)
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))

    assert result["summary"]["blocked"] == 1
    assert "reference_probe_unavailable_before_detach" in result["blocked"][0]["reasons"]
    assert calls == 2
    assert workspace.exists()


@pytest.mark.parametrize("self_link", [False, True])
def test_archive_verifies_copy_before_local_removal(tmp_path: Path, monkeypatch, self_link: bool) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "archive-job"
    archive = tmp_path / "vault" / "archive-job"
    archive.parent.mkdir()
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: f"42 1 0:99 / {archive.parent} rw - btrfs /dev/fixture rw\n")
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "result").write_text("preserve", encoding="utf-8")
    if self_link:
        (workspace / "z-dir").mkdir()
        (workspace / "a-link").symlink_to(workspace / "z-dir", target_is_directory=True)
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "ARCHIVE", "plan": {"kind": "archive_workspace", "target": str(archive), "required_mount": str(archive.parent)}}), encoding="utf-8")
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert result["summary"]["applied"] == 1
    assert not workspace.exists()
    assert (archive / "result").read_text(encoding="utf-8") == "preserve"
    assert adapters.workspace_content_fingerprint(archive, original_root=workspace)["digest"] == result["applied"][0]["receipt"]["archive_content_digest"]


def test_archive_absent_mount_preserves_source_and_creates_no_destination(tmp_path: Path, monkeypatch) -> None:
    root, workspace, vault = tmp_path / "state", tmp_path / "work/job", tmp_path / "vault"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "result").write_text("unique")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "ARCHIVE", "plan": {"kind": "archive_workspace", "target": str(vault / "job"), "required_mount": str(vault)}}))
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: "1 0 0:1 / / rw - ext4 /dev/root rw\n")
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert result["summary"]["blocked"] == 1
    assert (workspace / "result").read_text() == "unique"
    assert not vault.exists()


def test_archive_mount_disappears_after_copy_keeps_local_source(tmp_path: Path, monkeypatch) -> None:
    root, workspace, vault = tmp_path / "state", tmp_path / "work/job", tmp_path / "vault"
    vault.mkdir()
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "result").write_text("unique")
    assert adapters.seal_registered_workspace(root, workspace_id=opened["record"]["workspace_id"], lease_token=opened["lease_token"])["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(json.dumps({"decision": "ARCHIVE", "plan": {"kind": "archive_workspace", "target": str(vault / "job"), "required_mount": str(vault)}}))
    assert adapters.consume_owner_callback(root, workspace_id=opened["record"]["workspace_id"], grace_seconds=0)["released"]
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: f"42 1 0:99 / {vault} rw - btrfs /dev/fixture rw\n")
    original = adapters.shutil.copytree
    def copy_and_disconnect(*args, **kwargs):
        value = original(*args, **kwargs)
        monkeypatch.setattr(adapters, "_read_mountinfo", lambda: "")
        return value
    monkeypatch.setattr(adapters.shutil, "copytree", copy_and_disconnect)
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert result["summary"]["blocked"] == 1
    assert workspace.is_dir()
    assert (workspace / "result").read_text() == "unique"


def test_archive_binding_refuses_symlink_escape_and_root_mount(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "escape").symlink_to(tmp_path)
    monkeypatch.setattr(adapters, "_read_mountinfo", lambda: f"42 1 0:99 / {vault} rw - btrfs /dev/fixture rw\n")
    assert not adapters.archive_mount_binding(vault / "escape/job", vault)["ok"]
    assert not adapters.archive_mount_binding(tmp_path / "outside", vault)["ok"]
    assert not adapters.archive_mount_binding(tmp_path, Path("/"))["ok"]


def test_archive_vault_binding_authenticates_policy_mapper_and_label(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "archive" / "result.json"
    monkeypatch.setattr(
        adapters,
        "_read_mountinfo",
        lambda: f"42 1 0:99 / {vault} rw - btrfs /dev/mapper/fixture rw\n",
    )

    result = adapters.archive_vault_mount_binding(
        target,
        vault,
        expected_mapper="fixture",
        expected_label="FIXTURE",
        device_identity_reader=lambda device: {
            "ok": True,
            "mapper": device,
            "label": "FIXTURE",
            "uuid": "runtime-fixture-uuid",
        },
    )

    assert result["ok"] is True
    assert result["identity"]["mapper"] == "/dev/mapper/fixture"
    assert result["identity"]["label"] == "FIXTURE"
    assert result["identity"]["uuid"] == "runtime-fixture-uuid"
    assert result["identity"]["fs_root"] == "/"

    wrong_label = adapters.archive_vault_mount_binding(
        target,
        vault,
        expected_mapper="fixture",
        expected_label="OTHER",
        device_identity_reader=lambda device: {
            "ok": True,
            "mapper": device,
            "label": "FIXTURE",
            "uuid": "runtime-fixture-uuid",
        },
    )
    assert wrong_label["ok"] is False
    assert "vault_device_label_mismatch" in wrong_label["reasons"]

    wrong_mapper = adapters.archive_vault_mount_binding(
        target,
        vault,
        expected_mapper="other",
        expected_label="FIXTURE",
        device_identity_reader=lambda device: {"ok": True, "mapper": device, "label": "FIXTURE", "uuid": "u"},
    )
    assert wrong_mapper["ok"] is False
    assert "vault_mapper_source_mismatch" in wrong_mapper["reasons"]


def test_archive_vault_binding_requires_runtime_uuid_and_source_path_is_symlink_free(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    target = vault / "archive" / "result.json"
    monkeypatch.setattr(
        adapters,
        "_read_mountinfo",
        lambda: f"42 1 0:99 / {vault} rw - btrfs /dev/mapper/fixture rw\n",
    )
    missing_uuid = adapters.archive_vault_mount_binding(
        target,
        vault,
        expected_mapper="fixture",
        expected_label="FIXTURE",
        device_identity_reader=lambda device: {"ok": True, "mapper": device, "label": "FIXTURE"},
    )
    assert missing_uuid["ok"] is False
    assert "vault_runtime_uuid_missing" in missing_uuid["reasons"]

    source = tmp_path / "source"
    source.mkdir()
    (source / "link").symlink_to(tmp_path / "outside")
    assert adapters.archive_path_has_symlink(source / "link" / "result.json") is True


def test_archive_vault_binding_rejects_nested_mount_even_when_device_matches(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    nested = vault / "nested"
    vault.mkdir()
    nested.mkdir()
    target = nested / "result.json"
    monkeypatch.setattr(
        adapters,
        "_read_mountinfo",
        lambda: (
            f"42 1 0:99 / {vault} rw - btrfs /dev/mapper/fixture rw\n"
            f"43 42 0:99 /sub {nested} rw - btrfs /dev/mapper/fixture rw\n"
        ),
    )
    result = adapters.archive_vault_mount_binding(
        target,
        vault,
        expected_mapper="fixture",
        expected_label="FIXTURE",
        device_identity_reader=lambda device: {
            "ok": True,
            "mapper": device,
            "label": "FIXTURE",
            "uuid": "runtime-fixture-uuid",
        },
    )
    assert result["ok"] is False
    assert "archive_nested_mount_mismatch" in result["reasons"]


def test_runtime_vault_device_identity_reader_is_bounded_and_requires_one_uuid_record() -> None:
    commands: list[list[str]] = []

    def run(command: list[str], timeout: float) -> dict[str, object]:
        commands.append(command)
        assert timeout == 2.0
        return {
            "ok": True,
            "stdout": 'UUID="runtime-uuid" LABEL="FIXTURE"\n',
        }

    result = adapters.read_vault_device_identity(
        "/dev/mapper/fixture",
        command_runner=run,
    )
    assert result == {
        "ok": True,
        "uuid": "runtime-uuid",
        "label": "FIXTURE",
        "mapper": "/dev/mapper/fixture",
    }
    assert commands == [[
        "lsblk", "--noheadings", "--pairs", "--nodeps", "--output", "UUID,LABEL", "/dev/mapper/fixture",
    ]]
    ambiguous = adapters.read_vault_device_identity(
        "/dev/mapper/fixture",
        command_runner=lambda command, timeout: {
            "ok": True,
            "stdout": 'UUID="one" LABEL="FIXTURE"\nUUID="two" LABEL="FIXTURE"\n',
        },
    )
    assert ambiguous["ok"] is False
    assert ambiguous["reasons"] == ["vault_device_identity_ambiguous"]


def test_bounded_vault_file_copy_uses_anchor_fd_hash_and_preserves_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source = tmp_path / "source" / "result.json"
    vault.mkdir()
    source.parent.mkdir()
    source.write_bytes(b"bounded archive payload\n")
    destination = vault / "nested" / "result.json"
    mount_stat = vault.stat()
    binding = {
        "required_mount": str(vault),
        "mount_id": "42",
        "device": "0:99",
        "fs_root": "/",
        "filesystem": "btrfs",
        "source": "/dev/mapper/fixture",
        "st_dev": int(mount_stat.st_dev),
        "st_ino": int(mount_stat.st_ino),
        "uuid": "runtime-fixture-uuid",
        "mapper": "/dev/mapper/fixture",
        "label": "FIXTURE",
    }
    pair = {
        "ok": True,
        "source": str(source),
        "destination": str(destination),
        "relative_suffix": "result.json",
        "route_id": "fixture-vault-route",
        "owner": "fixture-owner",
    }
    reservation = {
        "active": True,
        "kind": "vault-archive",
        "owner": "fixture-owner",
        "target": str(destination),
        "reservation_id": "fixture-copy",
        "requested_bytes": source.stat().st_size,
        "route_metadata": {
            "route_id": "fixture-vault-route",
            "owner": "fixture-owner",
            "required_mount": str(vault),
            "archive_binding": binding,
        },
    }
    binding_checks: list[str] = []

    def reader(_target: Path, _mount: Path, **_kwargs: object) -> dict[str, object]:
        binding_checks.append("checked")
        return {"ok": True, "identity": binding}

    result = adapters.copy_vault_archive_file(
        source,
        destination,
        owner="fixture-owner",
        pair=pair,
        reservation_record=reservation,
        expected_binding=binding,
        required_mount=vault,
        expected_mapper="fixture",
        expected_label="FIXTURE",
        mount_binding_reader=reader,
    )

    assert result["ok"] is True
    assert result["hash_verified"] is True
    assert result["restore_proof"]["source_was_not_removed"] is True
    assert result["destination_anchor"]["st_dev"] == binding["st_dev"]
    assert len(binding_checks) == 4
    assert destination.read_bytes() == b"bounded archive payload\n"
    assert source.read_bytes() == b"bounded archive payload\n"
    assert not list(destination.parent.glob(".*.partial"))

    second = adapters.copy_vault_archive_file(
        source,
        destination,
        owner="fixture-owner",
        pair=pair,
        reservation_record={**reservation, "reservation_id": "fixture-copy-retry"},
        expected_binding=binding,
        required_mount=vault,
        expected_mapper="fixture",
        expected_label="FIXTURE",
        mount_binding_reader=reader,
    )
    assert second["ok"] is False
    assert second["reasons"] == ["archive_target_exists"]


def test_reaper_does_not_hold_registry_lock_during_disposition(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "state"
    workspace = tmp_path / "work" / "job"
    opened = adapters.register_workspace(root, owner="fixture", workspace=workspace, unit=None)
    (workspace / "derived").write_text("payload", encoding="utf-8")
    assert adapters.seal_registered_workspace(
        root,
        workspace_id=opened["record"]["workspace_id"],
        lease_token=opened["lease_token"],
    )["ok"]
    callback = Path(opened["record"]["callback_path"])
    callback.parent.mkdir(parents=True, exist_ok=True)
    callback.write_text(
        json.dumps({"decision": "DELETE", "plan": {"kind": "delete_workspace"}}),
        encoding="utf-8",
    )
    assert adapters.consume_owner_callback(
        root,
        workspace_id=opened["record"]["workspace_id"],
        grace_seconds=0,
    )["released"]

    def execute(_root: Path, _record: dict, **_kwargs) -> dict:
        fd = os.open(root / ".lock", os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        return {"ok": False, "workspace_id": _record["workspace_id"], "decision": "blocked", "reasons": ["fixture"]}

    monkeypatch.setattr(adapters, "execute_released_workspace", execute)
    result = adapters.reap(root, now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1))
    assert result["summary"]["examined"] == 1
    assert result["summary"]["blocked"] == 1
