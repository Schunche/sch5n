# Copyright (c) 2026 Schunche
"""A running game: the world and everything in it, stepped in fixed ticks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sch5n.game.ambient import Ambience
from sch5n.game.config import GameMode
from sch5n.game.content import AIR, TreePart
from sch5n.game.daylight import DAY_SECONDS, daylight, phase
from sch5n.game.floating_item import FloatingItem
from sch5n.game.inventory import CRAFTING_SIDE, Inventory, ItemStack
from sch5n.game.mining import HitResult, can_place, fell_tree, hit_tile, log_of
from sch5n.game.mobs import (
    CONTACT_COOLDOWN,
    KINDS,
    Mob,
)
from sch5n.game.plants import Garden
from sch5n.game.player import Player
from sch5n.log.logger import LOGGER
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sch5n.game.content import BlockDef, Content, ItemDef
    from sch5n.game.mobs import MobKind
    from sch5n.world.tilemap import TileMap

SPAWN_SEARCH_DEPTH = 512
"""How many tiles below the spawn point to look for ground."""

VOID_DEPTH = 32
"""How many tiles below the world's bottom players respawn and items vanish."""


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

    Tools swing whether or not they hit anything, like in the air, but only
    at tiles within reach. Shared
    by the game and by clients predicting their own player.

    Returns:
        bool: Whether a swing started.

    """
    held = player.inventory.held
    if not inp.use or inp.target is None or held is None:
        return False
    if not held.item.is_tool or player.use_cooldown < held.item.spec.use_time:
        return False
    if not player.can_reach(inp.target):
        return False
    player.start_swing(held.item, (inp.target[0] + 0.5) * tile_size)
    player.use_cooldown = 0
    return True


SPAWN_NEAR, SPAWN_FAR = 14, 24
"""Tiles from a player where creatures appear, nearest and farthest."""
SPAWN_SPAN = 40
"""Rows above and below a player searched for ground to appear on."""
SPAWN_EVERY = 90
"""Ticks between tries to spawn a creature."""
MOBS_PER_PLAYER = 3
MAX_MOBS = 16
NIGHT_LIGHT = 0.35
"""Daylight below which creatures spawn."""
DAY_LIGHT = 0.7
"""Daylight above which they start to fade away."""
FADE_CHANCE = 0.004
DESPAWN_TILES = 48
"""Creatures farther than this from every player vanish."""
PLAYER_KNOCK = 3.0
BAT_LIFT = (4, 9)
"""Rows above the ground where flying creatures appear, fewest and most."""
BOSS = "king_slime"
BOSS_CHANCE = 0.04
"""Chance per try, at night, that the boss comes, if none is around."""
LIT_SAFE = 8
"""Creatures do not appear this many tiles from a light."""


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
        self.time_offset = 0
        """Ticks the clock of the day was moved, like by `/time`."""
        self.players: dict[int, Player] = {}
        """Players in the session by id, in joining order."""
        self._next_id = 0
        self._departed: dict[str, Inventory] = {}
        """Inventories of players who left, by name, for when they return."""
        self.floating_items: list[FloatingItem] = []
        self.ambience = Ambience(self.config, self.rng)
        self.garden = Garden(tilemap, self.rng, self.config.tick_rate)
        self.mobs: dict[int, Mob] = {}
        """Hostile creatures by id."""
        self._next_mob = 0
        self.chests: dict[tuple[int, int], Inventory] = {}
        """Contents of the storage blocks that have been opened or
        filled, by tile."""
        self.announcements: list[str] = []
        """Things everyone should hear, like deaths. Servers send and clear
        them."""
        bounds = tilemap.bounds()
        self.horizon = (bounds[1] if bounds else 0) * self.config.tile_size
        """World y of the top of the world, where the sky begins."""
        self.void_y = (
            (bounds[3] + VOID_DEPTH) * self.config.tile_size
            if bounds
            else math.inf
        )
        """World y below which things have fallen out of the world."""
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

    def inventories(self) -> dict[str, Inventory]:
        """Inventories of every named player, present or gone, by name.

        Returns:
            dict[str, Inventory]: What a saved world keeps.

        """
        kept = dict(self._departed)
        for player in self.players.values():
            if player.name:
                kept[player.name] = player.inventory
        return kept

    def chest_at(self, x: int, y: int) -> Inventory | None:
        """Find the storage of the block at a tile, making it if new.

        Returns:
            Inventory | None: The contents, `None` if the tile holds no
            storage block.

        """
        block = self.content.blocks.get(self.tilemap.get(x, y))
        if block is None or block.spec.container is None:
            return None
        chest = self.chests.get((x, y))
        if chest is None:
            chest = self.chests[x, y] = Inventory(block.spec.container)
        return chest

    def chest_contents(self) -> dict[tuple[int, int], Inventory]:
        """Storage that is in the world, for saving.

        Returns:
            dict[tuple[int, int], Inventory]: Contents by tile.

        """
        return {
            tile: chest
            for tile, chest in self.chests.items()
            if self.chest_at(*tile) is chest
        }

    def restore_inventories(self, inventories: dict[str, Inventory]) -> None:
        """Give returning players these inventories, by name, on joining."""
        self._departed.update(inventories)

    def _spawn_point(
        self, preferred: tuple[float, float]
    ) -> tuple[float, float]:
        """Find the player's top left corner, standing on the ground.

        The nearest column with ground is used if the preferred one has none.

        Returns:
            tuple[float, float]: Position in pixels, `preferred` if there
            is no ground.

        """
        size = self.config.tile_size
        width, height = self.config.player.size
        x, y = preferred
        column = int(x // size)
        bounds = self.tilemap.bounds()
        if bounds is None:
            return (x, y)
        top = min(int(y // size), bounds[1]) - 1
        for near in sorted(
            {column, *range(bounds[0], bounds[2])},
            key=lambda c: abs(c - column),
        ):
            ground = self.tilemap.surface_y(
                near, top, top + SPAWN_SEARCH_DEPTH
            )
            if ground is not None:
                return (
                    near * size + (size - width) / 2,
                    ground * size - height,
                )
        return (x, y)

    def _home_point(self, player: Player) -> tuple[float, float] | None:
        """Where a player's bed stands them up, if it is still there.

        Returns:
            tuple[float, float] | None: Top left of the body, `None` without
            a bed.

        """
        home = player.inventory.home
        if home is None:
            return None
        block = self.content.blocks.get(self.tilemap.get(*home))
        if block is None or not block.spec.bed:
            player.inventory.home = None
            return None
        size = self.config.tile_size
        body = player.body
        return (
            home[0] * size + (size - body.w) / 2,
            home[1] * size - body.h,
        )

    def sleep_in(self, player: Player, tile: tuple[int, int]) -> bool:
        """Make the bed at a tile the player's spawn point.

        Returns:
            bool: Whether there was a bed in reach.

        """
        block = self.content.blocks.get(self.tilemap.get(*tile))
        if block is None or not block.spec.bed or not player.can_reach(tile):
            return False
        player.inventory.home = tile
        return True

    def _respawn(self, player: Player) -> None:
        """Put a player back at spawn, at rest. The inventory is kept."""
        body = player.body
        body.x, body.y = self._home_point(player) or self._spawn_point(
            self.setup.spawn
        )
        body.vx = body.vy = 0.0
        player.jump_hold = 0
        player.jumps = player.max_jumps
        player.air_time = 0

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
        """Put the cursor's and the crafting grid's stacks back.

        What won't fit is dropped. Done when the inventory closes, so
        nothing stays on the cursor or in the grid.
        """
        inventory = player.inventory
        loose = [inventory.cursor, *inventory.crafting]
        inventory.cursor = None
        inventory.crafting = [None] * len(inventory.crafting)
        self._stow(player, (stack for stack in loose if stack is not None))

    def _stow(self, player: Player, stacks: Iterable[ItemStack]) -> None:
        """Put stacks into a player's inventory, dropping what won't fit."""
        size = self.config.tile_size
        for stack in stacks:
            leftover = player.inventory.add(stack)
            if leftover is not None:
                body = player.body
                self.drop(
                    leftover,
                    (int(body.center[0] // size), int(body.y // size)),
                )

    def _stations_near(self, player: Player) -> tuple[int, frozenset[str]]:
        """Find what crafting a player has in reach.

        Returns:
            tuple[int, frozenset[str]]: The grid side, larger than usual
            near a bench, and the names of the stations in reach.

        """
        size = self.config.tile_size
        cx, cy = (int(v // size) for v in player.body.center)
        around = math.ceil(player.tuning.reach) + 1
        near = self.tilemap.region(
            cx - around, cy - around, cx + around + 1, cy + around + 1
        )
        side = CRAFTING_SIDE
        names: set[str] = set()
        for block in self.content.blocks:
            grid, station = block.spec.crafting_side, block.spec.station
            if grid is None and station is None:
                continue
            ys, xs = np.nonzero(near == block.id)
            if any(
                player.can_reach((cx - around + x, cy - around + y))
                for x, y in zip(xs.tolist(), ys.tolist(), strict=True)
            ):
                side = max(side, grid or side)
                if station is not None:
                    names.add(station)
        return side, frozenset(names)

    def _fit_crafting_grid(self, player: Player) -> None:
        """Grow or shrink a player's grid with the stations in reach."""
        side, stations = self._stations_near(player)
        player.inventory.stations = stations
        if side != player.inventory.crafting_side:
            self._stow(player, player.inventory.resize_crafting(side))

    def _use_held_item(self, player: Player, inp: TickInput) -> None:
        held = player.inventory.held
        if held is None or held.item.spec.food:
            self._use_by_hand(player, inp)
            return
        if inp.target is None:
            return
        if player.use_cooldown < held.item.spec.use_time:
            return
        x, y = inp.target
        if not player.can_reach(inp.target):
            return

        if swing_tool(player, inp, self.config.tile_size):
            self._strike_mobs(player, held.item.spec.damage, (x, y))
            hit = hit_tile(self.tilemap, x, y, held.item)
            if hit.result is HitResult.WRONG_TOOL and self.ticks % 10 == 0:
                LOGGER.debug("Another tool is needed for %s", hit.block)
            if hit.result is HitResult.BROKEN and hit.block is not None:
                self._broken(hit.block, (x, y))
            elif hit.result is HitResult.TRIMMED and hit.block is not None:
                self._drop_extras(hit.block, (x, y))

        elif inp.place and held.item.spec.places is not None:
            self._place_held(player, held.item, inp.target)

    def _use_by_hand(self, player: Player, inp: TickInput) -> None:
        """Eat the held food, or pick up a plant with an empty hand."""
        held = player.inventory.held
        if held is None:
            self._pick_by_hand(player, inp)
        elif (
            inp.use
            and player.use_cooldown >= held.item.spec.use_time
            and player.vitals.eat(held.item.spec.food)
        ):
            player.inventory.consume_held()
            player.use_cooldown = 0

    def _place_held(
        self, player: Player, item: ItemDef, target: tuple[int, int]
    ) -> None:
        """Build the held item's block at a tile, if it can go there.

        A block with several textures gets one of them at random.
        """
        if item.spec.places is None:
            return
        x, y = target
        size = self.config.tile_size
        tile = Rect(x * size, y * size, size, size)
        block = self.content.blocks.by_name(item.spec.places)
        if any(
            other.body.rect.collides(tile) for other in self.players.values()
        ) or not can_place(self.tilemap, x, y, block):
            return
        variants = len(block.spec.textures)
        variant = int(self.rng.integers(variants)) if variants > 1 else 0
        self.tilemap.set(x, y, block.id, variant)
        self.garden.plant(x, y)
        player.start_swing(item, (x + 0.5) * size)
        player.inventory.consume_held()
        player.use_cooldown = 0

    def _pick_by_hand(self, player: Player, inp: TickInput) -> None:
        """Take a block that an empty hand picks up whole, like a sapling."""
        if not inp.use or inp.target is None:
            return
        block = self.content.blocks.get(self.tilemap.get(*inp.target))
        if (
            block is None
            or not block.spec.hand_pickup
            or block.spec.drop is None
            or not player.can_reach(inp.target)
        ):
            return
        self.tilemap.set(*inp.target, AIR)
        stack = ItemStack(self.content.items[block.spec.drop])
        leftover = player.inventory.add(stack)
        if leftover is not None:
            self.drop(leftover, inp.target)

    def _drop_extras(self, block: BlockDef, tile: tuple[int, int]) -> None:
        """Roll the block's chance drops, like sticks from leaves."""
        for extra in block.spec.extra_drops:
            if self.rng.random() >= extra.chance:
                continue
            amount = int(
                self.rng.integers(extra.min_amount, extra.max_amount + 1)
            )
            self.drop(ItemStack(self.content.items[extra.item], amount), tile)

    def _broken(self, block: BlockDef, tile: tuple[int, int]) -> None:
        """Drop what a broken block leaves, and fell a tree above it.

        Every felled log drops where it was, so the whole tree comes down.
        Felled leaves and leafy logs roll their chance drops there too.
        """
        if block.spec.drop is not None:
            self.drop(ItemStack(self.content.items[block.spec.drop]), tile)
        if block.spec.container is not None:
            chest = self.chests.pop(tile, None)
            for stack in chest or ():
                if stack is not None:
                    self.drop(stack, tile)
        self._drop_extras(block, tile)
        if (
            self.tilemap.get(*tile) != AIR
            or block.spec.tree is not TreePart.TRUNK
        ):
            return
        for felled, where in fell_tree(self.tilemap, *tile):
            drop = log_of(self.tilemap.blocks, felled)
            if drop is not None:
                self.drop(ItemStack(self.content.items[drop]), where)
            self._drop_extras(felled, where)

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
            if floating.body.y > self.void_y or self._pick_up(floating):
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
        if player.body.y > self.void_y:
            self._respawn(player)

    def _tick_vitals(self) -> None:
        """Let players get hungry; one who starves is back at spawn."""
        immune = self.setup.mode is GameMode.ADMIN
        for player in self.players.values():
            if player.vitals.tick(self.config.tick_rate, immune=immune):
                player.vitals.restore()
                player.deaths += 1
                self._respawn(player)
                self.announcements.append(
                    f"{player.name or "A player"} starved"
                )

    @property
    def clock(self) -> int:
        """Ticks the day and night count: time passed plus any shift."""
        return self.ticks + self.time_offset

    def set_time(self, day_phase: float) -> None:
        """Jump to a moment of the day. See `daylight.phase`."""
        rate = self.config.tick_rate
        now = phase(self.clock, rate)
        shift = (day_phase - now) % 1.0
        self.time_offset += round(shift * DAY_SECONDS * rate)

    def hurt_player(self, player: Player, damage: int, cause: str) -> None:
        """Take health from a player. At zero it respawns, fed.

        Admins cannot be hurt.
        """
        if self.setup.mode is GameMode.ADMIN:
            return
        player.vitals.health -= player.inventory.soften(damage)
        if player.vitals.health <= 0:
            player.vitals.restore()
            player.deaths += 1
            self._respawn(player)
            self.announcements.append(f"{player.name or "A player"} {cause}")

    def _pick_kind(self) -> MobKind:
        kinds = list(KINDS.values())
        weights = np.array([kind.weight for kind in kinds], dtype=float)
        return kinds[
            int(self.rng.choice(len(kinds), p=weights / weights.sum()))
        ]

    def _spawn_mob(self, kind: MobKind | None = None) -> None:
        """Try to bring a creature out of the dark near a random player.

        Args:
            kind: What comes; picked by weight if not given.

        """
        if not self.players:
            return
        rng = self.rng
        player = list(self.players.values())[
            int(rng.integers(len(self.players)))
        ]
        size = self.config.tile_size
        side = int(rng.choice((-1, 1)))
        column = int(player.body.center[0] // size) + side * int(
            rng.integers(SPAWN_NEAR, SPAWN_FAR)
        )
        row = int(player.body.center[1] // size)
        surface = self.tilemap.surface_y(
            column, row - SPAWN_SPAN, row + SPAWN_SPAN
        )
        if surface is None:
            return
        kind = kind or self._pick_kind()
        lift = (
            int(rng.integers(BAT_LIFT[0], BAT_LIFT[1])) if kind.flying else 0
        )
        top = ((surface - lift) * size) - kind.size[1]
        mob = Mob(kind, (column * size + (size - kind.size[0]) / 2, top))
        lit = self.tilemap.region(
            column - LIT_SAFE,
            surface - LIT_SAFE,
            column + LIT_SAFE + 1,
            surface + LIT_SAFE + 1,
        )
        if self.tilemap.blocks.light[lit].any():
            return
        wide = -(-kind.size[0] // size)
        high = -(-kind.size[1] // size)
        if self.tilemap.any_solid(
            column, surface - lift - high, column + wide, surface - lift
        ):
            return
        self.mobs[self._next_mob] = mob
        self._next_mob += 1

    def _strike_mobs(
        self, player: Player, damage: int, target: tuple[int, int]
    ) -> None:
        """Hurt the creatures at the tile a player swung at."""
        size = self.config.tile_size
        area = Rect(
            (target[0] - 0.5) * size,
            (target[1] - 0.5) * size,
            2 * size,
            2 * size,
        )
        for mob_id, mob in list(self.mobs.items()):
            if not mob.body.rect.collides(area):
                continue
            if mob.hit(max(1, damage), player.body.center[0]):
                self._mob_died(mob_id)

    def _mob_died(self, mob_id: int) -> None:
        mob = self.mobs.pop(mob_id)
        if mob.kind.boss:
            self.announcements.append(f"The {mob.kind.display_name} fell!")
        if self.rng.random() < mob.kind.drop_chance:
            size = self.config.tile_size
            self.drop(
                ItemStack(
                    self.content.items[mob.kind.drop], mob.kind.drop_amount
                ),
                (int(mob.body.center[0] // size), int(mob.body.y // size)),
            )

    def _tick_mobs(self) -> None:
        """Spawn at night, move, touch players and fade with the day."""
        rate = self.config.tick_rate
        light = daylight(phase(self.clock, rate))
        wanted = min(MAX_MOBS, MOBS_PER_PLAYER * len(self.players))
        if (
            light < NIGHT_LIGHT
            and len(self.mobs) < wanted
            and self.ticks % SPAWN_EVERY == 0
        ):
            self._spawn_mob()
        if (
            light < NIGHT_LIGHT
            and self.ticks % SPAWN_EVERY == 0
            and not any(m.kind.boss for m in self.mobs.values())
            and self.rng.random() < BOSS_CHANCE
        ):
            self._spawn_mob(KINDS[BOSS])
        size = self.config.tile_size
        for mob_id, mob in list(self.mobs.items()):
            nearest = self._nearest_player(mob.body.center)
            target = None if nearest is None else nearest.body.center
            mob.tick(self.tilemap, self.config.physics, size, target)
            gone = mob.body.y > self.void_y or (
                nearest is None
                or math.dist(nearest.body.center, mob.body.center)
                > DESPAWN_TILES * size
                or (light > DAY_LIGHT and self.rng.random() < FADE_CHANCE)
            )
            if gone:
                del self.mobs[mob_id]
                continue
            for player in self.players.values():
                if player.hurt_cooldown <= 0 and mob.body.rect.collides(
                    player.body.rect
                ):
                    player.hurt_cooldown = CONTACT_COOLDOWN
                    away = (
                        1.0
                        if player.body.center[0] >= mob.body.center[0]
                        else -1.0
                    )
                    player.body.vx = away * PLAYER_KNOCK
                    player.body.vy = -PLAYER_KNOCK
                    self.hurt_player(player, mob.kind.damage, "was slain")
        for player in self.players.values():
            player.hurt_cooldown = max(0, player.hurt_cooldown - 1)

    def tick_world(self, view: Rect | None = None) -> None:
        """Advance everything but the players by one tick."""
        self.garden.tick(self._broken)
        for player in self.players.values():
            self._fit_crafting_grid(player)
        self._tick_vitals()
        self._tick_mobs()
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
