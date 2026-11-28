# Copyright (c) 2026 Schunche
"""Rain, which follows from the clock alone.

Server and clients agree without being told.
"""

from __future__ import annotations

from sch5n.game.daylight import DAY_SECONDS

RAIN_CHANCE = 0.35
"""Share of days with a shower. The first day is dry."""
EARLIEST, LATEST_START = 0.08, 0.6
"""Where in a day a shower may start, as a share of the day."""
SHORTEST, LONGEST = 0.12, 0.32
"""How long a shower lasts, as a share of the day."""
FADE = 0.03
"""Share of a day a shower takes to build up and die down."""
_MASK = 0xFFFFFFFF


def _mix(value: int) -> float:
    """Scramble a whole number into a repeatable value in [0, 1).

    Returns:
        float: The value.

    """
    value = (value * 0x9E3779B1) & _MASK
    value ^= value >> 15
    value = (value * 0x85EBCA6B) & _MASK
    value ^= value >> 13
    value = (value * 0xC2B2AE35) & _MASK
    value ^= value >> 16
    return value / (_MASK + 1)


def noise(index: int) -> float:
    """Give a repeatable value in [0, 1) for a whole number.

    Returns:
        float: The value; the same number always gives the same one.

    """
    return _mix(index)


def rain_amount(clock: int, tick_rate: int) -> float:
    """Tell how hard it rains.

    Returns:
        float: 0 when dry, up to 1 in the middle of a shower.

    """
    day_ticks = DAY_SECONDS * tick_rate
    day, ticks = divmod(clock, day_ticks)
    if day <= 0 or _mix(day * 3) >= RAIN_CHANCE:
        return 0.0
    start = EARLIEST + (LATEST_START - EARLIEST) * _mix(day * 3 + 1)
    end = start + SHORTEST + (LONGEST - SHORTEST) * _mix(day * 3 + 2)
    now = ticks / day_ticks
    ramp_up = (now - start) / FADE
    ramp_down = (end - now) / FADE
    return min(max(min(ramp_up, ramp_down), 0.0), 1.0)
