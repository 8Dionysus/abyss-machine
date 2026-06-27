from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.typing_capture_contracts import (
    ai_counterpart_context_anchor,
    ai_counterpart_recipient,
    atspi_paths_match,
    browser_content_record_url,
    browser_context_from_recent_captures,
    browser_context_max_age_sec,
    browser_context_safe_candidate,
    browser_ai_counterpart_identity,
    browser_ai_transcript_clean_text,
    browser_ai_transcript_message_metadata,
    browser_ai_transcript_normalize_role,
    browser_extension_message_metadata,
    browser_extension_policy,
    browser_privacy_record_summary,
    browser_title_fingerprint,
    browser_url_scheme_allowed,
    capture_gate_decision_document,
    causal_browser_metadata_context,
    causal_extract_context_value,
    causal_interaction_identity,
    causal_recipient,
    causal_surface_kind,
    context_anchor_from_parts,
    codex_prompt_event_summary,
    codex_prompt_submit_coverage,
    codex_prompt_submit_route_assessment,
    codex_prompt_time,
    codex_recent_prompt_summary,
    codex_record_is_selftest,
    codex_session_tail_latest_status_document,
    codex_session_tail_recent_prompt_summary,
    focused_browser_candidate_summary,
    focused_browser_event_summary,
    saved_text_file_allowed,
    saved_text_low_signal_artifact,
    saved_text_path_denied,
    saved_text_path_excluded,
    typing_atspi_text_events_policy,
    typing_causal_awareness_for_event,
    typing_causal_awareness_readmodel_status,
    typing_causal_project_binding_summary,
    typing_causal_project_for_path,
    typing_causal_project_for_paths,
    typing_causal_resolve_project,
    typing_causal_topic_project_for_text,
    typing_process_readmodel_status,
    typing_recent_records_shape_status,
    typing_saved_text_recent_records_status,
    typing_saved_text_scan_policy_status,
    typing_status_document,
    typing_validate_document,
    typing_browser_ai_transcript_selftest_status,
    typing_browser_ai_transcript_selftest_validation_status,
    typing_browser_atspi_selftest_validation_status,
    typing_atspi_compact_history_contract_document,
    typing_atspi_text_events_compact_history_record,
    typing_browser_context_fallback_status,
    typing_atspi_text_events_heartbeat_status,
    typing_browser_input_proof_summary,
    typing_browser_input_recency_status,
    typing_browser_input_recency_validation_status,
    typing_browser_privacy_selftest_validation_status,
    typing_browser_webextension_selftest_validation_status,
    typing_focused_browser_selftest_validation_status,
    typing_generic_gui_selftest_validation_status,
    typing_causal_controlled_probe_project,
    typing_causal_context_readmodel_from_records,
    typing_age_seconds,
    typing_browser_input_recency,
    typing_browser_like_record,
    typing_controlled_probe_record,
    typing_coverage_document_from_records,
    typing_end_to_end_document,
    typing_latest_record,
    typing_parse_iso,
    typing_process_entry_index,
    typing_process_context_anchor,
    typing_process_continuity_projects,
    typing_process_from_records,
    typing_process_generated_epoch,
    typing_process_interaction_for_record,
    typing_process_interaction_key,
    typing_process_interaction_keys,
    typing_process_lane_id,
    typing_process_project_for_record,
    typing_process_recipient_for_context,
    typing_recent_record_brief,
    typing_record_context_text,
    typing_record_url_origin,
    typing_process_unique_records,
    saved_text_policy,
    typing_coverage_route_notes_and_gaps,
    typing_coverage_status_decision,
    url_origin_path,
    url_path_hash,
)


def _capture_gate_defaults() -> dict:
    return {
        "deny_context_tokens": ["password", "private"],
        "capture_gate": {
            "enabled": True,
            "default_decision": "metadata_only",
            "unknown_decision": "metadata_only",
            "hard_skip_app_tokens": ["telegram"],
            "hard_skip_url_tokens": ["web.whatsapp"],
            "metadata_only_url_tokens": ["login", "checkout", "token"],
            "metadata_only_app_tokens": ["password manager"],
            "allow_text_source_adapters": [
                "manual_cli_stdin",
                "saved_text_snapshot",
                "browser_extension_explicit",
                "browser_ai_transcript",
                "atspi_text_changed_event",
                "atspi_focused_text_snapshot",
                "editor_extension_explicit",
            ],
            "allow_text_path_roots": ["/work"],
            "focused_allow_app_tokens": ["trusted-editor"],
            "offline_agent": {
                "id": "typing_capture_gate_agent",
                "kind": "local_rule_engine",
                "may_promote_safe_generic_text_role": True,
            },
        },
        "browser_extension": {
            "allowed_url_schemes": ["http:", "https:"],
            "allowed_event_kinds": ["committed_text"],
        },
        "browser_ai_transcript": {
            "allowed_url_schemes": ["https:"],
            "allowed_event_kinds": ["visible_message"],
            "allowed_message_roles": ["assistant", "user"],
        },
        "saved_text_scan": {
            "roots": ["/work"],
            "deny_path_tokens": ["secret"],
            "exclude_path_tokens": ["/.git/"],
        },
        "focused_snapshot": {
            "safe_text_routes": ["browser_safe_url", "generic_editable_text"],
            "generic_editable_text": {
                "enabled": True,
                "requires_editable": True,
                "requires_focused": True,
            },
            "text_roles": ["entry", "text"],
            "sensitive_roles": ["password"],
        },
        "atspi_text_events": {
            "text_roles": ["entry", "text"],
            "sensitive_roles": ["password"],
            "generic_editable_text": {
                "enabled": True,
                "requires_editable": True,
                "requires_focus_or_visible": True,
            },
        },
    }


def _capture_gate_document(**kwargs: object) -> dict:
    defaults = _capture_gate_defaults()
    params = {
        "source": "manual_cli_stdin",
        "policy": {},
        "default_policy": defaults,
        "schema_prefix": "abyss_machine",
        "version": "test",
        "generated_at": "2026-06-26T00:00:00Z",
    }
    params.update(kwargs)
    return capture_gate_decision_document(**params)


def _browser_capture_item(
    *,
    url: str = "https://example.test/project",
    title: str = "Abyss project context",
    captured_at: str = "2026-06-26T00:00:00+00:00",
    path: str = "0.1.2",
    classification: str = "usable",
    web_class: str = "project",
    skipped_text: bool = False,
    focused: bool = True,
    context_id: str = "ctx-fixture",
) -> dict:
    return {
        "generated_at": captured_at,
        "context": context_id,
        "atspi": {"path": path, "focused": focused, "showing": focused},
        "record": {
            "captured_at": captured_at,
            "context_id": context_id,
            "title": title,
            "content_type": "text/html",
            "skipped_text": skipped_text,
            "url": {
                "url": url,
                "query_present": "?" in url,
                "fragment_present": "#" in url,
                "raw_omitted": True,
            },
            "content_quality": {"classification": classification, "score": 0.9},
            "web_context_quality": {
                "class": web_class,
                "attention": {"focused": focused, "showing": focused, "priority": "focused" if focused else "unknown"},
                "sensitive_skip_preserved": skipped_text,
            },
            "page_identity": {"is_ai": False},
        },
    }


def test_browser_and_saved_text_policies_are_module_owned_contracts() -> None:
    defaults = {
        "browser_extension": {
            "allowed_url_schemes": ["http:", "https:"],
            "privacy": {"capture_gate_required": True, "cookies_captured": False},
        },
        "browser_ai_transcript": {
            "allowed_url_schemes": ["https:"],
            "privacy": {"capture_gate_required": True},
        },
        "saved_text_scan": {
            "include_extensions": [".md"],
            "deny_path_tokens": ["secret"],
            "exclude_path_tokens": ["/.git/"],
            "low_signal_artifact_path_tokens": ["node_modules"],
        },
    }
    policy = {
        "browser_extension": {"privacy": {"field_values_captured": False}},
        "saved_text_scan": {"include_names": ["AGENTS.md"], "include_extensions": [".txt"]},
    }

    browser_policy = browser_extension_policy(policy, defaults)
    transcript_policy = browser_extension_policy({"browser_extension": {"allowed_url_schemes": ["https:"]}}, defaults)
    saved_policy = saved_text_policy(policy, defaults)

    assert browser_policy["privacy"] == {
        "capture_gate_required": True,
        "cookies_captured": False,
        "field_values_captured": False,
    }
    assert browser_url_scheme_allowed("https://example.test", transcript_policy) is True
    assert browser_url_scheme_allowed("file:///tmp/private.txt", transcript_policy) is False
    assert saved_text_file_allowed(Path("notes.txt"), saved_policy) is True
    assert saved_text_file_allowed(Path("AGENTS.md"), saved_policy) is True
    assert saved_text_path_denied(Path("/home/me/secrets/token.txt"), saved_policy) == [
        {"kind": "deny_path_token", "token": "secret"}
    ]
    assert saved_text_path_excluded(Path("/repo/.git/config"), saved_policy) == [
        {"kind": "exclude_path_token", "token": "/.git/"}
    ]
    assert saved_text_low_signal_artifact(Path("/repo/node_modules/pkg/index.js"), saved_policy) == [
        {"kind": "low_signal_artifact_path_token", "token": "node_modules"}
    ]


def test_typing_saved_text_scan_policy_status_accepts_enabled_adapter_size_and_deny_list() -> None:
    status = typing_saved_text_scan_policy_status(
        allowed_adapters=["manual_cli_stdin", "saved_text_snapshot"],
        saved_policy={"enabled": True, "max_file_bytes": 262144, "deny_path_tokens": ["secret"]},
    )

    assert status["ok"] is True
    assert all(status["checks"].values())


def test_typing_saved_text_scan_policy_status_rejects_missing_or_disabled_contract_parts() -> None:
    cases = [
        (
            "missing_adapter",
            {"allowed_adapters": ["manual_cli_stdin"], "saved_policy": {"max_file_bytes": 1, "deny_path_tokens": ["secret"]}},
            "saved_text_adapter_allowed",
        ),
        (
            "disabled",
            {
                "allowed_adapters": ["saved_text_snapshot"],
                "saved_policy": {"enabled": False, "max_file_bytes": 1, "deny_path_tokens": ["secret"]},
            },
            "policy_enabled",
        ),
        (
            "zero_size",
            {
                "allowed_adapters": ["saved_text_snapshot"],
                "saved_policy": {"enabled": True, "max_file_bytes": 0, "deny_path_tokens": ["secret"]},
            },
            "max_file_bytes_positive",
        ),
        (
            "missing_deny_list",
            {
                "allowed_adapters": ["saved_text_snapshot"],
                "saved_policy": {"enabled": True, "max_file_bytes": 1, "deny_path_tokens": []},
            },
            "deny_path_tokens_present",
        ),
        (
            "missing_policy",
            {"allowed_adapters": ["saved_text_snapshot"], "saved_policy": None},
            "max_file_bytes_positive",
        ),
    ]

    for label, kwargs, failed_check in cases:
        status = typing_saved_text_scan_policy_status(**kwargs)
        assert status["ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_saved_text_scan_policy_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "allowed_adapters": ["saved_text_snapshot"],
        "saved_policy": {"max_file_bytes": 262144, "deny_path_tokens": ["secret"]},
    }

    assert cli.typing_saved_text_scan_policy_status(**kwargs) == typing_saved_text_scan_policy_status(**kwargs)


def test_typing_saved_text_recent_records_status_accepts_policy_safe_surface_matches() -> None:
    records = [
        {
            "event_id": "saved-1",
            "source_adapter": "saved_text_snapshot",
            "metadata": {"file": {"path": "/work/notes/plan.md"}},
            "causal_context": {
                "task": {
                    "active_changes": [
                        {"path": "/work/notes/plan.md", "match": "surface_match"},
                    ]
                }
            },
        },
        {"event_id": "manual-1", "source_adapter": "manual_cli_stdin"},
    ]

    status = typing_saved_text_recent_records_status(
        records=records,
        saved_policy={"deny_path_tokens": ["secret"], "exclude_path_tokens": ["/.git/"]},
    )

    assert status["ok"] is True
    assert status["saved_text_records"] == 1
    assert status["excluded_path_violations"] == []
    assert status["task_binding_violations"] == []


def test_typing_saved_text_recent_records_status_reports_path_and_binding_violations() -> None:
    records = [
        {
            "event_id": "secret-path",
            "source_adapter": "saved_text_snapshot",
            "metadata": {"file": {"path": "/work/secret-token.txt"}},
            "causal_context": {
                "task": {
                    "active_changes": [
                        {"path": "/work/secret-token.txt", "match": "surface_match"},
                    ]
                }
            },
        },
        {
            "event_id": "weak-binding",
            "source_adapter": "saved_text_snapshot",
            "metadata": {"file": {"path": "/work/notes/context.md"}},
            "causal_context": {
                "task": {
                    "active_changes": [
                        {"path": "/work/other/context.md", "match": "contextual_project"},
                    ]
                }
            },
        },
    ]

    status = typing_saved_text_recent_records_status(
        records=records,
        saved_policy={"deny_path_tokens": ["secret"], "exclude_path_tokens": ["/.git/"]},
    )

    assert status["ok"] is False
    assert status["excluded_path_violation_count"] == 1
    assert status["excluded_path_violations"] == [
        {
            "event_id": "secret-path",
            "path": "/work/secret-token.txt",
            "excluded": [],
            "denied": [{"kind": "deny_path_token", "token": "secret"}],
        }
    ]
    assert status["task_binding_violation_count"] == 1
    assert status["task_binding_violations"] == [
        {
            "event_id": "weak-binding",
            "path": "/work/notes/context.md",
            "active_changes": [
                {"path": "/work/other/context.md", "match": "contextual_project"},
            ],
        }
    ]


def test_cli_typing_saved_text_recent_records_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "records": [
            {
                "event_id": "saved-1",
                "source_adapter": "saved_text_snapshot",
                "metadata": {"file": {"path": "/work/notes/plan.md"}},
            }
        ],
        "saved_policy": {"deny_path_tokens": ["secret"]},
    }

    assert cli.typing_saved_text_recent_records_status(**kwargs) == typing_saved_text_recent_records_status(**kwargs)


def test_typing_recent_records_shape_status_accepts_safe_policy_and_causal_context() -> None:
    status = typing_recent_records_shape_status(
        [
            {
                "event_id": "event-safe",
                "policy": {
                    "raw_keylogging": False,
                    "password_fields_captured": False,
                    "raw_private_content": False,
                },
                "causal_context": {"task": {"id": "task-1"}},
            },
            "ignored",
        ]
    )

    assert status == {
        "ok": True,
        "records_checked": 1,
        "policy_violations": [],
        "policy_violation_count": 0,
        "missing_causal_context": [],
        "missing_causal_context_count": 0,
    }


def test_typing_recent_records_shape_status_flags_raw_policy_without_failing_causal_info() -> None:
    status = typing_recent_records_shape_status(
        [
            {
                "event_id": "event-raw",
                "policy": {
                    "raw_keylogging": True,
                    "password_fields_captured": False,
                    "raw_private_content": False,
                },
                "causal_context": {"task": {"id": "task-1"}},
            },
            {
                "event_id": "event-missing-policy",
                "policy": {
                    "raw_keylogging": False,
                    "password_fields_captured": False,
                },
                "causal_context": {"task": {"id": "task-2"}},
            },
            {
                "event_id": "event-old",
                "policy": {
                    "raw_keylogging": False,
                    "password_fields_captured": False,
                    "raw_private_content": False,
                },
            },
        ]
    )

    assert status["ok"] is False
    assert status["policy_violations"] == ["event-raw", "event-missing-policy"]
    assert status["policy_violation_count"] == 2
    assert status["missing_causal_context"] == ["event-old"]
    assert status["missing_causal_context_count"] == 1


def test_cli_typing_recent_records_shape_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    records = [
        {
            "event_id": "event-safe",
            "policy": {
                "raw_keylogging": False,
                "password_fields_captured": False,
                "raw_private_content": False,
            },
            "causal_context": {},
        }
    ]

    assert cli.typing_recent_records_shape_status(records) == typing_recent_records_shape_status(records)


def _typing_process_readmodel_fixture(**overrides: object) -> dict:
    process = {
        "schema": "abyss_machine_typing_process_v1",
        "ok": True,
        "status": "covered",
        "summary": {
            "records_processed": 2,
            "lanes": 1,
            "fail_gaps": 0,
            "missing_context_anchor": 0,
        },
        "policy": {
            "stores_extra_text": False,
            "widens_capture": False,
            "raw_keylogging": False,
        },
        "awareness": {
            "schema": "abyss_machine_typing_causal_awareness_summary_v1",
            "records": 2,
            "axis_states": {
                "privacy_gate": {"known": 2},
                "where_entered": {"known": 2},
                "who_received": {"known": 2},
                "task_context": {"known": 2},
            },
            "top_gaps": {},
            "policy": {
                "stores_extra_text": False,
                "widens_capture": False,
            },
        },
    }
    process.update(overrides)
    return process


def test_typing_process_readmodel_status_reports_ok_warn_and_fail_levels() -> None:
    ok_status = typing_process_readmodel_status(_typing_process_readmodel_fixture())
    assert ok_status["level"] == "ok"
    assert ok_status["core_ok"] is True
    assert ok_status["ok"] is True

    warn_process = _typing_process_readmodel_fixture(
        summary={
            "records_processed": 2,
            "lanes": 1,
            "fail_gaps": 0,
            "missing_context_anchor": 1,
        }
    )
    warn_status = typing_process_readmodel_status(warn_process)
    assert warn_status["level"] == "warn"
    assert warn_status["core_ok"] is True
    assert warn_status["ok"] is False

    fail_process = _typing_process_readmodel_fixture(
        policy={
            "stores_extra_text": False,
            "widens_capture": True,
            "raw_keylogging": False,
        }
    )
    fail_status = typing_process_readmodel_status(fail_process)
    assert fail_status["level"] == "fail"
    assert fail_status["checks"]["widens_capture"] is False


def test_typing_causal_awareness_readmodel_status_checks_axis_and_policy_shape() -> None:
    ok_status = typing_causal_awareness_readmodel_status(_typing_process_readmodel_fixture())
    assert ok_status["ok"] is True
    assert all(ok_status["checks"].values())

    mismatch_status = typing_causal_awareness_readmodel_status(
        _typing_process_readmodel_fixture(
            awareness={
                "schema": "abyss_machine_typing_causal_awareness_summary_v1",
                "records": 2,
                "axis_states": {
                    "privacy_gate": {"known": 2},
                    "where_entered": {"known": 1},
                    "who_received": {"known": 2},
                    "task_context": {"known": 2},
                },
                "top_gaps": {},
                "policy": {
                    "stores_extra_text": False,
                    "widens_capture": False,
                },
            }
        )
    )
    assert mismatch_status["ok"] is False
    assert mismatch_status["checks"]["where_entered_known"] is False

    unsafe_status = typing_causal_awareness_readmodel_status(
        _typing_process_readmodel_fixture(
            awareness={
                "schema": "abyss_machine_typing_causal_awareness_summary_v1",
                "records": 2,
                "axis_states": {
                    "privacy_gate": {"known": 2},
                    "where_entered": {"known": 2},
                    "who_received": {"known": 2},
                    "task_context": {"known": 2},
                },
                "top_gaps": {},
                "policy": {
                    "stores_extra_text": True,
                    "widens_capture": False,
                },
            }
        )
    )
    assert unsafe_status["ok"] is False
    assert unsafe_status["checks"]["stores_extra_text"] is False


def test_cli_typing_process_and_awareness_readmodel_status_delegate_to_module_contracts() -> None:
    from abyss_machine import cli

    process = _typing_process_readmodel_fixture()

    assert cli.typing_process_readmodel_status(process) == typing_process_readmodel_status(process)
    assert cli.typing_causal_awareness_readmodel_status(process) == typing_causal_awareness_readmodel_status(process)


def _typing_causal_policy() -> dict:
    return {
        "causal_context": {
            "project_roots": [
                {"id": "workspace", "kind": "workspace", "root": "/work"},
                {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"},
            ],
            "topic_hints": [
                {"id": "generic-seed", "kind": "topic", "root": "/work/seed", "keywords": ["seed"]},
                {
                    "id": "abyss-machine",
                    "kind": "repo",
                    "root": "/work/abyss-machine",
                    "keywords": ["abyss-machine", "portable seed"],
                },
            ],
            "broad_context_project_ids": ["workspace"],
        }
    }


def test_typing_causal_project_for_path_prefers_longest_matching_root() -> None:
    policy = _typing_causal_policy()

    direct = typing_causal_project_for_path("/work/abyss-machine/src/abyss_machine/cli.py", policy)
    first_match = typing_causal_project_for_paths(["/missing", "/work/abyss-machine/README.md"], policy)

    assert direct == {
        "id": "abyss-machine",
        "kind": "repo",
        "root": "/work/abyss-machine",
        "matched_path": "/work/abyss-machine/src/abyss_machine/cli.py",
    }
    assert first_match == {
        "id": "abyss-machine",
        "kind": "repo",
        "root": "/work/abyss-machine",
        "matched_path": "/work/abyss-machine/README.md",
        "basis": "explicit_path",
    }
    assert typing_causal_project_for_path("/other/place", policy) is None


def test_typing_causal_topic_project_for_text_selects_strongest_safe_hint() -> None:
    project = typing_causal_topic_project_for_text(
        "continue abyss-machine portable seed work",
        _typing_causal_policy(),
    )

    assert project is not None
    assert project["id"] == "abyss-machine"
    assert project["basis"] == "topic_hint"
    assert project["confidence"] == "topic_keyword_match"
    assert project["matched_keywords"] == ["abyss-machine", "portable seed"]
    assert project["stores_extra_text"] is False


def test_typing_causal_resolve_project_allows_topic_over_broad_workspace_only_for_safe_sources() -> None:
    policy = _typing_causal_policy()
    path_project = {
        "id": "workspace",
        "kind": "workspace",
        "root": "/work",
        "matched_path": "/work",
        "basis": "explicit_path",
    }
    topic_project = {
        "id": "abyss-machine",
        "kind": "repo",
        "root": "/work/abyss-machine",
        "matched_path": "/work/abyss-machine",
        "basis": "topic_hint",
        "confidence": "topic_keyword_match",
        "stores_extra_text": False,
    }

    resolved = typing_causal_resolve_project(path_project, topic_project, policy, "codex_user_prompt_submit")
    conservative = typing_causal_resolve_project(path_project, topic_project, policy, "browser_extension_explicit")

    assert resolved is not None
    assert resolved["id"] == "abyss-machine"
    assert resolved["basis"] == "topic_over_broad_workspace"
    assert resolved["workspace_project"] == path_project
    assert resolved["stores_extra_text"] is False
    assert conservative == path_project


def test_typing_causal_project_binding_summary_keeps_private_text_out_of_readmodel() -> None:
    summary = typing_causal_project_binding_summary(
        {
            "id": "abyss-machine",
            "kind": "repo",
            "root": "/work/abyss-machine",
            "basis": "topic_over_broad_workspace",
            "source_event_id": "evt-1",
            "source_age_sec": 10,
        }
    )
    missing = typing_causal_project_binding_summary(None, "fixture_missing")

    assert summary["id"] == "abyss-machine"
    assert summary["confidence"] == "topic_keyword_match"
    assert summary["source_event_id"] == "evt-1"
    assert summary["stores_extra_text"] is False
    assert missing == {
        "id": "unknown",
        "basis": "none",
        "confidence": "fixture_missing",
        "stores_extra_text": False,
    }


def test_cli_typing_causal_project_helpers_delegate_to_module_contracts() -> None:
    from abyss_machine import cli

    policy = _typing_causal_policy()
    path = "/work/abyss-machine/src/abyss_machine/cli.py"
    text = "continue abyss-machine portable seed work"
    path_project = typing_causal_project_for_path(path, policy)
    topic_project = typing_causal_topic_project_for_text(text, policy)

    assert cli.typing_causal_project_for_path(path, policy) == path_project
    assert cli.typing_causal_project_for_paths([path], policy) == typing_causal_project_for_paths([path], policy)
    assert cli.typing_causal_topic_project_for_text(text, policy) == topic_project
    assert (
        cli.typing_causal_resolve_project(path_project, topic_project, policy, "codex_user_prompt_submit")
        == typing_causal_resolve_project(path_project, topic_project, policy, "codex_user_prompt_submit")
    )
    assert cli.typing_causal_project_binding_summary(topic_project) == typing_causal_project_binding_summary(topic_project)


def _ai_counterpart_fixture() -> dict:
    return {
        "is_ai": True,
        "entity_id": "ai:openai:chatgpt",
        "label": "ChatGPT",
        "provider": "OpenAI",
        "product": "ChatGPT",
        "family": "gpt",
        "surface": "ai_chat",
        "origin": "https://chatgpt.com",
        "host": "chatgpt.com",
        "confidence": "known_ai_host",
    }


def test_typing_url_path_contracts_drop_query_text_and_hash_path_query() -> None:
    hashed = url_path_hash("https://chatgpt.com/c/secret-thread?model=gpt#fragment")

    assert url_origin_path("https://ChatGPT.com:443/c/secret-thread?model=gpt#fragment") == "https://chatgpt.com:443/c/secret-thread"
    assert url_origin_path("file:///tmp/private") is None
    assert hashed["url_path_present"] is True
    assert hashed["url_path_stored"] is False
    assert hashed["url_path_sha256"]
    assert "secret-thread" not in str(hashed)
    assert "model=gpt" not in str(hashed)
    assert url_path_hash(None) == {"url_path_present": False}


def test_typing_ai_counterpart_anchor_and_recipient_are_facts_only() -> None:
    counterpart = _ai_counterpart_fixture()
    anchor = ai_counterpart_context_anchor(counterpart)
    recipient = ai_counterpart_recipient(counterpart, "Firefox")

    assert anchor["kind"] == "ai_counterpart"
    assert anchor["id"] == "ai:openai:chatgpt"
    assert anchor["url_path_stored"] is False
    assert anchor["stores_extra_text"] is False
    assert recipient["kind"] == "ai_counterpart"
    assert recipient["route"] == "browser_ai_interaction"
    assert recipient["browser_app"] == "Firefox"
    assert "message" not in recipient


def test_typing_context_anchor_from_parts_is_module_owned_and_home_is_explicit() -> None:
    project = {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"}
    project_anchor = context_anchor_from_parts(
        "manual_cli_stdin",
        "Terminal",
        "shell",
        None,
        "/work/abyss-machine/README.md",
        project,
        home_path="/home/operator",
    )
    ai_anchor = context_anchor_from_parts(
        "browser_extension_explicit",
        "Firefox",
        "ChatGPT",
        "https://chatgpt.com/c/private-thread?model=gpt",
        None,
        None,
        home_path="/home/operator",
    )
    url_anchor = context_anchor_from_parts(
        "browser_extension_explicit",
        "Firefox",
        "Example",
        "https://example.test/private/path?token=secret",
        None,
        None,
        home_path="/home/operator",
    )
    home_anchor = context_anchor_from_parts(
        "saved_text_snapshot",
        None,
        None,
        None,
        "/home/operator/notes/private.txt",
        None,
        home_path="/home/operator",
    )
    path_anchor = context_anchor_from_parts(
        "saved_text_snapshot",
        None,
        None,
        None,
        "/srv/project/outside.txt",
        None,
        home_path="/home/operator",
    )
    app_anchor = context_anchor_from_parts(
        "manual_cli_stdin",
        "Terminal",
        "Private Window Title",
        None,
        None,
        None,
        home_path="/home/operator",
    )
    unknown_anchor = context_anchor_from_parts("manual_cli_stdin", None, None, None, None, None, home_path="/home/operator")

    assert project_anchor["kind"] == "project_root"
    assert project_anchor["id"] == "project:abyss-machine"
    assert project_anchor["stores_extra_text"] is False
    assert ai_anchor["kind"] == "ai_counterpart"
    assert ai_anchor["id"] == "ai:openai:chatgpt"
    assert ai_anchor["url_path_stored"] is False
    assert "private-thread" not in str(ai_anchor)
    assert url_anchor["kind"] == "url_origin"
    assert url_anchor["id"] == "url:https://example.test"
    assert url_anchor["url_path_stored"] is False
    assert "token=secret" not in str(url_anchor)
    assert home_anchor["kind"] == "operator_home_path"
    assert home_anchor["id"] == "path:/home/operator"
    assert home_anchor["matched_path"] == "/home/operator/notes/private.txt"
    assert path_anchor["kind"] == "path"
    assert path_anchor["id"] == "path:/srv/project/outside.txt"
    assert app_anchor["kind"] == "application_surface"
    assert app_anchor["app"] == "Terminal"
    assert app_anchor["window_title_sha256"] == hashlib.sha256(b"Private Window Title").hexdigest()
    assert "Private Window Title" not in str(app_anchor)
    assert unknown_anchor == {
        "kind": "unknown",
        "id": "unknown",
        "label": "unknown",
        "confidence": "missing_observable_context",
        "stores_extra_text": False,
    }


def test_typing_process_context_anchor_promotes_ai_and_guards_sensitive_atspi_context() -> None:
    project_anchor = typing_process_context_anchor(
        "manual_cli_stdin",
        {
            "context_anchor": {"kind": "unknown", "id": "unknown"},
            "app": "Terminal",
            "window_title": "shell",
            "path": "/work/abyss-machine/README.md",
        },
        {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"},
        home_path="/home/operator",
    )
    interaction_anchor = typing_process_context_anchor(
        "browser_ai_transcript",
        {
            "context_anchor": {"kind": "url_origin", "id": "url:https://chatgpt.com"},
            "interaction": {
                "ai_counterpart_id": "ai:openai:chatgpt",
                "product": "ChatGPT",
                "provider": "OpenAI",
                "family": "gpt",
                "surface": "ai_chat",
                "origin": "https://chatgpt.com",
                "confidence": "browser_ai_conversation",
            },
        },
        None,
        home_path="/home/operator",
    )
    atspi_anchor = typing_process_context_anchor(
        "atspi_text_changed_event",
        {
            "app": "Firefox",
            "window_title": "",
            "url": "https://gemini.google.com/app/private-thread?token=secret",
            "context": "role=entry editable=True",
        },
        None,
        home_path="/home/operator",
    )
    guarded_anchor = typing_process_context_anchor(
        "atspi_text_changed_event",
        {
            "app": "Firefox",
            "context": "password field username login",
        },
        None,
        home_path="/home/operator",
    )

    assert project_anchor["kind"] == "project_root"
    assert project_anchor["id"] == "project:abyss-machine"
    assert interaction_anchor["kind"] == "ai_counterpart"
    assert interaction_anchor["id"] == "ai:openai:chatgpt"
    assert interaction_anchor["readmodel_promoted_from"] == "url_origin"
    assert interaction_anchor["stores_extra_text"] is False
    assert atspi_anchor["kind"] == "ai_counterpart"
    assert atspi_anchor["id"] == "ai:google:gemini"
    assert atspi_anchor["url_path_stored"] is False
    assert "private-thread" not in str(atspi_anchor)
    assert "token=secret" not in str(atspi_anchor)
    assert guarded_anchor == {
        "kind": "privacy_guarded",
        "id": "privacy:atspi-sensitive-field",
        "label": "AT-SPI privacy-guarded field",
        "confidence": "metadata_only_sensitive_context",
        "stores_extra_text": False,
    }


def test_typing_process_recipient_and_interaction_keys_are_module_owned() -> None:
    context_anchor = {
        "kind": "ai_counterpart",
        "id": "ai:openai:chatgpt",
        "label": "ChatGPT",
        "provider": "OpenAI",
        "product": "ChatGPT",
        "family": "gpt",
        "surface": "ai_chat",
        "origin": "https://chatgpt.com",
        "confidence": "host",
    }
    promoted = typing_process_recipient_for_context(
        "browser_extension_explicit",
        {"kind": "browser_extension", "id": "firefox-extension"},
        {"app": "Firefox"},
        context_anchor,
    )
    original = {"kind": "file", "id": "/work/notes.md"}
    interaction = {
        "kind": "browser_ai_conversation",
        "id": "browser-ai:ai:openai:chatgpt:abc",
        "ai_counterpart_id": "ai:openai:chatgpt",
        "title_sha256": "1234567890abcdef9999",
    }
    keys = typing_process_interaction_keys(interaction, promoted, context_anchor)
    recipient_key = typing_process_interaction_keys({}, {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"}, {})
    anchor_key = typing_process_interaction_keys({}, {}, {"kind": "url_origin", "id": "url:https://example.test"})

    assert promoted["kind"] == "ai_counterpart"
    assert promoted["route"] == "browser_ai_interaction"
    assert promoted["id"] == "ai:openai:chatgpt"
    assert promoted["browser_app"] == "Firefox"
    assert typing_process_recipient_for_context("saved_text_snapshot", original, {}, context_anchor) == original
    assert keys == [
        "browser_ai_conversation:browser-ai:ai:openai:chatgpt:abc",
        "browser_ai_title:ai:openai:chatgpt:1234567890abcdef",
    ]
    assert typing_process_interaction_key(interaction, promoted, context_anchor) == keys[0]
    assert recipient_key == ["recipient:ai_counterpart:ai:openai:chatgpt"]
    assert anchor_key == ["anchor:url_origin:url:https://example.test"]


def test_typing_process_lane_id_is_stable_without_raw_text_payloads() -> None:
    parts = [
        "abyss-machine",
        "change-123",
        "url:https://example.test",
        "ai_counterpart",
        "ai:openai:chatgpt",
        "browser",
    ]
    lane_id = typing_process_lane_id(parts)
    label, digest = lane_id.rsplit("-", 1)

    assert lane_id.startswith("abyss-machine-change-123-url:https:-example.test-ai_counterpart")
    assert len(label) <= 80
    assert len(digest) == 12
    assert digest == "e4f6bdbd81ba"
    assert lane_id == typing_process_lane_id(parts)


def test_typing_process_project_and_interaction_helpers_are_module_owned() -> None:
    policy = {
        "causal_context": {
            "project_roots": [
                {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"},
                {"id": "workspace", "kind": "workspace", "root": "/work"},
            ],
            "topic_hints": [
                {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine", "keywords": ["typing process"]},
            ],
            "broad_context_project_ids": ["workspace"],
        }
    }
    record = {
        "event_id": "event-1",
        "source_adapter": "manual_cli_stdin",
        "generated_at": "2026-01-01T10:00:00Z",
        "text": {"text": "typing process helper work", "text_sha256": "sha256:text"},
        "metadata": {},
    }
    where = {
        "app": "Terminal",
        "window_title": "shell",
        "context": "cwd=/work typing process",
        "path": "/work",
    }
    controlled = typing_causal_controlled_probe_project(
        "browser_extension_explicit",
        {"app": {"text": "Firefox"}, "window_title": {"text": "Abyss browser webextension safe input probe"}},
        {"browser": {"event_kind": "selftest_committed_text"}},
    )
    inferred = typing_process_project_for_record(record, where, policy)
    existing = typing_process_project_for_record(record, {"project": {"id": "explicit", "kind": "repo"}}, policy)
    interaction = typing_process_interaction_for_record(
        {
            "source_adapter": "browser_ai_transcript",
            "metadata": {"ai_transcript": {"page_identity": _ai_counterpart_fixture()}},
        },
        {"app": "Firefox", "window_title": "ChatGPT", "url": "https://chatgpt.com/c/private?model=gpt"},
    )
    explicit_interaction = typing_process_interaction_for_record({}, {"interaction": {"kind": "codex_session", "id": "codex:session"}})

    assert controlled is not None
    assert controlled["id"] == "abyss-machine"
    assert controlled["basis"] == "controlled_probe"
    assert inferred["id"] == "abyss-machine"
    assert inferred["basis"] == "topic_over_broad_workspace"
    assert inferred["readmodel_promoted_from"] == "stored_safe_text_or_context"
    assert inferred["stores_extra_text"] is False
    assert existing == {"id": "explicit", "kind": "repo"}
    assert interaction["kind"] == "browser_ai_conversation"
    assert interaction["url_path_stored"] is False
    assert "private" not in str(interaction)
    assert explicit_interaction == {"kind": "codex_session", "id": "codex:session"}


def test_typing_process_unique_records_epoch_and_continuity_contracts() -> None:
    project = {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"}
    interaction = {"kind": "browser_ai_conversation", "id": "browser-ai:thread-1"}
    records = [
        {
            "event_id": "new",
            "generated_at": "2026-01-01T10:05:00Z",
            "source_adapter": "browser_ai_transcript",
            "causal_context": {
                "where": {"interaction": interaction, "app": "Firefox", "window_title": "ChatGPT"},
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
            },
        },
        {
            "event_id": "old",
            "generated_at": "2026-01-01T10:00:00Z",
            "source_adapter": "browser_ai_transcript",
            "causal_context": {
                "where": {"interaction": interaction, "project": project},
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
            },
        },
        {
            "event_id": "before",
            "generated_at": "2026-01-01T09:55:00Z",
            "source_adapter": "browser_ai_transcript",
            "causal_context": {
                "where": {"interaction": interaction, "app": "Firefox", "window_title": "ChatGPT"},
                "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
            },
        },
        {"event_id": "old", "generated_at": "2026-01-01T10:00:00Z"},
        "not-a-record",
    ]
    unique, dedupe = typing_process_unique_records(records)
    continuity, summary = typing_process_continuity_projects(
        unique,
        {"causal_context": {"max_interaction_continuity_age_sec": 7200}},
        home_path="/home/operator",
    )

    assert dedupe == {
        "raw_records": 4,
        "unique_records": 3,
        "duplicate_event_rows_collapsed": 1,
        "duplicate_event_ids": ["old"],
    }
    assert typing_process_generated_epoch({"generated_at": "2026-01-01T10:00:00Z"}) == 1767261600.0
    assert typing_process_generated_epoch({"generated_at": "not-a-date"}) == 0.0
    assert continuity["old"]["id"] == "abyss-machine"
    assert continuity["new"]["basis"] == "interaction_continuity"
    assert continuity["new"]["readmodel_promoted_from"] == "same_interaction_recent_project"
    assert continuity["new"]["source_event_id"] == "old"
    assert continuity["before"]["readmodel_promoted_from"] == "same_interaction_future_project"
    assert continuity["before"]["stores_extra_text"] is False
    assert summary["interaction_records"] == 3
    assert summary["continuity_promoted"] == 2
    assert summary["continuity_backfilled"] == 1
    assert summary["continuity_blocked_by_age"] == 0


def test_typing_process_from_records_builds_module_owned_readmodel_without_text_widening() -> None:
    record = {
        "event_id": "event-1",
        "generated_at": "2026-01-01T10:00:00Z",
        "source_adapter": "browser_ai_transcript",
        "status": "captured",
        "capture_gate": {"decision": "allow", "confidence": "safe_context"},
        "text": {"captured": True, "text_sha256": "sha256:text", "text_length": 42},
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
        "causal_context": {
            "where": {
                "kind": "browser",
                "project": {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"},
                "interaction": {"kind": "browser_ai_conversation", "id": "browser-ai:thread-1"},
            },
            "recipient": {
                "kind": "ai_counterpart",
                "id": "ai:openai:chatgpt",
                "provider": "OpenAI",
                "product": "ChatGPT",
                "confidence": "known_ai_host",
            },
            "task": {"binding": "project_or_surface_context"},
        },
    }
    process = typing_process_from_records(
        [record],
        [],
        {"ok": True, "causal_context": {"max_interaction_continuity_age_sec": 7200}},
        generated_at="2026-01-01T10:10:00Z",
        version="test-version",
        home_path="/home/operator",
    )

    assert process["schema"] == "abyss_machine_typing_process_v1"
    assert process["version"] == "test-version"
    assert process["generated_at"] == "2026-01-01T10:10:00Z"
    assert process["ok"] is True
    assert process["status"] == "processed"
    assert process["summary"]["records_processed"] == 1
    assert process["summary"]["lanes"] == 1
    assert process["summary"]["awareness_average_score"] == 1.0
    assert process["awareness"]["axis_states"]["privacy_gate"]["known"] == 1
    assert process["recent_entries"][0]["text_omitted"] is True
    assert process["policy"]["stores_extra_text"] is False
    assert process["policy"]["widens_capture"] is False
    assert "sha256:text" in str(process)
    assert "captured raw text" not in str(process)


def test_typing_causal_context_readmodel_from_records_builds_module_owned_document() -> None:
    record = {
        "event_id": "event-1",
        "generated_at": "2026-01-01T10:00:00Z",
        "source_adapter": "browser_ai_transcript",
        "status": "captured",
        "text": {"captured": True, "text": "sensitive raw text must not escape", "text_sha256": "sha256:text"},
        "causal_context": {
            "where": {
                "kind": "browser",
                "app": "Firefox",
                "window_title": "ChatGPT",
                "project": {"id": "abyss-machine", "kind": "repo", "root": "/work/abyss-machine"},
                "interaction": {"kind": "browser_ai_conversation", "id": "browser-ai:thread-1"},
            },
            "recipient": {
                "kind": "ai_counterpart",
                "id": "ai:openai:chatgpt",
                "provider": "OpenAI",
                "product": "ChatGPT",
                "confidence": "known_ai_host",
            },
            "task": {
                "binding": "active_change",
                "active_changes": [{"id": "change-1", "title": "Close command glue", "match": "surface_match"}],
            },
        },
    }
    readmodel = typing_causal_context_readmodel_from_records(
        [record, dict(record)],
        [],
        {"ok": True, "causal_context": {"contextual_active_change_task_binding": True}},
        generated_at="2026-01-01T10:10:00Z",
        version="test-version",
        home_path="/home/operator",
    )

    assert readmodel["schema"] == "abyss_machine_typing_causal_context_readmodel_v1"
    assert readmodel["version"] == "test-version"
    assert readmodel["generated_at"] == "2026-01-01T10:10:00Z"
    assert readmodel["ok"] is True
    assert readmodel["summary"]["returned"] == 1
    assert readmodel["summary"]["raw_records_scanned"] == 2
    assert readmodel["summary"]["duplicate_event_rows_collapsed"] == 1
    assert readmodel["summary"]["task_bound"] == 1
    assert readmodel["summary"]["context_bound"] == 1
    assert readmodel["summary"]["correlation_bound"] == 1
    assert readmodel["summary"]["by_recipient"] == {"ai_counterpart": 1}
    assert readmodel["summary"]["by_project"] == {"abyss-machine": 1}
    assert readmodel["entries"][0]["correlation"]["readmodel_backfill"] is True
    assert readmodel["entries"][0]["correlation"]["stores_text"] is False
    assert readmodel["entries"][0]["task"]["context_anchor"]["id"] == "change-1"
    assert readmodel["entries"][0]["task"]["project"]["id"] == "abyss-machine"
    assert readmodel["policy"]["stores_text"] is False
    assert "sensitive raw text must not escape" not in str(readmodel)


def test_typing_browser_input_recency_builds_module_owned_readmodel_without_text_widening() -> None:
    natural_record = {
        "event_id": "browser-natural",
        "generated_at": "2026-01-01T10:00:00Z",
        "source_adapter": "browser_extension_explicit",
        "status": "captured",
        "capture_gate": {"decision": "allow", "confidence": "safe_browser"},
        "text": {"captured": True, "text": "sensitive browser text must not escape", "text_length": 36},
        "context": {
            "app": {"text": "Firefox"},
            "window_title": {"text": "ChatGPT"},
            "url": {"text": "https://chatgpt.com/c/private?model=gpt"},
        },
        "causal_context": {
            "recipient": {"kind": "browser_extension", "id": "extension"},
            "task": {"binding": "unbound"},
        },
    }
    controlled_record = {
        "event_id": "browser-selftest",
        "generated_at": "2026-01-01T10:01:00Z",
        "source_adapter": "browser_extension_explicit",
        "status": "captured",
        "text": {"captured": True, "text_length": 12},
        "context": {
            "app": {"text": "Firefox"},
            "window_title": {"text": "Abyss browser webextension selftest"},
            "url": {"text": "http://127.0.0.1:3456/probe"},
        },
    }
    effective_entries = {
        "browser-natural": {
            "event_id": "browser-natural",
            "where": {
                "project": {"id": "abyss-machine", "kind": "repo"},
                "project_binding": {"basis": "interaction_continuity"},
                "context_anchor": {"kind": "url_origin", "id": "url:https://chatgpt.com"},
                "interaction": {"kind": "browser_ai_conversation", "id": "browser-ai:thread-1"},
            },
            "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt", "name": "ChatGPT"},
            "task": {"binding": "project_or_surface_context"},
            "awareness": {"state": "complete", "score": 1.0},
        }
    }
    recency = typing_browser_input_recency(
        [natural_record, controlled_record],
        "2026-01-01T10:05:00Z",
        effective_entries,
    )

    assert typing_parse_iso("2026-01-01T10:00:00Z").isoformat() == "2026-01-01T10:00:00+00:00"
    assert typing_age_seconds("2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z") == 300.0
    assert typing_record_context_text(natural_record, "app") == "Firefox"
    assert typing_record_url_origin(natural_record) == {
        "origin": "https://chatgpt.com",
        "scheme": "https",
        "host": "chatgpt.com",
        "id": "url:https://chatgpt.com",
    }
    assert typing_browser_like_record(natural_record) is True
    assert typing_controlled_probe_record(controlled_record) is True
    assert typing_latest_record([natural_record, controlled_record])["event_id"] == "browser-selftest"
    assert typing_process_entry_index({"recent_entries": [{"event_id": "browser-natural"}]}) == {"browser-natural": {"event_id": "browser-natural"}}
    assert recency["schema"] == "abyss_machine_typing_browser_input_recency_v1"
    assert recency["status"] == "natural_browser_text_observed"
    assert recency["records"] == 2
    assert recency["natural_records"] == 1
    assert recency["controlled_probe_records"] == 1
    assert recency["latest_natural_text"]["project_id"] == "abyss-machine"
    assert recency["latest_natural_text"]["effective_causal_promoted"] is True
    assert recency["latest_natural_text"]["page_identity"]["entity_id"] == "ai:openai:chatgpt"
    assert recency["policy"]["text_omitted"] is True
    assert recency["policy"]["url_query_fragment_omitted"] is True
    assert "sensitive browser text must not escape" not in str(recency)
    assert "private?model" not in str(recency)


def test_typing_causal_awareness_for_event_scores_known_guarded_and_missing_axes() -> None:
    complete = typing_causal_awareness_for_event(
        source_adapter="browser_ai_transcript",
        status="captured",
        gate={"decision": "allow", "confidence": "safe_context"},
        text_payload={"captured": True, "text_sha256": "sha256:text", "text_length": 42},
        project_id="abyss-machine",
        project_binding={"basis": "project_root_match", "confidence": "project_root_match"},
        recipient={"kind": "ai_counterpart", "id": "ai:openai:chatgpt", "provider": "OpenAI", "product": "ChatGPT"},
        task_binding="project_or_surface_context",
        context_anchor={"kind": "ai_counterpart", "id": "ai:openai:chatgpt", "confidence": "host"},
        interaction={"kind": "browser_ai_conversation", "id": "browser-ai:thread-1", "confidence": "host_path"},
        surface_kind="browser",
    )
    guarded = typing_causal_awareness_for_event(
        source_adapter="atspi_text_changed_event",
        status="metadata_only",
        gate={"decision": "metadata_only", "confidence": "sensitive_field"},
        text_payload={"captured": False, "text_length": 0, "metadata_only_reason": "sensitive_field"},
        project_id="unknown",
        project_binding={"confidence": "no_project_path_topic_or_continuity_signal"},
        recipient={"kind": "focused_application", "id": "Firefox"},
        task_binding="context_anchor",
        context_anchor={"kind": "privacy_guarded", "id": "privacy:atspi-sensitive-field", "confidence": "metadata_only_sensitive_context"},
        interaction={"kind": "browser_page", "id": "browser-page:fixture"},
        surface_kind="accessibility_text_event",
    )
    incomplete = typing_causal_awareness_for_event(
        source_adapter="manual_cli_stdin",
        status="captured",
        gate={},
        text_payload={},
        project_id="unknown",
        project_binding={},
        recipient={},
        task_binding="unbound",
        context_anchor={},
        interaction={},
        surface_kind="missing",
    )

    assert complete["schema"] == "abyss_machine_typing_causal_awareness_event_v1"
    assert complete["state"] == "complete"
    assert complete["score"] == 1.0
    assert complete["stores_extra_text"] is False
    assert guarded["state"] == "complete"
    assert guarded["guarded_axes"] == 2
    assert guarded["missing_axes"] == 0
    assert guarded["axes"]["project_context"]["basis"] == "metadata_only_context_does_not_widen_project_binding"
    assert incomplete["state"] == "incomplete"
    assert incomplete["missing_axes"] >= 5
    assert {"axis": "privacy_gate", "state": "missing", "basis": "missing_capture_gate"} in incomplete["gaps"]


def test_typing_causal_browser_metadata_context_prefers_browser_then_atspi_document_title() -> None:
    assert causal_browser_metadata_context(None) == {}
    assert causal_browser_metadata_context({"atspi": {"url": "https://example.test", "document_title": "Doc"}}) == {
        "url": "https://example.test",
        "title": "Doc",
    }
    assert causal_browser_metadata_context(
        {
            "browser": {"url": "https://browser.test", "title": "Browser"},
            "atspi": {"url": "https://atspi.test", "document_title": "AT-SPI"},
        }
    ) == {"url": "https://browser.test", "title": "Browser"}


def test_typing_causal_extract_context_value_trims_terminal_punctuation() -> None:
    context = "cwd=/work/repo session_id=session-1) turn_id=turn-2,"

    assert causal_extract_context_value(context, "session_id") == "session-1"
    assert causal_extract_context_value(context, "turn_id") == "turn-2"
    assert causal_extract_context_value(context, "missing") is None


def test_typing_causal_interaction_identity_builds_codex_session_without_text_storage() -> None:
    identity = causal_interaction_identity(
        "codex_session_jsonl_prompt_tail",
        {
            "app": {"text": "Codex"},
            "window_title": {"text": "Codex"},
            "context": {"text": "session_id=session-1 turn_id=turn-2 write private launch plan"},
        },
        {},
    )

    assert identity["kind"] == "codex_session"
    assert identity["id"] == "codex:session-1"
    assert identity["turn_id"] == "turn-2"
    assert identity["route"] == "codex_raw_jsonl_prompt_tail"
    assert identity["fallback"] is True
    assert identity["stores_extra_text"] is False
    assert "private launch plan" not in str(identity)


def test_typing_causal_interaction_identity_hashes_browser_ai_path_without_storing_url_path() -> None:
    url = "https://chatgpt.com/c/private-thread?model=gpt"
    identity = causal_interaction_identity(
        "browser_ai_transcript",
        {
            "app": {"text": "Firefox"},
            "window_title": {"text": "ChatGPT"},
            "url": {"text": url},
        },
        {
            "ai_transcript": {
                "page_identity": _ai_counterpart_fixture(),
                "message_role": "assistant",
                "message_index": 3,
                "message_fingerprint": "sha256:fixture",
                "completeness": "visible",
            }
        },
    )
    expected_hash = url_path_hash(url)["url_path_sha256"]

    assert identity["kind"] == "browser_ai_conversation"
    assert identity["id"] == f"browser-ai:ai:openai:chatgpt:{expected_hash[:16]}"
    assert identity["url_path_sha256"] == expected_hash
    assert identity["url_path_stored"] is False
    assert identity["message_role"] == "assistant"
    assert identity["stores_extra_text"] is False
    assert "private-thread" not in str(identity)
    assert "model=gpt" not in str(identity)


def test_typing_causal_interaction_identity_falls_back_to_surface_kind_hash() -> None:
    identity = causal_interaction_identity(
        "manual_cli_stdin",
        {
            "app": {"text": "terminal"},
            "window_title": {"text": "shell"},
            "context": {"text": "manual committed note"},
        },
        None,
    )

    assert identity["kind"] == "manual_cli"
    assert identity["id"].startswith("manual_cli:")
    assert identity["confidence"] == "adapter_surface_context"
    assert identity["stores_extra_text"] is False
    assert "manual committed note" not in str(identity)


def test_typing_causal_recipient_routes_known_adapters_without_live_io() -> None:
    context = {
        "app": {"text": "Firefox"},
        "window_title": {"text": "ChatGPT"},
        "url": {"text": ""},
    }
    ai = causal_recipient(
        "browser_extension_explicit",
        context,
        {"ai_transcript": {"page_identity": _ai_counterpart_fixture()}},
    )
    saved = causal_recipient(
        "saved_text_snapshot",
        {"window_title": {"text": "notes.md"}},
        {"file": {"path": "/work/notes.md", "name": "notes.md"}},
    )
    codex = causal_recipient(
        "codex_session_jsonl_prompt_tail",
        {"app": {"text": "codex-app"}, "window_title": {"text": "Codex"}},
        {"codex": {"session_id": "session-1"}},
    )

    assert ai["kind"] == "ai_counterpart"
    assert ai["id"] == "ai:openai:chatgpt"
    assert saved["kind"] == "file"
    assert saved["id"] == "/work/notes.md"
    assert codex["kind"] == "codex_session"
    assert codex["route"] == "codex_raw_jsonl_prompt_tail"
    assert causal_surface_kind("atspi_text_changed_event") == "accessibility_text_event"
    assert causal_surface_kind("browser_extension_explicit") == "browser"


def test_cli_typing_causal_identity_helpers_delegate_to_module_contracts(monkeypatch) -> None:
    from abyss_machine import cli

    counterpart = _ai_counterpart_fixture()
    context = {"app": {"text": "Firefox"}, "window_title": {"text": "ChatGPT"}}
    metadata = {"ai_transcript": {"page_identity": counterpart}}
    url = "https://chatgpt.com/c/example?model=gpt"
    monkeypatch.setattr(cli.Path, "home", lambda: Path("/home/operator"))

    assert cli.typing_causal_extract_context_value("session_id=session-1)", "session_id") == causal_extract_context_value(
        "session_id=session-1)",
        "session_id",
    )
    assert cli.typing_url_origin_path(url) == url_origin_path(url)
    assert cli.typing_url_path_hash(url) == url_path_hash(url)
    assert cli.typing_ai_counterpart_context_anchor(counterpart) == ai_counterpart_context_anchor(counterpart)
    assert cli.typing_causal_interaction_identity("browser_ai_transcript", {"url": {"text": url}}, metadata) == causal_interaction_identity(
        "browser_ai_transcript",
        {"url": {"text": url}},
        metadata,
    )
    assert cli.typing_context_anchor_from_parts(
        "saved_text_snapshot",
        None,
        None,
        None,
        "/home/operator/notes.txt",
        None,
    ) == context_anchor_from_parts(
        "saved_text_snapshot",
        None,
        None,
        None,
        "/home/operator/notes.txt",
        None,
        home_path="/home/operator",
    )
    assert cli.typing_causal_browser_metadata_context(metadata) == causal_browser_metadata_context(metadata)
    assert cli.typing_ai_counterpart_recipient(counterpart, "Firefox") == ai_counterpart_recipient(counterpart, "Firefox")
    assert cli.typing_causal_recipient("browser_extension_explicit", context, metadata) == causal_recipient(
        "browser_extension_explicit",
        context,
        metadata,
    )
    assert cli.typing_causal_surface_kind("manual_cli_stdin") == causal_surface_kind("manual_cli_stdin")
    process_where = {
        "app": "Firefox",
        "url": "https://chatgpt.com/c/example?model=gpt",
        "window_title": "ChatGPT",
    }
    process_anchor = typing_process_context_anchor(
        "browser_extension_explicit",
        process_where,
        None,
        home_path="/home/operator",
    )
    process_recipient = typing_process_recipient_for_context(
        "browser_extension_explicit",
        {"kind": "browser_extension", "id": "extension"},
        process_where,
        process_anchor,
    )
    process_interaction = {
        "kind": "browser_ai_page",
        "id": "browser-ai-page:fixture",
        "title_sha256": "abcdef1234567890ffff",
    }
    assert cli.typing_process_context_anchor("browser_extension_explicit", process_where, None) == process_anchor
    assert cli.typing_process_recipient_for_context(
        "browser_extension_explicit",
        {"kind": "browser_extension", "id": "extension"},
        process_where,
        process_anchor,
    ) == process_recipient
    assert cli.typing_process_interaction_keys(process_interaction, process_recipient, process_anchor) == typing_process_interaction_keys(
        process_interaction,
        process_recipient,
        process_anchor,
    )
    assert cli.typing_process_interaction_key(process_interaction, process_recipient, process_anchor) == typing_process_interaction_key(
        process_interaction,
        process_recipient,
        process_anchor,
    )
    assert cli.typing_process_lane_id(["project", "task", "anchor"]) == typing_process_lane_id(["project", "task", "anchor"])
    process_record = {
        "event_id": "event-1",
        "generated_at": "2026-01-01T10:00:00Z",
        "source_adapter": "browser_ai_transcript",
        "metadata": {"ai_transcript": {"page_identity": counterpart}},
        "causal_context": {
            "where": {
                "interaction": process_interaction,
                "project": {"id": "abyss-machine", "kind": "repo"},
            },
            "recipient": process_recipient,
        },
    }
    process_records = [process_record, process_record]
    process_policy = {"causal_context": {"max_interaction_continuity_age_sec": 7200}}
    assert cli.typing_causal_controlled_probe_project(
        "browser_extension_explicit",
        {"app": {"text": "Firefox"}, "context": {"text": "abyss browser webextension safe input probe"}},
        {"browser": {"event_kind": "selftest_committed_text"}},
    ) == typing_causal_controlled_probe_project(
        "browser_extension_explicit",
        {"app": {"text": "Firefox"}, "context": {"text": "abyss browser webextension safe input probe"}},
        {"browser": {"event_kind": "selftest_committed_text"}},
    )
    assert cli.typing_process_project_for_record(
        process_record,
        {"project": {"id": "abyss-machine", "kind": "repo"}},
        process_policy,
    ) == typing_process_project_for_record(
        process_record,
        {"project": {"id": "abyss-machine", "kind": "repo"}},
        process_policy,
    )
    assert cli.typing_process_unique_records(process_records) == typing_process_unique_records(process_records)
    assert cli.typing_process_interaction_for_record(process_record, {"interaction": process_interaction}) == typing_process_interaction_for_record(
        process_record,
        {"interaction": process_interaction},
    )
    assert cli.typing_process_generated_epoch(process_record) == typing_process_generated_epoch(process_record)
    assert cli.typing_process_continuity_projects([process_record], process_policy) == typing_process_continuity_projects(
        [process_record],
        process_policy,
        home_path="/home/operator",
    )
    process_doc_record = {
        **process_record,
        "status": "captured",
        "capture_gate": {"decision": "allow"},
        "text": {"captured": True, "text_sha256": "sha256:text", "text_length": 12},
        "policy": {"raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
    }
    assert cli.typing_process_from_records(
        [process_doc_record],
        [],
        {"ok": True, "causal_context": {"max_interaction_continuity_age_sec": 7200}},
        generated_at="2026-01-01T10:10:00Z",
    ) == typing_process_from_records(
        [process_doc_record],
        [],
        {"ok": True, "causal_context": {"max_interaction_continuity_age_sec": 7200}},
        generated_at="2026-01-01T10:10:00Z",
        version=cli.VERSION,
        home_path="/home/operator",
    )
    causal_policy = {"ok": True, "causal_context": {"max_interaction_continuity_age_sec": 7200}}
    assert cli.typing_causal_context_readmodel_from_records(
        [process_doc_record],
        [],
        causal_policy,
        generated_at="2026-01-01T10:11:00Z",
    ) == typing_causal_context_readmodel_from_records(
        [process_doc_record],
        [],
        causal_policy,
        generated_at="2026-01-01T10:11:00Z",
        version=cli.VERSION,
        home_path="/home/operator",
    )

    captured: dict[str, object] = {}

    def fake_typing_records(limit: int) -> tuple[list[dict], list[dict]]:
        captured["limit"] = limit
        return [process_doc_record], []

    def fake_typing_policy(write_latest: bool = True) -> dict:
        captured["write_latest"] = write_latest
        return causal_policy

    monkeypatch.setattr(cli, "typing_records", fake_typing_records)
    monkeypatch.setattr(cli, "typing_policy", fake_typing_policy)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-01-01T10:12:00Z")
    assert cli.typing_causal_context_readmodel(lines=9999) == typing_causal_context_readmodel_from_records(
        [process_doc_record],
        [],
        causal_policy,
        generated_at="2026-01-01T10:12:00Z",
        version=cli.VERSION,
        home_path="/home/operator",
    )
    assert captured == {"limit": 1000, "write_latest": False}
    browser_record = {
        "event_id": "browser-natural",
        "generated_at": "2026-01-01T10:00:00Z",
        "source_adapter": "browser_extension_explicit",
        "status": "captured",
        "text": {"captured": True, "text_length": 18},
        "context": {
            "app": {"text": "Firefox"},
            "window_title": {"text": "ChatGPT"},
            "url": {"text": "https://chatgpt.com/c/example?model=gpt"},
        },
    }
    effective_entries = {
        "browser-natural": {
            "where": {
                "project": {"id": "abyss-machine"},
                "context_anchor": {"kind": "url_origin", "id": "url:https://chatgpt.com"},
                "interaction": {"kind": "browser_ai_conversation", "id": "browser-ai:thread-1"},
            },
            "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
            "task": {"binding": "project_or_surface_context"},
        }
    }
    assert cli.typing_parse_iso("2026-01-01T10:00:00Z") == typing_parse_iso("2026-01-01T10:00:00Z")
    assert cli.typing_age_seconds("2026-01-01T10:00:00Z", "2026-01-01T10:05:00Z") == typing_age_seconds(
        "2026-01-01T10:00:00Z",
        "2026-01-01T10:05:00Z",
    )
    assert cli.typing_record_context_text(browser_record, "url") == typing_record_context_text(browser_record, "url")
    assert cli.typing_record_url_origin(browser_record) == typing_record_url_origin(browser_record)
    assert cli.typing_controlled_probe_record(browser_record) == typing_controlled_probe_record(browser_record)
    assert cli.typing_browser_like_record(browser_record) == typing_browser_like_record(browser_record)
    assert cli.typing_process_entry_index({"recent_entries": [browser_record]}) == typing_process_entry_index({"recent_entries": [browser_record]})
    assert cli.typing_recent_record_brief(
        browser_record,
        "2026-01-01T10:05:00Z",
        effective_entries["browser-natural"],
    ) == typing_recent_record_brief(
        browser_record,
        "2026-01-01T10:05:00Z",
        effective_entries["browser-natural"],
    )
    assert cli.typing_latest_record([browser_record]) == typing_latest_record([browser_record])
    assert cli.typing_browser_input_recency(
        [browser_record],
        "2026-01-01T10:05:00Z",
        effective_entries,
    ) == typing_browser_input_recency(
        [browser_record],
        "2026-01-01T10:05:00Z",
        effective_entries,
    )
    awareness_kwargs = {
        "source_adapter": "browser_ai_transcript",
        "status": "captured",
        "gate": {"decision": "allow"},
        "text_payload": {"captured": True, "text_sha256": "sha256:text", "text_length": 12},
        "project_id": "abyss-machine",
        "project_binding": {"basis": "project_root_match"},
        "recipient": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt", "provider": "OpenAI", "product": "ChatGPT"},
        "task_binding": "project_or_surface_context",
        "context_anchor": {"kind": "ai_counterpart", "id": "ai:openai:chatgpt"},
        "interaction": {"kind": "browser_ai_page", "id": "browser-ai-page:fixture"},
        "surface_kind": "browser",
    }
    assert cli.typing_causal_awareness_for_event(**awareness_kwargs) == typing_causal_awareness_for_event(**awareness_kwargs)


def test_browser_metadata_contracts_avoid_private_browser_storage_claims() -> None:
    extension = browser_extension_message_metadata(
        {
            "browser_name": "firefox",
            "event_kind": "committed_text",
            "field": {"safe": True, "kind": "textarea", "type": "text"},
            "url": "https://example.test/path",
        },
        extension_id="fixture-extension",
        native_host="fixture.native.host",
    )

    assert extension["browser"]["adapter"] == "browser_extension_explicit"
    assert extension["browser"]["field_safe"] is True
    assert extension["browser"]["form_values_captured"] is False
    assert extension["browser"]["cookies_captured"] is False
    assert extension["browser"]["local_storage_captured"] is False
    assert extension["browser"]["key_events_captured"] is False

    fingerprint = browser_title_fingerprint("ChatGPT \u2014 Mozilla Firefox")
    assert fingerprint == {
        "title_present": True,
        "title_sha256": hashlib.sha256("ChatGPT".encode("utf-8", errors="replace")).hexdigest(),
        "title_stored": False,
    }


def test_browser_context_inference_contract_matches_safe_recent_atspi_path() -> None:
    latest = {
        "generated_at": "2026-06-26T00:00:30+00:00",
        "captures": [
            _browser_capture_item(
                url="https://example.test/project?ref=docs#frag",
                captured_at="2026-06-26T00:00:00+00:00",
                path="0.1.2",
            )
        ],
    }

    assert atspi_paths_match("0.1.2.3", None, "0.1.2") is True
    assert atspi_paths_match(None, "9.0.1", "0.1.2") is False
    assert browser_content_record_url(latest["captures"][0]["record"]) == "https://example.test/project?ref=docs#frag"
    assert browser_context_max_age_sec({"browser_context_inference_max_age_sec": 5}) == 30
    assert browser_context_max_age_sec({"browser_context_inference_max_age_sec": 9999}) == 3600

    result = browser_context_from_recent_captures(
        latest,
        "0.1.2.3",
        None,
        max_age_sec=900,
        reference_at="2026-06-26T00:00:30+00:00",
    )

    assert result["ok"] is True
    assert result["status"] == "matched"
    assert result["basis"] == "recent_nervous_browser_content_atspi_path"
    assert result["url"] == "https://example.test/project?ref=docs#frag"
    assert result["age_sec"] == 30.0
    assert result["query_present"] is True
    assert result["fragment_present"] is True
    assert result["raw_url_omitted"] is True


def test_browser_context_inference_rejects_sensitive_noise_and_ambiguous_fallback() -> None:
    sensitive = _browser_capture_item(
        url="https://example.test/login",
        path="0.1.2",
        classification="skipped",
        web_class="login_sensitive",
        skipped_text=True,
    )
    noise = _browser_capture_item(
        url="about:preferences",
        path="0.1.2",
        classification="noise",
        web_class="browser_internal",
    )
    latest = {
        "generated_at": "2026-06-26T00:00:30+00:00",
        "captures": [sensitive, noise],
    }

    assert browser_context_safe_candidate(
        sensitive,
        latest,
        basis="recent_nervous_browser_content_atspi_path",
        reference_at="2026-06-26T00:00:30+00:00",
    ) is None
    assert browser_context_safe_candidate(
        noise,
        latest,
        basis="recent_nervous_browser_content_atspi_path",
        reference_at="2026-06-26T00:00:30+00:00",
    ) is None

    ambiguous_latest = {
        "generated_at": "2026-06-26T00:00:30+00:00",
        "captures": [
            _browser_capture_item(url="https://example.test/a", path="4.0.1", focused=True),
            _browser_capture_item(url="https://example.test/b", path="5.0.1", focused=True),
        ],
    }
    ambiguous = browser_context_from_recent_captures(
        ambiguous_latest,
        "9.9.9",
        None,
        max_age_sec=900,
        reference_at="2026-06-26T00:00:30+00:00",
        allow_attention_fallback=True,
    )

    assert ambiguous["ok"] is False
    assert ambiguous["status"] == "no_safe_recent_match"
    assert ambiguous["attention_fallback_candidates"] == 2
    assert ambiguous["attention_fallback_status"] == "ambiguous_or_absent"


def test_cli_browser_context_inference_delegates_latest_read_to_module(monkeypatch) -> None:
    from abyss_machine import cli

    latest = {
        "generated_at": "2026-06-26T00:00:30+00:00",
        "captures": [_browser_capture_item(captured_at="2026-06-26T00:00:00+00:00", path="0.1.2")],
    }
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T00:00:30+00:00")
    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))

    actual = cli.typing_browser_context_from_recent_atspi_path(
        "0.1.2.3",
        None,
        {"browser_context_inference_max_age_sec": 900},
        allow_attention_fallback=True,
    )
    expected = browser_context_from_recent_captures(
        latest,
        "0.1.2.3",
        None,
        max_age_sec=900,
        reference_at="2026-06-26T00:00:30+00:00",
        allow_attention_fallback=True,
        schema_prefix=cli.SCHEMA_PREFIX,
    )

    assert actual == expected
    assert cli.typing_browser_context_safe_candidate(
        latest["captures"][0],
        latest,
        source_path="0.1.2.3",
        capture_path="0.1.2",
        basis="recent_nervous_browser_content_atspi_path",
    )["url"] == "https://example.test/project"


def test_focused_browser_selftest_summaries_are_public_safe_contracts() -> None:
    text = "Abyss focused browser proof"
    text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    event = {
        "event_id": "evt-focused",
        "generated_at": "2026-06-26T00:00:00Z",
        "status": "captured",
        "source_adapter": "atspi_focused_text_snapshot",
        "capture_gate": {
            "decision": "allow_text",
            "confidence": "focused_browser_safe_url_allowed",
        },
        "text": {
            "text_length": len(text),
            "text_chars_stored": len(text),
            "text_sha256": text_sha,
        },
        "context": {
            "app": {"text": "Firefox"},
            "window_title": {"text": "Abyss focused browser safe input probe"},
            "url": {"text": "http://127.0.0.1:12345/index.html"},
        },
        "metadata": {
            "atspi": {
                "safe_route": "browser_safe_url",
                "browser_safe_url": True,
            },
        },
        "causal_context": {
            "recipient": {"kind": "browser"},
            "task": {"binding": "selftest"},
        },
    }
    candidate = {
        "app": "Firefox",
        "window_title": "Abyss focused browser safe input probe",
        "role": "entry",
        "url": "http://127.0.0.1:12345/index.html",
        "document_title": "Abyss focused browser safe input probe",
        "content_type": "text/html",
        "atspi_path": "0.1.2",
        "document_path": "0.1.2",
        "text_role": True,
        "text_read_allowed": True,
        "text_length": len(text),
        "text": text,
        "capture_gate_decision": "allow_text",
        "capture_gate": {"confidence": "focused_browser_safe_url_allowed"},
        "safe_route": "browser_safe_url",
        "safe_route_allowed": True,
        "browser_safe_url": True,
        "sensitive_context": False,
        "sensitive_state_override": {"allowed": True, "stores_extra_text": False},
        "sensitive_matches": [],
    }

    event_summary = focused_browser_event_summary(event)
    candidate_summary = focused_browser_candidate_summary(candidate, text_sha)

    assert event_summary == {
        "event_id": "evt-focused",
        "generated_at": "2026-06-26T00:00:00Z",
        "status": "captured",
        "source_adapter": "atspi_focused_text_snapshot",
        "capture_gate_decision": "allow_text",
        "capture_gate_confidence": "focused_browser_safe_url_allowed",
        "text_length": len(text),
        "text_chars_stored": len(text),
        "text_sha256": text_sha,
        "app": "Firefox",
        "window_title": "Abyss focused browser safe input probe",
        "url": "http://127.0.0.1:12345/index.html",
        "safe_route": "browser_safe_url",
        "browser_safe_url": True,
        "recipient_kind": "browser",
        "task_binding": "selftest",
    }
    assert candidate_summary["text_sha256"] == text_sha
    assert candidate_summary["expected_text_match"] is True
    assert candidate_summary["capture_gate_confidence"] == "focused_browser_safe_url_allowed"
    assert candidate_summary["safe_route"] == "browser_safe_url"
    assert candidate_summary["browser_safe_url"] is True
    assert "text" not in candidate_summary


def test_cli_focused_browser_summaries_delegate_to_module_contract() -> None:
    from abyss_machine import cli

    candidate = {
        "app": "Firefox",
        "text": "focused text",
        "text_length": 12,
        "capture_gate": {"confidence": "focused_browser_safe_url_allowed"},
    }
    expected_sha = hashlib.sha256("focused text".encode("utf-8", errors="replace")).hexdigest()
    event = {
        "event_id": "evt",
        "capture_gate": {"decision": "allow_text"},
        "text": {"text_sha256": expected_sha},
    }

    assert cli.typing_focused_browser_candidate_summary(candidate, expected_sha) == focused_browser_candidate_summary(
        candidate,
        expected_sha,
    )
    assert cli.typing_focused_browser_event_summary(event) == focused_browser_event_summary(event)


def test_browser_privacy_record_summary_is_public_safe_contract() -> None:
    text = "private login probe text"
    text_sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    record = {
        "event_id": "evt-browser-privacy",
        "generated_at": "2026-06-26T00:00:00Z",
        "status": "metadata_only",
        "source_adapter": "atspi_text_changed_event",
        "capture_gate": {
            "decision": "metadata_only",
            "confidence": "login_url_metadata_only",
        },
        "text": {
            "metadata_only_reason": "sensitive_browser_url",
            "text_length": len(text),
            "text_chars_stored": 0,
            "text_sha256": text_sha,
            "text": text,
        },
        "context": {
            "app": {"text": "Firefox"},
            "window_title": {"text": "Example Login"},
            "url": {"text": "https://example.test/login"},
        },
        "causal_context": {
            "recipient": {"kind": "browser"},
            "task": {"binding": "browser_privacy_selftest"},
        },
        "metadata": {
            "atspi": {
                "role": "entry",
                "name": "Password",
                "source_path": "0.1.2",
                "document_path": "0.1",
                "content_type": "text/html",
                "gate_decision": "metadata_only",
                "text_read": False,
                "safe_route": None,
                "browser_safe_url": False,
            },
        },
    }

    summary = browser_privacy_record_summary(record, text_sha)

    assert summary == {
        "event_id": "evt-browser-privacy",
        "generated_at": "2026-06-26T00:00:00Z",
        "status": "metadata_only",
        "source_adapter": "atspi_text_changed_event",
        "capture_gate_decision": "metadata_only",
        "capture_gate_confidence": "login_url_metadata_only",
        "metadata_only_reason": "sensitive_browser_url",
        "text_length": len(text),
        "text_chars_stored": 0,
        "text_sha256": text_sha,
        "text_value_present": True,
        "text_sha256_matches_probe": True,
        "app": "Firefox",
        "window_title": "Example Login",
        "url": "https://example.test/login",
        "recipient_kind": "browser",
        "task_binding": "browser_privacy_selftest",
        "atspi": {
            "role": "entry",
            "name": "Password",
            "source_path": "0.1.2",
            "document_path": "0.1",
            "content_type": "text/html",
            "gate_decision": "metadata_only",
            "text_read": False,
            "safe_route": None,
            "browser_safe_url": False,
        },
    }
    assert "text" not in summary
    assert browser_privacy_record_summary(None, text_sha) is None


def test_cli_browser_privacy_record_summary_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    record = {
        "event_id": "evt",
        "capture_gate": {"decision": "metadata_only"},
        "text": {"text_sha256": "abc", "text": "raw text stays out of summary"},
    }

    assert cli.typing_browser_privacy_record_summary(record, "abc") == browser_privacy_record_summary(record, "abc")


def test_codex_prompt_summaries_are_module_owned_public_safe_contracts() -> None:
    reference_at = "2026-06-26T00:00:30Z"
    live = {
        "event_id": "evt-live",
        "generated_at": "2026-06-26T00:00:00Z",
        "source_adapter": "codex_user_prompt_submit",
        "status": "captured",
        "capture_gate": {"decision": "allow_text"},
        "session_id": "session-live",
        "turn_id": "turn-live",
        "metadata": {
            "codex": {"raw_timestamp": "2026-06-26T00:00:10Z"},
            "file": {"path": "/work/abyss-machine"},
        },
        "text": {
            "text_length": 31,
            "text_chars_stored": 31,
            "text": "raw prompt must not leave summary",
        },
    }
    selftest = {
        "event_id": "evt-selftest",
        "generated_at": "2026-06-26T00:00:05Z",
        "source_adapter": "codex_user_prompt_submit",
        "status": "captured",
        "metadata": {
            "codex": {
                "session_id": "codex-hook-selftest",
                "turn_id": "codex-hook-selftest-turn",
                "raw_timestamp": "2026-06-26T00:00:06Z",
            },
        },
        "text": {"text_length": 8, "text_chars_stored": 8},
    }
    tail_fresh = {
        "event_id": "evt-tail",
        "generated_at": "2026-06-26T00:00:03Z",
        "source_adapter": "codex_session_jsonl_prompt_tail",
        "status": "metadata_only",
        "metadata": {"codex": {"raw_timestamp": "2026-06-26T00:00:20Z"}},
        "text": {"text_length": 17, "text_chars_stored": 0},
    }
    tail_stale = {
        "event_id": "evt-tail-stale",
        "generated_at": "2026-06-25T00:00:00Z",
        "source_adapter": "codex_session_jsonl_prompt_tail",
        "status": "metadata_only",
    }

    event_summary = codex_prompt_event_summary(live, reference_at)
    recent_summary = codex_recent_prompt_summary([live, selftest, tail_fresh], reference_at)
    tail_summary = codex_session_tail_recent_prompt_summary([tail_stale, tail_fresh, live], reference_at)

    assert event_summary == {
        "event_id": "evt-live",
        "generated_at": "2026-06-26T00:00:00Z",
        "observed_at": "2026-06-26T00:00:00Z",
        "raw_timestamp": "2026-06-26T00:00:10Z",
        "prompt_at": "2026-06-26T00:00:10Z",
        "prompt_age_sec": 20.0,
        "status": "captured",
        "capture_gate_decision": "allow_text",
        "session_id": "session-live",
        "turn_id": "turn-live",
        "cwd": "/work/abyss-machine",
        "text_length": 31,
        "text_chars_stored": 31,
        "selftest": False,
    }
    assert "text" not in event_summary
    assert codex_record_is_selftest(selftest) is True
    assert codex_record_is_selftest(live) is False
    assert codex_prompt_time(live).isoformat() == "2026-06-26T00:00:10+00:00"
    assert recent_summary["recent_records"] == 2
    assert recent_summary["live_prompt_records"] == 1
    assert recent_summary["selftest_records"] == 1
    assert recent_summary["latest_live_prompt"]["event_id"] == "evt-live"
    assert recent_summary["latest_selftest_prompt"]["selftest"] is True
    assert tail_summary["recent_records"] == 2
    assert tail_summary["live_prompt_records"] == 1
    assert tail_summary["backfilled_or_stale_records"] == 1
    assert tail_summary["latest_live_prompt"]["event_id"] == "evt-tail"
    assert codex_prompt_event_summary(None, reference_at) is None


def test_cli_codex_prompt_summaries_delegate_to_module_contracts() -> None:
    from abyss_machine import cli

    reference_at = "2026-06-26T00:00:30Z"
    record = {
        "event_id": "evt",
        "generated_at": "2026-06-26T00:00:00Z",
        "source_adapter": "codex_user_prompt_submit",
        "metadata": {"codex": {"raw_timestamp": "2026-06-26T00:00:10Z"}},
        "text": {"text_length": 4, "text_chars_stored": 4, "text": "raw"},
    }
    tail = {
        "event_id": "tail",
        "generated_at": "2026-06-26T00:00:05Z",
        "source_adapter": "codex_session_jsonl_prompt_tail",
    }

    assert cli.typing_codex_record_is_selftest(record) == codex_record_is_selftest(record)
    assert cli.typing_codex_prompt_event_summary(record, reference_at) == codex_prompt_event_summary(record, reference_at)
    assert cli.typing_codex_prompt_time(record) == codex_prompt_time(record)
    assert cli.typing_codex_recent_prompt_summary([record], reference_at) == codex_recent_prompt_summary([record], reference_at)
    assert cli.typing_codex_session_tail_recent_prompt_summary([tail], reference_at) == codex_session_tail_recent_prompt_summary([tail], reference_at)


def test_codex_prompt_submit_coverage_prefers_native_hook_when_selftest_ok() -> None:
    latest_live = {"event_id": "evt-live", "selftest": False}
    latest_selftest = {"event_id": "evt-selftest", "selftest": True}
    coverage = codex_prompt_submit_coverage(
        codex_prompt_summary={
            "recent_records": "2",
            "live_prompt_records": 1,
            "selftest_records": 1,
            "live_prompt_observed": True,
            "selftest_only": False,
            "latest_live_prompt": latest_live,
            "latest_selftest_prompt": latest_selftest,
        },
        codex_session_tail_summary={"recent_records": 0, "live_prompt_observed": False},
        codex_selftest_ok=True,
        codex_session_tail_latest={"status": "processed"},
    )

    assert coverage == {
        "covered": True,
        "effective_covered": True,
        "recent_records": 2,
        "live_prompt_records": 1,
        "selftest_records": 1,
        "live_prompt_observed": True,
        "selftest_only": False,
        "selftest_ok": True,
        "latest_live_prompt": latest_live,
        "latest_selftest_prompt": latest_selftest,
        "fallback_adapter": "codex_session_jsonl_prompt_tail",
        "fallback_observed": False,
        "fallback_recent_records": 0,
        "fallback_latest_prompt": None,
        "fallback_latest_status": "processed",
    }


def test_codex_prompt_submit_assessment_reports_tail_fallback_and_native_gap() -> None:
    fallback_prompt = {"event_id": "evt-tail", "selftest": False}
    assessment = codex_prompt_submit_route_assessment(
        configured_adapters=["codex_user_prompt_submit"],
        by_adapter={"codex_session_jsonl_prompt_tail": 1},
        codex_prompt_summary={
            "recent_records": 0,
            "live_prompt_records": 0,
            "selftest_records": 0,
            "live_prompt_observed": False,
            "selftest_only": False,
        },
        codex_session_tail_summary={
            "recent_records": 1,
            "live_prompt_records": 1,
            "live_prompt_observed": True,
            "latest_live_prompt": fallback_prompt,
        },
        codex_selftest_ok=True,
        codex_hook_selftest_error=None,
        codex_session_tail_latest={"status": "processed"},
    )

    assert assessment["coverage"]["covered"] is False
    assert assessment["coverage"]["effective_covered"] is True
    assert assessment["coverage"]["fallback_latest_prompt"] == fallback_prompt
    assert assessment["route_notes"] == [
        {
            "key": "codex_native_hook_not_observed_using_session_tail",
            "level": "info",
            "message": "native Codex UserPromptSubmit has no non-selftest prompt in the recent window; Codex input is covered by raw JSONL near-live tail fallback",
            "native_selftest_ok": True,
            "fallback_recent_records": 1,
            "fallback_latest_prompt": fallback_prompt,
            "fallback_latest_status": "processed",
        }
    ]
    assert assessment["gaps"] == [
        {
            "key": "codex_user_prompt_submit_not_observed_recently",
            "level": "info",
            "message": "Codex UserPromptSubmit adapter has not produced recent event records",
            "latest_selftest_ok": True,
            "latest_selftest_error": None,
        }
    ]


def test_codex_prompt_submit_assessment_keeps_selftest_only_as_watch_gap() -> None:
    latest_selftest = {"event_id": "evt-selftest", "selftest": True}
    assessment = codex_prompt_submit_route_assessment(
        configured_adapters=["codex_user_prompt_submit"],
        by_adapter={"codex_user_prompt_submit": 1},
        codex_prompt_summary={
            "recent_records": 1,
            "live_prompt_records": 0,
            "selftest_records": 1,
            "live_prompt_observed": False,
            "selftest_only": True,
            "latest_selftest_prompt": latest_selftest,
        },
        codex_session_tail_summary={"recent_records": 0, "live_prompt_observed": False},
        codex_selftest_ok=True,
        codex_hook_selftest_error="fixture-selftest-error",
        codex_session_tail_latest=None,
    )

    assert assessment["coverage"]["effective_covered"] is False
    assert assessment["route_notes"] == []
    assert assessment["gaps"] == [
        {
            "key": "codex_user_prompt_submit_selftest_only",
            "level": "watch",
            "message": "recent Codex UserPromptSubmit evidence is selftest-only; no non-selftest Codex prompt was observed in the coverage window",
            "recent_records": 1,
            "selftest_records": 1,
            "latest_selftest_prompt": latest_selftest,
            "latest_selftest_error": "fixture-selftest-error",
        }
    ]


def test_cli_codex_prompt_submit_assessment_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    prompt_summary = {"recent_records": 0, "live_prompt_observed": False}
    tail_summary = {"recent_records": 1, "live_prompt_observed": True}
    latest = {"status": "processed"}

    assert cli.typing_codex_prompt_submit_route_assessment(
        configured_adapters=["codex_user_prompt_submit"],
        by_adapter={"codex_session_jsonl_prompt_tail": 1},
        codex_prompt_summary=prompt_summary,
        codex_session_tail_summary=tail_summary,
        codex_selftest_ok=False,
        codex_hook_selftest_error="missing selftest",
        codex_session_tail_latest=latest,
    ) == codex_prompt_submit_route_assessment(
        configured_adapters=["codex_user_prompt_submit"],
        by_adapter={"codex_session_jsonl_prompt_tail": 1},
        codex_prompt_summary=prompt_summary,
        codex_session_tail_summary=tail_summary,
        codex_selftest_ok=False,
        codex_hook_selftest_error="missing selftest",
        codex_session_tail_latest=latest,
    )


def test_typing_coverage_status_decision_classifies_full_and_fallback_coverage() -> None:
    covered = typing_coverage_status_decision(
        record_count=4,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": True},
        },
        gaps=[],
        observed_adapters=["manual_cli_stdin", "codex_user_prompt_submit"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.5,
        live_input_count=2,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )
    fallback = typing_coverage_status_decision(
        record_count=4,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": False, "effective_covered": True},
            "browser_explicit_webextension": {"covered": True},
        },
        gaps=[],
        observed_adapters=["manual_cli_stdin", "codex_session_jsonl_prompt_tail", "browser_extension_explicit"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.34,
        live_input_count=3,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )

    assert covered["status"] == "covered"
    assert covered["coverage_routes"] == 2
    assert covered["effective_coverage_routes"] == 2
    assert covered["coverage_route_total"] == 2
    assert covered["watch_gaps"] is False
    assert fallback["status"] == "covered_with_fallbacks"
    assert fallback["coverage_routes"] == 2
    assert fallback["effective_coverage_routes"] == 3


def test_typing_coverage_status_decision_keeps_gaps_and_narrowness_visible() -> None:
    watch_gap = typing_coverage_status_decision(
        record_count=4,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": True},
        },
        gaps=[{"key": "codex_user_prompt_submit_selftest_only", "level": "watch"}],
        observed_adapters=["manual_cli_stdin", "codex_user_prompt_submit"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.5,
        live_input_count=2,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )
    narrow = typing_coverage_status_decision(
        record_count=10,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": False},
            "browser_explicit_webextension": {"covered": False},
        },
        gaps=[],
        observed_adapters=["manual_cli_stdin"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.9,
        live_input_count=10,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )
    empty = typing_coverage_status_decision(
        record_count=0,
        coverage_routes={"manual_cli": {"covered": True}},
        gaps=[{"key": "no_recent_records", "level": "watch"}],
        observed_adapters=[],
        dominant_adapter=None,
        dominant_ratio=0.0,
        live_input_count=0,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )

    assert watch_gap["status"] == "manual_only"
    assert watch_gap["watch_gaps"] is True
    assert narrow["status"] == "narrow"
    assert empty["status"] == "empty"


def test_typing_coverage_status_decision_classifies_broad_partial_and_manual_only() -> None:
    broad_partial = typing_coverage_status_decision(
        record_count=6,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": True},
            "browser_explicit_webextension": {"covered": True},
            "editor_committed_text": {"covered": False},
            "saved_text_scan": {"covered": False},
        },
        gaps=[{"key": "editor_extension_not_observed_recently", "level": "info"}],
        observed_adapters=["manual_cli_stdin", "codex_user_prompt_submit", "browser_extension_explicit"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.4,
        live_input_count=6,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )
    manual_only = typing_coverage_status_decision(
        record_count=3,
        coverage_routes={
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": False},
            "browser_explicit_webextension": {"covered": False},
        },
        gaps=[],
        observed_adapters=["manual_cli_stdin", "saved_text_snapshot"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.6,
        live_input_count=1,
        browser_release_gap=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
    )
    release_fallback = typing_coverage_status_decision(
        record_count=5,
        coverage_routes={
            "manual_cli": {"covered": True},
            "browser_explicit_webextension": {"covered": False},
        },
        gaps=[],
        observed_adapters=["manual_cli_stdin", "atspi_text_changed_event"],
        dominant_adapter="manual_cli_stdin",
        dominant_ratio=0.5,
        live_input_count=2,
        browser_release_gap=True,
        browser_temporary_proof_ok=True,
        browser_atspi_fallback_ok=True,
    )

    assert broad_partial["status"] == "broad_partial"
    assert manual_only["status"] == "manual_only"
    assert release_fallback["status"] == "covered_with_fallbacks"
    assert release_fallback["browser_release_fallback_ok"] is True


def test_cli_typing_coverage_status_decision_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "record_count": 4,
        "coverage_routes": {
            "manual_cli": {"covered": True},
            "codex_prompt_submit": {"covered": False, "effective_covered": True},
        },
        "gaps": [],
        "observed_adapters": ["manual_cli_stdin", "codex_session_jsonl_prompt_tail"],
        "dominant_adapter": "manual_cli_stdin",
        "dominant_ratio": 0.5,
        "live_input_count": 2,
        "browser_release_gap": False,
        "browser_temporary_proof_ok": False,
        "browser_atspi_fallback_ok": False,
    }

    assert cli.typing_coverage_status_decision(**kwargs) == typing_coverage_status_decision(**kwargs)


def test_typing_coverage_document_from_records_is_module_owned_with_cli_snapshot_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T10:03:00Z"
    policy = {
        "ok": True,
        **_capture_gate_defaults(),
        "capture": {
            "allowed_adapters": [
                "manual_cli_args",
                "browser_extension_explicit",
                "codex_user_prompt_submit",
                "zsh_preexec",
            ],
            "diagnostic_adapters": ["atspi_focused_text_snapshot"],
        },
        "focused_snapshot": {"enabled": True, "text_capture_enabled": True, "mode": "safe"},
    }
    records = [
        {
            "event_id": "manual-1",
            "generated_at": "2026-06-26T10:00:00Z",
            "source_adapter": "manual_cli_args",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "manual_cli_allowed"},
            "text": {"captured": True, "text_length": 12, "text_sha256": "sha256:manual"},
            "policy": {"capture_gate_required": True, "raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
            "causal_context": {
                "where": {"kind": "cli", "project": {"id": "abyss-machine", "kind": "repo"}},
                "recipient": {"kind": "typing_cli", "id": "manual_cli"},
                "task": {"binding": "project_or_surface_context"},
            },
        },
        {
            "event_id": "browser-1",
            "generated_at": "2026-06-26T10:02:00Z",
            "source_adapter": "browser_extension_explicit",
            "status": "captured",
            "capture_gate": {"decision": "allow_text", "confidence": "browser_url_and_field_allowed"},
            "text": {"captured": True, "text_length": 18, "text_sha256": "sha256:browser"},
            "context": {
                "app": {"text": "Firefox"},
                "window_title": {"text": "ChatGPT"},
                "url": {"text": "https://chatgpt.com/c/example?model=gpt"},
            },
            "policy": {"capture_gate_required": True, "raw_keylogging": False, "password_fields_captured": False, "automatic_action": False},
            "causal_context": {
                "where": {
                    "kind": "browser",
                    "app": "Firefox",
                    "window_title": "ChatGPT",
                    "url": "https://chatgpt.com/c/example?model=gpt",
                    "project": {"id": "abyss-machine", "kind": "repo"},
                },
                "recipient": {"kind": "browser_extension", "id": "extension"},
                "task": {"binding": "project_or_surface_context"},
            },
        },
    ]
    snapshot = {
        "capture_gate_policy": policy["capture_gate"],
        "atspi_text_events_policy": {"browser_recency_max_age_sec": 900},
        "browser_context_inference": {"ok": True, "status": "passed"},
        "focused_latest": {"generated_at": generated_at, "status": "skipped_no_focused_editable_text", "candidate": {"app": "Firefox"}},
        "atspi_events_latest": {"generated_at": generated_at, "status": "running", "summary": {"errors": 0}},
        "editor_callback_selftest_latest": {"generated_at": generated_at, "ok": True, "status": "passed"},
        "browser_extension_latest": {"generated_at": generated_at, "ok": True, "status": "ready"},
        "browser_ai_transcript_latest": {"generated_at": generated_at, "ok": True, "status": "ready"},
        "browser_ai_transcript_selftest_latest": {
            "generated_at": generated_at,
            "ok": True,
            "status": "passed",
            "safe": {
                "source_adapter": "browser_ai_transcript",
                "capture_gate_decision": "allow_text",
                "recipient": {"id": "ai:google:gemini"},
            },
        },
        "browser_webextension_selftest_latest": {
            "generated_at": generated_at,
            "ok": True,
            "status": "passed",
            "event": {"generated_at": generated_at},
        },
        "browser_context_selftest_latest": {
            "generated_at": generated_at,
            "ok": True,
            "status": "passed",
            "policy": {
                "raw_keylogging": False,
                "password_fields_captured": False,
                "form_values_captured": False,
                "uses_browser_content_capture": True,
                "uses_atspi_document_path_inference": True,
            },
        },
        "generic_gui_selftest_latest": {"generated_at": generated_at, "ok": False, "status": "not_run"},
        "browser_privacy_selftest_latest": {"generated_at": generated_at, "ok": True, "status": "passed"},
        "privacy_selftest_latest": {"generated_at": generated_at, "ok": True, "status": "passed"},
        "zsh_hook_selftest": {"generated_at": generated_at, "ok": True, "status": "passed", "summary": {"event_detected": True}},
        "codex_hook_status": {
            "generated_at": generated_at,
            "ok": True,
            "status": "ready",
            "recent_prompt_evidence": {"recent_records": 1, "live_prompt_observed": True},
            "fallback_prompt_evidence": {"recent_records": 0, "live_prompt_observed": False},
        },
        "codex_hook_selftest": {"generated_at": generated_at, "ok": True, "status": "passed", "summary": {"event_detected": True}},
        "codex_session_tail_latest": {"generated_at": generated_at, "status": "processed"},
        "browser_release_probe": {
            "generated_at": generated_at,
            "ok": True,
            "status": "active",
            "activation": {"active_profiles": 1},
            "profiles": [{"profile": "default", "active": True}],
        },
    }

    expected = typing_coverage_document_from_records(
        records,
        [],
        policy,
        latest=records[-1],
        generated_at=generated_at,
        coverage_snapshot=snapshot,
        version=cli.VERSION,
        home_path="/home/operator",
    )
    monkeypatch.setattr(cli.Path, "home", lambda: Path("/home/operator"))
    monkeypatch.setattr(cli, "typing_coverage_input_snapshot", lambda received_policy: snapshot)

    assert cli.typing_coverage_from_records(
        records,
        [],
        policy,
        latest=records[-1],
        generated_at=generated_at,
    ) == expected
    assert expected["schema"] == "abyss_machine_typing_coverage_v1"
    assert expected["coverage_routes"]["browser_explicit_webextension"]["covered"] is True
    assert expected["browser_input_recency"]["effective_status"] == "live_browser_text_recent"
    assert expected["browser_release_profile_status"]["active"] is True
    assert expected["policy"]["raw_keylogging"] is False


def test_typing_status_document_is_module_owned_with_cli_input_adapter(monkeypatch, tmp_path) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T11:00:00Z"
    latest_path = tmp_path / "typing" / "events" / "latest.json"
    latest_path.parent.mkdir(parents=True)
    latest_path.write_text("{}", encoding="utf-8")
    records = [
        {
            "event_id": "event-1",
            "status": "captured",
            "source_adapter": "manual_cli_args",
            "capture_gate": {"decision": "allow_text"},
            "causal_context": {
                "recipient": {"kind": "typing_cli"},
                "where": {"project": {"id": "abyss-machine"}},
            },
        }
    ]
    policy = {
        "ok": True,
        "mode": "safe_committed_text",
        "enabled": True,
        "capture": {
            "raw_keylogging": False,
            "requires_committed_text": True,
            "password_fields_captured": False,
        },
    }
    latest = {"ok": True, "status": "captured", "source_adapter": "manual_cli_args", "capture_gate": {"decision": "allow_text"}}
    coverage = {
        "status": "covered",
        "summary": {
            "gaps": 0,
            "route_notes": 1,
            "saved_text_records": 0,
            "saved_text_ratio": 0.0,
            "live_input_records": 1,
            "live_observed_adapters": ["manual_cli_args"],
            "live_dominant_adapter": "manual_cli_args",
            "live_dominant_ratio": 1.0,
            "browser_context_inference_status": "passed",
            "generic_gui_text_records": 0,
            "generic_gui_selftest_ok": False,
        },
        "by_capture_gate_decision": {"allow_text": 1},
        "zsh_hook": {"status": "ready", "selftest_ok": True},
        "codex_hook": {
            "status": "ready",
            "selftest_ok": True,
            "live_prompt_observed": True,
            "recent_prompt_evidence": {"live_prompt_records": 1, "selftest_records": 0},
            "fallback_prompt_observed": False,
            "fallback_prompt_evidence": {"recent_records": 0},
        },
        "browser_release_profile_status": {"status": "active"},
        "browser_extension_latest": {"status": "ready"},
        "browser_input_recency": {
            "effective_status": "live_browser_text_recent",
            "records": 1,
            "natural_records": 1,
            "natural_text_records": 1,
            "latest_any": {"age_sec": 30},
        },
        "browser_context_selftest_latest": {"ok": True, "status": "passed"},
        "coverage_routes": {"generic_gui_committed_text": {"latest_record": {"capture_gate_confidence": None}}},
        "atspi_text_events_latest": {"heartbeat_age_sec": 10, "last_event_age_sec": 20},
        "editor_extension_selftest_latest": {"ok": True, "status": "passed"},
        "editor_callback_selftest_latest": {"ok": True, "status": "passed"},
        "browser_atspi_selftest_latest": {"ok": True, "status": "passed", "firefox": {"profile_kind": "temporary"}, "policy": {"release_profile_mutated": False}},
        "browser_atspi_release_selftest_latest": {
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T10:59:30Z"},
            "firefox": {"profile_kind": "release_profile"},
        },
    }
    process = {
        "status": "processed",
        "summary": {
            "lanes": 1,
            "context_bound": 1,
            "missing_context_anchor": 0,
            "quality_gaps": 0,
            "fail_gaps": 0,
            "awareness_average_score": 1.0,
            "awareness_complete": 1,
            "awareness_guarded": 0,
            "awareness_incomplete": 0,
        },
        "awareness": {"top_gaps": {}, "axis_states": {}},
        "by_context_anchor_kind": {"project_root": 1},
    }
    browser_content = {"ok": True, "generated_at": generated_at, "summary": {"captures": 2, "text_records": 1}}
    status_inputs = {
        "gnome_accessibility": {"enabled": True},
        "nervous_processing": {"ok": True, "status": "ready", "summary": {"facts_ready": True, "index_ready": True}},
        "focused_snapshot": {"ok": True, "status": "ready", "summary": {"latest_generated_at": generated_at, "latest_age_sec": 5}},
        "saved_text_scan": {"ok": True, "status": "ready", "summary": {"latest_generated_at": generated_at, "latest_age_sec": 5}},
        "codex_session_tail": {"ok": True, "status": "processed", "summary": {"latest_generated_at": generated_at, "events": 1}},
        "editor_extension": {"ok": True, "status": "ready", "summary": {"activation_status": "active", "activation_age_sec": 5}},
        "nervous_refresh": {"ok": True, "status": "fresh", "summary": {"latest_generated_at": generated_at, "index_needed": False}},
    }
    paths = {"schema": "abyss_machine_typing_paths_v1", "commands": {"status": "abyss-machine typing status --json"}}

    expected = typing_status_document(
        records,
        [],
        [],
        policy,
        latest,
        coverage,
        process,
        generated_at=generated_at,
        coverage_limit=500,
        latest_exists=True,
        browser_content_latest=browser_content,
        browser_content_error=None,
        browser_content_latest_path="/tmp/browser-content/latest.json",
        paths=paths,
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        **status_inputs,
    )

    monkeypatch.setattr(cli, "ensure_typing_docs", lambda: [])
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: policy)
    monkeypatch.setattr(cli, "typing_latest", lambda: latest)
    monkeypatch.setattr(cli, "typing_records", lambda limit: (records, []))
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "typing_coverage_from_records", lambda *args, **kwargs: coverage)
    monkeypatch.setattr(cli, "typing_process_from_records", lambda *args, **kwargs: process)
    monkeypatch.setattr(cli, "typing_gnome_accessibility_status", lambda: status_inputs["gnome_accessibility"])
    monkeypatch.setattr(cli, "typing_nervous_processing_status", lambda: status_inputs["nervous_processing"])
    monkeypatch.setattr(cli, "typing_focused_snapshot_latest_status", lambda: status_inputs["focused_snapshot"])
    monkeypatch.setattr(cli, "typing_saved_text_scan_latest_status", lambda: status_inputs["saved_text_scan"])
    monkeypatch.setattr(cli, "typing_codex_session_tail_latest_status", lambda: status_inputs["codex_session_tail"])
    monkeypatch.setattr(cli, "typing_editor_extension_latest_status", lambda: status_inputs["editor_extension"])
    monkeypatch.setattr(cli, "typing_nervous_refresh_latest_status", lambda: status_inputs["nervous_refresh"])
    monkeypatch.setattr(cli, "load_json_document", lambda path: (browser_content, None))
    monkeypatch.setattr(cli, "TYPING_EVENTS_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "NERVOUS_BROWSER_CONTENT_LATEST_PATH", Path("/tmp/browser-content/latest.json"))
    monkeypatch.setattr(cli, "typing_paths", lambda generated_at=None: paths)

    assert cli.typing_status() == expected
    assert expected["summary"]["recent_records"] == 1
    assert expected["summary"]["coverage_status"] == "covered"
    assert expected["summary"]["browser_content_capture_captures"] == 2
    assert expected["policy"]["raw_keylogging"] is False
    assert expected["paths"] == paths


def test_typing_validate_document_is_module_owned_with_cli_input_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T12:00:00Z"
    checks = [
        {"level": "ok", "key": "typing_policy_schema", "message": "typing policy schema is valid"},
        {"level": "warn", "key": "nervous_refresh", "message": "nervous refresh is stale"},
    ]
    paths = {
        "schema": "abyss_machine_typing_paths_v1",
        "commands": {"validate": "abyss-machine typing validate --json"},
    }
    expected = typing_validate_document(
        checks,
        strict=True,
        generated_at=generated_at,
        records_checked=17,
        paths=paths,
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
    )

    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    monkeypatch.setattr(cli, "typing_paths", lambda generated_at=None: paths)

    assert cli.typing_validate_document_from_checks(
        checks,
        strict=True,
        records_checked=17,
    ) == expected
    assert expected["schema"] == "abyss_machine_typing_validate_v1"
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["ok"] is False
    assert expected["policy"]["read_only"] is True
    assert expected["non_claims"][0].startswith("This validates the safe intake surface")


def test_typing_validate_document_strict_and_fail_semantics() -> None:
    paths = {"schema": "abyss_machine_typing_paths_v1"}
    warn_checks = [{"level": "warn", "key": "optional", "message": "optional evidence missing"}]
    fail_checks = [{"level": "fail", "key": "contract", "message": "contract broken"}]

    non_strict_warn = typing_validate_document(
        warn_checks,
        strict=False,
        generated_at="2026-06-26T12:01:00Z",
        records_checked=3,
        paths=paths,
    )
    strict_warn = typing_validate_document(
        warn_checks,
        strict=True,
        generated_at="2026-06-26T12:01:00Z",
        records_checked=3,
        paths=paths,
    )
    fail_doc = typing_validate_document(
        fail_checks,
        strict=False,
        generated_at="2026-06-26T12:01:00Z",
        records_checked=3,
        paths=paths,
    )

    assert non_strict_warn["ok"] is True
    assert strict_warn["ok"] is False
    assert fail_doc["ok"] is False
    assert non_strict_warn["summary"]["status"] == "warn"
    assert fail_doc["summary"]["status"] == "fail"


def test_typing_end_to_end_document_is_module_owned_with_cli_input_adapter() -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T12:15:00Z"
    checks = [
        {"level": "ok", "key": "manual_input", "message": "manual input captured", "data": {"event_id": "evt-1"}},
        {"level": "warn", "key": "nervous_refresh", "message": "refresh skipped", "data": {"skipped": True}},
    ]
    artifacts = {
        "manual_input_stdin": {"ok": True, "event_id": "evt-1"},
        "nervous_refresh": {"skipped": True},
    }
    history_path = str(cli.TYPING_END_TO_END_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl")
    expected = typing_end_to_end_document(
        checks,
        strict=False,
        generated_at=generated_at,
        artifacts=artifacts,
        latest_path=str(cli.TYPING_END_TO_END_LATEST_PATH),
        history_path=history_path,
        skip_browser_atspi=True,
        skip_browser_webextension=False,
        skip_focused_browser=True,
        skip_browser_privacy=False,
        skip_editor_callback=True,
        refresh_nervous=False,
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
    )

    assert cli.typing_end_to_end_document_from_checks(
        checks,
        strict=False,
        generated_at=generated_at,
        artifacts=artifacts,
        skip_browser_atspi=True,
        skip_browser_webextension=False,
        skip_focused_browser=True,
        skip_browser_privacy=False,
        skip_editor_callback=True,
        refresh_nervous=False,
    ) == expected
    assert expected["schema"] == "abyss_machine_typing_end_to_end_v1"
    assert expected["ok"] is True
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["policy"]["read_only"] is False
    assert expected["policy"]["loopback_browser_probe_only"] is False
    assert expected["policy"]["temporary_browser_webextension_probe"] is True
    assert expected["policy"]["focused_browser_loopback_probe"] is False
    assert expected["policy"]["browser_privacy_loopback_probe"] is True
    assert expected["policy"]["live_editor_callback_probe"] is False
    assert expected["policy"]["refreshes_nervous_snapshot_index"] is False


def test_typing_browser_input_proof_summary_shapes_and_sorts_selftest_proofs() -> None:
    summary = typing_browser_input_proof_summary(
        browser_webextension_selftest_latest={
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T00:01:00Z"},
        },
        browser_atspi_selftest_latest={
            "ok": True,
            "status": "passed",
            "generated_at": "2026-06-25T23:59:00Z",
        },
        browser_atspi_release_selftest_latest={
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T00:02:00Z"},
            "firefox": {"profile_kind": "release_profile"},
            "policy": {"release_profile_mutated": True},
        },
        reference_at="2026-06-26T00:03:00Z",
    )

    assert summary["temporary_profile_selftest_ok"] is True
    assert summary["atspi_selftest_ok"] is True
    assert summary["atspi_release_selftest_ok"] is True
    assert [item["route"] for item in summary["proof_routes"]] == [
        "browser_atspi_release_selftest",
        "browser_webextension_selftest",
        "browser_atspi_selftest",
    ]
    assert summary["latest_proof"] == {
        "route": "browser_atspi_release_selftest",
        "generated_at": "2026-06-26T00:02:00Z",
        "age_sec": 60.0,
        "status": "passed",
        "profile_kind": "release_profile",
    }


def test_typing_browser_input_proof_summary_keeps_release_profile_gate_explicit() -> None:
    wrong_profile = typing_browser_input_proof_summary(
        browser_webextension_selftest_latest={"ok": False, "status": "failed"},
        browser_atspi_selftest_latest=None,
        browser_atspi_release_selftest_latest={
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T00:02:00Z"},
            "firefox": {"profile_kind": "temporary_profile"},
            "policy": {"release_profile_mutated": True},
        },
        reference_at="2026-06-26T00:03:00Z",
    )
    missing_mutation = typing_browser_input_proof_summary(
        browser_webextension_selftest_latest=None,
        browser_atspi_selftest_latest=None,
        browser_atspi_release_selftest_latest={
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T00:02:00Z"},
            "firefox": {"profile_kind": "release_profile"},
            "policy": {"release_profile_mutated": False},
        },
        reference_at="2026-06-26T00:03:00Z",
    )

    assert wrong_profile["atspi_release_selftest_ok"] is False
    assert wrong_profile["proof_routes"] == []
    assert wrong_profile["latest_proof"] is None
    assert missing_mutation["atspi_release_selftest_ok"] is False
    assert missing_mutation["proof_routes"] == []


def test_cli_typing_browser_input_proof_summary_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "browser_webextension_selftest_latest": {
            "ok": True,
            "status": "passed",
            "event": {"generated_at": "2026-06-26T00:01:00Z"},
        },
        "browser_atspi_selftest_latest": None,
        "browser_atspi_release_selftest_latest": None,
        "reference_at": "2026-06-26T00:03:00Z",
    }

    assert cli.typing_browser_input_proof_summary(**kwargs) == typing_browser_input_proof_summary(**kwargs)


def _browser_webextension_selftest_latest(
    *,
    source_adapter: str = "browser_extension_explicit",
    event_status: str = "captured",
    capture_gate_decision: str = "allow_text",
    capture_gate_confidence: str = "browser_url_and_field_allowed",
    text_length: int = 24,
    text_chars_stored: int = 24,
    recipient_kind: str = "browser_extension",
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    temporary_firefox_profile: bool = True,
    release_profile_mutated: bool = False,
    ok: bool = True,
    status: str = "passed",
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "event": {
            "source_adapter": source_adapter,
            "status": event_status,
            "capture_gate_decision": capture_gate_decision,
            "capture_gate_confidence": capture_gate_confidence,
            "text_length": text_length,
            "text_chars_stored": text_chars_stored,
            "recipient": {"kind": recipient_kind},
        },
        "policy": {
            "raw_keylogging": raw_keylogging,
            "password_fields_captured": password_fields_captured,
            "temporary_firefox_profile": temporary_firefox_profile,
            "release_profile_mutated": release_profile_mutated,
        },
    }


def test_typing_browser_webextension_selftest_validation_status_accepts_temporary_profile_route() -> None:
    status = typing_browser_webextension_selftest_validation_status(_browser_webextension_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["status"] == "passed"
    assert all(status["checks"].values())


def test_typing_browser_webextension_selftest_validation_status_rejects_route_and_policy_failures() -> None:
    cases = [
        ("failed_document", _browser_webextension_selftest_latest(ok=False), "document_passed"),
        ("wrong_source", _browser_webextension_selftest_latest(source_adapter="browser_ai_transcript"), "event_source_adapter"),
        ("not_captured", _browser_webextension_selftest_latest(event_status="filtered"), "event_status_captured"),
        ("metadata_only", _browser_webextension_selftest_latest(capture_gate_decision="metadata_only"), "event_capture_gate"),
        (
            "wrong_confidence",
            _browser_webextension_selftest_latest(capture_gate_confidence="browser_ai_transcript_known_ai_page_allowed"),
            "event_capture_confidence",
        ),
        ("truncated_text", _browser_webextension_selftest_latest(text_chars_stored=12), "event_text_stored"),
        ("wrong_recipient", _browser_webextension_selftest_latest(recipient_kind="ai_counterpart"), "recipient_kind"),
        ("raw_keylogging", _browser_webextension_selftest_latest(raw_keylogging=True), "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _browser_webextension_selftest_latest(password_fields_captured=True),
            "policy_password_fields_not_captured",
        ),
        (
            "release_profile",
            _browser_webextension_selftest_latest(temporary_firefox_profile=False),
            "policy_temporary_firefox_profile",
        ),
        (
            "mutated_release_profile",
            _browser_webextension_selftest_latest(release_profile_mutated=True),
            "policy_release_profile_not_mutated",
        ),
        ("missing_document", None, "document_passed"),
    ]

    for label, latest, failed_check in cases:
        status = typing_browser_webextension_selftest_validation_status(latest)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_browser_webextension_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _browser_webextension_selftest_latest()

    assert (
        cli.typing_browser_webextension_selftest_validation_status(latest)
        == typing_browser_webextension_selftest_validation_status(latest)
    )


def _browser_atspi_selftest_latest(
    *,
    release_profile: bool = False,
    source_adapter: str = "atspi_text_changed_event",
    event_status: str = "captured",
    capture_gate_decision: str = "allow_text",
    capture_gate_confidence: str = "atspi_browser_url_allowed",
    browser_app: bool = True,
    url_allowed: bool = True,
    text_length: int = 24,
    text_chars_stored: int = 24,
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    internet_access: bool = False,
    release_profile_mutated: bool | None = None,
    profile_kind: str = "release_profile",
    ok: bool = True,
    status: str = "passed",
) -> dict:
    policy = {
        "raw_keylogging": raw_keylogging,
        "password_fields_captured": password_fields_captured,
    }
    if release_profile:
        policy["release_profile_mutated"] = True if release_profile_mutated is None else release_profile_mutated
    else:
        policy["internet_access"] = internet_access
    payload = {
        "ok": ok,
        "status": status,
        "event": {
            "source_adapter": source_adapter,
            "status": event_status,
            "capture_gate_decision": capture_gate_decision,
            "capture_gate_confidence": capture_gate_confidence,
            "browser_app": browser_app,
            "url_allowed": url_allowed,
            "text_length": text_length,
            "text_chars_stored": text_chars_stored,
        },
        "policy": policy,
    }
    if release_profile:
        payload["firefox"] = {"profile_kind": profile_kind}
    return payload


def test_typing_browser_atspi_selftest_validation_status_accepts_temporary_browser_route() -> None:
    status = typing_browser_atspi_selftest_validation_status(_browser_atspi_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["release_profile"] is False
    assert status["status"] == "passed"
    assert all(status["checks"].values())


def test_typing_browser_atspi_selftest_validation_status_accepts_release_profile_route() -> None:
    status = typing_browser_atspi_selftest_validation_status(
        _browser_atspi_selftest_latest(release_profile=True),
        release_profile=True,
    )

    assert status["selftest_ok"] is True
    assert status["release_profile"] is True
    assert status["checks"]["firefox_release_profile"] is True
    assert status["checks"]["policy_release_profile_mutated"] is True


def test_typing_browser_atspi_selftest_validation_status_rejects_route_and_policy_failures() -> None:
    cases = [
        ("failed_document", _browser_atspi_selftest_latest(ok=False), {}, "document_passed"),
        ("wrong_source", _browser_atspi_selftest_latest(source_adapter="browser_extension_explicit"), {}, "event_source_adapter"),
        ("not_captured", _browser_atspi_selftest_latest(event_status="filtered"), {}, "event_status_captured"),
        ("metadata_only", _browser_atspi_selftest_latest(capture_gate_decision="metadata_only"), {}, "event_capture_gate"),
        (
            "wrong_confidence",
            _browser_atspi_selftest_latest(capture_gate_confidence="browser_url_and_field_allowed"),
            {},
            "event_capture_confidence",
        ),
        ("not_browser", _browser_atspi_selftest_latest(browser_app=False), {}, "event_browser_app"),
        ("url_denied", _browser_atspi_selftest_latest(url_allowed=False), {}, "event_url_allowed"),
        ("truncated_text", _browser_atspi_selftest_latest(text_chars_stored=12), {}, "event_text_stored"),
        ("raw_keylogging", _browser_atspi_selftest_latest(raw_keylogging=True), {}, "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _browser_atspi_selftest_latest(password_fields_captured=True),
            {},
            "policy_password_fields_not_captured",
        ),
        ("internet_access", _browser_atspi_selftest_latest(internet_access=True), {}, "policy_internet_access_disabled"),
        (
            "wrong_release_profile",
            _browser_atspi_selftest_latest(release_profile=True, profile_kind="temporary_profile"),
            {"release_profile": True},
            "firefox_release_profile",
        ),
        (
            "release_not_mutated",
            _browser_atspi_selftest_latest(release_profile=True, release_profile_mutated=False),
            {"release_profile": True},
            "policy_release_profile_mutated",
        ),
        ("missing_document", None, {}, "document_passed"),
    ]

    for label, latest, kwargs, failed_check in cases:
        status = typing_browser_atspi_selftest_validation_status(latest, **kwargs)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_browser_atspi_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _browser_atspi_selftest_latest()
    release_latest = _browser_atspi_selftest_latest(release_profile=True)

    assert cli.typing_browser_atspi_selftest_validation_status(latest) == typing_browser_atspi_selftest_validation_status(latest)
    assert (
        cli.typing_browser_atspi_selftest_validation_status(release_latest, release_profile=True)
        == typing_browser_atspi_selftest_validation_status(release_latest, release_profile=True)
    )


def _generic_gui_selftest_latest(
    *,
    source_adapter: str = "atspi_text_changed_event",
    event_status: str = "captured",
    capture_gate_decision: str = "allow_text",
    capture_gate_confidence: str = "atspi_generic_editable_text_allowed",
    text_length: int = 24,
    text_chars_stored: int = 24,
    recipient_kind: str = "focused_application",
    sensitive_status: str = "metadata_only",
    sensitive_capture_gate_decision: str = "metadata_only",
    sensitive_text_chars_stored: int = 0,
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    network_access: bool = False,
    ok: bool = True,
    status: str = "passed",
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "event": {
            "source_adapter": source_adapter,
            "status": event_status,
            "capture_gate_decision": capture_gate_decision,
            "capture_gate_confidence": capture_gate_confidence,
            "text_length": text_length,
            "text_chars_stored": text_chars_stored,
            "recipient": {"kind": recipient_kind},
        },
        "sensitive_probe": {
            "status": sensitive_status,
            "capture_gate_decision": sensitive_capture_gate_decision,
            "text_chars_stored": sensitive_text_chars_stored,
        },
        "policy": {
            "raw_keylogging": raw_keylogging,
            "password_fields_captured": password_fields_captured,
            "network_access": network_access,
        },
    }


def test_typing_generic_gui_selftest_validation_status_accepts_safe_route() -> None:
    status = typing_generic_gui_selftest_validation_status(_generic_gui_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["status"] == "passed"
    assert all(status["checks"].values())


def test_typing_generic_gui_selftest_validation_status_rejects_route_sensitive_and_policy_failures() -> None:
    cases = [
        ("failed_document", _generic_gui_selftest_latest(ok=False), "document_passed"),
        ("wrong_source", _generic_gui_selftest_latest(source_adapter="browser_extension_explicit"), "event_source_adapter"),
        ("not_captured", _generic_gui_selftest_latest(event_status="filtered"), "event_status_captured"),
        ("metadata_only", _generic_gui_selftest_latest(capture_gate_decision="metadata_only"), "event_capture_gate"),
        (
            "wrong_confidence",
            _generic_gui_selftest_latest(capture_gate_confidence="atspi_browser_url_allowed"),
            "event_capture_confidence",
        ),
        ("truncated_text", _generic_gui_selftest_latest(text_chars_stored=12), "event_text_stored"),
        ("wrong_recipient", _generic_gui_selftest_latest(recipient_kind="browser_extension"), "recipient_kind"),
        ("sensitive_captured", _generic_gui_selftest_latest(sensitive_status="captured"), "sensitive_status_metadata_only"),
        (
            "sensitive_allowed",
            _generic_gui_selftest_latest(sensitive_capture_gate_decision="allow_text"),
            "sensitive_capture_gate_metadata_only",
        ),
        ("sensitive_stored", _generic_gui_selftest_latest(sensitive_text_chars_stored=7), "sensitive_text_omitted"),
        ("raw_keylogging", _generic_gui_selftest_latest(raw_keylogging=True), "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _generic_gui_selftest_latest(password_fields_captured=True),
            "policy_password_fields_not_captured",
        ),
        ("network_access", _generic_gui_selftest_latest(network_access=True), "policy_network_access_disabled"),
        ("missing_document", None, "document_passed"),
    ]

    for label, latest, failed_check in cases:
        status = typing_generic_gui_selftest_validation_status(latest)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_generic_gui_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _generic_gui_selftest_latest()

    assert cli.typing_generic_gui_selftest_validation_status(latest) == typing_generic_gui_selftest_validation_status(latest)


def _focused_browser_selftest_latest(
    *,
    source_adapter: str = "atspi_focused_text_snapshot",
    event_status: str = "captured",
    capture_gate_decision: str = "allow_text",
    capture_gate_confidence: str = "focused_browser_safe_url_allowed",
    safe_route: str = "browser_safe_url",
    browser_safe_url: bool = True,
    text_length: int = 24,
    text_chars_stored: int = 24,
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    temporary_firefox_profile: bool = True,
    release_profile_mutated: bool = False,
    ok: bool = True,
    status: str = "passed",
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "event": {
            "source_adapter": source_adapter,
            "status": event_status,
            "capture_gate_decision": capture_gate_decision,
            "capture_gate_confidence": capture_gate_confidence,
            "safe_route": safe_route,
            "browser_safe_url": browser_safe_url,
            "text_length": text_length,
            "text_chars_stored": text_chars_stored,
        },
        "policy": {
            "raw_keylogging": raw_keylogging,
            "password_fields_captured": password_fields_captured,
            "temporary_firefox_profile": temporary_firefox_profile,
            "release_profile_mutated": release_profile_mutated,
        },
    }


def test_typing_focused_browser_selftest_validation_status_accepts_safe_browser_route() -> None:
    status = typing_focused_browser_selftest_validation_status(_focused_browser_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["status"] == "passed"
    assert all(status["checks"].values())


def test_typing_focused_browser_selftest_validation_status_rejects_route_and_policy_failures() -> None:
    cases = [
        ("failed_document", _focused_browser_selftest_latest(ok=False), "document_passed"),
        ("wrong_source", _focused_browser_selftest_latest(source_adapter="atspi_text_changed_event"), "event_source_adapter"),
        ("not_captured", _focused_browser_selftest_latest(event_status="filtered"), "event_status_captured"),
        ("metadata_only", _focused_browser_selftest_latest(capture_gate_decision="metadata_only"), "event_capture_gate"),
        (
            "wrong_confidence",
            _focused_browser_selftest_latest(capture_gate_confidence="atspi_browser_url_allowed"),
            "event_capture_confidence",
        ),
        ("wrong_route", _focused_browser_selftest_latest(safe_route="browser_unknown_url"), "event_safe_route"),
        ("unsafe_url", _focused_browser_selftest_latest(browser_safe_url=False), "event_browser_safe_url"),
        ("truncated_text", _focused_browser_selftest_latest(text_chars_stored=12), "event_text_stored"),
        ("raw_keylogging", _focused_browser_selftest_latest(raw_keylogging=True), "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _focused_browser_selftest_latest(password_fields_captured=True),
            "policy_password_fields_not_captured",
        ),
        (
            "release_profile",
            _focused_browser_selftest_latest(temporary_firefox_profile=False),
            "policy_temporary_firefox_profile",
        ),
        (
            "mutated_release_profile",
            _focused_browser_selftest_latest(release_profile_mutated=True),
            "policy_release_profile_not_mutated",
        ),
        ("missing_document", None, "document_passed"),
    ]

    for label, latest, failed_check in cases:
        status = typing_focused_browser_selftest_validation_status(latest)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_focused_browser_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _focused_browser_selftest_latest()

    assert cli.typing_focused_browser_selftest_validation_status(latest) == typing_focused_browser_selftest_validation_status(latest)


def _browser_privacy_selftest_latest(
    *,
    atspi_metadata_only_before_text_read: bool = True,
    focused_candidate_no_text_read: bool = True,
    focused_metadata_only_before_text_read: bool = True,
    probe_text_sha256_absent_from_recent_events: bool = True,
    atspi_text_chars_stored: int = 0,
    focused_text_chars_stored: int = 0,
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    login_url_text_persisted: bool = False,
    ok: bool = True,
    status: str = "passed",
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "checks": {
            "atspi_metadata_only_before_text_read": atspi_metadata_only_before_text_read,
            "focused_candidate_no_text_read": focused_candidate_no_text_read,
            "focused_metadata_only_before_text_read": focused_metadata_only_before_text_read,
            "probe_text_sha256_absent_from_recent_events": probe_text_sha256_absent_from_recent_events,
        },
        "atspi_text_event": {
            "text_chars_stored": atspi_text_chars_stored,
        },
        "focused_event": {
            "text_chars_stored": focused_text_chars_stored,
        },
        "policy": {
            "raw_keylogging": raw_keylogging,
            "password_fields_captured": password_fields_captured,
            "login_url_text_persisted": login_url_text_persisted,
        },
    }


def test_typing_browser_privacy_selftest_validation_status_accepts_metadata_only_route() -> None:
    status = typing_browser_privacy_selftest_validation_status(_browser_privacy_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["status"] == "passed"
    assert all(status["checks"].values())


def test_typing_browser_privacy_selftest_validation_status_rejects_privacy_failures() -> None:
    cases = [
        ("failed_document", _browser_privacy_selftest_latest(ok=False), "document_passed"),
        (
            "atspi_not_metadata_only",
            _browser_privacy_selftest_latest(atspi_metadata_only_before_text_read=False),
            "atspi_metadata_only_before_text_read",
        ),
        (
            "focused_candidate_text_read",
            _browser_privacy_selftest_latest(focused_candidate_no_text_read=False),
            "focused_candidate_no_text_read",
        ),
        (
            "focused_not_metadata_only",
            _browser_privacy_selftest_latest(focused_metadata_only_before_text_read=False),
            "focused_metadata_only_before_text_read",
        ),
        (
            "probe_text_found",
            _browser_privacy_selftest_latest(probe_text_sha256_absent_from_recent_events=False),
            "probe_text_sha256_absent_from_recent_events",
        ),
        ("atspi_text_stored", _browser_privacy_selftest_latest(atspi_text_chars_stored=7), "atspi_text_omitted"),
        ("focused_text_stored", _browser_privacy_selftest_latest(focused_text_chars_stored=7), "focused_text_omitted"),
        ("raw_keylogging", _browser_privacy_selftest_latest(raw_keylogging=True), "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _browser_privacy_selftest_latest(password_fields_captured=True),
            "policy_password_fields_not_captured",
        ),
        (
            "login_text_persisted",
            _browser_privacy_selftest_latest(login_url_text_persisted=True),
            "policy_login_url_text_not_persisted",
        ),
        ("missing_document", None, "document_passed"),
    ]

    for label, latest, failed_check in cases:
        status = typing_browser_privacy_selftest_validation_status(latest)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_browser_privacy_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _browser_privacy_selftest_latest()

    assert (
        cli.typing_browser_privacy_selftest_validation_status(latest)
        == typing_browser_privacy_selftest_validation_status(latest)
    )


def _browser_context_selftest_latest(**policy_overrides: object) -> dict:
    policy = {
        "raw_keylogging": False,
        "password_fields_captured": False,
        "form_values_captured": False,
        "uses_browser_content_capture": True,
        "uses_atspi_document_path_inference": True,
    }
    policy.update(policy_overrides)
    return {"ok": True, "status": "passed", "policy": policy}


def test_typing_browser_context_fallback_status_prefers_live_inference_when_passed() -> None:
    status = typing_browser_context_fallback_status(
        browser_context_inference={"ok": True, "status": "passed"},
        browser_context_selftest_latest={"ok": False, "status": "failed"},
        browser_atspi_selftest_ok=True,
        browser_atspi_release_selftest_ok=False,
    )

    assert status == {
        "context_selftest_ok": False,
        "context_inference_passed": True,
        "context_inference_effective_ok": True,
        "context_inference_effective_status": "passed",
        "context_inference_raw_status": "passed",
        "atspi_fallback_ok": True,
    }


def test_typing_browser_context_fallback_status_accepts_safe_context_selftest_fallback() -> None:
    status = typing_browser_context_fallback_status(
        browser_context_inference={"ok": False, "status": "no_recent_browser_context"},
        browser_context_selftest_latest=_browser_context_selftest_latest(),
        browser_atspi_selftest_ok=False,
        browser_atspi_release_selftest_ok=True,
    )

    assert status["context_selftest_ok"] is True
    assert status["context_inference_passed"] is False
    assert status["context_inference_effective_ok"] is True
    assert status["context_inference_effective_status"] == "passed_via_browser_context_selftest"
    assert status["context_inference_raw_status"] == "no_recent_browser_context"
    assert status["atspi_fallback_ok"] is True


def test_typing_browser_context_fallback_status_rejects_unsafe_selftest_policy() -> None:
    status = typing_browser_context_fallback_status(
        browser_context_inference={"ok": False, "status": "no_recent_browser_context"},
        browser_context_selftest_latest=_browser_context_selftest_latest(raw_keylogging=True),
        browser_atspi_selftest_ok=True,
        browser_atspi_release_selftest_ok=False,
    )

    assert status["context_selftest_ok"] is False
    assert status["context_inference_effective_ok"] is False
    assert status["context_inference_effective_status"] == "no_recent_browser_context"
    assert status["atspi_fallback_ok"] is False


def test_cli_typing_browser_context_fallback_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "browser_context_inference": {"ok": False, "status": "no_recent_browser_context"},
        "browser_context_selftest_latest": _browser_context_selftest_latest(),
        "browser_atspi_selftest_ok": True,
        "browser_atspi_release_selftest_ok": False,
    }

    assert cli.typing_browser_context_fallback_status(**kwargs) == typing_browser_context_fallback_status(**kwargs)


def _browser_ai_transcript_selftest_latest(
    *,
    recipient_id: str = "ai:google:gemini",
    recipient_kind: str = "ai_counterpart",
    source_adapter: str = "browser_ai_transcript",
    safe_status: str = "captured",
    capture_gate_decision: str = "allow_text",
    capture_gate_confidence: str = "browser_ai_transcript_known_ai_page_allowed",
    message_role: str = "assistant",
    sensitive_capture_gate_decision: str = "metadata_only",
    sensitive_text_chars_stored: int = 0,
    raw_keylogging: bool = False,
    password_fields_captured: bool = False,
    automatic_action: bool = False,
    ok: bool = True,
    status: str = "passed",
) -> dict:
    return {
        "ok": ok,
        "status": status,
        "safe": {
            "source_adapter": source_adapter,
            "status": safe_status,
            "capture_gate_decision": capture_gate_decision,
            "capture_gate_confidence": capture_gate_confidence,
            "recipient": {"kind": recipient_kind, "id": recipient_id},
            "message_role": message_role,
        },
        "sensitive": {
            "capture_gate_decision": sensitive_capture_gate_decision,
            "text_chars_stored": sensitive_text_chars_stored,
        },
        "policy": {
            "raw_keylogging": raw_keylogging,
            "password_fields_captured": password_fields_captured,
            "automatic_action": automatic_action,
        },
    }


def test_typing_browser_ai_transcript_selftest_status_accepts_safe_gemini_route() -> None:
    status = typing_browser_ai_transcript_selftest_status(_browser_ai_transcript_selftest_latest())

    assert status == {
        "selftest_ok": True,
        "status": "passed",
        "expected_recipient_id": "ai:google:gemini",
        "safe_event": {
            "source_adapter": "browser_ai_transcript",
            "capture_gate_decision": "allow_text",
            "recipient_id": "ai:google:gemini",
        },
    }


def test_typing_browser_ai_transcript_selftest_status_rejects_wrong_or_failed_route() -> None:
    cases = [
        _browser_ai_transcript_selftest_latest(recipient_id="ai:openai:chatgpt"),
        _browser_ai_transcript_selftest_latest(source_adapter="browser_extension_explicit"),
        _browser_ai_transcript_selftest_latest(capture_gate_decision="metadata_only"),
        _browser_ai_transcript_selftest_latest(ok=False),
        _browser_ai_transcript_selftest_latest(status="failed"),
        None,
    ]

    for latest in cases:
        assert typing_browser_ai_transcript_selftest_status(latest)["selftest_ok"] is False


def test_cli_typing_browser_ai_transcript_selftest_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _browser_ai_transcript_selftest_latest()

    assert cli.typing_browser_ai_transcript_selftest_status(latest) == typing_browser_ai_transcript_selftest_status(latest)


def test_typing_browser_ai_transcript_selftest_validation_status_accepts_safe_route() -> None:
    status = typing_browser_ai_transcript_selftest_validation_status(_browser_ai_transcript_selftest_latest())

    assert status["selftest_ok"] is True
    assert status["status"] == "passed"
    assert status["expected_recipient_id"] == "ai:google:gemini"
    assert all(status["checks"].values())


def test_typing_browser_ai_transcript_selftest_validation_status_rejects_policy_and_route_failures() -> None:
    cases = [
        ("failed_document", _browser_ai_transcript_selftest_latest(ok=False), "document_passed"),
        ("wrong_source", _browser_ai_transcript_selftest_latest(source_adapter="browser_extension_explicit"), "safe_source_adapter"),
        ("not_captured", _browser_ai_transcript_selftest_latest(safe_status="filtered"), "safe_status_captured"),
        ("metadata_safe", _browser_ai_transcript_selftest_latest(capture_gate_decision="metadata_only"), "safe_capture_gate"),
        (
            "wrong_confidence",
            _browser_ai_transcript_selftest_latest(capture_gate_confidence="browser_url_and_field_allowed"),
            "safe_capture_confidence",
        ),
        ("wrong_recipient_kind", _browser_ai_transcript_selftest_latest(recipient_kind="browser_extension"), "safe_recipient_kind"),
        ("wrong_recipient_id", _browser_ai_transcript_selftest_latest(recipient_id="ai:openai:chatgpt"), "safe_recipient_id"),
        ("wrong_role", _browser_ai_transcript_selftest_latest(message_role="user"), "safe_message_role"),
        (
            "sensitive_text_allowed",
            _browser_ai_transcript_selftest_latest(sensitive_capture_gate_decision="allow_text"),
            "sensitive_metadata_only",
        ),
        ("sensitive_text_stored", _browser_ai_transcript_selftest_latest(sensitive_text_chars_stored=12), "sensitive_text_omitted"),
        ("raw_keylogging", _browser_ai_transcript_selftest_latest(raw_keylogging=True), "policy_raw_keylogging_disabled"),
        (
            "password_fields",
            _browser_ai_transcript_selftest_latest(password_fields_captured=True),
            "policy_password_fields_not_captured",
        ),
        ("automatic_action", _browser_ai_transcript_selftest_latest(automatic_action=True), "policy_automatic_action_disabled"),
        ("missing_document", None, "document_passed"),
    ]

    for label, latest, failed_check in cases:
        status = typing_browser_ai_transcript_selftest_validation_status(latest)
        assert status["selftest_ok"] is False, label
        assert status["checks"][failed_check] is False, label


def test_cli_typing_browser_ai_transcript_selftest_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = _browser_ai_transcript_selftest_latest()

    assert (
        cli.typing_browser_ai_transcript_selftest_validation_status(latest)
        == typing_browser_ai_transcript_selftest_validation_status(latest)
    )


def test_typing_browser_input_recency_status_classifies_live_controlled_and_proof_routes() -> None:
    cases = [
        (
            {
                "latest_any": {"age_sec": 20},
                "latest_natural": {"age_sec": 20},
                "latest_natural_text": {"age_sec": 20},
                "latest_controlled_text": {"age_sec": 10},
            },
            None,
            "live_browser_text_recent",
            {"latest_natural_text_recent": True, "latest_proof_recent": False},
        ),
        (
            {
                "latest_any": {"age_sec": 20},
                "latest_natural": {"age_sec": 20},
                "latest_controlled_text": {"age_sec": 20},
            },
            None,
            "live_browser_metadata_controlled_text_recent",
            {"latest_natural_recent": True, "latest_controlled_text_recent": True},
        ),
        (
            {"latest_any": {"age_sec": 20}, "latest_natural": {"age_sec": 20}},
            None,
            "live_browser_metadata_recent",
            {"latest_natural_recent": True},
        ),
        (
            {"latest_any": {"age_sec": 20}, "latest_controlled_text": {"age_sec": 20}},
            None,
            "controlled_browser_text_recent",
            {"latest_controlled_text_recent": True},
        ),
        (
            {"latest_any": {"age_sec": 20}},
            None,
            "controlled_browser_metadata_recent",
            {"latest_any_recent": True},
        ),
        (
            {"latest_any": {"age_sec": 900}},
            {"route": "browser_webextension_selftest", "age_sec": 20},
            "selftest_proof_recent",
            {"latest_proof_recent": True, "latest_proof_present": True},
        ),
        (
            {"latest_any": {"age_sec": 900}},
            {"route": "browser_webextension_selftest", "age_sec": 900},
            "browser_proof_stale",
            {"latest_proof_recent": False, "latest_proof_present": True},
        ),
        (
            {"latest_any": {"age_sec": 900}},
            None,
            "browser_evidence_missing",
            {"latest_proof_present": False},
        ),
    ]

    for input_recency, latest_proof, expected_status, expected_flags in cases:
        decision = typing_browser_input_recency_status(
            browser_input_recency=input_recency,
            browser_latest_proof=latest_proof,
            max_age_sec=120,
        )
        assert decision["effective_status"] == expected_status
        assert decision["max_age_sec"] == 120
        for key, value in expected_flags.items():
            assert decision[key] is value


def test_cli_typing_browser_input_recency_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = {
        "browser_input_recency": {
            "latest_any": {"age_sec": 60},
            "latest_natural": {"age_sec": 60},
            "latest_controlled_text": {"age_sec": 30},
        },
        "browser_latest_proof": {"route": "browser_atspi_selftest", "age_sec": 45},
        "max_age_sec": 120,
    }

    assert cli.typing_browser_input_recency_status(**kwargs) == typing_browser_input_recency_status(**kwargs)


def test_typing_browser_input_recency_validation_status_accepts_only_fresh_routes() -> None:
    accepted = [
        "live_browser_text_recent",
        "live_browser_metadata_controlled_text_recent",
        "live_browser_metadata_recent",
        "controlled_browser_text_recent",
        "controlled_browser_metadata_recent",
        "selftest_proof_recent",
    ]

    for effective_status in accepted:
        decision = typing_browser_input_recency_validation_status({"effective_status": effective_status})
        assert decision["ok"] is True
        assert decision["effective_status"] == effective_status
        assert effective_status in decision["accepted_statuses"]

    stale = typing_browser_input_recency_validation_status({"effective_status": "browser_proof_stale"})
    missing = typing_browser_input_recency_validation_status({})

    assert stale["ok"] is False
    assert stale["effective_status"] == "browser_proof_stale"
    assert missing["ok"] is False
    assert missing["effective_status"] == "browser_evidence_missing"


def test_cli_typing_browser_input_recency_validation_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    browser_input_recency = {"effective_status": "controlled_browser_metadata_recent"}

    assert (
        cli.typing_browser_input_recency_validation_status(browser_input_recency)
        == typing_browser_input_recency_validation_status(browser_input_recency)
    )


def test_typing_atspi_text_events_heartbeat_status_uses_policy_fallback_and_staleness_gate() -> None:
    fresh = typing_atspi_text_events_heartbeat_status(
        {"status": "running_with_errors", "heartbeat_age_sec": 100},
        {"heartbeat_interval_sec": 30},
    )
    stale = typing_atspi_text_events_heartbeat_status(
        {"status": "running", "heartbeat_age_sec": 181, "heartbeat_interval_sec": 30},
        {"heartbeat_interval_sec": 60},
    )
    missing_age = typing_atspi_text_events_heartbeat_status({"status": "sample_complete"})
    stopped = typing_atspi_text_events_heartbeat_status({"status": "stopped", "heartbeat_age_sec": 10})

    assert fresh["ok"] is True
    assert fresh["latest_status"] == "running_with_errors"
    assert fresh["heartbeat_interval_sec"] == 30
    assert fresh["max_age_sec"] == 180
    assert stale["ok"] is False
    assert stale["heartbeat_interval_sec"] == 30
    assert stale["max_age_sec"] == 180
    assert missing_age["ok"] is False
    assert missing_age["heartbeat_age_sec"] is None
    assert stopped["ok"] is False
    assert stopped["latest_status"] == "stopped"


def test_cli_typing_atspi_text_events_heartbeat_status_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    latest = {"status": "sample_complete", "heartbeat_age_sec": 50, "heartbeat_interval_sec": 20}
    policy = {"heartbeat_interval_sec": 60}

    assert (
        cli.typing_atspi_text_events_heartbeat_status(latest, policy)
        == typing_atspi_text_events_heartbeat_status(latest, policy)
    )


def test_typing_atspi_text_events_policy_merges_default_and_override_without_mutation() -> None:
    default_policy = {
        "atspi_text_events": {
            "enabled": True,
            "heartbeat_interval_sec": 60,
            "event_types": ["object:text-changed:insert"],
            "generic_editable_text": {
                "enabled": True,
                "requires_editable": True,
                "requires_focus_or_visible": True,
            },
        }
    }
    policy = {
        "atspi_text_events": {
            "heartbeat_interval_sec": 30,
            "generic_editable_text": {"requires_editable": False},
            "compact_history": True,
        }
    }

    merged = typing_atspi_text_events_policy(policy=policy, default_policy=default_policy)

    assert merged == {
        "enabled": True,
        "heartbeat_interval_sec": 30,
        "event_types": ["object:text-changed:insert"],
        "generic_editable_text": {
            "enabled": True,
            "requires_editable": False,
            "requires_focus_or_visible": True,
        },
        "compact_history": True,
    }
    assert default_policy["atspi_text_events"]["heartbeat_interval_sec"] == 60
    assert policy["atspi_text_events"]["generic_editable_text"] == {"requires_editable": False}


def test_typing_atspi_text_events_policy_handles_missing_or_invalid_policy_roots() -> None:
    assert typing_atspi_text_events_policy(policy=None, default_policy=None) == {}
    assert typing_atspi_text_events_policy(
        policy={"atspi_text_events": {"enabled": False}},
        default_policy={"atspi_text_events": "invalid"},
    ) == {"enabled": False}
    assert typing_atspi_text_events_policy(
        policy={"atspi_text_events": "invalid"},
        default_policy={"atspi_text_events": {"enabled": True}},
    ) == {"enabled": True}


def test_cli_typing_atspi_text_events_policy_delegates_to_module_contract(monkeypatch) -> None:
    from abyss_machine import cli

    policy = {"atspi_text_events": {"heartbeat_interval_sec": 20}}
    default_policy = {"atspi_text_events": {"enabled": True, "heartbeat_interval_sec": 60}}
    monkeypatch.setattr(cli, "typing_policy", lambda write_latest=False: policy)
    monkeypatch.setattr(cli, "default_typing_policy", lambda: default_policy)

    assert cli.typing_atspi_text_events_policy() == typing_atspi_text_events_policy(
        policy=policy,
        default_policy=default_policy,
    )
    assert cli.typing_atspi_text_events_policy({"atspi_text_events": {"enabled": False}}) == typing_atspi_text_events_policy(
        policy={"atspi_text_events": {"enabled": False}},
        default_policy=default_policy,
    )


def _valid_atspi_compact_record() -> dict:
    return {
        "schema": "abyss_machine_typing_atspi_text_event_compact_v1",
        "version": "fixture",
        "generated_at": "2026-06-26T00:00:00Z",
        "ok": True,
        "status": "captured",
        "source_adapter": "atspi_text_changed_event",
        "listener_status": "running",
        "event_index": 7,
        "event_type": "object:text-changed:insert",
        "app": "Firefox",
        "window_title": "Fixture",
        "role": "entry",
        "atspi_path": "/fixture/path",
        "document_path": "/fixture/document",
        "states": {
            "editable": True,
            "focused": True,
            "showing": True,
            "visible": True,
            "enabled": True,
            "sensitive": False,
        },
        "capture_gate": {"decision": "allow_text"},
        "typing_event": {"event_id": "evt-1"},
        "text_probe": {"text_length": 12, "text_read": True},
        "policy": {
            "compact_history": True,
            "full_listener_state_in_latest": True,
            "raw_keylogging": False,
            "password_fields_captured": False,
            "automatic_action": False,
            "text_omitted_from_compact_record": True,
        },
    }


def _atspi_compact_record_kwargs(**overrides: object) -> dict:
    sample = {
        "generated_at": "2026-06-26T00:00:00Z",
        "ok": True,
        "status": "captured",
        "source_adapter": "atspi_text_changed_event",
        "event_type": "object:text-changed:insert",
        "detail1": 0,
        "detail2": 12,
        "any_data_type": "str",
        "app": "  Firefox\nNightly  ",
        "app_process_id": 4242,
        "window_title": "Fixture Browser Window",
        "url": "https://example.test/editor",
        "document_title": "Fixture Doc",
        "content_type": "text/html",
        "role": "entry",
        "name": " " + ("field " * 50),
        "atspi_path": "/fixture/path",
        "document_path": "/fixture/document",
        "states": {
            "editable": True,
            "focused": True,
            "showing": True,
            "visible": True,
            "enabled": True,
            "sensitive": False,
        },
        "text_role": True,
        "sensitive_context": False,
        "capture_gate": {
            "decision": "allow_text",
            "confidence": "fixture",
            "matched_policy": {"source_adapter": "atspi_text_changed_event"},
        },
        "typing_event": {
            "event_id": "evt-1",
            "status": "captured",
            "text_length": 12,
            "text_chars_stored": 12,
            "capture_gate_decision": "allow_text",
            "duplicate": False,
        },
        "text_length": 12,
        "caret_offset": 4,
        "browser_context_inference": {
            "ok": True,
            "status": "passed",
            "basis": "fixture",
            "context_id": "ctx-1",
            "max_age_sec": 120,
            "extra": "omitted",
        },
        "text": "private text must not be copied",
    }
    sample.update(overrides)
    return {
        "data": {"summary": {"events_seen": 7, "errors": 0}},
        "sample": sample,
        "listener_status": "running",
        "schema_prefix": "abyss_machine",
        "version": "fixture",
        "generated_at": "2026-06-26T00:00:01Z",
    }


def test_typing_atspi_text_events_compact_history_record_omits_text_and_preserves_search_keys() -> None:
    record = typing_atspi_text_events_compact_history_record(**_atspi_compact_record_kwargs())

    assert record["schema"] == "abyss_machine_typing_atspi_text_event_compact_v1"
    assert record["generated_at"] == "2026-06-26T00:00:00Z"
    assert record["event_index"] == 7
    assert record["app"] == "Firefox Nightly"
    assert record["name"].endswith("...")
    assert "text" not in record
    assert "text_raw" not in record
    assert record["text_probe"] == {"text_length": 12, "caret_offset": 4, "text_read": True}
    assert record["capture_gate"]["decision"] == "allow_text"
    assert record["typing_event"]["event_id"] == "evt-1"
    assert record["browser_context_inference"] == {
        "ok": True,
        "status": "passed",
        "basis": "fixture",
        "context_id": "ctx-1",
        "max_age_sec": 120,
    }
    assert record["policy"]["text_omitted_from_compact_record"] is True
    assert record["policy"]["raw_keylogging"] is False


def test_typing_atspi_text_events_compact_history_record_handles_listener_error_without_sample() -> None:
    record = typing_atspi_text_events_compact_history_record(
        data={"summary": {"events_seen": 9}},
        sample=None,
        listener_status="failed",
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-26T00:00:01Z",
        error="fixture error",
    )

    assert record["ok"] is False
    assert record["status"] == "listener_error"
    assert record["event_index"] == 9
    assert record["error"] == "fixture error"
    assert record["policy"]["raw_keylogging"] is False
    assert "text" not in record


def test_cli_typing_atspi_text_events_compact_history_record_delegates_to_module_contract(monkeypatch) -> None:
    from abyss_machine import cli

    kwargs = _atspi_compact_record_kwargs(generated_at=None)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T00:00:01Z")
    expected = typing_atspi_text_events_compact_history_record(
        data=kwargs["data"],
        sample=kwargs["sample"],
        listener_status=kwargs["listener_status"],
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T00:00:01Z",
    )

    assert (
        cli.typing_atspi_text_events_compact_history_record(
            kwargs["data"],
            kwargs["sample"],
            kwargs["listener_status"],
        )
        == expected
    )


def test_typing_atspi_compact_history_contract_document_checks_search_binding_keys() -> None:
    record = _valid_atspi_compact_record()
    document = typing_atspi_compact_history_contract_document(
        records=[record],
        parse_errors=[],
        path="/tmp/typing-atspi.jsonl",
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-26T00:00:01Z",
        lines_scanned=1,
    )
    missing_link_record = {
        **record,
        "typing_event": {},
    }
    failed = typing_atspi_compact_history_contract_document(
        records=[missing_link_record],
        parse_errors=[],
        path="/tmp/typing-atspi.jsonl",
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-26T00:00:01Z",
        lines_scanned=1,
    )
    empty = typing_atspi_compact_history_contract_document(
        records=[],
        parse_errors=[],
        path="/tmp/typing-atspi.jsonl",
        schema_prefix="abyss_machine",
        version="fixture",
        generated_at="2026-06-26T00:00:01Z",
        lines_scanned=0,
    )

    assert document["ok"] is True
    assert document["status"] == "passed"
    assert document["summary"]["compact_records"] == 1
    assert document["summary"]["lines_scanned"] == 1
    assert document["policy"]["search_binding_keys_required"] is True
    assert failed["ok"] is False
    assert failed["violations"][0]["missing_typing_event_link"] is True
    assert empty["ok"] is False
    assert empty["status"] == "warn"
    assert empty["warnings"][0]["key"] == "no_recent_compact_rows"


def test_cli_typing_atspi_compact_history_contract_delegates_to_module_document(monkeypatch) -> None:
    from abyss_machine import cli

    record = _valid_atspi_compact_record()
    path = Path("/tmp/typing-atspi-fixture.jsonl")
    monkeypatch.setattr(cli, "ai_daily_jsonl_path", lambda root: path)
    monkeypatch.setattr(cli, "read_recent_jsonl_lines", lambda *args, **kwargs: [json.dumps(record)])

    document = cli.typing_atspi_compact_history_contract(200)
    expected = typing_atspi_compact_history_contract_document(
        records=[record],
        parse_errors=[],
        path=str(path),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=document["generated_at"],
        lines_scanned=1,
    )

    assert document == expected


def _typing_route_assessment_kwargs(**overrides: object) -> dict:
    base = {
        "configured_adapters": [],
        "by_adapter": {"manual_cli_stdin": 1, "zsh_preexec": 1},
        "by_gate": {"metadata_only": 1},
        "record_count": 4,
        "dominant_adapter": "manual_cli_stdin",
        "dominant_ratio": 0.5,
        "saved_text_count": 0,
        "live_input_count": 2,
        "live_observed_adapters": ["manual_cli_stdin"],
        "live_dominant_adapter": "manual_cli_stdin",
        "live_dominant_ratio": 0.5,
        "browser_release_gap": False,
        "browser_release_status": "active",
        "browser_release_active": True,
        "browser_activation": {},
        "browser_temporary_proof_ok": False,
        "browser_atspi_fallback_ok": False,
        "browser_effective_recency_status": "live_browser_text_recent",
        "browser_recency_max_age_sec": 900,
        "browser_input_recency": {"records": 2},
        "browser_latest_proof": None,
        "codex_prompt_route_assessment": {"route_notes": [], "gaps": []},
        "focused_policy": {"enabled": True, "text_capture_enabled": True},
        "focused_latest": {"status": "skipped_no_focused_editable_text"},
        "focused_latest_error": None,
        "atspi_events_latest": {"status": "running", "summary": {"errors": 0}},
        "atspi_events_latest_error": None,
        "generic_gui_selftest_ok": False,
        "zsh_selftest_ok": True,
        "zsh_hook_selftest_error": None,
        "editor_extension_latest": {"ok": True, "status": "ready"},
        "editor_extension_latest_error": None,
        "editor_callback_selftest_ok": True,
        "browser_extension_latest": {"ok": True, "status": "ready"},
        "browser_extension_latest_error": None,
        "browser_ai_transcript_latest": {"status": "ready"},
        "browser_ai_transcript_latest_error": None,
        "browser_ai_transcript_selftest_ok": True,
        "browser_ai_transcript_selftest_error": None,
        "missing_gate_records": 0,
    }
    base.update(overrides)
    return base


def test_typing_coverage_route_notes_and_gaps_marks_ready_idle_routes_as_notes() -> None:
    assessment = typing_coverage_route_notes_and_gaps(**_typing_route_assessment_kwargs(
        configured_adapters=[
            "atspi_focused_text_snapshot",
            "atspi_text_changed_event",
            "editor_extension_explicit",
            "browser_extension_explicit",
            "browser_ai_transcript",
        ],
        by_adapter={"manual_cli_stdin": 2},
        record_count=12,
        dominant_adapter="saved_text_snapshot",
        dominant_ratio=0.9,
        saved_text_count=10,
        live_input_count=2,
        browser_release_gap=True,
        browser_release_status="inactive",
        browser_release_active=False,
        browser_activation={"passwordless_next_routes": ["native-messaging"]},
        browser_temporary_proof_ok=True,
        browser_atspi_fallback_ok=True,
        browser_effective_recency_status="controlled_browser_text_recent",
        browser_input_recency={
            "records": 3,
            "natural_records": 0,
            "controlled_probe_records": 2,
            "latest_any": {"event_id": "evt-browser"},
        },
        browser_latest_proof={"route": "browser_webextension_selftest"},
    ))

    assert [item["key"] for item in assessment["route_notes"]] == [
        "browser_release_webextension_not_active",
        "browser_input_recency",
        "saved_text_dominates_recent_window",
        "focused_snapshot_not_observed_recently",
        "atspi_text_events_not_observed_recently",
        "zsh_preexec_not_observed_recently",
        "editor_extension_not_observed_recently",
        "browser_extension_not_observed_recently",
        "browser_ai_transcript_not_observed_recently",
    ]
    assert assessment["route_notes"][0]["level"] == "info"
    assert assessment["route_notes"][0]["passwordless_next"] == ["native-messaging"]
    assert assessment["route_notes"][2]["level"] == "info"
    assert assessment["gaps"] == []


def test_typing_coverage_route_notes_and_gaps_keeps_unhealthy_routes_as_gaps() -> None:
    codex_gap = {"key": "codex_user_prompt_submit_selftest_only", "level": "watch"}
    assessment = typing_coverage_route_notes_and_gaps(**_typing_route_assessment_kwargs(
        configured_adapters=[
            "atspi_focused_text_snapshot",
            "atspi_text_changed_event",
            "editor_extension_explicit",
            "browser_extension_explicit",
            "browser_ai_transcript",
        ],
        by_adapter={"manual_cli_stdin": 1},
        by_gate={},
        record_count=12,
        dominant_adapter="saved_text_snapshot",
        dominant_ratio=0.9,
        saved_text_count=12,
        live_input_count=0,
        live_observed_adapters=[],
        live_dominant_adapter=None,
        live_dominant_ratio=0.0,
        browser_release_gap=True,
        browser_release_status="inactive",
        browser_release_active=False,
        browser_temporary_proof_ok=False,
        browser_atspi_fallback_ok=False,
        browser_effective_recency_status="browser_evidence_missing",
        browser_input_recency={"records": 0, "latest_any": None},
        codex_prompt_route_assessment={"route_notes": [], "gaps": [codex_gap]},
        focused_latest=None,
        focused_latest_error="missing latest",
        atspi_events_latest={"status": "failed", "summary": {"errors": 2}},
        atspi_events_latest_error="atspi failed",
        zsh_selftest_ok=False,
        zsh_hook_selftest_error="zsh selftest failed",
        editor_extension_latest={"ok": False, "status": "failed"},
        editor_extension_latest_error="editor failed",
        editor_callback_selftest_ok=False,
        browser_extension_latest={"ok": False, "status": "failed"},
        browser_extension_latest_error="browser failed",
        browser_ai_transcript_latest={"status": "failed"},
        browser_ai_transcript_latest_error="transcript failed",
        browser_ai_transcript_selftest_ok=False,
        browser_ai_transcript_selftest_error="transcript selftest failed",
        missing_gate_records=2,
    ))

    assert [item["key"] for item in assessment["route_notes"]] == [
        "browser_release_webextension_not_active",
        "browser_input_recency",
    ]
    assert assessment["route_notes"][0]["level"] == "watch"
    assert [item["key"] for item in assessment["gaps"]] == [
        "saved_text_dominates_recent_window",
        "focused_snapshot_not_observed_recently",
        "atspi_text_events_not_observed_recently",
        "zsh_preexec_not_observed_recently",
        "codex_user_prompt_submit_selftest_only",
        "focused_snapshot_attempt_latest_missing",
        "editor_extension_not_observed_recently",
        "browser_extension_not_observed_recently",
        "browser_ai_transcript_not_observed_recently",
        "browser_input_recency_not_fresh",
        "capture_gate_deny_routes_not_observed_recently",
        "legacy_or_missing_capture_gate_records",
    ]
    assert assessment["gaps"][0]["level"] == "watch"
    assert assessment["gaps"][-1]["records"] == 2


def test_cli_typing_coverage_route_notes_and_gaps_delegates_to_module_contract() -> None:
    from abyss_machine import cli

    kwargs = _typing_route_assessment_kwargs(
        configured_adapters=["editor_extension_explicit"],
        by_adapter={"manual_cli_stdin": 1},
        editor_extension_latest={"ok": True, "status": "ready"},
        editor_callback_selftest_ok=True,
    )

    assert cli.typing_coverage_route_notes_and_gaps(**kwargs) == typing_coverage_route_notes_and_gaps(**kwargs)


def _codex_session_tail_latest_fixture() -> dict:
    return {
        "schema": "abyss_machine_typing_codex_session_tail_v1",
        "version": "test",
        "generated_at": "2026-06-26T00:01:00Z",
        "ok": True,
        "status": "processed",
        "summary": {
            "files": 2,
            "events": 3,
            "captured": 2,
            "metadata_only": 1,
            "duplicate_skipped": 0,
            "raw_user_candidates": 5,
            "normalized_skipped": 1,
            "raw_route_duplicates_skipped": 0,
            "response_item_route_migration": {"enabled": True},
            "parse_errors": 0,
            "prime_state": False,
        },
        "files": [{"path": "/tmp/session.jsonl"}],
        "events": [{"event_id": "evt-tail"}],
        "parse_errors": [],
        "policy": {
            "raw_keylogging": False,
            "native_codex_submit_hook": False,
            "session_jsonl_tail_fallback": True,
            "raw_record_routes": ["event_msg.user_message", "response_item.message.role_user"],
            "committed_user_messages_only": True,
            "normalizes_codex_context_envelopes": True,
            "password_fields_captured": False,
            "capture_gate_required": True,
            "session_postprocessing": False,
        },
    }


def test_codex_session_tail_latest_status_document_is_module_owned_contract() -> None:
    latest = _codex_session_tail_latest_fixture()
    service = {"name": "abyss-machine-typing-codex-session-tail.service", "is_active": True, "is_enabled": True}
    timer = {"name": "abyss-machine-typing-codex-session-tail.timer", "is_active": False, "is_enabled": False}

    status = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:02:00Z",
        latest=latest,
        latest_error=None,
        latest_path="/var/lib/abyss-machine/typing/codex-session-tail/latest.json",
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )

    assert status["schema"] == "abyss_machine_typing_codex_session_tail_status_v1"
    assert status["ok"] is True
    assert status["status"] == "processed"
    assert status["summary"]["latest_age_sec"] == 60.0
    assert status["summary"]["recurring_ok"] is True
    assert status["summary"]["events"] == 3
    assert status["latest"]["events"] == [{"event_id": "evt-tail"}]
    assert status["policy"]["session_jsonl_tail_fallback"] is True

    stale = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:04:00Z",
        latest=latest,
        latest_error=None,
        latest_path="/latest.json",
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:04:00Z",
    )
    missing = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:02:00Z",
        latest=None,
        latest_error=None,
        latest_path="/latest.json",
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )
    unreadable = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:02:00Z",
        latest=latest,
        latest_error="permission denied",
        latest_path="/latest.json",
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )
    inactive = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:02:00Z",
        latest=latest,
        latest_error=None,
        latest_path="/latest.json",
        service=service,
        timer=timer,
        service_path_exists=False,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )
    bad_policy_latest = dict(latest)
    bad_policy_latest["policy"] = {**latest["policy"], "capture_gate_required": False}
    bad_policy = codex_session_tail_latest_status_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T00:02:00Z",
        latest=bad_policy_latest,
        latest_error=None,
        latest_path="/latest.json",
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )

    assert stale["status"] == "stale"
    assert missing["status"] == "missing"
    assert unreadable["status"] == "unreadable"
    assert inactive["status"] == "recurring_inactive"
    assert bad_policy["status"] == "policy_violation"


def test_cli_codex_session_tail_latest_status_delegates_to_module_contract(monkeypatch, tmp_path) -> None:
    from abyss_machine import cli

    latest = _codex_session_tail_latest_fixture()
    service = {"name": "service", "is_active": True, "is_enabled": True}
    timer = {"name": "timer", "is_active": False, "is_enabled": False}
    latest_path = tmp_path / "latest.json"
    service_path = tmp_path / "service"
    timer_path = tmp_path / "timer"
    service_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli, "TYPING_CODEX_SESSION_TAIL_LATEST_PATH", latest_path)
    monkeypatch.setattr(cli, "TYPING_CODEX_SESSION_TAIL_SERVICE_PATH", service_path)
    monkeypatch.setattr(cli, "TYPING_CODEX_SESSION_TAIL_TIMER_PATH", timer_path)
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-26T00:02:00Z")
    monkeypatch.setattr(cli, "load_json_document", lambda path: (latest, None))
    monkeypatch.setattr(cli, "user_systemd_unit", lambda unit: service if unit == cli.TYPING_CODEX_SESSION_TAIL_SERVICE else timer)

    assert cli.typing_codex_session_tail_latest_status(max_age_sec=120) == codex_session_tail_latest_status_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at="2026-06-26T00:02:00Z",
        latest=latest,
        latest_error=None,
        latest_path=str(latest_path),
        service=service,
        timer=timer,
        service_path_exists=True,
        timer_path_exists=False,
        max_age_sec=120,
        reference_at="2026-06-26T00:02:00Z",
    )


def test_browser_ai_transcript_cleanup_role_and_metadata_are_stable_contracts() -> None:
    cleanup = browser_ai_transcript_clean_text("Hello\nExpand\nWorldShow more")
    identity = {
        "is_ai": True,
        "entity_id": "ai:openai:chatgpt",
        "provider": "OpenAI",
        "product": "ChatGPT",
        "family": "chatgpt",
        "surface": "ai_chat",
    }
    role = browser_ai_transcript_normalize_role("bubble", "ChatGPT said hello", identity)
    message = {
        "browser_name": "firefox",
        "url": "https://chatgpt.com/c/fixture",
        "title": "ChatGPT",
        "text": "ChatGPT said hello",
        "browser": {"transcript_safe": True},
        "ai_transcript": {
            "message_role": "bubble",
            "message_index": "7",
            "message_order": "8",
            "partial": False,
            "selector_basis": "visible-dom",
            "safe": True,
        },
    }
    metadata = browser_ai_transcript_message_metadata(
        message,
        extension_id="fixture-extension",
        native_host="fixture.native.host",
        page_identity=identity,
    )

    assert cleanup["text"] == "Hello\nWorld"
    assert cleanup["removed_line_count"] == 1
    assert cleanup["removed_suffixes"] == ["Show more"]
    assert cleanup["stores_extra_text"] is False
    assert role == {"role": "assistant", "raw_role": "bubble", "basis": "provider_visible_label"}
    assert metadata["browser"]["adapter"] == "browser_ai_transcript"
    assert metadata["browser"]["transcript_safe"] is True
    assert metadata["browser"]["form_values_captured"] is False
    assert metadata["browser"]["cookies_captured"] is False
    assert metadata["ai_transcript"]["message_role"] == "assistant"
    assert metadata["ai_transcript"]["message_index"] == 7
    assert metadata["ai_transcript"]["message_order"] == 8
    assert metadata["ai_transcript"]["page_identity"] == identity
    assert metadata["ai_transcript"]["stores_extra_text"] is False
    assert len(metadata["ai_transcript"]["message_fingerprint"]) == 64


def test_capture_gate_decision_policy_keeps_private_context_out_of_text() -> None:
    hard_skip = _capture_gate_document(source="manual_cli_stdin", app="Telegram Desktop")
    sensitive_url = _capture_gate_document(
        source="browser_extension_explicit",
        url="https://example.test/login",
        metadata={"browser": {"field_safe": True, "event_kind": "committed_text"}},
    )
    sensitive_path = _capture_gate_document(
        source="saved_text_snapshot",
        paths=["/work/secret/token.txt"],
    )

    assert hard_skip["decision"] == "skip"
    assert hard_skip["confidence"] == "hard_skip"
    assert sensitive_url["decision"] == "metadata_only"
    assert sensitive_url["confidence"] == "sensitive_url"
    assert sensitive_path["decision"] == "metadata_only"
    assert sensitive_path["confidence"] == "sensitive_path"


def test_capture_gate_decision_allows_high_confidence_browser_and_ai_routes() -> None:
    browser = _capture_gate_document(
        source="browser_extension_explicit",
        url="https://example.test/editor",
        metadata={"browser": {"field_safe": True, "event_kind": "committed_text"}},
    )
    transcript = _capture_gate_document(
        source="browser_ai_transcript",
        url="https://chatgpt.com/c/fixture",
        window_title="ChatGPT",
        metadata={
            "browser": {"transcript_safe": True, "event_kind": "visible_message"},
            "ai_transcript": {"safe": True, "message_role": "assistant"},
        },
    )

    assert browser["decision"] == "allow_text"
    assert browser["confidence"] == "browser_url_and_field_allowed"
    assert transcript["decision"] == "allow_text"
    assert transcript["confidence"] == "browser_ai_transcript_known_ai_page_allowed"
    assert browser_ai_counterpart_identity("https://chatgpt.com/c/fixture", "ChatGPT")["is_ai"] is True


def test_capture_gate_decision_allows_generic_atspi_only_when_shape_is_safe() -> None:
    allowed = _capture_gate_document(
        source="atspi_text_changed_event",
        app="gedit",
        context="role=entry editable=true focused=true",
    )
    sensitive = _capture_gate_document(
        source="atspi_text_changed_event",
        app="password dialog",
        context="role=password editable=true focused=true",
    )

    assert allowed["decision"] == "allow_text"
    assert allowed["confidence"] == "atspi_generic_editable_text_allowed"
    assert sensitive["decision"] == "metadata_only"
    assert sensitive["confidence"] == "atspi_unknown_app"


def test_cli_capture_gate_uses_module_owned_document_builder(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T00:00:00Z"
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)
    policy = {
        "capture_gate": {
            "allow_text_source_adapters": ["browser_extension_explicit"],
        },
        "browser_extension": {
            "allowed_url_schemes": ["https:"],
            "allowed_event_kinds": ["committed_text"],
        },
    }
    metadata = {"browser": {"field_safe": True, "event_kind": "committed_text"}}
    kwargs = {
        "source": "browser_extension_explicit",
        "app": "Firefox",
        "window_title": "Fixture",
        "context": "event_kind=committed_text field_safe=true",
        "url": "https://example.test/write",
        "metadata": metadata,
        "paths": ["/tmp/fixture.txt"],
        "policy": policy,
    }

    assert cli.typing_capture_gate_decision(write_latest=False, **kwargs) == capture_gate_decision_document(
        **kwargs,
        default_policy=cli.default_typing_policy(),
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
    )
