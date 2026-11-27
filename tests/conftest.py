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
    """The real game data."""
    return Content.load(path.DATA_DIR)


@pytest.fixture
def blocks() -> BlockRegistry:
    """Solid stone, a non solid log and a leaf turning into a log."""
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
    """Items matching `blocks`."""
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
    """An empty map."""
    return TileMap(blocks)


def floor(tilemap: TileMap, y: int, x0: int = -20, x1: int = 20) -> None:
    """Fill a row with stone."""
    stone = tilemap.blocks.id_of("stone")
    for x in range(x0, x1):
        tilemap.set(x, y, stone)
