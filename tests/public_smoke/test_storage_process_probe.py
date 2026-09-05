from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

from abyss_machine import storage_process_probe


pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the authenticated AF_UNIX process-probe contract is Linux-only",
)


def _request(
    path: str, *, request_id: str = "test-request", **overrides: object
) -> bytes:
    payload: dict[str, object] = {
        "schema": storage_process_probe.REQUEST_SCHEMA,
        "request_id": request_id,
        "paths": [path],
        "max_refs_per_path": 4,
        "timeout_ms": 500,
    }
    payload.update(overrides)
    return json.dumps(payload).encode() + b"\n"


def test_path_allowlist_rejects_root_traversal_and_symlink_escape(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (allowed / "escape").symlink_to(outside, target_is_directory=True)
    roots = storage_process_probe.normalize_allowed_roots([allowed])

    assert (
        storage_process_probe.normalize_probe_paths(
            [str(allowed / "child")], allowed_roots=roots
        )[0][1]
        == allowed / "child"
    )
    for value in [
        str(allowed / ".." / "outside"),
        str(allowed / "escape" / "file"),
        "/",
    ]:
        with pytest.raises(storage_process_probe.ProcessProbeError):
            storage_process_probe.normalize_probe_paths([value], allowed_roots=roots)
    with pytest.raises(storage_process_probe.ProcessProbeError):
        storage_process_probe.normalize_allowed_roots([Path("/")])


def test_parse_request_enforces_shape_counts_and_bounds(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    roots = storage_process_probe.normalize_allowed_roots([root])
    payload = json.loads(_request(str(root / "work")))
    parsed = storage_process_probe.parse_request(payload, allowed_roots=roots)
    assert parsed["request_id"] == "test-request"
    assert parsed["paths"][0][1] == root / "work"

    for key, value in (
        ("max_refs_per_path", 0),
        ("max_refs_per_path", 33),
        ("timeout_ms", 99),
        ("timeout_ms", 30_001),
    ):
        invalid = dict(payload)
        invalid[key] = value
        with pytest.raises(storage_process_probe.ProcessProbeError):
            storage_process_probe.parse_request(invalid, allowed_roots=roots)
    invalid = dict(payload)
    invalid["extra"] = True
    with pytest.raises(storage_process_probe.ProcessProbeError):
        storage_process_probe.parse_request(invalid, allowed_roots=roots)

    with pytest.raises(storage_process_probe.ProcessProbeError):
        storage_process_probe.normalize_allowed_roots(
            [
                tmp_path / f"root-{index}"
                for index in range(storage_process_probe.MAX_ALLOWED_ROOTS + 1)
            ]
        )
    invalid = dict(payload)
    invalid["paths"] = [
        str(root / str(index)) for index in range(storage_process_probe.MAX_PATHS + 1)
    ]
    with pytest.raises(storage_process_probe.ProcessProbeError):
        storage_process_probe.parse_request(invalid, allowed_roots=roots)


def test_sanitize_probe_result_omits_cmdline_and_errors_force_incomplete() -> None:
    result = storage_process_probe.sanitize_probe_result(
        {
            "checked": True,
            "active": True,
            "pids_scanned": 2,
            "errors": ["permission denied with private detail"],
            "refs": [
                {
                    "pid": 12,
                    "source": "cwd",
                    "target": "/srv/AbyssOS/x",
                    "cmdline": "SECRET",
                }
            ],
        },
        source="test",
    )
    assert result["checked"] is False
    assert result["active"] is True
    assert result["refs"] == [{"pid": 12, "source": "cwd", "target": "/srv/AbyssOS/x"}]
    assert "cmdline" not in json.dumps(result)
    assert result["errors"] == ["process_probe_incomplete"]


@pytest.mark.parametrize(
    ("active", "refs", "errors"),
    [
        (
            False,
            [{"pid": 12, "source": "cwd", "target": "/srv/AbyssOS/x"}],
            [],
        ),
        (True, [], []),
        (False, [], "permission denied"),
    ],
)
def test_sanitize_probe_result_rejects_inconsistent_or_malformed_status(
    active: object, refs: object, errors: object
) -> None:
    result = storage_process_probe.sanitize_probe_result(
        {
            "checked": True,
            "active": active,
            "refs": refs,
            "errors": errors,
            "pids_scanned": 1,
        },
        source="test",
    )
    assert result["checked"] is False
    assert "process_probe_incomplete" in result["errors"]
    if refs:
        assert result["active"] is True


def test_socket_handler_authenticates_peer_and_returns_only_pathrefs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    client, server = socket.socketpair()

    def fake_scan(
        paths: tuple[str, ...], *, max_refs_per_path: int
    ) -> dict[str, object]:
        assert max_refs_per_path == 4
        return {
            paths[0]: {
                "checked": True,
                "active": True,
                "pids_scanned": 1,
                "errors": [],
                "refs": [
                    {
                        "pid": os.getpid(),
                        "source": "cwd",
                        "target": paths[0],
                        "cmdline": "PRIVATE",
                    }
                ],
            }
        }

    try:
        client.sendall(_request(str(root / "work")))
        client.shutdown(socket.SHUT_WR)
        response = storage_process_probe.handle_connection(
            server,
            allowed_uid=os.getuid(),
            allowed_roots=[root],
            scan_port=fake_scan,
        )
        received = json.loads(client.recv(1024 * 1024).decode())
    finally:
        client.close()
        server.close()
    assert response["ok"] is True
    assert received["authenticated"] is True
    assert received["complete"] is True
    assert received["results"][str(root / "work")]["active"] is True
    assert "cmdline" not in json.dumps(received)


def test_socket_handler_rejects_wrong_peer_uid(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    client, server = socket.socketpair()
    try:
        response = storage_process_probe.handle_connection(
            server,
            allowed_uid=os.getuid() + 1,
            allowed_roots=[root],
        )
        received = json.loads(client.recv(1024).decode())
    finally:
        client.close()
        server.close()
    assert response["ok"] is False
    assert response["error"] == "peer_uid_not_allowed"
    assert received["authenticated"] is False


def test_bounded_scan_timeout_terminates_probe_child() -> None:
    def slow_scan(
        _paths: tuple[str, ...], *, max_refs_per_path: int
    ) -> dict[str, object]:
        del max_refs_per_path
        time.sleep(2)
        return {}

    started = time.monotonic()
    result, error = storage_process_probe.bounded_scan(
        ["/srv/AbyssOS"],
        max_refs_per_path=1,
        timeout_ms=100,
        scan_port=slow_scan,
    )
    assert result is None
    assert error == "probe_timeout"
    assert time.monotonic() - started < 2


def test_protocol_request_and_response_sizes_are_bounded() -> None:
    client, server = socket.socketpair()
    try:
        client.sendall(b"x" * 17)
        client.shutdown(socket.SHUT_WR)
        assert storage_process_probe._read_request_line(server, 16) == (
            None,
            "request_too_large",
        )
    finally:
        client.close()
        server.close()
    with pytest.raises(
        storage_process_probe.ProcessProbeError, match="response_too_large"
    ):
        storage_process_probe._encode_response({"value": "x" * 100}, 16)


def test_client_accepts_authenticated_incomplete_response_without_fallback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    socket_path = tmp_path / "probe.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)

    def server() -> None:
        connection, _address = listener.accept()
        try:
            request = json.loads(
                connection.recv(storage_process_probe.MAX_REQUEST_BYTES).decode()
            )
            response = {
                "schema": storage_process_probe.RESPONSE_SCHEMA,
                "request_id": request["request_id"],
                "ok": True,
                "authenticated": True,
                "complete": False,
                "results": {
                    str(root / "work"): {
                        "checked": False,
                        "active": False,
                        "refs": [],
                        "errors": ["permission denied"],
                        "pids_scanned": 1,
                    }
                },
            }
            connection.sendall(json.dumps(response).encode() + b"\n")
        finally:
            connection.close()

    worker = threading.Thread(target=server)
    worker.start()
    try:
        result = storage_process_probe.owner_process_references(
            [str(root / "work")],
            socket_path=socket_path,
            allowed_roots=[root],
            expected_server_uid=os.getuid(),
            scan_port=lambda *_args, **_kwargs: pytest.fail(
                "incomplete server reply must not fallback"
            ),
        )
    finally:
        worker.join(timeout=5)
        listener.close()
    assert result[str(root / "work")]["checked"] is False
    assert result[str(root / "work")]["errors"] == ["process_probe_incomplete"]


def test_client_rejects_top_level_complete_mismatch_without_fallback(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    socket_path = tmp_path / "probe.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)

    def server() -> None:
        connection, _address = listener.accept()
        try:
            request = json.loads(
                connection.recv(storage_process_probe.MAX_REQUEST_BYTES).decode()
            )
            response = {
                "schema": storage_process_probe.RESPONSE_SCHEMA,
                "request_id": request["request_id"],
                "ok": True,
                "authenticated": True,
                "complete": True,
                "results": {
                    str(root / "work"): {
                        "checked": False,
                        "active": False,
                        "refs": [],
                        "errors": ["permission denied"],
                        "pids_scanned": 1,
                    }
                },
            }
            connection.sendall(json.dumps(response).encode() + b"\n")
        finally:
            connection.close()

    worker = threading.Thread(target=server)
    worker.start()
    try:
        result = storage_process_probe.owner_process_references(
            [str(root / "work")],
            socket_path=socket_path,
            allowed_roots=[root],
            expected_server_uid=os.getuid(),
            scan_port=lambda *_args, **_kwargs: pytest.fail(
                "protocol mismatch must not fallback"
            ),
        )
    finally:
        worker.join(timeout=5)
        listener.close()
    assert result[str(root / "work")]["source"] == "owner_probe_protocol"
    assert result[str(root / "work")]["errors"] == ["invalid_response"]


def test_bulk_owner_probe_isolates_out_of_scope_diagnostic_path(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    socket_path = tmp_path / "probe.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    valid = str(root / "work")
    invalid = str(outside / "work")
    seen_request: dict[str, object] = {}

    def server() -> None:
        connection, _address = listener.accept()
        try:
            raw = connection.recv(storage_process_probe.MAX_BULK_REQUEST_BYTES)
            seen_request.update(json.loads(raw.decode()))
            response = {
                "schema": storage_process_probe.RESPONSE_SCHEMA,
                "request_id": seen_request["request_id"],
                "ok": True,
                "authenticated": True,
                "complete": True,
                "results": {
                    valid: {
                        "checked": True,
                        "active": False,
                        "refs": [],
                        "errors": [],
                        "pids_scanned": 2,
                    }
                },
            }
            connection.sendall(json.dumps(response).encode() + b"\n")
        finally:
            connection.close()

    def fake_scan(
        paths: tuple[str, ...], *, proc_root: Path, max_refs_per_path: int
    ) -> dict[str, object]:
        assert proc_root == tmp_path / "proc"
        assert max_refs_per_path == 1
        assert paths == (invalid,)
        return {
            invalid: {
                "checked": True,
                "active": False,
                "refs": [],
                "errors": [],
                "pids_scanned": 2,
            }
        }

    worker = threading.Thread(target=server)
    worker.start()
    try:
        result = storage_process_probe.owner_process_references(
            [valid, invalid],
            socket_path=socket_path,
            allowed_roots=[root],
            expected_server_uid=os.getuid(),
            max_paths=storage_process_probe.MAX_BULK_PATHS,
            max_refs_per_path=1,
            max_request_bytes=storage_process_probe.MAX_BULK_REQUEST_BYTES,
            max_response_bytes=storage_process_probe.MAX_BULK_RESPONSE_BYTES,
            proc_root=tmp_path / "proc",
            scan_port=fake_scan,
        )
    finally:
        worker.join(timeout=5)
        listener.close()
    assert seen_request["paths"] == [valid]
    assert result[valid]["checked"] is True
    assert result[invalid]["checked"] is False
    assert "unprivileged_probe_incomplete" in result[invalid]["errors"]


def test_client_fixture_fallback_preserves_fixture_checked_semantics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()

    def fake_scan(
        paths: tuple[str, ...], *, proc_root: Path, max_refs_per_path: int
    ) -> dict[str, object]:
        assert proc_root == tmp_path / "proc"
        return {
            paths[0]: {
                "checked": True,
                "active": False,
                "refs": [],
                "errors": [],
                "pids_scanned": 1,
            }
        }

    result = storage_process_probe.owner_process_references(
        [str(root / "work")],
        socket_path=tmp_path / "missing.sock",
        allowed_roots=[root],
        proc_root=tmp_path / "proc",
        scan_port=fake_scan,
    )
    assert result[str(root / "work")]["checked"] is True


def test_client_real_proc_fallback_is_always_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(os, "geteuid", lambda: 1000)

    def fake_scan(
        paths: tuple[str, ...], *, proc_root: Path, max_refs_per_path: int
    ) -> dict[str, object]:
        assert proc_root == Path("/proc")
        return {
            paths[0]: {
                "checked": True,
                "active": False,
                "refs": [],
                "errors": [],
                "pids_scanned": 1,
            }
        }

    result = storage_process_probe.owner_process_references(
        [str(root / "work")],
        socket_path=tmp_path / "missing.sock",
        allowed_roots=[root],
        proc_root=Path("/proc"),
        scan_port=fake_scan,
    )
    assert result[str(root / "work")]["checked"] is False
    assert "unprivileged_probe_incomplete" in result[str(root / "work")]["errors"]


def test_systemd_templates_and_bootstrap_dispatch_are_dormant_source_routes() -> None:
    root = Path(__file__).resolve().parents[2]
    service = (root / "systemd/system/abyss-storage-process-probe.service").read_text()
    sock = (root / "systemd/system/abyss-storage-process-probe.socket").read_text()
    launcher = (root / "scripts/abyss-machine-bootstrap").read_text()
    assert "User=root" in service
    assert "ProtectSystem=strict" in service
    assert "RestrictAddressFamilies=AF_UNIX" in service
    assert "CapabilityBoundingSet=CAP_SYS_PTRACE CAP_DAC_READ_SEARCH" in service
    assert "MemoryMax=512M" in service
    assert "TasksMax=128" in service
    assert (
        "ABYSS_STORAGE_PROCESS_PROBE_ALLOWED_ROOTS={{ABYSS_MACHINE_SRV}}:{{ABYSS_OS_ROOT}}"
        in service
    )
    assert "ListenStream={{ABYSS_MACHINE_RUN}}/storage-process-probe.sock" in sock
    assert "SocketMode=0600" in sock
    assert '["storage", "process-probe"]' in launcher
    assert "abyss_machine.storage_process_probe" in launcher
    profile = json.loads(
        (root / "manifests/bootstrap_profiles.manifest.json").read_text()
    )
    profile_text = json.dumps(profile)
    assert "abyss-storage-process-probe.socket" not in profile_text
    assert "abyss-storage-process-probe.service" not in profile_text
