# Copyright (c) 2026 Schunche
"""The map viewer, which edits maps with `--edit`."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.keybinds import Action, Context, ContextBinds
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.settings import SettingsScene
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


class MapScene(Scene):
    """Fly over a map, or edit it.

    Viewing and editing have their own key bindings, as the mouse wheel
    zooms in one and picks the tile in the other. Editing saves on Escape.
    """

    has_backdrop = True

    def __init__(
        self, app: App, map_path: Path, *, editing: bool = False
    ) -> None:
        """Open `map_path`. A missing file gives an empty map."""
        super().__init__(app)
        self.map_path = map_path
        self.editing = editing
        self.controls = Context.EDITOR if editing else Context.VIEWER
        blocks = app.content.blocks
        if map_path.exists():
            self.tilemap = load_tilemap(map_path, blocks)
        else:
            LOGGER.info("%s does not exist, starting empty", map_path)
            self.tilemap = TileMap(blocks)
        self.tile_size = app.content.game.tile_size
        self.camera = Camera.showing_top_left((0, 0), app.screen)
        self.tiles = TileRenderer(app.assets, self.tile_size)
        self.palette = [
            (block.id, variant)
            for block in app.content.blocks
            for variant in range(len(block.spec.textures))
        ]
        self.selected = 0
        title = "Map Editor" if editing else "Map Viewer"
        app.window.set_title(f"{map_path.stem} - {title}")

    @property
    def keys(self) -> ContextBinds:
        """Bindings of the current mode."""
        return self.app.keybinds[self.controls]

    def mouse_tile(self) -> tuple[int, int]:
        """Tile under the mouse cursor.

        Returns:
            tuple[int, int]: Tile coordinate.

        """
        x, y = self.camera.screen_to_world(
            self.app.window.mouse_pos, self.app.screen
        )
        return math.floor(x / self.tile_size), math.floor(y / self.tile_size)

    def save(self) -> None:
        """Write the map to disk."""
        save_tilemap(self.map_path, self.tilemap)
        LOGGER.info("Saved %s tiles to %s", len(self.tilemap), self.map_path)

    def on_escape(self) -> None:
        """Quit, saving first when editing."""
        if self.editing:
            self.save()
        self.app.quit()

    def on_action(self, action: Action) -> None:
        """Handle a pressed binding."""
        mouse = self.app.window.mouse_pos
        match action:
            case Action.ZOOM_IN:
                self.camera.zoom_at(ZOOM_STEP, mouse, self.app.screen)
            case Action.ZOOM_OUT:
                self.camera.zoom_at(1 / ZOOM_STEP, mouse, self.app.screen)
            case Action.RESET_CAMERA:
                self.camera = Camera.showing_top_left((0, 0), self.app.screen)
            case Action.SETTINGS:
                self.app.switch(SettingsScene(self.app, back=self))
            case Action.SAVE if self.editing:
                self.save()
            case Action.NEXT_TILE if self.editing:
                self.selected = (self.selected + 1) % len(self.palette)
            case Action.PREVIOUS_TILE if self.editing:
                self.selected = (self.selected - 1) % len(self.palette)
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
        """Pan the camera; when editing, place and remove tiles."""
        window = self.app.window
        keys = self.keys
        dx = keys.is_held(Action.PAN_RIGHT, window) - keys.is_held(
            Action.PAN_LEFT, window
        )
        dy = keys.is_held(Action.PAN_DOWN, window) - keys.is_held(
            Action.PAN_UP, window
        )
        speed = PAN_SPEED / self.camera.zoom
        self.camera.pan(dx * speed, dy * speed)
        if not self.editing:
            return
        x, y = self.mouse_tile()
        if keys.is_held(Action.PLACE_TILE, window):
            block, variant = self.palette[self.selected]
            self.tilemap.set(x, y, block, variant)
        elif keys.is_held(Action.ERASE_TILE, window):
            self.tilemap.set(x, y, AIR)

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
        escape = "save & quit" if self.editing else "quit"
        line = f"{x}, {y}  zoom {zoom:.2f}  {tiles} tiles  "
        return [f"{line}{hint}Esc: {escape}"]

    def _selected_region(self) -> Region:
        block, variant = self.palette[self.selected]
        return self.app.assets.blocks[block][variant]

    def draw_backdrop(self) -> None:
        """Draw the map without the editing overlays."""
        app = self.app
        app.clear(BACKGROUND)
        app.batch.begin(
            app.screen, self.camera.offset(app.screen), self.camera.zoom
        )
        self.tiles.draw(
            app.batch,
            self.tilemap,
            self.camera.view(app.screen),
            breakage=False,
        )

    def render(self) -> None:
        """Draw the map, and what editing needs."""
        app = self.app
        self.draw_backdrop()
        if self.editing:
            self._draw_ghost()

        app.batch.begin(app.screen)
        color = rgba(app.ui.color("text"))
        y = app.screen[1] - 8
        for line in reversed(self.status_lines()):
            _, h = app.text.measure(line, 14)
            y -= h
            app.text.draw(
                app.batch, line, (8, y), TextStyle(size=14, color=color)
            )
        if self.editing:
            self._draw_selected()
        app.draw_cursor()

    def _draw_ghost(self) -> None:
        """Ghost of the selected tile under the cursor, in world space."""
        x, y = self.mouse_tile()
        size = self.tile_size
        self.app.batch.sprite(
            self.app.assets.atlas,
            (x * size, y * size, size, size),
            self._selected_region(),
            (1.0, 1.0, 1.0, 0.5),
        )

    def _draw_selected(self) -> None:
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
