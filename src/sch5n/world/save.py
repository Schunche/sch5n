# Copyright (c) 2026 Schunche
"""Saved worlds: the blocks of a world and the inventories of its players.

A world file is JSON: `{"format": 1, "name": ..., "map": ...,
"inventories": {player name: inventory}}`, where `map` uses the map file
format of `sch5n.world.io`. Worlds live in the user's data directory,
apart from the maps that come with the game.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sch5n.error.exceptions import ParseError
from sch5n.game.inventory import (
    ARMOR_PARTS,
    CRAFTING_SIDE,
    MAX_CRAFTING_SIDE,
    Inventory,
    ItemStack,
)
from sch5n.game.vitals import MAX_HEALTH, MAX_HUNGER
from sch5n.log.logger import LOGGER
from sch5n.utility.path import user_dirs
from sch5n.world.io import tilemap_from_json, tilemap_to_json

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.game.content import Content, ItemRegistry
    from sch5n.game.inventory import Slot
    from sch5n.vendor.json import Json
    from sch5n.world.tilemap import TileMap

WORLD_FORMAT = 1
SUFFIX = ".world.json"
FAVORITES_FILE = "favorites.json"
MAX_NAME_LENGTH = 40
_UNSAFE = re.compile(r"[^\w\- ]+")


def user_worlds_dir() -> Path:
    """Where the user's worlds are saved.

    Returns:
        Path: A directory in the per-user data directory.

    """
    return user_dirs().data / "worlds"


def clean_name(name: str) -> str:
    """Make a world name presentable: single spaces, limited length.

    Returns:
        str: The name, "World" if nothing is left.

    """
    return " ".join(name.split())[:MAX_NAME_LENGTH] or "World"


def world_path(directory: Path, name: str) -> Path:
    """File of a world, named after it.

    Returns:
        Path: The file, in `directory`.

    """
    stem = _UNSAFE.sub("", clean_name(name)).strip() or "world"
    return directory / f"{stem}{SUFFIX}"


def unique_name(directory: Path, wanted: str) -> str:
    """Find a world name whose file does not exist yet.

    Returns:
        str: `wanted`, or `wanted` with a number.

    """
    base = clean_name(wanted)
    name, number = base, 2
    while world_path(directory, name).exists():
        name = f"{base} {number}"
        number += 1
    return name


@dataclass(frozen=True, slots=True)
class WorldInfo:
    """A saved world, for listing."""

    name: str
    path: Path
    modified: float
    """Last save, as a timestamp."""
    favorite: bool = False


def _read_favorites(directory: Path) -> set[str]:
    try:
        data = json.loads(
            (directory / FAVORITES_FILE).read_text(encoding="utf-8")
        )
    except OSError, ValueError:
        return set()
    if not isinstance(data, list):
        return set()
    return {entry for entry in data if isinstance(entry, str)}


def set_favorite(path: Path, *, favorite: bool) -> None:
    """Mark a world as a favorite, or not.

    Favorites are kept beside the worlds, so saving a world never
    changes them.
    """
    directory = path.parent
    names = _read_favorites(directory)
    if favorite:
        names.add(path.name)
    else:
        names.discard(path.name)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / FAVORITES_FILE).write_text(
        json.dumps(sorted(names)), encoding="utf-8"
    )


def delete_world(path: Path) -> None:
    """Delete a world file. Favorites are protected.

    Raises:
        PermissionError: The world is a favorite. Unfavorite it first.

    """
    if path.name in _read_favorites(path.parent):
        msg = f"{path.name} is a favorite"
        raise PermissionError(msg)
    path.unlink(missing_ok=True)
    LOGGER.info("Deleted world %s", path)


def list_worlds(directory: Path) -> list[WorldInfo]:
    """List the saved worlds: favorites first, then most recently played.

    Returns:
        list[WorldInfo]: The worlds. Unreadable files are left out.

    """
    worlds: list[WorldInfo] = []
    if not directory.is_dir():
        return worlds
    favorites = _read_favorites(directory)
    for file in directory.glob(f"*{SUFFIX}"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            name = data["name"]
            modified = file.stat().st_mtime
        except OSError, ValueError, KeyError, TypeError:
            LOGGER.warning("Skipping unreadable world %s", file)
            continue
        if isinstance(name, str):
            worlds.append(
                WorldInfo(name, file, modified, file.name in favorites)
            )
    return sorted(worlds, key=lambda w: (not w.favorite, -w.modified))


def inventory_to_json(inventory: Inventory) -> dict[str, Json]:
    """Encode an inventory.

    Returns:
        dict[str, Json]: Slots and crafting grid as `[item, amount]` or
        `null`, and the selected hotbar slot.

    """
    return {
        "selected": inventory.selected,
        "slots": [_slot_to_json(slot) for slot in inventory],
        "crafting": [_slot_to_json(slot) for slot in inventory.crafting],
        "armor": [_slot_to_json(slot) for slot in inventory.armor],
        "home": None if inventory.home is None else list(inventory.home),
        "health": inventory.vitals.health,
        "hunger": inventory.vitals.hunger,
    }


def _slot_to_json(slot: Slot) -> Json:
    return None if slot is None else [slot.item.name, slot.amount]


def _slot_from_json(data: Json, items: ItemRegistry) -> Slot:
    match data:
        case None:
            return None
        case [str(name), int(amount)] if amount > 0:
            if name not in items:
                LOGGER.warning("Dropping unknown item %r", name)
                return None
            return ItemStack(items[name], amount)
        case _:
            msg = f"Invalid inventory slot {data!r}"
            raise ParseError(msg)


def _restore_worn(
    inventory: Inventory, data: dict[str, Json], items: ItemRegistry
) -> None:
    """Put back the armor and the bed of a saved inventory."""
    match data.get("home"):
        case [int(hx), int(hy)]:
            inventory.home = (hx, hy)
        case _:
            pass
    armor = data.get("armor", [])
    if isinstance(armor, list):
        for index, slot in enumerate(armor[: len(inventory.armor)]):
            stack = _slot_from_json(slot, items)
            if stack is None or stack.item.spec.armor == ARMOR_PARTS[index]:
                inventory.armor[index] = stack


def inventory_from_json(
    data: Json, items: ItemRegistry, size: int
) -> Inventory:
    """Decode an inventory. Items the game no longer has are dropped.

    Returns:
        Inventory: The inventory, `size` slots big.

    Raises:
        ParseError: The data is not an inventory.

    """
    slots = data.get("slots") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(slots, list):
        msg = "An inventory needs a list of slots"
        raise ParseError(msg)
    crafting = data.get("crafting", [])
    if not isinstance(crafting, list):
        msg = "The crafting grid must be a list of slots"
        raise ParseError(msg)
    inventory = Inventory(size)
    for index, slot in enumerate(slots[:size]):
        inventory.slots[index] = _slot_from_json(slot, items)
    if len(crafting) > CRAFTING_SIDE**2:
        inventory.resize_crafting(MAX_CRAFTING_SIDE)
    for index, slot in enumerate(crafting[: len(inventory.crafting)]):
        inventory.crafting[index] = _slot_from_json(slot, items)
    _restore_worn(inventory, data, items)
    selected = data.get("selected", 0)
    inventory.select(selected if isinstance(selected, int) else 0)
    health, hunger = data.get("health"), data.get("hunger")
    if isinstance(health, int) and isinstance(hunger, int):
        inventory.vitals.health = min(max(health, 1), MAX_HEALTH)
        inventory.vitals.hunger = min(max(hunger, 0), MAX_HUNGER)
    return inventory


@dataclass(slots=True)
class World:
    """A loaded world."""

    name: str
    tilemap: TileMap
    inventories: dict[str, Inventory]
    """Inventories of the players who played here, by name."""
    owner: str | None = None
    """The player whose single player world it is, if any."""
    chests: dict[tuple[int, int], Inventory] = field(default_factory=dict)
    """Contents of the storage blocks, by tile."""
    clock: int = 0
    """Ticks the day and night had counted when it was saved."""

    def hand_over(self, player: str) -> None:
        """Make `player` the owner, taking over the owner's inventory.

        The owner may have renamed itself since the world was saved; its
        inventory follows it, unless the new name already has one.
        """
        old = self.owner
        if (
            old is not None
            and old != player
            and player not in self.inventories
        ):
            inventory = self.inventories.pop(old, None)
            if inventory is not None:
                self.inventories[player] = inventory
        self.owner = player


def save_world(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
    path: Path,
    name: str,
    tilemap: TileMap,
    inventories: dict[str, Inventory],
    owner: str | None = None,
    chests: dict[tuple[int, int], Inventory] | None = None,
    clock: int = 0,
) -> None:
    """Write a world file. A crash while saving leaves the old file whole.

    `owner` is the player whose single player world it is, if any.
    """
    data = {
        "format": WORLD_FORMAT,
        "name": clean_name(name),
        "owner": owner,
        "clock": clock,
        "inventories": {
            player: inventory_to_json(inventory)
            for player, inventory in inventories.items()
        },
        "chests": {
            f"{x};{y}": inventory_to_json(chest)
            for (x, y), chest in (chests or {}).items()
        },
        "map": tilemap_to_json(tilemap),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=1), encoding="utf-8")
    temporary.replace(path)
    LOGGER.info("Saved world %r to %s", name, path)


def load_world(path: Path, content: Content) -> World:
    """Read a world file.

    Returns:
        World: The world.

    Raises:
        ParseError: The file is not a world this game can read.

    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        msg = f"Cannot read {path}: {error}"
        raise ParseError(msg) from error
    if not isinstance(data, dict) or data.get("format") != WORLD_FORMAT:
        msg = f"{path} is not a world, or from another game version"
        raise ParseError(msg)
    inventories = data.get("inventories", {})
    if not isinstance(inventories, dict):
        msg = "Inventories must be an object"
        raise ParseError(msg)
    size = content.game.inventory.size
    return World(
        name=clean_name(str(data.get("name", path.stem))),
        tilemap=tilemap_from_json(data.get("map"), content.blocks),
        inventories={
            str(player): inventory_from_json(inventory, content.items, size)
            for player, inventory in inventories.items()
        },
        owner=owner if isinstance(owner := data.get("owner"), str) else None,
        chests=_chests_from_json(data.get("chests"), content),
        clock=clock if isinstance(clock := data.get("clock"), int) else 0,
    )


def _chests_from_json(
    data: Json, content: Content
) -> dict[tuple[int, int], Inventory]:
    """Decode saved storage. Entries that cannot be read are skipped.

    Returns:
        dict[tuple[int, int], Inventory]: Contents by tile.

    """
    chests: dict[tuple[int, int], Inventory] = {}
    if not isinstance(data, dict):
        return chests
    for key, value in data.items():
        x, _, y = str(key).partition(";")
        try:
            tile = (int(x), int(y))
            slots = value["slots"] if isinstance(value, dict) else None
            size = len(slots) if isinstance(slots, list) else 0
            chests[tile] = inventory_from_json(value, content.items, size)
        except ValueError, KeyError, TypeError, ParseError:
            LOGGER.warning("Skipping unreadable chest %r", key)
    return chests
