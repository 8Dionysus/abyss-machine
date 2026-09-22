"""Transport success must never become host write permission."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from abyss_machine import code_intelligence_provider as provider  # noqa: E402


def storage_allow() -> dict:
    return {
        "ok": True,
        "decision": "allow",
        "strict_write_decision": "allow",
        "write_permission": True,
        "capacity_only": False,
    }


@pytest.mark.parametrize(
    "override",
    [
        {"decision": "reroute", "write_permission": False},
        {"decision": "cleanup_first", "write_permission": False},
        {"decision": "deny", "write_permission": False},
        {"decision": "unknown"},
        {"decision": None},
        {"capacity_only": True, "write_permission": False},
        {"capacity_only": True},
        {"capacity_only": None},
        {"write_permission": False},
        {"write_permission": None},
        {"strict_write_decision": "reroute"},
        {"strict_write_decision": None},
        {"ok": False},
    ],
)
def test_storage_observation_success_is_not_write_permission(override: dict) -> None:
    document = {**storage_allow(), **override}
    result = provider._preflight_summary(
        document, command="storage-write-preflight", returncode=0
    )
    assert result["ok"] is False
    assert result["decision"] == document["decision"]
    assert result["write_permission"] == document["write_permission"]
    assert result["capacity_only"] == document["capacity_only"]


def test_storage_requires_complete_successful_owner_response() -> None:
    for document, code, command, allowed in (
        (storage_allow(), 0, "storage-write-preflight", True),
        (storage_allow(), 1, "storage-write-preflight", False),
        ({"ok": True}, 0, "storage-write-preflight", False),
        (storage_allow(), 0, "unknown", False),
    ):
        assert (
            provider._preflight_summary(document, command=command, returncode=code)[
                "ok"
            ]
            is allowed
        )


@pytest.mark.parametrize("warning_allowed", [True, False, None])
def test_changes_warning_retains_owner_policy_and_diagnostics(
    warning_allowed: bool | None,
) -> None:
    result = provider._preflight_summary(
        {
            "ok": True,
            "decision": "warn",
            "summary": {"status": "warn", "fails": 0, "warnings": 1},
            "policy": {"warnings_do_not_block": warning_allowed},
            "checks": [
                {
                    "level": "warn",
                    "key": "change_record_recommended",
                    "message": "durable mutation needs a change record",
                }
            ],
        },
        command="changes-preflight",
        returncode=0,
    )
    assert result["ok"] is (warning_allowed is True)
    assert result["decision"] == result["status"] == "warn"
    assert result["warnings"] == [
        "change_record_recommended: durable mutation needs a change record"
    ]


@pytest.mark.parametrize("decision", ["deny", "unknown", None])
def test_changes_unknown_or_denied_decision_is_not_allowed(
    decision: str | None,
) -> None:
    assert not provider._preflight_summary(
        {"ok": True, "decision": decision},
        command="changes-preflight",
        returncode=0,
    )["ok"]


@pytest.mark.parametrize("failure", [None, "reroute", "timed_out", "output_truncated"])
def test_real_preflight_adapter_binds_target_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    executable = tmp_path / "owner-command"
    executable.write_text("fixture: never executed")
    executable.chmod(0o755)
    monkeypatch.setattr(provider.shutil, "which", lambda _: str(executable))
    calls = []

    def process(args: list[str], **kwargs: object) -> dict:
        calls.append(args)
        storage = args[1] == "storage"
        document = storage_allow() if storage else {"ok": True, "decision": "allow"}
        if storage and failure == "reroute":
            document.update(decision="reroute", write_permission=False)
        return {
            "returncode": 0,
            "stdout": json.dumps(document).encode(),
            "timed_out": storage and failure == "timed_out",
            "output_truncated": storage and failure == "output_truncated",
        }

    monkeypatch.setattr(provider, "_bounded_process", process)
    target = tmp_path / "runtime"
    result = provider.run_owner_preflights(
        archive_bytes=1234, runtime_root=target, provider_label="SCIP Python"
    )
    assert result["ok"] is (failure is None)
    assert calls[0][calls[0].index("--target") + 1] == str(target)
    assert calls[1][calls[1].index("--surface") + 1] == str(target)
    assert "SCIP Python" in calls[1][calls[1].index("--intent") + 1]
    assert not target.exists()
    if failure in {"timed_out", "output_truncated"}:
        assert (
            "owner_preflight_output_incomplete" in result["preflights"][0]["blockers"]
        )
