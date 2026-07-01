from __future__ import annotations

import hashlib
import io
import struct

import pytest

from abyss_machine import cli
from abyss_machine import typing_browser_adapters


def test_firefox_extension_profiles_parse_relative_and_absolute_paths(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=abc.default-release",
            "Default=1",
            "",
            "[Profile1]",
            "Name=work",
            "IsRelative=0",
            "Path=/srv/firefox/work",
            "Default=0",
        ]),
        encoding="utf-8",
    )

    profiles = typing_browser_adapters.firefox_extension_profiles(
        profiles_ini,
        extension_id="fixture@example.test",
    )

    assert profiles == [
        {
            "name": "default-release",
            "path": str(tmp_path / "abc.default-release"),
            "default": True,
            "extensions_json": str(tmp_path / "abc.default-release" / "extensions.json"),
            "sideload_xpi": str(tmp_path / "abc.default-release" / "extensions" / "fixture@example.test.xpi"),
        },
        {
            "name": "work",
            "path": "/srv/firefox/work",
            "default": False,
            "extensions_json": "/srv/firefox/work/extensions.json",
            "sideload_xpi": "/srv/firefox/work/extensions/fixture@example.test.xpi",
        },
    ]


def test_firefox_release_profile_selection_order_is_public_safe(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Install123]",
            "Default=custom.profile",
            "",
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=default-release.profile",
            "Default=1",
            "",
            "[Profile1]",
            "Name=custom",
            "IsRelative=1",
            "Path=custom.profile",
            "Default=0",
        ]),
        encoding="utf-8",
    )

    selected = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )

    assert selected is not None
    assert selected["name"] == "custom"
    assert selected["selection"] == "install_default"
    assert selected["path"] == str(tmp_path / "custom.profile")


def test_firefox_release_profile_falls_back_to_named_default_then_profile_default(tmp_path) -> None:
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=default-release",
            "IsRelative=1",
            "Path=release.profile",
            "Default=0",
            "",
            "[Profile1]",
            "Name=other",
            "IsRelative=1",
            "Path=other.profile",
            "Default=1",
        ]),
        encoding="utf-8",
    )

    selected = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )
    assert selected is not None
    assert selected["name"] == "default-release"
    assert selected["selection"] == "named_default_release"

    profiles_ini.write_text(
        "\n".join([
            "[Profile0]",
            "Name=plain",
            "IsRelative=1",
            "Path=plain.profile",
            "Default=1",
        ]),
        encoding="utf-8",
    )
    fallback = typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    )
    assert fallback is not None
    assert fallback["name"] == "plain"
    assert fallback["selection"] == "profile_default"


def test_firefox_profiles_missing_file_preserves_empty_behavior(tmp_path) -> None:
    profiles_ini = tmp_path / "missing.ini"

    assert typing_browser_adapters.firefox_extension_profiles(
        profiles_ini,
        extension_id="fixture@example.test",
    ) == []
    assert typing_browser_adapters.firefox_release_profile(
        profiles_ini,
        extension_id="fixture@example.test",
    ) is None


def test_browser_extension_plan_and_status_document_are_public_safe() -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "browser_name": "firefox",
        "title": "Writing",
        "url": "https://example.test/write",
        "text": "synthetic browser text",
        "field": {"safe": True, "kind": "textarea", "type": "textarea"},
    }

    plan = typing_browser_adapters.browser_extension_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_extension_explicit"
    assert plan["ingest"]["text"] == "synthetic browser text"
    assert plan["ingest"]["source"] == "browser_extension_explicit"
    assert plan["ingest"]["app"] == "firefox"
    assert "event_kind=committed_text" in plan["ingest"]["context"]
    assert "field_safe=True" in plan["ingest"]["context"]
    assert plan["ingest"]["metadata"]["browser"]["key_events_captured"] is False

    status = typing_browser_adapters.browser_extension_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-browser",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": 22, "text_chars_stored": 22},
            "duplicate": False,
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert status["ok"] is True
    assert status["event"]["event_id"] == "evt-browser"
    assert status["event"]["capture_gate_confidence"] == "browser_url_and_field_allowed"
    assert status["policy"]["raw_keylogging"] is False
    assert "text" not in status["event"]


def test_browser_ai_transcript_plan_cleans_text_and_preserves_counterpart_metadata() -> None:
    message = {
        "schema": "abyss_machine_browser_ai_transcript_message_v1",
        "event_kind": "ai_transcript_message",
        "browser_name": "firefox",
        "title": "ChatGPT",
        "url": "https://chatgpt.com/c/fixture",
        "text": "ChatGPT said hello\nShow more",
        "browser": {"transcript_safe": True},
        "ai_transcript": {"safe": True, "message_role": "bubble", "message_index": "3", "partial": False},
    }

    plan = typing_browser_adapters.browser_ai_transcript_ingest_plan(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
    )

    assert plan["valid"] is True
    assert plan["source_adapter"] == "browser_ai_transcript"
    assert plan["ingest"]["text"] == "ChatGPT said hello"
    assert "transcript_safe=True" in plan["ingest"]["context"]
    assert "message_role=assistant" in plan["ingest"]["context"]
    assert plan["text_cleanup"]["removed_line_count"] == 1
    assert plan["transcript_meta"]["message_role"] == "assistant"
    assert plan["transcript_meta"]["page_identity"]["entity_id"] == "ai:openai:chatgpt"

    status = typing_browser_adapters.browser_ai_transcript_status_document(
        plan,
        {
            "ok": True,
            "event_id": "evt-ai",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "source_adapter": "browser_ai_transcript",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_ai_transcript_known_ai_page_allowed"},
            "text": {"text_length": 18, "text_chars_stored": 18, "truncated": False},
            "causal_context": {
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
                "where": {"context_anchor": {"kind": "ai_chat"}, "interaction": {"id": "fixture"}},
            },
        },
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:02Z",
    )

    assert status["schema"] == "abyss_machine_typing_browser_ai_transcript_status_v1"
    assert status["event"]["message_role"] == "assistant"
    assert status["event"]["message_index"] == 3
    assert status["event"]["recipient"]["id"] == "ai:openai:chatgpt"
    assert status["policy"]["known_ai_counterpart_required"] is True


def test_browser_selftest_documents_and_native_host_response_envelopes() -> None:
    run_id = typing_browser_adapters.browser_selftest_run_id("fixture-seed")
    safe_message, sensitive_message = typing_browser_adapters.browser_extension_selftest_messages(run_id)
    ai_message, ai_sensitive_message = typing_browser_adapters.browser_ai_transcript_selftest_messages(run_id)

    assert len(run_id) == 12
    assert safe_message["text"].endswith(run_id)
    assert sensitive_message["url"] == "https://example.com/login"
    assert typing_browser_adapters.native_host_message_route(safe_message) == "browser_extension_explicit"
    assert typing_browser_adapters.native_host_message_route(ai_message) == "browser_ai_transcript"
    assert typing_browser_adapters.native_host_message_route(ai_sensitive_message) == "browser_ai_transcript"

    safe = {
        "ok": True,
        "event": {
            "source_adapter": "browser_ai_transcript",
            "status": "captured",
            "capture_gate_decision": "allow_text",
            "recipient": {"id": "ai:google:gemini"},
            "message_role": "assistant",
        },
    }
    sensitive = {"ok": True, "event": {"capture_gate_decision": "metadata_only", "text_chars_stored": 0}}
    selftest = typing_browser_adapters.browser_ai_transcript_selftest_document(
        safe=safe,
        sensitive=sensitive,
        schema_prefix="abyss_machine",
        version="fixture-version",
        generated_at="2026-06-27T00:00:00Z",
        test_run_id=run_id,
    )
    response = typing_browser_adapters.native_host_response({"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}})
    error = typing_browser_adapters.native_host_error_response(ValueError("boom"))

    assert selftest["ok"] is True
    assert selftest["status"] == "passed"
    assert response == {"ok": True, "status": "sent", "event": {"event_id": "evt"}, "policy": {"raw_keylogging": False}}
    assert error["ok"] is False
    assert error["status"] == "native_host_error"
    assert error["policy"]["automatic_action"] is False


def test_browser_selftest_store_outputs_routes_primary_secondary_and_index(tmp_path) -> None:
    data = {"schema": "abyss_machine_typing_browser_atspi_selftest_v1", "ok": True}
    calls = []

    def write_latest_history(document, latest_path, history_root, mode):
        calls.append(("history", latest_path.name, history_root.name, mode, document is data))
        if latest_path.name == "release-latest.json":
            return [{"path": str(latest_path), "error": "boom"}]
        return []

    def write_json(path, document, mode):
        calls.append(("index", path.name, document.get("schema"), mode))
        return None

    result = typing_browser_adapters.browser_selftest_store_outputs(
        data,
        write_latest=True,
        primary_latest_path=tmp_path / "primary-latest.json",
        primary_history_root=tmp_path / "primary",
        secondary_latest_path=tmp_path / "release-latest.json",
        secondary_history_root=tmp_path / "release",
        secondary_enabled=True,
        index_path=tmp_path / "index.json",
        write_latest_history=write_latest_history,
        write_json=write_json,
        index_document=lambda: {"schema": "abyss_machine_typing_index_v1"},
    )

    assert result is data
    assert calls == [
        ("history", "primary-latest.json", "primary", 0o664, True),
        ("history", "release-latest.json", "release", 0o664, True),
        ("index", "index.json", "abyss_machine_typing_index_v1", 0o664),
    ]
    assert result["ok"] is False
    assert result["write_errors"] == [{"path": str(tmp_path / "release-latest.json"), "error": "boom"}]

    no_write = {"ok": True}
    assert typing_browser_adapters.browser_selftest_store_outputs(
        no_write,
        write_latest=False,
        primary_latest_path=tmp_path / "unused.json",
        primary_history_root=tmp_path / "unused",
        index_path=tmp_path / "unused-index.json",
        write_latest_history=lambda *_args: (_ for _ in ()).throw(AssertionError("write should not run")),
        write_json=lambda *_args: (_ for _ in ()).throw(AssertionError("index should not run")),
        index_document=lambda: (_ for _ in ()).throw(AssertionError("index document should not run")),
    ) is no_write


def test_native_host_transport_reads_and_writes_length_prefixed_json() -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "text": "synthetic browser text",
    }
    framed = typing_browser_adapters.native_host_encode_response_frame(message)
    decoded = typing_browser_adapters.native_host_read_message(io.BytesIO(framed))
    empty = typing_browser_adapters.native_host_read_message(io.BytesIO(b""))

    assert decoded == message
    assert empty is None

    out = io.BytesIO()
    typing_browser_adapters.native_host_write_response(out, {"ok": True, "status": "captured", "note": "synthetic"})
    raw = out.getvalue()
    length = struct.unpack("<I", raw[:4])[0]
    assert length == len(raw[4:])
    assert raw[4:] == b'{"ok":true,"status":"captured","note":"synthetic"}'


def test_cli_native_host_transport_binds_to_standard_buffers(monkeypatch) -> None:
    message = {
        "schema": "abyss_machine_browser_extension_message_v1",
        "event_kind": "committed_text",
        "text": "synthetic browser text",
    }
    stdin_buffer = io.BytesIO(typing_browser_adapters.native_host_encode_response_frame(message))
    stdout_buffer = io.BytesIO()

    class FakeStdin:
        buffer = stdin_buffer

    class FakeStdout:
        buffer = stdout_buffer

    monkeypatch.setattr(cli.sys, "stdin", FakeStdin())
    monkeypatch.setattr(cli.sys, "stdout", FakeStdout())

    assert cli.typing_browser_native_host_read_message() == message
    cli.typing_browser_native_host_write_response({"ok": True, "status": "captured"})

    raw = stdout_buffer.getvalue()
    assert struct.unpack("<I", raw[:4])[0] == len(raw[4:])
    assert raw[4:] == b'{"ok":true,"status":"captured"}'


def test_native_host_transport_rejects_malformed_frames() -> None:
    with pytest.raises(ValueError, match="header"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(b"\x01\x02"))
    with pytest.raises(ValueError, match="out of range"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 0)))
    with pytest.raises(ValueError, match="out of range"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 1024 * 1024 + 1)))
    with pytest.raises(ValueError, match="truncated"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 5) + b"{}"))
    with pytest.raises(ValueError, match="JSON object"):
        typing_browser_adapters.native_host_read_message(io.BytesIO(struct.pack("<I", 2) + b"[]"))


def test_browser_webextension_base_command_selects_path_or_offline_npm(tmp_path) -> None:
    direct_command, direct_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: "/usr/bin/web-ext" if name == "web-ext" else None,
    )
    npm_command, npm_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: "/usr/bin/npm" if name == "npm" else None,
    )
    missing_command, missing_info = typing_browser_adapters.browser_webextension_base_command(
        npm_cache=tmp_path / "npm",
        which=lambda name: None,
    )

    assert direct_command == ["/usr/bin/web-ext"]
    assert direct_info["route"] == "path"
    assert npm_command[:5] == ["/usr/bin/npm", "exec", "--offline", "--yes", "--package"]
    assert npm_info["route"] == "npm_exec_offline"
    assert npm_info["npm_cache"] == str(tmp_path / "npm")
    assert missing_command == []
    assert missing_info["route"] == "missing"


def test_browser_webextension_selftest_reports_missing_runtime_without_probe(tmp_path) -> None:
    called = {"probe": False}

    def forbidden_probe(_text_sha: str, _limit: int):
        called["probe"] = True
        return None, []

    firefox_missing = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=forbidden_probe,
        which=lambda name: None,
    )
    web_ext_missing = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=forbidden_probe,
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
    )

    assert firefox_missing["status"] == "firefox_missing"
    assert firefox_missing["source_adapter"] == "browser_extension_explicit"
    assert web_ext_missing["status"] == "web_ext_missing"
    assert web_ext_missing["policy"]["raw_keylogging"] is False
    assert called["probe"] is False


def test_browser_webextension_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    probe_text = f"abyss browser webextension committed text {run_id}"
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    commands: list[tuple[list[str], float, dict[str, str] | None]] = []
    launched: list[list[str]] = []
    cleanup_tokens: list[str] = []

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "web-ext stdout", "web-ext stderr"

    def fake_which(name: str) -> str | None:
        return {
            "firefox": "/usr/bin/firefox",
            "web-ext": "/usr/bin/web-ext",
        }.get(name)

    def fake_run(cmd: list[str], timeout: float, env: dict[str, str] | None) -> dict[str, object]:
        commands.append((cmd, timeout, env))
        return {"ok": True, "returncode": 0, "stdout": "8.0.0", "stderr": ""}

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_find_probe_event(text_sha256: str, limit: int):
        assert text_sha256 == probe_hash
        assert limit == 520
        return {
            "event_id": "evt-webextension",
            "generated_at": generated_at,
            "status": "captured",
            "source_adapter": "browser_extension_explicit",
            "capture_gate_decision": "allow_text",
            "capture_gate_confidence": "browser_url_and_field_allowed",
            "text_length": len(probe_text),
            "text_chars_stored": len(probe_text),
            "text_sha256": probe_hash,
            "recipient": {"kind": "browser_extension"},
        }, []

    def fake_terminate(token: str) -> list[dict[str, object]]:
        cleanup_tokens.append(token)
        return [{"token": token, "ok": True}]

    data = typing_browser_adapters.browser_webextension_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        extension_root=tmp_path / "extension",
        npm_cache=tmp_path / "npm",
        schema_prefix="abyss_machine",
        version="fixture-version",
        find_probe_event=fake_find_probe_event,
        which=fake_which,
        run_command=fake_run,
        process_factory=fake_process_factory,
        terminate_processes=fake_terminate,
        sleep=lambda _seconds: None,
        deadline_seconds=1.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["probe"] == {
        "text_sha256": probe_hash,
        "text_length": len(probe_text),
        "text_omitted": True,
    }
    assert data["event"]["event_id"] == "evt-webextension"
    assert "text" not in data["event"]
    assert data["policy"]["temporary_firefox_profile"] is True
    assert data["policy"]["release_profile_mutated"] is False
    assert data["policy"]["loopback_http_only"] is True
    assert data["web_ext"]["loader"]["route"] == "path"
    assert data["web_ext"]["version"] == "8.0.0"
    assert data["web_ext"]["cleanup_actions"] == [{"token": str(tmp_path / "tmp"), "ok": True}]
    assert commands[0][0] == ["/usr/bin/web-ext", "--version"]
    assert launched[0][:4] == ["/usr/bin/web-ext", "run", "--source-dir", str(tmp_path / "extension")]
    assert "--firefox-profile" in launched[0]
    assert str(tmp_path / "tmp" / "profile") in launched[0]
    assert cleanup_tokens == [str(tmp_path / "tmp")]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()


def test_browser_atspi_selftest_reports_missing_runtime_without_probe(tmp_path) -> None:
    called = {"probe": False}

    def forbidden_find_event(_text_sha: str, _limit: int):
        called["probe"] = True
        return None, []

    data = typing_browser_adapters.browser_atspi_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        release_profile=False,
        natural_route=False,
        release_profile_info=None,
        find_event=forbidden_find_event,
        focus_window_by_title=lambda *_args, **_kwargs: {},
        focus_text_by_path=lambda *_args, **_kwargs: {},
        insert_text_by_path=lambda *_args, **_kwargs: {},
        insert_text_by_url=lambda *_args, **_kwargs: {},
        which=lambda name: None,
    )

    assert data["status"] == "firefox_missing"
    assert data["policy"]["raw_keylogging"] is False
    assert called["probe"] is False


def test_browser_atspi_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    probe_suffix = f" {run_id} 424242"
    base_text = "abyss browser atspi committed text probe"
    expected_text = base_text + probe_suffix
    base_sha = hashlib.sha256(base_text.encode("utf-8", errors="replace")).hexdigest()
    expected_sha = hashlib.sha256(expected_text.encode("utf-8", errors="replace")).hexdigest()
    launched: list[list[str]] = []
    calls: list[tuple[str, int]] = []

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "firefox stdout ?token=secret", "firefox stderr ?client_secret=secret"

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_find_event(text_sha256: str, limit: int):
        calls.append((text_sha256, limit))
        url = launched[0][-1]
        if text_sha256 == base_sha:
            return {
                "event_id": "evt-ready",
                "status": "captured",
                "url": url,
                "atspi": {"source_path": "/application/firefox/document/entry"},
            }, []
        if text_sha256 == expected_sha:
            return {
                "event_id": "evt-atspi",
                "status": "captured",
                "capture_gate_decision": "allow_text",
                "capture_gate_confidence": "atspi_browser_url_allowed",
                "text_sha256": expected_sha,
                "text_chars_stored": len(expected_text),
                "url": url,
            }, []
        raise AssertionError(text_sha256)

    data = typing_browser_adapters.browser_atspi_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        release_profile=False,
        natural_route=False,
        release_profile_info=None,
        find_event=fake_find_event,
        focus_window_by_title=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "title"},
        focus_text_by_path=lambda path, url, text_sha: {
            "ok": True,
            "matched": {"path": path, "_text": base_text, "_private": "hidden"},
            "url": url,
            "text_sha256": text_sha,
        },
        insert_text_by_path=lambda path, url, text_sha, text: {
            "ok": True,
            "method": "atspi_editable_text_insert",
            "matched": {"path": path, "_text": base_text, "_private": "hidden"},
            "url": url,
            "text_sha256": text_sha,
            "insert_text_omitted": bool(text),
        },
        insert_text_by_url=lambda *_args, **_kwargs: {"ok": False, "status": "not_used"},
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
        process_factory=fake_process_factory,
        sleep=lambda _seconds: None,
        monotonic=lambda: 100.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["source_adapter"] == "atspi_text_changed_event"
    assert data["probe"]["base_text_sha256"] == base_sha
    assert data["probe"]["text_sha256"] == expected_sha
    assert data["probe"]["uses_targeted_atspi_insert"] is True
    assert data["probe"]["uses_global_virtual_keyboard"] is False
    assert data["proof_input"]["accepted_route"] == "targeted_atspi_insert"
    assert data["event"]["event_id"] == "evt-atspi"
    assert data["ready_event"]["event_id"] == "evt-ready"
    assert "_private" not in data["window_focus_attempt"]
    assert "_private" not in data["focus_attempt"]["matched"]
    assert "_private" not in data["type_result"]["matched"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stdout_tail"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stderr_tail"]
    assert data["firefox"]["profile_kind"] == "temporary_profile"
    assert data["policy"]["loopback_http_only"] is True
    assert data["policy"]["global_virtual_keyboard"] is False
    assert calls == [(base_sha, 360), (expected_sha, 420)]
    assert launched[0][:4] == ["/usr/bin/firefox", "--new-instance", "--profile", str(tmp_path / "tmp" / "profile")]
    assert launched[0][-2:] == ["--new-window", data["url"]]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()


def test_cli_browser_atspi_selftest_binds_adapter_to_latest_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T18:00:00Z")
    monkeypatch.setattr(cli, "TYPING_BROWSER_ATSPI_SELFTEST_TMP_ROOT", tmp_path / "tmp")
    monkeypatch.setattr(cli, "typing_browser_atspi_selftest_store", lambda data, write_latest=True: {"stored": data, "write_latest": write_latest})
    monkeypatch.setattr(cli, "typing_firefox_release_profile", lambda: {"path": str(tmp_path / "release")})

    def fake_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "abyss_machine_typing_browser_atspi_selftest_v1", "ok": True}

    monkeypatch.setattr(typing_browser_adapters, "browser_atspi_selftest_document", fake_document)

    result = cli.typing_browser_atspi_selftest(write_latest=False, release_profile=True, natural_route=False)

    assert result["write_latest"] is False
    assert result["stored"]["ok"] is True
    assert captured["generated_at"] == "2026-06-27T18:00:00Z"
    assert captured["tmp_root"] == tmp_path / "tmp"
    assert captured["release_profile"] is True
    assert captured["natural_route"] is False
    assert captured["release_profile_info"] == {"path": str(tmp_path / "release")}
    assert captured["find_event"] is cli.typing_browser_atspi_find_event
    assert captured["focus_window_by_title"] is cli.typing_atspi_focus_firefox_frame_by_title
    assert captured["focus_text_by_path"] is cli.typing_atspi_focus_text_by_path
    assert captured["insert_text_by_path"] is cli.typing_atspi_insert_text_by_path
    assert captured["insert_text_by_url"] is cli.typing_atspi_insert_text_by_url
    assert captured["natural_route_host"] is cli.typing_browser_atspi_natural_route_host
    assert captured["process_tail"] is cli.typing_safe_process_tail


def test_browser_context_selftest_reports_missing_firefox_without_live_probe(tmp_path) -> None:
    called = {"live": False}

    def forbidden_live_capture(**_kwargs: object) -> dict[str, object]:
        called["live"] = True
        return {}

    data = typing_browser_adapters.browser_context_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        events_policy={"max_age_sec": 30},
        focus_window_by_title=lambda *_args, **_kwargs: {},
        focus_metadata_by_url=lambda *_args, **_kwargs: {},
        live_content_capture=forbidden_live_capture,
        context_from_recent_atspi_path=lambda *_args, **_kwargs: {},
        which=lambda name: None,
    )

    assert data["status"] == "firefox_missing"
    assert data["policy"]["raw_keylogging"] is False
    assert called["live"] is False


def test_browser_context_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    launched: list[list[str]] = []
    runtime_env = {
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS": "old",
        "KEEP": "1",
    }

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "opened ?token=secret", "stderr ?client_secret=secret"

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_live_capture(**kwargs: object) -> dict[str, object]:
        assert kwargs == {"write_latest": True}
        url = launched[0][-1]
        return {
            "ok": True,
            "summary": {"captures": 1},
            "captures": [{
                "record": {
                    "captured_at": generated_at,
                    "title": "Abyss Writing Context",
                    "url": {"url": url},
                    "content_type": "text/html",
                    "text_length": 512,
                    "skipped_text": False,
                    "web_context_quality": {"class": "project_context"},
                    "content_quality": {"classification": "usable"},
                },
                "atspi": {
                    "path": "/application/firefox/document",
                    "role": "document",
                    "showing": True,
                    "visible": True,
                    "focused": True,
                },
            }],
        }

    def fake_context_from_path(
        source_path: str,
        document_path: str,
        events_policy: dict[str, object] | None,
        *,
        allow_attention_fallback: bool,
    ) -> dict[str, object]:
        assert source_path == "/application/firefox/document"
        assert document_path == "/application/firefox/document"
        assert events_policy == {"max_age_sec": 30}
        assert allow_attention_fallback is False
        return {
            "ok": True,
            "status": "matched",
            "url": launched[0][-1],
            "title": "Abyss Writing Context",
            "basis": "recent_browser_content",
        }

    data = typing_browser_adapters.browser_context_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        events_policy={"max_age_sec": 30},
        focus_window_by_title=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "title"},
        focus_metadata_by_url=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "url"},
        live_content_capture=fake_live_capture,
        context_from_recent_atspi_path=fake_context_from_path,
        natural_route_host=lambda: "127.0.0.1",
        url_origin=lambda url: {"origin": "http://127.0.0.1"},
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
        process_factory=fake_process_factory,
        sleep=lambda _seconds: None,
        monotonic=lambda: 100.0,
        env_mapping=runtime_env,
        deadline_seconds=1.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["capture"]["record"]["text_captured"] is True
    assert data["capture"]["record"]["content_quality_class"] == "usable"
    assert data["capture"]["atspi"]["path"] == "/application/firefox/document"
    assert "_private" not in data["capture"]["window_focus_attempt"]
    assert "_private" not in data["capture"]["focus_attempt"]
    assert data["inference"] == {"ok": True, "status": "matched", "basis": "recent_browser_content"}
    assert data["policy"]["temporary_firefox_profile"] is True
    assert data["policy"]["release_profile_mutated"] is False
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stdout_tail"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stderr_tail"]
    assert launched[0][:4] == ["/usr/bin/firefox", "--new-instance", "--profile", str(tmp_path / "tmp" / "profile")]
    assert launched[0][-2:] == ["--new-window", data["url"]]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()
    assert runtime_env == {
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS": "old",
        "KEEP": "1",
    }


def test_cli_browser_context_selftest_binds_adapter_to_latest_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T18:00:00Z")
    monkeypatch.setattr(cli, "TYPING_BROWSER_CONTEXT_SELFTEST_TMP_ROOT", tmp_path / "tmp")
    monkeypatch.setattr(cli, "typing_browser_context_selftest_store", lambda data, write_latest=True: {"stored": data, "write_latest": write_latest})
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: {"policy": True})
    monkeypatch.setattr(cli, "typing_atspi_text_events_policy", lambda policy: {"events_policy": policy})

    def fake_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "abyss_machine_typing_browser_context_selftest_v1", "ok": True}

    monkeypatch.setattr(typing_browser_adapters, "browser_context_selftest_document", fake_document)

    result = cli.typing_browser_context_selftest(write_latest=False)

    assert result["write_latest"] is False
    assert result["stored"]["ok"] is True
    assert captured["generated_at"] == "2026-06-27T18:00:00Z"
    assert captured["tmp_root"] == tmp_path / "tmp"
    assert captured["events_policy"] == {"events_policy": {"policy": True}}
    assert captured["focus_window_by_title"] is cli.typing_atspi_focus_firefox_frame_by_title
    assert captured["focus_metadata_by_url"] is cli.typing_atspi_focus_metadata_by_url
    assert captured["live_content_capture"] is cli.nervous_browser_live_content_capture
    assert captured["context_from_recent_atspi_path"] is cli.typing_browser_context_from_recent_atspi_path
    assert captured["natural_route_host"] is cli.typing_browser_atspi_natural_route_host
    assert captured["process_tail"] is cli.typing_safe_process_tail


def test_focused_browser_selftest_reports_missing_firefox_without_live_probe(tmp_path) -> None:
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("live")
        return {}

    data = typing_browser_adapters.focused_browser_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        policy={},
        find_event=forbidden,
        focus_window_by_title=forbidden,
        focus_text_by_path=forbidden,
        focus_text_by_url=forbidden,
        insert_text_by_url=forbidden,
        focused_candidate=forbidden,
        focused_snapshot_from_candidate=forbidden,
        capture_gate_decision=forbidden,
        which=lambda name: None,
    )

    assert data["status"] == "firefox_missing"
    assert data["source_adapter"] == "atspi_focused_text_snapshot"
    assert data["policy"]["raw_keylogging"] is False
    assert called == []


def test_focused_browser_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    base_text = f"abyss focused browser committed text probe {run_id}"
    base_sha = hashlib.sha256(base_text.encode("utf-8", errors="replace")).hexdigest()
    launched: list[list[str]] = []
    captured_candidate: dict[str, object] = {}

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return None

        def communicate(self, timeout=0):
            return "focused stdout ?token=secret", "focused stderr ?client_secret=secret"

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_find_event(text_sha256: str, limit: int):
        assert text_sha256 == base_sha
        assert limit == 420
        return {
            "event_id": "evt-ready",
            "status": "captured",
            "url": launched[0][-1],
            "app": "Firefox",
            "window_title": "Abyss focused browser safe input probe",
            "atspi": {
                "source_path": "0.1.2.3",
                "document_path": "0.1.2",
                "content_type": "text/html",
            },
        }, []

    def fake_focus_text_by_path(source_path: str, url: str, expected_sha: str) -> dict[str, object]:
        assert source_path == "0.1.2.3"
        assert expected_sha == base_sha
        assert url == launched[0][-1]
        return {
            "ok": True,
            "matched": {
                "role": "entry",
                "name": "Abyss focused safe browser note",
                "path": source_path,
                "document_title": "Abyss focused browser safe input probe",
                "text_length": len(base_text),
                "_text": base_text,
                "_caret_offset": len(base_text),
                "_private": "hidden",
                "focus": {"states_after": {"focused": True, "editable": True}},
            },
        }

    def fake_capture_gate_decision(source: str, **kwargs: object) -> dict[str, object]:
        assert source == "atspi_focused_text_snapshot"
        assert kwargs["url"] == launched[0][-1]
        assert kwargs["write_latest"] is False
        return {"decision": "allow_text", "confidence": "focused_browser_safe_url_allowed"}

    def fake_snapshot_from_candidate(candidate: dict[str, object]) -> dict[str, object]:
        captured_candidate.update(candidate)
        return {
            "schema": "abyss_machine_typing_focused_snapshot_v1",
            "ok": True,
            "status": "captured",
            "generated_at": generated_at,
            "event": {
                "event_id": "evt-focused",
                "generated_at": generated_at,
                "status": "captured",
                "source_adapter": "atspi_focused_text_snapshot",
                "capture_gate": {
                    "decision": "allow_text",
                    "confidence": "focused_browser_safe_url_allowed",
                },
                "text": {
                    "text_length": len(base_text),
                    "text_chars_stored": len(base_text),
                    "text_sha256": base_sha,
                },
                "context": {
                    "app": {"text": "Firefox"},
                    "window_title": {"text": "Abyss focused browser safe input probe"},
                    "url": {"text": launched[0][-1]},
                },
                "metadata": {
                    "atspi": {
                        "safe_route": "browser_safe_url",
                        "browser_safe_url": True,
                    },
                },
                "causal_context": {
                    "recipient": {"kind": "browser"},
                    "task": {"binding": "selftest"},
                },
            },
        }

    data = typing_browser_adapters.focused_browser_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        policy={"focused_snapshot": {"enabled": True}},
        find_event=fake_find_event,
        focus_window_by_title=lambda *_args, **_kwargs: {"ok": True, "_private": "hidden", "method": "title"},
        focus_text_by_path=fake_focus_text_by_path,
        focus_text_by_url=lambda *_args, **_kwargs: pytest.fail("url focus fallback should not run"),
        insert_text_by_url=lambda *_args, **_kwargs: pytest.fail("noop insert fallback should not run"),
        focused_candidate=lambda *_args, **_kwargs: pytest.fail("focused candidate fallback should not run"),
        focused_snapshot_from_candidate=fake_snapshot_from_candidate,
        capture_gate_decision=fake_capture_gate_decision,
        terminate_processes=lambda token: [{"ok": True, "token_seen": bool(token)}],
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
        process_factory=fake_process_factory,
        sleep=lambda _seconds: None,
        monotonic=lambda: 100.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["source_adapter"] == "atspi_focused_text_snapshot"
    assert data["probe"]["base_text_sha256"] == base_sha
    assert data["probe"]["text_sha256"] == base_sha
    assert data["candidate"]["text_sha256"] == base_sha
    assert data["candidate"]["expected_text_match"] is True
    assert "text" not in data["candidate"]
    assert data["event"]["event_id"] == "evt-focused"
    assert "_private" not in data["window_focus_attempt"]
    assert "_private" not in data["path_focus_attempts"][0]["matched"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stdout_tail"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stderr_tail"]
    assert data["firefox"]["cleanup_actions"] == [{"ok": True, "token_seen": True}]
    assert captured_candidate["url"] == data["url"]
    assert launched[0][:4] == ["/usr/bin/firefox", "--new-instance", "--profile", str(tmp_path / "tmp" / "profile")]
    assert launched[0][-2:] == ["--new-window", data["url"]]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "index.html").exists()


def test_cli_focused_browser_selftest_binds_adapter_to_latest_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T18:00:00Z")
    monkeypatch.setattr(cli, "TYPING_FOCUSED_BROWSER_SELFTEST_TMP_ROOT", tmp_path / "tmp")
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: {"policy": True})
    monkeypatch.setattr(cli, "typing_focused_browser_selftest_store", lambda data, write_latest=True: {"stored": data, "write_latest": write_latest})
    monkeypatch.setattr(
        cli,
        "typing_focused_snapshot_from_candidate",
        lambda candidate, write_latest=True: {"candidate": candidate, "write_latest": write_latest},
    )

    def fake_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "abyss_machine_typing_focused_browser_selftest_v1", "ok": True}

    monkeypatch.setattr(typing_browser_adapters, "focused_browser_selftest_document", fake_document)

    result = cli.typing_focused_browser_selftest(write_latest=False)

    assert result["write_latest"] is False
    assert result["stored"]["ok"] is True
    assert captured["generated_at"] == "2026-06-27T18:00:00Z"
    assert captured["tmp_root"] == tmp_path / "tmp"
    assert captured["policy"] == {"policy": True}
    assert captured["find_event"] is cli.typing_browser_atspi_find_event
    assert captured["focus_window_by_title"] is cli.typing_atspi_focus_firefox_frame_by_title
    assert captured["focus_text_by_path"] is cli.typing_atspi_focus_text_by_path
    assert captured["focus_text_by_url"] is cli.typing_atspi_focus_text_by_url
    assert captured["insert_text_by_url"] is cli.typing_atspi_insert_text_by_url
    assert captured["focused_candidate"] is cli.typing_atspi_focused_candidate
    assert captured["capture_gate_decision"] is cli.typing_capture_gate_decision
    assert captured["process_tail"] is cli.typing_safe_process_tail
    snapshot = captured["focused_snapshot_from_candidate"]({"ok": True})
    assert snapshot["write_latest"] is False


def test_browser_privacy_selftest_reports_missing_firefox_without_live_probe(tmp_path) -> None:
    called: list[str] = []

    def forbidden(*_args: object, **_kwargs: object):
        called.append("live")
        return {}

    data = typing_browser_adapters.browser_privacy_selftest_document(
        generated_at="2026-06-27T18:00:00Z",
        pid=4242,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        policy={},
        find_event=forbidden,
        probe_absence=forbidden,
        focused_candidate=forbidden,
        focused_snapshot_from_candidate=forbidden,
        focus_metadata_by_path=forbidden,
        capture_gate_decision=forbidden,
        deny_context_matches=forbidden,
        capture_gate_policy=forbidden,
        capture_gate_token_matches=forbidden,
        browser_extension_policy=forbidden,
        browser_url_scheme_allowed=forbidden,
        url_origin=forbidden,
        browser_privacy_url_matches=forbidden,
        which=lambda name: None,
    )

    assert data["status"] == "firefox_missing"
    assert data["policy"]["raw_keylogging"] is False
    assert called == []


def test_browser_privacy_selftest_runtime_adapter_builds_public_safe_document(tmp_path) -> None:
    generated_at = "2026-06-27T18:00:00Z"
    pid = 4242
    run_id = typing_browser_adapters.browser_webextension_run_id(generated_at, pid)
    probe_text = f"abyss browser privacy visible login text probe {run_id}"
    probe_sha = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    launched: list[list[str]] = []
    captured_candidate: dict[str, object] = {}

    class FakeProcess:
        pid = 999999
        returncode = 0

        def poll(self):
            return 0

        def communicate(self, timeout=0):
            return "privacy stdout ?token=secret", "privacy stderr ?client_secret=secret"

    def fake_process_factory(command: list[str], **_kwargs: object) -> FakeProcess:
        launched.append(command)
        return FakeProcess()

    def fake_find_event(url: str, source_adapter: str, **kwargs: object):
        assert source_adapter == "atspi_text_changed_event"
        assert kwargs["generated_after"] == generated_at
        assert kwargs["probe_text_sha256"] == probe_sha
        assert kwargs["limit"] == 900
        assert url == launched[0][-1]
        return {
            "event_id": "evt-atspi",
            "source_adapter": "atspi_text_changed_event",
            "status": "metadata_only",
            "capture_gate_decision": "metadata_only",
            "capture_gate_confidence": "sensitive_url",
            "text_chars_stored": 0,
            "text_value_present": False,
            "text_sha256_matches_probe": False,
            "app": "Firefox",
            "window_title": "Abyss login privacy input probe",
            "atspi": {
                "text_read": False,
                "source_path": "0.1.2.3",
                "document_path": "0.1.2",
            },
        }, []

    def fake_focus_metadata_by_path(source_path: str, url: str) -> dict[str, object]:
        assert source_path == "0.1.2.3"
        assert url == launched[0][-1]
        return {
            "ok": True,
            "matched": {
                "role": "entry",
                "name": "Abyss login visible note",
                "description": "Login textarea",
                "app": "Firefox",
                "document_title": "Abyss login privacy input probe",
                "content_type": "text/html",
                "document_path": "0.1.2",
                "states_after": {"editable": True, "focused": True},
                "_private": "hidden",
            },
        }

    def fake_capture_gate_decision(source: str, **kwargs: object) -> dict[str, object]:
        assert source == "atspi_focused_text_snapshot"
        assert kwargs["url"] == launched[0][-1]
        assert kwargs["write_latest"] is False
        return {"decision": "metadata_only", "confidence": "sensitive_url"}

    def fake_capture_gate_token_matches(kind: str, probe: str, tokens: list[object]) -> list[dict[str, object]]:
        if kind == "browser_app_token" and "Firefox" in probe:
            return [{"kind": kind, "token": "firefox"}]
        return [{"kind": kind, "token": token} for token in tokens if str(token).lower() in probe.lower()]

    def fake_snapshot_from_candidate(candidate: dict[str, object]) -> dict[str, object]:
        captured_candidate.update(candidate)
        return {
            "schema": "abyss_machine_typing_focused_snapshot_v1",
            "ok": True,
            "status": "metadata_only",
            "generated_at": generated_at,
            "event": {
                "event_id": "evt-focused",
                "source_adapter": "atspi_focused_text_snapshot",
                "status": "metadata_only",
                "capture_gate": {"decision": "metadata_only", "confidence": "sensitive_url"},
                "text": {"text_length": 0, "text_chars_stored": 0},
                "metadata": {"atspi": {"text_read": False}},
            },
        }

    def fake_record_summary(record: object, expected_sha: str | None = None) -> dict[str, object]:
        assert isinstance(record, dict)
        assert expected_sha == probe_sha
        return {
            "event_id": record["event_id"],
            "source_adapter": record["source_adapter"],
            "status": "metadata_only",
            "capture_gate_decision": "metadata_only",
            "capture_gate_confidence": "sensitive_url",
            "text_chars_stored": 0,
            "text_value_present": False,
            "text_sha256_matches_probe": False,
            "atspi": {"text_read": False},
        }

    data = typing_browser_adapters.browser_privacy_selftest_document(
        generated_at=generated_at,
        pid=pid,
        tmp_root=tmp_path / "tmp",
        schema_prefix="abyss_machine",
        version="fixture-version",
        policy={"focused_snapshot": {"text_roles": ["entry"], "sensitive_roles": ["password"]}},
        find_event=fake_find_event,
        probe_absence=lambda text_sha: {"ok": text_sha == probe_sha, "records_scanned": 12, "matches": [], "parse_errors": []},
        focused_candidate=lambda _policy: {"status": "no_candidate"},
        focused_snapshot_from_candidate=fake_snapshot_from_candidate,
        focus_metadata_by_path=fake_focus_metadata_by_path,
        capture_gate_decision=fake_capture_gate_decision,
        deny_context_matches=lambda probe, _policy: [{"kind": "deny_context_token", "token": "login"}] if "login" in probe.lower() else [],
        capture_gate_policy=lambda _policy: {"metadata_only_url_tokens": ["login"], "hard_skip_url_tokens": []},
        capture_gate_token_matches=fake_capture_gate_token_matches,
        browser_extension_policy=lambda _policy: {"allowed_url_schemes": ["http:", "https:"]},
        browser_url_scheme_allowed=lambda url, _policy: url.startswith("http://"),
        url_origin=lambda url: {"origin": url.split("/login.html", 1)[0]},
        browser_privacy_url_matches=lambda observed, target: str(observed) == str(target),
        browser_privacy_record_summary=fake_record_summary,
        terminate_processes=lambda token: [{"ok": True, "token_seen": bool(token)}],
        which=lambda name: "/usr/bin/firefox" if name == "firefox" else None,
        process_factory=fake_process_factory,
        sleep=lambda _seconds: None,
        monotonic=lambda: 100.0,
    )

    assert data["ok"] is True
    assert data["status"] == "passed"
    assert data["run_id"] == run_id
    assert data["probe"]["text_sha256"] == probe_sha
    assert data["checks"] == {
        "atspi_metadata_only_before_text_read": True,
        "focused_candidate_no_text_read": True,
        "focused_metadata_only_before_text_read": True,
        "probe_text_sha256_absent_from_recent_events": True,
    }
    assert data["focused_event"]["event_id"] == "evt-focused"
    assert data["focused_candidate"]["capture_gate_decision"] == "metadata_only"
    assert data["focused_candidate"]["text_read_allowed"] is False
    assert "text" not in data["focused_candidate"]
    assert "_private" not in data["focused_metadata_focus"]["matched"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stdout_tail"]
    assert "[REDACTED:url_query_secret]" in data["firefox"]["stderr_tail"]
    assert data["firefox"]["cleanup_actions"] == [{"ok": True, "token_seen": True}]
    assert captured_candidate["url"] == data["url"]
    assert captured_candidate["text_read_allowed"] is False
    assert launched[0][:4] == ["/usr/bin/firefox", "--new-instance", "--profile", str(tmp_path / "tmp" / "profile")]
    assert launched[0][-2:] == ["--new-window", data["url"]]
    assert (tmp_path / "tmp" / "profile" / "user.js").exists()
    assert (tmp_path / "tmp" / "site" / "login.html").exists()


def test_cli_browser_privacy_selftest_binds_adapter_to_latest_store(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T18:00:00Z")
    monkeypatch.setattr(cli, "TYPING_BROWSER_PRIVACY_SELFTEST_TMP_ROOT", tmp_path / "tmp")
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: {"policy": True})
    monkeypatch.setattr(cli, "typing_browser_privacy_selftest_store", lambda data, write_latest=True: {"stored": data, "write_latest": write_latest})
    monkeypatch.setattr(
        cli,
        "typing_focused_snapshot_from_candidate",
        lambda candidate, write_latest=True: {"candidate": candidate, "write_latest": write_latest},
    )

    def fake_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema": "abyss_machine_typing_browser_privacy_selftest_v1", "ok": True}

    monkeypatch.setattr(typing_browser_adapters, "browser_privacy_selftest_document", fake_document)

    result = cli.typing_browser_privacy_selftest(write_latest=False)

    assert result["write_latest"] is False
    assert result["stored"]["ok"] is True
    assert captured["generated_at"] == "2026-06-27T18:00:00Z"
    assert captured["tmp_root"] == tmp_path / "tmp"
    assert captured["policy"] == {"policy": True}
    assert captured["find_event"] is cli.typing_browser_privacy_find_event
    assert captured["probe_absence"] is cli.typing_browser_privacy_probe_absence
    assert captured["focused_candidate"] is cli.typing_atspi_focused_candidate
    assert captured["focus_metadata_by_path"] is cli.typing_atspi_focus_metadata_by_path
    assert captured["capture_gate_decision"] is cli.typing_capture_gate_decision
    assert captured["deny_context_matches"] is cli.typing_deny_context_matches
    assert captured["capture_gate_policy"] is cli.typing_capture_gate_policy
    assert captured["capture_gate_token_matches"] is cli.typing_capture_gate_token_matches
    assert captured["browser_extension_policy"] is cli.typing_browser_extension_policy
    assert captured["browser_url_scheme_allowed"] is cli.typing_browser_url_scheme_allowed
    assert captured["url_origin"] is cli.typing_url_origin
    assert captured["browser_privacy_url_matches"] is cli.typing_browser_privacy_url_matches
    assert captured["browser_privacy_record_summary"] is cli.typing_browser_privacy_record_summary
    assert captured["process_tail"] is cli.typing_safe_process_tail
    snapshot = captured["focused_snapshot_from_candidate"]({"ok": True})
    assert snapshot["write_latest"] is True


def test_cli_browser_extension_ingest_executes_adapter_plan(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-27T00:00:00Z")
    monkeypatch.setattr(cli, "typing_browser_extension_store", lambda data, write_latest=True: data)

    def fake_ingest(text: str, **kwargs: object) -> dict[str, object]:
        captured["text"] = text
        captured.update(kwargs)
        return {
            "ok": True,
            "event_id": "evt-cli",
            "generated_at": "2026-06-27T00:00:01Z",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"text_length": len(text), "text_chars_stored": len(text)},
            "duplicate": False,
        }

    monkeypatch.setattr(cli, "typing_ingest", fake_ingest)

    result = cli.typing_browser_extension_ingest_message(
        {
            "event_kind": "committed_text",
            "browser_name": "firefox",
            "title": "Writing",
            "url": "https://example.test/write",
            "text": "cli fixture",
            "field": {"safe": True, "kind": "textarea", "type": "textarea"},
        },
        write_latest=False,
    )

    assert captured["text"] == "cli fixture"
    assert captured["source"] == "browser_extension_explicit"
    assert captured["write_latest"] is False
    assert captured["skip_duplicate"] is True
    assert result["schema"] == "abyss_machine_typing_browser_extension_status_v1"
    assert result["event"]["event_id"] == "evt-cli"
