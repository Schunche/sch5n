# Copyright (c) 2026 Schunche
"""Reading and writing tilemaps.

The format is the one of the original game: a JSON object mapping
`"x;y"` to `{"block": name, "variant": int}`.
"""

from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import TYPE_CHECKING

from sch5n.error.exceptions import ParseError
from sch5n.utility.path import MAPS_DIR
from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from sch5n.game.content import BlockRegistry
    from sch5n.vendor.json import Json


DEFAULT_MAP = "map1"
"""Map played when none is chosen."""


def map_file(name: str) -> Path:
    """Resolve a map argument: a path, or the name of a bundled map.

    Returns:
        Path: The map file.

    """
    candidate = Path(name)
    if candidate.suffix == ".json" or candidate.exists():
        return candidate
    return MAPS_DIR / f"{name}.json"


def _parse_key(key: str) -> tuple[int, int]:
    try:
        x, y = key.split(";")
        return int(x), int(y)
    except ValueError:
        msg = f"Invalid tile coordinate: {key!r}"
        raise ParseError(msg) from None


def tilemap_from_json(data: Json, blocks: BlockRegistry) -> TileMap:
    """Build a tilemap from decoded JSON.

    Returns:
        TileMap: The map.

    Raises:
        ParseError: The data does not describe a tilemap.

    """
    if not isinstance(data, dict):
        msg = "A tilemap must be a JSON object."
        raise ParseError(msg)

    tilemap = TileMap(blocks)
    for key, tile in data.items():
        x, y = _parse_key(key)
        if not isinstance(tile, dict) or not isinstance(
            name := tile.get("block"), str
        ):
            msg = f"Invalid tile at {key!r}: {tile!r}"
            raise ParseError(msg)
        variant = tile.get("variant", 0)
        if not isinstance(variant, int):
            msg = f"Invalid variant at {key!r}: {variant!r}"
            raise ParseError(msg)
        try:
            block = blocks.id_of(name)
        except KeyError as e:
            raise ParseError(str(e)) from None
        tilemap.set(x, y, block, variant)
    return tilemap


def tilemap_to_json(tilemap: TileMap) -> dict[str, dict[str, str | int]]:
    """Encode a tilemap as JSON compatible data, sorted for stable diffs.

    Returns:
        dict[str, dict[str, str | int]]: The encoded map.

    """
    out: dict[str, dict[str, str | int]] = {}
    for x, y, block, variant in sorted(
        tilemap.iter_tiles(), key=operator.itemgetter(1, 0)
    ):
        definition = tilemap.blocks.get(block)
        if definition is None:
            continue
        out[f"{x};{y}"] = {"block": definition.name, "variant": variant}
    return out


def load_tilemap(path: Path, blocks: BlockRegistry) -> TileMap:
    """Read a tilemap file.

    Returns:
        TileMap: The map.

    """
    return tilemap_from_json(
        json.loads(path.read_text(encoding="utf-8")), blocks
    )


def save_tilemap(path: Path, tilemap: TileMap) -> None:
    """Write a tilemap file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(tilemap_to_json(tilemap), separators=(",", ":")),
        encoding="utf-8",
    )
