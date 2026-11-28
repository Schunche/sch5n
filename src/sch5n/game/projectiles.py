# Copyright (c) 2026 Schunche
"""Arrows in flight, shot by players at creatures and back."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from sch5n.game.mobs import Mob
    from sch5n.game.player import Player
    from sch5n.world.tilemap import TileMap

GRAVITY = 0.12
"""Pixels per tick squared an arrow falls."""
MAX_AGE = 300
"""Ticks after which an arrow is gone."""
MAX_SPEED = 20.0
SUBSTEP = 4.0
"""Most pixels an arrow travels between two checks, so it cannot skip a
thin target."""


@dataclass(slots=True)
class Projectile:
    """One arrow. Units are pixels and ticks."""

    item: str
    """Item whose picture it takes."""
    x: float
    y: float
    vx: float
    vy: float
    damage: int
    hostile: bool
    """Shot by a creature: it hurts players. Otherwise it hurts creatures."""
    age: int = 0

    @property
    def angle(self) -> float:
        """Direction it flies in, clockwise in radians (y grows down)."""
        return math.atan2(self.vy, self.vx)


def aim(
    start: tuple[float, float],
    target: tuple[float, float],
    speed: float,
) -> tuple[float, float]:
    """Find the velocity that sends an arrow to a point, allowing for gravity.

    Returns:
        tuple[float, float]: Horizontal and vertical speed.

    """
    speed = min(speed, MAX_SPEED)
    dx, dy = target[0] - start[0], target[1] - start[1]
    dist = math.hypot(dx, dy) or 1.0
    flight = dist / speed
    # It sags by `GRAVITY * t^2 / 2` on the way, so aim a little higher.
    lift = GRAVITY * flight / 2
    return dx / dist * speed, dy / dist * speed - lift


@dataclass(frozen=True, slots=True)
class ArrowWorld:
    """What arrows can meet, and what happens when they do."""

    tilemap: TileMap
    """The world, which stops arrows."""
    tile_size: int
    mobs: Mapping[int, Mob]
    """Creatures, hit by arrows of players."""
    players: Mapping[int, Player]
    """Players, hit by arrows of creatures."""
    on_mob: Callable[[int, Mob, Projectile], None]
    """Called with the id of a creature, it and the arrow that hit it."""
    on_player: Callable[[Player, Projectile], None]
    """Called with a player and the arrow that hit them."""


def advance(arrows: dict[int, Projectile], world: ArrowWorld) -> None:
    """Move every arrow a tick, and let it hit what it meets.

    Spent arrows (on the ground, in a target, or old) are removed.
    """
    for arrow_id, arrow in list(arrows.items()):
        arrow.age += 1
        arrow.vy += GRAVITY
        steps = max(1, math.ceil(math.hypot(arrow.vx, arrow.vy) / SUBSTEP))
        spent = arrow.age > MAX_AGE
        for _ in range(steps):
            if spent:
                break
            arrow.x += arrow.vx / steps
            arrow.y += arrow.vy / steps
            spent = _meets(arrow, world)
        if spent:
            del arrows[arrow_id]


def _meets(arrow: Projectile, world: ArrowWorld) -> bool:
    """Check what an arrow is touching.

    Returns:
        bool: Whether it is spent, on the ground or in a target.

    """
    size = world.tile_size
    tile = (math.floor(arrow.x / size), math.floor(arrow.y / size))
    if world.tilemap.is_solid(*tile):
        return True
    if arrow.hostile:
        for player in world.players.values():
            if player.body.rect.contains_point(arrow.x, arrow.y):
                world.on_player(player, arrow)
                return True
        return False
    for mob_id, mob in list(world.mobs.items()):
        if mob.body.rect.contains_point(arrow.x, arrow.y):
            world.on_mob(mob_id, mob, arrow)
            return True
    return False
