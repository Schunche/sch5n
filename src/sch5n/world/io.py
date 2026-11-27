# Copyright (c) 2026 Schunche
"""Reading and writing tilemaps.

The format is the one of the original game: a JSON object mapping
`"x;y"` to `{"block": name, "variant": int}`.
"""

from __future__ import annotations

import errno
import json
import operator
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sch5n.error.exceptions import ParseError
from sch5n.log.logger import LOGGER
from sch5n.utility.path import MAPS_DIR, is_developing
from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from sch5n.game.content import BlockRegistry
    from sch5n.vendor.json import Json


DEFAULT_MAP = "map1"
"""Map played when none is chosen.

It also seeds new worlds and servers and is the main menu background, so
it is protected: it only changes while developing (see `is_developing`),
tools only overwrite it when asked to, and its previous version is backed
up first.
"""
BACKUP_DIR = "backups"
"""Folder next to a protected map holding its earlier versions, ignored by
git."""


class BackupError(OSError):
    """A protected map could not be backed up, so it was not saved."""


def map_file(name: str) -> Path:
    """Resolve a map argument: a path, or the name of a bundled map.

    Returns:
        Path: The map file.

    """
    candidate = Path(name)
    if candidate.suffix == ".json" or candidate.exists():
        return candidate
    return MAPS_DIR / f"{name}.json"


def is_protected(path: Path) -> bool:
    """Whether a file is the default map, however its path is written.

    Returns:
        bool: True for the default map.

    """
    default = MAPS_DIR / f"{DEFAULT_MAP}.json"
    if path.exists() and default.exists():
        return path.samefile(default)
    return path.resolve() == default.resolve()


def backup_map(path: Path) -> Path:
    """Copy a map into the backup folder next to it, never replacing one.

    Returns:
        Path: The new backup.

    """
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    target = path.parent / BACKUP_DIR / f"{path.stem}-{stamp}.json"
    target.parent.mkdir(exist_ok=True)
    with target.open("xb") as file:
        file.write(path.read_bytes())
    return target


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
    """Write a tilemap file, creating parent directories.

    A protected map is backed up before it changes. If that fails, the map
    is left as it was.

    Raises:
        PermissionError: The map is protected and this is not development.
        BackupError: The map is protected and could not be backed up.

    """
    if is_protected(path) and not is_developing():
        raise PermissionError(
            errno.EACCES, "the default map is read-only", str(path)
        )
    text = json.dumps(tilemap_to_json(tilemap), separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if (
        is_protected(path)
        and path.exists()
        and path.read_bytes() != text.encode()
    ):
        try:
            backup = backup_map(path)
        except OSError as error:
            raise BackupError(
                error.errno, error.strerror, error.filename
            ) from error
        LOGGER.info("Backed up %s to %s", path.name, backup)
    path.write_text(text, encoding="utf-8")
