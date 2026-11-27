# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import ParamSpec, TypeVar
lazy from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


def instant_call(func: Callable[[], None]) -> Callable[[], None]:
    """Evaluate a function instantly.

    Returns:
        Callable[[], None]: `func` itself, after calling it once.

    """
    return (func, func())[0]
