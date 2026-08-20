from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker
import pytest


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.active_organ_contracts import (  # noqa: E402
    ActiveOrganHostContractError,
    admit_canary_workload,
    admit_shadow_workload,
    build_host_capability_snapshot_reference,
    build_host_resource_storage_plan_reference,
    validate_host_capability_snapshot_reference,
    validate_host_resource_storage_plan_reference,
)


EXAMPLES_PATH = (
    ROOT
    / "mechanics"
    / "host-facts"
    / "examples"
    / "active_organ_host_contracts_v1.examples.json"
)
SCHEMA_BY_CONTRACT = {
    "C18": ROOT
    / "schemas"
    / "active-organ-host-capability-snapshot-reference.schema.json",
    "C19": ROOT
    / "schemas"
    / "active-organ-host-resource-storage-plan-reference.schema.json",
}
ER6_SCHEMA = (
    ROOT
    / "schemas"
    / "active-organ-host-erasure-owner-extension-v0.schema.json"
)
SEMANTIC_VALIDATOR = {
    "C18": validate_host_capability_snapshot_reference,
    "C19": validate_host_resource_storage_plan_reference,
}
BUILDER = {
    "C18": build_host_capability_snapshot_reference,
    "C19": build_host_resource_storage_plan_reference,
}


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def apply_mutation(payload: dict, mutation: dict) -> None:
    tokens = mutation["path"].lstrip("/").split("/")
    target = payload
    for token in tokens[:-1]:
        target = target[int(token)] if isinstance(target, list) else target[token]
    leaf = tokens[-1]
    if mutation["op"] == "remove":
        target.pop(int(leaf)) if isinstance(target, list) else target.pop(leaf)
    elif isinstance(target, list):
        target[int(leaf)] = mutation["value"]
    else:
        target[leaf] = mutation["value"]


def test_active_organ_host_contracts_validate_positive_and_negative_corpus() -> None:
    suite = load_json(EXAMPLES_PATH)
    valid_by_id = {case["case_id"]: case for case in suite["valid_cases"]}
    validators = {}
    for contract_id, path in SCHEMA_BY_CONTRACT.items():
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        validators[contract_id] = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    for case in suite["valid_cases"]:
        payload = case["payload"]
        contract_id = case["contract_id"]
        schema_errors = list(validators[contract_id].iter_errors(payload))
        semantic_issues = SEMANTIC_VALIDATOR[contract_id](payload)
        assert schema_errors == [], (case["case_id"], schema_errors)
        assert semantic_issues == [], (case["case_id"], semantic_issues)
        assert BUILDER[contract_id](**payload) == payload

    for case in suite["invalid_cases"]:
        base = valid_by_id[case["base_case"]]
        payload = deepcopy(base["payload"])
        apply_mutation(payload, case["mutation"])
        contract_id = base["contract_id"]
        schema_errors = list(validators[contract_id].iter_errors(payload))
        semantic_issues = SEMANTIC_VALIDATOR[contract_id](payload)
        if case["expected_failure"] == "schema":
            assert schema_errors, case["case_id"]
        else:
            assert any(
                case["expected_failure"] in issue for issue in semantic_issues
            ), (case["case_id"], semantic_issues)


def test_builders_fail_closed_on_semantic_authority_widening() -> None:
    suite = load_json(EXAMPLES_PATH)
    c18 = deepcopy(suite["valid_cases"][0]["payload"])
    c19 = deepcopy(suite["valid_cases"][1]["payload"])

    c18["capability_refs"][0]["artifact"]["owner_repo"] = "abyss-stack"
    with pytest.raises(
        ActiveOrganHostContractError,
        match="artifact must be owned by abyss-machine",
    ):
        build_host_capability_snapshot_reference(**c18)

    c19["resource_plan_decision"] = "deny"
    with pytest.raises(
        ActiveOrganHostContractError,
        match="resource-plan deny must remain host disposition deny",
    ):
        build_host_resource_storage_plan_reference(**c19)

    c18_incomplete = deepcopy(suite["valid_cases"][0]["payload"])
    c18_incomplete.pop("reference_id")
    with pytest.raises(
        ActiveOrganHostContractError,
        match="missing required top-level fields: reference_id",
    ):
        build_host_capability_snapshot_reference(**c18_incomplete)

    c19_unknown = deepcopy(suite["valid_cases"][1]["payload"])
    c19_unknown["memory_launch_override"] = True
    with pytest.raises(
        ActiveOrganHostContractError,
        match="unknown top-level fields: memory_launch_override",
    ):
        build_host_resource_storage_plan_reference(**c19_unknown)


def test_c19_is_reference_only_and_cannot_mutate_project_or_stack_roots() -> None:
    schema = load_json(SCHEMA_BY_CONTRACT["C19"])
    properties = schema["properties"]

    assert properties["launch_executed"]["const"] is False
    assert properties["machine_owned_roots_only"]["const"] is True
    assert properties["project_root_mutation"]["const"] == "forbidden"
    assert properties["stack_root_mutation"]["const"] == "forbidden"
    assert properties["memory_semantic_authority"]["const"] == "none"
    assert properties["effect_authority"]["const"] == "host_admission_only"


def test_phase11_er6_extension_is_host_bounded_and_content_minimized() -> None:
    schema = load_json(ER6_SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    payload = {
        "schema_version": "active_organ_owner_erasure_extension_v0",
        "extension_id": "erase-extension:phase11:ER6",
        "parent_owner": "abyss-machine",
        "worker_owner": "abyss-machine",
        "surface_id": "ER6",
        "work_item_ref": "erase-work:phase11:ER6",
        "material_classes": ["host_local_surface"],
        "target_ref_digests": ["sha256:" + ("1" * 64)],
        "operation_evidence_refs": ["operation:phase11:ER6"],
        "recovery_probe_ref": "probe:phase11:ER6",
        "result": "erased",
        "residue_refs": [],
        "retention_exceptions": [],
        "target_root_class": "srv_abyss_machine",
        "host_path_disclosed": False,
        "physical_evidence_ref": "host-evidence:phase11:ER6",
        "rebuild_recovery_checked": True,
        "project_root_mutation": "forbidden",
        "stack_root_mutation": "forbidden",
        "subject_material_included": False,
        "content_minimized": True,
        "execution_posture": "reference_lab_only",
        "live_execution": False,
        "effect_authority": "owner_local_erasure_only",
        "global_completion_authority": False,
        "content_digest": "sha256:" + ("2" * 64),
    }
    assert list(validator.iter_errors(payload)) == []

    leaked = deepcopy(payload)
    leaked["host_path_disclosed"] = True
    assert list(validator.iter_errors(leaked))

    project = deepcopy(payload)
    project["project_root_mutation"] = "allowed"
    assert list(validator.iter_errors(project))

    live = deepcopy(payload)
    live["live_execution"] = True
    assert list(validator.iter_errors(live))


def test_shadow_admission_is_pure_and_retains_exact_host_disposition() -> None:
    suite = load_json(EXAMPLES_PATH)
    c18 = deepcopy(suite["valid_cases"][0]["payload"])
    c19 = deepcopy(suite["valid_cases"][1]["payload"])

    admission = admit_shadow_workload(
        c18,
        c19,
        workload_id="active-organ-lab:run-a",
        consumer_id="abyss-stack",
        admitted_at=datetime.fromisoformat("2026-07-28T19:31:00-06:00"),
    )

    assert admission["host_disposition"] == "start"
    assert admission["launch_executed"] is False
    assert admission["project_root_mutation"] == "forbidden"
    assert admission["stack_root_mutation"] == "forbidden"
    assert admission["memory_semantic_authority"] == "none"
    assert admission["effect_authority"] == "host_admission_only"
    assert admission["capability_snapshot_digest"] == c18["content_digest"]
    assert admission["resource_plan_digest"] == c19["content_digest"]
    assert admission["admission_digest"].startswith("sha256:")


def test_shadow_admission_denies_stale_evidence_and_unlisted_consumer() -> None:
    suite = load_json(EXAMPLES_PATH)
    c18 = deepcopy(suite["valid_cases"][0]["payload"])
    c19 = deepcopy(suite["valid_cases"][1]["payload"])

    admission = admit_shadow_workload(
        c18,
        c19,
        workload_id="active-organ-lab:run-a",
        consumer_id="unknown-consumer",
        admitted_at=datetime.fromisoformat("2026-07-28T19:40:00-06:00"),
    )

    assert admission["host_disposition"] == "deny"
    assert admission["softening_constraints"] == []
    assert admission["reason_codes"] == [
        "stale-host-evidence",
        "consumer-not-admitted-by-c18",
    ]


def test_shadow_admission_preserves_softening_and_rejects_workload_drift() -> None:
    suite = load_json(EXAMPLES_PATH)
    c18 = deepcopy(suite["valid_cases"][0]["payload"])
    c19 = deepcopy(suite["valid_cases"][1]["payload"])
    c19["host_disposition"] = "soften"
    c19["softening_constraints"] = ["reduce-item-budget"]

    admission = admit_shadow_workload(
        c18,
        c19,
        workload_id="active-organ-lab:run-a",
        consumer_id="abyss-stack",
        admitted_at=datetime.fromisoformat("2026-07-28T19:31:00-06:00"),
    )
    assert admission["host_disposition"] == "soften"
    assert admission["softening_constraints"] == ["reduce-item-budget"]

    with pytest.raises(
        ActiveOrganHostContractError,
        match="workload_id must match",
    ):
        admit_shadow_workload(
            c18,
            c19,
            workload_id="active-organ-lab:other",
            consumer_id="abyss-stack",
            admitted_at=datetime.fromisoformat("2026-07-28T19:31:00-06:00"),
        )


def test_canary_admission_preserves_host_only_authority() -> None:
    suite = load_json(EXAMPLES_PATH)
    c18 = deepcopy(suite["valid_cases"][0]["payload"])
    c19 = deepcopy(suite["valid_cases"][1]["payload"])

    admission = admit_canary_workload(
        c18,
        c19,
        workload_id="active-organ-lab:run-a",
        runtime_consumer_id="abyss-stack",
        memory_consumer_id="codex_owner_orientation_canary_v0",
        admitted_at=datetime.fromisoformat("2026-07-28T19:31:00-06:00"),
    )
    payload = {
        key: value
        for key, value in admission.items()
        if key != "admission_digest"
    }
    expected_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    assert admission["schema_version"] == (
        "abyss_machine_canary_workload_admission_v0"
    )
    assert admission["consumer_id"] == "abyss-stack"
    assert admission["memory_consumer_id"] == (
        "codex_owner_orientation_canary_v0"
    )
    assert admission["delivery_semantic_authority"] == "none"
    assert admission["canary_effect_authority"] == "none"
    assert admission["launch_executed"] is False
    assert admission["admission_digest"] == expected_digest

    with pytest.raises(
        ActiveOrganHostContractError,
        match="limited to the exact memory consumer",
    ):
        admit_canary_workload(
            c18,
            c19,
            workload_id="active-organ-lab:run-a",
            runtime_consumer_id="abyss-stack",
            memory_consumer_id="another-consumer",
            admitted_at=datetime.fromisoformat("2026-07-28T19:31:00-06:00"),
        )
