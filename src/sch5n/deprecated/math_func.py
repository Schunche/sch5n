# Copyright (c) 2026 Schunche
"""Experimental software."""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sch5n.math.vector import FloatTuple2


def player_magnet_func(distance: FloatTuple2) -> FloatTuple2:
    """How much should the item move relative to player.

    Returns:
       FloatTuple2: (x, y) E [-1; 1]

    """
    x, y = distance[0], distance[1]
    return (
        (math.cos(math.pi * x) ** 2 - 1)
        * ((-1) if x > 0 else (0 if x == 0 else 1)),
        (math.cos(math.pi * y) ** 2 - 1)
        * ((-1) if y > 0 else (0 if y == 0 else 1)),
    )
