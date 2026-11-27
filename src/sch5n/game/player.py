# Copyright (c) 2026 Schunche
"""The player character: movement, jumping and wall sliding."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sch5n.game.physics import Body, approach, move_and_collide

if TYPE_CHECKING:
    from sch5n.game.config import GameConfig, GameMode
    from sch5n.game.inventory import Inventory
    from sch5n.world.tilemap import TileMap


class Action(StrEnum):
    """What the player is doing. Animation names match these."""

    IDLE = "idle"
    RUN = "run"
    JUMP = "jump"
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
        """Ticks since the held item was last used."""

    def _set_action(self, action: Action) -> None:
        if action != self.action:
            self.action = action
            self.action_age = 0

    @property
    def is_airborne(self) -> bool:
        """Whether the player has been off the ground for a while."""
        return self.air_time > self.tuning.airborne_after_ticks

    def tick(self, tilemap: TileMap, move_x: int) -> None:
        """Advance one tick. `move_x` is -1, 0 or 1."""
        tuning = self.tuning
        body = self.body

        hits = move_and_collide(
            body,
            move_x * tuning.walk_speed + body.vx,
            body.vy,
            tilemap,
            self.config.tile_size,
        )

        if move_x > 0:
            self.facing_left = False
            if not hits.right:
                body.vx = min(tuning.max_speed, body.vx + tuning.acceleration)
        elif move_x < 0:
            self.facing_left = True
            if not hits.left:
                body.vx = max(-tuning.max_speed, body.vx - tuning.acceleration)
        else:
            body.vx = (
                approach(body.vx, 0.0, tuning.friction)
                if abs(body.vx) > tuning.friction
                else 0.0
            )

        body.vy = min(
            self.config.physics.max_fall_speed,
            body.vy + self.config.physics.gravity,
        )
        if hits.vertical:
            body.vy = 0.0

        self.air_time += 1
        if hits.down:
            self.air_time = 0
            self.jumps = self.max_jumps

        self.wall_slide = hits.horizontal and self.is_airborne
        if self.wall_slide:
            body.vy = min(body.vy, tuning.wall_slide_speed)
            self.facing_left = hits.left
            self._set_action(Action.WALL_SLIDE)
        elif self.is_airborne:
            self._set_action(Action.JUMP)
        elif move_x:
            self._set_action(Action.RUN)
        else:
            self._set_action(Action.IDLE)

        self.action_age += 1
        self.use_cooldown += 1

    def jump(self) -> bool:
        """Jump, or wall jump while sliding on a wall.

        Returns:
            bool: Whether a jump happened.

        """
        tuning = self.tuning
        if self.wall_slide:
            push, lift = tuning.wall_jump_velocity
            self.body.vx = push if self.facing_left else -push
            self.body.vy = -lift
            self.jumps = max(0, self.jumps - 1)
        elif self.jumps:
            self.body.vy = -tuning.jump_velocity
            self.jumps -= 1
        else:
            return False
        self.air_time = tuning.airborne_after_ticks + 1
        return True
