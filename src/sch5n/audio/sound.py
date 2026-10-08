# Copyright (c) 2026 Schunche
"""Experimental software."""
# noqa: file

import pygame.constants as pgcons
import pygame.mixer as pg_mixer


class Sound(pg_mixer.Sound):
    pg_mixer.pre_init(allowedchanges=pgcons.AUDIO_ALLOW_ANY_CHANGE)
