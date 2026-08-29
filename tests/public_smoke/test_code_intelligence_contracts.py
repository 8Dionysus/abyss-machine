from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.code_intelligence_contracts import (  # noqa: E402
    CONFIG_SCHEMA,
    MACHINE_CONSUMER_ABI,
    PROVIDER_IDS,
    _owner_admission_receipt_from_verified_gate,
    _stable_digest,
    code_observation_envelope,
    code_intelligence_config,
    provider_admission,
    provider_baseline_document,
    resolve_provider_paths,
    validate_provider_config,
)
from abyss_machine.code_intelligence_adapters import (  # noqa: E402
    collect_code_intelligence_observations,
    collect_owner_admission_receipt,
    collect_provider_observation,
    compare_source_install_projection,
)
from abyss_machine.path_policy import AbyssMachinePathPolicy  # noqa: E402


CONFIG_PATH = ROOT / "config-templates" / "etc" / "abyss-machine" / "code-intelligence.json"
OBSERVED_AT = "2026-08-25T19:00:00Z"


def load_config() -> dict[str, object]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def admitted_ctags_evidence() -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    return {
        "provider_id": "universal-ctags",
        "observed_at": OBSERVED_AT,
        "evidence_ref": "runtime:test/code-intelligence/ctags",
        "owner_boundary": {
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "host_layer_mutates_stack": False,
        },
        "installed": {"executable": "ctags", "version": "fixture", "digest": digest},
        "installation_identity": {
            "provider_id": "universal-ctags",
            "owner": "abyss-machine",
            "version": "fixture",
            "executable_or_path": "ctags",
            "digest": digest,
        },
        "artifact_identity": {
            "provider_id": "universal-ctags",
            "owner": "abyss-machine",
            "class": "runtime_or_container_artifact",
            "subject_digest": digest,
            "source_ref": "source:fixture/code-intelligence/ctags",
        },
        "trust": {
            "provider_id": "universal-ctags",
            "owner": "abyss-machine",
            "verdict": "allow",
            "subject_digest": digest,
            "evidence_ref": "trust:test/code-intelligence/ctags",
        },
        "resource": {
            "provider_id": "universal-ctags",
            "owner": "abyss-machine",
            "kind": "indexing",
            "class": "light",
            "demand_mib": 512,
            "profile_ref": "resource-policy.json#indexing:light",
            "route_ref": "route:abyss-machine/code-intelligence/universal-ctags",
        },
        "live_measurement": {
            "schema": "abyss_machine_code_intelligence_live_measurement_v1",
            "provider_id": "universal-ctags",
            "owner": "abyss-machine",
            "observed_at": OBSERVED_AT,
            "evidence_ref": "measurement:test/code-intelligence/ctags",
            "version": "fixture",
            "health": "healthy",
        },
        "gates": {
            "artifact_identity": {"ok": True},
            "trust_gate": {"ok": True},
            "installed_identity": {"ok": True},
            "runnable_health": {"ok": True},
            "resource_route": {"ok": True},
        },
    }


def synthetic_owner_admission_receipt(
    config: dict[str, object],
    observation: dict[str, object],
) -> object:
    """Build a receipt-shaped unit fixture, without claiming live trust."""

    provider = config["providers"][0]
    assert isinstance(provider, dict)
    controls = ["abi_signature", "sbom", "slsa_in_toto", "sigstore_cosign"]
    subject_digest = "sha256:" + "b" * 64
    record_id = "sha256:" + "c" * 64
    record = {
        "schema": "abyss_machine_artifact_bundle_registry_record_v1",
        "record_id": record_id,
        "artifact_class": "runtime_or_container_artifact",
        "lifecycle_state": "release-ready",
        "latest_eligible": True,
        "terminal_state": False,
        "verification_ok": True,
        "source_repo": "abyss-machine",
        "source_ref": "source:fixture/runtime-bundle",
        "producer": "fixture-only",
        "trust_root_mode": "oci_registry",
        "verifier_versions": {"fixture": "unit-test"},
        "policy_ref": "source:fixture/artifact-policy",
        "bundle_ref": "registry:fixture/runtime-bundle",
        "required_controls": controls,
        "verified_controls": controls,
        "abi_ref": "generated/contract_abi_signatures.min.json",
        "bundle_manifest_ref": "manifests/artifact_bundles/code_intelligence_provider.bundle.json",
        "contract_surface_id": "code-intelligence-provider-route",
        "subject_digest": subject_digest,
    }
    gate = {
        "ok": True,
        "schema": "abyss_machine_artifact_trust_gate_v1",
        "verdict": "allow",
        "artifact_class": "runtime_or_container_artifact",
        "consumer_intent": "runtime",
        "subject_digest": subject_digest,
        "record_id": record_id,
        "latest_record_id": record_id,
        "require_latest": True,
        "registry_dir": "runtime",
        "record": record,
    }
    return _owner_admission_receipt_from_verified_gate(
        provider,
        observation,
        gate,
        record,
        source_config_digest=_stable_digest(config),
        registry_ref="registry:fixture/runtime-bundle",
    )


def test_code_intelligence_source_config_declares_all_required_lanes() -> None:
    config = load_config()
    validation = validate_provider_config(config)

    assert validation["ok"] is True
    assert config["schema"] == CONFIG_SCHEMA
    assert config["observation"] == code_intelligence_config()["observation"]
    assert config["admission"]["consumer_abi"] == MACHINE_CONSUMER_ABI
    assert config["admission"]["owner_admission_boundary"] == code_intelligence_config()["admission"]["owner_admission_boundary"]
    providers = config["providers"]
    assert isinstance(providers, list)
    assert {str(item["id"]) for item in providers if isinstance(item, dict)} == set(PROVIDER_IDS)
    assert config["admission"]["unknown_is"] == "not_admitted"
    assert config["ownership"]["host_layer_mutates_stack"] is False
    by_id = {str(item["id"]): item for item in providers if isinstance(item, dict)}
    assert by_id["tree-sitter"]["installation"]["expected_version"] == "0.26.13"
    assert by_id["scip"]["installation"]["executable"] == "scip-typescript"
    assert by_id["scip"]["installation"]["expected_version"] == "0.4.0"
    assert by_id["lsp"]["installation"]["executable"] == "typescript-language-server"
    assert by_id["lsp"]["installation"]["expected_version"] == "6.0.0"
    assert by_id["semgrep"]["installation"]["expected_version"] == "1.175.0"
    assert by_id["syft"]["installation"]["expected_version"] == "1.45.1"
    assert by_id["in-toto"]["installation"]["expected_version"] == "3.1.0"
    assert by_id["markitdown"]["installation"]["expected_version"] == "0.1.7"
    lock = json.loads((ROOT / "manifests/code_intelligence_node_providers.lock.json").read_text(encoding="utf-8"))
    assert lock["owner"] == "abyss-machine"
    assert {item["provider"] for item in lock["packages"]} == {"tree-sitter", "scip", "lsp"}
    adjacent_lock = json.loads((ROOT / "manifests/code_intelligence_adjacent_providers.lock.json").read_text(encoding="utf-8"))
    assert adjacent_lock["owner"] == "abyss-machine"
    assert {item["provider"] for item in adjacent_lock["packages"]} == {"semgrep", "markitdown"}
    assert {item["provider"] for item in adjacent_lock["shared_machine_routes"]} == {"syft", "in-toto"}


def test_provider_routes_stay_on_machine_roots_and_baseline_is_facts_only(tmp_path: Path) -> None:
    config = load_config()
    policy = AbyssMachinePathPolicy.from_values(
        user="fixture",
        home=tmp_path / "home",
        etc_root=tmp_path / "etc",
        state_root=tmp_path / "state",
        srv_root=tmp_path / "srv",
        run_root=tmp_path / "run",
    )

    routes = resolve_provider_paths(config, "scip", path_policy=policy)
    assert routes["state"].is_relative_to(policy.state_root / "code-intelligence")
    assert routes["runtime"].is_relative_to(policy.runtimes_root / "code-intelligence")
    assert routes["cache"].is_relative_to(policy.cache_root / "code-intelligence")
    assert routes["storage"].is_relative_to(policy.storage_root / "code-intelligence")
    assert routes["tmp"].is_relative_to(policy.tmp_root / "code-intelligence")

    baseline = provider_baseline_document(config, path_policy=policy, generated_at="2026-08-25T19:00:00Z")
    assert baseline["schema"] == "abyss_machine_code_intelligence_provider_baseline_v1"
    assert baseline["summary"] == {
        "provider_count": 9,
        "admitted": 0,
        "not_admitted": 9,
        "all_required_lanes_declared": True,
        "semantic_usefulness_proven": False,
    }
    assert all(item["admission"]["status"] == "not_admitted" for item in baseline["providers"])
    assert all(item["semantic"]["status"] == "unproven" for item in baseline["providers"])


def test_admission_requires_owner_receipt_before_any_live_gate_can_verify() -> None:
    config = load_config()
    unknown = provider_admission(config, "universal-ctags")
    assert unknown["decision"] == "deny"
    assert unknown["status"] == "not_admitted"
    assert unknown["blocking_reasons"] == ["owner_admission_receipt_missing"]
    assert unknown["admission_source"] == "caller_observation_only"
    assert unknown["semantic_usefulness"] == "unproven"

    incomplete = provider_admission(
        config,
        "universal-ctags",
        {
            "gates": {
                "artifact_identity": {"ok": True},
                "trust_gate": {"ok": True},
                "installed_identity": {"ok": True},
                "runnable_health": {"ok": True},
                "resource_route": {"ok": True},
            }
        },
    )
    assert incomplete["decision"] == "deny"
    assert incomplete["blocking_reasons"] == ["owner_admission_receipt_missing"]
    assert incomplete["gates"]["installed_identity"]["state"] == "unknown"

    failed = provider_admission(
        config,
        "universal-ctags",
        {
            "observed_at": "2026-08-25T19:00:00Z",
            "evidence_ref": "runtime:test/code-intelligence/ctags",
            "gates": {
                "artifact_identity": {"ok": True},
                "trust_gate": {"ok": False},
                "installed_identity": {"ok": True},
                "runnable_health": {"ok": True},
                "resource_route": {"ok": True},
            },
        },
    )
    assert failed["decision"] == "deny"
    assert failed["gates"]["trust_gate"]["state"] == "unknown"
    assert failed["blocking_reasons"] == ["owner_admission_receipt_missing"]


def test_caller_facts_cannot_mint_admission_but_an_owner_receipt_can_bind_it() -> None:
    config = load_config()
    evidence = admitted_ctags_evidence()
    denied = provider_admission(config, "universal-ctags", evidence)
    assert denied["decision"] == "deny"
    assert denied["blocking_reasons"] == ["owner_admission_receipt_missing"]

    forged_receipt = dict(synthetic_owner_admission_receipt(config, evidence))
    forged = provider_admission(
        config,
        "universal-ctags",
        evidence,
        admission_receipt=forged_receipt,
    )
    assert forged["decision"] == "deny"
    assert "owner_admission_receipt_not_owner_produced" in forged["blocking_reasons"]

    admitted = provider_admission(
        config,
        "universal-ctags",
        evidence,
        admission_receipt=synthetic_owner_admission_receipt(config, evidence),
    )
    assert admitted["decision"] == "admit"
    assert admitted["status"] == "admitted"
    assert admitted["admission_source"] == "owner_produced_content_addressed_receipt"
    assert admitted["observed_identity"]["version"] == "fixture"
    assert admitted["identity_checks"]["artifact"]["subject_digest"] == "sha256:" + "b" * 64
    assert admitted["identity_checks"]["trust"]["verdict"] == "allow"
    assert admitted["identity_checks"]["resource"]["profile_ref"] == "resource-policy.json#indexing:light"
    assert admitted["identity_checks"]["live_measurement"]["health"] == "healthy"
    assert admitted["semantic_usefulness"] == "unproven"
    assert admitted["admission_is_not_semantic_proof"] is True


def test_admission_rejects_green_gates_without_identity_or_valid_time_and_reference() -> None:
    config = load_config()
    evidence = {
        "observed_at": "not-a-time",
        "evidence_ref": "anything",
        "gates": {
            "artifact_identity": {"ok": True},
            "trust_gate": {"ok": True},
            "installed_identity": {"ok": True},
            "runnable_health": {"ok": True},
            "resource_route": {"ok": True},
        },
    }
    denied = provider_admission(config, "universal-ctags", evidence)

    assert denied["decision"] == "deny"
    assert denied["status"] == "not_admitted"
    assert denied["blocking_reasons"] == ["owner_admission_receipt_missing"]
    assert all(
        record["state"] in {"unknown", "not_required"}
        for name, record in denied["gates"].items()
        if name != "source_config"
    )


def test_config_validator_rejects_provider_prefix_collision_and_unconstrained_installation() -> None:
    config = load_config()
    assert isinstance(config["providers"], list)

    near_match = copy.deepcopy(config)
    assert isinstance(near_match["providers"][2], dict)
    near_match["providers"][2]["paths"]["storage"] = "providers/scip-evil/shared"
    near_match_result = validate_provider_config(near_match)
    assert near_match_result["ok"] is False
    assert any(error["key"] == "providers.scip.paths.storage" for error in near_match_result["errors"])

    unconstrained = copy.deepcopy(config)
    assert isinstance(unconstrained["providers"][0], dict)
    unconstrained["providers"][0]["installation"] = {"garbage": True}
    unconstrained_result = validate_provider_config(unconstrained)
    assert unconstrained_result["ok"] is False
    assert any("installation field is not part of the source contract" in error["message"] for error in unconstrained_result["errors"])


def test_caller_supplied_trust_install_and_resource_claims_stay_observation_only() -> None:
    config = load_config()
    evidence = admitted_ctags_evidence()
    assert isinstance(evidence["trust"], dict)
    evidence["trust"]["subject_digest"] = "sha256:different-trusted-subject"
    denied_trust = provider_admission(config, "universal-ctags", evidence)
    assert denied_trust["decision"] == "deny"
    assert denied_trust["blocking_reasons"] == ["owner_admission_receipt_missing"]

    evidence = admitted_ctags_evidence()
    assert isinstance(evidence["installed"], dict)
    evidence["installed"]["digest"] = "sha256:different-installed-subject"
    denied_installed = provider_admission(config, "universal-ctags", evidence)
    assert denied_installed["decision"] == "deny"
    assert denied_installed["blocking_reasons"] == ["owner_admission_receipt_missing"]

    evidence = admitted_ctags_evidence()
    assert isinstance(evidence["resource"], dict)
    evidence["resource"]["profile_ref"] = "resource-policy.json#indexing:heavy"
    denied_resource = provider_admission(config, "universal-ctags", evidence)
    assert denied_resource["decision"] == "deny"
    assert denied_resource["blocking_reasons"] == ["owner_admission_receipt_missing"]


def test_bootstrap_dry_run_projects_code_intelligence_config_without_mutating_hosts() -> None:
    bootstrap = ROOT / "scripts" / "abyss-machine-bootstrap"
    result = subprocess.run(
        [sys.executable, str(bootstrap), "render", "--dry-run", "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert any(
        isinstance(action, dict)
        and str(action.get("source", "")).endswith("config-templates/etc/abyss-machine/code-intelligence.json")
        and str(action.get("target", "")).endswith("etc/abyss-machine/code-intelligence.json")
        for action in payload["actions"]
    )


def test_config_validator_rejects_duplicate_or_unsafe_provider_routes() -> None:
    config = load_config()
    duplicate = copy.deepcopy(config)
    assert isinstance(duplicate["providers"], list)
    duplicate["providers"].append(copy.deepcopy(duplicate["providers"][0]))
    assert validate_provider_config(duplicate)["ok"] is False

    unsafe = copy.deepcopy(config)
    assert isinstance(unsafe["providers"], list)
    assert isinstance(unsafe["providers"][0], dict)
    unsafe["providers"][0]["paths"]["cache"] = "../outside"
    assert validate_provider_config(unsafe)["ok"] is False


def test_observation_envelope_binds_source_epoch_and_provenance_without_proof_claim() -> None:
    envelope = code_observation_envelope(
        "scip",
        [{"kind": "symbol", "id": "fixture:main"}],
        source_ref="repo:fixture/source.py",
        source_epoch="sha256:" + "b" * 64,
        config_digest="sha256:" + "c" * 64,
        generated_at="2026-08-25T19:00:00Z",
        provenance_ref="runtime:test/code-intelligence/scip",
    )

    assert envelope["source"]["binding_status"] == "bound"
    assert envelope["provenance"]["binding_status"] == "bound"
    assert envelope["lineage"]["observation_consumer"] == "aoa-kag"
    assert envelope["semantic"]["status"] == "unproven"
    assert envelope["semantic"]["admission_is_not_semantic_proof"] is True

    unbound = code_observation_envelope(
        "scip",
        [],
        source_ref="anything",
        source_epoch="not-a-digest",
        config_digest="not-a-digest",
        generated_at="not-a-time",
        provenance_ref="anything",
    )
    assert unbound["source"]["binding_status"] == "unbound"
    assert unbound["provenance"]["binding_status"] == "unbound"


def test_read_only_provider_adapter_collects_identity_but_cannot_self_supply_trust(tmp_path: Path) -> None:
    config = load_config()
    executable = tmp_path / "ctags"
    executable.write_bytes(b"fixture ctags executable\n")
    executable.chmod(0o755)
    calls: list[tuple[list[str], float]] = []

    def resolve(name: str) -> str | None:
        assert name == "ctags"
        return str(executable)

    def run(command: list[str], timeout: float) -> dict[str, object]:
        calls.append((command, timeout))
        return {
            "returncode": 0,
            "stdout": "Universal Ctags 6.1\nprivate-raw-output-must-not-escape",
            "stderr": "",
        }

    observation = collect_provider_observation(
        config,
        "universal-ctags",
        observed_at=OBSERVED_AT,
        executable_resolver=resolve,
        command_runner=run,
        memory_probe=lambda: {"status": "observed", "available_mib": 4096, "total_mib": 8192},
    )

    assert calls == [([str(executable), "--version"], 5.0)]
    assert observation["installed"]["version"] == "Universal Ctags 6.1"
    assert observation["live_measurement"]["health"] == "healthy"
    assert observation["probe"]["raw_output"] == "discarded"
    assert "private-raw-output-must-not-escape" not in json.dumps(observation, sort_keys=True)
    assert observation["admission"]["decision"] == "deny"
    assert observation["admission"]["blocking_reasons"] == ["owner_admission_receipt_missing"]
    assert observation["admission"]["admission_source"] == "caller_observation_only"
    assert observation["policy"]["trust_granted"] is False


def test_owner_admission_route_fails_closed_when_registry_has_no_record(tmp_path: Path) -> None:
    config = load_config()
    result = collect_owner_admission_receipt(
        config,
        "universal-ctags",
        admitted_ctags_evidence(),
        registry_dir=tmp_path,
        subject_digest="sha256:" + "b" * 64,
    )

    assert result["status"] == "not_admitted"
    assert result["receipt"] is None
    assert result["gate"]["verdict"] == "unknown"
    assert "no_registry_record" in result["blocking_reasons"]


def test_read_only_provider_adapter_keeps_missing_executable_unknown() -> None:
    config = load_config()
    called = False

    def run(command: Sequence[str], timeout: float) -> dict[str, object]:
        nonlocal called
        called = True
        return {"returncode": 0, "stdout": "should-not-run", "stderr": ""}

    observation = collect_provider_observation(
        config,
        "scip",
        observed_at=OBSERVED_AT,
        executable_resolver=lambda name: None,
        command_runner=run,
        memory_probe=lambda: {"status": "unknown"},
    )

    assert called is False
    assert observation["probe"]["status"] == "executable_not_found"
    assert observation["gates"]["installed_identity"]["ok"] is None
    assert observation["gates"]["runnable_health"]["ok"] is None
    assert observation["admission"]["decision"] == "deny"
    assert observation["admission"]["gates"]["installed_identity"]["state"] == "unknown"


def test_source_install_projection_is_bounded_and_never_synchronizes(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    installed = tmp_path / "installed.json"
    source.write_text('{"version":1}\n', encoding="utf-8")
    installed.write_text('{"version":1}\n', encoding="utf-8")

    current = compare_source_install_projection(source, installed)
    assert current["status"] == "current"
    assert current["current"] is True
    assert current["mutation_performed"] is False
    assert current["synchronization_performed"] is False

    installed.write_text('{"version":2}\n', encoding="utf-8")
    drifted = compare_source_install_projection(source, installed)
    assert drifted["status"] == "drifted"
    assert drifted["current"] is False
    assert drifted["source"]["sha256"] != drifted["installed"]["sha256"]

    installed.unlink()
    missing = compare_source_install_projection(source, installed)
    assert missing["status"] == "installed_missing"
    assert missing["current"] is None


def test_whole_read_only_collection_is_sequential_and_keeps_lsp_and_trust_separate(tmp_path: Path) -> None:
    config = load_config()
    binaries: dict[str, Path] = {}
    for executable_name in (
        "ctags",
        "tree-sitter",
        "scip-typescript",
        "typescript-language-server",
        "python3",
        "semgrep",
        "syft",
        "in-toto-verify",
        "markitdown",
    ):
        binary = tmp_path / executable_name
        binary.write_bytes(executable_name.encode("utf-8"))
        binary.chmod(0o755)
        binaries[executable_name] = binary
    calls: list[str] = []
    memory_calls = 0

    def resolve(name: str) -> str | None:
        return str(binaries[name]) if name in binaries else None

    def run(command: Sequence[str], timeout: float) -> dict[str, object]:
        calls.append(str(command[0]))
        if Path(command[0]).name == "syft":
            return {"returncode": 0, "stdout": '{"version":"1.45.1"}\n', "stderr": ""}
        return {
            "returncode": 0,
            "stdout": f"{Path(command[0]).name} fixture 1.0\nsecret-output",
            "stderr": "",
        }

    def memory() -> dict[str, object]:
        nonlocal memory_calls
        memory_calls += 1
        return {"status": "observed", "available_mib": 4096, "total_mib": 8192}

    source = tmp_path / "source-config.json"
    installed = tmp_path / "installed-config.json"
    source.write_text("same projection\n", encoding="utf-8")
    installed.write_text("same projection\n", encoding="utf-8")
    collection = collect_code_intelligence_observations(
        config,
        observed_at=OBSERVED_AT,
        source_epoch="sha256:" + "e" * 64,
        source_config_path=source,
        installed_config_path=installed,
        executable_resolver=resolve,
        command_runner=run,
        memory_probe=memory,
    )

    assert calls == [
        str(binaries["ctags"]),
        str(binaries["tree-sitter"]),
        str(binaries["scip-typescript"]),
        str(binaries["typescript-language-server"]),
        str(binaries["python3"]),
        str(binaries["semgrep"]),
        str(binaries["syft"]),
        str(binaries["in-toto-verify"]),
        str(binaries["markitdown"]),
    ]
    assert memory_calls == 1
    assert collection["summary"]["provider_count"] == 9
    assert collection["summary"]["healthy_version_probes"] == 9
    assert collection["summary"]["admitted_by_machine_contract"] == 0
    assert collection["source_install_projection"]["status"] == "current"
    assert collection["source"]["source_epoch_binding_status"] == "bound"
    assert collection["providers"]["lsp"]["probe"]["status"] == "healthy"
    assert collection["providers"]["syft"]["installed"]["version"] == "1.45.1"
    assert collection["providers"]["lsp"]["admission"]["decision"] == "deny"
    assert "secret-output" not in json.dumps(collection, sort_keys=True)

    invalid_epoch = collect_code_intelligence_observations(
        config,
        observed_at=OBSERVED_AT,
        source_epoch="not-a-digest",
        executable_resolver=lambda name: None,
        memory_probe=memory,
    )
    assert invalid_epoch["source"]["source_epoch_binding_status"] == "invalid"


def test_caller_supplied_provider_owner_and_resource_identity_stay_untrusted() -> None:
    config = load_config()

    forged_provider = admitted_ctags_evidence()
    forged_provider["provider_id"] = "scip"
    denied_provider = provider_admission(config, "universal-ctags", forged_provider)
    assert denied_provider["decision"] == "deny"
    assert denied_provider["blocking_reasons"] == ["owner_admission_receipt_missing"]

    forged_owner = admitted_ctags_evidence()
    assert isinstance(forged_owner["owner_boundary"], dict)
    forged_owner["owner_boundary"]["host_owner"] = "untrusted-owner"
    denied_owner = provider_admission(config, "universal-ctags", forged_owner)
    assert denied_owner["decision"] == "deny"
    assert denied_owner["blocking_reasons"] == ["owner_admission_receipt_missing"]

    forged_route = admitted_ctags_evidence()
    assert isinstance(forged_route["resource"], dict)
    forged_route["resource"]["route_ref"] = "route:other-owner/code-intelligence/universal-ctags"
    denied_route = provider_admission(config, "universal-ctags", forged_route)
    assert denied_route["decision"] == "deny"
    assert denied_route["blocking_reasons"] == ["owner_admission_receipt_missing"]


def test_admission_requires_owner_receipt_before_canonical_identity_is_usable() -> None:
    config = load_config()

    missing_identity = admitted_ctags_evidence()
    del missing_identity["installation_identity"]
    denied_identity = provider_admission(config, "universal-ctags", missing_identity)
    assert denied_identity["decision"] == "deny"
    assert denied_identity["blocking_reasons"] == ["owner_admission_receipt_missing"]

    conflicting_artifact = admitted_ctags_evidence()
    conflicting_artifact["artifact"] = copy.deepcopy(conflicting_artifact["artifact_identity"])
    assert isinstance(conflicting_artifact["artifact"], dict)
    conflicting_artifact["artifact"]["subject_digest"] = "sha256:" + "d" * 64
    denied_conflict = provider_admission(config, "universal-ctags", conflicting_artifact)
    assert denied_conflict["decision"] == "deny"
    assert denied_conflict["blocking_reasons"] == ["owner_admission_receipt_missing"]

    invalid_digest = admitted_ctags_evidence()
    assert isinstance(invalid_digest["installation_identity"], dict)
    assert isinstance(invalid_digest["installed"], dict)
    assert isinstance(invalid_digest["artifact_identity"], dict)
    assert isinstance(invalid_digest["trust"], dict)
    invalid_digest["installation_identity"]["digest"] = "sha256:fixture"
    invalid_digest["installed"]["digest"] = "sha256:fixture"
    invalid_digest["artifact_identity"]["subject_digest"] = "sha256:fixture"
    invalid_digest["trust"]["subject_digest"] = "sha256:fixture"
    denied_digest = provider_admission(config, "universal-ctags", invalid_digest)
    assert denied_digest["decision"] == "deny"
    assert denied_digest["blocking_reasons"] == ["owner_admission_receipt_missing"]
