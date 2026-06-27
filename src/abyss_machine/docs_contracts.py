from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from . import validation_contracts


DECISION_FILENAME_RE = re.compile(r"^(?P<sequence>\d{4})-(?P<slug>[a-z0-9][a-z0-9-]*[a-z0-9])\.md$")
REQUIRED_DECISION_SECTIONS = [
    "Status",
    "Date",
    "Index Tags",
    "Current Applicability",
    "Context",
    "Options Considered",
    "Decision",
    "Rationale",
    "Consequences",
    "Boundaries",
    "Review Log",
    "Source Surfaces",
    "Validation",
    "Follow-up Route",
]


def _schema(schema_prefix: str, suffix: str) -> str:
    return f"{schema_prefix}_{suffix}"


def markdown_section_map(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if not in_fence and line.startswith("# "):
            current = None
            continue
        if current is not None:
            sections.setdefault(current, []).append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def compact_markdown_text(text: str, limit: int = 420) -> str:
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        stripped = re.sub(r"^\s*[-*]\s+", "", stripped)
        stripped = stripped.replace("`", "")
        lines.append(stripped)
    compact = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if len(compact) > limit:
        return compact[: max(0, limit - 1)].rstrip() + "..."
    return compact


def section_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*[-*]\s+(.*\S)\s*$", line)
        if match:
            bullets.append(match.group(1).strip().strip("`"))
    return bullets


def decision_filename_parts(path: Path) -> dict[str, Any] | None:
    match = DECISION_FILENAME_RE.fullmatch(path.name)
    if not match:
        return None
    return {
        "sequence": int(match.group("sequence")),
        "sequence_text": match.group("sequence"),
        "slug": match.group("slug"),
    }


def decision_sort_key(path: Path) -> tuple[int, int, str]:
    parts = decision_filename_parts(path)
    if parts:
        return (0, int(parts["sequence"]), path.name)
    return (1, 9999, path.name)


def decision_record(
    path: Path,
    text: str,
    *,
    mtime: str | None = None,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    filename_parts = decision_filename_parts(path)
    sequence = filename_parts.get("sequence") if filename_parts else None
    sequence_text = filename_parts.get("sequence_text") if filename_parts else None
    slug = filename_parts.get("slug") if filename_parts else None
    title = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    sections = markdown_section_map(text)
    missing_sections = [section for section in REQUIRED_DECISION_SECTIONS if not sections.get(section)]
    status = compact_markdown_text(sections.get("Status", ""), limit=80)
    date_value = compact_markdown_text(sections.get("Date", ""), limit=40)
    index_tags = section_bullets(sections.get("Index Tags", ""))
    source_text = sections.get("Source Surfaces", "")
    source_surfaces = section_bullets(source_text)
    if not source_surfaces:
        source_surfaces = re.findall(r"`([^`]+)`", source_text)
    current_applicability_text = sections.get("Current Applicability", "")
    review_log_text = sections.get("Review Log", "")
    current_applicability_dates = sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", current_applicability_text)))
    review_log_dates = sorted(set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", review_log_text)))
    follow_up_text = sections.get("Follow-up Route", "")
    validation_text = sections.get("Validation", "") + "\n" + follow_up_text
    validation_commands = sorted(set(re.findall(r"abyss-machine [^\n`]+--json", validation_text)))
    issues: list[str] = []
    if not filename_parts:
        issues.append("filename is not NNNN-speaking-name.md")
    if not title:
        issues.append("missing title")
    elif sequence_text and not title.startswith(f"{sequence_text} "):
        issues.append("title does not start with filename sequence")
    if status not in {"proposed", "accepted", "superseded", "retired"}:
        issues.append("status is not in expected vocabulary")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        issues.append("date is not YYYY-MM-DD")
    if not index_tags:
        issues.append("no index tags listed")
    if not current_applicability_dates:
        issues.append("current applicability has no YYYY-MM-DD date")
    if not review_log_dates:
        issues.append("review log has no YYYY-MM-DD dated entries")
    if not source_surfaces:
        issues.append("no source surfaces listed")
    if not validation_commands:
        issues.append("no abyss-machine validation commands listed")
    issues.extend(f"missing section: {section}" for section in missing_sections)
    return {
        "path": str(path),
        "id": path.stem,
        "sequence": sequence,
        "slug": slug,
        "title": title,
        "status": status or None,
        "date": date_value or None,
        "ok": not issues,
        "issues": issues,
        "index_tags": index_tags,
        "source_surfaces": source_surfaces,
        "validation_commands": validation_commands,
        "context": compact_markdown_text(sections.get("Context", "")),
        "decision": compact_markdown_text(sections.get("Decision", "")),
        "rationale": compact_markdown_text(sections.get("Rationale", "")),
        "consequences": compact_markdown_text(sections.get("Consequences", "")),
        "boundaries": compact_markdown_text(sections.get("Boundaries", "")),
        "current_applicability": compact_markdown_text(current_applicability_text),
        "review_log": compact_markdown_text(review_log_text),
        "review_log_dates": review_log_dates,
        "follow_up_route": compact_markdown_text(follow_up_text),
        "options_considered": section_bullets(sections.get("Options Considered", "")),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        "mtime": mtime,
        "size_bytes": size_bytes,
    }


def decisions_index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    records: list[dict[str, Any]],
    decisions_root_exists: bool,
    source_root: Path,
    source_index: Path,
    generated_index: Path,
) -> dict[str, Any]:
    bad = [record for record in records if not record.get("ok")]
    statuses: dict[str, int] = {}
    tags: dict[str, int] = {}
    sequences: list[int] = []
    duplicate_sequences: list[int] = []
    seen_sequences: set[int] = set()
    for record in records:
        status = str(record.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        for tag in record.get("index_tags", []) if isinstance(record.get("index_tags"), list) else []:
            tags[str(tag)] = tags.get(str(tag), 0) + 1
        sequence = record.get("sequence")
        if isinstance(sequence, int):
            sequences.append(sequence)
            if sequence in seen_sequences and sequence not in duplicate_sequences:
                duplicate_sequences.append(sequence)
            seen_sequences.add(sequence)
    expected_sequences = list(range(1, max(sequences) + 1)) if sequences else []
    missing_sequences = [sequence for sequence in expected_sequences if sequence not in seen_sequences]
    sequence_issues: list[dict[str, Any]] = []
    if duplicate_sequences:
        sequence_issues.append({"kind": "duplicate_sequence", "sequences": duplicate_sequences})
    if missing_sequences:
        sequence_issues.append({"kind": "missing_sequence", "sequences": missing_sequences})
    if records and any(record.get("sequence") is None for record in records):
        sequence_issues.append({"kind": "unnumbered_records", "paths": [record.get("path") for record in records if record.get("sequence") is None]})
    return {
        "schema": _schema(schema_prefix, "docs_decisions_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "ok": not bad and not sequence_issues and decisions_root_exists,
        "source_root": str(source_root),
        "source_index": str(source_index),
        "generated_index": str(generated_index),
        "policy": {
            "generated": True,
            "do_not_hand_edit": True,
            "source_records_remain_truth": True,
            "purpose": "fast access to what changed when and why",
            "filename_contract": "NNNN-speaking-name.md",
            "do_not_renumber_accepted_records": True,
        },
        "summary": {
            "records": len(records),
            "statuses": statuses,
            "index_tags": tags,
            "first_sequence": min(sequences) if sequences else None,
            "last_sequence": max(sequences) if sequences else None,
            "next_sequence": (max(sequences) + 1) if sequences else 1,
            "missing_sequences": missing_sequences,
            "duplicate_sequences": duplicate_sequences,
            "issues": len(bad) + len(sequence_issues),
        },
        "sequence_issues": sequence_issues,
        "records": records,
    }


def spec_id(path: Path, prefix: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(path).strip("/")).strip("_").lower()
    return f"{prefix}_{slug}"[:96]


def paths_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    docs_root: Path,
    docs_doc_path: Path,
    latest_path: Path,
    index_path: Path,
    agents_mesh_latest_path: Path,
    agents_mesh_validate_latest_path: Path,
    decisions_index_latest_path: Path,
    history_root: Path,
    canonical: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "docs_paths_v1"),
        "version": version,
        "generated_at": generated_at,
        "root": str(docs_root),
        "contract": str(docs_doc_path),
        "preferred_standalone_contract": "/etc/abyss-machine/DOCS.md",
        "latest": str(latest_path),
        "index": str(index_path),
        "agents_mesh": str(agents_mesh_latest_path),
        "agents_mesh_validate": str(agents_mesh_validate_latest_path),
        "decisions_index": str(decisions_index_latest_path),
        "history_glob": str(history_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "canonical": canonical,
        "commands": {
            "status": "abyss-machine docs --json",
            "paths": "abyss-machine docs paths --json",
            "audit": "abyss-machine docs audit --json",
            "mesh": "abyss-machine docs mesh --json",
            "mesh_validate": "abyss-machine docs mesh-validate --json",
            "decisions_index": "abyss-machine docs decisions-index --json",
            "maps": "abyss-machine maps --json",
            "maps_packet": "abyss-machine maps packet --axis by-eval-packet --reader-profile proof-context --json",
            "maps_validate": "abyss-machine maps validate --json",
            "rag_refresh": "abyss-machine rag refresh --query TEXT --json",
            "rag_trace": "abyss-machine rag trace --query TEXT --json",
            "rag_validate": "abyss-machine rag validate --json",
        },
    }


def index_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    paths: dict[str, Any],
    documents: list[dict[str, Any]],
    agents_mesh_latest_path: Path,
    decisions_index_latest_path: Path,
    latest_audit_path: Path,
    audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": _schema(schema_prefix, "docs_index_v1"),
        "version": version,
        "generated_at": generated_at,
        "paths": paths,
        "documents": documents,
        "agents_mesh": str(agents_mesh_latest_path),
        "decisions_index": str(decisions_index_latest_path),
        "latest_audit": str(latest_audit_path),
        "latest_audit_summary": audit.get("summary") if isinstance(audit, dict) else None,
        "policy": {
            "single_purpose_docs": True,
            "do_not_duplicate_command_catalog": True,
            "generated_facts_do_not_replace_source_contracts": True,
            "agent_mesh_is_generated_from_source_cards": True,
            "decision_index_is_generated_from_source_records": True,
            "preferred_validation": "abyss-machine docs audit --json",
        },
    }


def agents_mesh_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: list[dict[str, Any]],
    strict: bool,
    index_path: Path,
    config_path: Path,
    current_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return validation_contracts.validation_document(
        schema=_schema(schema_prefix, "docs_agents_mesh_validate_v1"),
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="documentation agent mesh",
        extra={
            "index": str(index_path),
            "config": str(config_path),
            "current_summary": dict(current_summary) if isinstance(current_summary, dict) else None,
        },
    )
