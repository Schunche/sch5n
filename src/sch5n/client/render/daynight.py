# Copyright (c) 2026 Schunche
"""Day and night: the sky's colors and the dark over the world."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.game.daylight import daylight, sun_height, sun_position

if TYPE_CHECKING:
    from sch5n.client.render.batch import SpriteBatch
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


STAR_COUNT = 90
STAR_SIZE = 2
MOON_RADIUS = 22
MOON_HIDDEN_BELOW = -0.1
MOON_COLOR: Color = (226, 232, 246)
SKY_SHARE = 0.75
"""Share of the screen height, from the horizon up, that has stars."""


def _stars() -> list[tuple[float, float, float]]:
    """Make a fixed scatter of stars.

    Returns:
        list[tuple[float, float, float]]: Across, up the sky and
        brightness, each in [0, 1].

    """
    rng = random.Random(7)  # ruff: ignore[suspicious-non-cryptographic-random-usage]
    return [
        (rng.random(), rng.random(), 0.4 + 0.6 * rng.random())
        for _ in range(STAR_COUNT)
    ]


STARS = _stars()


def draw_stars_and_moon(
    batch: SpriteBatch,
    screen: tuple[int, int],
    horizon_y: float,
    day_phase: float,
) -> None:
    """Draw stars and the moon over the sky, fading in with the night.

    Draws in screen space. `horizon_y` is the screen y of the horizon.
    """
    night = 1.0 - daylight(day_phase)
    if night <= 0.0:
        return
    width, _ = screen
    span = min(horizon_y, screen[1]) * SKY_SHARE
    if span <= 0:
        return
    for across, up, brightness in STARS:
        y = horizon_y - 8 - up * span
        if y < 0 or y > horizon_y:
            continue
        batch.shape(
            (across * width, y, STAR_SIZE, STAR_SIZE),
            rgba((255, 255, 255), night * brightness),
        )
    moon_across, moon_up = sun_position((day_phase + 0.5) % 1.0)
    if moon_up > MOON_HIDDEN_BELOW:
        y = horizon_y - moon_up * span
        batch.shape(
            (
                moon_across * width - MOON_RADIUS,
                y - MOON_RADIUS,
                2 * MOON_RADIUS,
                2 * MOON_RADIUS,
            ),
            rgba(MOON_COLOR, night),
            radius=MOON_RADIUS,
        )
