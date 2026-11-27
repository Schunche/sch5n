# Copyright (c) 2026 Schunche
"""Saving and loading worlds with their players' inventories."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from sch5n.error.exceptions import ParseError
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.session import Game, GameSetup
from sch5n.world.save import (
    SUFFIX,
    list_worlds,
    load_world,
    save_world,
    unique_name,
    world_path,
)
from tests.test_session import flat_world

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.game.content import Content

DIRT_AMOUNT = 12
SELECTED = 3
OLDER = 1_000_000


def test_world_round_trip(tmp_path: Path, content: Content) -> None:
    """Blocks and inventories come back as they were saved."""
    tilemap = flat_world(content)
    tilemap.set(3, 2, content.blocks.id_of("stone"), 1)
    inventory = Inventory(content.game.inventory.size)
    inventory.slots[4] = ItemStack(content.items["dirt_block"], DIRT_AMOUNT)
    inventory.select(SELECTED)
    path = world_path(tmp_path, "My world")
    save_world(path, "My world", tilemap, {"Ann": inventory})

    world = load_world(path, content)
    assert world.name == "My world"
    assert sorted(world.tilemap.iter_tiles()) == sorted(tilemap.iter_tiles())
    loaded = world.inventories["Ann"]
    stack = loaded[4]
    assert stack is not None
    assert stack.item.name == "dirt_block"
    assert stack.amount == DIRT_AMOUNT
    assert loaded.selected == SELECTED


def test_unknown_items_are_dropped(tmp_path: Path, content: Content) -> None:
    """A world from a game that had other items still loads."""
    path = world_path(tmp_path, "old")
    save_world(path, "old", flat_world(content), {})
    data = json.loads(path.read_text(encoding="utf-8"))
    data["inventories"] = {"Ann": {"slots": [["laser", 1], ["dirt_block", 2]]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    inventory = load_world(path, content).inventories["Ann"]
    assert inventory[0] is None
    assert inventory[1] is not None


@pytest.mark.parametrize(
    "text",
    ["", "{}", '{"format": 99}', '{"format": 1, "map": {"0;0": 5}}'],
    ids=["empty", "no format", "newer format", "bad map"],
)
def test_broken_worlds_are_refused(
    tmp_path: Path, content: Content, text: str
) -> None:
    """Files that are not worlds raise a clear error, not a crash."""
    path = tmp_path / f"broken{SUFFIX}"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ParseError):
        load_world(path, content)


def test_listing_and_names(tmp_path: Path, content: Content) -> None:
    """Worlds are listed newest first; names stay unique and file safe."""
    assert list_worlds(tmp_path / "missing") == []
    first = world_path(tmp_path, "First")
    second = world_path(tmp_path, "Second")
    save_world(first, "First", flat_world(content), {})
    save_world(second, "Second", flat_world(content), {})
    os.utime(first, (OLDER, OLDER))
    (tmp_path / f"junk{SUFFIX}").write_text("not json", encoding="utf-8")
    assert [w.name for w in list_worlds(tmp_path)] == ["Second", "First"]

    assert unique_name(tmp_path, "First") == "First 2"
    assert unique_name(tmp_path, "  Third   one ") == "Third one"
    assert world_path(tmp_path, "../../etc/passwd").parent == tmp_path


def test_game_keeps_inventories_of_everyone(content: Content) -> None:
    """Present and departed players' inventories are saved and restored."""
    game = Game(content, flat_world(content), GameSetup(host_player=False))
    here = game.add_player("here")
    gone = game.add_player("gone")
    game.remove_player(gone)
    kept = game.inventories()
    assert set(kept) == {"here", "gone"}
    assert kept["here"] is game.players[here].inventory

    other = Game(content, flat_world(content), GameSetup(host_player=False))
    other.restore_inventories(kept)
    back = other.add_player("gone")
    assert other.players[back].inventory is kept["gone"]


def test_owner_keeps_inventory_when_renamed(
    tmp_path: Path, content: Content
) -> None:
    """A world's owner takes its inventory along to a new name."""
    inventory = Inventory(content.game.inventory.size)
    path = world_path(tmp_path, "Mine")
    save_world(path, "Mine", flat_world(content), {"Old": inventory}, "Old")
    world = load_world(path, content)
    assert world.owner == "Old"
    world.hand_over("New")
    assert world.owner == "New"
    assert set(world.inventories) == {"New"}

    # A name that already has an inventory keeps its own.
    other = Inventory(content.game.inventory.size)
    world.inventories["Guest"] = other
    world.hand_over("Guest")
    assert world.inventories["Guest"] is other
    assert "New" in world.inventories
