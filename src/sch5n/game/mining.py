# Copyright (c) 2026 Schunche
"""Breaking and placing blocks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from sch5n.game.content import AIR, TreePart
from sch5n.game.plants import can_stand

if TYPE_CHECKING:
    from sch5n.game.content import BlockDef, BlockRegistry, ItemDef
    from sch5n.world.tilemap import TileMap


class HitResult(Enum):
    """Outcome of hitting a tile."""

    NOTHING = auto()
    """No tile, or no tool."""
    WRONG_TOOL = auto()
    DAMAGED = auto()
    BROKEN = auto()
    TRIMMED = auto()
    """Turned into its trimmed block, like a leafy log into a log."""


@dataclass(frozen=True, slots=True)
class Hit:
    """What happened when a tile was hit."""

    result: HitResult
    block: BlockDef | None = None
    """The block that was hit."""


def tool_power(tool: ItemDef | None, block: BlockDef) -> int:
    """How much durability one hit with `tool` removes from `block`.

    The block's own tool type hits with full power; its `slower_tools`
    with a part of it.

    Returns:
        int: 0 if the tool cannot break the block.

    """
    spec = block.spec
    if tool is None or spec.tool is None:
        return 0
    powers = tool.spec.tool_power
    if spec.tool in powers:
        power = powers[spec.tool]
        return power if power >= spec.min_power else 0
    slower = max(
        (powers.get(kind, 0) for kind in spec.slower_tools), default=0
    )
    return int(slower * spec.slower_tool_power)


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

    A broken block turns into its `transform_to` block, or air. A tool that
    trims the block wears its trim durability down instead, then turns it
    into its trimmed block.

    Returns:
        Hit: The outcome.

    """
    block = tilemap.blocks.get(tilemap.get(x, y))
    if block is None or tool is None or not tool.is_tool:
        return Hit(HitResult.NOTHING, block)

    trim = block.spec.trim
    if trim is not None and (power := tool.spec.tool_power.get(trim.tool, 0)):
        remaining = tilemap.damage.get((x, y), trim.durability) - power
        if remaining > 0:
            tilemap.damage[x, y] = remaining
            return Hit(HitResult.DAMAGED, block)
        variant = tilemap.get_variant(x, y)
        tilemap.set(x, y, tilemap.blocks.id_of(trim.into), variant)
        return Hit(HitResult.TRIMMED, block)

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


CROWN_REACH = 3
"""Leaves this many tiles beside a trunk fall with its tree."""


def fell_tree(
    tilemap: TileMap, x: int, y: int
) -> list[tuple[BlockDef, tuple[int, int]]]:
    """Bring down the tree above a trunk tile that was just broken.

    The rest of the trunk above, in the same column, and the leaves joined
    to it within `CROWN_REACH` tiles beside it are removed. Other trees'
    trunks stay, and so do their crowns beyond that reach.

    Returns:
        list[tuple[BlockDef, tuple[int, int]]]: The removed blocks and
        where they were.

    """
    blocks = tilemap.blocks
    removed: list[tuple[BlockDef, tuple[int, int]]] = []
    seen = {(x, y)}
    todo = [(x, y - 1)]
    while todo:
        tx, ty = todo.pop()
        if (tx, ty) in seen or ty >= y:
            continue
        seen.add((tx, ty))
        block = blocks.get(tilemap.get(tx, ty))
        if block is None or block.spec.tree is None:
            continue
        if block.spec.tree is TreePart.TRUNK and tx != x:
            continue
        if abs(tx - x) > CROWN_REACH:
            continue
        removed.append((block, (tx, ty)))
        tilemap.set(tx, ty, AIR)
        todo += [(tx, ty - 1), (tx - 1, ty), (tx + 1, ty)]
    return removed


def log_of(blocks: BlockRegistry, block: BlockDef) -> str | None:
    """Name the item a felled block gives: its drop, or its stripped form's.

    Returns:
        str | None: Item id, `None` for leaves.

    """
    if block.spec.drop is not None:
        return block.spec.drop
    if block.spec.transform_to is not None:
        return blocks.by_name(block.spec.transform_to).spec.drop
    return None


def can_place(
    tilemap: TileMap, x: int, y: int, block: BlockDef | None = None
) -> bool:
    """Whether a block may be placed at a tile.

    The tile must be empty, with a solid block or a log above, below, left
    or right of it, so nothing is built in thin air. A plant instead needs
    ground it grows on right below.

    Returns:
        bool: True if a block may go there.

    """
    if tilemap.get(x, y) != AIR:
        return False
    if block is not None and block.spec.plant_on:
        return can_stand(tilemap, x, y, block)
    return any(
        _supports(tilemap, x + dx, y + dy)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
    )


def _supports(tilemap: TileMap, x: int, y: int) -> bool:
    """Whether blocks can be built against a tile.

    Solid blocks, logs, crafting stations and ladders can.

    Returns:
        bool: True for support.

    """
    if tilemap.is_solid(x, y):
        return True
    block = tilemap.blocks.get(tilemap.get(x, y))
    return block is not None and (
        block.spec.tree is TreePart.TRUNK
        or block.spec.crafting_side is not None
        or block.spec.climbable
    )
