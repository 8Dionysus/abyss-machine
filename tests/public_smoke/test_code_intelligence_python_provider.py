from __future__ import annotations

import base64
import copy
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from unittest.mock import create_autospec

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import artifact_bundles  # noqa: E402
from abyss_machine import code_intelligence_python_provider as provider  # noqa: E402
from abyss_machine import code_intelligence_python_install as installer  # noqa: E402

SOURCE = "commit:" + "a" * 40
LOCK = ROOT / "manifests/code_intelligence_python_provider.lock.json"
INPUTS = ROOT / "mechanics/code-intelligence/parts/scip-python"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def prepared(tmp_path: Path) -> dict:
    """Synthetic distribution metadata, never an upstream or admitted payload."""
    runtime = tmp_path / "prefix"
    lock = json.loads(LOCK.read_text())
    integrity = "sha512-" + base64.b64encode(b"fixture".ljust(64, b"!")).decode()
    lock["distribution"]["integrity"] = integrity
    manifest = {
        "name": "fixture",
        "version": "0.1.0",
        "private": True,
        "dependencies": {"@sourcegraph/scip-python": "0.6.6"},
    }
    packages = {"": {key: manifest[key] for key in ("name", "version", "dependencies")}}
    for name, version in (
        ("@sourcegraph/scip-python", "0.6.6"),
        ("dependency", "1.2.3"),
    ):
        key = "node_modules/" + name
        row = {
            "version": version,
            "integrity": integrity,
            "resolved": f"https://registry.npmjs.org/{name}/-/fixture.tgz",
        }
        if name == "@sourcegraph/scip-python":
            row["dependencies"] = {"dependency": "^1.0.0"}
        packages[key] = row
        write_json(runtime / key / "package.json", {"name": name, "version": version})
    package_lock = {"lockfileVersion": 3, "packages": packages}
    entrypoint = runtime / lock["distribution"]["entrypoint"]
    entrypoint.write_text("throw new Error('fixture must never execute');\n")
    entrypoint.chmod(0o755)
    bin_dir = runtime / "node_modules/.bin"
    bin_dir.mkdir()
    (bin_dir / "scip-python").symlink_to("../@sourcegraph/scip-python/index.js")
    write_json(runtime / "package.json", manifest)
    write_json(runtime / "package-lock.json", package_lock)
    write_json(
        runtime / "node_modules/.package-lock.json",
        {
            "lockfileVersion": 3,
            "packages": {key: row for key, row in packages.items() if key},
        },
    )
    write_json(tmp_path / "lock.json", lock)
    write_json(tmp_path / "package.json", manifest)
    write_json(tmp_path / "package-lock.json", package_lock)
    return {
        "runtime": runtime,
        "lock": lock,
        "manifest": manifest,
        "package_lock": package_lock,
        "args": {
            "lock_path": tmp_path / "lock.json",
            "package_manifest_path": tmp_path / "package.json",
            "package_lock_path": tmp_path / "package-lock.json",
            "source_ref": SOURCE,
        },
    }


def build(prepared: dict, path: Path) -> dict:
    return provider.build_python_provider_archive(
        prepared["runtime"], path, **prepared["args"]
    )


def test_public_lock_is_complete_but_not_admission() -> None:
    lock, manifest, package_lock = (
        json.loads(path.read_text())
        for path in (LOCK, INPUTS / "package.json", INPUTS / "package-lock.json")
    )
    result = provider.validate_python_provider_inputs(lock, manifest, package_lock)
    assert result["package_count"] == len(package_lock["packages"]) - 1
    assert result["package_count"] > 1
    assert manifest["dependencies"]["typescript"] == "4.9.5"
    assert (
        lock["consumer"]["position_encoding_basis"]
        == "pinned-source-inference-requires-runtime-canary"
    )


@pytest.mark.parametrize(
    "payload",
    [b'{"x":1e999}', b'{"x":NaN}', b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"],
    ids=["overflow", "nan", "nesting"],
)
def test_provider_json_rejects_nonfinite_or_deep_input(payload: bytes) -> None:
    with pytest.raises(ValueError):
        provider._object(payload)


def test_all_json_inputs_obey_the_control_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(provider, "MAX_CONTROL_BYTES", 4)
    with pytest.raises(ValueError, match="control byte bound"):
        provider._object(b'{"x":0}')


def test_json_nesting_guard_preserves_quoted_and_escaped_text() -> None:
    document = {"text": '\\"' + "[{" * 1000 + '"\\'}
    assert provider._object(json.dumps(document).encode()) == document


def test_deterministic_archive_never_executes_or_replaces(
    prepared: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("candidate packaging must not execute the provider")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    first = build(prepared, tmp_path / "one.tar.gz")
    second = build(prepared, tmp_path / "two.tar.gz")
    assert first["archive_sha256"] == second["archive_sha256"]
    assert first["provider_executed"] is False
    assert first["admission_status"] == "not_admitted"
    assert build(prepared, tmp_path / "one.tar.gz")["status"] == "already_present"
    archive = provider.read_python_provider_archive(tmp_path / "one.tar.gz")
    assert archive["metadata"]["package_count"] == 2
    assert archive["metadata"]["source_ref"] == SOURCE
    (tmp_path / "occupied.tar.gz").write_bytes(b"owned by somebody else")
    with pytest.raises(FileExistsError):
        build(prepared, tmp_path / "occupied.tar.gz")
    assert (tmp_path / "occupied.tar.gz").read_bytes() == b"owned by somebody else"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-transitive",
        "changed-integrity",
        "changed-metadata",
        "extra-file",
        "nested-package",
        "link-outside",
        "link-directory",
        "link-chain",
        "manifest-mismatch",
    ],
)
def test_prepared_prefix_rejects_drift(
    prepared: dict, tmp_path: Path, mutation: str
) -> None:
    runtime = prepared["runtime"]
    hidden_path = runtime / "node_modules/.package-lock.json"
    hidden = json.loads(hidden_path.read_text())
    if mutation == "missing-transitive":
        del hidden["packages"]["node_modules/dependency"]
        write_json(hidden_path, hidden)
    elif mutation == "changed-integrity":
        hidden["packages"]["node_modules/dependency"]["integrity"] += "different"
        write_json(hidden_path, hidden)
    elif mutation == "changed-metadata":
        write_json(
            runtime / "node_modules/dependency/package.json",
            {"name": "dependency", "version": "9.9.9"},
        )
    elif mutation == "extra-file":
        (runtime / "private-source.py").write_text("private = True\n")
    elif mutation == "nested-package":
        write_json(
            runtime / "node_modules/dependency/node_modules/foreign/package.json", {}
        )
    elif mutation == "manifest-mismatch":
        write_json(
            runtime / "package.json",
            {**prepared["manifest"], "scripts": {"postinstall": "unsafe"}},
        )
    else:
        link = runtime / "node_modules/.bin/scip-python"
        link.unlink()
        link.symlink_to(
            {
                "link-outside": "/outside",
                "link-directory": "../dependency",
                "link-chain": "another",
            }[mutation]
        )
        if mutation == "link-chain":
            (link.parent / "another").symlink_to("../@sourcegraph/scip-python/index.js")
    with pytest.raises(ValueError):
        build(prepared, tmp_path / "bad.tar.gz")
    assert not (tmp_path / "bad.tar.gz").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "optional",
        "script",
        "registry",
        "integrity",
        "incomplete",
        "root",
        "float-version",
    ],
)
def test_lock_rejects_unsealed_or_incomplete_closure(
    prepared: dict, mutation: str
) -> None:
    package_lock = copy.deepcopy(prepared["package_lock"])
    dependency = package_lock["packages"]["node_modules/dependency"]
    if mutation == "optional":
        dependency["optional"] = True
    elif mutation == "script":
        dependency["hasInstallScript"] = True
    elif mutation == "registry":
        dependency["resolved"] = "https://unbound.example/dependency.tgz"
    elif mutation == "integrity":
        dependency["integrity"] = "sha512-not-a-digest"
    elif mutation == "incomplete":
        del package_lock["packages"]["node_modules/dependency"]
    elif mutation == "root":
        package_lock["packages"][""]["dependencies"] = {}
    else:
        package_lock["lockfileVersion"] = 3.0
    with pytest.raises(ValueError):
        provider.validate_python_provider_inputs(
            prepared["lock"], prepared["manifest"], package_lock
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "payload",
        "mode",
        "duplicate-inventory",
        "float-count",
        "duplicate-json",
        "traversal",
        "symlink",
        "missing-control",
    ],
)
def test_archive_reader_rejects_tampering(
    prepared: dict, tmp_path: Path, mutation: str
) -> None:
    archive_path = tmp_path / "candidate.tar.gz"
    build(prepared, archive_path)
    archive = provider.read_python_provider_archive(archive_path)
    members = archive["members"]
    entrypoint = "runtime/" + prepared["lock"]["distribution"]["entrypoint"]
    metadata = archive["metadata"]
    if mutation == "payload":
        members[entrypoint]["payload"] += b"changed"
    elif mutation == "mode":
        members[entrypoint]["mode"] = 0o644
    elif mutation == "duplicate-inventory":
        metadata["files"].append(metadata["files"][0])
        members["provider.json"]["payload"] = json.dumps(metadata).encode()
    elif mutation == "float-count":
        metadata["package_count"] = 2.0
        members["provider.json"]["payload"] = json.dumps(metadata).encode()
    elif mutation == "duplicate-json":
        members["provider.json"]["payload"] = b'{"schema": 1, "schema": 2}'
    elif mutation == "traversal":
        members["runtime/../outside"] = members[entrypoint]
    elif mutation == "symlink":
        members["runtime/node_modules/.bin/scip-python"]["target"] = "../../../outside"
    else:
        del members["provider-lock.json"]
    archive_path.write_bytes(provider._tar_bytes(members))
    with pytest.raises(ValueError):
        provider.read_python_provider_archive(archive_path)


def test_duplicate_members_and_expansion_bomb_are_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for _ in range(2):
            info = tarfile.TarInfo("provider.json")
            info.size = 2
            archive.addfile(info, io.BytesIO(b"{}"))
    path = tmp_path / "duplicate.tar.gz"
    path.write_bytes(stream.getvalue())
    with pytest.raises(ValueError, match="duplicate"):
        provider.read_python_provider_archive(path)
    monkeypatch.setattr(provider, "MAX_TOTAL_BYTES", 512)
    monkeypatch.setattr(provider, "MAX_CONTROL_BYTES", 64)
    monkeypatch.setattr(provider, "MAX_FILES", 0)
    path.write_bytes(gzip.compress(b"\0" * 10000))
    with pytest.raises(ValueError, match="expansion bound"):
        provider.read_python_provider_archive(path)


def test_reader_rejects_hidden_trailing_payload(prepared: dict, tmp_path: Path) -> None:
    path = tmp_path / "candidate.tar.gz"
    build(prepared, path)
    path.write_bytes(
        gzip.compress(gzip.decompress(path.read_bytes()) + b"hidden payload")
    )
    with pytest.raises(ValueError, match="after archive end"):
        provider.read_python_provider_archive(path)


@pytest.mark.parametrize("corruption", ["truncated", "invalid-deflate"])
def test_corrupt_compression_is_a_blocked_inspection(
    prepared: dict, tmp_path: Path, corruption: str
) -> None:
    path = tmp_path / "candidate.tar.gz"
    build(prepared, path)
    payload = path.read_bytes()
    if corruption == "truncated":
        payload = payload[:-1]
    else:
        payload = payload[:10] + b"\xff" * 20 + payload[30:]
    path.write_bytes(payload)
    result = inspect(path, tmp_path / "no-bundle", tmp_path)
    assert result["status"] == "blocked"
    assert result["reason"] == "provider_inspection_failed"
    assert result["error_type"] in {"EOFError", "error"}


def bundle_for(prepared: dict, tmp_path: Path) -> tuple[Path, Path]:
    archive = (
        tmp_path / "abyss-machine-code-intelligence-python-provider-fixture.tar.gz"
    )
    build(prepared, archive)
    for name in ("universal-ctags", "node-providers", "adjacent-providers"):
        (
            tmp_path / f"abyss-machine-code-intelligence-{name}-fixture.tar.gz"
        ).write_bytes(b"untrusted fixture")
    bundle = tmp_path / "bundle"
    artifact_bundles.build_sidecars(
        bundle,
        manifest_ref=ROOT
        / "manifests/artifact_bundles/code_intelligence_provider.bundle.json",
        subject_root=tmp_path,
        owner_repo="abyss-machine",
        source_ref=SOURCE,
        repo_root=ROOT,
    )
    return archive, bundle


def inspect(archive: Path, bundle: Path, tmp_path: Path, source: str = SOURCE) -> dict:
    return provider.inspect_python_provider_artifact(
        archive,
        bundle,
        subject_root=tmp_path,
        registry_dir=tmp_path / "registry",
        source_root=ROOT,
        expected_source_ref=source,
    )


def test_real_unsigned_bundle_never_reaches_runtime_admission(
    prepared: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive, bundle = bundle_for(prepared, tmp_path)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unverified aggregate must not be admitted")

    monkeypatch.setattr(provider, "_trust_gate", forbidden)
    result = inspect(archive, bundle, tmp_path)
    assert result["status"] == "blocked"
    assert result["reason"] == "bundle_verification_failed"
    assert result["provider_executed"] is False


@pytest.mark.parametrize(
    "verdict,allowed",
    [
        ("allow", True),
        ("deny", False),
        ("manual_review_required", False),
        ("warn", False),
        ("unknown", False),
    ],
)
def test_exact_consumer_binding_and_verdict(
    prepared: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verdict: str,
    allowed: bool,
) -> None:
    archive, bundle = bundle_for(prepared, tmp_path)
    monkeypatch.setattr(
        artifact_bundles, "verify_bundle", lambda *args, **kwargs: {"ok": True}
    )
    calls = []

    def gate(registry: Path, **kwargs: object) -> dict:
        calls.append((registry, kwargs))
        return {"ok": verdict in {"allow", "warn"}, "verdict": verdict}

    monkeypatch.setattr(provider, "_trust_gate", gate)
    result = inspect(archive, bundle, tmp_path)
    assert (result["status"] == "admitted") is allowed
    subjects = json.loads((bundle / "artifact.subjects.json").read_text())
    assert calls == [
        (
            tmp_path / "registry",
            {"subject_digest": subjects["aggregate_digest"], "source_ref": SOURCE},
        )
    ]
    calls.clear()
    assert (
        inspect(archive, bundle, tmp_path, "commit:" + "b" * 40)["status"] == "blocked"
    )
    assert not calls
    archive.write_bytes(b"not the signed subject")
    assert inspect(archive, bundle, tmp_path)["status"] == "blocked"
    assert not calls


@pytest.fixture
def install_case(
    prepared: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict:
    """Fixture trust/source stubs test placement, never real admission."""
    archive, bundle = bundle_for(prepared, tmp_path)
    consumer = tmp_path / "consumer-source"
    write_json(
        consumer / "manifests/code_intelligence_python_provider.lock.json",
        prepared["lock"],
    )
    inputs = consumer / "mechanics/code-intelligence/parts/scip-python"
    write_json(inputs / "package.json", prepared["manifest"])
    write_json(inputs / "package-lock.json", prepared["package_lock"])
    for relative in (
        "manifests/artifact_signature_policy.manifest.json",
        "manifests/artifact_bundles/code_intelligence_provider.bundle.json",
    ):
        write_json(consumer / relative, json.loads((ROOT / relative).read_text()))
    monkeypatch.setattr(installer, "INSTALLER_ROOT", consumer)
    monkeypatch.setattr(
        installer,
        "_source_identity",
        lambda root, expected_ref=None: {
            "commit": "a" * 40 if root == ROOT else "b" * 40,
            "tree": "d" * 40,
        },
    )
    monkeypatch.setattr(
        artifact_bundles, "verify_bundle", lambda *args, **kwargs: {"ok": True}
    )
    gate_calls, preflight_calls = [], []

    def gate(*args: object, **kwargs: object) -> dict:
        gate_calls.append(kwargs)
        return {
            "ok": True,
            "verdict": "allow",
            "record_id": "sha256:" + "c" * 64,
            "latest_record_id": "sha256:" + "c" * 64,
        }

    def preflight(**kwargs: object) -> dict:
        preflight_calls.append(kwargs)
        return {"ok": True}

    real_gate = artifact_bundles.trust_gate
    monkeypatch.setattr(
        artifact_bundles,
        "trust_gate",
        create_autospec(real_gate, side_effect=gate),
    )
    monkeypatch.setattr(installer, "run_owner_preflights", preflight)
    return {
        "archive": archive,
        "bundle": bundle,
        "gate_calls": gate_calls,
        "real_gate": real_gate,
        "preflight_calls": preflight_calls,
        "runtime": tmp_path / "installed",
        "args": {
            "subject_root": tmp_path,
            "registry_dir": tmp_path / "registry",
            "producer_source_root": ROOT,
            "expected_source_ref": SOURCE,
            "runtime_root": tmp_path / "installed",
        },
    }


def install(case: dict, *, apply: bool = True) -> dict:
    return installer.install_python_provider_artifact(
        case["archive"], case["bundle"], **case["args"], apply=apply
    )


def test_install_dry_run_then_verified_idempotence(
    install_case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = install_case
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *a, **kw: pytest.fail("provider execution forbidden"),
    )
    dry = install(case, apply=False)
    assert dry["status"] == "ready_to_install" and dry["ok"]
    assert not case["runtime"].exists() and not case["preflight_calls"]
    result = install(case)
    assert result["status"] == "installed" and result["ok"]
    assert result["provider_executed"] is False
    assert result["installation"]["producer_source"]["commit"] == "a" * 40
    assert result["installation"]["installer_source"]["commit"] == "b" * 40
    assert result["installation"]["node_binding"] == "required-before-execution"
    assert all(
        call["consumer_intent"] == "runtime" and call["require_latest"] is True
        for call in case["gate_calls"]
    )
    assert case["gate_calls"][-1]["record_id"] == result["installation"]["record_id"]
    archive = provider.read_python_provider_archive(case["archive"])
    expanded = sum(
        len(member.get("payload", b"")) for member in archive["members"].values()
    )
    assert case["preflight_calls"][0]["archive_bytes"] > expanded
    assert case["preflight_calls"][0]["runtime_root"] == case["runtime"]
    monkeypatch.setattr(
        installer, "_write_tree", lambda *a: pytest.fail("idempotence must not rewrite")
    )
    again = install(case)
    assert again["status"] == "already_installed" and again["written"] == []
    assert len(case["preflight_calls"]) == 1


@pytest.mark.parametrize(
    "drift",
    [
        "bytes",
        "mode",
        "missing",
        "extra",
        "link",
        "directory-link",
        "empty-directory",
        "identity",
        "hardlink",
        "root-mode",
    ],
)
def test_installed_drift_is_not_repaired_or_accepted(
    install_case: dict, drift: str
) -> None:
    first = install(install_case)
    target = Path(first["target"])
    entry = target / first["installation"]["entrypoint"]
    if drift == "bytes":
        entry.write_bytes(b"foreign")
    elif drift == "mode":
        entry.chmod(0o600)
    elif drift == "missing":
        entry.unlink()
    elif drift == "extra":
        (target / "foreign").write_bytes(b"foreign")
    elif drift == "link":
        link = target / "runtime/node_modules/.bin/scip-python"
        link.unlink()
        link.symlink_to("/foreign")
    elif drift == "directory-link":
        directory = target / "runtime/node_modules/dependency"
        directory.rename(target / "moved")
        directory.symlink_to(target / "moved", target_is_directory=True)
    elif drift == "empty-directory":
        (target / "unexpected").mkdir()
    elif drift == "identity":
        (target / "installation.json").write_bytes(b"{}")
    elif drift == "hardlink":
        os.link(entry, install_case["runtime"] / "linked")
    else:
        target.chmod(0o777)
    for apply in (False, True):
        result = install(install_case, apply=apply)
        assert result["status"] == "blocked" and result["written"] == []
    assert len(install_case["preflight_calls"]) == 1


@pytest.mark.parametrize(
    "verdict", ["deny", "manual_review_required", "unknown", "warn"]
)
def test_installer_requires_actual_allow(
    install_case: dict, monkeypatch: pytest.MonkeyPatch, verdict: str
) -> None:
    monkeypatch.setattr(
        artifact_bundles,
        "trust_gate",
        lambda *a, **kw: {"ok": True, "verdict": verdict},
    )
    result = install(install_case)
    assert not result["ok"] and not install_case["runtime"].exists()
    assert not install_case["preflight_calls"]


def test_installer_stops_if_gate_changes_during_staging(
    install_case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def changing(*args: object, **kwargs: object) -> dict:
        nonlocal calls
        calls += 1
        return {
            "ok": True,
            "verdict": "allow" if calls == 1 else "deny",
            "record_id": "sha256:" + "c" * 64,
            "latest_record_id": "sha256:" + "c" * 64,
        }

    monkeypatch.setattr(artifact_bundles, "trust_gate", changing)
    result = install(install_case)
    assert result["status"] == "blocked" and result["written"] == []
    assert not Path(result["target"]).exists()
    assert list(Path(result["target"]).parent.iterdir()) == []


def test_installer_real_empty_registry_is_not_admission(
    install_case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(artifact_bundles, "trust_gate", install_case["real_gate"])
    result = install(install_case)
    assert result["status"] == "blocked"
    assert result["trust_gate"]["verdict"] == "unknown"
    assert result["trust_gate"]["blockers"] == ["no_registry_record"]
    assert not install_case["runtime"].exists()
    assert not install_case["preflight_calls"]


@pytest.mark.parametrize("failure", ["source-drift", "no-atomic-rename"])
def test_installer_cleans_only_staging_when_publication_is_unavailable(
    install_case: dict, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    if failure == "source-drift":
        original = installer._source_identity
        calls = 0

        def changed(root: Path, expected_ref: str | None = None) -> dict:
            nonlocal calls
            calls += 1
            identity = original(root, expected_ref)
            return {**identity, "tree": "e" * 40} if calls > 2 else identity

        monkeypatch.setattr(installer, "_source_identity", changed)
        reason = "source identity changed during staging"
    else:
        monkeypatch.setattr(installer.ctypes, "CDLL", lambda *a, **kw: object())
        reason = "atomic no-replace rename is unavailable"
    result = install(install_case)
    assert result["status"] == "blocked" and result["written"] == []
    assert reason in result["reason"]
    assert not Path(result["target"]).exists()
    assert list(Path(result["target"]).parent.iterdir()) == []


def test_installer_refuses_empty_destination_created_at_publish(
    install_case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = installer._rename_new
    occupied = []

    def race(parent: int, staging: str, target: str) -> None:
        os.mkdir(target, dir_fd=parent)
        occupied.append(os.stat(target, dir_fd=parent).st_ino)
        real(parent, staging, target)

    monkeypatch.setattr(installer, "_rename_new", race)
    result = install(install_case)
    assert result["status"] == "blocked" and result["error_type"] == "FileExistsError"
    target = Path(result["target"])
    assert target.stat().st_ino == occupied[0] and list(target.iterdir()) == []
    assert list(target.parent.iterdir()) == [target]


def test_installer_rejects_symlink_ancestor_and_owner_preflight_denial(
    install_case: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    install_case["runtime"].symlink_to(elsewhere, target_is_directory=True)
    assert install(install_case)["status"] == "blocked"
    assert list(elsewhere.iterdir()) == []
    install_case["runtime"].unlink()
    monkeypatch.setattr(installer, "run_owner_preflights", lambda **kw: {"ok": False})
    assert install(install_case)["reason"] == "owner write preflight denied"
    assert not install_case["runtime"].exists()


def test_installer_keeps_consumer_inputs_and_signature_required(
    install_case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        artifact_bundles, "verify_bundle", lambda *a, **kw: {"ok": False}
    )
    assert install(install_case)["reason"] == "producer bundle verification failed"
    assert not install_case["runtime"].exists()
    write_json(
        installer.INSTALLER_ROOT
        / "mechanics/code-intelligence/parts/scip-python/package.json",
        {},
    )
    assert (
        install(install_case)["reason"]
        == "provider inputs differ from current consumer contract"
    )
    assert not install_case["gate_calls"]


def test_source_identity_rejects_wrong_commit_dirty_or_ancestor_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "file").write_text("fixture\n")
    for args in (
        ("init", "-q"),
        ("add", "file"),
        (
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    identity = installer._source_identity(root)
    assert installer._source_identity(root, "commit:" + identity["commit"]) == identity
    with pytest.raises(ValueError, match="commit mismatch"):
        installer._source_identity(root, "commit:" + "e" * 40)
    (root / "untracked").write_text("dirty")
    with pytest.raises(ValueError, match="clean owner"):
        installer._source_identity(root)
    nested = root / "nested"
    nested.mkdir()
    with pytest.raises(ValueError, match="exact owner"):
        installer._source_identity(nested)


def test_installer_does_not_select_old_consumer_policy(install_case: dict) -> None:
    policy_path = (
        installer.INSTALLER_ROOT / "manifests/artifact_signature_policy.manifest.json"
    )
    policy = json.loads(policy_path.read_text())
    policy["artifact_classes"]["code_intelligence_provider_bundle"][
        "privacy_boundary"
    ] = "different policy"
    write_json(policy_path, policy)
    result = install(install_case)
    assert result["reason"] == "producer and current consumer artifact policy differ"
    assert not install_case["gate_calls"] and not install_case["runtime"].exists()
