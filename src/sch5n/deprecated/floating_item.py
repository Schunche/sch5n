# Copyright (c) 2026 Schunche
"""Experimental software."""

import math
from typing import TYPE_CHECKING

import pygame

from sch5n.deprecated.item_surface import ITEM_IMAGE
from sch5n.deprecated.loader import FIX_SETTINGS, SETTINGS
from sch5n.deprecated.math_func import player_magnet_func
from sch5n.math.vector import FloatTuple2, IntTuple2

if TYPE_CHECKING:
    import sch5n.deprecated.tilemap
    from sch5n.deprecated.item import Item


class FloatingItem:
    def __init__(self, pos: FloatTuple2, item: Item) -> None:
        self.pos: FloatTuple2 = pos
        self.item: Item = item
        self.velocity: FloatTuple2 = FloatTuple2(0, 0)

    def get_collision_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.pos.x + ITEM_IMAGE[self.item.id].get_width() * 0.25,
            self.pos.y + ITEM_IMAGE[self.item.id].get_height() * 0.25,
            ITEM_IMAGE[self.item.id].get_width() * 0.5,
            ITEM_IMAGE[self.item.id].get_height() * 0.5,
        )

    def update(
        self,
        tilemap: sch5n.deprecated.tilemap.Tilemap,
        player_pos: FloatTuple2 | None = None,
    ) -> None:
        """Update the item's position and handle collisions with the tilemap.

        Args:
            tilemap (Tilemap): The tilemap the item collides with.
            player_pos (FloatTuple2, optional)

        """
        if player_pos is None:
            player_pos = FloatTuple2(0, 0)

        self.collisions: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }
        frame_movement: FloatTuple2 = self.velocity.copy()

        self.pos = self.pos.with_x(self.pos.x + frame_movement.x)
        item_rect: pygame.Rect = self.get_collision_rect()
        for tile_rect in tilemap.physics_rects_around(
            IntTuple2(
                int(item_rect.x + item_rect.w * 0.5),
                int(item_rect.y + item_rect.h * 0.5),
            )
        ):
            if tile_rect.colliderect(item_rect):
                if frame_movement[0] > 0:
                    item_rect.right = tile_rect.left
                    self.collisions["right"] = True
                if frame_movement[0] < 0:
                    item_rect.left = tile_rect.right
                    self.collisions["left"] = True

                if self.collisions["left"] or self.collisions["right"]:
                    self.velocity = self.velocity.with_x(0)

                self.pos = self.pos.with_x(
                    item_rect.x - ITEM_IMAGE[self.item.id].get_width() * 0.25
                )

        self.pos = self.pos.with_y(self.pos.y + frame_movement.y)
        item_rect: pygame.Rect = self.get_collision_rect()
        for tile_rect in tilemap.physics_rects_around(
            IntTuple2(
                int(item_rect.x + item_rect.w * 0.5),
                int(item_rect.y + item_rect.h * 0.5),
            )
        ):
            if tile_rect.colliderect(item_rect):
                if frame_movement[1] > 0:
                    item_rect.bottom = tile_rect.top
                    self.collisions["down"] = True
                if frame_movement[1] < 0:
                    item_rect.top = tile_rect.bottom
                    self.collisions["up"] = True

                self.pos = self.pos.with_y(
                    item_rect.y - ITEM_IMAGE[self.item.id].get_height() * 0.25
                )

        # Slow down the item
        if self.velocity[0] > FIX_SETTINGS.air_resist_horizontal:
            self.velocity = self.velocity.with_x(
                self.velocity.x - FIX_SETTINGS.air_resist_horizontal
            )
        elif self.velocity[0] < -FIX_SETTINGS.air_resist_horizontal:
            self.velocity = self.velocity.with_x(
                self.velocity.x + FIX_SETTINGS.air_resist_horizontal
            )
        else:
            self.velocity = self.velocity.with_x(0)

        if (
            math.hypot(
                self.get_collision_rect().centerx - player_pos[0],
                self.get_collision_rect().centery - player_pos[1],
            )
            <= SETTINGS.tile_size * FIX_SETTINGS.reach
        ):
            # The item is in the range of the player
            # So it approaches the player
            app_velocity: FloatTuple2 = player_magnet_func(
                FloatTuple2(
                    (player_pos[0] - self.get_collision_rect().centerx)
                    / SETTINGS.tile_size
                    / FIX_SETTINGS.reach,
                    (player_pos[1] - self.get_collision_rect().centery)
                    / SETTINGS.tile_size
                    / FIX_SETTINGS.reach,
                )
            )

            # -------#####
            # -------------##
            # ---------------#
            # -------O-------#
            # ---------------#
            # -------------##
            # -------#####

            # Set horizontal velocity
            self.velocity = self.velocity.with_x(
                self.velocity.x + app_velocity.x * 0.4
            )

            # Set vertical velocity
            self.velocity = self.velocity.with_y(
                self.velocity.y + app_velocity.y * 0.15
            )
            if not self.collisions["down"] and not self.collisions["up"]:
                self.velocity = self.velocity.with_y(
                    self.velocity.y
                    - FIX_SETTINGS.gravity_strength * abs(app_velocity.y) * 0.5
                )

        # Terminal velocity
        if self.velocity.x > FIX_SETTINGS.floating_item_terminal_velocity:
            self.velocity = self.velocity.with_x(
                FIX_SETTINGS.floating_item_terminal_velocity
            )
        elif self.velocity.x < -FIX_SETTINGS.floating_item_terminal_velocity:
            self.velocity = self.velocity.with_x(
                -FIX_SETTINGS.floating_item_terminal_velocity
            )

        if self.velocity[1] > FIX_SETTINGS.floating_item_terminal_velocity:
            self.velocity = self.velocity.with_y(
                FIX_SETTINGS.floating_item_terminal_velocity
            )
        elif self.velocity[1] < -FIX_SETTINGS.floating_item_terminal_velocity:
            self.velocity = self.velocity.with_y(
                -FIX_SETTINGS.floating_item_terminal_velocity
            )

        self.velocity = self.velocity.with_y(
            min(
                FIX_SETTINGS.floating_item_terminal_velocity,
                self.velocity[1] + FIX_SETTINGS.gravity_strength,
            )
        )
        if self.collisions["down"] or self.collisions["up"]:
            self.velocity = self.velocity.with_y(0)

    def render(
        self, surface: pygame.Surface, offset: FloatTuple2 | None = None
    ) -> None:
        if offset is None:
            offset = FloatTuple2(0, 0)

        surface.blit(
            ITEM_IMAGE[self.item.id],
            (self.pos[0] - offset[0], self.pos[1] - offset[1]),
        )
