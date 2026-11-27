# Copyright (c) 2026 Schunche
"""Making items from the ones in the crafting grid."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from sch5n.game.inventory import ItemStack

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sch5n.game.content import Content, RecipeSpec
    from sch5n.game.inventory import Inventory


type Shape[T] = tuple[tuple[T | None, ...], ...]
"""Rows of slots, without empty rows or columns around them."""


def _trim[T](rows: Sequence[Sequence[T | None]]) -> Shape[T]:
    filled = [
        (y, x)
        for y, row in enumerate(rows)
        for x, cell in enumerate(row)
        if cell is not None
    ]
    if not filled:
        return ()
    ys, xs = zip(*filled, strict=True)
    return tuple(
        tuple(rows[y][min(xs) : max(xs) + 1])
        for y in range(min(ys), max(ys) + 1)
    )


def _fits(wanted: frozenset[str] | None, offered: str | None) -> bool:
    return offered is None if wanted is None else offered in wanted


def _matches(recipe: RecipeSpec, shape: Shape[str], content: Content) -> bool:
    items = content.items
    if recipe.pattern:
        wanted = _trim([
            [
                None
                if c == " "
                else frozenset(items[n].name for n in recipe.choices(c))
                for c in row
            ]
            for row in recipe.pattern
        ])
        return len(wanted) == len(shape) and all(
            len(want) == len(have) and all(map(_fits, want, have, strict=True))
            for want, have in zip(wanted, shape, strict=True)
        )
    offered = Counter(name for row in shape for name in row if name)
    return offered == Counter(items[name].name for name in recipe.ingredients)


def find_recipe(inventory: Inventory, content: Content) -> RecipeSpec | None:
    """Find the recipe the crafting grid matches.

    No slot may be left over. See `RecipeSpec` for the two kinds.

    Returns:
        RecipeSpec | None: The recipe, if any.

    """
    side = inventory.crafting_side
    names = [None if s is None else s.item.name for s in inventory.crafting]
    shape = _trim([names[y * side : (y + 1) * side] for y in range(side)])
    return next(
        (r for r in content.recipes if _matches(r, shape, content)), None
    )


def crafted(inventory: Inventory, content: Content) -> ItemStack | None:
    """Work out what the crafting grid would make.

    Returns:
        ItemStack | None: The result, `None` if nothing matches.

    """
    recipe = find_recipe(inventory, content)
    if recipe is None:
        return None
    result = recipe.result
    return ItemStack(content.items[result.item], result.amount)


def _use_ingredients(inventory: Inventory) -> None:
    for index, stack in enumerate(inventory.crafting):
        if stack is not None:
            stack.amount -= 1
            if stack.amount <= 0:
                inventory.crafting[index] = None


def craft(inventory: Inventory, content: Content) -> bool:
    """Craft once onto the cursor, using up one of each ingredient.

    Nothing happens if the cursor cannot take the whole result.

    Returns:
        bool: Whether something was made.

    """
    result = crafted(inventory, content)
    if result is None:
        return False
    cursor = inventory.cursor
    if cursor is None:
        inventory.cursor = result
    elif cursor.can_merge(result) and cursor.room >= result.amount:
        cursor.amount += result.amount
    else:
        return False
    _use_ingredients(inventory)
    return True


def craft_all(inventory: Inventory, content: Content) -> None:
    """Craft into the inventory until ingredients or room run out.

    It stops as well when what is left in the grid makes something else.
    The cursor is left alone.
    """
    first = crafted(inventory, content)
    result = first
    while (
        first is not None
        and result is not None
        and result.item is first.item
        and inventory.room_for(result.item) >= result.amount
    ):
        _use_ingredients(inventory)
        inventory.add(result)
        result = crafted(inventory, content)
