from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "src" / "abyss_machine" / "cli.py"


def test_direct_script_package_bindings_cover_lazy_and_eager_modules() -> None:
    tree = ast.parse(CLI.read_text(encoding="utf-8"))
    lazy_modules = {
        value.value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_lazy_module_bindings"
        for value in (
            [*call.args]
            + [keyword.value for keyword in call.keywords]
        )
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    }

    assert "doctor_adapters" in lazy_modules
    assert "self_awareness_adapters" in lazy_modules
    assert all(
        (ROOT / "src" / "abyss_machine" / f"{module_name}.py").is_file()
        for module_name in lazy_modules
    )

    fallback_block_found = False
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
        fallback_block_found = True

    assert fallback_block_found, "cli.py package import fallback block was not found"
