from __future__ import annotations

import hashlib

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_typing_ingest_redacts_secret_like_committed_text(abyss_machine_module) -> None:
    machine = abyss_machine_module

    event = machine.typing_ingest(
        "normal note password=example-redacted",
        source="manual_cli_args",
        app="editor",
        context="note",
        write_latest=False,
    )

    assert event["schema"] == "abyss_machine_typing_event_v1"
    assert event["ok"] is True
    assert event["status"] == "metadata_only"
    assert event["policy"]["raw_keylogging"] is False
    assert event["policy"]["password_fields_captured"] is False
    assert event["text"]["captured"] is False
    assert event["text"]["text"] is None
    assert event["text"]["metadata_only_reason"] == "secret_like_text"
    assert event["text"]["redaction"]["matches"] == 1
    assert "secret_assignment" in event["text"]["redaction"]["classes"]
    assert event["classification"]["secret_like_text"] is True


def test_typing_ingest_sensitive_context_is_metadata_only(abyss_machine_module) -> None:
    machine = abyss_machine_module

    event = machine.typing_ingest(
        "not stored because the context is sensitive",
        source="editor_extension_explicit",
        app="browser",
        window_title="Login",
        context="password field",
        write_latest=False,
    )

    assert event["ok"] is True
    assert event["status"] == "metadata_only"
    assert event["text"]["captured"] is False
    assert event["text"]["text"] is None
    assert event["text"]["text_sha256"]
    assert event["classification"]["sensitive_context"] is True


def test_capture_gate_skips_private_messenger_context(abyss_machine_module) -> None:
    machine = abyss_machine_module

    gate = machine.typing_capture_gate_decision(
        "atspi_focused_text_snapshot",
        app="Telegram",
        window_title="Telegram",
        context="chat draft",
        write_latest=False,
    )

    assert gate["schema"] == "abyss_machine_typing_capture_gate_v1"
    assert gate["decision"] == "skip"
    assert gate["agent"]["network_access"] is False
    assert gate["agent"]["subprocess_access"] is False
    assert gate["agent"]["may_promote_unknown_to_allow_text"] is False


def test_capture_gate_login_url_is_metadata_only(abyss_machine_module) -> None:
    machine = abyss_machine_module

    gate = machine.typing_capture_gate_decision(
        "browser_extension_explicit",
        app="firefox",
        url="https://example.com/login?next=/account",
        write_latest=False,
    )

    assert gate["decision"] == "metadata_only"
    assert gate["confidence"] == "sensitive_url"
    assert any(item.get("token") in {"login", "auth"} for item in gate["matches"])


def test_typing_ingest_capture_gate_metadata_only_for_login_url(abyss_machine_module) -> None:
    machine = abyss_machine_module

    event = machine.typing_ingest(
        "browser draft should not persist",
        source="browser_extension_explicit",
        app="firefox",
        url="https://example.com/login",
        write_latest=False,
    )

    assert event["ok"] is True
    assert event["status"] == "metadata_only"
    assert event["text"]["captured"] is False
    assert event["text"]["text"] is None
    assert event["text"]["metadata_only_reason"] == "capture_gate:metadata_only"
    assert event["capture_gate"]["decision"] == "metadata_only"
    assert event["classification"]["capture_gate"]["agent"]["network_access"] is False


def test_typing_ingest_capture_gate_skips_telegram_text(abyss_machine_module) -> None:
    machine = abyss_machine_module

    event = machine.typing_ingest(
        "telegram draft should not persist",
        source="atspi_focused_text_snapshot",
        app="Telegram",
        window_title="Telegram",
        write_latest=False,
    )

    assert event["ok"] is True
    assert event["status"] == "skipped_by_capture_gate"
    assert event["text"]["captured"] is False
    assert event["text"]["text"] is None
    assert event["text"]["metadata_only_reason"] == "capture_gate:skip"
    assert event["capture_gate"]["decision"] == "skip"


def test_typing_coverage_exposes_adapter_and_gate_distribution(abyss_machine_module) -> None:
    machine = abyss_machine_module
    policy = machine.default_typing_policy()
    records = [
        machine.typing_ingest("manual probe", source="manual_cli_args", app="codex", write_latest=False),
        machine.typing_ingest("browser probe", source="browser_extension_explicit", app="firefox", url="https://example.com/login", write_latest=False),
        machine.typing_ingest("telegram probe", source="atspi_focused_text_snapshot", app="Telegram", window_title="Telegram", write_latest=False),
    ]

    coverage = machine.typing_coverage_from_records(records, [], policy, latest=records[0])

    assert coverage["schema"] == "abyss_machine_typing_coverage_v1"
    assert coverage["policy"]["raw_keylogging"] is False
    assert coverage["policy"]["capture_gate_network_access"] is False
    assert coverage["by_adapter"]["manual_cli_args"] == 1
    assert coverage["by_capture_gate_decision"]["allow_text"] == 1
    assert coverage["by_capture_gate_decision"]["metadata_only"] == 1
    assert coverage["by_capture_gate_decision"]["skip"] == 1
    assert not any(item["key"] == "capture_gate_deny_routes_not_observed_recently" for item in coverage["gaps"])


def test_zsh_hook_status_verifies_committed_command_adapter_contract(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    hook = tmp_path / "abyss-typing.zsh"
    zshrc = tmp_path / ".zshrc"
    hook.write_text(
        "\n".join(
            [
                "# Abyss typing committed shell-command adapter.",
                "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1",
                "_abyss_typing_preexec() {",
                "  printf '%s' \"$1\" | abyss-machine typing ingest --stdin --source zsh_preexec --context \"shell_command cwd=$PWD hook=abyss-typing-zsh-v1\" --json",
                "}",
                "# abyss-typing-zsh-v1",
            ]
        ),
        encoding="utf-8",
    )
    zshrc.write_text("source $HOME/.config/zsh/abyss-typing.zsh\n", encoding="utf-8")
    monkeypatch.setattr(machine, "TYPING_ZSH_HOOK_PATH", hook)
    monkeypatch.setattr(machine, "TYPING_ZSHRC_PATH", zshrc)
    monkeypatch.setattr(machine, "typing_zsh_hook_function_probe", lambda: {"ok": True, "returncode": 0, "stderr": ""})
    monkeypatch.setattr(machine, "typing_latest", lambda: {"ok": False, "error": "missing"})

    status = machine.typing_zsh_hook_status(write_latest=False)

    assert status["schema"] == "abyss_machine_typing_zsh_hook_status_v1"
    assert status["ok"] is True
    assert status["policy"]["raw_keylogging"] is False
    assert status["policy"]["terminal_output_captured"] is False
    assert status["hook"]["missing_markers"] == []


def test_zsh_hook_selftest_detects_zsh_preexec_event(abyss_machine_module, monkeypatch) -> None:
    machine = abyss_machine_module
    probe_text = "print abyss-zsh-hook-selftest"
    probe_hash = hashlib.sha256(probe_text.encode("utf-8")).hexdigest()
    monkeypatch.setattr(machine, "typing_zsh_hook_status", lambda write_latest=False: {"ok": True, "status": "ready", "hook": {}, "zshrc": {}})
    monkeypatch.setattr(machine, "run", lambda cmd, timeout=3.0, env=None: {"ok": True, "returncode": 0, "stdout": "", "stderr": ""})
    monkeypatch.setattr(
        machine,
        "typing_zsh_hook_find_probe_event",
        lambda text_sha256: (
            {
                "event_id": "typing-zsh-test",
                "source_adapter": "zsh_preexec",
                "status": "captured",
                "capture_gate_decision": "allow_text",
            }
            if text_sha256 == probe_hash
            else None,
            [],
        ),
    )

    result = machine.typing_zsh_hook_selftest(write_latest=False)

    assert result["schema"] == "abyss_machine_typing_zsh_hook_selftest_v1"
    assert result["ok"] is True
    assert result["summary"]["event_detected"] is True
    assert result["probe"]["text_sha256"] == probe_hash
    assert result["policy"]["raw_keylogging"] is False


def test_codex_prompt_hook_ingests_user_prompt_submit_event(abyss_machine_module, monkeypatch) -> None:
    machine = abyss_machine_module
    monkeypatch.setattr(
        machine,
        "changes_index",
        lambda write_latest=False: {"active": []},
    )

    result = machine.typing_codex_prompt_hook_ingest_event(
        {
            "session_id": "codex-session-test",
            "turn_id": "codex-turn-test",
            "cwd": "/home/dionysus",
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-test",
            "permission_mode": "test",
            "prompt": "codex live prompt probe",
        },
        write_latest=False,
    )

    assert result["schema"] == "abyss_machine_typing_codex_prompt_hook_v1"
    assert result["ok"] is True
    assert result["status"] == "ingested"
    assert result["typing_event"]["source_adapter"] == "codex_user_prompt_submit"
    assert result["typing_event"]["capture_gate_decision"] == "allow_text"
    assert result["policy"]["session_postprocessing"] is False
    assert result["policy"]["raw_keylogging"] is False


def test_codex_prompt_hook_status_detects_user_prompt_submit_command(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    hooks = tmp_path / "hooks.json"
    config = tmp_path / "config.toml"
    hooks.write_text(
        """
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "abyss-machine typing codex-prompt-hook",
            "statusMessage": "Abyss typing Codex prompt",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config.write_text("[features]\nhooks = true\n", encoding="utf-8")
    monkeypatch.setattr(machine, "TYPING_CODEX_HOOKS_PATH", hooks)
    monkeypatch.setattr(machine, "TYPING_CODEX_CONFIG_PATH", config)
    monkeypatch.setattr(machine, "typing_latest", lambda: {"ok": False, "error": "missing"})

    status = machine.typing_codex_prompt_hook_status(write_latest=False)

    assert status["schema"] == "abyss_machine_typing_codex_prompt_hook_status_v1"
    assert status["ok"] is True
    assert status["status"] == "ready"
    assert status["policy"]["native_codex_submit_hook"] is True
    assert status["policy"]["session_postprocessing"] is False


def test_typing_ingest_adds_causal_context_without_action_claims(abyss_machine_module, monkeypatch) -> None:
    machine = abyss_machine_module
    monkeypatch.setattr(
        machine,
        "changes_index",
        lambda write_latest=False: {
            "active": [
                {
                    "id": "typing-causal-test",
                    "title": "Typing causal test",
                    "status": "active",
                    "created_at": "2026-05-19T00:00:00+00:00",
                    "surfaces": ["/srv/AbyssOS"],
                }
            ]
        },
    )

    event = machine.typing_ingest(
        "causal context probe",
        source="manual_cli_args",
        app="editor",
        context="note project path supplied as metadata",
        metadata={"file": {"path": "/srv/AbyssOS/aoa-evals/README.md"}},
        write_latest=False,
    )

    causal = event["causal_context"]
    assert causal["schema"] == "abyss_machine_typing_causal_context_v1"
    assert causal["input"]["event_id"] == event["event_id"]
    assert causal["input"]["stores_text"] is False
    assert causal["where"]["project"]["id"] == "AbyssOS"
    assert causal["recipient"]["kind"] == "typing_cli"
    assert causal["task"]["active_changes"][0]["id"] == "typing-causal-test"
    assert causal["task"]["active_changes"][0]["match"] == "surface_match"
    assert causal["policy"]["automatic_action"] is False
    assert causal["policy"]["intent_claim"] is False


def test_typing_validate_keeps_non_keylogger_contract(abyss_machine_module) -> None:
    machine = abyss_machine_module

    validation = machine.typing_validate(write_latest=False)

    assert validation["schema"] == "abyss_machine_typing_validate_v1"
    assert validation["summary"]["fails"] == 0
    keys = {item["key"]: item for item in validation["checks"]}
    assert keys["no_raw_keylogging"]["level"] == "ok"
    assert keys["no_password_fields"]["level"] == "ok"
    assert keys["capture_gate_policy"]["level"] == "ok"
    assert keys["capture_gate_deterministic_routes"]["level"] == "ok"
    assert keys["typing_coverage_readmodel"]["level"] == "ok"


def test_heartbeats_expose_typing_as_freshness_input(abyss_machine_module) -> None:
    machine = abyss_machine_module

    paths = machine.heartbeats_paths()

    assert paths["inputs"]["typing"] == str(machine.TYPING_EVENTS_LATEST_PATH)
    assert "typing" in machine.HEARTBEAT_SOURCE_FRESHNESS_TTLS


def test_heartbeat_capture_health_reports_typing_safety(abyss_machine_module) -> None:
    machine = abyss_machine_module

    result = machine.heartbeat_capture_health_from(
        capture_status={
            "ok": True,
            "latest": {"generated_at": "2026-05-19T10:00:00+00:00", "summary": {"facts": 1, "facts_ok": 1, "skipped": 0}},
            "browser_content_latest": {"generated_at": "2026-05-19T10:00:00+00:00", "summary": {}},
            "storage": {},
        },
        retention_plan={"generated_at": "2026-05-19T10:00:00+00:00", "summary": {"candidates": 0, "route_errors": 0}},
        privacy_status={"global_pause": False, "private_mode": False},
        typing_status_data={
            "ok": True,
            "summary": {"recent_records": 4, "by_status": {"captured": 1, "redacted": 1, "metadata_only": 2}, "coverage_status": "partial"},
            "policy": {"enabled": True, "raw_keylogging": False, "password_fields_captured": False},
            "coverage": {
                "status": "partial",
                "summary": {
                    "gaps": 1,
                    "dominant_adapter": "zsh_preexec",
                    "dominant_ratio": 0.5,
                    "missing_capture_gate_records": 0,
                },
                "by_adapter": {"zsh_preexec": 2, "saved_text_snapshot": 2},
                "by_capture_gate_decision": {"allow_text": 3, "metadata_only": 1},
                "policy": {"capture_gate_network_access": False, "unknown_surfaces_text_capture": False},
            },
            "latest": {"ok": True, "generated_at": "2026-05-19T10:00:00+00:00", "status": "captured", "source_adapter": "zsh_preexec"},
        },
        generated_at="2026-05-19T10:01:00+00:00",
    )

    assert result["volume"]["typed_text_recent_records"] == 4
    assert result["privacy"]["typed_text_raw_keylogging"] is False
    assert result["privacy"]["typed_text_password_fields_captured"] is False
    assert result["privacy"]["typed_text_capture_gate_network_access"] is False
    assert result["volume"]["typed_text_by_capture_gate"]["metadata_only"] == 1
    assert result["quality"]["typed_text_latest_adapter"] == "zsh_preexec"
    assert result["quality"]["typed_text_coverage_status"] == "partial"
    assert result["sources"]["typing_latest"]["path"] == str(machine.TYPING_EVENTS_LATEST_PATH)


def test_focused_snapshot_sensitive_role_is_metadata_only(abyss_machine_module) -> None:
    machine = abyss_machine_module

    result = machine.typing_focused_snapshot_from_candidate(
        {
            "ok": True,
            "app": "browser",
            "window_title": "Login",
            "role": "password text",
            "path": "1/2/3",
            "states": {"focused": True, "editable": True},
            "text_role": True,
            "sensitive_context": True,
            "text_read_allowed": False,
            "text_length": 0,
            "sensitive_matches": [{"kind": "sensitive_role", "role": "password text"}],
        },
        write_latest=False,
    )

    event = result["event"]
    assert result["policy"]["raw_keylogging"] is False
    assert result["policy"]["password_fields_captured"] is False
    assert result["candidate"]["text_read_allowed"] is False
    assert event["status"] == "metadata_only"
    assert event["text"]["captured"] is False
    assert event["text"]["text"] is None


def test_focused_snapshot_persists_skip_attempt_latest(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    root = tmp_path / "focused"
    monkeypatch.setattr(machine, "TYPING_FOCUSED_SNAPSHOT_ROOT", root)
    monkeypatch.setattr(machine, "TYPING_FOCUSED_SNAPSHOT_LATEST_PATH", root / "latest.json")

    result = machine.typing_focused_snapshot_from_candidate(
        {
            "ok": True,
            "app": "gnome-shell",
            "window_title": "Main stage",
            "role": "window",
            "path": "0/0",
            "states": {"focused": True, "editable": False},
            "text_role": False,
            "sensitive_context": False,
            "text_read_allowed": False,
            "text_length": 0,
        },
        write_latest=True,
    )

    assert result["status"] == "skipped_non_text_focus"
    latest = machine.load_json_document(root / "latest.json")[0]
    assert latest["schema"] == "abyss_machine_typing_focused_snapshot_v1"
    assert latest["status"] == "skipped_non_text_focus"
    assert latest["candidate"]["app"] == "gnome-shell"


def test_focused_snapshot_duplicate_gate_skips_recent_match(abyss_machine_module, monkeypatch) -> None:
    machine = abyss_machine_module

    first = machine.typing_focused_snapshot_from_candidate(
        {
            "ok": True,
            "app": "editor",
            "window_title": "Draft",
            "role": "text",
            "path": "1/2/3",
            "states": {"focused": True, "editable": True},
            "text_role": True,
            "sensitive_context": False,
            "text_read_allowed": True,
            "text": "focused snapshot duplicate probe",
            "text_length": 32,
        },
        write_latest=False,
    )
    monkeypatch.setattr(machine, "typing_records", lambda limit=20: ([first["event"]], []))

    duplicate = machine.typing_focused_snapshot_from_candidate(
        {
            "ok": True,
            "app": "editor",
            "window_title": "Draft",
            "role": "text",
            "path": "1/2/3",
            "states": {"focused": True, "editable": True},
            "text_role": True,
            "sensitive_context": False,
            "text_read_allowed": True,
            "text": "focused snapshot duplicate probe",
            "text_length": 32,
        },
        write_latest=False,
    )

    assert duplicate["status"] == "duplicate_skipped"
    assert duplicate["event"]["duplicate"]["duplicate"] is True
    assert duplicate["event"]["text"]["captured"] is False


def test_saved_text_scan_captures_recent_text_file(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    root = tmp_path / "workspace"
    root.mkdir()
    note = root / "note.md"
    note.write_text("saved text scan probe", encoding="utf-8")
    policy = machine.default_typing_policy()
    policy["saved_text_scan"]["roots"] = [str(root)]
    policy["saved_text_scan"]["changed_within_sec"] = 3600
    policy["saved_text_scan"]["max_files_per_scan"] = 10
    monkeypatch.setattr(machine, "typing_policy", lambda write_latest=False: policy)
    monkeypatch.setattr(machine, "typing_records", lambda limit=20: ([], []))

    result = machine.typing_saved_text_scan(write_latest=False)

    assert result["ok"] is True
    assert result["summary"]["events"] == 1
    assert result["events"][0]["status"] == "captured"
    assert result["events"][0]["capture_gate"]["decision"] == "allow_text"
    assert result["events"][0]["causal_context"]["recipient"]["kind"] == "file"
    assert result["events"][0]["causal_context"]["where"]["path"] == str(note)
    assert result["events"][0]["causal_context"]["task"]["active_changes"] == []
    assert result["policy"]["raw_keylogging"] is False
    assert result["policy"]["password_fields_captured"] is False


def test_saved_text_scan_does_not_treat_benign_doc_words_as_sensitive_context(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    root = tmp_path / "workspace"
    root.mkdir()
    note = root / "decision.md"
    note.write_text("route cards and validation pressure are ordinary project text", encoding="utf-8")
    policy = machine.default_typing_policy()
    policy["saved_text_scan"]["roots"] = [str(root)]
    policy["saved_text_scan"]["changed_within_sec"] = 3600
    monkeypatch.setattr(machine, "typing_policy", lambda write_latest=False: policy)
    monkeypatch.setattr(machine, "typing_records", lambda limit=20: ([], []))

    result = machine.typing_saved_text_scan(write_latest=False)

    assert result["ok"] is True
    assert result["summary"]["events"] == 1
    assert result["events"][0]["status"] == "captured"
    assert result["events"][0]["stored_chars"] > 0


def test_saved_text_scan_excludes_virtualenv_like_paths(abyss_machine_module, tmp_path) -> None:
    machine = abyss_machine_module
    policy = machine.default_typing_policy()["saved_text_scan"]

    matches = machine.typing_saved_text_path_excluded(
        tmp_path / ".venv-first-wave-check" / "lib" / "python" / "site-packages" / "module.py",
        policy,
    )

    assert matches
    assert any(item["token"] in {"/.venv", "/site-packages/"} for item in matches)


def test_saved_text_scan_excludes_aoa_runtime_paths(abyss_machine_module, tmp_path) -> None:
    machine = abyss_machine_module
    policy = machine.default_typing_policy()["saved_text_scan"]

    matches = machine.typing_saved_text_path_excluded(
        tmp_path / ".aoa" / "skill-runtime-sessions" / "session.json",
        policy,
    )

    assert matches
    assert any(item["token"] == "/.aoa/" for item in matches)


def test_saved_text_scan_denies_secret_paths_before_read(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    root = tmp_path / "workspace"
    root.mkdir()
    secret = root / ".env"
    secret.write_text("OPENAI_API_KEY=example-redacted", encoding="utf-8")
    policy = machine.default_typing_policy()
    policy["saved_text_scan"]["roots"] = [str(root)]
    policy["saved_text_scan"]["changed_within_sec"] = 3600
    monkeypatch.setattr(machine, "typing_policy", lambda write_latest=False: policy)

    result = machine.typing_saved_text_scan(write_latest=False)

    assert result["ok"] is True
    assert result["summary"]["events"] == 0
    assert any(item.get("reason") == "sensitive_path" for item in result["skips"])


def test_saved_text_scan_prime_state_writes_no_events(abyss_machine_module, tmp_path, monkeypatch) -> None:
    machine = abyss_machine_module
    root = tmp_path / "workspace"
    root.mkdir()
    note = root / "note.md"
    note.write_text("saved text scan priming probe", encoding="utf-8")
    policy = machine.default_typing_policy()
    policy["saved_text_scan"]["roots"] = [str(root)]
    policy["saved_text_scan"]["changed_within_sec"] = 3600
    monkeypatch.setattr(machine, "typing_policy", lambda write_latest=False: policy)

    result = machine.typing_saved_text_scan(write_latest=False, prime_state=True)

    assert result["ok"] is True
    assert result["summary"]["events"] == 0
    assert result["summary"]["primed"] == 1
