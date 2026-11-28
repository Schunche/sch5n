# Copyright (c) 2026 Schunche
"""Sound effects, synthesized at start so no audio files are needed.

The sounds are placeholders: short noise bursts and tones. `Audio` plays
them through pygame's mixer at the master and effects volumes, and quietly
does nothing where there is no sound device.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sch5n.game.config import Settings

LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 22050
PEAK = 0.6
"""Loudest sample of a sound, as a share of the full range."""
_SEED = 7


def _envelope(count: int, decay: float) -> np.ndarray:
    return np.exp(-np.linspace(0.0, decay, count))


def _noise(seconds: float, decay: float, *, low: float) -> np.ndarray:
    # Noise fading out; `low` near 1 keeps only the low rumble.
    count = int(SAMPLE_RATE * seconds)
    raw = np.random.default_rng(_SEED).uniform(-1.0, 1.0, count)
    out = np.empty(count)
    last = 0.0
    for index, value in enumerate(raw):
        last = low * last + (1.0 - low) * value
        out[index] = last
    return out * _envelope(count, decay)


def _tone(
    seconds: float, start: float, end: float, decay: float
) -> np.ndarray:
    # A sine gliding from `start` to `end` Hz, fading out.
    count = int(SAMPLE_RATE * seconds)
    freq = np.linspace(start, end, count)
    phase = np.cumsum(freq) * 2 * np.pi / SAMPLE_RATE
    return np.sin(phase) * _envelope(count, decay)


def _recipes() -> dict[str, np.ndarray]:
    return {
        "break": _noise(0.14, 6.0, low=0.5),
        "place": _noise(0.08, 7.0, low=0.8) + _tone(0.08, 180, 120, 7.0),
        "hit": _noise(0.1, 7.0, low=0.2) * 0.6 + _tone(0.1, 300, 100, 6.0),
        "hurt": _tone(0.22, 260, 90, 4.0),
        "chat": _tone(0.1, 880, 1320, 5.0),
        "pickup": _tone(0.06, 600, 900, 8.0),
        "craft": _tone(0.12, 520, 780, 4.0) + _tone(0.12, 780, 1040, 4.0),
    }


NAMES = tuple(_recipes())
"""Every sound that can be played."""


def synthesize(name: str) -> np.ndarray:
    """Make a sound.

    Returns:
        np.ndarray: Signed 16 bit mono samples.

    """
    wave = _recipes()[name]
    peak = float(np.max(np.abs(wave))) or 1.0
    return (wave / peak * PEAK * 32767).astype(np.int16)


def effect_volume(settings: Settings) -> float:
    """Give the loudness of effects under the volume settings.

    Returns:
        float: From 0 to 1.

    """
    return settings.master_volume / 100 * settings.effects_volume / 100


class Audio:
    """Plays the effects. Without a sound device every call is a no-op."""

    def __init__(self, *, enabled: bool = True) -> None:
        """Open the mixer unless `enabled` is false."""
        self.sounds: dict[str, object] = {}
        self.played: deque[str] = deque(maxlen=64)
        """Names of the sounds played, for tests."""
        if not enabled:
            return
        try:
            from pygame import mixer  # ruff: ignore[import-outside-top-level]

            mixer.init(SAMPLE_RATE, -16, 1, 512)
            for name in NAMES:
                self.sounds[name] = mixer.Sound(
                    buffer=synthesize(name).tobytes()
                )
        except (ImportError, OSError, RuntimeError) as error:
            LOGGER.info("No sound: %s", error)
            self.sounds.clear()
        except Exception as error:  # ruff: ignore[blind-except]
            LOGGER.info("No sound: %s", error)
            self.sounds.clear()

    def play(
        self, name: str, settings: Settings, *, gain: float = 1.0
    ) -> None:
        """Play a sound at the volume the settings give it."""
        volume = effect_volume(settings) * gain
        if volume <= 0:
            return
        self.played.append(name)
        sound = self.sounds.get(name)
        if sound is not None:
            sound.set_volume(min(1.0, volume))  # type: ignore[attr-defined]
            sound.play()  # type: ignore[attr-defined]
