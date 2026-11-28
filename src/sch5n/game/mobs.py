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
    """How often it is picked to spawn, next to the other kinds. Zero
    means it never spawns as one of the crowd."""
    drop_amount: int = 1
    boss: bool = False
    """Bosses show a health bar."""
    flying: bool = False
    """It flutters through the air, with no gravity."""
    ranged: bool = False
    """It shoots arrows, and keeps its distance."""
    keep: float = 0.0
    """Tiles a ranged creature tries to stay away from a player."""

    @property
    def display_name(self) -> str:
        """Name shown to players."""
        return self.name.replace("_", " ").title()


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
    "bat": MobKind(
        name="bat",
        size=(16, 12),
        health=4,
        speed=0.9,
        jump=0.0,
        damage=1,
        sight=20.0,
        drop="leaf",
        drop_chance=0.1,
        weight=2,
        flying=True,
    ),
    "skeleton": MobKind(
        name="skeleton",
        size=(16, 32),
        health=10,
        speed=0.45,
        jump=3.6,
        damage=3,
        sight=20.0,
        drop="arrow",
        drop_chance=0.7,
        drop_amount=3,
        ranged=True,
        keep=9.0,
    ),
    "king_slime": MobKind(
        name="king_slime",
        size=(96, 72),
        health=120,
        speed=0.35,
        jump=5.2,
        damage=4,
        sight=40.0,
        drop="slime_ball",
        drop_chance=1.0,
        weight=0,
        drop_amount=10,
        boss=True,
    ),
}
"""Every kind by name; each has a texture `mob/<name>.png`."""
FLUTTER_RATE = 0.25
FLUTTER_SIZE = 0.6
"""How fast and how far a flying creature bobs."""
KEEP_CLOSE = 0.6
"""Share of its distance below which a ranged creature backs off."""
SHOOT_EVERY = 110
"""Ticks between the arrows of a skeleton."""
HURT_TICKS = 12
"""Ticks a mob flashes after being hit."""
KNOCK_DECAY = 0.85
KNOCK_SPEED = 3.0
CONTACT_COOLDOWN = 70
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
        self.age = 0
        self.shoot_wait = SHOOT_EVERY // 2
        """Ticks until a ranged creature may shoot again."""

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

    def _walk_towards(self, dx: float, tile_size: int) -> float:
        """Horizontal speed for a target `dx` pixels away.

        A ranged creature backs off when close and waits at its distance.

        Returns:
            float: Speed, negative to the left.

        """
        speed = self.kind.speed
        if self.kind.ranged:
            keep = self.kind.keep * tile_size
            if abs(dx) < keep * KEEP_CLOSE:
                return -math.copysign(speed, dx)
            if abs(dx) < keep:
                return 0.0
        return math.copysign(speed, dx)

    def _flutter(
        self,
        tilemap: TileMap,
        tile_size: int,
        target: tuple[float, float] | None,
    ) -> None:
        """Fly towards the target, bobbing up and down, or drift about."""
        body = self.body
        self.age += 1
        vx = vy = 0.0
        if target is not None:
            reach = self.kind.sight * tile_size
            dx = target[0] - body.center[0]
            dy = target[1] - body.center[1]
            if abs(dx) < reach and abs(dy) < reach:
                dist = math.hypot(dx, dy) or 1.0
                vx = dx / dist * self.kind.speed
                vy = dy / dist * self.kind.speed
                self.facing_left = vx < 0
        vy += math.sin(self.age * FLUTTER_RATE) * FLUTTER_SIZE
        body.vy = vy
        move_and_collide(body, vx + self.knock, vy, tilemap, tile_size)
        self.knock *= KNOCK_DECAY
        if abs(self.knock) < 0.05:  # ruff: ignore[magic-value-comparison]
            self.knock = 0.0
        if self.hurt:
            self.hurt -= 1

    def tick(
        self,
        tilemap: TileMap,
        physics: PhysicsConfig,
        tile_size: int,
        target: tuple[float, float] | None,
    ) -> None:
        """Advance one tick, walking towards `target` if there is one."""
        body = self.body
        if self.kind.flying:
            self._flutter(tilemap, tile_size, target)
            return
        walk = 0.0
        if target is not None:
            cx = body.center[0]
            reach = self.kind.sight * tile_size
            if abs(target[0] - cx) < reach and abs(target[1] - body.y) < reach:
                walk = self._walk_towards(target[0] - cx, tile_size)
                self.facing_left = target[0] < cx
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
