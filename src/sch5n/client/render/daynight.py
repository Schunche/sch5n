# Copyright (c) 2026 Schunche
"""Day and night: the sky's colors and the dark over the world."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sch5n.game.daylight import daylight, sun_height, sun_position

if TYPE_CHECKING:
    from sch5n.game.config import Color, SkyConfig

NIGHT_HORIZON: Color = (30, 36, 78)
NIGHT_MIDDLE: Color = (14, 20, 54)
NIGHT_ZENITH: Color = (6, 8, 28)
NIGHT_GLOW: Color = (150, 170, 220)
TWILIGHT: Color = (244, 140, 92)
TWILIGHT_WIDTH = 0.22
"""Sun heights around the horizon that get the dawn and dusk glow."""
NIGHT_TINT: Color = (6, 10, 36)
MAX_DARKNESS = 0.55
"""Opacity of the night tint at midnight."""


def _mix(a: Color, b: Color, t: float) -> Color:
    r, g, b_ = (round(x + (y - x) * t) for x, y in zip(a, b, strict=True))
    return (r, g, b_)


def sky_at(sky: SkyConfig, day_phase: float) -> SkyConfig:
    """Make the sky of a moment of the day from the daytime sky.

    Returns:
        SkyConfig: Night colors at night, warm ones near the horizon at
        dawn and dusk, and the sun moved across the sky.

    """
    light = daylight(day_phase)
    height = sun_height(day_phase)
    twilight = math.exp(-((height / TWILIGHT_WIDTH) ** 2)) * 0.6
    horizon = _mix(NIGHT_HORIZON, sky.horizon, light)
    horizon = _mix(horizon, TWILIGHT, twilight)
    return sky.model_copy(
        update={
            "horizon": horizon,
            "middle": _mix(NIGHT_MIDDLE, sky.middle, light),
            "zenith": _mix(NIGHT_ZENITH, sky.zenith, light),
            "sun": _mix(NIGHT_GLOW, sky.sun, light),
            "sun_position": sun_position(day_phase),
        }
    )


def darkness(day_phase: float) -> float:
    """How opaque the night tint over the world is.

    Returns:
        float: 0 in the day, `MAX_DARKNESS` at night.

    """
    return MAX_DARKNESS * (1.0 - daylight(day_phase))
