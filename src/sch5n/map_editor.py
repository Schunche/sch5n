# Copyright (c) 2026 Schunche
"""Experimental software."""

import sys

if __name__ != "__main__":
    sys.exit()

import pygame

from sch5n.core.loader import load_json, load_tiles
from sch5n.core.log import log_error, log_message, log_success
from sch5n.core.tilemap import Tilemap

pygame.init()

log_message("Initialized pygame")


log_message("Loaded all local dependency script")

MOUSE_BUTTON_LEFT = 1
MOUSE_BUTTON_MIDDLE = 2
MOUSE_BUTTON_RIGHT = 3
MOUSE_BUTTON_UP = 4
MOUSE_BUTTON_DOWN = 5


class Main:
    """Main class to manage the game loop and handle game events."""

    def __init__(self, tile_size: int = 32) -> None:
        """Initialize the game.

        Args:
            tile_size (int, optional): Size of the tiles. Defaults to 32.

        """
        try:
            self.SETTINGS: dict[str, str | int] = load_json("data/settings")
            self.tile_size: int = tile_size

            self.assets: dict[str, dict[str, pygame.Surface]] = {}
            self.assets["tiles"] = load_tiles("src/img/tile")
            log_message("Loaded tile assets")

            self.tilemap: Tilemap = Tilemap(
                assets=self.assets["tiles"],
                mapName="map1"
            )
            log_message("Created tilemap")

            self.clock: pygame.time.Clock = pygame.time.Clock()

            self.WINDOW: pygame.Surface = pygame.display.set_mode([
                self.SETTINGS["window_width"],
                self.SETTINGS["window_height"],
            ])
            pygame.display.set_caption(
                f"{self.SETTINGS["windowName"]} von Map Editor"
            )
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

            self.tileList: list[tuple[str | int]] = []
            for block in self.assets["tiles"]:
                for variant in self.assets["tiles"][block]:
                    self.tileList.append((block, variant))
            self.tileIndex: int = 0
            self.currentTileImg: pygame.Surface = self.assets["tiles"][
                self.tileList[self.tileIndex][0]
            ][self.tileList[self.tileIndex][1]].copy()
            self.currentTileImg.set_alpha(100)

        except Exception as e:
            log_error(f"An error occurred during initialization: {e}")
            sys.exit(1)

    def exit_app(self) -> None:
        """Exit the application."""
        log_success("Successfully run program")
        pygame.quit()
        sys.exit()

    def handle_events(self) -> None:
        """Handle input game events."""
        self.mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
        self.tilePos = (
            int(self.mouse_pos[0] + self.pos[0]) // self.tile_size,
            int(self.mouse_pos[1] + self.pos[1]) // self.tile_size,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_app()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == MOUSE_BUTTON_LEFT:
                    self.clicking["left"] = True
                if event.button == MOUSE_BUTTON_MIDDLE:
                    self.clicking["middle"] = True
                if event.button == MOUSE_BUTTON_RIGHT:
                    self.clicking["right"] = True
                if event.button == MOUSE_BUTTON_UP:
                    self.clicking["up"] = True
                    self.tileIndex = (self.tileIndex + 1) % len(self.tileList)
                if event.button == MOUSE_BUTTON_DOWN:
                    self.clicking["down"] = True
                    self.tileIndex = (self.tileIndex - 1) % len(self.tileList)
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
                    self.exit_app()

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
            self.tilemap.insertTile(
                pos=(self.tilePos[0], self.tilePos[1]),
                tile={
                    "block": self.tileList[self.tileIndex][0],
                    "variant": self.tileList[self.tileIndex][1],
                },
            )

        if self.clicking["right"] and self.tilemap.is_tile_at(self.tilePos):
            log_message(f"Tile deleted at {self.tilePos}")
            self.tilemap.deleteTile(self.tilePos)

        self.currentTileImg = self.assets["tiles"][
            self.tileList[self.tileIndex][0]
        ][self.tileList[self.tileIndex][1]].copy()
        self.currentTileImg.set_alpha(100)

    def render(self) -> None:
        """Handle rendering of game objects."""
        self.WINDOW.fill([0, 0, 0])

        self.tilemap.render(self.WINDOW, offset=self.pos)

        self.WINDOW.blit(
            self.currentTileImg,
            (
                self.tilePos[0] * self.tile_size - self.pos[0],
                self.tilePos[1] * self.tile_size - self.pos[1],
            ),
        )
        self.WINDOW.blit(
            self.currentTileImg,
            (int(self.tile_size / 2), int(self.tile_size / 2)),
        )

    def run(self) -> None:
        """Run the game loop."""
        while True:
            self.handle_events()
            self.update_state()
            self.render()

            self.clock.tick(self.SETTINGS["FPS"])
            pygame.display.update()


GAME: Main = Main()
GAME.run()
