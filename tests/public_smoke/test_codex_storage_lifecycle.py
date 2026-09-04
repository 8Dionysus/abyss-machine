import datetime as dt
import json
from pathlib import Path
import subprocess

import pytest

from abyss_machine.codex_storage_lifecycle import Lifecycle


@pytest.fixture
def lifecycle(tmp_path):
    return Lifecycle(state_root=tmp_path / "state", scratch_root=tmp_path / "scratch",
                     candidates_root=tmp_path / "candidates", required_mount=None)


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


def test_explicit_close_preserves_receipt_and_resume_reopens_protection(lifecycle, tmp_path):
    lifecycle.observe(event())
    receipt = tmp_path / "result.md"
    receipt.write_text("Preserved output")
    result = lifecycle.close("native-task-123", receipt)
    assert result["state"] == "closed"
    assert len(result["closeout"]["sha256"]) == 64
    lifecycle.observe(event("SessionEnd"))
    assert records(lifecycle)["state"] == "closed"
    lifecycle.observe(event("UserPromptSubmit"))
    assert records(lifecycle)["state"] == "active"
    assert "closeout" not in records(lifecycle)
    claim = json.loads((lifecycle.candidates_root / "claims/codex-native-task-123.json").read_text())
    assert dt.datetime.fromisoformat(claim["expires_at"]) > dt.datetime.now(dt.timezone.utc)


def test_close_receipt_cannot_live_inside_scratch(lifecycle):
    lifecycle.observe(event())
    receipt = lifecycle.scratch_root / "native-task-123/report.md"
    receipt.write_text("Would be lost")
    with pytest.raises(ValueError, match="outside scratch"):
        lifecycle.close("native-task-123", receipt)
