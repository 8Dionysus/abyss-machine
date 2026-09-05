import datetime as dt
import json
from pathlib import Path
import stat
import subprocess

import pytest

from abyss_machine import storage_lifecycle_adapters
from abyss_machine.codex_storage_lifecycle import Lifecycle, main


@pytest.fixture
def lifecycle(tmp_path):
    return Lifecycle(state_root=tmp_path / "state", scratch_root=tmp_path / "scratch",
                     candidates_root=tmp_path / "candidates", lifecycle_root=tmp_path / "lifecycle",
                     required_mount=None)


def event(name="SessionStart", **extra):
    return {"session_id": "native-task-123", "hook_event_name": name, **extra}


def records(lifecycle):
    return json.loads((lifecycle.state_root / "native-task-123.json").read_text())


def test_native_hook_registers_candidate_and_renewable_claim_without_payload(lifecycle):
    result = lifecycle.observe(event(prompt="PRIVATE_PROMPT", transcript_path="PRIVATE_TRANSCRIPT"))
    assert "additionalContext" in result["hookSpecificOutput"]
    record = records(lifecycle)
    candidate = json.loads((lifecycle.candidates_root / "manifests" / (record["candidate_id"] + ".json")).read_text())
    assert candidate["owner"] == "codex-native-scratch"
    assert candidate["unique_data_clear"] is False
    assert "PRIVATE" not in json.dumps(record)
    claim = json.loads((lifecycle.candidates_root / "claims/codex-native-task-123.json").read_text())
    assert claim["candidate_id"] == candidate["candidate_id"]
    metadata = lifecycle.state_root / "native-task-123.json"
    assert stat.S_IMODE(metadata.stat().st_mode) == 0o600
    managed = json.loads(
        storage_lifecycle_adapters.record_path(
            lifecycle.lifecycle_root,
            record["workspace_lifecycle"]["workspace_id"],
        ).read_text()
    )
    assert managed["launcher_created"] is True
    assert managed["state"] == "open"
    assert managed["path"] == record["path"]


def test_active_hook_renews_existing_managed_lease(lifecycle):
    now = dt.datetime(2026, 9, 4, tzinfo=dt.timezone.utc)
    lifecycle.observe(event(), now=now)
    record = records(lifecycle)
    workspace_id = record["workspace_lifecycle"]["workspace_id"]
    first = storage_lifecycle_adapters.read_json(
        storage_lifecycle_adapters.record_path(lifecycle.lifecycle_root, workspace_id)
    )
    lifecycle.observe(event("UserPromptSubmit"), now=now + dt.timedelta(minutes=5))
    second = storage_lifecycle_adapters.read_json(
        storage_lifecycle_adapters.record_path(lifecycle.lifecycle_root, workspace_id)
    )
    assert first is not None and second is not None
    assert second["state"] == "open"
    assert second["lease"]["generation"] == first["lease"]["generation"] + 1
    assert dt.datetime.fromisoformat(second["lease"]["expires_at"]) > dt.datetime.fromisoformat(
        first["lease"]["expires_at"]
    )


@pytest.mark.parametrize("name", ["Stop", "SessionEnd", "SubagentStop", "Interrupt"])
def test_stop_or_idle_never_closes_or_clears_task(lifecycle, name):
    lifecycle.observe(event())
    protected = lifecycle.scratch_root / "native-task-123/source.txt"
    protected.write_text("unique result")
    assert lifecycle.observe(event(name)) == {}
    assert records(lifecycle)["state"] == "idle_observed"
    assert records(lifecycle)["automatic_deletion"] is False
    assert protected.read_text() == "unique result"


def test_shell_rewrite_preserves_arguments_and_explicit_assignment(lifecycle):
    command = "python3 -c 'import os; print(os.environ[\"TMPDIR\"])'"
    result = lifecycle.observe(event("PreToolUse", tool_name="Bash", tool_input={"command": command, "timeout_ms": 1200}), route_temp=True)
    updated = result["hookSpecificOutput"]["updatedInput"]
    assert updated["timeout_ms"] == 1200
    assert updated["command"].endswith(command)
    run = subprocess.run(["/bin/sh", "-c", updated["command"]], capture_output=True, text=True, check=True)
    assert run.stdout.strip() == str(lifecycle.scratch_root / "native-task-123")
    result = lifecycle.observe(event("PreToolUse", tool_name="Bash", tool_input={"command": "TMPDIR=/explicit " + command}), route_temp=True)
    run = subprocess.run(["/bin/sh", "-c", result["hookSpecificOutput"]["updatedInput"]["command"]], capture_output=True, text=True, check=True)
    assert run.stdout.strip() == "/explicit"


@pytest.mark.parametrize("identifier", ["../escape", "/absolute", "name;touch hacked", "", None])
def test_invalid_identity_does_not_create_state(lifecycle, identifier):
    with pytest.raises(ValueError):
        lifecycle.observe({"session_id": identifier, "hook_event_name": "SessionStart"})
    assert not lifecycle.state_root.exists()


def test_absent_mount_never_creates_scratch_or_state(tmp_path):
    lifecycle = Lifecycle(state_root=tmp_path / "state", scratch_root=tmp_path / "srv/scratch",
                          candidates_root=tmp_path / "candidates", required_mount=tmp_path / "srv")
    with pytest.raises(ValueError, match="mount is absent"):
        lifecycle.observe(event())
    assert not (tmp_path / "srv").exists()
    assert not lifecycle.state_root.exists()


def test_existing_unowned_directory_and_symlink_are_not_adopted(lifecycle, tmp_path):
    path = lifecycle.scratch_root / "native-task-123"
    path.mkdir(parents=True)
    with pytest.raises(ValueError, match="unowned"):
        lifecycle.observe(event())
    path.rmdir()
    path.symlink_to(tmp_path)
    with pytest.raises(ValueError):
        lifecycle.observe(event())


def test_prompt_after_close_creates_new_generation_and_preserves_old_scratch(lifecycle, tmp_path):
    lifecycle.observe(event())
    old_path = lifecycle.scratch_root / "native-task-123"
    (old_path / "unique.txt").write_text("preserved previous result")
    receipt = tmp_path / "result.md"
    receipt.write_text("Preserved output")
    result = lifecycle.close("native-task-123", receipt)
    assert result["state"] == "closed"
    assert len(result["closeout"]["sha256"]) == 64
    assert result["disposition"]["decision"] == "UNKNOWN"
    assert "lease_token" not in json.dumps(result)
    lifecycle.observe(event("SessionEnd"))
    assert records(lifecycle)["state"] == "closed"
    lifecycle.observe(event("UserPromptSubmit"))
    renewed = records(lifecycle)
    assert renewed["generation"] == 2
    assert renewed["path"] == str(lifecycle.scratch_root / "native-task-123-g2")
    assert renewed["workspace_lifecycle"]["workspace_id"] != result["workspace_lifecycle"]["workspace_id"]
    assert (old_path / "unique.txt").read_text() == "preserved previous result"
    assert list(Path(renewed["path"]).iterdir()) == []
    managed_id = result["workspace_lifecycle"]["workspace_id"]
    managed = storage_lifecycle_adapters.read_json(
        storage_lifecycle_adapters.record_path(lifecycle.lifecycle_root, managed_id)
    )
    assert managed is not None
    assert managed["state"] == "sealed"
    assert managed["disposition"]["decision"] == "UNKNOWN"

    second_close = lifecycle.close("native-task-123", receipt, decision="KEEP")
    assert second_close["generation"] == 2
    assert second_close["state"] == "closed"


def test_explicit_delete_uses_existing_reaper(lifecycle, tmp_path):
    lifecycle.observe(event())
    (lifecycle.scratch_root / "native-task-123" / "derived.txt").write_text("preserve then delete")
    receipt = tmp_path / "result.md"
    receipt.write_text("Preserved output")
    result = lifecycle.close(
        "native-task-123",
        receipt,
        decision="DELETE",
        owner_evidence_refs=["owner:preserved"],
        grace_seconds=0,
    )
    assert result["lifecycle_closeout"]["released"] is True
    managed_id = result["workspace_lifecycle"]["workspace_id"]
    managed = storage_lifecycle_adapters.read_json(
        storage_lifecycle_adapters.record_path(lifecycle.lifecycle_root, managed_id)
    )
    assert managed is not None
    assert managed["state"] == "released"
    assert managed["disposition"]["decision"] == "DELETE"
    reaped = storage_lifecycle_adapters.reap(
        lifecycle.lifecycle_root,
        now_time=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1),
    )
    assert reaped["summary"]["applied"] == 1
    assert not (lifecycle.scratch_root / "native-task-123").exists()
    lifecycle.observe(event("SessionStart"))
    renewed = records(lifecycle)
    assert renewed["generation"] == 2
    assert Path(renewed["path"]).is_dir()
    assert not (lifecycle.scratch_root / "native-task-123").exists()


def test_archive_requires_exact_absolute_target(lifecycle, tmp_path):
    lifecycle.observe(event())
    receipt = tmp_path / "result.md"
    receipt.write_text("Preserved output")
    with pytest.raises(ValueError, match="archive target"):
        lifecycle.close("native-task-123", receipt, decision="ARCHIVE")
    assert (lifecycle.scratch_root / "native-task-123").exists()
    managed_id = records(lifecycle)["workspace_lifecycle"]["workspace_id"]
    managed = storage_lifecycle_adapters.read_json(
        storage_lifecycle_adapters.record_path(lifecycle.lifecycle_root, managed_id)
    )
    assert managed is not None and managed["state"] == "open"


def test_show_and_close_never_print_private_lease_token(lifecycle, tmp_path, capsys):
    lifecycle.observe(event())
    raw_metadata = (lifecycle.state_root / "native-task-123.json").read_text()
    token = records(lifecycle)["workspace_lifecycle"]["lease_token"]
    assert token in raw_metadata
    assert stat.S_IMODE((lifecycle.state_root / "native-task-123.json").stat().st_mode) == 0o600

    assert main([
        "--state-root", str(lifecycle.state_root),
        "--scratch-root", str(lifecycle.scratch_root),
        "--candidates-root", str(lifecycle.candidates_root),
        "--lifecycle-root", str(lifecycle.lifecycle_root),
        "show", "--session-id", "native-task-123",
    ]) == 0
    shown = capsys.readouterr().out
    assert token not in shown

    receipt = tmp_path / "result.md"
    receipt.write_text("Preserved output")
    result = lifecycle.close("native-task-123", receipt)
    assert token not in json.dumps(result)


def test_close_receipt_cannot_live_inside_scratch(lifecycle):
    lifecycle.observe(event())
    receipt = lifecycle.scratch_root / "native-task-123/report.md"
    receipt.write_text("Would be lost")
    with pytest.raises(ValueError, match="outside scratch"):
        lifecycle.close("native-task-123", receipt)


def test_existing_native_record_is_not_retroactively_managed(lifecycle, tmp_path):
    lifecycle.scratch_root.mkdir(parents=True)
    scratch = lifecycle.scratch_root / "native-task-123"
    scratch.mkdir()
    metadata = lifecycle.state_root
    metadata.mkdir(parents=True)
    (metadata / "native-task-123.json").write_text(json.dumps({
        "schema": "abyss_machine_codex_scratch_v1",
        "session_id": "native-task-123",
        "owner": "codex-native-scratch",
        "path": str(scratch),
        "state": "active",
    }))
    lifecycle.observe(event("UserPromptSubmit"))
    assert not (lifecycle.lifecycle_root / "workspaces").exists()
    receipt = tmp_path / "legacy-result.md"
    receipt.write_text("Preserved output")
    with pytest.raises(ValueError, match="unmanaged"):
        lifecycle.close("native-task-123", receipt, decision="DELETE")
