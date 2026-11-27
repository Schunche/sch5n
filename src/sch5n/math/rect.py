# Copyright (c) 2026 Schunche
"""Axis aligned rectangles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Rect:
    """Axis aligned rectangle with float coordinates.

    The y axis grows downwards, like on screen.
    """

    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        """Left edge."""
        return self.x

    @property
    def right(self) -> float:
        """Right edge."""
        return self.x + self.w

    @property
    def top(self) -> float:
        """Top edge."""
        return self.y

    @property
    def bottom(self) -> float:
        """Bottom edge."""
        return self.y + self.h

    @property
    def center(self) -> tuple[float, float]:
        """Center point."""
        return (self.x + self.w / 2, self.y + self.h / 2)

    def collides(self, other: Rect) -> bool:
        """Whether the two rectangles overlap with a positive area.

        Returns:
            bool: Touching edges do not count as overlap.

        """
        return (
            self.x < other.x + other.w
            and other.x < self.x + self.w
            and self.y < other.y + other.h
            and other.y < self.y + self.h
        )

    def contains_point(self, x: float, y: float) -> bool:
        """Whether the point lies inside (half-open on the far edges).

        Returns:
            bool: True if inside.

        """
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def moved(self, dx: float, dy: float) -> Rect:
        """Copy translated by (dx, dy).

        Returns:
            Rect: A new rectangle.

        """
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def inflated(self, amount: float) -> Rect:
        """Copy grown by `amount` on every side.

        Returns:
            Rect: A new rectangle.

        """
        return Rect(
            self.x - amount,
            self.y - amount,
            self.w + 2 * amount,
            self.h + 2 * amount,
        )
