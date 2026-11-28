# Copyright (c) 2026 Schunche
"""Laying recipes out in the crafting grid from the recipe book."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.crafting import crafted, fill_recipe
from sch5n.game.inventory import Inventory, ItemStack

if TYPE_CHECKING:
    from sch5n.game.content import Content

SLOTS = 40
FIVE = 5


def recipe_index(content: Content, item: str) -> int:
    """Find the recipe that makes an item.

    Returns:
        int: Its index.

    """
    return next(
        i for i, r in enumerate(content.recipes) if r.result.item == item
    )


def test_a_recipe_is_laid_out_and_craftable(content: Content) -> None:
    """One set goes into the grid; the rest stays in the inventory."""
    inventory = Inventory(SLOTS)
    inventory.add(ItemStack(content.items["oak_log"], FIVE))
    index = recipe_index(content, "oak_planks")
    assert fill_recipe(inventory, content, index)
    result = crafted(inventory, content)
    assert result is not None
    assert result.item.name == "oak_planks"
    held = sum(s.amount for s in inventory.slots if s)
    assert held == FIVE - 1


def test_maximum_fills_every_slot_with_the_most_sets(
    content: Content,
) -> None:
    """Shift fills the grid with all the sets the inventory can give."""
    inventory = Inventory(SLOTS)
    inventory.add(ItemStack(content.items["oak_log"], FIVE))
    assert fill_recipe(
        inventory, content, recipe_index(content, "oak_planks"), maximum=True
    )
    used = [s for s in inventory.crafting if s]
    assert [s.amount for s in used] == [FIVE]
    assert not any(inventory.slots)


def test_a_missing_ingredient_changes_nothing(content: Content) -> None:
    """Without the items, or with the grid too small, nothing moves."""
    inventory = Inventory(SLOTS)
    inventory.add(ItemStack(content.items["stick"], 1))
    inventory.crafting[0] = ItemStack(content.items["oak_log"])
    index = recipe_index(content, "iron_pickaxe")
    assert not fill_recipe(inventory, content, index)
    assert inventory.crafting[0] is not None
    assert not fill_recipe(inventory, content, -1)
