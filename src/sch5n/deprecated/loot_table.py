# Copyright (c) 2026 Schunche
"""Experimental software."""

from sch5n.deprecated.item_data import ITEM_DATA
lazy from sch5n.deprecated.item import Item

# Loot tables here

# Breaking a tile, which gives back the exact same thing
SAME_LOOT_TILE: dict[str, Item] = {
    "dirt": ITEM_DATA[2],
    "oakLog": ITEM_DATA[3],
}
