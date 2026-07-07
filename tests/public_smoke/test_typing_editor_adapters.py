from __future__ import annotations

import signal
from pathlib import Path

from abyss_machine import cli
from abyss_machine import typing_editor_adapters


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
