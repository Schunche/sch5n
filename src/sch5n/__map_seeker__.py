# Copyright (c) 2026 Schunche
"""Game and player management package."""

import sys

import pygame

from sch5n.deprecated.loader import SETTINGS, load_tiles_resized
from sch5n.deprecated.tilemap import Tilemap
from sch5n.utility.log import log_info, log_message

log_info("Program started")
pygame.init()
log_message("Initialized pygame")


log_message("Loaded all local dependency script")


class Main:
    """Main class to manage the game do_loop and handle game events."""

    def __init__(self, tile_size: int = 1) -> None:
        """Initialize the game.

        Args:
            tile_size (int, optional): Size of the tile.

        """
        self.SETTINGS = SETTINGS
        self.tile_size: int = tile_size

        self.assets: dict[str, dict[str, pygame.Surface]] = {}
        self.assets["tile"] = load_tiles_resized("src/img/bit", self.tile_size)
        log_message("Loaded tile assets")

        map_name = "map1"

        self.tilemap: Tilemap = Tilemap(
            assets=self.assets,
            map_name=map_name,
        )
        log_message("Created tilemap")

        self.clock: pygame.time.Clock = pygame.time.Clock()

        self.WINDOW: pygame.Surface = pygame.display.set_mode([
            self.SETTINGS.window_width,
            self.SETTINGS.window_height,
        ])
        pygame.display.set_caption(f"{map_name} von Map Seeker")

        self.pos: list[float] = [0, 0]
        self.movement_input: dict[str, bool] = {
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }

    def exit_app(self) -> None:
        """Exit the application."""
        log_info(f"Successfully run program: {self.clock}")
        pygame.quit()
        sys.exit()

    def handle_events(self) -> None:
        """Handle input game events."""
        keys = {
            pygame.K_a: "left",
            pygame.K_d: "right",
            pygame.K_w: "up",
            pygame.K_s: "down",
        }

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_app()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.exit_app()

                if event.key in keys:
                    self.movement_input[keys[event.key]] = True

                if event.key == pygame.K_r:
                    self.pos = [self.tile_size, self.tile_size * 0]

            if (event.type == pygame.KEYUP) and (event.key in keys):
                self.movement_input[keys[event.key]] = False

    def update_state(self) -> None:
        """Handle game updates."""
        self.pos[0] += (
            self.movement_input["right"] - self.movement_input["left"]
        ) * 5
        self.pos[1] += (
            self.movement_input["down"] - self.movement_input["up"]
        ) * 5

    def render(self) -> None:
        """Handle rendering of game objects."""
        self.WINDOW.fill([0, 0, 0])

        self.tilemap.render_seek(self.WINDOW, offset=self.pos)

    def run(self) -> None:
        """Run the game do_loop."""
        while True:
            self.handle_events()
            self.update_state()
            self.render()

            self.clock.tick(int(self.SETTINGS.FPS / 4))
            pygame.display.update()


if __name__ == "__main__":
    GAME: Main = Main()
    GAME.run()
