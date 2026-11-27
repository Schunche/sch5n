# Copyright (c) 2026 Schunche
"""The player character: movement, jumping and wall sliding."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sch5n.game.physics import Body, approach, move_and_collide

if TYPE_CHECKING:
    from sch5n.game.config import GameConfig, GameMode
    from sch5n.game.inventory import Inventory
    from sch5n.game.physics import Collisions
    from sch5n.world.tilemap import TileMap


class Action(StrEnum):
    """What the player is doing. Animation names match these."""

    IDLE = "idle"
    RUN = "run"
    JUMP = "jump"
    """In the air, going up."""
    FALL = "fall"
    """In the air, going down."""
    WALL_SLIDE = "wall_slide"


class Player:
    """The player controlled character."""

    def __init__(
        self,
        config: GameConfig,
        inventory: Inventory,
        pos: tuple[float, float],
        mode: GameMode,
    ) -> None:
        """Create a player with its top left corner at `pos`."""
        self.config = config
        self.tuning = config.player
        width, height = self.tuning.size
        self.body = Body(pos[0], pos[1], width, height)
        self.inventory = inventory
        self.max_jumps = self.tuning.max_jumps.get(mode, 1)
        self.jumps = self.max_jumps
        self.air_time = 0
        self.wall_slide = False
        self.facing_left = False
        self.action = Action.IDLE
        self.action_age = 0
        """Ticks since `action` last changed."""
        self.use_cooldown = 0
        self.jump_hold = 0
        """Ticks the current jump may still be held to rise higher."""
        self._jump_speed = self.tuning.jump_velocity
        """Ticks since the held item was last used."""

    def _set_action(self, action: Action) -> None:
        if action != self.action:
            self.action = action
            self.action_age = 0

    @property
    def is_airborne(self) -> bool:
        """Whether the player has been off the ground for a while."""
        return self.air_time > self.tuning.airborne_after_ticks

    def tick(
        self, tilemap: TileMap, move_x: int, *, jump_held: bool = False
    ) -> None:
        """Advance one tick. `move_x` is -1, 0 or 1.

        Holding jump keeps a jump rising for up to `jump_hold_ticks`.
        """
        body = self.body
        hits = move_and_collide(
            body,
            move_x * self.tuning.walk_speed + body.vx,
            body.vy,
            tilemap,
            self.config.tile_size,
        )
        self._walk(move_x, hits)
        self._fall(hits, jump_held=jump_held)
        self._choose_action(hits, move_x)
        self.action_age += 1
        self.use_cooldown += 1

    def _walk(self, move_x: int, hits: Collisions) -> None:
        """Speed up towards `move_x`, or slow down without input."""
        tuning = self.tuning
        body = self.body
        if move_x > 0:
            self.facing_left = False
            if not hits.right:
                body.vx = min(tuning.max_speed, body.vx + tuning.acceleration)
        elif move_x < 0:
            self.facing_left = True
            if not hits.left:
                body.vx = max(-tuning.max_speed, body.vx - tuning.acceleration)
        elif abs(body.vx) > tuning.friction:
            body.vx = approach(body.vx, 0.0, tuning.friction)
        else:
            body.vx = 0.0

    def _fall(self, hits: Collisions, *, jump_held: bool) -> None:
        """Apply gravity, a held jump, and landing."""
        body = self.body
        physics = self.config.physics
        body.vy = min(physics.max_fall_speed, body.vy + physics.gravity)
        if hits.vertical:
            body.vy = 0.0
            self.jump_hold = 0
        if self.jump_hold > 0 and jump_held:
            body.vy = min(body.vy, -self._jump_speed)
            self.jump_hold -= 1
        else:
            self.jump_hold = 0

        self.air_time += 1
        if hits.down:
            self.air_time = 0
            self.jumps = self.max_jumps

    def _choose_action(self, hits: Collisions, move_x: int) -> None:
        """Pick the action (and so the animation) for this tick."""
        self.wall_slide = hits.horizontal and self.is_airborne
        if self.wall_slide:
            self.body.vy = min(self.body.vy, self.tuning.wall_slide_speed)
            self.facing_left = hits.left
            self._set_action(Action.WALL_SLIDE)
        elif self.is_airborne:
            rising = self.body.vy < 0
            self._set_action(Action.JUMP if rising else Action.FALL)
        elif move_x:
            self._set_action(Action.RUN)
        else:
            self._set_action(Action.IDLE)

    def jump(self) -> bool:
        """Jump, or wall jump while sliding on a wall.

        Returns:
            bool: Whether a jump happened.

        """
        tuning = self.tuning
        if self.wall_slide:
            push, lift = tuning.wall_jump_velocity
            self.body.vx = push if self.facing_left else -push
            self._jump_speed = lift
            self.jumps = max(0, self.jumps - 1)
        elif self.jumps:
            self._jump_speed = tuning.jump_velocity
            self.jumps -= 1
        else:
            return False
        self.body.vy = -self._jump_speed
        self.jump_hold = tuning.jump_hold_ticks
        self.air_time = tuning.airborne_after_ticks + 1
        return True
