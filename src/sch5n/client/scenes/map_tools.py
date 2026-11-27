# Copyright (c) 2026 Schunche
"""Map viewer and map editor."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.keybinds import Action, Context, ContextBinds
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.menu import SettingsScene
from sch5n.client.window import KeyEvent
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
    """Fly over a map. Uses the map viewer key bindings."""

    title = "Map Viewer"
    context = Context.VIEWER

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

    @property
    def keys(self) -> ContextBinds:
        """Bindings of this tool."""
        return self.app.keybinds[self.context]

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

    def on_action(self, action: Action) -> None:
        """Handle a pressed binding."""
        mouse = self.app.window.mouse_pos
        match action:
            case Action.ZOOM_IN:
                self.camera.zoom_at(ZOOM_STEP, mouse)
            case Action.ZOOM_OUT:
                self.camera.zoom_at(1 / ZOOM_STEP, mouse)
            case Action.RESET_CAMERA:
                self.camera = Camera()
            case Action.SETTINGS:
                self.app.switch(SettingsScene(self.app, back=self))
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle input."""
        if (
            isinstance(event, KeyEvent)
            and event.pressed
            and event.key == glfw.KEY_ESCAPE
        ):
            self.on_escape()
            return
        action = self.keys.pressed(event)
        if action is not None:
            self.on_action(action)

    def tick(self) -> None:
        """Pan the camera."""
        window = self.app.window
        keys = self.keys
        dx = keys.is_held(Action.PAN_RIGHT, window) - keys.is_held(
            Action.PAN_LEFT, window
        )
        dy = keys.is_held(Action.PAN_DOWN, window) - keys.is_held(
            Action.PAN_UP, window
        )
        speed = PAN_SPEED / self.camera.zoom
        self.camera.x += dx * speed
        self.camera.y += dy * speed

    def status_lines(self) -> list[str]:
        """Text shown in the corner.

        Returns:
            list[str]: Lines of text.

        """
        x, y = self.mouse_tile()
        settings = self.keys.slots(Action.SETTINGS)[0]
        hint = f"{settings.label}: controls  " if settings else ""
        zoom = self.camera.zoom
        tiles = len(self.tilemap)
        line = f"{x}, {y}  zoom {zoom:.2f}  {tiles} tiles  "
        return [f"{line}{hint}Esc: {self.escape_hint}"]

    escape_hint = "quit"

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
            app.text.draw(
                app.batch, line, (8, y), TextStyle(size=14, color=color)
            )
        self.draw_screen_overlay()
        app.draw_cursor()

    def draw_screen_overlay(self) -> None:
        """Draw tool specific things in screen space."""


class EditorScene(ViewerScene):
    """Edit a map. Uses the map editor key bindings.

    Escape saves and quits.
    """

    title = "Map Editor"
    context = Context.EDITOR
    escape_hint = "save & quit"

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

    def on_action(self, action: Action) -> None:
        """Handle editor actions, then the shared ones."""
        match action:
            case Action.SAVE:
                self.save()
            case Action.NEXT_TILE:
                self.selected = (self.selected + 1) % len(self.palette)
            case Action.PREVIOUS_TILE:
                self.selected = (self.selected - 1) % len(self.palette)
            case _:
                super().on_action(action)

    def tick(self) -> None:
        """Pan, place and remove tiles."""
        super().tick()
        window = self.app.window
        x, y = self.mouse_tile()
        if self.keys.is_held(Action.PLACE_TILE, window):
            block, variant = self.palette[self.selected]
            self.tilemap.set(x, y, block, variant)
        elif self.keys.is_held(Action.ERASE_TILE, window):
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
            TextStyle(size=16, color=rgba(app.ui.color("text"))),
        )
