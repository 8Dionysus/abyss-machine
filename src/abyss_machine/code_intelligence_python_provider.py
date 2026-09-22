"""Offline SCIP Python candidates: distribution identity, never execution authority."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import tarfile
import tempfile
from typing import Any, Mapping
from urllib.parse import urlsplit

from .code_intelligence_provider import (
    _artifact_tools,
    _canonical_json,
    _safe_source_ref,
    _subject_binding,
    _summarize_verify,
    _trust_gate,
)

PROVIDER_ID = "scip-python"
ARCHIVE_SCHEMA = "abyss_machine_code_intelligence_python_provider_archive_v1"
LOCK_SCHEMA = "abyss_machine_code_intelligence_python_provider_lock_v1"
MAX_FILES = 12000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_CONTROL_BYTES = 4 * 1024 * 1024
CONTROLS = {"provider.json", "provider-lock.json"}
PACKAGE_PATH = re.compile(
    r"node_modules/(?:@[a-z0-9._-]+/)?[a-z0-9._-]+(?:/node_modules/(?:@[a-z0-9._-]+/)?[a-z0-9._-]+)*"
)


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _object(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_CONTROL_BYTES:
        raise ValueError("provider JSON exceeds control byte bound")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ValueError(f"non-JSON constant: {value}")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite provider JSON number")
        return number

    try:
        result = json.loads(
            payload,
            object_pairs_hook=unique,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except RecursionError as exc:
        raise ValueError("provider JSON exceeds nesting bound") from exc
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def _read_bounded(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("regular provider input required")
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("provider input exceeds byte bound")
    return payload


def _safe_path(name: str) -> bool:
    return bool(
        isinstance(name, str)
        and name
        and len(name) <= 1024
        and not any(ord(char) < 32 or ord(char) == 127 for char in name)
        and "\\" not in name
        and not name.startswith("/")
        and all(part not in {"", ".", ".."} for part in name.split("/"))
    )


def validate_python_provider_inputs(
    lock: Mapping[str, Any],
    manifest: Mapping[str, Any],
    package_lock: Mapping[str, Any],
) -> dict[str, Any]:
    """Check lock structure/closure; does not verify upstream payloads or run npm."""
    if (
        lock.get("schema"),
        lock.get("owner"),
        lock.get("provider_id"),
        lock.get("language"),
    ) != (LOCK_SCHEMA, "abyss-machine", PROVIDER_ID, "python"):
        raise ValueError("Python provider lock identity mismatch")
    distribution = lock.get("distribution", {})
    if (
        not isinstance(distribution, dict)
        or distribution.get("name") != "@sourcegraph/scip-python"
    ):
        raise ValueError("SCIP Python distribution required")
    if (
        distribution.get("entrypoint")
        != "node_modules/@sourcegraph/scip-python/index.js"
    ):
        raise ValueError("unsupported Python provider entrypoint")
    if not re.fullmatch(r"[0-9a-f]{40}", str(distribution.get("source_commit", ""))):
        raise ValueError("exact upstream source commit required")
    if lock.get("build", {}).get("install_scripts") != "disabled":
        raise ValueError("provider install scripts must remain disabled")
    consumer = lock.get("consumer", {})
    if (
        consumer.get("implicit_pip_discovery") != "forbidden"
        or consumer.get("project_environment") != "explicit-stack-owned-snapshot"
        or consumer.get("index_format") != "scip-protobuf-stream"
        or consumer.get("position_encoding") != "utf-16"
    ):
        raise ValueError("explicit STACK-owned project environment required")
    if manifest.get("private") is not True or "scripts" in manifest:
        raise ValueError("private script-free build prefix required")
    if (
        type(package_lock.get("lockfileVersion")) is not int
        or package_lock["lockfileVersion"] != 3
    ):
        raise ValueError("npm v3 package lock required")
    packages = package_lock.get("packages")
    if not isinstance(packages, dict) or not 1 < len(packages) <= 256:
        raise ValueError("bounded complete npm package set required")
    root = packages.get("")
    if not isinstance(root, dict) or any(
        root.get(key) != manifest.get(key)
        for key in ("name", "version", "dependencies")
    ):
        raise ValueError("npm manifest and root lock mismatch")
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict) or dependencies.get(
        distribution["name"]
    ) != distribution.get("version"):
        raise ValueError("root SCIP dependency must be exactly pinned")
    for path, row in packages.items():
        if not isinstance(row, dict):
            raise ValueError("invalid npm package row")
        if not path:
            continue
        if not _safe_path(path) or not PACKAGE_PATH.fullmatch(path):
            raise ValueError("non-registry npm package path")
        if any(
            row.get(flag)
            for flag in ("link", "dev", "optional", "hasInstallScript", "os", "cpu")
        ):
            raise ValueError("conditional or script-bearing dependency is unsupported")
        if not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
            str(row.get("version", "")),
        ):
            raise ValueError("exact package version required")
        url = urlsplit(str(row.get("resolved", "")))
        if (
            url.scheme != "https"
            or url.netloc != "registry.npmjs.org"
            or url.query
            or url.fragment
            or not url.path.endswith(".tgz")
        ):
            raise ValueError("exact npm registry tarball required")
        integrity = row.get("integrity", "")
        try:
            checksum = base64.b64decode(
                integrity.removeprefix("sha512-"), validate=True
            )
        except (ValueError, AttributeError) as exc:
            raise ValueError("SHA-512 package integrity required") from exc
        if not integrity.startswith("sha512-") or len(checksum) != 64:
            raise ValueError("SHA-512 package integrity required")
    scip = packages.get("node_modules/" + distribution["name"], {})
    if any(scip.get(key) != distribution.get(key) for key in ("version", "integrity")):
        raise ValueError("provider distribution and npm lock mismatch")
    for path, row in packages.items():
        for key in ("dependencies", "peerDependencies"):
            for name in row.get(key, {}):
                if (
                    key == "peerDependencies"
                    and row.get("peerDependenciesMeta", {})
                    .get(name, {})
                    .get("optional")
                    is True
                ):
                    continue
                parent = path
                while True:
                    target = (parent + "/" if parent else "") + "node_modules/" + name
                    if target in packages:
                        break
                    if not parent:
                        raise ValueError(
                            f"npm dependency closure is incomplete: {name}"
                        )
                    parent = (
                        parent.rpartition("/node_modules/")[0]
                        if "/node_modules/" in parent
                        else ""
                    )
    return {
        "package_count": len(packages) - 1,
        "lock_digest": _digest(_canonical_json(lock)),
        "package_lock_digest": _digest(_canonical_json(package_lock)),
    }


def _regular(members: Mapping[str, dict[str, Any]], name: str) -> bytes:
    member = members.get(name, {})
    if member.get("kind") != "file":
        raise ValueError(f"regular provider file required: {name}")
    return member["payload"]


def _runtime_identity(
    members: Mapping[str, dict[str, Any]], lock: dict[str, Any]
) -> dict[str, Any]:
    manifest = _object(_regular(members, "runtime/package.json"))
    package_lock = _object(_regular(members, "runtime/package-lock.json"))
    identity = validate_python_provider_inputs(lock, manifest, package_lock)
    installed = _object(_regular(members, "runtime/node_modules/.package-lock.json"))
    expected = {path: row for path, row in package_lock["packages"].items() if path}
    if (
        type(installed.get("lockfileVersion")) is not int
        or installed["lockfileVersion"] != 3
        or set(installed.get("packages", {})) != set(expected)
    ):
        raise ValueError("installed npm closure differs from complete package lock")
    for path, row in expected.items():
        actual = installed["packages"][path]
        if any(
            actual.get(key) != row.get(key)
            for key in ("version", "integrity", "resolved")
        ):
            raise ValueError(f"installed package identity mismatch: {path}")
        package = _object(_regular(members, f"runtime/{path}/package.json"))
        name = path.rsplit("node_modules/", 1)[1]
        if package.get("name") != name or package.get("version") != row["version"]:
            raise ValueError(f"installed package metadata mismatch: {path}")
    _regular(members, "runtime/" + lock["distribution"]["entrypoint"])
    for name, member in members.items():
        if name in CONTROLS:
            continue
        relative = name.removeprefix("runtime/")
        if relative not in {
            "package.json",
            "package-lock.json",
            "node_modules/.package-lock.json",
        }:
            if not relative.startswith("node_modules/") or (
                not relative.startswith("node_modules/.bin/")
                and not any(relative.startswith(path + "/") for path in expected)
            ):
                raise ValueError("unexpected file outside locked runtime")
            if not relative.startswith("node_modules/.bin/"):
                package_path = max(
                    (path for path in expected if relative.startswith(path + "/")),
                    key=len,
                )
                remainder = relative[len(package_path) + 1 :]
                if "node_modules" in remainder.split("/"):
                    raise ValueError("unlocked nested npm package")
            elif member["kind"] != "symlink":
                raise ValueError("npm bin entries must be internal symlinks")
        for parent in PurePosixPath(name).parents:
            if str(parent) in members:
                raise ValueError("provider file shadows a directory")
        if member["kind"] == "symlink":
            target = member["target"]
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(name), target)
            )
            if (
                not isinstance(target, str)
                or "\\" in target
                or not _safe_path(resolved)
                or not resolved.startswith("runtime/")
            ):
                raise ValueError("unsafe provider symlink")
            _regular(
                members, resolved
            )  # No dangling links, link chains or directory links.
    return identity


def _inventory(members: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "path": name,
            "kind": item["kind"],
            "mode": item["mode"],
            **(
                {"bytes": len(item["payload"]), "sha256": _digest(item["payload"])}
                if item["kind"] == "file"
                else {"target": item["target"]}
            ),
        }
        for name, item in sorted(members.items())
        if name not in CONTROLS
    ]


def _tar_bytes(members: Mapping[str, dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(
            fileobj=compressed, mode="w|", format=tarfile.GNU_FORMAT
        ) as archive:
            for name, member in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.mode = member["mode"]
                if member["kind"] == "symlink":
                    info.type, info.linkname = tarfile.SYMTYPE, member["target"]
                    archive.addfile(info)
                else:
                    info.size = len(member["payload"])
                    archive.addfile(info, io.BytesIO(member["payload"]))
    return buffer.getvalue()


def build_python_provider_archive(
    runtime_dir: str | Path,
    output: str | Path,
    *,
    lock_path: str | Path,
    package_manifest_path: str | Path,
    package_lock_path: str | Path,
    source_ref: str,
    platform: str = "linux-x86_64",
) -> dict[str, Any]:
    """Package a supplied npm-ci prefix without downloading or executing it."""
    if not _safe_source_ref(source_ref) or not re.fullmatch(
        r"[a-z0-9_-]{1,64}", platform
    ):
        raise ValueError("qualified source ref and bounded platform required")
    lock = _object(_read_bounded(Path(lock_path), MAX_CONTROL_BYTES))
    manifest = _object(_read_bounded(Path(package_manifest_path), MAX_CONTROL_BYTES))
    package_lock = _object(_read_bounded(Path(package_lock_path), MAX_CONTROL_BYTES))
    validate_python_provider_inputs(lock, manifest, package_lock)
    runtime = Path(runtime_dir).resolve(strict=True)
    members: dict[str, dict[str, Any]] = {}
    total = 0
    for path in runtime.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        name = "runtime/" + path.relative_to(runtime).as_posix()
        if not _safe_path(name) or len(members) >= MAX_FILES:
            raise ValueError("unsafe or excessive provider member set")
        if path.is_symlink():
            members[name] = {
                "kind": "symlink",
                "target": os.readlink(path),
                "mode": 0o777,
            }
        elif path.is_file():
            payload = _read_bounded(path, MAX_MEMBER_BYTES)
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("provider exceeds total byte bound")
            members[name] = {
                "kind": "file",
                "payload": payload,
                "mode": 0o755 if path.stat().st_mode & 0o111 else 0o644,
            }
        else:
            raise ValueError("special provider files are forbidden")
    if (
        _object(_regular(members, "runtime/package.json")) != manifest
        or _object(_regular(members, "runtime/package-lock.json")) != package_lock
    ):
        raise ValueError("prepared runtime does not match supplied build inputs")
    identity = _runtime_identity(members, lock)
    metadata = {
        "schema": ARCHIVE_SCHEMA,
        "provider_id": PROVIDER_ID,
        "source_ref": source_ref,
        "platform": platform,
        **identity,
        "files": _inventory(members),
    }
    for name, document in (("provider.json", metadata), ("provider-lock.json", lock)):
        payload = _canonical_json(document) + b"\n"
        if len(payload) > MAX_CONTROL_BYTES:
            raise ValueError("provider control file exceeds byte bound")
        members[name] = {"kind": "file", "payload": payload, "mode": 0o644}
    payload = _tar_bytes(members)
    if len(payload) > MAX_TOTAL_BYTES:
        raise ValueError("provider archive exceeds byte bound")
    target = Path(output).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".scip-python-", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        try:
            os.link(temporary, target)  # Atomic create, never replacement.
            status = "built"
        except FileExistsError:
            if (
                target.is_symlink()
                or not target.is_file()
                or _read_bounded(target, MAX_TOTAL_BYTES) != payload
            ):
                raise FileExistsError("refusing to replace provider artifact") from None
            status = "already_present"
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "schema": "abyss_machine_code_intelligence_python_provider_build_v1",
        "status": status,
        "provider_id": PROVIDER_ID,
        "output": str(target),
        "archive_sha256": _digest(payload),
        "archive_bytes": len(payload),
        "metadata": metadata,
        "admission_status": "not_admitted",
        "provider_executed": False,
    }


def read_python_provider_archive(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path).resolve(strict=True)
    payload = _read_bounded(archive_path, MAX_TOTAL_BYTES)
    members: dict[str, dict[str, Any]] = {}
    total = 0
    expanded_limit = MAX_TOTAL_BYTES + 2 * MAX_CONTROL_BYTES + (MAX_FILES + 2) * 2048
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
        expanded = stream.read(expanded_limit + 1)
    if len(expanded) > expanded_limit:
        raise ValueError("archive exceeds total expansion bound")
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        for member in archive:
            if (
                not _safe_path(member.name)
                or member.name in members
                or len(members) >= MAX_FILES + 2
            ):
                raise ValueError("unsafe, duplicate or excessive archive member")
            if member.name not in CONTROLS and not member.name.startswith("runtime/"):
                raise ValueError("unexpected archive member")
            if member.issym() and member.name not in CONTROLS and member.mode == 0o777:
                members[member.name] = {
                    "kind": "symlink",
                    "target": member.linkname,
                    "mode": member.mode,
                }
            elif member.isreg() and member.mode in {0o644, 0o755}:
                limit = (
                    MAX_CONTROL_BYTES if member.name in CONTROLS else MAX_MEMBER_BYTES
                )
                total += member.size
                if (
                    member.size < 0
                    or member.size > limit
                    or total > MAX_TOTAL_BYTES + 2 * MAX_CONTROL_BYTES
                ):
                    raise ValueError("archive exceeds expanded byte bound")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("missing archive payload")
                data = stream.read(limit + 1)
                if len(data) != member.size:
                    raise ValueError("archive payload size mismatch")
                members[member.name] = {
                    "kind": "file",
                    "payload": data,
                    "mode": member.mode,
                }
            else:
                raise ValueError("unsupported archive member type or mode")
        if expanded[archive.offset :].strip(b"\0"):
            raise ValueError("nonzero data after archive end")
    metadata = _object(_regular(members, "provider.json"))
    lock = _object(_regular(members, "provider-lock.json"))
    if (
        metadata.get("schema") != ARCHIVE_SCHEMA
        or metadata.get("provider_id") != PROVIDER_ID
        or not _safe_source_ref(metadata.get("source_ref", ""))
        or not re.fullmatch(r"[a-z0-9_-]{1,64}", str(metadata.get("platform", "")))
    ):
        raise ValueError("Python provider archive identity mismatch")
    identity = _runtime_identity(members, lock)
    if _canonical_json({key: metadata.get(key) for key in identity}) != _canonical_json(
        identity
    ) or _canonical_json(metadata.get("files")) != _canonical_json(_inventory(members)):
        raise ValueError("Python provider inventory or lock identity mismatch")
    return {
        "provider_id": PROVIDER_ID,
        "archive_path": str(archive_path),
        "archive_sha256": _digest(payload),
        "archive_bytes": len(payload),
        "metadata": metadata,
        "lock": lock,
        "members": members,
    }


def inspect_python_provider_artifact(
    archive_path: str | Path,
    bundle_dir: str | Path,
    *,
    subject_root: str | Path,
    registry_dir: str | Path,
    source_root: str | Path,
    expected_source_ref: str,
) -> dict[str, Any]:
    """Require exact signed aggregate membership and latest runtime admission."""
    result: dict[str, Any] = {
        "schema": "abyss_machine_code_intelligence_python_provider_inspection_v1",
        "provider_id": PROVIDER_ID,
        "status": "blocked",
        "provider_executed": False,
        "claim_limit": "Inspection does not install, execute, verify coordinate semantics or establish owner acceptance.",
    }
    if not _safe_source_ref(expected_source_ref):
        result["reason"] = "exact_expected_source_ref_required"
        return result
    try:
        archive = read_python_provider_archive(archive_path)
        binding = _subject_binding(
            archive,
            Path(bundle_dir).resolve(),
            subject_root=Path(subject_root).resolve(),
            source_root=Path(source_root).resolve(),
        )
        result["subject_binding"] = binding
        if (
            binding.get("ok") is not True
            or binding.get("source_ref") != expected_source_ref
        ):
            result["reason"] = "exact_python_archive_not_bound"
            return result
        verification = _artifact_tools().verify_bundle(
            Path(bundle_dir).resolve(),
            subject_root=Path(subject_root).resolve(),
            repo_root=Path(source_root).resolve(),
            write=False,
        )
        result["bundle_verify"] = _summarize_verify(verification)
        if verification.get("ok") is not True:
            result["reason"] = "bundle_verification_failed"
            return result
        gate = _trust_gate(
            Path(registry_dir).resolve(),
            subject_digest=binding["subject_digest"],
            source_ref=expected_source_ref,
        )
        result["trust_gate"] = {
            key: gate.get(key)
            for key in (
                "ok",
                "verdict",
                "record_id",
                "latest_record_id",
                "reasons",
                "blockers",
            )
        }
        if gate.get("ok") is True and gate.get("verdict") == "allow":
            result["status"] = "admitted"
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        tarfile.TarError,
    ) as exc:
        result["reason"], result["error_type"] = (
            "provider_inspection_failed",
            type(exc).__name__,
        )
    return result
