from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import observability_contracts


def _refs(root: str = "/var/lib/abyss-machine/observability") -> dict[str, str]:
    return {
        "root": root,
        "agent_entrypoint": f"{root}/AGENTS.md",
        "index": f"{root}/index.json",
        "config": "/etc/abyss-machine/observability/config.json",
        "collector": "/usr/local/libexec/abyss-machine-observe",
        "thermal_root": f"{root}/thermal-battery",
        "timer": "abyss-observability-collect.timer",
        "service": "abyss-observability-collect.service",
    }


def test_observability_paths_and_latest_read_contracts_are_module_owned() -> None:
    paths = observability_contracts.paths_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        refs=_refs(),
        year="2026",
        month="06",
        date_name="2026-06-25",
    )
    missing = observability_contracts.latest_read_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        data=None,
        error="missing",
    )
    loaded = observability_contracts.latest_read_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        path="/var/lib/abyss-machine/observability/thermal-battery/latest.json",
        data={"ok": True, "sample": {"class": "green"}},
        error=None,
    )

    assert paths["schema"] == "abyss_machine_observability_paths_v1"
    assert paths["thermal_battery"]["today_samples"].endswith("/2026/06/2026-06-25.jsonl")
    assert paths["commands"]["collect"] == "abyss-machine observability collect --json"
    assert paths["policy_contract"]["automatic_permission_changes"] is False
    assert missing["schema"] == "abyss_machine_observability_latest_read_v1"
    assert missing["ok"] is False
    assert loaded["schema"] == "abyss_machine_observability_latest_v1"
    assert loaded["read_at"] == "2026-06-25T12:00:00+00:00"


def test_observability_manual_probe_and_status_contracts_are_module_owned() -> None:
    manual = observability_contracts.manual_collect_probe_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        collector="/usr/local/libexec/abyss-machine-observe",
        collector_exists=False,
        current_euid=1000,
        current_egid=1000,
        current_groups=[1000, 10],
        missing_or_unwritable=["samples"],
        directories=[{"name": "samples", "path": "/var/lib/abyss-machine/observability/thermal-battery/samples", "exists": False}],
    )
    status = observability_contracts.status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        root_exists=True,
        agent_entrypoint_exists=True,
        index_exists=False,
        config_exists=True,
        collector_exists=False,
        timer={"active": "inactive"},
        service={"active": "inactive"},
        manual_collect=manual,
        paths={"thermal_battery": {"latest": "/var/lib/abyss-machine/observability/thermal-battery/latest.json"}},
        latest={
            "ok": True,
            "updated_at": "2026-06-25T11:59:00+00:00",
            "sample": {
                "class": "green",
                "thermal": {"sensors": {"temperature_c_max": 71.2}},
                "power": {"battery": {"ac_online": True}},
            },
        },
        latest_age_sec=60.0,
        today={"samples": 3, "events": 1, "summary_exists": True},
    )

    assert manual["schema"] == "abyss_machine_observability_manual_collect_probe_v1"
    assert manual["ok"] is False
    assert manual["status"] == "operator_authorization_required"
    assert manual["policy"]["does_not_run_collector"] is True
    assert observability_contracts.sample_temperature(status["latest"].get("sample", {})) is None
    assert status["schema"] == "abyss_machine_observability_status_v1"
    assert status["latest"]["temperature_c_max"] == 71.2
    assert status["latest"]["age_sec"] == 60.0
    assert status["manual_collect"] is manual


def test_observability_sample_temperature_contract_handles_raw_samples() -> None:
    assert observability_contracts.sample_temperature({"thermal": {"sensors": {"temperature_c_max": 77}}}) == 77.0
    assert observability_contracts.sample_temperature({"thermal": {"sensors": {"temperature_c_max": True}}}) is None
    assert observability_contracts.sample_temperature({}) is None


def test_observability_paths_cli_uses_public_contract_shape_without_collecting() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "abyss_machine.cli", "observability", "paths", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_observability_paths_v1"
    assert payload["commands"]["status"] == "abyss-machine observability status --json"
    assert payload["policy_contract"]["automatic_permission_changes"] is False
