from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


EnsureDocs = Callable[[], list[dict[str, Any]]]
LoadJsonDocument = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
PathExists = Callable[[Path], bool]
WriteLatestAndHistory = Callable[[dict[str, Any], Path, Path], list[dict[str, Any]]]


@dataclass(frozen=True)
class DictationValidationPaths:
    validate_latest: Path
    validate_history: Path
    transcript_latest: Path


def _check(level: str, key: str, message: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "level": level,
        "key": key,
        "message": message,
    }
    if data is not None:
        item["data"] = dict(data)
    return item


def validation_checks(
    *,
    paths: DictationValidationPaths,
    ensure_docs: EnsureDocs,
    load_json_document: LoadJsonDocument,
    path_exists: PathExists,
    schema_prefix: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    doc_errors = ensure_docs()
    checks.append(
        _check(
            "fail" if doc_errors else "ok",
            "dictation_docs_index",
            "dictation docs and index are present" if not doc_errors else "dictation docs/index write failed",
            {"errors": doc_errors},
        )
    )
    expected_schema = f"{schema_prefix}_dictation_transcript_event_v1"
    if path_exists(paths.transcript_latest):
        latest_data, latest_error = load_json_document(paths.transcript_latest)
        latest_schema = latest_data.get("schema") if isinstance(latest_data, dict) else None
        checks.append(
            _check(
                "ok" if latest_schema == expected_schema else "fail",
                "dictation_transcript_latest",
                "latest dictation transcript event is valid"
                if latest_schema == expected_schema
                else "latest dictation transcript event is invalid",
                {
                    "path": str(paths.transcript_latest),
                    "schema": latest_schema,
                    "expected_schema": expected_schema,
                    "error": latest_error,
                },
            )
        )
    else:
        checks.append(
            _check(
                "ok",
                "dictation_transcript_latest_empty",
                "no persisted dictation transcript event yet",
                {"path": str(paths.transcript_latest), "empty_state": True},
            )
        )
    return checks


def write_validation_latest(
    data: dict[str, Any],
    *,
    paths: DictationValidationPaths,
    write_latest_and_history: WriteLatestAndHistory,
) -> list[dict[str, Any]]:
    return write_latest_and_history(data, paths.validate_latest, paths.validate_history)
