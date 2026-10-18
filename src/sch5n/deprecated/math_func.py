# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from math import cos, pi

lazy from sch5n.math.scalar import sign_or_zero
lazy from sch5n.math.vector import FloatTuple2


def player_magnet_func(distance: FloatTuple2) -> FloatTuple2:
    """How much should the item move relative to player.

    Returns:
       FloatTuple2: (x, y) E [-1; 1]

    """
    x, y = distance[0], distance[1]
    return (
        (cos(pi * x) ** 2 - 1) * sign_or_zero(x),
        (cos(pi * y) ** 2 - 1) * sign_or_zero(y),
    )
