from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_retention import (
    apply_document,
    apply_refused_result,
    file_candidate_record,
    layer_summary,
    plan_document,
    plan_refused_result,
    privacy_route,
    privacy_route_complete,
    root_missing_record,
    route_specs,
    validate_document,
)


ROOTS = {
    "facts": "/var/lib/abyss-machine/nervous/facts",
    "events": "/var/lib/abyss-machine/nervous/events",
    "episodes": "/var/lib/abyss-machine/nervous/episodes",
    "retrieval": "/var/lib/abyss-machine/nervous/retrieval",
    "synthesis": "/var/lib/abyss-machine/nervous/synthesis",
    "evals": "/var/lib/abyss-machine/nervous/evals",
    "checks": "/var/lib/abyss-machine/nervous/checks",
    "private_capture_artifacts": "/srv/abyss-machine/storage/nervous/captures",
    "browser_content": "/srv/abyss-machine/storage/nervous/browser-content",
}


def test_nervous_retention_route_specs_are_module_owned_contracts() -> None:
    routes = route_specs(
        {
            "retention": {
                "facts_days": "120",
                "raw_events_days": "21",
                "retrieval_packs_days": "10",
                "private_capture_artifacts_days": "3",
            }
        },
        ROOTS,
    )

    by_layer = {item["layer"]: item for item in routes}
    assert by_layer["facts"]["days"] == 120
    assert by_layer["facts"]["apply_allowed"] is False
    assert by_layer["retrieval"]["days"] == 10
    assert by_layer["retrieval"]["apply_allowed"] is True
    assert by_layer["private_capture_artifacts"]["extensions"] == [".png"]
    assert by_layer["browser_content"]["days"] == 3


def test_nervous_retention_file_candidate_classification_is_pure_contract() -> None:
    now = dt.datetime(2026, 6, 26, 12, 0, tzinfo=dt.timezone.utc)
    old = now - dt.timedelta(days=40)
    retrieval = {
        "layer": "retrieval",
        "root": ROOTS["retrieval"],
        "days": 10,
        "apply_allowed": True,
        "reason": "operator recall packs are reproducible from the index",
    }

    candidate = file_candidate_record(
        retrieval,
        path=f"{ROOTS['retrieval']}/2026/05/old.jsonl",
        relative="2026/05/old.jsonl",
        suffix=".jsonl",
        size_bytes=2048,
        mtime=old,
        now_time=now,
    )
    latest = file_candidate_record(
        retrieval,
        path=f"{ROOTS['retrieval']}/latest.json",
        relative="latest.json",
        suffix=".json",
        size_bytes=512,
        mtime=old,
        now_time=now,
    )
    wrong_extension = file_candidate_record(
        retrieval,
        path=f"{ROOTS['retrieval']}/old.bin",
        relative="old.bin",
        suffix=".bin",
        size_bytes=512,
        mtime=old,
        now_time=now,
    )

    assert candidate["candidate"] is True
    assert candidate["reason"] == "expired_and_apply_allowed"
    assert candidate["age_days"] == 40.0
    assert latest["protected"] is True
    assert latest["candidate"] is False
    assert wrong_extension["protected"] is True
    assert root_missing_record(retrieval)["reason"] == "root_missing"


def test_nervous_retention_plan_apply_and_validate_envelopes_are_module_owned() -> None:
    routes = route_specs({}, ROOTS)
    files = [
        {
            "layer": "retrieval",
            "path": f"{ROOTS['retrieval']}/old.jsonl",
            "exists": True,
            "size_bytes": 100,
            "candidate": True,
            "protected": False,
        },
        {
            "layer": "facts",
            "path": f"{ROOTS['facts']}/latest.json",
            "exists": True,
            "size_bytes": 50,
            "candidate": False,
            "protected": True,
        },
    ]
    paths = {
        "latest": "/var/lib/abyss-machine/nervous/retention/latest.json",
        "daily_glob": "/var/lib/abyss-machine/nervous/retention/YYYY/MM/YYYY-MM-DD.jsonl",
    }
    plan = plan_document(
        routes=routes,
        files=files,
        route_errors=[],
        paths=paths,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )
    apply = apply_document(
        plan=plan,
        dry_run=True,
        confirm=False,
        removed=[],
        errors=[],
        paths=paths,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )
    validate = validate_document(
        plan=plan,
        latest_exists=False,
        latest_path=paths["latest"],
        latest_error="missing",
        validate_latest_path="/var/lib/abyss-machine/nervous/retention/validate/latest.json",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )

    assert plan["schema"] == "abyss_machine_nervous_retention_plan_v1"
    assert plan["summary"]["candidates"] == 1
    assert plan["policy"]["facts_delete_behavior"] == "explicit forget only"
    assert apply["schema"] == "abyss_machine_nervous_retention_apply_v1"
    assert apply["applied"] is False
    assert apply["summary"]["candidate_files"] == 1
    assert validate["schema"] == "abyss_machine_nervous_retention_validate_v1"
    assert validate["ok"] is True
    assert validate["summary"]["warnings"] == 1
    assert plan_refused_result("abyss_machine", "test", "now")["refused"] is True
    assert apply_refused_result("abyss_machine", "test", "now")["refused"] is True


def test_nervous_retention_privacy_route_is_module_owned_contract() -> None:
    plan = plan_document(
        routes=route_specs({}, ROOTS),
        files=[
            {
                "layer": "private_capture_artifacts",
                "path": f"{ROOTS['private_capture_artifacts']}/old.png",
                "exists": True,
                "size_bytes": 2048,
                "candidate": True,
                "protected": False,
            },
            {
                "layer": "retrieval",
                "path": f"{ROOTS['retrieval']}/old.jsonl",
                "exists": True,
                "size_bytes": 1024,
                "candidate": True,
                "protected": False,
            },
        ],
        route_errors=[],
        paths={"latest": "/tmp/latest.json"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )
    route = privacy_route(
        plan,
        schema_prefix="abyss_machine",
        retention_latest_path="/var/lib/abyss-machine/nervous/retention/latest.json",
        retention_validate_latest_path="/var/lib/abyss-machine/nervous/retention/validate/latest.json",
        privacy_config_path="/etc/abyss-machine/nervous-privacy.json",
        privacy_state_path="/var/lib/abyss-machine/nervous/privacy/state.json",
    )

    assert layer_summary(plan["summary"])["private_capture_artifacts"]["candidate_bytes"] == 2048
    assert route["schema"] == "abyss_machine_nervous_retention_privacy_route_v1"
    assert route["complete"] is True
    assert privacy_route_complete(route) is True
    assert route["safe_next_action"]["executes_commands"] is False
    assert route["safe_next_action"]["requires_explicit_confirm_for_deletion"] is True
    assert route["policy"]["facts_delete_behavior_explicit_forget_only"] is True
    assert route["policy"]["raw_private_content"] is False
    assert route["candidate_layers"][0]["layer"] == "private_capture_artifacts"


def test_nervous_retention_cli_import_uses_contract_module() -> None:
    from abyss_machine import cli

    routes = cli.nervous_retention_contracts.route_specs({}, ROOTS)
    assert routes[0]["layer"] == "facts"
    assert routes[3]["layer"] == "retrieval"
    plan = plan_document(
        routes=routes,
        files=[
            {
                "layer": "retrieval",
                "path": f"{ROOTS['retrieval']}/old.jsonl",
                "exists": True,
                "size_bytes": 1024,
                "candidate": True,
                "protected": False,
            },
        ],
        route_errors=[],
        paths={"latest": "/tmp/latest.json"},
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-26T12:00:00+00:00",
    )
    route = cli.nervous_retention_privacy_route(plan)
    assert cli.nervous_retention_privacy_route_complete(route) is True
