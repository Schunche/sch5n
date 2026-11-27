# Copyright (c) 2026 Schunche
"""Map viewer and map editor."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.render.batch import rgba
from sch5n.client.scenes.base import Scene
from sch5n.client.window import KeyEvent, ScrollEvent
from sch5n.client.world_view import TileRenderer
from sch5n.game.content import AIR
from sch5n.log.logger import LOGGER
from sch5n.world.io import load_tilemap, save_tilemap
from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.client.app import App
    from sch5n.client.render.atlas import Region
    from sch5n.client.window import Event

PAN_SPEED = 5.0
"""Screen pixels per tick."""
ZOOM_STEP = 1.25
BACKGROUND = (0, 0, 0)


class ViewerScene(Scene):
    """Fly over a map. WASD to pan, wheel to zoom, R to reset."""

    title = "Map Viewer"

    def __init__(self, app: App, map_path: Path) -> None:
        """Open `map_path`. A missing file gives an empty map."""
        super().__init__(app)
        self.map_path = map_path
        blocks = app.content.blocks
        if map_path.exists():
            self.tilemap = load_tilemap(map_path, blocks)
        else:
            LOGGER.info("%s does not exist, starting empty", map_path)
            self.tilemap = TileMap(blocks)
        self.tile_size = app.content.game.tile_size
        self.camera = Camera()
        self.tiles = TileRenderer(app.assets, self.tile_size)
        app.window.set_title(f"{map_path.stem} - {self.title}")

    def reset_camera(self) -> None:
        """Go back to the origin at zoom 1."""
        self.camera = Camera()

    def mouse_tile(self) -> tuple[int, int]:
        """Tile under the mouse cursor.

        Returns:
            tuple[int, int]: Tile coordinate.

        """
        x, y = self.camera.screen_to_world(self.app.window.mouse_pos)
        return math.floor(x / self.tile_size), math.floor(y / self.tile_size)

    def on_escape(self) -> None:
        """Leave the tool."""
        self.app.quit()

    def on_scroll(self, dy: float) -> None:
        """Zoom around the cursor."""
        self.camera.zoom_at(
            ZOOM_STEP ** math.copysign(1, dy), self.app.window.mouse_pos
        )

    def on_key(self, event: KeyEvent) -> None:
        """Handle tool specific keys."""
        match event.key:
            case glfw.KEY_ESCAPE:
                self.on_escape()
            case glfw.KEY_R:
                self.reset_camera()
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle input."""
        match event:
            case KeyEvent() if event.pressed:
                self.on_key(event)
            case ScrollEvent(dy=dy) if dy:
                self.on_scroll(dy)
            case _:
                pass

    def tick(self) -> None:
        """Pan the camera."""
        window = self.app.window
        dx = window.is_key_down(glfw.KEY_D) - window.is_key_down(glfw.KEY_A)
        dy = window.is_key_down(glfw.KEY_S) - window.is_key_down(glfw.KEY_W)
        speed = PAN_SPEED / self.camera.zoom
        self.camera.x += dx * speed
        self.camera.y += dy * speed

    def status_lines(self) -> list[str]:
        """Text shown in the corner.

        Returns:
            list[str]: Lines of text.

        """
        x, y = self.mouse_tile()
        return [
            f"{x}, {y}  zoom {self.camera.zoom:.2f}  {len(self.tilemap)} tiles"
        ]

    def draw_overlay(self) -> None:
        """Draw tool specific things in world space."""

    def render(self) -> None:
        """Draw the map."""
        app = self.app
        app.clear(BACKGROUND)
        app.batch.begin(app.screen, self.camera.offset(), self.camera.zoom)
        self.tiles.draw(
            app.batch,
            self.tilemap,
            self.camera.view(app.screen),
            breakage=False,
        )
        self.draw_overlay()

        app.batch.begin(app.screen)
        color = rgba(app.ui.color("text"))
        y = app.screen[1] - 8
        for line in reversed(self.status_lines()):
            _, h = app.text.measure(line, 14)
            y -= h
            app.text.draw(app.batch, line, (8, y), 14, color)
        self.draw_screen_overlay()
        app.draw_cursor()

    def draw_screen_overlay(self) -> None:
        """Draw tool specific things in screen space."""


class EditorScene(ViewerScene):
    """Edit a map.

    Left mouse places the selected tile, right mouse removes tiles, the
    wheel changes the selected tile (Ctrl + wheel zooms), Ctrl+S saves and
    Escape saves and quits.
    """

    title = "Map Editor"

    def __init__(self, app: App, map_path: Path) -> None:
        """Open `map_path` for editing."""
        super().__init__(app, map_path)
        self.palette = [
            (block.id, variant)
            for block in app.content.blocks
            for variant in range(len(block.spec.textures))
        ]
        self.selected = 0

    def save(self) -> None:
        """Write the map to disk."""
        save_tilemap(self.map_path, self.tilemap)
        LOGGER.info("Saved %s tiles to %s", len(self.tilemap), self.map_path)

    def on_escape(self) -> None:
        """Save, then quit."""
        self.save()
        super().on_escape()

    def on_key(self, event: KeyEvent) -> None:
        """Ctrl+S saves."""
        if event.key == glfw.KEY_S and event.mods & glfw.MOD_CONTROL:
            self.save()
            return
        super().on_key(event)

    def on_scroll(self, dy: float) -> None:
        """Cycle the palette; zoom with Ctrl held."""
        window = self.app.window
        if window.is_key_down(glfw.KEY_LEFT_CONTROL) or window.is_key_down(
            glfw.KEY_RIGHT_CONTROL
        ):
            super().on_scroll(dy)
            return
        step = 1 if dy > 0 else -1
        self.selected = (self.selected + step) % len(self.palette)

    def tick(self) -> None:
        """Pan, place and remove tiles."""
        window = self.app.window
        if not (
            window.is_key_down(glfw.KEY_LEFT_CONTROL)
            or window.is_key_down(glfw.KEY_RIGHT_CONTROL)
        ):
            super().tick()
        x, y = self.mouse_tile()
        if window.is_mouse_down(glfw.MOUSE_BUTTON_LEFT):
            block, variant = self.palette[self.selected]
            self.tilemap.set(x, y, block, variant)
        elif window.is_mouse_down(glfw.MOUSE_BUTTON_RIGHT):
            self.tilemap.set(x, y, AIR)

    def _selected_region(self) -> Region:
        block, variant = self.palette[self.selected]
        return self.app.assets.blocks[block][variant]

    def draw_overlay(self) -> None:
        """Ghost of the selected tile under the cursor."""
        x, y = self.mouse_tile()
        size = self.tile_size
        self.app.batch.sprite(
            self.app.assets.atlas,
            (x * size, y * size, size, size),
            self._selected_region(),
            (1.0, 1.0, 1.0, 0.5),
        )

    def draw_screen_overlay(self) -> None:
        """Preview of the selected tile in the corner."""
        app = self.app
        size = self.tile_size
        pad = size // 2
        app.batch.sprite(
            app.assets.atlas, (pad, pad, size, size), self._selected_region()
        )
        block = app.content.blocks.get(self.palette[self.selected][0])
        name = block.name if block is not None else "?"
        app.text.draw(
            app.batch,
            name,
            (pad * 2 + size, pad + size / 4),
            16,
            rgba(app.ui.color("text")),
        )

    def status_lines(self) -> list[str]:
        """Add editor help.

        Returns:
            list[str]: Lines of text.

        """
        return [
            (
                "LMB place  RMB erase  wheel: tile  Ctrl+wheel: zoom  "
                "Ctrl+S: save  Esc: save & quit"
            ),
            *super().status_lines(),
        ]
