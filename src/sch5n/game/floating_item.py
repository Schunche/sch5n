# Copyright (c) 2026 Schunche
"""Items lying in the world, attracted by the player."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sch5n.game.physics import Body, approach, move_and_collide
from sch5n.math.rect import Rect
from sch5n.math.scalar import clamp, sign_or_zero

if TYPE_CHECKING:
    from sch5n.game.config import FloatingItemConfig
    from sch5n.game.inventory import ItemStack
    from sch5n.world.tilemap import TileMap


def magnet_pull(offset: float) -> float:
    """Attraction towards the player along one axis.

    Args:
        offset: Item position minus player position, divided by the
            magnet range. Meaningful in [-1, 1].

    Returns:
        float: Acceleration in [-1, 1], pointing towards the player.
        Strongest halfway, zero at the player and at the edge of range.

    """
    return -(math.sin(math.pi * offset) ** 2) * sign_or_zero(offset)


class FloatingItem:
    """A dropped item stack.

    The collision box is the middle half of the drawn sprite.
    """

    def __init__(self, stack: ItemStack, pos: tuple[float, float]) -> None:
        """Drop `stack` with its sprite's top left corner at `pos`."""
        self.stack = stack
        size = stack.item.spec.drop_size
        self.size = size
        self.body = Body(
            pos[0] + size / 4, pos[1] + size / 4, size / 2, size / 2
        )

    @property
    def sprite_rect(self) -> Rect:
        """Where the item is drawn."""
        return Rect(
            self.body.x - self.size / 4,
            self.body.y - self.size / 4,
            self.size,
            self.size,
        )

    def tick(
        self,
        tilemap: TileMap,
        tile_size: int,
        config: FloatingItemConfig,
        target: tuple[float, float] | None,
    ) -> None:
        """Advance one tick, pulled towards `target` when it is in range."""
        body = self.body
        hits = move_and_collide(body, body.vx, body.vy, tilemap, tile_size)
        if hits.horizontal:
            body.vx = 0.0

        resist = config.air_resistance
        body.vx = (
            approach(body.vx, 0.0, resist) if abs(body.vx) > resist else 0.0
        )

        if target is not None:
            reach = tile_size * config.magnet_range
            cx, cy = body.center
            if math.hypot(cx - target[0], cy - target[1]) <= reach:
                pull_x = magnet_pull((cx - target[0]) / reach)
                pull_y = magnet_pull((cy - target[1]) / reach)
                strength_x, strength_y = config.magnet_strength
                body.vx += pull_x * strength_x
                body.vy += pull_y * strength_y
                if not hits.vertical:
                    # Partially cancel gravity so items can float up.
                    body.vy -= config.gravity * abs(pull_y) * 0.5

        limit = config.terminal_velocity
        body.vx = clamp(body.vx, -limit, limit)
        body.vy = clamp(body.vy + config.gravity, -limit, limit)
        if hits.vertical:
            body.vy = 0.0
