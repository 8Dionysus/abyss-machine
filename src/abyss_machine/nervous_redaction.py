from __future__ import annotations

import collections
import hashlib
import math
import re
from typing import Any


def redaction_patterns() -> list[dict[str, Any]]:
    return [
        {"class": "private_key", "pattern": r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", "flags": re.DOTALL},
        {"class": "bearer_token", "pattern": r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", "flags": 0},
        {"class": "github_token", "pattern": r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", "flags": 0},
        {"class": "huggingface_token", "pattern": r"\bhf_[A-Za-z0-9]{20,}\b", "flags": 0},
        {"class": "openai_project_key", "pattern": r"\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}\b", "flags": 0},
        {"class": "openai_key", "pattern": r"\bsk-[A-Za-z0-9]{20,}\b", "flags": 0},
        {"class": "jwt_token", "pattern": r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "flags": 0},
        {"class": "stripe_key", "pattern": r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b", "flags": 0},
        {"class": "aws_access_key", "pattern": r"\bAKIA[0-9A-Z]{16}\b", "flags": 0},
        {"class": "secret_assignment", "pattern": r"(?i)\b(password|passwd|token|api[_-]?key|secret|credential|cookie)\b\s*[:=]\s*['\"]?[^\s'\";]{6,}", "flags": 0},
        {"class": "secret_cli_argument", "pattern": r"(?i)\b[\w./:-]*(?:token|secret|password|passwd|api[_-]?key|set[_-]?key|key)\b\s+['\"]?[A-Za-z0-9._~+/=-]{20,}", "flags": 0},
    ]


def token_entropy(token: str) -> float:
    value = str(token or "")
    if not value:
        return 0.0
    counts = collections.Counter(value)
    total = float(len(value))
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def high_entropy_token_candidates(text: str) -> list[dict[str, Any]]:
    raw = str(text or "")
    candidates: list[dict[str, Any]] = []
    token_re = re.compile(r"(?<![A-Za-z0-9._~+/=-])([A-Za-z0-9._~+/=-]{24,})(?![A-Za-z0-9._~+/=-])")
    for match in token_re.finditer(raw):
        token = match.group(1)
        start, end = match.span(1)
        if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", token):
            continue
        classes = sum(
            any(predicate(ch) for ch in token)
            for predicate in (
                str.islower,
                str.isupper,
                str.isdigit,
                lambda ch: ch in "._~+/=-",
            )
        )
        if classes < 3:
            continue
        entropy = token_entropy(token)
        unique_ratio = len(set(token)) / max(1, len(token))
        if entropy < 3.65 or unique_ratio < 0.34:
            continue
        fingerprint = hashlib.sha256(token.encode("utf-8", errors="replace")).hexdigest()[:16]
        candidates.append({
            "class": "high_entropy_token",
            "start": start,
            "end": end,
            "length": len(token),
            "fingerprint": fingerprint,
            "entropy": round(entropy, 3),
        })
    return candidates


def redaction_candidates(text: str, patterns: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for spec in patterns or redaction_patterns():
        pattern = re.compile(str(spec["pattern"]), int(spec.get("flags", 0)))
        for match in list(pattern.finditer(text)):
            secret = match.group(0)
            start, end = match.span()
            fingerprint = hashlib.sha256(secret.encode("utf-8", errors="replace")).hexdigest()[:16]
            candidates.append({
                "class": spec["class"],
                "start": start,
                "end": end,
                "length": len(secret),
                "fingerprint": fingerprint,
            })
    candidates.extend(high_entropy_token_candidates(text))
    candidates.sort(key=lambda item: (int(item["start"]), -int(item["length"])))
    return candidates


def non_overlapping_matches(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    cursor = 0
    for item in candidates:
        start = int(item["start"])
        end = int(item["end"])
        if start < cursor:
            continue
        matches.append(item)
        cursor = end
    return matches


def apply_matches(text: str, matches: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    cursor = 0
    for item in matches:
        start = int(item["start"])
        end = int(item["end"])
        pieces.append(text[cursor:start])
        pieces.append(f"[REDACTED:{item['class']}:{item['length']}:{item['fingerprint']}]")
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def redact_text(
    text: str,
    *,
    schema_prefix: str = "abyss_machine",
    version: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    raw = str(text or "")
    matches = non_overlapping_matches(redaction_candidates(raw))
    return {
        "schema": f"{schema_prefix}_nervous_redact_text_v1",
        "version": version,
        "generated_at": generated_at,
        "ok": True,
        "matches": matches,
        "summary": {
            "matches": len(matches),
            "classes": sorted({str(item["class"]) for item in matches}),
        },
        "redacted_text": apply_matches(raw, matches),
        "non_claims": [
            "Matches include fingerprints and lengths, not raw secret values.",
            "This is a dry-run helper and not a complete DLP engine.",
        ],
    }
