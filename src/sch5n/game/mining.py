# Copyright (c) 2026 Schunche
"""Breaking and placing blocks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from sch5n.game.content import AIR

if TYPE_CHECKING:
    from sch5n.game.content import BlockDef, ItemDef
    from sch5n.world.tilemap import TileMap


class HitResult(Enum):
    """Outcome of hitting a tile."""

    NOTHING = auto()
    """No tile, or no tool."""
    WRONG_TOOL = auto()
    DAMAGED = auto()
    BROKEN = auto()


@dataclass(frozen=True, slots=True)
class Hit:
    """What happened when a tile was hit."""

    result: HitResult
    block: BlockDef | None = None
    """The block that was hit."""


def tool_power(tool: ItemDef | None, block: BlockDef) -> int:
    """How much durability one hit with `tool` removes from `block`.

    Returns:
        int: 0 if the tool cannot break the block.

    """
    if tool is None or block.spec.tool is None:
        return 0
    return tool.spec.tool_power.get(block.spec.tool, 0)


def durability_fraction(tilemap: TileMap, x: int, y: int) -> float:
    """Remaining durability of a tile, 1.0 when undamaged.

    Returns:
        float: Value in [0, 1].

    """
    remaining = tilemap.damage.get((x, y))
    if remaining is None:
        return 1.0
    block = tilemap.blocks.get(tilemap.get(x, y))
    if block is None:
        return 1.0
    return max(remaining, 0) / block.durability


def hit_tile(tilemap: TileMap, x: int, y: int, tool: ItemDef | None) -> Hit:
    """Hit a tile with a tool, breaking it once its durability runs out.

    A broken block turns into its `transform_to` block, or air.

    Returns:
        Hit: The outcome.

    """
    block = tilemap.blocks.get(tilemap.get(x, y))
    if block is None or tool is None or not tool.is_tool:
        return Hit(HitResult.NOTHING, block)

    power = tool_power(tool, block)
    if power <= 0:
        return Hit(HitResult.WRONG_TOOL, block)

    remaining = tilemap.damage.get((x, y), block.durability) - power
    if remaining > 0:
        tilemap.damage[x, y] = remaining
        return Hit(HitResult.DAMAGED, block)

    variant = tilemap.get_variant(x, y)
    if block.spec.transform_to is not None:
        tilemap.set(
            x, y, tilemap.blocks.id_of(block.spec.transform_to), variant
        )
    else:
        tilemap.set(x, y, AIR)
    return Hit(HitResult.BROKEN, block)


def can_place(tilemap: TileMap, x: int, y: int) -> bool:
    """Whether a block may be placed: the tile must be empty.

    Returns:
        bool: True if empty.

    """
    return tilemap.get(x, y) == AIR
