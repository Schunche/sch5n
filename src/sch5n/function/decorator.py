# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from collections.abc import Callable


def instant_call(func: Callable[[], None]) -> Callable[[], None]:
    return (func, func())[0]
