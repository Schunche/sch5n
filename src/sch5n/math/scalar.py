# Copyright (c) 2026 Schunche
"""Experimental software."""

from math import signbit
from typing import Literal


def avg(*values: float) -> float:
    """Mean average of numbers.

    Returns:
        float: Mean average.

    """
    if not values:
        return 0
    return sum(values) / len(values)


def sign_or_zero(x: float) -> Literal[-1, 0, 1]:
    """Sign of x or zero.

    Returns:
        -1 | 0 | 1: The sign or zero.

    """
    return -1 if signbit(x) else (0 if x == 0 else 1)


def clamp(value: float, minv: float, maxv: float) -> float:
    """Clamp value.

    minv <= value <= maxv

    Returns:
        float: Clamped value.

    """
    if maxv < minv:
        return clamp(value, maxv, minv)

    return min(max(minv, value), maxv)
