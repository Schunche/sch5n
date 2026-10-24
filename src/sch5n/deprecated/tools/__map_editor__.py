# Copyright (c) 2026 Schunche
"""Experimental software."""

import sys

import pygame

from sch5n.deprecated.loader import SETTINGS, load_tiles
from sch5n.deprecated.tilemap import Tile, Tilemap
from sch5n.log.logger import LOGGER

pygame.init()

LOGGER.debug("Initialized pygame")


LOGGER.debug("Loaded all local dependency script")

MOUSE_BUTTON_LEFT = 1
MOUSE_BUTTON_MIDDLE = 2
MOUSE_BUTTON_RIGHT = 3
MOUSE_BUTTON_UP = 4
MOUSE_BUTTON_DOWN = 5


def exit_app() -> None:
    """Exit the application."""
    LOGGER.info("Successfully run program")
    pygame.quit()
    sys.exit()


class Main:
    """Main class to manage the game do_loop and handle game events."""

    def __init__(self, tile_size: int = 32) -> None:
        """Initialize the game.

        Args:
            tile_size (int, optional): Size of the tile. Defaults to 32.

        """
        self.SETTINGS = SETTINGS
        self.tile_size: int = tile_size

        self.assets: dict[str, dict[str, pygame.Surface]] = {}
        self.assets["tile"] = load_tiles("tile")
        LOGGER.debug("Loaded tile assets")

        map_name = "map1"

        self.tilemap: Tilemap = Tilemap(assets=self.assets, map_name=map_name)
        LOGGER.debug("Created tilemap")

        self.clock: pygame.time.Clock = pygame.time.Clock()

        self.WINDOW: pygame.Surface = pygame.display.set_mode([
            self.SETTINGS.window_width,
            self.SETTINGS.window_height,
        ])
        pygame.display.set_caption(f"{map_name} von Map Editor")
        self.scroll: list[float] = [0, 0]

        self.pos: list[float] = [0, 0]
        self.movement_input: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }
        self.clicking: dict[str, bool] = {
            "left": False,
            "right": False,
            "middle": False,
            "up": False,
            "down": False,
        }

        self.tile_list: list[tuple[str, int]] = []
        for block in self.assets["tile"]:
            for variant in self.assets["tile"][block]:
                self.tile_list.append((block, variant))
        self.tile_index: int = 0
        self.current_tile_img: pygame.Surface = self.assets["tile"][
            self.tile_list[self.tile_index][0]
        ][self.tile_list[self.tile_index][1]].copy()
        self.current_tile_img.set_alpha(100)

    def handle_events(self) -> None:
        """Handle input game events."""
        self.mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
        self.tile_pos = (
            int(self.mouse_pos[0] + self.pos[0]) // self.tile_size,
            int(self.mouse_pos[1] + self.pos[1]) // self.tile_size,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit_app()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == MOUSE_BUTTON_LEFT:
                    self.clicking["left"] = True
                if event.button == MOUSE_BUTTON_MIDDLE:
                    self.clicking["middle"] = True
                if event.button == MOUSE_BUTTON_RIGHT:
                    self.clicking["right"] = True
                if event.button == MOUSE_BUTTON_UP:
                    self.clicking["up"] = True
                    self.tile_index = (self.tile_index + 1) % len(
                        self.tile_list
                    )
                if event.button == MOUSE_BUTTON_DOWN:
                    self.clicking["down"] = True
                    self.tile_index = (self.tile_index - 1) % len(
                        self.tile_list
                    )
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == MOUSE_BUTTON_LEFT:
                    self.clicking["left"] = False
                if event.button == MOUSE_BUTTON_MIDDLE:
                    self.clicking["middle"] = False
                if event.button == MOUSE_BUTTON_RIGHT:
                    self.clicking["right"] = False
                if event.button == MOUSE_BUTTON_UP:
                    self.clicking["up"] = False
                if event.button == MOUSE_BUTTON_DOWN:
                    self.clicking["down"] = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.tilemap.save_map()
                    exit_app()

                if event.key == pygame.K_a:
                    self.movement_input["left"] = True
                if event.key == pygame.K_d:
                    self.movement_input["right"] = True
                if event.key == pygame.K_w:
                    self.movement_input["up"] = True
                if event.key == pygame.K_s:
                    self.movement_input["down"] = True
                if event.key == pygame.K_r:
                    self.pos = [self.tile_size, self.tile_size * 0]

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_a:
                    self.movement_input["left"] = False
                if event.key == pygame.K_d:
                    self.movement_input["right"] = False
                if event.key == pygame.K_w:
                    self.movement_input["up"] = False
                if event.key == pygame.K_s:
                    self.movement_input["down"] = False

    def update_state(self) -> None:
        """Handle game updates."""
        self.pos[0] += (
            self.movement_input["right"] - self.movement_input["left"]
        ) * 5
        self.pos[1] += (
            self.movement_input["down"] - self.movement_input["up"]
        ) * 5

        if self.clicking["left"]:
            tile: Tile = {
                "block": self.tile_list[self.tile_index][0],
                "variant": self.tile_list[self.tile_index][1],
            }
            self.tilemap.insert_tile(
                pos=(self.tile_pos[0], self.tile_pos[1]), tile=tile
            )
            LOGGER.debug("Placed tile: %s", tile)

        if self.clicking["right"] and self.tilemap.is_tile_at(self.tile_pos):
            LOGGER.debug("Tile deleted at %s", self.tile_pos)
            self.tilemap.delete_tile(self.tile_pos)

        self.current_tile_img = self.assets["tile"][
            self.tile_list[self.tile_index][0]
        ][self.tile_list[self.tile_index][1]].copy()
        self.current_tile_img.set_alpha(127)

    def render(self) -> None:
        """Handle rendering of game objects."""
        self.WINDOW.fill([0, 0, 0])

        self.tilemap.render(self.WINDOW, offset=self.pos, breakage=False)

        self.WINDOW.blit(
            self.current_tile_img,
            (
                self.tile_pos[0] * self.tile_size - self.pos[0],
                self.tile_pos[1] * self.tile_size - self.pos[1],
            ),
        )
        self.WINDOW.blit(
            self.current_tile_img,
            (int(self.tile_size / 2), int(self.tile_size / 2)),
        )

    def run(self) -> None:
        """Run the game do_loop."""
        while True:
            self.handle_events()
            self.update_state()
            self.render()

            self.clock.tick(self.SETTINGS.FPS)
            pygame.display.update()


def main() -> None:
    Main().run()


if __name__ == "__main__":
    main()
