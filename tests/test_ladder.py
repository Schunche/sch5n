# Copyright (c) 2026 Schunche
"""Ladders: crafting, placing and climbing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.crafting import crafted
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.mining import can_place
from sch5n.game.session import Game, GameSetup, TickInput
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

TILE = 32
SLOTS = 40
THREE = 3
SEVEN = 7
CLIMB_TICKS = 40


def test_seven_sticks_in_an_h_make_three_ladders(content: Content) -> None:
    """The H pattern gives three."""
    inventory = Inventory(SLOTS)
    inventory.resize_crafting(THREE)
    stick = content.items["stick"]
    for index in (0, 2, 3, 4, 5, 6, 8):
        inventory.crafting[index] = ItemStack(stick)
    result = crafted(inventory, content)
    assert result is not None
    assert (result.item.name, result.amount) == ("ladder", THREE)
    assert sum(s is not None for s in inventory.crafting) == SEVEN
    inventory.crafting[4] = None
    assert crafted(inventory, content) is None


def test_ladders_hang_from_each_other(content: Content) -> None:
    """A ladder can be placed against a wall or another ladder."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    ladder = content.blocks.by_name("ladder")
    assert not can_place(game.tilemap, 5, 3, ladder)
    game.tilemap.set(5, 4, content.blocks.id_of("ladder"))
    assert can_place(game.tilemap, 5, 3, ladder)


def test_the_player_climbs_while_jump_is_held(content: Content) -> None:
    """Holding jump in a ladder rises; letting go slides down slowly."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    game.tick(TickInput())
    player = game.player
    column = int(player.body.center[0] // TILE)
    ladder = content.blocks.id_of("ladder")
    for row in range(-30, 10):
        game.tilemap.set(column, row, ladder)
    start = player.body.y
    for _ in range(CLIMB_TICKS):
        game.tick(TickInput(jump_held=True))
    assert player.body.y < start - 2 * TILE
    assert player.on_ladder
    high = player.body.y
    health = player.vitals.health
    for _ in range(CLIMB_TICKS):
        game.tick(TickInput())
    assert high < player.body.y < high + CLIMB_TICKS * 2
    assert player.vitals.health == health
