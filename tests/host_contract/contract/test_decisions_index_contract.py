from __future__ import annotations

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_decision_record_extracts_dated_applicability_and_review_log(tmp_path, abyss_machine_module) -> None:
    record_path = tmp_path / "0001-test-decision.md"
    record_path.write_text(
        """# 0001 Test Decision

## Status

accepted

## Date

2026-05-21

## Index Tags

- test

## Current Applicability

As of 2026-05-21, this decision is active.

## Context

Test context.

## Options Considered

- Option A:

## Decision

Choose the test route.

## Rationale

Because it protects the contract.

## Consequences

The index can expose applicability.

## Boundaries

This is only a fixture.

## Review Log

- 2026-05-21: Initial fixture.

## Source Surfaces

- `/tmp/test`

## Validation

- `abyss-machine docs decisions-index --json`

## Follow-up Route

Run `abyss-machine docs decisions-index --json`.
""",
        encoding="utf-8",
    )

    record = abyss_machine_module.docs_decision_record(record_path)

    assert record["ok"] is True
    assert record["current_applicability"] == "As of 2026-05-21, this decision is active."
    assert record["review_log_dates"] == ["2026-05-21"]


def test_decision_record_rejects_undated_applicability_and_review_log(tmp_path, abyss_machine_module) -> None:
    record_path = tmp_path / "0001-test-decision.md"
    record_path.write_text(
        """# 0001 Test Decision

## Status

accepted

## Date

2026-05-21

## Index Tags

- test

## Current Applicability

This decision is active.

## Context

Test context.

## Options Considered

- Option A:

## Decision

Choose the test route.

## Rationale

Because it protects the contract.

## Consequences

The index can expose applicability.

## Boundaries

This is only a fixture.

## Review Log

- Initial fixture.

## Source Surfaces

- `/tmp/test`

## Validation

- `abyss-machine docs decisions-index --json`

## Follow-up Route

Run `abyss-machine docs decisions-index --json`.
""",
        encoding="utf-8",
    )

    record = abyss_machine_module.docs_decision_record(record_path)

    assert record["ok"] is False
    assert "current applicability has no YYYY-MM-DD date" in record["issues"]
    assert "review log has no YYYY-MM-DD dated entries" in record["issues"]
