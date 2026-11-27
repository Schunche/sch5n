# Copyright (c) 2026 Schunche
"""Rectangles and scalar helpers."""

from sch5n.math.rect import Rect
from sch5n.math.scalar import clamp, sign_or_zero


def test_rect_edges() -> None:
    r = Rect(1, 2, 3, 4)
    assert (r.left, r.top, r.right, r.bottom) == (1, 2, 4, 6)
    assert r.center == (2.5, 4)


def test_touching_rects_do_not_collide() -> None:
    assert not Rect(0, 0, 10, 10).collides(Rect(10, 0, 10, 10))
    assert Rect(0, 0, 10, 10).collides(Rect(9.5, 9.5, 10, 10))


def test_contains_point_is_half_open() -> None:
    r = Rect(0, 0, 10, 10)
    assert r.contains_point(0, 0)
    assert not r.contains_point(10, 5)


def test_inflated() -> None:
    assert Rect(5, 5, 10, 10).inflated(2) == Rect(3, 3, 14, 14)


def test_scalars() -> None:
    assert clamp(5, 0, 3) == 3
    assert clamp(5, 3, 0) == 3
    assert sign_or_zero(-0.5) == -1
    assert sign_or_zero(0) == 0
