"""Main entry point for Connect 4: vs The Devils.

Usage:
    python main.py             # Launch the graphical user interface (default)
    python main.py --console   # Launch the classic terminal interface
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Connect 4 AI Agent (Minimax with Alpha-Beta Pruning)"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="run the terminal version instead of the graphical interface",
    )
    args, qt_args = parser.parse_known_args(argv)

    if args.console:
        from game.console_game import main as run_console_main

        return run_console_main()

    from ui.ui import run_gui

    return run_gui([sys.argv[0], *qt_args])


if __name__ == "__main__":
    raise SystemExit(main())
