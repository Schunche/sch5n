# Copyright (c) 2026 Schunche
"""The light map: night darkness with the light of torches cut out of it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.atlas import create_texture
from sch5n.client.render.daynight import NIGHT_TINT

if TYPE_CHECKING:
    import moderngl

    from sch5n.client.render.batch import SpriteBatch

MAX_LIGHT = 32
"""Largest light radius, in tiles, so far away lights still show."""
MAX_SOURCES = 400
"""Most lights counted per frame, which keeps a crowd of torches cheap."""
FALLOFF = 1.2
"""Power of the fade from a light outwards; lower reaches further."""
GLOW_COLOR = (255, 170, 80)
GLOW_TINT = 0.7
"""How far the color of the dark moves towards the glow, at full light."""
GLOW_ALPHA = 0.10
"""Warm haze left at full light, as a share of the night's darkness."""


def _stamp(field: np.ndarray, row: int, column: int, radius: float) -> None:
    """Add the glow of one source to a field, keeping the stronger light."""
    reach = int(radius) + 1
    top, left = max(row - reach, 0), max(column - reach, 0)
    window = field[top : row + reach + 1, left : column + reach + 1]
    ys, xs = np.ogrid[
        top : top + window.shape[0], left : left + window.shape[1]
    ]
    dist = np.hypot(ys - row, xs - column)
    np.maximum(
        window,
        np.clip(1.0 - dist / (radius + 0.5), 0.0, 1.0) ** FALLOFF,
        out=window,
    )


def light_field(radii: np.ndarray) -> np.ndarray:
    """Spread the light of the sources over their surroundings.

    Args:
        radii: Light radius of every tile, 0 for tiles that give none.

    Returns:
        np.ndarray: Float array of the same shape, 0 (dark) to 1 (lit).

    """
    field = np.zeros(radii.shape, dtype=np.float32)
    rows, columns = np.nonzero(radii)
    if len(rows) > MAX_SOURCES:
        keep = np.linspace(0, len(rows) - 1, MAX_SOURCES).astype(int)
        rows, columns = rows[keep], columns[keep]
    for row, column in zip(rows.tolist(), columns.tolist(), strict=True):
        _stamp(field, row, column, float(radii[row, column]))
    return field


def night_pixels(light: np.ndarray, shade: float) -> np.ndarray:
    """Color the night over every tile of a light field.

    Args:
        light: Output of `light_field`.
        shade: How opaque the dark is where there is no light.

    Returns:
        np.ndarray: `(h, w, 4)` uint8 RGBA, ready to draw over the world.

    """
    tint = np.array(NIGHT_TINT, dtype=np.float32)
    glow = np.array(GLOW_COLOR, dtype=np.float32)
    mix = (light * GLOW_TINT)[..., None]
    rgb = tint * (1.0 - mix) + glow * mix
    alpha = shade * ((1.0 - light) + light * GLOW_ALPHA)
    pixels = np.empty((*light.shape, 4), dtype=np.uint8)
    pixels[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    pixels[..., 3] = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    return pixels


class LightMap:
    """Draws the night as one smooth texture, a pixel per tile."""

    def __init__(self, ctx: moderngl.Context) -> None:
        """Remember the context; the texture is made on first use."""
        self.ctx = ctx
        self.texture: moderngl.Texture | None = None

    def draw(
        self,
        batch: SpriteBatch,
        pixels: np.ndarray,
        rect: tuple[float, float, float, float],
    ) -> None:
        """Draw night pixels stretched over a rectangle of the screen."""
        height, width = pixels.shape[:2]
        texture = self.texture
        if texture is None or texture.size != (width, height):
            self.release()
            texture = create_texture(self.ctx, pixels)
            self.texture = texture
        else:
            texture.write(np.ascontiguousarray(pixels).tobytes())
        # A smooth blend between tiles is wanted here, it is no art.
        texture.filter = (self.ctx.LINEAR, self.ctx.LINEAR)
        batch.sprite(texture, rect)

    def release(self) -> None:
        """Free the texture."""
        if self.texture is not None:
            self.texture.release()
            self.texture = None
