from __future__ import annotations

from typing import Any, Callable

from . import dictation_contracts


ConfigDocument = Callable[[], dict[str, Any]]
ReplacementsDocument = Callable[[], dict[str, Any]]
Now = Callable[[], str]


def apply_common_transcript_fixes(
    text: str,
    options: dict[str, Any],
    *,
    replacements_document: ReplacementsDocument,
) -> tuple[str, bool, list[str]]:
    return dictation_contracts.apply_common_transcript_fixes(text, options, replacements_document())


def detect_intent(
    text: str,
    *,
    config: dict[str, Any] | None = None,
    config_document: ConfigDocument | None = None,
    schema_prefix: str,
) -> dict[str, Any]:
    resolved_config = config if config is not None else config_document() if config_document is not None else {}
    return dictation_contracts.detect_intent(text, resolved_config, schema_prefix)


def intent_test_document(
    text: str,
    *,
    config_document: ConfigDocument,
    generated_at: str,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    return dictation_contracts.intent_test_document(
        text,
        config_document(),
        generated_at=generated_at,
        schema_prefix=schema_prefix,
        version=version,
    )


def postprocess_transcript_data(
    data: dict[str, Any],
    profile: dict[str, Any],
    *,
    config_document: ConfigDocument,
    replacements_document: ReplacementsDocument,
    schema_prefix: str,
) -> dict[str, Any]:
    return dictation_contracts.postprocess_transcript_data(
        data,
        profile,
        config=config_document(),
        replacements_doc=replacements_document(),
        schema_prefix=schema_prefix,
    )
