# Copyright (c) 2026 Schunche
"""Axis separated AABB movement against the tile grid."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from sch5n.world.tilemap import TileMap


@dataclass(slots=True)
class Collisions:
    """Sides on which a body hit a solid tile during the last move."""

    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False

    @property
    def horizontal(self) -> bool:
        """Hit a wall."""
        return self.left or self.right

    @property
    def vertical(self) -> bool:
        """Hit a floor or ceiling."""
        return self.up or self.down


@dataclass(slots=True)
class Body:
    """A moving axis aligned box. `x`, `y` is the top left corner."""

    x: float
    y: float
    w: float
    h: float
    vx: float = 0.0
    vy: float = 0.0
    collisions: Collisions = field(default_factory=Collisions)

    @property
    def rect(self) -> Rect:
        """Current bounding box."""
        return Rect(self.x, self.y, self.w, self.h)

    @property
    def center(self) -> tuple[float, float]:
        """Center of the box."""
        return (self.x + self.w / 2, self.y + self.h / 2)


def _tile_span(start: float, end: float, tile_size: int) -> range:
    """Find the tiles overlapped by the open interval `(start, end)`.

    Returns:
        range: Tile indices along one axis.

    """
    return range(math.floor(start / tile_size), math.ceil(end / tile_size))


def _any_solid(tilemap: TileMap, xs: range, ys: range) -> bool:
    return (
        len(xs) > 0
        and len(ys) > 0
        and tilemap.any_solid(xs.start, ys.start, xs.stop, ys.stop)
    )


def move_and_collide(
    body: Body, dx: float, dy: float, tilemap: TileMap, tile_size: int
) -> Collisions:
    """Move a body by (dx, dy), stopping at solid tiles.

    Movement is resolved one axis at a time, x first. Moves are assumed to
    be shorter than a tile, which holds for every speed in the game.

    Returns:
        Collisions: Which sides hit something. Also stored on the body.

    """
    hits = Collisions()

    if dx:
        body.x += dx
        ys = _tile_span(body.y, body.y + body.h, tile_size)
        if dx > 0:
            column = math.ceil((body.x + body.w) / tile_size) - 1
            if _any_solid(tilemap, range(column, column + 1), ys):
                body.x = column * tile_size - body.w
                hits.right = True
        else:
            column = math.floor(body.x / tile_size)
            if _any_solid(tilemap, range(column, column + 1), ys):
                body.x = (column + 1) * tile_size
                hits.left = True

    if dy:
        body.y += dy
        xs = _tile_span(body.x, body.x + body.w, tile_size)
        if dy > 0:
            row = math.ceil((body.y + body.h) / tile_size) - 1
            if _any_solid(tilemap, xs, range(row, row + 1)):
                body.y = row * tile_size - body.h
                hits.down = True
        else:
            row = math.floor(body.y / tile_size)
            if _any_solid(tilemap, xs, range(row, row + 1)):
                body.y = (row + 1) * tile_size
                hits.up = True

    body.collisions = hits
    return hits


def approach(value: float, target: float, step: float) -> float:
    """Move `value` towards `target` by at most `step`.

    Returns:
        float: The new value.

    """
    if value < target:
        return min(value + step, target)
    return max(value - step, target)
