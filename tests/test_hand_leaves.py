# Copyright (c) 2026 Schunche
"""Starting from nothing: leaves break by hand and give sticks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.crafting import crafted
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

STICKS = 4
TICKS = 300
LEAVES = 40


def test_hands_break_leaves_and_the_sticks_make_planks(
    content: Content,
) -> None:
    """Leaves by hand, then sticks, then planks: progress from nothing."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    game.tick(TickInput())
    leaf = content.blocks.id_of("oak_leaf")
    air = 0
    inventory = game.player.inventory
    for index in range(len(inventory)):
        inventory.slots[index] = None
    player_x = int(game.player.body.center[0] // 32)
    row = int(game.player.body.y // 32)

    def sticks() -> int:
        return sum(
            s.amount
            for s in game.player.inventory
            if s and s.item.name == "stick"
        )

    for column in range(LEAVES):
        x = player_x + column % 3 - 1
        y = row - 1 - column // 3
        game.tilemap.set(x, y, leaf)
        for _ in range(TICKS):
            game.tick(TickInput(use=True, target=(x, y)))
            if game.tilemap.get(x, y) == air:
                break
        assert game.tilemap.get(x, y) == air
        for _ in range(60):
            game.tick(TickInput())
        if sticks() >= STICKS:
            break
    assert sticks() >= STICKS
    crafting = Inventory(40)
    crafting.resize_crafting(2)
    stick = content.items["stick"]
    for index in range(STICKS):
        crafting.crafting[index] = ItemStack(stick)
    result = crafted(crafting, content)
    assert result is not None
    assert result.item.name == "oak_planks"
