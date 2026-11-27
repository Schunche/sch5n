# Copyright (c) 2026 Schunche
"""Video options offered in the settings screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

WINDOW_SIZES: tuple[tuple[int, int], ...] = (
    (1024, 576),
    (1280, 720),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
)
FPS_LIMITS: tuple[int, ...] = (30, 60, 75, 120, 144, 165, 240, 0)
"""Frame caps used when vsync is off. 0 means unlimited."""


def cycle[T](options: Sequence[T], current: T, step: int) -> T:
    """Option `step` places after `current`, wrapping around.

    A value that is not an option counts as sitting before the first
    larger option, so stepping from it moves to a neighbour.

    Returns:
        T: The chosen option.

    """
    if current in options:
        index = options.index(current)
        return options[(index + step) % len(options)]
    # Insert the custom value in order, then step from it.
    ordered = sorted({*options, current}, key=_sort_key)
    index = ordered.index(current)
    return (
        ordered[(index + step) % len(ordered)] if len(ordered) > 1 else current
    )


def _sort_key(value: object) -> tuple[float, ...]:
    if isinstance(value, tuple):
        return tuple(float(v) for v in value)
    if value == 0:  # Unlimited sorts last.
        return (float("inf"),)
    return (float(value),)  # type: ignore[arg-type]


def fps_label(limit: int) -> str:
    """Text for a frame cap.

    Returns:
        str: E.g. `60 FPS` or `Unlimited`.

    """
    return "Unlimited" if limit <= 0 else f"{limit} FPS"
