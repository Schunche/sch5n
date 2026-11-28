# Copyright (c) 2026 Schunche
"""Furnaces: an input, a fuel and an output slot, worked on over time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sch5n.game.inventory import ItemStack

if TYPE_CHECKING:
    from sch5n.game.content import Content, SmeltSpec
    from sch5n.game.inventory import Inventory

INPUT, FUEL, OUTPUT = 0, 1, 2
"""Slots of a furnace."""


@dataclass(slots=True)
class Furnace:
    """What a furnace is doing. Lost when a world is saved."""

    burning: int = 0
    """Ticks of fuel left."""
    progress: int = 0
    """Ticks spent on the current item."""

    @property
    def lit(self) -> bool:
        """Whether the fire is going."""
        return self.burning > 0


def _recipe(slots: Inventory, content: Content) -> SmeltSpec | None:
    stack = slots.slots[INPUT]
    if stack is None:
        return None
    smelt = content.smelting.get(stack.item.name)
    if smelt is None:
        return None
    out = slots.slots[OUTPUT]
    made = content.items[smelt.result.item]
    if out is not None and (
        out.item is not made or out.room < smelt.result.amount
    ):
        return None
    return smelt


def tick_furnace(
    furnace: Furnace, slots: Inventory, content: Content, tick_rate: int
) -> None:
    """Burn fuel, and finish an item when its time has come.

    Fuel is only lit when there is something to smelt and room for it.
    """
    smelt = _recipe(slots, content)
    fuel = slots.slots[FUEL]
    if (
        not furnace.lit
        and smelt is not None
        and fuel is not None
        and fuel.item.spec.fuel > 0
    ):
        furnace.burning = round(fuel.item.spec.fuel * tick_rate)
        fuel.amount -= 1
        if fuel.amount <= 0:
            slots.slots[FUEL] = None
    if furnace.lit:
        furnace.burning -= 1
        if smelt is None:
            furnace.progress = 0
            return
        furnace.progress += 1
        if furnace.progress >= round(smelt.seconds * tick_rate):
            furnace.progress = 0
            _finish(slots, smelt, content)
    else:
        furnace.progress = 0


def _finish(slots: Inventory, smelt: SmeltSpec, content: Content) -> None:
    source = slots.slots[INPUT]
    if source is None:
        return
    source.amount -= 1
    if source.amount <= 0:
        slots.slots[INPUT] = None
    made = ItemStack(content.items[smelt.result.item], smelt.result.amount)
    out = slots.slots[OUTPUT]
    if out is None:
        slots.slots[OUTPUT] = made
    else:
        out.amount += made.amount
