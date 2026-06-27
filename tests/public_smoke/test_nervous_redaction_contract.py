from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.nervous_redaction import (
    high_entropy_token_candidates,
    redact_text,
    redaction_patterns,
    token_entropy,
)


FAKE_GITHUB_TOKEN = "ghp_" + "1" * 24
FAKE_OPENAI_PROJECT_KEY = "sk-" + "proj-" + "1234567890abcdefABCDEF_1234567890abcdef"


def test_nervous_redaction_patterns_and_entropy_detection_are_module_owned() -> None:
    classes = {str(item["class"]) for item in redaction_patterns()}
    assert {"github_token", "openai_project_key", "secret_assignment", "secret_cli_argument"}.issubset(classes)
    assert token_entropy("aaaaaaaaaaaaaaaa") == 0.0

    candidates = high_entropy_token_candidates("paste 9fKq_Z7mN2pLx8R5vT0aBcD3eFgH6jK9mP2sQ4uV here")
    assert candidates
    assert candidates[0]["class"] == "high_entropy_token"
    assert candidates[0]["fingerprint"]


def test_nervous_redact_text_contract_omits_raw_secret_material() -> None:
    raw = (
        "password=CorrectHorseBatteryStaple "
        f"{FAKE_GITHUB_TOKEN} "
        f"{FAKE_OPENAI_PROJECT_KEY}"
    )
    result = redact_text(
        raw,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert result["schema"] == "abyss_machine_nervous_redact_text_v1"
    assert result["version"] == "test"
    assert result["generated_at"] == "2026-06-25T12:00:00+00:00"
    assert result["ok"] is True
    assert result["summary"]["matches"] >= 3
    assert {"github_token", "openai_project_key", "secret_assignment"}.issubset(set(result["summary"]["classes"]))
    assert "CorrectHorseBatteryStaple" not in result["redacted_text"]
    assert FAKE_GITHUB_TOKEN not in result["redacted_text"]
    assert FAKE_OPENAI_PROJECT_KEY not in result["redacted_text"]
    assert all("fingerprint" in item and "length" in item for item in result["matches"])
