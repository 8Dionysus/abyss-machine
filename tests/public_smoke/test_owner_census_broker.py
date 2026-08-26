from __future__ import annotations

import copy
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest

from abyss_machine.owner_census_broker import (
    BROKER_RECEIPT_SCHEMA,
    CENSUS_EVIDENCE_SCHEMA,
    CensusBounds,
    CensusBroker,
    CensusCapability,
    CensusContractError,
    CensusEvidence,
    CensusRequest,
    DescriptorEvidence,
    LinuxProcCensusBackend,
    MemoryKeyProvider,
    ProcessIdentity,
    ProcessReferenceEvidence,
    BrokerReceipt,
    BrokerReceiptVerifier,
    CensusSafetyError,
    ReceiptReplayGuard,
    ScannerFdCloseCapability,
    canonical_json,
    digest,
)


KEY = b"owner-census-test-key-0123456789"


def _request(*, bounds: CensusBounds | None = None, nonce: str = "request-nonce") -> CensusRequest:
    return CensusRequest(
        request_id="request-1",
        scan_scope="fixture-process-census",
        target_snapshot_digest="sha256:" + "1" * 64,
        target_identities=((10, 20, 30, "directory"), (11, 21, 31, "regular")),
        bounds=bounds or CensusBounds(8, 64, 8, 1_000_000_000),
        requested_at_ns=100,
        expires_at_ns=1_000,
        nonce=nonce,
    )


def _capability(request: CensusRequest, *, generation: str = "broker-generation-1", boot_id: str = "boot-1") -> CensusCapability:
    return CensusCapability(
        capability_id="runtime-capability-1",
        scan_scope=request.scan_scope,
        target_snapshot_digest=request.target_snapshot_digest,
        target_identities=request.target_identities,
        bounds=request.bounds,
        broker_id="broker-1",
        broker_generation=generation,
        broker_version="v49-test",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id=boot_id,
    )


def _process(pid: int, boot_id: str = "boot-1", *, descriptors=None) -> ProcessReferenceEvidence:
    return ProcessReferenceEvidence(
        ProcessIdentity(pid, 4000 + pid, boot_id, f"pidns:{pid};mntns:{pid}"),
        tuple(
            descriptors
            or (
                DescriptorEvidence("cwd", None, 10, 20, 30, "directory"),
            )
        ),
        uid=1000,
    )


def _evidence(
    request: CensusRequest,
    *,
    complete: bool = True,
    boot_id: str = "boot-1",
    processes: tuple[ProcessReferenceEvidence, ...] | None = None,
) -> CensusEvidence:
    process = ProcessReferenceEvidence(
        ProcessIdentity(42, 4242, boot_id, "pidns:42;mntns:42"),
        (
            DescriptorEvidence("cwd", None, 10, 20, 30, "directory"),
            DescriptorEvidence("root", None, 10, 20, 30, "directory"),
            DescriptorEvidence("fd", 3, 11, 21, 31, "regular", deleted=True),
        ),
        uid=1000,
    )
    return CensusEvidence(
        request_id=request.request_id,
        request_digest=request.request_digest,
        scan_scope=request.scan_scope,
        target_snapshot_digest=request.target_snapshot_digest,
        target_identities=request.target_identities,
        processes=(process,) if processes is None else processes,
        bounds=request.bounds,
        scan_started_ns=200,
        scan_completed_ns=201,
        complete=complete,
        backend_id="fixture-backend",
        backend_version="v49",
        reason="" if complete else "fixture incomplete",
    )


class _FixtureBackend:
    backend_id = "fixture-backend"
    backend_version = "v49"

    def __init__(self, evidence: CensusEvidence) -> None:
        self.evidence = evidence

    def scan(self, request: CensusRequest) -> CensusEvidence:
        assert request.request_id == self.evidence.request_id
        return self.evidence


def _broker(request: CensusRequest, *, complete: bool = True, generation: str = "broker-generation-1") -> CensusBroker:
    capability = _capability(request, generation=generation)
    return CensusBroker(
        backend=_FixtureBackend(_evidence(request, complete=complete)),
        key_provider=MemoryKeyProvider(KEY),
        capability=capability,
        clock_ns=lambda: 300,
    )


def test_request_evidence_and_receipt_wire_contracts_are_exact_and_round_trip() -> None:
    request = _request()
    assert CensusRequest.from_wire(request.as_wire()) == request
    evidence = _evidence(request)
    assert evidence.as_wire()["schema"] == CENSUS_EVIDENCE_SCHEMA
    receipt = _broker(request).issue(request, receipt_id="receipt-1")
    payload = receipt.as_wire()
    assert payload["schema"] == BROKER_RECEIPT_SCHEMA
    assert payload["nonce"] == request.nonce
    assert payload["receipt_digest"].startswith("sha256:")
    assert BrokerReceipt.from_wire(payload) == receipt
    assert payload["processes"][0]["descriptors"][2]["deleted"] is True


def test_max_descriptors_is_one_aggregate_typed_constructor_bound() -> None:
    request = _request(bounds=CensusBounds(8, 1, 8, 1_000_000_000))
    first = _process(42, descriptors=(DescriptorEvidence("fd", 3, 10, 20, 30, "regular"),))
    second = _process(43, descriptors=(DescriptorEvidence("fd", 4, 11, 21, 31, "regular"),))
    with pytest.raises(CensusContractError, match="aggregate descriptor bound"):
        _evidence(request, processes=(first, second))


@pytest.mark.parametrize("receipt_kind", ["evidence", "receipt"])
def test_max_descriptors_is_one_aggregate_wire_decoder_bound(receipt_kind: str) -> None:
    request = _request(bounds=CensusBounds(8, 2, 8, 1_000_000_000))
    first = _process(42, descriptors=(DescriptorEvidence("fd", 3, 10, 20, 30, "regular"),))
    second = _process(43, descriptors=(DescriptorEvidence("fd", 4, 11, 21, 31, "regular"),))
    evidence = _evidence(request, processes=(first, second))
    payload = evidence.as_wire()
    if receipt_kind == "receipt":
        payload = BrokerReceipt.issue(
            evidence=evidence,
            capability=_capability(request),
            signing_key=KEY,
            receipt_id="receipt-aggregate",
            issued_at_ns=300,
            expires_at_ns=900,
            nonce=request.nonce,
        ).as_wire()
    payload["bounds"]["max_descriptors"] = 1
    decoder = BrokerReceipt.from_wire if receipt_kind == "receipt" else CensusEvidence.from_wire
    with pytest.raises(CensusContractError, match="aggregate descriptor bound|descriptors"):
        decoder(payload)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: {**value, "complete": "false"}, "boolean"),
        (lambda value: {**value, "replay_counter": True}, "integer"),
        (lambda value: {**value, "signature": "claimed"}, "signature"),
        (lambda value: {**value, "receipt_digest": "sha256:" + "0" * 64}, "digest"),
        (lambda value: {**value, "unexpected": True}, "missing or unknown"),
        (lambda value: {key: item for key, item in value.items() if key != "nonce"}, "missing or unknown"),
    ],
)
def test_receipt_wire_decoder_rejects_coercion_forgery_and_shape_drift(change, message: str) -> None:
    receipt = _broker(_request()).issue(_request(), receipt_id="receipt-1")
    with pytest.raises(CensusContractError, match=message):
        BrokerReceipt.from_wire(change(receipt.as_wire()))


def test_receipt_verifier_binds_request_generation_boot_key_and_replay() -> None:
    request = _request()
    broker = _broker(request)
    receipt = broker.issue(request, receipt_id="receipt-1")
    verifier = BrokerReceiptVerifier(
        MemoryKeyProvider(KEY),
        broker_id="broker-1",
        broker_generation="broker-generation-1",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id="boot-1",
        clock_ns=lambda: 301,
    )
    verifier.verify(receipt, expected_request=request)
    with pytest.raises(CensusSafetyError, match="replay"):
        verifier.verify(receipt, expected_request=request)

    forged = BrokerReceipt.from_wire({**receipt.as_wire(), "signature": "hmac-sha256:" + "0" * 64})
    fresh = BrokerReceiptVerifier(
        MemoryKeyProvider(KEY),
        broker_id="broker-1",
        broker_generation="broker-generation-1",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id="boot-1",
        clock_ns=lambda: 301,
    )
    with pytest.raises(CensusSafetyError, match="authenticity"):
        fresh.verify(forged, expected_request=request)

    restarted = BrokerReceiptVerifier(
        MemoryKeyProvider(KEY),
        broker_id="broker-1",
        broker_generation="broker-generation-2",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id="boot-1",
        clock_ns=lambda: 301,
    )
    with pytest.raises(CensusSafetyError, match="generation"):
        restarted.verify(receipt, expected_request=request)


def _forged_aggregate_overflow_receipt() -> tuple[CensusRequest, BrokerReceipt]:
    request = _request(bounds=CensusBounds(8, 2, 8, 1_000_000_000))
    first = _process(42, descriptors=(DescriptorEvidence("fd", 3, 10, 20, 30, "regular"),))
    second = _process(43, descriptors=(DescriptorEvidence("fd", 4, 11, 21, 31, "regular"),))
    evidence = _evidence(request, processes=(first, second))
    receipt = BrokerReceipt.issue(
        evidence=evidence,
        capability=_capability(request),
        signing_key=KEY,
        receipt_id="receipt-verifier-aggregate",
        issued_at_ns=300,
        expires_at_ns=900,
        nonce=request.nonce,
    )
    forged = copy.copy(receipt)
    object.__setattr__(forged, "bounds", CensusBounds(8, 1, 8, 1_000_000_000))
    object.__setattr__(forged, "receipt_digest", digest(forged.unsigned()))
    signature = hmac.new(KEY, canonical_json(forged.unsigned()), hashlib.sha256).hexdigest()
    object.__setattr__(forged, "signature", "hmac-sha256:" + signature)
    return request, forged


@pytest.mark.parametrize("boundary", ["receipt", "verifier"])
def test_receipt_verification_rechecks_aggregate_before_replay(boundary: str) -> None:
    request, forged = _forged_aggregate_overflow_receipt()
    replay = ReceiptReplayGuard()
    if boundary == "receipt":
        with pytest.raises(CensusSafetyError, match="aggregate descriptor bound"):
            forged.verify(KEY, expected_request=request, now_ns=301, replay_store=replay)
    else:
        verifier = BrokerReceiptVerifier(
            MemoryKeyProvider(KEY),
            broker_id="broker-1",
            broker_generation="broker-generation-1",
            key_id="key-1",
            key_generation="key-generation-1",
            boot_id="boot-1",
            replay_store=replay,
            clock_ns=lambda: 301,
        )
        with pytest.raises(CensusSafetyError, match="aggregate descriptor bound"):
            verifier.verify(forged, expected_request=request)
    assert replay.seen(forged) is False


def _forged_target_overflow_receipt() -> BrokerReceipt:
    request = _request(bounds=CensusBounds(8, 64, 2, 1_000_000_000))
    receipt = BrokerReceipt.issue(
        evidence=_evidence(request),
        capability=_capability(request),
        signing_key=KEY,
        receipt_id="receipt-verifier-target",
        issued_at_ns=300,
        expires_at_ns=900,
        nonce="target-overflow",
    )
    forged = copy.copy(receipt)
    object.__setattr__(forged, "bounds", CensusBounds(8, 64, 1, 1_000_000_000))
    object.__setattr__(forged, "receipt_digest", digest(forged.unsigned()))
    signature = hmac.new(KEY, canonical_json(forged.unsigned()), hashlib.sha256).hexdigest()
    object.__setattr__(forged, "signature", "hmac-sha256:" + signature)
    return forged


@pytest.mark.parametrize("boundary", ["receipt", "verifier"])
def test_receipt_verification_rejects_target_bound_before_key_and_replay(boundary: str) -> None:
    forged = _forged_target_overflow_receipt()
    replay = ReceiptReplayGuard()
    provider = MemoryKeyProvider(KEY)
    if boundary == "receipt":
        with pytest.raises(CensusSafetyError, match="target identity bound"):
            forged.verify(
                KEY,
                expected_bounds=forged.bounds,
                expected_target_identities=forged.target_identities,
                now_ns=301,
                replay_store=replay,
            )
    else:
        verifier = BrokerReceiptVerifier(
            provider,
            broker_id="broker-1",
            broker_generation="broker-generation-1",
            key_id="key-1",
            key_generation="key-generation-1",
            boot_id="boot-1",
            replay_store=replay,
            clock_ns=lambda: 301,
        )
        with pytest.raises(CensusSafetyError, match="target identity bound"):
            verifier.verify(
                forged,
                expected_bounds=forged.bounds,
                expected_target_identities=forged.target_identities,
            )
    assert replay.seen(forged) is False


def test_incomplete_receipt_is_authentic_evidence_but_not_complete_admission() -> None:
    request = _request()
    receipt = _broker(request, complete=False).issue(request, receipt_id="receipt-incomplete")
    verifier = BrokerReceiptVerifier(
        MemoryKeyProvider(KEY),
        broker_id="broker-1",
        broker_generation="broker-generation-1",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id="boot-1",
        clock_ns=lambda: 301,
    )
    with pytest.raises(CensusSafetyError, match="incomplete"):
        verifier.verify(receipt, expected_request=request)
    verifier.verify(receipt, expected_request=request, require_complete=False)


def _proc_fixture(tmp_path: Path, *, pids: tuple[int, ...] = (1, 42, 77)) -> tuple[Path, Path]:
    proc = tmp_path / "proc"
    proc.mkdir()
    boot = proc / "sys" / "kernel" / "random"
    boot.mkdir(parents=True)
    (boot / "boot_id").write_text("fixture-boot\n", encoding="ascii")
    target_dir = tmp_path / "target-dir"
    target_dir.mkdir()
    target_file = tmp_path / "target-file"
    target_file.write_bytes(b"fixture")
    for pid in pids:
        root = proc / str(pid)
        (root / "ns").mkdir(parents=True)
        (root / "fd").mkdir()
        (root / "ns" / "pid").symlink_to(f"pid:[{1000 + pid}]")
        (root / "ns" / "mnt").symlink_to(f"mnt:[{2000 + pid}]")
        (root / "cwd").symlink_to(target_dir)
        (root / "root").symlink_to(target_dir)
        (root / "fd" / "3").symlink_to(target_file)
    return proc, target_file


def _fixture_backend(
    proc: Path,
    *,
    current_pid: int = 42,
    uid_reader=None,
    start_reader=None,
    boot_reader=None,
    mount_reader=None,
    readlink=None,
    stat_path=None,
    open_fd=None,
    monotonic_ns=None,
    fstat=None,
    close_fd=None,
) -> LinuxProcCensusBackend:
    return LinuxProcCensusBackend(
        proc_root=proc,
        current_pid=current_pid,
        current_uid_reader=lambda: 1000,
        uid_reader=(lambda _pid: 1000) if uid_reader is None else uid_reader,
        start_reader=(lambda pid: 100 + pid) if start_reader is None else start_reader,
        boot_id_reader=(lambda: "fixture-boot") if boot_reader is None else boot_reader,
        mount_id_reader=(lambda _fd: 700) if mount_reader is None else mount_reader,
        clock_ns=lambda: 500,
        monotonic_ns=(lambda: 0) if monotonic_ns is None else monotonic_ns,
        readlink=os.readlink if readlink is None else readlink,
        stat_path=stat_path,
        open_fd=open_fd,
        fstat=fstat,
        close_fd=close_fd,
    )


class _FalseyCallable:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def __bool__(self) -> bool:
        return False

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.value


def test_falsey_injected_readers_are_selected_and_used(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    readers = {
        "boot": _FalseyCallable("fixture-boot"),
        "start": _FalseyCallable(142),
        "uid": _FalseyCallable(1000),
        "mount": _FalseyCallable(700),
    }
    backend = _fixture_backend(
        proc,
        uid_reader=readers["uid"],
        start_reader=readers["start"],
        boot_reader=readers["boot"],
        mount_reader=readers["mount"],
    )
    assert backend._uid_reader is readers["uid"]
    assert backend._start_reader is readers["start"]
    assert backend._boot_id_reader is readers["boot"]
    assert backend._mount_id_reader is readers["mount"]
    evidence = backend.scan(_fixture_request())
    assert evidence.complete is True
    assert all(reader.calls > 0 for reader in readers.values())


def _active_scanner_fd(backend: LinuxProcCensusBackend) -> int:
    assert len(backend._active_scanner_fds) == 1
    return next(iter(backend._active_scanner_fds))


def test_paused_capability_cannot_close_reopened_same_number(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    first_path = tmp_path / "paused-first"
    replacement_path = tmp_path / "paused-replacement"
    first_path.write_bytes(b"first")
    replacement_path.write_bytes(b"replacement")
    entered = threading.Event()
    release = threading.Event()
    received: list[ScannerFdCloseCapability] = []
    errors: list[BaseException] = []

    def close_fd(capability: ScannerFdCloseCapability) -> None:
        assert isinstance(capability, ScannerFdCloseCapability)
        assert not isinstance(capability, int)
        assert not hasattr(capability, "fd")
        assert not hasattr(capability, "_backend")
        received.append(capability)
        entered.set()
        assert release.wait(timeout=5)
        capability.close()

    backend = _fixture_backend(proc, close_fd=close_fd)
    fd = backend._open_scanner_fd(first_path, os.O_RDONLY)
    first_owner = backend._scanner_fd_owners[fd]

    def close_in_thread() -> None:
        try:
            backend._close_scanner_fd(fd)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=close_in_thread)
    worker.start()
    assert entered.wait(timeout=5)
    os.close(fd)
    replacement_fd = os.open(replacement_path, os.O_RDONLY)
    assert replacement_fd == fd
    replacement_owner = backend._register_scanner_fd(replacement_fd, backend._scanner_fd_identity(replacement_fd))
    release.set()
    worker.join(timeout=5)
    try:
        assert not worker.is_alive()
        assert len(received) == 1
        assert errors and isinstance(errors[0], CensusSafetyError)
        assert "stale" in str(errors[0])
        os.fstat(replacement_fd)
        assert replacement_owner.generation > first_owner.generation
        assert backend._scanner_fd_owners[replacement_fd] == replacement_owner
        assert backend._active_scanner_fds == {replacement_fd}
    finally:
        os.close(replacement_fd)
        backend._forget_scanner_fd(replacement_fd)


def test_stale_and_replayed_close_capabilities_are_rejected(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    first_path = tmp_path / "capability-first"
    replacement_path = tmp_path / "capability-replacement"
    first_path.write_bytes(b"first")
    replacement_path.write_bytes(b"replacement")
    backend = _fixture_backend(proc)
    fd = backend._open_scanner_fd(first_path, os.O_RDONLY)
    generation = backend._scanner_fd_owners[fd].generation
    capability = backend._issue_scanner_fd_close_capability(fd)
    os.close(fd)
    replacement_fd = os.open(replacement_path, os.O_RDONLY)
    assert replacement_fd == fd
    replacement_owner = backend._register_scanner_fd(replacement_fd, backend._scanner_fd_identity(replacement_fd))
    try:
        with pytest.raises(CensusSafetyError, match="stale"):
            capability.close()
        os.fstat(replacement_fd)
        assert backend._scanner_fd_owners[replacement_fd] == replacement_owner
    finally:
        backend._release_scanner_fd_close(fd, generation)
        os.close(replacement_fd)
        backend._forget_scanner_fd(replacement_fd)

    seen: list[ScannerFdCloseCapability] = []

    def replaying_close(capability: ScannerFdCloseCapability) -> None:
        seen.append(capability)
        capability.close()
        with pytest.raises(CensusSafetyError, match="replayed"):
            capability.close()

    backend = _fixture_backend(proc, close_fd=replaying_close)
    fd = backend._open_scanner_fd(first_path, os.O_RDONLY)
    with pytest.raises(CensusSafetyError, match="replay"):
        backend._close_scanner_fd(fd)
    assert len(seen) == 1
    assert backend._active_scanner_fds == set()
    assert backend._scanner_fd_owners == {}


def test_close_callback_return_without_close_is_typed_failure_and_truthful(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    seen: list[ScannerFdCloseCapability] = []

    def no_close(capability: ScannerFdCloseCapability) -> None:
        seen.append(capability)

    backend = _fixture_backend(proc, close_fd=no_close)
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    try:
        with pytest.raises(CensusSafetyError, match="returned without closing"):
            backend._close_scanner_fd(fd)
        assert len(seen) == 1
        os.fstat(fd)
        assert backend._active_scanner_fds == {fd}
        assert backend._scanner_fd_owners[fd].generation >= 1
        with pytest.raises(CensusSafetyError, match="replayed"):
            seen[0].close()
    finally:
        os.close(fd)
        backend._forget_scanner_fd(fd)


def test_close_failure_before_close_retains_descriptor_and_preserves_error(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    opened: dict[str, int] = {}

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened["fd"] = fd
        return fd

    def close_fd(capability: ScannerFdCloseCapability) -> None:
        assert isinstance(capability, ScannerFdCloseCapability)
        raise OSError("close-before-raise")

    backend = _fixture_backend(proc, open_fd=open_fd, close_fd=close_fd)
    try:
        with pytest.raises(OSError, match="close-before-raise"):
            backend._observe_descriptor(42, "fd", 3)
        os.fstat(opened["fd"])
        assert backend._active_scanner_fds == {opened["fd"]}
        assert set(backend._active_scanner_fd_identities) == {opened["fd"]}
    finally:
        os.close(opened["fd"])
        backend._forget_scanner_fd(opened["fd"])


def test_close_after_close_then_raise_does_not_double_close(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    opened: dict[str, int] = {}

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened["fd"] = fd
        return fd

    def close_fd(capability: ScannerFdCloseCapability) -> None:
        capability.close()
        raise OSError("close-after-close-then-raise")

    backend = _fixture_backend(proc, open_fd=open_fd, close_fd=close_fd)
    with pytest.raises(OSError, match="close-after-close-then-raise"):
        backend._observe_descriptor(42, "fd", 3)
    with pytest.raises(OSError):
        os.fstat(opened["fd"])
    assert backend._active_scanner_fds == set()
    assert backend._active_scanner_fd_identities == {}


def test_close_failure_does_not_close_reused_fd_number(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    reused_path = tmp_path / "reused-after-close"
    reused_path.write_bytes(b"reused")
    opened: dict[str, int] = {}
    reused: dict[str, int] = {}

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened["fd"] = fd
        return fd

    def close_fd(capability: ScannerFdCloseCapability) -> None:
        assert isinstance(capability, ScannerFdCloseCapability)
        os.close(opened["fd"])
        reused["fd"] = os.open(reused_path, os.O_RDONLY)
        raise OSError("close-after-reuse")

    backend = _fixture_backend(proc, open_fd=open_fd, close_fd=close_fd)
    try:
        with pytest.raises(OSError, match="close-after-reuse"):
            backend._observe_descriptor(42, "fd", 3)
        assert reused["fd"] == opened["fd"]
        os.fstat(reused["fd"])
        assert backend._active_scanner_fds == set()
        assert backend._active_scanner_fd_identities == {}
    finally:
        if "fd" in reused:
            os.close(reused["fd"])


def test_injected_ebadf_preserves_error_and_clears_owned_generation(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    opened: dict[str, int] = {}

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened["fd"] = fd
        return fd

    def close_fd(capability: ScannerFdCloseCapability) -> None:
        assert isinstance(capability, ScannerFdCloseCapability)
        os.close(opened["fd"])
        raise OSError(errno.EBADF, "close-after-ebadf")

    backend = _fixture_backend(proc, open_fd=open_fd, close_fd=close_fd)
    with pytest.raises(OSError, match="close-after-ebadf") as raised:
        backend._observe_descriptor(42, "fd", 3)
    assert raised.value.errno == errno.EBADF
    with pytest.raises(OSError):
        os.fstat(opened["fd"])
    assert backend._active_scanner_fds == set()
    assert backend._active_scanner_fd_identities == {}


def test_unknown_close_state_retains_descriptor_and_exact_ledger(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    backend = _fixture_backend(proc, close_fd=lambda _fd: (_ for _ in ()).throw(OSError("injected")))
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    original_identity = backend._scanner_fd_identity
    backend._scanner_fd_identity = lambda _fd: (_ for _ in ()).throw(OSError("identity unavailable"))
    try:
        with pytest.raises(OSError, match="injected"):
            backend._close_scanner_fd(fd)
        assert backend._active_scanner_fds == {fd}
        assert set(backend._active_scanner_fd_identities) == {fd}
        assert fd in backend._scanner_fd_owners
    finally:
        backend._scanner_fd_identity = original_identity
        os.close(fd)
        backend._forget_scanner_fd(fd)


def test_recovery_never_closes_reused_fd_after_identity_observation(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement_path = tmp_path / "replacement-after-identity"
    replacement_path.write_bytes(b"replacement")
    backend = _fixture_backend(proc, close_fd=lambda _fd: (_ for _ in ()).throw(OSError("race-close")))
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    original_state = backend._scanner_fd_state
    state_seen = threading.Event()
    release_state = threading.Event()
    errors: list[BaseException] = []

    def gated_state(value: int, expected):
        state = original_state(value, expected)
        if state == "owned" and not state_seen.is_set():
            state_seen.set()
            assert release_state.wait(timeout=5)
        return state

    backend._scanner_fd_state = gated_state

    def close_in_thread() -> None:
        try:
            backend._close_scanner_fd(fd)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=close_in_thread)
    worker.start()
    assert state_seen.wait(timeout=5)
    os.close(fd)
    replacement_fd = os.open(replacement_path, os.O_RDONLY)
    try:
        release_state.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], OSError)
        os.fstat(replacement_fd)
        assert backend._active_scanner_fds == set()
        assert backend._active_scanner_fd_identities == {}
    finally:
        os.close(replacement_fd)
        backend._forget_scanner_fd(fd)


def test_capability_revalidates_reuse_after_first_observation(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement_path = tmp_path / "replacement-after-capability-observation"
    replacement_path.write_bytes(b"replacement")
    backend = _fixture_backend(proc)
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    capability = backend._issue_scanner_fd_close_capability(fd)
    original_state = backend._scanner_fd_state
    first_state_seen = threading.Event()
    release_first_state = threading.Event()
    state_calls = 0

    def gated_state(value: int, expected):
        nonlocal state_calls
        state = original_state(value, expected)
        state_calls += 1
        if state_calls == 1:
            first_state_seen.set()
            assert release_first_state.wait(timeout=5)
        return state

    backend._scanner_fd_state = gated_state
    worker_error: list[BaseException] = []

    def consume() -> None:
        try:
            capability.close()
        except BaseException as exc:
            worker_error.append(exc)

    worker = threading.Thread(target=consume)
    worker.start()
    assert first_state_seen.wait(timeout=5)
    os.close(fd)
    replacement_fd = os.open(replacement_path, os.O_RDONLY)
    try:
        release_first_state.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert worker_error and isinstance(worker_error[0], CensusSafetyError)
        assert "stale" in str(worker_error[0])
        os.fstat(replacement_fd)
        assert backend._active_scanner_fds == set()
        assert backend._scanner_fd_owners == {}
    finally:
        os.close(replacement_fd)
        backend._forget_scanner_fd(fd)


def test_stale_finalization_cannot_forget_reopened_scanner_generation(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement_path = tmp_path / "replacement-before-reopen"
    replacement_path.write_bytes(b"replacement")
    reopened_path = tmp_path / "scanner-reopened"
    reopened_path.write_bytes(b"reopened")
    backend = _fixture_backend(proc, close_fd=lambda _fd: (_ for _ in ()).throw(OSError("ledger-race")))
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    original_state = backend._scanner_fd_state
    first_state_seen = threading.Event()
    second_state_seen = threading.Event()
    release_first_state = threading.Event()
    release_second_state = threading.Event()
    state_calls = 0
    errors: list[BaseException] = []

    def two_phase_state(value: int, expected):
        nonlocal state_calls
        state = original_state(value, expected)
        state_calls += 1
        if state_calls == 1:
            first_state_seen.set()
            assert release_first_state.wait(timeout=5)
        elif state_calls == 2:
            second_state_seen.set()
            assert release_second_state.wait(timeout=5)
        return state

    backend._scanner_fd_state = two_phase_state

    def close_in_thread() -> None:
        try:
            backend._close_scanner_fd(fd)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=close_in_thread)
    worker.start()
    assert first_state_seen.wait(timeout=5)
    os.close(fd)
    replacement_fd = os.open(replacement_path, os.O_RDONLY)
    release_first_state.set()
    assert second_state_seen.wait(timeout=5)
    os.close(replacement_fd)
    reopened_fd = backend._open_scanner_fd(reopened_path, os.O_RDONLY)
    try:
        assert reopened_fd == fd
        release_second_state.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], OSError)
        os.fstat(reopened_fd)
        assert backend._active_scanner_fds == {reopened_fd}
        assert set(backend._active_scanner_fd_identities) == {reopened_fd}
        assert len(backend._scanner_fd_owners) == 1
    finally:
        os.close(reopened_fd)
        backend._forget_scanner_fd(reopened_fd)


def test_default_os_close_closes_descriptor_once_and_clears_ledger(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    opened: dict[str, int] = {}

    def open_fd(path: Path, flags: int) -> int:
        fd = os.open(path, flags)
        opened["fd"] = fd
        return fd

    backend = _fixture_backend(proc, open_fd=open_fd)
    backend._observe_descriptor(42, "fd", 3)
    with pytest.raises(OSError):
        os.fstat(opened["fd"])
    assert backend._active_scanner_fds == set()
    assert backend._active_scanner_fd_identities == {}


def test_close_callback_reentrancy_fails_immediately_and_outer_close_progresses(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    reentrant_errors: list[BaseException] = []
    backend: LinuxProcCensusBackend

    def reentrant_close(capability: ScannerFdCloseCapability) -> None:
        try:
            backend._close_scanner_fd(_active_scanner_fd(backend))
        except BaseException as exc:
            reentrant_errors.append(exc)
        capability.close()

    backend = _fixture_backend(proc, close_fd=reentrant_close)
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    backend._close_scanner_fd(fd)
    assert reentrant_errors and isinstance(reentrant_errors[0], CensusSafetyError)
    assert "already in progress" in str(reentrant_errors[0])
    assert backend._active_scanner_fds == set()
    assert backend._scanner_fd_owners == {}


def test_paused_callback_does_not_block_unrelated_backend_progress(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def paused_close(capability: ScannerFdCloseCapability) -> None:
        entered.set()
        assert release.wait(timeout=5)
        capability.close()

    backend = _fixture_backend(proc, close_fd=paused_close)
    other_backend = _fixture_backend(proc)
    first_fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)

    def close_in_thread() -> None:
        try:
            backend._close_scanner_fd(first_fd)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=close_in_thread)
    worker.start()
    assert entered.wait(timeout=5)
    other_fd = other_backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    os.fstat(other_fd)
    other_backend._close_scanner_fd(other_fd)
    assert other_backend._active_scanner_fds == set()
    release.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert errors == []
    assert backend._active_scanner_fds == set()
    assert backend._scanner_fd_owners == {}


def test_close_capability_fd_and_ledger_baseline_cleanup_are_exact(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    before = set(os.listdir("/proc/self/fd"))
    backend = _fixture_backend(proc)
    fd = backend._open_scanner_fd(tmp_path / "target-file", os.O_RDONLY)
    owner = backend._scanner_fd_owners[fd]
    assert backend._active_scanner_fds == {fd}
    assert backend._active_scanner_fd_identities[fd] == owner.identity
    os.fstat(fd)
    backend._close_scanner_fd(fd)
    after = set(os.listdir("/proc/self/fd"))
    assert backend._active_scanner_fds == set()
    assert backend._active_scanner_fd_identities == {}
    assert backend._scanner_fd_owners == {}
    assert after == before


def _fixture_request(*, max_processes: int = 8, max_descriptors: int = 64, max_duration_ns: int = 1_000_000_000) -> CensusRequest:
    return _request(bounds=CensusBounds(max_processes, max_descriptors, 8, max_duration_ns))


def test_fixture_census_inspects_stable_cwd_root_fds_and_live_regular_file(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)

    evidence = _fixture_backend(proc).scan(_fixture_request())
    assert evidence.complete is True
    by_pid = {item.process.pid: item for item in evidence.processes}
    assert {item.kind for item in by_pid[42].descriptors} == {"cwd", "root", "fd"}
    assert by_pid[77].descriptors[-1].deleted is False
    assert all(item.process.run_id.startswith("pidns:") for item in evidence.processes)


def test_literal_deleted_suffix_on_linked_regular_file_is_ambiguous(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/77/fd/3"):
            return str(target_file) + " (deleted)"
        return value

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is False
    assert "other-uid" in evidence.reason


def test_deleted_regular_file_requires_zero_inode_link_count(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    deleted_target = tmp_path / "deleted-target"
    deleted_target.write_bytes(b"fixture-deleted")
    (proc / "77" / "fd" / "3").unlink()
    (proc / "77" / "fd" / "3").symlink_to(deleted_target)

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/77/fd/3"):
            return str(deleted_target) + " (deleted)"
        return value

    def fstat(fd):
        value = os.fstat(fd)
        target = os.readlink(f"/proc/{os.getpid()}/fd/{fd}")
        if target == str(deleted_target):
            return SimpleNamespace(st_mode=value.st_mode, st_dev=value.st_dev, st_ino=value.st_ino, st_nlink=0)
        return value

    evidence = _fixture_backend(proc, readlink=readlink, fstat=fstat).scan(_fixture_request())
    assert evidence.complete is True
    by_pid = {item.process.pid: item for item in evidence.processes}
    assert by_pid[77].descriptors[-1].deleted is True


def test_fd_addition_after_inventory_snapshot_is_incomplete(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)
    calls = {"count": 0}

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/42/cwd"):
            calls["count"] += 1
            if calls["count"] == 2:
                (proc / "42" / "fd" / "4").symlink_to(target_file)
        return value

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is False
    assert "descriptor" in evidence.reason or "same-uid" in evidence.reason


def test_fd_removal_after_inventory_snapshot_is_incomplete(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    calls = {"count": 0}

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/42/fd/3"):
            calls["count"] += 1
            if calls["count"] == 2:
                (proc / "42" / "fd" / "3").unlink()
        return value

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is False


def test_fd_reuse_and_readlink_open_disagreement_is_incomplete(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"replacement")
    calls = {"count": 0}

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/42/fd/3"):
            calls["count"] += 1
            if calls["count"] == 1:
                return str(target_file)
            if calls["count"] == 2:
                return str(replacement)
        return value

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is False


def test_target_inode_change_between_readlink_and_open_is_incomplete(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)
    replacement = tmp_path / "replacement-inode"
    replacement.write_bytes(b"replacement")
    fd_path = proc / "42" / "fd" / "3"
    calls = {"count": 0}

    def open_fd(path: Path, flags: int) -> int:
        if path == fd_path and calls["count"] == 0:
            calls["count"] += 1
            os.replace(replacement, target_file)
        return os.open(path, flags)

    evidence = _fixture_backend(proc, open_fd=open_fd).scan(_fixture_request())
    assert evidence.complete is False
    assert calls["count"] == 1


def test_readlink_target_transition_between_readlink_and_open_is_incomplete(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)
    replacement = tmp_path / "replacement-target"
    replacement.write_bytes(b"replacement")
    fd_path = proc / "42" / "fd" / "3"
    calls = {"count": 0}

    def open_fd(path: Path, flags: int) -> int:
        if path == fd_path and calls["count"] == 0:
            calls["count"] += 1
            fd_path.unlink()
            fd_path.symlink_to(replacement)
        return os.open(path, flags)

    evidence = _fixture_backend(proc, open_fd=open_fd).scan(_fixture_request())
    assert evidence.complete is False
    assert calls["count"] == 1


@pytest.mark.parametrize("entry", ["cwd", "root"])
def test_cwd_or_root_target_transition_between_readlink_and_open_is_incomplete(tmp_path: Path, entry: str) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement = tmp_path / f"open-replacement-{entry}"
    replacement.mkdir()
    entry_path = proc / "42" / entry
    calls = {"count": 0}

    def open_fd(path: Path, flags: int) -> int:
        if path == entry_path and calls["count"] == 0:
            calls["count"] += 1
            entry_path.unlink()
            entry_path.symlink_to(replacement)
        return os.open(path, flags)

    evidence = _fixture_backend(proc, open_fd=open_fd).scan(_fixture_request())
    assert evidence.complete is False
    assert calls["count"] == 1


def test_cwd_or_root_unreadable_during_open_is_incomplete(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    root_path = proc / "42" / "root"

    def open_fd(path: Path, flags: int) -> int:
        if path == root_path:
            raise PermissionError("fixture root became unreadable")
        return os.open(path, flags)

    evidence = _fixture_backend(proc, open_fd=open_fd).scan(_fixture_request())
    assert evidence.complete is False


def test_fd_reuse_between_snapshot_and_revalidation_is_incomplete(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"replacement")
    calls: dict[int, int] = {}

    def start_reader(pid: int) -> int:
        calls[pid] = calls.get(pid, 0) + 1
        if pid == 42 and calls[pid] == 2:
            path = proc / "42" / "fd" / "3"
            path.unlink()
            path.symlink_to(replacement)
        return 100 + pid

    evidence = _fixture_backend(proc, start_reader=start_reader).scan(_fixture_request())
    assert evidence.complete is False


def test_descriptor_unreadable_transition_is_incomplete(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    calls = {"count": 0}

    def readlink(path):
        if str(path).endswith("/42/fd/3"):
            calls["count"] += 1
            if calls["count"] == 3:
                raise PermissionError("fixture descriptor became unreadable")
        return os.readlink(path)

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is False


@pytest.mark.parametrize("entry", ["cwd", "root"])
def test_cwd_or_root_target_change_between_passes_is_incomplete(tmp_path: Path, entry: str) -> None:
    proc, _ = _proc_fixture(tmp_path)
    replacement = tmp_path / f"replacement-{entry}"
    replacement.mkdir()
    calls: dict[int, int] = {}

    def start_reader(pid: int) -> int:
        calls[pid] = calls.get(pid, 0) + 1
        if pid == 42 and calls[pid] == 2:
            path = proc / "42" / entry
            path.unlink()
            path.symlink_to(replacement)
        return 100 + pid

    evidence = _fixture_backend(proc, start_reader=start_reader).scan(_fixture_request())
    assert evidence.complete is False


def test_scanner_owned_transient_fd_is_filtered_by_runtime_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    proc, target_file = _proc_fixture(tmp_path)
    (proc / "42" / "fd" / "4").symlink_to(target_file)
    backend = _fixture_backend(proc)
    transient_fd = 3
    backend._active_scanner_fds.add(transient_fd)
    monkeypatch.setattr(backend, "_is_actual_scanner_process", lambda _pid: True)
    monkeypatch.setattr(backend, "_scanner_fd_snapshot", lambda: {4})
    assert backend._enumerate_fd_numbers(42, 8) == [4]


@pytest.mark.parametrize("unreadable_pid", [1, 42, 77])
def test_fixture_census_is_incomplete_for_unreadable_pid1_same_uid_or_other_uid(tmp_path: Path, unreadable_pid: int) -> None:
    proc, _ = _proc_fixture(tmp_path)

    def uid_reader(pid: int) -> int:
        if pid == unreadable_pid:
            raise PermissionError("fixture unreadable")
        return 1000 if pid == 42 else 2000

    evidence = _fixture_backend(proc, uid_reader=uid_reader).scan(_fixture_request())
    assert evidence.complete is False
    assert "PID 1" in evidence.reason or "same-uid" in evidence.reason or "other-uid" in evidence.reason


def test_fixture_census_fails_closed_for_pid_churn_stale_boot_namespace_and_mount(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    calls: dict[int, int] = {}

    def changing_start(pid: int) -> int:
        calls[pid] = calls.get(pid, 0) + 1
        return 100 + pid + (1 if pid == 42 and calls[pid] >= 2 else 0)

    churn = _fixture_backend(proc, start_reader=changing_start).scan(_fixture_request())
    assert churn.complete is False
    assert "same-uid" in churn.reason

    boot_calls = {"count": 0}

    def changing_boot() -> str:
        boot_calls["count"] += 1
        return "fixture-boot" if boot_calls["count"] < 3 else "new-boot"

    stale = _fixture_backend(proc, boot_reader=changing_boot).scan(_fixture_request())
    assert stale.complete is False

    ambiguous = _fixture_backend(
        proc,
        readlink=lambda path: "mnt:[ambiguous]" if str(path).endswith("/42/ns/mnt") else os.readlink(path),
    ).scan(_fixture_request())
    assert ambiguous.complete is False

    no_mount = _fixture_backend(proc, mount_reader=lambda _fd: None).scan(_fixture_request())
    assert no_mount.complete is False


def test_fixture_census_fails_closed_for_process_and_duration_bounds(tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    over_processes = _fixture_backend(proc).scan(_fixture_request(max_processes=2))
    assert over_processes.complete is False
    assert "bound" in over_processes.reason

    over_descriptors = _fixture_backend(proc).scan(_fixture_request(max_descriptors=8))
    assert over_descriptors.complete is False
    assert "bound" in over_descriptors.reason

    monotonic_values = iter((0, 2))
    over_time = _fixture_backend(proc, monotonic_ns=lambda: next(monotonic_values)).scan(_fixture_request(max_duration_ns=1))
    assert over_time.complete is False


@pytest.mark.parametrize("receipt_kind", ["evidence", "receipt"])
def test_schema_boundary_is_structural_and_owner_semantic_validator_rejects_aggregate_overflow(receipt_kind: str) -> None:
    import jsonschema

    request = _request(bounds=CensusBounds(8, 2, 8, 1_000_000_000))
    first = _process(42, descriptors=(DescriptorEvidence("fd", 3, 10, 20, 30, "regular"),))
    second = _process(43, descriptors=(DescriptorEvidence("fd", 4, 11, 21, 31, "regular"),))
    evidence = _evidence(request, processes=(first, second))
    if receipt_kind == "evidence":
        payload = evidence.as_wire()
        schema_name = "pytest-owner-lifecycle-census-evidence-v1.schema.json"
        decoder = CensusEvidence.from_wire
    else:
        payload = BrokerReceipt.issue(
            evidence=evidence,
            capability=_capability(request),
            signing_key=KEY,
            receipt_id="receipt-schema-boundary",
            issued_at_ns=300,
            expires_at_ns=900,
            nonce=request.nonce,
        ).as_wire()
        schema_name = "pytest-owner-lifecycle-broker-receipt-v1.schema.json"
        decoder = BrokerReceipt.from_wire

    candidate = copy.deepcopy(payload)
    candidate["bounds"]["max_descriptors"] = 1
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(candidate)) == []
    with pytest.raises(CensusContractError, match="aggregate descriptor bound|descriptors"):
        decoder(candidate)


def test_unsupported_platform_is_incomplete_without_forcing_complete(monkeypatch, tmp_path: Path) -> None:
    proc, _ = _proc_fixture(tmp_path)
    monkeypatch.setattr("abyss_machine.owner_census_broker.sys.platform", "unsupported")
    evidence = _fixture_backend(proc).scan(_fixture_request())
    assert evidence.complete is False
    assert evidence.reason == "unsupported platform"


@pytest.mark.skipif(sys.platform != "linux", reason="live procfs is Linux-specific")
def test_live_procfs_census_accepts_incomplete_as_fail_closed() -> None:
    request = CensusRequest(
        request_id="live-request",
        scan_scope="runtime-supplied-live-probe",
        target_snapshot_digest="sha256:" + "2" * 64,
        target_identities=(),
        bounds=CensusBounds(1, 1, 1, 50_000_000),
        requested_at_ns=1,
        expires_at_ns=9_999_999_999_999_999,
        nonce="live-nonce",
    )
    evidence = LinuxProcCensusBackend().scan(request)
    assert evidence.complete is False or evidence.evidence_digest.startswith("sha256:")
