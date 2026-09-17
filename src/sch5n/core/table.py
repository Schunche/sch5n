# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sch5n.core.item import Item
from sch5n.core.item_data import ITEM_DATA

# Loot tables here

# Breaking a tile, which gives back the exact same thing
SAME_LOOT_TILE: dict[str, Item] = {
    "dirt": ITEM_DATA[2],
    "oakLog": ITEM_DATA[3],
}
