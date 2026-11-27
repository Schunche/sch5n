# Copyright (c) 2026 Schunche
"""Full screen menu backgrounds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.client.render.program import uniform
from sch5n.game.config import BackgroundKind

if TYPE_CHECKING:
    from pathlib import Path

    import moderngl

    from sch5n.game.config import ThemeBackground


class BackgroundRenderer:
    """Draws the animated background shader over the whole screen."""

    def __init__(self, ctx: moderngl.Context, shader_dir: Path) -> None:
        """Compile the background shader."""
        self.ctx = ctx
        self.program = ctx.program(
            vertex_shader=(shader_dir / "fullscreen.vert").read_text(
                encoding="utf-8"
            ),
            fragment_shader=(shader_dir / "background.frag").read_text(
                encoding="utf-8"
            ),
        )
        # The vertices come from gl_VertexID, no buffers are needed.
        self.vao = ctx.vertex_array(self.program, [])

    def draw(self, background: ThemeBackground, seconds: float) -> None:
        """Fill the screen. Only shader backgrounds draw anything."""
        if background.kind is not BackgroundKind.SHADER:
            return
        program = self.program
        uniform(program, "u_resolution").value = tuple(
            float(v) for v in self.ctx.viewport[2:]
        )
        uniform(program, "u_time").value = seconds * background.speed
        uniform(program, "u_pixel").value = float(background.pixel_size)
        dark, mid, light = (
            tuple(c / 255 for c in color) for color in background.colors
        )
        uniform(program, "u_dark").value = dark
        uniform(program, "u_mid").value = mid
        uniform(program, "u_light").value = light
        self.vao.render(vertices=3)

    def release(self) -> None:
        """Free GPU resources."""
        self.vao.release()
        self.program.release()
