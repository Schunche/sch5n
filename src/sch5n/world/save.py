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
from dataclasses import dataclass
from typing import TYPE_CHECKING

import platformdirs

from sch5n.about import NAME, __author__
from sch5n.error.exceptions import ParseError
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.log.logger import LOGGER
from sch5n.world.io import tilemap_from_json, tilemap_to_json

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.game.content import Content, ItemRegistry
    from sch5n.vendor.json import Json
    from sch5n.world.tilemap import TileMap

WORLD_FORMAT = 1
SUFFIX = ".world.json"
MAX_NAME_LENGTH = 40
_UNSAFE = re.compile(r"[^\w\- ]+")


def user_worlds_dir() -> Path:
    """Where the user's worlds are saved.

    Returns:
        Path: A directory in the per-user data directory.

    """
    dirs = platformdirs.PlatformDirs(appname=NAME, appauthor=__author__)
    return dirs.user_data_path / "worlds"


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


def list_worlds(directory: Path) -> list[WorldInfo]:
    """List the saved worlds, most recently played first.

    Returns:
        list[WorldInfo]: The worlds. Unreadable files are left out.

    """
    worlds: list[WorldInfo] = []
    if not directory.is_dir():
        return worlds
    for file in directory.glob(f"*{SUFFIX}"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            name = data["name"]
            modified = file.stat().st_mtime
        except OSError, ValueError, KeyError, TypeError:
            LOGGER.warning("Skipping unreadable world %s", file)
            continue
        if isinstance(name, str):
            worlds.append(WorldInfo(name, file, modified))
    return sorted(worlds, key=lambda w: w.modified, reverse=True)


def inventory_to_json(inventory: Inventory) -> dict[str, Json]:
    """Encode an inventory.

    Returns:
        dict[str, Json]: Slots as `[item, amount]` or `null`, and the
        selected hotbar slot.

    """
    return {
        "selected": inventory.selected,
        "slots": [
            None if slot is None else [slot.item.name, slot.amount]
            for slot in inventory
        ],
    }


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
    inventory = Inventory(size)
    for index, slot in enumerate(slots[:size]):
        match slot:
            case None:
                continue
            case [str(name), int(amount)] if amount > 0:
                if name not in items:
                    LOGGER.warning("Dropping unknown item %r", name)
                    continue
                inventory.slots[index] = ItemStack(items[name], amount)
            case _:
                msg = f"Invalid inventory slot {slot!r}"
                raise ParseError(msg)
    selected = data.get("selected", 0)
    inventory.select(selected if isinstance(selected, int) else 0)
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


def save_world(
    path: Path,
    name: str,
    tilemap: TileMap,
    inventories: dict[str, Inventory],
    owner: str | None = None,
) -> None:
    """Write a world file. A crash while saving leaves the old file whole.

    `owner` is the player whose single player world it is, if any.
    """
    data = {
        "format": WORLD_FORMAT,
        "name": clean_name(name),
        "owner": owner,
        "inventories": {
            player: inventory_to_json(inventory)
            for player, inventory in inventories.items()
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
    )
