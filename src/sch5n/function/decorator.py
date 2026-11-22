# Copyright (c) 2026 Schunche
"""Experimental software."""

from functools import wraps
from typing import ParamSpec
lazy from collections.abc import Callable

from sch5n.math.scalar import clamp
from sch5n.math.vector import FloatTuple2


def instant_call(func: Callable[[], None]) -> Callable[[], None]:
    return (func, func())[0]


def clamped(
    rangev: FloatTuple2,
) -> Callable[[Callable[[float], None]], Callable[[float], None]]:
    def decorator(func: Callable[[float], None]) -> Callable[[float], None]:
        @wraps(func)
        def wrapper(x: float) -> None:
            return func(clamp(x, rangev[0], rangev[1]))

        return wrapper

    return decorator
