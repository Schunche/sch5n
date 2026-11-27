# Copyright (c) 2026 Schunche
"""Text rendered by pygame-ce fonts, cached as textures."""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pygame.freetype

from sch5n.client.render.atlas import create_texture
from sch5n.client.render.batch import WHITE
from sch5n.client.render.image import surface_to_rgba

if TYPE_CHECKING:
    from collections.abc import Sequence

    import moderngl

    from sch5n.client.render.batch import RGBA, SpriteBatch


class Anchor(StrEnum):
    """Which point of the text box the position refers to."""

    TOP_LEFT = "top_left"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_LEFT = "bottom_left"


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
        case Anchor.BOTTOM_LEFT:
            y -= h
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


def _simple(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


def system_font(names: Sequence[str]) -> str | None:
    """Find a font installed on the computer.

    Font lookups substitute similar fonts for missing ones, like FreeSans
    for Arial on Linux, so a font counts as found only if its file is named
    after it. Without any, the first substitute is used.

    Returns:
        str | None: The font file, `None` if there is none at all.

    """
    if not pygame.font.get_init():
        pygame.font.init()
    substitute = None
    for name in names:
        found = pygame.font.match_font(name)
        if found is None:
            continue
        if _simple(name) in _simple(Path(found).stem):
            return found
        substitute = substitute or found
    return substitute


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
        *,
        pixel_grid: float = 0,
        scale_step: float | None = None,
    ) -> None:
        """Create a renderer. `font_path=None` uses pygame's default font.

        `pixel_grid` is for pixel fonts: the size at which one pixel of the
        font is one screen pixel. Text is then rendered at exactly that size
        and enlarged by a whole factor with hard edges, so every font pixel
        is the same number of screen pixels, at any size. The factor is the
        requested size divided by `scale_step` (by default `pixel_grid`),
        rounded.
        """
        if not pygame.font.get_init():
            pygame.font.init()
        self.ctx = ctx
        self.font_path = font_path
        self.pixel_grid = pixel_grid if font_path is not None else 0
        self.scale_step = scale_step or self.pixel_grid
        self.max_cached = max_cached
        self._fonts: dict[int, pygame.font.Font] = {}
        self._pixel_font: pygame.freetype.Font | None = None
        if self.pixel_grid > 0:
            if not pygame.freetype.get_init():
                pygame.freetype.init()
            font = pygame.freetype.Font(font_path, self.pixel_grid)
            font.antialiased = False
            font.origin = True
            font.pad = False
            self._pixel_font = font
        self._cache: OrderedDict[
            tuple[str, int], tuple[moderngl.Texture, tuple[int, int]]
        ] = OrderedDict()

    @property
    def pixelated(self) -> bool:
        """Whether text keeps hard pixel edges."""
        return self._pixel_font is not None

    def scale(self, size: int) -> int:
        """Whole factor a pixel font is enlarged by for a requested size.

        Returns:
            int: At least 1.

        """
        return max(1, round(size / self.scale_step)) if self.pixelated else 1

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

    def _native_size(self, text: str) -> tuple[int, int]:
        """Size of text in a pixel font at its native size.

        Returns:
            tuple[int, int]: Width and height in font pixels.

        """
        font = self._pixel_font
        if font is None:
            return (0, 0)
        grid = self.pixel_grid
        advance = sum(m[4] for m in font.get_metrics(text, size=grid) if m)
        width = max(math.ceil(advance), font.get_rect(text, size=grid).right)
        return (width, font.get_sized_height(grid))

    def measure(self, text: str, size: int) -> tuple[int, int]:
        """Size of rendered text in pixels.

        Returns:
            tuple[int, int]: Width and height.

        """
        if self.pixelated:
            w, h = self._native_size(text)
            k = self.scale(size)
            return (w * k, h * k)
        return self.font(size).size(text)

    def _render(self, text: str, size: int) -> pygame.Surface:
        font = self._pixel_font
        if font is None:
            return self.font(size).render(
                text, antialias=True, color=(255, 255, 255)
            )
        w, h = self._native_size(text)
        surface = pygame.Surface((max(w, 1), h), pygame.SRCALPHA)
        grid = self.pixel_grid
        font.render_to(
            surface,
            (0, font.get_sized_ascender(grid)),
            text,
            fgcolor=(255, 255, 255),
            size=grid,
        )
        return surface

    def _texture(
        self, text: str, size: int
    ) -> tuple[moderngl.Texture, tuple[int, int]]:
        """Get the texture of a text, and its size on screen.

        Returns:
            tuple[moderngl.Texture, tuple[int, int]]: Texture and size.

        """
        k = self.scale(size)
        key = (text, k if self.pixelated else size)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        surface = self._render(text, size)
        texture = create_texture(
            self.ctx, surface_to_rgba(surface), smooth=not self.pixelated
        )
        w, h = surface.get_size()
        entry = (texture, (w * k, h * k))
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
