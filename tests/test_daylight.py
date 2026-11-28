# Copyright (c) 2026 Schunche
"""Time of day: the cycle and what the sky looks like."""

from __future__ import annotations

import pytest

from sch5n.client.render.daynight import MAX_DARKNESS, darkness, sky_at
from sch5n.game.config import SkyConfig
from sch5n.game.daylight import (
    DAY_SECONDS,
    daylight,
    phase,
    sun_height,
    sun_position,
)

RATE = 60


def test_a_game_starts_in_the_morning() -> None:
    """The first moments are bright."""
    assert daylight(phase(0, RATE)) == pytest.approx(1.0)


def test_the_day_repeats() -> None:
    """A whole day later it is the same time again."""
    ticks = DAY_SECONDS * RATE
    assert phase(5, RATE) == pytest.approx(phase(5 + ticks, RATE))


def test_noon_is_bright_and_midnight_dark() -> None:
    """The sun is highest at noon and lowest at midnight."""
    assert sun_height(0.5) == pytest.approx(1.0)
    assert sun_height(0.0) == pytest.approx(-1.0)
    assert daylight(0.5) == pytest.approx(1.0)
    assert daylight(0.0) == pytest.approx(0.0)
    assert daylight(0.25) < daylight(0.3) < daylight(0.4)


def test_the_sun_crosses_the_sky() -> None:
    """It rises on the left, sets on the right, and hides at night."""
    rise, set_ = sun_position(0.25), sun_position(0.75)
    assert rise[0] < sun_position(0.5)[0] < set_[0]
    assert sun_position(0.5)[1] > rise[1]
    assert sun_position(0.0)[1] < 0


def test_the_sky_darkens_at_night() -> None:
    """Night colors are darker than day colors; noon is the plain sky."""
    day = SkyConfig()
    noon, night = sky_at(day, 0.5), sky_at(day, 0.0)
    assert noon.zenith == day.zenith
    assert sum(night.zenith) < sum(day.zenith) / 3
    assert sum(night.horizon) < sum(day.horizon) / 2
    assert darkness(0.5) == pytest.approx(0.0)
    assert darkness(0.0) == pytest.approx(MAX_DARKNESS)
