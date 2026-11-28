# Copyright (c) 2026 Schunche
"""Synthesized sound effects and their volume."""

from __future__ import annotations

import numpy as np
import pytest

from sch5n.client.audio import (
    NAMES,
    PEAK,
    SAMPLE_RATE,
    Audio,
    effect_volume,
    synthesize,
)
from sch5n.game.config import Settings

MAX_SECONDS = 0.5
HALF = 0.5


def test_every_sound_is_short_and_not_clipped() -> None:
    """Sounds are audible, brief, and below full scale."""
    for name in NAMES:
        wave = synthesize(name)
        assert wave.dtype == np.int16
        assert 0 < len(wave) < SAMPLE_RATE * MAX_SECONDS
        assert int(np.abs(wave).max()) <= int(PEAK * 32767) + 1
        assert int(np.abs(wave).max()) > 0


def test_sounds_are_the_same_every_time() -> None:
    """The synthesis is deterministic."""
    assert np.array_equal(synthesize("break"), synthesize("break"))


def test_volume_follows_the_sliders() -> None:
    """Master and effects volume multiply; zero silences."""
    loud = Settings(master_volume=100, effects_volume=100)
    half = Settings(master_volume=50, effects_volume=100)
    mute = Settings(master_volume=0, effects_volume=100)
    assert effect_volume(loud) == pytest.approx(1.0)
    assert effect_volume(half) == pytest.approx(HALF)
    audio = Audio(enabled=False)
    audio.play("hit", mute)
    assert not audio.played
    audio.play("hit", half)
    assert list(audio.played) == ["hit"]
