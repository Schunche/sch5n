# Copyright (c) 2026 Schunche
"""Experimental software."""

from enum import StrEnum
lazy import argparse
lazy import logging
lazy import platform
lazy import sys

lazy from sch5n import __package__ as _package
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

    for program in Program:
        subparsers.add_parser(program)

    args, remaining = parser.parse_known_args()

    command = Program(args.command) if args.command else Program.CLIENT
    match command:
        case Program.CLIENT:
            client_main()
        case Program.SERVER:
            server_main(remaining)
        case _:
            raise NotImplementedError


if __name__ == "__main__":
    main()
