# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import ParamSpec, TypeVar
lazy from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")


def instant_call(func: Callable[[], None]) -> Callable[[], None]:
    """Evaluate a function instantly."""  # ruff: ignore[docstring-missing-returns]
    return (func, func())[0]
