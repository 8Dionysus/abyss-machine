from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.validation_contracts import (
    subsystem_validate_document,
    subsystems_validate_document,
    validation_document,
    validation_summary,
)


def test_validation_document_summary_and_strict_semantics() -> None:
    checks = [
        {"level": "ok", "key": "present", "message": "present"},
        {"level": "warn", "key": "optional", "message": "optional missing"},
    ]

    non_strict = validation_document(
        schema="abyss_machine_example_validate_v1",
        version="1.2.3",
        generated_at="2026-06-26T13:00:00Z",
        checks=checks,
        strict=False,
        scope="example subsystem",
    )
    strict = validation_document(
        schema="abyss_machine_example_validate_v1",
        version="1.2.3",
        generated_at="2026-06-26T13:00:00Z",
        checks=checks,
        strict=True,
        scope="example subsystem",
    )
    failed = validation_document(
        schema="abyss_machine_example_validate_v1",
        version="1.2.3",
        generated_at="2026-06-26T13:00:00Z",
        checks=[{"level": "fail", "key": "broken", "message": "broken"}],
        strict=False,
        scope="example subsystem",
    )

    assert validation_summary(checks) == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert non_strict["ok"] is True
    assert strict["ok"] is False
    assert failed["ok"] is False
    assert failed["summary"]["status"] == "fail"


def test_cli_validation_document_delegates_to_module_contract(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T13:05:00Z"
    checks = [{"level": "ok", "key": "ready", "message": "ready"}]
    extra = {
        "paths": {"latest": "/tmp/example/latest.json"},
        "policy": {"read_only": False, "future_safe": True},
    }
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    expected = validation_document(
        schema="abyss_machine_example_validate_v1",
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=False,
        scope="example subsystem",
        extra=extra,
    )

    assert cli.validation_summary(checks) == validation_summary(checks)
    assert cli.validation_document(
        "abyss_machine_example_validate_v1",
        checks,
        False,
        "example subsystem",
        extra,
    ) == expected
    assert expected["policy"] == extra["policy"]


def test_subsystem_validation_documents_are_module_owned_with_cli_adapters(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T15:20:00Z"
    checks = [{"level": "warn", "key": "latest", "message": "latest optional missing"}]
    paths = {"schema": "abyss_machine_example_paths_v1"}
    results = {"example": {"summary": {"status": "warn", "fails": 0, "warnings": 1, "checks": 1}}}
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    expected_one = subsystem_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        subsystem="stack-bridge",
        checks=checks,
        strict=True,
        paths=paths,
        latest="/var/lib/abyss-machine/stack-bridge/validate/latest.json",
    )
    expected_all = subsystems_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=False,
        results=results,
    )

    assert cli.subsystem_validate_document_from_checks(
        "stack-bridge",
        checks,
        strict=True,
        paths=paths,
        latest="/var/lib/abyss-machine/stack-bridge/validate/latest.json",
    ) == expected_one
    assert cli.subsystems_validate_document_from_checks(
        checks,
        strict=False,
        results=results,
    ) == expected_all
    assert expected_one["schema"] == "abyss_machine_stack_bridge_validate_v1"
    assert expected_one["scope"] == "stack-bridge subsystem"
    assert expected_one["ok"] is False
    assert expected_one["non_claims"][0].startswith("Subsystem validators")
    assert expected_all["schema"] == "abyss_machine_subsystems_validate_v1"
    assert expected_all["results"] == {"example": results["example"]["summary"]}
