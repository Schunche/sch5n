# Copyright (c) 2026 Schunche
"""Saplings: where they stand, and growing them into trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.content import AIR

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

    from sch5n.game.content import BlockDef
    from sch5n.math.vector import IntTuple2
    from sch5n.world.tilemap import TileMap

OAK = (
    " ooo ",
    " ooo ",
    "ooBoo",
    "ooBoo",
    "  L  ",
    "  L  ",
    "  L  ",
    "  L  ",
)
"""A grown oak, top row first. The sapling's tile is the bottom of the
trunk, in the middle column."""
OAK_BLOCKS = {"o": "oak_leaf", "B": "oak_log_leaf", "L": "oak_log"}
RETRY_SECONDS = 5
"""How long a sapling without room waits before trying again."""


def can_stand(tilemap: TileMap, x: int, y: int, plant: BlockDef) -> bool:
    """Whether the ground under a tile can hold the plant.

    Returns:
        bool: True on one of the blocks the plant grows on.

    """
    ground = tilemap.blocks.get(tilemap.get(x, y + 1))
    return ground is not None and ground.name in plant.spec.plant_on


def grow_tree(tilemap: TileMap, x: int, y: int) -> bool:
    """Turn the sapling at a tile into a grown tree, if there is room.

    Every other tile of the tree must be empty.

    Returns:
        bool: Whether it grew.

    """
    middle, bottom = len(OAK[0]) // 2, len(OAK) - 1
    tree = [
        (x + column - middle, y + row - bottom, OAK_BLOCKS[part])
        for row, line in enumerate(OAK)
        for column, part in enumerate(line)
        if part != " "
    ]
    if any(
        (tx, ty) != (x, y) and tilemap.get(tx, ty) != AIR for tx, ty, _ in tree
    ):
        return False
    for tx, ty, block in tree:
        tilemap.set(tx, ty, tilemap.blocks.id_of(block))
    return True


class Garden:
    """The growing plants of a world.

    How far along a plant is lasts only as long as the session: plants in
    a loaded world start over.
    """

    def __init__(
        self, tilemap: TileMap, rng: np.random.Generator, tick_rate: int
    ) -> None:
        """Find the plants already in the world."""
        self.tilemap = tilemap
        self.rng = rng
        self.tick_rate = tick_rate
        self.waiting: dict[IntTuple2, int] = {}
        """Ticks until each plant grows, by tile."""
        plants = {b.id for b in tilemap.blocks if b.spec.grows_after}
        for x, y, block, _ in tilemap.iter_tiles():
            if block in plants:
                self.plant(x, y)

    def plant(self, x: int, y: int) -> None:
        """Start the clock of the plant at a tile."""
        block = self.tilemap.blocks.get(self.tilemap.get(x, y))
        if block is None or block.spec.grows_after is None:
            return
        low, high = block.spec.grows_after
        seconds = float(self.rng.uniform(low, high))
        self.waiting[x, y] = round(seconds * self.tick_rate)

    def tick(self, uproot: Callable[[BlockDef, IntTuple2], None]) -> None:
        """Grow plants whose time has come.

        Args:
            uproot: Called with every plant that lost its ground, after it
                is removed.

        """
        for (x, y), left in list(self.waiting.items()):
            block = self.tilemap.blocks.get(self.tilemap.get(x, y))
            if block is None or block.spec.grows_after is None:
                del self.waiting[x, y]
            elif not can_stand(self.tilemap, x, y, block):
                del self.waiting[x, y]
                self.tilemap.set(x, y, AIR)
                uproot(block, (x, y))
            elif left > 1:
                self.waiting[x, y] = left - 1
            elif grow_tree(self.tilemap, x, y):
                del self.waiting[x, y]
            else:
                self.waiting[x, y] = RETRY_SECONDS * self.tick_rate
