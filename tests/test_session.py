# Copyright (c) 2026 Schunche
"""A whole game session, with the real game data."""

import pytest

from sch5n.game.config import GameMode
from sch5n.game.content import AIR, Content
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.math.rect import Rect
from sch5n.world.tilemap import TileMap


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
        "copper_pickaxe",
        "copper_axe",
        "iron_shovel",
        "copper_lopper",
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


def test_stone_drops_a_stone_block(game: Game, content: Content) -> None:
    """Mined stone can be picked up and placed again."""
    target = (2, 10)
    game.tilemap.set(*target, content.blocks.id_of("stone"))
    run(game, 300, use=True, target=target)
    assert game.tilemap.get(*target) == AIR
    run(game, 300)
    stones = [s for s in game.inventory if s and s.item.name == "stone_block"]
    assert sum(s.amount for s in stones) == 1
    assert stones[0].item.spec.places == "stone"


TILE = 32
LOGS_ABOVE_AND_CHOPPED = 3
"""The chopped log, the log above it and the leafy log on top."""
MIN_LOG_HITS = 8
MIN_JUMP_TILES = 2.1
"""A held jump must clear a two block step."""
MAX_JUMP_TILES = 2.6
MAX_WALK_TILES_PER_SECOND = 5.0


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
    axe = content.items["copper_axe"]
    log = content.blocks.by_name("oak_log")
    hits = -(-log.durability // axe.spec.tool_power["axe"])
    assert hits >= MIN_LOG_HITS
    run(game, (hits - 1) * axe.spec.use_time, use=True, target=(2, 7))
    assert game.tilemap.get(2, 7) != AIR
