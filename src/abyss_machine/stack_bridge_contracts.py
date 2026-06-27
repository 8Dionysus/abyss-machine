from __future__ import annotations

from pathlib import Path
from typing import Any

from . import validation_contracts


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root: Path,
    agents_path: Path,
    latest_path: Path,
    today: Path,
    validate_root: Path,
    validate_latest_path: Path,
    static_sync_root: Path,
    static_sync_latest_path: Path,
    observability_root: Path,
    observability_latest_path: Path,
    self_awareness_root: Path,
    self_awareness_latest_path: Path,
    self_awareness_probe_path: Path,
    self_awareness_validate_path: Path,
    manifest_path: Path,
    doc_path: Path,
    main_bridge_path: Path,
    hooks_etc_dir: Path,
    hooks_srv_dir: Path,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "stack_bridge_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(root),
        "agent_entrypoint": str(agents_path),
        "latest": str(latest_path),
        "today": str(today),
        "daily_glob": str(root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "validate": {
            "root": str(validate_root),
            "latest": str(validate_latest_path),
            "daily_glob": str(validate_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "static_sync": {
            "root": str(static_sync_root),
            "latest": str(static_sync_latest_path),
            "daily_glob": str(static_sync_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "observability": {
            "root": str(observability_root),
            "latest": str(observability_latest_path),
            "daily_glob": str(observability_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "self_awareness": {
            "root": str(self_awareness_root),
            "latest": str(self_awareness_latest_path),
            "probe": str(self_awareness_probe_path),
            "validate": str(self_awareness_validate_path),
            "daily_glob": str(self_awareness_root / "SUBSYSTEM" / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "config": {
            "manifest": str(manifest_path),
            "doc": str(doc_path),
            "main_bridge": str(main_bridge_path),
            "host_agents": str(Path("/etc/abyss-machine/AGENTS.md")),
            "commands": str(Path("/etc/abyss-machine/commands.md")),
        },
        "hooks": {
            "etc": str(hooks_etc_dir),
            "srv": str(hooks_srv_dir),
            "automatic_execution": False,
        },
        "commands": {
            "status": "abyss-machine stack-bridge --json",
            "paths": "abyss-machine stack-bridge paths --json",
            "export": "abyss-machine stack-bridge export --json",
            "latest": "abyss-machine stack-bridge latest --json",
            "validate": "abyss-machine stack-bridge validate --json",
            "observability": "abyss-machine stack-bridge observability --json",
        },
    }


def extension_commands(
    *,
    nervous_quality_audit_command: str,
    nervous_quality_audit_refresh_command: str,
) -> dict[str, list[str]]:
    return {
        "maps_json": ["abyss-machine", "maps", "--json"],
        "maps_validate_json": ["abyss-machine", "maps", "validate", "--json"],
        "rag_refresh_json": ["abyss-machine", "rag", "refresh", "--query", "scheduled machine context refresh", "--json"],
        "rag_trace_json": ["abyss-machine", "rag", "trace", "--query", "machine RAG trace", "--json"],
        "rag_validate_json": ["abyss-machine", "rag", "validate", "--json"],
        "resource_orchestrator_json": ["abyss-machine", "resource", "orchestrator", "--json"],
        "resource_orchestrator_refresh_nervous_json": ["abyss-machine", "resource", "orchestrator", "--refresh-nervous", "--json"],
        "nervous_quality_audit_json": nervous_quality_audit_command.split(),
        "nervous_quality_audit_refresh_json": nervous_quality_audit_refresh_command.split(),
        "nervous_quality_audit_refresh_index_json": ["abyss-machine", "nervous", "quality-audit", "--refresh", "--refresh-index", "--json"],
        "heartbeats_pulse_json": ["abyss-machine", "heartbeats", "pulse", "--json"],
        "heartbeats_paths_json": ["abyss-machine", "heartbeats", "paths", "--json"],
        "heartbeats_validate_json": ["abyss-machine", "heartbeats", "validate", "--json"],
        "stack_bridge_observability_json": ["abyss-machine", "stack-bridge", "observability", "--json"],
        "stack_bridge_sync_static_json": ["sudo", "abyss-machine", "stack-bridge", "sync-static", "--json"],
        "self_awareness_paths_json": ["abyss-machine", "self-awareness", "paths", "--json"],
        "self_awareness_status_json": ["abyss-machine", "self-awareness", "status", "--json"],
        "self_awareness_capabilities_json": ["abyss-machine", "self-awareness", "capabilities", "--json"],
        "self_awareness_requirements_json": ["abyss-machine", "self-awareness", "requirements", "--json"],
        "self_awareness_requirement_probes_json": ["abyss-machine", "self-awareness", "requirement-probes", "--json"],
        "self_awareness_stack_closure_dossier_json": ["abyss-machine", "self-awareness", "stack-closure-dossier", "--json"],
        "self_awareness_trace_context_json": ["abyss-machine", "self-awareness", "trace-context", "--json"],
        "self_awareness_working_stack_json": ["abyss-machine", "self-awareness", "working-stack", "--json"],
        "self_awareness_collect_json": ["abyss-machine", "self-awareness", "collect", "--json"],
        "self_awareness_query_json": ["abyss-machine", "self-awareness", "query", "--query", "TEXT", "--json"],
        "self_awareness_correlate_json": ["abyss-machine", "self-awareness", "correlate", "--json"],
        "self_awareness_timeline_json": ["abyss-machine", "self-awareness", "timeline", "--json"],
        "self_awareness_spatial_graph_json": ["abyss-machine", "self-awareness", "spatial-graph", "--json"],
        "self_awareness_context_json": ["abyss-machine", "self-awareness", "context", "--json"],
        "self_awareness_episodes_json": ["abyss-machine", "self-awareness", "episodes", "--json"],
        "self_awareness_alerts_json": ["abyss-machine", "self-awareness", "alerts", "--json"],
        "self_awareness_investigate_json": ["abyss-machine", "self-awareness", "investigate", "--query", "TEXT", "--json"],
        "self_awareness_replay_json": ["abyss-machine", "self-awareness", "replay", "--json"],
        "self_awareness_activation_smoke_json": ["abyss-machine", "self-awareness", "activation-smoke", "--json"],
        "self_awareness_autolink_json": ["abyss-machine", "self-awareness", "autolink", "--json"],
        "self_awareness_brief_json": ["abyss-machine", "self-awareness", "brief", "--json"],
        "self_awareness_failure_matrix_json": ["abyss-machine", "self-awareness", "failure-matrix", "--json"],
        "self_awareness_probe_json": ["abyss-machine", "self-awareness", "probe", "--json"],
        "self_awareness_cycle_json": ["abyss-machine", "self-awareness", "cycle", "--json"],
        "self_awareness_export_json": ["abyss-machine", "self-awareness", "export", "--json"],
        "self_awareness_validate_json": ["abyss-machine", "self-awareness", "validate", "--json"],
    }


def typing_bridge_contract(
    *,
    typing_agents_path: Path,
    events_latest_path: Path,
    coverage_latest_path: Path,
    process_latest_path: Path,
    nervous_refresh_latest_path: Path,
    validate_latest_path: Path,
) -> dict[str, Any]:
    return {
        "agent_entrypoint": str(typing_agents_path),
        "latest_event": str(events_latest_path),
        "coverage_latest": str(coverage_latest_path),
        "process_latest": str(process_latest_path),
        "nervous_refresh_latest": str(nervous_refresh_latest_path),
        "validate_latest": str(validate_latest_path),
        "stable_causal_fields": ["input", "where", "recipient", "task", "policy"],
        "commands": {
            "status": "abyss-machine typing status --json",
            "coverage": "abyss-machine typing coverage --json",
            "process": "abyss-machine typing process --json",
            "causal_context": "abyss-machine typing causal-context --json",
            "validate": "abyss-machine typing validate --json",
        },
        "contract": "Use typing coverage and causal-context to answer what was written, where it was written, to whom it was routed, and which task/context it belonged to.",
        "non_claim": "Typing bridge is committed-text evidence only; it is not raw keylogging and does not authorize automatic action.",
    }


def heartbeat_bridge_contract(
    *,
    heartbeats_agents_path: Path,
    latest_path: Path,
    validate_latest_path: Path,
    stable_fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "agent_entrypoint": str(heartbeats_agents_path),
        "latest": str(latest_path),
        "validate_latest": str(validate_latest_path),
        "stable_fields": list(stable_fields),
        "commands": {
            "pulse": "abyss-machine heartbeats pulse --json",
            "paths": "abyss-machine heartbeats paths --json",
            "validate": "abyss-machine heartbeats validate --json",
        },
        "contract": "Stack-side readers may consume heartbeat readmodel fields only after heartbeats validate proves the stable field set.",
        "non_claim": "Heartbeat bridge is evidence-only; it does not execute reactions, responses, browser diagnostics, model review, cleanup, or stack promotion.",
    }


def heartbeat_readiness(
    *,
    schema_prefix: str,
    latest: dict[str, Any],
    validation: dict[str, Any],
    stable_fields: tuple[str, ...],
    required_validate_checks: tuple[str, ...],
    latest_path: Path,
    validate_path: Path,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    missing_artifacts = [
        name for name in ("latest", "validate")
        if not isinstance(artifacts.get(name), dict)
    ]
    non_readonly_artifacts = [
        name for name, route in artifacts.items()
        if isinstance(route, dict) and route.get("write") is True
    ]
    missing_fields = [
        field for field in stable_fields
        if not isinstance(latest.get(field), dict)
    ]
    policy = latest.get("policy") if isinstance(latest.get("policy"), dict) else {}
    policy_ok = (
        policy.get("read_model") is True
        and policy.get("automatic_action") is False
        and policy.get("executes_reaction_commands") is False
        and policy.get("executes_response_commands") is False
        and policy.get("automatic_repo_write") is False
    )
    checks = validation.get("checks") if isinstance(validation.get("checks"), list) else []
    check_levels: dict[str, str] = {}
    for check in checks:
        if isinstance(check, dict) and check.get("key"):
            check_levels[str(check.get("key"))] = str(check.get("level"))
    missing_validate_checks = [
        key for key in required_validate_checks
        if check_levels.get(key) != "ok"
    ]
    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    validation_ok = (
        validation.get("ok") is True
        and int(summary.get("fails") or 0) == 0
        and not missing_validate_checks
    )
    ok = (
        latest.get("schema") == _schema(schema_prefix, "heartbeat_pulse_v1")
        and validation.get("schema") == _schema(schema_prefix, "heartbeats_validate_v1")
        and validation_ok
        and policy_ok
        and not missing_fields
        and not missing_artifacts
        and not non_readonly_artifacts
    )
    return {
        "schema": _schema(schema_prefix, "stack_bridge_heartbeat_readiness_v1"),
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "stable_fields": list(stable_fields),
        "missing_fields": missing_fields,
        "missing_artifacts": missing_artifacts,
        "non_readonly_artifacts": non_readonly_artifacts,
        "missing_validate_checks": missing_validate_checks,
        "validation_summary": summary,
        "policy": policy,
        "policy_ok": policy_ok,
        "latest_path": str(latest_path),
        "validate_path": str(validate_path),
        "contract": "read-only heartbeat handoff requires latest heartbeat fields plus green heartbeats validate checks",
    }


def observability_bridge_contract(*, latest_path: Path) -> dict[str, Any]:
    return {
        "latest": str(latest_path),
        "commands": {
            "observability": "abyss-machine stack-bridge observability --json",
        },
        "contract": "Use this read-only snapshot to verify abyss-stack Prometheus, Grafana, Loki, Alloy, PromQL, and LogQL availability from the host layer.",
        "non_claim": "Stack observability bridge reads host endpoints and stack container network probes only; it does not import, write, start, stop, or reconfigure abyss-stack.",
    }


def validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    export_summary: dict[str, Any] | None,
    paths: dict[str, Any],
) -> dict[str, Any]:
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, "stack_bridge_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="stack bridge handoff",
        extra={
            "export_summary": dict(export_summary) if isinstance(export_summary, dict) else None,
            "paths": dict(paths) if isinstance(paths, dict) else {},
            "policy": {
                "read_only": True,
                "future_safe": True,
                "does_not_mutate_stack": True,
                "evidence_first": True,
            },
        },
    )


def export_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root: Path,
    latest_path: Path,
    config_path: Path,
    config_exists: bool,
    manifest: dict[str, Any],
    paths: dict[str, Any],
    stack_roots: dict[str, Any],
    protected_roots: list[dict[str, Any]],
    bridges: dict[str, Any],
    artifacts: dict[str, Any],
    refs: dict[str, dict[str, Any]],
    required_missing: list[dict[str, Any]],
    schema_mismatches: list[dict[str, Any]],
    stack_command_keys: list[str],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "stack_bridge_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": not required_missing and not schema_mismatches,
        "status": "ready" if not required_missing and not schema_mismatches else "degraded",
        "root": str(root),
        "latest": str(latest_path),
        "manifest": {
            "path": str(config_path),
            "exists": config_exists,
            "schema": manifest.get("schema"),
            "config_error": manifest.get("config_error"),
        },
        "contract": manifest.get("contract"),
        "paths": paths,
        "stack_roots": stack_roots,
        "protected_roots": protected_roots,
        "bridges": bridges,
        "artifacts": artifacts,
        "refs": refs,
        "summary": {
            "layers": len(refs),
            "refs": sum(len(layer_refs) for layer_refs in refs.values()),
            "required_missing": len(required_missing),
            "schema_mismatches": len(schema_mismatches),
            "stack_bridge_commands": len(stack_command_keys),
            "named_bridges": sorted(bridges),
        },
        "issues": {
            "required_missing": required_missing,
            "schema_mismatches": schema_mismatches,
        },
        "commands": {
            "safe_read": manifest.get("first_commands"),
            "validation": manifest.get("validation_commands"),
            "mutation_gates": manifest.get("mutation_gates"),
            "bridge_keys": stack_command_keys,
            "manifest": manifest.get("commands") if isinstance(manifest.get("commands"), dict) else {},
        },
        "handoff_rules": [
            "Treat refs as evidence pointers; read the cited latest/history files before making claims.",
            "Use nervous recall packs for focused context retrieval instead of scanning every history file.",
            "Use synthesis candidates only as cited orientation; verify with facts/events/evals before acting.",
            "Use heartbeats only as a compact readmodel after heartbeats validate confirms bridge-stable fields.",
            "Do not write to abyss-stack or project roots from this host bridge.",
        ],
        "non_claims": manifest.get("non_claims"),
    }


def latest_read_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    latest_path: Path,
    data: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    if not data:
        return {
            "schema": _schema(schema_prefix, "stack_bridge_latest_read_v1"),
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "path": str(latest_path),
            "error": error or "missing",
        }
    result = dict(data)
    result["read_schema"] = _schema(schema_prefix, "stack_bridge_latest_read_v1")
    result["read_at"] = generated_at
    return result
