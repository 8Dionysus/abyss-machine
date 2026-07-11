from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validators" / "memory_controller_upgrade_rehearsal.py"


def test_synthetic_controller_overlay_upgrade_rolls_back_and_reapplies(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--seed-mode",
            "synthetic",
            "--tmp-root",
            str(tmp_path),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr[-1000:]
    payload = json.loads(result.stdout)
    assert payload["schema"] == "abyss_machine_memory_controller_upgrade_rehearsal_v1"
    assert payload["ok"] is True
    assert payload["seed"]["version"] == "0.8.86"
    assert payload["first_upgrade"]["verify"]["checks"] == {
        "controller_valid": True,
        "launcher_matches_entrypoint": True,
        "legacy_overlay_removed": True,
        "package_matches_source": True,
        "public_seed_matches_source": True,
    }
    assert payload["rollback"] == {
        "byte_exact_code_restore": True,
        "ok": True,
        "protected_surfaces_unchanged": True,
    }
    assert payload["second_upgrade"]["verify"]["ok"] is True
    assert all(payload["protected_surfaces"].values())
