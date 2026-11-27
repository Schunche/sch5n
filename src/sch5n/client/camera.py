# Copyright (c) 2026 Schunche
"""The 2D camera: what part of the world is on screen."""

from __future__ import annotations

from sch5n.math.rect import Rect
from sch5n.math.scalar import clamp

MIN_ZOOM = 0.25
MAX_ZOOM = 4.0


class Camera:
    """Maps world pixels to screen pixels.

    The camera remembers the world point in the middle of the screen, so
    resizing the window keeps that point in the middle. Everything that
    depends on the window size takes the screen size.
    """

    __slots__ = ("_zoom", "center_x", "center_y")

    def __init__(
        self, center: tuple[float, float] = (0.0, 0.0), zoom: float = 1.0
    ) -> None:
        """Create a camera looking at `center`."""
        self.center_x, self.center_y = center
        self._zoom = clamp(zoom, MIN_ZOOM, MAX_ZOOM)

    @classmethod
    def showing_top_left(
        cls, point: tuple[float, float], screen: tuple[float, float]
    ) -> Camera:
        """Create a camera with `point` at the top left of the screen.

        Returns:
            Camera: The camera, at zoom 1.

        """
        return cls((point[0] + screen[0] / 2, point[1] + screen[1] / 2))

    @property
    def center(self) -> tuple[float, float]:
        """World position in the middle of the screen."""
        return (self.center_x, self.center_y)

    @property
    def zoom(self) -> float:
        """Scale factor, clamped to [MIN_ZOOM, MAX_ZOOM]."""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        self._zoom = clamp(value, MIN_ZOOM, MAX_ZOOM)

    def top_left(self, screen: tuple[float, float]) -> tuple[float, float]:
        """World position at the top left corner of the screen.

        Returns:
            tuple[float, float]: World position.

        """
        return (
            self.center_x - screen[0] / self._zoom / 2,
            self.center_y - screen[1] / self._zoom / 2,
        )

    def offset(self, screen: tuple[float, float]) -> tuple[float, float]:
        """Top left world position snapped to whole screen pixels.

        Returns:
            tuple[float, float]: Offset for rendering.

        """
        x, y = self.top_left(screen)
        return (
            round(x * self._zoom) / self._zoom,
            round(y * self._zoom) / self._zoom,
        )

    def view(self, screen: tuple[float, float]) -> Rect:
        """Visible world area.

        Returns:
            Rect: In world pixels.

        """
        x, y = self.top_left(screen)
        return Rect(x, y, screen[0] / self._zoom, screen[1] / self._zoom)

    def screen_to_world(
        self, pos: tuple[float, float], screen: tuple[float, float]
    ) -> tuple[float, float]:
        """Convert a screen position to world pixels.

        Returns:
            tuple[float, float]: World position.

        """
        x, y = self.top_left(screen)
        return (x + pos[0] / self._zoom, y + pos[1] / self._zoom)

    def center_on(self, point: tuple[float, float]) -> None:
        """Put a world point in the middle of the screen immediately."""
        self.center_x, self.center_y = point

    def follow(self, point: tuple[float, float], factor: float) -> None:
        """Move a `factor` fraction of the way towards centering `point`."""
        self.center_x += (point[0] - self.center_x) * factor
        self.center_y += (point[1] - self.center_y) * factor

    def pan(self, dx: float, dy: float) -> None:
        """Move by world pixels."""
        self.center_x += dx
        self.center_y += dy

    def zoom_at(
        self,
        factor: float,
        pivot: tuple[float, float],
        screen: tuple[float, float],
    ) -> None:
        """Zoom while keeping the world point under screen `pivot` fixed."""
        before = self.screen_to_world(pivot, screen)
        self.zoom = self._zoom * factor
        after = self.screen_to_world(pivot, screen)
        self.pan(before[0] - after[0], before[1] - after[1])
