from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import docs_contracts


DECISION_TEXT = """# 0001 Test Decision

## Status

accepted

## Date

2026-06-25

## Index Tags

- command-glue
- docs

## Current Applicability

- 2026-06-25: applies to portable seed docs.

## Context

Keep docs contracts importable.

## Options Considered

- Leave in CLI.
- Move stable parsing.

## Decision

Move stable parsing.

## Rationale

Agents need a portable contract.

## Consequences

CLI keeps file IO.

## Boundaries

No generated state becomes source truth.

## Review Log

- 2026-06-25: reviewed.

## Source Surfaces

- `src/abyss_machine/docs_contracts.py`

## Validation

- abyss-machine docs audit --json

## Follow-up Route

- abyss-machine docs decisions-index --json
"""


def test_docs_markdown_and_decision_record_contracts(tmp_path: Path) -> None:
    sections = docs_contracts.markdown_section_map(DECISION_TEXT)
    assert "Decision" in sections
    assert docs_contracts.compact_markdown_text("- `accepted`") == "accepted"
    assert docs_contracts.section_bullets("- `one`\n- two") == ["one", "two"]

    path = tmp_path / "0001-test-decision.md"
    record = docs_contracts.decision_record(
        path,
        DECISION_TEXT,
        mtime="2026-06-25T00:00:00+00:00",
        size_bytes=len(DECISION_TEXT),
    )
    assert record["ok"] is True
    assert record["sequence"] == 1
    assert record["slug"] == "test-decision"
    assert record["status"] == "accepted"
    assert record["validation_commands"] == [
        "abyss-machine docs audit --json",
        "abyss-machine docs decisions-index --json",
    ]

    bad = docs_contracts.decision_record(tmp_path / "bad.md", "## Status\n\nweird\n")
    assert bad["ok"] is False
    assert "filename is not NNNN-speaking-name.md" in bad["issues"]
    assert "missing title" in bad["issues"]


def test_docs_decisions_index_detects_sequence_issues(tmp_path: Path) -> None:
    records = [
        docs_contracts.decision_record(tmp_path / "0001-test-decision.md", DECISION_TEXT),
        docs_contracts.decision_record(tmp_path / "0001-duplicate-decision.md", DECISION_TEXT.replace("# 0001 Test Decision", "# 0001 Duplicate Decision")),
        docs_contracts.decision_record(tmp_path / "0003-third-decision.md", DECISION_TEXT.replace("# 0001 Test Decision", "# 0003 Third Decision")),
    ]
    index = docs_contracts.decisions_index_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        records=records,
        decisions_root_exists=True,
        source_root=tmp_path,
        source_index=tmp_path / "README.md",
        generated_index=tmp_path / "decisions-index.json",
    )
    assert index["schema"] == "abyss_machine_docs_decisions_index_v1"
    assert index["ok"] is False
    assert {"kind": "duplicate_sequence", "sequences": [1]} in index["sequence_issues"]
    assert {"kind": "missing_sequence", "sequences": [2]} in index["sequence_issues"]


def test_docs_paths_and_index_documents_are_portable_read_models(tmp_path: Path) -> None:
    paths = docs_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        docs_root=tmp_path / "docs",
        docs_doc_path=tmp_path / "DOCS.md",
        latest_path=tmp_path / "latest.json",
        index_path=tmp_path / "index.json",
        agents_mesh_latest_path=tmp_path / "agents-mesh.json",
        agents_mesh_validate_latest_path=tmp_path / "agents-mesh-validate.json",
        decisions_index_latest_path=tmp_path / "decisions-index.json",
        history_root=tmp_path / "history",
        canonical={"design": "/etc/abyss-machine/DESIGN.md"},
    )
    assert paths["schema"] == "abyss_machine_docs_paths_v1"
    assert paths["commands"]["decisions_index"] == "abyss-machine docs decisions-index --json"
    assert paths["canonical"] == {"design": "/etc/abyss-machine/DESIGN.md"}

    index = docs_contracts.index_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T00:00:00+00:00",
        paths=paths,
        documents=[{"id": "docs_contract", "exists": True}],
        agents_mesh_latest_path=tmp_path / "agents-mesh.json",
        decisions_index_latest_path=tmp_path / "decisions-index.json",
        latest_audit_path=tmp_path / "latest.json",
        audit={"summary": {"status": "ok"}},
    )
    assert index["schema"] == "abyss_machine_docs_index_v1"
    assert index["latest_audit_summary"] == {"status": "ok"}
    assert index["policy"]["generated_facts_do_not_replace_source_contracts"] is True


def test_docs_agents_mesh_validate_document_is_module_owned_with_cli_adapter(monkeypatch) -> None:
    from abyss_machine import cli

    generated_at = "2026-06-26T14:25:00Z"
    checks = [
        {"level": "ok", "key": "config", "message": "mesh config valid", "data": {"path": "docs/agents-mesh.json"}},
        {"level": "warn", "key": "card_exists:/etc/abyss-machine/AGENTS.md", "message": "optional missing", "data": {"path": "/etc/abyss-machine/AGENTS.md"}},
    ]
    current_summary = {"cards": 12, "required_cards": 9, "missing_required": 0}
    expected = docs_contracts.agents_mesh_validate_document(
        schema_prefix=cli.SCHEMA_PREFIX,
        version=cli.VERSION,
        generated_at=generated_at,
        checks=checks,
        strict=True,
        index_path=cli.DOCS_AGENTS_MESH_LATEST_PATH,
        config_path=cli.AGENTS_MESH_CONFIG_PATH,
        current_summary=current_summary,
    )
    monkeypatch.setattr(cli, "now_iso", lambda: generated_at)

    assert cli.docs_agents_mesh_validate_document_from_checks(
        checks,
        strict=True,
        current_summary=current_summary,
    ) == expected
    assert expected["schema"] == "abyss_machine_docs_agents_mesh_validate_v1"
    assert expected["scope"] == "documentation agent mesh"
    assert expected["ok"] is False
    assert expected["summary"] == {"status": "warn", "fails": 0, "warnings": 1, "checks": 2}
    assert expected["current_summary"] == current_summary
    assert expected["policy"]["read_only"] is True


def test_docs_paths_cli_surface_is_json_read_only() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "docs", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_docs_paths_v1"
    assert payload["commands"]["audit"] == "abyss-machine docs audit --json"
    assert payload["canonical"]["decisions_generated_index"].endswith("decisions-index.min.json")
