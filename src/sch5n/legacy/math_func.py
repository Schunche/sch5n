# Copyright (c) 2026 Schunche
"""Experimental software."""

import math


def get_hypotenuse(side1: float, side2: float) -> float:
    """Hypotenuse of a right triangle given two sides."""
    return math.sqrt(side1**2 + side2**2)


def player_magnet_func(distance: tuple[float, float]) -> tuple[float, float]:
    """How much should the item move relative to player.

    Returns:
        tuple[float]: (x, y) E [-1; 1]

    """
    x, y = distance
    return (
        (math.cos(math.pi * x) ** 2 - 1)
        * ((-1) if x > 0 else (0 if x == 0 else 1)),
        (math.cos(math.pi * y) ** 2 - 1)
        * ((-1) if y > 0 else (0 if y == 0 else 1)),
    )
