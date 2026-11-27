# Copyright (c) 2026 Schunche
"""Instanced quad renderer: one draw call per texture run."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

import numpy as np
lazy import moderngl

from sch5n.client.render.atlas import FULL, Region

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.math.rect import Rect

type RGBA = tuple[float, float, float, float]

WHITE: RGBA = (1.0, 1.0, 1.0, 1.0)
_RGBA_LEN = 4
INSTANCE_FLOATS = 20
"""rect (4) + uv (4) + color (4) + params (4) + transform (4)."""


@dataclass(frozen=True, slots=True)
class Transform:
    """How a sprite is mirrored and rotated."""

    flip_x: bool = False
    """Mirror the image horizontally (before rotating)."""
    rotation: float = 0.0
    """Clockwise, in radians, since y grows downwards."""
    pivot: tuple[float, float] = (0.5, 0.5)
    """Point the sprite rotates around, as a fraction of its size."""


IDENTITY = Transform()


class Kind(IntEnum):
    """How the fragment shader treats an instance."""

    SPRITE = 0
    SHAPE = 1


def rgba(color: tuple[int, ...], alpha: float | None = None) -> RGBA:
    """Convert 0-255 RGB(A) to normalized RGBA.

    Returns:
        RGBA: Floats in [0, 1].

    """
    r, g, b = (c / 255 for c in color[:3])
    a = (
        alpha
        if alpha is not None
        else (color[3] / 255 if len(color) == _RGBA_LEN else 1.0)
    )
    return (r, g, b, a)


def sprite_instances(
    rects: np.ndarray, uvs: np.ndarray, color: RGBA = WHITE
) -> np.ndarray:
    """Build instance rows for many sprites at once.

    Args:
        rects: `(n, 4)` array of x, y, width, height.
        uvs: `(n, 4)` array of u0, v0, u1, v1.
        color: Tint shared by all sprites.

    Returns:
        np.ndarray: `(n, INSTANCE_FLOATS)` float32 array.

    """
    out = np.zeros((len(rects), INSTANCE_FLOATS), dtype=np.float32)
    out[:, 0:4] = rects
    out[:, 4:8] = uvs
    out[:, 8:12] = color
    return out


class SpriteBatch:
    """Collects quads and draws them with instancing.

    Quads are drawn in submission order. Changing the texture or the
    projection flushes the pending quads.
    """

    def __init__(
        self, ctx: moderngl.Context, shader_dir: Path, capacity: int = 4096
    ) -> None:
        """Compile the shader and allocate buffers."""
        self.ctx = ctx
        self.program = ctx.program(
            vertex_shader=(shader_dir / "sprite.vert").read_text(
                encoding="utf-8"
            ),
            fragment_shader=(shader_dir / "sprite.frag").read_text(
                encoding="utf-8"
            ),
        )
        self._quad = ctx.buffer(
            np.array([0, 0, 1, 0, 0, 1, 1, 1], dtype=np.float32).tobytes()
        )
        self._white = ctx.texture((1, 1), 4, b"\xff\xff\xff\xff")
        self._capacity = 0
        self._instances = np.zeros((0, INSTANCE_FLOATS), dtype=np.float32)
        self._count = 0
        self._texture: moderngl.Texture = self._white
        self._allocate(capacity)
        self.draw_calls = 0
        """Draw calls issued. Reset by the application every frame."""

    def _allocate(self, capacity: int) -> None:
        self._capacity = capacity
        old = self._instances[: self._count]
        self._instances = np.zeros(
            (capacity, INSTANCE_FLOATS), dtype=np.float32
        )
        self._instances[: len(old)] = old
        if hasattr(self, "_vbo"):
            self._vao.release()
            self._vbo.release()
        self._vbo = self.ctx.buffer(
            reserve=capacity * INSTANCE_FLOATS * 4, dynamic=True
        )
        self._vao = self.ctx.vertex_array(
            self.program,
            [
                (self._quad, "2f", "in_corner"),
                (
                    self._vbo,
                    "4f 4f 4f 4f 4f/i",
                    "i_rect",
                    "i_uv",
                    "i_color",
                    "i_params",
                    "i_transform",
                ),
            ],
        )

    def _reserve(self, extra: int) -> None:
        needed = self._count + extra
        if needed > self._capacity:
            self._allocate(max(needed, self._capacity * 2))

    def begin(
        self,
        screen: tuple[float, float],
        offset: tuple[float, float] = (0.0, 0.0),
        zoom: float = 1.0,
    ) -> None:
        """Set the projection: world pixel `offset` maps to the top left."""
        self.flush()
        self.program["u_screen"].value = screen
        self.program["u_offset"].value = offset
        self.program["u_zoom"].value = zoom

    def _use_texture(self, texture: moderngl.Texture | None) -> None:
        if texture is not None and texture is not self._texture:
            self.flush()
            self._texture = texture

    def sprite(
        self,
        texture: moderngl.Texture,
        rect: tuple[float, float, float, float],
        region: Region = FULL,
        color: RGBA = WHITE,
        transform: Transform = IDENTITY,
    ) -> None:
        """Queue a textured quad, optionally mirrored and rotated."""
        self._use_texture(texture)
        self._reserve(1)
        u0, v0, u1, v1 = region.uv
        if transform.flip_x:
            u0, u1 = u1, u0
        self._instances[self._count] = (
            *rect,
            u0,
            v0,
            u1,
            v1,
            *color,
            Kind.SPRITE,
            0,
            0,
            0,
            transform.rotation,
            *transform.pivot,
            0,
        )
        self._count += 1

    def shape(
        self,
        rect: tuple[float, float, float, float],
        color: RGBA,
        radius: float = 0.0,
        border: float = 0.0,
    ) -> None:
        """Queue a filled (or, with `border`, outlined) rounded rectangle."""
        self._reserve(1)
        self._instances[self._count] = (
            *rect,
            0,
            0,
            0,
            0,
            *color,
            Kind.SHAPE,
            radius,
            border,
            0,
            0,
            0,
            0,
            0,
        )
        self._count += 1

    def extend(self, texture: moderngl.Texture, instances: np.ndarray) -> None:
        """Queue prebuilt instance rows (see `sprite_instances`)."""
        if len(instances) == 0:
            return
        self._use_texture(texture)
        self._reserve(len(instances))
        self._instances[self._count : self._count + len(instances)] = instances
        self._count += len(instances)

    def flush(self) -> None:
        """Draw everything queued so far."""
        if self._count == 0:
            return
        data = self._instances[: self._count]
        self._vbo.write(data.tobytes())
        self._texture.use(0)
        self._vao.render(
            moderngl.TRIANGLE_STRIP, vertices=4, instances=self._count
        )
        self._count = 0
        self.draw_calls += 1

    def release(self) -> None:
        """Free GPU resources."""
        self._vao.release()
        self._vbo.release()
        self._quad.release()
        self._white.release()
        self.program.release()


def rect_tuple(rect: Rect) -> tuple[float, float, float, float]:
    """`Rect` as an `(x, y, w, h)` tuple.

    Returns:
        tuple[float, float, float, float]: The rectangle.

    """
    return (rect.x, rect.y, rect.w, rect.h)
