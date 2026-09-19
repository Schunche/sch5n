# Copyright (c) 2026 Schunche
"""Game and player management package."""

import sys

if __name__ != "__main__":
    sys.exit()

import pygame

from sch5n.core.loader import load_json
from sch5n.core.log import log_error, log_message, log_success
from sch5n.core.tilemap import Tilemap

log_success("Program started")
pygame.init()
log_message("Initialized pygame")


log_message("Loaded all local dependency script")


class Main:
    """Main class to manage the game loop and handle game events."""

    def __init__(self, tile_size: int = 1) -> None:
        """Initialize the game.

        Args:
            tile_size (int, optional): Size of the tiles. Defaults to 2.

        """
        try:
            self.SETTINGS: dict[str, str | int] = load_json("data/settings")
            self.tile_size: int = tile_size

            self.assets: dict[str, dict[str, pygame.Surface]] = {}
            self.assets["tiles"] = loadTilesResized(
                "src/img/bit", tile_size=self.tile_size
            )
            log_message("Loaded tile assets")

            self.tilemap: Tilemap = Tilemap(
                assets=self.assets["tiles"],
                mapName="procedural",
                tile_size=self.tile_size,
            )
            log_message("Created tilemap")

            self.clock: pygame.time.Clock = pygame.time.Clock()

            self.WINDOW: pygame.Surface = pygame.display.set_mode([
                self.SETTINGS["window_width"],
                self.SETTINGS["window_height"],
            ])
            pygame.display.set_caption(
                f"{self.SETTINGS["windowName"]} von Map Seeker"
            )

            self.pos: list[float] = [0, 0]
            self.movement_input: dict[str, bool] = {
                "left": False,
                "right": False,
                "up": False,
                "down": False,
            }

        except Exception as e:
            log_error(f"An error occurred during initialization: {e}")
            sys.exit(1)

    def exit_app(self) -> None:
        """Exit the application."""
        log_success(f"Successfully run program: {self.clock}")
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
        """Run the game loop."""
        while True:
            self.handle_events()
            self.update_state()
            self.render()

            self.clock.tick(int(self.SETTINGS["FPS"] / 4))
            pygame.display.update()


GAME: Main = Main()
GAME.run()
