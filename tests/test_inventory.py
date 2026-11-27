# Copyright (c) 2026 Schunche
"""Inventory stacking and the click rules of the inventory screen."""

import pytest

from sch5n.game.inventory import HOTBAR_SIZE, Inventory, ItemStack
lazy from sch5n.game.content import ItemRegistry


@pytest.fixture
def inv(items: ItemRegistry) -> Inventory:
    return Inventory(12, [ItemStack(items["pick"])])


def amounts(inv: Inventory) -> list[tuple[str, int] | None]:
    return [None if s is None else (s.item.name, s.amount) for s in inv]


def test_add_tops_up_then_uses_free_slots(
    inv: Inventory, items: ItemRegistry
) -> None:
    assert inv.add(ItemStack(items["rock"], 7)) is None
    assert inv.add(ItemStack(items["rock"], 7)) is None
    assert amounts(inv)[:4] == [("pick", 1), ("rock", 10), ("rock", 4), None]


def test_add_returns_leftover_when_full(items: ItemRegistry) -> None:
    inv = Inventory(HOTBAR_SIZE, [ItemStack(items["pick"]) for _ in range(9)])
    inv.slots[9] = ItemStack(items["rock"], 8)
    leftover = inv.add(ItemStack(items["rock"], 5))
    assert leftover is not None
    assert leftover.amount == 3
    assert inv[9] is not None
    assert inv[9].amount == 10
    assert inv.is_full


def test_tools_never_stack(inv: Inventory, items: ItemRegistry) -> None:
    inv.add(ItemStack(items["pick"]))
    assert amounts(inv)[:2] == [("pick", 1), ("pick", 1)]


def test_hotbar_selection_wraps(inv: Inventory) -> None:
    inv.scroll(-1)
    assert inv.selected == HOTBAR_SIZE - 1
    inv.scroll(2)
    assert inv.selected == 1


def test_held_prefers_cursor(inv: Inventory, items: ItemRegistry) -> None:
    assert inv.held is inv[0]
    inv.cursor = ItemStack(items["rock"])
    assert inv.held is inv.cursor


def test_left_click_picks_up_and_puts_down(inv: Inventory) -> None:
    inv.left_click(0)
    assert inv[0] is None
    assert inv.cursor is not None
    inv.left_click(5)
    assert inv.cursor is None
    assert amounts(inv)[5] == ("pick", 1)


def test_left_click_merges_same_items(
    inv: Inventory, items: ItemRegistry
) -> None:
    inv.slots[1] = ItemStack(items["rock"], 6)
    inv.cursor = ItemStack(items["rock"], 7)
    inv.left_click(1)
    assert amounts(inv)[1] == ("rock", 10)
    assert inv.cursor is not None
    assert inv.cursor.amount == 3


def test_left_click_swaps_different_items(
    inv: Inventory, items: ItemRegistry
) -> None:
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
    inv.slots[1] = ItemStack(items["rock"], amount)
    inv.right_click(1)
    assert amounts(inv)[1] == ("rock", kept)
    assert (inv.cursor.amount if inv.cursor else None) == taken


def test_right_click_places_one(inv: Inventory, items: ItemRegistry) -> None:
    inv.cursor = ItemStack(items["rock"], 2)
    inv.right_click(3)
    inv.right_click(3)
    assert amounts(inv)[3] == ("rock", 2)
    assert inv.cursor is None


def test_right_click_on_full_stack_does_nothing(
    inv: Inventory, items: ItemRegistry
) -> None:
    inv.slots[1] = ItemStack(items["rock"], 10)
    inv.cursor = ItemStack(items["rock"], 2)
    inv.right_click(1)
    assert amounts(inv)[1] == ("rock", 10)
    assert inv.cursor.amount == 2


def test_right_click_swaps_unstackables(
    inv: Inventory, items: ItemRegistry
) -> None:
    inv.cursor = ItemStack(items["rock"], 2)
    inv.right_click(0)
    assert amounts(inv)[0] == ("rock", 2)
    assert inv.cursor is not None
    assert inv.cursor.item.name == "pick"


def test_consume_held(inv: Inventory, items: ItemRegistry) -> None:
    inv.slots[0] = ItemStack(items["rock"], 2)
    inv.consume_held()
    inv.consume_held()
    assert inv[0] is None
