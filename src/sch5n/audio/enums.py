# Copyright (c) 2026 Schunche
"""Experimental software."""

from enum import StrEnum

type IsSoundAmbient = bool


class NewSoundBeyondLimitBehavior(StrEnum):
    """Define what happens if the buffer is filled."""

    IGNORE_NEW = "IGNORE_NEW"
    REPLACE_OLDEST = "REPLACE_OLDEST"


class MusicOnPauseBehavior:
    """Define what happens to the music on pause or being unfocused."""

    STOP = "STOP"
    KEEP_PLAYING = "KEEP_PLAYING"
