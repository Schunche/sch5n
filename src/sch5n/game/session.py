# Copyright (c) 2026 Schunche
"""A running game: the world and everything in it, stepped in fixed ticks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sch5n.game.ambient import Ambience
from sch5n.game.config import GameMode
from sch5n.game.floating_item import FloatingItem
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.mining import HitResult, can_place, hit_tile
from sch5n.game.player import Player
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from sch5n.game.content import Content
    from sch5n.math.rect import Rect
    from sch5n.world.tilemap import TileMap

SPAWN_SEARCH_DEPTH = 512
"""How many tiles below the spawn point to look for ground."""


@dataclass(slots=True)
class TickInput:
    """Player intent for one tick."""

    move_x: int = 0
    """-1 left, 0 none, 1 right."""
    jump: bool = False
    """Jump was pressed since the last tick."""
    use: bool = False
    """Use the held item (break blocks)."""
    place: bool = False
    """Place the held block."""
    target: tuple[int, int] | None = None
    """Tile under the cursor, `None` when the cursor is over the GUI."""
    view: Rect | None = None
    """Visible world area, in pixels. Particles only spawn inside it."""


@dataclass(frozen=True, slots=True)
class GameSetup:
    """How a session starts."""

    mode: GameMode = GameMode.SURVIVAL
    seed: int | None = None
    """Seed for cosmetic randomness and item scatter."""
    spawn: tuple[float, float] = (640.0, 360.0)
    """Preferred spawn position in pixels. The player is dropped onto the
    ground below it."""


DEFAULT_SETUP = GameSetup()


class Game:
    """Owns the simulation state of one play session."""

    def __init__(
        self,
        content: Content,
        tilemap: TileMap,
        setup: GameSetup = DEFAULT_SETUP,
    ) -> None:
        """Start a session on `tilemap`.

        Args:
            content: Loaded game data.
            tilemap: The world. It is modified in place.
            setup: Game mode, seed and spawn point.

        """
        self.content = content
        self.config = content.game
        self.tilemap = tilemap
        self.rng = np.random.default_rng(setup.seed)
        self.ticks = 0

        items = content.items
        inventory = Inventory(
            self.config.inventory.size,
            (
                ItemStack(items[start.item], start.amount)
                for start in self.config.inventory.starting_items
            ),
        )
        self.player = Player(
            self.config,
            inventory,
            self._spawn_point(setup.spawn),
            setup.mode,
        )
        self.floating_items: list[FloatingItem] = []
        self.ambience = Ambience(self.config, self.rng)
        bounds = tilemap.bounds()
        self.horizon = (bounds[1] if bounds else 0) * self.config.tile_size
        """World y of the top of the world, where the sky begins."""

    def _spawn_point(
        self, preferred: tuple[float, float]
    ) -> tuple[float, float]:
        """Find the player's top left corner, standing on the ground.

        Returns:
            tuple[float, float]: Position in pixels, `preferred` if there
            is no ground.

        """
        size = self.config.tile_size
        width, height = self.config.player.size
        x, y = preferred
        column = int(x // size)
        bounds = self.tilemap.bounds()
        top = min(int(y // size), bounds[1] if bounds else 0) - 1
        ground = self.tilemap.surface_y(column, top, top + SPAWN_SEARCH_DEPTH)
        if ground is None:
            return (x, y)
        return (column * size + (size - width) / 2, ground * size - height)

    @property
    def inventory(self) -> Inventory:
        """The player's inventory."""
        return self.player.inventory

    def drop(self, stack: ItemStack, tile: tuple[int, int]) -> FloatingItem:
        """Pop an item out of a tile with a little random toss.

        Returns:
            FloatingItem: The dropped item.

        """
        size = self.config.tile_size
        floating = FloatingItem(
            stack,
            (
                size * (tile[0] + 0.5) - stack.item.spec.drop_size / 2,
                size * tile[1],
            ),
        )
        floating.body.vx = float(self.rng.uniform(-2, 2))
        floating.body.vy = -0.3 - float(self.rng.random()) * 0.2
        self.floating_items.append(floating)
        return floating

    def _use_held_item(self, inp: TickInput) -> None:
        player = self.player
        held = player.inventory.held
        if inp.target is None or held is None:
            return
        if player.use_cooldown < held.item.spec.use_time:
            return
        x, y = inp.target

        if inp.use and held.item.is_tool:
            hit = hit_tile(self.tilemap, x, y, held.item)
            if hit.result is HitResult.WRONG_TOOL:
                if self.ticks % 10 == 0:
                    LOGGER.debug("Another tool is needed for %s", hit.block)
                return
            if hit.result is HitResult.NOTHING:
                return
            player.use_cooldown = 0
            if (
                hit.result is HitResult.BROKEN
                and hit.block is not None
                and hit.block.spec.drop is not None
            ):
                self.drop(
                    ItemStack(self.content.items[hit.block.spec.drop]), (x, y)
                )

        elif inp.place and held.item.spec.places is not None:
            size = self.config.tile_size
            tile_rect = (x * size, y * size)
            body = player.body.rect
            overlaps_player = (
                body.left < tile_rect[0] + size
                and tile_rect[0] < body.right
                and body.top < tile_rect[1] + size
                and tile_rect[1] < body.bottom
            )
            if overlaps_player or not can_place(self.tilemap, x, y):
                return
            block = self.content.blocks.id_of(held.item.spec.places)
            self.tilemap.set(x, y, block)
            player.inventory.consume_held()
            player.use_cooldown = 0

    def _tick_floating_items(self) -> None:
        player = self.player
        target = player.body.center
        player_rect = player.body.rect
        remaining: list[FloatingItem] = []
        for floating in self.floating_items:
            floating.tick(
                self.tilemap,
                self.config.tile_size,
                self.config.floating_item,
                target,
            )
            if floating.body.rect.collides(player_rect):
                leftover = player.inventory.add(floating.stack)
                if leftover is None:
                    continue
            remaining.append(floating)
        self.floating_items = remaining

    def tick(self, inp: TickInput) -> None:
        """Advance the simulation by one tick."""
        if inp.jump:
            self.player.jump()

        self._use_held_item(inp)
        self.ambience.tick(self.tilemap, inp.view, self.config.tile_size)
        self.player.tick(self.tilemap, inp.move_x)
        self._tick_floating_items()
        self.ticks += 1
