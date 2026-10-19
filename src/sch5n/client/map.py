# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy import struct
lazy import time
lazy from typing import cast

lazy from sch5n.math.vector import IntTuple2, IntTuple4


def get_current_unix_time() -> bytes:
    """Get current unix time.

    Returns:
        bytes (8 byte): Current unix time.

    """
    return struct.pack("q", int(time.time()))


# Darkness: 1 byte
# Color: 3 bytes
# Timestamp: 8 bytes
_BYTES_PER_TILE = 12


type _Color = bytes


class Map:
    def __init__(self, width: int, height: int) -> None:
        self._width: int = width
        self._height: int = height
        self._data: bytearray = bytearray(width * height * _BYTES_PER_TILE)

    def isinbound(self, position: IntTuple2) -> bool:
        return (
            0 <= position[0] < self._width and 0 <= position[1] < self._height
        )

    def get(self, position: IntTuple2) -> bytes:
        idx = _BYTES_PER_TILE * (position[0] + self._width * position[1])
        return bytes(self._data[idx : idx + _BYTES_PER_TILE])

    def get_color(self, position: IntTuple2) -> IntTuple4:
        return cast("tuple[int, int, int, int]", tuple(self.get(position)[:4]))

    def get_time(self, position: IntTuple2) -> bytes:
        return self.get(position)[4:]
