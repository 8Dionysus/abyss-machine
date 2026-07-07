from __future__ import annotations

import signal
from pathlib import Path

from abyss_machine import cli
from abyss_machine import typing_editor_adapters


def test_editor_extension_selftest_plan_builds_committed_text_ingest() -> None:
    plan = typing_editor_adapters.editor_extension_selftest_plan(
        generated_at="2026-06-30T12:34:56Z",
        pid=12345,
        extension_id="fixture.extension",
    )

    assert plan["run_id"] == "2026063012345612345"
    assert plan["probe"]["text"] == "abyss editor extension selftest 2026063012345612345"
    assert plan["probe"]["text_length"] == len(plan["probe"]["text"])
    assert plan["probe"]["path"] == "/srv/work/abyss-machine/editor-extension-selftest.txt"
    assert plan["ingest"]["source"] == "editor_extension_explicit"
    assert plan["ingest"]["app"] == "code"
    assert plan["ingest"]["window_title"] == "editor-extension-selftest.txt"
    assert plan["ingest"]["skip_duplicate"] is True
    assert plan["ingest"]["metadata"]["editor"] == {
        "extension_id": "fixture.extension",
        "selftest": True,
        "ui_callback_proven": False,
    }


def test_editor_extension_probe_event_from_records_projects_public_safe_event() -> None:
    plan = typing_editor_adapters.editor_extension_selftest_plan(
        generated_at="2026-06-30T12:34:56Z",
        pid=12345,
        extension_id="fixture.extension",
    )
    record = {
        "event_id": "evt-1",
        "generated_at": "2026-06-30T12:35:00Z",
        "status": "captured",
        "source_adapter": "editor_extension_explicit",
        "capture_gate": {"decision": "allow_text", "confidence": "editor_path_allowed"},
        "text": {
            "text_sha256": plan["probe"]["text_sha256"],
            "text_length": plan["probe"]["text_length"],
            "text_chars_stored": plan["probe"]["text_length"],
        },
        "causal_context": {
            "recipient": {"kind": "editor_extension"},
            "where": {"path": plan["probe"]["path"]},
            "task": {"kind": "selftest"},
        },
    }

    event, errors = typing_editor_adapters.editor_extension_probe_event_from_records(
        [{"source_adapter": "other"}, record],
        [{"warning": "parse"}],
        plan["probe"]["text_sha256"],
    )

    assert errors == [{"warning": "parse"}]
    assert event == {
        "event_id": "evt-1",
        "generated_at": "2026-06-30T12:35:00Z",
        "status": "captured",
        "source_adapter": "editor_extension_explicit",
        "capture_gate_decision": "allow_text",
        "capture_gate_confidence": "editor_path_allowed",
        "text_length": plan["probe"]["text_length"],
        "text_chars_stored": plan["probe"]["text_length"],
        "text_sha256": plan["probe"]["text_sha256"],
        "recipient": {"kind": "editor_extension"},
        "where": {"path": plan["probe"]["path"]},
        "task": {"kind": "selftest"},
    }


def test_editor_extension_selftest_document_passes_and_omits_probe_text() -> None:
    plan = typing_editor_adapters.editor_extension_selftest_plan(
        generated_at="2026-06-30T12:34:56Z",
        pid=12345,
        extension_id="fixture.extension",
    )
    event = {
        "status": "captured",
        "source_adapter": "editor_extension_explicit",
        "capture_gate_decision": "allow_text",
        "capture_gate_confidence": "editor_path_allowed",
        "text_sha256": plan["probe"]["text_sha256"],
        "text_chars_stored": plan["probe"]["text_length"],
        "recipient": {"kind": "editor_extension"},
    }
    ingest = {
        "ok": True,
        "event_id": "evt-1",
        "status": "captured",
        "source_adapter": "editor_extension_explicit",
        "capture_gate": {"decision": "allow_text", "confidence": "editor_path_allowed"},
        "text": {"text_length": plan["probe"]["text_length"], "text_chars_stored": plan["probe"]["text_length"]},
        "causal_context": {"recipient": {"kind": "editor_extension"}},
    }

    data = typing_editor_adapters.editor_extension_selftest_document(
        plan=plan,
        ingest=ingest,
        event=event,
        parse_errors=[],
        latest_status={"ok": True, "status": "activated", "generated_at": "2026-06-30T12:33:00Z"},
        latest_status_error=None,
        schema_prefix="abyss_machine",
        version="0.1.0",
        generated_at="2026-06-30T12:34:56Z",
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["probe"] == {
        "text_sha256": plan["probe"]["text_sha256"],
        "text_length": plan["probe"]["text_length"],
        "text_omitted": True,
        "path": plan["probe"]["path"],
    }
    assert "text" not in data["probe"]
    assert data["latest_extension_status"]["status"] == "activated"
    assert data["ingest"]["capture_gate_decision"] == "allow_text"
    assert data["policy"]["raw_keylogging"] is False


def test_editor_extension_latest_status_document_ready_and_failure_precedence(tmp_path) -> None:
    latest = {
        "ok": True,
        "status": "activated",
        "generated_at": "2026-06-30T12:00:00Z",
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
    }
    selftest = {
        "ok": True,
        "status": "passed",
        "generated_at": "2026-06-30T12:01:00Z",
        "event": {
            "source_adapter": "editor_extension_explicit",
            "status": "captured",
            "capture_gate_decision": "allow_text",
            "capture_gate_confidence": "editor_path_allowed",
            "text_length": 5,
            "text_chars_stored": 5,
        },
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "network_access": False},
    }
    callback = {
        "ok": True,
        "status": "passed",
        "generated_at": "2026-06-30T12:02:00Z",
        "event": {
            "source_adapter": "editor_extension_explicit",
            "status": "captured",
            "capture_gate_decision": "allow_text",
            "capture_gate_confidence": "editor_path_allowed",
            "text_length": 5,
            "text_chars_stored": 5,
        },
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "live_vscode_extension_callback": True},
    }

    ready = typing_editor_adapters.editor_extension_latest_status_document(
        latest=latest,
        latest_error=None,
        selftest=selftest,
        selftest_error=None,
        callback=callback,
        callback_error=None,
        extension_path_exists=True,
        max_age_sec=120.0,
        generated_at="2026-06-30T12:03:00Z",
        age_seconds_from_iso=lambda value: {"2026-06-30T12:00:00Z": 180.0, "2026-06-30T12:01:00Z": 60.0, "2026-06-30T12:02:00Z": 30.0}.get(value),
        schema_prefix="abyss_machine",
        version="0.1.0",
    )

    missing = typing_editor_adapters.editor_extension_latest_status_document(
        latest=latest,
        latest_error=None,
        selftest=selftest,
        selftest_error=None,
        callback=callback,
        callback_error=None,
        extension_path_exists=False,
        max_age_sec=120.0,
        generated_at="2026-06-30T12:03:00Z",
        age_seconds_from_iso=lambda _value: 1.0,
        schema_prefix="abyss_machine",
        version="0.1.0",
    )

    assert ready["ok"] is True
    assert ready["status"] == "ready"
    assert ready["summary"]["activation_ok"] is True
    assert ready["summary"]["proof_age_sec"] == 60.0
    assert ready["policy"]["live_vscode_extension_callback"] is True
    assert missing["ok"] is False
    assert missing["status"] == "extension_missing"


def test_editor_callback_selftest_reports_missing_code_without_live_ports(tmp_path) -> None:
    data = typing_editor_adapters.editor_callback_selftest_document(
        generated_at="2026-06-30T12:34:56Z",
        pid=12345,
        schema_prefix="abyss_machine",
        version="0.1.0",
        code_bin=None,
        file_path=tmp_path / "target.txt",
        tmp_root=tmp_path / "runtime",
        vscode_extension_path=tmp_path / "extension",
        base_env={},
        write_text=lambda *_args: (_ for _ in ()).throw(AssertionError("write should not run")),
        find_event=lambda *_args: (_ for _ in ()).throw(AssertionError("find should not run")),
        terminate_processes=lambda *_args: (_ for _ in ()).throw(AssertionError("cleanup should not run")),
    )

    assert data == {
        "schema": "abyss_machine_typing_editor_callback_selftest_v1",
        "version": "0.1.0",
        "generated_at": "2026-06-30T12:34:56Z",
        "ok": False,
        "status": "code_missing",
        "source_adapter": "editor_extension_explicit",
        "error": "code executable not found",
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
    }


def test_editor_callback_selftest_runs_vscode_route_through_fakeable_ports(tmp_path) -> None:
    generated_at = "2026-06-30T12:34:56Z"
    probe = typing_editor_adapters.editor_callback_selftest_probe(generated_at, 12345)
    calls: dict[str, object] = {}

    class FakeProc:
        pid = 4242
        returncode = 0

        def poll(self):
            return None

        def communicate(self, timeout):
            calls["communicate_timeout"] = timeout
            return "stdout tail", "stderr tail"

    def fake_popen(command, **kwargs):
        calls["command"] = command
        calls["env"] = kwargs["env"]
        calls["stdout"] = kwargs["stdout"]
        calls["stderr"] = kwargs["stderr"]
        calls["text"] = kwargs["text"]
        calls["preexec_fn"] = kwargs["preexec_fn"]
        return FakeProc()

    def fake_write(path: Path, text: str, mode: int):
        calls["write"] = {"path": path, "text": text, "mode": mode}
        return None

    def fake_find(text_sha256: str, limit: int):
        calls["find"] = {"text_sha256": text_sha256, "limit": limit}
        return {
            "status": "captured",
            "source_adapter": "editor_extension_explicit",
            "capture_gate_decision": "allow_text",
            "capture_gate_confidence": "editor_path_allowed",
            "text_sha256": probe["text_sha256"],
            "text_chars_stored": probe["text_length"],
            "recipient": {"kind": "editor_extension"},
        }, []

    def fake_cleanup(token: str):
        calls["cleanup_token"] = token
        return [{"phase": "cleanup", "ok": True}]

    def fake_getpgid(pid: int) -> int:
        calls["getpgid_pid"] = pid
        return 9000

    data = typing_editor_adapters.editor_callback_selftest_document(
        generated_at=generated_at,
        pid=12345,
        schema_prefix="abyss_machine",
        version="0.1.0",
        code_bin="/usr/bin/code",
        file_path=tmp_path / "target.txt",
        tmp_root=tmp_path / "runtime",
        vscode_extension_path=tmp_path / "extension",
        base_env={"BASE": "1"},
        write_text=fake_write,
        find_event=fake_find,
        terminate_processes=fake_cleanup,
        popen=fake_popen,
        monotonic=iter([10.0, 10.5]).__next__,
        sleep=lambda _seconds: calls.setdefault("slept", True),
        killpg=lambda pgid, sig: calls.setdefault("killpg", {"pgid": pgid, "sig": sig}),
        getpgid=fake_getpgid,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["probe"] == {
        "text_sha256": probe["text_sha256"],
        "text_length": probe["text_length"],
        "text_omitted": True,
    }
    assert data["code"]["binary"] == "/usr/bin/code"
    assert data["code"]["returncode"] == 0
    assert data["code"]["stdout_tail"] == "stdout tail"
    assert data["code"]["stderr_tail"] == "stderr tail"
    assert data["code"]["cleanup_actions"] == [{"phase": "cleanup", "ok": True}]
    assert calls["command"] == [
        "/usr/bin/code",
        "--new-window",
        "--user-data-dir",
        str(tmp_path / "runtime" / "user-data"),
        "--extensionDevelopmentPath",
        str(tmp_path / "extension"),
        "--wait",
        str(tmp_path / "target.txt"),
    ]
    assert calls["env"]["BASE"] == "1"
    assert calls["env"]["ABYSS_TYPING_EDITOR_CALLBACK_SELFTEST_PATH"] == str(tmp_path / "target.txt")
    assert calls["env"]["ABYSS_TYPING_EDITOR_CALLBACK_SELFTEST_TEXT"] == probe["text"]
    assert calls["write"] == {"path": tmp_path / "target.txt", "text": "", "mode": 0o664}
    assert calls["find"] == {"text_sha256": probe["text_sha256"], "limit": 520}
    assert calls["killpg"] == {"pgid": 9000, "sig": signal.SIGTERM}
    assert calls["getpgid_pid"] == 4242
    assert calls["cleanup_token"] == str(tmp_path / "runtime" / "user-data")


def test_editor_callback_selftest_reports_runtime_errors_and_cleans_up(tmp_path) -> None:
    data = typing_editor_adapters.editor_callback_selftest_document(
        generated_at="2026-06-30T12:34:56Z",
        pid=12345,
        schema_prefix="abyss_machine",
        version="0.1.0",
        code_bin="/usr/bin/code",
        file_path=tmp_path / "target.txt",
        tmp_root=tmp_path / "runtime",
        vscode_extension_path=tmp_path / "extension",
        base_env={},
        write_text=lambda *_args: {"path": "target.txt", "error": "write failed"},
        find_event=lambda *_args: (None, []),
        terminate_processes=lambda token: [{"phase": "cleanup", "token": token, "ok": True}],
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("cannot launch code")),
        monotonic=iter([1.0, 2.0]).__next__,
    )

    assert data["ok"] is False
    assert data["status"] == "failed"
    assert data["event"] is None
    assert data["errors"] == [
        {"path": "target.txt", "error": "write failed"},
        {"error": "RuntimeError('cannot launch code')"},
    ]
    assert data["code"]["cleanup_actions"] == [{"phase": "cleanup", "token": str(tmp_path / "runtime" / "user-data"), "ok": True}]


def test_cli_editor_callback_selftest_binds_adapter_ports_and_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    target_file = tmp_path / "callback.txt"
    tmp_root = tmp_path / "runtime"
    extension_path = tmp_path / "extension"

    def fake_document(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "status": "passed"}

    def fake_store(data, write_latest):
        captured["store"] = {"data": data, "write_latest": write_latest}
        return {"stored": data, "write_latest": write_latest}

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-30T12:34:56Z")
    monkeypatch.setattr(cli.os, "getpid", lambda: 12345)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/code" if name == "code" else None)
    monkeypatch.setattr(cli, "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_FILE", target_file)
    monkeypatch.setattr(cli, "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_TMP_ROOT", tmp_root)
    monkeypatch.setattr(cli, "TYPING_VSCODE_EXTENSION_PATH", extension_path)
    monkeypatch.setattr(cli.typing_editor_adapters, "editor_callback_selftest_document", fake_document)
    monkeypatch.setattr(cli, "typing_editor_callback_selftest_store", fake_store)

    result = cli.typing_editor_callback_selftest(write_latest=False)

    assert result == {"stored": {"ok": True, "status": "passed"}, "write_latest": False}
    assert captured["generated_at"] == "2026-06-30T12:34:56Z"
    assert captured["pid"] == 12345
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
    assert captured["code_bin"] == "/usr/bin/code"
    assert captured["file_path"] == target_file
    assert captured["tmp_root"] == tmp_root
    assert captured["vscode_extension_path"] == extension_path
    assert captured["base_env"] is cli.os.environ
    assert captured["write_text"] is cli.safe_atomic_write_text
    assert captured["find_event"] is cli.typing_editor_extension_find_probe_event
    assert captured["terminate_processes"] is cli.typing_terminate_processes_with_arg_token
    assert captured["store"] == {"data": {"ok": True, "status": "passed"}, "write_latest": False}


def test_cli_editor_extension_selftest_binds_adapter_plan_ingest_and_store(monkeypatch) -> None:
    captured: dict[str, object] = {}
    plan = {
        "probe": {"text_sha256": "sha256-fixture"},
        "ingest": {
            "text": "fixture text",
            "source": "editor_extension_explicit",
            "app": "code",
            "window_title": "fixture.txt",
            "context": "editor_extension selftest=true",
            "skip_duplicate": True,
            "metadata": {"editor": {"selftest": True}},
        },
    }

    def fake_plan(**kwargs):
        captured["plan_kwargs"] = kwargs
        return plan

    def fake_ingest(**kwargs):
        captured["ingest_kwargs"] = kwargs
        return {"ok": True, "event_id": "evt-1"}

    def fake_document(**kwargs):
        captured["document_kwargs"] = kwargs
        return {"ok": True, "status": "passed"}

    def fake_store(data, write_latest):
        captured["store"] = {"data": data, "write_latest": write_latest}
        return {"stored": data, "write_latest": write_latest}

    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-30T12:34:56Z")
    monkeypatch.setattr(cli.os, "getpid", lambda: 12345)
    monkeypatch.setattr(cli, "load_json_document", lambda path: ({"ok": True, "status": "activated"}, None))
    monkeypatch.setattr(cli.typing_editor_adapters, "editor_extension_selftest_plan", fake_plan)
    monkeypatch.setattr(cli.typing_editor_adapters, "editor_extension_selftest_document", fake_document)
    monkeypatch.setattr(cli, "typing_ingest", fake_ingest)
    monkeypatch.setattr(cli, "typing_editor_extension_find_probe_event", lambda text_sha256: ({"text_sha256": text_sha256}, []))
    monkeypatch.setattr(cli, "typing_editor_extension_selftest_store", fake_store)

    result = cli.typing_editor_extension_selftest(write_latest=False)

    assert result == {"stored": {"ok": True, "status": "passed"}, "write_latest": False}
    assert captured["plan_kwargs"] == {
        "generated_at": "2026-06-30T12:34:56Z",
        "pid": 12345,
        "extension_id": cli.TYPING_VSCODE_EXTENSION_ID,
    }
    assert captured["ingest_kwargs"] == {**plan["ingest"], "write_latest": False}
    assert captured["document_kwargs"]["plan"] is plan
    assert captured["document_kwargs"]["ingest"] == {"ok": True, "event_id": "evt-1"}
    assert captured["document_kwargs"]["event"] == {"text_sha256": "sha256-fixture"}
    assert captured["document_kwargs"]["parse_errors"] == []
    assert captured["document_kwargs"]["latest_status"] == {"ok": True, "status": "activated"}
    assert captured["document_kwargs"]["latest_status_error"] is None
    assert captured["document_kwargs"]["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["document_kwargs"]["version"] == cli.VERSION
    assert captured["document_kwargs"]["generated_at"] == "2026-06-30T12:34:56Z"


def test_cli_editor_extension_latest_status_binds_adapter_inputs(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    latest_path = tmp_path / "latest.json"
    selftest_path = tmp_path / "selftest.json"
    callback_path = tmp_path / "callback.json"
    extension_path = tmp_path / "extension"

    def fake_load(path):
        mapping = {
            latest_path: ({"status": "activated"}, None),
            selftest_path: ({"status": "passed"}, None),
            callback_path: ({"status": "passed"}, "callback warning"),
        }
        return mapping[path]

    def fake_status(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "status": "ready"}

    monkeypatch.setattr(cli, "TYPING_EDITOR_EXTENSION_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "TYPING_EDITOR_EXTENSION_SELFTEST_LATEST_PATH", selftest_path)
    monkeypatch.setattr(cli, "TYPING_EDITOR_EXTENSION_CALLBACK_SELFTEST_LATEST_PATH", callback_path)
    monkeypatch.setattr(cli, "TYPING_VSCODE_EXTENSION_PATH", extension_path)
    monkeypatch.setattr(cli, "load_json_document", fake_load)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-30T12:34:56Z")
    monkeypatch.setattr(cli.typing_editor_adapters, "editor_extension_latest_status_document", fake_status)

    result = cli.typing_editor_extension_latest_status(max_age_sec=42.0)

    assert result == {"ok": True, "status": "ready"}
    assert captured["latest"] == {"status": "activated"}
    assert captured["latest_error"] is None
    assert captured["selftest"] == {"status": "passed"}
    assert captured["selftest_error"] is None
    assert captured["callback"] == {"status": "passed"}
    assert captured["callback_error"] == "callback warning"
    assert captured["extension_path_exists"] is False
    assert captured["max_age_sec"] == 42.0
    assert captured["generated_at"] == "2026-06-30T12:34:56Z"
    assert captured["age_seconds_from_iso"] is cli.age_seconds_from_iso
    assert captured["schema_prefix"] == cli.SCHEMA_PREFIX
    assert captured["version"] == cli.VERSION
