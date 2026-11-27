# Copyright (c) 2026 Schunche
"""The map viewer, which edits maps with `--edit`."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.keybinds import Action, Context, ContextBinds
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.settings import SettingsScene
from sch5n.client.ui import (
    Align,
    Button,
    GridLayout,
    aligned_rect,
    draw_panel,
    hit_button,
)
from sch5n.client.window import KeyEvent, MouseButtonEvent, ScrollEvent
from sch5n.client.world_view import TileRenderer
from sch5n.game.content import AIR
from sch5n.log.logger import LOGGER
from sch5n.math.rect import Rect
from sch5n.world.io import (
    BackupError,
    is_protected,
    load_tilemap,
    save_tilemap,
    tilemap_to_json,
)
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

PROMPT_TITLE = "Unsaved changes"
PROMPT_ENTRIES = (
    ("save", "Save & Quit"),
    ("discard", "Quit Without Saving"),
    ("cancel", "Keep Editing"),
)
PROMPT_PADDING = 24
PROMPT_GAP = 12
PROMPT_TITLE_SIZE = 20

PALETTE_COLUMNS = 4
PALETTE_CELL = 48
PALETTE_GAP = 6
PALETTE_PADDING = 12
PALETTE_MARGIN = 12
"""Space between the palette and the window's edges."""
PALETTE_TEXT_SIZE = 16
PALETTE_LABEL = PALETTE_TEXT_SIZE + 8
"""Height of the palette's title and of the block name below it."""
PALETTE_SCROLLBAR = 4

TOAST_TEXT_SIZE = 18
TOAST_PADDING = 12
TOAST_TOP = 16
TOAST_SECONDS = 2.5
TOAST_ERROR_SECONDS = 8.0
ERROR_COLOR = (255, 96, 96)


@dataclass(slots=True)
class Toast:
    """A short lived message about something that just happened."""

    text: str
    error: bool
    ticks: int
    """Ticks left to show it."""


class MapScene(Scene):
    """Fly over a map, or edit it.

    Viewing and editing share the map viewer's key bindings; the editing
    ones only work when editing. Blocks are picked from a palette on the
    right. Leaving with unsaved changes asks whether to save them.
    """

    has_backdrop = True

    def __init__(
        self,
        app: App,
        map_path: Path,
        *,
        editing: bool = False,
        edit_default: bool = False,
    ) -> None:
        """Open `map_path`. A missing file gives an empty map.

        Editing the default map needs `edit_default`.

        Raises:
            ValueError: Editing the default map without asking for it.

        """
        if editing and not edit_default and is_protected(map_path):
            msg = f"{map_path.name} is the default map and is protected"
            raise ValueError(msg)
        super().__init__(app)
        self.map_path = map_path
        self.editing = editing
        self.controls = Context.VIEWER
        blocks = app.content.blocks
        if map_path.exists():
            self.tilemap = load_tilemap(map_path, blocks)
        else:
            LOGGER.info("%s does not exist, starting empty", map_path)
            self.tilemap = TileMap(blocks)
        self._saved = tilemap_to_json(self.tilemap)
        """The map as loaded or last saved."""
        self.prompting = False
        """Whether the unsaved changes question is shown."""
        self.buttons: list[Button] = []
        self.panel = Rect(0, 0, 0, 0)
        self.toast: Toast | None = None
        self._leaving = False
        self._await_release = False
        """Do not edit until the mouse button that clicked the question or
        the palette is released."""
        if editing:
            app.close_guard = self.may_close
        self.tile_size = app.content.game.tile_size
        self.camera = Camera.showing_top_left((0, 0), app.screen)
        self.tiles = TileRenderer(app.assets, self.tile_size)
        self.palette = [
            (block.id, variant)
            for block in app.content.blocks
            for variant in range(len(block.spec.textures))
        ]
        self.selected = 0
        self.palette_scroll = 0
        """Rows of the palette scrolled past."""
        self._wheel = 0.0
        """Wheel movement over the palette not yet worth a row."""
        title = "Map Editor" if editing else "Map Viewer"
        app.window.set_title(f"{map_path.stem} - {title}")

    @property
    def keys(self) -> ContextBinds:
        """Bindings of the map viewer."""
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

    @property
    def unsaved(self) -> bool:
        """Whether the map differs from what was loaded or last saved."""
        return self.editing and tilemap_to_json(self.tilemap) != self._saved

    def save(self) -> bool:
        """Write the map to disk, and say on screen how that went.

        Returns:
            bool: False if it could not be written.

        """
        try:
            save_tilemap(self.map_path, self.tilemap)
        except OSError as error:
            LOGGER.exception("Cannot save %s", self.map_path)
            reason = error.strerror or str(error)
            if isinstance(error, BackupError):
                reason = f"backup failed: {reason}"
            self._notify(f"Not saved, {reason}", error=True)
            return False
        self._saved = tilemap_to_json(self.tilemap)
        self._notify(f"Saved {self.map_path.name}")
        LOGGER.info("Saved %s tiles to %s", len(self.tilemap), self.map_path)
        return True

    def _notify(self, text: str, *, error: bool = False) -> None:
        seconds = TOAST_ERROR_SECONDS if error else TOAST_SECONDS
        ticks = round(seconds * self.app.tick_rate)
        self.toast = Toast(text, error, ticks)

    def palette_grid(self) -> GridLayout:
        """Where the palette's blocks are on screen.

        Returns:
            GridLayout: The grid, docked to the right edge.

        """
        w, h = self.app.screen
        step = PALETTE_CELL + PALETTE_GAP
        width = PALETTE_COLUMNS * step - PALETTE_GAP
        chrome = 2 * (PALETTE_MARGIN + PALETTE_PADDING + PALETTE_LABEL)
        return GridLayout(
            count=len(self.palette),
            columns=PALETTE_COLUMNS,
            visible_rows=max(int((h - chrome + PALETTE_GAP) // step), 1),
            origin=(
                w - PALETTE_MARGIN - PALETTE_PADDING - width,
                PALETTE_MARGIN + PALETTE_PADDING + PALETTE_LABEL,
            ),
            cell=PALETTE_CELL,
            gap=PALETTE_GAP,
        )

    def palette_panel(self) -> Rect:
        """Area the palette covers. Tiles under it cannot be edited.

        Returns:
            Rect: Screen rectangle.

        """
        area = self.palette_grid().area
        return Rect(
            area.x - PALETTE_PADDING,
            area.y - PALETTE_LABEL - PALETTE_PADDING,
            area.w + 2 * PALETTE_PADDING,
            area.h + 2 * (PALETTE_LABEL + PALETTE_PADDING),
        )

    def over_palette(self, pos: tuple[float, float]) -> bool:
        """Whether a screen position is on the palette.

        Returns:
            bool: Always False when only viewing.

        """
        return self.editing and self.palette_panel().contains_point(*pos)

    def _select(self, index: int) -> None:
        """Pick a block of the palette and scroll it into view."""
        self.selected = index % len(self.palette)
        self.palette_scroll = self.palette_grid().scroll_to(
            self.selected, self.palette_scroll
        )

    def may_close(self) -> bool:
        """Whether the program may close. Asks first about unsaved changes.

        Returns:
            bool: False while the question is open.

        """
        if self._leaving or not self.unsaved:
            return True
        self.prompting = True
        # The window may be closed from the settings opened from here.
        self.app.switch(self)
        return False

    def on_escape(self) -> None:
        """Quit, or close the question about unsaved changes."""
        if self.prompting:
            self._answer("cancel")
        elif self.may_close():
            self.app.quit()

    def _answer(self, answer: str | None) -> None:
        """Handle a button of the unsaved changes question."""
        match answer:
            case "save" if self.save():
                self._leave()
            case "discard":
                self._leave()
            case "save" | "cancel":
                self.prompting = False
                self._await_release = True
            case _:
                pass

    def _leave(self) -> None:
        self._leaving = True
        self.app.quit()

    def layout(self) -> None:
        """Keep the palette in range and center the question."""
        self.palette_scroll = self.palette_grid().clamp_scroll(
            self.palette_scroll
        )
        app = self.app
        style = app.ui.button
        width = max(
            style.width,
            *(
                app.text.measure(label, style.font_size)[0] + PROMPT_PADDING
                for _, label in PROMPT_ENTRIES
            ),
        )
        step = style.height + PROMPT_GAP
        title = PROMPT_TITLE_SIZE + PROMPT_PADDING
        w, h = app.screen
        height = title + len(PROMPT_ENTRIES) * step - PROMPT_GAP
        self.panel = Rect(
            (w - width) / 2 - PROMPT_PADDING,
            (h - height) / 2 - PROMPT_PADDING,
            width + 2 * PROMPT_PADDING,
            height + 2 * PROMPT_PADDING,
        )
        top = self.panel.y + PROMPT_PADDING + title
        self.buttons = [
            Button(
                button_id,
                label,
                aligned_rect(
                    (w / 2, top + i * step + style.height / 2),
                    (width, style.height),
                    Align.CENTER,
                ),
            )
            for i, (button_id, label) in enumerate(PROMPT_ENTRIES)
        ]

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
                self._select(self.selected + 1)
            case Action.PREVIOUS_TILE if self.editing:
                self._select(self.selected - 1)
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
        if self.prompting:
            if (
                isinstance(event, MouseButtonEvent)
                and event.pressed
                and event.button == glfw.MOUSE_BUTTON_LEFT
            ):
                self._answer(hit_button(self.buttons, event.pos))
            return
        if self._on_palette_event(event):
            return
        action = self.keys.pressed(event)
        if action is not None:
            self.on_action(action)

    def _on_palette_event(self, event: Event) -> bool:
        """Scroll the palette, or pick a block from it.

        Returns:
            bool: Whether the event was meant for the palette.

        """
        match event:
            case ScrollEvent() if self.over_palette(self.app.window.mouse_pos):
                self._wheel -= event.dy
                rows = int(self._wheel)
                self._wheel -= rows
                self.palette_scroll = self.palette_grid().clamp_scroll(
                    self.palette_scroll + rows
                )
                return True
            case MouseButtonEvent(pressed=True) if self.over_palette(
                event.pos
            ):
                self._await_release = True
                if event.button == glfw.MOUSE_BUTTON_LEFT:
                    index = self.palette_grid().cell_at(
                        event.pos, self.palette_scroll
                    )
                    if index is not None:
                        self.selected = index
                return True
            case _:
                return False

    def tick(self) -> None:
        """Pan the camera; when editing, place and remove tiles."""
        if self.toast is not None:
            self.toast.ticks -= 1
            if self.toast.ticks <= 0:
                self.toast = None
        if self.prompting:
            return
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
        place = keys.is_held(Action.PLACE_TILE, window)
        erase = keys.is_held(Action.ERASE_TILE, window)
        if self._await_release:
            self._await_release = place or erase
        elif self.over_palette(window.mouse_pos):
            return
        elif place:
            block, variant = self.palette[self.selected]
            self.tilemap.set(x, y, block, variant)
        elif erase:
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
        line = f"{x}, {y}  zoom {zoom:.2f}  {tiles} tiles  "
        return [f"{line}{hint}Esc: quit"]

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
        if (
            self.editing
            and not self.prompting
            and not self.over_palette(app.window.mouse_pos)
        ):
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
            self._draw_palette()
        if self.prompting:
            self._draw_prompt()
        self._draw_toast()
        app.draw_cursor()

    def _block_name(self, index: int) -> str:
        """Name of a palette entry, numbered if the block has variants.

        Returns:
            str: The name.

        """
        block_id, variant = self.palette[index]
        block = self.app.content.blocks.get(block_id)
        if block is None:
            return "?"
        if len(block.spec.textures) > 1:
            return f"{block.name} {variant + 1}"
        return block.name

    def _draw_palette(self) -> None:
        """Draw the grid of blocks, naming the hovered or selected one."""
        app = self.app
        grid = self.palette_grid()
        panel = self.palette_panel()
        draw_panel(app.batch, panel, app.ui)
        mouse = app.window.mouse_pos
        hovered = (
            None
            if self.prompting
            else grid.cell_at(mouse, self.palette_scroll)
        )
        for index in grid.visible(self.palette_scroll):
            self._draw_cell(
                index,
                grid.cell_rect(index, self.palette_scroll),
                hovered=index == hovered,
            )
        if grid.max_scroll:
            self._draw_scrollbar(grid)

        color = rgba(app.ui.color("text"))
        middle = panel.center[0]
        edge = PALETTE_PADDING + PALETTE_LABEL / 2
        name = self._block_name(self.selected if hovered is None else hovered)
        for text, y in (
            ("Blocks", panel.top + edge),
            (name, panel.bottom - edge),
        ):
            app.text.draw(
                app.batch,
                text,
                (middle, y),
                TextStyle(PALETTE_TEXT_SIZE, color, Anchor.CENTER),
            )

    def _draw_cell(self, index: int, cell: Rect, *, hovered: bool) -> None:
        """Draw one block of the palette."""
        app = self.app
        style = app.ui.button
        box = (cell.x, cell.y, cell.w, cell.h)
        fill = "button_hover" if hovered else "button_inner"
        app.batch.shape(
            box, rgba(app.ui.color(fill)), radius=style.border_radius
        )
        selected = index == self.selected
        app.batch.shape(
            box,
            rgba(app.ui.color("accent" if selected else "button_border")),
            radius=style.border_radius,
            border=style.border_width if selected else style.border_width / 2,
        )
        block, variant = self.palette[index]
        # Already tile sized, so it is drawn pixel for pixel.
        size = self.tile_size
        x, y = cell.center
        app.batch.sprite(
            app.assets.atlas,
            (round(x - size / 2), round(y - size / 2), size, size),
            app.assets.blocks[block][variant],
        )

    def _draw_scrollbar(self, grid: GridLayout) -> None:
        """Show which part of the palette is visible."""
        app = self.app
        area = grid.area
        x = area.right + (PALETTE_PADDING - PALETTE_SCROLLBAR) / 2
        height = area.h * grid.visible_rows / grid.rows
        top = area.y + area.h * self.palette_scroll / grid.rows
        for y, h, color in (
            (area.y, area.h, "button_inner"),
            (top, height, "accent"),
        ):
            app.batch.shape(
                (x, y, PALETTE_SCROLLBAR, h),
                rgba(app.ui.color(color)),
                radius=PALETTE_SCROLLBAR / 2,
            )

    def _draw_toast(self) -> None:
        """Show the latest message at the top of the window."""
        toast = self.toast
        if toast is None:
            return
        app = self.app
        w, h = app.text.measure(toast.text, TOAST_TEXT_SIZE)
        width = w + 2 * TOAST_PADDING
        height = h + 2 * TOAST_PADDING
        # Centered in the room left of the palette, when it fits there.
        room = self.palette_panel().x if self.editing else app.screen[0]
        x = max((room - width) / 2, 0)
        rect = Rect(x, TOAST_TOP, width, height)
        draw_panel(app.batch, rect, app.ui)
        edge = ERROR_COLOR if toast.error else app.ui.color("accent")
        app.batch.shape(
            (rect.x, rect.y, rect.w, rect.h),
            rgba(edge),
            radius=app.ui.button.border_radius,
            border=app.ui.button.border_width,
        )
        app.text.draw(
            app.batch,
            toast.text,
            rect.center,
            TextStyle(
                TOAST_TEXT_SIZE, rgba(app.ui.color("text")), Anchor.CENTER
            ),
        )

    def _draw_prompt(self) -> None:
        """Ask what to do with unsaved changes."""
        app = self.app
        draw_panel(app.batch, self.panel, app.ui)
        app.text.draw(
            app.batch,
            PROMPT_TITLE,
            (
                app.screen[0] / 2,
                self.panel.y + PROMPT_PADDING + PROMPT_TITLE_SIZE / 2,
            ),
            TextStyle(
                PROMPT_TITLE_SIZE, rgba(app.ui.color("text")), Anchor.CENTER
            ),
        )
        mouse = app.window.mouse_pos
        for button in self.buttons:
            button.draw(app.batch, app.text, app.ui, mouse)

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
        app.text.draw(
            app.batch,
            self._block_name(self.selected),
            (pad * 2 + size, pad + size / 4),
            TextStyle(size=16, color=rgba(app.ui.color("text"))),
        )
