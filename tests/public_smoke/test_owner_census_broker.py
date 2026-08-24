from __future__ import annotations

import os
from pathlib import Path
import sys
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
    monotonic_ns=None,
    fstat=None,
) -> LinuxProcCensusBackend:
    return LinuxProcCensusBackend(
        proc_root=proc,
        current_pid=current_pid,
        current_uid_reader=lambda: 1000,
        uid_reader=uid_reader or (lambda _pid: 1000),
        start_reader=start_reader or (lambda pid: 100 + pid),
        boot_id_reader=boot_reader or (lambda: "fixture-boot"),
        mount_id_reader=mount_reader or (lambda _fd: 700),
        clock_ns=lambda: 500,
        monotonic_ns=monotonic_ns or (lambda: 0),
        readlink=readlink or os.readlink,
        fstat=fstat,
    )


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
