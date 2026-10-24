# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from sch5n.math.scalar import clamp
lazy from sch5n.math.vector import FloatTuple2

_MIN_ZOOM = 0.25
_MAX_ZOOM = 4.0


class Camera:
    __slots__ = ("_pos", "_zoom")

    def __init__(self, pos: FloatTuple2, zoom: float) -> None:
        self._pos = pos
        self._zoom = zoom

    @property
    def center(self) -> FloatTuple2:
        return self._pos

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        self._zoom = clamp(value, _MIN_ZOOM, _MAX_ZOOM)
