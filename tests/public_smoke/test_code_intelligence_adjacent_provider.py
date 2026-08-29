from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import artifact_bundles  # noqa: E402
from abyss_machine.code_intelligence_adjacent_provider import (  # noqa: E402
    ARCHIVE_SCHEMA,
    build_adjacent_provider_archive,
    inspect_adjacent_provider_artifact,
    install_adjacent_provider_artifact,
    read_adjacent_provider_archive,
)


def fixture_lock(tmp_path: Path) -> tuple[Path, Path]:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    packages = []
    for provider, name, version in (("semgrep", "semgrep", "1.175.0"), ("markitdown", "markitdown", "0.1.7")):
        filename = f"{name}-{version}-py3-none-any.whl"
        payload = f"fixture:{name}:{version}\n".encode()
        (wheelhouse / filename).write_bytes(payload)
        packages.append({
            "name": name,
            "version": version,
            "filename": filename,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "provider": provider,
            "executable": name,
        })
    lock = {
        "schema": "abyss_machine_code_intelligence_adjacent_provider_lock_v1",
        "version": "fixture",
        "owner": "abyss-machine",
        "packages": packages,
    }
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    (wheelhouse / ("transitive_dependency_with_a_deliberately_long_distribution_name_" * 2 + "1.0-py3-none-any.whl")).write_bytes(b"transitive\n")
    return wheelhouse, lock_path


def test_adjacent_archive_is_deterministic_and_binds_every_wheel(tmp_path: Path) -> None:
    wheelhouse, lock_path = fixture_lock(tmp_path)
    first = build_adjacent_provider_archive(
        wheelhouse, tmp_path / "one.tar.gz", lock_path=lock_path,
        source_ref="commit:" + "a" * 40, platform="test",
    )
    second = build_adjacent_provider_archive(
        wheelhouse, tmp_path / "two.tar.gz", lock_path=lock_path,
        source_ref="commit:" + "a" * 40, platform="test",
    )
    assert first["archive_sha256"] == second["archive_sha256"]
    assert (tmp_path / "one.tar.gz").read_bytes() == (tmp_path / "two.tar.gz").read_bytes()
    archive = read_adjacent_provider_archive(tmp_path / "one.tar.gz")
    assert archive["metadata"]["schema"] == ARCHIVE_SCHEMA
    assert archive["metadata"]["providers"] == ["semgrep", "markitdown"]
    assert len(archive["metadata"]["files"]) == 3


def test_adjacent_install_is_fail_closed_without_signature_and_registry_admission(tmp_path: Path) -> None:
    wheelhouse, lock_path = fixture_lock(tmp_path)
    archive_path = tmp_path / "abyss-machine-code-intelligence-adjacent-providers-test.tar.gz"
    source_ref = "commit:" + "b" * 40
    build_adjacent_provider_archive(
        wheelhouse, archive_path, lock_path=lock_path, source_ref=source_ref, platform="test",
    )
    bundle = tmp_path / "bundle"
    sidecars = artifact_bundles.build_sidecars(
        bundle,
        manifest_ref=ROOT / "manifests/artifact_bundles/code_intelligence_provider.bundle.json",
        subject_root=tmp_path,
        owner_repo="abyss-machine",
        source_ref=source_ref,
        repo_root=ROOT,
    )
    inspection = inspect_adjacent_provider_artifact(
        archive_path, bundle, subject_root=tmp_path,
        registry_dir=tmp_path / "registry", source_root=ROOT,
    )
    installation = install_adjacent_provider_artifact(
        archive_path, bundle, subject_root=tmp_path,
        registry_dir=tmp_path / "registry", runtime_root=tmp_path / "runtime",
        source_root=ROOT, apply=True,
    )
    assert sidecars["ok"] is True
    assert inspection["subject_binding"]["ok"] is True
    assert inspection["checks"]["bundle_verify"]["ok"] is False
    assert inspection["status"] == "blocked"
    assert installation["status"] == "blocked"
    assert installation["blocking_reasons"] == ["exact_adjacent_provider_artifact_not_admitted"]
    assert not (tmp_path / "runtime").exists()
