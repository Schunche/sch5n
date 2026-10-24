# Copyright (c) 2026 Schunche
"""Experimental software."""

from enum import StrEnum
lazy import argparse
lazy import logging
lazy import platform
lazy import sys

lazy from sch5n import __package__ as _package
lazy from sch5n.client.__main__ import main as client_main
lazy from sch5n.deprecated.tools.__map_editor__ import main as map_editor_main
lazy from sch5n.deprecated.tools.__map_viewer__ import main as map_viewer_main
lazy from sch5n.server.__main__ import main as server_main
lazy from sch5n.world.generator.__main_old__ import main as world_generate_main


class Program(StrEnum):
    """Define tools."""

    CLIENT = "client"
    SERVER = "server"
    MAP_EDITOR = "edit"
    MAP_VIEWER = "view"
    MAP_GENERATOR = "generate"


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
        case Program.MAP_EDITOR:
            map_editor_main()
        case Program.MAP_VIEWER:
            map_viewer_main()
        case Program.MAP_GENERATOR:
            world_generate_main()
        case _:
            raise RuntimeError


if __name__ == "__main__":
    main()
