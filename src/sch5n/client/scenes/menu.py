# Copyright (c) 2026 Schunche
"""Main menu and settings screens."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

import glfw

from sch5n.client.keybinds import MODIFIER_KEYS, Action, Binding, Context
from sch5n.client.render.batch import WHITE, rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import (
    Align,
    Button,
    TableLayout,
    aligned_rect,
    button_column,
    hit_button,
)
from sch5n.client.video import FPS_LIMITS, WINDOW_SIZES, cycle, fps_label
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ResizeEvent,
    ScrollEvent,
)
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.math.rect import Rect


class MenuScene(Scene):
    """Shared behaviour of simple button screens."""

    entries: ClassVar[tuple[tuple[str, str], ...]] = ()

    def __init__(self, app: App) -> None:
        """Create the screen."""
        super().__init__(app)
        self.buttons: list[Button] = []
        self.layout()

    def layout(self) -> None:
        """Place the buttons for the current window size."""
        w, h = self.app.screen
        self.buttons = button_column(
            self.entries,
            (w / 2, h / 2),
            self.app.ui.main_menu.button_spacing,
            self.app.ui,
        )

    def on_button(self, button_id: str) -> None:
        """React to a click on a button."""

    def on_escape(self) -> None:
        """React to the escape key."""

    def on_event(self, event: Event) -> None:
        """Handle clicks, escape and resizing."""
        match event:
            case ResizeEvent():
                self.layout()
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self.on_escape()
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT) if (
                event.pressed
            ):
                button_id = hit_button(self.buttons, event.pos)
                if button_id is not None:
                    self.on_button(button_id)
            case _:
                pass

    def draw_background(self) -> None:
        """Draw what is behind the buttons."""
        self.app.clear(self.app.ui.color("main_theme"))

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        self.draw_background()
        app.batch.begin(app.screen)
        self.draw_foreground()
        mouse = app.window.mouse_pos
        for button in self.buttons:
            button.draw(app.batch, app.text, app.ui, mouse)
        app.draw_cursor()

    def draw_foreground(self) -> None:
        """Draw extra content above the background."""


class MainMenu(MenuScene):
    """The title screen."""

    entries = (("play", "Play"), ("settings", "Settings"), ("exit", "Exit"))

    def on_button(self, button_id: str) -> None:
        """Start the game, open settings or quit."""
        match button_id:
            case "play":
                self.app.switch(PlayScene(self.app))
            case "settings":
                self.app.switch(SettingsScene(self.app, back=self))
            case "exit":
                self.app.quit()
            case _:
                pass

    def on_escape(self) -> None:
        """Quit."""
        self.app.quit()

    def draw_foreground(self) -> None:
        """Draw the background image stretched over the window."""
        app = self.app
        texture = app.texture(app.ui.main_menu.background)
        app.batch.sprite(texture, (0, 0, *app.screen))


class VideoOption(StrEnum):
    """Adjustable video settings."""

    DISPLAY_MODE = "Display mode"
    WINDOW_SIZE = "Window size"
    VSYNC = "VSync"
    FPS_LIMIT = "Frame rate limit"


@dataclass(frozen=True, slots=True)
class HeaderRow:
    """A section title."""

    title: str


@dataclass(frozen=True, slots=True)
class OptionRow:
    """A video setting; click to cycle its value."""

    option: VideoOption


@dataclass(frozen=True, slots=True)
class BindRow:
    """An action with its binding slots."""

    context: Context
    action: Action


type Row = HeaderRow | OptionRow | BindRow


def option_value(app: App, option: VideoOption) -> str:
    """Describe the current value of a video setting.

    Returns:
        str: Display text.

    """
    s = app.settings
    match option:
        case VideoOption.DISPLAY_MODE:
            return "Fullscreen" if s.fullscreen else "Windowed"
        case VideoOption.WINDOW_SIZE:
            return f"{s.window_width} x {s.window_height}"
        case VideoOption.VSYNC:
            return "On" if s.vsync else "Off"
        case VideoOption.FPS_LIMIT:
            text = fps_label(s.fps_limit)
            return f"{text} (VSync on)" if s.vsync else text


def change_option(app: App, option: VideoOption, step: int) -> None:
    """Move a video setting `step` values forward (or back), apply, save."""
    s = app.settings
    match option:
        case VideoOption.DISPLAY_MODE:
            app.update_settings(fullscreen=not s.fullscreen)
        case VideoOption.WINDOW_SIZE:
            width, height = cycle(
                WINDOW_SIZES, (s.window_width, s.window_height), step
            )
            app.update_settings(window_width=width, window_height=height)
        case VideoOption.VSYNC:
            app.update_settings(vsync=not s.vsync)
        case VideoOption.FPS_LIMIT:
            app.update_settings(fps_limit=cycle(FPS_LIMITS, s.fps_limit, step))


def settings_rows(app: App) -> list[Row]:
    """Every row of the settings screen, top to bottom.

    Returns:
        list[Row]: The rows.

    """
    rows: list[Row] = [HeaderRow("Video")]
    rows += [OptionRow(option) for option in VideoOption]
    for binds in app.keybinds:
        rows.append(HeaderRow(f"Controls: {binds.context.label}"))
        rows += [BindRow(binds.context, action) for action, _ in binds]
    return rows


class SettingsScene(Scene):
    """Video settings and rebindable controls of every program.

    Video values: left click for the next value, right click for the
    previous one. Bindings: click a slot, then press a key, mouse button or
    wheel direction, with modifiers if wanted. Escape cancels, Backspace or
    Delete clears; right clicking a slot clears it too. Changes are applied
    and saved immediately.
    """

    ROW_HEIGHT = 32
    TABLE_TOP = 80
    TABLE_BOTTOM_MARGIN = 130
    FOOTER_BUTTON_WIDTH = 160
    CLEAR_KEYS = frozenset({glfw.KEY_BACKSPACE, glfw.KEY_DELETE})

    def __init__(
        self, app: App, back: Scene, *, in_game: bool = False
    ) -> None:
        """Create the screen. `back` is shown again when leaving."""
        super().__init__(app)
        self.back = back
        self.in_game = in_game
        self.rows = settings_rows(app)
        self.scroll = 0.0
        self.capturing: BindRow | None = None
        self.capture_slot = 0
        self._pending_modifier: int | None = None
        """Modifier key pressed while capturing, bound if released alone."""
        self.message = ""
        self.table = TableLayout.centered(0, app.screen, 0, 0)
        self.buttons: list[Button] = []
        self.layout()

    def layout(self) -> None:
        """Place the table and footer buttons for the window size."""
        w, h = self.app.screen
        self.table = TableLayout.centered(
            len(self.rows),
            (w, h),
            self.TABLE_TOP,
            h - self.TABLE_BOTTOM_MARGIN,
            row_height=self.ROW_HEIGHT,
        )
        self.scroll = self.table.clamp_scroll(self.scroll)

        entries = [("reset", "Reset Controls"), ("back", "Back")]
        if self.in_game:
            entries.append(("menu", "Main Menu"))
        size = (self.FOOTER_BUTTON_WIDTH, self.app.ui.button.height)
        gap = 16
        total = len(entries) * size[0] + (len(entries) - 1) * gap
        x = (w - total) / 2
        self.buttons = [
            Button(
                button_id,
                label,
                aligned_rect(
                    (x + i * (size[0] + gap), h - 60), size, Align.TOP_LEFT
                ),
            )
            for i, (button_id, label) in enumerate(entries)
        ]

    def row_index(self, row: Row) -> int:
        """Position of a row in the table.

        Returns:
            int: Row index.

        """
        return self.rows.index(row)

    # Input

    def _leave(self) -> None:
        self.app.switch(self.back)

    def _assign(self, binding: Binding | None) -> None:
        if self.capturing is None:
            return
        row, slot = self.capturing, self.capture_slot
        self.capturing = None
        self._pending_modifier = None
        binds = self.app.keybinds[row.context]
        try:
            lost = binds.bind(row.action, slot, binding)
        except ValueError as e:
            self.message = str(e)
            return
        action = row.action
        if binding is None:
            self.message = f"Cleared {action.label}"
        elif lost is not None:
            self.message = (
                f"{binding.label} was moved from {lost.label} "
                f"to {action.label}"
            )
        else:
            self.message = f"{action.label}: {binding.label}"
        self.app.update_settings()

    def _on_capture(self, event: Event) -> None:
        match event:
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self.capturing = None
                self._pending_modifier = None
                self.message = "Cancelled"
            case KeyEvent(key=key) if event.pressed and key in self.CLEAR_KEYS:
                self._assign(None)
            case KeyEvent(key=key) if event.pressed and key in MODIFIER_KEYS:
                # Wait: it may be the start of a combination like Ctrl+S.
                self._pending_modifier = key
            case KeyEvent(key=key, action=glfw.RELEASE) if (
                key == self._pending_modifier
            ):
                self._assign(Binding.key(key))
            case _:
                binding = Binding.from_event(event)
                if binding is not None:
                    self._assign(binding)

    def _start_capture(self, row: BindRow, slot: int) -> None:
        self.capturing = row
        self.capture_slot = slot
        self.message = (
            "Press a key, mouse button or wheel (modifiers allowed). "
            "Esc cancels, Backspace clears"
        )

    def _on_click(self, event: MouseButtonEvent) -> None:
        step = {glfw.MOUSE_BUTTON_LEFT: 1, glfw.MOUSE_BUTTON_RIGHT: -1}.get(
            event.button
        )
        if step is None:
            return
        index = self.table.row_at(event.pos, self.scroll)
        row = None if index is None else self.rows[index]
        match row:
            case OptionRow(option) if self.table.span_rect(
                index,
                self.scroll,  # type: ignore[arg-type]
            ).contains_point(*event.pos):
                change_option(self.app, option, step)
                self.message = f"{option}: {option_value(self.app, option)}"
                return
            case BindRow():
                cell = self.table.cell_at(event.pos, self.scroll)
                if cell is not None:
                    if step > 0:
                        self._start_capture(row, cell[1])
                    else:
                        self.capturing, self.capture_slot = row, cell[1]
                        self._assign(None)
                    return
            case _:
                pass

        if step < 0:
            return
        match hit_button(self.buttons, event.pos):
            case "reset":
                self.app.keybinds.reset()
                self.app.update_settings()
                self.message = "Controls reset to defaults"
            case "back":
                self._leave()
            case "menu":
                self.app.switch(MainMenu(self.app))
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle input."""
        if isinstance(event, ResizeEvent):
            self.layout()
            return
        if self.capturing is not None:
            self._on_capture(event)
            return
        match event:
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self._leave()
            case MouseButtonEvent() if event.pressed:
                self._on_click(event)
            case ScrollEvent(dy=dy) if dy:
                self.scroll = self.table.clamp_scroll(
                    self.scroll - dy * self.ROW_HEIGHT
                )
            case _:
                pass

    # Drawing

    def _highlight(self, rect: Rect) -> None:
        style = self.app.ui
        self.app.batch.shape(
            (rect.x, rect.y, rect.w, rect.h),
            rgba(style.color("hotbar_selected_border")),
            radius=style.button.border_radius,
            border=style.button.border_width,
        )

    def _draw_row(
        self, index: int, row: Row, mouse: tuple[float, float]
    ) -> None:
        app = self.app
        table = self.table
        color = rgba(app.ui.color("text"))
        anchor = table.label_anchor(index, self.scroll)
        match row:
            case HeaderRow(title):
                app.text.draw(
                    app.batch,
                    title,
                    anchor,
                    TextStyle(size=20, color=color, anchor=Anchor.MIDDLE_LEFT),
                )
            case OptionRow(option):
                app.text.draw(
                    app.batch,
                    option,
                    anchor,
                    TextStyle(size=16, color=color, anchor=Anchor.MIDDLE_LEFT),
                )
                rect = table.span_rect(index, self.scroll)
                Button(option, option_value(app, option), rect).draw(
                    app.batch, app.text, app.ui, mouse
                )
            case BindRow(context, action):
                app.text.draw(
                    app.batch,
                    action.label,
                    anchor,
                    TextStyle(size=16, color=color, anchor=Anchor.MIDDLE_LEFT),
                )
                slots = app.keybinds[context].slots(action)
                for slot, binding in enumerate(slots):
                    rect = table.cell_rect(index, slot, self.scroll)
                    capturing = (
                        self.capturing == row and self.capture_slot == slot
                    )
                    if capturing:
                        label = "..."
                    else:
                        label = binding.label if binding else "-"
                    Button(f"{action}:{slot}", label, rect).draw(
                        app.batch, app.text, app.ui, mouse
                    )
                    if capturing:
                        self._highlight(rect)

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        text_color = rgba(style.color("text"))
        w, h = app.screen
        mouse = app.window.mouse_pos

        app.clear(style.color("main_theme"))
        app.batch.begin(app.screen)
        app.text.draw(
            app.batch,
            "Settings",
            (w / 2, 40),
            TextStyle(size=32, color=text_color, anchor=Anchor.CENTER),
        )

        for index, row in enumerate(self.rows):
            if self.table.is_visible(index, self.scroll):
                self._draw_row(index, row, mouse)
        if self.table.max_scroll > 0:
            self._draw_scrollbar()

        if self.message:
            app.text.draw(
                app.batch,
                self.message,
                (w / 2, h - 95),
                TextStyle(size=16, color=text_color, anchor=Anchor.CENTER),
            )
        for button in self.buttons:
            button.draw(app.batch, app.text, style, mouse)
        app.draw_cursor()

    def _draw_scrollbar(self) -> None:
        table = self.table
        area = table.area
        content = table.rows * table.row_height
        height = area.h * area.h / content
        top = area.y + (area.h - height) * (self.scroll / table.max_scroll)
        color = (*WHITE[:3], 0.3)
        self.app.batch.shape((area.right + 8, top, 4, height), color, radius=2)
