"""Source contracts for the machine side of code-intelligence providers.

This module deliberately stops at the host boundary.  It declares provider
lanes, resolves their machine-owned storage/resource routes, and evaluates
caller-supplied host observations with a fail-closed admission rule.  It does
not install tools, start services, parse repositories, materialize KAG data,
or turn admission into semantic proof.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .path_policy import AbyssMachinePathPolicy, DEFAULT_PATH_POLICY
from .resource_planning import RESOURCE_CLASSES, RESOURCE_KINDS


CONFIG_SCHEMA = "abyss_machine_code_intelligence_config_v1"
BASELINE_SCHEMA = "abyss_machine_code_intelligence_provider_baseline_v1"
OBSERVATION_SCHEMA = "abyss_machine_code_observation_envelope_v1"
MEASUREMENT_SCHEMA = "abyss_machine_code_intelligence_live_measurement_v1"
ADMISSION_RECEIPT_SCHEMA = "abyss_machine_code_intelligence_admission_receipt_v1"
VERSION = "0.1.0"
_MACHINE_OWNER = "abyss-machine"
_CONSUMER_OWNER = "abyss-stack"
_ARTIFACT_REGISTRY_BOUNDARY = "artifact_registry_trust_gate"
_RUNTIME_ARTIFACT_CLASS = "runtime_or_container_artifact"
_RUNTIME_ARTIFACT_CONTRACT_SURFACE_ID = "code-intelligence-provider-route"
_RUNTIME_ARTIFACT_REQUIRED_CONTROLS = (
    "abi_signature",
    "sbom",
    "slsa_in_toto",
    "sigstore_cosign",
)
_RUNTIME_ARTIFACT_ABI_REF = "generated/contract_abi_signatures.min.json"
_RUNTIME_ARTIFACT_MANIFEST_REF = "manifests/artifact_bundles/code_intelligence_provider.bundle.json"
_OWNER_ADMISSION_RECEIPT_MARKER = object()

# This is the exact consumer ABI accepted by the later abyss-stack LIVE
# direction. The machine source declares the names and trust-anchor posture
# here, but it does not copy or mint the stack-owned evidence bundle.
MACHINE_CONSUMER_ABI = {
    "owner": "abyss-stack",
    "binding_schema": "abyss-machine-code-intelligence-provider-binding-v1",
    "evidence_schema": "abyss-stack-machine-code-intelligence-evidence-v1",
    "gate_schema": "abyss-stack-machine-code-intelligence-gate-v1",
    "gate_record_schema": "abyss-machine-admission-gate-v1",
    "signed_payload_schema": "abyss-machine-admission-gate-signed-payload-v1",
    "public_key_schema": "abyss-machine-code-intelligence-gate-public-key-v1",
    "algorithm": "ed25519",
    "verification_method": "ed25519-owner-signature-v1",
    "trust_anchor_ref": "/etc/abyss-machine/trust/code-intelligence-gate-ed25519.json",
    "trust_anchor_posture": "existing_root_owned_anchor_only",
    "provider_neutral": True,
    "state_axes": ["candidate", "current", "last_good"],
    "required_separations": [
        "machine artifact trust vs machine evidence gate",
        "installation and admission vs deployed runtime lifecycle",
        "runtime observation vs normalized observation meaning",
        "runtime evidence vs semantic proof and eval verdict",
    ],
}
PROVIDER_IDS = (
    "universal-ctags",
    "tree-sitter",
    "scip",
    "lsp",
    "python-ast-bootstrap",
)
_LIVE_GATES = (
    "artifact_identity",
    "trust_gate",
    "installed_identity",
    "runnable_health",
    "resource_route",
)
_ROUTE_ROOTS = {
    "state": "state_root",
    "runtime": "runtime_root",
    "cache": "cache_root",
    "storage": "storage_root",
    "tmp": "tmp_root",
}
_ROOT_PLACEHOLDERS = {
    "state_root": "{{ABYSS_MACHINE_STATE}}/code-intelligence",
    "runtime_root": "{{ABYSS_MACHINE_SRV}}/runtimes/code-intelligence",
    "cache_root": "{{ABYSS_MACHINE_SRV}}/cache/code-intelligence",
    "storage_root": "{{ABYSS_MACHINE_SRV}}/storage/code-intelligence",
    "tmp_root": "{{ABYSS_MACHINE_SRV}}/tmp/code-intelligence",
}
_EVIDENCE_REF_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*:[^\s]+$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_TRUST_VERDICTS = {"allow", "allowed", "admit", "admitted", "pass", "passed", "verified"}
_HEALTH_STATES = {"healthy", "ready", "runnable", "ok", "pass", "passed"}
_INSTALLATION_FIELDS = {
    "executable",
    "version_command",
    "version_command_shape",
    "expected_version",
    "version_source",
}
_OBSERVATION_TIMEOUT_MAX_SECONDS = 60.0
_OBSERVATION_OUTPUT_MAX_BYTES = 1024 * 1024
_OBSERVATION_DIGEST_MAX_BYTES = 512 * 1024 * 1024
_OBSERVATION_FIELDS = {
    "mode",
    "version_probe_timeout_seconds",
    "max_version_output_bytes",
    "max_file_digest_bytes",
    "host_memory_source",
    "network_downloads",
    "service_mutation",
    "trust_grant",
    "raw_command_output",
}


class _OwnerAdmissionReceipt(Mapping[str, Any]):
    """Opaque receipt issued by the machine-owned registry/trust boundary.

    A plain caller mapping is deliberately not interchangeable with this
    value. The only source-side issuer is the owner adapter that has already
    inspected the durable artifact registry and trust-gate result. The
    payload remains content-addressed so consumers can bind the exact record,
    gate snapshot, and host observation used for the decision.
    """

    __slots__ = ("_payload", "_marker")

    def __init__(self, payload: Mapping[str, Any], marker: object) -> None:
        if marker is not _OWNER_ADMISSION_RECEIPT_MARKER:
            raise TypeError("owner admission receipts are issued by the owner boundary")
        self._payload = _copy(payload)
        self._marker = marker

    def __getitem__(self, key: str) -> Any:
        return _copy(self._payload[key])

    def __iter__(self):
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)


_RUNTIME_ARTIFACT_ROUTE = {
    "artifact_class": _RUNTIME_ARTIFACT_CLASS,
    "contract_surface_id": _RUNTIME_ARTIFACT_CONTRACT_SURFACE_ID,
    "abi_ref": _RUNTIME_ARTIFACT_ABI_REF,
    "bundle_manifest_ref": _RUNTIME_ARTIFACT_MANIFEST_REF,
    "required_controls": list(_RUNTIME_ARTIFACT_REQUIRED_CONTROLS),
    "sidecars": {
        "abi_signature": ["artifact.abi.json"],
        "sbom": ["artifact.sbom.cdx.json", "artifact.sbom.spdx.json"],
        "slsa_in_toto": ["artifact.provenance.intoto.jsonl", "artifact.provenance.json"],
        "sigstore_cosign": ["artifact.sigstore.json", "artifact.cosign.signature", "artifact.cosign.pub"],
    },
    "registry": {
        "layout": "abyss_machine_artifact_bundle_registry_v1",
        "index_ref": "index.json",
        "record_ref": "records/<sha256>.json",
        "record_schema": "abyss_machine_artifact_bundle_registry_record_v1",
    },
    "trust_gate": {
        "schema": "abyss_machine_artifact_trust_gate_v1",
        "consumer_intent": "runtime",
        "expected_source_repo": _MACHINE_OWNER,
        "expected_trust_root_mode": "oci_registry",
        "require_latest": True,
        "required_verdict": "allow",
        "command": (
            "abyss-machine artifacts trust-gate --registry-dir REGISTRY_DIR "
            "--artifact-class runtime_or_container_artifact --consumer-intent runtime "
            "--source-repo abyss-machine --trust-root-mode oci_registry "
            "--subject-digest SUBJECT_DIGEST --json"
        ),
    },
}


def _copy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy(item) for item in value]
    if isinstance(value, tuple):
        return [_copy(item) for item in value]
    return value


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _content_addressed_digest(value: Mapping[str, Any]) -> str:
    """Digest a receipt body without allowing the digest to sign itself."""

    body = {str(key): _copy(item) for key, item in value.items() if str(key) != "receipt_digest"}
    return _stable_digest(body)


def _valid_durable_ref(value: Any) -> bool:
    text = _text(value)
    if not text or re.search(r"(^|[/=:])(tmp|run|scratch)(?:[/]|$)", text):
        return False
    if _valid_evidence_ref(text) or text.startswith(("state:", "host:", "registry:")):
        return True
    # The artifact-bundles owner may return a durable host path when a real
    # registry is inspected. Keep that path bounded to declared artifact
    # roots; arbitrary caller paths cannot become receipt references.
    return text.startswith(("/var/lib/abyss-machine/artifacts/", "/srv/abyss-machine/artifacts/"))


def _observation_identity_claims(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Select host facts that an owner receipt may bind without trusting gates."""

    return {
        "provider_id": _copy(observation.get("provider_id")),
        "observed_at": _copy(observation.get("observed_at")),
        "evidence_ref": _copy(observation.get("evidence_ref")),
        "owner_boundary": _copy(observation.get("owner_boundary")),
        "installed": _copy(observation.get("installed")),
        "installation_identity": _copy(observation.get("installation_identity")),
        "resource": _copy(observation.get("resource")),
        "live_measurement": _copy(observation.get("live_measurement")),
    }


def _observation_identity_digest(observation: Mapping[str, Any]) -> str:
    return _stable_digest(_observation_identity_claims(observation))


def _observation_measurement_digest(observation: Mapping[str, Any]) -> str:
    return _stable_digest(
        {
            "provider_id": _copy(observation.get("provider_id")),
            "observed_at": _copy(observation.get("observed_at")),
            "evidence_ref": _copy(observation.get("evidence_ref")),
            "resource": _copy(observation.get("resource")),
            "live_measurement": _copy(observation.get("live_measurement")),
        }
    )


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _valid_observed_at(value: Any) -> bool:
    """Accept only timezone-aware ISO-8601 timestamps for live evidence."""

    text = _text(value)
    if not text:
        return False
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _valid_evidence_ref(value: Any) -> bool:
    """Require a qualified, non-whitespace evidence reference."""

    text = value if isinstance(value, str) else ""
    return bool(text and text == text.strip() and _EVIDENCE_REF_PATTERN.fullmatch(text))


def _valid_digest(value: Any) -> bool:
    return bool(isinstance(value, str) and _DIGEST_PATTERN.fullmatch(value.strip()))


def _safe_token(value: Any) -> bool:
    text = value if isinstance(value, str) else ""
    return bool(text and text == text.strip() and not any(character.isspace() for character in text))


def _safe_identity_token(value: Any) -> bool:
    text = value if isinstance(value, str) else ""
    return bool(text and text == text.strip() and "\x00" not in text and not any(character.isspace() for character in text))


def _expected_resource_route(provider: Mapping[str, Any]) -> str:
    return f"route:{_MACHINE_OWNER}/code-intelligence/{_text(provider.get('id'))}"


def _provider_owner(provider: Mapping[str, Any]) -> str:
    return _text(provider.get("host_owner")) or _MACHINE_OWNER


def _observation_evidence_conflicts(
    observation: Mapping[str, Any],
    name: str,
    *aliases: str,
) -> list[str]:
    """Find fields that disagree across equivalent evidence locations."""

    mappings: list[Mapping[str, Any]] = []
    for key in (*aliases, name):
        value = observation.get(key)
        if isinstance(value, Mapping):
            mappings.append(value)
    gates = observation.get("gates")
    if isinstance(gates, Mapping) and isinstance(gates.get(name), Mapping):
        mappings.append(gates[name])
    values: dict[str, list[Any]] = {}
    for mapping in mappings:
        for key, value in mapping.items():
            values.setdefault(str(key), []).append(value)
    conflicts: list[str] = []
    for key, candidates in values.items():
        meaningful = [item for item in candidates if item is not None and item != ""]
        if len(meaningful) > 1 and any(item != meaningful[0] for item in meaningful[1:]):
            conflicts.append(key)
    return sorted(conflicts)


def _merge_mappings(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        if isinstance(value, Mapping):
            merged.update({str(key): item for key, item in value.items()})
    return merged


def _provider_path(provider_id: str) -> dict[str, str]:
    relative = f"providers/{provider_id}"
    return {
        "state": relative,
        "runtime": relative,
        "cache": relative,
        "storage": relative,
        "tmp": relative,
    }


def _provider_declarations() -> list[dict[str, Any]]:
    return [
        {
            "id": "universal-ctags",
            "display_name": "Universal Ctags",
            "role": "broad_navigation_fallback",
            "mode": "indexed",
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "declared_capabilities": ["definitions", "symbols", "fallback_navigation"],
            "artifact": {
                "required": True,
                "class": "runtime_or_container_artifact",
                "source_ref_required": True,
                "subject_digest_required": True,
                "trust_gate_required": True,
            },
            "installation": {
                "executable": "ctags",
                "version_command": ["ctags", "--version"],
                "expected_version": None,
                "version_source": "release_or_operator_manifest",
            },
            "resource": {
                "kind": "indexing",
                "class": "light",
                "startup_demand_mib": 512,
                "max_parallelism": 1,
                "profile_ref": "resource-policy.json#indexing:light",
            },
            "paths": _provider_path("universal-ctags"),
            "semantic": {
                "status": "unproven",
                "proof_owner": "aoa-evals",
                "requires_symbol_smoke": True,
            },
            "diagnostics": {
                "version_probe": ["ctags", "--version"],
                "health_probe": "bounded_version_and_symbol_probe",
            },
        },
        {
            "id": "tree-sitter",
            "display_name": "Tree-sitter",
            "role": "incremental_syntax_and_structural_diff",
            "mode": "indexed",
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "declared_capabilities": ["syntax", "structural_diff", "incremental_parse"],
            "artifact": {
                "required": True,
                "class": "runtime_or_container_artifact",
                "source_ref_required": True,
                "subject_digest_required": True,
                "trust_gate_required": True,
            },
            "installation": {
                "executable": "tree-sitter",
                "version_command": ["tree-sitter", "--version"],
                "expected_version": "0.26.13",
                "version_source": "manifests/code_intelligence_node_providers.lock.json",
            },
            "resource": {
                "kind": "indexing",
                "class": "medium",
                "startup_demand_mib": 1536,
                "max_parallelism": 1,
                "profile_ref": "resource-policy.json#indexing:medium",
            },
            "paths": _provider_path("tree-sitter"),
            "semantic": {
                "status": "unproven",
                "proof_owner": "aoa-evals",
                "requires_structural_delta_smoke": True,
            },
            "diagnostics": {
                "version_probe": ["tree-sitter", "--version"],
                "health_probe": "bounded_parse_and_structural_delta_probe",
            },
        },
        {
            "id": "scip",
            "display_name": "SCIP",
            "role": "cross_file_semantic_symbols_and_relations",
            "mode": "indexed",
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "declared_capabilities": ["semantic_symbols", "occurrences", "relations"],
            "artifact": {
                "required": True,
                "class": "runtime_or_container_artifact",
                "source_ref_required": True,
                "subject_digest_required": True,
                "trust_gate_required": True,
            },
            "installation": {
                "executable": "scip-typescript",
                "version_command": ["scip-typescript", "--version"],
                "expected_version": "0.4.0",
                "version_source": "manifests/code_intelligence_node_providers.lock.json",
            },
            "resource": {
                "kind": "indexing",
                "class": "heavy",
                "startup_demand_mib": 4096,
                "max_parallelism": 1,
                "profile_ref": "resource-policy.json#indexing:heavy",
            },
            "paths": _provider_path("scip"),
            "semantic": {
                "status": "unproven",
                "proof_owner": "aoa-evals",
                "requires_cross_file_relation_smoke": True,
            },
            "diagnostics": {
                "version_probe": ["scip", "--version"],
                "health_probe": "bounded_index_and_cross_file_relation_probe",
            },
        },
        {
            "id": "lsp",
            "display_name": "Language Server Protocol",
            "role": "live_working_tree_observation",
            "mode": "live",
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "declared_capabilities": ["live_definitions", "live_references", "diagnostics", "workspace_symbols"],
            "artifact": {
                "required": True,
                "class": "runtime_or_container_artifact",
                "source_ref_required": True,
                "subject_digest_required": True,
                "trust_gate_required": True,
            },
            "installation": {
                "executable": "typescript-language-server",
                "version_command": ["typescript-language-server", "--version"],
                "version_command_shape": ["<language-server>", "--version"],
                "expected_version": "6.0.0",
                "version_source": "manifests/code_intelligence_node_providers.lock.json",
            },
            "resource": {
                "kind": "indexing",
                "class": "medium",
                "startup_demand_mib": 2048,
                "max_parallelism": 1,
                "profile_ref": "resource-policy.json#indexing:medium",
            },
            "paths": _provider_path("lsp"),
            "semantic": {
                "status": "unproven",
                "proof_owner": "aoa-evals",
                "requires_initialize_definition_reference_smoke": True,
            },
            "diagnostics": {
                "version_probe": "language_server_specific",
                "health_probe": "stack_owned_initialize_and_shutdown_probe",
            },
        },
        {
            "id": "python-ast-bootstrap",
            "display_name": "Python AST bootstrap",
            "role": "portable_bootstrap_extractor",
            "mode": "bootstrap",
            "host_owner": "abyss-machine",
            "consumer_owner": "abyss-stack",
            "declared_capabilities": ["ast_bootstrap", "definitions", "imports"],
            "artifact": {
                "required": False,
                "class": "host_interpreter",
                "source_ref_required": True,
                "subject_digest_required": False,
                "trust_gate_required": False,
            },
            "installation": {
                "executable": "python3",
                "version_command": ["python3", "--version"],
                "expected_version": None,
                "version_source": "host_interpreter_or_consumer_manifest",
            },
            "resource": {
                "kind": "indexing",
                "class": "light",
                "startup_demand_mib": 512,
                "max_parallelism": 1,
                "profile_ref": "resource-policy.json#indexing:light",
            },
            "paths": _provider_path("python-ast-bootstrap"),
            "semantic": {
                "status": "unproven",
                "proof_owner": "aoa-evals",
                "requires_ast_symbol_and_import_smoke": True,
            },
            "diagnostics": {
                "version_probe": ["python3", "--version"],
                "health_probe": "bounded_ast_parse_probe",
            },
        },
    ]


def code_intelligence_config() -> dict[str, Any]:
    """Return the public source declaration for the machine provider plane."""

    return {
        "schema": CONFIG_SCHEMA,
        "version": VERSION,
        "kind": "code-intelligence-provider-plane",
        "source": {
            "owner": "abyss-machine",
            "authority": "source-config",
            "config_ref": "config-templates/etc/abyss-machine/code-intelligence.json",
            "source_epoch_binding": "consumer_binds_observations_to_source_epoch",
        },
        "paths": _copy(_ROOT_PLACEHOLDERS),
        "providers": _provider_declarations(),
        "admission": {
            "required_gates": [
                "source_config",
                "owner_admission_receipt",
                "installed_identity",
                "runnable_health",
                "resource_route",
            ],
            "artifact_gates_when_required": ["artifact_identity", "trust_gate"],
            "requires_owner_produced_receipt": True,
            "requires_content_addressed_receipt": True,
            "admission_receipt_schema": ADMISSION_RECEIPT_SCHEMA,
            "owner_admission_boundary": _copy(_RUNTIME_ARTIFACT_ROUTE),
            "consumer_abi": _copy(MACHINE_CONSUMER_ABI),
            "unknown_is": "not_admitted",
            "success_requires_observed_at": True,
            "success_requires_evidence_ref": True,
            "requires_installation_identity": True,
            "requires_provider_identity": True,
            "requires_owner_boundary": True,
            "requires_canonical_installation_identity": True,
            "requires_resource_envelope": True,
            "requires_live_measurement": True,
            "observed_at_format": "timezone_aware_iso8601",
            "evidence_ref_format": "qualified_scheme_reference",
            "installation_identity_fields": ["version", "executable_or_path", "digest_when_artifact_required"],
            "provider_identity_fields": ["provider_id", "owner_boundary"],
            "owner_boundary_fields": ["host_owner", "consumer_owner", "host_layer_mutates_stack"],
            "artifact_identity_fields": ["class", "subject_digest", "source_ref"],
            "trust_identity_fields": ["verdict", "subject_digest", "evidence_ref", "provider_id", "owner"],
            "resource_envelope_fields": ["kind", "class", "demand_mib", "profile_ref", "route_ref", "provider_id", "owner"],
            "live_measurement_fields": ["observed_at", "evidence_ref", "version", "health"],
            "resource_route_format": "route:abyss-machine/code-intelligence/<provider_id>",
            "live_measurement_schema": MEASUREMENT_SCHEMA,
            "semantic_usefulness": "unproven_until_owner_proof",
        },
        "observation": {
            "mode": "bounded_read_only",
            "version_probe_timeout_seconds": 5.0,
            "max_version_output_bytes": 4096,
            "max_file_digest_bytes": 128 * 1024 * 1024,
            "host_memory_source": "sysconf_read_only",
            "network_downloads": False,
            "service_mutation": False,
            "trust_grant": False,
            "raw_command_output": "discarded",
        },
        "storage": {
            "large_data_route": "paths.storage_root",
            "runtime_route": "paths.runtime_root",
            "cache_route": "paths.cache_root",
            "durable_fact_route": "paths.state_root",
            "temporary_route": "paths.tmp_root",
            "protected_project_roots": True,
        },
        "ownership": {
            "host_install_and_trust_owner": "abyss-machine",
            "provider_lifecycle_owner": "abyss-stack",
            "live_lsp_session_owner": "abyss-stack",
            "normalized_observation_consumer": "aoa-kag",
            "semantic_proof_owner": "aoa-evals",
            "host_layer_mutates_stack": False,
        },
        "diagnostics": {
            "probe_mode": "bounded_read_only",
            "version_and_health_probes_are_facts_only": True,
            "network_downloads": False,
            "service_mutation": False,
            "raw_command_output_persisted": False,
        },
        "rollback": {
            "strategy": "last_good_admitted_provider",
            "automatic": False,
            "requires_prior_admission_receipt": True,
            "state_route": "state/providers/rollback",
        },
        "non_claims": [
            "Source declaration does not prove installation, current version, trust, or runnable health.",
            "Host admission does not prove semantic usefulness, proof, or owner acceptance.",
            "The machine layer does not own provider lifecycle, LSP sessions, or KAG materialization.",
            "The G58 consumer ABI requires an authenticated machine evidence gate; artifact trust alone is not that gate.",
            "The machine source does not create, replace, or infer the root-owned G58 trust anchor.",
        ],
    }


def default_provider_catalog(*, path_policy: AbyssMachinePathPolicy | None = None) -> dict[str, Any]:
    """Return the source catalog with target-machine roots resolved."""

    config = code_intelligence_config()
    policy = path_policy or DEFAULT_PATH_POLICY
    validation = validate_provider_config(config, path_policy=policy)
    return {
        "schema": "abyss_machine_code_intelligence_provider_catalog_v1",
        "version": VERSION,
        "source": _copy(config["source"]),
        "config_digest": _stable_digest(config),
        "validation": validation,
        "paths": _resolved_roots(policy),
        "providers": [
            {
                "id": provider["id"],
                "display_name": provider["display_name"],
                "role": provider["role"],
                "mode": provider["mode"],
                "declared_capabilities": list(provider["declared_capabilities"]),
                "paths": {key: str(value) for key, value in resolve_provider_paths(config, provider["id"], path_policy=policy).items()},
                "resource": _copy(provider["resource"]),
                "installation": _copy(provider["installation"]),
                "artifact": _copy(provider["artifact"]),
            }
            for provider in config["providers"]
        ],
        "policy": _copy(config["admission"]),
        "observation": _copy(config["observation"]),
        "non_claims": list(config["non_claims"]),
    }


def provider_catalog(*, path_policy: AbyssMachinePathPolicy | None = None) -> dict[str, Any]:
    """Compatibility spelling for callers that ask for the source catalog."""

    return default_provider_catalog(path_policy=path_policy)


def _resolved_roots(path_policy: AbyssMachinePathPolicy) -> dict[str, str]:
    return {
        "config_root": str(path_policy.etc_root),
        "state_root": str(path_policy.state_root / "code-intelligence"),
        "runtime_root": str(path_policy.runtimes_root / "code-intelligence"),
        "cache_root": str(path_policy.cache_root / "code-intelligence"),
        "storage_root": str(path_policy.storage_root / "code-intelligence"),
        "tmp_root": str(path_policy.tmp_root / "code-intelligence"),
    }


def _validate_installation_declaration(
    provider_id: str,
    installation: Any,
) -> list[dict[str, str]]:
    """Validate the finite installation contract, including its command shape."""

    failures: list[dict[str, str]] = []
    key_prefix = f"providers.{provider_id}.installation"
    if not isinstance(installation, Mapping):
        return [{"key": key_prefix, "message": "installation declaration is required"}]

    unknown = sorted(str(key) for key in installation if str(key) not in _INSTALLATION_FIELDS)
    for key in unknown:
        failures.append({"key": f"{key_prefix}.{key}", "message": "installation field is not part of the source contract"})

    executable = installation.get("executable")
    if executable is not None and not _safe_token(executable):
        failures.append({"key": f"{key_prefix}.executable", "message": "executable must be a non-empty token"})
    if executable is None and provider_id != "lsp":
        failures.append({"key": f"{key_prefix}.executable", "message": "an executable is required for this provider"})

    version_command = installation.get("version_command")
    if version_command is not None:
        if not isinstance(version_command, list) or not version_command or not all(_safe_token(item) for item in version_command):
            failures.append({"key": f"{key_prefix}.version_command", "message": "version_command must be a non-empty token list"})
        elif executable is not None and Path(str(version_command[0])).name != str(executable):
            failures.append({"key": f"{key_prefix}.version_command", "message": "version probe must start with the declared executable"})
    elif executable is not None:
        failures.append({"key": f"{key_prefix}.version_command", "message": "version_command is required when executable is declared"})

    version_shape = installation.get("version_command_shape")
    if version_shape is not None and (
        not isinstance(version_shape, list) or not version_shape or not all(_safe_token(item) for item in version_shape)
    ):
        failures.append({"key": f"{key_prefix}.version_command_shape", "message": "version_command_shape must be a non-empty token list"})
    if executable is None and version_shape is None:
        failures.append({"key": f"{key_prefix}.version_command_shape", "message": "a command shape is required for provider-selected executables"})

    expected_version = installation.get("expected_version")
    if expected_version is not None and not _safe_token(expected_version):
        failures.append({"key": f"{key_prefix}.expected_version", "message": "expected_version must be a non-empty token when present"})
    version_source = installation.get("version_source")
    if not _safe_token(version_source):
        failures.append({"key": f"{key_prefix}.version_source", "message": "version_source is required"})
    return failures


def _is_safe_relative(value: Any) -> bool:
    text = value if isinstance(value, str) else ""
    if not text or text != text.strip() or "\\" in text or "\x00" in text or "//" in text:
        return False
    path = PurePosixPath(text)
    return not path.is_absolute() and ".." not in path.parts and text != "."


def _path_matches(value: Any, placeholder: str, resolved: Path) -> bool:
    text = _text(value)
    return text == str(resolved) or text == placeholder


def _validate_owner_admission_declaration(admission: Mapping[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for field in ("requires_owner_produced_receipt", "requires_content_addressed_receipt"):
        if admission.get(field) is not True:
            failures.append({"key": f"admission.{field}", "message": "must be true"})
    if admission.get("admission_receipt_schema") != ADMISSION_RECEIPT_SCHEMA:
        failures.append({"key": "admission.admission_receipt_schema", "message": f"must be {ADMISSION_RECEIPT_SCHEMA}"})
    boundary = admission.get("owner_admission_boundary")
    if not isinstance(boundary, Mapping):
        failures.append({"key": "admission.owner_admission_boundary", "message": "owner-produced boundary declaration is required"})
    elif dict(boundary) != _RUNTIME_ARTIFACT_ROUTE:
        failures.append({
            "key": "admission.owner_admission_boundary",
            "message": "boundary must remain the exact runtime artifact registry/trust-gate route",
        })
    return failures


def validate_provider_config(
    config: Mapping[str, Any],
    *,
    path_policy: AbyssMachinePathPolicy | None = None,
) -> dict[str, Any]:
    """Validate the public provider declaration without reading host state."""

    failures: list[dict[str, str]] = []
    if not isinstance(config, Mapping):
        return {"ok": False, "schema": CONFIG_SCHEMA, "errors": [{"key": "config", "message": "config must be an object"}]}

    if config.get("schema") != CONFIG_SCHEMA:
        failures.append({"key": "schema", "message": f"schema must be {CONFIG_SCHEMA}"})
    if not _text(config.get("version")):
        failures.append({"key": "version", "message": "version is required"})
    source = config.get("source")
    if not isinstance(source, Mapping):
        failures.append({"key": "source", "message": "source owner declaration is required"})
    else:
        if source.get("owner") != _MACHINE_OWNER:
            failures.append({"key": "source.owner", "message": "source owner must be abyss-machine"})
        if source.get("authority") != "source-config":
            failures.append({"key": "source.authority", "message": "source authority must remain source-config"})
    ownership = config.get("ownership")
    if not isinstance(ownership, Mapping):
        failures.append({"key": "ownership", "message": "owner boundary declaration is required"})
    else:
        expected_ownership = {
            "host_install_and_trust_owner": _MACHINE_OWNER,
            "provider_lifecycle_owner": _CONSUMER_OWNER,
            "live_lsp_session_owner": _CONSUMER_OWNER,
            "normalized_observation_consumer": "aoa-kag",
            "semantic_proof_owner": "aoa-evals",
        }
        for key, expected in expected_ownership.items():
            if ownership.get(key) != expected:
                failures.append({"key": f"ownership.{key}", "message": f"owner must remain {expected}"})
        if ownership.get("host_layer_mutates_stack") is not False:
            failures.append({"key": "ownership.host_layer_mutates_stack", "message": "host layer must not mutate abyss-stack"})
    paths = config.get("paths")
    if not isinstance(paths, Mapping):
        failures.append({"key": "paths", "message": "paths must be an object"})
        paths = {}
    policy = path_policy or DEFAULT_PATH_POLICY
    resolved = _resolved_roots(policy)
    path_expectations = {
        "state_root": (_ROOT_PLACEHOLDERS["state_root"], Path(resolved["state_root"])),
        "runtime_root": (_ROOT_PLACEHOLDERS["runtime_root"], Path(resolved["runtime_root"])),
        "cache_root": (_ROOT_PLACEHOLDERS["cache_root"], Path(resolved["cache_root"])),
        "storage_root": (_ROOT_PLACEHOLDERS["storage_root"], Path(resolved["storage_root"])),
        "tmp_root": (_ROOT_PLACEHOLDERS["tmp_root"], Path(resolved["tmp_root"])),
    }
    for key, (placeholder, target) in path_expectations.items():
        if not _path_matches(paths.get(key), placeholder, target):
            failures.append({"key": f"paths.{key}", "message": "route must remain on its declared machine root"})

    admission = config.get("admission")
    if not isinstance(admission, Mapping):
        failures.append({"key": "admission", "message": "admission policy is required"})
    else:
        required_gates = admission.get("required_gates")
        if not isinstance(required_gates, list) or not required_gates or not all(_text(item) for item in required_gates):
            failures.append({"key": "admission.required_gates", "message": "required gate names are required"})
        artifact_gates = admission.get("artifact_gates_when_required")
        if not isinstance(artifact_gates, list) or not artifact_gates or not all(_text(item) for item in artifact_gates):
            failures.append({"key": "admission.artifact_gates_when_required", "message": "artifact gate names are required"})
        if admission.get("unknown_is") != "not_admitted":
            failures.append({"key": "admission.unknown_is", "message": "unknown evidence must remain not_admitted"})
        for field in (
            "success_requires_observed_at",
            "success_requires_evidence_ref",
            "requires_installation_identity",
            "requires_provider_identity",
            "requires_owner_boundary",
            "requires_canonical_installation_identity",
            "requires_resource_envelope",
            "requires_live_measurement",
        ):
            if not isinstance(admission.get(field), bool):
                failures.append({"key": f"admission.{field}", "message": "must be boolean"})
        failures.extend(_validate_owner_admission_declaration(admission))

    observation_policy = config.get("observation")
    if not isinstance(observation_policy, Mapping):
        failures.append({"key": "observation", "message": "bounded read-only observation policy is required"})
    else:
        for key in observation_policy:
            if str(key) not in _OBSERVATION_FIELDS:
                failures.append({"key": f"observation.{key}", "message": "observation field is not part of the source contract"})
        if observation_policy.get("mode") != "bounded_read_only":
            failures.append({"key": "observation.mode", "message": "observation mode must be bounded_read_only"})
        timeout = observation_policy.get("version_probe_timeout_seconds")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)) or timeout <= 0 or timeout > _OBSERVATION_TIMEOUT_MAX_SECONDS:
            failures.append({"key": "observation.version_probe_timeout_seconds", "message": "timeout must be finite, positive, and at most 60 seconds"})
        output_limit = observation_policy.get("max_version_output_bytes")
        if isinstance(output_limit, bool) or not isinstance(output_limit, int) or output_limit <= 0 or output_limit > _OBSERVATION_OUTPUT_MAX_BYTES:
            failures.append({"key": "observation.max_version_output_bytes", "message": "output bound must be a positive integer no larger than 1 MiB"})
        digest_limit = observation_policy.get("max_file_digest_bytes")
        if isinstance(digest_limit, bool) or not isinstance(digest_limit, int) or digest_limit <= 0 or digest_limit > _OBSERVATION_DIGEST_MAX_BYTES:
            failures.append({"key": "observation.max_file_digest_bytes", "message": "digest bound must be a positive integer no larger than 512 MiB"})
        if observation_policy.get("host_memory_source") != "sysconf_read_only":
            failures.append({"key": "observation.host_memory_source", "message": "host memory must use the read-only sysconf source"})
        if observation_policy.get("network_downloads") is not False:
            failures.append({"key": "observation.network_downloads", "message": "observation cannot download over the network"})
        if observation_policy.get("service_mutation") is not False:
            failures.append({"key": "observation.service_mutation", "message": "observation cannot mutate services"})
        if observation_policy.get("trust_grant") is not False:
            failures.append({"key": "observation.trust_grant", "message": "observation cannot grant trust"})
        if observation_policy.get("raw_command_output") != "discarded":
            failures.append({"key": "observation.raw_command_output", "message": "raw command output must be discarded"})

    providers = config.get("providers")
    if not isinstance(providers, list) or not providers:
        failures.append({"key": "providers", "message": "providers must be a non-empty list"})
        providers = []
    seen: set[str] = set()
    provider_ids: set[str] = set()
    for provider in providers:
        if not isinstance(provider, Mapping):
            failures.append({"key": "providers", "message": "each provider must be an object"})
            continue
        provider_id = _text(provider.get("id"))
        provider_ids.add(provider_id)
        if not provider_id:
            failures.append({"key": "providers.id", "message": "provider id is required"})
            continue
        if provider_id not in PROVIDER_IDS:
            failures.append({"key": f"providers.{provider_id}", "message": "provider id is not declared by the machine contract"})
        if provider_id in seen:
            failures.append({"key": f"providers.{provider_id}", "message": "provider id is duplicated"})
        seen.add(provider_id)
        artifact = provider.get("artifact")
        resource = provider.get("resource")
        provider_paths = provider.get("paths")
        capabilities = provider.get("declared_capabilities")
        if not _text(provider.get("role")) or not _text(provider.get("mode")):
            failures.append({"key": f"providers.{provider_id}", "message": "role and mode are required"})
        if provider.get("host_owner") != _MACHINE_OWNER:
            failures.append({"key": f"providers.{provider_id}.host_owner", "message": "host owner must be abyss-machine"})
        if provider.get("consumer_owner") != _CONSUMER_OWNER:
            failures.append({"key": f"providers.{provider_id}.consumer_owner", "message": "consumer owner must be abyss-stack"})
        if not isinstance(capabilities, list) or not capabilities or not all(_text(item) for item in capabilities):
            failures.append({"key": f"providers.{provider_id}.declared_capabilities", "message": "at least one capability is required"})
        if not isinstance(artifact, Mapping):
            failures.append({"key": f"providers.{provider_id}.artifact", "message": "artifact declaration is required"})
        else:
            for field in ("required", "source_ref_required", "subject_digest_required", "trust_gate_required"):
                if not isinstance(artifact.get(field), bool):
                    failures.append({"key": f"providers.{provider_id}.artifact.{field}", "message": "must be boolean"})
            if not _safe_token(artifact.get("class")):
                failures.append({"key": f"providers.{provider_id}.artifact.class", "message": "artifact class is required"})
        failures.extend(_validate_installation_declaration(provider_id, provider.get("installation")))
        if not isinstance(resource, Mapping):
            failures.append({"key": f"providers.{provider_id}.resource", "message": "resource declaration is required"})
        else:
            if resource.get("kind") not in RESOURCE_KINDS:
                failures.append({"key": f"providers.{provider_id}.resource.kind", "message": "kind is not in the machine resource policy"})
            if resource.get("class") not in RESOURCE_CLASSES:
                failures.append({"key": f"providers.{provider_id}.resource.class", "message": "class is not in the machine resource policy"})
            if not isinstance(resource.get("startup_demand_mib"), int) or resource.get("startup_demand_mib", 0) <= 0:
                failures.append({"key": f"providers.{provider_id}.resource.startup_demand_mib", "message": "positive startup demand is required"})
            if not isinstance(resource.get("max_parallelism"), int) or resource.get("max_parallelism", 0) <= 0:
                failures.append({"key": f"providers.{provider_id}.resource.max_parallelism", "message": "positive max parallelism is required"})
            if not _safe_token(resource.get("profile_ref")):
                failures.append({"key": f"providers.{provider_id}.resource.profile_ref", "message": "resource profile reference is required"})
        if not isinstance(provider_paths, Mapping):
            failures.append({"key": f"providers.{provider_id}.paths", "message": "provider routes are required"})
        else:
            for route in _ROUTE_ROOTS:
                value = provider_paths.get(route)
                route_parts = PurePosixPath(value).parts if _is_safe_relative(value) else ()
                if not route_parts or len(route_parts) < 2 or route_parts[:2] != ("providers", provider_id):
                    failures.append({"key": f"providers.{provider_id}.paths.{route}", "message": "route must be a safe provider-relative path"})

    missing = sorted(set(PROVIDER_IDS) - provider_ids)
    for provider_id in missing:
        failures.append({"key": "providers", "message": f"required provider lane is missing: {provider_id}"})

    return {
        "ok": not failures,
        "schema": CONFIG_SCHEMA,
        "provider_count": len(providers),
        "errors": failures,
    }


def validate_config(
    config: Mapping[str, Any],
    *,
    path_policy: AbyssMachinePathPolicy | None = None,
) -> dict[str, Any]:
    """Compatibility spelling for the source-config validator."""

    return validate_provider_config(config, path_policy=path_policy)


def _provider_for_id(config: Mapping[str, Any], provider_id: str) -> Mapping[str, Any] | None:
    providers = config.get("providers")
    if not isinstance(providers, list):
        return None
    for provider in providers:
        if isinstance(provider, Mapping) and provider.get("id") == provider_id:
            return provider
    return None


def resolve_provider_paths(
    config: Mapping[str, Any],
    provider_id: str,
    *,
    path_policy: AbyssMachinePathPolicy | None = None,
) -> dict[str, Path]:
    """Resolve provider-relative routes onto the machine-owned roots."""

    validation = validate_provider_config(config, path_policy=path_policy)
    if not validation["ok"]:
        raise ValueError("cannot resolve invalid code-intelligence config")
    provider = _provider_for_id(config, provider_id)
    if provider is None:
        raise KeyError(provider_id)
    routes = provider["paths"]
    policy = path_policy or DEFAULT_PATH_POLICY
    bases = {
        "state": policy.state_root / "code-intelligence",
        "runtime": policy.runtimes_root / "code-intelligence",
        "cache": policy.cache_root / "code-intelligence",
        "storage": policy.storage_root / "code-intelligence",
        "tmp": policy.tmp_root / "code-intelligence",
    }
    resolved: dict[str, Path] = {}
    for route, root_key in _ROUTE_ROOTS.items():
        relative = PurePosixPath(str(routes[route]))
        resolved[route] = bases[route] / Path(*relative.parts)
    return resolved


def _gate_entry(observation: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    gates = observation.get("gates")
    entry: Any = gates.get(name) if isinstance(gates, Mapping) else None
    if not isinstance(entry, Mapping):
        entry = observation.get(name)
    return entry if isinstance(entry, Mapping) else None


def _observation_evidence_mapping(
    observation: Mapping[str, Any],
    name: str,
    *aliases: str,
) -> dict[str, Any]:
    """Collect one evidence object from top-level and gate-compatible forms."""

    result: dict[str, Any] = {}
    for key in (*aliases, name):
        value = observation.get(key)
        if isinstance(value, Mapping):
            result.update({str(item_key): item_value for item_key, item_value in value.items()})
    entry = _gate_entry(observation, name)
    if entry is not None:
        result.update({str(item_key): item_value for item_key, item_value in entry.items()})
    return result


def _gate_input(observation: Mapping[str, Any], name: str) -> tuple[Any, str, str]:
    entry = _gate_entry(observation, name)
    observed_at = _text(observation.get("observed_at"))
    evidence_ref = _text(observation.get("evidence_ref"))
    if entry is not None:
        value = entry.get("ok", entry.get("value"))
        observed_at = _text(entry.get("observed_at")) or observed_at
        evidence_ref = _text(entry.get("evidence_ref")) or evidence_ref
    else:
        value = entry
    return value, observed_at, evidence_ref


def _live_gate_record(
    name: str,
    value: Any,
    observed_at: str,
    evidence_ref: str,
) -> dict[str, Any]:
    if not isinstance(value, bool):
        state = "unknown"
        reason = f"{name}_unknown"
        ok: bool | None = None
    elif not value:
        state = "failed"
        reason = f"{name}_failed"
        ok = False
    elif not observed_at:
        state = "unknown"
        reason = f"{name}_missing_observed_at"
        ok = None
    elif not _valid_observed_at(observed_at):
        state = "unknown"
        reason = f"{name}_invalid_observed_at"
        ok = None
    elif not evidence_ref:
        state = "unknown"
        reason = f"{name}_missing_evidence_ref"
        ok = None
    elif not _valid_evidence_ref(evidence_ref):
        state = "unknown"
        reason = f"{name}_invalid_evidence_ref"
        ok = None
    else:
        state = "verified"
        reason = None
        ok = True
    record: dict[str, Any] = {
        "required": True,
        "state": state,
        "ok": ok,
        "observed_at": observed_at or None,
        "evidence_ref": evidence_ref or None,
    }
    if reason:
        record["blocking_reason"] = reason
    return record


def _not_required_gate() -> dict[str, Any]:
    return {
        "required": False,
        "state": "not_required",
        "ok": True,
        "observed_at": None,
        "evidence_ref": None,
    }


def _owner_receipt_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, _OwnerAdmissionReceipt):
        return None
    if value._marker is not _OWNER_ADMISSION_RECEIPT_MARKER:
        return None
    return value._payload


def _untrusted_observation_gate(
    name: str,
    observation: Mapping[str, Any],
    *,
    reason: str = "owner_admission_receipt_missing",
) -> dict[str, Any]:
    """Keep caller observations visible without treating them as admission."""

    _, observed_at, evidence_ref = _gate_input(observation, name)
    return {
        "required": True,
        "state": "unknown",
        "ok": None,
        "observed_at": observed_at or None,
        "evidence_ref": evidence_ref or None,
        "authority": "caller_observation_only",
        "blocking_reason": reason,
    }


def _safe_identity(observation: Mapping[str, Any]) -> dict[str, Any]:
    installed = observation.get("installation_identity")
    if not isinstance(installed, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in ("provider_id", "owner", "version", "digest", "executable_or_path"):
        value = installed.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            result[key] = value
    return result


def _validate_observation_binding(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> list[str]:
    """Bind caller facts to the authored provider and owner boundary."""

    failures: list[str] = []
    provider_id = _text(provider.get("id"))
    if provider_id not in PROVIDER_IDS:
        failures.append("provider_identity_unknown")
    if _text(provider.get("host_owner")) != _MACHINE_OWNER:
        failures.append("provider_host_owner_invalid")
    if _text(provider.get("consumer_owner")) != _CONSUMER_OWNER:
        failures.append("provider_consumer_owner_invalid")

    observed_provider_id = _text(observation.get("provider_id"))
    if not observed_provider_id:
        failures.append("provider_identity_missing")
    elif observed_provider_id != provider_id:
        failures.append("provider_identity_mismatch")

    boundary = observation.get("owner_boundary")
    if not isinstance(boundary, Mapping):
        failures.append("owner_boundary_missing")
    else:
        if boundary.get("host_owner") != _MACHINE_OWNER or boundary.get("host_owner") != _text(provider.get("host_owner")):
            failures.append("owner_boundary_host_owner_mismatch")
        if boundary.get("consumer_owner") != _CONSUMER_OWNER or boundary.get("consumer_owner") != _text(provider.get("consumer_owner")):
            failures.append("owner_boundary_consumer_owner_mismatch")
        if boundary.get("host_layer_mutates_stack") is not False:
            failures.append("owner_boundary_mutation_not_false")

    top_observed_at = _text(observation.get("observed_at"))
    if not _valid_observed_at(top_observed_at):
        failures.append("observation_invalid_observed_at")
    gates = observation.get("gates")
    if isinstance(gates, Mapping):
        for gate_name, gate in gates.items():
            if not isinstance(gate, Mapping):
                continue
            gate_observed_at = _text(gate.get("observed_at"))
            if gate_observed_at and top_observed_at and gate_observed_at != top_observed_at:
                failures.append(f"{gate_name}_observed_at_mismatch")
    return failures


def _validate_nested_identity(
    provider: Mapping[str, Any],
    name: str,
    evidence: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    conflicts = _observation_evidence_conflicts(
        {name: evidence},
        name,
    )
    if conflicts:
        failures.append(f"{name}_conflicting_evidence")
    provider_id = _text(provider.get("id"))
    observed_provider_id = _text(evidence.get("provider_id"))
    if not observed_provider_id:
        failures.append(f"{name}_missing_provider_id")
    elif observed_provider_id != provider_id:
        failures.append(f"{name}_provider_id_mismatch")
    owner = _text(evidence.get("owner"))
    if not owner:
        failures.append(f"{name}_missing_owner")
    elif owner != _MACHINE_OWNER or owner != _text(provider.get("host_owner")):
        failures.append(f"{name}_owner_mismatch")
    return failures


def _validate_installation_evidence(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    failures.extend(_validate_observation_binding(provider, observation))
    canonical = observation.get("installation_identity")
    installed = observation.get("installed")
    if not isinstance(canonical, Mapping):
        failures.append("installed_identity_missing_canonical_identity")
        if not isinstance(installed, Mapping):
            failures.append("installed_identity_missing")
        return failures, {}
    if not isinstance(installed, Mapping):
        return [*failures, "installed_identity_missing"], {}

    provider_id = _text(provider.get("id"))
    if _text(canonical.get("provider_id")) != provider_id:
        failures.append("installed_identity_provider_id_mismatch")
    canonical_owner = _text(canonical.get("owner"))
    if canonical_owner != _MACHINE_OWNER:
        failures.append("installed_identity_owner_mismatch")

    version = _text(canonical.get("version"))
    if not version:
        failures.append("installed_identity_missing_version")
    executable_or_path = _text(canonical.get("executable_or_path"))
    if not executable_or_path:
        failures.append("installed_identity_missing_executable_or_path")
    elif not _safe_identity_token(executable_or_path):
        failures.append("installed_identity_invalid_executable_or_path")

    observed_version = _text(installed.get("version"))
    observed_executable_or_path = _text(installed.get("executable")) or _text(installed.get("path"))
    if observed_version != version:
        failures.append("installed_identity_observation_version_mismatch")
    if observed_executable_or_path != executable_or_path and Path(observed_executable_or_path).name != Path(executable_or_path).name:
        failures.append("installed_identity_observation_path_mismatch")

    installation = provider.get("installation") if isinstance(provider.get("installation"), Mapping) else {}
    declared_executable = _text(installation.get("executable"))
    if declared_executable and executable_or_path:
        observed_executable = Path(executable_or_path).name
        if observed_executable != declared_executable and executable_or_path != declared_executable:
            failures.append("installed_identity_executable_mismatch")
    expected_version = _text(installation.get("expected_version"))
    if expected_version and version and version != expected_version:
        failures.append("installed_identity_version_mismatch")

    artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    artifact_required = artifact.get("required") is True
    installed_digest = _text(canonical.get("digest"))
    observed_digest = _text(installed.get("digest"))
    if observed_digest != installed_digest:
        failures.append("installed_identity_observation_digest_mismatch")
        if observed_digest and installed_digest:
            failures.append("installed_identity_artifact_digest_mismatch")
    if artifact_required and not _valid_digest(installed_digest):
        failures.append("installed_identity_missing_digest")
    return failures, {
        "version": version or None,
        "executable_or_path": executable_or_path or None,
        "digest": installed_digest or None,
    }


def _validate_artifact_and_trust_evidence(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    failures: list[str] = []
    artifact_declaration = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    artifact_evidence = _observation_evidence_mapping(observation, "artifact_identity", "artifact")
    failures.extend(_validate_nested_identity(provider, "artifact_identity", artifact_evidence))
    if _observation_evidence_conflicts(observation, "artifact_identity", "artifact"):
        failures.append("artifact_identity_conflicting_evidence")
    expected_class = _text(artifact_declaration.get("class"))
    artifact_class = _text(artifact_evidence.get("artifact_class")) or _text(artifact_evidence.get("class"))
    if not artifact_class:
        failures.append("artifact_identity_missing_class")
    elif expected_class and artifact_class != expected_class:
        failures.append("artifact_identity_class_mismatch")

    subject_digest = _text(artifact_evidence.get("subject_digest")) or _text(artifact_evidence.get("digest"))
    if not subject_digest:
        failures.append("artifact_identity_missing_subject_digest")
    elif not _valid_digest(subject_digest):
        failures.append("artifact_identity_invalid_subject_digest")
    source_ref = _text(artifact_evidence.get("source_ref")) or _text(artifact_evidence.get("source"))
    if artifact_declaration.get("source_ref_required") is True and not source_ref:
        failures.append("artifact_identity_missing_source_ref")
    elif artifact_declaration.get("source_ref_required") is True and not _valid_evidence_ref(source_ref):
        failures.append("artifact_identity_invalid_source_ref")
    elif artifact_declaration.get("source_ref_required") is True and not source_ref.startswith("source:"):
        failures.append("artifact_identity_unqualified_source_ref")

    trust_evidence = _observation_evidence_mapping(observation, "trust_gate", "trust", "trust_identity")
    failures.extend(_validate_nested_identity(provider, "trust_gate", trust_evidence))
    if _observation_evidence_conflicts(observation, "trust_gate", "trust", "trust_identity"):
        failures.append("trust_gate_conflicting_evidence")
    verdict = _text(trust_evidence.get("verdict")) or _text(trust_evidence.get("status"))
    if artifact_declaration.get("trust_gate_required") is True and not verdict:
        failures.append("trust_gate_missing_verdict")
    elif artifact_declaration.get("trust_gate_required") is True and verdict.lower() not in _TRUST_VERDICTS:
        failures.append("trust_gate_invalid_verdict")
    trusted_subject = _text(trust_evidence.get("subject_digest")) or _text(trust_evidence.get("digest"))
    if artifact_declaration.get("subject_digest_required") is True and not trusted_subject:
        failures.append("trust_gate_missing_subject_digest")
    elif trusted_subject and subject_digest and trusted_subject != subject_digest:
        failures.append("trust_gate_subject_mismatch")
    trust_ref = _text(trust_evidence.get("evidence_ref"))
    if artifact_declaration.get("trust_gate_required") is True and not _valid_evidence_ref(trust_ref):
        failures.append("trust_gate_missing_evidence_ref")
    elif artifact_declaration.get("trust_gate_required") is True and not trust_ref.startswith("trust:"):
        failures.append("trust_gate_unqualified_evidence_ref")

    return failures, {
        "artifact_class": artifact_class or None,
        "subject_digest": subject_digest or None,
        "source_ref": source_ref or None,
    }, {
        "verdict": verdict.lower() or None,
        "subject_digest": trusted_subject or None,
        "evidence_ref": trust_ref or None,
    }


def _validate_resource_evidence(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    declaration = provider.get("resource") if isinstance(provider.get("resource"), Mapping) else {}
    evidence = _observation_evidence_mapping(observation, "resource_route", "resource", "resource_envelope")
    if not evidence or not any(key in evidence for key in ("kind", "class", "demand_mib", "profile_ref", "route_ref", "route")):
        return ["resource_route_missing_envelope"], {}
    failures.extend(_validate_nested_identity(provider, "resource_route", evidence))
    if _observation_evidence_conflicts(observation, "resource_route", "resource", "resource_envelope"):
        failures.append("resource_route_conflicting_evidence")

    if evidence.get("kind") != declaration.get("kind"):
        failures.append("resource_route_kind_mismatch")
    if evidence.get("class") != declaration.get("class"):
        failures.append("resource_route_class_mismatch")
    demand = evidence.get("demand_mib")
    if isinstance(demand, bool) or not isinstance(demand, (int, float)) or not math.isfinite(float(demand)) or demand <= 0:
        failures.append("resource_route_invalid_demand")
    profile_ref = _text(evidence.get("profile_ref"))
    if profile_ref != _text(declaration.get("profile_ref")):
        failures.append("resource_route_profile_mismatch")
    route_ref = _text(evidence.get("route_ref")) or _text(evidence.get("route"))
    if not _valid_evidence_ref(route_ref):
        failures.append("resource_route_missing_route_ref")
    elif route_ref != _expected_resource_route(provider):
        failures.append("resource_route_provider_mismatch")
    return failures, {
        "kind": evidence.get("kind"),
        "class": evidence.get("class"),
        "demand_mib": demand if isinstance(demand, (int, float)) and not isinstance(demand, bool) else None,
        "profile_ref": profile_ref or None,
        "route_ref": route_ref or None,
    }


def _validate_live_measurement(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
    installed_identity: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    measurement = _observation_evidence_mapping(observation, "live_measurement", "measurement")
    if not measurement:
        return ["live_measurement_missing"], {}
    failures.extend(_validate_nested_identity(provider, "live_measurement", measurement))
    if _observation_evidence_conflicts(observation, "live_measurement", "measurement"):
        failures.append("live_measurement_conflicting_evidence")
    if measurement.get("schema") != MEASUREMENT_SCHEMA:
        failures.append("live_measurement_schema_mismatch")
    observed_at = _text(measurement.get("observed_at"))
    if not _valid_observed_at(observed_at):
        failures.append("live_measurement_invalid_observed_at")
    evidence_ref = _text(measurement.get("evidence_ref"))
    if not _valid_evidence_ref(evidence_ref):
        failures.append("live_measurement_invalid_evidence_ref")
    version = _text(measurement.get("version"))
    if not version:
        failures.append("live_measurement_missing_version")
    installed_version = _text(installed_identity.get("version"))
    if version and installed_version and version != installed_version:
        failures.append("live_measurement_version_mismatch")
    health = _text(measurement.get("health")) or _text(measurement.get("status"))
    if health.lower() not in _HEALTH_STATES:
        failures.append("live_measurement_not_healthy")
    return failures, {
        "schema": MEASUREMENT_SCHEMA,
        "observed_at": observed_at or None,
        "evidence_ref": evidence_ref or None,
        "version": version or None,
        "health": health.lower() or None,
    }


def _validate_observed_installation_identity(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    canonical = observation.get("installation_identity")
    installed = observation.get("installed")
    if not isinstance(canonical, Mapping):
        return ["installed_identity_missing_canonical_identity"], {}
    if not isinstance(installed, Mapping):
        return ["installed_identity_missing"], {}

    provider_id = _text(provider.get("id"))
    version = _text(canonical.get("version"))
    executable_or_path = _text(canonical.get("executable_or_path"))
    digest = _text(canonical.get("digest"))
    if _text(canonical.get("provider_id")) != provider_id:
        failures.append("installed_identity_provider_id_mismatch")
    if _text(canonical.get("owner")) != _MACHINE_OWNER:
        failures.append("installed_identity_owner_mismatch")
    if not version:
        failures.append("installed_identity_missing_version")
    if not executable_or_path or not _safe_identity_token(executable_or_path):
        failures.append("installed_identity_missing_executable_or_path")
    if _text(installed.get("version")) != version:
        failures.append("installed_identity_observation_version_mismatch")
    observed_executable = _text(installed.get("executable")) or _text(installed.get("path"))
    if observed_executable != executable_or_path and Path(observed_executable).name != Path(executable_or_path).name:
        failures.append("installed_identity_observation_path_mismatch")
    artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    if artifact.get("required") is True and not _valid_digest(digest):
        failures.append("installed_identity_missing_digest")
    if _text(installed.get("digest")) != digest:
        failures.append("installed_identity_observation_digest_mismatch")
    return failures, {
        "provider_id": provider_id,
        "owner": _MACHINE_OWNER,
        "version": version or None,
        "executable_or_path": executable_or_path or None,
        "digest": digest or None,
    }


def _validate_owner_receipt_observation(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any], dict[str, Any], dict[str, Any]]:
    failures = _validate_observation_binding(provider, observation)
    installation_failures, installation = _validate_observed_installation_identity(provider, observation)
    failures.extend(installation_failures)
    resource_failures, resource = _validate_resource_evidence(provider, observation)
    failures.extend(resource_failures)
    measurement_failures, measurement = _validate_live_measurement(provider, observation, installation)
    failures.extend(measurement_failures)
    return failures, installation, resource, measurement


def _receipt_gate_record(
    name: str,
    *,
    observed_at: str | None,
    evidence_ref: str | None,
    state: str,
    ok: bool | None,
    reason: str | None = None,
    authority: str = "owner_produced_receipt",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "required": True,
        "state": state,
        "ok": ok,
        "observed_at": observed_at,
        "evidence_ref": evidence_ref,
        "authority": authority,
    }
    if reason:
        record["blocking_reason"] = reason
    return record


def _owner_admission_receipt_from_verified_gate(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
    gate: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    source_config_digest: str,
    registry_ref: str | None = None,
) -> _OwnerAdmissionReceipt:
    """Issue the opaque receipt only after the real owner gate has passed.

    This private issuer is used by the host adapter after calling the
    artifact-bundles trust gate. It is intentionally not a parser for caller
    evidence: the registry record and gate snapshot are copied into a
    content-addressed receipt, and the admission consumer accepts only the
    resulting opaque value.
    """

    provider_artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    route = _RUNTIME_ARTIFACT_ROUTE
    observation_failures, installation, resource, measurement = _validate_owner_receipt_observation(provider, observation)
    if observation_failures:
        raise ValueError("owner admission receipt observation is invalid: " + ",".join(observation_failures))
    if not _valid_digest(source_config_digest):
        raise ValueError("owner admission receipt requires a source config digest")
    if not isinstance(gate, Mapping) or not isinstance(record, Mapping):
        raise ValueError("owner admission receipt requires registry record and trust-gate snapshots")

    record_payload = _copy(record)
    gate_payload = _copy(gate)
    record_id = _text(record_payload.get("record_id"))
    subject_digest = _text(record_payload.get("subject_digest"))
    gate_record = gate_payload.get("record")
    if not record_id or not _valid_digest(record_id) or not _valid_digest(subject_digest):
        raise ValueError("owner admission receipt requires content-addressed record and subject identities")
    if gate_record != record_payload:
        raise ValueError("trust-gate record must match the selected registry record")
    required_controls = [str(item) for item in record_payload.get("required_controls", [])]
    verified_controls = {str(item) for item in record_payload.get("verified_controls", [])}
    if (
        provider_artifact.get("required") is not True
        or record_payload.get("artifact_class") != route["artifact_class"]
        or record_payload.get("source_repo") != _MACHINE_OWNER
        or not _text(record_payload.get("source_ref"))
        or not _text(record_payload.get("producer"))
        or not isinstance(record_payload.get("verifier_versions"), Mapping)
        or not record_payload.get("verifier_versions")
        or record_payload.get("trust_root_mode") != route["trust_gate"]["expected_trust_root_mode"]
        or record_payload.get("latest_eligible") is not True
        or record_payload.get("terminal_state") is not False
        or record_payload.get("verification_ok") is not True
        or required_controls != list(route["required_controls"])
        or not set(route["required_controls"]).issubset(verified_controls)
        or record_payload.get("abi_ref") != route["abi_ref"]
        or record_payload.get("bundle_manifest_ref") != route["bundle_manifest_ref"]
        or record_payload.get("contract_surface_id") != route["contract_surface_id"]
    ):
        raise ValueError("registry record does not satisfy the exact runtime artifact route")
    if (
        gate_payload.get("schema") != route["trust_gate"]["schema"]
        or gate_payload.get("ok") is not True
        or gate_payload.get("verdict") != route["trust_gate"]["required_verdict"]
        or gate_payload.get("artifact_class") != route["artifact_class"]
        or gate_payload.get("consumer_intent") != route["trust_gate"]["consumer_intent"]
        or gate_payload.get("subject_digest") != subject_digest
        or gate_payload.get("record_id") != record_id
        or gate_payload.get("latest_record_id") != record_id
        or gate_payload.get("require_latest") is not True
    ):
        raise ValueError("trust-gate result does not satisfy the exact runtime admission route")
    resolved_registry_ref = _text(registry_ref) or _text(gate_payload.get("registry_dir"))
    if not _valid_durable_ref(resolved_registry_ref):
        raise ValueError("owner admission receipt requires a durable registry reference")

    receipt: dict[str, Any] = {
        "schema": ADMISSION_RECEIPT_SCHEMA,
        "version": VERSION,
        "provider_id": _text(provider.get("id")),
        "producer": {
            "owner": _MACHINE_OWNER,
            "boundary": _ARTIFACT_REGISTRY_BOUNDARY,
            "registry_ref": resolved_registry_ref,
            "record_ref": f"{resolved_registry_ref}/records/{record_id.removeprefix('sha256:')}.json",
        },
        "source": {
            "config_digest": source_config_digest,
            "config_ref": "config-templates/etc/abyss-machine/code-intelligence.json",
        },
        "registry": {
            "schema": route["registry"]["layout"],
            "record_schema": route["registry"]["record_schema"],
            "record_id": record_id,
            "record_digest": _stable_digest(record_payload),
            "record": record_payload,
        },
        "artifact": {
            "artifact_class": route["artifact_class"],
            "contract_surface_id": route["contract_surface_id"],
            "abi_ref": route["abi_ref"],
            "bundle_manifest_ref": route["bundle_manifest_ref"],
            "subject_digest": subject_digest,
            "required_controls": list(route["required_controls"]),
            "verified_controls": sorted(verified_controls),
        },
        "trust_gate": {
            "schema": route["trust_gate"]["schema"],
            "gate_ref": f"trust:abyss-machine/artifact-registry/{record_id.removeprefix('sha256:')}/runtime",
            "gate_digest": _stable_digest(gate_payload),
            "gate": gate_payload,
        },
        "observation": {
            "provider_id": _text(observation.get("provider_id")),
            "observed_at": _text(observation.get("observed_at")),
            "evidence_ref": _text(observation.get("evidence_ref")),
            "identity_digest": _observation_identity_digest(observation),
            "measurement_digest": _observation_measurement_digest(observation),
            "installation_digest": installation.get("digest"),
            "resource_route": resource.get("route_ref"),
            "measurement": measurement,
        },
    }
    receipt["receipt_digest"] = _content_addressed_digest(receipt)
    return _OwnerAdmissionReceipt(receipt, _OWNER_ADMISSION_RECEIPT_MARKER)


def _validate_owner_admission_receipt(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
    receipt: _OwnerAdmissionReceipt,
    *,
    source_config_digest: str,
) -> tuple[list[str], dict[str, Any], dict[str, dict[str, Any]]]:
    failures, installation, resource, measurement = _validate_owner_receipt_observation(provider, observation)
    payload = receipt._payload
    if receipt._marker is not _OWNER_ADMISSION_RECEIPT_MARKER:
        failures.append("owner_admission_receipt_marker_invalid")
    if payload.get("schema") != ADMISSION_RECEIPT_SCHEMA:
        failures.append("owner_admission_receipt_schema_mismatch")
    if payload.get("version") != VERSION:
        failures.append("owner_admission_receipt_version_mismatch")
    if payload.get("provider_id") != _text(provider.get("id")):
        failures.append("owner_admission_receipt_provider_id_mismatch")
    if not _valid_digest(_text(payload.get("receipt_digest"))):
        failures.append("owner_admission_receipt_digest_missing_or_invalid")
    elif _text(payload.get("receipt_digest")) != _content_addressed_digest(payload):
        failures.append("owner_admission_receipt_digest_mismatch")

    producer = payload.get("producer") if isinstance(payload.get("producer"), Mapping) else {}
    if producer.get("owner") != _MACHINE_OWNER:
        failures.append("owner_admission_receipt_producer_owner_mismatch")
    if producer.get("boundary") != _ARTIFACT_REGISTRY_BOUNDARY:
        failures.append("owner_admission_receipt_boundary_mismatch")
    registry_ref = _text(producer.get("registry_ref"))
    if not _valid_durable_ref(registry_ref):
        failures.append("owner_admission_receipt_registry_ref_invalid")
    record_ref = _text(producer.get("record_ref"))
    if not _valid_durable_ref(record_ref):
        failures.append("owner_admission_receipt_record_ref_invalid")

    source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    if source.get("config_digest") != source_config_digest:
        failures.append("owner_admission_receipt_source_config_mismatch")
    if source.get("config_ref") != "config-templates/etc/abyss-machine/code-intelligence.json":
        failures.append("owner_admission_receipt_source_ref_mismatch")

    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    record = registry.get("record") if isinstance(registry.get("record"), Mapping) else {}
    record_id = _text(registry.get("record_id"))
    subject_digest = _text(record.get("subject_digest"))
    record_digest = _text(registry.get("record_digest"))
    if registry.get("schema") != _RUNTIME_ARTIFACT_ROUTE["registry"]["layout"]:
        failures.append("owner_admission_receipt_registry_schema_mismatch")
    if registry.get("record_schema") != _RUNTIME_ARTIFACT_ROUTE["registry"]["record_schema"]:
        failures.append("owner_admission_receipt_record_schema_mismatch")
    if not _valid_digest(record_id) or record.get("record_id") != record_id:
        failures.append("owner_admission_receipt_record_id_invalid")
    if not _valid_digest(record_digest) or record_digest != _stable_digest(record):
        failures.append("owner_admission_receipt_record_digest_mismatch")

    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), Mapping) else {}
    route = _RUNTIME_ARTIFACT_ROUTE
    if artifact.get("artifact_class") != route["artifact_class"] or record.get("artifact_class") != route["artifact_class"]:
        failures.append("owner_admission_receipt_artifact_class_mismatch")
    for field in ("contract_surface_id", "abi_ref", "bundle_manifest_ref"):
        if artifact.get(field) != route[field]:
            failures.append(f"owner_admission_receipt_{field}_mismatch")
    if artifact.get("subject_digest") != subject_digest:
        failures.append("owner_admission_receipt_subject_digest_mismatch")
    if artifact.get("required_controls") != list(route["required_controls"]):
        failures.append("owner_admission_receipt_required_controls_mismatch")
    verified_controls = artifact.get("verified_controls")
    if not isinstance(verified_controls, list) or not set(route["required_controls"]).issubset(set(str(item) for item in verified_controls)):
        failures.append("owner_admission_receipt_verified_controls_incomplete")
    if (
        record.get("source_repo") != _MACHINE_OWNER
        or not _text(record.get("source_ref"))
        or not _text(record.get("producer"))
        or not isinstance(record.get("verifier_versions"), Mapping)
        or not record.get("verifier_versions")
        or record.get("trust_root_mode") != route["trust_gate"]["expected_trust_root_mode"]
        or record.get("latest_eligible") is not True
        or record.get("terminal_state") is not False
        or record.get("verification_ok") is not True
        or record.get("required_controls") != list(route["required_controls"])
        or not set(route["required_controls"]).issubset(set(str(item) for item in record.get("verified_controls", [])))
        or record.get("abi_ref") != route["abi_ref"]
        or record.get("bundle_manifest_ref") != route["bundle_manifest_ref"]
        or record.get("contract_surface_id") != route["contract_surface_id"]
    ):
        failures.append("owner_admission_receipt_registry_record_not_admitted")

    trust = payload.get("trust_gate") if isinstance(payload.get("trust_gate"), Mapping) else {}
    gate = trust.get("gate") if isinstance(trust.get("gate"), Mapping) else {}
    gate_digest = _text(trust.get("gate_digest"))
    if trust.get("schema") != route["trust_gate"]["schema"]:
        failures.append("owner_admission_receipt_gate_schema_mismatch")
    if not _valid_digest(gate_digest) or gate_digest != _stable_digest(gate):
        failures.append("owner_admission_receipt_gate_digest_mismatch")
    if (
        gate.get("schema") != route["trust_gate"]["schema"]
        or gate.get("ok") is not True
        or gate.get("verdict") != route["trust_gate"]["required_verdict"]
        or gate.get("artifact_class") != route["artifact_class"]
        or gate.get("consumer_intent") != route["trust_gate"]["consumer_intent"]
        or gate.get("subject_digest") != subject_digest
        or gate.get("record_id") != record_id
        or gate.get("latest_record_id") != record_id
        or gate.get("require_latest") is not True
        or gate.get("record") != record
    ):
        failures.append("owner_admission_receipt_gate_not_admitted")
    if _text(trust.get("gate_ref")) == "" or not _valid_evidence_ref(_text(trust.get("gate_ref"))):
        failures.append("owner_admission_receipt_gate_ref_invalid")

    bound = payload.get("observation") if isinstance(payload.get("observation"), Mapping) else {}
    if bound.get("provider_id") != _text(observation.get("provider_id")):
        failures.append("owner_admission_receipt_observation_provider_mismatch")
    if bound.get("observed_at") != _text(observation.get("observed_at")):
        failures.append("owner_admission_receipt_observation_time_mismatch")
    if bound.get("evidence_ref") != _text(observation.get("evidence_ref")):
        failures.append("owner_admission_receipt_observation_ref_mismatch")
    if bound.get("identity_digest") != _observation_identity_digest(observation):
        failures.append("owner_admission_receipt_observation_identity_mismatch")
    if bound.get("measurement_digest") != _observation_measurement_digest(observation):
        failures.append("owner_admission_receipt_measurement_digest_mismatch")
    if bound.get("resource_route") != resource.get("route_ref"):
        failures.append("owner_admission_receipt_resource_route_mismatch")

    evidence_ref = _text(observation.get("evidence_ref")) or None
    observed_at = _text(observation.get("observed_at")) or None
    gate_ref = _text(trust.get("gate_ref")) or None
    record_ref = _text(producer.get("record_ref")) or None
    gates = {
        "owner_admission_receipt": _receipt_gate_record(
            "owner_admission_receipt",
            observed_at=observed_at,
            evidence_ref=gate_ref,
            state="verified" if not failures else "failed",
            ok=True if not failures else False,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
        "artifact_identity": _receipt_gate_record(
            "artifact_identity",
            observed_at=observed_at,
            evidence_ref=record_ref,
            state="verified" if not failures else "unknown",
            ok=True if not failures else None,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
        "trust_gate": _receipt_gate_record(
            "trust_gate",
            observed_at=observed_at,
            evidence_ref=gate_ref,
            state="verified" if not failures else "unknown",
            ok=True if not failures else None,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
        "installed_identity": _receipt_gate_record(
            "installed_identity",
            observed_at=observed_at,
            evidence_ref=evidence_ref,
            state="verified" if not failures else "unknown",
            ok=True if not failures else None,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
        "runnable_health": _receipt_gate_record(
            "runnable_health",
            observed_at=observed_at,
            evidence_ref=evidence_ref,
            state="verified" if not failures else "unknown",
            ok=True if not failures else None,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
        "resource_route": _receipt_gate_record(
            "resource_route",
            observed_at=observed_at,
            evidence_ref=_text(resource.get("route_ref")) or None,
            state="verified" if not failures else "unknown",
            ok=True if not failures else None,
            reason=None if not failures else "owner_admission_receipt_invalid",
        ),
    }
    identity_checks = {
        "installation": installation,
        "artifact": {
            "artifact_class": artifact.get("artifact_class"),
            "contract_surface_id": artifact.get("contract_surface_id"),
            "abi_ref": artifact.get("abi_ref"),
            "bundle_manifest_ref": artifact.get("bundle_manifest_ref"),
            "subject_digest": subject_digest or None,
            "source_ref": record.get("source_ref"),
        },
        "trust": {
            "verdict": gate.get("verdict"),
            "subject_digest": gate.get("subject_digest"),
            "record_id": gate.get("record_id"),
            "registry_ref": registry_ref or None,
        },
        "resource": resource,
        "live_measurement": measurement,
        "receipt": {
            "schema": payload.get("schema"),
            "receipt_digest": payload.get("receipt_digest"),
            "record_digest": record_digest,
            "gate_digest": gate_digest,
        },
    }
    return failures, identity_checks, gates


def _validate_admission_evidence(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    failures, installed_identity = _validate_installation_evidence(provider, observation)
    artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    artifact_identity: dict[str, Any] = {}
    trust_identity: dict[str, Any] = {}
    if artifact.get("required") is True:
        artifact_failures, artifact_identity, trust_identity = _validate_artifact_and_trust_evidence(provider, observation)
        failures.extend(artifact_failures)
        installed_digest = _text(installed_identity.get("digest"))
        subject_digest = _text(artifact_identity.get("subject_digest"))
        if installed_digest and subject_digest and installed_digest != subject_digest:
            failures.append("installed_identity_artifact_digest_mismatch")
    resource_failures, resource_identity = _validate_resource_evidence(provider, observation)
    failures.extend(resource_failures)
    measurement_failures, measurement = _validate_live_measurement(provider, observation, installed_identity)
    failures.extend(measurement_failures)
    return failures, {
        "installation": installed_identity,
        "artifact": artifact_identity,
        "trust": trust_identity,
        "resource": resource_identity,
        "live_measurement": measurement,
    }


def admit_provider(
    provider: Mapping[str, Any],
    observation: Mapping[str, Any] | None = None,
    *,
    source_config_valid: bool = True,
    source_evidence_ref: str = "source:config-templates/etc/abyss-machine/code-intelligence.json",
    source_config_digest: str | None = None,
    admission_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one provider against source and an owner-issued admission receipt.

    Caller observations remain useful facts, but their booleans, owner strings,
    digests, measurements, and gate values cannot establish admission.  The
    required receipt is an opaque value issued only after the machine-owned
    artifact registry and trust gate have passed the exact runtime route.
    """

    provider_id = _text(provider.get("id"))
    raw_observation = observation if isinstance(observation, Mapping) else {}
    artifact = provider.get("artifact") if isinstance(provider.get("artifact"), Mapping) else {}
    artifact_required = artifact.get("required") is True
    gates: dict[str, dict[str, Any]] = {}
    if source_config_valid:
        gates["source_config"] = {
            "required": True,
            "state": "declared",
            "ok": True,
            "observed_at": None,
            "evidence_ref": source_evidence_ref,
        }
    else:
        gates["source_config"] = {
            "required": True,
            "state": "invalid",
            "ok": False,
            "observed_at": None,
            "evidence_ref": source_evidence_ref,
            "blocking_reason": "source_config_invalid",
        }

    receipt_failures: list[str] = []
    receipt_identity: dict[str, Any] = {}
    receipt_gates: dict[str, dict[str, Any]] = {}
    receipt_payload = _owner_receipt_payload(admission_receipt)
    if receipt_payload is not None and source_config_valid and _valid_digest(source_config_digest):
        receipt_failures, receipt_identity, receipt_gates = _validate_owner_admission_receipt(
            provider,
            raw_observation,
            admission_receipt,
            source_config_digest=str(source_config_digest),
        )
    elif admission_receipt is not None:
        receipt_failures.append(
            "owner_admission_receipt_not_owner_produced"
            if receipt_payload is None
            else "owner_admission_receipt_source_config_digest_missing"
        )

    if receipt_gates:
        gates.update(receipt_gates)
    else:
        gates["owner_admission_receipt"] = _receipt_gate_record(
            "owner_admission_receipt",
            observed_at=_text(raw_observation.get("observed_at")) or None,
            evidence_ref=None,
            state="failed" if admission_receipt is not None else "unknown",
            ok=False if admission_receipt is not None else None,
            reason=(
                receipt_failures[0]
                if receipt_failures
                else "owner_admission_receipt_missing"
            ),
            authority="owner_admission_boundary",
        )

    for name in _LIVE_GATES:
        if name in {"artifact_identity", "trust_gate"} and not artifact_required:
            gates[name] = _not_required_gate()
            continue
        if receipt_gates:
            # The receipt validator owns the verified state for these gates.
            continue
        gates[name] = _untrusted_observation_gate(
            name,
            raw_observation,
            reason=(
                receipt_failures[0]
                if receipt_failures
                else "owner_admission_receipt_missing"
            ),
        )

    required_names = [name for name, record in gates.items() if record["required"]]
    blocking_reasons = list(receipt_failures)
    blocking_reasons.extend(
        str(gates[name]["blocking_reason"])
        for name in required_names
        if gates[name].get("state") not in {"declared", "verified"} and gates[name].get("blocking_reason")
    )
    identity_checks: dict[str, Any] = receipt_identity
    admitted = not blocking_reasons and all(gates[name].get("ok") is True for name in required_names)
    unique_blocking_reasons: list[str] = []
    for reason in blocking_reasons:
        if reason not in unique_blocking_reasons:
            unique_blocking_reasons.append(reason)
    if not unique_blocking_reasons and not admitted:
        unique_blocking_reasons = ["admission_unknown"]

    observation_evidence_refs = sorted(
        {
            str(value)
            for name in _LIVE_GATES
            for value in [_gate_input(raw_observation, name)[2]]
            if _valid_evidence_ref(value)
        }
    )
    evidence_refs = sorted(
        {
            str(record["evidence_ref"])
            for record in gates.values()
            if record.get("authority") == "owner_produced_receipt"
            and _valid_evidence_ref(record.get("evidence_ref"))
        }
        | ({source_evidence_ref} if _valid_evidence_ref(source_evidence_ref) else set())
    )
    receipt_digest = _text(receipt_payload.get("receipt_digest")) if receipt_payload is not None else None
    return {
        "provider_id": provider_id,
        "decision": "admit" if admitted else "deny",
        "status": "admitted" if admitted else "not_admitted",
        "required_gates": required_names,
        "gates": gates,
        "blocking_reasons": unique_blocking_reasons,
        "observed_identity": _safe_identity(raw_observation),
        "identity_checks": identity_checks,
        "evidence_refs": evidence_refs,
        "observation_evidence_refs": observation_evidence_refs,
        "admission_source": (
            "owner_produced_content_addressed_receipt"
            if receipt_gates and not receipt_failures
            else "caller_observation_only"
        ),
        "receipt_digest": receipt_digest,
        "semantic_usefulness": "unproven",
        "semantic_proof_owner": "aoa-evals",
        "admission_is_not_semantic_proof": True,
    }


def provider_admission(
    config: Mapping[str, Any],
    provider_id: str,
    observation: Mapping[str, Any] | None = None,
    *,
    admission_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate config and evaluate the named provider lane."""

    validation = validate_provider_config(config)
    provider = _provider_for_id(config, provider_id)
    if provider is None:
        return {
            "provider_id": provider_id,
            "decision": "deny",
            "status": "not_admitted",
            "required_gates": ["source_config"],
            "gates": {
                "source_config": {
                    "required": True,
                    "state": "invalid",
                    "ok": False,
                    "observed_at": None,
                    "evidence_ref": "source:config-templates/etc/abyss-machine/code-intelligence.json",
                    "blocking_reason": "provider_not_declared",
                }
            },
            "blocking_reasons": ["provider_not_declared"],
            "observed_identity": {},
            "evidence_refs": [],
            "semantic_usefulness": "unproven",
            "semantic_proof_owner": "aoa-evals",
            "admission_is_not_semantic_proof": True,
        }
    return admit_provider(
        provider,
        observation,
        source_config_valid=bool(validation["ok"]),
        source_config_digest=_stable_digest(config),
        admission_receipt=admission_receipt,
    )


def _provider_record(
    provider: Mapping[str, Any],
    admission: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    path_policy: AbyssMachinePathPolicy,
) -> dict[str, Any]:
    provider_id = str(provider["id"])
    resolved_paths = resolve_provider_paths(config, provider_id, path_policy=path_policy)
    return {
        "id": provider_id,
        "display_name": provider.get("display_name"),
        "role": provider.get("role"),
        "mode": provider.get("mode"),
        "ownership": {
            "host_owner": provider.get("host_owner"),
            "consumer_owner": provider.get("consumer_owner"),
        },
        "declared_capabilities": list(provider.get("declared_capabilities") or []),
        "paths": {key: str(value) for key, value in resolved_paths.items()},
        "resource": _copy(provider.get("resource") or {}),
        "installation": {
            **_copy(provider.get("installation") or {}),
            "observed_identity": _copy(admission.get("observed_identity") or {}),
            "status": admission.get("gates", {}).get("installed_identity", {}).get("state"),
        },
        "artifact": {
            **_copy(provider.get("artifact") or {}),
            "identity_status": admission.get("gates", {}).get("artifact_identity", {}).get("state"),
            "trust_status": admission.get("gates", {}).get("trust_gate", {}).get("state"),
        },
        "admission": _copy(admission),
        "semantic": _copy(provider.get("semantic") or {"status": "unproven"}),
    }


def provider_baseline_document(
    config: Mapping[str, Any] | None = None,
    observations: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    path_policy: AbyssMachinePathPolicy | None = None,
    generated_at: str = "",
) -> dict[str, Any]:
    """Build a facts-only provider baseline from source and optional evidence."""

    effective_config = config if isinstance(config, Mapping) else code_intelligence_config()
    policy = path_policy or DEFAULT_PATH_POLICY
    validation = validate_provider_config(effective_config, path_policy=policy)
    raw_observations = observations if isinstance(observations, Mapping) else {}
    provider_items: list[dict[str, Any]] = []
    configured_providers = effective_config.get("providers")
    for provider in configured_providers if isinstance(configured_providers, list) else []:
        if not isinstance(provider, Mapping):
            continue
        provider_id = str(provider.get("id") or "")
        observation = raw_observations.get(provider_id)
        admission = admit_provider(
            provider,
            observation if isinstance(observation, Mapping) else None,
            source_config_valid=bool(validation["ok"]),
            source_config_digest=_stable_digest(effective_config),
        )
        if validation["ok"]:
            provider_items.append(
                _provider_record(
                    provider,
                    admission,
                    config=effective_config,
                    path_policy=policy,
                )
            )

    admitted = sum(1 for item in provider_items if item["admission"]["status"] == "admitted")
    not_admitted = len(provider_items) - admitted
    return {
        "schema": BASELINE_SCHEMA,
        "version": VERSION,
        "generated_at": generated_at,
        "source": {
            "owner": "abyss-machine",
            "config_ref": effective_config.get("source", {}).get("config_ref") if isinstance(effective_config.get("source"), Mapping) else None,
            "config_schema": effective_config.get("schema"),
            "config_digest": _stable_digest(effective_config),
            "observation_source": "caller_supplied_host_facts",
        },
        "validation": validation,
        "paths": _resolved_roots(policy),
        "providers": provider_items,
        "summary": {
            "provider_count": len(provider_items),
            "admitted": admitted,
            "not_admitted": not_admitted,
            "all_required_lanes_declared": set(PROVIDER_IDS).issubset({item["id"] for item in provider_items}),
            "semantic_usefulness_proven": False,
        },
        "policy": {
            "read_only": True,
            "fail_closed": True,
            "unknown_is": "not_admitted",
            "host_layer_mutates_stack": False,
            "network_downloads": False,
            "service_mutation": False,
            "trust_grant": False,
            "raw_command_output": "discarded",
            "semantic_usefulness": "unproven",
        },
        "ownership": _copy(effective_config.get("ownership") or {}),
        "storage": _copy(effective_config.get("storage") or {}),
        "rollback": _copy(effective_config.get("rollback") or {}),
        "non_claims": list(effective_config.get("non_claims") or []),
    }


def code_observation_envelope(
    provider_id: str,
    records: Sequence[Mapping[str, Any]],
    *,
    source_ref: str,
    source_epoch: str | None,
    config_digest: str | None,
    generated_at: str,
    provenance_ref: str | None = None,
) -> dict[str, Any]:
    """Create the boundary envelope consumed by a downstream observation owner."""

    if provider_id not in PROVIDER_IDS:
        raise ValueError(f"unknown provider id: {provider_id}")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise TypeError("records must be a sequence of objects")
    if not all(isinstance(record, Mapping) for record in records):
        raise TypeError("records must contain only objects")
    bound = bool(
        _valid_evidence_ref(source_ref)
        and _valid_digest(source_epoch)
        and _valid_digest(config_digest)
        and _valid_observed_at(generated_at)
    )
    provenance_bound = _valid_evidence_ref(provenance_ref)
    return {
        "schema": OBSERVATION_SCHEMA,
        "version": VERSION,
        "generated_at": generated_at,
        "provider": {
            "id": provider_id,
            "owner": _MACHINE_OWNER,
            "config_digest": config_digest,
        },
        "source": {
            "owner": _MACHINE_OWNER,
            "ref": source_ref or None,
            "epoch": source_epoch or None,
            "binding_status": "bound" if bound else "unbound",
        },
        "records": [_copy(record) for record in records],
        "record_count": len(records),
        "provenance": {
            "evidence_ref": provenance_ref or None,
            "binding_status": "bound" if provenance_bound else "unbound",
        },
        "lineage": {
            "derived_from_source": True,
            "canonical_source": "owner_repository",
            "observation_consumer": "aoa-kag",
        },
        "semantic": {
            "status": "unproven",
            "proof_owner": "aoa-evals",
            "admission_is_not_semantic_proof": True,
        },
        "policy": {
            "machine_layer_materializes_no_kag_truth": True,
            "unbound_source_or_provenance_is_not_admitted": True,
        },
    }


__all__ = [
    "BASELINE_SCHEMA",
    "CONFIG_SCHEMA",
    "MACHINE_CONSUMER_ABI",
    "MEASUREMENT_SCHEMA",
    "OBSERVATION_SCHEMA",
    "PROVIDER_IDS",
    "VERSION",
    "admit_provider",
    "code_intelligence_config",
    "code_observation_envelope",
    "default_provider_catalog",
    "provider_admission",
    "provider_baseline_document",
    "provider_catalog",
    "resolve_provider_paths",
    "validate_config",
    "validate_provider_config",
]
