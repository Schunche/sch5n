# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from functools import wraps
lazy from collections.abc import Callable

lazy from sch5n.math.scalar import clamp
lazy from sch5n.math.vector import FloatTuple2


def clamp_zoom(
    rangev: tuple[float, float],
) -> Callable[
    [Callable[[Camera, float], None]], Callable[[Camera, float], None]
]:  # ruff: ignore[line-too-long]
    def decorator(
        func: Callable[[Camera, float], None],
    ) -> Callable[[Camera, float], None]:  # ruff: ignore[line-too-long]
        @wraps(func)
        def wrapper(slf: Camera, value: float) -> None:
            return func(slf, clamp(value, rangev[0], rangev[1]))

        return wrapper

    return decorator


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
    @clamp_zoom((0.25, 4.0))
    def zoom(self, value: float) -> None:
        self._zoom = value
