# Copyright (c) 2026 Schunche
"""Grass: tall grass drops, planting, and dying under blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.inventory import ItemStack
from sch5n.game.mining import can_place
from sch5n.game.plants import SMOTHER_SECONDS
from sch5n.game.session import Game, GameSetup, TickInput
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

SEEDS = 40


def make(content: Content) -> Game:
    """Start a game on flat ground.

    Returns:
        Game: The game.

    """
    return Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))


def test_tall_grass_grows_on_dirt_and_grass_only(content: Content) -> None:
    """Plantable on dirt or grass, not stone; walk through."""
    game = make(content)
    plant = content.blocks.by_name("tall_grass")
    assert not plant.spec.solid
    tiles = game.tilemap
    tiles.set(5, 10, content.blocks.id_of("grass"))
    tiles.set(6, 10, content.blocks.id_of("dirt"))
    tiles.set(7, 10, content.blocks.id_of("stone"))
    assert can_place(tiles, 5, 9, plant)
    assert can_place(tiles, 6, 9, plant)
    assert not can_place(tiles, 7, 9, plant)


def test_breaking_grass_sometimes_drops_tall_grass(content: Content) -> None:
    """The grass block lists tall grass as a chance drop."""
    grass = content.blocks.by_name("grass")
    drops = {d.item: d.chance for d in grass.spec.extra_drops}
    assert 0 < drops["tall_grass"] < 1
    assert "tall_grass" in content.items


def test_grass_under_a_placed_block_turns_to_dirt(content: Content) -> None:
    """After a while, grass with something solid on top becomes dirt."""
    game = make(content)
    tiles = game.tilemap
    grass = content.blocks.id_of("grass")
    stone = content.blocks.id_of("stone")
    tiles.set(5, 10, grass)
    tiles.set(5, 9, stone)
    game.garden.plant(5, 9)
    assert (5, 10) in game.garden.smothering
    assert game.garden.smothering[5, 10] <= round(
        SMOTHER_SECONDS[1] * game.config.tick_rate
    )
    for _ in range(round(SMOTHER_SECONDS[1] * game.config.tick_rate) + 5):
        game.tick(TickInput())
    assert tiles.get(5, 10) == content.blocks.id_of("dirt")


def test_grass_survives_if_the_cover_is_removed(content: Content) -> None:
    """Taking the block away in time saves the grass; plants do not hurt."""
    game = make(content)
    tiles = game.tilemap
    grass = content.blocks.id_of("grass")
    tiles.set(5, 10, grass)
    tiles.set(5, 9, content.blocks.id_of("stone"))
    game.garden.plant(5, 9)
    tiles.set(5, 9, content.blocks.id_of("tall_grass"))
    for _ in range(round(SMOTHER_SECONDS[1] * game.config.tick_rate) + 5):
        game.tick(TickInput())
    assert tiles.get(5, 10) == grass
    assert ItemStack(content.items["tall_grass"]).amount == 1
