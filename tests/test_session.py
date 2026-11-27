# Copyright (c) 2026 Schunche
"""A whole game session, with the real game data."""

import pytest

from sch5n.game.config import GameMode
from sch5n.game.content import AIR, Content
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, TickInput
from sch5n.math.rect import Rect
from sch5n.world.tilemap import TileMap


def flat_world(content: Content) -> TileMap:
    tilemap = TileMap(content.blocks)
    dirt = content.blocks.id_of("dirt")
    for x in range(-30, 30):
        for y in range(10, 14):
            tilemap.set(x, y, dirt)
    return tilemap


@pytest.fixture
def game(content: Content) -> Game:
    return Game(
        content,
        flat_world(content),
        mode=GameMode.SURVIVAL,
        seed=1,
        spawn=(0, 0),
    )


def run(game: Game, ticks: int, **kwargs: object) -> None:
    for _ in range(ticks):
        game.tick(TickInput(**kwargs))  # type: ignore[arg-type]


def test_spawns_on_the_ground(game: Game) -> None:
    body = game.player.body
    assert body.y + body.h == 10 * 32
    run(game, 30)
    assert body.y + body.h == 10 * 32


def test_starting_items(game: Game) -> None:
    assert [s.item.name for s in game.inventory if s] == [
        "copper_pickaxe",
        "copper_axe",
    ]


def test_mine_drop_and_pick_up(game: Game) -> None:
    target = (1, 10)
    run(game, 200, use=True, target=target)
    assert game.tilemap.get(*target) == AIR
    run(game, 300)
    assert not game.floating_items
    stacks = [s for s in game.inventory if s and s.item.name == "dirt_block"]
    assert sum(s.amount for s in stacks) >= 1


def test_cannot_mine_through_gui(game: Game) -> None:
    run(game, 200, use=True, target=None)
    assert game.tilemap.get(1, 10) != AIR


def test_place_block(game: Game, content: Content) -> None:
    game.inventory.slots[2] = ItemStack(content.items["dirt_block"], 3)
    game.inventory.select(2)
    run(game, 40, place=True, target=(5, 9))
    assert game.tilemap.get(5, 9) == content.blocks.id_of("dirt")
    assert game.inventory[2] is not None
    assert game.inventory[2].amount == 2


def test_cannot_place_inside_player(game: Game, content: Content) -> None:
    game.inventory.slots[2] = ItemStack(content.items["dirt_block"], 3)
    game.inventory.select(2)
    body = game.player.body
    tile = (int(body.center[0] // 32), int(body.center[1] // 32))
    run(game, 40, place=True, target=tile)
    assert game.tilemap.get(*tile) == AIR


def test_jump(game: Game) -> None:
    y0 = game.player.body.y
    game.tick(TickInput(jump=True))
    run(game, 10)
    assert game.player.body.y < y0


def test_leaves_emit_particles_deterministically(content: Content) -> None:
    def particles(seed: int) -> list[tuple[float, float]]:
        tilemap = flat_world(content)
        leaf = content.blocks.id_of("oak_leaf")
        for x in range(10):
            for y in range(5):
                tilemap.set(x, y, leaf)
        game = Game(content, tilemap, seed=seed, spawn=(-500, 0))
        run(game, 300, view=Rect(-100, -100, 1000, 1000))
        return [(p.x, p.y) for p in game.ambience.particles]

    first = particles(5)
    assert first
    assert first == particles(5)
    assert first != particles(6)
