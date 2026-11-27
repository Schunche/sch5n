# Copyright (c) 2026 Schunche
"""Shared fixtures."""

from __future__ import annotations

import pytest

from sch5n.game.content import (
    BlockRegistry,
    BlocksFile,
    Content,
    ItemRegistry,
    ItemsFile,
)
from sch5n.utility import path
from sch5n.world.tilemap import TileMap


@pytest.fixture(scope="session")
def content() -> Content:
    """Load the real game data.

    Returns:
        Content: Blocks, items and rules from `assets/base/data`.

    """
    return Content.load(path.DATA_DIR)


@pytest.fixture
def blocks() -> BlockRegistry:
    """Register a tiny block set.

    Returns:
        BlockRegistry: Solid stone, a non solid log and a leaf turning
            into a log.

    """
    return BlockRegistry(
        BlocksFile.model_validate({
            "default_durability": 100,
            "blocks": {
                "stone": {
                    "textures": ["s"],
                    "solid": True,
                    "tool": "pickaxe",
                    "drop": "rock",
                },
                "log": {
                    "textures": ["l"],
                    "durability": 60,
                    "tool": "axe",
                    "aliases": ["oldLog"],
                },
                "leaf": {
                    "textures": ["f"],
                    "tool": "axe",
                    "transform_to": "log",
                    "particle": "leaf",
                },
            },
        })
    )


@pytest.fixture
def items(blocks: BlockRegistry) -> ItemRegistry:
    """Register items for the tiny block set.

    Returns:
        ItemRegistry: A pickaxe, an axe and two stackables.

    """
    return ItemRegistry(
        ItemsFile.model_validate({
            "items": {
                "pick": {
                    "name": "Pick",
                    "icon": "p",
                    "max_stack": 1,
                    "use_time": 2,
                    "tool_power": {"pickaxe": 40},
                },
                "axe": {
                    "name": "Axe",
                    "icon": "a",
                    "max_stack": 1,
                    "tool_power": {"axe": 30},
                },
                "rock": {
                    "name": "Rock",
                    "icon": "r",
                    "max_stack": 10,
                    "places": "stone",
                },
                "stick": {"name": "Stick", "icon": "s", "max_stack": 10},
            }
        }),
        blocks,
    )


@pytest.fixture
def tilemap(blocks: BlockRegistry) -> TileMap:
    """Create an empty map.

    Returns:
        TileMap: A map using the tiny block set.

    """
    return TileMap(blocks)


def floor(tilemap: TileMap, y: int, x0: int = -20, x1: int = 20) -> None:
    """Fill a row with stone."""
    stone = tilemap.blocks.id_of("stone")
    for x in range(x0, x1):
        tilemap.set(x, y, stone)
