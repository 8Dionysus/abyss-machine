import json
from pathlib import Path

import pytest

from abyss_machine import storage_cargo_adapters as cargo
from abyss_machine import storage_candidate_adapters as candidates
from abyss_machine import storage_candidate_contracts as contracts


def fixture(tmp_path):
    root = tmp_path / "cache"
    target = root / "cargo/target/example/source-bound/commit-toolchain"
    target.mkdir(parents=True)
    (target / "debug").mkdir()
    (target / "debug/.cargo-lock").touch()
    (target / "debug/product").write_bytes(b"rebuildable")
    preserved = []
    for role in ("product", "proof", "terminal_receipt"):
        path = tmp_path / role
        path.write_text(role)
        preserved.append({"role": role, "path": str(path), "sha256": cargo.file_digest(path)})
    attestation = tmp_path / "retirement.json"
    attestation.write_text(json.dumps({
        "schema": "abyss_machine_cargo_target_retirement_v1", "path": str(target),
        "source_id": "commit-toolchain", "owner": "project", "terminal": True,
        "future_consumers_independent": True, "unique_data_clear": True,
        "recovery_command": "cargo build --locked --target-dir CACHE", "preserved_files": preserved,
    }))
    candidate = {"candidate_id": "test", "path": str(target), "kind": "cargo_target",
                 "source_id": "commit-toolchain", "owner": "project",
                 "executor": {"type": "cargo_target_cleanup_v1", "owner_specific": True},
                 "fingerprint": candidates.filesystem_fingerprint(target),
                 "evidence": {"manifest": {"replacement": {"ref": "sha256:" + cargo.file_digest(attestation)}}}}
    return root, target, attestation, candidate


def test_dry_run_and_confirmed_exact_executor(tmp_path, monkeypatch):
    root, target, attestation, candidate = fixture(tmp_path)
    assert contracts.apply_contract(candidate, "snapshot")["executor_admitted"]
    dry = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation)
    assert dry["ok"] and dry["dry_run"] and target.exists()
    monkeypatch.setattr(cargo.storage_process_probe, "owner_process_references", lambda paths, **kwargs: {
        paths[0]: {"checked": True, "active": False, "refs": []}})
    actual = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation, dry_run=False, admission_check=lambda: {"ok": True})
    assert actual["ok"] and actual["reclaimed_bytes"] > 0 and not target.exists()
    assert (tmp_path / "product").exists() and attestation.exists()


@pytest.mark.parametrize("change", ["outside", "symlink", "preserved_digest", "attestation_digest", "drift", "nonterminal"])
def test_fail_closed(tmp_path, change):
    root, target, attestation, candidate = fixture(tmp_path)
    if change == "outside":
        candidate["path"] = str(tmp_path)
    elif change == "symlink":
        (target / "link").symlink_to(tmp_path / "product")
        candidate["fingerprint"] = candidates.filesystem_fingerprint(target)
    elif change == "preserved_digest":
        (tmp_path / "product").write_text("changed")
    elif change == "attestation_digest":
        attestation.write_text(attestation.read_text() + " ")
    elif change == "drift":
        (target / "new").touch()
    elif change == "nonterminal":
        doc = json.loads(attestation.read_text()); doc["terminal"] = False
        attestation.write_text(json.dumps(doc))
        candidate["evidence"]["manifest"]["replacement"]["ref"] = "sha256:" + cargo.file_digest(attestation)
    result = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation, dry_run=False, admission_check=lambda: {"ok": True})
    assert not result["ok"] and target.exists()


@pytest.mark.parametrize("refs", [{"checked": False, "refs": []}, {"checked": True, "refs": [{"pid": 999999}]}])
def test_writer_or_permission_uncertainty_blocks(tmp_path, monkeypatch, refs):
    root, target, attestation, candidate = fixture(tmp_path)
    monkeypatch.setattr(cargo.storage_process_probe, "owner_process_references", lambda paths, **kwargs: {paths[0]: refs})
    result = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation, dry_run=False, admission_check=lambda: {"ok": True})
    assert not result["ok"] and target.exists()


def test_external_hardlink_preserved_and_blocks_reclaim(tmp_path, monkeypatch):
    root, target, attestation, candidate = fixture(tmp_path)
    (tmp_path / "external-copy").hardlink_to(target / "debug/product")
    candidate["fingerprint"] = candidates.filesystem_fingerprint(target)
    monkeypatch.setattr(cargo.storage_process_probe, "owner_process_references", lambda paths, **kwargs: {
        paths[0]: {"checked": True, "refs": []}})
    result = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation, dry_run=False, admission_check=lambda: {"ok": True})
    assert not result["ok"] and "external_hardlinks_reclaim_uncertain" in result["reasons"]
    dry_run = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation)
    assert not dry_run["ok"] and "external_hardlinks_reclaim_uncertain" in dry_run["reasons"]
    assert target.exists() and (tmp_path / "external-copy").exists()


def test_internal_cargo_hardlinks_are_removable(tmp_path, monkeypatch):
    root, target, attestation, candidate = fixture(tmp_path)
    (target / "debug/linked-product").hardlink_to(target / "debug/product")
    candidate["fingerprint"] = candidates.filesystem_fingerprint(target)
    monkeypatch.setattr(cargo.storage_process_probe, "owner_process_references", lambda paths, **kwargs: {
        paths[0]: {"checked": True, "refs": []}})
    result = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation, dry_run=False, admission_check=lambda: {"ok": True})
    assert result["ok"] and not target.exists()
    assert result["capacity_delta_is_not_exclusive_attribution"]



def test_new_claim_or_expired_approval_blocks_immediately(tmp_path, monkeypatch):
    root, target, attestation, candidate = fixture(tmp_path)
    monkeypatch.setattr(cargo.storage_process_probe, "owner_process_references", lambda paths, **kwargs: {
        paths[0]: {"checked": True, "refs": []}})
    result = cargo.execute_cargo_target(candidate, cache_root=root, attestation_path=attestation,
                                       dry_run=False, admission_check=lambda: {"ok": False, "active_claims": ["new"]})
    assert not result["ok"] and result["error"] == "immediate_claim_or_approval_not_clear"
    assert target.exists()
