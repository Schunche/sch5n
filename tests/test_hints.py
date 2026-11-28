# Copyright (c) 2026 Schunche
"""New player tips."""

from __future__ import annotations

from sch5n.client.hints import (
    BASICS,
    BASICS_SECONDS,
    NIGHT,
    RESPAWN,
    SHOW_SECONDS,
    Hints,
    Situation,
    pick,
)

RATE = 10


def situation(**changes: object) -> Situation:
    """Make a calm daytime situation, with changes.

    Returns:
        Situation: The situation.

    """
    base = {
        "seconds_played": 100.0,
        "night": False,
        "deaths": 0,
        "armed": False,
    }
    return Situation(**{**base, **changes})  # type: ignore[arg-type]


def test_the_most_urgent_tip_wins() -> None:
    """Respawn beats night, which beats the basics; calm days are silent."""
    assert pick(situation()) is None
    assert pick(situation(seconds_played=1.0)) is BASICS
    assert pick(situation(seconds_played=1.0, night=True)) is NIGHT
    assert pick(situation(night=True, armed=True)) is None
    assert pick(situation(night=True, deaths=1)) is RESPAWN
    assert BASICS_SECONDS > 1


def test_each_tip_shows_once_for_a_while() -> None:
    """A tip stays for its time, then never comes back."""
    hints = Hints(RATE)
    early = situation(seconds_played=1.0)
    hints.tick(early)
    assert hints.text == BASICS.text
    for _ in range(SHOW_SECONDS * RATE):
        hints.tick(early)
    assert not hints.text
    hints.tick(early)
    assert not hints.text
    hints.tick(situation(night=True))
    assert hints.text == NIGHT.text
