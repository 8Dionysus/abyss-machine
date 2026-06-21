from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.safety]


@pytest.mark.parametrize(
    ("path", "decision"),
    [
        ("/srv/abyss-machine/cache/model", "allow_candidate"),
        ("/srv/AbyssOS/abyss-stack/Configs", "deny"),
        ("/home/dionysus/src/abyss-stack", "deny"),
        ("/srv/work/client", "deny"),
        ("/work/client", "deny"),
        ("/home/dionysus/.cache/ai-model", "reroute_for_large_generated_data"),
    ],
)
def test_storage_path_protection_keeps_machine_owned_writes_in_machine_roots(abyss_machine_module, path: str, decision: str) -> None:
    result = abyss_machine_module.storage_path_protection(Path(path))

    assert result["decision"] == decision


@pytest.mark.parametrize(
    ("path", "surface_class"),
    [
        ("/usr/local/bin/abyss-machine", "host_binary"),
        ("/usr/local/libexec/abyss_machine/cli.py", "host_binary"),
        ("/usr/local/share/abyss-machine/manifests/bootstrap_profiles.manifest.json", "host_public_seed"),
        ("/etc/systemd/system/abyss-ai-workload-refresh.timer", "host_system_systemd"),
        ("/home/dionysus/.config/systemd/user/abyss-machine-heartbeat.timer", "host_user_systemd"),
        ("/run/abyss-machine", "host_runtime"),
        ("/run/abyss-machine/socket", "host_runtime"),
    ],
)
def test_change_preflight_classifies_bootstrap_installed_surfaces_as_machine_owned(
    abyss_machine_module, path: str, surface_class: str
) -> None:
    result = abyss_machine_module.surface_path_class(path)

    assert result["decision"] == "allow_candidate"
    assert result["owner"] == "abyss-machine"
    assert result["class"] == surface_class


def test_change_preflight_does_not_allow_broad_systemd_system_root(abyss_machine_module) -> None:
    result = abyss_machine_module.surface_path_class("/etc/systemd/system")

    assert result["decision"] == "deny"


def test_quick_test_lane_does_not_include_password_prompting_commands() -> None:
    runner = Path("/srv/abyss-machine/tools/abyss-machine-test").read_text(encoding="utf-8")

    assert '"pkexec"' not in runner
    assert "'pkexec'" not in runner
    assert '"sudo"' not in runner
    assert "'sudo'" not in runner
    assert "--execute-live" not in runner
    assert "cooling apply" not in runner


def test_memory_apply_requires_explicit_live_acknowledgement_in_cli_source() -> None:
    source = Path("/usr/local/libexec/abyss-machine").read_text(encoding="utf-8")

    assert "--execute-live" in source
    assert "--acknowledge-live-restart" in source
    assert "do_not_tune_zram_or_sysctl_from_plan" in source
