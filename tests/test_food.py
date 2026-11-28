# Copyright (c) 2026 Schunche
"""Cooking and smelting in a furnace."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.game.smelting import FUEL, INPUT, OUTPUT, Furnace, tick_furnace
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

RATE = 60
THREE = 3


def furnace_slots(
    content: Content, ore: str, fuel: str, amount: int = 1
) -> Inventory:
    """Fill a furnace with ore and fuel.

    Returns:
        Inventory: The three slots.

    """
    slots = Inventory(THREE)
    slots.slots[INPUT] = ItemStack(content.items[ore], amount)
    slots.slots[FUEL] = ItemStack(content.items[fuel])
    return slots


def run(
    content: Content,
    slots: Inventory,
    seconds: float,
    fire: Furnace | None = None,
) -> Furnace:
    """Let a furnace work.

    Returns:
        Furnace: Its fire.

    """
    fire = fire or Furnace()
    for _ in range(round(seconds * RATE)):
        tick_furnace(fire, slots, content, RATE)
    return fire


def test_a_baked_apple_feeds_more_than_an_apple(content: Content) -> None:
    """The cooked fruit restores more hunger."""
    apple, baked = content.items["apple"], content.items["baked_apple"]
    assert baked.spec.food > apple.spec.food
    assert content.smelting["apple"].result.item == "baked_apple"


def test_ore_and_fuel_make_an_ingot_over_time(content: Content) -> None:
    """After its smelting time the ore is gone and an ingot is waiting."""
    slots = furnace_slots(content, "copper_ore", "stick")
    seconds = content.smelting["copper_ore"].seconds
    fire = run(content, slots, seconds / 2)
    assert slots.slots[OUTPUT] is None
    run(content, slots, seconds, fire)
    assert slots.slots[INPUT] is None
    assert slots.slots[FUEL] is None
    out = slots.slots[OUTPUT]
    assert out is not None
    assert out.item.name == "copper_ingot"


def test_no_fuel_or_no_room_means_no_work(content: Content) -> None:
    """Without fuel, or with another item in the output, nothing is lit."""
    slots = furnace_slots(content, "iron_ore", "stick")
    slots.slots[FUEL] = None
    run(content, slots, 30)
    assert slots.slots[INPUT] is not None
    slots = furnace_slots(content, "iron_ore", "stick")
    slots.slots[OUTPUT] = ItemStack(content.items["copper_ingot"])
    fire = run(content, slots, 30)
    assert not fire.lit
    assert slots.slots[FUEL] is not None


def test_a_fuel_item_burns_for_several_ores(content: Content) -> None:
    """A log keeps the fire going for more than one ore."""
    slots = furnace_slots(content, "tin_ore", "oak_log", 3)
    run(content, slots, 100)
    out = slots.slots[OUTPUT]
    assert out is not None
    assert out.amount == THREE
    assert slots.slots[FUEL] is None


def test_the_game_runs_furnaces_it_has_opened(content: Content) -> None:
    """A furnace block with contents smelts while the world ticks."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    tile = (4, 9)
    game.tilemap.set(*tile, content.blocks.id_of("furnace"))
    slots = game.chest_at(*tile)
    assert slots is not None
    slots.slots[INPUT] = ItemStack(content.items["gold_ore"])
    slots.slots[FUEL] = ItemStack(content.items["stick"])
    seconds = content.smelting["gold_ore"].seconds
    for _ in range(round(seconds * game.config.tick_rate) + 5):
        game.tick(TickInput())
    out = slots.slots[OUTPUT]
    assert out is not None
    assert out.item.name == "gold_ingot"
