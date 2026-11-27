# Copyright (c) 2026 Schunche
"""Packing many small images into one texture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
lazy import moderngl

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping


@dataclass(frozen=True, slots=True)
class Region:
    """Part of a texture, in normalized coordinates (v grows downwards)."""

    u0: float
    v0: float
    u1: float
    v1: float
    width: int
    """Size in pixels."""
    height: int

    @property
    def uv(self) -> tuple[float, float, float, float]:
        """`(u0, v0, u1, v1)`."""
        return (self.u0, self.v0, self.u1, self.v1)


FULL = Region(0.0, 0.0, 1.0, 1.0, 1, 1)
"""The whole texture."""


def next_power_of_two(value: int) -> int:
    """Smallest power of two that is at least `value`.

    Returns:
        int: A power of two, at least 1.

    """
    return 1 << max(value - 1, 0).bit_length()


def pack_shelves[K: Hashable](
    sizes: Mapping[K, tuple[int, int]], width: int, padding: int = 1
) -> tuple[dict[K, tuple[int, int]], int]:
    """Place rectangles on horizontal shelves, tallest first.

    Args:
        sizes: Width and height of each rectangle.
        width: Width of the target area.
        padding: Free border around every rectangle.

    Returns:
        tuple[dict[K, tuple[int, int]], int]: Top left corner of each
        rectangle (inside its padding) and the total height used.

    Raises:
        ValueError: A rectangle is wider than the target area.

    """
    positions: dict[K, tuple[int, int]] = {}
    x = y = shelf_height = 0
    order = sorted(sizes, key=lambda k: (-sizes[k][1], -sizes[k][0]))
    for key in order:
        w, h = sizes[key]
        padded_w, padded_h = w + 2 * padding, h + 2 * padding
        if padded_w > width:
            msg = f"Image {key!r} ({w}px) does not fit in {width}px"
            raise ValueError(msg)
        if x + padded_w > width:
            x, y = 0, y + shelf_height
            shelf_height = 0
        positions[key] = (x + padding, y + padding)
        x += padded_w
        shelf_height = max(shelf_height, padded_h)
    return positions, y + shelf_height


def _blit_extruded(
    target: np.ndarray, image: np.ndarray, x: int, y: int, padding: int
) -> None:
    """Copy `image` and repeat its edge pixels into the padding.

    Prevents neighbouring images bleeding in when sampling at edges.
    """
    padded = np.pad(
        image, ((padding, padding), (padding, padding), (0, 0)), mode="edge"
    )
    h, w = padded.shape[:2]
    target[y - padding : y - padding + h, x - padding : x - padding + w] = (
        padded
    )


class AtlasBuilder[K: Hashable]:
    """Collects images, then packs them into one RGBA pixel array."""

    def __init__(self, width: int = 1024, padding: int = 1) -> None:
        """Create an empty builder."""
        self.width = width
        self.padding = padding
        self.images: dict[K, np.ndarray] = {}

    def add(self, key: K, pixels: np.ndarray) -> None:
        """Add an image with shape `(height, width, 4)`."""
        self.images[key] = pixels

    def build(self) -> tuple[np.ndarray, dict[K, Region]]:
        """Pack all images.

        Returns:
            tuple[np.ndarray, dict[K, Region]]: Atlas pixels (power of two
            height) and the region of every image.

        """
        sizes = {
            k: (img.shape[1], img.shape[0]) for k, img in self.images.items()
        }
        positions, used = pack_shelves(sizes, self.width, self.padding)
        height = next_power_of_two(max(used, 1))
        pixels = np.zeros((height, self.width, 4), dtype=np.uint8)
        regions: dict[K, Region] = {}
        for key, (x, y) in positions.items():
            w, h = sizes[key]
            _blit_extruded(pixels, self.images[key], x, y, self.padding)
            regions[key] = Region(
                x / self.width,
                y / height,
                (x + w) / self.width,
                (y + h) / height,
                w,
                h,
            )
        return pixels, regions


def create_texture(
    ctx: moderngl.Context, pixels: np.ndarray, *, smooth: bool = False
) -> moderngl.Texture:
    """Upload an RGBA array as a texture, top row at v = 0.

    Returns:
        moderngl.Texture: The texture.

    """
    height, width = pixels.shape[:2]
    texture = ctx.texture(
        (width, height), 4, np.ascontiguousarray(pixels).tobytes()
    )
    flt = moderngl.LINEAR if smooth else moderngl.NEAREST
    texture.filter = (flt, flt)
    texture.repeat_x = texture.repeat_y = False
    return texture
