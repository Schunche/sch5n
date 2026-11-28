# Copyright (c) 2026 Schunche
"""Short tips for new players, each shown once while it is useful."""

from __future__ import annotations

from dataclasses import dataclass

SHOW_SECONDS = 8
"""How long a tip stays on screen."""
BASICS_SECONDS = 20
"""The controls tip is only useful in this first stretch of play."""


@dataclass(frozen=True, slots=True)
class Situation:
    """What the tips depend on."""

    seconds_played: float
    night: bool
    deaths: int
    armed: bool
    """Whether the player carries a sword."""


@dataclass(frozen=True, slots=True)
class _Tip:
    key: str
    text: str


BASICS = _Tip(
    "basics",
    "A and D move, Space jumps. Left click mines, right click places.",
)
NIGHT = _Tip(
    "night",
    "Night: creatures come out. Craft a sword, or wall yourself in.",
)
RESPAWN = _Tip(
    "respawn",
    "You came back at spawn. Sleep in a bed to set a new home.",
)


def pick(situation: Situation) -> _Tip | None:
    """Choose the tip that fits now, most urgent first.

    Returns:
        _Tip | None: A tip, or `None` if nothing is worth saying.

    """
    if situation.deaths:
        return RESPAWN
    if situation.night and not situation.armed:
        return NIGHT
    if situation.seconds_played < BASICS_SECONDS:
        return BASICS
    return None


class Hints:
    """Shows one tip at a time, each only once."""

    def __init__(self, tick_rate: int) -> None:
        """Start with nothing shown."""
        self.tick_rate = tick_rate
        self.shown: set[str] = set()
        self.text = ""
        self.left = 0
        """Ticks the current tip stays."""

    def tick(self, situation: Situation) -> None:
        """Advance one tick, starting a new tip when the last is done."""
        if self.left:
            self.left -= 1
            if not self.left:
                self.text = ""
            return
        tip = pick(situation)
        if tip is not None and tip.key not in self.shown:
            self.shown.add(tip.key)
            self.text = tip.text
            self.left = SHOW_SECONDS * self.tick_rate
