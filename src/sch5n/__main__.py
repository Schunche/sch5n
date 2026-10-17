# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

import platform
from enum import StrEnum
lazy import argparse
lazy import logging
lazy import sys

from sch5n import __package__ as _package
lazy from sch5n.__oldmain__ import Main
lazy from sch5n.client.__main__ import main as client_main
lazy from sch5n.server.__main__ import main as server_main


class Program(StrEnum):
    """Define tools."""

    CLIENT = "client"
    SERVER = "server"


def main() -> None:
    """Entry point of program."""
    if platform.system() not in {"Linux", "Windows"}:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(_package).error(
            "Your operating system is not supported."
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog=_package,
        description="Experiental software.",
        epilog=None,
        suggest_on_error=True,
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(Program.CLIENT)
    subparsers.add_parser(Program.SERVER)

    args, remaining = parser.parse_known_args()

    command = Program(args.command) if args.command else Program.CLIENT
    match command:
        case Program.CLIENT:
            client_main(remaining)

            m = Main()
            m.run()
        case Program.SERVER:
            server_main(remaining)


if __name__ == "__main__":
    main()
