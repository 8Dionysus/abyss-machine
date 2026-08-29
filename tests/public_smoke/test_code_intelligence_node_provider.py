from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import artifact_bundles  # noqa: E402
from abyss_machine.code_intelligence_node_provider import (  # noqa: E402
    ARCHIVE_SCHEMA,
    build_node_provider_archive,
    inspect_node_provider_artifact,
    install_node_provider_artifact,
    read_node_provider_archive,
)


def fixture_runtime(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "node-runtime"
    bin_root = runtime / "node_modules" / ".bin"
    bin_root.mkdir(parents=True)
    packages = []
    package_lock = {"lockfileVersion": 3, "packages": {}}
    rows = (
        ("tree-sitter", "tree-sitter-cli", "0.26.13", "tree-sitter"),
        ("tree-sitter", "tree-sitter-typescript", "0.23.2", None),
        ("scip", "@sourcegraph/scip-typescript", "0.4.0", "scip-typescript"),
        ("lsp", "typescript-language-server", "6.0.0", "typescript-language-server"),
        ("lsp", "typescript", "7.0.2", None),
    )
    for provider, name, version, executable in rows:
        integrity = "sha512-fixture-" + name
        package = {"name": name, "version": version, "integrity": integrity, "provider": provider}
        if executable:
            package["executable"] = executable
            script = runtime / "node_modules" / name / "cli.js"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("#!/usr/bin/env node\n", encoding="utf-8")
            script.chmod(0o755)
            (bin_root / executable).symlink_to(Path("..") / name / "cli.js")
        else:
            directory = runtime / "node_modules" / name
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "package.json").write_text(json.dumps({"name": name, "version": version}), encoding="utf-8")
        packages.append(package)
        package_lock["packages"][f"node_modules/{name}"] = {"version": version, "integrity": integrity}
    (runtime / "node_modules" / ".package-lock.json").write_text(json.dumps(package_lock), encoding="utf-8")
    lock = {"schema": "abyss_machine_code_intelligence_node_provider_lock_v1", "version": "fixture", "owner": "abyss-machine", "packages": packages}
    lock_path = tmp_path / "node-lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    return runtime, lock_path


def test_node_archive_is_deterministic_and_binds_locked_runtime(tmp_path: Path) -> None:
    runtime, lock_path = fixture_runtime(tmp_path)
    first = build_node_provider_archive(runtime, tmp_path / "one.tar.gz", lock_path=lock_path, source_ref="commit:" + "a" * 40, platform="test")
    second = build_node_provider_archive(runtime, tmp_path / "two.tar.gz", lock_path=lock_path, source_ref="commit:" + "a" * 40, platform="test")
    assert first["archive_sha256"] == second["archive_sha256"]
    archive = read_node_provider_archive(tmp_path / "one.tar.gz")
    assert archive["metadata"]["schema"] == ARCHIVE_SCHEMA
    assert archive["metadata"]["providers"] == ["tree-sitter", "scip", "lsp"]


def test_node_install_is_fail_closed_without_registry_admission(tmp_path: Path) -> None:
    runtime, lock_path = fixture_runtime(tmp_path)
    archive_path = tmp_path / "abyss-machine-code-intelligence-node-providers-test.tar.gz"
    source_ref = "commit:" + "b" * 40
    build_node_provider_archive(runtime, archive_path, lock_path=lock_path, source_ref=source_ref, platform="test")
    # The manifest requires the complete provider plane, so add deterministic
    # fixture subjects for the two sibling provider archives.
    (tmp_path / "abyss-machine-code-intelligence-universal-ctags-test.tar.gz").write_bytes(b"ctags-fixture\n")
    (tmp_path / "abyss-machine-code-intelligence-adjacent-providers-test.tar.gz").write_bytes(b"adjacent-fixture\n")
    bundle = tmp_path / "bundle"
    artifact_bundles.build_sidecars(bundle, manifest_ref=ROOT / "manifests/artifact_bundles/code_intelligence_provider.bundle.json", subject_root=tmp_path, owner_repo="abyss-machine", source_ref=source_ref, repo_root=ROOT)
    inspection = inspect_node_provider_artifact(archive_path, bundle, subject_root=tmp_path, registry_dir=tmp_path / "registry", source_root=ROOT)
    installation = install_node_provider_artifact(archive_path, bundle, subject_root=tmp_path, registry_dir=tmp_path / "registry", runtime_root=tmp_path / "installed", source_root=ROOT, apply=True)
    assert inspection["status"] == "blocked"
    assert installation["blocking_reasons"] == ["exact_node_provider_artifact_not_admitted"]
    assert not (tmp_path / "installed").exists()
