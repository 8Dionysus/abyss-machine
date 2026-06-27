from __future__ import annotations

import http.server
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socketserver
import subprocess
import struct
import tempfile
import threading
import time
from typing import Any, Callable, Mapping

from . import typing_capture_contracts


BROWSER_EXTENSION_SOURCE = "browser_extension_explicit"
BROWSER_AI_TRANSCRIPT_SOURCE = "browser_ai_transcript"
BROWSER_EXTENSION_MESSAGE_SCHEMA = "abyss_machine_browser_extension_message_v1"
BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA = "abyss_machine_browser_ai_transcript_message_v1"
NATIVE_HOST_MAX_MESSAGE_BYTES = 1024 * 1024

ProbeEventFinder = Callable[[str, int], tuple[dict[str, Any] | None, list[dict[str, Any]]]]
RunCommand = Callable[[list[str], float, dict[str, str] | None], dict[str, Any]]
TerminateProcesses = Callable[[str], list[dict[str, Any]]]


def _nested_get(data: Mapping[str, Any] | None, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def browser_selftest_run_id(seed: str) -> str:
    return hashlib.sha256(str(seed or "").encode("utf-8", errors="replace")).hexdigest()[:12]


def browser_webextension_run_id(generated_at: str, pid: int) -> str:
    return re.sub(r"[^0-9]", "", str(generated_at or ""))[:14] + str(pid)[-5:]


def firefox_selftest_user_prefs() -> str:
    return "\n".join([
        'user_pref("app.normandy.enabled", false);',
        'user_pref("app.shield.optoutstudies.enabled", false);',
        'user_pref("app.update.enabled", false);',
        'user_pref("browser.aboutConfig.showWarning", false);',
        'user_pref("browser.cache.disk.enable", false);',
        'user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false);',
        'user_pref("browser.newtabpage.activity-stream.telemetry", false);',
        'user_pref("browser.safebrowsing.blockedURIs.enabled", false);',
        'user_pref("browser.safebrowsing.downloads.enabled", false);',
        'user_pref("browser.safebrowsing.downloads.remote.enabled", false);',
        'user_pref("browser.safebrowsing.downloads.remote.url", "");',
        'user_pref("browser.safebrowsing.malware.enabled", false);',
        'user_pref("browser.safebrowsing.phishing.enabled", false);',
        'user_pref("browser.safebrowsing.provider.google.updateURL", "");',
        'user_pref("browser.safebrowsing.provider.google4.updateURL", "");',
        'user_pref("browser.safebrowsing.provider.mozilla.updateURL", "");',
        'user_pref("browser.shell.checkDefaultBrowser", false);',
        'user_pref("browser.startup.homepage_override.mstone", "ignore");',
        'user_pref("browser.urlbar.speculativeConnect.enabled", false);',
        'user_pref("datareporting.healthreport.uploadEnabled", false);',
        'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
        'user_pref("dom.security.https_only_mode", false);',
        'user_pref("extensions.getAddons.cache.enabled", false);',
        'user_pref("extensions.systemAddon.update.enabled", false);',
        'user_pref("extensions.update.enabled", false);',
        'user_pref("network.captive-portal-service.enabled", false);',
        'user_pref("network.connectivity-service.enabled", false);',
        'user_pref("network.dns.disablePrefetch", true);',
        'user_pref("network.http.speculative-parallel-limit", 0);',
        'user_pref("network.predictor.enabled", false);',
        'user_pref("network.prefetch-next", false);',
        'user_pref("toolkit.telemetry.enabled", false);',
        'user_pref("toolkit.telemetry.unified", false);',
        "",
    ])


def _atomic_write_text(path: Path, text: str, mode: int = 0o664) -> dict[str, Any] | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            delete=False,
        ) as tmp:
            tmp.write(text)
            tmp_name = tmp.name
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
        return None
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def prepare_firefox_selftest_profile(profile_dir: Path) -> dict[str, Any] | None:
    return _atomic_write_text(profile_dir / "user.js", firefox_selftest_user_prefs(), 0o664)


def browser_webextension_base_command(
    *,
    npm_cache: Path,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[list[str], dict[str, Any]]:
    web_ext_bin = which("web-ext")
    if web_ext_bin:
        return [web_ext_bin], {"route": "path", "binary": web_ext_bin, "offline_npm_cache": False}
    npm_bin = which("npm")
    if not npm_bin:
        return [], {"route": "missing", "error": "neither web-ext nor npm executable was found"}
    return [
        npm_bin,
        "exec",
        "--offline",
        "--yes",
        "--package",
        "web-ext",
        "--",
        "web-ext",
    ], {
        "route": "npm_exec_offline",
        "binary": npm_bin,
        "npm_cache": str(npm_cache),
        "offline_npm_cache": True,
    }


def _webextension_selftest_error_document(
    *,
    status: str,
    error: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_browser_webextension_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": status,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "error": error,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }


def _default_run_command(cmd: list[str], timeout: float, env: dict[str, str] | None) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": "not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "stdout": "", "stderr": "timeout"}


def _terminate_process_group(proc: Any) -> tuple[str, str, int | None]:
    stdout = ""
    stderr = ""
    if proc is None:
        return stdout, stderr, None
    try:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        stdout, stderr = proc.communicate(timeout=5.0)
    except Exception:
        try:
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=2.0)
        except Exception:
            stdout, stderr = "", ""
    return str(stdout or ""), str(stderr or ""), getattr(proc, "returncode", None)


def browser_webextension_selftest_document(
    *,
    generated_at: str,
    pid: int,
    tmp_root: Path,
    extension_root: Path,
    npm_cache: Path,
    schema_prefix: str,
    version: str,
    find_probe_event: ProbeEventFinder,
    which: Callable[[str], str | None] = shutil.which,
    run_command: RunCommand = _default_run_command,
    process_factory: Callable[..., Any] = subprocess.Popen,
    terminate_processes: TerminateProcesses | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    deadline_seconds: float = 35.0,
) -> dict[str, Any]:
    run_id = browser_webextension_run_id(generated_at, pid)
    probe_text = f"abyss browser webextension committed text {run_id}"
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    profile_dir = tmp_root / "profile"
    site_dir = tmp_root / "site"
    artifacts_dir = tmp_root / "web-ext-artifacts"
    firefox_bin = which("firefox")
    base_command, web_ext_info = browser_webextension_base_command(npm_cache=npm_cache, which=which)
    stdout_tail = ""
    stderr_tail = ""
    web_ext_returncode: int | None = None
    web_ext_version: dict[str, Any] | None = None
    cleanup_actions: list[dict[str, Any]] = []
    event: dict[str, Any] | None = None
    parse_errors: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    url = ""

    if not firefox_bin:
        return _webextension_selftest_error_document(
            status="firefox_missing",
            error="firefox executable not found",
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
    if not base_command:
        return _webextension_selftest_error_document(
            status="web_ext_missing",
            error=str(web_ext_info.get("error") or "web-ext loader unavailable"),
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )

    proc: Any | None = None
    httpd: socketserver.TCPServer | None = None
    server_thread: threading.Thread | None = None
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
        site_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        prefs_error = prepare_firefox_selftest_profile(profile_dir)
        if prefs_error:
            errors.append(prefs_error)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        npm_cache.mkdir(parents=True, exist_ok=True)
        page = f"""<!doctype html>
<meta charset=\"utf-8\">
<title>Abyss browser WebExtension safe input probe</title>
<textarea id=\"probe\" name=\"abyss_note\" aria-label=\"Abyss safe note\" autocomplete=\"off\" autofocus></textarea>
<script>
  const probeText = {json.dumps(probe_text)};
  function emitProbe() {{
    const probe = document.getElementById(\"probe\");
    probe.focus();
    probe.value = probeText;
    probe.setSelectionRange(probe.value.length, probe.value.length);
    probe.dispatchEvent(new InputEvent(\"input\", {{bubbles: true, inputType: \"insertText\", data: \"probe\"}}));
  }}
  setTimeout(emitProbe, 2500);
</script>
"""
        write_error = _atomic_write_text(site_dir / "index.html", page, 0o664)
        if write_error:
            errors.append(write_error)

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(site_dir), **kwargs)

            def log_message(self, format: str, *args: Any) -> None:
                return

        class ReusableTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        httpd = ReusableTCPServer(("127.0.0.1", 0), Handler)
        port = int(httpd.server_address[1])
        url = f"http://127.0.0.1:{port}/index.html"
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        env = os.environ.copy()
        env["MOZ_NO_REMOTE"] = "1"
        if web_ext_info.get("offline_npm_cache"):
            env["NPM_CONFIG_CACHE"] = str(npm_cache)
        web_ext_version = run_command(base_command + ["--version"], 20.0, env)
        if not web_ext_version.get("ok"):
            errors.append({
                "error": "web_ext_version_check_failed",
                "returncode": web_ext_version.get("returncode"),
                "stderr": str(web_ext_version.get("stderr") or "")[-500:],
                "stdout": str(web_ext_version.get("stdout") or "")[-500:],
            })
        command = base_command + [
            "run",
            "--source-dir",
            str(extension_root),
            "--artifacts-dir",
            str(artifacts_dir),
            "--firefox",
            firefox_bin,
            "--firefox-profile",
            str(profile_dir),
            "--profile-create-if-missing",
            "--keep-profile-changes",
            "--no-reload",
            "--no-input",
            "--no-config-discovery",
            "--pref",
            "browser.shell.checkDefaultBrowser=false",
            "--pref",
            "browser.startup.homepage_override.mstone=ignore",
            "--start-url",
            url,
            "--arg=--new-instance",
        ]
        proc = process_factory(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=os.setsid,
        )
        deadline = monotonic() + max(1.0, float(deadline_seconds or 35.0))
        while monotonic() < deadline:
            event, parse_errors = find_probe_event(probe_hash, 520)
            if isinstance(event, dict):
                break
            if proc.poll() is not None:
                break
            sleep(0.5)
    except Exception as exc:
        errors.append({"error": repr(exc)[:500]})
    finally:
        stdout, stderr, web_ext_returncode = _terminate_process_group(proc)
        stdout_tail = str(stdout or "")[-2000:]
        stderr_tail = str(stderr or "")[-2000:]
        if terminate_processes is not None:
            cleanup_actions = terminate_processes(str(tmp_root))
        if httpd is not None:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass
        if server_thread is not None:
            try:
                server_thread.join(timeout=1.0)
            except Exception:
                pass

    event_ok = (
        isinstance(event, dict)
        and event.get("status") == "captured"
        and event.get("source_adapter") == BROWSER_EXTENSION_SOURCE
        and event.get("capture_gate_decision") == "allow_text"
        and event.get("capture_gate_confidence") == "browser_url_and_field_allowed"
        and event.get("text_sha256") == probe_hash
        and event.get("text_chars_stored") == len(probe_text)
        and _nested_get(event, ["recipient", "kind"]) == "browser_extension"
    )
    ok = bool(event_ok and not parse_errors and not errors)
    return {
        "schema": f"{schema_prefix}_typing_browser_webextension_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "run_id": run_id,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "url": url,
        "probe": {
            "text_sha256": probe_hash,
            "text_length": len(probe_text),
            "text_omitted": True,
        },
        "event": event,
        "web_ext": {
            "loader": web_ext_info,
            "version": str((web_ext_version or {}).get("stdout") or "").strip(),
            "version_check_ok": bool((web_ext_version or {}).get("ok")),
            "returncode": web_ext_returncode,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "cleanup_actions": cleanup_actions[:40],
        },
        "firefox": {
            "binary": firefox_bin,
            "profile": str(profile_dir),
            "extension_source": str(extension_root),
        },
        "tmp_root": str(tmp_root),
        "parse_errors": parse_errors[:20],
        "errors": errors[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "internet_access": False,
            "loopback_http_only": True,
            "temporary_firefox_profile": True,
            "release_profile_mutated": False,
            "uses_webextension_content_script": True,
            "uses_native_messaging_host": True,
        },
        "non_claims": [
            "This selftest proves the WebExtension content-script to native-host route in a temporary Firefox profile.",
            "It does not prove the extension is active in the user's release Firefox profiles.",
            "It does not collect raw key events, password fields, cookies, local storage, or full form values.",
        ],
    }


def browser_extension_message_metadata(
    message: Mapping[str, Any],
    *,
    extension_id: str,
    native_host: str,
) -> dict[str, Any]:
    return typing_capture_contracts.browser_extension_message_metadata(
        dict(message),
        extension_id=extension_id,
        native_host=native_host,
    )


def browser_ai_transcript_message_metadata(
    message: Mapping[str, Any],
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str = "abyss_machine",
) -> dict[str, Any]:
    page_identity = typing_capture_contracts.browser_ai_counterpart_identity(
        str(message.get("url") or ""),
        str(message.get("title") or ""),
        schema_prefix=schema_prefix,
    )
    return typing_capture_contracts.browser_ai_transcript_message_metadata(
        dict(message),
        extension_id=extension_id,
        native_host=native_host,
        page_identity=page_identity,
    )


def invalid_browser_message_status_document(
    *,
    schema_name: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_{schema_name}_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "status": "invalid_message",
        "error": "message must be an object",
    }


def browser_extension_ingest_plan(
    message: Any,
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        return {
            "valid": False,
            "route": BROWSER_EXTENSION_SOURCE,
            "status_document": invalid_browser_message_status_document(
                schema_name="typing_browser_extension_status",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ),
        }
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    url = str(message.get("url") or "")
    metadata = browser_extension_message_metadata(
        message,
        extension_id=extension_id,
        native_host=native_host,
    )
    context = (
        f"browser_extension event_kind={event_kind} "
        f"field_safe={bool(_nested_get(metadata, ['browser', 'field_safe']))} "
        f"url={url}"
    )
    return {
        "valid": True,
        "route": BROWSER_EXTENSION_SOURCE,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "extension_id": extension_id,
        "native_host": native_host,
        "ingest": {
            "text": str(message.get("text") or ""),
            "source": BROWSER_EXTENSION_SOURCE,
            "app": str(message.get("browser_name") or "firefox"),
            "window_title": str(message.get("title") or ""),
            "context": context,
            "url": url,
            "skip_duplicate": True,
            "metadata": metadata,
            "include_text_in_context_probe": True,
        },
    }


def browser_extension_status_document(
    plan: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_typing_browser_extension_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(event.get("ok")),
        "status": "sent",
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "extension_id": plan.get("extension_id"),
        "native_host": plan.get("native_host"),
        "event": {
            "event_id": event.get("event_id"),
            "generated_at": event.get("generated_at"),
            "status": event.get("status"),
            "capture_gate_decision": _nested_get(event, ["capture_gate", "decision"]),
            "capture_gate_confidence": _nested_get(event, ["capture_gate", "confidence"]),
            "text_length": _nested_get(event, ["text", "text_length"]),
            "text_chars_stored": _nested_get(event, ["text", "text_chars_stored"]),
            "duplicate": event.get("duplicate"),
        },
        "policy": {
            "raw_keylogging": False,
            "keydown_keyup_keypress_captured": False,
            "password_fields_captured": False,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "automatic_action": False,
            "capture_gate_required": True,
        },
        "non_claims": [
            "Browser extension intake receives debounced committed text messages, not raw key events.",
            "Content scripts skip sensitive URLs and fields before native host handoff; host capture-gate is the second line of defense.",
        ],
    }


def browser_ai_transcript_ingest_plan(
    message: Any,
    *,
    extension_id: str,
    native_host: str,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        return {
            "valid": False,
            "route": BROWSER_AI_TRANSCRIPT_SOURCE,
            "status_document": invalid_browser_message_status_document(
                schema_name="typing_browser_ai_transcript_status",
                schema_prefix=schema_prefix,
                version=version,
                generated_at=generated_at,
            ),
        }
    text_cleanup = typing_capture_contracts.browser_ai_transcript_clean_text(str(message.get("text") or ""))
    text = str(text_cleanup.get("text") or "")
    url = str(message.get("url") or "")
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    metadata = browser_ai_transcript_message_metadata(
        message,
        extension_id=extension_id,
        native_host=native_host,
        schema_prefix=schema_prefix,
    )
    metadata["text_cleanup"] = text_cleanup
    transcript_meta = metadata.get("ai_transcript") if isinstance(metadata.get("ai_transcript"), dict) else {}
    context = (
        f"browser_ai_transcript event_kind={event_kind} "
        f"transcript_safe={bool(_nested_get(metadata, ['browser', 'transcript_safe']))} "
        f"message_role={transcript_meta.get('message_role') or 'unknown'} "
        f"message_index={transcript_meta.get('message_index')} "
        f"partial={bool(transcript_meta.get('partial'))} "
        f"url={url}"
    )
    return {
        "valid": True,
        "route": BROWSER_AI_TRANSCRIPT_SOURCE,
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "extension_id": extension_id,
        "native_host": native_host,
        "text_cleanup": text_cleanup,
        "transcript_meta": transcript_meta,
        "ingest": {
            "text": text,
            "source": BROWSER_AI_TRANSCRIPT_SOURCE,
            "app": str(message.get("browser_name") or "firefox"),
            "window_title": str(message.get("title") or ""),
            "context": context,
            "url": url,
            "skip_duplicate": True,
            "metadata": metadata,
            "include_text_in_context_probe": True,
        },
    }


def browser_ai_transcript_status_document(
    plan: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    transcript_meta = plan.get("transcript_meta") if isinstance(plan.get("transcript_meta"), Mapping) else {}
    return {
        "schema": f"{schema_prefix}_typing_browser_ai_transcript_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(event.get("ok")),
        "status": "sent",
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "extension_id": plan.get("extension_id"),
        "native_host": plan.get("native_host"),
        "event": {
            "event_id": event.get("event_id"),
            "generated_at": event.get("generated_at"),
            "status": event.get("status"),
            "source_adapter": event.get("source_adapter"),
            "capture_gate_decision": _nested_get(event, ["capture_gate", "decision"]),
            "capture_gate_confidence": _nested_get(event, ["capture_gate", "confidence"]),
            "text_length": _nested_get(event, ["text", "text_length"]),
            "text_chars_stored": _nested_get(event, ["text", "text_chars_stored"]),
            "text_truncated": _nested_get(event, ["text", "truncated"]),
            "text_cleanup": plan.get("text_cleanup"),
            "duplicate": event.get("duplicate"),
            "recipient": _nested_get(event, ["causal_context", "recipient"]),
            "context_anchor": _nested_get(event, ["causal_context", "where", "context_anchor"]),
            "interaction": _nested_get(event, ["causal_context", "where", "interaction"]),
            "project_binding": _nested_get(event, ["causal_context", "where", "binding_signals", "project_binding"]),
            "message_role": transcript_meta.get("message_role"),
            "message_index": transcript_meta.get("message_index"),
            "partial": transcript_meta.get("partial"),
            "completeness": transcript_meta.get("completeness"),
        },
        "policy": {
            "raw_keylogging": False,
            "keydown_keyup_keypress_captured": False,
            "password_fields_captured": False,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "automatic_action": False,
            "capture_gate_required": True,
            "known_ai_counterpart_required": True,
            "transcript_safe_marker_required": True,
        },
        "non_claims": [
            "Browser AI transcript intake records visible AI-chat message text from known AI pages; it is not raw keylogging.",
            "Message completeness is explicit metadata and must not be treated as a full transcript proof when partial or unknown.",
            "AT-SPI browser content remains a fallback context route, not transcript authority.",
        ],
    }


def browser_extension_selftest_messages(test_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_message = {
        "schema": BROWSER_EXTENSION_MESSAGE_SCHEMA,
        "event_kind": "selftest",
        "browser_name": "firefox",
        "title": "Abyss browser typing selftest",
        "url": "https://example.com/abyss-input-selftest",
        "text": f"abyss browser explicit committed text selftest {test_run_id}",
        "field": {"safe": True, "kind": "textarea", "type": "textarea"},
    }
    sensitive_message = {
        "schema": BROWSER_EXTENSION_MESSAGE_SCHEMA,
        "event_kind": "selftest",
        "browser_name": "firefox",
        "title": "Login selftest",
        "url": "https://example.com/login",
        "text": f"should remain metadata only browser login probe {test_run_id}",
        "field": {"safe": True, "kind": "input", "type": "text"},
    }
    return safe_message, sensitive_message


def browser_extension_selftest_document(
    *,
    safe: Mapping[str, Any],
    sensitive: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    test_run_id: str,
) -> dict[str, Any]:
    safe_event = safe.get("event") if isinstance(safe.get("event"), Mapping) else {}
    sensitive_event = sensitive.get("event") if isinstance(sensitive.get("event"), Mapping) else {}
    return {
        "schema": f"{schema_prefix}_typing_browser_extension_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(safe.get("ok"))
        and bool(sensitive.get("ok"))
        and safe_event.get("capture_gate_decision") == "allow_text"
        and sensitive_event.get("capture_gate_decision") == "metadata_only",
        "status": "passed",
        "test_run_id": test_run_id,
        "source_adapter": BROWSER_EXTENSION_SOURCE,
        "safe": safe_event,
        "sensitive": sensitive_event,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "safe_route_allows_text": safe_event.get("capture_gate_decision") == "allow_text",
            "login_route_metadata_only": sensitive_event.get("capture_gate_decision") == "metadata_only",
        },
    }


def browser_ai_transcript_selftest_messages(test_run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    safe_message = {
        "schema": BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA,
        "event_kind": "ai_transcript_selftest",
        "browser_name": "firefox",
        "title": "Gemini transcript selftest",
        "url": "https://gemini.google.com/app/abyss-transcript-selftest",
        "text": f"Gemini assistant transcript selftest message {test_run_id}",
        "browser": {"transcript_safe": True, "event_kind": "ai_transcript_selftest"},
        "ai_transcript": {
            "safe": True,
            "message_role": "assistant",
            "message_index": 1,
            "message_order": 1,
            "partial": False,
            "selector_basis": "selftest",
            "reason": "selftest",
        },
    }
    sensitive_message = {
        **safe_message,
        "title": "Gemini login transcript selftest",
        "url": "https://gemini.google.com/login",
        "text": f"Gemini transcript login probe should stay metadata only {test_run_id}",
        "ai_transcript": {
            **safe_message["ai_transcript"],
            "message_index": 2,
            "message_order": 2,
        },
    }
    return safe_message, sensitive_message


def browser_ai_transcript_selftest_document(
    *,
    safe: Mapping[str, Any],
    sensitive: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    test_run_id: str,
) -> dict[str, Any]:
    safe_event = safe.get("event") if isinstance(safe.get("event"), Mapping) else {}
    sensitive_event = sensitive.get("event") if isinstance(sensitive.get("event"), Mapping) else {}
    data = {
        "schema": f"{schema_prefix}_typing_browser_ai_transcript_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(safe.get("ok"))
        and bool(sensitive.get("ok"))
        and safe_event.get("source_adapter") == BROWSER_AI_TRANSCRIPT_SOURCE
        and safe_event.get("capture_gate_decision") == "allow_text"
        and _nested_get(safe_event, ["recipient", "id"]) == "ai:google:gemini"
        and safe_event.get("message_role") == "assistant"
        and sensitive_event.get("capture_gate_decision") == "metadata_only"
        and _safe_int(sensitive_event.get("text_chars_stored"), 0) == 0,
        "status": "passed",
        "test_run_id": test_run_id,
        "source_adapter": BROWSER_AI_TRANSCRIPT_SOURCE,
        "safe": safe_event,
        "sensitive": sensitive_event,
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "safe_known_ai_route_allows_text": safe_event.get("capture_gate_decision") == "allow_text",
            "login_route_metadata_only": sensitive_event.get("capture_gate_decision") == "metadata_only",
            "recipient_is_ai_counterpart": _nested_get(safe_event, ["recipient", "id"]) == "ai:google:gemini",
            "automatic_action": False,
        },
    }
    if data["ok"] is not True:
        data["status"] = "failed"
    return data


def native_host_message_route(message: Mapping[str, Any]) -> str:
    event_kind = str(message.get("event_kind") or _nested_get(message, ["browser", "event_kind"]) or "")
    if message.get("schema") == BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA or event_kind.startswith("ai_transcript_"):
        return BROWSER_AI_TRANSCRIPT_SOURCE
    return BROWSER_EXTENSION_SOURCE


def native_host_decode_message_frame(
    header: bytes,
    body: bytes,
    *,
    max_message_bytes: int = NATIVE_HOST_MAX_MESSAGE_BYTES,
) -> dict[str, Any] | None:
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("native message header must be 4 bytes")
    length = struct.unpack("<I", header)[0]
    if length <= 0 or length > max_message_bytes:
        raise ValueError(f"native message length out of range: {length}")
    if len(body) != length:
        raise ValueError("native message body truncated")
    payload = json.loads(body.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("native message body must be a JSON object")
    return payload


def native_host_read_message(
    input_buffer: Any,
    *,
    max_message_bytes: int = NATIVE_HOST_MAX_MESSAGE_BYTES,
) -> dict[str, Any] | None:
    header = input_buffer.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("native message header must be 4 bytes")
    length = struct.unpack("<I", header)[0]
    if length <= 0 or length > max_message_bytes:
        raise ValueError(f"native message length out of range: {length}")
    body = input_buffer.read(length)
    return native_host_decode_message_frame(header, body, max_message_bytes=max_message_bytes)


def native_host_encode_response_frame(payload: Mapping[str, Any]) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def native_host_write_response(output_buffer: Any, payload: Mapping[str, Any]) -> None:
    output_buffer.write(native_host_encode_response_frame(payload))
    output_buffer.flush()


def native_host_response(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "event": result.get("event"),
        "policy": result.get("policy"),
    }


def native_host_error_response(error: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "native_host_error",
        "error": repr(error)[:240],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }
