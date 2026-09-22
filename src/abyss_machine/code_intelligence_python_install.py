"""Exact, non-executing SCIP Python placement on a Linux host-owned runtime."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
import errno
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
from typing import Any, Iterator

from . import artifact_bundles
from . import code_intelligence_python_provider as archive_tools
from .code_intelligence_provider import (
    ARTIFACT_CLASS,
    BUNDLE_MANIFEST_REF,
    CONTRACT_SURFACE_ID,
    DEFAULT_RUNTIME_ROOT,
    _bounded_process,
    _canonical_json,
    _decode,
    _subject_binding,
    _summarize_verify,
    run_owner_preflights,
)

INSTALLER_ROOT = Path(__file__).resolve().parents[2]
INSTALLATION_SCHEMA = "abyss_machine_code_intelligence_python_installation_v1"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _git(root: Path, *arguments: str) -> str:
    result = _bounded_process(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
        timeout=30,
        max_output_bytes=64 * 1024,
    )
    if result["returncode"] or result["timed_out"] or result["output_truncated"]:
        raise ValueError("source identity is unavailable or exceeds its bound")
    return _decode(result["stdout"]).strip()


def _source_identity(root: Path, expected_ref: str | None = None) -> dict[str, str]:
    root = root.resolve(strict=True)
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("exact owner source root required")
    commit, tree = _git(root, "rev-parse", "HEAD", "HEAD^{tree}").splitlines()
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (commit, tree)):
        raise ValueError("exact commit and tree required")
    if expected_ref is not None and expected_ref != "commit:" + commit:
        raise ValueError("producer source commit mismatch")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("clean owner source required")
    return {"commit": commit, "tree": tree}


def _consumption_contract(root: Path) -> bytes:
    def document(relative: str) -> dict:
        return archive_tools._object(
            archive_tools._read_bounded(
                root / relative, archive_tools.MAX_CONTROL_BYTES
            )
        )

    policy = document("manifests/artifact_signature_policy.manifest.json")
    policy["artifact_classes"] = {
        ARTIFACT_CLASS: policy["artifact_classes"][ARTIFACT_CLASS]
    }
    surfaces = [
        surface
        for surface in policy["contract_surfaces"]
        if surface["id"] == CONTRACT_SURFACE_ID
    ]
    if len(surfaces) != 1:
        raise ValueError("one current provider ABI surface required")
    # Source files naturally differ between producer and consumer implementations;
    # the producer ABI is independently verified, not rewritten to current bytes.
    policy["contract_surfaces"] = [
        {key: value for key, value in surfaces[0].items() if key != "source_paths"}
    ]
    manifest = document(BUNDLE_MANIFEST_REF)
    manifest.pop("consumer_command", None)  # Operator syntax, not admission law.
    return _canonical_json({"policy": policy, "manifest": manifest})


@contextmanager
def _directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """Walk from / using directory FDs; no symlink component is followed."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute non-traversing runtime path required")
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _rename_new(parent: int, staging: str, target: str) -> None:
    # Linux renameat2(2): do not emulate NOREPLACE with exists() + rename().
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise OSError(errno.ENOSYS, "atomic no-replace rename is unavailable")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(staging), parent, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


def _expected_members(archive: dict[str, Any], identity: dict[str, Any]) -> dict:
    return {
        **archive["members"],
        "installation.json": {
            "kind": "file",
            "mode": 0o644,
            "payload": _canonical_json(identity) + b"\n",
        },
    }


def _directories(members: dict) -> set[str]:
    return {
        str(parent)
        for name in members
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }


def _verify_tree(descriptor: int, members: dict) -> None:
    expected_dirs = _directories(members)
    seen: set[str] = set()

    def walk(directory: int, prefix: str = "") -> None:
        with os.scandir(directory) as entries:
            for entry in entries:
                name = prefix + entry.name
                seen.add(name)
                if len(seen) > len(members) + len(expected_dirs):
                    raise ValueError("unexpected installed entry")
                info = os.stat(entry.name, dir_fd=directory, follow_symlinks=False)
                if name in expected_dirs:
                    if (
                        not stat.S_ISDIR(info.st_mode)
                        or stat.S_IMODE(info.st_mode) != 0o755
                    ):
                        raise ValueError("installed directory type or mode mismatch")
                    child = os.open(entry.name, DIRECTORY_FLAGS, dir_fd=directory)
                    try:
                        walk(child, name + "/")
                    finally:
                        os.close(child)
                    continue
                member = members.get(name)
                if member is None:
                    raise ValueError("unexpected installed entry")
                if stat.S_IMODE(info.st_mode) != member["mode"]:
                    raise ValueError("installed member mode mismatch")
                if member["kind"] == "symlink":
                    if (
                        not stat.S_ISLNK(info.st_mode)
                        or os.readlink(entry.name, dir_fd=directory) != member["target"]
                    ):
                        raise ValueError("installed symlink mismatch")
                else:
                    file = os.open(
                        entry.name,
                        os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                        dir_fd=directory,
                    )
                    with os.fdopen(file, "rb") as stream:
                        opened = os.fstat(stream.fileno())
                        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                            raise ValueError("one regular installed file required")
                        if (
                            stat.S_IMODE(opened.st_mode) != member["mode"]
                            or stream.read(len(member["payload"]) + 1)
                            != member["payload"]
                        ):
                            raise ValueError("installed bytes or mode mismatch")
        # Directories are also exact: no empty, hidden, or foreign subtrees.

    walk(descriptor)
    if seen != set(members) | expected_dirs:
        raise ValueError("installed entries are missing")


def _write_tree(root: Path, members: dict) -> None:
    for name in sorted(
        _directories(members), key=lambda value: (value.count("/"), value)
    ):
        with _directory(root / PurePosixPath(name).parent) as parent:
            os.mkdir(PurePosixPath(name).name, mode=0o755, dir_fd=parent)
            child = os.open(PurePosixPath(name).name, DIRECTORY_FLAGS, dir_fd=parent)
            try:
                os.fchmod(child, 0o755)
            finally:
                os.close(child)
    for name, member in sorted(members.items()):
        path = PurePosixPath(name)
        with _directory(root / path.parent) as parent:
            if member["kind"] == "symlink":
                os.symlink(member["target"], path.name, dir_fd=parent)
            else:
                descriptor = os.open(
                    path.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(member["payload"])
                    stream.flush()
                    os.fchmod(stream.fileno(), member["mode"])
                    os.fsync(stream.fileno())
    for name in sorted(_directories(members), key=lambda value: -value.count("/")):
        with _directory(root / name) as descriptor:
            os.fsync(descriptor)


def _verify_existing(parent_path: Path, target_name: str, members: dict) -> bool:
    with ExitStack() as stack:
        try:
            parent = stack.enter_context(_directory(parent_path))
        except FileNotFoundError:
            return False
        try:
            descriptor = os.open(target_name, DIRECTORY_FLAGS, dir_fd=parent)
        except FileNotFoundError:
            return False
        try:
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o755:
                raise ValueError("installed root mode mismatch")
            _verify_tree(descriptor, members)
        finally:
            os.close(descriptor)
    return True


def _gate(binding: dict, registry: Path, record_id: str | None = None) -> dict:
    gate = artifact_bundles.trust_gate(
        registry,
        artifact_class=ARTIFACT_CLASS,
        consumer_intent="runtime",
        subject_digest=binding["subject_digest"],
        record_id=record_id or "",
        expected_source_repo="abyss-machine",
        expected_source_ref=binding["source_ref"],
        expected_trust_root_mode="github_oidc",
        require_latest=True,
    )
    return {
        key: gate.get(key)
        for key in (
            "ok",
            "verdict",
            "record_id",
            "latest_record_id",
            "reasons",
            "blockers",
            "warnings",
            "manual_review",
        )
    }


def _require_allow(gate: dict) -> None:
    if not (
        gate.get("ok") is True
        and gate.get("verdict") == "allow"
        and re.fullmatch(r"sha256:[0-9a-f]{64}", str(gate.get("record_id", "")))
        and gate["record_id"] == gate.get("latest_record_id")
    ):
        raise ValueError("exact latest runtime allow required")


def install_python_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path,
    producer_source_root: str | Path,
    expected_source_ref: str,
    runtime_root: str | Path = DEFAULT_RUNTIME_ROOT,
    apply: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_python_install_v1",
        "ok": False,
        "status": "blocked",
        "provider_executed": False,
        "written": [],
        "claim_limit": "Verified placement only; Node binding, execution, coordinate semantics, STACK lifecycle and owner acceptance remain separate.",
    }
    staging: str | None = None
    try:
        producer = Path(producer_source_root).resolve(strict=True)
        producer_identity = _source_identity(producer, expected_source_ref)
        installer_identity = _source_identity(INSTALLER_ROOT)
        result["producer_source"] = producer_identity
        result["installer_source"] = installer_identity
        if _consumption_contract(producer) != _consumption_contract(INSTALLER_ROOT):
            raise ValueError("producer and current consumer artifact policy differ")
        archive = archive_tools.read_python_provider_archive(archive_path)
        if (
            archive["metadata"]["platform"] != "linux-x86_64"
            or os.uname().machine != "x86_64"
        ):
            raise ValueError("supported Linux x86_64 provider platform required")
        # Old producer ABI is checked against its exact clean checkout; current
        # consumer inputs and policy independently constrain consumption.
        lock = archive_tools._object(
            archive_tools._read_bounded(
                INSTALLER_ROOT
                / "manifests/code_intelligence_python_provider.lock.json",
                archive_tools.MAX_CONTROL_BYTES,
            )
        )
        if _canonical_json(lock) != _canonical_json(archive["lock"]):
            raise ValueError("provider lock differs from current consumer contract")
        inputs = INSTALLER_ROOT / "mechanics/code-intelligence/parts/scip-python"
        for name in ("package.json", "package-lock.json"):
            expected = archive_tools._object(
                archive_tools._read_bounded(
                    inputs / name, archive_tools.MAX_CONTROL_BYTES
                )
            )
            actual = archive_tools._object(
                archive["members"]["runtime/" + name]["payload"]
            )
            if _canonical_json(expected) != _canonical_json(actual):
                raise ValueError(
                    "provider inputs differ from current consumer contract"
                )
        binding = _subject_binding(
            archive,
            Path(bundle_dir).resolve(),
            subject_root=Path(subject_root).resolve(),
            source_root=producer,
        )
        result["subject_binding"] = binding
        if binding["ok"] is not True or binding["source_ref"] != expected_source_ref:
            raise ValueError("exact Python archive and source binding required")
        verification = artifact_bundles.verify_bundle(
            Path(bundle_dir).resolve(),
            subject_root=Path(subject_root).resolve(),
            repo_root=producer,
            write=False,
        )
        result["bundle_verify"] = _summarize_verify(verification)
        if verification.get("ok") is not True:
            raise ValueError("producer bundle verification failed")
        registry = Path(registry_dir).resolve()
        gate = _gate(binding, registry)
        result["trust_gate"] = gate
        _require_allow(gate)
        identity = {
            "schema": INSTALLATION_SCHEMA,
            "provider_id": archive_tools.PROVIDER_ID,
            "archive_sha256": archive["archive_sha256"],
            "aggregate_digest": binding["subject_digest"],
            "source_ref": expected_source_ref,
            "record_id": gate["record_id"],
            "producer_source": producer_identity,
            "installer_source": installer_identity,
            "entrypoint": "runtime/" + lock["distribution"]["entrypoint"],
            "node_minimum": lock["build"]["node_minimum"],
            "node_binding": "required-before-execution",
        }
        members = _expected_members(archive, identity)
        parent_path = Path(runtime_root) / "providers" / archive_tools.PROVIDER_ID
        target_name = archive["archive_sha256"].removeprefix("sha256:")
        target = parent_path / target_name
        result["target"] = str(target)
        # Even a dry run traverses existing ancestors without following links.
        if _verify_existing(parent_path, target_name, members):
            result.update(ok=True, status="already_installed", installation=identity)
            return result
        required_bytes = sum(
            len(member.get("payload", b"")) for member in members.values()
        ) + 4096 * (len(members) + len(_directories(members)) + 4)
        result["required_write_bytes"] = required_bytes
        if not apply:
            result.update(ok=True, status="ready_to_install")
            return result
        preflight = run_owner_preflights(
            archive_bytes=required_bytes,
            runtime_root=Path(runtime_root),
            provider_label="SCIP Python",
        )
        result["preflight"] = preflight
        if preflight.get("ok") is not True:
            raise ValueError("owner write preflight denied")
        with _directory(parent_path, create=True) as parent:
            staging = ".scip-python-" + secrets.token_hex(16)
            os.mkdir(staging, mode=0o700, dir_fd=parent)
            stage_path = parent_path / staging
            try:
                _write_tree(stage_path, members)
                with _directory(stage_path) as descriptor:
                    _verify_tree(descriptor, members)
                    os.fchmod(descriptor, 0o755)
                    os.fsync(descriptor)
                if (
                    _source_identity(producer, expected_source_ref) != producer_identity
                    or _source_identity(INSTALLER_ROOT) != installer_identity
                ):
                    raise ValueError("source identity changed during staging")
                result["trust_gate"] = _gate(binding, registry, gate["record_id"])
                _require_allow(result["trust_gate"])
                with _directory(parent_path) as current_parent:
                    current_info, original_info = (
                        os.fstat(current_parent),
                        os.fstat(parent),
                    )
                    if (current_info.st_dev, current_info.st_ino) != (
                        original_info.st_dev,
                        original_info.st_ino,
                    ):
                        raise ValueError("runtime parent changed during staging")
                _rename_new(parent, staging, target_name)
                staging = None
                result["written"] = [str(target)]
                os.fsync(parent)
                with _directory(target) as descriptor:
                    _verify_tree(descriptor, members)
            finally:
                if staging is not None:
                    # Only this invocation's fresh staging directory is removed.
                    shutil.rmtree(staging, dir_fd=parent)
            result.update(ok=True, status="installed", installation=identity)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result.update(reason=str(exc), error_type=type(exc).__name__)
    return result
