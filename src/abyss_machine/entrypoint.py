#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:2] == ["memory", "controller"]:
        try:
            from .memory_controller_service import main as controller_main
        except ImportError:  # Supports the bootstrap-installed direct script copy.
            from abyss_machine.memory_controller_service import main as controller_main

        return controller_main(arguments[2:])
    try:
        from .cli import main as cli_main
    except ImportError:  # Supports the bootstrap-installed direct script copy.
        from abyss_machine.cli import main as cli_main

    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
