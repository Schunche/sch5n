# Copyright (c) 2026 Schunche
"""Tests for armor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.crafting import crafted
from sch5n.game.inventory import (
    ARMOR_PARTS,
    HOTBAR_SIZE,
    Inventory,
    ItemStack,
)
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.net.protocol import InventoryAction
from sch5n.world.save import inventory_from_json, inventory_to_json
from tests.test_mobs import SLIME, add_slime, make_game
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

HEAD, CHEST, LEGS = range(3)
IRON_DEFENSE = 7


def stack(content: Content, name: str, amount: int = 1) -> ItemStack:
    """Make a stack of an item.

    Returns:
        ItemStack: The stack.

    """
    return ItemStack(content.items[name], amount)


def test_armor_goes_only_into_its_own_slot(content: Content) -> None:
    """A helmet fits the head slot; the cursor keeps it elsewhere."""
    inventory = Inventory(10)
    inventory.cursor = stack(content, "iron_helmet")
    inventory.armor_click(CHEST)
    assert inventory.armor[CHEST] is None
    assert inventory.cursor is not None
    inventory.armor_click(HEAD)
    assert inventory.armor[HEAD] is not None
    assert inventory.cursor is None
    inventory.armor_click(HEAD)
    assert inventory.armor[HEAD] is None
    assert inventory.cursor is not None


def test_other_items_are_not_worn(content: Content) -> None:
    """A stick does not go into an armor slot."""
    inventory = Inventory(10)
    inventory.cursor = stack(content, "stick")
    for index in range(len(ARMOR_PARTS)):
        inventory.armor_click(index)
    assert not any(inventory.armor)


def test_defense_softens_damage(content: Content) -> None:
    """The more is worn, the less a blow takes, but never below one."""
    inventory = Inventory(10)
    assert inventory.soften(3) == 3  # ruff: ignore[magic-value-comparison]
    for index, name in enumerate((
        "iron_helmet",
        "iron_chestplate",
        "iron_leggings",
    )):
        inventory.armor[index] = stack(content, name)
    assert inventory.defense == IRON_DEFENSE
    assert inventory.soften(3) == 2  # ruff: ignore[magic-value-comparison]
    assert inventory.soften(1) == 1


def test_armor_protects_in_the_game(content: Content) -> None:
    """A slime's touch hurts less in armor."""
    game: Game = make_game(content)
    for index, name in enumerate((
        "iron_helmet",
        "iron_chestplate",
        "iron_leggings",
    )):
        game.player.inventory.armor[index] = stack(content, name)
    add_slime(game, game.player.body.x)
    before = game.player.vitals.health
    game.tick(TickInput())
    taken = before - game.player.vitals.health
    assert 0 < taken < SLIME.damage


def test_armor_is_saved(content: Content) -> None:
    """Worn armor comes back with the inventory."""
    inventory = Inventory(10)
    inventory.armor[LEGS] = stack(content, "copper_leggings")
    data = inventory_to_json(inventory)
    again = inventory_from_json(data, content.items, 10)
    worn = again.armor[LEGS]
    assert worn is not None
    assert worn.item.name == "copper_leggings"
    # A piece in the wrong slot is not worn.
    data["armor"] = [["copper_leggings", 1], None, None]
    wrong = inventory_from_json(data, content.items, 10)
    assert not any(wrong.armor)


def test_armor_is_crafted(content: Content) -> None:
    """Cloth makes a cap; iron ingots make a chestplate."""
    inventory = Inventory(10)
    inventory.crafting = [None] * 9
    for index in (0, 1, 2, 3, 5):
        inventory.crafting[index] = stack(content, "cloth")
    result = crafted(inventory, content)
    assert result is not None
    assert result.item.name == "cloth_cap"


def test_armor_goes_through_the_server(content: Content) -> None:
    """The server wears armor for a client and tells it."""
    from sch5n.server.server import Server  # ruff: ignore[import-outside-top-level]
    from tests.test_server import join, step  # ruff: ignore[import-outside-top-level]

    server = Server(
        content, flat_world(content), GameSetup(seed=1, spawn=(0, 0))
    )
    alice = join(server, content)
    assert alice.world is not None
    player = next(iter(server.game.players.values()))
    player.inventory.cursor = stack(content, "iron_helmet")
    alice.inventory(InventoryAction.ARMOR_CLICK, HEAD)
    step(server, [alice], 2)
    assert player.inventory.armor[HEAD] is not None
    mine = alice.world.inventory.armor[HEAD]
    assert mine is not None
    assert mine.item.name == "iron_helmet"


def test_the_bed_is_saved(content: Content) -> None:
    """A set spawn point comes back with the inventory."""
    inventory = Inventory(10)
    inventory.home = (4, 7)
    again = inventory_from_json(
        inventory_to_json(inventory), content.items, 10
    )
    assert again.home == (4, 7)


def test_quick_move_swaps_between_hotbar_and_the_rest(
    content: Content,
) -> None:
    """A shift click sends a stack to the other part of the inventory."""
    inventory = Inventory(30)
    inventory.slots[0] = ItemStack(content.items["stick"], 5)
    inventory.slots[HOTBAR_SIZE + 3] = ItemStack(content.items["stick"], 4)
    inventory.quick_move(0)
    assert inventory[0] is None
    moved = inventory[HOTBAR_SIZE + 3]
    assert moved is not None
    assert moved.amount == 9  # ruff: ignore[magic-value-comparison]
    inventory.quick_move(HOTBAR_SIZE + 3)
    assert inventory[HOTBAR_SIZE + 3] is None
    assert inventory[0] is not None


def test_quick_move_wears_armor_and_fills_chests(content: Content) -> None:
    """Armor goes on if its place is free; a chest takes anything."""
    inventory = Inventory(30)
    inventory.slots[HOTBAR_SIZE] = ItemStack(content.items["iron_helmet"])
    inventory.quick_move(HOTBAR_SIZE)
    assert inventory.armor[0] is not None
    assert inventory[HOTBAR_SIZE] is None
    inventory.slots[1] = ItemStack(content.items["stick"], 3)
    chest = Inventory(27)
    inventory.quick_move(1, chest)
    assert inventory[1] is None
    taken = chest[0]
    assert taken is not None
    assert taken.amount == 3  # ruff: ignore[magic-value-comparison]
    inventory.take_from(chest, 0)
    assert chest[0] is None
    assert inventory[0] is not None
    inventory.quick_move(99)
    inventory.take_from(chest, 99)


def test_shift_click_through_the_server(content: Content) -> None:
    """The server moves stacks for shift clicks, in the inventory and chest."""
    from sch5n.server.server import Server  # ruff: ignore[import-outside-top-level]
    from tests.test_server import join, step  # ruff: ignore[import-outside-top-level]

    server = Server(
        content, flat_world(content), GameSetup(seed=1, spawn=(0, 0))
    )
    alice = join(server, content)
    player = next(iter(server.game.players.values()))
    player.inventory.slots[HOTBAR_SIZE] = stack(content, "copper_helmet")
    alice.inventory(InventoryAction.QUICK_MOVE, HOTBAR_SIZE)
    step(server, [alice], 2)
    assert player.inventory.armor[HEAD] is not None
    server.game.tilemap.set(1, 9, content.blocks.id_of("chest"))
    player.inventory.slots[1] = stack(content, "stick", 4)
    alice.open_chest(1, 9)
    step(server, [alice], 2)
    alice.inventory(InventoryAction.QUICK_MOVE, 1)
    step(server, [alice], 2)
    chest = server.game.chest_at(1, 9)
    assert chest is not None
    assert chest[0] is not None
    alice.click_chest(0, quick=True)
    step(server, [alice], 2)
    assert chest[0] is None
    assert player.inventory[1] is not None
