from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import dictation_contracts


LoadJsonDocument = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
WriteJsonDocument = Callable[[Path, dict[str, Any], int], None]
PathExists = Callable[[Path], bool]
Now = Callable[[], str]


@dataclass(frozen=True)
class DictationReplacementsPaths:
    replacements_path: Path


def default_document(schema_prefix: str, version: str) -> dict[str, Any]:
    return dictation_contracts.default_replacements_document(schema_prefix, version)


def load_document(
    paths: DictationReplacementsPaths,
    *,
    schema_prefix: str,
    version: str,
    load_json_document: LoadJsonDocument,
) -> dict[str, Any]:
    defaults = default_document(schema_prefix, version)
    loaded, error = load_json_document(paths.replacements_path)
    if loaded is None:
        if error != "missing":
            defaults["_load_error"] = error
        return defaults
    items = loaded.get("items")
    if not isinstance(items, list):
        defaults["_load_error"] = "items must be a list"
        return defaults
    loaded.setdefault("schema", f"{schema_prefix}_dictation_replacements_v1")
    loaded.setdefault("version", version)
    return loaded


def save_document(
    paths: DictationReplacementsPaths,
    doc: dict[str, Any],
    *,
    updated_by: str,
    schema_prefix: str,
    version: str,
    now: Now,
    write_json_document: WriteJsonDocument,
    mode: int = 0o664,
) -> None:
    clean = dictation_contracts.normalize_replacements_document(
        doc,
        schema_prefix=schema_prefix,
        version=version,
        updated_at=now(),
        updated_by=updated_by,
    )
    write_json_document(paths.replacements_path, clean, mode)


def apply_text(text: str, doc: dict[str, Any]) -> tuple[str, list[str]]:
    return dictation_contracts.apply_replacements(text, list(doc.get("items", [])))


def list_document(
    paths: DictationReplacementsPaths,
    doc: dict[str, Any],
    *,
    generated_at: str,
    schema_prefix: str,
    version: str,
    path_exists: PathExists,
) -> dict[str, Any]:
    return dictation_contracts.replacements_list_document(
        doc,
        path=str(paths.replacements_path),
        exists=path_exists(paths.replacements_path),
        generated_at=generated_at,
        schema_prefix=schema_prefix,
        version=version,
    )


def test_document(
    text: str,
    doc: dict[str, Any],
    *,
    generated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return dictation_contracts.replacements_test_document(
        text,
        doc,
        generated_at=generated_at,
        schema_prefix=schema_prefix,
        version=version,
    )


def replacement_id_from_text(text: str, fallback_token: Any = None) -> str:
    return dictation_contracts.replacement_id_from_text(text, fallback_token)


def add_replacement(
    paths: DictationReplacementsPaths,
    *,
    kind: str,
    source: str,
    target: str,
    item_id: str | None,
    ignore_case: bool,
    fallback_token: Any,
    schema_prefix: str,
    version: str,
    now: Now,
    load_json_document: LoadJsonDocument,
    write_json_document: WriteJsonDocument,
    path_exists: PathExists,
) -> dict[str, Any]:
    doc = load_document(
        paths,
        schema_prefix=schema_prefix,
        version=version,
        load_json_document=load_json_document,
    )
    items = list(doc.get("items", []))
    resolved_id = item_id or replacement_id_from_text(source, fallback_token)
    if any(isinstance(item, dict) and item.get("id") == resolved_id for item in items):
        raise ValueError(f"replacement id already exists: {resolved_id}")
    items.append(dictation_contracts.build_replacement_item(kind, source, target, resolved_id, ignore_case))
    doc["items"] = items
    save_document(
        paths,
        doc,
        updated_by=f"add:{resolved_id}",
        schema_prefix=schema_prefix,
        version=version,
        now=now,
        write_json_document=write_json_document,
    )
    return list_document(
        paths,
        doc,
        generated_at=now(),
        schema_prefix=schema_prefix,
        version=version,
        path_exists=path_exists,
    )


def remove_replacement(
    paths: DictationReplacementsPaths,
    *,
    item_id: str,
    schema_prefix: str,
    version: str,
    now: Now,
    load_json_document: LoadJsonDocument,
    write_json_document: WriteJsonDocument,
    path_exists: PathExists,
) -> dict[str, Any]:
    doc = load_document(
        paths,
        schema_prefix=schema_prefix,
        version=version,
        load_json_document=load_json_document,
    )
    original_items = doc.get("items", [])
    items = [item for item in original_items if not (isinstance(item, dict) and item.get("id") == item_id)]
    if len(items) == len(original_items):
        raise ValueError(f"replacement id not found: {item_id}")
    doc["items"] = items
    save_document(
        paths,
        doc,
        updated_by=f"remove:{item_id}",
        schema_prefix=schema_prefix,
        version=version,
        now=now,
        write_json_document=write_json_document,
    )
    return list_document(
        paths,
        doc,
        generated_at=now(),
        schema_prefix=schema_prefix,
        version=version,
        path_exists=path_exists,
    )
