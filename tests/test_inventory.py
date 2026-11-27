# Copyright (c) 2026 Schunche
"""Inventory stacking and the click rules of the inventory screen."""

import pytest

from sch5n.game.inventory import HOTBAR_SIZE, Inventory, ItemStack
lazy from sch5n.game.content import ItemRegistry

ROCK_STACK = 10
"""`max_stack` of the rock item in `conftest.py`."""


@pytest.fixture
def inv(items: ItemRegistry) -> Inventory:
    """Create an inventory holding a pickaxe in the first slot.

    Returns:
        Inventory: A 12 slot inventory.

    """
    return Inventory(12, [ItemStack(items["pick"])])


def amounts(inv: Inventory) -> list[tuple[str, int] | None]:
    """Summarize slots as item names and amounts.

    Returns:
        list[tuple[str, int] | None]: One entry per slot.

    """
    return [None if s is None else (s.item.name, s.amount) for s in inv]


def test_add_tops_up_then_uses_free_slots(
    inv: Inventory, items: ItemRegistry
) -> None:
    """Adding fills existing stacks before taking empty slots."""
    assert inv.add(ItemStack(items["rock"], 7)) is None
    assert inv.add(ItemStack(items["rock"], 7)) is None
    assert amounts(inv)[:4] == [("pick", 1), ("rock", 10), ("rock", 4), None]


def test_add_returns_leftover_when_full(items: ItemRegistry) -> None:
    """What does not fit is handed back."""
    last = HOTBAR_SIZE - 1
    inv = Inventory(
        HOTBAR_SIZE, [ItemStack(items["pick"]) for _ in range(last)]
    )
    inv.slots[last] = ItemStack(items["rock"], ROCK_STACK - 2)
    leftover = inv.add(ItemStack(items["rock"], 5))
    assert leftover is not None
    assert leftover.amount == 5 - 2
    assert inv[last] is not None
    assert inv[last].amount == ROCK_STACK
    assert inv.is_full


def test_tools_never_stack(inv: Inventory, items: ItemRegistry) -> None:
    """Unstackable items always take their own slot."""
    inv.add(ItemStack(items["pick"]))
    assert amounts(inv)[:2] == [("pick", 1), ("pick", 1)]


def test_hotbar_selection_wraps(inv: Inventory) -> None:
    """Scrolling past either end of the hotbar wraps around."""
    inv.scroll(-1)
    assert inv.selected == HOTBAR_SIZE - 1
    inv.scroll(2)
    assert inv.selected == 1


def test_held_prefers_cursor(inv: Inventory, items: ItemRegistry) -> None:
    """The stack on the cursor is used before the selected slot."""
    assert inv.held is inv[0]
    inv.cursor = ItemStack(items["rock"])
    assert inv.held is inv.cursor


def test_left_click_picks_up_and_puts_down(inv: Inventory) -> None:
    """Left click moves a stack between a slot and the cursor."""
    inv.left_click(0)
    assert inv[0] is None
    assert inv.cursor is not None
    inv.left_click(5)
    assert inv.cursor is None
    assert amounts(inv)[5] == ("pick", 1)


def test_left_click_merges_same_items(
    inv: Inventory, items: ItemRegistry
) -> None:
    """Left click tops up a stack of the same item."""
    inv.slots[1] = ItemStack(items["rock"], 6)
    inv.cursor = ItemStack(items["rock"], 7)
    inv.left_click(1)
    assert amounts(inv)[1] == ("rock", ROCK_STACK)
    assert inv.cursor is not None
    assert inv.cursor.amount == 6 + 7 - ROCK_STACK


def test_left_click_swaps_different_items(
    inv: Inventory, items: ItemRegistry
) -> None:
    """Left click swaps different items."""
    inv.cursor = ItemStack(items["rock"], 2)
    inv.left_click(0)
    assert amounts(inv)[0] == ("rock", 2)
    assert inv.cursor is not None
    assert inv.cursor.item.name == "pick"


@pytest.mark.parametrize(
    ("amount", "kept", "taken"), [(7, 4, 3), (8, 4, 4), (1, 1, None)]
)
def test_right_click_takes_half(
    inv: Inventory,
    items: ItemRegistry,
    amount: int,
    kept: int,
    taken: int | None,
) -> None:
    """Right click on a stack takes the smaller half."""
    inv.slots[1] = ItemStack(items["rock"], amount)
    inv.right_click(1)
    assert amounts(inv)[1] == ("rock", kept)
    assert (inv.cursor.amount if inv.cursor else None) == taken


def test_right_click_places_one(inv: Inventory, items: ItemRegistry) -> None:
    """Right click with a stack puts down a single item."""
    inv.cursor = ItemStack(items["rock"], 2)
    inv.right_click(3)
    inv.right_click(3)
    assert amounts(inv)[3] == ("rock", 2)
    assert inv.cursor is None


def test_right_click_on_full_stack_does_nothing(
    inv: Inventory, items: ItemRegistry
) -> None:
    """A full stack accepts nothing more."""
    inv.slots[1] = ItemStack(items["rock"], ROCK_STACK)
    held = 2
    inv.cursor = ItemStack(items["rock"], held)
    inv.right_click(1)
    assert amounts(inv)[1] == ("rock", ROCK_STACK)
    assert inv.cursor.amount == held


def test_right_click_swaps_unstackables(
    inv: Inventory, items: ItemRegistry
) -> None:
    """Right click swaps when either side cannot stack."""
    inv.cursor = ItemStack(items["rock"], 2)
    inv.right_click(0)
    assert amounts(inv)[0] == ("rock", 2)
    assert inv.cursor is not None
    assert inv.cursor.item.name == "pick"


def test_consume_held(inv: Inventory, items: ItemRegistry) -> None:
    """Using up the held stack empties its slot."""
    inv.slots[0] = ItemStack(items["rock"], 2)
    inv.consume_held()
    inv.consume_held()
    assert inv[0] is None
