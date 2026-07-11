from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "src" / "abyss_machine" / "cli.py"


def test_direct_script_fallback_imports_all_simple_package_modules() -> None:
    tree = ast.parse(CLI.read_text(encoding="utf-8"))

    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        relative_imports = {
            alias.name
            for statement in node.body
            if isinstance(statement, ast.ImportFrom)
            and statement.level == 1
            and statement.module is None
            for alias in statement.names
        }
        if not relative_imports:
            continue

        fallback_imports = {
            alias.name
            for handler in node.handlers
            for statement in handler.body
            if isinstance(statement, ast.ImportFrom)
            and statement.level == 0
            and statement.module == "abyss_machine"
            for alias in statement.names
        }

        assert relative_imports <= fallback_imports
        assert "doctor_adapters" in fallback_imports
        return

    raise AssertionError("cli.py package import fallback block was not found")
