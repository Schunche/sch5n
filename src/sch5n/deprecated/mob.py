# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING

import pygame

from sch5n.deprecated.loader import SETTINGS

if TYPE_CHECKING:
    from sch5n.deprecated.animation import Animation
    from sch5n.deprecated.tilemap import Tilemap
    from sch5n.math.vector import FloatTuple2, IntTuple2


class Mob:
    """A class representing a mobile entity in a game."""

    def __init__(
        self,
        species: str,
        assets: dict[str, dict[str, Animation]],
        pos: FloatTuple2,
    ) -> None:
        """Initialize a Mob object.

        Args:
            species (str): The species of the mob.
            assets (dict[str, dict[str, Animation]]): Dictionary mapping.
            pos (tuple[float, float]): The initial position.

        """
        self.pos: FloatTuple2 = pos
        self.width: int = 48
        self.height: int = 48

        # Vector from TopLeft of posxy to TopLeft of hitboxWH
        self.pivot: FloatTuple2 = (0, 0)

        self.hitbox_width: int = 48
        self.hitbox_height: int = 48

        self.species = species
        self.assets: dict[str, dict[str, Animation]] = assets
        self.movement_input: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
            "space": False,
        }
        self.velocity: FloatTuple2 = (0, 0)

        self.action: str = ""
        self.animation_offset: IntTuple2 = (0, 0)
        self.flip: bool = False

        self.set_action("idle")

    def rect(self) -> pygame.rect.Rect:
        """Return the rectangular hitbox of the mob."""
        return pygame.Rect(
            self.pos[0] + self.pivot[0],
            self.pos[1] + self.pivot[1],
            self.hitbox_width,
            self.hitbox_height,
        )

    def set_action(self, action: str) -> None:
        """Set the action of the mob.

        Args:
            action (str): The new action of the mob.

        """
        if action != self.action:
            self.action: str = action
            self.animation: Animation = self.assets[self.species][
                self.action
            ].copy()

    def update(self, tilemap: Tilemap, movement: FloatTuple2 = (0, 0)) -> None:
        """Update the mob's position and handle collisions with the tilemap.

        Args:
            tilemap (Tilemap): The tilemap the mob interacts with.
            movement (FloatTuple2, optional): The movement vector.

        """
        self.collisions: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }
        frame_movement: FloatTuple2 = (
            movement[0] + self.velocity[0],
            movement[1] + self.velocity[1],
        )

        self.pos = (self.pos[0] + frame_movement[0], self.pos[1])
        mob_rect: pygame.Rect = self.rect()
        for rect in tilemap.physics_rects_around((
            int(self.pos[0] + self.pivot[0] + self.hitbox_width / 2),
            int(self.pos[1] + self.pivot[1] + self.hitbox_height / 2),
        )):
            if rect.colliderect(mob_rect):
                if frame_movement[0] > 0:
                    mob_rect.right = rect.left
                    self.collisions["right"] = True
                if frame_movement[0] < 0:
                    mob_rect.left = rect.right
                    self.collisions["left"] = True
                self.pos = (mob_rect.x - self.pivot[0], self.pos[1])

        self.pos = (self.pos[0], self.pos[1] + frame_movement[1])
        mob_rect: pygame.Rect = self.rect()
        for rect in tilemap.physics_rects_around((
            int(self.pos[0] + self.pivot[0] + self.hitbox_width / 2),
            int(self.pos[1] + self.pivot[1] + self.hitbox_height / 2),
        )):
            if rect.colliderect(mob_rect):
                if frame_movement[1] > 0:
                    mob_rect.bottom = rect.top
                    self.collisions["down"] = True
                if frame_movement[1] < 0:
                    mob_rect.top = rect.bottom
                    self.collisions["up"] = True
                self.pos = (self.pos[0], mob_rect.y - self.pivot[1])

        truncate_from_value = 0.1

        if movement[0] > 0:
            self.flip = False
            if not self.collisions["right"]:
                self.velocity = (
                    min(2, self.velocity[0] + 0.1),
                    self.velocity[1],
                )
        elif movement[0] < 0:
            self.flip = True
            if not self.collisions["left"]:
                self.velocity = (
                    max(-2, self.velocity[0] - 0.1),
                    self.velocity[1],
                )
        elif self.velocity[0] > truncate_from_value:
            self.velocity = (self.velocity[0] - 0.1, self.velocity[1])
        elif self.velocity[0] < -truncate_from_value:
            self.velocity = (self.velocity[0] + 0.1, self.velocity[1])
        else:
            self.velocity = (0, self.velocity[1])

        self.velocity = (
            self.velocity[0],
            min(SETTINGS.tile_size / 8, self.velocity[1] + 0.1),
        )
        if self.collisions["down"] or self.collisions["up"]:
            self.velocity = (self.velocity[0], 0)

        self.animation.update()

    def render(
        self, surface: pygame.Surface, offset: tuple[float, float] = (0, 0)
    ) -> None:
        """Render the mob on the given surface with optional offset.

        Args:
            surface (pygame.Surface): The surface to render the mob on.
            offset (tuple[float], optional): The offset to apply to the mob.

        """
        surface.blit(
            pygame.transform.flip(
                self.animation.img(), flip_x=self.flip, flip_y=False
            ),
            (
                self.pos[0] - offset[0] + self.animation_offset[0],
                self.pos[1] - offset[1] + self.animation_offset[1],
            ),
        )
