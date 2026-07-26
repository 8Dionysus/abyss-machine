from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import cli


def test_docs_agents_mesh_skips_materialized_artifact_subject_store(tmp_path: Path, monkeypatch) -> None:
    state_root = tmp_path / "var" / "lib" / "abyss-machine"
    srv_root = tmp_path / "srv" / "abyss-machine"
    monkeypatch.setattr(cli, "STATE_DIR", state_root)
    monkeypatch.setattr(cli, "ARTIFACTS_ROOT", state_root / "artifacts")
    monkeypatch.setattr(cli, "ABYSS_MACHINE_ROOT", srv_root)
    monkeypatch.setattr(cli, "ABYSS_MACHINE_STORAGE_ROOT", srv_root / "storage")
    monkeypatch.setattr(cli, "ABYSS_MACHINE_TMP_ROOT", srv_root / "tmp")
    custom_subject_root = state_root / "custom-subject-store"
    monkeypatch.setenv("ABYSS_MACHINE_ARTIFACT_SUBJECT_STORE_ROOTS", str(custom_subject_root))

    subject_card = (
        state_root
        / "artifacts"
        / "subjects"
        / "aoa_session_memory_portable_bundle"
        / "bdbab27504173e7e2a1c7d8a680fb2f0eaedf8fad8bccfd4f35f467c1c5a95bb"
        / "AGENTS.md"
    )
    custom_subject_card = custom_subject_root / "bundle" / "digest" / "AGENTS.md"
    host_card = state_root / "nervous" / "AGENTS.md"
    subject_card.parent.mkdir(parents=True)
    custom_subject_card.parent.mkdir(parents=True)
    host_card.parent.mkdir(parents=True)
    subject_card.write_text("# Portable Subject Route\n", encoding="utf-8")
    custom_subject_card.write_text("# Portable Subject Route\n", encoding="utf-8")
    host_card.write_text("# Host Nervous Route\n", encoding="utf-8")

    discovered = cli.docs_agents_mesh_discovered_cards()

    assert str(host_card) in discovered
    assert str(subject_card) not in discovered
    assert str(custom_subject_card) not in discovered
    assert cli.docs_agents_mesh_skip_root(subject_card) is True
    assert cli.docs_agents_mesh_skip_root(custom_subject_card) is True
