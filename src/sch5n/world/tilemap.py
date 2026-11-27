# Copyright (c) 2026 Schunche
"""Chunked tile storage backed by numpy arrays."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from sch5n.game.content import AIR

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sch5n.game.content import BlockRegistry
    from sch5n.math.vector import IntTuple2

CHUNK_SHIFT = 5
CHUNK_SIZE = 1 << CHUNK_SHIFT
"""Width and height of a chunk in tiles."""
_CHUNK_MASK = CHUNK_SIZE - 1


@dataclass(slots=True)
class Chunk:
    """A `CHUNK_SIZE`² block of tiles. Arrays are indexed `[y, x]`."""

    blocks: np.ndarray = field(
        default_factory=lambda: np.zeros(
            (CHUNK_SIZE, CHUNK_SIZE), dtype=np.uint16
        )
    )
    variants: np.ndarray = field(
        default_factory=lambda: np.zeros(
            (CHUNK_SIZE, CHUNK_SIZE), dtype=np.uint8
        )
    )
    filled: int = 0
    """Number of non-air tiles."""
    revision: int = 0
    """Incremented on every change. Lets renderers cache chunk meshes."""


def chunk_of(x: int, y: int) -> IntTuple2:
    """Chunk coordinate containing a tile.

    Returns:
        IntTuple2: Chunk coordinate.

    """
    return (x >> CHUNK_SHIFT, y >> CHUNK_SHIFT)


class TileMap:
    """An unbounded grid of tiles.

    Tile coordinates are integers; x grows right, y grows down.
    Breaking progress is kept sparsely in `damage`.
    """

    def __init__(self, blocks: BlockRegistry) -> None:
        """Create an empty map."""
        self.blocks = blocks
        self.chunks: dict[IntTuple2, Chunk] = {}
        self.damage: dict[IntTuple2, float] = {}
        """Remaining durability of partially broken tiles."""

    def __len__(self) -> int:
        """Count non-air tiles.

        Returns:
            int: Number of tiles.

        """
        return sum(chunk.filled for chunk in self.chunks.values())

    def get(self, x: int, y: int) -> int:
        """Block id at a tile. Air outside of existing chunks.

        Returns:
            int: Block id.

        """
        chunk = self.chunks.get((x >> CHUNK_SHIFT, y >> CHUNK_SHIFT))
        if chunk is None:
            return AIR
        return int(chunk.blocks[y & _CHUNK_MASK, x & _CHUNK_MASK])

    def get_variant(self, x: int, y: int) -> int:
        """Texture variant at a tile.

        Returns:
            int: Variant index.

        """
        chunk = self.chunks.get((x >> CHUNK_SHIFT, y >> CHUNK_SHIFT))
        if chunk is None:
            return 0
        return int(chunk.variants[y & _CHUNK_MASK, x & _CHUNK_MASK])

    def set(self, x: int, y: int, block: int, variant: int = 0) -> None:
        """Place a block (or `AIR`) at a tile. Clears breaking progress."""
        key = (x >> CHUNK_SHIFT, y >> CHUNK_SHIFT)
        chunk = self.chunks.get(key)
        if chunk is None:
            if block == AIR:
                return
            chunk = self.chunks[key] = Chunk()

        ly, lx = y & _CHUNK_MASK, x & _CHUNK_MASK
        previous = int(chunk.blocks[ly, lx])
        chunk.blocks[ly, lx] = block
        chunk.variants[ly, lx] = variant if block != AIR else 0
        chunk.filled += (block != AIR) - (previous != AIR)
        chunk.revision += 1
        self.damage.pop((x, y), None)

        if chunk.filled == 0:
            del self.chunks[key]

    def is_solid(self, x: int, y: int) -> bool:
        """Whether the tile blocks movement.

        Returns:
            bool: True for solid blocks.

        """
        return bool(self.blocks.solid[self.get(x, y)])

    def region(self, x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
        """Block ids of the half-open tile rectangle `[x0, x1) x [y0, y1)`.

        Returns:
            np.ndarray: uint16 array with shape `(y1 - y0, x1 - x0)`.

        """
        width, height = max(x1 - x0, 0), max(y1 - y0, 0)
        out = np.zeros((height, width), dtype=np.uint16)
        if width == 0 or height == 0:
            return out

        for cy in range(y0 >> CHUNK_SHIFT, ((y1 - 1) >> CHUNK_SHIFT) + 1):
            for cx in range(x0 >> CHUNK_SHIFT, ((x1 - 1) >> CHUNK_SHIFT) + 1):
                chunk = self.chunks.get((cx, cy))
                if chunk is None:
                    continue
                ox, oy = cx << CHUNK_SHIFT, cy << CHUNK_SHIFT
                sx0, sy0 = max(x0, ox), max(y0, oy)
                sx1 = min(x1, ox + CHUNK_SIZE)
                sy1 = min(y1, oy + CHUNK_SIZE)
                out[sy0 - y0 : sy1 - y0, sx0 - x0 : sx1 - x0] = chunk.blocks[
                    sy0 - oy : sy1 - oy, sx0 - ox : sx1 - ox
                ]
        return out

    def any_solid(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        """Whether any tile in `[x0, x1) x [y0, y1)` is solid.

        Returns:
            bool: True if a solid tile is present.

        """
        return bool(self.blocks.solid[self.region(x0, y0, x1, y1)].any())

    def iter_tiles(self) -> Iterator[tuple[int, int, int, int]]:
        """Iterate over non-air tiles as `(x, y, block, variant)`.

        Yields:
            tuple[int, int, int, int]: A tile.

        """
        for (cx, cy), chunk in self.chunks.items():
            ys, xs = np.nonzero(chunk.blocks)
            for ly, lx in zip(ys.tolist(), xs.tolist(), strict=True):
                yield (
                    (cx << CHUNK_SHIFT) + lx,
                    (cy << CHUNK_SHIFT) + ly,
                    int(chunk.blocks[ly, lx]),
                    int(chunk.variants[ly, lx]),
                )

    def bounds(self) -> tuple[int, int, int, int] | None:
        """Bounding box of all tiles as half-open `(x0, y0, x1, y1)`.

        Returns:
            tuple[int, int, int, int] | None: `None` for an empty map.

        """
        boxes: list[tuple[int, int, int, int]] = []
        for (cx, cy), chunk in self.chunks.items():
            ys, xs = np.nonzero(chunk.blocks)
            ox, oy = cx << CHUNK_SHIFT, cy << CHUNK_SHIFT
            boxes.append((
                ox + int(xs.min()),
                oy + int(ys.min()),
                ox + int(xs.max()) + 1,
                oy + int(ys.max()) + 1,
            ))
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

    def surface_y(self, x: int, y_from: int, y_to: int) -> int | None:
        """Topmost solid tile of a column between `y_from` and `y_to`.

        Returns:
            int | None: The y coordinate, `None` if the column is empty.

        """
        column = self.blocks.solid[self.region(x, y_from, x + 1, y_to)[:, 0]]
        hits = np.flatnonzero(column)
        return y_from + int(hits[0]) if hits.size else None
