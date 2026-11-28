# Copyright (c) 2026 Schunche
"""Crafting with the real recipes."""

from typing import TYPE_CHECKING

import pytest

from sch5n.game.content import AIR
from sch5n.game.crafting import craft, craft_all, crafted
from sch5n.game.inventory import CRAFTING_SIDE, Inventory, ItemStack
from sch5n.game.mining import can_place
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.world.io import tilemap_to_json
from sch5n.world.save import inventory_from_json, inventory_to_json
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

PLANKS = 4
UNMOVED = 3
"""Items left in the grid when the inventory fills up."""
CRAFTING_SIZE = CRAFTING_SIDE**2
BENCH = (3, 9)
"""Next to where players spawn."""


@pytest.fixture
def inventory(content: Content) -> Inventory:
    """Make an empty inventory.

    Returns:
        Inventory: The inventory.

    """
    return Inventory(content.game.inventory.size)


@pytest.mark.parametrize("slot", range(CRAFTING_SIZE))
def test_a_log_anywhere_makes_planks(
    content: Content, inventory: Inventory, slot: int
) -> None:
    """One oak log in any slot makes four planks, using one log."""
    inventory.crafting[slot] = ItemStack(content.items["oak_log"], 2)
    result = crafted(inventory, content)
    assert result is not None
    assert (result.item.name, result.amount) == ("oak_planks", PLANKS)

    assert craft(inventory, content)
    assert craft(inventory, content)
    assert inventory.cursor is not None
    assert inventory.cursor.amount == 2 * PLANKS
    assert inventory.crafting[slot] is None
    assert not craft(inventory, content)


@pytest.mark.parametrize(
    "grid", [[], ["dirt_block"], ["oak_log", "oak_log"], ["oak_log", "leaf"]]
)
def test_other_grids_make_nothing(
    content: Content, inventory: Inventory, grid: list[str]
) -> None:
    """Every filled slot must belong to the recipe."""
    for slot, item in enumerate(grid):
        inventory.crafting[slot] = ItemStack(content.items[item])
    assert crafted(inventory, content) is None
    assert not craft(inventory, content)


@pytest.mark.parametrize(
    ("item", "amount"), [("dirt_block", 1), ("oak_planks", 1021)]
)
def test_a_cursor_without_room_stops_crafting(
    content: Content, inventory: Inventory, item: str, amount: int
) -> None:
    """Nothing is used up if the result cannot go onto the cursor."""
    inventory.crafting[0] = ItemStack(content.items["oak_log"])
    inventory.cursor = ItemStack(content.items[item], amount)
    assert not craft(inventory, content)
    assert inventory.crafting[0] is not None
    assert inventory.cursor.amount == amount


def test_closing_returns_the_grid(content: Content) -> None:
    """Items left in the grid go back into the inventory."""
    game = Game(content, flat_world(content), GameSetup(seed=1))
    game.inventory.crafting[3] = ItemStack(content.items["oak_log"], 5)
    game.return_cursor_stack(game.player)
    assert game.inventory.crafting == [None] * CRAFTING_SIZE
    assert any(s and s.item.name == "oak_log" for s in game.inventory)


def test_the_grid_is_saved(content: Content, inventory: Inventory) -> None:
    """A saved world keeps what was in the grid."""
    inventory.crafting[2] = ItemStack(content.items["oak_log"], 5)
    loaded = inventory_from_json(
        inventory_to_json(inventory), content.items, len(inventory)
    )
    assert loaded.crafting == inventory.crafting


def fill(inventory: Inventory, content: Content, *rows: str) -> None:
    """Lay out a grid, one row per string.

    L leaf, P planks, S stick, C cobblestone, B stone block.
    """
    names = {
        "L": "leaf",
        "P": "oak_planks",
        "S": "stick",
        "C": "cobblestone",
        "B": "stone_block",
    }
    inventory.resize_crafting(len(rows))
    for index, symbol in enumerate("".join(rows)):
        inventory.crafting[index] = (
            ItemStack(content.items[names[symbol]]) if symbol != " " else None
        )


@pytest.mark.parametrize(
    ("rows", "made"),
    [
        (("SS", "SS"), ("oak_planks", 2)),
        (("CCC", " S ", " S "), ("stone_pickaxe", 1)),
        (("BBB", " S ", " S "), ("stone_pickaxe", 1)),
        (("CBC", " S ", " S "), ("stone_pickaxe", 1)),
        (("CPC", " S ", " S "), None),
        (("CC ", " S ", " S "), None),
        (("LL", "LL"), None),
        (("PP", "PP"), ("crafting_bench", 1)),
        (("P ", "P "), ("stick", 4)),
        ((" P", " P"), ("stick", 4)),
        (("   ", "  P", "  P"), ("stick", 4)),
        (("PP", "  "), None),
        (("   ", " PP", " PP"), ("crafting_bench", 1)),
        (("PPP", " S ", " S "), ("wooden_pickaxe", 1)),
        (("PP", "P "), None),
        (("SS", "  "), None),
        (("PPP", "S  ", "S  "), None),
        (("PPP", " S ", "S  "), None),
        (("PP ", "PS ", " S "), ("wooden_axe", 1)),
        (("PP ", "SP ", "S  "), None),
        (("P  ", "S  ", "S  "), ("wooden_shovel", 1)),
        (("CC ", "CS ", " S "), ("stone_axe", 1)),
        (("BC ", "CS ", " S "), ("stone_axe", 1)),
        (("C  ", "S  ", "S  "), ("stone_shovel", 1)),
        (("C  ", "S  ", "P  "), None),
        (("PPP", " SL", " S "), None),
    ],
)
def test_shaped_recipes(
    content: Content,
    inventory: Inventory,
    rows: tuple[str, ...],
    made: tuple[str, int] | None,
) -> None:
    """Shapes match anywhere in the grid, and only exactly."""
    fill(inventory, content, *rows)
    result = crafted(inventory, content)
    assert (result and (result.item.name, result.amount)) == made


def test_the_wooden_pickaxe_is_the_weakest(content: Content) -> None:
    """Wood is weaker and slower than stone, and stone than copper."""
    kinds = ("wooden", "stone", "copper")
    specs = [content.items[f"{kind}_pickaxe"].spec for kind in kinds]
    powers = [spec.tool_power["pickaxe"] for spec in specs]
    times = [spec.use_time for spec in specs]
    assert powers == sorted(set(powers))
    assert times == sorted(set(times), reverse=True)


@pytest.mark.parametrize("tool", ["axe", "shovel"])
def test_wooden_and_stone_tools_are_weaker_than_copper(
    content: Content, tool: str
) -> None:
    """Every kind of tool gets stronger and quicker with better material."""
    kinds = ("wooden", "stone", "copper")
    specs = [content.items[f"{kind}_{tool}"].spec for kind in kinds]
    powers = [spec.tool_power[tool] for spec in specs]
    times = [spec.use_time for spec in specs]
    assert powers == sorted(set(powers))
    assert times == sorted(set(times), reverse=True)


def at_bench(content: Content) -> Game:
    """Start a game beside a crafting bench.

    Returns:
        Game: The game, after one tick.

    """
    tilemap = flat_world(content)
    tilemap.set(*BENCH, content.blocks.id_of("crafting_bench"))
    game = Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))
    game.tick(TickInput())
    return game


def test_a_bench_in_reach_enlarges_the_grid(content: Content) -> None:
    """The grid is 3x3 near a bench and 2x2 away from it."""
    game = at_bench(content)
    assert game.inventory.crafting_side == CRAFTING_SIDE + 1
    game.player.body.x += 20 * content.game.tile_size
    game.tick(TickInput())
    assert game.inventory.crafting_side == CRAFTING_SIDE


@pytest.mark.parametrize("full", [False, True])
def test_leaving_the_bench_keeps_only_the_small_grid(
    content: Content, *, full: bool
) -> None:
    """Items outside the 2x2 corner are stowed, or dropped if it is full."""
    game = at_bench(content)
    inventory = game.inventory
    if full:
        dirt = content.items["dirt_block"]
        inventory.slots = [
            ItemStack(dirt, dirt.spec.max_stack) for _ in inventory
        ]
    stick, leaf = content.items["stick"], content.items["leaf"]
    inventory.crafting[4] = ItemStack(leaf, 2)  # Middle: stays.
    inventory.crafting[8] = ItemStack(stick, 3)  # Corner: does not.
    game.tilemap.set(*BENCH, AIR)
    game.tick(TickInput())
    assert [s and s.item.name for s in inventory.crafting] == [
        None,
        None,
        None,
        "leaf",
    ]
    stowed = [s for s in inventory if s and s.item is stick]
    dropped = [f.stack for f in game.floating_items if f.stack.item is stick]
    assert [s.amount for s in (dropped if full else stowed)] == [3]
    assert not (stowed if full else dropped)


def test_a_large_grid_is_saved(content: Content, inventory: Inventory) -> None:
    """All nine slots come back."""
    fill(inventory, content, "PPP", " S ", " S ")
    loaded = inventory_from_json(
        inventory_to_json(inventory), content.items, len(inventory)
    )
    assert loaded.crafting == inventory.crafting


def test_placed_benches_pick_a_random_look(content: Content) -> None:
    """Each placed bench gets one of its textures, and keeps it saved."""
    game = Game(content, flat_world(content), GameSetup(seed=1, spawn=(0, 0)))
    bench = content.blocks.by_name("crafting_bench")
    game.inventory.slots[4] = ItemStack(content.items["crafting_bench"], 20)
    game.inventory.select(4)
    seen = set()
    for _ in range(20):
        for _ in range(40):
            game.tick(TickInput(place=True, target=(3, 9)))
        assert game.tilemap.get(3, 9) == bench.id
        variant = game.tilemap.get_variant(3, 9)
        saved = tilemap_to_json(game.tilemap)["3;9"]
        assert saved["variant"] == variant
        seen.add(variant)
        game.tilemap.set(3, 9, AIR)
    assert seen == set(range(len(bench.spec.textures)))


def test_players_walk_through_a_bench(content: Content) -> None:
    """A bench does not block movement, but can still be built against."""
    game = at_bench(content)
    assert not game.tilemap.is_solid(*BENCH)
    assert can_place(game.tilemap, BENCH[0], BENCH[1] - 1)
    far_side = (BENCH[0] + 2) * content.game.tile_size
    for _ in range(300):
        game.tick(TickInput(move_x=1))
    assert game.player.body.x > far_side


@pytest.mark.parametrize(
    ("offered", "shares", "left"),
    [
        ((10, False), [3, 3, 3], 1),
        ((2, False), [1, 1, None], 0),
        ((10, True), [1, 1, 1], 7),
    ],
)
def test_spreading_a_stack(
    content: Content,
    inventory: Inventory,
    offered: tuple[int, bool],
    shares: list[int | None],
    left: int,
) -> None:
    """Slots share the cursor stack; other items are skipped."""
    amount, single = offered
    inventory.slots[0] = ItemStack(content.items["leaf"])
    inventory.cursor = ItemStack(content.items["stick"], amount)
    grid = len(inventory)
    inventory.spread([0, 1, 1, grid, 2, 999], single=single)
    got = [inventory[1], inventory.crafting[0], inventory[2]]
    assert [s and s.amount for s in got] == shares
    assert (inventory.cursor.amount if inventory.cursor else 0) == left
    assert inventory[0] is not None
    assert inventory[0].item.name == "leaf"


def test_gathering_stops_at_a_full_stack(
    content: Content, inventory: Inventory
) -> None:
    """Matching stacks move into the slot until it is full."""
    stick = content.items["stick"]
    full = stick.spec.max_stack
    inventory.slots[3] = ItemStack(stick, full - 4)
    inventory.slots[7] = ItemStack(stick, 10)
    inventory.cursor = ItemStack(stick, 1)
    inventory.gather(5)
    assert inventory[5] is not None
    assert inventory[5].amount == full
    assert sum(s.amount for s in inventory if s) == full + 7
    assert inventory.cursor is None


def test_crafting_all_stops_when_full(
    content: Content, inventory: Inventory
) -> None:
    """Only whole results that fit are made; nothing is lost."""
    dirt = content.items["dirt_block"]
    inventory.slots = [ItemStack(dirt, dirt.spec.max_stack) for _ in inventory]
    planks = content.items["oak_planks"]
    inventory.slots[0] = ItemStack(planks, planks.spec.max_stack - 9)
    inventory.crafting[0] = ItemStack(content.items["oak_log"], 5)
    craft_all(inventory, content)
    assert inventory.crafting[0] is not None
    assert inventory.crafting[0].amount == UNMOVED
    assert inventory[0] is not None
    assert inventory[0].amount == planks.spec.max_stack - 1


def test_stowing_keeps_what_does_not_fit(
    content: Content, inventory: Inventory
) -> None:
    """A grid stack moves out only as far as there is room."""
    stick = content.items["stick"]
    full = stick.spec.max_stack
    inventory.slots = [ItemStack(stick, full) for _ in inventory]
    inventory.slots[0] = ItemStack(stick, full - 2)
    inventory.crafting[2] = ItemStack(stick, 5)
    inventory.stow_crafting(2)
    assert inventory.crafting[2] is not None
    assert inventory.crafting[2].amount == UNMOVED


ORES = (
    "copper",
    "tin",
    "iron",
    "lead",
    "silver",
    "tungsten",
    "gold",
    "platinum",
)


@pytest.mark.parametrize("ore", ORES)
def test_ores_need_a_pickaxe_and_drop_ore(content: Content, ore: str) -> None:
    """Ore blocks are dug with a pickaxe and give their raw ore."""
    block = content.blocks.by_name(ore)
    assert block.spec.tool == "pickaxe"
    assert block.spec.drop == f"{ore}_ore"
    assert f"{ore}_ore" in content.items
    assert block.durability > content.blocks.by_name("stone").durability


@pytest.mark.parametrize("metal", ["copper", "iron"])
def test_metal_tools_are_made_from_ingots(
    content: Content, inventory: Inventory, metal: str
) -> None:
    """Ore and sticks smelt into an ingot; ingots make the four tools."""
    names = {"O": f"{metal}_ore", "I": f"{metal}_ingot", "S": "stick"}

    def lay(*rows: str) -> str | None:
        inventory.resize_crafting(len(rows))
        for index, symbol in enumerate("".join(rows)):
            inventory.crafting[index] = (
                ItemStack(content.items[names[symbol]])
                if symbol != " "
                else None
            )
        result = crafted(inventory, content)
        return result and result.item.name

    assert lay("OS ", "S  ", "   ") == f"{metal}_ingot"
    assert lay("III", " S ", " S ") == f"{metal}_pickaxe"
    assert lay("II ", "IS ", " S ") == f"{metal}_axe"
    assert lay("I  ", "S  ", "S  ") == f"{metal}_shovel"
    assert lay("I I", " S ", "S S") == f"{metal}_lopper"
    assert lay("III", " S ", "   ") is None
