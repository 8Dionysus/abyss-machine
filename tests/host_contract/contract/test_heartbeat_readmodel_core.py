from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_heartbeat_freshness_class_boundaries(abyss_machine_module) -> None:
    machine = abyss_machine_module

    assert machine.heartbeat_freshness_class(True, 30, 900, 300) == "fresh"
    assert machine.heartbeat_freshness_class(True, 301, 900, 300) == "aging"
    assert machine.heartbeat_freshness_class(True, 901, 900, 300) == "stale"
    assert machine.heartbeat_freshness_class(False, None, 900, 300, "missing") == "missing"
    assert machine.heartbeat_freshness_class(False, None, 900, 300, "invalid json") == "invalid"


def test_heartbeat_source_freshness_tracks_stale_streak_and_last_ok(abyss_machine_module) -> None:
    machine = abyss_machine_module
    previous = {
        "source_freshness": {
            "sources": {
                "doctor": {
                    "stale_streak": 2,
                    "last_ok_at": "2026-05-19T10:00:00+00:00",
                }
            }
        }
    }
    inputs = {
        "doctor": {
            "name": "doctor",
            "path": "/var/lib/abyss-machine/doctor/latest.json",
            "ok": True,
            "status": "ok",
            "generated_at": "2026-05-19T11:00:00+00:00",
            "age_sec": 8000,
            "error": None,
        },
        "changes": {
            "name": "changes",
            "path": "/var/lib/abyss-machine/changes/index.json",
            "ok": False,
            "status": None,
            "generated_at": None,
            "age_sec": None,
            "error": "missing",
        },
    }

    result = machine.heartbeat_source_freshness(inputs, previous)

    assert result["schema"] == "abyss_machine_heartbeat_source_freshness_v1"
    assert result["sources"]["doctor"]["freshness_class"] == "stale"
    assert result["sources"]["doctor"]["stale_streak"] == 3
    assert result["sources"]["doctor"]["last_ok_at"] == "2026-05-19T11:00:00+00:00"
    assert result["sources"]["changes"]["freshness_class"] == "missing"
    assert result["summary"]["stale_sources"] == ["doctor"]
    assert result["summary"]["missing_or_invalid_sources"] == ["changes"]


def test_heartbeat_parse_user_jobs_extracts_waiting_heartbeat(abyss_machine_module) -> None:
    text = """JOB UNIT                                  TYPE  STATE
123 abyss-machine-heartbeat.service       start waiting
124 abyss-machine-doctor.service          start running
125 abyss-machine-heartbeat.timer         start waiting
3 jobs listed.
"""

    jobs = abyss_machine_module.heartbeat_parse_user_jobs(text)

    assert [job["job"] for job in jobs] == [123, 124, 125]
    assert jobs[0]["unit"] == "abyss-machine-heartbeat.service"
    assert jobs[0]["state"] == "waiting"
    assert jobs[1]["unit"] == "abyss-machine-doctor.service"


def test_heartbeat_parse_timer_line_keeps_passed_interval(abyss_machine_module) -> None:
    line = (
        "Tue 2026-05-19 09:11:47 CST 9min "
        "Tue 2026-05-19 08:56:47 CST 5min ago "
        "abyss-machine-heartbeat.timer abyss-machine-heartbeat.service"
    )

    parsed = abyss_machine_module.heartbeat_parse_timer_line(line)

    assert parsed["next_beat_at"] == "Tue 2026-05-19 09:11:47 CST"
    assert parsed["left"] == "9min"
    assert parsed["last_trigger"] == "Tue 2026-05-19 08:56:47 CST"
    assert parsed["passed"] == "5min ago"


def test_heartbeat_candidate_lifecycle_persists_and_resolves(abyss_machine_module) -> None:
    previous = {
        "candidate_lifecycle": {
            "active": [
                {
                    "id": "resource-watch",
                    "active": True,
                    "first_seen_at": "2026-05-19T10:00:00+00:00",
                    "last_seen_at": "2026-05-19T10:15:00+00:00",
                    "consecutive_beats": 2,
                    "total_beats": 3,
                    "severity": "watch",
                    "severity_history": ["warning", "watch"],
                    "category": "resource",
                    "owner_route": "abyss-machine",
                    "command": None,
                    "reason": "resource pressure",
                    "resolved_at": None,
                },
                {
                    "id": "old-warning",
                    "active": True,
                    "first_seen_at": "2026-05-19T09:00:00+00:00",
                    "last_seen_at": "2026-05-19T10:15:00+00:00",
                    "consecutive_beats": 1,
                    "total_beats": 1,
                    "severity": "warning",
                    "severity_history": ["warning"],
                    "category": "doctor",
                    "owner_route": "abyss-machine",
                    "command": None,
                    "reason": "old warning",
                    "resolved_at": None,
                },
            ]
        }
    }
    candidates = [
        {
            "id": "resource-watch",
            "severity": "critical",
            "category": "resource",
            "owner_route": "abyss-machine",
            "command": None,
            "reason": "resource pressure",
        },
        {
            "id": "new-info",
            "severity": "info",
            "category": "heartbeat",
            "owner_route": "abyss-machine",
            "command": None,
            "reason": "new candidate",
        },
    ]

    result = abyss_machine_module.heartbeat_candidate_lifecycle(
        candidates,
        previous,
        "2026-05-19T10:30:00+00:00",
    )

    active = {item["id"]: item for item in result["active"]}
    resolved = {item["id"]: item for item in result["recently_resolved"]}
    assert active["resource-watch"]["consecutive_beats"] == 3
    assert active["resource-watch"]["total_beats"] == 4
    assert active["resource-watch"]["severity_history"] == ["warning", "watch", "critical"]
    assert active["new-info"]["first_seen_at"] == "2026-05-19T10:30:00+00:00"
    assert resolved["old-warning"]["active"] is False
    assert resolved["old-warning"]["resolved_at"] == "2026-05-19T10:30:00+00:00"
    assert result["summary"]["persistent"] == 1


def test_heartbeat_self_awareness_breath_compacts_autolink_without_execution(monkeypatch, abyss_machine_module) -> None:
    machine = abyss_machine_module
    autolink = {
        "schema": "abyss_machine_self_awareness_autolink_v1",
        "ok": True,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "state_digest": "a" * 32,
        "state_delta": {
            "previous_seen": True,
            "state_changed": True,
            "added_services": ["aoa-browser"],
            "removed_services": [],
            "changed_services": [],
            "added_requirements": ["stack.trace-backend"],
            "removed_requirements": [],
            "changed_requirements": [],
            "open_stack_requirements_delta": 1,
            "working_stack_usage_gaps_delta": 1,
        },
        "summary": {
            "organ_links": 2,
            "organ_links_complete": 2,
            "stack_requirement_links": 1,
            "stack_requirement_links_complete": 1,
            "working_stack_usage_gaps": 1,
            "open_stack_requirements": 1,
            "synthetic_scenarios": 3,
            "synthetic_scenarios_complete": 3,
            "full_stack_potential_covered": False,
        },
        "organ_links": [
            {"service": "prometheus", "usage_gap": None},
            {"service": "aoa-browser", "usage_gap": "runtime smoke failed"},
        ],
        "stack_requirement_links": [
            {"requirement_id": "stack.trace-backend", "automatic_link_state": "open_stack_blocker"}
        ],
    }

    def fake_load(path, schema):
        if path == machine.SELF_AWARENESS_AUTOLINK_LATEST_PATH:
            return autolink
        if path == machine.SELF_AWARENESS_WORKING_STACK_LATEST_PATH:
            return {"schema": "abyss_machine_self_awareness_working_stack_inventory_v1"}
        if path == machine.SELF_AWARENESS_COVERAGE_AUDIT_LATEST_PATH:
            return {"schema": "abyss_machine_self_awareness_objective_coverage_audit_v1", "working_stack_link_integrity": {"ok": True}}
        if path == machine.SELF_AWARENESS_STACK_CLOSURE_DOSSIER_LATEST_PATH:
            return {
                "schema": "abyss_machine_self_awareness_stack_closure_dossier_v1",
                "working_stack_activation_dossier": {"entries": []},
            }
        if path == machine.SELF_AWARENESS_ACTIVATION_SMOKE_LATEST_PATH:
            return {"schema": "abyss_machine_self_awareness_working_stack_activation_smoke_v1", "ok": True, "summary": {"rows": 0}, "rows": []}
        return {"schema": schema, "ok": True}

    monkeypatch.setattr(machine, "load_latest_json", fake_load)
    monkeypatch.setattr(machine, "self_awareness_autolink_complete", lambda doc: doc is autolink)
    monkeypatch.setattr(machine, "self_awareness_working_stack_link_integrity_matrix_complete", lambda doc: True)
    monkeypatch.setattr(machine, "self_awareness_activation_smoke_needs_refresh", lambda smoke, entries: False)
    monkeypatch.setattr(machine, "heartbeat_age_seconds", lambda generated_at: 30.0)

    breath = machine.heartbeat_self_awareness_breath(
        {"self_awareness_breath": {"state_digest": "b" * 32}},
        "2026-01-01T00:01:00+00:00",
    )

    assert machine.heartbeats_paths()["inputs"]["self_awareness_autolink"] == str(machine.SELF_AWARENESS_AUTOLINK_LATEST_PATH)
    assert breath["schema"] == "abyss_machine_heartbeat_self_awareness_breath_v1"
    assert breath["ok"] is True
    assert breath["status"] == "linked"
    assert breath["autolink"]["refreshed"] is False
    assert breath["state_changed_since_previous_heartbeat"] is True
    assert breath["summary"]["organ_links"] == 2
    assert breath["summary"]["open_potential_services"] == ["aoa-browser"]
    assert breath["summary"]["open_stack_requirement_ids"] == ["stack.trace-backend"]
    assert breath["state_delta"]["added_services"] == ["aoa-browser"]
    assert breath["policy"]["does_not_run_cycle"] is True
    assert breath["policy"]["does_not_run_probe"] is True
    assert breath["policy"]["action_execution"] is False
    assert breath["policy"]["host_layer_mutates_stack"] is False
