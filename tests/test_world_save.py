# Copyright (c) 2026 Schunche
"""Saving and loading worlds with their players' inventories."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, cast

import pytest

from sch5n.error.exceptions import ParseError
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.session import Game, GameSetup
from sch5n.game.vitals import MAX_HEALTH, MAX_HUNGER
from sch5n.world.save import (
    SUFFIX,
    delete_world,
    inventory_from_json,
    inventory_to_json,
    list_worlds,
    load_world,
    save_world,
    set_favorite,
    unique_name,
    world_path,
)
from tests.test_session import flat_world

HUNGRY = 4

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


def test_favorites_come_first_and_survive_saving(
    tmp_path: Path, content: Content
) -> None:
    """A favorite world is listed first, even after it is saved again."""
    for name in ("old", "new"):
        save_world(world_path(tmp_path, name), name, flat_world(content), {})
    os.utime(world_path(tmp_path, "old"), (OLDER, OLDER))
    assert [w.name for w in list_worlds(tmp_path)] == ["new", "old"]

    set_favorite(world_path(tmp_path, "old"), favorite=True)
    save_world(world_path(tmp_path, "old"), "old", flat_world(content), {})
    worlds = list_worlds(tmp_path)
    assert [w.name for w in worlds] == ["old", "new"]
    assert worlds[0].favorite
    assert not worlds[1].favorite

    set_favorite(world_path(tmp_path, "old"), favorite=False)
    assert not any(w.favorite for w in list_worlds(tmp_path))


def test_delete_world(tmp_path: Path, content: Content) -> None:
    """A deleted world is gone from the list. A favorite is refused."""
    path = world_path(tmp_path, "doomed")
    save_world(path, "doomed", flat_world(content), {})
    set_favorite(path, favorite=True)
    with pytest.raises(PermissionError):
        delete_world(path)
    assert path.exists()
    set_favorite(path, favorite=False)
    delete_world(path)
    assert not path.exists()
    assert list_worlds(tmp_path) == []
    delete_world(path)


def test_saved_branches_load_as_sticks(content: Content) -> None:
    """Inventories saved before the rename keep their items."""
    inventory = inventory_from_json(
        {"selected": 0, "slots": [["branch", 7]]}, content.items, 10
    )
    stack = inventory[0]
    assert stack is not None
    assert (stack.item.name, stack.amount) == ("stick", 7)
    slots = cast("list[object]", inventory_to_json(inventory)["slots"])
    assert slots[0] == ["stick", 7]


def test_health_and_hunger_are_saved(tmp_path: Path, content: Content) -> None:
    """Vitals come back with the inventory; old saves start full."""
    inventory = Inventory(content.game.inventory.size)
    inventory.vitals.health = 7
    inventory.vitals.hunger = 3
    path = world_path(tmp_path, "vitals")
    save_world(path, "vitals", flat_world(content), {"Ann": inventory})
    loaded = load_world(path, content).inventories["Ann"]
    assert (loaded.vitals.health, loaded.vitals.hunger) == (7, 3)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["inventories"]["Ann"].update(health=-5, hunger=999)
    path.write_text(json.dumps(data), encoding="utf-8")
    clamped = load_world(path, content).inventories["Ann"].vitals
    assert (clamped.health, clamped.hunger) == (1, MAX_HUNGER)
    data["inventories"]["Ann"].pop("health")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert (
        load_world(path, content).inventories["Ann"].vitals.health
        == MAX_HEALTH
    )


def test_vitals_survive_leaving_the_game(content: Content) -> None:
    """A player who rejoins is as hungry as when leaving."""
    game = Game(content, flat_world(content), GameSetup(host_player=False))
    player_id = game.add_player("ann")
    game.players[player_id].vitals.hunger = HUNGRY
    game.remove_player(player_id)
    again = game.add_player("ann")
    assert game.players[again].vitals.hunger == HUNGRY


def test_chests_are_saved_with_the_world(
    tmp_path: Path, content: Content
) -> None:
    """Chest contents come back, and chests that vanished are not saved."""
    tilemap = flat_world(content)
    chest_id = content.blocks.id_of("chest")
    tilemap.set(2, 9, chest_id)
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    chest = game.chest_at(2, 9)
    assert chest is not None
    chest.slots[5] = ItemStack(content.items["stick"], 4)
    gone = game.chest_at(2, 9)
    assert gone is chest
    assert game.chest_at(3, 9) is None
    game.chests[7, 7] = Inventory(27)  # Nothing stands there.
    path = world_path(tmp_path, "boxes")
    save_world(path, "boxes", tilemap, {}, None, game.chest_contents())
    world = load_world(path, content)
    assert set(world.chests) == {(2, 9)}
    stack = world.chests[2, 9][5]
    assert stack is not None
    assert (stack.item.name, stack.amount) == ("stick", 4)
    again = Game(content, world.tilemap, GameSetup(seed=1, spawn=(0, 0)))
    again.chests.update(world.chests)
    reopened = again.chest_at(2, 9)
    assert reopened is not None
    assert reopened[5] is not None


def test_the_time_of_day_is_saved(tmp_path: Path, content: Content) -> None:
    """A world comes back at the moment of the day it was left at."""
    from sch5n.server.server import Server  # ruff: ignore[import-outside-top-level]

    server = Server(content, flat_world(content))
    server.game.set_time(0.9)
    clock = server.game.clock
    path = world_path(tmp_path, "Night")
    server.save(path)
    world = load_world(path, content)
    assert world.clock == clock
    again = Server(content, world.tilemap, clock=world.clock)
    assert again.game.clock == clock
