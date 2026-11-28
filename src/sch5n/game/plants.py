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
BIRCH = (
    "  o  ",
    " ooo ",
    " oBo ",
    " oBo ",
    "  L  ",
    "  L  ",
    "  L  ",
    "  L  ",
    "  L  ",
    "  L  ",
)
"""A tall, slim birch."""
PINE = (
    "  o  ",
    "  B  ",
    " ooo ",
    " oBo ",
    "ooooo",
    "ooBoo",
    "  L  ",
    "  L  ",
    "  L  ",
)
"""A pine with a pointed crown."""
TREES = {"oak": OAK, "birch": BIRCH, "pine": PINE}
"""Tree shapes by the wood; a sapling `<wood>_sapling` grows one."""
SKY_ROWS = 256
"""Rows above the world's top searched for the surface."""
SMOTHER_SECONDS = (20.0, 40.0)
"""Shortest and longest time grass lives under a block placed on it."""
SPREAD_EVERY = 6
"""Ticks between tries of the grass to spread to a random column."""
SPREAD_CHANCE = 0.25
BOUNDS_REFRESH = 600
"""Ticks the width of the world is remembered for picking columns."""
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
    sapling = tilemap.blocks.get(tilemap.get(x, y))
    wood = sapling.name.removesuffix("_sapling") if sapling else "oak"
    shape = TREES.get(wood, OAK)
    names = {"o": f"{wood}_leaf", "B": f"{wood}_log_leaf", "L": f"{wood}_log"}
    middle, bottom = len(shape[0]) // 2, len(shape) - 1
    tree = [
        (x + column - middle, y + row - bottom, names[part])
        for row, line in enumerate(shape)
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
        self.smothering: dict[IntTuple2, int] = {}
        """Ticks until grass dies under a block on top, by grass tile."""
        self.ticks = 0
        self._columns: tuple[int, int, int] | None = None
        """Left, right and bottom of the world as of the last refresh."""
        plants = {b.id for b in tilemap.blocks if b.spec.grows_after}
        for x, y, block, _ in tilemap.iter_tiles():
            if block in plants:
                self.plant(x, y)

    def plant(self, x: int, y: int) -> None:
        """Start the clock of what was placed at a tile.

        A plant starts to grow. A solid block over grass starts to smother
        the grass under it.
        """
        block = self.tilemap.blocks.get(self.tilemap.get(x, y))
        if block is not None and block.spec.solid:
            under = self.tilemap.blocks.get(self.tilemap.get(x, y + 1))
            if under is not None and under.spec.spreads_onto:
                low, high = SMOTHER_SECONDS
                seconds = float(self.rng.uniform(low, high))
                self.smothering[x, y + 1] = round(seconds * self.tick_rate)
            return
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
        self.ticks += 1
        if self.ticks % SPREAD_EVERY == 0:
            self._spread_grass()
        self._tick_smothering()
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

    def _tick_smothering(self) -> None:
        for (x, y), left in list(self.smothering.items()):
            grass = self.tilemap.blocks.get(self.tilemap.get(x, y))
            if (
                grass is None
                or not grass.spec.spreads_onto
                or not self.tilemap.is_solid(x, y - 1)
            ):
                del self.smothering[x, y]
            elif left > 1:
                self.smothering[x, y] = left - 1
            else:
                del self.smothering[x, y]
                self.tilemap.set(
                    x, y, self.tilemap.blocks.id_of(grass.spec.spreads_onto[0])
                )

    def _world_columns(self) -> tuple[int, int, int] | None:
        if self._columns is None or self.ticks % BOUNDS_REFRESH == 0:
            bounds = self.tilemap.bounds()
            self._columns = (
                None if bounds is None else (bounds[0], bounds[2], bounds[3])
            )
        return self._columns

    def _spread_grass(self) -> None:
        """Let grass cover the dirt next to it, in a random column.

        Only the topmost solid tile of the column counts, and it needs
        open air above it, so caves and buried dirt stay as they are.
        """
        columns = self._world_columns()
        if columns is None:
            return
        left, right, bottom = columns
        blocks = self.tilemap.blocks
        x = int(self.rng.integers(left, right))
        y = self.tilemap.surface_y(x, -SKY_ROWS, bottom)
        if y is None or self.rng.random() >= SPREAD_CHANCE:
            return
        self._smother(x, y + 1)
        ground = blocks.get(self.tilemap.get(x, y))
        if ground is None or self.tilemap.get(x, y - 1) != AIR:
            return
        for grass in blocks:
            if ground.name not in grass.spec.spreads_onto:
                continue
            near = ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            if any(
                self.tilemap.get(nx, ny) == grass.id
                for nx, ny in near
                if (nx, ny) != (x, y)
            ):
                self.tilemap.set(x, y, grass.id)
                return

    def _smother(self, x: int, y: int) -> None:
        """Turn grass that has a solid block on top back into dirt."""
        cover = self.tilemap.blocks.get(self.tilemap.get(x, y))
        if cover is not None and cover.spec.spreads_onto:
            self.tilemap.set(
                x, y, self.tilemap.blocks.id_of(cover.spec.spreads_onto[0])
            )
