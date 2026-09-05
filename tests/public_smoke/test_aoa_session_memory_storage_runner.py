from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from abyss_machine import aoa_session_memory_storage_runner as runner


def _config(tmp_path: Path, **updates: object) -> runner.RunnerConfig:
    subject_root = tmp_path / "subjects"
    config = runner.RunnerConfig(
        config_path=tmp_path / "config.json",
        enabled=True,
        record_id="sha256:" + "a" * 64,
        subject_store_root=subject_root,
        state_dir=tmp_path / "state",
        workspace_root=tmp_path / "workspace",
        aoa_root=tmp_path / "workspace" / ".aoa",
        host_cli=tmp_path / "bin" / "abyss-machine",
        backup_cli=tmp_path / "bin" / "abyss-backup",
    )
    bundle = config.bundle_dir
    (bundle / "scripts").mkdir(parents=True)
    (bundle / "scripts" / "aoa_session_memory.py").write_text(
        "# fixture owner bundle\n", encoding="utf-8"
    )
    return replace(config, **updates)


def _trust_payload(config: runner.RunnerConfig) -> dict[str, object]:
    return {
        "schema": "abyss_machine_artifact_trust_gate_v1",
        "ok": True,
        "verdict": "allow",
        "artifact_class": config.artifact_class,
        "subject_digest": config.subject_digest,
        "record_id": config.record_id,
        "consumer_intent": runner.CONSUMER_INTENT,
        "record": {
            "record_id": config.record_id,
            "artifact_class": config.artifact_class,
            "subject_digest": config.subject_digest,
            "source_repo": config.source_repo,
            "source_ref": config.source_ref,
            "trust_root_mode": runner.TRUST_ROOT_MODE,
            "artifact_subject_store": {
                "required": True,
                "ok": True,
                "path": str(config.bundle_dir),
            },
        },
        "reasons": [],
    }


def _owner_payload(
    status: str,
    *,
    ok: bool = True,
    mutates: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": "owner-schema",
        "artifact_type": runner.OWNER_ARTIFACT_TYPE,
        "ok": ok,
        "status": status,
        "mutates": mutates,
        "plain_bytes": 100,
        "compressed_bytes": 40,
        "compressed_count": 1 if mutates else 0,
        "_plain_block_candidates": [{"raw": "private"}],
        "results": [{"status": status, "session_dir": "/private/session"}],
        "diagnostics": ["safe_code:private-detail"],
    }


def _maintenance_payload(
    status: str = "no_eligible_candidates",
    *,
    ok: bool = True,
    mutates: bool = True,
) -> dict[str, object]:
    compact = _owner_payload(status, ok=ok, mutates=False)
    compact.update(
        {
            "storage_mode": "sealed_only",
            "preflight_raw_block_ref_audit": {
                "ok": True,
                "status": "ok",
                "checked_count": 2,
                "missing_count": 0,
                "mismatch_count": 0,
            },
            "created_compressed_bytes": 0,
            "removed_plain_bytes": 0,
        }
    )
    return {
        "schema_version": "maintenance-schema",
        "artifact_type": runner.OWNER_MAINTENANCE_ARTIFACT_TYPE,
        "ok": ok,
        "status": status,
        "mutates": mutates,
        "storage_mutates": False,
        "cursor_before": "session-a",
        "cursor_after": "session-b",
        "cursor_committed": True,
        "block_cursor_before": {"session-a": "block-1"},
        "block_cursor_after": {"session-a": "block-2"},
        "block_cursor_committed": True,
        "scanned_count": 32,
        "selected_count": 0,
        "selected_block_counts": {"session-a": 0},
        "selected_plain_bytes": 0,
        "eligible_plain_bytes": 100,
        "estimated_compressed_bytes": 40,
        "successful_publish_session_ids": [],
        "scanned": [{"status": "skipped", "session_dir": "/private/session"}],
        "compact": compact,
    }


def test_missing_or_disabled_config_is_safe_noop() -> None:
    code, missing = runner.run(Path("/tmp/runner-config-that-does-not-exist"), run_port=lambda *_a, **_k: pytest.fail("subprocess must not run"))
    assert code == 0
    assert missing["status"] == "disabled_configuration_missing"
    assert missing["mutates"] is False


def test_enabled_config_requires_exact_record_id(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema": runner.SCHEMA,
                "enabled": True,
                "artifact_class": runner.ARTIFACT_CLASS,
                "subject_digest": runner.SUBJECT_DIGEST,
                "source_repo": runner.SOURCE_REPO,
                "source_ref": runner.SOURCE_REF,
                "registry_dir": str(runner.DEFAULT_REGISTRY_DIR),
                "reservation": {
                    "status": "reservation_not_supported_for_owner_path",
                    "hard_bytes_reservation": False,
                },
            }
        ),
        encoding="utf-8",
    )
    code, payload = runner.run(path, run_port=lambda *_a, **_k: pytest.fail("blocked config must not run"))
    assert code == 1
    assert payload["status"] == "blocked_configuration"
    assert "record_id_required_when_enabled" in payload["errors"]


def test_malformed_schema_or_disabled_config_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema": "wrong-schema",
                "enabled": False,
                "reservation": {
                    "status": "reservation_not_supported_for_owner_path",
                    "hard_bytes_reservation": False,
                },
            }
        ),
        encoding="utf-8",
    )
    code, payload = runner.run(path, run_port=lambda *_a, **_k: pytest.fail("blocked config must not run"))
    assert code == 1
    assert payload["status"] == "blocked_configuration"
    assert "schema_mismatch" in payload["errors"]


def test_config_rejects_malformed_numeric_and_reservation_contract(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema": runner.SCHEMA,
                "enabled": True,
                "record_id": "record-1",
                "artifact_class": runner.ARTIFACT_CLASS,
                "subject_digest": runner.SUBJECT_DIGEST,
                "source_repo": runner.SOURCE_REPO,
                "source_ref": runner.SOURCE_REF,
                "registry_dir": str(runner.DEFAULT_REGISTRY_DIR),
                "session_limit": "4",
                "reservation": {
                    "status": "hard_bytes_reservation",
                    "hard_bytes_reservation": True,
                },
            }
        ),
        encoding="utf-8",
    )
    code, payload = runner.run(path, run_port=lambda *_a, **_k: pytest.fail("blocked config must not run"))
    assert code == 1
    assert payload["status"] == "blocked_configuration"
    assert "session_limit_must_be_integer" in payload["errors"]
    assert "reservation_status_mismatch" in payload["errors"]
    assert "hard_bytes_reservation_must_be_false" in payload["errors"]


def test_public_template_is_disabled_and_binds_pinned_runtime_bundle() -> None:
    template = json.loads(
        (
            Path(__file__).parents[2]
            / "config-templates/etc/abyss-machine/aoa-session-memory-storage.json"
        ).read_text(encoding="utf-8")
    )
    assert template["schema"] == runner.SCHEMA
    assert template["enabled"] is False
    assert template["record_id"] == ""
    assert template["artifact_class"] == runner.ARTIFACT_CLASS
    assert template["subject_digest"] == runner.SUBJECT_DIGEST
    assert template["source_ref"] == runner.SOURCE_REF
    assert template["reservation"]["status"] == "reservation_not_supported_for_owner_path"
    assert template["reservation"]["hard_bytes_reservation"] is False


def test_bootstrap_profile_and_narrow_dispatch_are_source_bound() -> None:
    root = Path(__file__).parents[2]
    profiles = json.loads(
        (root / "manifests/bootstrap_profiles.manifest.json").read_text(encoding="utf-8")
    )
    assert profiles["profiles"]["aoa-session-memory-storage"] == {
        "system": [],
        "user": ["abyss-aoa-session-memory-raw-block-compact.timer"],
    }
    bootstrap = (root / "scripts/abyss-machine-bootstrap").read_text(encoding="utf-8")
    cli = (root / "src/abyss_machine/cli.py").read_text(encoding="utf-8")
    assert '["storage", "aoa-session-memory-compact"]' in bootstrap
    assert '["storage", "aoa-session-memory-compact-child"]' in bootstrap
    assert '["storage", "aoa-session-memory-compact"]' in cli
    assert '["storage", "aoa-session-memory-compact-child"]' in cli


def test_live_archive_bundle_fallback_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path, subject_store_root=runner.LIVE_ARCHIVE_ROOT)
    payload = runner.run_once(config, write_state=False, run_port=lambda *_a, **_k: pytest.fail("path guard must run first"))
    assert payload["status"] == "blocked_bundle"
    assert "bundle_dir_must_not_be_live_archive" in payload["errors"]


def test_resource_command_uses_owner_lease_without_bytes_target_and_keeps_pilot_nonremoving(tmp_path: Path) -> None:
    config = _config(tmp_path)
    argv = runner.owner_resource_argv(config)
    assert "--bytes" not in argv
    assert "--target" not in argv
    assert "--include-open-tail" in argv
    assert "--confirm-remove-plain" not in argv
    assert "aoa-session-memory-compact-child" in argv
    assert str(config.bundle_dir / runner.OWNER_SCRIPT_RELATIVE) in argv
    assert float(argv[argv.index("--timeout") + 1]) == (
        config.retry_deadline_sec - runner.RESOURCE_TIMEOUT_RESERVE_SEC
    )
    assert argv[argv.index("--kind") + 1] == runner.RESOURCE_KIND
    assert argv[argv.index("--demand-key") + 1] == runner.RESOURCE_DEMAND_KEY

    reclaim = replace(
        config,
        mode="reclaim",
        reclaim_plain=True,
        pilot_verified=True,
        pilot_evidence_ref="owner-proof/session-pilot.json",
    )
    assert "--confirm-remove-plain" in runner.owner_resource_argv(reclaim)


def test_reclaim_mode_without_verified_pilot_fails_config(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema": runner.SCHEMA,
                "enabled": True,
                "record_id": "sha256:" + "b" * 64,
                "mode": "reclaim",
                "reclaim_plain": True,
                "artifact_class": runner.ARTIFACT_CLASS,
                "subject_digest": runner.SUBJECT_DIGEST,
                "source_repo": runner.SOURCE_REPO,
                "source_ref": runner.SOURCE_REF,
                "registry_dir": str(runner.DEFAULT_REGISTRY_DIR),
            }
        ),
        encoding="utf-8",
    )
    code, payload = runner.run(path, run_port=lambda *_a, **_k: pytest.fail("blocked config must not run"))
    assert code == 1
    assert payload["status"] == "blocked_configuration"
    assert "reclaim_requires_verified_pilot_evidence" in payload["errors"]


def test_direct_runner_cannot_add_plain_removal_without_pilot_evidence(tmp_path: Path) -> None:
    config = _config(tmp_path, reclaim_plain=True, mode="reclaim")
    payload = runner.run_once(
        config,
        write_state=False,
        run_port=lambda *_a, **_k: pytest.fail("unverified reclaim must not run"),
    )
    assert payload["status"] == "blocked_configuration"
    assert payload["mutates"] is False


def test_runtime_gate_and_vault_guard_precede_owner(tmp_path: Path) -> None:
    config = _config(tmp_path)
    calls: list[list[str]] = []

    def fake(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(_trust_payload(config)), "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 1, "", "vault absent")
        pytest.fail("owner must not run while Vault is absent")

    payload = runner.run_once(config, run_port=fake, write_state=False)
    assert payload["status"] == "deferred_vault_not_mounted"
    assert len(calls) == 2
    assert calls[0][1:3] == ["artifacts", "trust-gate"]
    assert calls[1][1:3] == ["timer-preflight", "sessions"]


def test_runtime_gate_requires_source_and_trust_root_binding(tmp_path: Path) -> None:
    config = _config(tmp_path)
    gate = _trust_payload(config)
    assert isinstance(gate["record"], dict)
    gate["record"]["source_ref"] = "wrong-source"
    result = runner._trust_gate_summary(
        {"returncode": 0, "stdout": "diagnostic line\n" + json.dumps(gate)},
        config,
    )
    summary, allowed = result
    assert allowed is False
    assert summary["ok"] is False
    assert summary["source_ref"] == "wrong-source"


def test_recorded_subject_store_path_is_authoritative_and_reaches_owner(tmp_path: Path) -> None:
    config = _config(tmp_path)
    rerouted_bundle = tmp_path / "srv" / "storage" / "subjects" / config.artifact_class / config.subject_digest.removeprefix("sha256:")
    (rerouted_bundle / "scripts").mkdir(parents=True)
    (rerouted_bundle / "scripts" / "aoa_session_memory.py").write_text(
        "# rerouted owner bundle\n", encoding="utf-8"
    )
    gate = _trust_payload(config)
    record = gate["record"]
    assert isinstance(record, dict)
    record["artifact_subject_store"] = {
        "required": True,
        "ok": True,
        "path": str(rerouted_bundle),
    }
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if argv[1:3] == ["artifacts", "trust-gate"]:
            environment = kwargs.get("env")
            assert isinstance(environment, dict)
            assert environment["ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOT"] == str(config.subject_store_root)
            assert environment["ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOTS"] == str(config.subject_store_root)
            return subprocess.CompletedProcess(argv, 0, json.dumps(gate), "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(
            argv, 0, json.dumps(_owner_payload("no_eligible_candidates")), ""
        )

    payload = runner.run_once(config, run_port=fake, write_state=False)
    assert payload["status"] == "no_eligible_candidates"
    assert payload["paths"]["subject_store_record_path"] == str(rerouted_bundle)
    owner_call = calls[2][0]
    assert str(rerouted_bundle / runner.OWNER_SCRIPT_RELATIVE) in owner_call
    assert str(config.bundle_dir / runner.OWNER_SCRIPT_RELATIVE) not in owner_call


def test_missing_or_unverified_subject_store_record_blocks_after_trust(tmp_path: Path) -> None:
    config = _config(tmp_path)
    gate = _trust_payload(config)
    record = gate["record"]
    assert isinstance(record, dict)
    record.pop("artifact_subject_store")

    def missing(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(gate), "")
        pytest.fail("subject-store failure must precede Vault and owner")

    payload = runner.run_once(config, run_port=missing, write_state=False)
    assert payload["status"] == "blocked_subject_store"
    assert payload["errors"] == ["subject_store_record_missing"]

    gate = _trust_payload(config)
    record = gate["record"]
    assert isinstance(record, dict)
    store = record["artifact_subject_store"]
    assert isinstance(store, dict)
    store["ok"] = False

    def unverified(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(gate), "")
        pytest.fail("subject-store failure must precede Vault and owner")

    payload = runner.run_once(config, run_port=unverified, write_state=False)
    assert payload["status"] == "blocked_subject_store"
    assert payload["errors"] == ["subject_store_record_not_verified"]


def test_lock_contention_retries_5_15_then_applies_and_writes_compact_state(tmp_path: Path) -> None:
    config = _config(tmp_path)
    calls: list[list[str]] = []
    owner_results = iter(
        [
            _owner_payload("skipped_lock_held"),
            _owner_payload("skipped_lock_held"),
            _owner_payload("applied", mutates=True),
        ]
    )
    current = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return current[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        current[0] += seconds

    def fake(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(_trust_payload(config)), "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, json.dumps(next(owner_results)), "")

    payload = runner.run_once(
        config,
        run_port=fake,
        sleep_port=sleep,
        clock_port=clock,
    )
    assert payload["status"] == "applied"
    assert payload["ok"] is True
    assert payload["mutates"] is True
    assert sleeps == [5, 15]
    assert [item["owner_status"] for item in payload["attempts"]] == [
        "skipped_lock_held",
        "skipped_lock_held",
        "applied",
    ]
    saved = json.loads((config.state_dir / "latest.json").read_text(encoding="utf-8"))
    assert saved["status"] == "applied"
    assert saved["reservation"]["hard_bytes_reservation"] is False
    assert len(calls) == 5


def test_resource_block_is_truthful_defer_and_missing_child_is_error(tmp_path: Path) -> None:
    config = _config(tmp_path)
    gate = json.dumps(_trust_payload(config))

    def blocked(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, gate, "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, json.dumps({"ok": True, "blocked_reasons": ["memory_pressure"]}), "")

    deferred = runner.run_once(config, run_port=blocked, write_state=False)
    assert deferred["status"] == "deferred_resource_admission"
    assert deferred["ok"] is True
    assert deferred["mutates"] is False

    def missing(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, gate, "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, json.dumps({"ok": True}), "")

    failed = runner.run_once(config, run_port=missing, write_state=False)
    assert failed["status"] == "resource_child_json_missing"
    assert failed["ok"] is False


def test_no_eligible_owner_result_is_successful_noop(tmp_path: Path) -> None:
    config = _config(tmp_path)
    gate = json.dumps(_trust_payload(config))
    owner = json.dumps(_owner_payload("no_eligible_candidates"))

    def fake(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, gate, "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, owner, "")

    payload = runner.run_once(config, run_port=fake, write_state=False)
    assert payload["status"] == "no_eligible_candidates"
    assert payload["ok"] is True
    assert payload["deferred"] is False


def test_maintenance_owner_result_preserves_cursor_progress_and_real_artifact_type(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    gate = json.dumps(_trust_payload(config))
    owner = json.dumps(_maintenance_payload())

    def fake(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, gate, "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, owner, "")

    payload = runner.run_once(config, run_port=fake, write_state=False)
    assert payload["status"] == "no_eligible_candidates"
    assert payload["ok"] is True
    assert payload["mutates"] is True
    assert payload["owner"]["artifact_type"] == runner.OWNER_MAINTENANCE_ARTIFACT_TYPE
    assert payload["owner"]["cursor_committed"] is True
    assert payload["owner"]["block_cursor_after"] == {"session-a": "block-2"}
    assert payload["owner"]["result_status_counts"] == {"no_eligible_candidates": 1}


def test_lock_conflict_artifact_is_a_known_retryable_owner_outcome() -> None:
    lock_conflict = {
        "artifact_type": runner.OWNER_LOCK_CONFLICT_ARTIFACT_TYPE,
        "status": "skipped_lock_held",
        "ok": True,
        "mutates": False,
        "conflict_kind": "lock_held",
        "diagnostics": ["lock_held"],
    }
    maintenance = _maintenance_payload(status="blocked", ok=True, mutates=False)
    maintenance["compact"] = lock_conflict
    classification, owner, _summary = runner._classify_resource_result(
        {"returncode": 0, "stdout": json.dumps(maintenance), "stderr": ""}
    )
    assert classification == "deferred_lock_busy"
    assert owner is not None
    assert owner["artifact_type"] == runner.OWNER_MAINTENANCE_ARTIFACT_TYPE
    assert owner["nested_artifact_type"] == runner.OWNER_LOCK_CONFLICT_ARTIFACT_TYPE


def test_resource_or_owner_failure_cannot_be_classified_as_no_eligible() -> None:
    maintenance = _maintenance_payload()
    resource_failure = runner._classify_resource_result(
        {"returncode": 1, "stdout": json.dumps(maintenance), "stderr": "failed"}
    )
    assert resource_failure[0] == "resource_child_failed"
    owner_failure = dict(maintenance)
    owner_failure["ok"] = False
    owner_failure_result = runner._classify_resource_result(
        {"returncode": 0, "stdout": json.dumps(owner_failure), "stderr": ""}
    )
    assert owner_failure_result[0] == "owner_failed"


def test_resource_tail_finds_nested_maintenance_payload_and_keeps_mutates() -> None:
    maintenance = _maintenance_payload()
    resource = {
        "ok": True,
        "execution": {"returncode": 0, "stdout_tail": json.dumps(maintenance)},
    }
    classification, owner, summary = runner._classify_resource_result(
        {"returncode": 0, "stdout": json.dumps(resource), "stderr": ""}
    )
    assert classification == "no_eligible_candidates"
    assert owner is not None
    assert owner["artifact_type"] == runner.OWNER_MAINTENANCE_ARTIFACT_TYPE
    assert owner["mutates"] is True
    assert owner["cursor_after"] == "session-b"
    assert summary["owner"]["storage_mutates"] is False


def test_child_wrapper_captures_and_sanitizes_complete_owner_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _maintenance_payload()
    owner_script = tmp_path / "owner.py"
    owner_script.write_text(
        f"print({json.dumps(json.dumps(payload))})\n",
        encoding="utf-8",
    )
    code = runner.child_main(
        [
            "--python",
            sys.executable,
            "--owner-script",
            str(owner_script),
            "--",
            "raw-block-storage-compact",
            "all",
        ]
    )
    captured = capsys.readouterr().out
    output = json.loads(captured)
    assert code == 0
    assert len(captured.encode("utf-8")) <= runner.MAX_CHILD_SUMMARY_BYTES + 1
    assert output["artifact_type"] == runner.OWNER_MAINTENANCE_ARTIFACT_TYPE
    assert output["owner_payload_complete"] is True
    assert output["child_returncode"] == 0
    assert output["mutates"] is True
    assert output["cursor_after"] == "session-b"
    assert output["block_cursor_after"] == {"session-a": "block-2"}
    encoded = json.dumps(output)
    assert "_plain_block_candidates" not in encoded
    assert "/private/session" not in encoded


def test_child_wrapper_rejects_oversized_capture_without_emitting_raw_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    owner_script = tmp_path / "owner.py"
    owner_script.write_text("print('x' * 128)\n", encoding="utf-8")
    code = runner.child_main(
        [
            "--python",
            sys.executable,
            "--owner-script",
            str(owner_script),
            "--max-capture-bytes",
            "16",
            "--",
            "raw-block-storage-compact",
            "all",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 1
    assert output["status"] == "child_capture_failed"
    assert output["diagnostic_codes"] == ["child_output_oversize"]
    assert output["child_stdout_bytes"] > 16
    assert "x" * 32 not in json.dumps(output)


def test_session_lease_deferral_is_reported_without_false_failure(tmp_path: Path) -> None:
    config = _config(tmp_path)
    gate = json.dumps(_trust_payload(config))
    owner = json.dumps(_owner_payload("deferred_session_lease"))

    def fake(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["artifacts", "trust-gate"]:
            return subprocess.CompletedProcess(argv, 0, gate, "")
        if argv[1:3] == ["timer-preflight", "sessions"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, owner, "")

    payload = runner.run_once(config, run_port=fake, write_state=False)
    assert payload["status"] == "deferred_session_lease"
    assert payload["ok"] is True
    assert payload["deferred"] is True


def test_owner_projection_sanitizer_omits_private_candidates_and_session_paths() -> None:
    sanitized = runner.sanitize_owner_payload(_owner_payload("applied", mutates=True))
    encoded = json.dumps(sanitized)
    assert "_plain_block_candidates" not in encoded
    assert "/private/session" not in encoded
    assert sanitized["status"] == "applied"
    assert sanitized["diagnostic_codes"] == ["safe_code"]


def test_owner_projection_sanitizer_reads_nested_compact_and_preserves_type() -> None:
    sanitized = runner.sanitize_owner_payload(_maintenance_payload())
    assert sanitized["artifact_type"] == runner.OWNER_MAINTENANCE_ARTIFACT_TYPE
    assert sanitized["storage_mutates"] is False
    assert sanitized["compressed_bytes"] == 40
    assert sanitized["preflight_raw_block_ref_audit"]["checked_count"] == 2
    assert sanitized["scanned_status_counts"] == {"skipped": 1}


def test_child_summary_is_bounded_even_with_large_cursor_maps() -> None:
    payload = _maintenance_payload()
    payload["block_cursor_before"] = {f"session-{i}": "x" * 512 for i in range(32)}
    payload["block_cursor_after"] = {f"session-{i}": "y" * 512 for i in range(32)}
    bounded = runner._bounded_child_summary(runner.sanitize_owner_payload(payload))
    assert len(json.dumps(bounded, ensure_ascii=False).encode("utf-8")) <= runner.MAX_CHILD_SUMMARY_BYTES
    assert bounded["child_summary_truncated"] is True
