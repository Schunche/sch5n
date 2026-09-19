import pygame

from sch5n.core.item import Item
from sch5n.core.item_surface import ITEM_IMAGE
from sch5n.core.loader import FIX_SETTINGS, SETTINGS
from sch5n.core.math_func import getHyp, playerMagnetFunc
from sch5n.core.tilemap import Tilemap


class FloatingItem:
    def __init__(self, pos: list[float], item: Item) -> None:
        self.pos: list[float] = pos
        self.item: Item = item
        self.velocity: list[float] = [0, 0]

    def get_collision_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.pos[0] + ITEM_IMAGE[self.item.id].get_width() * 0.25,
            self.pos[1] + ITEM_IMAGE[self.item.id].get_height() * 0.25,
            ITEM_IMAGE[self.item.id].get_width() * 0.5,
            ITEM_IMAGE[self.item.id].get_height() * 0.5,
        )

    def update(
        self, tilemap: Tilemap, playerPos: tuple[float] = (0, 0)
    ) -> None:
        """Update the item's position and handle collisions with the tilemap.

        Args:
            tilemap (Tilemap): The tilemap the item collides with.
            playerPos (tuple[float], optional)

        """
        self.collisions: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }
        frameMovement: tuple[float] = (self.velocity[0], self.velocity[1])

        self.pos[0] += frameMovement[0]
        itemRect: pygame.Rect = self.get_collision_rect()
        for tileRect in tilemap.physicsRectsAround((
            int(itemRect.x + itemRect.w * 0.5),
            int(itemRect.y + itemRect.h * 0.5),
        )):
            if tileRect.colliderect(itemRect):
                if frameMovement[0] > 0:
                    itemRect.right = tileRect.left
                    self.collisions["right"] = True
                if frameMovement[0] < 0:
                    itemRect.left = tileRect.right
                    self.collisions["left"] = True

                if self.collisions["left"] or self.collisions["right"]:
                    self.velocity[0] = 0

                self.pos[0] = (
                    itemRect.x - ITEM_IMAGE[self.item.id].get_width() * 0.25
                )

        self.pos[1] += frameMovement[1]
        itemRect: pygame.Rect = self.get_collision_rect()
        for tileRect in tilemap.physicsRectsAround((
            int(itemRect.x + itemRect.w * 0.5),
            int(itemRect.y + itemRect.h * 0.5),
        )):
            if tileRect.colliderect(itemRect):
                if frameMovement[1] > 0:
                    itemRect.bottom = tileRect.top
                    self.collisions["down"] = True
                if frameMovement[1] < 0:
                    itemRect.top = tileRect.bottom
                    self.collisions["up"] = True
                self.pos[1] = (
                    itemRect.y - ITEM_IMAGE[self.item.id].get_width() * 0.25
                )

        # Slow down the item
        if self.velocity[0] > FIX_SETTINGS["airResistHorizontal"]:
            self.velocity[0] -= FIX_SETTINGS["airResistHorizontal"]
        elif self.velocity[0] < -FIX_SETTINGS["airResistHorizontal"]:
            self.velocity[0] += FIX_SETTINGS["airResistHorizontal"]
        else:
            self.velocity[0] = 0

        if (
            getHyp(
                self.get_collision_rect().centerx - playerPos[0],
                self.get_collision_rect().centery - playerPos[1],
            )
            <= SETTINGS["tile_size"] * FIX_SETTINGS["reach"]
        ):
            # The item is in the range of the player
            # So it approaches the player
            appVel: tuple[float] = playerMagnetFunc((
                (playerPos[0] - self.get_collision_rect().centerx)
                / SETTINGS["tile_size"]
                / FIX_SETTINGS["reach"],
                (playerPos[1] - self.get_collision_rect().centery)
                / SETTINGS["tile_size"]
                / FIX_SETTINGS["reach"],
            ))

            # -------#####
            # -------------##
            # ---------------#
            # -------O-------#
            # ---------------#
            # -------------##
            # -------#####

            # Set horizontal velocity
            self.velocity[0] += appVel[0] * 0.4

            # Set vertical velocity
            self.velocity[1] += appVel[1] * 0.15
            if not self.collisions["down"] and not self.collisions["up"]:
                self.velocity[1] -= (
                    FIX_SETTINGS["gravityStrength"] * abs(appVel[1]) * 0.5
                )

        # Terminal velocity
        if self.velocity[0] > FIX_SETTINGS["floatingItemTermVel"]:
            self.velocity[0] = FIX_SETTINGS["floatingItemTermVel"]
        elif self.velocity[0] < -FIX_SETTINGS["floatingItemTermVel"]:
            self.velocity[0] = -FIX_SETTINGS["floatingItemTermVel"]

        if self.velocity[1] > FIX_SETTINGS["floatingItemTermVel"]:
            self.velocity[1] = FIX_SETTINGS["floatingItemTermVel"]
        elif self.velocity[1] < -FIX_SETTINGS["floatingItemTermVel"]:
            self.velocity[1] = -FIX_SETTINGS["floatingItemTermVel"]

        self.velocity[1] = min(
            FIX_SETTINGS["floatingItemTermVel"],
            self.velocity[1] + FIX_SETTINGS["gravityStrength"],
        )
        if self.collisions["down"] or self.collisions["up"]:
            self.velocity[1] = 0

    def render(
        self, surface: pygame.Surface, offset: tuple[float] = (0, 0)
    ) -> None:
        surface.blit(
            ITEM_IMAGE[self.item.id],
            (self.pos[0] - offset[0], self.pos[1] - offset[1]),
        )
