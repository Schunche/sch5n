# Copyright (c) 2026 Schunche
"""Hostile creatures: they come out at night and chase players."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sch5n.game.physics import Body, move_and_collide

if TYPE_CHECKING:
    from sch5n.game.config import PhysicsConfig
    from sch5n.world.tilemap import TileMap


@dataclass(frozen=True, slots=True)
class MobKind:
    """What a kind of creature is like. Units are pixels and ticks."""

    name: str
    size: tuple[int, int]
    health: int
    speed: float
    jump: float
    """Upward speed of a hop over a step in its way."""
    damage: int
    """Health a touch takes from a player."""
    sight: float
    """How far, in tiles, it notices a player."""
    drop: str
    """Item that may drop when it dies."""
    drop_chance: float
    weight: int = 1
    """How often it is picked to spawn, next to the other kinds."""


KINDS = {
    "slime": MobKind(
        name="slime",
        size=(32, 24),
        health=8,
        speed=0.55,
        jump=4.2,
        damage=2,
        sight=14.0,
        drop="slime_ball",
        drop_chance=0.7,
        weight=2,
    ),
    "zombie": MobKind(
        name="zombie",
        size=(16, 32),
        health=14,
        speed=0.4,
        jump=3.6,
        damage=3,
        sight=18.0,
        drop="cloth",
        drop_chance=0.5,
    ),
}
"""Every kind by name; each has a texture `mob/<name>.png`."""
HURT_TICKS = 12
"""Ticks a mob flashes after being hit."""
KNOCK_DECAY = 0.85
KNOCK_SPEED = 3.0
CONTACT_COOLDOWN = 45
"""Ticks a player is safe after being touched."""


class Mob:
    """One creature."""

    def __init__(self, kind: MobKind, pos: tuple[float, float]) -> None:
        """Place a mob with its top left corner at `pos`."""
        self.kind = kind
        self.body = Body(pos[0], pos[1], *kind.size)
        self.health = kind.health
        self.facing_left = False
        self.hurt = 0
        """Ticks left of the flash after a hit."""
        self.knock = 0.0
        """Horizontal push from a hit, fading away."""

    def hit(self, damage: int, from_x: float) -> bool:
        """Take damage and get pushed away from `from_x`.

        Returns:
            bool: Whether it died.

        """
        self.health -= damage
        self.hurt = HURT_TICKS
        away = 1.0 if self.body.center[0] >= from_x else -1.0
        self.knock = away * KNOCK_SPEED
        self.body.vy = -2.5
        return self.health <= 0

    def tick(
        self,
        tilemap: TileMap,
        physics: PhysicsConfig,
        tile_size: int,
        target: tuple[float, float] | None,
    ) -> None:
        """Advance one tick, walking towards `target` if there is one."""
        body = self.body
        walk = 0.0
        if target is not None:
            cx = body.center[0]
            reach = self.kind.sight * tile_size
            if abs(target[0] - cx) < reach and abs(target[1] - body.y) < reach:
                walk = math.copysign(self.kind.speed, target[0] - cx)
                self.facing_left = walk < 0
        body.vy = min(body.vy + physics.gravity, physics.max_fall_speed)
        grounded = body.collisions.down
        hits = move_and_collide(
            body, walk + self.knock, body.vy, tilemap, tile_size
        )
        if hits.down or hits.up:
            body.vy = 0.0
        if hits.horizontal and (grounded or hits.down):
            body.vy = -self.kind.jump
        self.knock *= KNOCK_DECAY
        if abs(self.knock) < 0.05:  # ruff: ignore[magic-value-comparison]
            self.knock = 0.0
        if self.hurt:
            self.hurt -= 1
