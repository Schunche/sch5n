# Copyright (c) 2026 Schunche
"""Experimental software."""

import secrets
lazy from collections.abc import Callable


def randf() -> float:
    """Generate a random float in the range [0.0, 1.0).

    Returns:
        float: Generated number

    """
    return secrets.randbits(53) / 2**53


randbelow: Callable[[int], int] = secrets.randbelow


def randint(a: int, b: int) -> int:
    """Generate a random float in the range [a, b].

    Returns:
        int: Generated number

    """
    if a > b:
        return randint(b, a)

    return randbelow(b - a + 1) + a


def choice[T](iterable: list[T]) -> T:
    """Choose a random element from a non-empty sequence.

    Returns:
        T: Random item.

    """
    return secrets.choice(iterable)
