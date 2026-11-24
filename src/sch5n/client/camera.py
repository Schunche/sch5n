# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from functools import wraps
lazy from collections.abc import Callable

lazy from sch5n.math.scalar import clamp
lazy from sch5n.math.vector import FloatTuple2


def _clamp_zoom(
    rangev: tuple[float, float],
) -> Callable[
    [Callable[[Camera, float], None]], Callable[[Camera, float], None]
]:
    def decorator(
        func: Callable[[Camera, float], None],
    ) -> Callable[[Camera, float], None]:
        @wraps(func)
        def wrapper(slf: Camera, value: float) -> None:
            return func(slf, clamp(value, rangev[0], rangev[1]))

        return wrapper

    return decorator


class Camera:  # ruff: ignore[undocumented-public-class]
    __slots__ = ("_pos", "_zoom")

    def __init__(self, pos: FloatTuple2, zoom: float) -> None:  # ruff: ignore[undocumented-public-init]
        self._pos = pos
        self._zoom = zoom

    @property
    def center(self) -> FloatTuple2:  # ruff: ignore[undocumented-public-method]
        return self._pos

    @property
    def zoom(self) -> float:  # ruff: ignore[undocumented-public-method]
        return self._zoom

    @zoom.setter
    @_clamp_zoom((0.25, 4.0))
    def zoom(self, value: float) -> None:
        self._zoom = value
