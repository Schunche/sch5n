# Copyright (c) 2026 Schunche
"""Experimental software."""

import sys

if __name__ != "__main__":
    sys.exit()
import logging
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
logging.basicConfig(level=logging.DEBUG)

import math
import secrets
from copy import deepcopy

from sch5n.core.log import log_error, log_message, log_success
from sch5n.core.random import randf

log_success("Program started")

import pygame

pygame.init()
log_message("Initialized pygame")

from sch5n.core.animation import Animation
from sch5n.core.cloud import Clouds
from sch5n.core.floating_item import FloatingItem
from sch5n.core.gui import Button, render_text
from sch5n.core.item import Item, Tool
from sch5n.core.item_surface import ITEM_IMAGE
from sch5n.core.loader import (
    FIX_SETTINGS,
    NAME_SPACE,
    SETTINGS,
    load_dir,
    load_image,
    load_image_resized,
    load_images_as_list,
    load_tiles,
    resize_image,
)
from sch5n.core.particle import Particle
from sch5n.core.player import Player
from sch5n.core.table import SAME_LOOT_TILE
from sch5n.core.tilemap import Tilemap

log_message("Loaded local dependency from script")

# INITIAL INPUTS HERE
GAME_MODE: str = "admin"


class Main:
    """Main class responsible for managing the game."""

    def __init__(self) -> None:
        """Initialize the game with specified tile size and settings.

        Raises:
            Exception: If an error occurs during initialization.

        """
        try:
            # Base initialization
            self.frame = 0

            # State
            self.state = "main_menu"
            pygame.mouse.set_visible(False)

            # Main assets
            # tile/block/int
            # mob/species/action/int
            # paricle/species/int
            # cloud/int
            self.assets: dict[
                str,
                dict[
                    str,
                    dict[str | int, pygame.Surface | Animation] | Animation,
                ],
            ] = {
                "mob": {"player": {}},
                "particle": {},
                "icon": {
                    "main": load_image("icon/main"),
                    "cursor": load_image("icon/cursor"),
                },
            }

            # Main window, timer, camera offset
            self.clock: pygame.time.Clock = pygame.time.Clock()
            self.WINDOW: pygame.Surface = pygame.display.set_mode([
                SETTINGS["window_width"],
                SETTINGS["window_height"],
            ])
            pygame.display.set_caption(FIX_SETTINGS["windowName"])
            pygame.display.set_icon(self.assets["icon"]["main"])
            self.scroll: list[float] = [0, 0]
            log_message("Created main window")

            # Tilemap
            self.assets["tile"] = load_tiles("tile")
            self.assets["tileBreakage"] = {
                int(key): resize_image(
                    surf, (SETTINGS["tile_size"], SETTINGS["tile_size"])
                )
                for key, surf in load_dir("tileBreakage").items()
            }
            log_message("Loaded tile assets")

            self.tilemap: Tilemap = Tilemap(assets=self.assets, mapName="map1")
            log_message("Created tilemap")
            self.floating_items: list[FloatingItem] = []

            # Clouds
            self.assets["cloud"] = load_images_as_list("cloud")

            self.wind_speed: float = randf() * 2 - 1
            log_message(f"Starting wind speed: {round(self.wind_speed, 2)}")
            log_message(
                f"Starting wind direction: {
                    "west" if self.wind_speed < 0 else "east"}"
            )
            self.clouds = Clouds(self.assets["cloud"], count=2**4)
            log_message("Generated clouds")

            # Player
            self.assets["mob"]["player"]["idle"] = Animation(
                load_images_as_list("mob/player/idle"), imageDuration=6
            )
            self.assets["mob"]["player"]["run"] = Animation(
                load_images_as_list("mob/player/run"), imageDuration=4
            )
            self.assets["mob"]["player"]["jump"] = Animation(
                load_images_as_list("mob/player/jump"),
                imageDuration=SETTINGS["FPS"] / 6,
            )
            self.assets["mob"]["player"]["slide"] = Animation(
                load_images_as_list("mob/player/slide")
            )
            self.assets["mob"]["player"]["wallSlide"] = Animation(
                load_images_as_list("mob/player/wallSlide")
            )

            self.player: Player = Player(
                self.assets["mob"],
                pos=[SETTINGS["window_width"] / 2, SETTINGS["window_height"] / 2],
                gameMode=GAME_MODE,
            )
            log_message("Created player")

            # Particles
            self.assets["particle"]["leaf"] = Animation(
                load_images_as_list("particle/leaf"),
                imageDuration=SETTINGS["FPS"] // 2,
                loop=False,
            )
            self.particles: list[
                Particle
            ] = []  # List of all existing particles at a given moment

            # Any tile that spawns particles
            self.particleTilePairs: dict[str, list[tuple[str | int]]] = (
                NAME_SPACE["idPairParticleSpawners"]
            )

            # Any tile thats any variant spawns particles
            self.particleTiles: dict[str, list[str]] = NAME_SPACE[
                "anyVariantParticleSpawners"
            ]

            # Format: {"leaf": [rects], "": [rects]} ~ dict[particle] = rectsOfTilesThatEmit{particle}
            # This contains all the rects of tiles, that emit particles
            self.particle_spawner_tiles: dict[str, list[pygame.Rect]] = {}

            for particle_str, spawnerPairs in self.particleTilePairs.items():
                for spawner in self.tilemap.extract(spawnerPairs, keep=True):
                    if particle_str in self.particle_spawner_tiles:
                        self.particle_spawner_tiles[particle_str].append(
                            pygame.Rect(
                                spawner[0][0],
                                spawner[0][1],
                                SETTINGS["tile_size"],
                                SETTINGS["tile_size"],
                            )
                        )
                    else:
                        self.particle_spawner_tiles[particle_str] = [
                            pygame.Rect(
                                spawner[0][0],
                                spawner[0][1],
                                SETTINGS["tile_size"],
                                SETTINGS["tile_size"],
                            )
                        ]

            for particle_str, blockList in self.particleTiles.items():
                for block in blockList:
                    for spawner in self.tilemap.extractAnyVariant(
                        block, keep=True
                    ):
                        if particle_str in self.particle_spawner_tiles:
                            self.particle_spawner_tiles[particle_str].append(
                                pygame.Rect(
                                    spawner[0][0],
                                    spawner[0][1],
                                    SETTINGS["tile_size"],
                                    SETTINGS["tile_size"],
                                )
                            )
                        else:
                            self.particle_spawner_tiles[particle_str] = [
                                pygame.Rect(
                                    spawner[0][0],
                                    spawner[0][1],
                                    SETTINGS["tile_size"],
                                    SETTINGS["tile_size"],
                                )
                            ]

            log_message(
                "Loaded and generated particles, and their respective spawning tiles"
            )
            log_message(
                f"Currently {sum([len(rect_list) for rect_list in self.particle_spawner_tiles.values()])} tiles emit particles"
            )

            self.clicking: dict[str, bool] = {
                "left": False,
                "middle": False,
                "right": False,
                "up": False,
                "down": False,
            }

            self.buttons: dict[str, dict[str, Button]] = {
                "main_game": {
                    # Nothing here lol
                },
                "main_game_inventory": {
                    "settings": Button(
                        pos=(
                            SETTINGS["window_width"]
                            - FIX_SETTINGS["GUI"]["outer_window_padding"],
                            SETTINGS["window_height"]
                            - FIX_SETTINGS["GUI"]["outer_window_padding"],
                        ),
                        text="Settings",
                        align_by="bottom_right",
                    )
                },
                "main_menu": {
                    "play": Button(
                        pos=(
                            int(SETTINGS["window_width"] * 0.5),
                            int(SETTINGS["window_height"] * 0.5),
                        ),
                        text="Play",
                        align_by="center",
                    ),
                    "settings": Button(
                        pos=(
                            int(SETTINGS["window_width"] * 0.5),
                            int(SETTINGS["window_height"] * 0.5)
                            + FIX_SETTINGS["GUI"]["main_menu"]["buttonPadding"],
                        ),
                        text="Settings",
                        align_by="center",
                    ),
                    "exit": Button(
                        pos=(
                            int(SETTINGS["window_width"] * 0.5),
                            int(SETTINGS["window_height"] * 0.5)
                            + FIX_SETTINGS["GUI"]["main_menu"]["buttonPadding"] * 2,
                        ),
                        text="Exit",
                        align_by="center",
                    ),
                },
                "settings": {},
                "main_game_settings": {},
            }

        except Exception as e:
            log_error(f"An error occurred during initialization: {e}")
            sys.exit(1)

    @staticmethod
    def exit_app() -> None:
        """Exit the application."""
        log_success("Successfully ran program")
        pygame.quit()
        sys.exit()

    def spawn_floating_item(
        self, item: Item, spawn_type: str = "tile_broke"
    ) -> None:
        """Spawn a floating item."""
        if spawn_type == "tile_broke":
            self.floating_items.append(
                FloatingItem(
                    [
                        SETTINGS["tile_size"] * (self.tile_pos_at_mouse[0] + 0.5)
                        - ITEM_IMAGE[item.id].get_width() * 0.5,
                        SETTINGS["tile_size"] * self.tile_pos_at_mouse[1],
                    ],
                    item,
                )
            )
            # Set .velocity to a bit side so it has a curve TODO using random
            self.floating_items[-1].velocity[1] = -0.3 - randf() * 0.2
            self.floating_items[-1].velocity[0] = (randf() * 2 - 1) * 2

    def set_state(self, state: str) -> None:
        """Set the current state of the game."""
        self.state = state
        log_message(f"Set state to '{state}'")

    def handle_events(self) -> None:
        """Handle input game events."""
        self.mouse_pos: tuple[int, int] = pygame.mouse.get_pos()
        # pygame.key.get_pressed()[pygame.K_q]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_app()

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.clicking["left"] = True

                    # Slot changing in inventory
                    if self.state == "main_game_inventory":
                        if self.player.inventory.does_hover(self.mouse_pos):
                            slot_num = self.player.inventory.get_slot_num(
                                self.mouse_pos
                            )

                            # This block of code is for when the player clicks on an item in the inventory
                            # In case the items are stackable in both the inventory slot and the cursor slot, and they have the same itemID:
                            # Put more stuff onto the cursor slot, so later the swapping puts it to the inventory slot
                            # Otherwise swapping is enough
                            if (
                                self.player.inventory.get_item_by_num(slot_num)
                                is not None
                            ):
                                if (
                                    self.player.cursor_slot.get_item()
                                    is not None
                                ):
                                    if (
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ).max_amount
                                        != 1
                                    ):
                                        if (
                                            self.player.cursor_slot.get_item().max_amount
                                            != 1
                                        ):
                                            if (
                                                self.player.cursor_slot.get_item().id
                                                == self.player.inventory.get_item_by_num(
                                                    slot_num
                                                ).id
                                            ):
                                                # Items are the same, they are stackable
                                                # So put the difference of # max amount ad slot amount # to the inventory slot
                                                #     In the end swapping, so it reverses the swap at the end

                                                diff_to_max_in_slot: int = (
                                                    self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ).max_amount
                                                    - self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ).amount
                                                )

                                                if (
                                                    diff_to_max_in_slot
                                                    >= self.player.cursor_slot.get_item().amount
                                                ):
                                                    self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ).amount += self.player.cursor_slot.get_item().amount
                                                    self.player.cursor_slot.slot = None
                                                else:
                                                    self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ).amount = self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ).max_amount
                                                    self.player.cursor_slot.slot.amount -= diff_to_max_in_slot

                                                # Cursor item and slot item swich places
                                                (
                                                    self.player.get_inventory()[
                                                        slot_num
                                                    ],
                                                    self.player.cursor_slot.slot,
                                                ) = (
                                                    self.player.cursor_slot.get_item(),
                                                    self.player.inventory.get_item_by_num(
                                                        slot_num
                                                    ),
                                                )

                            # Cursor item and slot item swich places
                            (
                                self.player.get_inventory()[slot_num],
                                self.player.cursor_slot.slot,
                            ) = (
                                self.player.cursor_slot.get_item(),
                                self.player.inventory.get_item_by_num(slot_num),
                            )

                    # Changing states via buttons
                    for name, button in self.buttons[self.state].items():
                        if button.push(self.mouse_pos):
                            match self.state:
                                case "main_menu":
                                    match name:
                                        case "play":
                                            self.set_state("main_game")
                                        case "settings":
                                            self.set_state("settings")
                                        case "exit":
                                            self.exit_app()
                                        case _:
                                            log_error(
                                                "Unknow button fount in existing state: Ignoring this will have consequences"
                                            )
                                case "main_game_inventory":
                                    match name:
                                        case "settings":
                                            self.set_state("main_game_settings")
                                        case _:
                                            log_error(
                                                "Unknow button fount in existing state: Ignoring this will have consequences"
                                            )
                                case _:
                                    log_error(
                                        "Unknown button found in unknown state: Ignoring this may have consequences"
                                    )

                if event.button == 2:
                    self.clicking["middle"] = True
                if event.button == 3:
                    self.clicking["right"] = True

                    # Slot changing in inventory
                    if self.state == "main_game_inventory":
                        if self.player.inventory.does_hover(self.mouse_pos):
                            slot_num = self.player.inventory.get_slot_num(
                                self.mouse_pos
                            )

                            if self.player.cursor_slot.get_item() is None:
                                if (
                                    self.player.inventory.get_item_by_num(slot_num)
                                    is None
                                ):
                                    log_message("'None' with 'None' lol")

                                elif (
                                    self.player.inventory.get_item_by_num(
                                        slot_num
                                    ).max_amount
                                    == 1
                                ):
                                    # Cursor item and slot item swich places
                                    (
                                        self.player.get_inventory()[slot_num],
                                        self.player.cursor_slot.slot,
                                    ) = (
                                        self.player.cursor_slot.get_item(),
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ),
                                    )
                                    log_message("Picked up 'non-stackable' item")

                                else:
                                    if (
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ).amount
                                        % 2
                                        == 0
                                    ):
                                        self.player.get_inventory()[
                                            slot_num
                                        ].amount = int(
                                            self.player.inventory.get_item_by_num(
                                                slot_num
                                            ).amount
                                            // 2
                                        )
                                        self.player.cursor_slot.slot = deepcopy(
                                            self.player.inventory.get_item_by_num(
                                                slot_num
                                            )
                                        )
                                    else:
                                        self.player.get_inventory()[
                                            slot_num
                                        ].amount = (
                                            int(
                                                self.player.inventory.get_item_by_num(
                                                    slot_num
                                                ).amount
                                                // 2
                                            )
                                            + 1
                                        )
                                        self.player.cursor_slot.slot = deepcopy(
                                            self.player.inventory.get_item_by_num(
                                                slot_num
                                            )
                                        )
                                        self.player.cursor_slot.get_item().amount -= 1
                                        if (
                                            self.player.cursor_slot.get_item().amount
                                            == 0
                                        ):
                                            self.player.cursor_slot.slot = None
                                    log_message(
                                        "Picked up half of 'stackable' item"
                                    )

                            elif (
                                self.player.cursor_slot.get_item().max_amount == 1
                            ):
                                if (
                                    self.player.inventory.get_item_by_num(slot_num)
                                    is None
                                ):
                                    (
                                        self.player.get_inventory()[slot_num],
                                        self.player.cursor_slot.slot,
                                    ) = (
                                        self.player.cursor_slot.get_item(),
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ),
                                    )
                                    log_message("Put down 'non-stackable' item")

                                elif (
                                    self.player.inventory.get_item_by_num(
                                        slot_num
                                    ).max_amount
                                    == 1
                                ):
                                    (
                                        self.player.get_inventory()[slot_num],
                                        self.player.cursor_slot.slot,
                                    ) = (
                                        self.player.cursor_slot.get_item(),
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ),
                                    )
                                    log_message("Swapped 'non-stackable' items")

                                else:
                                    (
                                        self.player.get_inventory()[slot_num],
                                        self.player.cursor_slot.slot,
                                    ) = (
                                        self.player.cursor_slot.get_item(),
                                        self.player.inventory.get_item_by_num(
                                            slot_num
                                        ),
                                    )
                                    log_message(
                                        "Put 'non-stackable' itemin the place of 'stackable' item"
                                    )

                            elif (
                                self.player.inventory.get_item_by_num(slot_num)
                                is None
                            ):
                                self.player.get_inventory()[slot_num] = (
                                    deepcopy(self.player.cursor_slot.slot)
                                )
                                self.player.get_inventory()[
                                    slot_num
                                ].amount = 1
                                self.player.cursor_slot.slot.amount -= 1
                                if self.player.cursor_slot.slot.amount == 0:
                                    self.player.cursor_slot.slot = None

                                log_message(
                                    "Put down 1 'stackable' item to empty slot"
                                )

                            elif (
                                self.player.inventory.get_item_by_num(
                                    slot_num
                                ).max_amount
                                == 1
                            ):
                                (
                                    self.player.get_inventory()[slot_num],
                                    self.player.cursor_slot.slot,
                                ) = (
                                    self.player.cursor_slot.get_item(),
                                    self.player.inventory.get_item_by_num(
                                        slot_num
                                    ),
                                )
                                log_message(
                                    "Swapped 'non-stackable' item with 'stackable' items"
                                )

                            elif (
                                self.player.inventory.get_item_by_num(
                                    slot_num
                                ).id
                                != self.player.cursor_slot.get_item().id
                            ):
                                (
                                    self.player.get_inventory()[
                                        slot_num
                                    ],
                                    self.player.cursor_slot.slot,
                                ) = (
                                    self.player.cursor_slot.get_item(),
                                    self.player.inventory.get_item_by_num(
                                        slot_num
                                    ),
                                )
                                log_message("Swapped 'stackable' items")
                            # ItemIDs are the same

                            elif (
                                self.player.inventory.get_item_by_num(
                                    slot_num
                                ).amount
                                == self.player.inventory.get_item_by_num(
                                    slot_num
                                ).max_amount
                            ):
                                # Item in inventpry is at max stack
                                log_message("Swapped 'stackable' items")
                            else:
                                self.player.get_inventory()[
                                    slot_num
                                ].amount += 1
                                self.player.cursor_slot.slot.amount -= 1
                                if (
                                    self.player.cursor_slot.slot.amount
                                    == 0
                                ):
                                    self.player.cursor_slot.slot = (
                                        None
                                    )
                                log_message(
                                    "Put 1 'stackable' item to inventory"
                                )

                if event.button == 4:
                    self.clicking["up"] = True

                    if self.state == "main_game":
                        # Hotbar #Index# changing
                        self.player.hotbar_num = (
                            self.player.hotbar_num - 1
                        ) % 10
                if event.button == 5:
                    self.clicking["down"] = True

                    if self.state == "main_game":
                        # Hotbar #Index# changing
                        self.player.hotbar_num = (
                            self.player.hotbar_num + 1
                        ) % 10

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.clicking["left"] = False
                if event.button == 2:
                    self.clicking["middle"] = False
                if event.button == 3:
                    self.clicking["right"] = False
                if event.button == 4:
                    self.clicking["up"] = False
                if event.button == 5:
                    self.clicking["down"] = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "main_menu":
                        self.exit_app()
                    elif self.state in ["main_game", "main_game_inventory"]:
                        pass  # Intentional
                    elif self.state == "settings":
                        self.set_state("main_menu")

                if event.key == pygame.K_a:
                    self.player.movement_input["left"] = True
                if event.key == pygame.K_d:
                    self.player.movement_input["right"] = True
                if event.key == pygame.K_w:
                    self.player.movement_input["up"] = True
                if event.key == pygame.K_s:
                    self.player.movement_input["down"] = True
                if event.key == pygame.K_SPACE:
                    if self.state in ["main_game", "main_game_inventory"]:
                        self.player.jump()
                if event.key == pygame.K_TAB:
                    if self.state == "main_game_inventory":
                        self.set_state("main_game")
                    elif self.state == "main_game":
                        self.set_state("main_game_inventory")

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_a:
                    self.player.movement_input["left"] = False
                if event.key == pygame.K_d:
                    self.player.movement_input["right"] = False
                if event.key == pygame.K_w:
                    self.player.movement_input["up"] = False
                if event.key == pygame.K_s:
                    self.player.movement_input["down"] = False
                if event.key == pygame.K_SPACE:
                    self.player.movement_input["space"] = False

        # Mouse movement based events
        if self.state in {"main_game", "main_game_inventory"}:
            self.tile_pos_at_mouse = (
                int(self.mouse_pos[0]
                    + self.scroll[0]) // SETTINGS["tile_size"],
                int(self.mouse_pos[1]
                    + self.scroll[1]) // SETTINGS["tile_size"],
            )

    def update_state(self) -> None:
        """Update game state."""
        if self.state in {"main_game", "main_game_inventory"}:
            # Camera movement
            self.scroll[0] += (
                (
                    self.player.pos[0]
                    + self.player.width / 2
                    - SETTINGS["window_width"] / 2
                    - self.scroll[0]
                )
                / SETTINGS["FPS"]
                * 2
            )
            self.scroll[1] += (
                (
                    self.player.pos[1]
                    + self.player.height / 2
                    - SETTINGS["window_height"] / 2
                    - self.scroll[1]
                )
                / SETTINGS["FPS"]
                * 2
            )
            self.render_scroll: tuple[int, int] = (
                int(self.scroll[0]),
                int(self.scroll[1]),
            )

            # Player breaking tiles
            self.player.tool_use_penalty += 1

            if self.clicking["left"]:
                if self.tilemap.is_tile_at(self.tile_pos_at_mouse):
                    if isinstance(
                        self.player.get_item_in_hand(), Tool
                    ):  # Tool in hand
                        if (
                            self.player.tool_use_penalty
                            >= self.player.get_item_in_hand().use_time
                        ):
                            tile = self.tilemap.get_tile_at(self.tile_pos_at_mouse)

                            if self.player.is_able_to_break(block=tile["block"]):
                                # Currenty you have the correct tool in hand

                                hit_tile_rect = pygame.Rect(
                                    self.tile_pos_at_mouse[0] * SETTINGS["tile_size"],
                                    self.tile_pos_at_mouse[1] * SETTINGS["tile_size"],
                                    SETTINGS["tile_size"],
                                    SETTINGS["tile_size"],
                                )

                                if (
                                    tile["block"]
                                    in NAME_SPACE["instant_mined_blocks"]
                                ):
                                    tile["durability"] = 0

                                elif "durability" in tile:
                                    power_type = self.player.break_tile_with(
                                        block=tile["block"]
                                    )

                                    # Already hit tile
                                    tile["durability"] -= (
                                        self.player.get_item_in_hand().tool_type[
                                            power_type
                                        ]
                                    )

                                else:
                                    power_type = self.player.break_tile_with(
                                        block=tile["block"]
                                    )

                                    # Tile has full durability
                                    if (
                                        tile["block"]
                                        in NAME_SPACE[
                                            "durability_of_tile"
                                        ]
                                    ):
                                        tile["durability"] = NAME_SPACE[
                                            "durability_of_tile"
                                        ][tile["block"]]
                                    else:
                                        tile["durability"] = NAME_SPACE[
                                            "durability_of_tile"
                                        ]["_"]
                                    tile["durability"] -= (
                                        self.player.get_item_in_hand().tool_type[
                                            power_type
                                        ]
                                    )

                                if tile["durability"] <= 0:
                                    self.tilemap.break_tile(self.tile_pos_at_mouse)

                                    # Spawn particles TODO

                                    # Pop an item TODO other cases
                                    if tile["block"] in SAME_LOOT_TILE:
                                        self.spawn_floating_item(
                                            deepcopy(
                                                SAME_LOOT_TILE[tile["block"]]
                                            )
                                        )

                                    # Remove the tile formed as rect from particle spawners
                                    for (
                                        key,
                                        rect_list,
                                    ) in self.particle_spawner_tiles.items():
                                        if hit_tile_rect in rect_list:
                                            rect_list.remove(hit_tile_rect)

                                    # Check for tile below/ at the broken tile TODO if it would spawn particles, and then append it accordingly

                                self.player.tool_use_penalty = 0
                            elif not self.frame % 10:
                                log_message(
                                    "Other tool is required to break this tile"
                                )

            # Background
            self.clouds.update(wind_speed=self.wind_speed)

            # Particles
            # Spawn particles
            rects_on_window: list[pygame.Rect] = self.tilemap.get_rects_on_window(
                self.WINDOW, self.render_scroll
            )
            for rect in rects_on_window:
                for particle_str, rects in self.particle_spawner_tiles.items():
                    if rect in rects and (
                        randf() * 49999 * 4
                        < rect.width * rect.height
                    ):
                        pos: tuple[float] = (
                            rect.x + randf() * rect.width,
                            rect.y + randf() * rect.height,
                        )
                        self.particles.append(
                            Particle(
                                assets=self.assets["particle"],
                                species=particle_str,
                                pos=pos,
                                velocity=[
                                    (
                                        self.wind_speed
                                        if particle_str == "leaf"
                                        else randf()
                                    )
                                    * 0.2,
                                    randf() * 0.4,
                                ],
                                frame=secrets.randbelow(
                                    len(
                                        self.assets["particle"][
                                            particle_str
                                        ].images
                                    ),
                                ),
                            )
                        )

            # Udpate particles
            for particle in self.particles.copy():
                kill = particle.update()
                if kill:
                    self.particles.remove(particle)
                if particle.species == "leaf":
                    particle.pos[0] += (
                        math.sin(particle.animation.frame * 0.035) * 0.25
                    )

            # Player movement
            self.player.update(
                self.tilemap,
                (
                    self.player.movement_input["right"]
                    - self.player.movement_input["left"],
                    0,
                ),
            )

            # Floating items
            for index, floating_item in enumerate(self.floating_items):
                floating_item.update(
                    self.tilemap,
                    (
                        self.player.pos[0]
                        + self.player.pivot[0]
                        + self.player.hitBoxWidth / 2,
                        self.player.pos[1]
                        + self.player.pivot[1]
                        + self.player.hitBoxHeight / 2,
                    ),
                )
                if floating_item.get_collision_rect().colliderect(
                    self.player.rect()
                ):
                    item = self.player.inventory.add_item(floating_item.item)
                    if item is None:
                        self.floating_items.remove(floating_item)
                    else:
                        self.floating_items[index] = item

    def render(self) -> None:
        """Render game elements."""
        if self.state == "main_menu":
            # Background
            self.WINDOW.fill(NAME_SPACE["color"]["main_theme"])
            self.WINDOW.blit(
                load_image_resized(
                    "icon/lolBG", (SETTINGS["window_width"], SETTINGS["window_height"])
                ),
                (0, 0),
            )

        elif self.state in ["main_game", "main_game_inventory"]:
            # Background
            self.WINDOW.fill(NAME_SPACE["color"]["pink"])

            self.clouds.render(self.WINDOW, offset=self.render_scroll)

            # Tilemap
            self.tilemap.render(self.WINDOW, offset=self.render_scroll)

            # Mobs
            self.player.render(self.WINDOW, offset=self.render_scroll)

            # Particles
            for particle in self.particles:
                particle.render(self.WINDOW, offset=self.render_scroll)

            # Floating items
            for item in self.floating_items:
                item.render(self.WINDOW, offset=self.render_scroll)

            # Inventory
            if self.state == "main_game":
                self.player.inventory.render_hotbar(
                    self.WINDOW, self.player.hotbar_num, mouse_pos=self.mouse_pos
                )

            elif self.state == "main_game_inventory":
                self.player.inventory.render_full_inventory(
                    self.WINDOW, self.player.hotbar_num, mouse_pos=self.mouse_pos
                )
                self.player.cursor_slot.render_item_at_cursor(
                    self.WINDOW, self.mouse_pos
                )

        else:
            # Unknown state
            self.WINDOW.fill(NAME_SPACE["color"]["main_theme"])

            # Render das text
            render_text(
                self.WINDOW,
                (
                    int(SETTINGS["window_width"] // 2),
                    int(SETTINGS["window_height"] // 2),
                ),
                "Unknown state",
                font_name="arial",
                font_size=48,
            )

        # Buttons
        for button in self.buttons[self.state].values():
            button.render(self.WINDOW, self.mouse_pos)

        # Cursor
        self.WINDOW.blit(self.assets["icon"]["cursor"], self.mouse_pos)

    def run(self) -> None:
        """Main game loop."""
        while True:
            self.handle_events()
            self.update_state()
            self.render()

            self.clock.tick(SETTINGS["FPS"])
            pygame.display.update()
            self.frame += 1


GAME: Main = Main()
GAME.run()
