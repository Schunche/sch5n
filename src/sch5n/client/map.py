# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy import contextlib
lazy import json
lazy import pickle  # ruff: ignore[suspicious-pickle-import]
lazy import time
lazy import zlib
lazy from pathlib import Path
lazy from typing import cast

lazy from sch5n.log.logger import LOGGER
lazy from sch5n.math.vector import IntTuple2, IntTuple3

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


class Map:  # ruff: ignore[undocumented-public-class]
    __slots__ = ("_size", "_tiles")

    def __init__(self, size: IntTuple2) -> None:  # ruff: ignore[undocumented-public-init]
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError

        self._size: IntTuple2 = size
        self._tiles: dict[IntTuple2, MapTile] = {}

    def isinbound(self, position: IntTuple2) -> bool:  # ruff: ignore[undocumented-public-method]
        return (
            0 <= position[0] < self._size[0]
            and 0 <= position[1] < self._size[1]
        )

    def get(self, position: IntTuple2) -> MapTile | None:  # ruff: ignore[undocumented-public-method]
        return self._tiles.get(position, None)

    def set(  # ruff: ignore[undocumented-public-method]
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

    def clear(self) -> None:  # ruff: ignore[undocumented-public-method]
        self._tiles = {}

    def empty(self, position: IntTuple2) -> None:  # ruff: ignore[undocumented-public-method]
        with contextlib.suppress(KeyError):
            self._tiles.pop(position)

    def is_revealed(self, position: IntTuple2) -> bool:  # ruff: ignore[undocumented-public-method]
        tile = self.get(position)
        return tile is not None and tile[1] > 0

    @staticmethod
    def _remove_corrupt_file(path: Path) -> None:
        LOGGER.error("Corrupted map file.")
        LOGGER.info("Removing corrupted map file.")
        path.unlink(missing_ok=True)

    def load(self, path: Path, backup_path: Path | None = None) -> None:  # ruff: ignore[undocumented-public-method]
        if not path.exists():
            LOGGER.info("Tried to load non-existing map.")
            if backup_path is not None:
                LOGGER.info("Trying to load backup.")
                self.load(backup_path)
            else:
                LOGGER.info("No backup path was given.")
            return

        with path.open("rb") as file:
            compressed = file.read()

        decompressed = zlib.decompress(compressed)
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
                    pickle.loads(position),  # ruff: ignore[suspicious-pickle-usage] # pyright: ignore[reportArgumentType]
                    (map_tile[0], map_tile[1], map_tile[2]),
                )

        except Exception:  # ruff: ignore[blind-except]
            Map._remove_corrupt_file(path)

        else:
            self._size = other._size
            self._tiles = other._tiles

    def save(self, path: Path) -> None:  # ruff: ignore[undocumented-public-method]
        json_data = {  # pyright: ignore[reportUnknownVariableType]
            "size": self._size,
            "data": {pickle.dumps(k): v for k, v in self._tiles.items()},
        }

        json_bytes = json.dumps(json_data).encode(encoding="utf-8")
        compressed = zlib.compress(json_bytes, level=1)

        LOGGER.debug(
            "Saving map with compression ratio: %s",
            len(compressed) / len(json_bytes),
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)
