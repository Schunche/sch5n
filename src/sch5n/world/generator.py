# Copyright (c) 2026 Schunche
"""Procedural world generation.

Port of the original generator: the upper half is dirt, the lower half is
stone, and both are sprinkled with meandering strokes of the other one.
Generation is deterministic for a given seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sch5n.log.logger import LOGGER
from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from sch5n.game.content import BlockRegistry

ORE_PAIRS: tuple[tuple[str, str], ...] = (
    ("copper", "tin"),
    ("iron", "lead"),
    ("silver", "tungsten"),
    ("gold", "platinum"),
)
"""Each world contains exactly one ore of every pair."""

MAX_STROKE_LENGTH = 32
SIGNS = (-1, 1)


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """Size of the generated world in tiles (half-open ranges)."""

    left: int = 0
    right: int = 300
    top: int = 0
    bottom: int = 160

    def contains(self, x: int, y: int) -> bool:
        """Whether a tile is inside the world.

        Returns:
            bool: True if inside.

        """
        return self.left <= x < self.right and self.top <= y < self.bottom

    @property
    def dirt_until(self) -> int:
        """First row of the stone layer."""
        return (self.top + self.bottom) // 2


class _Generator:
    def __init__(
        self, spec: WorldSpec, blocks: BlockRegistry, rng: np.random.Generator
    ) -> None:
        self.spec = spec
        self.rng = rng
        self.tilemap = TileMap(blocks)
        self.dirt = blocks.id_of("dirt")
        self.stone = blocks.id_of("stone")

    def jitter(self, value: float) -> float:
        """Randomly change `value` by at most 25 percent.

        Returns:
            float: The changed, non negative value.

        """
        return abs(value * (1 + math.sin(self.rng.random() * 2 * math.pi) / 4))

    def fill_layers(self) -> None:
        spec = self.spec
        for y in range(spec.top, spec.bottom):
            block = self.dirt if y < spec.dirt_until else self.stone
            for x in range(spec.left, spec.right):
                self.tilemap.set(x, y, block)

    def stroke_length(self, y: int, block: int) -> int:
        """Pick a stroke length: more stone deeper in dirt and vice versa.

        Returns:
            int: Number of discs, between 0 and `MAX_STROKE_LENGTH`.

        """
        spec = self.spec
        if block == self.stone:
            depth = (y - spec.top) / max(spec.dirt_until - spec.top, 1)
            length = self.jitter(2 ** (5 * (2 * depth - 1)))
        else:
            depth = (y - spec.dirt_until) / max(
                spec.bottom - spec.dirt_until, 1
            )
            length = self.jitter(8 * (1 - depth) ** 3)
        return int(min(max(length, 0), MAX_STROKE_LENGTH))

    def disc(self, cx: float, cy: float, radius: float, block: int) -> None:
        limit = round(radius**2)
        for x in range(int(cx - radius), int(cx + radius) + 1):
            for y in range(int(cy - radius), int(cy + radius) + 1):
                if (
                    self.spec.contains(x, y)
                    and (x - cx) ** 2 + (y - cy) ** 2 <= limit
                ):
                    self.tilemap.set(x, y, block)

    def stroke(self, start: tuple[int, int], block: int) -> None:
        """Draw a chain of overlapping discs wandering from `start`."""
        rng = self.rng
        x, y = start
        radius = int(rng.integers(9, 51)) / int(rng.integers(9, 13))
        length = self.stroke_length(y, block)
        if length == 0:
            return

        for _ in range(length + 1):
            self.disc(x, y, radius, block)
            direction = math.pi * (1 + rng.random())
            sign = int(rng.choice(SIGNS))
            x = int(x + sign * radius / 2 * math.cos(direction))
            y = int(y + radius / 2 * math.sin(direction))
            radius = min(max(self.jitter(radius), 1), 5)

    def scatter(self, block: int, y0: int, y1: int, density: float) -> int:
        spec = self.spec
        count = int(
            self.jitter((spec.right - spec.left) * (y1 - y0) * density)
        )
        for _ in range(count):
            self.stroke(
                (
                    spec.left
                    + int(self.rng.random() * (spec.right - spec.left)),
                    y0 + int(self.rng.random() * (y1 - y0)),
                ),
                block,
            )
        return count

    def run(self) -> TileMap:
        spec = self.spec
        self.fill_layers()
        stone = self.scatter(self.stone, spec.top, spec.dirt_until, 0.003)
        dirt = self.scatter(self.dirt, spec.dirt_until, spec.bottom, 0.004)
        LOGGER.info("Strokes: %s stone in dirt, %s dirt in stone", stone, dirt)
        ores = [pair[int(self.rng.integers(len(pair)))] for pair in ORE_PAIRS]
        LOGGER.info("This world contains the ores: %s", ", ".join(ores))
        return self.tilemap


def generate(
    blocks: BlockRegistry, spec: WorldSpec | None = None, seed: int = 0
) -> TileMap:
    """Generate a world.

    Returns:
        TileMap: The generated tiles.

    """
    spec = spec or WorldSpec()
    LOGGER.info("Generating world %s with seed %s", spec, seed)
    return _Generator(spec, blocks, np.random.default_rng(seed)).run()
