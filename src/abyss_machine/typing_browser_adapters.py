from __future__ import annotations

import html
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
from typing import Any, Callable, Mapping, MutableMapping

from . import typing_capture_contracts


BROWSER_EXTENSION_SOURCE = "browser_extension_explicit"
BROWSER_AI_TRANSCRIPT_SOURCE = "browser_ai_transcript"
BROWSER_EXTENSION_MESSAGE_SCHEMA = "abyss_machine_browser_extension_message_v1"
BROWSER_AI_TRANSCRIPT_MESSAGE_SCHEMA = "abyss_machine_browser_ai_transcript_message_v1"
NATIVE_HOST_MAX_MESSAGE_BYTES = 1024 * 1024

ProbeEventFinder = Callable[[str, int], tuple[dict[str, Any] | None, list[dict[str, Any]]]]
RunCommand = Callable[[list[str], float, dict[str, str] | None], dict[str, Any]]
TerminateProcesses = Callable[[str], list[dict[str, Any]]]
FocusCallback = Callable[..., dict[str, Any]]
AtspiAction = Callable[..., dict[str, Any]]
LiveContentCapture = Callable[..., dict[str, Any]]
ContextFromAtspiPath = Callable[..., dict[str, Any]]
UrlOrigin = Callable[[str], Mapping[str, Any] | None]
ProcessTail = Callable[..., str]
CaptureGateDecision = Callable[..., dict[str, Any]]
FocusedCandidateProbe = Callable[[Mapping[str, Any] | None], dict[str, Any]]
FocusedSnapshotFromCandidate = Callable[[dict[str, Any]], dict[str, Any]]


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


def _read_firefox_profiles_ini(profiles_ini: Path) -> list[str] | None:
    if not profiles_ini.exists():
        return None
    try:
        return profiles_ini.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def firefox_extension_profiles_from_lines(
    lines: list[str],
    *,
    profiles_root: Path,
    extension_id: str,
) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    for raw in lines + ["[end]"]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if current.get("Path"):
                path = Path(current.get("Path") or "")
                if current.get("IsRelative", "1") == "1":
                    path = profiles_root / path
                profiles.append({
                    "name": current.get("Name"),
                    "path": str(path),
                    "default": current.get("Default") == "1",
                    "extensions_json": str(path / "extensions.json"),
                    "sideload_xpi": str(path / "extensions" / f"{extension_id}.xpi"),
                })
            current = {}
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()
    return profiles


def firefox_extension_profiles(
    profiles_ini: Path,
    *,
    extension_id: str,
) -> list[dict[str, Any]]:
    lines = _read_firefox_profiles_ini(profiles_ini)
    if lines is None:
        return []
    return firefox_extension_profiles_from_lines(
        lines,
        profiles_root=profiles_ini.parent,
        extension_id=extension_id,
    )


def firefox_release_profile(
    profiles_ini: Path,
    *,
    extension_id: str,
) -> dict[str, Any] | None:
    lines = _read_firefox_profiles_ini(profiles_ini)
    if lines is None:
        return None
    current_section = ""
    install_default = ""
    for raw in lines:
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        if current_section.startswith("Install") and line.startswith("Default="):
            install_default = line.split("=", 1)[1].strip()
            break
    profiles = firefox_extension_profiles_from_lines(
        lines,
        profiles_root=profiles_ini.parent,
        extension_id=extension_id,
    )
    if install_default:
        for profile in profiles:
            if Path(str(profile.get("path") or "")).name == install_default:
                return {**profile, "selection": "install_default"}
    for profile in profiles:
        if str(profile.get("name") or "") == "default-release":
            return {**profile, "selection": "named_default_release"}
    for profile in profiles:
        if profile.get("default") is True:
            return {**profile, "selection": "profile_default"}
    return profiles[0] if profiles else None


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


def _omit_private_text_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _omit_private_text_fields(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_omit_private_text_fields(item) for item in value]
    return value


def _safe_process_tail(text: Any, max_chars: int = 1000) -> str:
    raw = str(text or "")[-4000:]
    redacted = re.sub(
        r"(?i)([?&](?:key|token|api[_-]?key|apikey|client[_-]?secret)=)[^\s&]+",
        r"\1[REDACTED:url_query_secret]",
        raw,
    )
    return redacted[-max(1, int(max_chars or 1000)):]


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


def browser_atspi_selftest_document(
    *,
    generated_at: str,
    pid: int,
    tmp_root: Path,
    schema_prefix: str,
    version: str,
    release_profile: bool,
    natural_route: bool,
    release_profile_info: Mapping[str, Any] | None,
    find_event: ProbeEventFinder,
    focus_window_by_title: FocusCallback,
    focus_text_by_path: AtspiAction,
    insert_text_by_path: AtspiAction,
    insert_text_by_url: AtspiAction,
    prepare_profile: Callable[[Path], dict[str, Any] | None] = prepare_firefox_selftest_profile,
    natural_route_host: Callable[[], str | None] = lambda: None,
    omit_private_text_fields: Callable[[Any], Any] = _omit_private_text_fields,
    process_tail: ProcessTail = _safe_process_tail,
    which: Callable[[str], str | None] = shutil.which,
    process_factory: Callable[..., Any] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    env_mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    run_id = browser_webextension_run_id(generated_at, pid)
    probe_suffix = f" {run_id} 424242"
    base_text = "safe writing surface committed text" if natural_route else "abyss browser atspi committed text probe"
    expected_text = base_text + probe_suffix
    base_sha = hashlib.sha256(base_text.encode("utf-8", errors="replace")).hexdigest()
    expected_sha = hashlib.sha256(expected_text.encode("utf-8", errors="replace")).hexdigest()
    page_script_probe_delays_ms = [4200, 6200, 8500]
    profile_dir = Path(str(release_profile_info.get("path"))) if isinstance(release_profile_info, Mapping) else tmp_root / "profile"
    site_dir = tmp_root / "site"
    stdout_tail = ""
    stderr_tail = ""
    type_result: dict[str, Any] | None = None
    firefox_returncode: int | None = None
    ready_event: dict[str, Any] | None = None
    event: dict[str, Any] | None = None
    parse_errors: list[dict[str, Any]] = []
    ready_parse_errors: list[dict[str, Any]] = []
    readiness_notes: list[dict[str, Any]] = []
    window_focus_attempt: dict[str, Any] | None = None
    focus_attempt: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = []

    firefox_bin = which("firefox")
    if not firefox_bin:
        return {
            "schema": f"{schema_prefix}_typing_browser_atspi_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "firefox_missing",
            "error": "firefox executable not found",
            "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        }
    if release_profile and not isinstance(release_profile_info, Mapping):
        return {
            "schema": f"{schema_prefix}_typing_browser_atspi_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "release_profile_missing",
            "error": "Firefox release profile was not found in profiles.ini",
            "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        }
    if natural_route and release_profile:
        return {
            "schema": f"{schema_prefix}_typing_browser_atspi_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "natural_route_requires_temporary_profile",
            "error": "--natural-route is intentionally limited to the temporary Firefox profile proof route",
            "natural_route": True,
            "policy": {
                "raw_keylogging": False,
                "password_fields_captured": False,
                "automatic_action": False,
                "temporary_firefox_profile": True,
                "release_profile_mutated": False,
            },
        }

    proc: Any | None = None
    httpd: socketserver.TCPServer | None = None
    server_thread: threading.Thread | None = None
    url = ""
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
        site_dir.mkdir(parents=True, exist_ok=True)
        if release_profile:
            if not profile_dir.exists():
                errors.append({"error": "release_profile_path_missing", "path": str(profile_dir)})
        else:
            profile_dir.mkdir(parents=True, exist_ok=True)
            prefs_error = prepare_profile(profile_dir)
            if prefs_error:
                errors.append(prefs_error)
        title = "Writing Surface" if natural_route else "Abyss browser AT-SPI safe input probe"
        textarea_id = "note" if natural_route else "probe"
        textarea_label = "Safe writing note" if natural_route else "Abyss safe browser probe"
        input_data = "text" if natural_route else "probe"
        page = f"""<!doctype html>
<meta charset=\"utf-8\">
<title>{html.escape(title)}</title>
<div id=\"{html.escape(textarea_id)}\" role=\"textbox\" aria-label=\"{html.escape(textarea_label)}\" contenteditable=\"true\" tabindex=\"0\" style=\"white-space: pre-wrap; min-height: 4rem;\"></div>
<script>
  const baseText = {json.dumps(base_text)};
  const expectedText = {json.dumps(expected_text)};
  const probeSuffix = {json.dumps(probe_suffix)};
  function getField() {{
    return document.getElementById({json.dumps(textarea_id)});
  }}
  function focusField(field) {{
    try {{
      field.focus({{preventScroll: true}});
    }} catch (error) {{
      field.focus();
    }}
  }}
  function moveCaretEnd(field) {{
    const range = document.createRange();
    range.selectNodeContents(field);
    range.collapse(false);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }}
  function dispatchCommittedInput(field, data) {{
    try {{
      field.dispatchEvent(new InputEvent(\"input\", {{bubbles: true, inputType: \"insertText\", data}}));
    }} catch (error) {{
      field.dispatchEvent(new Event(\"input\", {{bubbles: true}}));
    }}
  }}
  function emitBaseText() {{
    const field = getField();
    focusField(field);
    field.textContent = baseText;
    moveCaretEnd(field);
    dispatchCommittedInput(field, {json.dumps(input_data)});
  }}
  function emitExpectedText() {{
    const field = getField();
    focusField(field);
    if (field.textContent !== baseText) {{
      field.textContent = baseText;
    }}
    moveCaretEnd(field);
    let inserted = false;
    try {{
      inserted = document.execCommand(\"insertText\", false, probeSuffix);
    }} catch (error) {{
      inserted = false;
    }}
    if (!inserted || field.textContent !== expectedText) {{
      field.textContent = expectedText;
    }}
    moveCaretEnd(field);
    dispatchCommittedInput(field, probeSuffix);
  }}
  window.addEventListener(\"load\", emitBaseText);
  setTimeout(emitBaseText, 300);
  setTimeout(emitBaseText, 1200);
  setTimeout(emitBaseText, 2400);
  setTimeout(emitExpectedText, 4200);
  setTimeout(emitExpectedText, 6200);
  setTimeout(emitExpectedText, 8500);
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

        server_host = "127.0.0.1"
        if natural_route:
            detected_host = natural_route_host()
            if not detected_host:
                errors.append({"error": "nonloopback_ipv4_unavailable"})
                raise RuntimeError("nonloopback_ipv4_unavailable")
            server_host = detected_host
        httpd = ReusableTCPServer((server_host, 0), Handler)
        port = int(httpd.server_address[1])
        url = f"http://{server_host}:{port}/index.html"
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        process_env = dict(env_mapping or os.environ)
        process_env["MOZ_NO_REMOTE"] = "1"
        process_env.setdefault("GNOME_ACCESSIBILITY", "1")
        process_env.setdefault("NO_AT_BRIDGE", "0")
        process_env.setdefault("GTK_MODULES", "gail:atk-bridge")
        proc = process_factory(
            [firefox_bin, "--new-instance", "--profile", str(profile_dir), "--new-window", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=process_env,
            preexec_fn=os.setsid,
        )
        sleep(0.8)
        window_focus_attempt = focus_window_by_title(title, timeout_sec=3.0)
        ready_deadline = monotonic() + 12.0
        last_window_focus_at = monotonic()
        while monotonic() < ready_deadline:
            ready_event, ready_parse_errors = find_event(base_sha, 360)
            if isinstance(ready_event, dict) and ready_event.get("url") == url:
                break
            if monotonic() - last_window_focus_at >= 3.0:
                window_focus_attempt = focus_window_by_title(title, timeout_sec=2.0)
                last_window_focus_at = monotonic()
            ready_event = None
            sleep(0.5)
        if not isinstance(ready_event, dict):
            readiness_notes.append({
                "level": "info",
                "key": "browser_atspi_base_text_not_observed_before_type",
                "message": "base text was not observed before controlled typing; final committed-text event remains the authoritative proof",
                "url": url,
            })
        ready_source_path = str(_nested_get(ready_event, ["atspi", "source_path"]) or "") if isinstance(ready_event, dict) else ""
        if ready_source_path:
            focus_attempt = focus_text_by_path(ready_source_path, url, base_sha)
        sleep(0.3)
        insert_source_path = ready_source_path or str(_nested_get(focus_attempt, ["matched", "path"]) or "")
        type_result = (
            insert_text_by_path(insert_source_path, url, base_sha, probe_suffix)
            if insert_source_path
            else {
                "ok": False,
                "status": "target_path_missing",
                "method": "atspi_editable_text_insert",
                "error": "safe selftest field path was not observed",
                "policy": {
                    "raw_keylogging": False,
                    "password_fields_captured": False,
                    "global_virtual_keyboard": False,
                },
            }
        )
        if not (isinstance(type_result, dict) and type_result.get("ok")):
            fallback_insert = insert_text_by_url(url, base_sha, probe_suffix, timeout_sec=12.0)
            if isinstance(type_result, dict):
                type_result = {**fallback_insert, "path_insert": omit_private_text_fields(type_result)}
            else:
                type_result = fallback_insert
        deadline = monotonic() + 24.0
        while monotonic() < deadline:
            event, parse_errors = find_event(expected_sha, 420)
            if isinstance(event, dict):
                break
            sleep(0.5)
    except Exception as exc:
        errors.append({"error": repr(exc)[:500]})
    finally:
        stdout, stderr, firefox_returncode = _terminate_process_group(proc)
        stdout_tail = process_tail(stdout, max_chars=1000)
        stderr_tail = process_tail(stderr, max_chars=1000)
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
        and event.get("capture_gate_decision") == "allow_text"
        and event.get("capture_gate_confidence") == "atspi_browser_url_allowed"
        and event.get("text_sha256") == expected_sha
        and event.get("text_chars_stored") == len(expected_text)
    )
    targeted_insert_ok = bool(isinstance(type_result, dict) and type_result.get("ok"))
    page_script_controlled_insert_ok = bool(event_ok)
    input_proof_ok = bool(targeted_insert_ok or page_script_controlled_insert_ok)
    ok = bool(event_ok and not parse_errors and not errors and input_proof_ok)
    return {
        "schema": f"{schema_prefix}_typing_browser_atspi_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "run_id": run_id,
        "source_adapter": "atspi_text_changed_event",
        "natural_route": bool(natural_route),
        "url": url,
        "probe": {
            "base_text_sha256": base_sha,
            "text_sha256": expected_sha,
            "text_length": len(expected_text),
            "text_omitted": True,
            "attempts_targeted_atspi_insert": True,
            "uses_targeted_atspi_insert": targeted_insert_ok,
            "targeted_atspi_insert_confirmed": targeted_insert_ok,
            "uses_page_script_controlled_insert": True,
            "uses_global_virtual_keyboard": False,
            "synthetic_operator_like_text": bool(natural_route),
        },
        "proof_input": {
            "event_ok": event_ok,
            "targeted_atspi_insert_ok": targeted_insert_ok,
            "page_script_controlled_insert_ok": page_script_controlled_insert_ok,
            "accepted_route": "targeted_atspi_insert" if targeted_insert_ok else "page_script_controlled_insert" if page_script_controlled_insert_ok else None,
            "page_script_probe_delays_ms": page_script_probe_delays_ms,
        },
        "ready_event": ready_event,
        "readiness_notes": readiness_notes,
        "window_focus_attempt": omit_private_text_fields(window_focus_attempt) if isinstance(window_focus_attempt, dict) else None,
        "focus_attempt": omit_private_text_fields(focus_attempt),
        "event": event,
        "type_result": omit_private_text_fields(type_result),
        "firefox": {
            "binary": firefox_bin,
            "returncode": firefox_returncode,
            "profile": str(profile_dir),
            "profile_kind": "release_profile" if release_profile else "temporary_profile",
            "release_profile": release_profile_info,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        },
        "tmp_root": str(tmp_root),
        "ready_parse_errors": ready_parse_errors[:20],
        "parse_errors": parse_errors[:20],
        "errors": errors[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "internet_access": False,
            "loopback_http_only": not natural_route,
            "nonloopback_local_http_only": bool(natural_route),
            "targeted_atspi_insert_for_selftest_only": True,
            "page_script_controlled_insert_for_selftest_only": True,
            "global_virtual_keyboard": False,
            "requires_safe_browser_url": True,
            "temporary_firefox_profile": not release_profile,
            "release_profile_mutated": bool(release_profile),
        },
        "non_claims": [
            (
                "This selftest uses a local non-loopback HTTP page to prove browser AT-SPI natural-route recency; "
                "it is synthetic operator-like text, not proof of human typing."
            )
            if natural_route
            else "This selftest uses a loopback HTTP page; it does not prove the unsigned WebExtension is active.",
            "The selftest uses only the temporary safe page or a matched safe AT-SPI editable field; it does not use global key events.",
        ],
    }


def focused_browser_selftest_document(
    *,
    generated_at: str,
    pid: int,
    tmp_root: Path,
    schema_prefix: str,
    version: str,
    policy: Mapping[str, Any] | None,
    find_event: ProbeEventFinder,
    focus_window_by_title: FocusCallback,
    focus_text_by_path: AtspiAction,
    focus_text_by_url: AtspiAction,
    insert_text_by_url: AtspiAction,
    focused_candidate: FocusedCandidateProbe,
    focused_snapshot_from_candidate: FocusedSnapshotFromCandidate,
    capture_gate_decision: CaptureGateDecision,
    prepare_profile: Callable[[Path], dict[str, Any] | None] = prepare_firefox_selftest_profile,
    omit_private_text_fields: Callable[[Any], Any] = _omit_private_text_fields,
    process_tail: ProcessTail = _safe_process_tail,
    which: Callable[[str], str | None] = shutil.which,
    process_factory: Callable[..., Any] = subprocess.Popen,
    terminate_processes: TerminateProcesses | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    env_mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    run_id = browser_webextension_run_id(generated_at, pid)
    base_text = f"abyss focused browser committed text probe {run_id}"
    probe_text = base_text
    base_hash = hashlib.sha256(base_text.encode("utf-8", errors="replace")).hexdigest()
    probe_hash = hashlib.sha256(probe_text.encode("utf-8", errors="replace")).hexdigest()
    profile_dir = tmp_root / "profile"
    site_dir = tmp_root / "site"
    firefox_bin = which("firefox")
    stdout_tail = ""
    stderr_tail = ""
    firefox_returncode: int | None = None
    ready_event: dict[str, Any] | None = None
    ready_parse_errors: list[dict[str, Any]] = []
    focused_snapshot: dict[str, Any] | None = None
    candidate: dict[str, Any] | None = None
    candidate_attempts: list[dict[str, Any]] = []
    window_focus_attempt: dict[str, Any] | None = None
    focus_attempts: list[dict[str, Any]] = []
    noop_focus_attempts: list[dict[str, Any]] = []
    path_focus_attempts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    readiness_notes: list[dict[str, Any]] = []
    cleanup_actions: list[dict[str, Any]] = []
    url = ""

    if not firefox_bin:
        return {
            "schema": f"{schema_prefix}_typing_focused_browser_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "firefox_missing",
            "source_adapter": "atspi_focused_text_snapshot",
            "error": "firefox executable not found",
            "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        }

    proc: Any | None = None
    httpd: socketserver.TCPServer | None = None
    server_thread: threading.Thread | None = None
    policy_data = policy if isinstance(policy, Mapping) else {}
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
        site_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        prefs_error = prepare_profile(profile_dir)
        if prefs_error:
            errors.append(prefs_error)
        page = f"""<!doctype html>
<meta charset=\"utf-8\">
<title>Abyss focused browser safe input probe</title>
<textarea id=\"probe\" aria-label=\"Abyss focused safe browser note\" autocomplete=\"off\" autofocus></textarea>
<script>
  const probeText = {json.dumps(base_text)};
  function focusProbe() {{
    const probe = document.getElementById(\"probe\");
    probe.focus();
    probe.value = probeText;
    probe.setSelectionRange(probe.value.length, probe.value.length);
    probe.dispatchEvent(new InputEvent(\"input\", {{bubbles: true, inputType: \"insertText\", data: \"probe\"}}));
  }}
  window.addEventListener(\"load\", focusProbe);
  setTimeout(focusProbe, 300);
  setTimeout(focusProbe, 1200);
  setTimeout(focusProbe, 2400);
  const refocusUntil = Date.now() + 36000;
  const refocusTimer = setInterval(() => {{
    if (Date.now() > refocusUntil) {{
      clearInterval(refocusTimer);
      return;
    }}
    focusProbe();
  }}, 1000);
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

        process_env = dict(env_mapping or os.environ)
        process_env["MOZ_NO_REMOTE"] = "1"
        proc = process_factory(
            [firefox_bin, "--new-instance", "--profile", str(profile_dir), "--new-window", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=process_env,
            preexec_fn=os.setsid,
        )
        sleep(0.8)
        window_focus_attempt = focus_window_by_title("Abyss focused browser safe input probe", timeout_sec=3.0)
        ready_deadline = monotonic() + 28.0
        last_window_focus_at = monotonic()
        while monotonic() < ready_deadline:
            ready_event, ready_parse_errors = find_event(base_hash, 420)
            if isinstance(ready_event, dict) and ready_event.get("url") == url:
                break
            if monotonic() - last_window_focus_at >= 3.0:
                window_focus_attempt = focus_window_by_title("Abyss focused browser safe input probe", timeout_sec=2.0)
                last_window_focus_at = monotonic()
            ready_event = None
            if proc.poll() is not None:
                break
            sleep(0.5)
        if not isinstance(ready_event, dict):
            readiness_notes.append({
                "level": "info",
                "key": "focused_browser_base_text_not_observed_before_snapshot",
                "message": "base text was not observed through the text-event listener before focused snapshot; the focused snapshot event remains the authoritative proof",
                "url": url,
            })
        else:
            ready_source_path = str(_nested_get(ready_event, ["atspi", "source_path"]) or "")
            if ready_source_path:
                path_focus = focus_text_by_path(ready_source_path, url, base_hash)
                path_focus_attempts.append(omit_private_text_fields(path_focus))
                matched = path_focus.get("matched") if isinstance(path_focus.get("matched"), Mapping) else {}
                matched_text = str(matched.get("_text") or "")
                matched_sha = hashlib.sha256(matched_text.encode("utf-8", errors="replace")).hexdigest() if matched_text else ""
                if path_focus.get("ok") is True and matched_sha == probe_hash:
                    states_after = _nested_get(matched, ["focus", "states_after"])
                    states_after = states_after if isinstance(states_after, Mapping) else matched.get("states_before")
                    gate = capture_gate_decision(
                        "atspi_focused_text_snapshot",
                        app=str(ready_event.get("app") or "Firefox"),
                        window_title=str(ready_event.get("window_title") or ""),
                        context=f"focused_text role={matched.get('role')} path={ready_source_path} editable={bool((states_after or {}).get('editable'))} focused={bool((states_after or {}).get('focused'))} name={matched.get('name')} url={url}",
                        url=url,
                        policy=dict(policy_data),
                        write_latest=False,
                    )
                    candidate = {
                        "ok": True,
                        "app": str(ready_event.get("app") or "Firefox"),
                        "window_title": str(ready_event.get("window_title") or ""),
                        "role": str(matched.get("role") or "entry"),
                        "name": str(matched.get("name") or ""),
                        "description": "",
                        "path": ready_source_path,
                        "url": url,
                        "document_title": str(matched.get("document_title") or ""),
                        "content_type": str(_nested_get(ready_event, ["atspi", "content_type"]) or "text/html"),
                        "atspi_path": ready_source_path,
                        "document_path": str(_nested_get(ready_event, ["atspi", "document_path"]) or ""),
                        "url_query_present": False,
                        "url_fragment_present": False,
                        "raw_url_omitted": True,
                        "states": states_after or {},
                        "text_role": True,
                        "sensitive_context": False,
                        "sensitive_matches": [],
                        "capture_gate": gate,
                        "capture_gate_decision": str(gate.get("decision") or "metadata_only"),
                        "safe_route": "browser_safe_url" if gate.get("decision") == "allow_text" else None,
                        "safe_route_allowed": gate.get("decision") == "allow_text",
                        "browser_safe_url": gate.get("decision") == "allow_text",
                        "browser_context_inference": None,
                        "text_read_allowed": gate.get("decision") == "allow_text",
                        "diagnostic_only": False,
                        "text": matched_text,
                        "text_length": _safe_int(matched.get("text_length"), len(matched_text)),
                        "caret_offset": matched.get("_caret_offset") or _nested_get(ready_event, ["atspi", "caret_offset"]),
                    }
                    candidate_attempts.append(typing_capture_contracts.focused_browser_candidate_summary(candidate, probe_hash) or {})
        if not isinstance(candidate, dict):
            deadline = monotonic() + 20.0
            last_window_focus_at = 0.0
            while monotonic() < deadline:
                if monotonic() - last_window_focus_at >= 3.0:
                    window_focus_attempt = focus_window_by_title("Abyss focused browser safe input probe", timeout_sec=2.0)
                    last_window_focus_at = monotonic()
                focus_attempt = focus_text_by_url(url, probe_hash, timeout_sec=2.0)
                focus_attempts.append({
                    "ok": focus_attempt.get("ok"),
                    "status": focus_attempt.get("status"),
                    "nodes_seen": focus_attempt.get("nodes_seen"),
                    "matched": omit_private_text_fields(focus_attempt.get("matched")) if isinstance(focus_attempt.get("matched"), Mapping) else None,
                    "attempts": omit_private_text_fields(focus_attempt.get("attempts")) if isinstance(focus_attempt.get("attempts"), list) else [],
                    "error": focus_attempt.get("error"),
                })
                focus_attempts = focus_attempts[-4:]
                snapshot = focused_candidate(policy_data)
                item = snapshot.get("candidate") if isinstance(snapshot.get("candidate"), Mapping) else None
                summary = typing_capture_contracts.focused_browser_candidate_summary(item, probe_hash)
                if isinstance(summary, dict):
                    candidate_attempts.append(summary)
                    candidate_attempts = candidate_attempts[-8:]
                text = str(item.get("text") or "") if isinstance(item, Mapping) else ""
                text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest() if text else ""
                if (
                    isinstance(item, Mapping)
                    and item.get("text_read_allowed") is True
                    and item.get("safe_route") == "browser_safe_url"
                    and item.get("browser_safe_url") is True
                    and str(item.get("url") or "") == url
                    and text_sha == probe_hash
                ):
                    candidate = dict(item)
                    break
                noop_probe = insert_text_by_url(url, probe_hash, "", timeout_sec=2.0)
                noop_focus_attempts.append(omit_private_text_fields(noop_probe))
                noop_focus_attempts = noop_focus_attempts[-4:]
                matched = noop_probe.get("matched") if isinstance(noop_probe.get("matched"), Mapping) else {}
                matched_text = str(matched.get("_after_text") or matched.get("_text") or "")
                matched_sha = hashlib.sha256(matched_text.encode("utf-8", errors="replace")).hexdigest() if matched_text else ""
                if noop_probe.get("ok") is True and matched_sha == probe_hash:
                    gate = capture_gate_decision(
                        "atspi_focused_text_snapshot",
                        app="Firefox",
                        window_title="Abyss focused browser safe input probe - Mozilla Firefox",
                        context=f"focused_text role={matched.get('role')} path={matched.get('path')} editable={bool(_nested_get(matched, ['states_before', 'editable']))} focused={bool(_nested_get(matched, ['states_before', 'focused']))} name={matched.get('name')} url={url}",
                        url=url,
                        policy=dict(policy_data),
                        write_latest=False,
                    )
                    states_after = _nested_get(matched, ["field_focus", "states_after"])
                    candidate = {
                        "ok": True,
                        "app": "Firefox",
                        "window_title": "Abyss focused browser safe input probe - Mozilla Firefox",
                        "role": str(matched.get("role") or "entry"),
                        "name": str(matched.get("name") or ""),
                        "description": "",
                        "path": str(matched.get("path") or ""),
                        "url": url,
                        "document_title": str(matched.get("document_title") or ""),
                        "content_type": str(matched.get("content_type") or "text/html"),
                        "atspi_path": str(matched.get("path") or ""),
                        "document_path": str(matched.get("document_path") or ""),
                        "url_query_present": False,
                        "url_fragment_present": False,
                        "raw_url_omitted": True,
                        "states": states_after if isinstance(states_after, Mapping) else matched.get("states_before") or {},
                        "text_role": True,
                        "sensitive_context": False,
                        "sensitive_matches": [],
                        "sensitive_state_override": {
                            "allowed": True,
                            "reason": "controlled_firefox_loopback_selftest_noop_focus_probe",
                            "stores_extra_text": False,
                        },
                        "capture_gate": gate,
                        "capture_gate_decision": str(gate.get("decision") or "metadata_only"),
                        "safe_route": "browser_safe_url" if gate.get("decision") == "allow_text" else None,
                        "safe_route_allowed": gate.get("decision") == "allow_text",
                        "browser_safe_url": gate.get("decision") == "allow_text",
                        "browser_context_inference": None,
                        "text_read_allowed": gate.get("decision") == "allow_text",
                        "diagnostic_only": False,
                        "text": matched_text,
                        "text_length": _safe_int(matched.get("after_text_length"), len(matched_text)),
                        "caret_offset": matched.get("after_caret_offset") or matched.get("_caret_offset"),
                    }
                    candidate_attempts.append(typing_capture_contracts.focused_browser_candidate_summary(candidate, probe_hash) or {})
                    break
                if proc.poll() is not None:
                    break
                sleep(0.5)
        if isinstance(candidate, dict):
            focused_snapshot = focused_snapshot_from_candidate(candidate)
        else:
            errors.append({"error": "focused_browser_candidate_not_observed", "url": url})
    except Exception as exc:
        errors.append({"error": repr(exc)[:500]})
    finally:
        stdout, stderr, firefox_returncode = _terminate_process_group(proc)
        stdout_tail = process_tail(stdout, max_chars=1000)
        stderr_tail = process_tail(stderr, max_chars=1000)
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

    event = focused_snapshot.get("event") if isinstance(focused_snapshot, Mapping) and isinstance(focused_snapshot.get("event"), Mapping) else None
    event_summary = typing_capture_contracts.focused_browser_event_summary(event)
    event_ok = (
        isinstance(event_summary, dict)
        and event_summary.get("status") == "captured"
        and event_summary.get("source_adapter") == "atspi_focused_text_snapshot"
        and event_summary.get("capture_gate_decision") == "allow_text"
        and event_summary.get("capture_gate_confidence") == "focused_browser_safe_url_allowed"
        and event_summary.get("text_sha256") == probe_hash
        and event_summary.get("text_chars_stored") == len(probe_text)
        and event_summary.get("safe_route") == "browser_safe_url"
        and event_summary.get("browser_safe_url") is True
    )
    ok = bool(event_ok and not errors)
    return {
        "schema": f"{schema_prefix}_typing_focused_browser_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "run_id": run_id,
        "source_adapter": "atspi_focused_text_snapshot",
        "url": url,
        "probe": {
            "base_text_sha256": base_hash,
            "text_sha256": probe_hash,
            "text_length": len(probe_text),
            "text_omitted": True,
            "uses_ydotool_for_controlled_suffix": False,
        },
        "ready_event": ready_event,
        "candidate": typing_capture_contracts.focused_browser_candidate_summary(candidate, probe_hash),
        "candidate_attempts": candidate_attempts,
        "window_focus_attempt": omit_private_text_fields(window_focus_attempt) if isinstance(window_focus_attempt, Mapping) else None,
        "focus_attempts": focus_attempts,
        "noop_focus_attempts": noop_focus_attempts,
        "path_focus_attempts": path_focus_attempts[-4:],
        "focused_snapshot": {
            "schema": focused_snapshot.get("schema") if isinstance(focused_snapshot, Mapping) else None,
            "ok": focused_snapshot.get("ok") if isinstance(focused_snapshot, Mapping) else None,
            "status": focused_snapshot.get("status") if isinstance(focused_snapshot, Mapping) else None,
            "generated_at": focused_snapshot.get("generated_at") if isinstance(focused_snapshot, Mapping) else None,
            "event": event_summary,
        },
        "event": event_summary,
        "firefox": {
            "binary": firefox_bin,
            "returncode": firefox_returncode,
            "profile": str(profile_dir),
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "cleanup_actions": cleanup_actions[:40],
        },
        "tmp_root": str(tmp_root),
        "ready_parse_errors": ready_parse_errors[:20],
        "readiness_notes": readiness_notes[:20],
        "errors": errors[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "internet_access": False,
            "loopback_http_only": True,
            "temporary_firefox_profile": True,
            "release_profile_mutated": False,
            "temp_profile_network_prefs_disabled": True,
            "requires_safe_browser_url": True,
            "requires_capture_gate_allow_text": True,
            "focused_accessibility_text_only": True,
            "virtual_input_for_selftest_only": False,
            "targeted_atspi_noop_focus_probe_for_selftest_only": True,
        },
        "non_claims": [
            "This selftest proves focused snapshot capture only on a temporary Firefox loopback page.",
            "It does not read raw key events, password fields, cookies, local storage, or release Firefox profile data.",
            "It does not prove the Firefox WebExtension is active in release profiles.",
        ],
    }


def browser_context_selftest_document(
    *,
    generated_at: str,
    pid: int,
    tmp_root: Path,
    schema_prefix: str,
    version: str,
    events_policy: dict[str, Any] | None,
    focus_window_by_title: FocusCallback,
    focus_metadata_by_url: FocusCallback,
    live_content_capture: LiveContentCapture,
    context_from_recent_atspi_path: ContextFromAtspiPath,
    prepare_profile: Callable[[Path], dict[str, Any] | None] = prepare_firefox_selftest_profile,
    natural_route_host: Callable[[], str | None] = lambda: None,
    url_origin: UrlOrigin | None = None,
    omit_private_text_fields: Callable[[Any], Any] = _omit_private_text_fields,
    process_tail: ProcessTail = _safe_process_tail,
    which: Callable[[str], str | None] = shutil.which,
    process_factory: Callable[..., Any] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    env_mapping: MutableMapping[str, str] | None = None,
    deadline_seconds: float = 36.0,
    capture_env_overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    run_id = browser_webextension_run_id(generated_at, pid)
    profile_dir = tmp_root / "profile"
    site_dir = tmp_root / "site"
    firefox_bin = which("firefox")
    stdout_tail = ""
    stderr_tail = ""
    firefox_returncode: int | None = None
    captures: dict[str, Any] | None = None
    matched_capture: dict[str, Any] | None = None
    inference: dict[str, Any] | None = None
    window_focus_attempt: dict[str, Any] | None = None
    focus_attempt: dict[str, Any] | None = None
    capture_env = dict(capture_env_overrides or {
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_APPS": "16",
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_DOCUMENTS_PER_APP": "64",
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_SCAN_MAX_NODES": "24000",
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_TEXT_MAX_NODES": "12000",
        "ABYSS_MACHINE_NERVOUS_BROWSER_ATSPI_MAX_CHILDREN": "160",
    })
    runtime_env = env_mapping if env_mapping is not None else os.environ
    previous_capture_env: dict[str, str | None] = {}
    errors: list[dict[str, Any]] = []
    url = ""

    if not firefox_bin:
        return {
            "schema": f"{schema_prefix}_typing_browser_context_selftest_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "status": "firefox_missing",
            "error": "firefox executable not found",
            "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        }

    proc: Any | None = None
    httpd: socketserver.TCPServer | None = None
    server_thread: threading.Thread | None = None
    try:
        shutil.rmtree(tmp_root, ignore_errors=True)
        site_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        prefs_error = prepare_profile(profile_dir)
        if prefs_error:
            errors.append(prefs_error)
        page = f"""<!doctype html>
<meta charset=\"utf-8\">
<title>Abyss Writing Context</title>
<main>
  <h1>Abyss Writing Context</h1>
  <p>Safe browser context proof {html.escape(run_id)} links page title, URL origin, visible document text, and AT-SPI document path for an Abyss Machine typing route.</p>
  <p>The page represents a normal project reading surface: a short design note, a visible browser document, and a focused window that a future typed event can be connected to without reading private fields or account material.</p>
  <p>The capture should identify this as project context because the title names Abyss, the document is visible, and the body has enough meaningful language to separate it from browser chrome, media controls, counters, or thin navigation.</p>
  <p>The useful causal link is document first, then origin, then visible page context, then typed input. That gives later readmodels a better route for deciding where text was entered, what task it belonged to, and which browser surface was active.</p>
  <p>The proof text is public and intentionally boring. It carries no credentials, no personal identifiers, no account fields, no payment material, and no form values. The empty note area remains empty so the route proves context capture rather than form capture.</p>
  <textarea aria-label=\"Safe context note\"></textarea>
</main>
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

        server_host = natural_route_host() or "127.0.0.1"
        httpd = ReusableTCPServer((server_host, 0), Handler)
        port = int(httpd.server_address[1])
        url = f"http://{server_host}:{port}/index.html"
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        process_env = dict(runtime_env)
        process_env["MOZ_NO_REMOTE"] = "1"
        process_env.setdefault("GNOME_ACCESSIBILITY", "1")
        process_env.setdefault("NO_AT_BRIDGE", "0")
        process_env.setdefault("GTK_MODULES", "gail:atk-bridge")
        proc = process_factory(
            [firefox_bin, "--new-instance", "--profile", str(profile_dir), "--new-window", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=process_env,
            preexec_fn=os.setsid,
        )
        sleep(1.2)
        window_focus_attempt = focus_window_by_title("Abyss Writing Context", timeout_sec=3.0)
        for key, value in capture_env.items():
            previous_capture_env[key] = runtime_env.get(key)
            runtime_env[key] = value
        deadline = monotonic() + max(1.0, float(deadline_seconds or 36.0))
        last_focus_attempt_at = 0.0
        last_window_focus_attempt_at = monotonic()
        while monotonic() < deadline:
            if monotonic() - last_window_focus_attempt_at >= 3.0:
                window_focus_attempt = focus_window_by_title("Abyss Writing Context", timeout_sec=2.0)
                last_window_focus_attempt_at = monotonic()
            if monotonic() - last_focus_attempt_at >= 4.0:
                focus_attempt = focus_metadata_by_url(url, timeout_sec=3.0)
                last_focus_attempt_at = monotonic()
            captures = live_content_capture(write_latest=True)
            for item in captures.get("captures", []) if isinstance(captures, dict) else []:
                if not isinstance(item, dict):
                    continue
                record = item.get("record") if isinstance(item.get("record"), dict) else {}
                record_url = typing_capture_contracts.browser_content_record_url(record)
                if record_url == url and record.get("skipped_text") is not True:
                    matched_capture = item
                    break
            if matched_capture:
                break
            if proc.poll() is not None:
                break
            sleep(1.0)
        if isinstance(matched_capture, dict):
            record = matched_capture.get("record") if isinstance(matched_capture.get("record"), dict) else {}
            atspi = matched_capture.get("atspi") if isinstance(matched_capture.get("atspi"), dict) else {}
            if not atspi and isinstance(record.get("atspi_context"), dict):
                atspi = record["atspi_context"]
            path = str(atspi.get("path") or "")
            if path:
                inference = context_from_recent_atspi_path(
                    path,
                    path,
                    events_policy,
                    allow_attention_fallback=False,
                )
    except Exception as exc:
        errors.append({"error": repr(exc)[:500]})
    finally:
        for key, previous_value in previous_capture_env.items():
            if previous_value is None:
                runtime_env.pop(key, None)
            else:
                runtime_env[key] = previous_value
        stdout, stderr, firefox_returncode = _terminate_process_group(proc)
        stdout_tail = process_tail(stdout, max_chars=1000)
        stderr_tail = process_tail(stderr, max_chars=1000)
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

    matched_record = matched_capture.get("record") if isinstance(matched_capture, dict) and isinstance(matched_capture.get("record"), dict) else {}
    matched_atspi = matched_capture.get("atspi") if isinstance(matched_capture, dict) and isinstance(matched_capture.get("atspi"), dict) else {}
    text_record_ok = bool(
        matched_record
        and matched_record.get("skipped_text") is not True
        and _safe_int(matched_record.get("text_length"), 0) > 0
        and str(_nested_get(matched_record, ["content_quality", "classification"]) or "") == "usable"
    )
    inference_ok = bool(isinstance(inference, dict) and inference.get("ok") is True and inference.get("url") == url)
    ok = bool(text_record_ok and inference_ok and not errors)
    url_origin_doc = url_origin(typing_capture_contracts.browser_content_record_url(matched_record)) if matched_record and url_origin else None
    return {
        "schema": f"{schema_prefix}_typing_browser_context_selftest_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "run_id": run_id,
        "url": url,
        "capture": {
            "ok": captures.get("ok") if isinstance(captures, dict) else None,
            "status": "matched" if matched_capture else "missing_match",
            "summary": captures.get("summary") if isinstance(captures, dict) else None,
            "record": {
                "captured_at": matched_record.get("captured_at") if matched_record else None,
                "title": matched_record.get("title") if matched_record else None,
                "url_origin": _nested_get(url_origin_doc, ["origin"]) if matched_record else None,
                "content_type": matched_record.get("content_type") if matched_record else None,
                "text_captured": bool(
                    matched_record.get("skipped_text") is not True
                    and _safe_int(matched_record.get("text_length"), 0) > 0
                ) if matched_record else None,
                "text_length": matched_record.get("text_length") if matched_record else None,
                "skipped_text": matched_record.get("skipped_text") if matched_record else None,
                "web_context_class": _nested_get(matched_record, ["web_context_quality", "class"]) if matched_record else None,
                "content_quality_class": _nested_get(matched_record, ["content_quality", "classification"]) if matched_record else None,
            },
            "atspi": {
                "path": matched_atspi.get("path"),
                "role": matched_atspi.get("role"),
                "showing": matched_atspi.get("showing"),
                "visible": matched_atspi.get("visible"),
                "focused": matched_atspi.get("focused"),
            } if matched_atspi else None,
            "window_focus_attempt": omit_private_text_fields(window_focus_attempt) if isinstance(window_focus_attempt, dict) else None,
            "focus_attempt": omit_private_text_fields(focus_attempt) if isinstance(focus_attempt, dict) else None,
            "capture_env_overrides": capture_env,
        },
        "inference": {
            key: value
            for key, value in (inference or {}).items()
            if key not in {"url", "title"}
        } if isinstance(inference, dict) else None,
        "firefox": {
            "binary": firefox_bin,
            "returncode": firefox_returncode,
            "profile": str(profile_dir),
            "profile_kind": "temporary_profile",
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        },
        "tmp_root": str(tmp_root),
        "errors": errors[:20],
        "policy": {
            "raw_keylogging": False,
            "password_fields_captured": False,
            "form_values_captured": False,
            "cookies_captured": False,
            "local_storage_captured": False,
            "automatic_action": False,
            "temporary_firefox_profile": True,
            "release_profile_mutated": False,
            "uses_browser_content_capture": True,
            "uses_atspi_document_path_inference": True,
        },
        "non_claims": [
            "This proves safe browser document context capture and AT-SPI URL/context inference in a temporary Firefox profile.",
            "It does not prove the unsigned release-profile WebExtension is active.",
            "It does not collect raw key events, password fields, cookies, local storage, or form values.",
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
