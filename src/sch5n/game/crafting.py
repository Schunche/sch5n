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
        (
            r
            for r in content.recipes
            if (r.station is None or r.station in inventory.stations)
            and _matches(r, shape, content)
        ),
        None,
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


def _layout(
    recipe: RecipeSpec, side: int
) -> list[tuple[int, tuple[str, ...]]] | None:
    """Place a recipe in a grid of `side`, from its top left corner.

    Returns:
        list[tuple[int, tuple[str, ...]]] | None: Grid slot and accepted
        item names of each ingredient, or `None` if it does not fit.

    """
    if recipe.pattern:
        if len(recipe.pattern) > side or len(recipe.pattern[0]) > side:
            return None
        return [
            (row * side + column, recipe.choices(symbol))
            for row, line in enumerate(recipe.pattern)
            for column, symbol in enumerate(line)
            if symbol != " "
        ]
    if len(recipe.ingredients) > side**2:
        return None
    return [(i, (name,)) for i, name in enumerate(recipe.ingredients)]


def _available(inventory: Inventory) -> dict[str, int]:
    totals: dict[str, int] = {}
    for stack in inventory.slots:
        if stack is not None:
            name = stack.item.name
            totals[name] = totals.get(name, 0) + stack.amount
    return totals


def _take(inventory: Inventory, name: str, amount: int) -> None:
    for index, stack in enumerate(inventory.slots):
        if amount <= 0:
            return
        if stack is not None and stack.item.name == name:
            used = min(amount, stack.amount)
            stack.amount -= used
            amount -= used
            if stack.amount <= 0:
                inventory.slots[index] = None


def _choose(
    layout: list[tuple[int, tuple[str, ...]]], have: dict[str, int]
) -> tuple[list[tuple[int, str]], dict[str, int]] | None:
    """Pick an item for every slot of a layout from what is held.

    Returns:
        tuple | None: The item of each slot and how many of each item one
        set takes, or `None` if something is missing.

    """
    chosen: list[tuple[int, str]] = []
    need: dict[str, int] = {}
    for slot, names in layout:
        name = next((n for n in names if have.get(n, 0) > need.get(n, 0)), "")
        if not name:
            return None
        chosen.append((slot, name))
        need[name] = need.get(name, 0) + 1
    return chosen, need


def fill_recipe(
    inventory: Inventory,
    content: Content,
    index: int,
    *,
    maximum: bool = False,
) -> bool:
    """Lay the ingredients of recipe `index` out in the crafting grid.

    The grid is cleared into the inventory first. One set is laid out, or
    as many as the inventory holds with `maximum`. Nothing changes if the
    recipe does not fit the grid, needs a station out of reach, or the
    inventory lacks the items.

    Returns:
        bool: Whether the grid now holds the recipe.

    """
    if not 0 <= index < len(content.recipes):
        return False
    recipe = content.recipes[index]
    if recipe.station and recipe.station not in inventory.stations:
        return False
    layout = _layout(recipe, inventory.crafting_side)
    if layout is None:
        return False
    before = inventory.copy()
    for slot in range(len(inventory.crafting)):
        inventory.stow_crafting(slot)
    if any(stack is not None for stack in inventory.crafting):
        _restore(inventory, before)
        return False
    have = _available(inventory)
    picked = _choose(layout, have)
    if picked is None:
        _restore(inventory, before)
        return False
    chosen, need = picked
    sets = min(have[name] // count for name, count in need.items())
    if maximum:
        sets = min(
            sets, *(content.items[name].spec.max_stack for name in need)
        )
    else:
        sets = 1
    for name, count in need.items():
        _take(inventory, name, count * sets)
    for slot, name in chosen:
        inventory.crafting[slot] = ItemStack(content.items[name], sets)
    return True


def _restore(inventory: Inventory, before: Inventory) -> None:
    inventory.slots[:] = before.slots
    inventory.crafting[:] = before.crafting
