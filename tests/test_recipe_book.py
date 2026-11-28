# Copyright (c) 2026 Schunche
"""The recipe book: what recipes need and what the player can make."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.client.recipe_book import (
    RecipeBook,
    can_make,
    entries,
    have,
)
from sch5n.game.inventory import Inventory, ItemStack

if TYPE_CHECKING:
    from sch5n.client.recipe_book import Entry
    from sch5n.game.content import Content

ROW = 48.0


def entry_for(content: Content, item: str) -> Entry:
    """Find the first entry that makes an item.

    Returns:
        Entry: The entry.

    """
    return next(e for e in entries(content) if e.result.name == item)


def test_every_recipe_has_an_entry(content: Content) -> None:
    """Entries cover the recipes, with their ingredient amounts."""
    book = entries(content)
    assert len(book) == len(content.recipes)
    pickaxe = entry_for(content, "stone_pickaxe")
    amounts = {n.choices[0].name: n.amount for n in pickaxe.needs}
    assert amounts == {"cobblestone": 3, "stick": 2}
    assert pickaxe.grid == "3x3"
    planks = next(e for e in book if not e.grid)
    assert planks.needs[0].amount == 1


def test_what_can_be_made(content: Content) -> None:
    """Recipes light up once every ingredient is in the inventory."""
    inventory = Inventory(content.game.inventory.size)
    entry = entry_for(content, "wooden_pickaxe")
    assert not can_make(entry, have(inventory))
    inventory.slots[0] = ItemStack(content.items["oak_planks"], 3)
    inventory.slots[1] = ItemStack(content.items["stick"], 1)
    assert not can_make(entry, have(inventory))
    inventory.slots[2] = ItemStack(content.items["stick"], 1)
    assert can_make(entry, have(inventory))


def test_scrolling_stays_in_bounds(content: Content) -> None:
    """The list scrolls only as far as it has recipes."""
    book = RecipeBook(content)
    book.place(100, 50, (900, 220), ROW)
    assert book.usable
    book.open = True
    assert book.contains((120, 80))
    assert not book.contains((5, 5))
    book.scroll_by(-5)
    assert book.scroll == 0
    book.scroll_by(1000)
    assert book.scroll == book.max_scroll
    book.place(10, 50, (200, 500), ROW)
    assert not book.usable
