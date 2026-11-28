# Copyright (c) 2026 Schunche
"""Cooking food."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.crafting import crafted
from sch5n.game.inventory import Inventory, ItemStack

if TYPE_CHECKING:
    from sch5n.game.content import Content

SLOTS = 40


def test_a_baked_apple_needs_a_furnace_and_feeds_more(
    content: Content,
) -> None:
    """Apple and a stick bake into a better meal, next to a furnace."""
    apple, baked = content.items["apple"], content.items["baked_apple"]
    assert baked.spec.food > apple.spec.food
    inventory = Inventory(SLOTS)
    inventory.crafting[0] = ItemStack(apple)
    inventory.crafting[1] = ItemStack(content.items["stick"])
    assert crafted(inventory, content) is None
    inventory.stations = frozenset({"furnace"})
    result = crafted(inventory, content)
    assert result is not None
    assert result.item.name == "baked_apple"
