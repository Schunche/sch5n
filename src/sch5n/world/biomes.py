# Copyright (c) 2026 Schunche
"""Biomes: stretches of the world with their own ground and trees."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True, slots=True)
class Biome:
    """What a stretch of world is like."""

    name: str
    top: str
    """Block on the surface."""
    body: str
    """Block under the surface, as deep as `depth`."""
    depth: int
    """Rows of `body` under the surface, before the dirt."""
    trees: tuple[str, ...]
    """Woods that grow here, as in `plants.TREES`; none means bare."""
    tree_chance: float
    """Chance per column, spaced out by `TREE_GAP`, that a tree stands."""


BIOMES = {
    "plains": Biome("plains", "grass", "dirt", 0, ("oak", "birch"), 0.35),
    "desert": Biome("desert", "sand", "sand", 6, (), 0.0),
    "tundra": Biome("tundra", "snow", "dirt", 0, ("pine",), 0.3),
}
"""Every biome by name."""
MIN_WIDTH, MAX_WIDTH = 50, 110
"""Narrowest and widest stretch of one biome, in tiles."""
TREE_GAP = 7
"""Fewest columns between two trees."""


def biome_bands(
    left: int,
    right: int,
    rng: np.random.Generator,
    home: int | None = None,
) -> list[tuple[int, int, Biome]]:
    """Cut a width of world into stretches of biomes.

    Neighbors differ, and the stretch with column `home` (the first one by
    default) is plains, where players start. A stretch next to plains that
    holds `home` joins them, so it may be wider than usual.

    Returns:
        list[tuple[int, int, Biome]]: Half-open `[start, end)` columns and
        the biome of each, left to right, without gaps.

    """
    names = list(BIOMES)
    home = left if home is None else min(max(home, left), right - 1)
    bands: list[tuple[int, int, Biome]] = []
    start, previous = left, None
    while start < right:
        width = int(rng.integers(MIN_WIDTH, MAX_WIDTH + 1))
        end = right if right - (start + width) < MIN_WIDTH else start + width
        if start <= home < end and previous == "plains":
            first, _, plains = bands.pop()
            bands.append((first, end, plains))
            start = end
            continue
        choices = [n for n in names if n != previous]
        if start <= home < end:
            choices = ["plains"]
        name = choices[int(rng.integers(len(choices)))]
        bands.append((start, end, BIOMES[name]))
        start, previous = end, name
    return bands
