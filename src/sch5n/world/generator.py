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

from sch5n.game.plants import grow_tree
from sch5n.log.logger import LOGGER
from sch5n.world.biomes import TREE_GAP, Biome, biome_bands
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

ORE_DEPTH = {
    0: (0.0, 0.6),
    1: (0.2, 0.8),
    2: (0.5, 1.0),
    3: (0.7, 1.0),
}
"""Share of the stone layer, from its top, where each pair of ores lies."""
ORE_DENSITY = 0.0012
"""Veins per tile of the band an ore lies in."""
VEIN_STEPS = (4, 10)
"""Fewest and most tiles stepped through while drawing a vein."""

MAX_STROKE_LENGTH = 32
SIGNS = (-1, 1)


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """Size of the generated world in tiles (half-open ranges)."""

    left: int = 0
    right: int = 300
    top: int = 0
    bottom: int = 160
    trees: bool = True
    """Whether trees stand on the surface."""

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

    def vein(self, block: int, y0: int, y1: int) -> None:
        """Draw a small wandering blob of an ore inside the stone."""
        spec, rng = self.spec, self.rng
        x = spec.left + int(rng.random() * (spec.right - spec.left))
        y = y0 + int(rng.random() * max(y1 - y0, 1))
        for _ in range(int(rng.integers(*VEIN_STEPS))):
            if spec.contains(x, y) and self.tilemap.get(x, y) == self.stone:
                self.tilemap.set(x, y, block)
            x += int(rng.integers(-1, 2))
            y += int(rng.integers(-1, 2))

    def place_ores(self) -> list[str]:
        """Put one ore of every pair into the stone, deeper for rarer ones.

        Returns:
            list[str]: The ores of this world.

        """
        spec, rng = self.spec, self.rng
        stone_rows = max(spec.bottom - spec.dirt_until, 1)
        ores = [pair[int(rng.integers(len(pair)))] for pair in ORE_PAIRS]
        for pair, name in enumerate(ores):
            near, far = ORE_DEPTH[pair]
            y0 = spec.dirt_until + int(near * stone_rows)
            y1 = spec.dirt_until + int(far * stone_rows)
            width = spec.right - spec.left
            count = int(self.jitter(width * (y1 - y0) * ORE_DENSITY))
            for _ in range(count):
                self.vein(self.tilemap.blocks.id_of(name), y0, y1)
        return ores

    def cover(self, band: tuple[int, int, Biome]) -> None:
        """Lay the surface of a biome over its columns."""
        start, end, biome = band
        spec, blocks = self.spec, self.tilemap.blocks
        top, body = blocks.id_of(biome.top), blocks.id_of(biome.body)
        for x in range(start, end):
            y = self.tilemap.surface_y(x, spec.top, spec.bottom)
            if y is None or self.tilemap.get(x, y) != self.dirt:
                continue
            self.tilemap.set(x, y, top)
            for deeper in range(1, biome.depth):
                if self.tilemap.get(x, y + deeper) == self.dirt:
                    self.tilemap.set(x, y + deeper, body)

    def plant_trees(self, band: tuple[int, int, Biome]) -> int:
        """Grow trees along a biome, spaced out.

        Returns:
            int: How many grew.

        """
        start, end, biome = band
        if not biome.trees or not self.spec.trees:
            return 0
        spec, rng, blocks = self.spec, self.rng, self.tilemap.blocks
        grown, x = 0, start + TREE_GAP // 2
        while x < end - TREE_GAP // 2:
            y = self.tilemap.surface_y(x, spec.top, spec.bottom)
            if y is not None and rng.random() < biome.tree_chance:
                wood = biome.trees[int(rng.integers(len(biome.trees)))]
                self.tilemap.set(x, y - 1, blocks.id_of(f"{wood}_sapling"))
                if grow_tree(self.tilemap, x, y - 1):
                    grown += 1
                    x += TREE_GAP
                else:
                    self.tilemap.set(x, y - 1, 0)
            x += 1
        return grown

    def grow_surface(self) -> None:
        """Give every stretch of world its biome: ground cover and trees."""
        spec = self.spec
        bands = biome_bands(spec.left, spec.right, self.rng)
        trees = 0
        for band in bands:
            self.cover(band)
        for band in bands:
            trees += self.plant_trees(band)
        LOGGER.info(
            "Biomes: %s; %s trees",
            ", ".join(f"{b.name} {a}-{z}" for a, z, b in bands),
            trees,
        )

    def run(self) -> TileMap:
        spec = self.spec
        self.fill_layers()
        stone = self.scatter(self.stone, spec.top, spec.dirt_until, 0.003)
        dirt = self.scatter(self.dirt, spec.dirt_until, spec.bottom, 0.004)
        LOGGER.info("Strokes: %s stone in dirt, %s dirt in stone", stone, dirt)
        self.grow_surface()
        ores = self.place_ores()
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
