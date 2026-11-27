# Copyright (c) 2026 Schunche
"""Generate a world and save it as a map."""

from __future__ import annotations

import argparse
import secrets
from typing import TYPE_CHECKING

from sch5n.game.config import load_model
from sch5n.game.content import BlockRegistry, BlocksFile
from sch5n.log.logger import LOGGER
from sch5n.log.logger import init as init_logging
from sch5n.utility import path
from sch5n.world.generator import WorldSpec, generate
from sch5n.world.io import DEFAULT_MAP, is_protected, save_tilemap

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    """Generate a map file."""
    defaults = WorldSpec()
    parser = argparse.ArgumentParser(prog="sch5n generate")
    parser.add_argument("name", nargs="?", default="procedural")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--width", type=int, default=defaults.right)
    parser.add_argument("--height", type=int, default=defaults.bottom)
    developing = path.is_developing()
    if developing:
        parser.add_argument(
            "--overwrite-default",
            action="store_true",
            help=(
                "developers: allow replacing the protected default map, "
                f"{DEFAULT_MAP}"
            ),
        )
    parser.set_defaults(overwrite_default=False)
    args = parser.parse_args(argv)

    target = path.MAPS_DIR / f"{args.name}.json"
    if is_protected(target) and not args.overwrite_default:
        hint = " Or add --overwrite-default." if developing else ""
        parser.error(
            f"{DEFAULT_MAP} is the default map and is protected. Pick another "
            f"name.{hint}"
        )

    init_logging()
    seed = args.seed if args.seed is not None else secrets.randbelow(2**32)
    blocks = BlockRegistry(
        load_model(BlocksFile, path.DATA_DIR / "blocks.json")
    )
    tilemap = generate(
        blocks, WorldSpec(right=args.width, bottom=args.height), seed
    )

    save_tilemap(target, tilemap)
    LOGGER.info("Saved %s tiles to %s", len(tilemap), target)


if __name__ == "__main__":
    main()
