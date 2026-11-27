# Copyright (c) 2026 Schunche
"""Breaking blocks."""

import pytest

from sch5n.game.content import AIR, ItemRegistry
from sch5n.game.mining import HitResult, durability_fraction, hit_tile
lazy from sch5n.world.tilemap import TileMap


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
