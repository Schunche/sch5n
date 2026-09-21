# Copyright (c) 2026 Schunche
"""Experimental software."""

import argparse

from sch5n import __package__ as _package


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=_package,
        description="Experimental Software.",
        epilog=None)

    parser.add_argument("-server", "--server", action="store_true")
    parser.add_argument("-dev", "--developer", action="store_true")

    args = parser.parse_args()

    if args.server:
        launch_server(args)
    else:
        launch_client(args)


if __name__ == "__main__":
    main()
