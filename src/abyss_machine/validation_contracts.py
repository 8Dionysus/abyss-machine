from __future__ import annotations

from typing import Any, Iterable, Mapping


def validation_summary(checks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    check_items = [item for item in checks if isinstance(item, Mapping)]
    fails = sum(1 for item in check_items if item.get("level") == "fail")
    warnings = sum(1 for item in check_items if item.get("level") == "warn")
    return {
        "status": "fail" if fails else "warn" if warnings else "ok",
        "fails": fails,
        "warnings": warnings,
        "checks": len(check_items),
    }


def validation_document(
    *,
    schema: str,
    version: str,
    generated_at: str,
    checks: Iterable[Mapping[str, Any]],
    strict: bool,
    scope: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    check_items = [dict(item) for item in checks if isinstance(item, Mapping)]
    summary = validation_summary(check_items)
    data: dict[str, Any] = {
        "schema": schema,
        "version": version,
        "generated_at": generated_at,
        "ok": summary["fails"] == 0 and (not strict or summary["warnings"] == 0),
        "strict": strict,
        "scope": scope,
        "summary": summary,
        "checks": check_items,
        "policy": {
            "read_only": True,
            "future_safe": True,
            "severity_rule": "fail only for broken contracts or protected-boundary violations; warn for stale, missing optional, or future-expandable evidence",
        },
    }
    if extra:
        data.update(dict(extra))
    return data


def subsystem_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    subsystem: str,
    checks: Iterable[Mapping[str, Any]],
    strict: bool,
    paths: Mapping[str, Any],
    latest: Any,
) -> dict[str, Any]:
    schema_slug = {"processes": "process", "stack-bridge": "stack_bridge"}.get(subsystem, subsystem)
    return validation_document(
        schema=f"{schema_prefix}_{schema_slug}_validate_v1",
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope=f"{subsystem} subsystem",
        extra={
            "subsystem": subsystem,
            "paths": dict(paths),
            "latest": str(latest),
            "non_claims": [
                "Subsystem validators are contract validators, not heavy benchmarks.",
                "Missing optional latest evidence is a warning so future expansion is not blocked prematurely.",
            ],
        },
    )


def subsystems_validate_document(
    *,
    schema_prefix: str,
    version: str,
    generated_at: str,
    checks: Iterable[Mapping[str, Any]],
    strict: bool,
    results: Mapping[str, Any],
) -> dict[str, Any]:
    result_summaries = {
        str(name): result.get("summary")
        for name, result in results.items()
        if isinstance(result, Mapping)
    }
    return validation_document(
        schema=f"{schema_prefix}_subsystems_validate_v1",
        version=version,
        generated_at=generated_at,
        checks=checks,
        strict=strict,
        scope="all registered subsystems",
        extra={"results": result_summaries},
    )
