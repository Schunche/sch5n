# Copyright (c) 2026 Schunche
"""The client application: window, GL context, main loop and scenes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
lazy from pathlib import Path

import moderngl

from sch5n.client.assets import ClientAssets
from sch5n.client.keybinds import Keybinds
from sch5n.client.render.atlas import create_texture
from sch5n.client.render.batch import SpriteBatch, rgba
from sch5n.client.render.text import TextRenderer
from sch5n.client.window import ResizeEvent, Window
from sch5n.game.config import GameMode, Settings
from sch5n.game.content import (
    Content,
    load_animations,
    load_settings,
    load_ui,
    save_settings,
)
from sch5n.log.logger import LOGGER
from sch5n.utility import path

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.scenes.base import Scene

MAX_TICKS_PER_FRAME = 5
"""Ticks are dropped beyond this, so a slow frame does not snowball."""
WINDOW_ICON_SIZE = 64


@dataclass(frozen=True, slots=True)
class Options:
    """Command line options of the client."""

    map_path: Path | None = None
    """Map to play or edit. `None` plays the default map."""
    game_mode: GameMode = GameMode.SURVIVAL
    seed: int | None = None
    max_frames: int | None = None
    """Stop after this many frames. For automated runs."""
    hidden: bool = False
    """Do not show the window. For automated runs."""
    settings_file: Path | None = None
    """Where user settings are read and saved. Defaults to the per-user
    config directory."""


class App:
    """Runs one scene at a time at a fixed tick rate."""

    def __init__(self, options: Options | None = None) -> None:
        """Load data, open the window and build GPU resources."""
        self.options = options or Options()
        self.content = Content.load(path.DATA_DIR)
        self.settings_file = (
            self.options.settings_file or path.user_settings_file()
        )
        self.settings = load_settings(path.DATA_DIR, self.settings_file)
        self.keybinds = Keybinds(self.settings.keybinds)
        self.ui = load_ui(path.DATA_DIR)
        self.animations = load_animations(path.DATA_DIR)

        self.window = Window(
            self.content.game.title,
            (self.settings.window_width, self.settings.window_height),
            vsync=self.settings.vsync,
            visible=not self.options.hidden,
        )
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        LOGGER.info("OpenGL renderer: %s", self.ctx.info["GL_RENDERER"])

        self.batch = SpriteBatch(self.ctx, path.SHADER_DIR)
        self.text = TextRenderer(self.ctx)
        self.assets = ClientAssets(
            self.ctx, path.TEXTURES_DIR, self.content, self.animations
        )
        self.window.set_icon(
            self.assets.load_image(
                self.animations.window_icon,
                (WINDOW_ICON_SIZE, WINDOW_ICON_SIZE),
            )
        )
        self.window.hide_cursor()
        self._apply_video(None)
        self._textures: dict[str, moderngl.Texture] = {}

        self.screen: tuple[int, int] = self.window.size
        self.scene: Scene | None = None
        self._next_scene: Scene | None = None
        self.frame = 0
        self.fps = 0.0
        self._update_viewport()

    @property
    def tick_rate(self) -> int:
        """Game ticks per second."""
        return self.content.game.tick_rate

    def texture(
        self, image: str, size: tuple[int, int] | None = None
    ) -> moderngl.Texture:
        """Load a standalone texture (not in the atlas) once.

        Returns:
            moderngl.Texture: The texture.

        """
        key = f"{image}@{size}"
        texture = self._textures.get(key)
        if texture is None:
            texture = self._textures[key] = create_texture(
                self.ctx, self.assets.load_image(image, size)
            )
        return texture

    def update_settings(self, **changes: object) -> None:
        """Change settings, apply them to the window and save them.

        The current keybinds are always included.
        """
        previous = self.settings
        self.settings = Settings.model_validate({
            **previous.model_dump(),
            **changes,
            "keybinds": self.keybinds.to_config(),
        })
        self._apply_video(previous)
        save_settings(self.settings, self.settings_file)
        LOGGER.info("Saved settings to %s", self.settings_file)

    def _apply_video(self, previous: Settings | None) -> None:
        s = self.settings
        size = (s.window_width, s.window_height)
        if previous is None or previous.fullscreen != s.fullscreen:
            self.window.set_fullscreen(fullscreen=s.fullscreen, size=size)
        if previous is not None and (
            (previous.window_width, previous.window_height) != size
        ):
            self.window.set_size(size)
        if previous is None or previous.vsync != s.vsync:
            Window.set_vsync(vsync=s.vsync)

    def switch(self, scene: Scene) -> None:
        """Make `scene` active at the end of the current frame."""
        self._next_scene = scene

    def quit(self) -> None:
        """Stop the main loop after the current frame."""
        self.window.close()

    def _update_viewport(self) -> None:
        self.screen = self.window.size
        fb_w, fb_h = self.window.framebuffer_size
        self.ctx.viewport = (0, 0, fb_w, fb_h)

    @property
    def pending_scene(self) -> Scene | None:
        """Scene that becomes active at the end of the frame, if any."""
        return self._next_scene

    def _apply_scene_switch(self, current: Scene) -> Scene:
        """Activate the pending scene, if any.

        Returns:
            Scene: The active scene.

        """
        upcoming = self._next_scene
        if upcoming is None:
            return current
        self._next_scene = None
        current.on_exit()
        self.scene = upcoming
        LOGGER.debug("Scene: %s", type(upcoming).__name__)
        upcoming.on_enter()
        return upcoming

    def draw_cursor(self) -> None:
        """Draw the custom mouse cursor in screen space."""
        region = self.assets.cursor
        x, y = self.window.mouse_pos
        self.batch.sprite(
            self.assets.atlas,
            (round(x), round(y), region.width, region.height),
            region,
        )

    def clear(self, color: tuple[int, int, int]) -> None:
        """Clear the screen."""
        r, g, b, _ = rgba(color)
        self.ctx.clear(r, g, b)

    def run(self, first: Callable[[App], Scene]) -> None:
        """Run the main loop until the window closes."""
        scene = self.scene = first(self)
        scene.on_enter()

        tick = 1.0 / self.tick_rate
        previous = Window.time()
        lag = 0.0
        fps_timer, fps_frames = previous, 0

        try:
            while not self.window.should_close:
                now = Window.time()
                lag += min(now - previous, tick * MAX_TICKS_PER_FRAME)
                previous = now

                for event in self.window.poll():
                    if isinstance(event, ResizeEvent):
                        self._update_viewport()
                    scene.on_event(event)

                while lag >= tick:
                    scene.tick()
                    lag -= tick

                self.batch.draw_calls = 0
                scene.render()
                self.batch.flush()
                self.window.swap()
                scene = self._apply_scene_switch(scene)

                self.frame += 1
                fps_frames += 1
                if now - fps_timer >= 1.0:
                    self.fps = fps_frames / (now - fps_timer)
                    fps_timer, fps_frames = now, 0

                if (
                    self.options.max_frames is not None
                    and self.frame >= self.options.max_frames
                ):
                    break
                frame_limit = (
                    0 if self.settings.vsync else self.settings.fps_limit
                )
                if frame_limit > 0:
                    remaining = 1.0 / frame_limit - (Window.time() - now)
                    if remaining > 0:
                        time.sleep(remaining)
        finally:
            scene.on_exit()
            self.release()

    def release(self) -> None:
        """Free resources and close the window."""
        for texture in self._textures.values():
            texture.release()
        self.text.release()
        self.assets.release()
        self.batch.release()
        self.window.destroy()
        LOGGER.info("Closed after %s frames", self.frame)
