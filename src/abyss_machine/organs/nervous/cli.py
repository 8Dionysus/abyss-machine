"""Nervous memory and knowledge (index, synthesis, semantic, recall) organ CLI, moved out of the abyss_machine core CLI.

The command group stays in `abyss_machine.cli`, which also serves the
host's raw capture, privacy and source subcommands; the core calls these
handlers lazily. Shared core helpers are reached as `_core.<name>`,
so callers and tests that patch `abyss_machine.cli` keep the same effect.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import fcntl
import fnmatch
import grp
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import secrets
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from abyss_machine import cli as _core

_ORGAN_PACKAGE = "abyss_machine.organs.nervous"
sys.dont_write_bytecode = True

globals().update(
    {
        "nervous_events_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_events_adapters"),
        "nervous_index_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_index_adapters"),
        "nervous_quality_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_quality_adapters"),
        "nervous_retrieval_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_retrieval_adapters"),
        "nervous_rerank_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_rerank_adapters"),
        "nervous_retention_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_retention_adapters"),
        "nervous_semantic_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_semantic_adapters"),
        "nervous_status_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_status_adapters"),
        "nervous_synthesis_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_synthesis_adapters"),
        "nervous_brief_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_brief"),
        "nervous_events_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_events"),
        "nervous_quality_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_quality"),
        "nervous_recall_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_recall"),
        "nervous_rerank_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_rerank"),
        "nervous_retention_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_retention"),
        "nervous_synthesis_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.nervous_synthesis"),
    }
)
from abyss_machine.organs.nervous.nervous_index import (
    allowed_source_ids as build_nervous_index_allowed_source_ids,
    build_index_build_document as build_nervous_index_build_document,
    build_index_derived_refresh_summary as build_nervous_index_derived_refresh_summary,
    build_index_disabled_result as build_nervous_index_disabled_result,
    build_index_fts_unavailable_result as build_nervous_index_fts_unavailable_result,
    build_index_global_pause_refused_result as build_nervous_index_global_pause_refused_result,
    build_index_projection as build_nervous_index_projection,
    build_index_semantic_lock_deferred_result as build_nervous_index_semantic_lock_deferred_result,
    chunks_from_record as build_nervous_index_chunks_from_record,
    compact_json_for_index as build_nervous_index_compact_json,
    deferred_source_ids as build_nervous_index_deferred_source_ids,
    enabled_index_source_ids as build_nervous_index_enabled_index_source_ids,
    enabled_safe_source_ids as build_nervous_index_enabled_safe_source_ids,
    fact_index_payload as build_nervous_index_fact_index_payload,
    fact_source_id as build_nervous_index_fact_source_id,
    index_source_files as build_nervous_index_source_files,
    load_source_records as build_nervous_index_load_source_records,
    nervous_index_bounded_validate_from_status as build_nervous_index_bounded_validate_from_status,
    parse_duration_seconds as build_nervous_index_parse_duration_seconds,
    nervous_index_schema_sql as build_nervous_index_schema_sql,
    record_is_safe_for_index as build_nervous_index_record_is_safe_for_index,
    search_dedupe_key as build_nervous_index_search_dedupe_key,
    search_dedupe_results as build_nervous_index_search_dedupe_results,
    search_match_query as build_nervous_index_search_match_query,
    search_sort_key as build_nervous_index_search_sort_key,
    sort_source_records as build_nervous_index_sort_source_records,
    vacuum_error_result as build_nervous_index_vacuum_error_result,
    vacuum_missing_db_result as build_nervous_index_vacuum_missing_db_result,
    vacuum_refused_result as build_nervous_index_vacuum_refused_result,
    vacuum_start_document as build_nervous_index_vacuum_start_document,
    vacuum_success_result as build_nervous_index_vacuum_success_result,
)
from abyss_machine.organs.nervous.nervous_synthesis import (
    build_candidate as build_nervous_synthesis_candidate,
    markdown as build_nervous_synthesis_markdown,
    period_jsonl_path as build_nervous_synthesis_period_jsonl_path,
    record_ids as build_nervous_record_ids,
    record_time_value as build_nervous_record_time_value,
    select_events_for_episode_ids as build_nervous_events_for_episode_ids,
    select_period_episodes as build_nervous_episodes_for_period,
    validate_records as build_nervous_synthesis_validate,
)
from abyss_machine.organs.nervous.nervous_semantic import (
    age_minutes as build_nervous_semantic_age_minutes,
    batch_policy as build_nervous_semantic_batch_policy,
    body_preview as build_nervous_semantic_body_preview,
    build_command as build_nervous_semantic_build_command,
    build_status as build_nervous_semantic_status,
    dedupe_results as build_nervous_semantic_dedupe_results,
    dot as build_nervous_semantic_dot,
    embedding_text as build_nervous_semantic_embedding_text,
    embedding_input_jsonl as build_nervous_semantic_embedding_input_jsonl,
    embedding_runtime_options as build_nervous_semantic_embedding_runtime_options,
    embedding_subprocess_command as build_nervous_semantic_embedding_subprocess_command,
    embedding_subprocess_result as build_nervous_semantic_embedding_subprocess_result,
    embedding_window_size as build_nervous_semantic_embedding_window_size,
    maintain_assess as build_nervous_semantic_maintain_assess,
    maintain_index_refresh_assess as build_nervous_semantic_maintain_index_refresh_assess,
    query_text as build_nervous_semantic_query_text,
    schema_sql as build_nervous_semantic_schema_sql,
    search_with_vector as build_nervous_semantic_search_with_vector,
    search_sort_key as build_nervous_semantic_search_sort_key,
    vector_from_blob as build_nervous_semantic_vector_from_blob,
)

dictation_cli = _core._lazy_import_module("abyss_machine.organs.dictation.cli", allow_eager=False)
ai_cli = _core._lazy_import_module("abyss_machine.organs.ai.cli", allow_eager=False)
artifacts_cli = _core._lazy_import_module("abyss_machine.organs.artifacts.cli", allow_eager=False)


NERVOUS_BRIEF_CACHE: dict[str, dict[str, Any]] = {}


def user_systemd_running_units(pattern: str) -> list[dict[str, str]]:
    out = _core.run(
        [
            "systemctl",
            "--user",
            "list-units",
            "--type=service",
            "--state=running",
            "--no-legend",
            "--no-pager",
            pattern,
        ],
        timeout=2.0,
    )
    if not out.get("ok"):
        return []
    units: list[dict[str, str]] = []
    for line in str(out.get("stdout") or "").splitlines():
        parts = line.split(None, 4)
        if not parts:
            continue
        units.append({
            "unit": parts[0],
            "load": parts[1] if len(parts) > 1 else "",
            "active": parts[2] if len(parts) > 2 else "",
            "sub": parts[3] if len(parts) > 3 else "",
            "description": parts[4] if len(parts) > 4 else "",
        })
    return units


def nervous_derived_refresh_status() -> dict[str, Any]:
    passive_unit = _core.user_systemd_unit(_core.NERVOUS_PASSIVE_CHRONICLE_SERVICE)
    derived_unit = _core.user_systemd_unit(_core.NERVOUS_DERIVED_REFRESH_SERVICE)
    passive_show = _core.systemd_unit_properties(_core.NERVOUS_PASSIVE_CHRONICLE_SERVICE, ["OnSuccess", "FragmentPath"], user=True)
    derived_show = _core.systemd_unit_properties(_core.NERVOUS_DERIVED_REFRESH_SERVICE, ["LoadState", "FragmentPath", "ExecStart"], user=True)
    return nervous_quality_contracts.derived_refresh_status_document(
        passive_unit=passive_unit,
        derived_unit=derived_unit,
        passive_show=passive_show,
        derived_show=derived_show,
        passive_service=_core.NERVOUS_PASSIVE_CHRONICLE_SERVICE,
        derived_service=_core.NERVOUS_DERIVED_REFRESH_SERVICE,
        dropin_path=str(_core.NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH),
        dropin_exists=_core.NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH.exists(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def default_nervous_policy() -> dict[str, Any]:
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_policy_v1",
        "version": _core.VERSION,
        "mode": "passive-local-capture",
        "active_daemon": False,
        "activation": {
            "watcher_enabled": False,
            "automatic_actions_enabled": False,
            "browser_capture_enabled": True,
            "terminal_capture_enabled": True,
            "clipboard_capture_enabled": True,
            "typed_text_capture_enabled": True,
            "screenshot_capture_enabled": True,
            "passive_chronicle_timer_enabled": True,
            "passive_chronicle_interval": "15min",
            "browser_content_capture_timer_enabled": True,
            "browser_content_capture_interval": "120s",
            "local_index_timer_enabled": True,
            "local_index_interval": "45min",
        },
        "browser_content": {
            "method": "browser_accessibility_tree_primary_with_firefox_bidi_diagnostic",
            "bidi_url": _core.NERVOUS_BROWSER_BIDI_DEFAULT_URL,
            "captures": "Firefox/Chromium-family document text through AT-SPI during normal browsing; Firefox BiDi only when explicitly launched in diagnostic mode",
            "normal_browser_launch": "must not add --remote-debugging-port; use accessibility bridge env only",
            "firefox_accessibility_env": "GNOME_ACCESSIBILITY=1 NO_AT_BRIDGE=0 GTK_MODULES=gail:atk-bridge",
            "fast_tick": "abyss-nervous-browser-content-capture.timer runs about every 120s while a supported browser is open, uses a bounded focused/visible-first AT-SPI budget, and skips when supported browsers are closed",
            "dedupe": "raw captures are deduplicated by url hash, title hash, text hash, and skipped_text flag before append",
            "privacy": "no cookies, no localStorage, no form values; body text is skipped on login/password-like pages",
            "storage": str(_core.NERVOUS_BROWSER_CONTENT_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        },
        "automation": {
            "passive_chronicle": {
                "enabled": True,
                "scope": "user",
                "service": _core.NERVOUS_PASSIVE_CHRONICLE_SERVICE,
                "timer": _core.NERVOUS_PASSIVE_CHRONICLE_TIMER,
                "command": "abyss-machine nervous snapshot --json",
                "interval": "15min",
                "stdout": "null",
                "source_class": "safe_and_private_connector_facts",
                "on_success": _core.NERVOUS_DERIVED_REFRESH_SERVICE,
            },
            "browser_content_capture": {
                "enabled": True,
                "scope": "user",
                "service": _core.NERVOUS_BROWSER_CONTENT_CAPTURE_SERVICE,
                "timer": _core.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER,
                "command": str(_core.PATH_POLICY.home / ".local/bin/abyss-nervous-browser-content-capture-tick"),
                "interval": "120s",
                "stdout": "null",
                "source_class": "local_private_firefox_page_text",
                "idle_behavior": "exit 0 without writing when supported browsers are closed",
            },
            "typed_text_autolog": {
                "enabled": True,
                "scope": "explicit_committed_text_adapters",
                "command": "abyss-machine typing ingest --stdin --source SOURCE --json",
                "source_class": "redacted_committed_text_or_metadata_only",
                "raw_keylogging": False,
                "password_fields_captured": False,
                "automatic_actions": False,
            },
            "derived_events": {
                "enabled": True,
                "scope": "user",
                "command": "abyss-machine nervous events-build --json",
                "trigger": "after passive chronicle snapshot, before local_index build, and on operator demand",
                "source_class": "fact_snapshots_only",
                "stdout": "json",
            },
            "derived_episodes": {
                "enabled": True,
                "scope": "user",
                "command": "abyss-machine nervous episodes-build --json",
                "trigger": "after passive chronicle snapshot, before local_index build, and on operator demand",
                "source_class": "derived_events_only",
                "stdout": "json",
            },
            "derived_refresh": {
                "enabled": True,
                "scope": "user",
                "service": _core.NERVOUS_DERIVED_REFRESH_SERVICE,
                "trigger": f"OnSuccess={_core.NERVOUS_DERIVED_REFRESH_SERVICE} from {_core.NERVOUS_PASSIVE_CHRONICLE_SERVICE}",
                "dropin": str(_core.NERVOUS_PASSIVE_CHRONICLE_DERIVED_DROPIN_PATH),
                "commands": [
                    "abyss-machine nervous quality-audit --refresh --json",
                    "abyss-machine resource launch --class medium --kind indexing --unattended --timeout 300 --success-on-block --json -- abyss-machine nervous index-build --json",
                ],
                "policy": "deterministic derived refresh runs first; SQLite/FTS refresh remains resource-gated and may skip on game/memory/thermal pressure",
            },
            "local_index": {
                "enabled": True,
                "scope": "user",
                "service": _core.NERVOUS_SEARCH_INDEX_SERVICE,
                "timer": _core.NERVOUS_SEARCH_INDEX_TIMER,
                "command": "abyss-machine nervous index-build --json",
                "interval": "45min",
                "stdout": "null",
                "source_class": "redacted_fact_event_episode_records",
                "storage": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
            },
            "retrieval_packs": {
                "enabled": True,
                "scope": "operator_command",
                "command": "abyss-machine nervous recall --query TEXT --json",
                "hybrid_command": "abyss-machine nervous recall --mode hybrid --query TEXT --json",
                "rerank_command": "abyss-machine nervous rerank --query TEXT --json",
                "source_class": "local_index_plus_optional_semantic_sidecar",
                "automatic_actions": False,
            },
            "agent_brief": {
                "enabled": True,
                "scope": "operator_command",
                "command": "abyss-machine nervous brief --scope now --json",
                "source_class": "quality_index_semantic_status_recent_episodes",
                "automatic_actions": False,
            },
            "synthesis_candidates": {
                "enabled": True,
                "scope": "operator_command",
                "command": "abyss-machine nervous synthesis-build --scope daily --json",
                "source_class": "derived_episodes_and_events_only",
                "llm_required": False,
                "automatic_repo_writes": False,
            },
            "retention": {
                "enabled": True,
                "scope": "operator_command",
                "plan_command": "abyss-machine nervous retention-plan --json",
                "apply_command": "abyss-machine nervous retention-apply --dry-run --json",
                "facts_delete_behavior": "explicit forget only",
            },
        },
        "boundaries": {
            "machine_layer": "host facts, storage routes, privacy policy, passive local evidence",
            "stack_layer": "runtime services and future service bridge consumers",
            "aoa_repositories": "source material under reformation, read-only until each repo publishes a stable import contract",
            "forbidden_write_roots": [
                str(_core.ABYSS_STACK_USER_SOURCE_ROOT),
                "/srv/AbyssOS/abyss-stack",
                "/srv/abyss-stack",
            ],
            "machine_large_data_root": str(_core.ABYSS_MACHINE_ROOT),
            "compact_state_root": str(_core.STATE_DIR),
            "stable_config_root": "/etc/abyss-machine",
            "work_root_rule": "Do not use /work for machine-owned caches, runtimes, model artifacts, or logs.",
            "symlink_tail_rule": "Do not leave symlink tails for machine-owned routes unless explicitly approved.",
        },
        "pipeline": [
            "observe",
            "filter",
            "classify",
            "route",
            "index",
            "summarize",
            "retrieve",
            "rerank",
            "synthesize",
            "verify",
            "record",
        ],
        "promotion_rules": [
            "Candidate models and services are promoted only with local evidence.",
            "Community reports are signals, not promotion evidence.",
            "Private connector facts require explicit source policy, redaction, retention, and audit.",
            "Absent measurements must stay absent; do not invent benchmark claims.",
        ],
    }


def default_nervous_index_config() -> dict[str, Any]:
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_index_config_v1",
        "version": _core.VERSION,
        "enabled": True,
        "backend": "sqlite_fts5",
        "db_path": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
        "source": {
            "kind": "passive_fact_events_episodes",
            "facts_root": str(_core.NERVOUS_FACTS_ROOT),
            "facts_glob": str(_core.NERVOUS_FACTS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "events_root": str(_core.NERVOUS_EVENTS_ROOT),
            "events_glob": str(_core.NERVOUS_EVENTS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "episodes_root": str(_core.NERVOUS_EPISODES_ROOT),
            "episodes_glob": str(_core.NERVOUS_EPISODES_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "latest": str(_core.NERVOUS_FACTS_LATEST_PATH),
            "raw_private_content": False,
        },
        "storage": {
            "large_root": str(_core.ABYSS_MACHINE_STORAGE_ROOT),
            "index_root": str(_core.NERVOUS_SEARCH_INDEX_ROOT),
            "compact_state_latest": str(_core.NERVOUS_SEARCH_INDEX_LATEST_PATH),
            "schema_path": str(_core.NERVOUS_SEARCH_INDEX_SCHEMA_PATH),
            "no_symlink_tails": True,
        },
        "privacy": {
            "enforce_global_pause": True,
            "index_only_existing_fact_snapshots": False,
            "index_only_existing_fact_event_episode_records": True,
            "deferred_sources_allowed": True,
            "redact_before_insert": True,
            "forget_requires_rebuild": True,
        },
        "search": {
            "tokenizer": "unicode61",
            "default_limit": 12,
            "max_limit": 50,
            "snippet_tokens": 18,
        },
        "semantic": {
            "enabled": True,
            "backend": "sqlite_float32_sidecar",
            "db_path": str(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH),
            "latest": str(_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH),
            "source_index_db_path": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
            "embedding": {
                "model_dir": str(ai_cli.default_ai_config().get("eval", {}).get("embedding_model")),
                "device": str(ai_cli.default_ai_config().get("eval", {}).get("embedding_device", "AUTO:GPU,CPU")),
                "dimension": 1024,
                "max_tokens": 512,
                "max_input_chars": 2400,
                "batch_size": 16,
                "timeout_sec": 1800,
            },
            "search": {
                "default_limit": 12,
                "max_limit": 50,
                "candidate_limit": 50,
                "dedupe": True,
            },
            "automation": {
                "enabled": False,
                "reason": "pilot is on-demand only; no resident embedding service and no timer yet",
            },
        },
        "automation": {
            "scope": "user",
            "service": _core.NERVOUS_SEARCH_INDEX_SERVICE,
            "timer": _core.NERVOUS_SEARCH_INDEX_TIMER,
            "interval": "45min",
            "command": "abyss-machine nervous index-build --json",
            "stdout": "null",
            "priority": "nice+ionice",
        },
        "bridge_contract": {
            "consumer": "future abyss-stack bridge",
            "read_commands": [
                "abyss-machine nervous index-status --json",
                "abyss-machine nervous index-validate --json",
                "abyss-machine nervous search --query TEXT --json",
                "abyss-machine nervous rerank --query TEXT --json",
                "abyss-machine nervous search --query TEXT --source nervous_events --json",
                "abyss-machine nervous recall --query TEXT --json",
                "abyss-machine nervous recall --mode hybrid --query TEXT --json",
                "abyss-machine nervous brief --scope now --json",
                "abyss-machine nervous synthesis-latest --json",
                "abyss-machine nervous eval-latest --json",
                "abyss-machine nervous retention-plan --json",
            ],
            "write_commands": [
                "abyss-machine nervous events-build --json",
                "abyss-machine nervous episodes-build --json",
                "abyss-machine nervous index-build --json",
                "abyss-machine nervous synthesis-build --scope daily --json",
                "abyss-machine nervous eval-run --json",
                "abyss-machine nervous retention-apply --dry-run --json",
                "abyss-machine nervous index-vacuum --json",
            ],
            "no_repo_mutation": [
                str(_core.ABYSS_STACK_USER_SOURCE_ROOT),
                "/srv/AbyssOS/abyss-stack",
                "/srv/abyss-stack",
            ],
        },
    }


def nervous_config_document(path: Path, defaults: dict[str, Any]) -> dict[str, Any]:
    loaded, error = _core.load_json_document(path)
    if loaded is None:
        doc = defaults
        if error != "missing":
            doc["_load_error"] = error
        doc["_config_exists"] = False
    else:
        doc = _core.deep_merge(defaults, loaded)
        doc["_config_exists"] = True
    doc["_config_path"] = str(path)
    return doc


def nervous_index_config() -> dict[str, Any]:
    data = nervous_config_document(_core.NERVOUS_INDEX_CONFIG_PATH, default_nervous_index_config())
    data["generated_at"] = _core.now_iso()
    data["ok"] = data.get("_load_error") is None
    return data


def nervous_change_id(prefix: str) -> str:
    raw = f"{prefix}:{_core.now_iso()}:{os.getpid()}:{time.monotonic_ns()}"
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def nervous_latest() -> dict[str, Any]:
    return _core.typing_nervous_adapters.read_latest_document(
        _core.NERVOUS_LATEST_PATH,
        f"{_core.SCHEMA_PREFIX}_nervous_latest_read_v1",
        version=_core.VERSION,
        now=_core.now_iso,
        default_existing_ok=True,
    )


NERVOUS_BROWSER_BOILERPLATE_PATTERNS = [
    r"^skip to content$",
    r"^перейти к содержимому$",
    r"^type / to search$",
    r"^repository navigation$",
    r"^repository files navigation$",
    r"^footer navigation$",
    r"^footer ©",
    r"^terms privacy status community docs contact$",
    r"^terms privacy",
    r"^github profile guide$",
    r"^user navigation$",
    r"^overview$",
    r"^repositories$",
    r"^packages$",
    r"^watch(?:ers watching)?$",
    r"^stars?$",
    r"^forks?$",
    r"^branches?$",
    r"^tags?$",
    r"^settings$",
    r"^insights$",
    r"^security and quality$",
    r"^actions$",
    r"^projects$",
    r"^wiki$",
    r"^issues$",
    r"^pull requests$",
    r"^add file$",
    r"^folders and files$",
    r"^last commit (message|date)$",
    r"^latest commit$",
    r"^history$",
    r"^code of conduct$",
    r"^contributing$",
    r"^apache-2\.0 license$",
    r"^security$",
    r"^вход$",
    r"^регистрация$",
    r"^главная$",
    r"^новинки$",
    r"^топ (фильмов|сериалов|мультфильмов|мультсериалов|аниме)$",
    r"^панель навигации \|?$",
    r"^мои списки$",
    r"^все фильмы$",
    r"^созданные$",
    r"^сохраненные$",
    r"^создать$",
    r"^изменить профиль$",
]


NERVOUS_BROWSER_MEDIA_PATTERNS = [
    r"\b(пауза|воспроизвести) \(space\)",
    r"\bпредыдущая серия\b",
    r"\bследующая серия\b",
    r"\bвыключить звук\b",
    r"\bвыключить субтитры\b",
    r"\bвыйти из полноэкранного режима\b",
    r"^\d{1,2}:\d{2}$",
    r"^/\d{1,2}:\d{2}$",
    r"^⁄\d{1,2}:\d{2}$",
]


NERVOUS_BROWSER_BOILERPLATE_PATTERNS = _core.nervous_source_contracts.BROWSER_BOILERPLATE_PATTERNS


NERVOUS_BROWSER_MEDIA_PATTERNS = _core.nervous_source_contracts.BROWSER_MEDIA_PATTERNS


def nervous_fact_freshness(data: dict[str, Any]) -> dict[str, Any]:
    source_time = data.get("updated_at") or data.get("generated_at")
    return {
        "source_time": source_time,
        "age_sec": _core.age_seconds_from_iso(source_time),
        "basis": "updated_at_or_generated_at",
    }


def nervous_json_fact(name: str, path: Path) -> dict[str, Any]:
    data, error = _core.load_json_document(path)
    source = _core.nervous_file_source(path)
    fact: dict[str, Any] = {
        "name": name,
        "path": str(path),
        "exists": path.exists(),
        "ok": data is not None,
        "source": source,
    }
    if data is None:
        fact["error"] = error or "missing"
        return fact
    for key in ("schema", "version", "generated_at", "updated_at", "ok", "status", "phase"):
        if key in data:
            fact[key] = data.get(key)
    fact["freshness"] = nervous_fact_freshness(data)
    if isinstance(data.get("summary"), dict):
        fact["summary"] = data["summary"]
    return fact


def nervous_ai_llm_registry_fact() -> dict[str, Any]:
    data, error = _core.load_json_document(_core.AI_LLM_REGISTRY_LATEST_PATH)
    source = _core.nervous_file_source(_core.AI_LLM_REGISTRY_LATEST_PATH)
    fact: dict[str, Any] = {
        "name": "ai_llm_registry_latest",
        "path": str(_core.AI_LLM_REGISTRY_LATEST_PATH),
        "exists": _core.AI_LLM_REGISTRY_LATEST_PATH.exists(),
        "ok": data is not None,
        "source": source,
    }
    if data is None:
        fact["error"] = error or "missing"
        return fact
    for key in ("schema", "version", "generated_at", "updated_at", "ok", "backend"):
        if key in data:
            fact[key] = data.get(key)
    if isinstance(data.get("summary"), dict):
        fact["summary"] = data["summary"]
    profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
    fact["profiles"] = {
        profile_id: {
            "status": profile.get("status"),
            "role": profile.get("role"),
            "backend": profile.get("backend"),
            "model_id": profile.get("model_id"),
            "hf_file": profile.get("hf_file"),
            "quant": profile.get("quant"),
            "declared_class": profile.get("declared_class"),
            "warm_policy": profile.get("warm_policy"),
            "local_path": profile.get("local_path"),
            "local_exists": profile.get("local_exists"),
            "size_bytes": profile.get("size_bytes"),
        }
        for profile_id, profile in profiles.items()
        if isinstance(profile, dict)
    }
    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    fact["runtime"] = {
        "name": runtime.get("name"),
        "configured_version": runtime.get("configured_version"),
        "backend": runtime.get("backend"),
        "root": runtime.get("root"),
        "llama_server": runtime.get("llama_server"),
        "server_exists": runtime.get("server_exists"),
        "ok": runtime.get("ok"),
    }
    return fact


def nervous_ai_llm_resident_status_fact() -> dict[str, Any]:
    path = _core.AI_LLM_RESIDENT_ROOT / "status" / "latest.json"
    data, error = _core.load_json_document(path)
    source = _core.nervous_file_source(path)
    fact: dict[str, Any] = {
        "name": "ai_llm_resident_status_latest",
        "path": str(path),
        "exists": path.exists(),
        "ok": data is not None,
        "source": source,
    }
    if data is None:
        fact["error"] = error or "missing"
        return fact
    for key in ("schema", "version", "generated_at", "updated_at", "ok", "status", "profile"):
        if key in data:
            fact[key] = data.get(key)
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
    service = data.get("service") if isinstance(data.get("service"), dict) else {}
    health = data.get("health") if isinstance(data.get("health"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    fact["model"] = {
        "path": model.get("path"),
        "exists": model.get("exists"),
        "size_bytes": model.get("size_bytes"),
    }
    fact["runtime"] = {
        "llama_server": runtime.get("llama_server"),
        "exists": runtime.get("exists"),
    }
    fact["service"] = {
        "service": service.get("service"),
        "active": service.get("active"),
        "enabled": service.get("enabled"),
        "timer": service.get("timer"),
        "monitor_timer": service.get("monitor_timer"),
        "digest_timer": service.get("digest_timer"),
        "jobs_timer": service.get("jobs_timer"),
        "micro_timer": service.get("micro_timer"),
    }
    fact["health"] = {
        "base_url": health.get("base_url"),
        "ok": health.get("ok"),
    }
    fact["metrics"] = {
        "package_temp_c": metrics.get("package_temp_c"),
        "loadavg": metrics.get("loadavg"),
        "power": metrics.get("power"),
    }
    return fact


def nervous_ai_llm_resident_candidates_fact() -> dict[str, Any]:
    path = _core.AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH
    data, error = _core.load_json_document(path)
    source = _core.nervous_file_source(path)
    fact: dict[str, Any] = {
        "name": "ai_llm_resident_candidates_latest",
        "source_id": "abyss_machine_facts",
        "path": str(path),
        "exists": path.exists(),
        "ok": data is not None and bool(data.get("ok")),
        "source": source,
        "raw_private_content": False,
    }
    if data is None:
        fact["error"] = error or "missing"
        return fact
    for key in ("schema", "version", "generated_at", "updated_at", "ok", "status", "profile", "mode"):
        if key in data:
            fact[key] = data.get(key)
    if isinstance(data.get("summary"), dict):
        fact["summary"] = data["summary"]
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    fact["entries"] = [
        {
            "candidate_id": item.get("candidate_id"),
            "kind": item.get("kind"),
            "source_job": item.get("source_job"),
            "source_id": item.get("source_id"),
            "title": item.get("title"),
            "text": item.get("text"),
            "score": item.get("score"),
            "risk": item.get("risk"),
            "route": item.get("route"),
            "review_required": item.get("review_required"),
            "action_execution": item.get("action_execution"),
        }
        for item in candidates[:64]
        if isinstance(item, dict)
    ]
    queues = data.get("queues") if isinstance(data.get("queues"), dict) else {}
    fact["content_entries"] = {
        key: len(value) if isinstance(value, list) else 0
        for key, value in queues.items()
    }
    fact["commands"] = data.get("commands") if isinstance(data.get("commands"), dict) else {}
    return fact


def nervous_dictation_status_fact() -> dict[str, Any]:
    data = dictation_cli.dictation_status()
    service = _core.user_systemd_unit("abyss-dictation-server.service")
    active = str(service.get("active") or "unknown")
    enabled = str(service.get("enabled") or "unknown")
    socket_exists = bool(data.get("server_socket_exists"))
    fact: dict[str, Any] = {
        "name": "dictation_status_live",
        "path": str(dictation_cli.dictation_state_file()),
        "exists": dictation_cli.dictation_state_file().exists(),
        "ok": bool(service.get("is_active") and socket_exists),
        "source": _core.nervous_virtual_source(
            "abyss_machine_facts",
            {"name": "dictation_status_live", "dictation": data, "service": service},
            "dictation-status-live",
        ),
        "schema": data.get("schema"),
        "version": data.get("version"),
        "generated_at": data.get("generated_at") or _core.now_iso(),
        "status": active,
        "service": service,
        "server": data.get("server"),
        "server_socket": data.get("server_socket"),
        "server_socket_exists": socket_exists,
        "recording_active": data.get("recording_active"),
        "default_profile": data.get("default_profile"),
        "summary": {
            "capability": "speech_to_text_dictation",
            "unit": "abyss-dictation-server.service",
            "active": active,
            "enabled": enabled,
            "socket_exists": socket_exists,
            "recording_active": data.get("recording_active"),
            "default_profile": data.get("default_profile"),
        },
        "text": (
            "local speech dictation voice input service "
            f"abyss-dictation-server.service active={active} enabled={enabled} "
            f"running={bool(service.get('is_active'))} server_socket_exists={socket_exists}"
        ),
    }
    return fact


def nervous_ai_tts_server_status_fact() -> dict[str, Any]:
    data = ai_cli.ai_tts_server_status(write_latest=False)
    service = data.get("service") if isinstance(data.get("service"), dict) else _core.user_systemd_unit("abyss-tts-server.service")
    ping = data.get("ping") if isinstance(data.get("ping"), dict) else {}
    active = str(service.get("active") or "unknown")
    enabled = str(service.get("enabled") or "unknown")
    socket_exists = bool(data.get("socket_exists"))
    fact: dict[str, Any] = {
        "name": "ai_tts_server_status_live",
        "path": str(_core.AI_TTS_SERVER_LATEST_PATH),
        "exists": _core.AI_TTS_SERVER_LATEST_PATH.exists(),
        "ok": bool(data.get("ok")),
        "source": _core.nervous_virtual_source(
            "abyss_machine_facts",
            {"name": "ai_tts_server_status_live", "server": data},
            "tts-server-status-live",
        ),
        "schema": data.get("schema"),
        "version": data.get("version"),
        "generated_at": data.get("generated_at") or _core.now_iso(),
        "status": active,
        "service": service,
        "socket": data.get("socket"),
        "socket_exists": socket_exists,
        "ping": ping,
        "summary": {
            "capability": "text_to_speech_voice_output",
            "unit": "abyss-tts-server.service",
            "active": active,
            "enabled": enabled,
            "socket_exists": socket_exists,
            "ping_ok": ping.get("ok"),
            "profile": ping.get("profile"),
        },
        "text": (
            "local speech voice text to speech tts output service "
            f"abyss-tts-server.service active={active} enabled={enabled} "
            f"running={bool(service.get('is_active'))} socket_exists={socket_exists} ping_ok={bool(ping.get('ok'))}"
        ),
    }
    return fact


def nervous_observability_fact() -> dict[str, Any]:
    path = _core.OBSERVABILITY_ROOT / "thermal-battery" / "latest.json"
    data, error = _core.load_json_document(path)
    source = _core.nervous_file_source(path)
    fact: dict[str, Any] = {
        "name": "observability_thermal_battery_latest",
        "path": str(path),
        "exists": path.exists(),
        "ok": data is not None,
        "source": source,
    }
    if data is None:
        fact["error"] = error or "missing"
        return fact
    sample = data.get("sample") if isinstance(data.get("sample"), dict) else {}
    fact.update({
        "schema": data.get("schema"),
        "generated_at": data.get("generated_at"),
        "updated_at": data.get("updated_at"),
        "sample_generated_at": sample.get("generated_at") if isinstance(sample, dict) else None,
        "freshness": nervous_fact_freshness(data),
        "class": sample.get("class") if isinstance(sample, dict) else None,
        "thermal": {
            "temperature_c_max": _core.nested_get(sample, ["thermal", "sensors", "temperature_c_max"]) if isinstance(sample, dict) else None,
            "hottest": _core.nested_get(sample, ["thermal", "sensors", "hottest"]) if isinstance(sample, dict) else None,
        },
        "battery": _core.nested_get(sample, ["power", "battery"]) if isinstance(sample, dict) else None,
    })
    return fact


def nervous_explicit_metadata_roots() -> list[Path]:
    home = Path(os.environ.get("HOME", str(_core.PATH_POLICY.home)))
    return [
        home / "src",
        Path("/srv/AbyssOS"),
        _core.ABYSS_MACHINE_ROOT,
        _core.STATE_DIR,
    ]


def nervous_filesystem_metadata_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "filesystem_metadata"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    exclusions = [str(item) for item in sources.get("exclusions", [])] if isinstance(sources.get("exclusions"), list) else []
    roots: list[dict[str, Any]] = []
    total_entries = 0
    max_entries_per_root = 160
    max_depth = 3
    for root in nervous_explicit_metadata_roots():
        root_report: dict[str, Any] = {
            "path": str(root),
            "exists": root.exists(),
            "entries": [],
            "truncated": False,
        }
        if not root.exists():
            roots.append(root_report)
            continue
        base_depth = len(root.parts)
        try:
            for current, dirnames, filenames in os.walk(root):
                current_path = Path(current)
                depth = len(current_path.parts) - base_depth
                dirnames[:] = sorted([
                    dirname
                    for dirname in dirnames
                    if not _core.nervous_excluded_capture_path(current_path / dirname, exclusions)
                ])
                if depth >= max_depth:
                    dirnames[:] = []
                names = [(name, True) for name in dirnames] + [(name, False) for name in sorted(filenames)]
                for name, is_dir in names:
                    path = current_path / name
                    if _core.nervous_excluded_capture_path(path, exclusions):
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    try:
                        relative = str(path.relative_to(root))
                    except ValueError:
                        relative = str(path)
                    root_report["entries"].append({
                        "relative_path": relative,
                        "type": "dir" if is_dir else "file",
                        "size_bytes": stat.st_size,
                        "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
                    })
                    total_entries += 1
                    if len(root_report["entries"]) >= max_entries_per_root:
                        root_report["truncated"] = True
                        dirnames[:] = []
                        break
                if root_report["truncated"]:
                    break
        except OSError as exc:
            root_report["error"] = str(exc)
        roots.append(root_report)
    payload = {
        "roots": roots,
        "max_depth": max_depth,
        "max_entries_per_root": max_entries_per_root,
        "total_entries": total_entries,
        "exclusions": exclusions,
    }
    return {
        "name": "filesystem_metadata",
        "source_id": source_id,
        "ok": True,
        "observed_at": _core.now_iso(),
        "sensitivity": "machine_metadata",
        "summary": {
            "roots": len(roots),
            "entries": total_entries,
            "truncated_roots": sum(1 for item in roots if item.get("truncated")),
        },
        "roots": roots,
        "source": _core.nervous_virtual_source(source_id, payload),
    }, None


def nervous_git_explicit_repositories_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "git_explicit_repositories"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    repos: list[dict[str, Any]] = []
    roots = [Path(os.environ.get("HOME", str(_core.PATH_POLICY.home))) / "src", Path("/srv/AbyssOS")]
    for root in roots:
        if not root.exists():
            continue
        candidates: list[Path] = []
        for current, dirnames, _filenames in os.walk(root):
            current_path = Path(current)
            if ".git" in dirnames:
                candidates.append(current_path)
                dirnames[:] = []
                continue
            if len(current_path.parts) - len(root.parts) >= 3:
                dirnames[:] = []
        for repo in sorted(candidates)[:80]:
            branch = _core.run(["git", "-C", str(repo), "branch", "--show-current"], timeout=2.0)
            head = _core.run(["git", "-C", str(repo), "rev-parse", "--short=12", "HEAD"], timeout=2.0)
            status = _core.run(["git", "-C", str(repo), "status", "--porcelain=v1", "-uno"], timeout=3.0)
            lines = str(status.get("stdout") or "").splitlines() if status.get("ok") else []
            repos.append({
                "path": str(repo),
                "branch": str(branch.get("stdout") or "").strip() if branch.get("ok") else None,
                "head": str(head.get("stdout") or "").strip() if head.get("ok") else None,
                "dirty_entries": len(lines),
                "status_error": None if status.get("ok") else str(status.get("stderr") or "")[:400],
                "diffs_captured": False,
                "writes": False,
            })
    payload = {"repositories": repos}
    return {
        "name": "git_explicit_repositories",
        "source_id": source_id,
        "ok": True,
        "observed_at": _core.now_iso(),
        "sensitivity": "machine_metadata",
        "summary": {
            "repositories": len(repos),
            "dirty": sum(1 for item in repos if int(item.get("dirty_entries") or 0) > 0),
            "diffs_captured": False,
        },
        "repositories": repos,
        "source": _core.nervous_virtual_source(source_id, payload),
    }, None


def nervous_podman_metadata_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "podman_metadata"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    if not _core.command_exists("podman"):
        return {
            "name": "podman_metadata",
            "source_id": source_id,
            "ok": False,
            "observed_at": _core.now_iso(),
            "sensitivity": "machine_metadata",
            "error": "podman not installed",
            "source": _core.nervous_virtual_source(source_id, {"error": "podman not installed"}),
        }, None
    ps = _core.run(["podman", "ps", "-a", "--format", "json"], timeout=4.0)
    images = _core.run(["podman", "images", "--format", "json"], timeout=4.0)

    def parse_podman_json(stdout: str) -> Any:
        text = stdout.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            records = []
            for line in text.splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                records.append(item)
            return records

    containers_raw = parse_podman_json(str(ps.get("stdout") or "")) if ps.get("ok") else []
    images_raw = parse_podman_json(str(images.get("stdout") or "")) if images.get("ok") else []
    containers = []
    for item in containers_raw[:80] if isinstance(containers_raw, list) else []:
        if not isinstance(item, dict):
            continue
        containers.append({
            "id": item.get("Id") or item.get("ID") or item.get("ContainerID"),
            "name": item.get("Names") or item.get("Name"),
            "image": item.get("Image"),
            "state": item.get("State") or item.get("Status"),
            "created": item.get("Created") or item.get("CreatedAt"),
        })
    image_items = []
    for item in images_raw[:80] if isinstance(images_raw, list) else []:
        if not isinstance(item, dict):
            continue
        image_items.append({
            "id": item.get("Id") or item.get("ID"),
            "repository": item.get("Repository"),
            "tag": item.get("Tag"),
            "size": item.get("Size"),
            "created": item.get("Created") or item.get("CreatedAt"),
        })
    payload = {
        "containers": containers,
        "images": image_items,
        "ps_ok": ps.get("ok"),
        "images_ok": images.get("ok"),
        "env_captured": False,
        "create_command_captured": False,
    }
    return {
        "name": "podman_metadata",
        "source_id": source_id,
        "ok": bool(ps.get("ok")) and bool(images.get("ok")),
        "observed_at": _core.now_iso(),
        "sensitivity": "machine_metadata",
        "summary": {
            "containers": len(containers),
            "images": len(image_items),
            "running_or_created": sum(1 for item in containers if str(item.get("state") or "").lower() in {"running", "created"}),
            "env_captured": False,
            "create_command_captured": False,
        },
        "containers": containers,
        "images": image_items,
        "error": None if ps.get("ok") and images.get("ok") else {"ps": str(ps.get("stderr") or "")[:400], "images": str(images.get("stderr") or "")[:400]},
        "source": _core.nervous_virtual_source(source_id, payload),
    }, None


def nervous_terminal_activity_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "terminal_stdout_stderr"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    home = Path(os.environ.get("HOME", str(_core.PATH_POLICY.home)))
    history_path = home / ".zsh_history"
    commands: list[dict[str, Any]] = []
    if history_path.exists():
        try:
            lines = history_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            for line in lines:
                raw = line.split(";", 1)[1] if line.startswith(": ") and ";" in line else line
                payload = _core.nervous_text_payload(raw, max_chars=1200)
                commands.append({
                    "command": payload["text"],
                    "command_sha256": payload["text_sha256"],
                    "redaction": payload["redaction"],
                })
        except OSError:
            pass
    ps = _core.run(["ps", "-eo", "pid=,ppid=,comm=,args="], timeout=2.0)
    processes: list[dict[str, Any]] = []
    if ps.get("ok"):
        terminal_terms = ("zsh", "bash", "fish", "gnome-terminal", "ptyxis", "kgx", "konsole", "codex", "ssh")
        for line in str(ps.get("stdout") or "").splitlines():
            if not any(term in line for term in terminal_terms):
                continue
            parts = line.strip().split(None, 3)
            if len(parts) < 3:
                continue
            args_payload = _core.nervous_text_payload(parts[3] if len(parts) > 3 else parts[2], max_chars=1200)
            processes.append({
                "pid": parts[0],
                "ppid": parts[1],
                "comm": parts[2],
                "args": args_payload["text"],
                "args_sha256": args_payload["text_sha256"],
            })
            if len(processes) >= 40:
                break
    payload = {"commands": commands, "processes": processes, "coverage": "history_and_process_metadata_no_stdout_stderr"}
    return {
        "name": "terminal_activity",
        "source_id": source_id,
        "ok": True,
        "observed_at": _core.now_iso(),
        "sensitivity": "local_private_redacted",
        "coverage": "history_and_process_metadata_no_stdout_stderr",
        "summary": {
            "history_commands": len(commands),
            "terminal_processes": len(processes),
            "stdout_stderr_captured": False,
        },
        "commands": commands[-40:],
        "processes": processes,
        "source": _core.nervous_virtual_source(source_id, payload),
    }, None


def nervous_dictation_text_from_record(record: dict[str, Any]) -> str:
    for key in ("text", "transcript", "final_text", "cleaned_text", "inserted_text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for key in ("result", "payload", "dictation"):
        value = record.get(key)
        if isinstance(value, dict):
            nested = nervous_dictation_text_from_record(value)
            if nested:
                return nested
    return ""


def nervous_audio_transcript_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "audio_transcript_autolog"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    today = _core.nervous_today_path(_core.DICTATION_TRANSCRIPT_JSONL_ROOT)
    readable = _core.nervous_today_path(_core.DICTATION_TRANSCRIPT_READABLE_ROOT, suffix=".md")
    records, errors = _core.nervous_parse_jsonl_records(today) if today.exists() else ([], [])
    entries: list[dict[str, Any]] = []
    for record in records[-30:]:
        if not isinstance(record, dict):
            continue
        text = nervous_dictation_text_from_record(record)
        text_payload = _core.nervous_text_payload(text, max_chars=3000) if text else None
        entries.append({
            "generated_at": record.get("generated_at") or record.get("created_at") or record.get("started_at"),
            "profile": record.get("profile") or record.get("model_profile"),
            "language": record.get("language"),
            "duration_sec": record.get("duration_sec") or record.get("audio_duration_sec"),
            "text": text_payload["text"] if text_payload else None,
            "text_sha256": text_payload["text_sha256"] if text_payload else None,
            "redaction": text_payload["redaction"] if text_payload else None,
        })
    payload = {
        "jsonl": str(today),
        "readable": str(readable),
        "entries": entries,
        "parse_errors": errors[:10],
    }
    return {
        "name": "audio_transcript_autolog",
        "source_id": source_id,
        "ok": today.exists(),
        "observed_at": _core.now_iso(),
        "sensitivity": "local_private_redacted",
        "summary": {
            "jsonl_exists": today.exists(),
            "readable_exists": readable.exists(),
            "records": len(records),
            "entries_indexed": len(entries),
            "microphone_opened": False,
        },
        "jsonl_path": str(today),
        "readable_path": str(readable),
        "entries": entries,
        "parse_errors": errors[:10],
        "source": _core.nervous_file_source(today) if today.exists() else _core.nervous_virtual_source(source_id, payload),
    }, None


def nervous_fact_jsonl_files() -> list[Path]:
    return _core.nervous_jsonl_files(_core.NERVOUS_FACTS_ROOT)


def nervous_event_jsonl_files() -> list[Path]:
    return _core.nervous_jsonl_files(_core.NERVOUS_EVENTS_ROOT)


def nervous_episode_jsonl_files() -> list[Path]:
    return _core.nervous_jsonl_files(_core.NERVOUS_EPISODES_ROOT)


def nervous_index_source_files() -> list[Path]:
    return build_nervous_index_source_files((_core.NERVOUS_FACTS_ROOT, _core.NERVOUS_EVENTS_ROOT, _core.NERVOUS_EPISODES_ROOT))


def nervous_records_from_jsonl_root(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _core.typing_nervous_adapters.load_source_records_from_root(root)


def nervous_severity_max(values: list[str]) -> str:
    return nervous_events_contracts.severity_max(values)


def nervous_thermal_event_thresholds() -> dict[str, float]:
    policy: dict[str, Any] = {}
    ai_policy = ai_cli.ai_config().get("thermal_policy", {})
    if isinstance(ai_policy, dict):
        policy.update(ai_policy)
    cooling_auto = _core.cooling_config().get("auto", {})
    if isinstance(cooling_auto, dict):
        policy.update(cooling_auto)
    return nervous_events_contracts.thermal_event_thresholds(policy)


def nervous_events_from_fact_records(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return nervous_events_contracts.events_from_fact_records(
        items,
        thresholds=nervous_thermal_event_thresholds(),
        fact_source_id=_core.nervous_fact_source_id,
        deferred_source_ids=_core.nervous_deferred_source_ids(),
        compact_json_func=nervous_compact_json_for_index,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
    )


def nervous_events_build(
    write_latest: bool = True,
    force_full: bool = False,
) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    thresholds = nervous_thermal_event_thresholds()
    sources = _core.nervous_effective_sources(write_latest=False)
    deferred_source_ids = _core.nervous_deferred_source_ids(sources)

    def stateful_builder(
        items: list[dict[str, Any]],
        *,
        initial_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        return nervous_events_contracts.events_from_fact_records_with_state(
            items,
            initial_state=initial_state,
            thresholds=thresholds,
            fact_source_id=_core.nervous_fact_source_id,
            deferred_source_ids=deferred_source_ids,
            compact_json_func=nervous_compact_json_for_index,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
        )

    return nervous_events_adapters.run_events_build(
        privacy=privacy,
        facts_root=_core.NERVOUS_FACTS_ROOT,
        events_root=_core.NERVOUS_EVENTS_ROOT,
        latest_path=_core.NERVOUS_EVENTS_LATEST_PATH,
        events_from_fact_records=nervous_events_from_fact_records,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        latest_writer=_core.safe_atomic_write_json,
        events_from_fact_records_with_state=stateful_builder,
        derivation_identity=nervous_events_contracts.event_derivation_identity(
            thresholds=thresholds,
            deferred_source_ids=deferred_source_ids,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
        ),
        force_full=force_full,
    )


def nervous_events_latest() -> dict[str, Any]:
    return nervous_events_adapters.latest_read_document(
        latest_path=_core.NERVOUS_EVENTS_LATEST_PATH,
        read_schema=f"{_core.SCHEMA_PREFIX}_nervous_events_latest_read_v1",
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        reader=_core.load_json_document,
    )


def nervous_events_validate(write_latest: bool = True) -> dict[str, Any]:
    allowed_sources = _core.nervous_allowed_source_ids(_core.nervous_effective_sources(write_latest=False))
    return nervous_events_adapters.validate_events(
        events_root=_core.NERVOUS_EVENTS_ROOT,
        latest_path=_core.NERVOUS_EVENTS_LATEST_PATH,
        validate_latest_path=_core.NERVOUS_EVENTS_ROOT / "validate" / "latest.json",
        allowed_sources=allowed_sources,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        latest_reader=_core.load_json_document,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_episodes_from_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return nervous_events_contracts.episodes_from_events(
        events,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
    )


def nervous_episodes_build(
    write_latest: bool = True,
    refresh_events: bool = True,
    force_full: bool = False,
) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    return nervous_events_adapters.run_episodes_build(
        privacy=privacy,
        events_root=_core.NERVOUS_EVENTS_ROOT,
        episodes_root=_core.NERVOUS_EPISODES_ROOT,
        latest_path=_core.NERVOUS_EPISODES_LATEST_PATH,
        episodes_from_events=nervous_episodes_from_events,
        event_records_from_items=lambda items: nervous_events_contracts.event_records_from_items(items, schema_prefix=_core.SCHEMA_PREFIX),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        events_builder=nervous_events_build,
        refresh_events=refresh_events,
        incremental_enabled=True,
        force_full=force_full,
        write_latest_enabled=write_latest,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_episodes_latest() -> dict[str, Any]:
    return nervous_events_adapters.latest_read_document(
        latest_path=_core.NERVOUS_EPISODES_LATEST_PATH,
        read_schema=f"{_core.SCHEMA_PREFIX}_nervous_episodes_latest_read_v1",
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        reader=_core.load_json_document,
    )


def nervous_episode_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return nervous_records_from_jsonl_root(_core.NERVOUS_EPISODES_ROOT)


def nervous_episodes_validate(write_latest: bool = True) -> dict[str, Any]:
    allowed_sources = _core.nervous_allowed_source_ids(_core.nervous_effective_sources(write_latest=False))
    return nervous_events_adapters.validate_episodes(
        episodes_root=_core.NERVOUS_EPISODES_ROOT,
        latest_path=_core.NERVOUS_EPISODES_LATEST_PATH,
        validate_latest_path=_core.NERVOUS_EPISODES_ROOT / "validate" / "latest.json",
        allowed_sources=allowed_sources,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        latest_reader=_core.load_json_document,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_sqlite_fts5_ok() -> tuple[bool, str | None]:
    return nervous_index_adapters.sqlite_fts5_ok()


def nervous_index_schema_sql() -> str:
    return build_nervous_index_schema_sql()


def nervous_index_connect(create: bool = False) -> sqlite3.Connection:
    return nervous_index_adapters.connect_db(_core.NERVOUS_SEARCH_INDEX_DB_PATH, create=create)


def nervous_index_initialize(conn: sqlite3.Connection) -> None:
    nervous_index_adapters.initialize_db(
        conn,
        schema_path=_core.NERVOUS_SEARCH_INDEX_SCHEMA_PATH,
        schema_sql=nervous_index_schema_sql(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        group=_core.MODE_STATE_GROUP,
    )


def nervous_index_lock() -> Any:
    return nervous_index_adapters.index_lock(_core.NERVOUS_SEARCH_INDEX_ROOT)


def nervous_index_lock_active() -> bool:
    return nervous_index_adapters.index_lock_active(_core.NERVOUS_SEARCH_INDEX_ROOT)


def nervous_enabled_index_source_ids(sources: dict[str, Any]) -> set[str]:
    return build_nervous_index_enabled_index_source_ids(sources)


def nervous_compact_json_for_index(value: Any, max_chars: int = 6000) -> str:
    return build_nervous_index_compact_json(value, max_chars=max_chars)


def nervous_index_db_counts() -> dict[str, Any]:
    return nervous_index_adapters.db_counts(_core.NERVOUS_SEARCH_INDEX_DB_PATH)


def nervous_index_db_counts_bounded(busy_timeout_ms: int = 100) -> dict[str, Any]:
    return nervous_index_adapters.db_counts_bounded(
        _core.NERVOUS_SEARCH_INDEX_DB_PATH,
        busy_timeout_ms=busy_timeout_ms,
    )


def nervous_index_source_present(source_id: str, busy_timeout_ms: int = 100) -> dict[str, Any]:
    return nervous_index_adapters.source_present(
        _core.NERVOUS_SEARCH_INDEX_DB_PATH,
        source_id,
        busy_timeout_ms=busy_timeout_ms,
    )


def nervous_index_scan(db_path: Path, *, smoke_match_query: str) -> dict[str, Any]:
    return nervous_index_adapters.scan_index(db_path, smoke_match_query=smoke_match_query)


def nervous_index_write_latest(data: dict[str, Any]) -> dict[str, Any]:
    return nervous_index_adapters.write_latest(data, _core.NERVOUS_SEARCH_INDEX_LATEST_PATH, group=_core.MODE_STATE_GROUP)


def nervous_index_build(
    write_latest: bool = True,
    refresh_derived: bool = True,
    force_full: bool = False,
) -> dict[str, Any]:
    run_started_monotonic = time.monotonic()
    started_at = _core.now_iso()
    run_id = nervous_change_id("index")
    config = nervous_index_config()
    privacy = _core.nervous_effective_privacy(write_latest=False)
    sources = _core.nervous_effective_sources(write_latest=False)
    if not bool(config.get("enabled", True)):
        data = build_nervous_index_disabled_result(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            config_path=_core.NERVOUS_INDEX_CONFIG_PATH,
        )
        return nervous_index_write_latest(data) if write_latest else data
    if bool(privacy.get("global_pause")) and bool(config.get("privacy", {}).get("enforce_global_pause", True)):
        return build_nervous_index_global_pause_refused_result(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            privacy=privacy,
            privacy_state_path=_core.NERVOUS_PRIVACY_STATE_PATH,
        )
    fts_ok, fts_error = nervous_sqlite_fts5_ok()
    if not fts_ok:
        data = build_nervous_index_fts_unavailable_result(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            fts_error=fts_error,
        )
        return nervous_index_write_latest(data) if write_latest else data

    if nervous_semantic_lock_active():
        data = build_nervous_index_semantic_lock_deferred_result(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
            config_path=_core.NERVOUS_INDEX_CONFIG_PATH,
        )
        return nervous_index_write_latest(data) if write_latest else data

    derived_started_monotonic = time.monotonic()
    derived_refresh = nervous_index_adapters.derived_refresh_from_ports(
        refresh_enabled=refresh_derived,
        force_full=force_full,
        include_internal_attestations=True,
        events_builder=nervous_events_build,
        episodes_builder=nervous_episodes_build,
    )
    source_delta_attestations = derived_refresh.pop(
        "_internal_source_delta_attestations",
        [],
    )
    derived_finished_monotonic = time.monotonic()

    build_inputs = nervous_index_adapters.build_incremental_document_from_source_roots(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        run_id=run_id,
        started_at=started_at,
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        config_path=_core.NERVOUS_INDEX_CONFIG_PATH,
        privacy=privacy,
        sources=sources,
        source_roots=(_core.NERVOUS_FACTS_ROOT, _core.NERVOUS_EVENTS_ROOT, _core.NERVOUS_EPISODES_ROOT),
        derived_refresh=derived_refresh,
        redact_text=_core.nervous_redact_index_text,
        force_full=force_full,
        source_delta_attestations=source_delta_attestations,
    )
    data: dict[str, Any] = build_inputs["data"]
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    execution_timings = execution.get("timings_ms") if isinstance(execution.get("timings_ms"), dict) else {}
    data["execution"] = {
        **execution,
        "timings_ms": {
            **execution_timings,
            "derived_refresh": round((derived_finished_monotonic - derived_started_monotonic) * 1000.0, 3),
        },
    }
    files = build_inputs["source_files"]
    projection = build_inputs["projection"]
    parse_errors = build_inputs["parse_errors"]
    privacy_state = privacy.get("state") if isinstance(privacy.get("state"), dict) else {}
    data = nervous_index_adapters.write_build_projection(
        data,
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        root=_core.NERVOUS_SEARCH_INDEX_ROOT,
        schema_path=_core.NERVOUS_SEARCH_INDEX_SCHEMA_PATH,
        schema_sql=nervous_index_schema_sql(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        group=_core.MODE_STATE_GROUP,
        run_id=run_id,
        started_at=started_at,
        source_files=files,
        projection=projection,
        parse_errors=parse_errors,
        facts_root=_core.NERVOUS_FACTS_ROOT,
        events_root=_core.NERVOUS_EVENTS_ROOT,
        episodes_root=_core.NERVOUS_EPISODES_ROOT,
        source_state_change_id=data["sources"].get("state_change_id"),
        privacy_state_change_id=privacy_state.get("last_change_id"),
        semantic_lock_active=nervous_semantic_lock_active,
        now=_core.now_iso,
        counts_reader=nervous_index_db_counts,
        manifest_entries=build_inputs["manifest_entries"],
        projection_identity=build_inputs["projection_identity"],
        changed_source_paths=build_inputs["changed_source_paths"],
        replace_source_paths=build_inputs["replace_source_paths"],
        append_source_paths=build_inputs["append_source_paths"],
        source_observations=build_inputs["source_observations"],
        write_mode=build_inputs["write_mode"],
        base_run_id=build_inputs["base_run_id"],
    )

    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    execution_timings = execution.get("timings_ms") if isinstance(execution.get("timings_ms"), dict) else {}
    data["execution"] = {
        **execution,
        "timings_ms": {
            **execution_timings,
            "total_before_latest_write": round((time.monotonic() - run_started_monotonic) * 1000.0, 3),
        },
    }

    return nervous_index_write_latest(data) if write_latest else data


def nervous_index_freshness(meta: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    config = config if isinstance(config, dict) else nervous_index_config()
    fact_files = nervous_fact_jsonl_files()
    event_files = nervous_event_jsonl_files()
    episode_files = nervous_episode_jsonl_files()
    return nervous_index_adapters.freshness_document_from_paths(
        meta=meta,
        config=config,
        facts_latest_path=_core.NERVOUS_FACTS_LATEST_PATH,
        events_latest_path=_core.NERVOUS_EVENTS_LATEST_PATH,
        episodes_latest_path=_core.NERVOUS_EPISODES_LATEST_PATH,
        fact_files=fact_files,
        event_files=event_files,
        episode_files=episode_files,
        now=dt.datetime.now(dt.timezone.utc).astimezone(),
        latest_reader=_core.load_json_document,
        line_counter=_core.count_file_lines,
        line_counts_reader=_core.count_file_lines_snapshot,
    )


def nervous_index_search(
    query: str,
    limit: int | None = None,
    dedupe: bool = True,
    order: str = "latest",
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
) -> dict[str, Any]:
    config = nervous_index_config()
    privacy = _core.nervous_effective_privacy(write_latest=False)
    return nervous_index_adapters.search_from_ports(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        query=query,
        config=config,
        privacy=privacy,
        requested_limit=limit,
        requested_order=order,
        dedupe=dedupe,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        freshness_reader=nervous_index_freshness,
    )


def nervous_index_status(write_latest: bool = True) -> dict[str, Any]:
    config = nervous_index_config()
    privacy = _core.nervous_effective_privacy(write_latest=False)
    sources = _core.nervous_effective_sources(write_latest=False)
    fts_ok, fts_error = nervous_sqlite_fts5_ok()
    data = nervous_index_adapters.status_document_from_ports(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        config=config,
        config_path=_core.NERVOUS_INDEX_CONFIG_PATH,
        privacy=privacy,
        sources=sources,
        sqlite_version=sqlite3.sqlite_version,
        fts_ok=fts_ok,
        fts_error=fts_error,
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        root_path=_core.NERVOUS_SEARCH_INDEX_ROOT,
        schema_path=_core.NERVOUS_SEARCH_INDEX_SCHEMA_PATH,
        latest_path=_core.NERVOUS_SEARCH_INDEX_LATEST_PATH,
        service_name=_core.NERVOUS_SEARCH_INDEX_SERVICE,
        timer_name=_core.NERVOUS_SEARCH_INDEX_TIMER,
        latest_reader=_core.load_json_document,
        counts_reader=nervous_index_db_counts,
        freshness_reader=nervous_index_freshness,
        unit_status_reader=_core.user_systemd_unit,
    )
    if write_latest:
        return nervous_index_write_latest(data)
    return data


def nervous_index_validate(write_latest: bool = True) -> dict[str, Any]:
    config = nervous_index_config()
    sources = _core.nervous_effective_sources(write_latest=False)
    fts_ok, fts_error = nervous_sqlite_fts5_ok()
    data = nervous_index_adapters.validation_document_from_ports(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        storage_root=_core.ABYSS_MACHINE_STORAGE_ROOT,
        config=config,
        config_path=_core.NERVOUS_INDEX_CONFIG_PATH,
        sources=sources,
        fts_ok=fts_ok,
        fts_error=fts_error,
        event_files=nervous_event_jsonl_files(),
        episode_files=nervous_episode_jsonl_files(),
        counts_reader=nervous_index_db_counts,
        freshness_reader=nervous_index_freshness,
        scan_reader=nervous_index_scan,
        line_counter=_core.count_file_lines,
        symlink_tail_probe=_core.nervous_path_has_symlink_tail,
    )
    if write_latest:
        return nervous_index_write_latest(data)
    return data


def nervous_index_bounded_validate_from_status(index_status: dict[str, Any]) -> dict[str, Any]:
    return build_nervous_index_bounded_validate_from_status(
        index_status,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def nervous_index_vacuum(write_latest: bool = True) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    if bool(privacy.get("global_pause")):
        data = build_nervous_index_vacuum_refused_result(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
        )
        return nervous_index_write_latest(data) if write_latest else data
    before = nervous_index_db_counts()
    data = build_nervous_index_vacuum_start_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        before=before,
    )
    if not _core.NERVOUS_SEARCH_INDEX_DB_PATH.exists():
        data = build_nervous_index_vacuum_missing_db_result(data)
        return nervous_index_write_latest(data) if write_latest else data
    try:
        after = nervous_index_adapters.vacuum_index(_core.NERVOUS_SEARCH_INDEX_DB_PATH, _core.NERVOUS_SEARCH_INDEX_ROOT)
        data = build_nervous_index_vacuum_success_result(data, after=after)
    except BlockingIOError:
        data = build_nervous_index_vacuum_error_result(data, "another index operation is already running")
    except (OSError, sqlite3.Error) as exc:
        data = build_nervous_index_vacuum_error_result(data, exc)
    return nervous_index_write_latest(data) if write_latest else data


def nervous_semantic_config() -> dict[str, Any]:
    config = nervous_index_config()
    semantic = config.get("semantic") if isinstance(config.get("semantic"), dict) else {}
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    ai_doc = ai_cli.ai_config()
    ai_eval = ai_doc.get("eval", {}) if isinstance(ai_doc.get("eval"), dict) else {}
    if not embedding.get("model_dir") and ai_eval.get("embedding_model"):
        embedding["model_dir"] = str(ai_eval.get("embedding_model"))
    if not embedding.get("device") and ai_eval.get("embedding_device"):
        embedding["device"] = str(ai_eval.get("embedding_device"))
    embedding.setdefault("pooling", "last_token")
    embedding.setdefault("padding_side", "left")
    semantic["embedding"] = embedding
    semantic.setdefault("enabled", True)
    semantic.setdefault("backend", "sqlite_float32_sidecar")
    semantic.setdefault("db_path", str(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH))
    semantic.setdefault("latest", str(_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH))
    automation = semantic.get("automation") if isinstance(semantic.get("automation"), dict) else {}
    automation.setdefault("enabled", False)
    automation.setdefault("reason", "semantic sidecar is maintained by a resource-gated timer, not a resident embedding service")
    semantic["automation"] = automation
    maintain = semantic.get("maintain") if isinstance(semantic.get("maintain"), dict) else {}
    maintain.setdefault("enabled", True)
    maintain.setdefault("review_command", _core.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND)
    maintain.setdefault("retry_command", _core.NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND)
    maintain.setdefault("command", _core.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND)
    maintain.setdefault("min_delta_chunks", 128)
    maintain.setdefault("max_stale_minutes", 90)
    maintain.setdefault("timeout_sec", 1800)
    maintain.setdefault("resource_class", "medium")
    maintain.setdefault("resource_kind", "indexing")
    maintain.setdefault("unattended", True)
    maintain.setdefault("success_on_block", True)
    maintain.setdefault("refresh_index_first", True)
    maintain.setdefault("index_refresh_timeout_sec", 300)
    maintain.setdefault("loaded_batch_size", 8)
    maintain.setdefault("embedding_window_chunks", 1024)
    maintain.setdefault("timer", _core.NERVOUS_SEMANTIC_MAINTAIN_TIMER)
    maintain.setdefault("service", _core.NERVOUS_SEMANTIC_MAINTAIN_SERVICE)
    semantic["maintain"] = maintain
    return semantic


def nervous_semantic_connect(create: bool = False) -> sqlite3.Connection:
    return nervous_semantic_adapters.connect_db(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH, create=create)


def nervous_semantic_initialize(conn: sqlite3.Connection) -> None:
    nervous_semantic_adapters.initialize_db(conn, schema_prefix=_core.SCHEMA_PREFIX, version=_core.VERSION)


@contextmanager
def nervous_semantic_lock() -> Any:
    with nervous_semantic_adapters.semantic_lock(_core.NERVOUS_SEMANTIC_INDEX_ROOT):
        yield


def nervous_semantic_write_latest(data: dict[str, Any]) -> dict[str, Any]:
    return nervous_semantic_adapters.write_latest(data, _core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH, group=_core.MODE_STATE_GROUP)


def nervous_semantic_counts() -> dict[str, Any]:
    return nervous_semantic_adapters.counts(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH)


def nervous_semantic_status(write_latest: bool = True) -> dict[str, Any]:
    semantic = nervous_semantic_config()
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    model_dir = Path(str(embedding.get("model_dir") or ""))
    counts = nervous_semantic_counts()
    source_counts = nervous_index_db_counts()
    semantic_meta = counts.get("meta") if isinstance(counts.get("meta"), dict) else {}
    cache_dir = Path(str(semantic_meta.get("cache_dir") or ai_cli.ai_openvino_cache_path(ai_cli.ai_model_cache_label(model_dir, "semantic-embedding"))))
    data = build_nervous_semantic_status(
        semantic=semantic,
        counts=counts,
        source_counts=source_counts,
        model_dir=str(model_dir),
        model_exists=model_dir.exists(),
        cache_dir=str(cache_dir),
        cache_exists=cache_dir.exists(),
        source_index_db_exists=_core.NERVOUS_SEARCH_INDEX_DB_PATH.exists(),
        semantic_index_db_exists=_core.NERVOUS_SEMANTIC_INDEX_DB_PATH.exists(),
        paths={
            "db": str(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH),
            "root": str(_core.NERVOUS_SEMANTIC_INDEX_ROOT),
            "latest": str(_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH),
            "source_index_db": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
        },
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )
    if write_latest:
        return nervous_semantic_write_latest(data)
    return data


def nervous_semantic_maintain_write_latest(data: dict[str, Any]) -> dict[str, Any]:
    return nervous_semantic_adapters.write_maintain_latest(data, _core.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH, _core.NERVOUS_SEMANTIC_MAINTAIN_ROOT)


def nervous_semantic_eval_write_latest(data: dict[str, Any]) -> dict[str, Any]:
    return nervous_semantic_adapters.write_latest_history(data, _core.NERVOUS_SEMANTIC_EVAL_LATEST_PATH, _core.NERVOUS_SEMANTIC_EVAL_ROOT)


def nervous_semantic_lock_active() -> bool:
    return nervous_semantic_adapters.semantic_lock_active(_core.NERVOUS_SEMANTIC_INDEX_ROOT)


def nervous_semantic_maintain_assess(
    status: dict[str, Any],
    min_delta_chunks: int,
    max_stale_minutes: float,
    force_refresh: bool = False,
) -> dict[str, Any]:
    return build_nervous_semantic_maintain_assess(
        status,
        min_delta_chunks,
        max_stale_minutes,
        force_refresh=force_refresh,
    )


def nervous_semantic_maintain(
    min_delta_chunks: int | None = None,
    max_stale_minutes: float | None = None,
    timeout_sec: float | None = None,
    dry_run: bool = False,
    force_refresh: bool = False,
    max_chunks: int | None = None,
    batch_size: int | None = None,
    rebuild: bool = False,
    no_thermal_sample: bool = False,
    refresh_index_first: bool | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    return nervous_semantic_adapters.semantic_maintain_document(
        semantic_config=nervous_semantic_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        maintain_latest_path=_core.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH,
        maintain_daily_root=_core.NERVOUS_SEMANTIC_MAINTAIN_ROOT,
        semantic_latest_path=_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH,
        index_status=lambda: nervous_index_status(write_latest=False),
        semantic_status=lambda: nervous_semantic_status(write_latest=False),
        lock_active=nervous_semantic_lock_active,
        resource_launch=_core.resource_launch,
        memory_plan=lambda: _core.memory_plan(write_latest=False),
        latest_writer=nervous_semantic_maintain_write_latest,
        json_parser=_core.parse_json_stdout,
        min_delta_chunks=min_delta_chunks,
        max_stale_minutes=max_stale_minutes,
        timeout_sec=timeout_sec,
        dry_run=dry_run,
        force_refresh=force_refresh,
        max_chunks=max_chunks,
        batch_size=batch_size,
        rebuild=rebuild,
        no_thermal_sample=no_thermal_sample,
        refresh_index_first=refresh_index_first,
        write_latest=write_latest,
    )


def nervous_semantic_source_chunks(max_chunks: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    semantic = nervous_semantic_config()
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    max_input_chars = max(200, int(embedding.get("max_input_chars") or 2400))
    return nervous_semantic_adapters.source_chunks(
        _core.NERVOUS_SEARCH_INDEX_DB_PATH,
        max_chunks=max_chunks,
        max_input_chars=max_input_chars,
        connect_source=nervous_index_adapters.connect_db,
    )


def nervous_semantic_model_paths(embedding: dict[str, Any], *, create_cache_dir: bool = True) -> tuple[Path, str, Path, str | None]:
    model_dir = Path(str(embedding.get("model_dir") or ""))
    device = str(embedding.get("device") or "AUTO:GPU,CPU")
    cache_label = ai_cli.ai_model_cache_label(model_dir, "semantic-embedding")
    cache_dir = ai_cli.ai_openvino_cache_dir(cache_label) if create_cache_dir else ai_cli.ai_openvino_cache_path(cache_label)
    python = shutil.which("abyss-openvino-python") or str(ai_cli.ai_config().get("openvino", {}).get("python", ""))
    error = None
    if not model_dir.exists():
        error = f"embedding model directory missing: {model_dir}"
    elif not python or not Path(python).exists():
        error = "abyss-openvino-python not found"
    return model_dir, device, cache_dir, error


def nervous_semantic_embed_texts(text_items: list[dict[str, str]], embedding: dict[str, Any]) -> dict[str, Any]:
    if not text_items:
        return {"ok": True, "vectors": {}, "summary": {"items": 0}}

    model_dir, device, cache_dir, error = nervous_semantic_model_paths(embedding)
    python = shutil.which("abyss-openvino-python") or str(ai_cli.ai_config().get("openvino", {}).get("python", ""))
    if error:
        python = ""
    return nervous_semantic_adapters.embed_texts_with_subprocess(
        text_items,
        embedding=embedding,
        model_dir=model_dir,
        device=device,
        cache_dir=cache_dir,
        python=str(python),
        tmp_root=_core.ABYSS_MACHINE_TMP_ROOT / "nervous" / "semantic",
        run_command=_core.run,
        env=ai_cli.ai_subprocess_env(),
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
    )


def nervous_semantic_existing_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    return nervous_semantic_adapters.existing_hashes(conn)


def nervous_semantic_existing_vectors_by_hash(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return nervous_semantic_adapters.existing_vectors_by_hash(conn)


def nervous_semantic_build(
    max_chunks: int | None = None,
    batch_size: int | None = None,
    device: str | None = None,
    force_policy: bool = False,
    rebuild: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    started_at = _core.now_iso()
    run_id = nervous_change_id("semantic")
    semantic = nervous_semantic_config()
    embedding = semantic.get("embedding") if isinstance(semantic.get("embedding"), dict) else {}
    embedding = nervous_semantic_adapters.semantic_build_embedding_config(
        embedding,
        batch_size=batch_size,
        device=device,
    )
    build_command = nervous_semantic_adapters.semantic_build_command(
        max_chunks=max_chunks,
        batch_size=batch_size,
        device=device,
        rebuild=rebuild,
    )
    privacy = _core.nervous_effective_privacy(write_latest=False)
    if bool(privacy.get("global_pause")):
        data = nervous_semantic_adapters.semantic_build_refusal_document(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            refused=True,
            error="global_pause is active; semantic index build did not touch the database",
        )
        return nervous_semantic_write_latest(data) if write_latest else data
    if not bool(semantic.get("enabled", True)):
        data = nervous_semantic_adapters.semantic_build_refusal_document(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            run_id=run_id,
            error="semantic index disabled by config",
        )
        return nervous_semantic_write_latest(data) if write_latest else data
    model_dir_for_provenance, device_for_provenance, cache_dir_for_provenance, _ = nervous_semantic_model_paths(embedding)
    cache_before = artifacts_cli.artifact_path_stats(cache_dir_for_provenance, artifacts_cli.artifact_backup_state(cache_dir_for_provenance))
    chunks, source_error = nervous_semantic_source_chunks(max_chunks=max_chunks)
    source_counts = nervous_index_db_counts()
    partial = max_chunks is not None and max_chunks > 0
    data = nervous_semantic_adapters.semantic_build_initial_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        run_id=run_id,
        started_at=started_at,
        db_path=_core.NERVOUS_SEMANTIC_INDEX_DB_PATH,
        source_index_db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        latest_path=_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH,
        source_counts=source_counts,
        partial=partial,
        max_chunks=max_chunks,
        rebuild=rebuild,
        build_command=build_command,
        semantic_config=semantic,
        embedding=embedding,
        model_dir=model_dir_for_provenance,
        device=device_for_provenance,
        cache_dir=cache_dir_for_provenance,
        cache_before=cache_before,
    )
    if source_error:
        nervous_semantic_adapters.semantic_build_apply_source_error(data, source_error)
        return nervous_semantic_write_latest(data) if write_latest else data
    try:
        with nervous_semantic_lock():
            if nervous_index_lock_active():
                nervous_semantic_adapters.semantic_build_defer_source_index_active(data)
                return nervous_semantic_write_latest(data) if write_latest else data
            locked_source_counts = nervous_index_db_counts()
            if nervous_semantic_adapters.semantic_build_source_index_changed(source_counts, locked_source_counts):
                chunks, source_error = nervous_semantic_source_chunks(max_chunks=max_chunks)
                source_counts = nervous_index_db_counts()
                nervous_semantic_adapters.semantic_build_mark_source_index_reloaded(data, source_counts)
                if source_error:
                    nervous_semantic_adapters.semantic_build_apply_source_error(data, source_error)
                    return nervous_semantic_write_latest(data) if write_latest else data
            conn = nervous_semantic_connect(create=True)
            nervous_semantic_initialize(conn)
            conn.commit()
            existing = nervous_semantic_existing_hashes(conn)
            existing_vectors_by_hash = {} if rebuild else nervous_semantic_existing_vectors_by_hash(conn)
            pending_plan = nervous_semantic_adapters.semantic_build_pending_plan(
                chunks,
                existing=existing,
                existing_vectors_by_hash=existing_vectors_by_hash,
                rebuild=rebuild,
            )
            pending = pending_plan["pending"]
            pending_by_id = pending_plan["pending_by_id"]
            reuse_vectors = pending_plan["reuse_vectors"]
            embed_pending = pending_plan["embed_pending"]
            data["summary"] = pending_plan["summary"]
            indexed = nervous_semantic_adapters.semantic_build_insert_reused_vectors(
                conn,
                reuse_vectors=reuse_vectors,
                pending_by_id=pending_by_id,
                started_at=started_at,
            )
            data["summary"]["vectors_indexed"] = indexed
            if pending:
                gate = ai_cli.ai_policy_gate_for_class("medium", "nervous semantic-build", force=force_policy)
                data["policy_gate"] = gate
                if not gate.get("ok"):
                    nervous_semantic_adapters.semantic_build_apply_policy_denial(data, gate)
                    conn.close()
                    return nervous_semantic_write_latest(data) if write_latest else data
            embedding_windows = nervous_semantic_adapters.semantic_build_embedding_windows(
                conn,
                data,
                semantic_config=semantic,
                embedding=embedding,
                chunks=chunks,
                pending=pending,
                pending_by_id=pending_by_id,
                embed_pending=embed_pending,
                started_at=started_at,
                run_id=run_id,
                partial=partial,
                cache_before=cache_before,
                cache_dir=cache_dir_for_provenance,
                cache_stats=lambda path: artifacts_cli.artifact_path_stats(path, artifacts_cli.artifact_backup_state(path)),
                now=_core.now_iso,
                embed_texts=nervous_semantic_embed_texts,
            )
            indexed = int(embedding_windows.get("indexed") or 0)
            if not embedding_windows.get("ok"):
                conn.close()
                return nervous_semantic_write_latest(data) if write_latest else data
            data = nervous_semantic_adapters.semantic_build_finalize_success(
                conn,
                data,
                schema_prefix=_core.SCHEMA_PREFIX,
                version=_core.VERSION,
                source_counts=source_counts,
                chunks=chunks,
                embedding=embedding,
                run_id=run_id,
                started_at=started_at,
                partial=partial,
                cache_before=cache_before,
                cache_dir=cache_dir_for_provenance,
                cache_stats=lambda path: artifacts_cli.artifact_path_stats(path, artifacts_cli.artifact_backup_state(path)),
                now=_core.now_iso,
                indexed=indexed,
                pending=pending,
                reuse_vectors=reuse_vectors,
                db_path=_core.NERVOUS_SEMANTIC_INDEX_DB_PATH,
                embed_pending=embed_pending,
                state_group=_core.MODE_STATE_GROUP,
                counts_port=nervous_semantic_counts,
            )
            conn.close()
    except BlockingIOError:
        data["error"] = "another semantic index operation is already running"
    except (OSError, sqlite3.Error) as exc:
        data["error"] = str(exc)
    return nervous_semantic_write_latest(data) if write_latest else data


def nervous_semantic_query_text(query: str) -> str:
    return build_nervous_semantic_query_text(query)


def nervous_semantic_query_vector(query: str, embedding: dict[str, Any], force_policy: bool = False) -> dict[str, Any]:
    gate = ai_cli.ai_policy_gate_for_class("medium", "nervous semantic-search", force=force_policy)
    if not gate.get("ok"):
        return {"ok": False, "policy_denied": True, "error": "host AI policy denied semantic search", "policy_gate": gate}
    query_text = nervous_semantic_query_text(query)
    embedded = nervous_semantic_embed_texts([{"id": "query", "text": query_text}], embedding)
    if not embedded.get("ok"):
        return embedded
    vectors = embedded.get("vectors") if isinstance(embedded.get("vectors"), dict) else {}
    vector = vectors.get("query") if isinstance(vectors.get("query"), dict) else {}
    blob = vector.get("blob")
    if not isinstance(blob, (bytes, bytearray)):
        return {"ok": False, "error": "query embedding missing from subprocess output"}
    return {
        "ok": True,
        "blob": bytes(blob),
        "dim": int(vector.get("dim") or 0),
        "embedding_status": {key: value for key, value in embedded.items() if key != "vectors"},
        "policy_gate": gate,
    }


def nervous_semantic_search_with_vector(
    query: str,
    query_vector_blob: bytes,
    query_vector_result: dict[str, Any],
    final_limit: int,
    dedupe: bool = True,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
) -> dict[str, Any]:
    return build_nervous_semantic_search_with_vector(
        db_path=_core.NERVOUS_SEMANTIC_INDEX_DB_PATH,
        query=query,
        query_vector_blob=query_vector_blob,
        query_vector_result=query_vector_result,
        final_limit=final_limit,
        dedupe=dedupe,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def nervous_semantic_search(
    query: str,
    limit: int | None = None,
    dedupe: bool = True,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    force_policy: bool = False,
) -> dict[str, Any]:
    return nervous_semantic_adapters.semantic_search_document(
        query=query,
        semantic_config=nervous_semantic_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        db_path=_core.NERVOUS_SEMANTIC_INDEX_DB_PATH,
        privacy=_core.nervous_effective_privacy(write_latest=False),
        counts=nervous_semantic_counts,
        db_exists=lambda path: path.exists(),
        query_vector=nervous_semantic_query_vector,
        semantic_search_with_vector=nervous_semantic_search_with_vector,
        limit=limit,
        dedupe=dedupe,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        force_policy=force_policy,
    )


def nervous_semantic_eval(force_policy: bool = False, write_latest: bool = True) -> dict[str, Any]:
    return nervous_semantic_adapters.semantic_eval_document(
        semantic_config=nervous_semantic_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        latest_path=_core.NERVOUS_SEMANTIC_EVAL_LATEST_PATH,
        daily_root=_core.NERVOUS_SEMANTIC_EVAL_ROOT,
        semantic_status=lambda: nervous_semantic_status(write_latest=False),
        policy_gate=lambda: ai_cli.ai_policy_gate_for_class("medium", "nervous semantic-eval", force=force_policy),
        embed_texts=nervous_semantic_embed_texts,
        lexical_search=lambda query: nervous_index_search(query, limit=8, dedupe=False, order="ranked"),
        semantic_search_with_vector=nervous_semantic_search_with_vector,
        latest_writer=nervous_semantic_eval_write_latest,
        write_latest=write_latest,
    )


def nervous_latest_read(path: Path, read_schema: str) -> dict[str, Any]:
    return _core.typing_nervous_adapters.read_latest_document(
        path,
        read_schema,
        version=_core.VERSION,
        now=_core.now_iso,
        default_existing_ok=True,
    )


def nervous_replace_synthesis_period_record(path: Path, data: dict[str, Any], mode: int = 0o664) -> dict[str, Any] | None:
    return nervous_synthesis_adapters.replace_period_record(path, data, mode, group=_core.MODE_STATE_GROUP)


def nervous_rerank_default_profile() -> dict[str, Any]:
    return nervous_rerank_contracts.default_profile()


def nervous_rerank_profile(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config if isinstance(config, dict) else nervous_index_config()
    return nervous_rerank_contracts.profile_from_config(config)


def nervous_neural_rerank_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config if isinstance(config, dict) else nervous_index_config()
    return nervous_rerank_contracts.neural_config_from_config(
        config,
        default_model_dir=str(_core.AI_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov"),
        default_cache_dir=str(_core.AI_OPENVINO_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov"),
        default_scorer="/srv/abyss-machine/tools/ai/rerankers/qwen3_reranker_openvino_canary.py",
    )


def nervous_neural_rerank_scores(query: str, items: list[dict[str, Any]], config: dict[str, Any], force_policy: bool = False) -> dict[str, Any]:
    model_dir = Path(str(config.get("model_dir") or ""))
    scorer = Path(str(config.get("scorer") or ""))
    python = shutil.which("abyss-openvino-python") or str(ai_cli.ai_config().get("openvino", {}).get("python", ""))
    return nervous_rerank_adapters.score_with_subprocess(
        query,
        items,
        config=config,
        model_dir=model_dir,
        scorer=scorer,
        python=str(python),
        tmp_root=_core.ABYSS_MACHINE_TMP_ROOT / "nervous" / "rerank" / "neural",
        run_command=_core.run,
        env=ai_cli.ai_subprocess_env(),
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
        policy_gate=lambda: ai_cli.ai_policy_gate_for_class(
            str(config.get("resource_class") or "medium"),
            "nervous neural-rerank",
            force=force_policy,
        ),
        cache_dir=Path(str(config.get("cache_dir") or (_core.AI_OPENVINO_CACHE_ROOT / "qwen3-reranker-0.6b-int8-ov"))),
    )


def nervous_apply_neural_rerank_scores(
    ranked: list[dict[str, Any]],
    query: str,
    query_tokens: set[str],
    rerank_profile: dict[str, Any],
    neural_config: dict[str, Any],
    force_policy: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    if not bool(neural_config.get("enabled")):
        return ranked, {"ok": False, "skipped": True, "reason": "neural rerank disabled"}, warnings
    candidate_limit = max(1, min(int(neural_config.get("candidate_limit") or 24), len(ranked)))
    candidates = ranked[:candidate_limit]
    neural = nervous_neural_rerank_scores(query, candidates, neural_config, force_policy=force_policy)
    if not neural.get("ok"):
        warnings.append(str(neural.get("error") or neural.get("reason") or "neural rerank failed"))
        return ranked, neural, warnings
    ranked = nervous_rerank_contracts.apply_neural_scores(
        ranked,
        [item for item in neural.get("scores", []) if isinstance(item, dict)],
        query_tokens,
        rerank_profile,
        neural_config,
        candidate_limit=candidate_limit,
    )
    return ranked, neural, warnings


def nervous_result_source_score(item: dict[str, Any], query_tokens: set[str], profile: dict[str, Any] | None = None) -> float:
    profile = profile if isinstance(profile, dict) else nervous_rerank_default_profile()
    return nervous_rerank_contracts.result_source_score(item, query_tokens, profile)


def nervous_rerank_search(
    query: str,
    limit: int | None = None,
    candidate_limit: int | None = None,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    use_semantic: bool = True,
    use_neural: bool | None = None,
    force_policy: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    config = nervous_index_config()
    return nervous_retrieval_adapters.hybrid_rerank_search(
        query=query,
        config=config,
        rerank_profile=nervous_rerank_profile(config),
        neural_config=nervous_neural_rerank_config(config),
        lexical_search=nervous_index_search,
        semantic_status=lambda: nervous_semantic_status(write_latest=False),
        semantic_config=nervous_semantic_config(),
        semantic_maintain_assess=nervous_semantic_maintain_assess,
        semantic_search=nervous_semantic_search,
        neural_apply=nervous_apply_neural_rerank_scores,
        latest_path=_core.NERVOUS_RERANK_LATEST_PATH,
        daily_root=_core.NERVOUS_RERANK_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        limit=limit,
        candidate_limit=candidate_limit,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        use_semantic=use_semantic,
        use_neural=use_neural,
        force_policy=force_policy,
        write_latest=write_latest,
    )


def nervous_rerank_eval_write_latest(data: dict[str, Any]) -> dict[str, Any]:
    return nervous_retrieval_adapters.write_latest_history(data, _core.NERVOUS_RERANK_EVAL_LATEST_PATH, _core.NERVOUS_RERANK_EVAL_ROOT)


def nervous_rerank_eval(force_policy: bool = False, write_latest: bool = True) -> dict[str, Any]:
    return nervous_retrieval_adapters.rerank_eval_document(
        profile=nervous_rerank_profile(),
        rerank_search=nervous_rerank_search,
        latest_path=_core.NERVOUS_RERANK_EVAL_LATEST_PATH,
        daily_root=_core.NERVOUS_RERANK_EVAL_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        force_policy=force_policy,
        write_latest=write_latest,
        latest_writer=nervous_rerank_eval_write_latest,
    )


def nervous_recall_pack(
    query: str,
    limit: int | None = None,
    mode: str = "lexical",
    force_policy: bool = False,
    source: str | None = None,
    schema: str | None = None,
    since: str | None = None,
    until: str | None = None,
    severity: str | None = None,
    sensitivity: str | None = None,
    write_latest: bool = True,
) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    if bool(privacy.get("global_pause")):
        return nervous_recall_contracts.refused_result(_core.SCHEMA_PREFIX, _core.VERSION, _core.now_iso())
    return nervous_retrieval_adapters.build_recall_pack(
        query=query,
        index_search=nervous_index_search,
        rerank_search=nervous_rerank_search,
        latest_path=_core.NERVOUS_RETRIEVAL_LATEST_PATH,
        daily_root=_core.NERVOUS_RETRIEVAL_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        limit=limit,
        mode=mode,
        force_policy=force_policy,
        source=source,
        schema=schema,
        since=since,
        until=until,
        severity=severity,
        sensitivity=sensitivity,
        write_latest=write_latest,
    )


def nervous_recent_episodes(limit: int = 8, scope: str = "now") -> dict[str, Any]:
    items, parse_errors = nervous_episode_records()
    return nervous_brief_contracts.recent_episodes_document(items, parse_errors, limit=limit, scope=scope)


def nervous_brief(scope: str = "now", limit: int = 8, refresh: bool = False, write_latest: bool = True) -> dict[str, Any]:
    global NERVOUS_BRIEF_CACHE
    scope = nervous_brief_contracts.normalize_scope(scope)
    limit = nervous_brief_contracts.normalize_limit(limit)
    cache_key = nervous_brief_contracts.cache_key(scope, limit, refresh)
    if cache_key in NERVOUS_BRIEF_CACHE:
        return json.loads(json.dumps(NERVOUS_BRIEF_CACHE[cache_key]))
    quality = nervous_quality_audit(refresh=refresh, refresh_index=False, write_latest=True, deep_index_validate=False)
    nervous_status(write_latest=True)
    privacy = _core.nervous_privacy_status(write_latest=True)
    capture = _core.nervous_capture_status()
    index_status = nervous_index_status(write_latest=True)
    semantic_status = nervous_semantic_status(write_latest=True)
    derived_refresh = nervous_derived_refresh_status()
    synthesis = nervous_synthesis_latest()
    obs = _core.observability_status()
    memory = _core.memory_plan(write_latest=False)
    storage = _core.storage_status(write_latest=True, full_ai_scan=False)
    processes = _core.process_latest()
    resource = _core.resource_status(write_latest=True)
    recent_episodes = nervous_recent_episodes(limit=limit, scope="today" if scope == "today" else "now")

    semantic_config = nervous_semantic_config()
    semantic_thresholds = nervous_brief_contracts.semantic_maintenance_thresholds(semantic_config)
    semantic_maintenance_assessment = nervous_semantic_maintain_assess(
        semantic_status,
        int(semantic_thresholds["min_delta_chunks"]),
        float(semantic_thresholds["max_stale_minutes"]),
        force_refresh=False,
    )
    data = nervous_brief_contracts.brief_document(
        scope=scope,
        quality=quality,
        privacy=privacy,
        capture=capture,
        index_status=index_status,
        semantic_status=semantic_status,
        semantic_maintenance=semantic_maintenance_assessment,
        derived_refresh=derived_refresh,
        synthesis=synthesis,
        observability=obs,
        memory=memory,
        storage=storage,
        processes=processes,
        resource=resource,
        recent_episodes=recent_episodes,
        commands={
            "quality": _core.NERVOUS_QUALITY_AUDIT_COMMAND,
            "quality_refresh": _core.NERVOUS_QUALITY_AUDIT_REFRESH_COMMAND,
            "quality_refresh_index_operator": _core.NERVOUS_QUALITY_AUDIT_REFRESH_INDEX_COMMAND,
            "quality_recheck": _core.NERVOUS_QUALITY_AUDIT_COMMAND,
            "search": "abyss-machine nervous search --query TEXT --json",
            "rerank": "abyss-machine nervous rerank --query TEXT --json",
            "hybrid_recall": "abyss-machine nervous recall --mode hybrid --query TEXT --json",
            "semantic_status": _core.NERVOUS_SEMANTIC_MAINTAIN_STATUS_COMMAND,
            "semantic_maintain_review": _core.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
            "semantic_maintain_retry": _core.NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
        },
        latest_path=str(_core.NERVOUS_BRIEF_LATEST_PATH),
        daily_glob=str(_core.NERVOUS_BRIEF_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )
    if write_latest:
        errors = _core.nervous_write_json_latest_and_daily(_core.NERVOUS_BRIEF_LATEST_PATH, _core.NERVOUS_BRIEF_ROOT, data)
        if errors:
            data["ok"] = False
            data["write_errors"] = errors
        NERVOUS_BRIEF_CACHE[cache_key] = json.loads(json.dumps(data))
    return data


def nervous_synthesis_build(scope: str = "daily", date_value: str | None = None, hour: int | None = None, write_latest: bool = True) -> dict[str, Any]:
    scope = scope if scope in {"hourly", "daily"} else "daily"
    privacy = _core.nervous_effective_privacy(write_latest=False)
    return nervous_synthesis_adapters.run_synthesis_build(
        privacy=privacy,
        episodes_root=_core.NERVOUS_EPISODES_ROOT,
        events_root=_core.NERVOUS_EVENTS_ROOT,
        latest_path=_core.NERVOUS_SYNTHESIS_LATEST_PATH,
        hourly_root=_core.NERVOUS_SYNTHESIS_HOURLY_ROOT,
        daily_root=_core.NERVOUS_SYNTHESIS_DAILY_ROOT,
        scope=scope,
        date_value=date_value,
        hour=hour,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        records_reader=nervous_records_from_jsonl_root,
        latest_writer=_core.safe_atomic_write_json,
        period_writer=nervous_replace_synthesis_period_record,
        text_writer=_core.nervous_write_text_atomic,
    )


def nervous_synthesis_latest() -> dict[str, Any]:
    return nervous_latest_read(_core.NERVOUS_SYNTHESIS_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_nervous_synthesis_latest_read_v1")


def nervous_synthesis_validate(write_latest: bool = True) -> dict[str, Any]:
    return nervous_synthesis_adapters.validate_synthesis(
        latest_path=_core.NERVOUS_SYNTHESIS_LATEST_PATH,
        episodes_latest_path=_core.NERVOUS_EPISODES_LATEST_PATH,
        validate_latest_path=_core.NERVOUS_SYNTHESIS_VALIDATE_LATEST_PATH,
        hourly_root=_core.NERVOUS_SYNTHESIS_HOURLY_ROOT,
        daily_root=_core.NERVOUS_SYNTHESIS_DAILY_ROOT,
        episodes_root=_core.NERVOUS_EPISODES_ROOT,
        events_root=_core.NERVOUS_EVENTS_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        records_reader=nervous_records_from_jsonl_root,
        latest_reader=_core.load_json_document,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_eval_run(write_latest: bool = True) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    return nervous_synthesis_adapters.run_eval(
        privacy=privacy,
        latest_path=_core.NERVOUS_EVALS_LATEST_PATH,
        daily_root=_core.NERVOUS_EVALS_ROOT,
        recall_latest_path=_core.NERVOUS_RETRIEVAL_LATEST_PATH,
        synthesis_latest_path=_core.NERVOUS_SYNTHESIS_LATEST_PATH,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        events_validate=nervous_events_validate,
        episodes_validate=nervous_episodes_validate,
        index_validate=nervous_index_validate,
        recall_pack=nervous_recall_pack,
        synthesis_build=nervous_synthesis_build,
        synthesis_validate=nervous_synthesis_validate,
    )


def nervous_eval_latest() -> dict[str, Any]:
    return nervous_latest_read(_core.NERVOUS_EVALS_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_nervous_eval_latest_read_v1")


def nervous_eval_validate(write_latest: bool = True) -> dict[str, Any]:
    return nervous_synthesis_adapters.validate_eval(
        latest_path=_core.NERVOUS_EVALS_LATEST_PATH,
        validate_latest_path=_core.NERVOUS_EVALS_VALIDATE_LATEST_PATH,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest_enabled=write_latest,
        latest_reader=_core.load_json_document,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_file_record_time(path: Path) -> dt.datetime | None:
    return nervous_retention_adapters.file_record_time(path)


def nervous_retention_roots() -> dict[str, Any]:
    return {
        "facts": _core.NERVOUS_FACTS_ROOT,
        "events": _core.NERVOUS_EVENTS_ROOT,
        "episodes": _core.NERVOUS_EPISODES_ROOT,
        "retrieval": _core.NERVOUS_RETRIEVAL_ROOT,
        "synthesis": _core.NERVOUS_SYNTHESIS_ROOT,
        "evals": _core.NERVOUS_EVALS_ROOT,
        "checks": _core.NERVOUS_CHECKS_ROOT,
        "private_capture_artifacts": _core.NERVOUS_PRIVATE_CAPTURE_ROOT,
        "browser_content": _core.NERVOUS_BROWSER_CONTENT_ROOT,
    }


def nervous_retention_paths_document(validate: bool = False) -> dict[str, Any]:
    paths = {
        "latest": str(_core.NERVOUS_RETENTION_LATEST_PATH),
        "daily_glob": str(_core.NERVOUS_RETENTION_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
    }
    if validate:
        paths["validate_latest"] = str(_core.NERVOUS_RETENTION_VALIDATE_LATEST_PATH)
    return paths


def nervous_retention_route_specs() -> list[dict[str, Any]]:
    return nervous_retention_contracts.route_specs(_core.nervous_privacy(write_latest=False), nervous_retention_roots())


def nervous_retention_plan(write_latest: bool = True) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    if bool(privacy.get("global_pause")) and write_latest:
        return nervous_retention_contracts.plan_refused_result(_core.SCHEMA_PREFIX, _core.VERSION, _core.now_iso())
    return nervous_retention_adapters.plan(
        routes=nervous_retention_route_specs(),
        paths=nervous_retention_paths_document(),
        latest_path=_core.NERVOUS_RETENTION_LATEST_PATH,
        daily_root=_core.NERVOUS_RETENTION_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        stop_at=_core.NERVOUS_ROOT,
        write_latest=write_latest,
    )


def nervous_retention_apply(dry_run: bool = True, confirm: bool = False, write_latest: bool = True) -> dict[str, Any]:
    privacy = _core.nervous_effective_privacy(write_latest=False)
    if bool(privacy.get("global_pause")):
        return nervous_retention_contracts.apply_refused_result(_core.SCHEMA_PREFIX, _core.VERSION, _core.now_iso())
    plan = nervous_retention_plan(write_latest=False)
    return nervous_retention_adapters.apply(
        plan_document=plan,
        dry_run=dry_run,
        confirm=confirm,
        paths=nervous_retention_paths_document(),
        latest_path=_core.NERVOUS_RETENTION_LATEST_PATH,
        daily_root=_core.NERVOUS_RETENTION_ROOT,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest=write_latest,
    )


def nervous_retention_validate(write_latest: bool = True) -> dict[str, Any]:
    plan = nervous_retention_plan(write_latest=False)
    return nervous_retention_adapters.validate(
        plan_document=plan,
        latest_path=_core.NERVOUS_RETENTION_LATEST_PATH,
        validate_latest_path=_core.NERVOUS_RETENTION_VALIDATE_LATEST_PATH,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        write_latest=write_latest,
        latest_reader=_core.load_json_document,
        latest_writer=_core.safe_atomic_write_json,
    )


def nervous_latest_record_from_history(root: Path) -> dict[str, Any] | None:
    latest_record: dict[str, Any] | None = None
    latest_time: dt.datetime | None = None
    for path in _core.nervous_jsonl_files(root):
        records, _errors = _core.nervous_parse_jsonl_records(path)
        for record in records:
            record_time = _core.parse_time(record.get("observed_at") or record.get("start_at") or record.get("generated_at"))
            if record_time is None:
                continue
            if latest_time is None or record_time > latest_time:
                latest_time = record_time
                latest_record = record
    return latest_record


def nervous_latest_fact_from_history() -> dict[str, Any] | None:
    return nervous_latest_record_from_history(_core.NERVOUS_FACTS_ROOT)


def nervous_rebuild_fact_latest() -> dict[str, Any]:
    latest = nervous_latest_fact_from_history()
    if latest is None:
        empty = {
            "schema": f"{_core.SCHEMA_PREFIX}_nervous_fact_snapshot_empty_v1",
            "version": _core.VERSION,
            "generated_at": _core.now_iso(),
            "ok": True,
            "empty": True,
            "reason": "no remaining fact snapshots",
        }
        error = _core.safe_atomic_write_json(_core.NERVOUS_FACTS_LATEST_PATH, empty, 0o664)
        if error:
            empty["write_errors"] = [error]
            empty["ok"] = False
        return empty
    error = _core.safe_atomic_write_json(_core.NERVOUS_FACTS_LATEST_PATH, latest, 0o664)
    if error:
        latest = dict(latest)
        latest["write_errors"] = [error]
        latest["ok"] = False
    return latest


def nervous_forget(minutes: float, dry_run: bool = False, reason: str | None = None) -> dict[str, Any]:
    if dry_run:
        return _nervous_forget_unlocked(minutes, dry_run=True, reason=reason)
    with _core.snapshot_history.maintenance_lock(_core.NERVOUS_FACTS_ROOT):
        return _nervous_forget_unlocked(minutes, dry_run=False, reason=reason)


def _nervous_forget_unlocked(minutes: float, dry_run: bool = False, reason: str | None = None) -> dict[str, Any]:
    minutes = max(0.1, min(float(minutes), 24 * 60.0))
    cutoff = dt.datetime.now(dt.timezone.utc).astimezone() - dt.timedelta(minutes=minutes)
    files: list[dict[str, Any]] = []
    artifact_files: list[dict[str, Any]] = []
    removed_total = 0
    kept_total = 0
    artifact_removed_total = 0
    parse_errors: list[dict[str, Any]] = []
    for path in nervous_fact_jsonl_files():
        records, errors = _core.nervous_parse_jsonl_records(path)
        parse_errors.extend(errors)
        kept: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        for record in records:
            record_time = _core.parse_time(record.get("generated_at"))
            if record_time is not None and record_time >= cutoff:
                removed.append(record)
            else:
                kept.append(record)
        removed_total += len(removed)
        kept_total += len(kept)
        file_report = {
            "path": str(path),
            "records_before": len(records),
            "records_removed": len(removed),
            "records_kept": len(kept),
        }
        if removed and not dry_run:
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), prefix=f".{path.name}.", delete=False) as tmp:
                    for record in kept:
                        json.dump(record, tmp, sort_keys=False)
                        tmp.write("\n")
                    tmp_name = tmp.name
                os.chmod(tmp_name, 0o664)
                try:
                    os.chown(tmp_name, -1, grp.getgrnam(_core.MODE_STATE_GROUP).gr_gid)
                except (KeyError, OSError):
                    pass
                os.replace(tmp_name, path)
                file_report["rewritten"] = True
            except OSError as exc:
                file_report["rewrite_error"] = str(exc)
        files.append(file_report)
    if _core.NERVOUS_PRIVATE_CAPTURE_ROOT.exists():
        for path in sorted(item for item in _core.NERVOUS_PRIVATE_CAPTURE_ROOT.rglob("*") if item.is_file()):
            mtime = nervous_file_record_time(path)
            if mtime is None or mtime < cutoff:
                continue
            artifact_report = {
                "path": str(path),
                "mtime": mtime.isoformat(timespec="seconds"),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "removed": False,
            }
            if not dry_run:
                try:
                    path.unlink()
                    artifact_report["removed"] = True
                    artifact_removed_total += 1
                except OSError as exc:
                    artifact_report["remove_error"] = str(exc)
            artifact_files.append(artifact_report)
    latest = None if dry_run else nervous_rebuild_fact_latest()
    derived_rebuild = None
    index_rebuild = None
    if not dry_run:
        events_rebuild = nervous_events_build(write_latest=True)
        episodes_rebuild = nervous_episodes_build(write_latest=True, refresh_events=False)
        index_rebuild = nervous_index_build(write_latest=True, refresh_derived=False)
        derived_rebuild = {
            "events": {
                "ok": events_rebuild.get("ok"),
                "events": _core.nested_get(events_rebuild, ["summary", "events"]),
                "error": events_rebuild.get("error"),
            },
            "episodes": {
                "ok": episodes_rebuild.get("ok"),
                "episodes": _core.nested_get(episodes_rebuild, ["summary", "episodes"]),
                "error": episodes_rebuild.get("error"),
            },
        }
    audit = _core.nervous_privacy_audit({
        "event": "forget_window",
        "change_id": nervous_change_id("forget"),
        "minutes": minutes,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "records_removed": removed_total,
        "records_kept": kept_total,
        "artifact_files_removed": artifact_removed_total,
        "reason": reason,
    }, write=not dry_run)
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_forget_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": not any(item.get("rewrite_error") for item in files) and not parse_errors,
        "dry_run": dry_run,
        "minutes": minutes,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "summary": {
            "files": len(files),
            "records_removed": removed_total,
            "records_kept": kept_total,
            "artifact_files_seen": len(artifact_files),
            "artifact_files_removed": artifact_removed_total,
            "parse_errors": len(parse_errors),
        },
        "files": files,
        "artifact_files": artifact_files[:200],
        "parse_errors": parse_errors[:20],
        "latest": {
            "path": str(_core.NERVOUS_FACTS_LATEST_PATH),
            "schema": latest.get("schema") if isinstance(latest, dict) else None,
            "generated_at": latest.get("generated_at") if isinstance(latest, dict) else None,
        } if not dry_run else None,
        "derived_rebuild": derived_rebuild,
        "index_rebuild": {
            "ok": index_rebuild.get("ok"),
            "records_indexed": _core.nested_get(index_rebuild, ["summary", "records_indexed"]),
            "chunks_indexed": _core.nested_get(index_rebuild, ["summary", "chunks_indexed"]),
            "error": index_rebuild.get("error"),
        } if isinstance(index_rebuild, dict) else None,
        "audit": audit,
    }


def typing_nervous_refresh_store(data: dict[str, Any], write_latest: bool = True) -> dict[str, Any]:
    return _core.typing_store_latest_history_and_index(
        data,
        write_latest,
        _core.TYPING_NERVOUS_REFRESH_LATEST_PATH,
        _core.TYPING_NERVOUS_REFRESH_ROOT,
    )


def typing_nervous_refresh_latest_status(max_age_sec: float = 900.0) -> dict[str, Any]:
    latest, latest_error = _core.load_json_document(_core.TYPING_NERVOUS_REFRESH_LATEST_PATH)
    timer = _core.user_systemd_unit(_core.TYPING_NERVOUS_REFRESH_TIMER)
    service = _core.user_systemd_unit(_core.TYPING_NERVOUS_REFRESH_SERVICE)
    return _core.build_typing_nervous_refresh_latest_status(
        latest=latest,
        latest_error=latest_error,
        timer=timer,
        service=service,
        latest_path=_core.TYPING_NERVOUS_REFRESH_LATEST_PATH,
        max_age_sec=max_age_sec,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def typing_nervous_refresh_fact_state() -> dict[str, Any]:
    facts_latest, facts_error = _core.load_json_document(_core.NERVOUS_FACTS_LATEST_PATH)
    return _core.build_typing_nervous_refresh_fact_state(
        facts_latest=facts_latest,
        facts_error=facts_error,
        latest_path=_core.NERVOUS_FACTS_LATEST_PATH,
    )


def typing_nervous_refresh(
    limit: int = 240,
    force_snapshot: bool = False,
    force_index: bool = False,
    write_latest: bool = True,
) -> dict[str, Any]:
    generated_at = _core.now_iso()
    bounded_limit = max(1, min(int(limit), 1000))
    latest_event, latest_error = _core.load_json_document(_core.TYPING_EVENTS_LATEST_PATH)
    latest_event_data = latest_event if isinstance(latest_event, dict) else {}
    previous_refresh, previous_refresh_error = _core.load_json_document(_core.TYPING_NERVOUS_REFRESH_LATEST_PATH)
    previous_refresh_data = previous_refresh if isinstance(previous_refresh, dict) else {}
    process = _core.typing_process(limit=bounded_limit, write_latest=True)
    fact_before = typing_nervous_refresh_fact_state()
    processing_before = typing_nervous_processing_status()
    index_before: dict[str, Any] = {}
    assessment_before = _core.typing_nervous_refresh_needed(
        latest_event_data,
        fact_before,
        process,
        index_before,
        processing_before,
    )
    if force_index or processing_before.get("ok") is not True:
        index_before = nervous_index_status(write_latest=False)
        assessment_before = _core.typing_nervous_refresh_needed(
            latest_event_data,
            fact_before,
            process,
            index_before,
            processing_before,
        )

    actions: list[dict[str, Any]] = []
    snapshot: dict[str, Any] | None = None
    if force_snapshot or assessment_before.get("snapshot_needed"):
        snapshot = _core.nervous_snapshot(write_latest=True, trigger="typing_nervous_refresh")
        actions.append(_core.typing_nervous_refresh_snapshot_action(snapshot=snapshot, force_snapshot=force_snapshot))
    else:
        actions.append(_core.typing_nervous_refresh_snapshot_action(snapshot=None, force_snapshot=force_snapshot))

    if isinstance(snapshot, dict):
        fact_after_snapshot = typing_nervous_refresh_fact_state()
        processing_after_snapshot = typing_nervous_processing_status()
        index_after_snapshot = nervous_index_status(write_latest=False)
        assessment_after_snapshot = _core.typing_nervous_refresh_needed(
            latest_event_data,
            fact_after_snapshot,
            process,
            index_after_snapshot,
            processing_after_snapshot,
        )
    else:
        fact_after_snapshot = fact_before
        processing_after_snapshot = processing_before
        index_after_snapshot = index_before
        assessment_after_snapshot = assessment_before

    index_service = _core.user_systemd_unit(_core.NERVOUS_SEARCH_INDEX_SERVICE)
    dynamic_index_units = user_systemd_running_units("abyss-machine-indexing*.service")
    index_service_running = (
        str(index_service.get("active") or "") in {"active", "activating", "reloading"}
        or bool(dynamic_index_units)
    )
    snapshot_ran_ok = isinstance(snapshot, dict) and snapshot.get("ok") is True
    index_needed = bool(force_index or snapshot_ran_ok or assessment_after_snapshot.get("index_needed"))
    index_min_interval_sec = max(
        0.0,
        _core.safe_float(os.environ.get("ABYSS_MACHINE_TYPING_NERVOUS_INDEX_MIN_INTERVAL_SEC"), 900.0) or 0.0,
    )
    index_attempt_context = _core.typing_nervous_refresh_index_attempt_context(
        index_needed=index_needed,
        force_index=force_index,
        previous_refresh=previous_refresh_data,
        index_status=index_after_snapshot,
        assessment=assessment_after_snapshot,
        index_min_interval_sec=index_min_interval_sec,
    )
    index_min_interval_sec = index_attempt_context["index_min_interval_sec"]
    previous_refresh_age_sec = index_attempt_context["previous_refresh_age_sec"]
    previous_index_launch_attempted = index_attempt_context["previous_index_launch_attempted"]
    previous_index_attempt_age_basis = index_attempt_context["previous_index_attempt_age_basis"]
    previous_index_attempt_age_sec = index_attempt_context["previous_index_attempt_age_sec"]
    debounce_candidate_records_lag = index_attempt_context["debounce_candidate_records_lag"]
    debounce_candidate_records_lag_tolerance = index_attempt_context["debounce_candidate_records_lag_tolerance"]
    recent_index_debounce_candidate = index_attempt_context["recent_index_debounce_candidate"]
    index_deferred_recent_attempt = index_attempt_context["index_deferred_recent_attempt"]
    index_debounce_bypassed_for_lag = index_attempt_context["index_debounce_bypassed_for_lag"]
    index_launch: dict[str, Any] | None = None
    index_retry_launch: dict[str, Any] | None = None
    index_launch_already_running = False
    index_wait_observations: list[dict[str, Any]] = []
    if index_deferred_recent_attempt:
        actions.append(
            _core.typing_nervous_refresh_index_action(
                action_status="deferred_recent_index_attempt",
                previous_refresh=previous_refresh_data,
                previous_index_attempt_age_sec=previous_index_attempt_age_sec,
                index_min_interval_sec=index_min_interval_sec,
            )
        )
    elif index_needed and index_service_running and not force_index:
        actions.append(
            _core.typing_nervous_refresh_index_action(
                action_status="deferred_existing_index_build_running",
                index_service=index_service,
                dynamic_index_units=dynamic_index_units,
            )
        )
    elif index_needed:
        index_launch = _core.resource_launch(
            ["abyss-machine", "nervous", "index-build", "--json"],
            workload_class="medium",
            kind="indexing",
            unattended=True,
            timeout_sec=300,
            write_latest=True,
        )
        index_launch_text = " ".join(
            str(item or "")
            for item in (
                _core.nested_get(index_launch, ["execution", "stdout_tail"]),
                _core.nested_get(index_launch, ["execution", "stderr_tail"]),
                index_launch.get("error"),
            )
        )
        index_launch_already_running = "another index build is already running" in index_launch_text
        actions.append(
            _core.typing_nervous_refresh_index_action(
                action_status="launched",
                index_launch=index_launch,
                force_index=force_index,
                index_launch_already_running=index_launch_already_running,
                index_debounce_bypassed_for_lag=index_debounce_bypassed_for_lag,
                debounce_candidate_records_lag=debounce_candidate_records_lag,
                debounce_candidate_records_lag_tolerance=debounce_candidate_records_lag_tolerance,
            )
        )
    else:
        actions.append(_core.typing_nervous_refresh_index_action(action_status="not_needed"))

    if index_needed and not index_deferred_recent_attempt and not (index_service_running and not force_index):
        processing_after = typing_nervous_processing_status()
        index_after = nervous_index_status(write_latest=False)
        if index_launch_already_running and processing_after.get("ok") is not True:
            deadline = time.monotonic() + 45.0
            while time.monotonic() < deadline and processing_after.get("ok") is not True:
                time.sleep(5.0)
                processing_after = typing_nervous_processing_status()
                index_after = nervous_index_status(write_latest=False)
                index_wait_observations.append({
                    "observed_at": _core.now_iso(),
                    "processing_ok": processing_after.get("ok"),
                    "records_lag": _core.nested_get(index_after, ["freshness", "records_lag"]),
                    "stale": _core.nested_get(index_after, ["freshness", "stale"]),
                    "index_built_at": _core.nested_get(index_after, ["freshness", "index_built_at"]),
                })
        assessment_after = _core.typing_nervous_refresh_needed(
            latest_event_data,
            fact_after_snapshot,
            process,
            index_after,
            processing_after,
        )
    else:
        processing_after = processing_after_snapshot
        index_after = index_after_snapshot
        assessment_after = assessment_after_snapshot
    if (
        index_needed
        and not index_deferred_recent_attempt
        and processing_after.get("ok") is not True
        and str(processing_after.get("status") or "") == "facts_ready_index_stale"
        and isinstance(index_launch, dict)
        and index_launch.get("ok") is True
        and not index_launch_already_running
    ):
        index_retry_launch = _core.resource_launch(
            ["abyss-machine", "nervous", "index-build", "--json"],
            workload_class="medium",
            kind="indexing",
            unattended=True,
            timeout_sec=300,
            write_latest=True,
        )
        actions.append(_core.typing_nervous_refresh_index_retry_action(index_retry_launch))
        processing_after = typing_nervous_processing_status()
        index_after = nervous_index_status(write_latest=False)
        assessment_after = _core.typing_nervous_refresh_needed(
            latest_event_data,
            fact_after_snapshot,
            process,
            index_after,
            processing_after,
        )
    synthesis_refresh: dict[str, Any] | None = None
    synthesis_validation: dict[str, Any] | None = None
    final_context = _core.typing_nervous_refresh_final_context(
        process=process,
        latest_event=latest_event_data,
        assessment_before=assessment_before,
        processing_after=processing_after,
        fact_after_snapshot=fact_after_snapshot,
        index_after=index_after,
        index_launch=index_launch,
        index_needed=index_needed,
        force_index=force_index,
        index_deferred_recent_attempt=index_deferred_recent_attempt,
        index_service_running=index_service_running,
        index_launch_already_running=index_launch_already_running,
        previous_index_attempt_age_sec=previous_index_attempt_age_sec,
        previous_index_attempt_age_basis=previous_index_attempt_age_basis,
        previous_refresh_age_sec=previous_refresh_age_sec,
        index_min_interval_sec=index_min_interval_sec,
        recent_index_debounce_candidate=recent_index_debounce_candidate,
        index_debounce_bypassed_for_lag=index_debounce_bypassed_for_lag,
        debounce_candidate_records_lag=debounce_candidate_records_lag,
        debounce_candidate_records_lag_tolerance=debounce_candidate_records_lag_tolerance,
    )
    final_pending = bool(final_context["final_pending"])
    index_resource_gated = bool(final_context["index_resource_gated"])
    synthesis_needed = bool(final_context["synthesis_needed"])
    if synthesis_needed:
        synthesis_refresh = nervous_synthesis_build(scope="daily", write_latest=True)
        synthesis_validation = nervous_synthesis_validate(write_latest=True)
    actions.append(
        _core.typing_nervous_refresh_synthesis_action(
            synthesis_needed=synthesis_needed,
            index_needed=index_needed,
            final_context=final_context,
            synthesis_refresh=synthesis_refresh,
            synthesis_validation=synthesis_validation,
        )
    )
    final_context = _core.typing_nervous_refresh_final_context(
        process=process,
        latest_event=latest_event_data,
        assessment_before=assessment_before,
        processing_after=processing_after,
        fact_after_snapshot=fact_after_snapshot,
        index_after=index_after,
        index_launch=index_launch,
        index_needed=index_needed,
        force_index=force_index,
        index_deferred_recent_attempt=index_deferred_recent_attempt,
        index_service_running=index_service_running,
        index_launch_already_running=index_launch_already_running,
        previous_index_attempt_age_sec=previous_index_attempt_age_sec,
        previous_index_attempt_age_basis=previous_index_attempt_age_basis,
        previous_refresh_age_sec=previous_refresh_age_sec,
        index_min_interval_sec=index_min_interval_sec,
        recent_index_debounce_candidate=recent_index_debounce_candidate,
        index_debounce_bypassed_for_lag=index_debounce_bypassed_for_lag,
        debounce_candidate_records_lag=debounce_candidate_records_lag,
        debounce_candidate_records_lag_tolerance=debounce_candidate_records_lag_tolerance,
        synthesis_refresh=synthesis_refresh,
        synthesis_validation=synthesis_validation,
    )
    data = _core.typing_nervous_refresh_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=generated_at,
        finished_at=_core.now_iso(),
        final_context=final_context,
        latest_event=latest_event,
        latest_error=latest_error,
        process=process,
        fact_before=fact_before,
        fact_after_snapshot=fact_after_snapshot,
        index_before=index_before,
        index_after=index_after,
        index_service=index_service,
        index_launch=index_launch,
        index_retry_launch=index_retry_launch,
        index_launch_already_running=index_launch_already_running,
        index_wait_observations=index_wait_observations,
        previous_refresh=previous_refresh,
        previous_refresh_error=previous_refresh_error,
        previous_index_launch_attempted=previous_index_launch_attempted,
        synthesis_refresh=synthesis_refresh,
        synthesis_validation=synthesis_validation,
        processing_before=processing_before,
        processing_after_snapshot=processing_after_snapshot,
        processing_after=processing_after,
        assessment_before=assessment_before,
        assessment_after_snapshot=assessment_after_snapshot,
        assessment_after=assessment_after,
        actions=actions,
        latest_path=_core.TYPING_NERVOUS_REFRESH_LATEST_PATH,
        daily_glob_path=_core.TYPING_NERVOUS_REFRESH_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl",
        typing_process_path=_core.TYPING_PROCESS_LATEST_PATH,
        nervous_facts_path=_core.NERVOUS_FACTS_LATEST_PATH,
        nervous_index_path=_core.NERVOUS_SEARCH_INDEX_LATEST_PATH,
    )
    return typing_nervous_refresh_store(data, write_latest)


def typing_nervous_processing_status() -> dict[str, Any]:
    source_id = "typed_text_autolog"
    source = _core.nervous_source_lookup(source_id) or {}
    facts_latest, facts_error = _core.load_json_document(_core.NERVOUS_FACTS_LATEST_PATH)
    index_latest, index_error = _core.load_json_document(_core.NERVOUS_SEARCH_INDEX_LATEST_PATH)
    index_evidence = _core.typing_nervous_index_latest_evidence(index_latest, source_id=source_id)
    index_source_ids = {
        str(item)
        for item in index_evidence.get("source_ids", [])
        if str(item or "").strip()
    }
    counts = index_evidence.get("counts") if isinstance(index_evidence.get("counts"), dict) else {}
    if not counts or counts.get("fts_chunks") is None:
        counts = nervous_index_db_counts_bounded()
    source_probe: dict[str, Any] = {}
    if source_id not in index_source_ids and _core.NERVOUS_SEARCH_INDEX_DB_PATH.exists():
        source_probe = nervous_index_source_present(source_id)
    return _core.build_typing_nervous_processing_status_document(
        source=source,
        facts_latest=facts_latest,
        facts_error=facts_error,
        index_latest=index_latest,
        index_error=index_error,
        facts_latest_path=_core.NERVOUS_FACTS_LATEST_PATH,
        index_latest_path=_core.NERVOUS_SEARCH_INDEX_LATEST_PATH,
        counts_fallback=counts,
        source_probe=source_probe,
        source_id=source_id,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )


def nervous_typed_text_fact(sources: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    source_id = "typed_text_autolog"
    if not _core.nervous_source_enabled(sources, source_id):
        return None, {"source": source_id, "reason": "disabled_by_source_policy"}
    latest, latest_error = _core.load_json_document(_core.TYPING_EVENTS_LATEST_PATH)
    process_latest, process_error = _core.load_json_document(_core.TYPING_PROCESS_LATEST_PATH)
    process_summary = process_latest.get("summary") if isinstance(process_latest, dict) and isinstance(process_latest.get("summary"), dict) else {}
    records, parse_errors = _core.typing_records(20)
    entries: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        text_payload = record.get("text") if isinstance(record.get("text"), dict) else {}
        entries.append({
            "event_id": record.get("event_id"),
            "generated_at": record.get("generated_at"),
            "status": record.get("status"),
            "source_adapter": record.get("source_adapter"),
            "sensitivity": record.get("sensitivity"),
            "text": text_payload.get("text") if text_payload.get("captured") else None,
            "text_sha256": text_payload.get("text_sha256"),
            "text_length": text_payload.get("text_length"),
            "redaction": text_payload.get("redaction"),
            "classification": record.get("classification") if isinstance(record.get("classification"), dict) else {},
            "causal_context": record.get("causal_context") if isinstance(record.get("causal_context"), dict) else {},
        })
    payload = {
        "latest": str(_core.TYPING_EVENTS_LATEST_PATH),
        "latest_error": latest_error,
        "process_latest": str(_core.TYPING_PROCESS_LATEST_PATH),
        "process_error": process_error,
        "process_summary": process_summary,
        "entries": entries,
        "parse_errors": parse_errors[:10],
    }
    return {
        "name": "typed_text_autolog",
        "source_id": source_id,
        "ok": isinstance(latest, dict) or bool(entries),
        "observed_at": _core.now_iso(),
        "sensitivity": "local_private_redacted",
        "summary": {
            "latest_exists": isinstance(latest, dict),
            "entries_indexed": len(entries),
            "parse_errors": len(parse_errors),
            "process_latest_exists": isinstance(process_latest, dict),
            "process_lanes": process_summary.get("lanes"),
            "process_context_bound": process_summary.get("context_bound"),
            "process_missing_context_anchor": process_summary.get("missing_context_anchor"),
            "process_quality_gaps": process_summary.get("quality_gaps"),
            "raw_keylogging": False,
            "password_fields_captured": False,
        },
        "entries": entries,
        "process": {
            "latest": str(_core.TYPING_PROCESS_LATEST_PATH),
            "exists": isinstance(process_latest, dict),
            "error": process_error,
            "status": process_latest.get("status") if isinstance(process_latest, dict) else None,
            "summary": process_summary,
            "by_project": process_latest.get("by_project") if isinstance(process_latest, dict) else None,
            "by_recipient": process_latest.get("by_recipient") if isinstance(process_latest, dict) else None,
            "by_task_binding": process_latest.get("by_task_binding") if isinstance(process_latest, dict) else None,
            "by_context_anchor_kind": process_latest.get("by_context_anchor_kind") if isinstance(process_latest, dict) else None,
            "context_notes": process_latest.get("context_notes") if isinstance(process_latest, dict) else None,
        },
        "parse_errors": parse_errors[:10],
        "source": _core.nervous_file_source(_core.TYPING_EVENTS_LATEST_PATH) if _core.TYPING_EVENTS_LATEST_PATH.exists() else _core.nervous_virtual_source(source_id, payload),
        "raw_private_content": False,
        "policy": {
            "facts_only": True,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
        },
    }, None


def nervous_baseline(write_latest: bool = True) -> dict[str, Any]:
    status_data = nervous_status(write_latest=write_latest)
    validate_data = _core.nervous_validate_snapshot()
    events_validate_data = nervous_events_validate(write_latest=False)
    episodes_validate_data = nervous_episodes_validate(write_latest=False)
    synthesis_validate_data = nervous_synthesis_validate(write_latest=False)
    eval_validate_data = nervous_eval_validate(write_latest=False)
    retention_validate_data = nervous_retention_validate(write_latest=False)
    index_status_data = nervous_index_status(write_latest=False)
    index_validate_data = nervous_index_validate(write_latest=False) if _core.NERVOUS_SEARCH_INDEX_DB_PATH.exists() else {
        "ok": False,
        "summary": {"fails": 1, "warnings": 0, "checks": 0},
        "error": "index database missing",
    }
    timer = _core.user_systemd_unit(_core.NERVOUS_PASSIVE_CHRONICLE_TIMER)
    service = _core.user_systemd_unit(_core.NERVOUS_PASSIVE_CHRONICLE_SERVICE)
    browser_content_timer = _core.user_systemd_unit(_core.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER)
    browser_content_service = _core.user_systemd_unit(_core.NERVOUS_BROWSER_CONTENT_CAPTURE_SERVICE)
    index_timer = _core.user_systemd_unit(_core.NERVOUS_SEARCH_INDEX_TIMER)
    index_service = _core.user_systemd_unit(_core.NERVOUS_SEARCH_INDEX_SERVICE)
    facts_latest, latest_error = _core.load_json_document(_core.NERVOUS_FACTS_LATEST_PATH)
    facts_today = _core.nervous_today_path(_core.NERVOUS_FACTS_ROOT)
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_baseline_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": (
            bool(status_data.get("ok"))
            and bool(validate_data.get("ok"))
            and bool(events_validate_data.get("ok"))
            and bool(episodes_validate_data.get("ok"))
            and bool(synthesis_validate_data.get("ok"))
            and bool(eval_validate_data.get("ok"))
            and bool(retention_validate_data.get("ok"))
            and bool(timer.get("is_active"))
            and bool(browser_content_timer.get("is_active"))
            and bool(index_validate_data.get("ok"))
            and bool(index_timer.get("is_active"))
        ),
        "status": {
            "ok": status_data.get("ok"),
            "phase": status_data.get("phase"),
            "warnings": status_data.get("warnings", []),
        },
        "validate": {
            "ok": validate_data.get("ok"),
            "summary": validate_data.get("summary"),
        },
        "events": {
            "latest_path": str(_core.NERVOUS_EVENTS_LATEST_PATH),
            "latest_exists": _core.NERVOUS_EVENTS_LATEST_PATH.exists(),
            "today_path": str(_core.nervous_today_path(_core.NERVOUS_EVENTS_ROOT)),
            "today_lines": _core.count_file_lines(_core.nervous_today_path(_core.NERVOUS_EVENTS_ROOT)),
            "validate": {
                "ok": events_validate_data.get("ok"),
                "summary": events_validate_data.get("summary"),
            },
        },
        "episodes": {
            "latest_path": str(_core.NERVOUS_EPISODES_LATEST_PATH),
            "latest_exists": _core.NERVOUS_EPISODES_LATEST_PATH.exists(),
            "today_path": str(_core.nervous_today_path(_core.NERVOUS_EPISODES_ROOT)),
            "today_lines": _core.count_file_lines(_core.nervous_today_path(_core.NERVOUS_EPISODES_ROOT)),
            "validate": {
                "ok": episodes_validate_data.get("ok"),
                "summary": episodes_validate_data.get("summary"),
            },
        },
        "synthesis": {
            "latest_path": str(_core.NERVOUS_SYNTHESIS_LATEST_PATH),
            "latest_exists": _core.NERVOUS_SYNTHESIS_LATEST_PATH.exists(),
            "daily_root": str(_core.NERVOUS_SYNTHESIS_DAILY_ROOT),
            "validate": {
                "ok": synthesis_validate_data.get("ok"),
                "summary": synthesis_validate_data.get("summary"),
            },
        },
        "evals": {
            "latest_path": str(_core.NERVOUS_EVALS_LATEST_PATH),
            "latest_exists": _core.NERVOUS_EVALS_LATEST_PATH.exists(),
            "today_path": str(_core.nervous_today_path(_core.NERVOUS_EVALS_ROOT)),
            "today_lines": _core.count_file_lines(_core.nervous_today_path(_core.NERVOUS_EVALS_ROOT)),
            "validate": {
                "ok": eval_validate_data.get("ok"),
                "summary": eval_validate_data.get("summary"),
            },
        },
        "retention": {
            "latest_path": str(_core.NERVOUS_RETENTION_LATEST_PATH),
            "latest_exists": _core.NERVOUS_RETENTION_LATEST_PATH.exists(),
            "today_path": str(_core.nervous_today_path(_core.NERVOUS_RETENTION_ROOT)),
            "today_lines": _core.count_file_lines(_core.nervous_today_path(_core.NERVOUS_RETENTION_ROOT)),
            "validate": {
                "ok": retention_validate_data.get("ok"),
                "summary": retention_validate_data.get("summary"),
            },
        },
        "timer": timer,
        "service": service,
        "browser_content_capture": {
            "timer": browser_content_timer,
            "service": browser_content_service,
            "latest": str(_core.NERVOUS_BROWSER_CONTENT_LATEST_PATH),
            "raw_storage_root": str(_core.NERVOUS_BROWSER_CONTENT_ROOT),
            "idle_behavior": "timer tick exits cleanly without capture while supported browsers are closed",
        },
        "index": {
            "status": {
                "ok": index_status_data.get("ok"),
                "ready": index_status_data.get("ready"),
                "warnings": index_status_data.get("warnings", []),
            },
            "validate": {
                "ok": index_validate_data.get("ok"),
                "summary": index_validate_data.get("summary"),
                "error": index_validate_data.get("error"),
            },
            "timer": index_timer,
            "service": index_service,
        },
        "facts": {
            "latest_path": str(_core.NERVOUS_FACTS_LATEST_PATH),
            "latest_exists": _core.NERVOUS_FACTS_LATEST_PATH.exists(),
            "latest_error": latest_error,
            "latest_schema": facts_latest.get("schema") if isinstance(facts_latest, dict) else None,
            "latest_generated_at": facts_latest.get("generated_at") if isinstance(facts_latest, dict) else None,
            "today_path": str(facts_today),
            "today_lines": _core.count_file_lines(facts_today),
        },
        "storage": {
            "nervous_dir": str(_core.NERVOUS_ROOT),
            "nervous_dir_size_bytes": _core.du_size_bytes(_core.NERVOUS_ROOT) if _core.NERVOUS_ROOT.exists() else 0,
            "search_index_db": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
            "search_index_db_size_bytes": _core.NERVOUS_SEARCH_INDEX_DB_PATH.stat().st_size if _core.NERVOUS_SEARCH_INDEX_DB_PATH.exists() else 0,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.NERVOUS_CHECKS_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.nervous_today_path(_core.NERVOUS_CHECKS_ROOT), data, 0o664)
        errors = [error for error in (latest_error, daily_error) if error]
        if errors:
            data["write_errors"] = errors
            data["ok"] = False
    return data


def nervous_quality_audit(
    refresh: bool = False,
    refresh_index: bool = False,
    write_latest: bool = True,
    deep_index_validate: bool = True,
) -> dict[str, Any]:
    return nervous_quality_adapters.run_quality_audit(
        refresh=refresh,
        refresh_index=refresh_index,
        write_latest_enabled=write_latest,
        deep_index_validate=deep_index_validate,
        search_index_db_path=_core.NERVOUS_SEARCH_INDEX_DB_PATH,
        browser_content_latest_path=_core.NERVOUS_BROWSER_CONTENT_LATEST_PATH,
        privacy_state_path=_core.NERVOUS_PRIVACY_STATE_PATH,
        quality_latest_path=_core.NERVOUS_QUALITY_LATEST_PATH,
        quality_root=_core.NERVOUS_QUALITY_ROOT,
        semantic_maintain_latest_path=_core.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH,
        passive_chronicle_timer=_core.NERVOUS_PASSIVE_CHRONICLE_TIMER,
        browser_content_capture_timer=_core.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER,
        search_index_timer=_core.NERVOUS_SEARCH_INDEX_TIMER,
        semantic_maintain_timer=_core.NERVOUS_SEMANTIC_MAINTAIN_TIMER,
        semantic_maintain_service=_core.NERVOUS_SEMANTIC_MAINTAIN_SERVICE,
        commands={
            "audit": "abyss-machine nervous quality-audit --json",
            "refresh": "abyss-machine nervous quality-audit --refresh --json",
            "refresh_index": "abyss-machine nervous quality-audit --refresh --refresh-index --json",
            "validate": "abyss-machine nervous validate --json",
        },
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        index_build=nervous_index_build,
        events_build=nervous_events_build,
        episodes_build=nervous_episodes_build,
        synthesis_build=nervous_synthesis_build,
        eval_run=nervous_eval_run,
        status=nervous_status,
        capture_status=_core.nervous_capture_status,
        derived_refresh_status=nervous_derived_refresh_status,
        privacy_status=_core.nervous_privacy_status,
        effective_sources=_core.nervous_effective_sources,
        facts_validate=_core.nervous_validate_snapshot,
        events_validate=nervous_events_validate,
        episodes_validate=nervous_episodes_validate,
        synthesis_validate=nervous_synthesis_validate,
        eval_validate=nervous_eval_validate,
        retention_validate=nervous_retention_validate,
        index_status=nervous_index_status,
        index_validate=nervous_index_validate,
        bounded_index_validate_from_status=nervous_index_bounded_validate_from_status,
        latest_reader=_core.load_json_document,
        redaction_smoke=_core.nervous_redact_text,
        systemd_unit=_core.user_systemd_unit,
        latest_writer=_core.safe_atomic_write_json,
        jsonl_append=_core.safe_append_jsonl,
        today_path=_core.nervous_today_path,
    )


def nervous_status(write_latest: bool = True) -> dict[str, Any]:
    paths = _core.nervous_paths()
    policy = _core.nervous_policy(write_latest=write_latest)
    sources = _core.nervous_effective_sources(write_latest=write_latest)
    privacy = _core.nervous_effective_privacy(write_latest=write_latest)
    data = nervous_status_adapters.status_document_from_ports(
        paths=paths,
        policy=policy,
        sources=sources,
        privacy=privacy,
        status_paths={
            "design": _core.NERVOUS_DESIGN_PATH,
            "agents": _core.NERVOUS_AGENTS_PATH,
            "policy_config": _core.NERVOUS_POLICY_CONFIG_PATH,
            "sources_config": _core.NERVOUS_SOURCES_CONFIG_PATH,
            "privacy_config": _core.NERVOUS_PRIVACY_CONFIG_PATH,
            "sources_state": _core.NERVOUS_SOURCES_STATE_PATH,
            "privacy_state": _core.NERVOUS_PRIVACY_STATE_PATH,
            "facts_latest": _core.NERVOUS_FACTS_LATEST_PATH,
            "events_latest": _core.NERVOUS_EVENTS_LATEST_PATH,
            "episodes_latest": _core.NERVOUS_EPISODES_LATEST_PATH,
            "retrieval_latest": _core.NERVOUS_RETRIEVAL_LATEST_PATH,
            "synthesis_latest": _core.NERVOUS_SYNTHESIS_LATEST_PATH,
            "evals_latest": _core.NERVOUS_EVALS_LATEST_PATH,
            "retention_latest": _core.NERVOUS_RETENTION_LATEST_PATH,
            "capture_latest": _core.NERVOUS_CAPTURE_LATEST_PATH,
            "private_capture_root": _core.NERVOUS_PRIVATE_CAPTURE_ROOT,
            "screenshot_root": _core.NERVOUS_SCREENSHOT_ROOT,
            "browser_content_latest": _core.NERVOUS_BROWSER_CONTENT_LATEST_PATH,
            "browser_content_root": _core.NERVOUS_BROWSER_CONTENT_ROOT,
            "search_index_db": _core.NERVOUS_SEARCH_INDEX_DB_PATH,
            "search_index_latest": _core.NERVOUS_SEARCH_INDEX_LATEST_PATH,
            "storage_latest": _core.STORAGE_LATEST_PATH,
            "observability_latest": _core.OBSERVABILITY_ROOT / "thermal-battery" / "latest.json",
            "ai_capabilities_latest": _core.AI_CAPABILITIES_LATEST_PATH,
        },
        unit_names={
            "daemon_service": "abyss-nervous.service",
            "daemon_timer": "abyss-nervous.timer",
            "passive_chronicle_service": _core.NERVOUS_PASSIVE_CHRONICLE_SERVICE,
            "passive_chronicle_timer": _core.NERVOUS_PASSIVE_CHRONICLE_TIMER,
            "browser_content_capture_service": _core.NERVOUS_BROWSER_CONTENT_CAPTURE_SERVICE,
            "browser_content_capture_timer": _core.NERVOUS_BROWSER_CONTENT_CAPTURE_TIMER,
            "search_index_service": _core.NERVOUS_SEARCH_INDEX_SERVICE,
            "search_index_timer": _core.NERVOUS_SEARCH_INDEX_TIMER,
        },
        index_counts=nervous_index_db_counts,
        latest_reader=_core.load_json_document,
        path_exists=lambda path: path.exists(),
        line_counter=_core.count_file_lines,
        systemd_unit=_core.user_systemd_unit,
        process_latest=_core.process_latest_summary,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
    )
    if write_latest:
        data = nervous_status_adapters.write_status_outputs(
            data,
            latest_path=_core.NERVOUS_LATEST_PATH,
            index_path=_core.NERVOUS_INDEX_PATH,
            index_document=nervous_index_document,
            writer=_core.safe_atomic_write_json,
        )
    return data


def nervous_index_document(status_data: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = _core.nervous_paths()
    schema = status_data.get("schema") if isinstance(status_data, dict) else None
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_index_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "status": "stage-8-retrieval-synthesis-eval-retention",
        "design": str(_core.NERVOUS_DESIGN_PATH),
        "agent_entrypoint": str(_core.NERVOUS_AGENTS_PATH),
        "paths": paths,
        "latest_status": {
            "path": str(_core.NERVOUS_LATEST_PATH),
            "generated_at": status_data.get("generated_at") if schema == f"{_core.SCHEMA_PREFIX}_nervous_status_v1" else None,
            "ok": status_data.get("ok") if schema == f"{_core.SCHEMA_PREFIX}_nervous_status_v1" else None,
            "phase": status_data.get("phase") if schema == f"{_core.SCHEMA_PREFIX}_nervous_status_v1" else None,
        },
        "latest_facts": {
            "path": str(_core.NERVOUS_FACTS_LATEST_PATH),
            "generated_at": status_data.get("generated_at") if schema == f"{_core.SCHEMA_PREFIX}_nervous_fact_snapshot_v1" else None,
            "ok": status_data.get("ok") if schema == f"{_core.SCHEMA_PREFIX}_nervous_fact_snapshot_v1" else None,
            "phase": status_data.get("phase") if schema == f"{_core.SCHEMA_PREFIX}_nervous_fact_snapshot_v1" else None,
            "summary": status_data.get("summary") if schema == f"{_core.SCHEMA_PREFIX}_nervous_fact_snapshot_v1" else None,
        },
        "latest_capture": {
            "path": str(_core.NERVOUS_CAPTURE_LATEST_PATH),
            "private_root": str(_core.NERVOUS_PRIVATE_CAPTURE_ROOT),
            "commands": [
                "abyss-machine nervous capture-status --json",
                "abyss-machine nervous source-disable SOURCE --reason TEXT --json",
            ],
        },
        "latest_events": {
            "path": str(_core.NERVOUS_EVENTS_LATEST_PATH),
            "commands": [
                "abyss-machine nervous events-build --json",
                "abyss-machine nervous events-latest --json",
                "abyss-machine nervous events-validate --json",
            ],
        },
        "latest_episodes": {
            "path": str(_core.NERVOUS_EPISODES_LATEST_PATH),
            "commands": [
                "abyss-machine nervous episodes-build --json",
                "abyss-machine nervous episodes-latest --json",
                "abyss-machine nervous episodes-validate --json",
            ],
        },
        "search_index": {
            "config": str(_core.NERVOUS_INDEX_CONFIG_PATH),
            "db": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
            "latest": str(_core.NERVOUS_SEARCH_INDEX_LATEST_PATH),
            "schema": str(_core.NERVOUS_SEARCH_INDEX_SCHEMA_PATH),
            "commands": [
                "abyss-machine nervous index-status --json",
                "abyss-machine nervous index-build --json",
                "abyss-machine nervous index-validate --json",
                "abyss-machine nervous search --query TEXT --json",
                "abyss-machine nervous search --query TEXT --source nervous_events --json",
                "abyss-machine nervous search --query TEXT --schema abyss_machine_nervous_episode_v1 --json",
                "abyss-machine nervous index-vacuum --json",
            ],
        },
        "semantic_index": {
            "config": str(_core.NERVOUS_INDEX_CONFIG_PATH),
            "db": str(_core.NERVOUS_SEMANTIC_INDEX_DB_PATH),
            "latest": str(_core.NERVOUS_SEMANTIC_INDEX_LATEST_PATH),
            "eval_latest": str(_core.NERVOUS_SEMANTIC_EVAL_LATEST_PATH),
            "source_index_db": str(_core.NERVOUS_SEARCH_INDEX_DB_PATH),
            "automation": "on-demand-only",
            "commands": [
                "abyss-machine nervous semantic-status --json",
                "abyss-machine nervous semantic-build --json",
                "abyss-machine nervous semantic-search --query TEXT --json",
                "abyss-machine nervous semantic-eval --json",
            ],
        },
        "retrieval": {
            "latest": str(_core.NERVOUS_RETRIEVAL_LATEST_PATH),
            "rerank_latest": str(_core.NERVOUS_RERANK_LATEST_PATH),
            "daily_glob": str(_core.NERVOUS_RETRIEVAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "rerank_daily_glob": str(_core.NERVOUS_RERANK_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "commands": [
                "abyss-machine nervous rerank --query TEXT --json",
                "abyss-machine nervous recall --query TEXT --json",
                "abyss-machine nervous recall --mode hybrid --query TEXT --json",
                "abyss-machine nervous recall --query TEXT --source nervous_events --json",
                "abyss-machine nervous recall --query TEXT --schema abyss_machine_nervous_episode_v1 --json",
            ],
        },
        "brief": {
            "latest": str(_core.NERVOUS_BRIEF_LATEST_PATH),
            "daily_glob": str(_core.NERVOUS_BRIEF_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "commands": [
                "abyss-machine nervous brief --scope now --json",
                "abyss-machine nervous brief --scope today --json",
            ],
        },
        "synthesis": {
            "latest": str(_core.NERVOUS_SYNTHESIS_LATEST_PATH),
            "validate_latest": str(_core.NERVOUS_SYNTHESIS_VALIDATE_LATEST_PATH),
            "hourly_glob": str(_core.NERVOUS_SYNTHESIS_HOURLY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "daily_jsonl_glob": str(_core.NERVOUS_SYNTHESIS_DAILY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "daily_markdown_glob": str(_core.NERVOUS_SYNTHESIS_DAILY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.md"),
            "commands": [
                "abyss-machine nervous synthesis-build --scope daily --json",
                "abyss-machine nervous synthesis-latest --json",
                "abyss-machine nervous synthesis-validate --json",
            ],
        },
        "evals": {
            "latest": str(_core.NERVOUS_EVALS_LATEST_PATH),
            "validate_latest": str(_core.NERVOUS_EVALS_VALIDATE_LATEST_PATH),
            "daily_glob": str(_core.NERVOUS_EVALS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "commands": [
                "abyss-machine nervous eval-run --json",
                "abyss-machine nervous eval-latest --json",
                "abyss-machine nervous eval-validate --json",
            ],
        },
        "retention": {
            "latest": str(_core.NERVOUS_RETENTION_LATEST_PATH),
            "validate_latest": str(_core.NERVOUS_RETENTION_VALIDATE_LATEST_PATH),
            "daily_glob": str(_core.NERVOUS_RETENTION_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
            "commands": [
                "abyss-machine nervous retention-plan --json",
                "abyss-machine nervous retention-apply --dry-run --json",
                "abyss-machine nervous retention-validate --json",
            ],
        },
        "rules": [
            "No watcher daemon is installed yet.",
            "Events and episodes are deterministic derived records from passive fact snapshots.",
            "Retrieval packs and synthesis candidates cite existing indexed evidence; they do not become facts by themselves.",
            "Retention apply defaults to dry-run and does not delete fact records; use explicit forget for fact deletion.",
            "Enabled local-private connectors must keep raw_private_content=false and route raw artifacts only under /srv/abyss-machine/storage/nervous/captures.",
            "Browser capture reads recent local history metadata plus supported browser document text through AT-SPI during normal browsing; terminal capture does not attach to existing stdout/stderr streams.",
            "Do not write to abyss-stack or sibling AoA repositories from this host layer.",
            "Treat AoA repositories as source material under reformation until owner contracts stabilize.",
            "Local index reads passive facts plus derived events/episodes and stores SQLite/FTS data under /srv/abyss-machine/storage.",
        ],
    }


def nervous_semantic_resource_gate_evidence(
    *,
    nervous_brief: dict[str, Any],
    readiness: dict[str, Any],
    semantic_maintain: dict[str, Any],
    game_guard: dict[str, Any],
) -> dict[str, Any]:
    assessment = semantic_maintain.get("assessment") if isinstance(semantic_maintain.get("assessment"), dict) else {}
    index_refresh = semantic_maintain.get("index_refresh") if isinstance(semantic_maintain.get("index_refresh"), dict) else {}
    launch = index_refresh.get("launch") if isinstance(index_refresh.get("launch"), dict) else {}
    plan = launch.get("plan") if isinstance(launch.get("plan"), dict) else {}
    launch_blocked = launch.get("blocked_reasons") if isinstance(launch.get("blocked_reasons"), list) else []
    plan_blocked = plan.get("blocked_reasons") if isinstance(plan.get("blocked_reasons"), list) else []
    blocked_reasons = sorted({str(item) for item in [*launch_blocked, *plan_blocked] if item})
    denied_reasons = sorted({
        str(item)
        for item in [
            *(launch.get("denied_reasons") if isinstance(launch.get("denied_reasons"), list) else []),
            *(plan.get("denied_reasons") if isinstance(plan.get("denied_reasons"), list) else []),
        ]
        if item
    })
    launch_request = launch.get("request") if isinstance(launch.get("request"), dict) else {}
    game_active = bool(
        game_guard.get("active")
        or _core.nested_get(plan, ["inputs", "game_guard", "active"])
        or "game_guard_active" in blocked_reasons
        or "game_guard_unattended_medium_or_heavier" in blocked_reasons
    )
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_nervous_semantic_resource_gate_v1",
        "generated_at": _core.now_iso(),
        "status": "blocked" if blocked_reasons or denied_reasons else ("ready" if semantic_maintain.get("ok") else "unknown"),
        "decision": semantic_maintain.get("decision"),
        "dry_run": bool(semantic_maintain.get("dry_run")),
        "resource_plan_decision": plan.get("decision"),
        "resource_launch_ok": launch.get("ok"),
        "blocked_reasons": blocked_reasons,
        "denied_reasons": denied_reasons,
        "semantic": {
            "maintenance_needed": bool(readiness.get("semantic_maintenance_needed") or assessment.get("needed")),
            "semantic_stale": bool(readiness.get("semantic_stale") or assessment.get("stale")),
            "reasons": assessment.get("reasons") if isinstance(assessment.get("reasons"), list) else [],
            "source_chunks": assessment.get("source_chunks"),
            "vectors": assessment.get("vectors"),
            "delta_chunks": assessment.get("delta_chunks"),
            "min_delta_chunks": assessment.get("min_delta_chunks"),
            "semantic_age_minutes": assessment.get("semantic_age_minutes"),
            "source_index_changed": assessment.get("source_index_changed"),
        },
        "source_index": {
            "refresh_needed": _core.nested_get(index_refresh, ["assessment", "needed"]),
            "decision": _core.nested_get(index_refresh, ["launch", "plan", "decision"]),
            "records_lag": _core.nested_get(index_refresh, ["assessment", "records_lag"]) or _core.nested_get(index_refresh, ["before", "freshness", "records_lag"]),
            "stale": _core.nested_get(index_refresh, ["assessment", "stale"]) or _core.nested_get(index_refresh, ["before", "freshness", "stale"]),
            "command": index_refresh.get("command"),
        },
        "resource_request": {
            "class": launch_request.get("class"),
            "kind": launch_request.get("kind"),
            "unattended": launch_request.get("unattended"),
            "timeout_sec": launch_request.get("timeout_sec"),
            "command": launch_request.get("command"),
        },
        "game_guard": {
            "active": game_active,
            "path": str(_core.PROCESS_GAME_GUARD_LATEST_PATH),
            "generated_at": game_guard.get("generated_at"),
            "summary": game_guard.get("summary") if isinstance(game_guard.get("summary"), dict) else None,
        },
        "safe_next_action": {
            "kind": "resource_gated_nervous_semantic_maintenance_review",
            "owner_route": "abyss-machine",
            "review_command": _core.NERVOUS_SEMANTIC_MAINTAIN_REVIEW_COMMAND,
            "retry_command": _core.NERVOUS_SEMANTIC_MAINTAIN_RETRY_COMMAND,
            "condition": "retry only when resource gate allows it or after explicit operator review; do not bypass active game guard automatically",
            "requires_operator": True,
            "automatic": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
        },
        "evidence_refs": [
            {"path": str(_core.NERVOUS_BRIEF_LATEST_PATH), "schema": nervous_brief.get("schema"), "readiness": readiness},
            {"path": str(_core.NERVOUS_SEMANTIC_MAINTAIN_LATEST_PATH), "schema": semantic_maintain.get("schema"), "decision": semantic_maintain.get("decision")},
            {"path": str(_core.RESOURCE_RUN_LATEST_PATH), "schema": f"{_core.SCHEMA_PREFIX}_resource_launch_v1", "blocked_reasons": blocked_reasons},
            {"path": str(_core.PROCESS_GAME_GUARD_LATEST_PATH), "schema": game_guard.get("schema"), "active": game_active},
        ],
        "policy": {
            "read_model": True,
            "resource_gated": True,
            "does_not_bypass_resource_gate": True,
            "automatic_execution": False,
            "executes_commands": False,
            "host_layer_mutates_stack": False,
            "repo_mutation": False,
        },
    }


def nervous_resource_gate_complete(item: dict[str, Any]) -> bool:
    gate = item.get("resource_gate") if isinstance(item.get("resource_gate"), dict) else {}
    policy = gate.get("policy") if isinstance(gate.get("policy"), dict) else {}
    safe_next = gate.get("safe_next_action") if isinstance(gate.get("safe_next_action"), dict) else {}
    evidence_refs = gate.get("evidence_refs") if isinstance(gate.get("evidence_refs"), list) else []
    return (
        bool(gate)
        and policy.get("does_not_bypass_resource_gate") is True
        and policy.get("automatic_execution") is False
        and policy.get("executes_commands") is False
        and policy.get("host_layer_mutates_stack") is False
        and safe_next.get("executes_commands") is False
        and safe_next.get("host_layer_mutates_stack") is False
        and safe_next.get("automatic") is False
        and bool(safe_next.get("review_command"))
        and bool(evidence_refs)
    )


def nervous_retention_privacy_route(retention_plan: dict[str, Any]) -> dict[str, Any]:
    route_errors = retention_plan.get("route_errors") if isinstance(retention_plan.get("route_errors"), list) else []
    return nervous_retention_contracts.privacy_route(
        retention_plan,
        schema_prefix=_core.SCHEMA_PREFIX,
        retention_latest_path=str(_core.NERVOUS_RETENTION_LATEST_PATH),
        retention_validate_latest_path=str(_core.NERVOUS_RETENTION_VALIDATE_LATEST_PATH),
        privacy_config_path=str(_core.NERVOUS_PRIVACY_CONFIG_PATH),
        privacy_state_path=str(_core.NERVOUS_PRIVACY_STATE_PATH),
        route_errors_shape=_core.self_awareness_bounded_json_shape(route_errors, max_depth=2, max_items=8),
    )


def nervous_retention_privacy_route_complete(route: Any) -> bool:
    return nervous_retention_contracts.privacy_route_complete(route, schema_prefix=_core.SCHEMA_PREFIX)


def print_nervous_status_text(data: dict[str, Any]) -> None:
    print(f"nervous: ok={data.get('ok')} phase={data.get('phase')}")
    print(f"policy: {data.get('policy', {}).get('mode')} daemon={data.get('policy', {}).get('active_daemon')}")
    print(f"sources: {','.join(data.get('sources', {}).get('enabled_safe_sources', [])) or 'none'}")
    print(f"privacy: {data.get('privacy', {}).get('mode')} pause={data.get('privacy', {}).get('global_pause')}")
    passive = data.get("passive_chronicle", {})
    if passive:
        timer = passive.get("timer", {})
        print(f"passive chronicle timer: {timer.get('active')}/{timer.get('enabled')}")
    local_index = data.get("local_index", {})
    if local_index:
        timer = local_index.get("timer", {})
        print(f"local index: db={local_index.get('db_exists')} chunks={local_index.get('chunks')} timer={timer.get('active')}/{timer.get('enabled')}")
    warnings = data.get("warnings", [])
    if warnings:
        print(f"warnings: {'; '.join(warnings)}")
