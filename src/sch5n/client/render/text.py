# Copyright (c) 2026 Schunche
"""Text rendered by pygame-ce fonts, cached as textures."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import pygame

from sch5n.client.render.atlas import create_texture
from sch5n.client.render.batch import WHITE
from sch5n.client.render.image import surface_to_rgba

if TYPE_CHECKING:
    import moderngl

    from sch5n.client.render.batch import RGBA, SpriteBatch


class Anchor(StrEnum):
    """Which point of the text box the position refers to."""

    TOP_LEFT = "top_left"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"


def anchored(
    pos: tuple[float, float], size: tuple[int, int], anchor: Anchor
) -> tuple[int, int]:
    """Top left corner of a box of `size` anchored at `pos`.

    Returns:
        tuple[int, int]: Pixel aligned top left corner.

    """
    x, y = pos
    w, h = size
    match anchor:
        case Anchor.TOP_LEFT:
            pass
        case Anchor.MIDDLE_LEFT:
            y -= h / 2
        case Anchor.CENTER:
            x, y = x - w / 2, y - h / 2
        case Anchor.BOTTOM_RIGHT:
            x, y = x - w, y - h
        case Anchor.BOTTOM_CENTER:
            x, y = x - w / 2, y - h
    return round(x), round(y)


@dataclass(frozen=True, slots=True)
class TextStyle:
    """How text is drawn."""

    size: int = 16
    """Font size in pixels."""
    color: RGBA = WHITE
    anchor: Anchor = Anchor.TOP_LEFT
    """Which point of the text box the position refers to."""


DEFAULT_STYLE = TextStyle()


class TextRenderer:
    """Renders strings with pygame and keeps recently used ones on the GPU.

    Text is rendered white and tinted when drawn, so the cache does not
    depend on color.
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        font_path: str | None = None,
        max_cached: int = 512,
    ) -> None:
        """Create a renderer. `font_path=None` uses pygame's default font."""
        if not pygame.font.get_init():
            pygame.font.init()
        self.ctx = ctx
        self.font_path = font_path
        self.max_cached = max_cached
        self._fonts: dict[int, pygame.font.Font] = {}
        self._cache: OrderedDict[
            tuple[str, int], tuple[moderngl.Texture, tuple[int, int]]
        ] = OrderedDict()

    def font(self, size: int) -> pygame.font.Font:
        """Font of a pixel size, roughly matching common system fonts.

        Returns:
            pygame.font.Font: The font.

        """
        font = self._fonts.get(size)
        if font is None:
            # pygame's default font renders small, scale it up a bit.
            scaled = round(size * 4 / 3) if self.font_path is None else size
            font = self._fonts[size] = pygame.font.Font(self.font_path, scaled)
        return font

    @property
    def cached_count(self) -> int:
        """Number of strings currently kept as textures."""
        return len(self._cache)

    def measure(self, text: str, size: int) -> tuple[int, int]:
        """Size of rendered text in pixels.

        Returns:
            tuple[int, int]: Width and height.

        """
        return self.font(size).size(text)

    def _texture(
        self, text: str, size: int
    ) -> tuple[moderngl.Texture, tuple[int, int]]:
        key = (text, size)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        surface = self.font(size).render(
            text, antialias=True, color=(255, 255, 255)
        )
        texture = create_texture(
            self.ctx, surface_to_rgba(surface), smooth=True
        )
        entry = (texture, surface.get_size())
        self._cache[key] = entry
        while len(self._cache) > self.max_cached:
            _, (old, _) = self._cache.popitem(last=False)
            old.release()
        return entry

    def draw(
        self,
        batch: SpriteBatch,
        text: str,
        pos: tuple[float, float],
        style: TextStyle = DEFAULT_STYLE,
    ) -> tuple[int, int]:
        """Queue text for drawing.

        Returns:
            tuple[int, int]: Size of the drawn text.

        """
        if not text:
            return (0, 0)
        texture, (w, h) = self._texture(text, style.size)
        x, y = anchored(pos, (w, h), style.anchor)
        batch.sprite(texture, (x, y, w, h), color=style.color)
        return (w, h)

    def release(self) -> None:
        """Free all cached textures."""
        for texture, _ in self._cache.values():
            texture.release()
        self._cache.clear()
