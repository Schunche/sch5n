# Copyright (c) 2026 Schunche
"""A running game: the world and everything in it, stepped in fixed ticks."""

from __future__ import annotations

import math
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
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sch5n.game.content import Content
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
    jump_held: bool = False
    """Jump is held down, for higher jumps."""
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
    """Preferred spawn position in pixels. Players are dropped onto the
    ground below it."""
    host_player: bool = True
    """Start with a player. Servers start empty and add players as they
    join."""


DEFAULT_SETUP = GameSetup()


def swing_tool(player: Player, inp: TickInput, tile_size: int) -> bool:
    """Swing the held tool at the target if the input asks and it is ready.

    Tools swing whether or not they hit anything, like in the air. Shared
    by the game and by clients predicting their own player.

    Returns:
        bool: Whether a swing started.

    """
    held = player.inventory.held
    if not inp.use or inp.target is None or held is None:
        return False
    if not held.item.is_tool or player.use_cooldown < held.item.spec.use_time:
        return False
    player.start_swing(held.item, (inp.target[0] + 0.5) * tile_size)
    player.use_cooldown = 0
    return True


class Game:
    """Owns the simulation state of one play session.

    Any number of players may join and leave. A session starts with one
    player unless `GameSetup.host_player` is off, as on a server.
    """

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
        self.setup = setup
        self.rng = np.random.default_rng(setup.seed)
        self.ticks = 0
        self.players: dict[int, Player] = {}
        """Players in the session by id, in joining order."""
        self._next_id = 0
        self._departed: dict[str, Inventory] = {}
        """Inventories of players who left, by name, for when they return."""
        self.floating_items: list[FloatingItem] = []
        self.ambience = Ambience(self.config, self.rng)
        bounds = tilemap.bounds()
        self.horizon = (bounds[1] if bounds else 0) * self.config.tile_size
        """World y of the top of the world, where the sky begins."""
        if setup.host_player:
            self.add_player()

    def _starting_inventory(self) -> Inventory:
        items = self.content.items
        return Inventory(
            self.config.inventory.size,
            (
                ItemStack(items[start.item], start.amount)
                for start in self.config.inventory.starting_items
            ),
        )

    def add_player(self, name: str = "") -> int:
        """Spawn a player. A returning `name` gets its inventory back.

        Returns:
            int: The new player's id.

        """
        inventory = self._departed.pop(name, None) if name else None
        player = Player(
            self.config,
            inventory or self._starting_inventory(),
            self._spawn_point(self.setup.spawn),
            self.setup.mode,
            name=name,
        )
        player_id = self._next_id
        self._next_id += 1
        self.players[player_id] = player
        return player_id

    def remove_player(self, player_id: int) -> None:
        """Take a player out of the world, keeping its inventory by name."""
        player = self.players.pop(player_id, None)
        if player is None:
            return
        self.return_cursor_stack(player)
        if player.name:
            self._departed[player.name] = player.inventory

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
    def player(self) -> Player:
        """The first player, who is the only one in single player.

        Raises:
            LookupError: Nobody is playing.

        """
        for player in self.players.values():
            return player
        msg = "No player is in the game"
        raise LookupError(msg)

    @property
    def inventory(self) -> Inventory:
        """The first player's inventory."""
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

    def return_cursor_stack(self, player: Player) -> None:
        """Put the stack held by the cursor back, dropping what won't fit.

        Done when the inventory closes, so nothing stays on the cursor.
        """
        inventory = player.inventory
        if inventory.cursor is None:
            return
        leftover = inventory.add(inventory.cursor)
        inventory.cursor = None
        if leftover is not None:
            body = player.body
            size = self.config.tile_size
            self.drop(
                leftover,
                (int(body.center[0] // size), int(body.y // size)),
            )

    def _use_held_item(self, player: Player, inp: TickInput) -> None:
        held = player.inventory.held
        if inp.target is None or held is None:
            return
        if player.use_cooldown < held.item.spec.use_time:
            return
        x, y = inp.target
        target_x = (x + 0.5) * self.config.tile_size

        if swing_tool(player, inp, self.config.tile_size):
            hit = hit_tile(self.tilemap, x, y, held.item)
            if hit.result is HitResult.WRONG_TOOL and self.ticks % 10 == 0:
                LOGGER.debug("Another tool is needed for %s", hit.block)
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
            tile = Rect(x * size, y * size, size, size)
            if any(
                other.body.rect.collides(tile)
                for other in self.players.values()
            ) or not can_place(self.tilemap, x, y):
                return
            block = self.content.blocks.id_of(held.item.spec.places)
            self.tilemap.set(x, y, block)
            player.start_swing(held.item, target_x)
            player.inventory.consume_held()
            player.use_cooldown = 0

    def _nearest_player(self, pos: tuple[float, float]) -> Player | None:
        return min(
            self.players.values(),
            key=lambda p: math.dist(p.body.center, pos),
            default=None,
        )

    def _tick_floating_items(self) -> None:
        remaining: list[FloatingItem] = []
        for floating in self.floating_items:
            nearest = self._nearest_player(floating.body.center)
            floating.tick(
                self.tilemap,
                self.config.tile_size,
                self.config.floating_item,
                None if nearest is None else nearest.body.center,
            )
            if self._pick_up(floating):
                continue
            remaining.append(floating)
        self.floating_items = remaining

    def _pick_up(self, floating: FloatingItem) -> bool:
        """Give an item to a player touching it.

        Returns:
            bool: Whether all of it was picked up.

        """
        rect = floating.body.rect
        for player in self.players.values():
            if (
                rect.collides(player.body.rect)
                and player.inventory.add(floating.stack) is None
            ):
                return True
        return False

    def step_player(self, player_id: int, inp: TickInput) -> None:
        """Advance one player by one input: jump, use items, move.

        Servers call this once for every input a client sends, so the
        client can predict its player exactly. See `tick_world`.
        """
        player = self.players[player_id]
        if inp.jump:
            player.jump()
        self._use_held_item(player, inp)
        player.tick(self.tilemap, inp.move_x, jump_held=inp.jump_held)

    def tick_world(self, view: Rect | None = None) -> None:
        """Advance everything but the players by one tick."""
        self.ambience.tick(self.tilemap, view, self.config.tile_size)
        self._tick_floating_items()
        self.ticks += 1

    def tick(self, inputs: TickInput | Mapping[int, TickInput]) -> None:
        """Advance the simulation by one tick.

        Args:
            inputs: Input for every player by id, or for the first player.
                Players without input stand still.

        """
        if isinstance(inputs, TickInput):
            view = inputs.view
            inputs = {next(iter(self.players)): inputs} if self.players else {}
        else:
            view = None

        idle = TickInput()
        for player_id in list(self.players):
            self.step_player(player_id, inputs.get(player_id, idle))
        self.tick_world(view)
