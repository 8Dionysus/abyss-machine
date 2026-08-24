from __future__ import annotations

import os
from pathlib import Path
import sys

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
    GenerationReplayGuard,
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
        broker_version="v48-test",
        key_id="key-1",
        key_generation="key-generation-1",
        boot_id=boot_id,
    )


def _evidence(request: CensusRequest, *, complete: bool = True, boot_id: str = "boot-1") -> CensusEvidence:
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
        processes=(process,),
        bounds=request.bounds,
        scan_started_ns=200,
        scan_completed_ns=201,
        complete=complete,
        backend_id="fixture-backend",
        backend_version="v48",
        reason="" if complete else "fixture incomplete",
    )


class _FixtureBackend:
    backend_id = "fixture-backend"
    backend_version = "v48"

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


def _fixture_backend(proc: Path, *, current_pid: int = 42, uid_reader=None, start_reader=None, boot_reader=None, mount_reader=None, readlink=None, monotonic_ns=None) -> LinuxProcCensusBackend:
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
    )


def _fixture_request(*, max_processes: int = 8, max_descriptors: int = 64, max_duration_ns: int = 1_000_000_000) -> CensusRequest:
    return _request(bounds=CensusBounds(max_processes, max_descriptors, 8, max_duration_ns))


def test_fixture_census_inspects_cwd_root_fds_and_deleted_regular_file(tmp_path: Path) -> None:
    proc, target_file = _proc_fixture(tmp_path)

    def readlink(path):
        value = os.readlink(path)
        if str(path).endswith("/77/fd/3"):
            return str(target_file) + " (deleted)"
        return value

    evidence = _fixture_backend(proc, readlink=readlink).scan(_fixture_request())
    assert evidence.complete is True
    by_pid = {item.process.pid: item for item in evidence.processes}
    assert {item.kind for item in by_pid[42].descriptors} == {"cwd", "root", "fd"}
    assert by_pid[77].descriptors[-1].deleted is True
    assert all(item.process.run_id.startswith("pidns:") for item in evidence.processes)


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
