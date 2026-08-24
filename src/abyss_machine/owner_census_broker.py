"""Bounded, read-only process census evidence and broker receipts.

This module is a host-owned observation boundary.  It accepts the scope,
target snapshot, limits, broker identity, and key/replay providers from the
caller at runtime.  It never treats a pathname, a process id, a free-space
measurement, or a receipt as permission to change host state.

The Linux backend deliberately returns ``complete=False`` when procfs,
namespace, mount, credential, or process-incarnation evidence is not
available.  A consumer may authenticate an incomplete receipt for diagnosis,
but a consumer that needs a complete census must reject it explicitly.

Descriptor completeness is observational stability only.  Each sampled
descriptor binds its textual readlink presentation to a followed target
identity before open, the opened fd identity, and a post-open followed
identity/readlink observation.  This cannot prove that an exact A→B→A
replacement happened between observations; consumers must not turn a complete
sample into a historical no-churn claim.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import threading
import time
from typing import Any, Protocol


CENSUS_REQUEST_SCHEMA = "pytest-owner-lifecycle-census-request-v1"
CENSUS_EVIDENCE_SCHEMA = "pytest-owner-lifecycle-census-evidence-v1"
BROKER_RECEIPT_SCHEMA = "pytest-owner-lifecycle-broker-receipt-v1"

# Runtime callers choose smaller limits.  These ceilings make malformed wire
# input finite even when a caller forgot to provide a sensible capability.
MAX_PROCESSES = 65_536
MAX_DESCRIPTORS = 262_144
MAX_TARGET_IDENTITIES = 65_536
MAX_DURATION_NS = 300_000_000_000
MAX_TEXT_LENGTH = 4_096
MAX_REASON_LENGTH = 512

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SIGNATURE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
_NAMESPACE = re.compile(r"^(pid|mnt):\[([0-9]+)\]$")
_OBJECT_KINDS = frozenset({"directory", "regular", "symlink", "special", "other"})
_DESCRIPTOR_KINDS = frozenset({"cwd", "root", "fd"})
_PROCESS_FIELDS = {"process", "descriptors", "uid"}


class CensusContractError(ValueError):
    """Malformed or structurally unsafe census contract data."""


class CensusSafetyError(CensusContractError):
    """Authenticated evidence cannot be admitted for the requested use."""


# Familiar names make the boundary easy to use without importing another
# error hierarchy.  They remain local aliases; no mutation API is exposed.
ContractError = CensusContractError
SafetyError = CensusSafetyError


def canonical_json(value: Any) -> bytes:
    """Return the one canonical byte representation used for digests/HMAC."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _fields(value: Any, expected: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise CensusContractError(f"{field} has missing or unknown fields")
    return value


def _text(value: Any, field: str, *, allow_empty: bool = False, limit: int = MAX_TEXT_LENGTH) -> str:
    if type(value) is not str or (not allow_empty and not value) or "\x00" in value or len(value) > limit:
        raise CensusContractError(f"{field} must be bounded text without NUL")
    return value


def _integer(value: Any, field: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise CensusContractError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise CensusContractError(f"{field} is below its lower bound")
    if maximum is not None and value > maximum:
        raise CensusContractError(f"{field} exceeds its bound")
    return value


def _positive(value: Any, field: str, *, maximum: int | None = None) -> int:
    return _integer(value, field, minimum=1, maximum=maximum)


def _nonnegative(value: Any, field: str, *, maximum: int | None = None) -> int:
    return _integer(value, field, minimum=0, maximum=maximum)


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise CensusContractError(f"{field} must be a boolean")
    return value


def _digest_text(value: Any, field: str) -> str:
    text = _text(value, field)
    if _DIGEST.fullmatch(text) is None:
        raise CensusContractError(f"{field} is not a sha256 digest")
    return text


def _signature_text(value: Any, field: str, *, pending: bool = False) -> str:
    if pending and value == "pending":
        return value
    if type(value) is not str or _SIGNATURE.fullmatch(value) is None:
        raise CensusContractError(f"{field} is not a structured HMAC signature")
    return value


def _wire_list(value: Any, field: str, *, maximum: int) -> list[Any]:
    if type(value) is not list:
        raise CensusContractError(f"{field} must be a JSON array")
    if len(value) > maximum:
        raise CensusContractError(f"{field} exceeds its collection bound")
    return value


def validate_aggregate_descriptor_bound(processes: Any, bounds: Any, field: str) -> int:
    """Authoritatively validate the typed aggregate descriptor bound.

    Standard JSON Schema validates the nested wire shape and scalar bounds,
    but it cannot express the dynamic sum of every process's descriptors.
    This owner semantic validator is therefore the aggregate admission gate
    for typed models, decoders, and broker consumers.
    """

    if not isinstance(bounds, CensusBounds):
        raise CensusContractError(f"{field} bounds are malformed")
    if type(processes) is not tuple:
        raise CensusContractError(f"{field} processes must be materialized")
    if len(processes) > bounds.max_processes:
        raise CensusContractError(f"{field} process bound is exhausted")
    total = 0
    for item in processes:
        if not isinstance(item, ProcessReferenceEvidence):
            raise CensusContractError(f"{field} process collection is malformed")
        total += len(item.descriptors)
        if total > bounds.max_descriptors:
            raise CensusContractError(f"{field} aggregate descriptor bound is exhausted")
    return total


def _validate_processes(processes: Any, bounds: Any, field: str) -> int:
    """Compatibility alias for the owner aggregate semantic validator."""

    return validate_aggregate_descriptor_bound(processes, bounds, field)


def _wire_processes(value: Any, bounds: Any, field: str) -> tuple["ProcessReferenceEvidence", ...]:
    """Preflight nested process arrays before constructing typed evidence."""

    if not isinstance(bounds, CensusBounds):
        raise CensusContractError(f"{field} bounds are malformed")
    raw_processes = _wire_list(value, field, maximum=bounds.max_processes)
    total = 0
    for index, item in enumerate(raw_processes):
        process_fields = _fields(item, _PROCESS_FIELDS, f"{field}[{index}]")
        remaining = bounds.max_descriptors - total
        descriptors = _wire_list(
            process_fields["descriptors"],
            f"{field}[{index}].descriptors",
            maximum=min(MAX_DESCRIPTORS, remaining),
        )
        total += len(descriptors)
    # The aggregate count has been checked before any nested descriptor tuple
    # is materialized by ProcessReferenceEvidence.from_wire.
    return tuple(ProcessReferenceEvidence.from_wire(item) for item in raw_processes)


def _identity_tuple(value: Any, field: str, *, wire: bool = False) -> tuple[int, int, int, str]:
    if isinstance(value, ObjectIdentity):
        result = value.as_tuple()
    elif isinstance(value, Mapping):
        fields = _fields(value, {"dev", "ino", "mount_id", "object_kind"}, field)
        result = (
            _nonnegative(fields["dev"], f"{field}.dev"),
            _nonnegative(fields["ino"], f"{field}.ino"),
            _nonnegative(fields["mount_id"], f"{field}.mount_id"),
            _text(fields["object_kind"], f"{field}.object_kind"),
        )
    elif type(value) is list and len(value) == 4:
        result = (
            _nonnegative(value[0], f"{field}.dev"),
            _nonnegative(value[1], f"{field}.ino"),
            _nonnegative(value[2], f"{field}.mount_id"),
            _text(value[3], f"{field}.object_kind"),
        )
    elif not wire and type(value) is tuple and len(value) == 4:
        result = (
            _nonnegative(value[0], f"{field}.dev"),
            _nonnegative(value[1], f"{field}.ino"),
            _nonnegative(value[2], f"{field}.mount_id"),
            _text(value[3], f"{field}.object_kind"),
        )
    else:
        raise CensusContractError(f"{field} is malformed")
    if result[3] not in _OBJECT_KINDS:
        raise CensusContractError(f"{field}.object_kind is unsupported")
    return result


def _identity_wire(value: Any, field: str) -> tuple[int, int, int, str]:
    return _identity_tuple(value, field, wire=True)


@dataclass(frozen=True, slots=True)
class ObjectIdentity:
    """Exact device/inode/mount/object identity; a path is intentionally absent."""

    dev: int
    ino: int
    mount_id: int
    object_kind: str

    def __post_init__(self) -> None:
        _nonnegative(self.dev, "object identity dev")
        _nonnegative(self.ino, "object identity ino")
        _nonnegative(self.mount_id, "object identity mount_id")
        _text(self.object_kind, "object identity object_kind")
        if self.object_kind not in _OBJECT_KINDS:
            raise CensusContractError("object identity object_kind is unsupported")

    def as_tuple(self) -> tuple[int, int, int, str]:
        return self.dev, self.ino, self.mount_id, self.object_kind

    def as_wire(self) -> list[Any]:
        return list(self.as_tuple())

    @classmethod
    def from_wire(cls, value: Any, field: str = "object identity") -> "ObjectIdentity":
        return cls(*_identity_wire(value, field))

    from_dict = from_wire
    as_dict = as_wire


ReferenceIdentity = tuple[int, int, int, str]


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    start_ticks: int
    boot_id: str
    run_id: str

    def __post_init__(self) -> None:
        _positive(self.pid, "process.pid")
        _positive(self.start_ticks, "process.start_ticks")
        _text(self.boot_id, "process.boot_id")
        _text(self.run_id, "process.run_id")

    def as_wire(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "start_ticks": self.start_ticks,
            "boot_id": self.boot_id,
            "run_id": self.run_id,
        }

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "ProcessIdentity":
        fields = _fields(value, {"pid", "start_ticks", "boot_id", "run_id"}, "process identity")
        return cls(
            _positive(fields["pid"], "process.pid"),
            _positive(fields["start_ticks"], "process.start_ticks"),
            _text(fields["boot_id"], "process.boot_id"),
            _text(fields["run_id"], "process.run_id"),
        )

    from_dict = from_wire

    def incarnation_key(self) -> tuple[int, int, str, str]:
        return self.pid, self.start_ticks, self.boot_id, self.run_id


@dataclass(frozen=True, slots=True)
class DescriptorEvidence:
    kind: str
    fd_number: int | None
    dev: int
    ino: int
    mount_id: int
    object_kind: str
    deleted: bool = False

    def __post_init__(self) -> None:
        _text(self.kind, "descriptor.kind")
        if self.kind not in _DESCRIPTOR_KINDS:
            raise CensusContractError("descriptor kind is unsupported")
        if self.kind == "fd":
            if self.fd_number is None:
                raise CensusContractError("fd descriptor requires fd_number")
            _nonnegative(self.fd_number, "descriptor.fd_number")
        elif self.fd_number is not None:
            raise CensusContractError("cwd/root descriptor cannot carry fd_number")
        _nonnegative(self.dev, "descriptor.dev")
        _nonnegative(self.ino, "descriptor.ino")
        _nonnegative(self.mount_id, "descriptor.mount_id")
        _text(self.object_kind, "descriptor.object_kind")
        if self.object_kind not in _OBJECT_KINDS:
            raise CensusContractError("descriptor object_kind is unsupported")
        _boolean(self.deleted, "descriptor.deleted")
        if self.deleted and self.object_kind != "regular":
            raise CensusContractError("only a regular file descriptor may be marked deleted")

    def identity(self) -> ReferenceIdentity:
        return self.dev, self.ino, self.mount_id, self.object_kind

    def as_wire(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "fd_number": self.fd_number,
            "dev": self.dev,
            "ino": self.ino,
            "mount_id": self.mount_id,
            "object_kind": self.object_kind,
            "deleted": self.deleted,
        }

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "DescriptorEvidence":
        fields = _fields(
            value,
            {"kind", "fd_number", "dev", "ino", "mount_id", "object_kind", "deleted"},
            "descriptor evidence",
        )
        fd_number = fields["fd_number"]
        if fd_number is not None:
            fd_number = _nonnegative(fd_number, "descriptor.fd_number")
        return cls(
            _text(fields["kind"], "descriptor.kind"),
            fd_number,
            _nonnegative(fields["dev"], "descriptor.dev"),
            _nonnegative(fields["ino"], "descriptor.ino"),
            _nonnegative(fields["mount_id"], "descriptor.mount_id"),
            _text(fields["object_kind"], "descriptor.object_kind"),
            _boolean(fields["deleted"], "descriptor.deleted"),
        )

    from_dict = from_wire
    from_value = from_wire


@dataclass(frozen=True, slots=True)
class ProcessReferenceEvidence:
    process: ProcessIdentity
    descriptors: tuple[DescriptorEvidence, ...]
    uid: int

    def __post_init__(self) -> None:
        if not isinstance(self.process, ProcessIdentity):
            raise CensusContractError("process evidence identity is malformed")
        if type(self.descriptors) is not tuple:
            raise CensusContractError("process evidence descriptors must be materialized")
        if any(not isinstance(item, DescriptorEvidence) for item in self.descriptors):
            raise CensusContractError("process evidence descriptors are malformed")
        if len(self.descriptors) > MAX_DESCRIPTORS:
            raise CensusContractError("process evidence descriptor ceiling is exhausted")
        _nonnegative(self.uid, "process evidence uid")

    def as_wire(self) -> dict[str, Any]:
        return {
            "process": self.process.as_wire(),
            "descriptors": [item.as_wire() for item in self.descriptors],
            "uid": self.uid,
        }

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "ProcessReferenceEvidence":
        fields = _fields(value, _PROCESS_FIELDS, "process reference evidence")
        descriptors = _wire_list(fields["descriptors"], "process descriptors", maximum=MAX_DESCRIPTORS)
        return cls(
            ProcessIdentity.from_wire(fields["process"]),
            tuple(DescriptorEvidence.from_wire(item) for item in descriptors),
            _nonnegative(fields["uid"], "process evidence uid"),
        )

    from_dict = from_wire
    from_value = from_wire


@dataclass(frozen=True, slots=True)
class CensusBounds:
    max_processes: int
    max_descriptors: int
    max_target_identities: int
    max_duration_ns: int

    def __post_init__(self) -> None:
        _positive(self.max_processes, "bounds.max_processes", maximum=MAX_PROCESSES)
        _positive(self.max_descriptors, "bounds.max_descriptors", maximum=MAX_DESCRIPTORS)
        _positive(self.max_target_identities, "bounds.max_target_identities", maximum=MAX_TARGET_IDENTITIES)
        _positive(self.max_duration_ns, "bounds.max_duration_ns", maximum=MAX_DURATION_NS)

    def as_wire(self) -> dict[str, int]:
        return {
            "max_processes": self.max_processes,
            "max_descriptors": self.max_descriptors,
            "max_target_identities": self.max_target_identities,
            "max_duration_ns": self.max_duration_ns,
        }

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "CensusBounds":
        fields = _fields(
            value,
            {"max_processes", "max_descriptors", "max_target_identities", "max_duration_ns"},
            "census bounds",
        )
        return cls(
            _positive(fields["max_processes"], "bounds.max_processes", maximum=MAX_PROCESSES),
            _positive(fields["max_descriptors"], "bounds.max_descriptors", maximum=MAX_DESCRIPTORS),
            _positive(fields["max_target_identities"], "bounds.max_target_identities", maximum=MAX_TARGET_IDENTITIES),
            _positive(fields["max_duration_ns"], "bounds.max_duration_ns", maximum=MAX_DURATION_NS),
        )

    from_dict = from_wire


def _normalize_identities(values: Sequence[Any], field: str) -> tuple[ReferenceIdentity, ...]:
    if type(values) not in (tuple, list):
        raise CensusContractError(f"{field} must be a bounded sequence")
    if len(values) > MAX_TARGET_IDENTITIES:
        raise CensusContractError(f"{field} exceeds its collection bound")
    return tuple(_identity_tuple(item, field) for item in values)


@dataclass(frozen=True, slots=True)
class CensusRequest:
    request_id: str
    scan_scope: str
    target_snapshot_digest: str
    target_identities: tuple[ReferenceIdentity, ...]
    bounds: CensusBounds
    requested_at_ns: int
    expires_at_ns: int
    nonce: str
    request_digest: str = ""

    def __post_init__(self) -> None:
        _text(self.request_id, "request_id")
        _text(self.scan_scope, "scan_scope")
        _digest_text(self.target_snapshot_digest, "target_snapshot_digest")
        if not isinstance(self.bounds, CensusBounds):
            raise CensusContractError("request bounds are malformed")
        if type(self.target_identities) is not tuple:
            raise CensusContractError("request target identities must be materialized")
        for item in self.target_identities:
            _identity_tuple(item, "request target identity")
        if len(self.target_identities) > self.bounds.max_target_identities:
            raise CensusContractError("request target identity bound is exhausted")
        _positive(self.requested_at_ns, "request requested_at_ns")
        _positive(self.expires_at_ns, "request expires_at_ns")
        if self.expires_at_ns <= self.requested_at_ns:
            raise CensusContractError("request expiry must be after request time")
        _text(self.nonce, "request nonce")
        if self.request_digest:
            _digest_text(self.request_digest, "request_digest")
            if self.request_digest != digest(self.unsigned_without_digest()):
                raise CensusContractError("request digest mismatch")
        else:
            object.__setattr__(self, "request_digest", digest(self.unsigned_without_digest()))

    def unsigned_without_digest(self) -> dict[str, Any]:
        return {
            "schema": CENSUS_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "scan_scope": self.scan_scope,
            "target_snapshot_digest": self.target_snapshot_digest,
            "target_identities": [list(item) for item in self.target_identities],
            "bounds": self.bounds.as_wire(),
            "requested_at_ns": self.requested_at_ns,
            "expires_at_ns": self.expires_at_ns,
            "nonce": self.nonce,
        }

    def as_wire(self) -> dict[str, Any]:
        value = self.unsigned_without_digest()
        value["request_digest"] = self.request_digest
        return value

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "CensusRequest":
        fields = _fields(
            value,
            {
                "schema",
                "request_id",
                "scan_scope",
                "target_snapshot_digest",
                "target_identities",
                "bounds",
                "requested_at_ns",
                "expires_at_ns",
                "nonce",
                "request_digest",
            },
            "census request",
        )
        if fields["schema"] != CENSUS_REQUEST_SCHEMA:
            raise CensusContractError("census request schema mismatch")
        bounds = CensusBounds.from_wire(fields["bounds"])
        targets = _wire_list(
            fields["target_identities"],
            "request target identities",
            maximum=min(MAX_TARGET_IDENTITIES, bounds.max_target_identities),
        )
        return cls(
            _text(fields["request_id"], "request_id"),
            _text(fields["scan_scope"], "scan_scope"),
            _digest_text(fields["target_snapshot_digest"], "target_snapshot_digest"),
            tuple(_identity_wire(item, "request target identity") for item in targets),
            bounds,
            _positive(fields["requested_at_ns"], "request requested_at_ns"),
            _positive(fields["expires_at_ns"], "request expires_at_ns"),
            _text(fields["nonce"], "request nonce"),
            _digest_text(fields["request_digest"], "request_digest"),
        )

    from_dict = from_wire

    from_dict = from_wire


@dataclass(frozen=True, slots=True)
class CensusEvidence:
    """One bounded, observationally stable census sample, not history proof."""

    request_id: str
    request_digest: str
    scan_scope: str
    target_snapshot_digest: str
    target_identities: tuple[ReferenceIdentity, ...]
    processes: tuple[ProcessReferenceEvidence, ...]
    bounds: CensusBounds
    scan_started_ns: int
    scan_completed_ns: int
    complete: bool
    backend_id: str
    backend_version: str
    reason: str = ""
    evidence_digest: str = ""

    def __post_init__(self) -> None:
        _text(self.request_id, "evidence request_id")
        _digest_text(self.request_digest, "evidence request_digest")
        _text(self.scan_scope, "evidence scan_scope")
        _digest_text(self.target_snapshot_digest, "evidence target_snapshot_digest")
        if not isinstance(self.bounds, CensusBounds):
            raise CensusContractError("evidence bounds are malformed")
        if type(self.target_identities) is not tuple or type(self.processes) is not tuple:
            raise CensusContractError("evidence collections must be materialized")
        for item in self.target_identities:
            _identity_tuple(item, "evidence target identity")
        if len(self.target_identities) > self.bounds.max_target_identities:
            raise CensusContractError("evidence target identity bound is exhausted")
        validate_aggregate_descriptor_bound(self.processes, self.bounds, "evidence")
        _positive(self.scan_started_ns, "evidence scan_started_ns")
        _positive(self.scan_completed_ns, "evidence scan_completed_ns")
        if self.scan_completed_ns < self.scan_started_ns:
            raise CensusContractError("evidence timestamps are out of order")
        if self.scan_completed_ns - self.scan_started_ns > self.bounds.max_duration_ns:
            raise CensusContractError("evidence duration exceeds its bound")
        _boolean(self.complete, "evidence complete")
        _text(self.backend_id, "evidence backend_id")
        _text(self.backend_version, "evidence backend_version")
        _text(self.reason, "evidence reason", allow_empty=True, limit=MAX_REASON_LENGTH)
        computed = digest(self.unsigned())
        if self.evidence_digest:
            _digest_text(self.evidence_digest, "evidence_digest")
            if self.evidence_digest != computed:
                raise CensusContractError("evidence digest mismatch")
        else:
            object.__setattr__(self, "evidence_digest", computed)

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema": CENSUS_EVIDENCE_SCHEMA,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "scan_scope": self.scan_scope,
            "target_snapshot_digest": self.target_snapshot_digest,
            "target_identities": [list(item) for item in self.target_identities],
            "processes": [item.as_wire() for item in self.processes],
            "bounds": self.bounds.as_wire(),
            "scan_started_ns": self.scan_started_ns,
            "scan_completed_ns": self.scan_completed_ns,
            "complete": self.complete,
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "reason": self.reason,
        }

    def as_wire(self) -> dict[str, Any]:
        value = self.unsigned()
        value["evidence_digest"] = self.evidence_digest
        return value

    as_dict = as_wire

    @classmethod
    def from_wire(cls, value: Any) -> "CensusEvidence":
        fields = _fields(
            value,
            {
                "schema",
                "request_id",
                "request_digest",
                "scan_scope",
                "target_snapshot_digest",
                "target_identities",
                "processes",
                "bounds",
                "scan_started_ns",
                "scan_completed_ns",
                "complete",
                "backend_id",
                "backend_version",
                "reason",
                "evidence_digest",
            },
            "census evidence",
        )
        if fields["schema"] != CENSUS_EVIDENCE_SCHEMA:
            raise CensusContractError("census evidence schema mismatch")
        bounds = CensusBounds.from_wire(fields["bounds"])
        targets = _wire_list(
            fields["target_identities"],
            "evidence target identities",
            maximum=min(MAX_TARGET_IDENTITIES, bounds.max_target_identities),
        )
        processes = _wire_processes(fields["processes"], bounds, "evidence processes")
        return cls(
            _text(fields["request_id"], "evidence request_id"),
            _digest_text(fields["request_digest"], "evidence request_digest"),
            _text(fields["scan_scope"], "evidence scan_scope"),
            _digest_text(fields["target_snapshot_digest"], "evidence target_snapshot_digest"),
            tuple(_identity_wire(item, "evidence target identity") for item in targets),
            processes,
            bounds,
            _positive(fields["scan_started_ns"], "evidence scan_started_ns"),
            _positive(fields["scan_completed_ns"], "evidence scan_completed_ns"),
            _boolean(fields["complete"], "evidence complete"),
            _text(fields["backend_id"], "evidence backend_id"),
            _text(fields["backend_version"], "evidence backend_version"),
            _text(fields["reason"], "evidence reason", allow_empty=True, limit=MAX_REASON_LENGTH),
            _digest_text(fields["evidence_digest"], "evidence_digest"),
        )

    from_dict = from_wire

    def to_receipt(
        self,
        *,
        capability: CensusCapability,
        signing_key: bytes,
        nonce: str,
        expires_at_ns: int,
        receipt_id: str | None = None,
        issued_at_ns: int | None = None,
        replay_counter: int = 0,
    ) -> "BrokerReceipt":
        receipt = BrokerReceipt.issue(
            evidence=self,
            capability=capability,
            signing_key=signing_key,
            nonce=nonce,
            expires_at_ns=expires_at_ns,
            receipt_id=receipt_id,
            issued_at_ns=issued_at_ns,
            replay_counter=replay_counter,
        )
        return receipt


class SigningKeyProvider(Protocol):
    def get_key(self, *, key_id: str, key_generation: str) -> bytes:
        """Return the runtime-injected signing/verifying key."""


class ReplayStore(Protocol):
    def accept(self, receipt: "BrokerReceipt") -> None:
        """Atomically consume a receipt nonce/replay tuple or raise."""


class RuntimeKeyProvider:
    """Adapter for a future privileged key injection boundary.

    The resolver is supplied by the runtime.  This source module contains no
    key material and never writes or logs it.
    """

    def __init__(self, resolver: Any) -> None:
        if not callable(resolver):
            raise CensusContractError("key resolver must be callable")
        self._resolver = resolver

    def get_key(self, *, key_id: str, key_generation: str) -> bytes:
        value = self._resolver(key_id=key_id, key_generation=key_generation)
        if type(value) is not bytes or len(value) < 16:
            raise CensusSafetyError("runtime signing key is unavailable")
        return value


class MemoryKeyProvider(RuntimeKeyProvider):
    """Explicit test adapter; callers still provide the key at construction."""

    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) < 16:
            raise CensusContractError("test key must contain at least 16 bytes")
        super().__init__(lambda **_kwargs: key)


def _resolve_key(provider: SigningKeyProvider | bytes, *, key_id: str, key_generation: str) -> bytes:
    if type(provider) is bytes:
        key = provider
    elif hasattr(provider, "get_key"):
        key = provider.get_key(key_id=key_id, key_generation=key_generation)
    else:
        raise CensusSafetyError("key provider is unavailable")
    if type(key) is not bytes or len(key) < 16:
        raise CensusSafetyError("key provider returned an invalid key")
    return key


@dataclass(frozen=True, slots=True)
class CensusCapability:
    """Runtime-supplied scope/target capability accepted by one broker call."""

    capability_id: str
    scan_scope: str
    target_snapshot_digest: str
    target_identities: tuple[ReferenceIdentity, ...]
    bounds: CensusBounds
    broker_id: str
    broker_generation: str
    broker_version: str
    key_id: str
    key_generation: str
    boot_id: str

    def __post_init__(self) -> None:
        _text(self.capability_id, "capability_id")
        _text(self.scan_scope, "capability scan_scope")
        _digest_text(self.target_snapshot_digest, "capability target_snapshot_digest")
        if not isinstance(self.bounds, CensusBounds):
            raise CensusContractError("capability bounds are malformed")
        if type(self.target_identities) is not tuple:
            raise CensusContractError("capability target identities must be materialized")
        if len(self.target_identities) > self.bounds.max_target_identities:
            raise CensusContractError("capability target identity bound is exhausted")
        for item in self.target_identities:
            _identity_tuple(item, "capability target identity")
        for name in ("broker_id", "broker_generation", "broker_version", "key_id", "key_generation", "boot_id"):
            _text(getattr(self, name), f"capability {name}")

    def authorize(self, request: CensusRequest) -> None:
        if not isinstance(request, CensusRequest):
            raise CensusSafetyError("census request is not typed")
        if request.scan_scope != self.scan_scope:
            raise CensusSafetyError("request scope is outside the runtime capability")
        if request.target_snapshot_digest != self.target_snapshot_digest:
            raise CensusSafetyError("request target snapshot is outside the runtime capability")
        if request.target_identities != self.target_identities:
            raise CensusSafetyError("request target identities are outside the runtime capability")
        if request.bounds != self.bounds:
            raise CensusSafetyError("request bounds are outside the runtime capability")


@dataclass(frozen=True, slots=True)
class BrokerReceipt:
    request_id: str
    request_digest: str
    receipt_id: str
    scan_scope: str
    target_snapshot_digest: str
    target_identities: tuple[ReferenceIdentity, ...]
    processes: tuple[ProcessReferenceEvidence, ...]
    bounds: CensusBounds
    scan_started_ns: int
    scan_completed_ns: int
    issued_at_ns: int
    expires_at_ns: int
    broker_id: str
    broker_generation: str
    broker_version: str
    key_id: str
    key_generation: str
    boot_id: str
    nonce: str
    replay_counter: int
    complete: bool
    reason: str
    signature: str = "pending"
    receipt_digest: str = ""

    FIELDS = frozenset(
        {
            "schema",
            "request_id",
            "request_digest",
            "receipt_id",
            "scan_scope",
            "target_snapshot_digest",
            "target_identities",
            "processes",
            "bounds",
            "scan_started_ns",
            "scan_completed_ns",
            "issued_at_ns",
            "expires_at_ns",
            "broker_id",
            "broker_generation",
            "broker_version",
            "key_id",
            "key_generation",
            "boot_id",
            "nonce",
            "replay_counter",
            "complete",
            "reason",
            "signature",
            "receipt_digest",
        }
    )

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "receipt_id",
            "scan_scope",
            "broker_id",
            "broker_generation",
            "broker_version",
            "key_id",
            "key_generation",
            "boot_id",
            "nonce",
        ):
            _text(getattr(self, name), f"receipt {name}")
        _digest_text(self.request_digest, "receipt request_digest")
        _digest_text(self.target_snapshot_digest, "receipt target_snapshot_digest")
        if not isinstance(self.bounds, CensusBounds):
            raise CensusContractError("receipt bounds are malformed")
        if type(self.target_identities) is not tuple or type(self.processes) is not tuple:
            raise CensusContractError("receipt collections must be materialized")
        for item in self.target_identities:
            _identity_tuple(item, "receipt target identity")
        if len(self.target_identities) > self.bounds.max_target_identities:
            raise CensusContractError("receipt target identity bound is exhausted")
        validate_aggregate_descriptor_bound(self.processes, self.bounds, "receipt")
        for process in self.processes:
            if process.process.boot_id != self.boot_id:
                raise CensusContractError("receipt process boot identity differs from broker boot identity")
        for name in ("scan_started_ns", "scan_completed_ns", "issued_at_ns", "expires_at_ns"):
            _positive(getattr(self, name), f"receipt {name}")
        if self.scan_completed_ns < self.scan_started_ns:
            raise CensusContractError("receipt scan timestamps are out of order")
        if self.scan_completed_ns - self.scan_started_ns > self.bounds.max_duration_ns:
            raise CensusContractError("receipt duration exceeds its bound")
        if self.issued_at_ns < self.scan_completed_ns:
            raise CensusContractError("receipt was issued before scan completion")
        if self.expires_at_ns <= self.issued_at_ns:
            raise CensusContractError("receipt expiry must be after issue time")
        _nonnegative(self.replay_counter, "receipt replay_counter")
        _boolean(self.complete, "receipt complete")
        _text(self.reason, "receipt reason", allow_empty=True, limit=MAX_REASON_LENGTH)
        _signature_text(self.signature, "receipt signature", pending=True)
        computed = digest(self.unsigned())
        if self.receipt_digest:
            _digest_text(self.receipt_digest, "receipt_digest")
            if self.receipt_digest != computed:
                raise CensusContractError("receipt digest mismatch")
        else:
            object.__setattr__(self, "receipt_digest", computed)

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema": BROKER_RECEIPT_SCHEMA,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "receipt_id": self.receipt_id,
            "scan_scope": self.scan_scope,
            "target_snapshot_digest": self.target_snapshot_digest,
            "target_identities": [list(item) for item in self.target_identities],
            "processes": [item.as_wire() for item in self.processes],
            "bounds": self.bounds.as_wire(),
            "scan_started_ns": self.scan_started_ns,
            "scan_completed_ns": self.scan_completed_ns,
            "issued_at_ns": self.issued_at_ns,
            "expires_at_ns": self.expires_at_ns,
            "broker_id": self.broker_id,
            "broker_generation": self.broker_generation,
            "broker_version": self.broker_version,
            "key_id": self.key_id,
            "key_generation": self.key_generation,
            "boot_id": self.boot_id,
            "nonce": self.nonce,
            "replay_counter": self.replay_counter,
            "complete": self.complete,
            "reason": self.reason,
        }

    def as_wire(self) -> dict[str, Any]:
        value = self.unsigned()
        value["signature"] = self.signature
        value["receipt_digest"] = self.receipt_digest
        return value

    @classmethod
    def issue(
        cls,
        *,
        evidence: CensusEvidence,
        capability: CensusCapability,
        signing_key: bytes,
        receipt_id: str | None = None,
        issued_at_ns: int | None = None,
        expires_at_ns: int | None = None,
        nonce: str | None = None,
        replay_counter: int = 0,
    ) -> "BrokerReceipt":
        if not isinstance(evidence, CensusEvidence) or not isinstance(capability, CensusCapability):
            raise CensusContractError("receipt issue requires typed evidence and capability")
        if type(signing_key) is not bytes or len(signing_key) < 16:
            raise CensusSafetyError("signing key is unavailable")
        if (
            evidence.scan_scope != capability.scan_scope
            or evidence.target_snapshot_digest != capability.target_snapshot_digest
            or evidence.target_identities != capability.target_identities
            or evidence.bounds != capability.bounds
            or any(item.process.boot_id != capability.boot_id for item in evidence.processes)
        ):
            raise CensusSafetyError("evidence is outside the runtime capability")
        issue_time = time.time_ns() if issued_at_ns is None else issued_at_ns
        expiry = capability.bounds.max_duration_ns + issue_time if expires_at_ns is None else expires_at_ns
        provisional = cls(
            request_id=evidence.request_id,
            request_digest=evidence.request_digest,
            receipt_id=receipt_id or secrets.token_urlsafe(18),
            scan_scope=evidence.scan_scope,
            target_snapshot_digest=evidence.target_snapshot_digest,
            target_identities=evidence.target_identities,
            processes=evidence.processes,
            bounds=evidence.bounds,
            scan_started_ns=evidence.scan_started_ns,
            scan_completed_ns=evidence.scan_completed_ns,
            issued_at_ns=issue_time,
            expires_at_ns=expiry,
            broker_id=capability.broker_id,
            broker_generation=capability.broker_generation,
            broker_version=capability.broker_version,
            key_id=capability.key_id,
            key_generation=capability.key_generation,
            boot_id=capability.boot_id,
            nonce=evidence.request_digest if nonce is None else nonce,
            replay_counter=replay_counter,
            complete=evidence.complete,
            reason=evidence.reason,
            signature="pending",
        )
        signature = "hmac-sha256:" + hmac.new(signing_key, canonical_json(provisional.unsigned()), hashlib.sha256).hexdigest()
        return cls(
            request_id=provisional.request_id,
            request_digest=provisional.request_digest,
            receipt_id=provisional.receipt_id,
            scan_scope=provisional.scan_scope,
            target_snapshot_digest=provisional.target_snapshot_digest,
            target_identities=provisional.target_identities,
            processes=provisional.processes,
            bounds=provisional.bounds,
            scan_started_ns=provisional.scan_started_ns,
            scan_completed_ns=provisional.scan_completed_ns,
            issued_at_ns=provisional.issued_at_ns,
            expires_at_ns=provisional.expires_at_ns,
            broker_id=provisional.broker_id,
            broker_generation=provisional.broker_generation,
            broker_version=provisional.broker_version,
            key_id=provisional.key_id,
            key_generation=provisional.key_generation,
            boot_id=provisional.boot_id,
            nonce=provisional.nonce,
            replay_counter=provisional.replay_counter,
            complete=provisional.complete,
            reason=provisional.reason,
            signature=signature,
        )

    @classmethod
    def from_wire(cls, value: Any) -> "BrokerReceipt":
        fields = _fields(value, set(cls.FIELDS), "broker receipt")
        if fields["schema"] != BROKER_RECEIPT_SCHEMA:
            raise CensusContractError("broker receipt schema mismatch")
        bounds = CensusBounds.from_wire(fields["bounds"])
        targets = _wire_list(
            fields["target_identities"],
            "receipt target identities",
            maximum=min(MAX_TARGET_IDENTITIES, bounds.max_target_identities),
        )
        processes = _wire_processes(fields["processes"], bounds, "receipt processes")
        receipt = cls(
            request_id=_text(fields["request_id"], "receipt request_id"),
            request_digest=_digest_text(fields["request_digest"], "receipt request_digest"),
            receipt_id=_text(fields["receipt_id"], "receipt receipt_id"),
            scan_scope=_text(fields["scan_scope"], "receipt scan_scope"),
            target_snapshot_digest=_digest_text(fields["target_snapshot_digest"], "receipt target_snapshot_digest"),
            target_identities=tuple(_identity_wire(item, "receipt target identity") for item in targets),
            processes=processes,
            bounds=bounds,
            scan_started_ns=_positive(fields["scan_started_ns"], "receipt scan_started_ns"),
            scan_completed_ns=_positive(fields["scan_completed_ns"], "receipt scan_completed_ns"),
            issued_at_ns=_positive(fields["issued_at_ns"], "receipt issued_at_ns"),
            expires_at_ns=_positive(fields["expires_at_ns"], "receipt expires_at_ns"),
            broker_id=_text(fields["broker_id"], "receipt broker_id"),
            broker_generation=_text(fields["broker_generation"], "receipt broker_generation"),
            broker_version=_text(fields["broker_version"], "receipt broker_version"),
            key_id=_text(fields["key_id"], "receipt key_id"),
            key_generation=_text(fields["key_generation"], "receipt key_generation"),
            boot_id=_text(fields["boot_id"], "receipt boot_id"),
            nonce=_text(fields["nonce"], "receipt nonce"),
            replay_counter=_nonnegative(fields["replay_counter"], "receipt replay_counter"),
            complete=_boolean(fields["complete"], "receipt complete"),
            reason=_text(fields["reason"], "receipt reason", allow_empty=True, limit=MAX_REASON_LENGTH),
            signature=_signature_text(fields["signature"], "receipt signature"),
            receipt_digest=_digest_text(fields["receipt_digest"], "receipt_digest"),
        )
        if fields["receipt_digest"] != receipt.receipt_digest:
            raise CensusContractError("receipt digest mismatch")
        return receipt

    as_dict = as_wire
    from_dict = from_wire

    def verify(
        self,
        signing_key: bytes,
        *,
        expected_request: CensusRequest | None = None,
        expected_broker_id: str | None = None,
        expected_broker_generation: str | None = None,
        expected_key_id: str | None = None,
        expected_key_generation: str | None = None,
        expected_boot_id: str | None = None,
        expected_scope: str | None = None,
        expected_target_snapshot_digest: str | None = None,
        expected_target_identities: Sequence[Any] | None = None,
        expected_bounds: CensusBounds | None = None,
        now_ns: int | None = None,
        replay_store: ReplayStore | None = None,
        require_complete: bool = True,
    ) -> None:
        if type(signing_key) is not bytes or len(signing_key) < 16:
            raise CensusSafetyError("verification key is unavailable")
        if self.receipt_digest != digest(self.unsigned()):
            raise CensusSafetyError("receipt digest integrity check failed")
        expected_signature = "hmac-sha256:" + hmac.new(signing_key, canonical_json(self.unsigned()), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, self.signature):
            raise CensusSafetyError("receipt authenticity check failed")
        if require_complete and not self.complete:
            raise CensusSafetyError("receipt is an authenticated incomplete census")
        current = time.time_ns() if now_ns is None else now_ns
        _positive(current, "verification now_ns")
        if current < self.issued_at_ns:
            raise CensusSafetyError("receipt is not yet valid")
        if current >= self.expires_at_ns:
            raise CensusSafetyError("receipt is stale")
        for value, expected, label in (
            (self.broker_id, expected_broker_id, "broker identity"),
            (self.broker_generation, expected_broker_generation, "broker generation"),
            (self.key_id, expected_key_id, "key identity"),
            (self.key_generation, expected_key_generation, "key generation"),
            (self.boot_id, expected_boot_id, "boot identity"),
        ):
            if expected is not None and value != expected:
                raise CensusSafetyError(f"receipt {label} mismatch")
        if expected_scope is not None and self.scan_scope != expected_scope:
            raise CensusSafetyError("receipt scope mismatch")
        if expected_target_snapshot_digest is not None and self.target_snapshot_digest != expected_target_snapshot_digest:
            raise CensusSafetyError("receipt target snapshot mismatch")
        if expected_target_identities is not None:
            expected_targets = tuple(_identity_tuple(item, "expected target identity") for item in expected_target_identities)
            if self.target_identities != expected_targets:
                raise CensusSafetyError("receipt target identities mismatch")
        if expected_bounds is not None and self.bounds != expected_bounds:
            raise CensusSafetyError("receipt bounds mismatch")
        if any(item.process.boot_id != self.boot_id for item in self.processes):
            raise CensusSafetyError("receipt contains a stale process boot identity")
        if expected_request is not None:
            if not isinstance(expected_request, CensusRequest):
                raise CensusSafetyError("expected request is not typed")
            if (
                self.request_id != expected_request.request_id
                or self.request_digest != expected_request.request_digest
                or self.scan_scope != expected_request.scan_scope
                or self.target_snapshot_digest != expected_request.target_snapshot_digest
                or self.target_identities != expected_request.target_identities
                or self.bounds != expected_request.bounds
                or self.nonce != expected_request.nonce
                or self.issued_at_ns < expected_request.requested_at_ns
                or self.expires_at_ns > expected_request.expires_at_ns
            ):
                raise CensusSafetyError("receipt is not bound to the expected request")
        if replay_store is None:
            raise CensusSafetyError("replay store is unavailable")
        replay_store.accept(self)


class ReceiptReplayGuard:
    """Thread-safe process-local replay guard for tests and bounded workers."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, int, str]] = set()
        self._lock = threading.Lock()

    def accept(self, receipt: BrokerReceipt) -> None:
        token = (receipt.broker_generation, receipt.nonce, receipt.replay_counter, receipt.request_digest)
        with self._lock:
            if token in self._seen:
                raise CensusSafetyError("receipt replay detected")
            self._seen.add(token)

    def seen(self, receipt: BrokerReceipt) -> bool:
        token = (receipt.broker_generation, receipt.nonce, receipt.replay_counter, receipt.request_digest)
        with self._lock:
            return token in self._seen


class GenerationReplayGuard(ReceiptReplayGuard):
    """Replay guard whose active generation must be explicitly rotated."""

    def __init__(self, generation: str) -> None:
        super().__init__()
        self._generation = _text(generation, "replay guard generation")

    def rotate(self, generation: str) -> None:
        generation = _text(generation, "replay guard generation")
        with self._lock:
            self._generation = generation
            self._seen.clear()

    def accept(self, receipt: BrokerReceipt) -> None:
        with self._lock:
            if receipt.broker_generation != self._generation:
                raise CensusSafetyError("receipt broker generation is not current")
            token = (receipt.broker_generation, receipt.nonce, receipt.replay_counter, receipt.request_digest)
            if token in self._seen:
                raise CensusSafetyError("receipt replay detected")
            self._seen.add(token)


class BrokerReceiptVerifier:
    """Centralized authenticity, freshness, generation, and replay admission."""

    def __init__(
        self,
        key_provider: SigningKeyProvider | bytes,
        *,
        broker_id: str,
        broker_generation: str,
        key_id: str,
        key_generation: str,
        boot_id: str,
        replay_store: ReplayStore | None = None,
        clock_ns: Any = time.time_ns,
    ) -> None:
        for value, field in (
            (broker_id, "broker_id"),
            (broker_generation, "broker_generation"),
            (key_id, "key_id"),
            (key_generation, "key_generation"),
            (boot_id, "boot_id"),
        ):
            _text(value, field)
        if not callable(clock_ns):
            raise CensusContractError("clock_ns must be callable")
        self.key_provider = key_provider
        self.broker_id = broker_id
        self.broker_generation = broker_generation
        self.key_id = key_id
        self.key_generation = key_generation
        self.boot_id = boot_id
        self.replay_store = replay_store or GenerationReplayGuard(broker_generation)
        self.clock_ns = clock_ns

    def verify(
        self,
        receipt: BrokerReceipt,
        *,
        expected_request: CensusRequest | None = None,
        expected_scope: str | None = None,
        expected_target_snapshot_digest: str | None = None,
        expected_target_identities: Sequence[Any] | None = None,
        expected_bounds: CensusBounds | None = None,
        require_complete: bool = True,
    ) -> None:
        if not isinstance(receipt, BrokerReceipt):
            raise CensusSafetyError("receipt is not typed")
        key = _resolve_key(self.key_provider, key_id=self.key_id, key_generation=self.key_generation)
        receipt.verify(
            key,
            expected_request=expected_request,
            expected_broker_id=self.broker_id,
            expected_broker_generation=self.broker_generation,
            expected_key_id=self.key_id,
            expected_key_generation=self.key_generation,
            expected_boot_id=self.boot_id,
            expected_scope=expected_scope,
            expected_target_snapshot_digest=expected_target_snapshot_digest,
            expected_target_identities=expected_target_identities,
            expected_bounds=expected_bounds,
            now_ns=self.clock_ns(),
            replay_store=self.replay_store,
            require_complete=require_complete,
        )


class CensusBackend(Protocol):
    backend_id: str
    backend_version: str

    def scan(self, request: CensusRequest) -> CensusEvidence:
        """Return bounded evidence; incomplete is a valid fail-closed result."""


class CensusBroker:
    """Runtime-bound read-only broker facade."""

    def __init__(
        self,
        *,
        backend: CensusBackend,
        key_provider: SigningKeyProvider | bytes,
        capability: CensusCapability,
        clock_ns: Any = time.time_ns,
    ) -> None:
        if not hasattr(backend, "scan"):
            raise CensusContractError("census backend is unavailable")
        if not isinstance(capability, CensusCapability):
            raise CensusContractError("census capability is not typed")
        if not callable(clock_ns):
            raise CensusContractError("clock_ns must be callable")
        self.backend = backend
        self.key_provider = key_provider
        self.capability = capability
        self.clock_ns = clock_ns

    def scan(self, request: CensusRequest) -> CensusEvidence:
        self.capability.authorize(request)
        now = self.clock_ns()
        if type(now) is not int or now < request.requested_at_ns or now >= request.expires_at_ns:
            raise CensusSafetyError("request is outside its runtime validity window")
        evidence = self.backend.scan(request)
        if not isinstance(evidence, CensusEvidence):
            raise CensusSafetyError("backend did not return typed evidence")
        validate_aggregate_descriptor_bound(evidence.processes, request.bounds, "backend evidence")
        if (
            evidence.request_id != request.request_id
            or evidence.request_digest != request.request_digest
            or evidence.scan_scope != request.scan_scope
            or evidence.target_snapshot_digest != request.target_snapshot_digest
            or evidence.target_identities != request.target_identities
            or evidence.bounds != request.bounds
        ):
            raise CensusSafetyError("backend evidence is not bound to the request")
        if any(item.process.boot_id != self.capability.boot_id for item in evidence.processes):
            raise CensusSafetyError("backend evidence has a stale boot identity")
        return evidence

    def issue(self, request: CensusRequest, *, receipt_id: str | None = None, replay_counter: int = 0) -> BrokerReceipt:
        evidence = self.scan(request)
        key = _resolve_key(
            self.key_provider,
            key_id=self.capability.key_id,
            key_generation=self.capability.key_generation,
        )
        receipt = BrokerReceipt.issue(
            evidence=evidence,
            capability=self.capability,
            signing_key=key,
            receipt_id=receipt_id,
            issued_at_ns=self.clock_ns(),
            expires_at_ns=request.expires_at_ns,
            nonce=request.nonce,
            replay_counter=replay_counter,
        )
        return receipt


def _object_kind(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
        return "special"
    return "other"


class _ScanBoundExceeded(CensusSafetyError):
    pass


@dataclass(frozen=True, slots=True)
class _FollowedObjectIdentity:
    """Identity obtained by following a descriptor path without opening it."""

    dev: int
    ino: int
    object_kind: str


@dataclass(frozen=True, slots=True)
class _DescriptorObservation:
    evidence: DescriptorEvidence
    link: str
    followed_before_open: _FollowedObjectIdentity
    followed_after_open: _FollowedObjectIdentity


@dataclass(frozen=True, slots=True)
class _DescriptorInventory:
    fd_numbers: tuple[int, ...]
    observations: tuple[_DescriptorObservation, ...]


class LinuxProcCensusBackend:
    """Conservative Linux procfs census with no write-capable operations."""

    backend_id = "linux-procfs-read-only-census"
    backend_version = "v51"

    def __init__(
        self,
        *,
        proc_root: str | os.PathLike[str] = "/proc",
        current_pid: int | None = None,
        current_uid_reader: Any = os.getuid,
        boot_id_reader: Any | None = None,
        start_reader: Any | None = None,
        uid_reader: Any | None = None,
        mount_id_reader: Any | None = None,
        clock_ns: Any = time.time_ns,
        monotonic_ns: Any = time.monotonic_ns,
        readlink: Any = os.readlink,
        stat_path: Any | None = None,
        open_fd: Any | None = None,
        fstat: Any | None = None,
        close_fd: Any | None = None,
    ) -> None:
        self.proc_root = Path(proc_root)
        self.current_pid = os.getpid() if current_pid is None else current_pid
        if type(self.current_pid) is not int or self.current_pid <= 0:
            raise CensusContractError("current_pid must be a positive integer")
        if not callable(current_uid_reader) or not callable(clock_ns) or not callable(monotonic_ns) or not callable(readlink):
            raise CensusContractError("runtime census readers must be callable")
        self._current_uid_reader = current_uid_reader
        self._clock_ns = clock_ns
        self._monotonic_ns = monotonic_ns
        self._readlink = readlink
        self._stat_path = os.stat if stat_path is None else stat_path
        self._boot_id_reader = boot_id_reader or self._read_boot_id
        self._start_reader = start_reader or self._read_start_ticks
        self._uid_reader = uid_reader or self._read_uid
        self._mount_id_reader = mount_id_reader or self._mount_id_for_fd
        self._open_fd = open_fd
        self._fstat = fstat
        self._close_fd = close_fd
        self._scanner_pid = os.getpid()
        self._active_scanner_fds: set[int] = set()
        for reader, field in (
            (self._boot_id_reader, "boot_id_reader"),
            (self._start_reader, "start_reader"),
            (self._uid_reader, "uid_reader"),
            (self._mount_id_reader, "mount_id_reader"),
        ):
            if not callable(reader):
                raise CensusContractError(f"{field} must be callable")
        for reader, field in (
            (open_fd, "open_fd"),
            (stat_path, "stat_path"),
            (fstat, "fstat"),
            (close_fd, "close_fd"),
        ):
            if reader is not None and not callable(reader):
                raise CensusContractError(f"{field} must be callable")

    def scan(self, request: CensusRequest) -> CensusEvidence:
        if not isinstance(request, CensusRequest):
            raise CensusContractError("scan requires a typed census request")
        started_ns = self._positive_clock()
        monotonic_start = self._monotonic_ns()
        processes: list[ProcessReferenceEvidence] = []

        def finish(complete: bool, reason: str) -> CensusEvidence:
            completed_ns = max(started_ns, self._positive_clock())
            if completed_ns - started_ns > request.bounds.max_duration_ns:
                complete = False
                reason = reason or "census duration bound exhausted"
            return CensusEvidence(
                request_id=request.request_id,
                request_digest=request.request_digest,
                scan_scope=request.scan_scope,
                target_snapshot_digest=request.target_snapshot_digest,
                target_identities=request.target_identities,
                processes=tuple(processes),
                bounds=request.bounds,
                scan_started_ns=started_ns,
                scan_completed_ns=completed_ns,
                complete=complete,
                backend_id=self.backend_id,
                backend_version=self.backend_version,
                reason=reason,
            )

        if sys.platform != "linux":
            return finish(False, "unsupported platform")
        try:
            current_uid = self._current_uid_reader()
            if type(current_uid) is not int or current_uid < 0:
                return finish(False, "current credential evidence is unavailable")
            boot_id = self._boot_id_reader()
            if not boot_id:
                return finish(False, "boot identity is unavailable")
            boot_id = _text(boot_id, "boot identity")
            pids = self._list_pids(request.bounds.max_processes)
            required = {1, self.current_pid}
            missing = sorted(required.difference(pids))
            if missing:
                return finish(False, "required PID visibility is incomplete")
            descriptor_total = 0
            for pid in pids:
                if self._over_deadline(monotonic_start, request.bounds.max_duration_ns):
                    return finish(False, "census duration bound exhausted")
                try:
                    uid = self._uid_reader(pid)
                    if type(uid) is not int or uid < 0:
                        raise CensusSafetyError("credential evidence is malformed")
                    before = self._process_identity(pid, boot_id)
                    remaining_descriptors = request.bounds.max_descriptors - descriptor_total
                    descriptors = self._descriptors_for_process(
                        pid,
                        remaining_descriptors,
                        monotonic_start,
                        request.bounds.max_duration_ns,
                        boot_id=boot_id,
                        expected_identity=before,
                        expected_uid=uid,
                    )
                    descriptor_total += len(descriptors)
                    if descriptor_total > request.bounds.max_descriptors:
                        raise _ScanBoundExceeded("descriptor scan bound exhausted")
                    processes.append(ProcessReferenceEvidence(before, descriptors, uid))
                except _ScanBoundExceeded:
                    raise
                except (OSError, ValueError, CensusContractError) as exc:
                    return finish(False, self._failure_reason(pid, exc))
            final_pids = self._list_pids(request.bounds.max_processes)
            if final_pids != pids:
                return finish(False, "process inventory changed during census")
            if self._boot_id_reader() != boot_id:
                return finish(False, "boot identity changed during census")
            return finish(True, "")
        except _ScanBoundExceeded as exc:
            return finish(False, str(exc))
        except (OSError, ValueError, CensusContractError) as exc:
            return finish(False, f"census observation failed:{type(exc).__name__}")

    def _positive_clock(self) -> int:
        value = self._clock_ns()
        if type(value) is not int or value <= 0:
            raise CensusSafetyError("clock evidence is unavailable")
        return value

    def _over_deadline(self, started: int, duration: int) -> bool:
        now = self._monotonic_ns()
        return type(now) is not int or now - started > duration

    def _list_pids(self, maximum: int) -> list[int]:
        pids: list[int] = []
        with os.scandir(self.proc_root) as entries:
            for entry in entries:
                name = entry.name
                if type(name) is not str or not name.isdecimal():
                    continue
                pid = _positive(int(name), "proc pid")
                pids.append(pid)
                if len(pids) > maximum:
                    raise _ScanBoundExceeded("process scan bound exhausted")
        return sorted(set(pids))

    def _process_identity(self, pid: int, boot_id: str) -> ProcessIdentity:
        start_ticks = self._start_reader(pid)
        if type(start_ticks) is not int or start_ticks <= 0:
            raise CensusSafetyError("process start ticks are unavailable")
        run_id = self._namespace_run_id(pid)
        return ProcessIdentity(pid, start_ticks, boot_id, run_id)

    def _namespace_run_id(self, pid: int) -> str:
        values: dict[str, str] = {}
        for name in ("pid", "mnt"):
            raw = self._readlink(self.proc_root / str(pid) / "ns" / name)
            if type(raw) is not str:
                raise CensusSafetyError("namespace identity is malformed")
            match = _NAMESPACE.fullmatch(raw)
            if match is None or match.group(1) != name:
                raise CensusSafetyError("namespace identity is ambiguous")
            values[name] = match.group(2)
        return f"pidns:{values['pid']};mntns:{values['mnt']}"

    def _assert_process_stable(
        self,
        pid: int,
        *,
        boot_id: str,
        expected_identity: ProcessIdentity,
        expected_uid: int,
    ) -> None:
        observed_identity = self._process_identity(pid, boot_id)
        observed_uid = self._uid_reader(pid)
        observed_boot = self._boot_id_reader()
        if type(observed_uid) is not int or observed_uid < 0:
            raise CensusSafetyError("credential evidence is malformed")
        if observed_uid != expected_uid or observed_identity != expected_identity or observed_boot != boot_id:
            raise CensusSafetyError("process incarnation changed during census")

    def _descriptors_for_process(
        self,
        pid: int,
        maximum: int,
        started: int,
        duration: int,
        *,
        boot_id: str,
        expected_identity: ProcessIdentity,
        expected_uid: int,
    ) -> tuple[DescriptorEvidence, ...]:
        if maximum < 2:
            raise _ScanBoundExceeded("descriptor scan bound exhausted")
        first = self._snapshot_descriptor_inventory(pid, maximum, started, duration)
        self._assert_process_stable(
            pid,
            boot_id=boot_id,
            expected_identity=expected_identity,
            expected_uid=expected_uid,
        )
        second = self._revalidate_descriptor_inventory(pid, first, maximum, started, duration)
        self._assert_process_stable(
            pid,
            boot_id=boot_id,
            expected_identity=expected_identity,
            expected_uid=expected_uid,
        )
        return tuple(item.evidence for item in second.observations)

    def _snapshot_descriptor_inventory(
        self,
        pid: int,
        maximum: int,
        started: int,
        duration: int,
    ) -> _DescriptorInventory:
        if self._over_deadline(started, duration):
            raise _ScanBoundExceeded("census duration bound exhausted")
        fd_numbers = self._enumerate_fd_numbers(pid, maximum - 2)
        if len(fd_numbers) + 2 > maximum:
            raise _ScanBoundExceeded("descriptor scan bound exhausted")
        keys: tuple[tuple[str, int | None], ...] = (
            ("cwd", None),
            ("root", None),
            *(("fd", fd_number) for fd_number in fd_numbers),
        )
        observations: list[_DescriptorObservation] = []
        for kind, fd_number in keys:
            if self._over_deadline(started, duration):
                raise _ScanBoundExceeded("census duration bound exhausted")
            observations.append(self._observe_descriptor(pid, kind, fd_number))
        return _DescriptorInventory(tuple(fd_numbers), tuple(observations))

    def _revalidate_descriptor_inventory(
        self,
        pid: int,
        expected: _DescriptorInventory,
        maximum: int,
        started: int,
        duration: int,
    ) -> _DescriptorInventory:
        if self._over_deadline(started, duration):
            raise _ScanBoundExceeded("census duration bound exhausted")
        fd_numbers = self._enumerate_fd_numbers(pid, maximum - 2)
        if tuple(fd_numbers) != expected.fd_numbers:
            raise CensusSafetyError("process descriptor inventory changed during census")
        keys: tuple[tuple[str, int | None], ...] = (
            ("cwd", None),
            ("root", None),
            *(("fd", fd_number) for fd_number in fd_numbers),
        )
        observations: list[_DescriptorObservation] = []
        for index, (kind, fd_number) in enumerate(keys):
            if self._over_deadline(started, duration):
                raise _ScanBoundExceeded("census duration bound exhausted")
            observed = self._observe_descriptor(pid, kind, fd_number)
            previous = expected.observations[index]
            if observed != previous:
                raise CensusSafetyError("process descriptor identity changed during census")
            observations.append(observed)
        final_fd_numbers = self._enumerate_fd_numbers(pid, maximum - 2)
        if tuple(final_fd_numbers) != expected.fd_numbers:
            raise CensusSafetyError("process descriptor inventory changed during census")
        return _DescriptorInventory(tuple(fd_numbers), tuple(observations))

    def _enumerate_fd_numbers(self, pid: int, maximum: int) -> list[int]:
        if maximum < 0:
            raise _ScanBoundExceeded("descriptor scan bound exhausted")
        fd_root = self.proc_root / str(pid) / "fd"
        scanner_process = self._is_actual_scanner_process(pid)
        scanner_before = self._scanner_fd_snapshot() if scanner_process else None
        names: list[int] = []
        seen: set[int] = set()
        try:
            with os.scandir(fd_root) as entries:
                for entry in entries:
                    name = entry.name
                    if type(name) is not str or not name.isdecimal():
                        raise CensusSafetyError("process fd table contains an ambiguous entry")
                    fd_number = _nonnegative(int(name), "process fd number")
                    if scanner_process and fd_number in self._active_scanner_fds:
                        continue
                    if fd_number in seen:
                        raise CensusSafetyError("process fd table contains duplicate entries")
                    seen.add(fd_number)
                    names.append(fd_number)
                    if len(names) > maximum:
                        raise _ScanBoundExceeded("descriptor scan bound exhausted")
        except OSError as exc:
            raise CensusSafetyError("process fd table is unreadable") from exc
        names.sort()
        if scanner_process:
            scanner_after = self._scanner_fd_snapshot()
            if scanner_before is None or scanner_after is None:
                raise CensusSafetyError("scanner descriptor inventory is unavailable")
            if scanner_after != scanner_before:
                raise CensusSafetyError("scanner descriptor inventory changed during census")
            stable_names = [fd_number for fd_number in names if fd_number in scanner_before]
            if set(stable_names) != scanner_before:
                raise CensusSafetyError("scanner descriptor inventory is unreadable")
            return stable_names
        return names

    def _is_actual_scanner_process(self, pid: int) -> bool:
        if pid != self._scanner_pid:
            return False
        try:
            return os.path.samefile(
                self.proc_root / str(pid),
                Path("/proc") / str(self._scanner_pid),
            )
        except OSError:
            return False

    def _scanner_fd_snapshot(self) -> set[int] | None:
        fd_root = self.proc_root / "self" / "fd"
        candidates: list[int] = []
        try:
            with os.scandir(fd_root) as entries:
                for entry in entries:
                    name = entry.name
                    if type(name) is not str or not name.isdecimal():
                        continue
                    candidates.append(_nonnegative(int(name), "scanner fd number"))
                    if len(candidates) > MAX_DESCRIPTORS:
                        raise _ScanBoundExceeded("scanner descriptor scan bound exhausted")
        except OSError:
            return None
        # The iterator used above is itself transient.  Only retain entries
        # that remain readable after it has closed; no fd number/path/name is
        # special-cased.
        stable: set[int] = set()
        for fd_number in candidates:
            try:
                value = os.readlink(fd_root / str(fd_number))
            except OSError:
                continue
            if type(value) is str:
                stable.add(fd_number)
        return stable

    def _open_scanner_fd(self, path: Path, flags: int) -> int:
        opener = os.open if self._open_fd is None else self._open_fd
        fd = opener(path, flags)
        if type(fd) is not int or fd < 0:
            raise CensusSafetyError("descriptor open returned an invalid fd")
        self._active_scanner_fds.add(fd)
        return fd

    def _close_scanner_fd(self, fd: int) -> None:
        try:
            closer = os.close if self._close_fd is None else self._close_fd
            closer(fd)
        finally:
            self._active_scanner_fds.discard(fd)

    def _descriptor_path(self, pid: int, kind: str, fd_number: int | None) -> Path:
        if kind in {"cwd", "root"}:
            if fd_number is not None:
                raise CensusContractError("cwd/root descriptor cannot carry fd_number")
            return self.proc_root / str(pid) / kind
        if kind == "fd" and fd_number is not None:
            return self.proc_root / str(pid) / "fd" / str(fd_number)
        raise CensusContractError("fd descriptor is malformed")

    def _followed_object_identity(self, path: Path) -> _FollowedObjectIdentity:
        value = self._stat_path(path)
        mode = getattr(value, "st_mode", None)
        if type(mode) is not int:
            raise CensusSafetyError("followed descriptor mode identity is unavailable")
        return _FollowedObjectIdentity(
            _nonnegative(getattr(value, "st_dev", None), "followed descriptor.dev"),
            _nonnegative(getattr(value, "st_ino", None), "followed descriptor.ino"),
            _object_kind(mode),
        )

    def _observe_descriptor(self, pid: int, kind: str, fd_number: int | None) -> _DescriptorObservation:
        path = self._descriptor_path(pid, kind, fd_number)
        link = self._readlink(path)
        if type(link) is not str:
            raise CensusSafetyError("descriptor reference is unreadable")
        link = _text(link, "descriptor link target")
        followed_before_open = self._followed_object_identity(path)
        flags = getattr(os, "O_PATH", 0) | getattr(os, "O_CLOEXEC", 0)
        if not flags:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        fd = self._open_scanner_fd(path, flags)
        try:
            statter = os.fstat if self._fstat is None else self._fstat
            value = statter(fd)
            mount_id = self._mount_id_reader(fd)
            if type(mount_id) is not int or mount_id < 0:
                raise CensusSafetyError("descriptor mount identity is unavailable")
            mode = getattr(value, "st_mode", None)
            if type(mode) is not int:
                raise CensusSafetyError("descriptor mode identity is unavailable")
            object_kind = _object_kind(mode)
            dev = _nonnegative(getattr(value, "st_dev", None), "descriptor.dev")
            ino = _nonnegative(getattr(value, "st_ino", None), "descriptor.ino")
            opened_identity = _FollowedObjectIdentity(dev, ino, object_kind)
            if followed_before_open != opened_identity:
                raise CensusSafetyError("descriptor target identity changed before open")
            link_deleted = link.endswith(" (deleted)")
            if object_kind == "regular":
                nlink = _nonnegative(getattr(value, "st_nlink", None), "descriptor.st_nlink")
                if link_deleted != (nlink == 0):
                    raise CensusSafetyError("deleted file link/count disagreement")
                deleted = link_deleted
            else:
                if link_deleted:
                    raise CensusSafetyError("deleted descriptor is not a regular file")
                deleted = False
            link_after = self._readlink(path)
            if type(link_after) is not str or _text(link_after, "descriptor link target") != link:
                raise CensusSafetyError("descriptor readlink changed during open")
            followed_after_open = self._followed_object_identity(path)
            if followed_after_open != opened_identity:
                raise CensusSafetyError("descriptor target identity changed after open")
            evidence = DescriptorEvidence(kind, fd_number, dev, ino, mount_id, object_kind, deleted)
            return _DescriptorObservation(evidence, link, followed_before_open, followed_after_open)
        finally:
            self._close_scanner_fd(fd)

    def _descriptor_from_proc_path(self, pid: int, kind: str, fd_number: int | None) -> DescriptorEvidence:
        """Compatibility helper returning the opened descriptor evidence."""

        return self._observe_descriptor(pid, kind, fd_number).evidence

    def _failure_reason(self, pid: int, exc: BaseException) -> str:
        if pid == 1:
            role = "PID 1"
        elif pid == self.current_pid:
            role = "same-uid process"
        else:
            role = "other-uid process"
        return f"{role} census evidence unavailable:{type(exc).__name__}"

    def _read_boot_id(self) -> str:
        value = (self.proc_root / "sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        return _text(value, "boot identity")

    def _read_start_ticks(self, pid: int) -> int:
        raw = (self.proc_root / str(pid) / "stat").read_bytes()
        closing = raw.rfind(b")")
        if closing < 0:
            raise CensusSafetyError("process stat record is malformed")
        fields = raw[closing + 2 :].split()
        if len(fields) <= 19:
            raise CensusSafetyError("process stat record lacks start ticks")
        return _positive(int(fields[19]), "process start ticks")

    def _read_uid(self, pid: int) -> int:
        for line in (self.proc_root / str(pid) / "status").read_text(encoding="ascii").splitlines():
            if line.startswith("Uid:"):
                fields = line.split()
                if len(fields) >= 2:
                    return _nonnegative(int(fields[1]), "process uid")
                break
        raise CensusSafetyError("process credential evidence is unavailable")

    def _mount_id_for_fd(self, fd: int) -> int | None:
        try:
            for line in (self.proc_root / "self" / "fdinfo" / str(fd)).read_text(encoding="ascii").splitlines():
                if line.startswith("mnt_id:"):
                    return _nonnegative(int(line.split(":", 1)[1].strip()), "descriptor mount_id")
        except (OSError, ValueError):
            return None
        return None


# Compatibility/discoverability aliases for owner consumers.
ProcessCensusEvidence = CensusEvidence
ProcessCensusReceipt = BrokerReceipt
BrokerCensusReceipt = BrokerReceipt
LinuxProcessInspector = LinuxProcCensusBackend
