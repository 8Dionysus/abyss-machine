from __future__ import annotations

import base64
import copy
import gzip
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import artifact_bundles  # noqa: E402
from abyss_machine import code_intelligence_python_provider as provider  # noqa: E402

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
