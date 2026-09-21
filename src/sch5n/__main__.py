# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

import argparse
import logging
import platform

from sch5n import __package__ as _package
from sch5n.core.game import Game
from sch5n.core.path import Directories


def main() -> None:
    """Entry point of program."""
    if platform.system() not in {"Linux", "Windows"}:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(_package)
        logger.fatal("Your current architecture is not supported.")
        return

    parser = argparse.ArgumentParser(
        prog=_package,
        description="Experiental software.",
        epilog=None,
        suggest_on_error=True
    )

    parser.add_argument("-server", "--server", action="store_true")

    args = parser.parse_args()

    Directories.set_developer()
    Directories.make()

    game = Game(Program())


if __name__ == "__main__":
    main()
