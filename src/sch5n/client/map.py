# Copyright (c) 2026 Schunche
"""The minimap: what the player has discovered of the world."""

from __future__ import annotations

lazy import contextlib
lazy import json
lazy import time
lazy import zlib
lazy from pathlib import Path

lazy from sch5n.log.logger import LOGGER
lazy from sch5n.math.vector import IntTuple2, IntTuple3

type _Color = IntTuple3
type _Light = int
type _Timestamp = int

type MapTile = tuple[_Color, _Light, _Timestamp]

_FILE_KEYS = frozenset({"size", "data"})


def get_current_unix_time() -> int:
    """Get current unix time.

    Returns:
        int: Current unix time.

    """
    return int(time.time())


def _encode_position(position: IntTuple2) -> str:
    return f"{position[0]};{position[1]}"


def _decode_position(key: str) -> IntTuple2:
    x, y = key.split(";")
    return int(x), int(y)


class Map:
    """Discovered map tiles: color, light level and when they were seen.

    Saved as zlib compressed JSON.
    """

    __slots__ = ("_size", "_tiles")

    def __init__(self, size: IntTuple2) -> None:
        """Create an empty map of `size` tiles.

        Raises:
            ValueError: The size is not positive.

        """
        if size[0] <= 0 or size[1] <= 0:
            msg = f"Map size must be positive, got {size}"
            raise ValueError(msg)

        self._size: IntTuple2 = size
        self._tiles: dict[IntTuple2, MapTile] = {}

    def isinbound(self, position: IntTuple2) -> bool:
        """Check whether a position lies on the map.

        Returns:
            bool: True if inside.

        """
        return (
            0 <= position[0] < self._size[0]
            and 0 <= position[1] < self._size[1]
        )

    def get(self, position: IntTuple2) -> MapTile | None:
        """Get a discovered tile.

        Returns:
            MapTile | None: The tile, `None` if undiscovered.

        """
        return self._tiles.get(position, None)

    def set(
        self,
        position: IntTuple2,
        color: _Color,
        light: _Light,
        *,
        check_bounds: bool,
    ) -> None:
        """Record a tile as seen now.

        Out of bounds positions are ignored when `check_bounds` is set.
        """
        if check_bounds and not self.isinbound(position):
            return

        self._tiles[position] = (color, light, get_current_unix_time())

    def clear(self) -> None:
        """Forget every tile."""
        self._tiles = {}

    def empty(self, position: IntTuple2) -> None:
        """Forget one tile."""
        with contextlib.suppress(KeyError):
            self._tiles.pop(position)

    def is_revealed(self, position: IntTuple2) -> bool:
        """Check whether a tile has been seen with some light.

        Returns:
            bool: True if revealed.

        """
        tile = self.get(position)
        return tile is not None and tile[1] > 0

    @staticmethod
    def _remove_corrupt_file(path: Path) -> None:
        LOGGER.error("Corrupted map file.")
        LOGGER.info("Removing corrupted map file.")
        path.unlink(missing_ok=True)

    @staticmethod
    def _decode(
        compressed: bytes,
    ) -> tuple[IntTuple2, dict[IntTuple2, MapTile]]:
        """Parse a saved map.

        Returns:
            tuple[IntTuple2, dict[IntTuple2, MapTile]]: Size and tiles.

        Raises:
            ValueError: Not a map file, or a non positive size.

        """
        data = json.loads(zlib.decompress(compressed))
        if not isinstance(data, dict) or data.keys() != _FILE_KEYS:
            msg = "Not a map file"
            raise ValueError(msg)
        width, height = (int(v) for v in data["size"])
        if width <= 0 or height <= 0:
            msg = "Map size must be positive"
            raise ValueError(msg)
        tiles: dict[IntTuple2, MapTile] = {}
        for key, (color, light, timestamp) in data["data"].items():
            r, g, b = color
            tiles[_decode_position(key)] = (
                (int(r), int(g), int(b)),
                int(light),
                int(timestamp),
            )
        return (width, height), tiles

    def load(self, path: Path, backup_path: Path | None = None) -> None:
        """Replace this map with a saved one.

        A missing file falls back to `backup_path`. A corrupt file is
        deleted and leaves this map unchanged.
        """
        if not path.exists():
            LOGGER.info("Tried to load non-existing map.")
            if backup_path is not None:
                LOGGER.info("Trying to load backup.")
                self.load(backup_path)
            else:
                LOGGER.info("No backup path was given.")
            return

        try:
            self._size, self._tiles = Map._decode(path.read_bytes())
        except zlib.error, TypeError, ValueError, KeyError, AttributeError:
            Map._remove_corrupt_file(path)

    def save(self, path: Path) -> None:
        """Write the map, creating parent directories."""
        json_bytes = json.dumps({
            "size": self._size,
            "data": {
                _encode_position(position): tile
                for position, tile in self._tiles.items()
            },
        }).encode(encoding="utf-8")
        compressed = zlib.compress(json_bytes, level=1)

        LOGGER.debug(
            "Saving map with compression ratio: %s",
            len(compressed) / len(json_bytes),
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)
