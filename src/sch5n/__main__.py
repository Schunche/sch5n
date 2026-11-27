# Copyright (c) 2026 Schunche
"""Command line entry point: `sch5n [program] [options]`."""

from __future__ import annotations

from enum import StrEnum
lazy import argparse
lazy import logging
lazy import platform
lazy import sys

lazy from sch5n.about import NAME
lazy from sch5n.client.__main__ import editor_main, viewer_main
lazy from sch5n.client.__main__ import main as client_main
lazy from sch5n.server.__main__ import main as server_main
lazy from sch5n.world.__main__ import main as world_generate_main


class Program(StrEnum):
    """Available programs."""

    CLIENT = "client"
    SERVER = "server"
    MAP_EDITOR = "edit"
    MAP_VIEWER = "view"
    MAP_GENERATOR = "generate"


def main(argv: list[str] | None = None) -> None:
    """Entry point of program."""
    if platform.system() not in {"Linux", "Windows"}:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(NAME).error(
            "Your operating system is not supported."
        )
        sys.exit(1)

    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        prog=NAME,
        description="Experimental software.",
        usage=f"%(prog)s [{{{",".join(Program)}}}] [options]",
        suggest_on_error=True,
    )
    parser.add_argument(
        "program",
        choices=list(Program),
        help="what to run (default: client), see `<program> --help`",
    )
    if not argv or argv[0].startswith("-"):
        if argv and argv[0] in {"-h", "--help"}:
            parser.print_help()
            return
        argv = [Program.CLIENT, *argv]
    args = parser.parse_args(argv[:1])
    rest = argv[1:]

    match Program(args.program):
        case Program.CLIENT:
            client_main(rest)
        case Program.SERVER:
            server_main(rest)
        case Program.MAP_EDITOR:
            editor_main(rest)
        case Program.MAP_VIEWER:
            viewer_main(rest)
        case Program.MAP_GENERATOR:
            world_generate_main(rest)


if __name__ == "__main__":
    main()
