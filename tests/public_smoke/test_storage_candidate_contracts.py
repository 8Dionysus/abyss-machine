from __future__ import annotations

import copy
import datetime as dt

from abyss_machine import storage_candidate_contracts as contracts


NOW = dt.datetime(2026, 8, 1, 16, 0, tzinfo=dt.timezone.utc)


def _observation(
    *,
    path: str = "/srv/abyss-machine/tmp/fixture",
    owner: str = "abyss-machine",
    kind: str = "generated_tmp",
    fingerprint: str = "fp-1",
    physical_bytes: int = 1024,
    reclaimable_bytes: int = 1024,
) -> dict:
    return {
        "path": path,
        "owner": owner,
        "kind": kind,
        "source_id": path,
        "source_adapter": "fixture",
        "exists": True,
        "physical_bytes": physical_bytes,
        "reclaimable_bytes": reclaimable_bytes,
        "fingerprint": {"digest": fingerprint, "complete": True, "entries": 1},
        "latest_mtime": "2026-07-20T00:00:00+00:00",
        "observed_at": NOW.isoformat(),
        "executor": {
            "type": contracts.EXECUTORS_BY_KIND[kind],
            "owner_specific": True,
        },
        "evidence": {
            "protection": {"decision": "allow_candidate", "owner": "abyss_machine"},
            "process_refs": {"active": False, "refs": []},
            "mount_refs": {"active": False, "refs": []},
            "service_refs": {"active": False, "units": []},
            "container_refs": {"active": False, "containers": []},
            "config_refs": {"active": False, "strong_live_hit_count": 0, "hits": []},
            "runtime_refs": {"active": False, "matches": []},
            "active_claims": [],
            "unique_data": {"status": "clear", "reasons": ["fixture_clear"]},
            "recovery": {"verified": True, "command": "fixture rebuild"},
            "replacement": {"verified": False},
            "backup": {"fresh": False, "digest_match": False},
            "restore": {"verified": False},
        },
    }


def _one_scan_policy() -> dict:
    return {
        "default": {"minimum_observations": 1, "quiet_seconds": 0},
        "by_kind": {
            kind: {"minimum_observations": 1, "quiet_seconds": 0}
            for kind in contracts.EXECUTORS_BY_KIND
        },
    }


def test_candidate_id_is_stable_and_owner_typed() -> None:
    first = contracts.stable_candidate_id(
        owner="abyss-machine",
        kind="runtime",
        path="/srv/abyss-machine/runtimes/example",
        source_id="runtime:example",
    )
    assert first == contracts.stable_candidate_id(
        owner="abyss-machine",
        kind="runtime",
        path="/srv/abyss-machine/runtimes/example",
        source_id="runtime:example",
    )
    assert first != contracts.stable_candidate_id(
        owner="another-owner",
        kind="runtime",
        path="/srv/abyss-machine/runtimes/example",
        source_id="runtime:example",
    )


def test_failed_runtime_with_preserved_receipts_and_verified_replacement_is_delete_ready() -> None:
    observation = _observation(kind="failed_runtime")
    observation["executor"] = {
        "type": "runtime_retire_preserve_receipts",
        "owner_specific": True,
        "preserve": ["receipts", "manifest"],
    }
    observation["evidence"]["replacement"] = {
        "verified": True,
        "ref": "/srv/abyss-machine/runtimes/replacement",
        "validator": "owner runtime validator",
    }
    observation["evidence"]["unique_data"] = {
        "status": "clear",
        "reasons": ["receipts and manifest are outside the candidate payload"],
    }

    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "delete_ready_superseded"
    assert record["executor"]["preserve"] == ["receipts", "manifest"]


def test_gemma_like_active_service_and_container_remains_current() -> None:
    observation = _observation(kind="model_cache", path="/srv/abyss-machine/cache/ai/gemma4")
    observation["evidence"]["service_refs"] = {
        "active": True,
        "units": [{"unit": "abyss-gemma4-spark-digest.timer"}],
    }
    observation["evidence"]["container_refs"] = {
        "active": True,
        "containers": [{"name": "llama-cpp", "running": True}],
    }

    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "keep_current"
    codes = {item["code"] for item in record["blockers"]}
    assert "active_service_reference" in codes
    assert "active_container_reference" in codes


def test_absence_of_pid_does_not_make_openvino_cache_ready_without_recovery() -> None:
    observation = _observation(kind="openvino_cache", path="/srv/abyss-machine/cache/ai/openvino/example")
    observation["evidence"]["recovery"] = {"verified": False, "command": None}

    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "blocked_unknown"
    assert "recovery_or_replacement_not_verified" in {item["code"] for item in record["blockers"]}


def test_unique_dirty_patches_require_archive_and_stale_vault_is_pending() -> None:
    observation = _observation(kind="git_worktree")
    observation["evidence"]["unique_data"] = {
        "status": "present",
        "archivable": True,
        "reasons": ["two dirty patch files"],
    }
    observation["evidence"]["backup"] = {
        "fresh": False,
        "digest_match": False,
        "status": "latest-success older than candidate mutation",
    }

    pending = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )
    assert pending["verdict"] == "archive_pending"
    assert "backup_lane_not_fresh" in {item["code"] for item in pending["blockers"]}

    observation["evidence"]["backup"] = {
        "fresh": True,
        "digest_match": True,
        "status": "verified",
    }
    observation["evidence"]["restore"] = {
        "verified": True,
        "command": "restore fixture",
        "status": "restore-check passed",
    }
    ready = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )
    assert ready["verdict"] == "archive_ready"


def test_active_claim_blocks_even_when_process_scan_is_clear() -> None:
    observation = _observation()
    observation["evidence"]["active_claims"] = [
        {
            "claim_id": "session-claim",
            "owner": "codex-session",
            "expires_at": "2026-08-01T18:00:00+00:00",
        }
    ]

    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "keep_current"
    assert "active_session_or_change_claim" in {item["code"] for item in record["blockers"]}


def test_owner_unknown_fails_closed() -> None:
    observation = _observation(owner="unknown")
    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "blocked_owner_reference"
    assert "owner_unknown" in {item["code"] for item in record["blockers"]}


def test_aoa_owner_verdict_cannot_be_overridden_by_generic_age_or_size() -> None:
    observation = _observation(
        path="/srv/AbyssOS/.aoa/sessions/.projection-stage",
        owner="aoa-session-memory",
        kind="aoa_owner_debris",
        physical_bytes=5_000_000_000,
        reclaimable_bytes=5_000_000_000,
    )
    observation["evidence"]["protection"] = {
        "decision": "deny",
        "owner": "aoa-session-memory",
    }
    observation["evidence"]["owner_verdict"] = {
        "authoritative": True,
        "safe_to_remove": False,
        "status": "orphaned_raw_authority_unresolved",
    }

    record = contracts.candidate_record(
        observation,
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    assert record["verdict"] == "blocked_owner_reference"
    assert "owner_verdict_blocks_removal" in {item["code"] for item in record["blockers"]}


def test_delete_ready_requires_repeated_stable_observations_and_quiet_window() -> None:
    observation = _observation()
    policy = {"default": {"minimum_observations": 3, "quiet_seconds": 0}}

    first = contracts.candidate_record(observation, configured_policy=policy, now_time=NOW)
    second_observation = copy.deepcopy(observation)
    second_observation["observed_at"] = "2026-08-01T16:10:00+00:00"
    second = contracts.candidate_record(second_observation, previous=first, configured_policy=policy, now_time=NOW)
    third_observation = copy.deepcopy(observation)
    third_observation["observed_at"] = "2026-08-01T16:20:00+00:00"
    third = contracts.candidate_record(third_observation, previous=second, configured_policy=policy, now_time=NOW)

    assert first["verdict"] == "blocked_unknown"
    assert second["verdict"] == "blocked_unknown"
    assert third["verdict"] == "delete_ready_rebuildable"
    assert third["stability"]["consecutive_observations"] == 3


def test_parent_candidate_is_summary_only_when_child_candidates_exist() -> None:
    parent = contracts.candidate_record(
        _observation(path="/srv/abyss-machine/tmp"),
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )
    child = contracts.candidate_record(
        _observation(path="/srv/abyss-machine/tmp/inactive-child", fingerprint="fp-child"),
        configured_policy=_one_scan_policy(),
        now_time=NOW,
    )

    guarded = contracts.apply_overlap_guards([parent, child])

    assert guarded[0]["verdict"] == "blocked_unknown"
    assert guarded[0]["reclaimable_bytes"] == 0
    assert guarded[1]["verdict"] == "delete_ready_rebuildable"


def test_validate_and_apply_preflight_fail_closed_on_fingerprint_drift() -> None:
    observation = _observation()
    document = contracts.candidates_document(
        [observation],
        previous_document=None,
        configured_policy=_one_scan_policy(),
        schema_prefix="abyss_machine",
        version="test",
        generated_at=NOW.isoformat(),
        paths={},
        deep=True,
    )
    candidate = document["candidates"][0]
    validation = contracts.validate_candidate(
        document,
        observation,
        candidate_id=candidate["candidate_id"],
        configured_policy=_one_scan_policy(),
        generated_at=NOW.isoformat(),
    )
    assert validation["valid"] is True

    changed = copy.deepcopy(observation)
    changed["fingerprint"] = {"digest": "fp-changed", "complete": True}
    preflight = contracts.apply_preflight(candidate, validation, changed)

    assert preflight["ok"] is False
    assert preflight["decision"] == "blocked_fail_closed"
    assert "filesystem_fingerprint_drift" in preflight["reasons"]


def test_expired_claim_does_not_block_but_is_not_permission() -> None:
    claim = contracts.claim_document(
        claim_id="old",
        candidate_id="reclaim-example",
        path=None,
        owner="codex-session",
        session_id="session",
        change_id=None,
        purpose="fixture",
        issued_at="2026-07-01T00:00:00+00:00",
        expires_at="2026-07-02T00:00:00+00:00",
    )

    active = contracts.active_claims(
        [claim],
        candidate_id="reclaim-example",
        path="/srv/abyss-machine/tmp/example",
        now_time=NOW,
    )

    assert active == []
    assert claim["absence_or_expiry_is_not_delete_permission"] is True


def test_operator_approval_and_external_receipt_are_candidate_bound() -> None:
    observation = _observation()
    document = contracts.candidates_document(
        [observation],
        previous_document=None,
        configured_policy=_one_scan_policy(),
        schema_prefix="abyss_machine",
        version="test",
        generated_at=NOW.isoformat(),
        paths={},
        deep=True,
    )
    candidate = document["candidates"][0]
    validation = contracts.validate_candidate(
        document,
        observation,
        candidate_id=candidate["candidate_id"],
        configured_policy=_one_scan_policy(),
        generated_at=NOW.isoformat(),
    )
    approval = contracts.approval_document(
        candidate=candidate,
        validation=validation,
        approved_by="operator",
        approved_at=NOW.isoformat(),
        expires_at=(NOW + dt.timedelta(hours=1)).isoformat(),
    )
    preflight = contracts.operator_apply_preflight(
        candidate=candidate,
        validation=validation,
        approval=approval,
        now_time=NOW + dt.timedelta(minutes=1),
    )
    receipt = contracts.receipt_document(
        candidate_id=candidate["candidate_id"],
        approval=approval,
        action="owner cleanup outside source contract",
        result="applied",
        applied_at=(NOW + dt.timedelta(minutes=5)).isoformat(),
        before_bytes=4096,
        after_bytes=0,
        evidence_refs=["validation/latest.json"],
    )

    assert approval["valid"] is True
    assert approval["does_not_execute_mutation"] is True
    assert preflight["ok"] is True
    assert preflight["executes_mutation"] is False
    assert receipt["valid"] is True
    assert receipt["reclaimed_bytes"] == 4096
    assert receipt["lifecycle_state"] == "receipted"
