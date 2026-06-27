from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from . import validation_contracts


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    docs: dict[str, str],
    roots: dict[str, str],
    topology: dict[str, Any],
    changes: dict[str, Any],
    doctor: dict[str, Any],
    stack_bridge: dict[str, Any],
    mode: dict[str, Any],
    bridge_commands: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "topology_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "docs": docs,
        "roots": roots,
        "topology": topology,
        "changes": changes,
        "doctor": doctor,
        "stack_bridge": stack_bridge,
        "mode": mode,
        "bridge_commands": bridge_commands,
    }


def surface_states(
    *,
    cache_root: Path,
    runtime_root: Path,
    storage_root: Path,
    tmp_root: Path,
    runtime_dir: Path,
    uid: int,
    manifest_path: Path,
    stack_bridge_config_path: Path,
    stack_bridge_latest_path: Path,
    topology_latest_path: Path,
    change_index_path: Path,
    stack_user_source_root: Path,
) -> list[dict[str, Any]]:
    return [
        {
            "state": "source-config",
            "roots": ["/etc/abyss-machine"],
            "meaning": "Stable host policy, bridge contracts, and operator-readable machine law.",
            "mutation": "Edit only as host-layer work; prefer JSON validation and bridge updates in the same change.",
        },
        {
            "state": "host-fact",
            "roots": ["/var/lib/abyss-machine/*/latest.json"],
            "meaning": "Latest compact machine facts written by abyss-machine commands or timers.",
            "mutation": "Regenerate through the owning command; do not hand-edit latest facts.",
        },
        {
            "state": "history",
            "roots": ["/var/lib/abyss-machine/*/YYYY/MM/YYYY-MM-DD.jsonl"],
            "meaning": "Append-only evidence history for later agents and audits.",
            "mutation": "Append through the owning command; deletion needs explicit operator reason.",
        },
        {
            "state": "large-cache",
            "roots": [str(cache_root)],
            "meaning": "Regenerable host-owned caches that should not pressure the limited system root.",
            "mutation": "Clean only through policy-aware commands when storage pressure justifies it.",
        },
        {
            "state": "large-runtime",
            "roots": [str(runtime_root), str(storage_root)],
            "meaning": "Host-managed runtime and large mutable support data.",
            "mutation": "Use direct storage routes; no /work use and no symlink tails by default.",
        },
        {
            "state": "runtime",
            "roots": [str(runtime_dir), f"/run/user/{uid}/abyss-machine"],
            "meaning": "Ephemeral sockets, recordings, and live process state.",
            "mutation": "Treat as disposable live state, not durable evidence unless copied through an owning command.",
        },
        {
            "state": "bridge",
            "roots": [str(manifest_path), str(stack_bridge_config_path), str(stack_bridge_latest_path), str(topology_latest_path), str(change_index_path)],
            "meaning": "Machine-readable entry contracts for future abyss-stack and agents.",
            "mutation": "Keep schema, docs, commands, and validation aligned.",
        },
        {
            "state": "project-readonly",
            "roots": ["/srv/AbyssOS", str(stack_user_source_root), "/srv/abyss-stack"],
            "meaning": "Project source material. The host layer may read it for routing evidence only.",
            "mutation": "Do not mutate from abyss-machine unless the operator explicitly routes that work to the owning repo.",
        },
    ]


def status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    docs: dict[str, Any],
    roots: dict[str, Any],
    writable_roots: list[str],
    surface_states: list[dict[str, Any]],
    protected_roots: list[dict[str, Any]],
    stack_user_source_root: Path,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "topology_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "purpose": "Host-machine topology contract for future agents and abyss-stack consumers.",
        "paths": paths,
        "docs": docs,
        "roots": roots,
        "surface_states": surface_states,
        "write_policy": {
            "machine_owned_writable_roots": writable_roots,
            "forbidden_machine_owned_roots": ["/work", "/srv/work"],
            "project_roots_readonly_by_default": [
                "/srv/AbyssOS",
                "/srv/AbyssOS/abyss-stack",
                "/srv/abyss-stack",
                str(stack_user_source_root),
            ],
            "dependency_direction": "abyss-stack may consume abyss-machine; abyss-machine must not import or mutate abyss-stack.",
        },
        "protected_roots": protected_roots,
        "first_commands": [
            "abyss-machine enter --json",
            "abyss-machine topology --json",
            "abyss-machine topology validate --json",
            "abyss-machine topology audit --json",
            "abyss-machine bridge --json",
            "abyss-machine stack-bridge --json",
            "abyss-machine stack-bridge validate --json",
            "abyss-machine mode plan --json",
            "abyss-machine mode validate --json",
            "abyss-machine doctor --json",
            "abyss-machine changes status --json",
            "abyss-machine storage pressure --json",
            "abyss-machine nervous status --json",
        ],
        "non_claims": [
            "This topology does not redefine AoA, ToS, or abyss-stack ownership.",
            "This topology is a host-side bridge and routing contract, not a project-repo source of truth.",
            "Generated/latest host facts accelerate orientation but do not replace stronger owner repositories.",
        ],
    }


def index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    topology_root: Path,
    latest_path: Path,
    agent_entrypoint: Path,
    topology_doc_path: Path,
    roadmap_doc_path: Path,
    changelog_doc_path: Path,
    decisions_agents_path: Path,
    bridge_manifest_path: Path,
    topology_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "topology_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(topology_root),
        "latest": str(latest_path),
        "agent_entrypoint": str(agent_entrypoint),
        "topology_doc": str(topology_doc_path),
        "roadmap_doc": str(roadmap_doc_path),
        "changelog_doc": str(changelog_doc_path),
        "decisions_agents": str(decisions_agents_path),
        "bridge": str(bridge_manifest_path),
        "commands": {
            "enter": ["abyss-machine", "enter", "--json"],
            "topology": ["abyss-machine", "topology", "--json"],
            "topology_validate": ["abyss-machine", "topology", "validate", "--json"],
            "topology_audit": ["abyss-machine", "topology", "audit", "--json"],
            "stack_bridge": ["abyss-machine", "stack-bridge", "--json"],
            "stack_bridge_validate": ["abyss-machine", "stack-bridge", "validate", "--json"],
            "mode_plan": ["abyss-machine", "mode", "plan", "--json"],
            "mode_validate": ["abyss-machine", "mode", "validate", "--json"],
            "changes_status": ["abyss-machine", "changes", "status", "--json"],
            "changes_preflight": ["abyss-machine", "changes", "preflight", "--intent", "TEXT", "--surface", "SURFACE", "--json"],
            "graph": ["abyss-machine", "graph", "--json"],
            "graph_validate": ["abyss-machine", "graph", "validate", "--json"],
        },
        "latest_status": {
            "generated_at": topology_data.get("generated_at") if isinstance(topology_data, dict) else None,
            "ok": topology_data.get("ok") if isinstance(topology_data, dict) else None,
        },
    }


def validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: Iterable[Mapping[str, Any]],
    strict: bool,
) -> dict[str, Any]:
    check_items = [dict(item) for item in checks if isinstance(item, Mapping)]
    summary = validation_contracts.validation_summary(check_items)
    return {
        "schema": _schema(schema_prefix, "topology_validate_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0 and (not strict or summary["warnings"] == 0),
        "strict": strict,
        "summary": summary,
        "checks": check_items,
        "policy": {
            "read_only": True,
            "does_not_mutate_project_repos": True,
            "validator_scope": "host-machine topology, bridge, lifecycle, and path-boundary consistency",
        },
        "non_claims": [
            "This validator checks host-layer topology consistency; it is not a full system health benchmark.",
            "Warnings require operator judgment and may be acceptable during active work.",
        ],
    }


def under_forbidden_root(path: str, forbidden_roots: tuple[str, ...] = ("/work", "/srv/work")) -> str | None:
    candidate = path.rstrip("/")
    for forbidden in forbidden_roots:
        root = forbidden.rstrip("/")
        if candidate == root or candidate.startswith(root + "/"):
            return forbidden
    return None
