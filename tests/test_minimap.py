# Copyright (c) 2026 Schunche
"""Tests for the minimap."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.minimap import (
    MAP_TILES,
    SKY,
    block_colors,
    minimap_pixels,
)
from sch5n.utility import path
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

COLORKEY = (255, 0, 254)


def test_every_block_has_a_color(content: Content) -> None:
    """Colors come from the textures; none is the missing-texture magenta."""
    colors = block_colors(content.blocks, path.TEXTURES_DIR, COLORKEY)
    assert colors.shape[1] == 4  # ruff: ignore[magic-value-comparison]
    assert tuple(colors[0]) == SKY
    for block in content.blocks:
        assert tuple(colors[block.id][:3]) != (255, 0, 255), block.name
    dirt, stone = content.blocks.id_of("dirt"), content.blocks.id_of("stone")
    assert tuple(colors[dirt]) != tuple(colors[stone])


def test_minimap_shows_sky_above_and_ground_below(content: Content) -> None:
    """Around the surface, the top rows are sky and the bottom is ground."""
    world = flat_world(content)
    colors = block_colors(content.blocks, path.TEXTURES_DIR, COLORKEY)
    surface = 10
    pixels = minimap_pixels(world, colors, (0, surface))
    width, height = MAP_TILES
    assert pixels.shape == (height, width, 4)
    assert tuple(pixels[0, width // 2]) == SKY
    row = height // 2
    assert tuple(pixels[row - 1, width // 2]) == SKY
    assert tuple(pixels[row, width // 2]) != SKY
    assert tuple(pixels[row + 1, width // 2]) != SKY
    assert pixels.dtype == np.uint8
