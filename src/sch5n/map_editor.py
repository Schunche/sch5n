# Copyright (c) 2026 Schunche
"""Experimental software."""

import sys

if __name__ != "__main__":
    sys.exit()

import pygame

pygame.init()
from sch5n.core.log import log_error, log_message, log_success

log_message("Initialized pygame")

from sch5n.core.loader import loadJson, loadTiles
from sch5n.core.tilemap import Tilemap

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
            self.STGS: dict[str, str | int] = loadJson("data/settings")
            self.tile_size: int = tile_size

            self.assets: dict[str, dict[str, pygame.Surface]] = {}
            self.assets["tiles"] = loadTiles("src/img/tile")
            log_message("Loaded tile assets")

            self.tilemap: Tilemap = Tilemap(
                assets=self.assets["tiles"],
                mapName="map1",
                tile_size=self.tile_size,
            )
            log_message("Created tilemap")

            self.clock: pygame.time.Clock = pygame.time.Clock()

            self.WINDOW: pygame.Surface = pygame.display.set_mode([
                self.STGS["windowWidth"],
                self.STGS["windowHeight"],
            ])
            pygame.display.set_caption(
                f"{self.STGS["windowName"]} von Map Editor"
            )
            self.scroll: list[float] = [0, 0]

            self.pos: list[float] = [0, 0]
            self.movementInput: dict[str, bool] = {
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
        self.mousePos: tuple[int] = pygame.mouse.get_pos()
        self.tilePos = (
            int(self.mousePos[0] + self.pos[0]) // self.tile_size,
            int(self.mousePos[1] + self.pos[1]) // self.tile_size,
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
                    self.tilemap.saveMap()
                    self.exit_app()

                if event.key == pygame.K_a:
                    self.movementInput["left"] = True
                if event.key == pygame.K_d:
                    self.movementInput["right"] = True
                if event.key == pygame.K_w:
                    self.movementInput["up"] = True
                if event.key == pygame.K_s:
                    self.movementInput["down"] = True
                if event.key == pygame.K_r:
                    self.pos = [self.tile_size, self.tile_size * 0]

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_a:
                    self.movementInput["left"] = False
                if event.key == pygame.K_d:
                    self.movementInput["right"] = False
                if event.key == pygame.K_w:
                    self.movementInput["up"] = False
                if event.key == pygame.K_s:
                    self.movementInput["down"] = False

    def update_state(self) -> None:
        """Handle game updates."""
        self.pos[0] += (
            self.movementInput["right"] - self.movementInput["left"]
        ) * 5
        self.pos[1] += (
            self.movementInput["down"] - self.movementInput["up"]
        ) * 5

        if self.clicking["left"]:
            self.tilemap.insertTile(
                pos=(self.tilePos[0], self.tilePos[1]),
                tile={
                    "block": self.tileList[self.tileIndex][0],
                    "variant": self.tileList[self.tileIndex][1],
                },
            )

        if self.clicking["right"] and self.tilemap.isTileAt(self.tilePos):
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

            self.clock.tick(self.STGS["FPS"])
            pygame.display.update()


GAME: Main = Main()
GAME.run()
