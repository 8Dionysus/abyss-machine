from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.code_intelligence_provider import (  # noqa: E402
    ARCHIVE_SCHEMA,
    build_provider_archive,
    exercise_provider,
    inspect_provider_artifact,
    install_provider,
    read_provider_archive,
)
from abyss_machine import artifact_bundles  # noqa: E402
from abyss_machine import code_intelligence_provider as provider  # noqa: E402


def fake_ctags(tmp_path: Path) -> Path:
    executable = tmp_path / "ctags"
    executable.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then\n"
        "  printf 'Universal Ctags 6.2.1\\n'\n"
        "  exit 0\n"
        "fi\n"
        "printf '{\"_type\":\"tag\",\"name\":\"fixture\"}\\n'\n",
        encoding="utf-8",
    )
    os.chmod(executable, 0o755)
    return executable


def test_provider_archive_is_deterministic_and_content_addressed(tmp_path: Path) -> None:
    executable = fake_ctags(tmp_path)
    first = build_provider_archive(
        executable,
        tmp_path / "one.tar.gz",
        source_ref="commit:" + "a" * 40,
        platform="test",
    )
    second = build_provider_archive(
        executable,
        tmp_path / "two.tar.gz",
        source_ref="commit:" + "a" * 40,
        platform="test",
    )

    assert first["archive_sha256"] == second["archive_sha256"]
    assert (tmp_path / "one.tar.gz").read_bytes() == (tmp_path / "two.tar.gz").read_bytes()
    archive = read_provider_archive(tmp_path / "one.tar.gz")
    assert archive["metadata"]["schema"] == ARCHIVE_SCHEMA
    assert archive["metadata"]["source_ref"] == "commit:" + "a" * 40
    assert archive["metadata"]["binary"]["sha256"].startswith("sha256:")


def test_install_is_fail_closed_without_exact_bundle_and_trust_gate(tmp_path: Path) -> None:
    executable = fake_ctags(tmp_path)
    archive_path = tmp_path / "provider.tar.gz"
    build_provider_archive(
        executable,
        archive_path,
        source_ref="commit:" + "b" * 40,
        platform="test",
    )

    runtime_root = tmp_path / "runtime"
    result = install_provider(
        archive_path,
        tmp_path / "missing-bundle",
        subject_root=tmp_path,
        runtime_root=runtime_root,
        registry_dir=tmp_path / "registry",
        source_root=ROOT,
        apply=True,
        preflight=lambda **_kwargs: {"ok": True, "preflights": []},
    )

    assert result["status"] == "blocked"
    assert result["written"] == []
    assert not runtime_root.exists()


def test_exercise_is_fail_closed_before_provider_execution(tmp_path: Path) -> None:
    executable = fake_ctags(tmp_path)
    archive_path = tmp_path / "provider.tar.gz"
    build_provider_archive(
        executable,
        archive_path,
        source_ref="commit:" + "c" * 40,
        platform="test",
    )

    result = exercise_provider(
        tmp_path / "missing-bundle",
        archive_path=archive_path,
        subject_root=tmp_path,
        runtime_root=tmp_path / "runtime",
        registry_dir=tmp_path / "registry",
        source_root=ROOT,
    )

    assert result["status"] == "blocked"
    assert "exact_provider_artifact_not_admitted" in result["blocking_reasons"]
    assert "health" not in result


def test_provider_archive_builds_required_candidate_sidecars_without_trust(tmp_path: Path) -> None:
    executable = fake_ctags(tmp_path)
    source_ref = "commit:" + "d" * 40
    archive_path = tmp_path / "abyss-machine-code-intelligence-universal-ctags-test.tar.gz"
    build_provider_archive(
        executable,
        archive_path,
        source_ref=source_ref,
        platform="test",
    )

    bundle = tmp_path / "bundle"
    result = artifact_bundles.build_sidecars(
        bundle,
        manifest_ref=ROOT / "manifests/artifact_bundles/code_intelligence_provider.bundle.json",
        subject_root=tmp_path,
        owner_repo="abyss-machine",
        source_ref=source_ref,
        repo_root=ROOT,
    )
    verification = artifact_bundles.verify_bundle(
        bundle,
        subject_root=tmp_path,
        repo_root=ROOT,
        write=False,
    )
    inspection = inspect_provider_artifact(
        archive_path,
        bundle,
        subject_root=tmp_path,
        registry_dir=tmp_path / "registry",
        source_root=ROOT,
        expected_source_ref=source_ref,
    )

    assert result["ok"] is True
    assert result["required_controls"] == [
        "abi_signature",
        "sbom",
        "slsa_in_toto",
        "sigstore_cosign",
    ]
    assert verification["ok"] is False
    assert artifact_bundles.SIGNATURE_DECISION_SIDECAR in verification["missing"]
    assert inspection["subject_binding"]["ok"] is True
    assert inspection["status"] == "blocked"
    assert inspection["trust_gate"]["verdict"] == "unknown"


def test_install_does_not_replace_a_dangling_provider_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = fake_ctags(tmp_path)
    archive_path = tmp_path / "provider.tar.gz"
    source_ref = "commit:" + "e" * 40
    build_provider_archive(
        executable,
        archive_path,
        source_ref=source_ref,
        platform="test",
    )

    runtime_root = tmp_path / "runtime"
    target = runtime_root / "providers" / "universal-ctags"
    target.parent.mkdir(parents=True)
    missing_target = tmp_path / "missing-target"
    target.symlink_to(missing_target, target_is_directory=True)
    monkeypatch.setattr(
        provider,
        "inspect_provider_artifact",
        lambda *_args, **_kwargs: {
            "status": "admitted",
            "artifact": {"subject_digest": "sha256:" + "f" * 64, "source_ref": source_ref},
        },
    )

    result = install_provider(
        archive_path,
        tmp_path / "unused-bundle",
        subject_root=tmp_path,
        runtime_root=runtime_root,
        registry_dir=tmp_path / "registry",
        source_root=ROOT,
        apply=True,
        preflight=lambda **_kwargs: {"ok": True, "preflights": []},
    )

    assert result["status"] == "blocked"
    assert result["blocking_reasons"] == ["different_provider_installation_exists; replacement is not implicit"]
    assert target.is_symlink()
    assert target.readlink() == missing_target
