# Copyright (c) 2026 Schunche
"""Rectangles and scalar helpers."""

from sch5n.math.rect import Rect
from sch5n.math.scalar import clamp, sign_or_zero


def test_rect_edges() -> None:
    """Edges and center follow from position and size."""
    r = Rect(1, 2, 3, 4)
    assert (r.left, r.top, r.right, r.bottom) == (1, 2, 4, 6)
    assert r.center == (2.5, 4)


def test_touching_rects_do_not_collide() -> None:
    """Only a positive overlap counts as a collision."""
    assert not Rect(0, 0, 10, 10).collides(Rect(10, 0, 10, 10))
    assert Rect(0, 0, 10, 10).collides(Rect(9.5, 9.5, 10, 10))


def test_contains_point_is_half_open() -> None:
    """The far edges are not inside."""
    r = Rect(0, 0, 10, 10)
    assert r.contains_point(0, 0)
    assert not r.contains_point(10, 5)


def test_inflated() -> None:
    """Inflating grows every side."""
    assert Rect(5, 5, 10, 10).inflated(2) == Rect(3, 3, 14, 14)


def test_scalars() -> None:
    """Clamping works with swapped bounds, signs include zero."""
    high = 3
    assert clamp(5, 0, high) == high
    assert clamp(5, high, 0) == high
    assert sign_or_zero(-0.5) == -1
    assert sign_or_zero(0) == 0
