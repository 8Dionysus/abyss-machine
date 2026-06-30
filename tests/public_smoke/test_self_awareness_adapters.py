from __future__ import annotations

from pathlib import Path

from abyss_machine import self_awareness_adapters


def _path_map(tmp_path: Path) -> dict[str, Path]:
    paths = {
        name: tmp_path / name / "latest.json"
        for name, _suffix in self_awareness_adapters.READMODEL_SCHEMA_SUFFIXES
    }
    paths["completion_audit"] = tmp_path / "completion-audit" / "latest.json"
    return paths


def test_readmodel_latest_specs_keep_public_order_and_cycle_switch(tmp_path: Path) -> None:
    specs = self_awareness_adapters.readmodel_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
        include_cycle=False,
    )

    assert specs[0].name == "events"
    assert "cycle" not in {spec.name for spec in specs}
    assert specs[-1].name == "validate"
    assert specs[-1].schema == "abyss_machine_self_awareness_validate_v1"


def test_status_latest_specs_include_completion_audit_after_readmodels(tmp_path: Path) -> None:
    specs = self_awareness_adapters.status_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
    )

    assert specs[-2].name == "validate"
    assert specs[-1].name == "completion_audit"
    assert specs[-1].schema == "abyss_machine_self_awareness_completion_audit_v1"


def test_load_latest_documents_uses_fake_read_port_without_live_io(tmp_path: Path) -> None:
    calls: list[tuple[Path, str]] = []
    specs = self_awareness_adapters.validation_latest_specs(
        schema_prefix="abyss_machine",
        paths=_path_map(tmp_path),
        require_cycle=False,
    )

    def fake_loader(path: Path, schema: str) -> dict[str, object]:
        calls.append((path, schema))
        return {"schema": schema, "ok": True, "generated_at": "2026-06-30T00:00:00Z", "summary": {}}

    documents = self_awareness_adapters.load_latest_documents(specs, load_latest_json=fake_loader)

    assert "completion_audit" in documents
    assert "probe" in documents
    assert "validate" not in documents
    assert "cycle" not in documents
    assert list(documents) == [spec.name for spec in specs]
    assert calls == [(spec.path, spec.schema) for spec in specs]


def test_latest_summary_omits_raw_payload_and_redacts_summary(tmp_path: Path) -> None:
    spec = self_awareness_adapters.SelfAwarenessLatestSpec(
        name="events",
        path=tmp_path / "events" / "latest.json",
        schema="abyss_machine_self_awareness_events_v1",
    )
    document = {
        "schema": spec.schema,
        "ok": True,
        "generated_at": "2026-06-30T00:00:00Z",
        "summary": {
            "events": 2,
            "token": "Authorization: Bearer " + "sk-" + "testsecret1234567890",
        },
        "raw_events": [{"body": "private body"}],
    }

    summary = self_awareness_adapters.latest_summary(spec, document)

    assert summary["path"].endswith("events/latest.json")
    assert summary["summary"] == {"events": 2, "token": "<redacted>"}
    assert "raw_events" not in summary


def test_missing_latest_document_names_only_reports_error_documents() -> None:
    documents = {
        "events": {"ok": True},
        "collect": {"ok": False},
        "validate": {"ok": False, "error": "missing"},
    }

    assert self_awareness_adapters.missing_latest_document_names(documents) == ["validate"]
