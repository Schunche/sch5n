# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
lazy import contextlib
lazy import json
lazy import time
lazy from pathlib import Path
lazy from typing import cast

lazy import zstandard

lazy from sch5n.math.vector import (
    IntTuple2,
    IntTuple3,
    deserialize_int_tuple_2,
    parse_int_tuple2,
    parse_int_tuple3,
    serialize_int_tuple_2,
)

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


type _Color = IntTuple3
type _Light = int
type _Timestamp = int

type MapTile = tuple[_Color, _Light, _Timestamp]


def get_current_unix_time() -> int:
    """Get current unix time.

    Returns:
        int: Current unix time.

    """
    return int(time.time())


class Map:
    __slots__ = ("_size", "_tiles")

    def __init__(self, size: IntTuple2) -> None:
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError

        self._size: IntTuple2 = size
        self._tiles: dict[IntTuple2, MapTile] = {}

    def isinbound(self, position: IntTuple2) -> bool:
        return (
            0 <= position[0] < self._size[0]
            and 0 <= position[1] < self._size[1]
        )

    def get(self, position: IntTuple2) -> MapTile | None:
        return self._tiles.get(position, None)

    def set(
        self,
        position: IntTuple2,
        color: _Color,
        light: _Light,
        *,
        check_bounds: bool,
    ) -> None:
        if check_bounds and self.isinbound(position):
            return

        self._tiles[position] = (color, light, get_current_unix_time())

    def _set_unchecked_timed(
        self, position: IntTuple2, map_tile: MapTile
    ) -> None:
        self._tiles[position] = map_tile

    def clear(self) -> None:
        self._tiles = {}

    def empty(self, position: IntTuple2) -> None:
        with contextlib.suppress(KeyError):
            self._tiles.pop(position)

    def is_revealed(self, position: IntTuple2) -> bool:
        tile = self.get(position)
        return tile is not None and tile[1] > 0

    @staticmethod
    def _remove_corrupt_file(path: Path) -> None:
        _logger.error("Corrupted map file.")
        _logger.info("Removing corrupted map file.")
        path.unlink(missing_ok=True)

    def load(self, path: Path) -> None:
        if not path.exists():
            _logger.info("Tried to load non-existing map.")
            return

        with path.open("rb") as file:
            compressed = file.read()

        decompressed = zstandard.decompress(compressed)
        json_data = json.loads(decompressed)

        try:
            size = json_data.get("size", None)
            data = json_data.get("data", None)
        except AttributeError:
            Map._remove_corrupt_file(path)
            return

        if len(json_data) != 2 or size is None or data is None:  # ruff: ignore[magic-value-comparison]
            Map._remove_corrupt_file(path)
            return

        try:
            other = Map(cast("IntTuple2", size))
            for position, map_tile in cast(
                "dict[str, tuple[IntTuple3, int, int]]", data
            ).items():
                other._set_unchecked_timed(
                    deserialize_int_tuple_2(position),
                    (map_tile[0], map_tile[1], map_tile[2]),
                )

        except Exception:  # ruff: ignore[blind-except]
            Map._remove_corrupt_file(path)

        else:
            self._size = other._size
            self._tiles = other._tiles

    def save(self, path: Path) -> None:
        json_data = {  # pyright: ignore[reportUnknownVariableType]
            "size": self._size,
            "data": {
                serialize_int_tuple_2(k): v for k, v in self._tiles.items()
            },
        }

        json_bytes = json.dumps(json_data).encode(encoding="utf-8")
        compressed = zstandard.compress(json_bytes, level=1)

        _logger.debug(
            "Saving map with compression ratio: %s",
            len(compressed) / len(json_bytes),
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)
