# Copyright (c) 2026 Schunche
"""Breaking blocks."""

import pytest

from sch5n.game.content import AIR, Content, ItemDef, ItemRegistry
from sch5n.game.mining import (
    HitResult,
    durability_fraction,
    hit_tile,
    tool_power,
)
from sch5n.world.tilemap import TileMap


def test_needs_the_right_tool(tilemap: TileMap, items: ItemRegistry) -> None:
    """Only a matching tool damages a block."""
    tilemap.set(0, 0, tilemap.blocks.id_of("stone"))
    assert hit_tile(tilemap, 0, 0, items["axe"]).result is HitResult.WRONG_TOOL
    assert hit_tile(tilemap, 0, 0, items["rock"]).result is HitResult.NOTHING
    assert hit_tile(tilemap, 0, 0, None).result is HitResult.NOTHING
    assert hit_tile(tilemap, 5, 5, items["pick"]).result is HitResult.NOTHING
    assert durability_fraction(tilemap, 0, 0) == pytest.approx(1.0)


def test_breaks_after_enough_hits(
    tilemap: TileMap, items: ItemRegistry
) -> None:
    """Durability goes down per hit until the block breaks."""
    tilemap.set(
        0, 0, tilemap.blocks.id_of("stone")
    )  # 100 durability, 40 per hit.
    assert hit_tile(tilemap, 0, 0, items["pick"]).result is HitResult.DAMAGED
    assert durability_fraction(tilemap, 0, 0) == pytest.approx(0.6)
    assert hit_tile(tilemap, 0, 0, items["pick"]).result is HitResult.DAMAGED
    hit = hit_tile(tilemap, 0, 0, items["pick"])
    assert hit.result is HitResult.BROKEN
    assert hit.block is not None
    assert hit.block.name == "stone"
    assert tilemap.get(0, 0) == AIR
    assert not tilemap.damage


def test_transforming_block(tilemap: TileMap, items: ItemRegistry) -> None:
    """Some blocks leave another block behind."""
    tilemap.set(0, 0, tilemap.blocks.id_of("leaf"))
    for _ in range(4):
        hit_tile(tilemap, 0, 0, items["axe"])
    assert tilemap.get(0, 0) == tilemap.blocks.id_of("log")
    assert (0, 0) not in tilemap.damage


def hits_to_break(tilemap: TileMap, tool: ItemDef) -> int:
    """Hit a fresh tile at the origin until it breaks.

    Returns:
        int: Number of hits it took.

    """
    for hits in range(1, 100):
        if hit_tile(tilemap, 0, 0, tool).result is HitResult.BROKEN:
            return hits
    pytest.fail("never broke")


def test_shovel_is_made_for_dirt(content: Content) -> None:
    """A shovel digs dirt best; a pickaxe still can, more slowly."""
    dirt = content.blocks.by_name("dirt")
    shovel = content.items["iron_shovel"]
    pickaxe = content.items["copper_pickaxe"]
    assert 0 < tool_power(pickaxe, dirt) < tool_power(shovel, dirt)
    assert tool_power(content.items["copper_axe"], dirt) == 0

    tilemap = TileMap(content.blocks)
    tilemap.set(0, 0, dirt.id)
    by_shovel = hits_to_break(tilemap, shovel)
    tilemap.set(0, 0, dirt.id)
    by_pickaxe = hits_to_break(tilemap, pickaxe)
    assert by_shovel < by_pickaxe
    # Measured in time, too: the shovel is also quicker to swing.
    assert (
        by_shovel * shovel.spec.use_time < by_pickaxe * pickaxe.spec.use_time
    )
    # A shovel is no pickaxe.
    assert tool_power(shovel, content.blocks.by_name("stone")) == 0


def test_lopper_is_made_for_leaves(content: Content) -> None:
    """A lopper cuts leaves in one snip; an axe still can, more slowly."""
    leaf = content.blocks.by_name("oak_leaf")
    lopper = content.items["copper_lopper"]
    axe = content.items["copper_axe"]
    tilemap = TileMap(content.blocks)
    tilemap.set(0, 0, leaf.id)
    assert hits_to_break(tilemap, lopper) == 1
    tilemap.set(0, 0, leaf.id)
    by_axe = hits_to_break(tilemap, axe)
    assert by_axe > 1
    assert lopper.spec.use_time < by_axe * axe.spec.use_time
    # Loppers are no axes.
    assert tool_power(lopper, content.blocks.by_name("oak_log")) == 0
