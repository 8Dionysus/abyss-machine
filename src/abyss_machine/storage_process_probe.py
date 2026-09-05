"""Bounded authenticated process-path observation for storage owners.

The privileged side of this module is intentionally a read-only systemd
socket worker.  It accepts one bounded JSON request, authenticates the peer
UID, and delegates the existing process-path scanner.  The worker never
receives commands, opens arbitrary files, or mutates storage.  A caller that
cannot reach the worker may use the existing scanner only as an explicitly
incomplete non-root ``/proc`` fallback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import argparse
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import socket
import struct
import sys
from typing import Any

from . import storage_candidate_adapters


REQUEST_SCHEMA = "abyss_machine_storage_process_probe_request_v1"
RESPONSE_SCHEMA = "abyss_machine_storage_process_probe_response_v1"
DEFAULT_SOCKET_PATH = Path("/run/abyss-machine/storage-process-probe.sock")
DEFAULT_ALLOWED_ROOTS = (Path("/srv/abyss-machine"), Path("/srv/AbyssOS"))
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_ALLOWED_ROOTS = 4
MAX_PATHS = 16
MAX_PATH_BYTES = 4096
MAX_REFS_PER_PATH = 32
MAX_TIMEOUT_MS = 30_000
DEFAULT_TIMEOUT_MS = 5_000
REQUEST_READ_TIMEOUT_SEC = 2.0
_REQUEST_FIELDS = frozenset(
    {"schema", "request_id", "paths", "max_refs_per_path", "timeout_ms"}
)


class ProcessProbeError(ValueError):
    """A request or host process-probe configuration is unsafe."""


def _current_euid() -> int | None:
    getter = getattr(os, "geteuid", None)
    if not callable(getter):
        return None
    try:
        return int(getter())
    except OSError:
        return None


def _failure(
    *,
    source: str,
    error: str,
    active: bool = False,
) -> dict[str, Any]:
    return {
        "checked": False,
        "active": bool(active),
        "refs": [],
        "errors": [error],
        "pids_scanned": 0,
        "source": source,
    }


def _safe_text(value: object, maximum: int) -> str | None:
    if not isinstance(value, str) or any(ord(char) < 32 for char in value):
        return None
    return value[:maximum]


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalized_root(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise ProcessProbeError("allowed root must be a path")
    text = str(value)
    if _safe_text(text, MAX_PATH_BYTES) is None or not text:
        raise ProcessProbeError("allowed root is malformed")
    if len(os.fsencode(text)) > MAX_PATH_BYTES:
        raise ProcessProbeError("allowed root is too long")
    path = Path(text)
    if not path.is_absolute() or ".." in path.parts:
        raise ProcessProbeError("allowed roots must be absolute and traversal-free")
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ProcessProbeError("allowed root cannot be resolved") from exc
    if resolved == Path("/"):
        raise ProcessProbeError("filesystem root is never an allowed probe root")
    return resolved


def normalize_allowed_roots(values: Sequence[str | Path]) -> tuple[Path, ...]:
    """Resolve a finite, non-root allowlist supplied by the owner unit."""
    if not isinstance(values, (tuple, list)) or not values:
        raise ProcessProbeError("at least one allowed probe root is required")
    if len(values) > MAX_ALLOWED_ROOTS:
        raise ProcessProbeError("allowed root count exceeds the host bound")
    roots: list[Path] = []
    for value in values:
        resolved = _normalized_root(value)
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def configured_allowed_roots(
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    source = os.environ if environ is None else environ
    raw = source.get("ABYSS_STORAGE_PROCESS_PROBE_ALLOWED_ROOTS")
    if raw is None or not raw.strip():
        return normalize_allowed_roots(DEFAULT_ALLOWED_ROOTS)
    return normalize_allowed_roots([item for item in raw.split(os.pathsep) if item])


def configured_allowed_uid(environ: Mapping[str, str] | None = None) -> int:
    """Read the peer UID from root-owned unit configuration."""
    source = os.environ if environ is None else environ
    raw = str(source.get("ABYSS_STORAGE_PROCESS_PROBE_ALLOWED_USER") or "").strip()
    if not raw:
        raise ProcessProbeError("allowed probe user is not configured")
    if raw.isdecimal():
        uid = int(raw)
    else:
        try:
            import pwd

            uid = int(pwd.getpwnam(raw).pw_uid)
        except (ImportError, KeyError, OSError, ValueError) as exc:
            raise ProcessProbeError("allowed probe user cannot be resolved") from exc
    if uid < 0:
        raise ProcessProbeError("allowed probe UID is invalid")
    return uid


def _normalized_request_path(
    value: object, allowed_roots: Sequence[Path]
) -> tuple[str, Path]:
    if _safe_text(value, MAX_PATH_BYTES) is None or not value:
        raise ProcessProbeError("probe path is malformed")
    if len(os.fsencode(value)) > MAX_PATH_BYTES:
        raise ProcessProbeError("probe path is too long")
    path = Path(value)
    if not path.is_absolute():
        raise ProcessProbeError("probe paths must be absolute")
    if ".." in path.parts:
        raise ProcessProbeError("probe path traversal is rejected")
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ProcessProbeError("probe path cannot be resolved") from exc
    if not any(_within(resolved, root) for root in allowed_roots):
        raise ProcessProbeError("probe path is outside the owner allowlist")
    return value, resolved


def normalize_probe_paths(
    values: object,
    *,
    allowed_roots: Sequence[Path],
    maximum: int = MAX_PATHS,
) -> tuple[tuple[str, Path], ...]:
    if not isinstance(values, (tuple, list)):
        raise ProcessProbeError("probe paths must be a bounded list")
    if not values or len(values) > maximum:
        raise ProcessProbeError("probe path count exceeds the request bound")
    normalized: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for value in values:
        original, resolved = _normalized_request_path(value, allowed_roots)
        if original in seen:
            raise ProcessProbeError("duplicate probe path")
        seen.add(original)
        normalized.append((original, resolved))
    return tuple(normalized)


def parse_request(payload: object, *, allowed_roots: Sequence[Path]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or set(payload) != _REQUEST_FIELDS:
        raise ProcessProbeError("request shape is not supported")
    if payload.get("schema") != REQUEST_SCHEMA:
        raise ProcessProbeError("request schema is not supported")
    request_id = payload.get("request_id")
    if _safe_text(request_id, 128) is None or not request_id or len(request_id) > 128:
        raise ProcessProbeError("request identity is malformed")
    roots = normalize_allowed_roots(allowed_roots)
    paths = normalize_probe_paths(payload.get("paths"), allowed_roots=roots)
    max_refs = payload.get("max_refs_per_path")
    timeout_ms = payload.get("timeout_ms")
    if type(max_refs) is not int or not 1 <= max_refs <= MAX_REFS_PER_PATH:
        raise ProcessProbeError("reference count bound is invalid")
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= MAX_TIMEOUT_MS:
        raise ProcessProbeError("probe timeout bound is invalid")
    return {
        "request_id": request_id,
        "paths": paths,
        "max_refs_per_path": max_refs,
        "timeout_ms": timeout_ms,
    }


def _peer_credentials(connection: socket.socket) -> tuple[int, int, int]:
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise ProcessProbeError("peer UID authentication is unavailable")
    raw = connection.getsockopt(
        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
    )
    if len(raw) != struct.calcsize("3i"):
        raise ProcessProbeError("peer credential record is malformed")
    pid, uid, gid = struct.unpack("3i", raw)
    if pid <= 0 or uid < 0 or gid < 0:
        raise ProcessProbeError("peer credential record is invalid")
    return pid, uid, gid


def _read_request_line(
    connection: socket.socket, maximum: int
) -> tuple[bytes | None, str | None]:
    data = bytearray()
    try:
        connection.settimeout(REQUEST_READ_TIMEOUT_SEC)
        while len(data) <= maximum:
            chunk = connection.recv(min(4096, maximum + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            newline = data.find(b"\n")
            if newline >= 0:
                if data[newline + 1 :].strip():
                    return None, "multiple_requests"
                return bytes(data[:newline]), None
        if len(data) > maximum:
            return None, "request_too_large"
        return bytes(data), None
    except (OSError, TimeoutError):
        return None, "request_read_failed"


def _error_code(value: object) -> str:
    """Turn scanner errors into bounded, non-content-bearing diagnostics."""
    if isinstance(value, str) and value in {
        "path_outside_allowlist",
        "probe_path_traversal",
        "probe_path_malformed",
        "probe_timeout",
        "probe_worker_unavailable",
        "probe_worker_failed",
        "unprivileged_probe_incomplete",
    }:
        return value
    return "process_probe_incomplete"


def sanitize_probe_result(value: object, *, source: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return _failure(source=source, error="process_probe_incomplete")
    checked = value.get("checked") is True
    active = value.get("active") is True
    refs: list[dict[str, Any]] = []
    raw_ref_value = value.get("refs")
    raw_refs = raw_ref_value if isinstance(raw_ref_value, list) else []
    malformed_refs = raw_ref_value is not None and not isinstance(raw_ref_value, list)
    for item in raw_refs[:MAX_REFS_PER_PATH]:
        if not isinstance(item, Mapping):
            malformed_refs = True
            continue
        pid = item.get("pid")
        source_name = _safe_text(item.get("source"), 64)
        target = _safe_text(item.get("target"), MAX_PATH_BYTES)
        if type(pid) is not int or pid <= 0 or source_name is None or target is None:
            malformed_refs = True
            continue
        # Deliberately omit cmdline and every other process metadata field.
        refs.append({"pid": pid, "source": source_name, "target": target})
    errors: list[str] = []
    raw_errors = value.get("errors")
    if isinstance(raw_errors, list) and raw_errors:
        errors.append(_error_code(raw_errors[0]))
    if value.get("error"):
        errors.append(_error_code(value.get("error")))
    if malformed_refs:
        errors.append("process_probe_incomplete")
    # A scanner that reports an error is incomplete even if a buggy adapter
    # left its checked bit set.  Never let a malformed result authorize a
    # destructive caller.
    if errors:
        checked = False
    if not checked and not errors:
        errors.append("process_probe_incomplete")
    deduplicated_errors = list(dict.fromkeys(errors))
    pids_scanned = value.get("pids_scanned")
    if type(pids_scanned) is not int or pids_scanned < 0:
        pids_scanned = 0
    return {
        "checked": checked,
        "active": active,
        "refs": refs,
        "errors": deduplicated_errors,
        "pids_scanned": min(pids_scanned, 1_000_000),
        "source": source,
    }


def _sanitize_results(
    paths: Sequence[tuple[str, Path]],
    raw_results: Mapping[str, Any] | None,
    *,
    source: str,
    force_incomplete: bool = False,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    raw_results = raw_results if isinstance(raw_results, Mapping) else {}
    for original, resolved in paths:
        raw = raw_results.get(str(resolved))
        if raw is None:
            raw = raw_results.get(original)
        result = sanitize_probe_result(raw, source=source)
        if force_incomplete:
            result["checked"] = False
            result["errors"] = list(
                dict.fromkeys([*result["errors"], "unprivileged_probe_incomplete"])
            )
        results[original] = result
    return results


def _scan_worker(
    paths: tuple[str, ...],
    max_refs_per_path: int,
    scan_port: Callable[..., Mapping[str, Any]],
    sender: Any,
) -> None:
    try:
        value = scan_port(paths, max_refs_per_path=max_refs_per_path)
        sender.send(dict(value) if isinstance(value, Mapping) else None)
    except BaseException:
        try:
            sender.send(None)
        except (OSError, EOFError, BrokenPipeError):
            pass
    finally:
        sender.close()


def bounded_scan(
    paths: Sequence[str],
    *,
    max_refs_per_path: int,
    timeout_ms: int,
    scan_port: Callable[
        ..., Mapping[str, Any]
    ] = storage_candidate_adapters.process_references,
) -> tuple[Mapping[str, Any] | None, str | None]:
    """Run the existing scanner in a killable, read-only bounded child."""
    if sys.platform != "linux":
        return None, "probe_worker_unavailable"
    receiver: Any | None = None
    sender: Any | None = None
    worker: multiprocessing.Process | None = None
    try:
        context = multiprocessing.get_context("fork")
        receiver, sender = context.Pipe(duplex=False)
        worker = context.Process(
            target=_scan_worker,
            args=(tuple(paths), max_refs_per_path, scan_port, sender),
        )
        worker.daemon = True
        worker.start()
        sender.close()
    except (OSError, RuntimeError, ValueError):
        try:
            if receiver is not None:
                receiver.close()
            if sender is not None:
                sender.close()
            if worker is not None and worker.is_alive():
                worker.terminate()
            if worker is not None:
                worker.join(timeout=1.0)
        except (AttributeError, OSError, RuntimeError):
            pass
        return None, "probe_worker_unavailable"
    assert receiver is not None
    assert worker is not None
    try:
        if not receiver.poll(timeout_ms / 1000.0):
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=1.0)
            return None, "probe_timeout"
        value = receiver.recv()
    except (EOFError, OSError, RuntimeError):
        value = None
    finally:
        receiver.close()
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=1.0)
    if not isinstance(value, Mapping):
        return None, "probe_worker_failed"
    return value, None


def _response_error(
    error: str,
    *,
    request_id: str | None = None,
    authenticated: bool = False,
) -> dict[str, Any]:
    return {
        "schema": RESPONSE_SCHEMA,
        "request_id": request_id,
        "ok": False,
        "authenticated": authenticated,
        "error": error,
        "results": {},
    }


def _encode_response(payload: Mapping[str, Any], maximum: int) -> bytes:
    encoded = (
        json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        + b"\n"
    )
    if len(encoded) > maximum:
        raise ProcessProbeError("response_too_large")
    return encoded


def handle_connection(
    connection: socket.socket,
    *,
    allowed_uid: int,
    allowed_roots: Sequence[Path],
    scan_port: Callable[
        ..., Mapping[str, Any]
    ] = storage_candidate_adapters.process_references,
    max_request_bytes: int = MAX_REQUEST_BYTES,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """Serve exactly one request on an already accepted AF_UNIX connection."""
    try:
        _pid, peer_uid, _gid = _peer_credentials(connection)
    except ProcessProbeError:
        response = _response_error("peer_uid_unavailable")
        try:
            connection.sendall(_encode_response(response, max_response_bytes))
        except OSError:
            pass
        return response
    if peer_uid != allowed_uid:
        response = _response_error("peer_uid_not_allowed")
        try:
            connection.sendall(_encode_response(response, max_response_bytes))
        except OSError:
            pass
        return response

    raw, read_error = _read_request_line(connection, max_request_bytes)
    if read_error is not None:
        response = _response_error(read_error, authenticated=True)
        try:
            connection.sendall(_encode_response(response, max_response_bytes))
        except OSError:
            pass
        return response
    try:
        payload = json.loads((raw or b"").decode("utf-8"))
        request = parse_request(payload, allowed_roots=allowed_roots)
    except (UnicodeDecodeError, json.JSONDecodeError, ProcessProbeError):
        response = _response_error("malformed_request", authenticated=True)
        try:
            connection.sendall(_encode_response(response, max_response_bytes))
        except OSError:
            pass
        return response

    pairs = request["paths"]
    raw_results, scan_error = bounded_scan(
        [str(resolved) for _original, resolved in pairs],
        max_refs_per_path=request["max_refs_per_path"],
        timeout_ms=request["timeout_ms"],
        scan_port=scan_port,
    )
    if scan_error:
        results = {
            original: _failure(source="privileged_proc_probe", error=scan_error)
            for original, _resolved in pairs
        }
    else:
        results = _sanitize_results(pairs, raw_results, source="privileged_proc_probe")
    complete = all(
        item.get("checked") is True and not item.get("errors")
        for item in results.values()
    )
    response: dict[str, Any] = {
        "schema": RESPONSE_SCHEMA,
        "request_id": request["request_id"],
        "ok": True,
        "authenticated": True,
        "complete": complete,
        "results": results,
    }
    try:
        encoded = _encode_response(response, max_response_bytes)
    except ProcessProbeError:
        response = _response_error(
            "response_too_large", request_id=request["request_id"], authenticated=True
        )
        encoded = _encode_response(response, max_response_bytes)
    try:
        connection.sendall(encoded)
    except OSError:
        pass
    return response


def _client_exchange(
    payload: Mapping[str, Any],
    *,
    socket_path: Path,
    expected_server_uid: int,
    timeout_ms: int,
    max_response_bytes: int,
    socket_factory: Callable[..., socket.socket] = socket.socket,
) -> tuple[dict[str, Any] | None, str | None, bool]:
    family = getattr(socket, "AF_UNIX", None)
    if family is None:
        return None, "owner_probe_unavailable", False
    try:
        with socket_factory(family, socket.SOCK_STREAM) as client:
            # The worker's bounded child may need a short termination/join
            # grace period after the requested scan budget expires.
            client.settimeout(max(0.1, timeout_ms / 1000.0 + 1.0))
            client.connect(str(socket_path))
            _pid, peer_uid, _gid = _peer_credentials(client)
            if peer_uid != expected_server_uid:
                return None, "server_peer_uid_not_allowed", True
            encoded = (
                json.dumps(
                    dict(payload),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
                + b"\n"
            )
            if len(encoded) > MAX_REQUEST_BYTES:
                return None, "request_too_large", True
            client.sendall(encoded)
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            received = 0
            while True:
                chunk = client.recv(min(65536, max_response_bytes + 1 - received))
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)
                if received > max_response_bytes:
                    return None, "response_too_large", True
    except (OSError, ProcessProbeError):
        return None, "owner_probe_unavailable", False
    try:
        response = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid_response", True
    if not isinstance(response, dict):
        return None, "invalid_response", True
    return response, None, True


def owner_process_references(
    paths: Sequence[str],
    *,
    socket_path: Path | None = None,
    allowed_roots: Sequence[Path] | None = None,
    expected_server_uid: int = 0,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    max_refs_per_path: int = MAX_REFS_PER_PATH,
    proc_root: Path = Path("/proc"),
    socket_factory: Callable[..., socket.socket] = socket.socket,
    scan_port: Callable[
        ..., Mapping[str, Any]
    ] = storage_candidate_adapters.process_references,
) -> dict[str, dict[str, Any]]:
    """Use the owner worker, with a strictly incomplete non-root fallback."""
    roots = normalize_allowed_roots(
        configured_allowed_roots() if allowed_roots is None else allowed_roots
    )
    try:
        pairs = normalize_probe_paths(paths, allowed_roots=roots)
    except ProcessProbeError as exc:
        return {
            str(value): _failure(
                source="local_request_validation", error=_error_code(str(exc))
            )
            for value in paths
            if isinstance(value, str)
        }
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= MAX_TIMEOUT_MS:
        return {
            original: _failure(
                source="local_request_validation", error="timeout_bound_invalid"
            )
            for original, _resolved in pairs
        }
    if (
        type(max_refs_per_path) is not int
        or not 1 <= max_refs_per_path <= MAX_REFS_PER_PATH
    ):
        return {
            original: _failure(
                source="local_request_validation", error="reference_count_bound_invalid"
            )
            for original, _resolved in pairs
        }
    path = Path(
        socket_path
        or os.environ.get(
            "ABYSS_STORAGE_PROCESS_PROBE_SOCKET", str(DEFAULT_SOCKET_PATH)
        )
    )
    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": secrets.token_hex(16),
        "paths": [original for original, _resolved in pairs],
        "max_refs_per_path": max_refs_per_path,
        "timeout_ms": timeout_ms,
    }
    response, exchange_error, responded = _client_exchange(
        request,
        socket_path=path,
        expected_server_uid=expected_server_uid,
        timeout_ms=timeout_ms,
        max_response_bytes=MAX_RESPONSE_BYTES,
        socket_factory=socket_factory,
    )
    if response is not None:
        if (
            response.get("schema") != RESPONSE_SCHEMA
            or response.get("request_id") != request["request_id"]
            or response.get("ok") is not True
            or response.get("authenticated") is not True
            or type(response.get("complete")) is not bool
            or not isinstance(response.get("results"), Mapping)
        ):
            return {
                original: _failure(
                    source="owner_probe_protocol", error="invalid_response"
                )
                for original, _resolved in pairs
            }
        raw_results = response["results"]
        if set(raw_results) != {original for original, _resolved in pairs}:
            return {
                original: _failure(
                    source="owner_probe_protocol", error="invalid_response"
                )
                for original, _resolved in pairs
            }
        return {
            original: sanitize_probe_result(
                raw_results.get(original), source="privileged_proc_probe"
            )
            for original, _resolved in pairs
        }
    if responded:
        return {
            original: _failure(
                source="owner_probe_auth",
                error=exchange_error or "owner_probe_unavailable",
            )
            for original, _resolved in pairs
        }

    # A real /proc fallback is a diagnostic observation only.  A root caller
    # without the worker must never turn its partial view into complete proof.
    euid = _current_euid()
    fallback_allowed = proc_root != Path("/proc") or (euid is not None and euid != 0)
    if not fallback_allowed:
        return {
            original: _failure(
                source="owner_probe_unavailable", error="owner_probe_unavailable"
            )
            for original, _resolved in pairs
        }

    def local_scan(
        scan_paths: Sequence[str], *, max_refs_per_path: int
    ) -> Mapping[str, Any]:
        return scan_port(
            scan_paths, proc_root=proc_root, max_refs_per_path=max_refs_per_path
        )

    raw_results, scan_error = bounded_scan(
        [str(resolved) for _original, resolved in pairs],
        max_refs_per_path=max_refs_per_path,
        timeout_ms=timeout_ms,
        scan_port=local_scan,
    )
    if scan_error:
        return {
            original: _failure(source="direct_proc_fallback", error=scan_error)
            for original, _resolved in pairs
        }
    return _sanitize_results(
        pairs,
        raw_results,
        source="direct_proc_fallback",
        force_incomplete=proc_root == Path("/proc") and (euid is None or euid != 0),
    )


def systemd_listener(environ: Mapping[str, str] | None = None) -> socket.socket:
    source = os.environ if environ is None else environ
    try:
        listen_pid = int(source.get("LISTEN_PID") or "0")
        listen_fds = int(source.get("LISTEN_FDS") or "0")
    except ValueError as exc:
        raise ProcessProbeError(
            "systemd socket activation metadata is malformed"
        ) from exc
    if listen_pid != os.getpid() or listen_fds != 1:
        raise ProcessProbeError("systemd socket activation is required")
    try:
        listener = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError as exc:
        raise ProcessProbeError("systemd listener is unavailable") from exc
    try:
        os.close(3)
    except OSError:
        listener.close()
        raise ProcessProbeError("systemd listener descriptor cannot be closed")
    if listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM:
        listener.close()
        raise ProcessProbeError("systemd listener is not an AF_UNIX stream")
    return listener


def serve(*, environ: Mapping[str, str] | None = None) -> int:
    allowed_uid = configured_allowed_uid(environ)
    allowed_roots = configured_allowed_roots(environ)
    listener = systemd_listener(environ)
    try:
        while True:
            connection, _address = listener.accept()
            try:
                handle_connection(
                    connection,
                    allowed_uid=allowed_uid,
                    allowed_roots=allowed_roots,
                )
            finally:
                connection.close()
    except KeyboardInterrupt:
        return 0
    finally:
        listener.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve", action="store_true", help="serve the root-owned systemd socket"
    )
    args = parser.parse_args(argv)
    if not args.serve:
        parser.error("--serve is required")
    try:
        return serve()
    except (OSError, ProcessProbeError) as exc:
        print(f"storage process probe: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
