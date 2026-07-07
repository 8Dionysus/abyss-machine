from __future__ import annotations

from abyss_machine import cli
from abyss_machine import typing_shell_adapters


def _hook_text() -> str:
    return "\n".join(
        [
            "# Abyss typing committed shell-command adapter.",
            "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1",
            "_abyss_typing_preexec() {",
            '  printf "%s" "$1" | abyss-machine typing ingest --stdin --source zsh_preexec --context "shell_command cwd=$PWD hook=abyss-typing-zsh-v1" --json',
            "}",
            "# abyss-typing-zsh-v1",
        ]
    )


def test_zsh_hook_status_document_verifies_committed_command_contract() -> None:
    data = typing_shell_adapters.zsh_hook_status_document(
        generated_at="2026-06-30T12:34:56Z",
        hook_path="/home/user/.config/zsh/abyss-typing.zsh",
        hook_exists=True,
        hook_size_bytes=123,
        hook_text=_hook_text(),
        hook_read_error=None,
        zshrc_path="/home/user/.zshrc",
        zshrc_exists=True,
        zshrc_text="source $HOME/.config/zsh/abyss-typing.zsh\n",
        zshrc_read_error=None,
        function_probe={"ok": True, "returncode": 0, "stderr": ""},
        latest_selftest={"ok": True, "generated_at": "2026-06-30T12:30:00Z", "summary": {"event_detected": True}},
        latest_selftest_error=None,
        latest_event={"ok": True, "generated_at": "2026-06-30T12:33:00Z", "source_adapter": "zsh_preexec", "status": "captured"},
        schema_prefix="abyss_machine",
        version="0.1.0",
    )

    assert data["schema"] == "abyss_machine_typing_zsh_hook_status_v1"
    assert data["ok"] is True
    assert data["status"] == "ready"
    assert data["hook"]["missing_markers"] == []
    assert data["zshrc"]["sources_hook"] is True
    assert data["latest_selftest"]["event_detected"] is True
    assert data["policy"]["raw_keylogging"] is False
    assert data["policy"]["terminal_output_captured"] is False


def test_zsh_hook_function_probe_plan_builds_fakeable_command() -> None:
    missing_zsh = typing_shell_adapters.zsh_hook_function_probe_plan(
        hook_path="/tmp/abyss-typing.zsh",
        zsh_available=False,
        hook_exists=True,
    )
    plan = typing_shell_adapters.zsh_hook_function_probe_plan(
        hook_path="/tmp/abyss-typing.zsh",
        zsh_available=True,
        hook_exists=True,
    )

    assert missing_zsh == {"run": False, "result": {"ok": False, "returncode": 127, "error": "zsh not found"}}
    assert plan["run"] is True
    assert plan["command"][:4] == ["env", "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1", "zsh", "-fic"]
    assert "source /tmp/abyss-typing.zsh" in plan["command"][4]
    assert "typeset -f _abyss_typing_preexec" in plan["command"][4]
    assert plan["timeout_sec"] == 3.0


def test_zsh_hook_probe_event_from_records_projects_public_safe_event() -> None:
    plan = typing_shell_adapters.zsh_hook_selftest_plan(hook_path="/tmp/abyss-typing.zsh")
    record = {
        "event_id": "evt-zsh",
        "generated_at": "2026-06-30T12:35:00Z",
        "status": "captured",
        "source_adapter": "zsh_preexec",
        "capture_gate": {"decision": "allow_text"},
        "text": {"text_sha256": plan["probe"]["text_sha256"]},
        "causal_context": {
            "recipient": {"kind": "shell"},
            "where": {"project": {"id": "abyss-machine"}},
        },
    }

    event, errors = typing_shell_adapters.zsh_hook_probe_event_from_records(
        [{"source_adapter": "other"}, record],
        [{"warning": "parse"}],
        plan["probe"]["text_sha256"],
    )

    assert errors == [{"warning": "parse"}]
    assert event == {
        "event_id": "evt-zsh",
        "generated_at": "2026-06-30T12:35:00Z",
        "status": "captured",
        "source_adapter": "zsh_preexec",
        "capture_gate_decision": "allow_text",
        "recipient": "shell",
        "project": "abyss-machine",
    }


def test_zsh_hook_selftest_plan_and_document_pass_without_probe_text() -> None:
    plan = typing_shell_adapters.zsh_hook_selftest_plan(hook_path="/tmp/abyss-typing.zsh")
    event = {
        "event_id": "evt-zsh",
        "status": "captured",
        "source_adapter": "zsh_preexec",
        "capture_gate_decision": "allow_text",
    }

    data = typing_shell_adapters.zsh_hook_selftest_document(
        generated_at="2026-06-30T12:34:56Z",
        status_before={"ok": True, "status": "ready", "hook": {"exists": True}, "zshrc": {"sources_hook": True}},
        plan=plan,
        run_result={"ok": True, "returncode": 0, "stderr": ""},
        event=event,
        parse_errors=[],
        schema_prefix="abyss_machine",
        version="0.1.0",
    )

    assert plan["probe"]["text"] == "print abyss-zsh-hook-selftest"
    assert "_abyss_typing_preexec 'print abyss-zsh-hook-selftest'" in plan["command"][4]
    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["probe"] == {
        "source_adapter": "zsh_preexec",
        "text_sha256": plan["probe"]["text_sha256"],
        "text_length": len("print abyss-zsh-hook-selftest"),
        "text_omitted": True,
    }
    assert "text" not in data["probe"]
    assert data["policy"]["raw_keylogging"] is False


def test_cli_zsh_hook_status_binds_adapter_inputs(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    hook = tmp_path / "abyss-typing.zsh"
    zshrc = tmp_path / ".zshrc"
    hook.write_text(_hook_text(), encoding="utf-8")
    zshrc.write_text("source $HOME/.config/zsh/abyss-typing.zsh\n", encoding="utf-8")

    def fake_status(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "status": "ready"}

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-30T12:34:56Z")
    monkeypatch.setattr(cli, "TYPING_ZSH_HOOK_PATH", hook)
    monkeypatch.setattr(cli, "TYPING_ZSHRC_PATH", zshrc)
    monkeypatch.setattr(cli, "TYPING_ZSH_HOOK_SELFTEST_LATEST_PATH", tmp_path / "selftest.json")
    monkeypatch.setattr(cli, "typing_zsh_hook_function_probe", lambda: {"ok": True, "returncode": 0, "stderr": ""})
    monkeypatch.setattr(cli, "load_json_document", lambda _path: ({"ok": True, "summary": {"event_detected": True}}, None))
    monkeypatch.setattr(cli, "typing_latest", lambda: {"ok": True, "source_adapter": "zsh_preexec", "status": "captured"})
    monkeypatch.setattr(cli.typing_shell_adapters, "zsh_hook_status_document", fake_status)

    result = cli.typing_zsh_hook_status(write_latest=False)

    assert result == {"ok": True, "status": "ready"}
    assert captured["generated_at"] == "2026-06-30T12:34:56Z"
    assert captured["hook_path"] == hook
    assert captured["hook_exists"] is True
    assert captured["hook_size_bytes"] == hook.stat().st_size
    assert captured["hook_text"] == _hook_text()
    assert captured["zshrc_path"] == zshrc
    assert captured["zshrc_exists"] is True
    assert captured["zshrc_text"] == "source $HOME/.config/zsh/abyss-typing.zsh\n"
    assert captured["function_probe"] == {"ok": True, "returncode": 0, "stderr": ""}
    assert captured["latest_selftest"] == {"ok": True, "summary": {"event_detected": True}}
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION


def test_cli_zsh_hook_selftest_binds_adapter_plan_run_event_and_document(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    plan = {
        "probe": {"text_sha256": "sha256-fixture", "text_length": 12},
        "command": ["env", "ABYSS_TYPING_HOOK_DISABLE_REGISTER=1", "zsh", "-fic", "script"],
        "timeout_sec": 5.0,
    }

    def fake_document(**kwargs):
        captured["document_kwargs"] = kwargs
        return {"ok": True, "status": "passed"}

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-30T12:34:56Z")

    def fake_plan(**kwargs):
        captured["plan_kwargs"] = kwargs
        return plan

    def fake_run(command, timeout):
        captured["run"] = {"command": command, "timeout": timeout}
        return {"ok": True, "returncode": 0, "stderr": ""}

    monkeypatch.setattr(cli, "TYPING_ZSH_HOOK_PATH", tmp_path / "abyss-typing.zsh")
    monkeypatch.setattr(cli.typing_shell_adapters, "zsh_hook_selftest_plan", fake_plan)
    monkeypatch.setattr(cli.typing_shell_adapters, "zsh_hook_selftest_run_result", lambda raw: {"ok": raw["ok"], "returncode": raw["returncode"], "stderr": ""})
    monkeypatch.setattr(cli.typing_shell_adapters, "zsh_hook_selftest_document", fake_document)
    monkeypatch.setattr(cli, "typing_zsh_hook_status", lambda write_latest=False: {"ok": True, "status": "ready", "hook": {}, "zshrc": {}})
    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "typing_zsh_hook_find_probe_event", lambda text_sha256: ({"text_sha256": text_sha256}, []))

    result = cli.typing_zsh_hook_selftest(write_latest=False)

    assert result == {"ok": True, "status": "passed"}
    assert captured["plan_kwargs"] == {"hook_path": tmp_path / "abyss-typing.zsh"}
    assert captured["run"] == {"command": plan["command"], "timeout": 5.0}
    assert captured["document_kwargs"]["generated_at"] == "2026-06-30T12:34:56Z"
    assert captured["document_kwargs"]["status_before"] == {"ok": True, "status": "ready", "hook": {}, "zshrc": {}}
    assert captured["document_kwargs"]["plan"] is plan
    assert captured["document_kwargs"]["run_result"] == {"ok": True, "returncode": 0, "stderr": ""}
    assert captured["document_kwargs"]["event"] == {"text_sha256": "sha256-fixture"}
    assert captured["document_kwargs"]["parse_errors"] == []
    assert captured["document_kwargs"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["document_kwargs"]["version"] == cli.VERSION
