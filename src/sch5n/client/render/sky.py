# Copyright (c) 2026 Schunche
"""The sky behind the world, drawn by a shader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.client.render.program import uniform

if TYPE_CHECKING:
    from pathlib import Path

    import moderngl

    from sch5n.client.camera import Camera
    from sch5n.game.config import Color, SkyConfig


def _rgb(color: Color) -> tuple[float, float, float]:
    r, g, b = color[:3]
    return (r / 255, g / 255, b / 255)


def horizon_on_screen(
    camera: Camera, horizon: float, screen_height: float, parallax: float
) -> float:
    """Screen y of the sky's horizon, which moves less than the world.

    Returns:
        float: Pixels from the top of the screen.

    """
    return screen_height / 2 + (horizon - camera.center_y) * parallax


class SkyRenderer:
    """Fills the screen with the sky."""

    def __init__(self, ctx: moderngl.Context, shader_dir: Path) -> None:
        """Compile the sky shader."""
        self.ctx = ctx
        self.program = ctx.program(
            vertex_shader=(shader_dir / "fullscreen.vert").read_text(
                encoding="utf-8"
            ),
            fragment_shader=(shader_dir / "sky.frag").read_text(
                encoding="utf-8"
            ),
        )
        # The vertices come from gl_VertexID, no buffers are needed.
        self.vao = ctx.vertex_array(self.program, [])

    def draw(
        self,
        config: SkyConfig,
        camera: Camera,
        screen: tuple[int, int],
        horizon: float,
    ) -> None:
        """Draw the sky for a camera looking at a world.

        Args:
            config: Sky colors and sizes.
            camera: The world camera.
            screen: Screen size in screen pixels.
            horizon: World y of the surface, where the sky begins.

        """
        width, height = self.ctx.viewport[2:]
        program = self.program
        uniform(program, "u_resolution").value = (float(width), float(height))
        uniform(program, "u_scale").value = height / max(screen[1], 1)
        uniform(program, "u_horizon_y").value = horizon_on_screen(
            camera, horizon, screen[1], config.parallax
        )
        uniform(program, "u_height").value = float(config.height)
        uniform(program, "u_view_top").value = camera.top_left(screen)[1]
        uniform(program, "u_world_per_px").value = 1 / camera.zoom
        uniform(program, "u_surface").value = horizon
        uniform(program, "u_underground").value = config.underground
        uniform(program, "u_horizon").value = _rgb(config.horizon)
        uniform(program, "u_middle").value = _rgb(config.middle)
        uniform(program, "u_zenith").value = _rgb(config.zenith)
        uniform(program, "u_sun").value = config.sun_position
        uniform(program, "u_sun_size").value = config.sun_size
        uniform(program, "u_sun_color").value = _rgb(config.sun)
        uniform(program, "u_deep").value = _rgb(config.deep)
        self.vao.render(vertices=3)

    def release(self) -> None:
        """Free GPU resources."""
        self.vao.release()
        self.program.release()
