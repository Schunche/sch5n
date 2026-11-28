# Copyright (c) 2026 Schunche
"""The time of day. Server and clients agree because both count ticks."""

from __future__ import annotations

import math

DAY_SECONDS = 600
"""Length of a whole day and night."""
START = 0.35
"""Where in the day a new game starts: just after sunrise."""
SUNRISE = 0.25
SUNSET = 0.75


def phase(ticks: int, tick_rate: int) -> float:
    """Tell how far through the day it is.

    Returns:
        float: 0 at midnight, 0.25 at sunrise, 0.5 at noon, 0.75 at
        sunset, back to 1.

    """
    return (START + ticks / (DAY_SECONDS * tick_rate)) % 1.0


def sun_height(day_phase: float) -> float:
    """Height of the sun, from -1 at midnight to 1 at noon.

    Returns:
        float: The height.

    """
    return -math.cos(2 * math.pi * day_phase)


def daylight(day_phase: float) -> float:
    """How bright it is: 1 in the day, 0 at night, smooth at dawn and dusk.

    Returns:
        float: A value in [0, 1].

    """
    height = sun_height(day_phase)
    t = min(max((height + 0.15) / 0.5, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sun_position(day_phase: float) -> tuple[float, float]:
    """Where the sun glow sits: across the screen, up the sky.

    Returns:
        tuple[float, float]: Like `SkyConfig.sun_position`; below the
        horizon at night.

    """
    across = 0.1 + 0.8 * (day_phase - SUNRISE) / (SUNSET - SUNRISE)
    across = min(max(across, -0.2), 1.2)
    return (across, sun_height(day_phase) * 0.9)
