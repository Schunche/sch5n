# Copyright (c) 2026 Schunche
"""A whole game session, with the real game data."""

import pytest

from sch5n.game.config import GameMode
from sch5n.game.content import AIR, Content
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.math.rect import Rect
from sch5n.world.tilemap import TileMap

PLACE_TICKS = 40
"""Long enough to place one block."""
LEAF_LOOT = {"stick", "leaf", "bird_nest", "oak_sapling", "apple"}


def flat_world(content: Content) -> TileMap:
    """Build a flat strip of dirt.

    Returns:
        TileMap: The world.

    """
    tilemap = TileMap(content.blocks)
    dirt = content.blocks.id_of("dirt")
    for x in range(-30, 30):
        for y in range(10, 14):
            tilemap.set(x, y, dirt)
    return tilemap


@pytest.fixture
def game(content: Content) -> Game:
    """Start a survival game on a flat world.

    Returns:
        Game: The game.

    """
    return Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))


def run(game: Game, ticks: int, **kwargs: object) -> None:
    """Advance the game with the same input every tick."""
    for _ in range(ticks):
        game.tick(TickInput(**kwargs))  # type: ignore[arg-type]


def test_spawns_on_the_ground(game: Game) -> None:
    """The player starts standing on the ground and stays there."""
    body = game.player.body
    assert body.y + body.h == 10 * 32
    run(game, 30)
    assert body.y + body.h == 10 * 32


def test_starting_items(game: Game) -> None:
    """The player starts with the configured tools."""
    assert [s.item.name for s in game.inventory if s] == [
        "iron_pickaxe",
        "iron_axe",
        "iron_shovel",
        "iron_lopper",
    ]


def test_mine_drop_and_pick_up(game: Game) -> None:
    """A mined block drops an item that ends up in the inventory."""
    target = (1, 10)
    run(game, 200, use=True, target=target)
    assert game.tilemap.get(*target) == AIR
    run(game, 300)
    assert not game.floating_items
    stacks = [s for s in game.inventory if s and s.item.name == "dirt_block"]
    assert sum(s.amount for s in stacks) >= 1


def test_cannot_mine_through_gui(game: Game) -> None:
    """Nothing is mined while the cursor is over the GUI."""
    run(game, 200, use=True, target=None)
    assert game.tilemap.get(1, 10) != AIR


def test_place_block(game: Game, content: Content) -> None:
    """Placing a block uses one item."""
    slot, amount = 2, 3
    game.inventory.slots[slot] = ItemStack(content.items["dirt_block"], amount)
    game.inventory.select(slot)
    run(game, 40, place=True, target=(3, 9))
    assert game.tilemap.get(3, 9) == content.blocks.id_of("dirt")
    placed = game.inventory[slot]
    assert placed is not None
    assert placed.amount == amount - 1


def test_cannot_place_inside_player(game: Game, content: Content) -> None:
    """Blocks cannot be placed inside the player."""
    game.inventory.slots[2] = ItemStack(content.items["dirt_block"], 3)
    game.inventory.select(2)
    body = game.player.body
    tile = (int(body.center[0] // 32), int(body.center[1] // 32))
    run(game, 40, place=True, target=tile)
    assert game.tilemap.get(*tile) == AIR


def test_cannot_place_in_thin_air(game: Game, content: Content) -> None:
    """A block with no solid neighbour is refused and not used up."""
    slot, amount = 2, 3
    game.inventory.slots[slot] = ItemStack(content.items["dirt_block"], amount)
    game.inventory.select(slot)
    run(game, 40, place=True, target=(3, 7))
    assert game.tilemap.get(3, 7) == AIR
    held = game.inventory[slot]
    assert held is not None
    assert held.amount == amount


def test_jump(game: Game) -> None:
    """Jumping moves the player up."""
    y0 = game.player.body.y
    game.tick(TickInput(jump=True))
    run(game, 10)
    assert game.player.body.y < y0


def test_leaves_emit_particles_deterministically(content: Content) -> None:
    """Leaf particles depend only on the seed."""

    def particles(seed: int) -> list[tuple[float, float]]:
        """Simulate leaves with a seed.

        Returns:
            list[tuple[float, float]]: Particle positions.

        """
        tilemap = flat_world(content)
        leaf = content.blocks.id_of("oak_leaf")
        for x in range(10):
            for y in range(5):
                tilemap.set(x, y, leaf)
        game = Game(content, tilemap, GameSetup(seed=seed, spawn=(-500, 0)))
        run(game, 300, view=Rect(-100, -100, 1000, 1000))
        return [(p.x, p.y) for p in game.ambience.particles]

    first = particles(5)
    assert first
    assert first == particles(5)
    assert first != particles(6)


def test_survival_is_the_default_mode(content: Content) -> None:
    """Without asking for admin, the player gets a single jump."""
    game = Game(content, flat_world(content))
    assert game.player.max_jumps == 1
    admin = Game(content, flat_world(content), GameSetup(mode=GameMode.ADMIN))
    assert admin.player.max_jumps > 1


def test_stone_drops_cobblestone(game: Game, content: Content) -> None:
    """Mined stone can be picked up and placed again."""
    target = (2, 10)
    game.tilemap.set(*target, content.blocks.id_of("stone"))
    run(game, 300, use=True, target=target)
    assert game.tilemap.get(*target) == AIR
    run(game, 300)
    stones = [s for s in game.inventory if s and s.item.name == "cobblestone"]
    assert sum(s.amount for s in stones) == 1
    assert stones[0].item.spec.places == "cobblestone"


TILE = 32
LOGS_ABOVE_AND_CHOPPED = 3
"""The chopped log, the log above it and the leafy log on top."""
MIN_LOG_HITS = 8
MIN_JUMP_TILES = 2.1
"""A held jump must clear a two block step."""
MAX_JUMP_TILES = 2.6
MAX_WALK_TILES_PER_SECOND = 5.0
MAX_NEST_CHANCE = 0.05


def test_jump_height_and_walk_speed(content: Content) -> None:
    """A held jump clears two blocks but not three; walking is moderate."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    body = game.player.body
    ground = body.y
    game.tick(TickInput(jump=True, jump_held=True))
    top = ground
    for _ in range(120):
        game.tick(TickInput(jump_held=True))
        top = min(top, body.y)
    assert MIN_JUMP_TILES < (ground - top) / TILE < MAX_JUMP_TILES

    run(game, 120, move_x=1)
    x = body.x
    run(game, 30, move_x=1)
    tiles_per_second = (body.x - x) / 30 * content.game.tick_rate / TILE
    assert tiles_per_second < MAX_WALK_TILES_PER_SECOND


def test_distant_blocks_are_out_of_reach(game: Game, content: Content) -> None:
    """Blocks farther than the reach can be neither broken nor built on."""
    reach = content.game.player.reach
    far = (int(reach) + 3, 10)
    run(game, 300, use=True, target=far)
    assert game.tilemap.get(*far) != AIR
    assert game.player.swing is None
    game.inventory.slots[2] = ItemStack(content.items["dirt_block"], 3)
    game.inventory.select(2)
    above = (far[0], 9)
    run(game, 40, place=True, target=above)
    assert game.tilemap.get(*above) == AIR


def planted(content: Content) -> tuple[Game, dict[str, int]]:
    """Grow two trees on flat ground: trunks at x 2 and 5, crowns touching.

    Returns:
        tuple[Game, dict[str, int]]: The game, and block ids by name.

    """
    ids = {
        name: content.blocks.id_of(name)
        for name in ("oak_log", "oak_leaf", "oak_log_leaf")
    }
    tilemap = flat_world(content)
    for trunk in (2, 5):
        for y in range(6, 10):
            tilemap.set(trunk, y, ids["oak_log"])
        tilemap.set(trunk, 5, ids["oak_log_leaf"])
        for x in range(trunk - 1, trunk + 2):
            for y in (4, 5):
                if (x, y) != (trunk, 5):
                    tilemap.set(x, y, ids["oak_leaf"])
    tilemap.set(3, 5, ids["oak_leaf"])  # Joins the two crowns.
    tilemap.set(4, 5, ids["oak_leaf"])
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    game.inventory.select(1)  # The axe.
    return game, ids


def test_chopping_a_log_fells_the_tree_above(content: Content) -> None:
    """Breaking a trunk brings down what is above; the stump stays."""
    game, ids = planted(content)
    tilemap = game.tilemap
    run(game, 600, use=True, target=(2, 7))
    assert tilemap.get(2, 7) == AIR
    # Above: trunk and crown are gone.
    assert all(tilemap.get(2, y) == AIR for y in range(4, 7))
    assert tilemap.get(1, 4) == AIR
    # Below: the stump stays.
    assert tilemap.get(2, 8) == ids["oak_log"]
    assert tilemap.get(2, 9) == ids["oak_log"]
    # The other tree keeps its trunk.
    assert tilemap.get(5, 6) == ids["oak_log"]
    assert tilemap.get(5, 5) == ids["oak_log_leaf"]
    # Every log of the felled part comes down, in one stack.
    run(game, 300)
    logs = sum(
        s.amount for s in game.inventory if s and s.item.name == "oak_log"
    )
    assert logs == LOGS_ABOVE_AND_CHOPPED


def test_leafy_logs_are_logs(content: Content) -> None:
    """A leafy log is chopped like a log, and fells what is above it."""
    game, ids = planted(content)
    tilemap = game.tilemap
    leafy, log = (
        content.blocks.by_name(name) for name in ("oak_log_leaf", "oak_log")
    )
    assert leafy.durability == log.durability
    run(game, 600, use=True, target=(2, 5))
    assert tilemap.get(2, 5) == AIR
    assert tilemap.get(2, 4) == AIR  # The crown above fell.
    assert tilemap.get(2, 6) == ids["oak_log"]  # The trunk below stays.
    run(game, 300)
    logs = sum(
        s.amount for s in game.inventory if s and s.item.name == "oak_log"
    )
    assert logs == 1


def test_logs_take_longer_than_one_swing_a_second(content: Content) -> None:
    """A log takes many axe hits."""
    game, _ = planted(content)
    axe = content.items["iron_axe"]
    log = content.blocks.by_name("oak_log")
    hits = -(-log.durability // axe.spec.tool_power["axe"])
    assert hits >= MIN_LOG_HITS
    run(game, (hits - 1) * axe.spec.use_time, use=True, target=(2, 7))
    assert game.tilemap.get(2, 7) != AIR


def test_lopper_trims_leafy_logs(content: Content) -> None:
    """A lopper strips a leafy log to a log, dropping only leaf extras."""
    game, ids = planted(content)
    tilemap = game.tilemap
    game.inventory.select(3)  # The lopper.
    run(game, 100, use=True, target=(2, 5))
    assert tilemap.get(2, 5) == ids["oak_log"]
    assert tilemap.get(2, 4) == ids["oak_leaf"]  # The crown stays up.
    run(game, 120)
    assert {f.stack.item.name for f in game.floating_items} <= LEAF_LOOT
    assert not any(s and s.item.name == "oak_log" for s in game.inventory)


def test_every_felled_log_drops_where_it_was(content: Content) -> None:
    """Felled logs, leafy ones too, each drop from their own place."""
    game, _ = planted(content)
    chop = TickInput(use=True, target=(2, 7))
    while game.tilemap.get(2, 7) != AIR:
        game.tick(chop)
    logs = [f for f in game.floating_items if f.stack.item.name == "oak_log"]
    places = sorted(round(f.body.center[1] / TILE - 0.5) for f in logs)
    assert len(logs) == LOGS_ABOVE_AND_CHOPPED
    assert places[0] < places[-1]  # From up the tree, not all at the cut.


def test_felled_leaves_drop_their_extras(content: Content) -> None:
    """Chopping a tree down also gives the loot of the leaves that fall."""
    game, _ = planted(content)
    chop = TickInput(use=True, target=(2, 7))
    while game.tilemap.get(2, 7) != AIR:
        game.tick(chop)
    names = {f.stack.item.name for f in game.floating_items}
    assert {"stick", "leaf"} <= names


def test_broken_leaves_drop_branches_and_leaves(content: Content) -> None:
    """Leaves give some sticks and leaves, and rarely a bird's nest."""
    game, ids = planted(content)
    game.inventory.select(3)  # The lopper.
    # Leaves within the player's reach.
    crown = [(-1, 6), (0, 6), (1, 6), (1, 4), (1, 5), (3, 5)]
    for x, y in crown:
        game.tilemap.set(x, y, ids["oak_leaf"])
        run(game, 100, use=True, target=(x, y))
        assert game.tilemap.get(x, y) == AIR
    dropped = [f.stack for f in game.floating_items]
    dropped += [s for s in list(game.inventory)[4:] if s]  # Picked up.
    names = {stack.item.name for stack in dropped}
    assert names
    assert names <= LEAF_LOOT
    for name in LEAF_LOOT - {"oak_sapling"}:
        assert content.items[name].spec.places is None


def test_bird_nest_is_rare(content: Content) -> None:
    """A leaf block holds a small chance of a nest."""
    leaf = content.blocks.by_name("oak_leaf")
    nest = next(d for d in leaf.spec.extra_drops if d.item == "bird_nest")
    assert nest.chance <= MAX_NEST_CHANCE


@pytest.mark.parametrize("name", ["oak_leaf", "oak_log_leaf"])
def test_leaves_can_drop_saplings_and_apples(
    content: Content, name: str
) -> None:
    """Both kinds of leaves have a chance of a sapling and of an apple."""
    block = content.blocks.by_name(name)
    chances = {d.item: d.chance for d in block.spec.extra_drops}
    assert 0 < chances["oak_sapling"] < 1
    assert 0 < chances["apple"] < 1


def test_falling_into_the_void_respawns(game: Game) -> None:
    """A player far below the world returns to spawn with its inventory."""
    body = game.player.body
    spawn = (body.x, body.y)
    items = [s.item.name for s in game.inventory if s]
    body.x = 100 * TILE  # Past the edge of the world.
    fallen = False
    for _ in range(1000):
        game.tick(TickInput())
        if (body.x, body.y) == spawn:
            break
        fallen = fallen or body.y > 14 * TILE
    assert fallen
    assert (body.x, body.y) == spawn
    assert (body.vx, body.vy) == (0, 0)
    assert [s.item.name for s in game.inventory if s] == items


def test_items_vanish_in_the_void(game: Game, content: Content) -> None:
    """An item that falls out of the world is removed."""
    game.drop(ItemStack(content.items["dirt_block"]), (100, 0))
    run(game, 1000)
    assert not game.floating_items


def test_respawns_beside_a_dug_out_spawn_column(game: Game) -> None:
    """With no ground under spawn, a player lands on the nearest column."""
    for y in range(10, 14):
        game.tilemap.set(0, y, AIR)
    body = game.player.body
    body.y = game.void_y + 1
    run(game, 60)
    assert body.y + body.h == 10 * TILE
    assert abs(body.center[0] // TILE) == 1  # Either neighbour.


def hold(game: Game, content: Content, item: str, amount: int = 3) -> None:
    """Put a stack in the fifth slot and hold it."""
    game.inventory.slots[4] = ItemStack(content.items[item], amount)
    game.inventory.select(4)


@pytest.mark.parametrize(
    ("ground", "allowed"),
    [("dirt", True), ("grass", True), ("stone", False), ("oak_log", False)],
)
def test_saplings_are_planted_on_dirt_or_grass(
    game: Game, content: Content, ground: str, *, allowed: bool
) -> None:
    """Only dirt and grass take a sapling."""
    game.tilemap.set(3, 10, content.blocks.id_of(ground))
    hold(game, content, "oak_sapling")
    run(game, 40, place=True, target=(3, 9))
    planted_here = game.tilemap.get(3, 9) == content.blocks.id_of(
        "oak_sapling"
    )
    assert planted_here is allowed
    assert ((3, 9) in game.garden.waiting) is allowed


def test_saplings_need_ground_below(game: Game, content: Content) -> None:
    """Ground beside a sapling is not enough."""
    game.tilemap.set(4, 8, content.blocks.id_of("dirt"))
    hold(game, content, "oak_sapling")
    run(game, 40, place=True, target=(3, 8))
    assert game.tilemap.get(3, 8) == AIR


def test_a_sapling_becomes_a_tree_at_once(
    game: Game, content: Content
) -> None:
    """After its time a sapling is a grown tree, with nothing in between."""
    hold(game, content, "oak_sapling")
    run(game, PLACE_TICKS, place=True, target=(4, 9))
    sapling = content.blocks.by_name("oak_sapling")
    low, high = sapling.spec.grows_after or (0, 0)
    ticks = game.garden.waiting[4, 9]
    assert low * 60 - PLACE_TICKS <= ticks <= high * 60
    run(game, ticks - 1)
    assert game.tilemap.get(4, 9) == sapling.id
    assert game.tilemap.get(4, 4) == AIR
    run(game, 1)
    ids = content.blocks.id_of
    assert game.tilemap.get(4, 9) == ids("oak_log")
    assert game.tilemap.get(4, 4) == ids("oak_log_leaf")
    assert game.tilemap.get(2, 4) == ids("oak_leaf")
    assert game.tilemap.get(4, 2) == ids("oak_leaf")
    assert not game.garden.waiting


def test_a_crowded_sapling_waits_for_room(content: Content) -> None:
    """It stays a sapling until the whole tree fits, also after loading."""
    tilemap = flat_world(content)
    sapling = content.blocks.id_of("oak_sapling")
    tilemap.set(4, 9, sapling)
    tilemap.set(4, 5, content.blocks.id_of("stone"))
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    game.garden.waiting[4, 9] = 1
    run(game, 1)
    assert tilemap.get(4, 9) == sapling
    assert tilemap.get(4, 6) == AIR
    tilemap.set(4, 5, AIR)
    run(game, game.garden.waiting[4, 9])
    assert tilemap.get(4, 9) == content.blocks.id_of("oak_log")


def test_a_sapling_without_ground_drops(game: Game, content: Content) -> None:
    """Digging out the ground uproots the sapling."""
    hold(game, content, "oak_sapling")
    run(game, PLACE_TICKS, place=True, target=(4, 9))
    game.tilemap.set(4, 10, AIR)
    run(game, 1)
    assert game.tilemap.get(4, 9) == AIR
    assert [f.stack.item.name for f in game.floating_items] == ["oak_sapling"]


def test_an_empty_hand_picks_a_sapling_up_at_once(
    game: Game, content: Content
) -> None:
    """One tick of use puts the sapling in the inventory."""
    game.tilemap.set(3, 9, content.blocks.id_of("oak_sapling"))
    game.inventory.select(4)  # Nothing there.
    run(game, 1, use=True, target=(3, 9))
    assert game.tilemap.get(3, 9) == AIR
    assert game.inventory.held is not None
    assert game.inventory.held.item.name == "oak_sapling"
    assert not game.floating_items


def test_an_empty_hand_picks_up_nothing_else(game: Game) -> None:
    """Ordinary blocks need a tool."""
    game.inventory.select(4)
    run(game, 100, use=True, target=(1, 10))
    assert game.tilemap.get(1, 10) != AIR
    assert game.inventory.held is None


@pytest.mark.parametrize(("slot", "breaks"), [(3, True), (1, False)])
def test_the_lopper_is_the_sapling_tool(
    game: Game, content: Content, slot: int, *, breaks: bool
) -> None:
    """A lopper cuts a sapling; an axe does not."""
    game.tilemap.set(3, 9, content.blocks.id_of("oak_sapling"))
    game.inventory.select(slot)
    run(game, 60, use=True, target=(3, 9))
    assert (game.tilemap.get(3, 9) == AIR) is breaks


GRASS_TICKS = 6 * 400
"""Enough ticks for grass to try every column of the flat world."""


def test_grass_spreads_over_open_dirt(content: Content) -> None:
    """Grass covers open dirt beside it, but not dirt under a block."""
    tilemap = flat_world(content)
    grass = content.blocks.id_of("grass")
    dirt = content.blocks.id_of("dirt")
    tilemap.set(0, 10, grass)
    tilemap.set(5, 9, dirt)  # A block sitting on the surface.
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    run(game, GRASS_TICKS * 4)
    assert tilemap.get(1, 10) == grass
    assert tilemap.get(-1, 10) == grass
    assert tilemap.get(0, 11) == dirt  # Not at the surface.
    assert tilemap.get(5, 10) == dirt  # Covered by the block above.
    assert tilemap.get(5, 9) == grass  # The block's top is open to the sky.


def test_grass_needs_a_neighbour(content: Content) -> None:
    """Dirt far from any grass stays dirt."""
    tilemap = flat_world(content)
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    run(game, GRASS_TICKS)
    assert tilemap.get(0, 10) == content.blocks.id_of("dirt")
