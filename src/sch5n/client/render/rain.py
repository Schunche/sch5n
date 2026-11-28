# Copyright (c) 2026 Schunche
"""Rain on the screen: a gray veil and falling streaks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.game.weather import noise

if TYPE_CHECKING:
    from sch5n.client.render.batch import SpriteBatch

MAX_STREAKS = 220
STREAK_COLOR = (170, 190, 230)
VEIL_COLOR = (36, 44, 64)
VEIL_ALPHA = 0.22
"""Opacity of the veil at full rain."""
STREAK_ALPHA = 0.75
FALL_SPEED = (14.0, 24.0)
STREAK_LENGTH = (9.0, 20.0)
SLANT = 0.18
"""Pixels a streak drifts sideways for each pixel it falls."""
SEED_Y, SEED_SPEED, SEED_LENGTH = 7919, 104729, 1299709


def draw_rain(
    batch: SpriteBatch,
    screen: tuple[int, int],
    amount: float,
    time: int,
    wind: float = 0.0,
) -> None:
    """Draw rain over the screen. Does nothing when it is dry.

    Args:
        batch: Where to queue the shapes.
        screen: Screen size in pixels.
        amount: How hard it rains, 0 to 1.
        time: Ticks, which move the streaks.
        wind: Wind strength, which bends the fall.

    """
    if amount <= 0.01:  # ruff: ignore[magic-value-comparison]
        return
    w, h = screen
    batch.shape((0, 0, w, h), rgba(VEIL_COLOR, VEIL_ALPHA * amount))
    color = rgba(STREAK_COLOR, STREAK_ALPHA * amount)
    slant = SLANT + wind * 0.1
    for index in range(int(MAX_STREAKS * amount)):
        speed = FALL_SPEED[0] + noise(index + SEED_SPEED) * (
            FALL_SPEED[1] - FALL_SPEED[0]
        )
        length = STREAK_LENGTH[0] + noise(index + SEED_LENGTH) * (
            STREAK_LENGTH[1] - STREAK_LENGTH[0]
        )
        fall = (noise(index + SEED_Y) * h + time * speed) % (h + length)
        x = (noise(index) * (w + h * slant) + fall * slant) % (w + 20) - 10
        batch.shape((x, fall - length, 2, length), color)
