# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    """Run the dedicated server. Not implemented yet."""
    # parser = argparse.ArgumentParser(prog="sch5n server")

    # parser.add_argument("--host", default="0.0.0.0")
    # parser.add_argument("--port", type=int, default=25565)

    # args = parser.parse_args(argv)
    LOGGER.error("The server is not implemented yet (arguments: %s)", argv)


if __name__ == "__main__":
    main()
