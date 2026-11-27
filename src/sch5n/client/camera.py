# Copyright (c) 2026 Schunche
"""The 2D camera: what part of the world is on screen."""

from __future__ import annotations

from sch5n.math.rect import Rect
from sch5n.math.scalar import clamp

MIN_ZOOM = 0.25
MAX_ZOOM = 4.0


class Camera:
    """Maps world pixels to screen pixels.

    `x`, `y` is the world position shown at the top left of the screen.
    """

    __slots__ = ("_zoom", "x", "y")

    def __init__(
        self, x: float = 0.0, y: float = 0.0, zoom: float = 1.0
    ) -> None:
        """Create a camera."""
        self.x = x
        self.y = y
        self._zoom = clamp(zoom, MIN_ZOOM, MAX_ZOOM)

    @property
    def zoom(self) -> float:
        """Scale factor, clamped to [MIN_ZOOM, MAX_ZOOM]."""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        self._zoom = clamp(value, MIN_ZOOM, MAX_ZOOM)

    def offset(self) -> tuple[float, float]:
        """Camera position snapped to whole screen pixels.

        Returns:
            tuple[float, float]: Offset for rendering.

        """
        return (
            round(self.x * self._zoom) / self._zoom,
            round(self.y * self._zoom) / self._zoom,
        )

    def view(self, screen: tuple[float, float]) -> Rect:
        """Visible world area.

        Returns:
            Rect: In world pixels.

        """
        return Rect(
            self.x, self.y, screen[0] / self._zoom, screen[1] / self._zoom
        )

    def screen_to_world(self, pos: tuple[float, float]) -> tuple[float, float]:
        """Convert a screen position to world pixels.

        Returns:
            tuple[float, float]: World position.

        """
        return (self.x + pos[0] / self._zoom, self.y + pos[1] / self._zoom)

    def center_on(
        self, point: tuple[float, float], screen: tuple[float, float]
    ) -> None:
        """Put a world point in the middle of the screen immediately."""
        self.x = point[0] - screen[0] / self._zoom / 2
        self.y = point[1] - screen[1] / self._zoom / 2

    def follow(
        self,
        point: tuple[float, float],
        screen: tuple[float, float],
        factor: float,
    ) -> None:
        """Move a `factor` fraction of the way towards centering `point`."""
        target_x = point[0] - screen[0] / self._zoom / 2
        target_y = point[1] - screen[1] / self._zoom / 2
        self.x += (target_x - self.x) * factor
        self.y += (target_y - self.y) * factor

    def zoom_at(self, factor: float, pivot: tuple[float, float]) -> None:
        """Zoom while keeping the world point under screen `pivot` fixed."""
        before = self.screen_to_world(pivot)
        self.zoom = self._zoom * factor
        self.x = before[0] - pivot[0] / self._zoom
        self.y = before[1] - pivot[1] / self._zoom
