# Copyright (c) 2026 Schunche
"""A small map of the world around the player, one pixel per tile."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.atlas import create_texture
from sch5n.client.render.batch import rgba
from sch5n.client.render.image import load_rgba

if TYPE_CHECKING:
    from pathlib import Path

    import moderngl

    from sch5n.client.render.batch import SpriteBatch
    from sch5n.game.content import BlockRegistry
    from sch5n.world.tilemap import TileMap

MAP_TILES = (128, 96)
"""Width and height in tiles of the part of the world shown."""
SCALE = 2
"""Screen pixels per tile."""
SKY = (120, 170, 230, 90)
"""Color of empty tiles: see-through sky."""
BACKDROP = (10, 14, 24, 150)
"""Dark behind the whole map."""


def average_color(
    textures_dir: Path, name: str, colorkey: tuple[int, int, int]
) -> tuple[int, int, int, int]:
    """Find the mean color of a texture, without its see-through pixels.

    Returns:
        tuple[int, int, int, int]: Opaque RGBA, magenta if there is no
        texture to look at.

    """
    path = textures_dir / f"{name}.png"
    if not path.exists():
        return (255, 0, 255, 255)
    pixels = load_rgba(path, colorkey)
    solid = pixels[pixels[..., 3] > 0]
    if len(solid) == 0:
        return (255, 0, 255, 255)
    red, green, blue = (int(v) for v in solid[:, :3].mean(axis=0))
    return (red, green, blue, 255)


def block_colors(
    blocks: BlockRegistry, textures_dir: Path, colorkey: tuple[int, int, int]
) -> np.ndarray:
    """Make a color for every block id.

    Returns:
        np.ndarray: `(blocks, 4)` uint8 array; id 0, the empty tile, is
        the sky.

    """
    table = np.zeros((max(b.id for b in blocks) + 1, 4), dtype=np.uint8)
    table[0] = SKY
    for block in blocks:
        first = block.spec.textures[0]
        name = first if isinstance(first, str) else first[-1]
        table[block.id] = average_color(textures_dir, name, colorkey)
    return table


def minimap_pixels(
    tilemap: TileMap,
    colors: np.ndarray,
    center: tuple[int, int],
    size: tuple[int, int] = MAP_TILES,
) -> np.ndarray:
    """Color the tiles around a point.

    Returns:
        np.ndarray: `(height, width, 4)` uint8 RGBA, the top row first.

    """
    width, height = size
    x0, y0 = center[0] - width // 2, center[1] - height // 2
    ids = tilemap.region(x0, y0, x0 + width, y0 + height)
    pixels = colors[np.minimum(ids, len(colors) - 1)]
    pixels[ids == 0] = SKY
    return pixels


class MiniMap:
    """Draws the minimap as one texture."""

    def __init__(self, ctx: moderngl.Context, colors: np.ndarray) -> None:
        """Keep the context and the block colors."""
        self.ctx = ctx
        self.colors = colors
        self.texture: moderngl.Texture | None = None

    def draw(
        self,
        batch: SpriteBatch,
        tilemap: TileMap,
        center: tuple[int, int],
        corner: tuple[float, float],
    ) -> tuple[float, float, float, float]:
        """Draw the map with its top right at `corner`.

        Returns:
            tuple[float, float, float, float]: The screen rectangle it
            covers, as x, y, width and height.

        """
        pixels = minimap_pixels(tilemap, self.colors, center)
        height, width = pixels.shape[:2]
        if self.texture is None:
            self.texture = create_texture(self.ctx, pixels)
        else:
            self.texture.write(np.ascontiguousarray(pixels).tobytes())
        w, h = width * SCALE, height * SCALE
        rect = (corner[0] - w, corner[1], float(w), float(h))
        batch.shape(rect, rgba(BACKDROP))
        batch.sprite(self.texture, rect)
        return rect

    def release(self) -> None:
        """Free the texture."""
        if self.texture is not None:
            self.texture.release()
            self.texture = None
