# Copyright (c) 2026 Schunche
"""Image loading through pygame-ce. Produces plain RGBA pixel arrays."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pygame

if TYPE_CHECKING:
    from pathlib import Path


def surface_to_rgba(surface: pygame.Surface) -> np.ndarray:
    """Copy a surface into an array.

    Returns:
        np.ndarray: uint8 array with shape `(height, width, 4)`, top row first.

    """
    width, height = surface.get_size()
    data = pygame.image.tobytes(surface, "RGBA")
    return np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4).copy()


def apply_colorkey(
    pixels: np.ndarray, key: tuple[int, int, int]
) -> np.ndarray:
    """Make every pixel of color `key` fully transparent, in place.

    Returns:
        np.ndarray: `pixels`.

    """
    mask = np.all(pixels[..., :3] == np.asarray(key, dtype=np.uint8), axis=-1)
    pixels[mask] = 0
    return pixels


def load_rgba(
    path: Path,
    colorkey: tuple[int, int, int] | None = None,
    size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Load an image file, optionally resized (nearest neighbour).

    Returns:
        np.ndarray: uint8 array with shape `(height, width, 4)`.

    """
    surface = pygame.image.load(str(path))
    if size is not None and surface.get_size() != size:
        surface = pygame.transform.scale(surface, size)
    pixels = surface_to_rgba(surface)
    if colorkey is not None:
        apply_colorkey(pixels, colorkey)
    return pixels
