"""Grafting-layer boundary between the abyss_machine core and its organs.

The core keeps device drivers, OS surfaces, desktop adapters, raw sensors and
trust parts. Organs under `abyss_machine.organs` are reasoning, memory,
AI-runtime, release and application layers, and the core reaches them only
lazily. Every remaining core -> organ edge is listed here with its reason, so
a new edge is a review decision instead of drift.
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "abyss_machine"

# (core module, organ module) -> why the core still imports it
KNOWN_CORE_IMPORTS = {
    ("code_intelligence_adapters", "artifacts.artifact_bundles"): "code-intelligence release gate checks signed bundle trust",
    ("code_intelligence_gate", "artifacts.artifact_bundles"): "code-intelligence release gate checks signed bundle trust",
    ("code_intelligence_provider", "artifacts.artifact_bundles"): "provider install verifies the signed provider bundle",
    ("code_intelligence_python_install", "artifacts.artifact_bundles"): "provider install verifies the signed provider bundle",
    ("typing_nervous_adapters", "nervous.nervous_index"): "raw typing capture hands committed text to the nervous index",
}

# organ modules bound lazily by abyss_machine.cli -> core helpers that use them
KNOWN_CLI_ORGAN_BINDINGS = {
    "organs.ai.ai_runtime_adapters": "host package probes (rpm, ldconfig, model dirs) for doctor",
    "organs.ai.ai_runtime_contracts": "TOKEN_ACCOUNTING_* fields and numeric deltas shared with resource admission",
    "organs.artifacts.artifact_bundles": "docs mesh subject-store roots",
    "organs.dictation.dictation_contracts": "shared transcript text normalisation",
    "organs.dictation.dictation_execution_adapters": "recording_is_active for mode and admission checks",
    "organs.dictation.dictation_notifications_adapters": "desktop notify actuator",
    "organs.dictation.dictation_postprocess_adapters": "shared transcript text normalisation",
    "organs.dictation.dictation_replacements_adapters": "shared transcript text normalisation",
    "organs.nervous.nervous_index_adapters": "path_has_symlink_tail, a generic symlink-tail guard the core sensors use; candidate for a core path-safety module",
    "organs.nervous.nervous_events": "snapshot_evidence, systemd_facts_from_snapshot and private_capture_events for the core passive snapshot capture",
    "organs.nervous.nervous_events_adapters": "write_jsonl_records and write_derived_records, the evidence writers core capture uses",
    "organs.nervous.nervous_synthesis_adapters": "write_text_atomic, a generic atomic text writer",
}

# executed while `import abyss_machine.cli` runs; every other organ module stays
# an unexecuted lazy module until a command uses it
KNOWN_IMPORT_TIME_ORGAN_MODULES = {
    # docstring-only package __init__ files, imported by find_spec() of lazy submodules
    "abyss_machine.organs",
    "abyss_machine.organs.ai",
    "abyss_machine.organs.artifacts",
    "abyss_machine.organs.dictation",
    "abyss_machine.organs.knowledge",
    "abyss_machine.organs.nervous",
    # core evaluates TOKEN_ACCOUNTING_* fields at import time
    "abyss_machine.organs.ai.ai_runtime_contracts",
    # eager typing_nervous_adapters imports it at top level
    "abyss_machine.organs.nervous.nervous_index",
}


def _organ_targets(tree: ast.AST) -> set[str]:
    prefix = "abyss_machine.organs."
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(prefix):
            rest = node.module[len(prefix):]
            if "." in rest:
                targets.add(rest)
            else:
                targets.update(f"{rest}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            targets.update(a.name[len(prefix):] for a in node.names if a.name.startswith(prefix))
    return targets


def test_core_modules_import_only_known_organ_modules() -> None:
    found = {
        (path.stem, target)
        for path in sorted(PACKAGE.glob("*.py"))
        for target in _organ_targets(ast.parse(path.read_text(encoding="utf-8")))
    }

    assert found == set(KNOWN_CORE_IMPORTS)


def test_core_cli_binds_organs_only_through_lazy_bindings() -> None:
    tree = ast.parse((PACKAGE / "cli.py").read_text(encoding="utf-8"))
    bound = {
        keyword.value.value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "_lazy_module_bindings"
        for keyword in call.keywords
        if isinstance(keyword.value, ast.Constant) and str(keyword.value.value).startswith("organs.")
    }
    organ_clis = {
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", None) == "_lazy_import_module"
        and call.args
        and isinstance(call.args[0], ast.Constant)
    }

    assert bound == set(KNOWN_CLI_ORGAN_BINDINGS)
    assert organ_clis == {
        f"abyss_machine.organs.{organ}.cli"
        for organ in ("nervous", "dictation", "ai", "artifacts", "knowledge")
    }
    assert _organ_targets(tree) == set()


def test_importing_core_cli_executes_no_unlisted_organ_code() -> None:
    probe = (
        "import importlib.util, json, sys\n"
        "import abyss_machine.cli\n"
        "lazy = importlib.util._LazyModule\n"
        "print(json.dumps(sorted(\n"
        "    name for name, module in sys.modules.items()\n"
        "    if name.startswith('abyss_machine.organs') and not isinstance(module, lazy)\n"
        ")))\n"
    )
    env = {key: value for key, value in os.environ.items() if not key.startswith("ABYSS_MACHINE_CLI_EAGER")}
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        check=True,
        timeout=60,
    )

    assert set(json.loads(result.stdout)) <= KNOWN_IMPORT_TIME_ORGAN_MODULES


@pytest.mark.parametrize("old_name", sorted(importlib.import_module("abyss_machine._organ_aliases").MOVED_MODULES))
def test_pre_split_module_paths_resolve_to_organ_modules(old_name: str) -> None:
    from abyss_machine import _organ_aliases

    target = _organ_aliases.MOVED_MODULES[old_name]
    old = importlib.import_module(f"abyss_machine.{old_name}")
    new = importlib.import_module(target)

    assert old is new
    assert new.__spec__.name == target
    assert new.__package__ == target.rsplit(".", 1)[0]
