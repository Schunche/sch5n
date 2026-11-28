# Copyright (c) 2026 Schunche
"""Tests for the weather."""

from __future__ import annotations

from itertools import pairwise

import pytest

from sch5n.game.daylight import DAY_SECONDS
from sch5n.game.weather import FADE, rain_amount

RATE = 60
DAYS = 400


def samples(day: int, count: int = 200) -> list[float]:
    """Sample the rain over one day.

    Returns:
        list[float]: The amounts.

    """
    day_ticks = DAY_SECONDS * RATE
    return [
        rain_amount(day * day_ticks + day_ticks * i // count, RATE)
        for i in range(count)
    ]


def test_the_first_day_is_dry() -> None:
    """A new game starts without rain."""
    assert not any(samples(0))


def test_some_days_rain_and_most_do_not() -> None:
    """Showers come on about a third of the days, in the 0 to 1 range."""
    wet = [day for day in range(1, DAYS) if max(samples(day, 50)) > 0]
    assert 0.2 * DAYS < len(wet) < 0.5 * DAYS
    for day in wet[:20]:
        amounts = samples(day)
        assert max(amounts) == pytest.approx(1.0)
        assert min(amounts) == pytest.approx(0.0)


def test_rain_is_a_continuous_shower() -> None:
    """Within a day the rain is one stretch that builds and fades."""
    day = next(d for d in range(1, DAYS) if max(samples(d)) > 0)
    amounts = samples(day, 1000)
    wet = [i for i, a in enumerate(amounts) if a > 0]
    assert wet == list(range(wet[0], wet[-1] + 1))
    step = abs(amounts[1] - amounts[0])
    biggest = max(abs(b - a) for a, b in pairwise(amounts))
    assert biggest < 1 / (FADE * 1000) * 1.5 + step


def test_rain_is_repeatable() -> None:
    """The same clock always gives the same weather."""
    day_ticks = DAY_SECONDS * RATE
    clocks = [day_ticks * d + 1234 * d for d in range(1, 60)]
    assert [rain_amount(c, RATE) for c in clocks] == [
        rain_amount(c, RATE) for c in clocks
    ]
