from __future__ import annotations

import collections
import datetime as dt
import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import ai_cpu_routing


WORKLOAD_CLASS_LEVELS = {
    "probe": 0,
    "light": 1,
    "medium": 2,
    "heavy": 3,
    "sustained": 4,
}


EVAL_SUITE_CLASSES = {
    "stt": "medium",
    "embeddings": "medium",
    "text": "heavy",
}

TOKEN_ACCOUNTING_CONTRACT = "abyss_token_accounting_v1"
TOKEN_ACCOUNTING_SCHEMA_VERSION = 1
TOKEN_ACCOUNTING_COUNT_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "context_tokens",
    "context_window_tokens",
)
TOKEN_ACCOUNTING_CONTEXT_FIELDS = {"context_tokens", "context_window_tokens"}


def resource_numeric_delta(after: Any, before: Any, digits: int = 6) -> float | None:
    if isinstance(after, bool) or isinstance(before, bool):
        return None
    if isinstance(after, (int, float)) and isinstance(before, (int, float)):
        return round(float(after) - float(before), digits)
    return None


def resource_profile_document(
    *,
    schema_prefix: str,
    version: str,
    before: dict[str, Any],
    after: dict[str, Any],
    scope: str,
    basis: str,
) -> dict[str, Any]:
    child_before = _nested_get(before, ["rusage", "children"]) or {}
    child_after = _nested_get(after, ["rusage", "children"]) or {}
    self_before = _nested_get(before, ["rusage", "self"]) or {}
    self_after = _nested_get(after, ["rusage", "self"]) or {}
    delta = {
        "mem_available_mib": resource_numeric_delta(
            _nested_get(after, ["memory", "mem_available_mib"]),
            _nested_get(before, ["memory", "mem_available_mib"]),
            1,
        ),
        "temperature_c_max": resource_numeric_delta(
            _nested_get(after, ["thermal", "temperature_c_max"]),
            _nested_get(before, ["thermal", "temperature_c_max"]),
            1,
        ),
        "battery_capacity_percent": resource_numeric_delta(
            _nested_get(after, ["battery", "capacity_percent"]),
            _nested_get(before, ["battery", "capacity_percent"]),
            0,
        ),
        "children_user_cpu_sec": resource_numeric_delta(child_after.get("user_cpu_sec"), child_before.get("user_cpu_sec")),
        "children_system_cpu_sec": resource_numeric_delta(child_after.get("system_cpu_sec"), child_before.get("system_cpu_sec")),
        "children_maxrss_kib": resource_numeric_delta(child_after.get("maxrss_kib"), child_before.get("maxrss_kib"), 0),
        "self_user_cpu_sec": resource_numeric_delta(self_after.get("user_cpu_sec"), self_before.get("user_cpu_sec")),
        "self_system_cpu_sec": resource_numeric_delta(self_after.get("system_cpu_sec"), self_before.get("system_cpu_sec")),
    }
    return {
        "schema": f"{schema_prefix}_ai_resource_profile_v1",
        "version": version,
        "scope": scope,
        "basis": basis,
        "facts_only": True,
        "before": before,
        "after": after,
        "delta": {key: value for key, value in delta.items() if value is not None},
        "non_claims": [
            "System snapshots are point-in-time context and are not exclusive attribution to this workload.",
            "Child rusage covers subprocesses launched by this command; warm user services are not included unless explicitly measured.",
        ],
    }


def token_accounting_privacy_flags() -> dict[str, bool]:
    return {
        "raw_text_logged": False,
        "prompt_text_logged": False,
        "stores_counts_only": True,
        "stores_refs": True,
    }


def token_accounting_contract_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root: Any,
    latest_path: Any,
    profiles_latest_path: Any,
    counts_latest_path: Any,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_ai_token_accounting_contract_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "contract": TOKEN_ACCOUNTING_CONTRACT,
        "contract_schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "fields": {
            "counts": list(TOKEN_ACCOUNTING_COUNT_FIELDS),
            "basis": ["provider_reported", "exact_tokenizer", "estimated", "unknown"],
            "identity": ["tokenizer_id", "model_id", "source_ref", "workload_ref", "session_ref"],
            "privacy": token_accounting_privacy_flags(),
        },
        "paths": {
            "root": str(root),
            "latest": str(latest_path),
            "profiles_latest": str(profiles_latest_path),
            "counts_latest": str(counts_latest_path),
        },
        "policy": {
            "exact_requires_model_tokenizer_match": True,
            "estimates_are_never_exact": True,
            "do_not_store_prompt_text": True,
            "host_layer_mutates_stack": False,
        },
        "commands": {
            "contract": "abyss-machine ai token-accounting contract --json",
            "profiles": "abyss-machine ai token-accounting profiles --json",
            "count": "abyss-machine ai token-accounting count --profile gemma4.spark --text 'hello' --json",
        },
    }


def token_accounting_profile_entry(name: str, profile: dict[str, Any], tokenizer: dict[str, Any]) -> dict[str, Any]:
    model_exists = bool(profile.get("local_exists"))
    exact_supported = bool(model_exists and tokenizer.get("tokenizer_exists"))
    configured_version = _nested_get(profile, ["runtime", "configured_version"])
    return {
        "profile": name,
        "status": "exact-ready" if exact_supported else "not-ready",
        "count_basis": "exact_tokenizer" if exact_supported else "unknown",
        "exact_supported": exact_supported,
        "model_id": profile.get("model_id"),
        "model_path": profile.get("local_path"),
        "model_exists": model_exists,
        "tokenizer_id": f"llama.cpp:{configured_version}:{name}" if exact_supported else None,
        "runtime": {
            "backend": profile.get("backend"),
            "configured_version": configured_version,
            "llama_cli": _nested_get(profile, ["runtime", "llama_cli"]),
            "llama_server": _nested_get(profile, ["runtime", "llama_server"]),
        },
        "tokenizer": tokenizer,
        "policy": {
            "stores_prompt_text": False,
            "exact_requires_this_model_path": True,
        },
    }


def token_accounting_tokenizer_candidates(profile: dict[str, Any]) -> list[Path]:
    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    roots: list[Path] = []
    for key in ("llama_cli", "llama_server"):
        raw = str(runtime.get(key) or "")
        if raw:
            path = Path(raw)
            roots.extend([path.parent, path.parent / "bin"])
    root_raw = str(runtime.get("root") or "")
    if root_raw:
        root = Path(root_raw)
        roots.extend([root, root / "bin"])
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        candidate = root / "llama-tokenize"
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def token_accounting_library_candidates(tokenizer: Path, profile: dict[str, Any]) -> list[Path]:
    runtime = profile.get("runtime") if isinstance(profile.get("runtime"), dict) else {}
    roots = [tokenizer.parent, tokenizer.parent.parent]
    root_raw = str(runtime.get("root") or "")
    if root_raw:
        root = Path(root_raw)
        roots.extend([root, root / "bin"])
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for child in (root / "lib64", root / "lib"):
            key = str(child)
            if key not in seen:
                seen.add(key)
                candidates.append(child)
    return candidates


def token_accounting_tokenizer_resolution(
    *,
    tokenizer: Path | None,
    candidate_paths: list[Path],
    library_paths: list[Path] | None = None,
) -> dict[str, Any]:
    return {
        "tokenizer_path": str(tokenizer) if tokenizer else None,
        "tokenizer_exists": bool(tokenizer),
        "candidate_paths": [str(path) for path in candidate_paths],
        "library_paths": [str(path) for path in (library_paths or [])],
    }


def token_accounting_count_command(profile: dict[str, Any]) -> list[str]:
    tokenizer = str(_nested_get(profile, ["tokenizer", "tokenizer_path"]) or "")
    model_path = str(profile.get("model_path") or "")
    return [
        tokenizer,
        "-m",
        model_path,
        "--stdin",
        "--ids",
        "--show-count",
        "--no-bos",
        "--log-disable",
    ]


def token_accounting_count_env_overlay(profile: dict[str, Any], existing_ld_library_path: str | None = None) -> dict[str, str]:
    library_paths = [str(path) for path in _nested_get(profile, ["tokenizer", "library_paths"]) or [] if path]
    if not library_paths:
        return {}
    return {
        "LD_LIBRARY_PATH": ":".join(library_paths + ([existing_ld_library_path] if existing_ld_library_path else [])),
    }


def token_accounting_count_execution_result(*, stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    total_tokens = token_accounting_parse_count(stdout or "")
    ok = returncode == 0 and total_tokens is not None
    return {
        "ok": ok,
        "total_tokens": total_tokens,
        "error": None if ok else (stderr.strip() or "tokenizer_output_missing_total_count"),
        "returncode": returncode,
        "stderr": stderr,
    }


def token_accounting_profiles_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    root: Any,
    profile_rows: dict[str, Any],
) -> dict[str, Any]:
    exact_ready = sum(1 for item in profile_rows.values() if isinstance(item, dict) and item.get("exact_supported"))
    return {
        "schema": f"{schema_prefix}_ai_token_accounting_profiles_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": exact_ready > 0,
        "contract": TOKEN_ACCOUNTING_CONTRACT,
        "contract_schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "root": str(root),
        "profiles": profile_rows,
        "summary": {
            "profiles": len(profile_rows),
            "exact_ready_profiles": exact_ready,
            "unknown_profiles": len(profile_rows) - exact_ready,
        },
        "non_claims": [
            "Exact tokenizer count is local tokenizer length only; it is not provider billing metadata.",
            "No prompt text is persisted by this surface.",
        ],
    }


def token_accounting_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+", text):
            return int(text)
    return None


def token_accounting_sanitize_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    sanitized: dict[str, Any] = {
        "schema": str(summary.get("schema") or TOKEN_ACCOUNTING_CONTRACT),
        "schema_version": token_accounting_int(summary.get("schema_version")) or TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "privacy": token_accounting_privacy_flags(),
        "basis_rule": str(
            summary.get("basis_rule")
            or "provider_reported and estimated counts are separate ledgers; estimates are never promoted to exact."
        ),
    }
    generator_version = token_accounting_int(summary.get("generator_version"))
    if generator_version is not None:
        sanitized["generator_version"] = generator_version
    for key in ("observed_event_count", "provider_reported_event_count", "estimated_event_count", "observation_count"):
        value = token_accounting_int(summary.get(key))
        if value is not None:
            sanitized[key] = value
    count_by_basis = summary.get("count_by_basis") if isinstance(summary.get("count_by_basis"), dict) else {}
    clean_counts: dict[str, int] = {}
    for basis, raw_value in count_by_basis.items():
        value = token_accounting_int(raw_value)
        if value is not None:
            clean_counts[str(basis)] = value
    sanitized["count_by_basis"] = dict(sorted(clean_counts.items()))
    totals_by_basis = summary.get("totals_by_basis") if isinstance(summary.get("totals_by_basis"), dict) else {}
    clean_totals: dict[str, dict[str, int]] = {}
    for basis, payload in totals_by_basis.items():
        if not isinstance(payload, dict):
            continue
        totals: dict[str, int] = {}
        for field in TOKEN_ACCOUNTING_COUNT_FIELDS:
            value = token_accounting_int(payload.get(field))
            if value is not None:
                totals[field] = value
        if totals:
            clean_totals[str(basis)] = totals
    sanitized["totals_by_basis"] = dict(sorted(clean_totals.items()))
    return sanitized


def token_accounting_summary_has_counts(summary: dict[str, Any]) -> bool:
    return bool(summary.get("count_by_basis")) or bool(summary.get("totals_by_basis"))


def token_accounting_context_pressure(summary: dict[str, Any]) -> dict[str, Any]:
    totals_by_basis = summary.get("totals_by_basis") if isinstance(summary.get("totals_by_basis"), dict) else {}
    for basis in ("provider_reported", "exact_tokenizer", "estimated"):
        totals = totals_by_basis.get(basis) if isinstance(totals_by_basis.get(basis), dict) else {}
        context_window = token_accounting_int(totals.get("context_window_tokens"))
        context_tokens = token_accounting_int(totals.get("context_tokens")) or token_accounting_int(totals.get("total_tokens"))
        if context_window and context_tokens is not None:
            return {
                "available": True,
                "basis": basis,
                "context_tokens": context_tokens,
                "context_window_tokens": context_window,
                "ratio": round(context_tokens / context_window, 6),
            }
    return {"available": False, "basis": None}


def token_accounting_merge_summaries(summaries: list[dict[str, Any]], scope: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "schema": TOKEN_ACCOUNTING_CONTRACT,
        "schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "scope": scope,
        "privacy": token_accounting_privacy_flags(),
        "observed_event_count": 0,
        "provider_reported_event_count": 0,
        "estimated_event_count": 0,
        "observation_count": 0,
        "count_by_basis": {},
        "totals_by_basis": {},
        "basis_rule": "provider_reported and estimated counts are separate ledgers; estimates are never promoted to exact.",
    }
    basis_counts: collections.Counter[str] = collections.Counter()
    totals_by_basis: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for summary in summaries:
        for key in ("observed_event_count", "provider_reported_event_count", "estimated_event_count", "observation_count"):
            merged[key] += token_accounting_int(summary.get(key)) or 0
        for basis, value in (summary.get("count_by_basis") or {}).items():
            count = token_accounting_int(value)
            if count is not None:
                basis_counts[str(basis)] += count
        for basis, payload in (summary.get("totals_by_basis") or {}).items():
            if not isinstance(payload, dict):
                continue
            for field in TOKEN_ACCOUNTING_COUNT_FIELDS:
                value = token_accounting_int(payload.get(field))
                if value is not None:
                    if field in TOKEN_ACCOUNTING_CONTEXT_FIELDS:
                        totals_by_basis[str(basis)][field] = max(totals_by_basis[str(basis)][field], value)
                    else:
                        totals_by_basis[str(basis)][field] += value
    merged["count_by_basis"] = dict(sorted(basis_counts.items()))
    merged["totals_by_basis"] = {
        basis: dict(sorted(values.items()))
        for basis, values in sorted(totals_by_basis.items())
        if values
    }
    return merged


def token_accounting_aoa_record_date(record: dict[str, Any]) -> str:
    display = record.get("display") if isinstance(record.get("display"), dict) else {}
    for value in (display.get("date"), record.get("updated_at"), record.get("session_label")):
        text = str(value or "")
        if re.match(r"^\d{4}-\d{2}-\d{2}", text):
            return text[:10]
    return ""


def token_accounting_aoa_record_sequence(record: dict[str, Any]) -> int | None:
    display = record.get("display") if isinstance(record.get("display"), dict) else {}
    value = token_accounting_int(display.get("sequence"))
    if value is not None:
        return value
    match = re.match(r"^\d{4}-\d{2}-\d{2}__(\d{3})__", str(record.get("session_label") or ""))
    return int(match.group(1)) if match else None


def token_accounting_aoa_select_records(
    sessions: list[dict[str, Any]],
    *,
    target: str,
    since: str | None,
    since_days: int | None,
    until: str | None,
    limit: int | None,
    today: dt.date | None = None,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    diagnostics: list[str] = []
    effective_since = since
    if not effective_since and since_days is not None:
        days = max(0, int(since_days))
        base_date = today or dt.datetime.now(dt.timezone.utc).date()
        effective_since = (base_date - dt.timedelta(days=days)).isoformat()
    ordered = sorted(
        sessions,
        key=lambda item: (
            token_accounting_aoa_record_date(item),
            token_accounting_aoa_record_sequence(item) or 0,
            str(item.get("updated_at") or ""),
            str(item.get("session_id") or ""),
        ),
    )
    target_text = str(target or "all").strip()
    if target_text == "latest":
        selected = sorted(sessions, key=lambda item: str(item.get("updated_at") or ""), reverse=True)[:1]
    elif target_text and target_text != "all":
        selected = [
            item for item in ordered
            if target_text in str(item.get("session_id") or "") or target_text in str(item.get("session_label") or "")
        ]
        if not selected:
            diagnostics.append("target_not_found")
    else:
        selected = ordered
    if effective_since:
        selected = [item for item in selected if token_accounting_aoa_record_date(item) >= effective_since]
    if until:
        selected = [item for item in selected if token_accounting_aoa_record_date(item) <= until]
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    return selected, diagnostics, effective_since


def token_accounting_aoa_planning(aggregate: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    totals_by_basis = aggregate.get("totals_by_basis") if isinstance(aggregate.get("totals_by_basis"), dict) else {}
    primary_basis = None
    primary_total = None
    for basis in ("provider_reported", "exact_tokenizer", "estimated"):
        totals = totals_by_basis.get(basis) if isinstance(totals_by_basis.get(basis), dict) else {}
        total = token_accounting_int(totals.get("total_tokens"))
        if total is not None:
            primary_basis = basis
            primary_total = total
            break
    missing = int(summary.get("missing_generated_token_accounting") or 0)
    estimated_only = int(summary.get("estimated_only_sessions") or 0)
    return {
        "source_kind": "aoa_session_memory_generated_summary",
        "usable_for_capacity_planning": primary_total is not None,
        "primary_basis": primary_basis,
        "primary_total_tokens": primary_total,
        "provider_total_tokens": token_accounting_int((totals_by_basis.get("provider_reported") or {}).get("total_tokens")) if isinstance(totals_by_basis.get("provider_reported"), dict) else None,
        "estimated_total_tokens": token_accounting_int((totals_by_basis.get("estimated") or {}).get("total_tokens")) if isinstance(totals_by_basis.get("estimated"), dict) else None,
        "context_pressure": token_accounting_context_pressure(aggregate),
        "quality": "missing_generated_ledgers" if missing else "estimated_only" if estimated_only else "provider_or_exact_available",
        "warnings": [
            item for item, active in (
                ("some sessions lack generated token accounting; run .aoa token-accounting-backfill in .aoa if needed", missing > 0),
                ("some sessions only have estimated counts; estimates are not exact provider usage", estimated_only > 0),
            )
            if active
        ],
        "non_claims": [
            "This is not provider billing metadata unless basis is provider_reported.",
            "This bridge does not read raw transcripts and does not validate .aoa index truth.",
        ],
    }


def token_accounting_aoa_summary_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    ok: bool,
    aoa_root: Any,
    target: str,
    since: str | None,
    until: str | None,
    limit: int | None,
    summary: dict[str, Any],
    aggregate: dict[str, Any],
    sessions: list[dict[str, Any]],
    diagnostics: list[str],
    session_registry_path: Any,
    session_registry_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_ai_token_accounting_aoa_session_memory_summary_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "contract": TOKEN_ACCOUNTING_CONTRACT,
        "contract_schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "source_kind": "aoa_session_memory_generated_summary",
        "source_truth_owner": "aoa-session-memory",
        "source_truth": "generated_token_summaries_only",
        "aoa_root": str(aoa_root),
        "target": target,
        "since": since,
        "until": until,
        "limit": limit,
        "summary": summary,
        "aggregate": aggregate,
        "planning": token_accounting_aoa_planning(aggregate, summary),
        "sessions": sessions,
        "diagnostics": sorted(set(str(item) for item in diagnostics if item)),
        "source_refs": {
            "session_registry": str(session_registry_path),
            "session_registry_sha256": session_registry_sha256,
        },
        "privacy": {
            **token_accounting_privacy_flags(),
            "session_titles_logged": False,
            "session_labels_logged": False,
            "session_paths_logged": False,
            "raw_paths_logged": False,
            "transcript_paths_logged": False,
        },
        "policy": {
            "raw_transcripts_read": False,
            "raw_blocks_read": False,
            "mutates_aoa": False,
            "mutates_aoa_indexes": False,
            "host_projection_only": True,
            "estimates_are_never_exact": True,
        },
        "non_claims": [
            "abyss-machine consumes .aoa generated token summaries for planning only; .aoa remains owner of raw, manifests, registry and indexes.",
            "Missing generated ledgers are reported as diagnostics instead of recomputing from raw in the host layer.",
            "Session titles, labels, transcript paths, raw paths and raw text are intentionally omitted from this projection.",
        ],
    }


def token_accounting_parse_count(stdout: str) -> int | None:
    match = re.search(r"Total number of tokens:\s*(\d+)", stdout)
    if match:
        return int(match.group(1))
    ids_match = re.search(r"\[([0-9,\s]+)\]", stdout)
    if not ids_match:
        return None
    ids = [item.strip() for item in ids_match.group(1).split(",") if item.strip()]
    return len(ids)


def token_accounting_count_error_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile_name: str,
    error: str,
    known_profiles: list[str] | None = None,
    profile_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_ai_token_accounting_count_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "contract": TOKEN_ACCOUNTING_CONTRACT,
        "contract_schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "profile": profile_name,
        "error": error,
    }
    if known_profiles is not None:
        data["known_profiles"] = sorted(known_profiles)
    if profile_status is not None:
        data["profile_status"] = profile_status
    return data


def token_accounting_count_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    profile_name: str,
    profile: dict[str, Any],
    input_bytes: bytes,
    elapsed_sec: float,
    total_tokens: int | None,
    ok: bool,
    error: str | None,
    returncode: int | None,
    stderr: str | None,
) -> dict[str, Any]:
    token_accounting: dict[str, Any] = {
        "schema": TOKEN_ACCOUNTING_CONTRACT,
        "schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "source_kind": "abyss_machine_llama_tokenize",
        "count_basis": "exact_tokenizer" if ok else "unknown",
        "tokenizer_id": profile.get("tokenizer_id"),
        "model_id": profile.get("model_id"),
        "privacy": token_accounting_privacy_flags(),
    }
    if total_tokens is not None:
        token_accounting["total_tokens"] = total_tokens
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_ai_token_accounting_count_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok,
        "contract": TOKEN_ACCOUNTING_CONTRACT,
        "contract_schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "profile": profile_name,
        "model_path": str(profile.get("model_path") or ""),
        "tokenizer_path": str(_nested_get(profile, ["tokenizer", "tokenizer_path"]) or ""),
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "input_bytes": len(input_bytes),
        "elapsed_sec": round(elapsed_sec, 6),
        "token_accounting": token_accounting,
        "command_shape": ["llama-tokenize", "-m", "<model_path>", "--stdin", "--ids", "--show-count", "--no-bos", "--log-disable"],
        "privacy": token_accounting_privacy_flags(),
        "policy": {
            "prompt_text_persisted": False,
            "token_ids_persisted": False,
            "stdout_persisted": False,
        },
    }
    if returncode is not None:
        data["tokenizer_returncode"] = returncode
    if stderr:
        data["tokenizer_stderr_tail"] = stderr[-1000:]
    if error:
        data["error"] = error
    return data


def cache_dir_path(cache_root: Path, label: str = "general") -> Path:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(label or "")).strip("-") or "general"
    return cache_root / clean


def model_cache_label(model_path: str | Path, prefix: str) -> str:
    resolved = str(Path(model_path))
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{Path(resolved).name}-{digest}"


def subprocess_env(
    base_env: dict[str, str],
    *,
    machine_cache_root: Path,
    ai_cache_root: Path,
    tmp_root: Path,
    openvino_cache_root: Path,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base_env)
    env.setdefault("OPENVINO_LOG_LEVEL", "2")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("XDG_CACHE_HOME", str(machine_cache_root / "home/dionysus/cache"))
    env.setdefault("HF_HOME", str(ai_cache_root / "huggingface"))
    env.setdefault("HUGGINGFACE_HUB_CACHE", str(ai_cache_root / "huggingface/hub"))
    env.setdefault("TRANSFORMERS_CACHE", str(ai_cache_root / "huggingface/transformers"))
    env.setdefault("PIP_CACHE_DIR", str(machine_cache_root / "home/dionysus/cache/pip"))
    env.setdefault("TORCH_HOME", str(ai_cache_root / "torch"))
    env.setdefault("TORCHINDUCTOR_CACHE_DIR", str(ai_cache_root / "torchinductor"))
    env.setdefault("TRITON_CACHE_DIR", str(ai_cache_root / "triton"))
    env.setdefault("NLTK_DATA", str(ai_cache_root / "nltk_data"))
    env.setdefault("SYCL_CACHE_DIR", str(machine_cache_root / "home/dionysus/cache/ze_intel_npu_cache"))
    env.setdefault("SYCL_CACHE_PERSISTENT", "1")
    env.setdefault("TMPDIR", str(tmp_root / "ai"))
    env.setdefault("ABYSS_OPENVINO_CACHE_DIR", str(openvino_cache_root))
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(machine_cache_root / "home/dionysus/cache/ms-playwright"))
    env.setdefault("PUPPETEER_CACHE_DIR", str(machine_cache_root / "home/dionysus/cache/puppeteer"))
    if extra:
        env.update(extra)
    return env


def model_dir_category(path: Path, filenames: list[str]) -> str | None:
    lowered_files = {name.lower() for name in filenames}
    lowered_parts = [part.lower() for part in path.parts]
    xml_files = [name for name in filenames if name.lower().endswith(".xml")]
    onnx_files = [name for name in filenames if name.lower().endswith(".onnx")]
    has_hf_config = "config.json" in lowered_files and any(
        name.endswith((".safetensors", ".bin")) or name in {"tokenizer.json", "generation_config.json"}
        for name in lowered_files
    )
    if xml_files and "stt" in lowered_parts and "whisper" in lowered_parts:
        return "stt_whisper_openvino"
    if xml_files and "ovms" in lowered_parts:
        return "ovms_openvino"
    if xml_files:
        return "openvino_ir"
    if onnx_files:
        return "onnx"
    if has_hf_config and "hf" in lowered_parts:
        return "huggingface_local"
    if has_hf_config:
        return "model_config"
    return None


def classify_model_dir(
    path: Path,
    root: Path,
    filenames: list[str],
    file_summary: dict[str, Any],
) -> dict[str, Any] | None:
    category = model_dir_category(path, filenames)
    if category is None:
        return None
    lowered_files = {name.lower() for name in filenames}
    xml_files = sorted([name for name in filenames if name.lower().endswith(".xml")])
    onnx_files = sorted([name for name in filenames if name.lower().endswith(".onnx")])
    try:
        relative = str(path.relative_to(root))
    except ValueError:
        relative = str(path)
    return {
        "kind": "directory",
        "category": category,
        "name": path.name,
        "path": str(path),
        "root": str(root),
        "relative_path": relative,
        "artifacts": {
            "xml": xml_files[:20],
            "onnx": onnx_files[:20],
            "has_config_json": "config.json" in lowered_files,
            "has_tokenizer_json": "tokenizer.json" in lowered_files,
            "has_safetensors": any(name.endswith(".safetensors") for name in lowered_files),
            "has_bin": any(name.endswith(".bin") for name in lowered_files),
        },
        "file_summary": file_summary,
        "read_only_source": True,
    }


def model_file_entry(file_path: Path, root: Path, size_bytes: int | None = None) -> dict[str, Any] | None:
    lowered = file_path.name.lower()
    if not lowered.endswith((".gguf", ".onnx")):
        return None
    try:
        relative_file = str(file_path.relative_to(root))
    except ValueError:
        relative_file = str(file_path)
    entry: dict[str, Any] = {
        "kind": "file",
        "category": "gguf" if lowered.endswith(".gguf") else "onnx_file",
        "name": file_path.name,
        "path": str(file_path),
        "root": str(root),
        "relative_path": relative_file,
        "read_only_source": True,
    }
    if size_bytes is not None:
        entry["size_bytes"] = size_bytes
    return entry


def inventory_summary(entries: list[dict[str, Any]], *, truncated: bool, max_entries: int, max_depth: int) -> dict[str, Any]:
    by_category: dict[str, int] = {}
    for item in entries:
        category = str(item.get("category"))
        by_category[category] = by_category.get(category, 0) + 1
    return {
        "entries": len(entries),
        "by_category": dict(sorted(by_category.items())),
        "truncated": truncated,
        "max_entries": max_entries,
        "max_depth": max_depth,
    }


def sort_inventory_entries(entries: list[dict[str, Any]], max_entries: int) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda item: (str(item.get("category")), str(item.get("relative_path"))))[:max_entries]


def build_models_inventory_document(
    *,
    entries: list[dict[str, Any]],
    roots: list[dict[str, Any]],
    errors: list[dict[str, str]],
    truncated: bool,
    max_entries: int,
    max_depth: int,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str,
) -> dict[str, Any]:
    sorted_entries = sort_inventory_entries(entries, max_entries)
    data: dict[str, Any] = {
        "schema": f"{schema_prefix}_ai_models_v1",
        "version": version,
        "generated_at": generated_at,
        "policy": {
            "read_only_stack_roots": True,
            "host_layer_mutates_stack": False,
        },
        "roots": roots,
        "summary": inventory_summary(sorted_entries, truncated=truncated, max_entries=max_entries, max_depth=max_depth),
        "entries": sorted_entries,
    }
    if errors:
        data["errors"] = errors
    return data


def text_tail(value: Any, limit: int) -> Any:
    if not isinstance(value, str):
        return value
    return value[-limit:]


def parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            return data if isinstance(data, dict) else None
        marker = stdout.rfind("\n{")
        if marker < 0:
            return None
        try:
            data = json.loads(stdout[marker + 1 :])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def llm_runtime_status(
    runtime: dict[str, Any],
    *,
    cli_exists: bool,
    server_exists: bool,
    version_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cli = Path(str(runtime.get("llama_cli") or ""))
    server = Path(str(runtime.get("llama_server") or ""))
    probe = version_probe if isinstance(version_probe, dict) else {}
    version = probe.get("stdout") if version_probe is not None else None
    return {
        "name": runtime.get("name") or "llama.cpp",
        "configured_version": runtime.get("version"),
        "release_url": runtime.get("release_url"),
        "backend": runtime.get("backend"),
        "root": runtime.get("root"),
        "llama_cli": str(cli),
        "llama_server": str(server),
        "llama_bench": str(runtime.get("llama_bench") or ""),
        "cli_exists": cli_exists,
        "server_exists": server_exists,
        "ok": cli_exists and server_exists,
        "version_stdout": version,
        "version_returncode": probe.get("returncode") if version_probe is not None else None,
        "version_stderr_tail": text_tail(probe.get("stderr"), 1000) if version_probe is not None else None,
        "source": runtime.get("source"),
    }


def openvino_smoke_script() -> str:
    return r'''
import json
import sys
import time
import numpy as np
import openvino as ov
from openvino import opset8 as ops

device = sys.argv[1]
started = time.perf_counter()
core = ov.Core()
p = ops.parameter([1, 16], ov.Type.f32, name="x")
c = ops.constant(np.ones((1, 16), dtype=np.float32))
y = ops.relu(ops.add(p, c))
model = ov.Model([y], [p], "abyss_ai_smoke")
compile_started = time.perf_counter()
compiled = core.compile_model(model, device)
compile_sec = time.perf_counter() - compile_started
payload = {"x": np.zeros((1, 16), dtype=np.float32)}
times = []
checksum = None
for _ in range(5):
    infer_started = time.perf_counter()
    result = compiled(payload)
    times.append(time.perf_counter() - infer_started)
    if checksum is None:
        checksum = float(np.sum(next(iter(result.values()))))
times_sorted = sorted(times)
data = {
    "device": device,
    "ok": True,
    "compile_sec": round(compile_sec, 6),
    "first_infer_sec": round(times[0], 6),
    "median_infer_sec": round(times_sorted[len(times_sorted) // 2], 6),
    "runs": len(times),
    "output_checksum": round(checksum, 6),
    "elapsed_sec": round(time.perf_counter() - started, 6),
}
print(json.dumps(data, sort_keys=False))
'''


def openvino_smoke_command(python: str, device: str) -> list[str]:
    return [python, "-c", openvino_smoke_script(), device]


def openvino_smoke_missing_python(device: str) -> dict[str, Any]:
    return {"device": device, "ok": False, "error": "abyss-openvino-python not found"}


def openvino_benchmark_requested_devices(devices: list[str] | None, benchmark_config: dict[str, Any]) -> list[str]:
    if devices:
        return [str(item) for item in devices]
    defaults = benchmark_config.get("default_devices", ["CPU", "GPU", "NPU"])
    return [str(item) for item in defaults]


def openvino_benchmark_device_timeout(device: str, benchmark_config: dict[str, Any]) -> float:
    per_device_timeout = float(benchmark_config.get("per_device_timeout_sec", 30))
    npu_timeout = float(benchmark_config.get("npu_timeout_sec", 60))
    return npu_timeout if str(device).upper() == "NPU" else per_device_timeout


def openvino_benchmark_skipped_device_result(device: str, reason: str = "device not available") -> dict[str, Any]:
    return {"device": str(device).upper(), "ok": False, "skipped": True, "reason": reason}


def openvino_benchmark_device_plan(
    *,
    requested_devices: list[str],
    available_devices: list[str],
    benchmark_config: dict[str, Any],
) -> list[dict[str, Any]]:
    available = {str(item) for item in available_devices}
    plan: list[dict[str, Any]] = []
    for requested in requested_devices:
        device = str(requested).upper()
        if device not in available:
            plan.append({
                "device": device,
                "available": False,
                "timeout_sec": None,
                "skip_result": openvino_benchmark_skipped_device_result(device),
            })
            continue
        plan.append({
            "device": device,
            "available": True,
            "timeout_sec": openvino_benchmark_device_timeout(device, benchmark_config),
            "skip_result": None,
        })
    return plan


def openvino_smoke_result(device: str, run_result: dict[str, Any], resource_profile: dict[str, Any]) -> dict[str, Any]:
    data = parse_json_stdout(str(run_result.get("stdout") or ""))
    if run_result.get("ok") and data is not None:
        data["returncode"] = run_result.get("returncode")
        data["stderr"] = run_result.get("stderr")
        data["resource_profile"] = resource_profile
        return data
    return {
        "device": device,
        "ok": False,
        "returncode": run_result.get("returncode"),
        "error": run_result.get("stderr") or run_result.get("stdout") or "OpenVINO smoke failed",
        "resource_profile": resource_profile,
    }


def openvino_benchmark_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    gate: dict[str, Any],
    requested_devices: list[str],
    available_devices: list[str],
    runtime: dict[str, Any],
    results: list[dict[str, Any]],
    resource_profile: dict[str, Any],
) -> dict[str, Any]:
    ok_count = sum(1 for item in results if item.get("ok"))
    return {
        "schema": f"{schema_prefix}_ai_benchmark_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok_count > 0,
        "benchmark": "openvino_synthetic_compile_infer_smoke",
        "declared_class": "probe",
        "policy_gate": gate,
        "requested_devices": requested_devices,
        "available_devices": available_devices,
        "openvino": {
            "ok": runtime.get("ok"),
            "openvino_version": runtime.get("openvino_version"),
            "python": runtime.get("python"),
        },
        "results": results,
        "resource_profile": resource_profile,
        "summary": {
            "devices_tested": len([item for item in results if not item.get("skipped")]),
            "devices_ok": ok_count,
            "devices_failed": len([item for item in results if not item.get("ok") and not item.get("skipped")]),
            "devices_skipped": len([item for item in results if item.get("skipped")]),
        },
    }


def embedding_eval_missing_model(model_dir: Path) -> dict[str, Any]:
    return {"suite": "embeddings", "ok": False, "model_dir": str(model_dir), "error": "model directory missing"}


def embedding_eval_missing_python() -> dict[str, Any]:
    return {"suite": "embeddings", "ok": False, "error": "abyss-openvino-python not found"}


def embedding_eval_script() -> str:
    return r'''
import json
import os
import sys
import time
import numpy as np

saved_stdout = os.dup(1)
os.dup2(2, 1)

def emit(data):
    os.write(saved_stdout, json.dumps(data, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")
    os.close(saved_stdout)

model_dir, device, cache_dir = sys.argv[1:4]
try:
    from transformers import AutoTokenizer
    from optimum.intel.openvino import OVModelForFeatureExtraction

    def last_token_pool(hidden, mask):
        left_padding = bool(mask[:, -1].sum() == mask.shape[0])
        if left_padding:
            return hidden[:, -1]
        sequence_lengths = mask.sum(axis=1).astype(np.int64) - 1
        return hidden[np.arange(hidden.shape[0]), sequence_lengths]

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    tokenizer.padding_side = "left"
    tokenizer_sec = time.perf_counter() - started
    load_started = time.perf_counter()
    model = OVModelForFeatureExtraction.from_pretrained(
        model_dir,
        device=device,
        ov_config={"CACHE_DIR": cache_dir},
        local_files_only=True,
    )
    load_sec = time.perf_counter() - load_started
    texts = [
        "Abyss host bridge test",
        "Abyss host bridge test",
        "локальный искусственный интеллект готов к работе",
    ]
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
    infer_started = time.perf_counter()
    outputs = model(**inputs)
    infer_sec = time.perf_counter() - infer_started
    hidden = outputs.last_hidden_state.detach().cpu().numpy()
    mask = inputs["attention_mask"].detach().cpu().numpy()
    pooled = last_token_pool(hidden, mask)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    normalized = pooled / np.maximum(norms, 1e-9)
    duplicate_cosine = float(np.dot(normalized[0], normalized[1]))
    cross_cosine = float(np.dot(normalized[0], normalized[2]))
    emit({
        "ok": bool(np.isfinite(pooled).all() and pooled.shape[0] == 3),
        "model_dir": model_dir,
        "device": device,
        "cache_dir": cache_dir,
        "tokenizer_sec": round(tokenizer_sec, 3),
        "load_sec": round(load_sec, 3),
        "infer_sec": round(infer_sec, 3),
        "pooling": "last_token",
        "padding_side": "left",
        "shape": list(pooled.shape),
        "duplicate_cosine": round(duplicate_cosine, 5),
        "cross_cosine": round(cross_cosine, 5),
    })
except Exception as exc:
    emit({"ok": False, "model_dir": model_dir, "device": device, "cache_dir": cache_dir, "error": repr(exc)})
    raise SystemExit(1)
'''


def embedding_eval_command(python: str, model_dir: Path, device: str, cache_dir: Path) -> list[str]:
    return [python, "-c", embedding_eval_script(), str(model_dir), device, str(cache_dir)]


def embedding_eval_result(run_result: dict[str, Any], resource_profile: dict[str, Any]) -> dict[str, Any]:
    data = parse_json_stdout(str(run_result.get("stdout") or ""))
    if data is None:
        data = {"ok": False, "error": "embedding eval returned invalid JSON", "stdout_tail": text_tail(run_result.get("stdout"), 1000)}
    data.update({
        "suite": "embeddings",
        "returncode": run_result.get("returncode"),
        "stderr_tail": text_tail(run_result.get("stderr"), 2000),
        "resource_profile": resource_profile,
    })
    data["ok"] = bool(data.get("ok") and data.get("duplicate_cosine", 0) > 0.95)
    return data


def text_eval_missing_model(model_dir: Path) -> dict[str, Any]:
    return {"suite": "text", "ok": False, "model_dir": str(model_dir), "error": "model directory missing"}


def text_eval_missing_python() -> dict[str, Any]:
    return {"suite": "text", "ok": False, "error": "abyss-openvino-python not found"}


def text_eval_script() -> str:
    return r'''
import json
import os
import sys
import time

saved_stdout = os.dup(1)
os.dup2(2, 1)

def emit(data):
    os.write(saved_stdout, json.dumps(data, ensure_ascii=False, sort_keys=False).encode("utf-8") + b"\n")
    os.close(saved_stdout)

model_dir, device, cache_dir, prompt = sys.argv[1:5]
try:
    import openvino_genai as ov_genai
    started = time.perf_counter()
    try:
        pipe = ov_genai.LLMPipeline(model_dir, device, {"CACHE_DIR": cache_dir})
    except TypeError:
        pipe = ov_genai.LLMPipeline(model_dir, device, CACHE_DIR=cache_dir)
    load_sec = time.perf_counter() - started
    generate_started = time.perf_counter()
    response = pipe.generate(prompt, max_new_tokens=8)
    generate_sec = time.perf_counter() - generate_started
    text = str(response).strip()
    emit({
        "ok": bool(text),
        "model_dir": model_dir,
        "device": device,
        "cache_dir": cache_dir,
        "prompt": prompt,
        "text": text,
        "load_sec": round(load_sec, 3),
        "generate_sec": round(generate_sec, 3),
        "chars": len(text),
    })
except Exception as exc:
    emit({"ok": False, "model_dir": model_dir, "device": device, "cache_dir": cache_dir, "prompt": prompt, "error": repr(exc)})
    raise SystemExit(1)
'''


def text_eval_command(python: str, model_dir: Path, device: str, cache_dir: Path, prompt: str) -> list[str]:
    return [python, "-c", text_eval_script(), str(model_dir), device, str(cache_dir), prompt]


def text_eval_result(run_result: dict[str, Any], resource_profile: dict[str, Any]) -> dict[str, Any]:
    data = parse_json_stdout(str(run_result.get("stdout") or ""))
    if data is None:
        data = {"ok": False, "error": "text eval returned invalid JSON", "stdout_tail": text_tail(run_result.get("stdout"), 1000)}
    data.update({
        "suite": "text",
        "returncode": run_result.get("returncode"),
        "stderr_tail": text_tail(run_result.get("stderr"), 3000),
        "resource_profile": resource_profile,
        "non_claims": [
            "This is a bounded executable-path smoke/eval, not a stack runtime promotion packet.",
            "abyss-stack runtime winner decisions still belong to its benchmark and promotion loop.",
        ],
    })
    data["ok"] = bool(data.get("ok"))
    return data


def stt_eval_normalize_text(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def stt_eval_text_similarity(reference: str, hypothesis: str) -> float:
    ref = stt_eval_normalize_text(reference)
    hyp = stt_eval_normalize_text(hypothesis)
    if not ref and not hyp:
        return 1.0
    if not ref or not hyp:
        return 0.0
    return round(difflib.SequenceMatcher(None, ref, hyp).ratio(), 4)


def stt_eval_profile_result(
    *,
    profile: str,
    reference_text: str,
    transcript: dict[str, Any],
    elapsed_sec: float,
    similarity_warn_below: float,
    resource_profile: dict[str, Any],
) -> dict[str, Any]:
    text = str(transcript.get("text", ""))
    similarity = stt_eval_text_similarity(reference_text, text)
    return {
        "profile": profile,
        "ok": bool(transcript.get("ok") and text.strip()),
        "elapsed_sec": elapsed_sec,
        "transcript_elapsed_sec": transcript.get("elapsed_sec") or transcript.get("client_elapsed_sec"),
        "text": text,
        "raw_text": transcript.get("raw_text"),
        "similarity": similarity,
        "similarity_warn_below": similarity_warn_below,
        "quality_warning": similarity < similarity_warn_below,
        "via": transcript.get("via"),
        "profile_selection": transcript.get("profile_selection"),
        "error": transcript.get("error"),
        "resource_profile": resource_profile,
    }


def stt_eval_result(
    *,
    reference_text: str,
    fixture: dict[str, Any],
    profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile_results = profiles or []
    data: dict[str, Any] = {
        "suite": "stt",
        "ok": any(item.get("ok") for item in profile_results),
        "reference_text": reference_text,
        "fixture": fixture,
        "profiles": profile_results,
        "non_claims": [
            "Synthetic TTS audio is a bounded executable-path check, not a human speech quality verdict.",
            "Use live microphone captures or stack-side trial packets for stronger STT quality claims.",
        ],
    }
    if not fixture.get("ok"):
        data["ok"] = False
        data["error"] = fixture.get("error") or "fixture generation failed"
    return data


def eval_suites_for_request(suite: str, eval_config: dict[str, Any] | None = None) -> list[str]:
    eval_config = eval_config if isinstance(eval_config, dict) else {}
    if suite == "quick":
        return [str(item) for item in eval_config.get("quick_suites", ["stt", "embeddings", "text"])]
    return [suite]


def eval_suite_declared_class(suite: str) -> str:
    return EVAL_SUITE_CLASSES.get(suite, "sustained")


def eval_unknown_suite_result(suite: str) -> dict[str, Any]:
    return {"suite": str(suite), "ok": False, "error": "unknown eval suite"}


def eval_suite_execution_plan(
    suites: list[str],
    known_suites: set[str] | None = None,
) -> list[dict[str, Any]]:
    known = known_suites if known_suites is not None else set(EVAL_SUITE_CLASSES)
    plan: list[dict[str, Any]] = []
    for suite in suites:
        item: dict[str, Any] = {"suite": str(suite), "known": str(suite) in known}
        if not item["known"]:
            item["result"] = eval_unknown_suite_result(str(suite))
        plan.append(item)
    return plan


def highest_workload_class(classes: list[str], class_levels: dict[str, int] | None = None) -> str:
    levels = class_levels if isinstance(class_levels, dict) else WORKLOAD_CLASS_LEVELS
    if not classes:
        return "probe"
    return max(classes, key=lambda name: levels.get(name, 99))


def policy_workload_route_level(policy: dict[str, Any]) -> tuple[int, str]:
    policy_class = str(policy.get("class") or "degraded")
    if not policy.get("ok"):
        return 0, "policy_not_ok"
    if policy_class in {"hot", "degraded"}:
        return 0, policy_class
    if policy_class == "battery_saver":
        return 1, policy_class
    if policy.get("can_run_heavy"):
        return 3, "can_run_heavy"
    if policy.get("can_run_routed_heavy"):
        return 2, "routed_heavy_requires_cpu_route"
    return 2, policy_class


def policy_gate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    declared_class: str,
    operation: str,
    policy: dict[str, Any],
    force: bool = False,
    class_levels: dict[str, int] | None = None,
) -> dict[str, Any]:
    current_level, basis = policy_workload_route_level(policy)
    levels = class_levels if isinstance(class_levels, dict) else WORKLOAD_CLASS_LEVELS
    required_level = levels.get(declared_class, 99)
    allowed = required_level <= current_level
    return {
        "schema": f"{schema_prefix}_ai_policy_gate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": allowed or force,
        "allowed": allowed,
        "forced": bool(force and not allowed),
        "operation": operation,
        "declared_class": declared_class,
        "required_level": required_level,
        "current_max_recommended_level": current_level,
        "route_basis": basis,
        "policy_class": policy.get("class"),
        "can_run_heavy": policy.get("can_run_heavy"),
        "can_run_routed_heavy": policy.get("can_run_routed_heavy"),
        "heavy_policy": policy.get("heavy_policy"),
        "reasons": policy.get("reasons", []),
        "force_hint": "rerun with --force to override host policy explicitly" if not allowed and not force else None,
    }


def workload_taxonomy_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    class_levels: dict[str, int] | None = None,
) -> dict[str, Any]:
    levels = class_levels if isinstance(class_levels, dict) else WORKLOAD_CLASS_LEVELS
    classes = [
        {
            "class": "probe",
            "level": levels["probe"],
            "description": "metadata, inventory, or tiny synthetic smoke checks",
            "route": "allowed in every machine mode; keep low frequency on battery",
        },
        {
            "class": "light",
            "level": levels["light"],
            "description": "short interactive AI work with bounded latency and low sustained pressure",
            "route": "allowed interactively; prefer CPU or already-warm services on battery saver",
        },
        {
            "class": "medium",
            "level": levels["medium"],
            "description": "model-backed work that may load/compile an accelerator graph or run a bounded eval",
            "route": "prefer AC balanced/performance; consult ai policy before battery use",
        },
        {
            "class": "heavy",
            "level": levels["heavy"],
            "description": "large model load/generation, long STT, or GPU/NPU work with visible thermal cost",
            "route": "require current ai policy can_run_heavy=true for unrestricted work; CPU-backed work may use can_run_routed_heavy only with the explicit ai cpu route",
        },
        {
            "class": "sustained",
            "level": levels["sustained"],
            "description": "long-running batches, conversions, training, or services that can shape the whole session",
            "route": "AC performance/ai mode only; stack-owned orchestration should make final routing decisions",
        },
    ]
    workloads = {
        "openvino.synthetic_smoke": {
            "class": "probe",
            "capability": "openvino",
            "command": "abyss-machine ai benchmark --quick --json",
            "known_metrics": ["compile_sec", "first_infer_sec", "median_infer_sec", "elapsed_sec"],
        },
        "stt.fast": {
            "class": "light",
            "capability": "stt",
            "command": "abyss-machine dictation transcribe AUDIO.wav --profile fast --json",
            "known_metrics": ["wall_sec", "transcript_elapsed_sec", "audio_sec", "similarity"],
        },
        "stt.quality": {
            "class": "medium",
            "capability": "stt",
            "command": "abyss-machine dictation transcribe AUDIO.wav --profile quality --json",
            "known_metrics": ["wall_sec", "transcript_elapsed_sec", "audio_sec", "similarity"],
        },
        "stt.long": {
            "class": "heavy",
            "capability": "stt",
            "command": "abyss-machine dictation transcribe AUDIO.wav --profile long --json",
            "known_metrics": ["wall_sec", "transcript_elapsed_sec", "audio_sec", "similarity"],
        },
        "embeddings.openvino.eval": {
            "class": "medium",
            "capability": "embeddings",
            "command": "abyss-machine ai eval --suite embeddings --json",
            "known_metrics": ["tokenizer_sec", "load_sec", "infer_sec", "component_sum_sec"],
        },
        "llm_text.openvino.eval": {
            "class": "heavy",
            "capability": "llm_text",
            "command": "abyss-machine ai eval --suite text --json",
            "known_metrics": ["load_sec", "generate_sec", "component_sum_sec", "chars"],
        },
        "llm_text.llama_cpp.resident_probe.gemma4_spark": {
            "class": "probe",
            "capability": "llm_text",
            "command": "abyss-gemma4-spark-resident audit --json",
            "known_metrics": ["elapsed_sec", "token_input_tokens", "token_output_tokens", "token_total_tokens", "token_total_per_sec"],
        },
        "tts.quality.eval": {
            "class": "heavy",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile quality --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "load_sec", "synth_sec", "text_chars", "sample_rate"],
        },
        "tts.quality_compact.eval": {
            "class": "heavy",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile quality-compact --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "load_sec", "synth_sec", "text_chars", "sample_rate"],
        },
        "tts.npu_fast_experimental.eval": {
            "class": "heavy",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile npu-fast-experimental --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "text_chars", "sample_rate"],
        },
        "tts.gpu_fast_experimental.eval": {
            "class": "heavy",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile gpu-fast-experimental --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "text_chars", "sample_rate"],
        },
        "tts.cpu_fast_experimental.eval": {
            "class": "heavy",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile cpu-fast-experimental --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "text_chars", "sample_rate"],
        },
        "tts.fallback.eval": {
            "class": "light",
            "capability": "tts",
            "command": "abyss-machine ai tts eval --profile fallback --json",
            "known_metrics": ["wall_sec", "audio_sec", "rtf", "text_chars", "sample_rate"],
        },
    }
    return {
        "schema": f"{schema_prefix}_ai_workload_taxonomy_v1",
        "version": version,
        "generated_at": generated_at,
        "classes": classes,
        "workloads": workloads,
        "policy": {
            "facts_only": True,
            "measurement_rule": "Only measured durations/results from abyss-machine eval/benchmark are written as statistics.",
            "non_claims": [
                "Class labels are host routing policy, not abyss-stack runtime promotion decisions.",
                "Unmeasured CPU, RAM, power, and token throughput fields are intentionally absent; token throughput appears only when source artifacts carry token evidence.",
            ],
        },
    }


def workload_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    taxonomy: dict[str, Any],
    refresh: Any,
    stats: dict[str, Any],
    policy: dict[str, Any],
    paths: dict[str, str],
    auto_refresh: dict[str, Any],
) -> dict[str, Any]:
    allowed_level, route_basis = policy_workload_route_level(policy)
    class_levels = {
        item["class"]: int(item["level"])
        for item in taxonomy.get("classes", [])
        if isinstance(item, dict)
    }
    routes: dict[str, Any] = {}
    workloads = taxonomy.get("workloads", {}) if isinstance(taxonomy.get("workloads"), dict) else {}
    for workload_id, workload in workloads.items():
        if not isinstance(workload, dict):
            continue
        declared = str(workload.get("class") or "unknown")
        level = class_levels.get(declared, 99)
        routes[str(workload_id)] = {
            "declared_class": declared,
            "recommended_now": level <= allowed_level,
            "route_basis": route_basis,
            "current_max_recommended_level": allowed_level,
            "command": workload.get("command"),
            "stats_group_hint": str(workload_id),
        }
    return {
        "schema": f"{schema_prefix}_ai_workload_status_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(stats.get("ok")),
        "paths": paths,
        "summary": stats.get("summary", {}),
        "current_policy": {
            "class": policy.get("class"),
            "can_run_heavy": policy.get("can_run_heavy"),
            "can_run_routed_heavy": policy.get("can_run_routed_heavy"),
            "heavy_policy": policy.get("heavy_policy"),
            "reasons": policy.get("reasons"),
        },
        "routing": {
            "current_max_recommended_level": allowed_level,
            "basis": route_basis,
            "workloads": routes,
        },
        "taxonomy": {
            "latest": paths.get("taxonomy"),
            "classes": taxonomy.get("classes", []),
        },
        "stats": {
            "latest": paths.get("stats_latest"),
            "groups": stats.get("groups", []),
        },
        "refresh": refresh,
        "auto_refresh": auto_refresh,
        "policy": {
            "facts_only": True,
            "stack_boundary": "This is host-side routing evidence; abyss-stack should consume it but keep stack-owned promotion decisions.",
        },
    }


def workload_numeric(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def workload_slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "unknown"


def workload_resource_metrics(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    delta = profile.get("delta", {}) if isinstance(profile.get("delta"), dict) else {}
    after = profile.get("after", {}) if isinstance(profile.get("after"), dict) else {}
    before = profile.get("before", {}) if isinstance(profile.get("before"), dict) else {}
    metrics: dict[str, Any] = {}
    mapping = {
        "resource_mem_available_delta_mib": delta.get("mem_available_mib"),
        "resource_temperature_c_max_delta": delta.get("temperature_c_max"),
        "resource_battery_capacity_delta_percent": delta.get("battery_capacity_percent"),
        "resource_children_user_cpu_sec": delta.get("children_user_cpu_sec"),
        "resource_children_system_cpu_sec": delta.get("children_system_cpu_sec"),
        "resource_children_maxrss_delta_kib": delta.get("children_maxrss_kib"),
        "resource_self_user_cpu_sec": delta.get("self_user_cpu_sec"),
        "resource_self_system_cpu_sec": delta.get("self_system_cpu_sec"),
        "resource_mem_available_after_mib": _nested_get(after, ["memory", "mem_available_mib"]),
        "resource_temperature_c_max_after": _nested_get(after, ["thermal", "temperature_c_max"]),
        "resource_battery_capacity_after_percent": _nested_get(after, ["battery", "capacity_percent"]),
        "resource_mem_available_before_mib": _nested_get(before, ["memory", "mem_available_mib"]),
        "resource_temperature_c_max_before": _nested_get(before, ["thermal", "temperature_c_max"]),
    }
    for key, value in mapping.items():
        numeric = workload_numeric(value)
        if numeric is not None:
            metrics[key] = numeric
    return metrics


def workload_token_int(value: Any) -> int | None:
    numeric = workload_numeric(value)
    if numeric is None or numeric < 0 or not float(numeric).is_integer():
        return None
    return int(numeric)


def workload_token_accounting(source: Any, *, duration_sec: float | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(source, dict):
        return {}, None
    usage = source.get("usage") if isinstance(source.get("usage"), dict) else {}
    token_payload = source.get("token_accounting") if isinstance(source.get("token_accounting"), dict) else {}
    payloads = [source, usage, token_payload]
    counts: dict[str, int] = {}
    mapping = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "total_tokens": ("total_tokens", "token_count", "tokens"),
        "cached_tokens": ("cached_tokens", "input_cached_tokens", "prompt_cached_tokens"),
        "reasoning_tokens": ("reasoning_tokens", "output_reasoning_tokens", "completion_reasoning_tokens"),
    }
    for field, keys in mapping.items():
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            for key in keys:
                value = workload_token_int(payload.get(key))
                if value is not None:
                    counts[field] = value
                    break
            if field in counts:
                break
    if "total_tokens" not in counts and "input_tokens" in counts and "output_tokens" in counts:
        counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
    if not counts:
        return {}, None
    count_basis = str(
        token_payload.get("count_basis")
        or source.get("count_basis")
        or ("provider_reported" if usage else "unknown")
    )
    metrics = {f"token_{field}": value for field, value in counts.items()}
    if duration_sec and duration_sec > 0 and counts.get("total_tokens") is not None:
        metrics["token_total_per_sec"] = round(counts["total_tokens"] / duration_sec, 6)
    accounting = {
        "schema": TOKEN_ACCOUNTING_CONTRACT,
        "schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "source_kind": str(token_payload.get("source_kind") or ("provider_usage" if usage else "workload_measurement")),
        "count_basis": count_basis,
        "privacy": token_accounting_privacy_flags(),
    }
    for field, value in counts.items():
        accounting[field] = value
    for key in ("model_id", "tokenizer_id"):
        value = token_payload.get(key) or source.get(key)
        if value:
            accounting[key] = value
    return metrics, accounting


def workload_component_sum(metrics: dict[str, Any], keys: list[str]) -> float | None:
    values = [workload_numeric(metrics.get(key)) for key in keys]
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean), 6)


def workload_record_id(parts: list[Any]) -> str:
    raw = "\0".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def workload_duration_band(seconds: float | None, config: dict[str, Any] | None = None) -> str | None:
    if seconds is None:
        return None
    config = config if isinstance(config, dict) else {}
    workload_config = config.get("workload", {}) if isinstance(config.get("workload"), dict) else {}
    bands = workload_config.get("duration_bands_sec", {}) if isinstance(workload_config.get("duration_bands_sec"), dict) else {}
    probe = float(bands.get("probe", 1.0))
    light = float(bands.get("light", 5.0))
    medium = float(bands.get("medium", 30.0))
    heavy = float(bands.get("heavy", 180.0))
    if seconds <= probe:
        return "probe"
    if seconds <= light:
        return "light"
    if seconds <= medium:
        return "medium"
    if seconds <= heavy:
        return "heavy"
    return "sustained"


def workload_base_record(
    *,
    schema_prefix: str,
    version: str,
    recorded_at: str,
    source: dict[str, Any],
    workload_id: str,
    workload_class: str,
    capability: str,
    operation: str,
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_ai_workload_measurement_v1",
        "version": version,
        "recorded_at": recorded_at,
        "source": source,
        "workload_id": workload_id,
        "declared_class": workload_class,
        "capability": capability,
        "operation": operation,
        "measurement_source": "abyss-machine",
        "facts_only": True,
    }


def workload_measurements_from_benchmark(
    data: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    recorded_at: str,
    benchmark_latest_path: str,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source = {
        "type": "benchmark",
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "path": benchmark_latest_path,
        "benchmark": data.get("benchmark"),
    }
    records: list[dict[str, Any]] = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        device = str(item.get("device") or "unknown").upper()
        workload_id = f"openvino.synthetic_smoke.{workload_slug(device)}"
        metrics = {
            key: item.get(key)
            for key in ("compile_sec", "first_infer_sec", "median_infer_sec", "elapsed_sec", "runs")
            if workload_numeric(item.get(key)) is not None
        }
        metrics.update(workload_resource_metrics(item.get("resource_profile")))
        measured_duration = workload_numeric(item.get("elapsed_sec"))
        token_metrics, token_accounting = workload_token_accounting(item, duration_sec=measured_duration)
        metrics.update(token_metrics)
        record = workload_base_record(
            schema_prefix=schema_prefix,
            version=version,
            recorded_at=recorded_at,
            source=source,
            workload_id=workload_id,
            workload_class="probe",
            capability="openvino",
            operation="synthetic_compile_infer_smoke",
        )
        record.update({
            "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, device]),
            "ok": bool(item.get("ok")),
            "device": device,
            "metrics": metrics,
            "measured_duration_sec": measured_duration,
            "resource_profile_scope": _nested_get(item, ["resource_profile", "scope"]),
            "error": item.get("error") or item.get("reason"),
        })
        if token_accounting:
            record["token_accounting"] = token_accounting
        record["duration_band"] = workload_duration_band(record.get("measured_duration_sec"), config)
        records.append(record)
    return records


def workload_measurements_from_eval(
    data: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    recorded_at: str,
    eval_latest_path: str,
    dictation_profile_defs: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source = {
        "type": "eval",
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "path": eval_latest_path,
        "requested_suite": data.get("requested_suite"),
    }
    records: list[dict[str, Any]] = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        suite = str(item.get("suite") or "unknown")
        if suite == "stt":
            fixture = item.get("fixture", {}) if isinstance(item.get("fixture"), dict) else {}
            audio_sec = workload_numeric(fixture.get("duration_sec"))
            for profile_result in item.get("profiles", []):
                if not isinstance(profile_result, dict):
                    continue
                profile = str(profile_result.get("profile") or "unknown")
                profile_info = dictation_profile_defs.get(profile, {}) if isinstance(dictation_profile_defs, dict) else {}
                workload_class = "light" if profile == "fast" else "heavy" if profile == "long" else "medium"
                workload_id = f"stt.{workload_slug(profile)}"
                metrics = {
                    "wall_sec": profile_result.get("elapsed_sec"),
                    "transcript_elapsed_sec": profile_result.get("transcript_elapsed_sec"),
                    "audio_sec": audio_sec,
                    "similarity": profile_result.get("similarity"),
                }
                metrics = {key: value for key, value in metrics.items() if workload_numeric(value) is not None}
                metrics.update(workload_resource_metrics(profile_result.get("resource_profile")))
                measured = workload_numeric(metrics.get("wall_sec"))
                token_metrics, token_accounting = workload_token_accounting(profile_result, duration_sec=measured)
                metrics.update(token_metrics)
                record = workload_base_record(
                    schema_prefix=schema_prefix,
                    version=version,
                    recorded_at=recorded_at,
                    source=source,
                    workload_id=workload_id,
                    workload_class=workload_class,
                    capability="stt",
                    operation="transcribe",
                )
                record.update({
                    "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, profile]),
                    "ok": bool(profile_result.get("ok")),
                    "profile": profile,
                    "device": profile_info.get("device"),
                    "model_dir": profile_info.get("model_dir"),
                    "metrics": metrics,
                    "measured_duration_sec": measured,
                    "resource_profile_scope": _nested_get(profile_result, ["resource_profile", "scope"]),
                    "quality": {
                        "similarity": profile_result.get("similarity"),
                        "quality_warning": profile_result.get("quality_warning"),
                        "basis": "synthetic fixture similarity" if profile_result.get("similarity") is not None else None,
                    },
                    "error": profile_result.get("error"),
                })
                if token_accounting:
                    record["token_accounting"] = token_accounting
                record["duration_band"] = workload_duration_band(measured, config)
                records.append(record)
        elif suite == "embeddings":
            metrics = {
                "tokenizer_sec": item.get("tokenizer_sec"),
                "load_sec": item.get("load_sec"),
                "infer_sec": item.get("infer_sec"),
                "duplicate_cosine": item.get("duplicate_cosine"),
                "cross_cosine": item.get("cross_cosine"),
            }
            metrics = {key: value for key, value in metrics.items() if workload_numeric(value) is not None}
            metrics.update(workload_resource_metrics(item.get("resource_profile")))
            component_sum = workload_component_sum(metrics, ["tokenizer_sec", "load_sec", "infer_sec"])
            if component_sum is not None:
                metrics["component_sum_sec"] = component_sum
            token_metrics, token_accounting = workload_token_accounting(item, duration_sec=component_sum)
            metrics.update(token_metrics)
            workload_id = "embeddings.openvino.eval"
            record = workload_base_record(
                schema_prefix=schema_prefix,
                version=version,
                recorded_at=recorded_at,
                source=source,
                workload_id=workload_id,
                workload_class="medium",
                capability="embeddings",
                operation="embedding_eval_batch",
            )
            record.update({
                "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, item.get("model_dir"), item.get("device")]),
                "ok": bool(item.get("ok")),
                "device": item.get("device"),
                "model_dir": item.get("model_dir"),
                "metrics": metrics,
                "measured_duration_sec": component_sum,
                "measured_duration_basis": "sum(tokenizer_sec,load_sec,infer_sec)" if component_sum is not None else None,
                "resource_profile_scope": _nested_get(item, ["resource_profile", "scope"]),
                "quality": {
                    "duplicate_cosine": item.get("duplicate_cosine"),
                    "basis": "duplicate embedding cosine" if item.get("duplicate_cosine") is not None else None,
                },
                "error": item.get("error"),
            })
            if token_accounting:
                record["token_accounting"] = token_accounting
            record["duration_band"] = workload_duration_band(component_sum, config)
            records.append(record)
        elif suite == "text":
            metrics = {
                "load_sec": item.get("load_sec"),
                "generate_sec": item.get("generate_sec"),
                "chars": item.get("chars"),
            }
            metrics = {key: value for key, value in metrics.items() if workload_numeric(value) is not None}
            metrics.update(workload_resource_metrics(item.get("resource_profile")))
            component_sum = workload_component_sum(metrics, ["load_sec", "generate_sec"])
            if component_sum is not None:
                metrics["component_sum_sec"] = component_sum
            token_metrics, token_accounting = workload_token_accounting(item, duration_sec=component_sum)
            metrics.update(token_metrics)
            workload_id = "llm_text.openvino.eval"
            record = workload_base_record(
                schema_prefix=schema_prefix,
                version=version,
                recorded_at=recorded_at,
                source=source,
                workload_id=workload_id,
                workload_class="heavy",
                capability="llm_text",
                operation="short_text_generation_eval",
            )
            record.update({
                "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, item.get("model_dir"), item.get("device")]),
                "ok": bool(item.get("ok")),
                "device": item.get("device"),
                "model_dir": item.get("model_dir"),
                "metrics": metrics,
                "measured_duration_sec": component_sum,
                "measured_duration_basis": "sum(load_sec,generate_sec)" if component_sum is not None else None,
                "resource_profile_scope": _nested_get(item, ["resource_profile", "scope"]),
                "quality": {
                    "non_empty_text": bool(str(item.get("text") or "").strip()),
                    "basis": "bounded smoke prompt produced non-empty text",
                },
                "error": item.get("error"),
            })
            if token_accounting:
                record["token_accounting"] = token_accounting
            record["duration_band"] = workload_duration_band(component_sum, config)
            records.append(record)
    return records


def workload_measurements_from_resident_audit(
    data: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    recorded_at: str,
    resident_audit_latest_path: str,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    generation = current.get("tiny_generation") if isinstance(current.get("tiny_generation"), dict) else {}
    if not generation:
        return []
    source = {
        "type": "llm_resident_audit",
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "path": resident_audit_latest_path,
        "profile": data.get("profile"),
    }
    elapsed_ms = workload_numeric(generation.get("elapsed_ms"))
    measured = round(elapsed_ms / 1000.0, 6) if elapsed_ms is not None else None
    metrics = {
        "elapsed_sec": measured,
        "max_tokens": generation.get("max_tokens"),
    }
    metrics = {key: value for key, value in metrics.items() if workload_numeric(value) is not None}
    token_metrics, token_accounting = workload_token_accounting(generation, duration_sec=measured)
    metrics.update(token_metrics)
    workload_id = "llm_text.llama_cpp.resident_probe.gemma4_spark"
    record = workload_base_record(
        schema_prefix=schema_prefix,
        version=version,
        recorded_at=recorded_at,
        source=source,
        workload_id=workload_id,
        workload_class="probe",
        capability="llm_text",
        operation="openai_compatible_tiny_generation",
    )
    http = generation.get("http") if isinstance(generation.get("http"), dict) else {}
    record.update({
        "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, data.get("profile")]),
        "ok": bool(generation.get("ok")),
        "profile": data.get("profile"),
        "model_id": _nested_get(generation, ["token_accounting", "model_id"]),
        "provider": _nested_get(generation, ["token_accounting", "provider"]),
        "metrics": metrics,
        "measured_duration_sec": measured,
        "measured_duration_basis": "resident tiny_generation elapsed_ms" if measured is not None else None,
        "quality": {
            "non_empty_text": bool(str(generation.get("content_excerpt") or "").strip()),
            "basis": "bounded resident liveness probe produced non-empty output",
        },
        "http": {
            "ok": http.get("ok"),
            "status": http.get("status"),
            "elapsed_sec": http.get("elapsed_sec"),
        },
        "error": generation.get("error") or http.get("error"),
    })
    if token_accounting:
        record["token_accounting"] = token_accounting
    record["duration_band"] = workload_duration_band(measured, config)
    return [record]


def workload_measurements_from_tts_eval(
    data: dict[str, Any],
    *,
    schema_prefix: str,
    version: str,
    recorded_at: str,
    tts_eval_latest_path: str,
    class_levels: dict[str, int] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source = {
        "type": "tts_eval",
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "path": tts_eval_latest_path,
        "profile": data.get("profile"),
    }
    levels = class_levels if isinstance(class_levels, dict) else WORKLOAD_CLASS_LEVELS
    profile = str(data.get("profile") or "unknown")
    result = data.get("result", {}) if isinstance(data.get("result"), dict) else {}
    profile_status = result.get("profile_status", {}) if isinstance(result.get("profile_status"), dict) else {}
    audio = result.get("audio", {}) if isinstance(result.get("audio"), dict) else {}
    declared = str(data.get("declared_class") or result.get("declared_class") or "heavy")
    if declared not in levels:
        declared = "heavy"
    metrics = {
        "wall_sec": result.get("wall_sec"),
        "audio_sec": audio.get("duration_sec"),
        "rtf": result.get("rtf"),
        "text_chars": result.get("text_chars"),
        "sample_rate": audio.get("sample_rate"),
    }
    subprocess_data = result.get("subprocess", {}) if isinstance(result.get("subprocess"), dict) else {}
    for key in ("load_sec", "synth_sec", "samples"):
        if workload_numeric(subprocess_data.get(key)) is not None:
            metrics[key] = subprocess_data.get(key)
    server_data = result.get("server", {}) if isinstance(result.get("server"), dict) else {}
    if workload_numeric(server_data.get("server_load_sec")) is not None:
        metrics["server_load_sec"] = server_data.get("server_load_sec")
    for key in ("synth_sec", "samples"):
        if workload_numeric(server_data.get(key)) is not None:
            metrics[key] = server_data.get(key)
    metrics = {key: value for key, value in metrics.items() if workload_numeric(value) is not None}
    metrics.update(workload_resource_metrics(result.get("resource_profile")))
    measured = workload_numeric(metrics.get("wall_sec"))
    token_metrics, token_accounting = workload_token_accounting(result, duration_sec=measured)
    metrics.update(token_metrics)
    workload_id = f"tts.{workload_slug(profile)}.eval"
    record = workload_base_record(
        schema_prefix=schema_prefix,
        version=version,
        recorded_at=recorded_at,
        source=source,
        workload_id=workload_id,
        workload_class=declared,
        capability="tts",
        operation="speech_synthesis_eval",
    )
    record.update({
        "record_id": workload_record_id([source.get("type"), source.get("generated_at"), workload_id, profile, result.get("output")]),
        "ok": bool(data.get("ok")),
        "profile": profile,
        "device": result.get("device"),
        "model_dir": _nested_get(profile_status, ["model", "path"]),
        "metrics": metrics,
        "measured_duration_sec": measured,
        "measured_duration_basis": "wall_sec" if measured is not None else None,
        "resource_profile_scope": _nested_get(result, ["resource_profile", "scope"]),
        "quality": {
            "audio_exists": audio.get("exists"),
            "basis": "WAV generated and duration measured" if audio.get("duration_sec") is not None else "runtime/error only",
        },
        "error": result.get("error") or data.get("summary", {}).get("error"),
    })
    if token_accounting:
        record["token_accounting"] = token_accounting
    record["duration_band"] = workload_duration_band(measured, config)
    return [record]


def workload_metric_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "avg": round(sum(values) / len(values), 6),
        "latest": round(values[-1], 6),
    }


def workload_stats_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    records: list[dict[str, Any]],
    config: dict[str, Any],
    runs_daily_glob: str,
    latest_path: str,
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        workload_id = str(record.get("workload_id") or "unknown")
        device = str(record.get("device") or "")
        profile = str(record.get("profile") or "")
        group_key = "|".join([workload_id, device, profile])
        group = groups.setdefault(group_key, {
            "workload_id": workload_id,
            "device": record.get("device"),
            "profile": record.get("profile"),
            "declared_class": record.get("declared_class"),
            "capability": record.get("capability"),
            "operation": record.get("operation"),
            "resource_profile_scope": record.get("resource_profile_scope"),
            "count": 0,
            "ok_count": 0,
            "failed_count": 0,
            "first_seen_at": record.get("source", {}).get("generated_at"),
            "latest_seen_at": record.get("source", {}).get("generated_at"),
            "_metrics": {},
            "_latest_duration": None,
        })
        group["count"] = int(group["count"]) + 1
        if record.get("ok"):
            group["ok_count"] = int(group["ok_count"]) + 1
        else:
            group["failed_count"] = int(group["failed_count"]) + 1
        source_at = record.get("source", {}).get("generated_at")
        if source_at:
            group["latest_seen_at"] = source_at
        if record.get("resource_profile_scope"):
            group["resource_profile_scope"] = record.get("resource_profile_scope")
        measured = workload_numeric(record.get("measured_duration_sec"))
        if measured is not None:
            group["_latest_duration"] = measured
        metrics = record.get("metrics", {}) if isinstance(record.get("metrics"), dict) else {}
        for key, value in metrics.items():
            numeric = workload_numeric(value)
            if numeric is None:
                continue
            group["_metrics"].setdefault(key, []).append(numeric)

    aggregated: list[dict[str, Any]] = []
    for group in groups.values():
        metric_values = group.pop("_metrics")
        latest_duration = group.pop("_latest_duration")
        group["success_rate"] = round(float(group["ok_count"]) / float(group["count"]), 4) if group["count"] else None
        group["metrics"] = {
            key: workload_metric_stats(values)
            for key, values in sorted(metric_values.items())
        }
        group["latest_duration_band"] = workload_duration_band(latest_duration, config)
        group["latest_duration_band_basis"] = "measured_duration_sec" if latest_duration is not None else None
        group["evidence"] = "measured" if group["count"] else "none"
        aggregated.append(group)

    aggregated.sort(key=lambda item: (str(item.get("declared_class")), str(item.get("workload_id")), str(item.get("device"))))
    by_class: dict[str, int] = {}
    by_capability: dict[str, int] = {}
    for group in aggregated:
        klass = str(group.get("declared_class") or "unknown")
        capability = str(group.get("capability") or "unknown")
        by_class[klass] = by_class.get(klass, 0) + int(group.get("count") or 0)
        by_capability[capability] = by_capability.get(capability, 0) + int(group.get("count") or 0)
    return {
        "schema": f"{schema_prefix}_ai_workload_stats_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "summary": {
            "records": len(records),
            "groups": len(aggregated),
            "by_declared_class": dict(sorted(by_class.items())),
            "by_capability": dict(sorted(by_capability.items())),
        },
        "groups": aggregated,
        "paths": {
            "runs_daily_glob": runs_daily_glob,
            "latest": latest_path,
        },
        "policy": {
            "facts_only": True,
            "absent_metrics_mean_unmeasured": True,
        },
    }


def workload_refresh_probe_plan(
    *,
    config: dict[str, Any],
    policy: dict[str, Any],
    run_probe: bool | None = None,
) -> dict[str, Any]:
    workload_config = config.get("workload", {}) if isinstance(config.get("workload"), dict) else {}
    auto = workload_config.get("auto_refresh", {}) if isinstance(workload_config.get("auto_refresh"), dict) else {}
    policy_class = str(policy.get("class") or "degraded")
    should_run_probe = bool(auto.get("run_quick_benchmark", True)) if run_probe is None else bool(run_probe)
    skip_reasons: list[str] = []
    if should_run_probe:
        if policy_class == "degraded":
            skip_reasons.append("policy_degraded")
        if policy_class == "hot" and not bool(auto.get("allow_when_hot", False)):
            skip_reasons.append("policy_hot")
        if policy_class == "battery_saver" and not bool(auto.get("allow_on_battery", False)):
            skip_reasons.append("battery_saver")
    return {
        "quick_benchmark_requested": should_run_probe,
        "quick_benchmark_skip_reasons": skip_reasons,
    }


def workload_refresh_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    policy: dict[str, Any],
    probe_plan: dict[str, Any],
    benchmark_result: dict[str, Any] | None,
    refresh: dict[str, Any],
    stats: dict[str, Any],
    stats_latest_path: str,
) -> dict[str, Any]:
    benchmark_summary = benchmark_result.get("summary") if isinstance(benchmark_result, dict) else {}
    if not isinstance(benchmark_summary, dict):
        benchmark_summary = {}
    benchmark_devices_tested = int(benchmark_summary.get("devices_tested") or 0)
    benchmark_devices_failed = int(benchmark_summary.get("devices_failed") or 0)
    benchmark_devices_skipped = int(benchmark_summary.get("devices_skipped") or 0)
    benchmark_nonfatal_skip = bool(
        benchmark_result is not None
        and not benchmark_result.get("ok")
        and benchmark_devices_tested == 0
        and benchmark_devices_failed == 0
        and benchmark_devices_skipped > 0
    )
    benchmark_ok_for_refresh = bool(
        benchmark_result is None
        or benchmark_result.get("ok")
        or benchmark_nonfatal_skip
    )
    return {
        "schema": f"{schema_prefix}_ai_workload_refresh_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(refresh.get("ok")) and bool(stats.get("ok")) and benchmark_ok_for_refresh,
        "policy": {
            "class": policy.get("class"),
            "can_run_heavy": policy.get("can_run_heavy"),
            "reasons": policy.get("reasons"),
        },
        "actions": {
            "quick_benchmark_requested": bool(probe_plan.get("quick_benchmark_requested")),
            "quick_benchmark_ran": benchmark_result is not None,
            "quick_benchmark_skip_reasons": probe_plan.get("quick_benchmark_skip_reasons", []),
            "quick_benchmark_nonfatal_skip": benchmark_nonfatal_skip,
            "latest_refresh": refresh,
        },
        "benchmark": {
            "ok": benchmark_result.get("ok"),
            "summary": benchmark_result.get("summary"),
            "generated_at": benchmark_result.get("generated_at"),
            "nonfatal_for_refresh": benchmark_nonfatal_skip,
        } if benchmark_result is not None else None,
        "stats": {
            "latest": stats_latest_path,
            "summary": stats.get("summary"),
        },
        "policy_notes": [
            "Automatic refresh may run probe-class quick benchmarks only.",
            "Automatic refresh never runs real eval suites or heavy model workloads.",
        ],
    }


def policy_denied_result(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    command: str,
    requested_suite: str,
    suites: list[str],
    gate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_ai_policy_denied_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": False,
        "policy_denied": True,
        "command": command,
        "requested_suite": requested_suite,
        "suites": suites,
        "declared_class": gate.get("declared_class"),
        "required_level": gate.get("required_level"),
        "current_max_recommended_level": gate.get("current_max_recommended_level"),
        "policy_class": gate.get("policy_class"),
        "can_run_heavy": gate.get("can_run_heavy"),
        "can_run_routed_heavy": gate.get("can_run_routed_heavy"),
        "heavy_policy": gate.get("heavy_policy"),
        "reasons": gate.get("reasons"),
        "force_hint": gate.get("force_hint"),
        "policy_gate": gate,
        "non_claims": [
            "Denied commands do not update latest eval results.",
            "Use --force only for explicit operator-controlled validation.",
        ],
    }


def eval_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    requested_suite: str,
    declared_class: str,
    policy_gate: dict[str, Any],
    results: list[dict[str, Any]],
    resource_profile: dict[str, Any],
    openvino_cache_root: Any,
) -> dict[str, Any]:
    ok_count = sum(1 for item in results if item.get("ok"))
    return {
        "schema": f"{schema_prefix}_ai_eval_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": ok_count == len(results) and bool(results),
        "requested_suite": requested_suite,
        "declared_class": declared_class,
        "policy_gate": policy_gate,
        "results": results,
        "resource_profile": resource_profile,
        "summary": {
            "suites": len(results),
            "suites_ok": ok_count,
            "suites_failed": len(results) - ok_count,
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "openvino_cache_root": str(openvino_cache_root),
            "non_claim": "Host evals are bridge evidence, not abyss-stack promotion verdicts.",
        },
    }


def llm_profile_status(
    *,
    family_name: str,
    profile_name: str,
    profile: dict[str, Any],
    runtime: dict[str, Any],
    local_path: Path,
    local_exists: bool,
    local_size_bytes: int | None,
    mmproj_path: Path | None,
    mmproj_exists: bool,
    mmproj_size_bytes: int | None,
    storage_protection: dict[str, Any],
    under_host_cache: bool,
) -> dict[str, Any]:
    status = "ready" if local_exists and runtime.get("ok") else "model-missing" if not local_exists else "runtime-missing"
    command_base = [str(runtime.get("llama_cli") or "llama-cli"), "-m", str(local_path)]
    if profile.get("gpu_layers") is not None:
        command_base += ["-ngl", str(profile.get("gpu_layers"))]
    if profile.get("context_size") is not None:
        command_base += ["-c", str(profile.get("context_size"))]
    data = {
        "family": family_name,
        "profile": profile_name,
        "status": status,
        "role": profile.get("role"),
        "backend": "llama.cpp",
        "model_id": profile.get("model_id"),
        "revision": profile.get("revision"),
        "hf_file": profile.get("hf_file"),
        "quant": profile.get("quant"),
        "declared_class": profile.get("declared_class"),
        "warm_policy": profile.get("warm_policy"),
        "local_path": str(local_path),
        "local_exists": local_exists,
        "size_bytes": local_size_bytes,
        "mmproj": {
            "hf_file": profile.get("mmproj_file"),
            "path": str(mmproj_path) if mmproj_path else None,
            "exists": mmproj_exists,
            "size_bytes": mmproj_size_bytes,
            "optional_for_text": True,
        },
        "runtime": {
            "ok": runtime.get("ok"),
            "llama_cli": runtime.get("llama_cli"),
            "llama_server": runtime.get("llama_server"),
            "configured_version": runtime.get("configured_version"),
            "version_stdout": runtime.get("version_stdout"),
        },
        "launch": {
            "cli_smoke": command_base + ["-n", "64", "-p", "\u041e\u0442\u0432\u0435\u0442\u044c \u043e\u0434\u043d\u0438\u043c \u0441\u043b\u043e\u0432\u043e\u043c: \u0433\u043e\u0442\u043e\u0432?"],
            "server_base": [
                str(runtime.get("llama_server") or "llama-server"),
                "-m", str(local_path),
                "-ngl", str(profile.get("gpu_layers", 99)),
                "-c", str(profile.get("context_size", 8192)),
                "--host", "127.0.0.1",
            ],
            "hf_download": [
                "hf", "download", str(profile.get("model_id") or ""),
                "--include", str(profile.get("hf_file") or ""),
                "--local-dir", str(local_path.parent),
            ],
        },
        "storage": {
            "protection": storage_protection,
            "under_host_cache": under_host_cache,
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "profile_is_candidate_until_measured": True,
        },
    }
    for optional_key in ("max_context_size", "server", "lazy_load"):
        if optional_key in profile:
            data[optional_key] = profile.get(optional_key)
    return data


def llm_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    def ref(key: str) -> Any:
        return refs.get(key)

    runtime = config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
    families = config.get("families") if isinstance(config.get("families"), dict) else {}
    return {
        "schema": f"{schema_prefix}_ai_llm_paths_v1",
        "version": version,
        "generated_at": generated_at,
        "root": ref("AI_LLM_ROOT"),
        "agent_entrypoint": ref("AI_LLM_AGENTS_PATH"),
        "config": ref("AI_CONFIG_PATH"),
        "registry": {
            "root": ref("AI_LLM_REGISTRY_ROOT"),
            "latest": ref("AI_LLM_REGISTRY_LATEST_PATH"),
            "today": ref("AI_LLM_REGISTRY_TODAY_PATH"),
            "daily_glob": ref("AI_LLM_REGISTRY_DAILY_GLOB"),
        },
        "validate": {
            "root": ref("AI_LLM_VALIDATE_ROOT"),
            "latest": ref("AI_LLM_VALIDATE_LATEST_PATH"),
        },
        "resident": {
            "profile": "gemma4.spark",
            "root": ref("AI_LLM_RESIDENT_ROOT"),
            "controller": ref("AI_LLM_RESIDENT_CONTROLLER"),
            "status_latest": ref("AI_LLM_RESIDENT_STATUS_LATEST_PATH"),
            "monitor_latest": ref("AI_LLM_RESIDENT_MONITOR_LATEST_PATH"),
            "digest_latest": ref("AI_LLM_RESIDENT_DIGEST_LATEST_PATH"),
            "jobs_root": ref("AI_LLM_RESIDENT_JOBS_ROOT"),
            "jobs_latest": ref("AI_LLM_RESIDENT_JOBS_LATEST_PATH"),
            "micro_latest": ref("AI_LLM_RESIDENT_MICRO_LATEST_PATH"),
            "jobs_validate_latest": ref("AI_LLM_RESIDENT_JOBS_VALIDATE_LATEST_PATH"),
            "candidates_latest": ref("AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH"),
            "candidates_validate_latest": ref("AI_LLM_RESIDENT_CANDIDATES_VALIDATE_LATEST_PATH"),
            "evals_latest": ref("AI_LLM_RESIDENT_EVALS_LATEST_PATH"),
            "evals_validate_latest": ref("AI_LLM_RESIDENT_EVALS_VALIDATE_LATEST_PATH"),
            "job_names": list(ref("AI_LLM_RESIDENT_JOB_NAMES") or []),
        },
        "workhorse": {
            "profile": "gemma4.workhorse",
            "root": ref("AI_LLM_WORKHORSE_ROOT"),
            "controller": ref("AI_LLM_WORKHORSE_CONTROLLER"),
            "preflight_latest": ref("AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH"),
            "pack_latest": ref("AI_LLM_WORKHORSE_PACK_LATEST_PATH"),
            "review_latest": ref("AI_LLM_WORKHORSE_REVIEW_LATEST_PATH"),
            "validate_latest": ref("AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH"),
            "resident_candidate_input": ref("AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH"),
            "mode": "non_resident_on_demand_review_harness",
            "policy": {
                "starts_llama_server": False,
                "resident_service": False,
                "default_model_execution": False,
                "action_execution": False,
            },
        },
        "runtime": {
            "root": str(runtime.get("root") or "/srv/abyss-machine/runtimes/llama.cpp"),
            "llama_cli": str(runtime.get("llama_cli") or ""),
            "llama_server": str(runtime.get("llama_server") or ""),
        },
        "model_roots": {
            "base": str(config.get("model_root_base") or ref("AI_CACHE_ROOT")),
            "families": {
                family: str(family_cfg.get("local_root") or "")
                for family, family_cfg in families.items()
                if isinstance(family_cfg, dict)
            },
        },
        "commands": {
            "paths": "abyss-machine ai llm paths --json",
            "registry": "abyss-machine ai llm registry --json",
            "latest": "abyss-machine ai llm latest --json",
            "validate": "abyss-machine ai llm validate --json",
            "resident_paths": "abyss-machine ai llm resident paths --json",
            "resident_preflight": "abyss-machine ai llm resident preflight --json",
            "resident_status": "abyss-machine ai llm resident status --json",
            "resident_monitor": "abyss-machine ai llm resident monitor --json",
            "resident_digest": "abyss-machine ai llm resident digest --json",
            "resident_job": "abyss-machine ai llm resident job JOB --json",
            "resident_micro": "abyss-machine ai llm resident micro --json",
            "resident_jobs": "abyss-machine ai llm resident jobs latest --json",
            "resident_jobs_run": "abyss-machine ai llm resident jobs run --json",
            "resident_jobs_validate": "abyss-machine ai llm resident jobs-validate --json",
            "resident_candidates": "abyss-machine ai llm resident candidates --json",
            "resident_candidates_validate": "abyss-machine ai llm resident candidates-validate --json",
            "resident_evals": "abyss-machine ai llm resident evals --json",
            "resident_evals_validate": "abyss-machine ai llm resident evals-validate --json",
            "resident_smoke": "abyss-machine ai llm resident smoke --json",
            "resident_validate": "abyss-machine ai llm resident validate --json",
            "workhorse_paths": "abyss-machine ai llm workhorse paths --json",
            "workhorse_preflight": "abyss-machine ai llm workhorse preflight --json",
            "workhorse_pack": "abyss-machine ai llm workhorse pack --json",
            "workhorse_review": "abyss-machine ai llm workhorse review --json",
            "workhorse_review_model": "abyss-machine ai llm workhorse review --run-model --json",
            "workhorse_validate": "abyss-machine ai llm workhorse validate --json",
            "workhorse_self_test": "abyss-machine ai llm workhorse self-test --json",
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "models_are_host_managed": True,
            "large_downloads_require_storage_preflight": True,
        },
    }


def llm_registry_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    config: dict[str, Any],
    runtime: dict[str, Any],
    family_runtimes: dict[str, dict[str, Any]],
    profile_statuses: dict[str, dict[str, Any]],
    registry_latest_path: Any,
    registry_daily_path: Any,
    validate_latest_path: Any,
) -> dict[str, Any]:
    families: dict[str, Any] = {}
    profiles_flat: dict[str, Any] = {}
    configured_families = config.get("families") if isinstance(config.get("families"), dict) else {}
    for family_name, family in configured_families.items():
        if not isinstance(family, dict):
            continue
        family_key = str(family_name)
        family_runtime = family_runtimes.get(family_key, runtime)
        profile_status_map: dict[str, Any] = {}
        profiles = family.get("profiles") if isinstance(family.get("profiles"), dict) else {}
        for profile_name, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            profile_key = str(profile_name)
            flat_key = f"{family_key}.{profile_key}"
            status = profile_statuses.get(flat_key)
            if not isinstance(status, dict):
                continue
            profile_status_map[profile_key] = status
            profiles_flat[flat_key] = status
        families[family_key] = {
            "status": family.get("status"),
            "provider": family.get("provider"),
            "format_provider": family.get("format_provider"),
            "license": family.get("license"),
            "upstream": family.get("upstream"),
            "local_root": family.get("local_root"),
            "runtime": family_runtime,
            "notes": family.get("notes", []),
            "profiles": profile_status_map,
        }
    ready_profiles = [item for item in profiles_flat.values() if item.get("status") == "ready"]
    return {
        "schema": f"{schema_prefix}_ai_llm_registry_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(runtime.get("ok")),
        "backend": config.get("backend") or "llama.cpp",
        "runtime": runtime,
        "families": families,
        "profiles": profiles_flat,
        "summary": {
            "families": len(families),
            "profiles": len(profiles_flat),
            "ready_profiles": len(ready_profiles),
            "missing_models": sum(1 for item in profiles_flat.values() if item.get("status") == "model-missing"),
            "runtime_ok": bool(runtime.get("ok")),
        },
        "paths": {
            "latest": str(registry_latest_path),
            "daily": str(registry_daily_path),
            "validate_latest": str(validate_latest_path),
        },
        "bridge": {
            "stack_consumption": "Future abyss-stack should consume this registry, then run stack-owned runtime-bench before promotion.",
            "no_stack_mutation": True,
        },
        "non_claims": [
            "Registry readiness means files and executable runtime exist; it does not prove quality, latency, or safe resident warming.",
            "Gemma 4 profiles are host candidates, not final abyss-stack service topology.",
        ],
    }


def llm_validate_contract_checks(
    *,
    registry: dict[str, Any],
    token_profiles: dict[str, Any],
    config: dict[str, Any],
    protected_roots: list[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"level": level, "key": key, "message": message}
        if details is not None:
            item["details"] = details
        checks.append(item)

    runtime = registry.get("runtime") if isinstance(registry.get("runtime"), dict) else {}
    profiles = registry.get("profiles") if isinstance(registry.get("profiles"), dict) else {}
    add("ok" if runtime.get("ok") else "fail", "runtime", "llama.cpp runtime exists and reports version", runtime)
    add("ok" if profiles else "fail", "profiles_configured", "LLM profiles are configured", {"profiles": sorted(profiles)})
    add(
        "ok" if int(_nested_get(token_profiles, ["summary", "exact_ready_profiles"]) or 0) > 0 else "warn",
        "token_accounting_profiles",
        "LLM profiles expose at least one exact tokenizer route",
        token_profiles.get("summary") if isinstance(token_profiles.get("summary"), dict) else {},
    )
    missing = [name for name, profile in profiles.items() if isinstance(profile, dict) and not profile.get("local_exists")]
    add("ok" if not missing else "warn", "profile_models", "configured model files exist", {"missing": missing})
    bad_paths = [
        {"profile": name, "path": profile.get("local_path"), "protection": profile.get("storage", {}).get("protection")}
        for name, profile in profiles.items()
        if isinstance(profile, dict)
        and (
            not profile.get("storage", {}).get("under_host_cache")
            or profile.get("storage", {}).get("protection", {}).get("decision") == "deny"
        )
    ]
    add("ok" if not bad_paths else "fail", "storage_routes", "LLM model paths stay under host cache and outside protected roots", {"bad_paths": bad_paths})
    families = config.get("families") if isinstance(config.get("families"), dict) else {}
    hardcoded_stack_paths = [
        {"family": family_name, "profile": profile_name, "path": profile.get("local_path")}
        for family_name, family in families.items()
        if isinstance(family, dict)
        for profile_name, profile in (family.get("profiles") or {}).items()
        if isinstance(profile, dict) and any(root in str(profile.get("local_path") or "") for root in protected_roots)
    ]
    add("ok" if not hardcoded_stack_paths else "fail", "protected_roots", "LLM registry does not write into stack/work/game roots", {"bad_paths": hardcoded_stack_paths})
    return checks


def llm_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    registry: dict[str, Any],
    paths: dict[str, Any],
) -> dict[str, Any]:
    profiles = registry.get("profiles") if isinstance(registry.get("profiles"), dict) else {}
    fails = sum(1 for item in checks if item.get("level") == "fail")
    warnings = sum(1 for item in checks if item.get("level") == "warn")
    return {
        "schema": f"{schema_prefix}_ai_llm_validate_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": fails == 0,
        "checks": checks,
        "summary": {
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
            "profiles": len(profiles),
            "ready_profiles": _nested_get(registry, ["summary", "ready_profiles"]),
        },
        "paths": paths,
        "policy": {
            "warnings_allow_missing_models_before_download": True,
            "fail_only_for_broken_runtime_or_protected_routes": True,
        },
    }


def _nested_get(data: Any, path: list[str]) -> Any:
    cursor: Any = data
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def ai_paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    refs: dict[str, Any],
    stack_model_roots: list[Any],
    openvino_config: dict[str, Any],
) -> dict[str, Any]:
    def ref(key: str) -> Any:
        return refs.get(key)

    return {
        "schema": f"{schema_prefix}_ai_paths_v1",
        "version": version,
        "generated_at": generated_at,
        "root": ref("AI_ROOT"),
        "agent_entrypoint": ref("AI_AGENTS_PATH"),
        "index": ref("AI_INDEX_PATH"),
        "config": ref("AI_CONFIG_PATH"),
        "devices": {"latest": ref("AI_DEVICES_LATEST_PATH")},
        "models": {"latest": ref("AI_MODELS_LATEST_PATH")},
        "benchmarks": {
            "root": ref("AI_BENCHMARK_ROOT"),
            "latest": ref("AI_BENCHMARK_LATEST_PATH"),
            "today": ref("AI_BENCHMARK_TODAY_PATH"),
            "daily_glob": ref("AI_BENCHMARK_DAILY_GLOB"),
        },
        "evals": {
            "root": ref("AI_EVAL_ROOT"),
            "latest": ref("AI_EVAL_LATEST_PATH"),
            "today": ref("AI_EVAL_TODAY_PATH"),
            "daily_glob": ref("AI_EVAL_DAILY_GLOB"),
        },
        "capabilities": {"latest": ref("AI_CAPABILITIES_LATEST_PATH")},
        "policy": {"latest": ref("AI_POLICY_LATEST_PATH")},
        "token_accounting": {
            "root": ref("AI_TOKEN_ACCOUNTING_ROOT"),
            "latest": ref("AI_TOKEN_ACCOUNTING_LATEST_PATH"),
            "profiles_latest": ref("AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH"),
            "counts_latest": ref("AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH"),
            "counts_daily_glob": ref("AI_TOKEN_ACCOUNTING_COUNTS_DAILY_GLOB"),
            "aoa_session_memory_latest": ref("AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH"),
            "aoa_session_memory_daily_glob": ref("AI_TOKEN_ACCOUNTING_AOA_DAILY_GLOB"),
        },
        "llm": refs.get("AI_LLM_PATHS", {}),
        "cpu": {
            "root": ref("AI_CPU_ROOT"),
            "topology_latest": ref("AI_CPU_TOPOLOGY_LATEST_PATH"),
            "thermal_map_latest": ref("AI_CPU_THERMAL_MAP_LATEST_PATH"),
            "route_latest": ref("AI_CPU_ROUTE_LATEST_PATH"),
            "test_latest": ref("AI_CPU_TEST_LATEST_PATH"),
            "test_daily_glob": ref("AI_CPU_TEST_DAILY_GLOB"),
        },
        "cooling": {
            "agent_entrypoint": ref("COOLING_AGENTS_PATH"),
            "latest": ref("COOLING_LATEST_PATH"),
            "actions_daily_glob": ref("COOLING_ACTION_DAILY_GLOB"),
            "config": ref("COOLING_CONFIG_PATH"),
        },
        "storage": {
            "host_latest": ref("STORAGE_LATEST_PATH"),
            "host_index": ref("STORAGE_INDEX_PATH"),
            "host_policy": ref("STORAGE_POLICY_PATH"),
            "host_policy_env": ref("STORAGE_POLICY_ENV_PATH"),
            "latest": ref("AI_STORAGE_LATEST_PATH"),
            "cleanups_glob": ref("AI_STORAGE_CLEANUP_DAILY_GLOB"),
            "hooks_etc": ref("HOOKS_ETC_DIR"),
            "hooks_srv": ref("HOOKS_SRV_DIR"),
        },
        "processes": {
            "root": ref("PROCESS_ROOT"),
            "agent_entrypoint": ref("PROCESS_AGENTS_PATH"),
            "index": ref("PROCESS_INDEX_PATH"),
            "latest": ref("PROCESS_LATEST_PATH"),
            "daily_glob": ref("PROCESS_SNAPSHOT_DAILY_GLOB"),
        },
        "runtime": {
            "latest": ref("AI_RUNTIME_LATEST_PATH"),
            "today": ref("AI_RUNTIME_TODAY_PATH"),
            "daily_glob": ref("AI_RUNTIME_DAILY_GLOB"),
        },
        "reports": {
            "latest": ref("AI_REPORT_LATEST_PATH"),
            "today": ref("AI_REPORT_TODAY_PATH"),
            "daily_glob": ref("AI_REPORT_DAILY_GLOB"),
        },
        "workloads": {
            "root": ref("AI_WORKLOAD_ROOT"),
            "latest": ref("AI_WORKLOAD_LATEST_PATH"),
            "taxonomy": ref("AI_WORKLOAD_TAXONOMY_PATH"),
            "stats_latest": ref("AI_WORKLOAD_STATS_LATEST_PATH"),
            "runs_today": ref("AI_WORKLOAD_RUNS_TODAY_PATH"),
            "runs_daily_glob": ref("AI_WORKLOAD_RUNS_DAILY_GLOB"),
            "refresh_today": ref("AI_WORKLOAD_REFRESH_TODAY_PATH"),
            "refresh_daily_glob": ref("AI_WORKLOAD_REFRESH_DAILY_GLOB"),
        },
        "tts": {
            "root": ref("AI_TTS_ROOT"),
            "latest": ref("AI_TTS_LATEST_PATH"),
            "inventory_latest": ref("AI_TTS_INVENTORY_LATEST_PATH"),
            "profiles_latest": ref("AI_TTS_PROFILES_LATEST_PATH"),
            "eval_latest": ref("AI_TTS_EVAL_LATEST_PATH"),
            "eval_latest_success": ref("AI_TTS_EVAL_LATEST_SUCCESS_PATH"),
            "eval_latest_success_by_profile": ref("AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH"),
            "eval_success_by_profile_root": ref("AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT"),
            "eval_today": ref("AI_TTS_EVAL_TODAY_PATH"),
            "eval_daily_glob": ref("AI_TTS_EVAL_DAILY_GLOB"),
            "compare_latest": ref("AI_TTS_COMPARE_LATEST_PATH"),
            "server_latest": ref("AI_TTS_SERVER_LATEST_PATH"),
            "synth_root": ref("AI_TTS_SYNTH_ROOT"),
            "synth_today": ref("AI_TTS_SYNTH_TODAY_PATH"),
            "cache": ref("AI_TTS_CACHE_ROOT"),
        },
        "fixtures": {
            "root": ref("AI_FIXTURE_ROOT"),
            "stt_ru_smoke": ref("AI_FIXTURE_STT_RU_SMOKE"),
        },
        "cache": {
            "root": ref("AI_CACHE_ROOT"),
            "openvino": ref("AI_OPENVINO_CACHE_ROOT"),
            "tts": ref("AI_TTS_CACHE_ROOT"),
        },
        "stack_model_roots": [str(path) for path in stack_model_roots],
        "openvino": openvino_config,
    }


def ai_runtime_snapshot_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    current: dict[str, Any],
    devices: dict[str, Any],
    python_runtime: dict[str, Any],
    kernel_modules: dict[str, Any],
    previous_latest: dict[str, Any] | None,
) -> dict[str, Any]:
    drift: list[str] = []
    if isinstance(previous_latest, dict):
        previous_current = previous_latest.get("current", {})
        for key in ("kernel", "openvino_version", "available_devices", "python_packages", "npu_user_driver", "packages"):
            if isinstance(previous_current, dict) and previous_current.get(key) != current.get(key):
                drift.append(key)
    return {
        "schema": f"{schema_prefix}_ai_runtime_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(devices.get("openvino", {}).get("ok")),
        "current": current,
        "devices": devices,
        "python_runtime": python_runtime,
        "kernel_modules": kernel_modules,
        "drift_from_previous_latest": drift,
        "retest_triggers": [
            "kernel",
            "openvino_version",
            "available_devices",
            "python_packages",
            "npu_user_driver",
            "packages",
        ],
        "policy": {
            "internet_freshness_checked": False,
            "non_claim": "Runtime snapshot records installed state; it does not decide package freshness against remote repos.",
        },
    }


def ai_capabilities_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    devices: dict[str, Any],
    models: dict[str, Any],
    dictation: dict[str, Any],
    tts_profiles: dict[str, Any],
    latest_tts_eval: dict[str, Any],
    latest_tts_success: dict[str, Any],
    llm_registry: dict[str, Any],
    llm_resident_status: dict[str, Any],
    llm_resident_digest: dict[str, Any],
    llm_resident_micro: dict[str, Any],
    llm_resident_jobs: dict[str, Any],
    refs: dict[str, Any],
    resident_refs: dict[str, Any],
    resident_job_names: list[str],
) -> dict[str, Any]:
    entries = models.get("entries") if isinstance(models.get("entries"), list) else []
    stt_profiles = dictation.get("profiles") if isinstance(dictation.get("profiles"), dict) else {}
    embedding_entries = [item for item in entries if "embedding" in str(item.get("name", "")).lower()]
    text_entries = [
        item for item in entries
        if item.get("category") in {"openvino_ir", "ovms_openvino"} and any(
            needle in str(item.get("path", "")).lower() for needle in ("qwen3-4b", "qwen3-8b", "phi-3.5", "ovms-text")
        )
    ]
    llm_profiles = llm_registry.get("profiles") if isinstance(llm_registry.get("profiles"), dict) else {}
    llm_ready = [item for item in llm_profiles.values() if isinstance(item, dict) and item.get("status") == "ready"]
    tts_entries = [item for item in entries if "tts" in str(item.get("path", "")).lower()]
    tts_profile_values = tts_profiles.get("profiles") if isinstance(tts_profiles.get("profiles"), dict) else {}
    tts_model_ready = [
        item for item in tts_profile_values.values()
        if isinstance(item, dict) and item.get("status") in {"executable", "model-ready-adapter-missing"}
    ]
    ready = devices.get("ready") if isinstance(devices.get("ready"), dict) else {}
    capabilities = {
        "stt": {
            "status": "ready" if dictation.get("server_socket_exists") and any(p.get("model_dir_exists") for p in stt_profiles.values() if isinstance(p, dict)) else "degraded",
            "host_recommended_backend": "OpenVINO Whisper AUTO:GPU,CPU",
            "primary_bridge": "abyss-machine dictation transcribe AUDIO.wav --profile auto --json",
            "source_models": [
                {"profile": name, "model_dir": profile.get("model_dir"), "device": profile.get("device")}
                for name, profile in stt_profiles.items()
                if isinstance(profile, dict) and profile.get("model_dir_exists")
            ],
            "non_claims": ["NPU is available, but current Whisper STT remains GPU-preferred until measured otherwise."],
        },
        "embeddings": {
            "status": "ready" if ready.get("openvino") and embedding_entries else "inventory-missing",
            "host_recommended_backend": "OpenVINO AUTO:GPU,CPU",
            "primary_bridge": "abyss-machine ai eval --suite embeddings --json",
            "source_models": embedding_entries,
            "stack_bridge_hint": "Future abyss-stack should decide whether to route through OVMS or another stack-owned service.",
        },
        "llm_text": {
            "status": "resident-running" if isinstance(llm_resident_status, dict) and llm_resident_status.get("ok") and llm_resident_status.get("status") == "running" else "llama-cpp-ready" if llm_ready else "llama-cpp-candidate-missing-models" if llm_profiles else "host-eval-ready" if ready.get("openvino") and text_entries else "inventory-missing",
            "host_recommended_backend": "llama.cpp 05ff59c Vulkan/CPU for Gemma 4 host candidates; OpenVINO GenAI remains bounded smoke evidence",
            "primary_bridge": "abyss-machine ai llm registry --json",
            "resident_bridge": "abyss-machine ai llm resident status --json",
            "eval_bridge": "abyss-machine ai eval --suite text --json",
            "source_models": text_entries,
            "llm_registry": {
                "latest": refs.get("AI_LLM_REGISTRY_LATEST_PATH"),
                "summary": llm_registry.get("summary"),
                "profiles": llm_profiles,
            },
            "resident_candidate": {
                "profile": "gemma4.spark",
                "status_latest": str(resident_refs.get("status_latest") or ""),
                "monitor_latest": str(resident_refs.get("monitor_latest") or ""),
                "digest_latest": str(resident_refs.get("digest_latest") or ""),
                "micro_latest": str(resident_refs.get("micro_latest") or ""),
                "jobs_latest": str(resident_refs.get("jobs_latest") or ""),
                "jobs_validate_latest": str(resident_refs.get("jobs_validate_latest") or ""),
                "status": llm_resident_status if isinstance(llm_resident_status, dict) else None,
                "digest": {
                    "ok": llm_resident_digest.get("ok") if isinstance(llm_resident_digest, dict) else None,
                    "generated_at": llm_resident_digest.get("generated_at") if isinstance(llm_resident_digest, dict) else None,
                    "status": llm_resident_digest.get("status") if isinstance(llm_resident_digest, dict) else None,
                    "items": len((llm_resident_digest.get("digest") or {}).get("items") or []) if isinstance(llm_resident_digest, dict) and isinstance(llm_resident_digest.get("digest"), dict) else 0,
                },
                "micro": {
                    "ok": llm_resident_micro.get("ok") if isinstance(llm_resident_micro, dict) else None,
                    "generated_at": llm_resident_micro.get("generated_at") if isinstance(llm_resident_micro, dict) else None,
                    "summary": llm_resident_micro.get("summary") if isinstance(llm_resident_micro, dict) else None,
                },
                "jobs": {
                    "ok": llm_resident_jobs.get("ok") if isinstance(llm_resident_jobs, dict) else None,
                    "generated_at": llm_resident_jobs.get("generated_at") if isinstance(llm_resident_jobs, dict) else None,
                    "summary": llm_resident_jobs.get("summary") if isinstance(llm_resident_jobs, dict) else None,
                    "job_names": resident_job_names,
                },
                "non_claims": [
                    "Resident-running means the host candidate is available and monitored; it is not an abyss-stack production promotion.",
                    "Digest artifacts are derived orientation over cited local dictation events, not canonical user intent.",
                    "Micro artifacts are frequent small-work evidence; they are not automatic commands.",
                    "Jobs artifacts are local candidate summaries for calibration; they are not automatic commands or stack-owned truth.",
                ],
            },
            "stack_bridge_hint": "Future abyss-stack should consume ai llm registry, then run stack-owned runtime-bench and promotion loop before live serving.",
        },
        "tts": {
            "status": "runtime-proven" if latest_tts_success.get("ok") or latest_tts_eval.get("ok") else "bridge-ready" if tts_model_ready else "runtime-missing" if tts_entries else "missing",
            "host_recommended_backend": "Qwen3-TTS 1.7B via OpenVINO GPU for quality; BabelVox/Qwen3-TTS 0.6B INT8 NPU remains experimental until measured",
            "primary_bridge": "abyss-machine ai tts profiles --json",
            "eval_bridge": "abyss-machine ai tts eval --profile quality --json",
            "server_bridge": "abyss-machine ai tts server status --json",
            "source_models": tts_entries,
            "profiles": tts_profile_values,
            "latest_eval": {
                "ok": latest_tts_eval.get("ok"),
                "generated_at": latest_tts_eval.get("generated_at"),
                "profile": latest_tts_eval.get("profile"),
                "summary": latest_tts_eval.get("summary"),
            },
            "latest_success_eval": {
                "ok": latest_tts_success.get("ok"),
                "generated_at": latest_tts_success.get("generated_at"),
                "profile": latest_tts_success.get("profile"),
                "summary": latest_tts_success.get("summary"),
            },
            "non_claims": [
                "TTS bridge/profile presence is not an abyss-stack runtime promotion decision.",
                "NPU TTS must be measured on this machine before it is treated as a preferred path.",
                "Russian pronunciation quality requires text-normalization/accent handling before publication-grade use.",
            ],
        },
        "npu": {
            "status": "runtime-ready" if ready.get("npu") else "degraded",
            "host_recommended_backend": "OpenVINO NPU for explicitly measured NPU-compatible tasks",
            "primary_bridge": "abyss-machine ai benchmark --quick --devices NPU --json",
            "source_models": [],
            "non_claims": ["NPU device readiness does not mean every model family is faster or supported on NPU."],
        },
    }
    return {
        "schema": f"{schema_prefix}_ai_capabilities_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": all(cap.get("status") not in {"degraded"} for cap in capabilities.values() if isinstance(cap, dict)),
        "capabilities": capabilities,
        "source_refs": {
            "devices_latest": refs.get("AI_DEVICES_LATEST_PATH"),
            "models_latest": refs.get("AI_MODELS_LATEST_PATH"),
            "dictation_status": "abyss-machine dictation status --json",
            "llm_registry": refs.get("AI_LLM_REGISTRY_LATEST_PATH"),
            "llm_resident_status": str(resident_refs.get("status_latest") or ""),
            "llm_resident_digest": str(resident_refs.get("digest_latest") or ""),
            "llm_resident_micro": str(resident_refs.get("micro_latest") or ""),
        },
        "policy": {
            "host_layer_mutates_stack": False,
            "promotion_boundary": "Capability presence is not an abyss-stack runtime winner decision.",
        },
    }


def ai_capabilities_latest_document(data: dict[str, Any], *, latest_path: str) -> dict[str, Any]:
    payload = dict(data)
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    policy = dict(policy)
    policy.update({
        "consumed_from_latest": True,
        "refresh_inputs": False,
        "heavy_runtime_probe_allowed": False,
    })
    payload["policy"] = policy
    payload["latest_consumption"] = {
        "path": latest_path,
        "source": "latest_artifact",
        "refresh_inputs": False,
        "heavy_runtime_probe_allowed": False,
    }
    return payload


def ai_policy_float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def ai_policy_episode_thresholds(thresholds: dict[str, Any] | None = None) -> dict[str, float]:
    data = thresholds if isinstance(thresholds, dict) else {}
    active_range = data.get("thin_laptop_active_range_c")
    active_low = 100.0
    active_high = 105.0
    if isinstance(active_range, list) and len(active_range) >= 2:
        try:
            active_low = float(active_range[0])
            active_high = float(active_range[1])
        except (TypeError, ValueError):
            active_low = 100.0
            active_high = 105.0
    warm = ai_policy_float(data, "warm_temperature_c", 80.0)
    hot = ai_policy_float(data, "hot_temperature_c", 106.0)
    critical = ai_policy_float(data, "critical_temperature_c", 109.0)
    watch = ai_policy_float(data, "watch_above_c", active_high)
    hard = ai_policy_float(data, "hard_emergency_temperature_c", critical)
    if active_high < active_low:
        active_high = active_low
    if watch < active_low:
        watch = active_high
    if hot < watch:
        hot = watch
    if critical < hot:
        critical = hot
    if hard < critical:
        hard = critical
    return {
        "warm_c": warm,
        "active_low_c": active_low,
        "active_high_c": active_high,
        "watch_c": watch,
        "hot_c": hot,
        "critical_c": critical,
        "hard_emergency_c": hard,
    }


def ai_policy_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    config: dict[str, Any],
    telemetry_age_sec: Any,
    battery: dict[str, Any],
    mode: dict[str, Any],
    thermal: dict[str, Any],
    cpu_thermal_map: dict[str, Any],
    observability_latest_path: str,
    cpu_thermal_map_latest_path: str,
    mode_status_command: str = "abyss-machine mode status --json",
) -> dict[str, Any]:
    thresholds = config.get("thermal_policy", {}) if isinstance(config.get("thermal_policy"), dict) else {}
    warm_temp = float(thresholds.get("warm_temperature_c", 80.0))
    hot_temp = float(thresholds.get("hot_temperature_c", 106.0))
    balanced_warm_heavy_max = float(thresholds.get("balanced_warm_heavy_max_c", 105.0))
    min_battery = int(thresholds.get("min_battery_percent_for_heavy", 35))
    max_age = float(thresholds.get("telemetry_max_age_sec", 300))
    temp = thermal.get("current_temperature_c")
    rolling_avg = thermal.get("rolling_avg_temperature_c")
    recent_peak = thermal.get("recent_peak_temperature_c")
    trend = str(thermal.get("trend") or "unknown")
    age = telemetry_age_sec
    ac_online = bool(battery.get("ac_online"))
    capacity = battery.get("capacity_percent")
    reasons: list[str] = []

    if not isinstance(age, (int, float)) or age > max_age:
        policy_class = "degraded"
        reasons.append("telemetry_stale_or_missing")
    elif not ac_online:
        policy_class = "battery_saver"
        reasons.append("battery_discharging")
    elif isinstance(capacity, int) and capacity < min_battery:
        policy_class = "battery_saver"
        reasons.append("battery_below_heavy_threshold")
    elif isinstance(temp, (int, float)) and temp >= hot_temp:
        policy_class = "hot"
        reasons.append(f"temperature_hot:current={temp}>=threshold={hot_temp}")
    elif (
        isinstance(rolling_avg, (int, float))
        and rolling_avg >= hot_temp
        and trend != "falling"
    ):
        policy_class = "hot"
        reasons.append(f"temperature_hot:rolling_avg={rolling_avg}>=threshold={hot_temp}:trend={trend}")
    elif (
        isinstance(recent_peak, (int, float))
        and recent_peak >= hot_temp
        and isinstance(temp, (int, float))
        and temp >= warm_temp
        and trend != "falling"
    ):
        policy_class = "hot"
        reasons.append(f"temperature_hot:recent_peak={recent_peak}:current={temp}:trend={trend}")
    elif (
        isinstance(temp, (int, float))
        and temp >= warm_temp
    ) or (
        isinstance(rolling_avg, (int, float))
        and rolling_avg >= warm_temp
    ) or (
        isinstance(recent_peak, (int, float))
        and recent_peak >= hot_temp
    ):
        policy_class = "warm"
        if isinstance(temp, (int, float)) and temp >= warm_temp:
            reasons.append(f"temperature_warm:current={temp}>=threshold={warm_temp}")
        elif isinstance(rolling_avg, (int, float)) and rolling_avg >= warm_temp:
            reasons.append(f"temperature_warm:rolling_avg={rolling_avg}>=threshold={warm_temp}")
        else:
            reasons.append(f"temperature_warm:recent_peak={recent_peak}:current={temp}:trend={trend}")
    else:
        policy_class = "green"

    if mode.get("effective_mode") == "saver":
        reasons.append("effective_mode_saver")
        if policy_class == "green":
            policy_class = "battery_saver"

    effective_mode = mode.get("effective_mode")
    can_run_heavy = policy_class == "green" and effective_mode in {"performance", "ai", "balanced"}
    if policy_class == "warm" and effective_mode in {"performance", "ai"}:
        can_run_heavy = True
    if (
        policy_class == "warm"
        and effective_mode == "balanced"
        and isinstance(temp, (int, float))
        and temp < balanced_warm_heavy_max
    ):
        can_run_heavy = True
        reasons.append(f"balanced_warm_controlled_allowed:current={temp}<threshold={balanced_warm_heavy_max}:trend={trend}")
    elif policy_class == "warm" and effective_mode == "balanced":
        can_run_heavy = False
        reasons.append(f"balanced_mode_warm:current={temp}:threshold={balanced_warm_heavy_max}:trend={trend}")

    routed_heavy = ai_cpu_routing.routed_heavy_policy(
        cpu_thermal_map,
        policy_class,
        effective_mode,
        ac_online,
        config=config,
        capacity_percent=capacity,
        trend=trend,
    )
    can_run_routed_heavy = bool(routed_heavy.get("allowed"))
    can_run_routed_heavy_unattended = bool(routed_heavy.get("unattended_allowed"))
    if can_run_heavy:
        heavy_policy = "unrestricted"
    elif can_run_routed_heavy:
        heavy_policy = "routed"
        route = routed_heavy.get("route", {}) if isinstance(routed_heavy.get("route"), dict) else {}
        reasons.append(
            "routed_heavy_available:"
            f"decision={routed_heavy.get('decision')}:"
            f"cpuset={route.get('cpuset')}:threads={route.get('thread_limit')}"
        )
    else:
        heavy_policy = "defer"
        decision = routed_heavy.get("decision")
        if decision:
            reasons.append(f"routed_heavy_unavailable:{decision}")

    recommended = {
        "stt": ["GPU", "CPU"] if policy_class in {"green", "warm"} else ["CPU"],
        "embeddings": ["GPU", "CPU"] if can_run_heavy else ["CPU"],
        "llm_text": ["GPU", "CPU"] if can_run_heavy else ["CPU"] if can_run_routed_heavy else [],
        "tts": ["GPU", "CPU"] if can_run_heavy else ["CPU"] if policy_class not in {"degraded"} else [],
        "tts_npu_experimental": ["NPU"] if can_run_heavy else [],
        "npu_smoke": ["NPU"] if policy_class in {"green", "warm"} else [],
    }
    return {
        "schema": f"{schema_prefix}_ai_policy_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": policy_class != "degraded",
        "class": policy_class,
        "can_run_heavy": can_run_heavy,
        "can_run_routed_heavy": can_run_routed_heavy,
        "can_run_routed_heavy_unattended": can_run_routed_heavy_unattended,
        "heavy_policy": heavy_policy,
        "routing_required_for_heavy": bool(can_run_routed_heavy and not can_run_heavy),
        "thermal_episode": thermal.get("episode"),
        "recommended_devices_by_capability": recommended,
        "reasons": reasons,
        "thresholds": {
            "warm_temperature_c": warm_temp,
            "hot_temperature_c": hot_temp,
            "rolling_window_sec": float(thresholds.get("rolling_window_sec", 180)),
            "balanced_warm_heavy_max_c": balanced_warm_heavy_max,
            "falling_trend_min_c": float(thresholds.get("falling_trend_min_c", 3.0)),
            "min_battery_percent_for_heavy": min_battery,
            "telemetry_max_age_sec": max_age,
            "episode": ai_policy_episode_thresholds(thresholds),
        },
        "current": {
            "temperature_c_max": temp,
            "thermal": thermal,
            "telemetry_age_sec": age,
            "battery": battery,
            "mode": {
                "selected": mode.get("selected_mode"),
                "effective": mode.get("effective_mode"),
                "power_profile": mode.get("actual_power_profile"),
            },
            "cpu_thermal_map": {
                "class": cpu_thermal_map.get("class"),
                "summary": cpu_thermal_map.get("summary", {}),
                "available_by_role_cpuset": cpu_thermal_map.get("available_by_role_cpuset", {}),
            },
        },
        "cpu_routing": {
            "routed_heavy": routed_heavy,
        },
        "source_refs": {
            "observability_latest": observability_latest_path,
            "cpu_thermal_map_latest": cpu_thermal_map_latest_path,
            "mode_status": mode_status_command,
        },
    }


def ai_status_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    config_path: str,
    config_exists: bool,
    config_load_error: Any,
    devices: dict[str, Any],
    models: dict[str, Any],
    llm_registry: dict[str, Any],
    latest_benchmark: dict[str, Any],
    latest_eval: dict[str, Any],
    latest_tts_eval: dict[str, Any],
    latest_tts_success: dict[str, Any],
    tts_profiles: dict[str, Any],
    tts_server: dict[str, Any],
    dictation: dict[str, Any],
    cpu_route_latest: dict[str, Any],
    cpu_thermal_latest: dict[str, Any],
    cooling_latest: dict[str, Any],
    refs: dict[str, Any],
    include_report: bool,
    report_latest_path: str,
    report_exists: bool,
) -> dict[str, Any]:
    ready = devices.get("ready", {})
    llm_profiles = llm_registry.get("profiles") if isinstance(llm_registry.get("profiles"), dict) else {}
    dictation_profiles = dictation.get("profiles") if isinstance(dictation.get("profiles"), dict) else {}
    data = {
        "schema": f"{schema_prefix}_ai_status_v1",
        "version": version,
        "generated_at": generated_at,
        "paths": paths,
        "config": {
            "path": config_path,
            "exists": config_exists,
            "load_error": config_load_error,
        },
        "ready": {
            "openvino": bool(ready.get("openvino")),
            "gpu": bool(ready.get("gpu")),
            "npu": bool(ready.get("npu")),
            "models": models.get("summary", {}).get("entries", 0) > 0,
            "llm": bool(llm_registry.get("summary", {}).get("ready_profiles")),
            "dictation_server": bool(dictation.get("server_socket_exists")),
        },
        "devices": {
            "latest": refs.get("AI_DEVICES_LATEST_PATH"),
            "openvino_version": devices.get("openvino", {}).get("openvino_version"),
            "available_devices": devices.get("openvino", {}).get("available_devices"),
            "ready": ready,
        },
        "models": {
            "latest": refs.get("AI_MODELS_LATEST_PATH"),
            "summary": models.get("summary", {}),
            "roots": models.get("roots", []),
        },
        "llm": {
            "registry_latest": refs.get("AI_LLM_REGISTRY_LATEST_PATH"),
            "validate_latest": refs.get("AI_LLM_VALIDATE_LATEST_PATH"),
            "summary": llm_registry.get("summary"),
            "runtime_ok": _nested_get(llm_registry, ["runtime", "ok"]),
            "profiles": {
                name: {
                    "status": profile.get("status"),
                    "role": profile.get("role"),
                    "local_path": profile.get("local_path"),
                    "size_bytes": profile.get("size_bytes"),
                    "model_id": profile.get("model_id"),
                    "hf_file": profile.get("hf_file"),
                }
                for name, profile in llm_profiles.items()
                if isinstance(profile, dict)
            },
        },
        "benchmark": {
            "latest": refs.get("AI_BENCHMARK_LATEST_PATH"),
            "latest_ok": latest_benchmark.get("ok"),
            "latest_generated_at": latest_benchmark.get("generated_at"),
            "summary": latest_benchmark.get("summary"),
            "error": latest_benchmark.get("error"),
        },
        "eval": {
            "latest": refs.get("AI_EVAL_LATEST_PATH"),
            "latest_ok": latest_eval.get("ok"),
            "latest_generated_at": latest_eval.get("generated_at"),
            "summary": latest_eval.get("summary"),
            "error": latest_eval.get("error"),
        },
        "workload": {
            "latest": refs.get("AI_WORKLOAD_LATEST_PATH"),
            "stats_latest": refs.get("AI_WORKLOAD_STATS_LATEST_PATH"),
            "exists": bool(refs.get("AI_WORKLOAD_LATEST_EXISTS")),
        },
        "cpu": {
            "topology_latest": refs.get("AI_CPU_TOPOLOGY_LATEST_PATH"),
            "thermal_map_latest": refs.get("AI_CPU_THERMAL_MAP_LATEST_PATH"),
            "route_latest": refs.get("AI_CPU_ROUTE_LATEST_PATH"),
            "test_latest": refs.get("AI_CPU_TEST_LATEST_PATH"),
            "latest_route_allowed": cpu_route_latest.get("allowed"),
            "latest_route_cpuset": _nested_get(cpu_route_latest, ["route", "cpuset"]),
            "latest_route_class": _nested_get(cpu_route_latest, ["requested", "normalized_class"]),
            "latest_thermal_class": cpu_thermal_latest.get("class"),
            "latest_avoid_cpus": _nested_get(cpu_thermal_latest, ["summary", "route_avoid_cpus"]),
        },
        "cooling": {
            "agent_entrypoint": refs.get("COOLING_AGENTS_PATH"),
            "latest": refs.get("COOLING_LATEST_PATH"),
            "latest_ok": cooling_latest.get("ok"),
            "latest_generated_at": cooling_latest.get("generated_at"),
            "latest_class": _nested_get(cooling_latest, ["temperature", "class"]),
            "latest_temperature_c_max": _nested_get(cooling_latest, ["temperature", "summary", "temperature_c_max"]),
            "fan_mode": _nested_get(cooling_latest, ["fan", "fan_mode"]),
            "platform_profile": _nested_get(cooling_latest, ["power", "platform_profile", "current"]),
        },
        "tts": {
            "latest": refs.get("AI_TTS_LATEST_PATH"),
            "profiles_latest": refs.get("AI_TTS_PROFILES_LATEST_PATH"),
            "eval_latest": refs.get("AI_TTS_EVAL_LATEST_PATH"),
            "eval_latest_success": refs.get("AI_TTS_EVAL_LATEST_SUCCESS_PATH"),
            "eval_latest_success_by_profile": refs.get("AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH"),
            "eval_success_by_profile_root": refs.get("AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT"),
            "server_latest": refs.get("AI_TTS_SERVER_LATEST_PATH"),
            "profiles_summary": tts_profiles.get("summary"),
            "latest_eval_ok": latest_tts_eval.get("ok"),
            "latest_eval_generated_at": latest_tts_eval.get("generated_at"),
            "latest_eval_summary": latest_tts_eval.get("summary"),
            "latest_success_ok": latest_tts_success.get("ok"),
            "latest_success_generated_at": latest_tts_success.get("generated_at"),
            "latest_success_summary": latest_tts_success.get("summary"),
            "server_ok": tts_server.get("ok"),
            "server_profile": _nested_get(tts_server, ["ping", "profile"]),
            "server_socket": tts_server.get("socket"),
        },
        "dictation": {
            "default_profile": dictation.get("default_profile"),
            "model_root": dictation.get("model_root"),
            "server_socket_exists": dictation.get("server_socket_exists"),
            "profiles": {
                name: {
                    "model_dir": profile.get("model_dir"),
                    "model_dir_exists": profile.get("model_dir_exists"),
                    "device": profile.get("device"),
                }
                for name, profile in dictation_profiles.items()
                if isinstance(profile, dict)
            },
        },
    }
    if include_report:
        data["report"] = {
            "latest": report_latest_path,
            "exists": report_exists,
        }
    return data


def ai_report_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    status_data: dict[str, Any],
    capabilities: dict[str, Any],
    policy: dict[str, Any],
    runtime: dict[str, Any],
    storage: dict[str, Any],
    llm_registry: dict[str, Any],
    llm_validate: dict[str, Any],
    token_accounting_profiles: dict[str, Any],
    aoa_token_summary: dict[str, Any],
    latest_eval: dict[str, Any],
    latest_benchmark: dict[str, Any],
    latest_tts_eval: dict[str, Any],
    latest_tts_success: dict[str, Any],
    tts_profiles: dict[str, Any],
    tts_server: dict[str, Any],
    workload: dict[str, Any],
    cpu_route_latest: dict[str, Any],
    cpu_thermal_latest: dict[str, Any],
    cooling_latest: dict[str, Any],
    observability: dict[str, Any],
    dictation: dict[str, Any],
    refs: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": f"{schema_prefix}_ai_report_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": bool(status_data.get("ready", {}).get("openvino")) and bool(capabilities.get("ok")) and bool(policy.get("ok")),
        "summary": {
            "ready": status_data.get("ready"),
            "capabilities": {key: value.get("status") for key, value in capabilities.get("capabilities", {}).items()},
            "policy_class": policy.get("class"),
            "can_run_heavy": policy.get("can_run_heavy"),
            "can_run_routed_heavy": policy.get("can_run_routed_heavy"),
            "heavy_policy": policy.get("heavy_policy"),
            "runtime_ok": runtime.get("ok"),
            "storage_cache_dirs": storage.get("summary", {}).get("stack_local_openvino_cache_dirs"),
            "latest_eval_ok": latest_eval.get("ok"),
            "latest_tts_eval_ok": latest_tts_eval.get("ok"),
            "latest_tts_success_ok": latest_tts_success.get("ok"),
            "tts_server_ok": tts_server.get("ok"),
            "latest_benchmark_ok": latest_benchmark.get("ok"),
            "workload_records": workload.get("summary", {}).get("records"),
            "workload_groups": workload.get("summary", {}).get("groups"),
            "llm_ready_profiles": llm_registry.get("summary", {}).get("ready_profiles"),
            "llm_validate_ok": llm_validate.get("ok"),
            "token_accounting_exact_ready_profiles": token_accounting_profiles.get("summary", {}).get("exact_ready_profiles"),
            "aoa_token_summary_sessions": aoa_token_summary.get("summary", {}).get("selected_sessions"),
            "aoa_token_summary_missing_generated": aoa_token_summary.get("summary", {}).get("missing_generated_token_accounting"),
            "cpu_route_allowed": cpu_route_latest.get("allowed"),
            "cpu_route_cpuset": _nested_get(cpu_route_latest, ["route", "cpuset"]),
            "cpu_thermal_class": cpu_thermal_latest.get("class"),
        },
        "paths": paths,
        "status": status_data,
        "capabilities": capabilities,
        "policy": policy,
        "runtime": {
            "latest": refs.get("AI_RUNTIME_LATEST_PATH"),
            "ok": runtime.get("ok"),
            "current": runtime.get("current"),
            "drift_from_previous_latest": runtime.get("drift_from_previous_latest"),
        },
        "storage": {
            "latest": refs.get("AI_STORAGE_LATEST_PATH"),
            "summary": storage.get("summary"),
            "host_cache": storage.get("host_cache"),
        },
        "llm": {
            "registry_latest": refs.get("AI_LLM_REGISTRY_LATEST_PATH"),
            "validate_latest": refs.get("AI_LLM_VALIDATE_LATEST_PATH"),
            "summary": llm_registry.get("summary"),
            "runtime": llm_registry.get("runtime"),
            "profiles": llm_registry.get("profiles"),
            "validation": llm_validate.get("summary"),
        },
        "token_accounting": {
            "latest": refs.get("AI_TOKEN_ACCOUNTING_LATEST_PATH"),
            "profiles_latest": refs.get("AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH"),
            "counts_latest": refs.get("AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH"),
            "aoa_session_memory_latest": refs.get("AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH"),
            "summary": token_accounting_profiles.get("summary"),
            "aoa_session_memory": {
                "ok": aoa_token_summary.get("ok"),
                "summary": aoa_token_summary.get("summary"),
                "planning": aoa_token_summary.get("planning"),
                "source_truth_owner": aoa_token_summary.get("source_truth_owner"),
                "source_truth": aoa_token_summary.get("source_truth"),
            },
            "contract": refs.get("TOKEN_ACCOUNTING_CONTRACT"),
            "contract_schema_version": refs.get("TOKEN_ACCOUNTING_SCHEMA_VERSION"),
        },
        "eval": {
            "latest": refs.get("AI_EVAL_LATEST_PATH"),
            "ok": latest_eval.get("ok"),
            "summary": latest_eval.get("summary"),
            "generated_at": latest_eval.get("generated_at"),
        },
        "tts": {
            "latest": refs.get("AI_TTS_LATEST_PATH"),
            "profiles_latest": refs.get("AI_TTS_PROFILES_LATEST_PATH"),
            "eval_latest": refs.get("AI_TTS_EVAL_LATEST_PATH"),
            "eval_latest_success": refs.get("AI_TTS_EVAL_LATEST_SUCCESS_PATH"),
            "eval_latest_success_by_profile": refs.get("AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH"),
            "eval_success_by_profile_root": refs.get("AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT"),
            "server_latest": refs.get("AI_TTS_SERVER_LATEST_PATH"),
            "profiles_summary": tts_profiles.get("summary"),
            "latest_eval_ok": latest_tts_eval.get("ok"),
            "latest_eval_summary": latest_tts_eval.get("summary"),
            "latest_success_ok": latest_tts_success.get("ok"),
            "latest_success_generated_at": latest_tts_success.get("generated_at"),
            "latest_success_summary": latest_tts_success.get("summary"),
            "server": {
                "ok": tts_server.get("ok"),
                "socket": tts_server.get("socket"),
                "ping": tts_server.get("ping"),
                "service": tts_server.get("service"),
            },
        },
        "benchmark": {
            "latest": refs.get("AI_BENCHMARK_LATEST_PATH"),
            "ok": latest_benchmark.get("ok"),
            "summary": latest_benchmark.get("summary"),
            "generated_at": latest_benchmark.get("generated_at"),
        },
        "workload": {
            "latest": refs.get("AI_WORKLOAD_LATEST_PATH"),
            "ok": workload.get("ok"),
            "summary": workload.get("summary"),
            "routing": workload.get("routing"),
        },
        "cpu": {
            "topology_latest": refs.get("AI_CPU_TOPOLOGY_LATEST_PATH"),
            "thermal_map_latest": refs.get("AI_CPU_THERMAL_MAP_LATEST_PATH"),
            "route_latest": refs.get("AI_CPU_ROUTE_LATEST_PATH"),
            "test_latest": refs.get("AI_CPU_TEST_LATEST_PATH"),
            "route": {
                "allowed": cpu_route_latest.get("allowed"),
                "requested": cpu_route_latest.get("requested"),
                "route": cpu_route_latest.get("route"),
                "reasons": cpu_route_latest.get("reasons"),
            },
            "thermal": {
                "class": cpu_thermal_latest.get("class"),
                "summary": cpu_thermal_latest.get("summary"),
                "available_by_role_cpuset": cpu_thermal_latest.get("available_by_role_cpuset"),
            },
        },
        "cooling": {
            "latest": refs.get("COOLING_LATEST_PATH"),
            "ok": cooling_latest.get("ok"),
            "class": _nested_get(cooling_latest, ["temperature", "class"]),
            "temperature_c_max": _nested_get(cooling_latest, ["temperature", "summary", "temperature_c_max"]),
            "fan_mode": _nested_get(cooling_latest, ["fan", "fan_mode"]),
            "platform_profile": _nested_get(cooling_latest, ["power", "platform_profile", "current"]),
        },
        "dictation": {
            "default_profile": dictation.get("default_profile"),
            "server_socket_exists": dictation.get("server_socket_exists"),
        },
        "observability": {
            "latest": observability.get("latest"),
        },
        "bridge": {
            "manifest": refs.get("MANIFEST_PATH"),
            "agent_docs": refs.get("AI_AGENTS_PATH"),
            "index": refs.get("AI_INDEX_PATH"),
        },
        "non_claims": [
            "Host report is an integration support bundle, not an abyss-stack runtime promotion verdict.",
            "Use abyss-stack runtime-bench and machine-fit policies for stack-owned runtime decisions.",
        ],
    }
