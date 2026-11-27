# Copyright (c) 2026 Schunche
"""The settings screen: one page per topic, chosen in a sidebar."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import glfw

from sch5n.client.keybinds import MODIFIER_KEYS, Action, Binding, Context
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import (
    TABLE_WIDTH,
    Button,
    TableLayout,
    aligned_rect,
    draw_panel,
    hit_button,
)
from sch5n.client.video import FPS_LIMITS, WINDOW_SIZES, cycle, fps_label
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ScrollEvent,
)
from sch5n.game.config import MenuBackground, Settings
from sch5n.math.rect import Rect
lazy from sch5n.client.scenes.menu import MainMenu, draw_menu_background
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.app import App
    from sch5n.client.window import Event

GUI_SIZES = (16, 20, 24, 28, 32)
MENU_BACKGROUND_LABELS = {
    MenuBackground.WORLD: "Game world",
    MenuBackground.THEME: "Theme",
}
VOLUME_STEP = 5
MAX_VOLUME = 100

SIDEBAR_WIDTH = 200
SIDEBAR_BUTTON_HEIGHT = 34
SIDEBAR_SPACING = 42
PADDING = 24
TITLE_Y = 44
PANEL_TOP = 84
PANEL_BOTTOM_MARGIN = 76
MESSAGE_HEIGHT = 28
ROW_HEIGHT = 32
FOOTER_BUTTON_WIDTH = 160
FOOTER_GAP = 16
BACKDROP_DIM = 0.55
"""Opacity of the theme color over the backdrop."""
SLIDER_HEIGHT = 8
SLIDER_LABEL_WIDTH = 56
"""Room right of a slider for its value."""


class Page(StrEnum):
    """Settings pages, in sidebar order."""

    VIDEO = "Video"
    AUDIO = "Audio"
    INTERFACE = "Interface"
    CONTROLS = "Controls"
    """Bindings of the program the settings were opened from."""


class Option(StrEnum):
    """Adjustable values, other than key bindings."""

    DISPLAY_MODE = "Display mode"
    WINDOW_SIZE = "Window size"
    VSYNC = "VSync"
    FPS_LIMIT = "Frame rate limit"
    MASTER_VOLUME = "Master volume"
    MUSIC_VOLUME = "Music volume"
    EFFECTS_VOLUME = "Effects volume"
    THEME = "Theme"
    MENU_BACKGROUND = "Menu background"
    GUI_SIZE = "GUI size"


PAGE_OPTIONS: dict[Page, tuple[Option, ...]] = {
    Page.VIDEO: (
        Option.DISPLAY_MODE,
        Option.WINDOW_SIZE,
        Option.VSYNC,
        Option.FPS_LIMIT,
    ),
    Page.AUDIO: (
        Option.MASTER_VOLUME,
        Option.MUSIC_VOLUME,
        Option.EFFECTS_VOLUME,
    ),
    Page.INTERFACE: (Option.THEME, Option.MENU_BACKGROUND, Option.GUI_SIZE),
}

OPTION_FIELDS: dict[Option, tuple[str, ...]] = {
    Option.DISPLAY_MODE: ("fullscreen",),
    Option.WINDOW_SIZE: ("window_width", "window_height"),
    Option.VSYNC: ("vsync",),
    Option.FPS_LIMIT: ("fps_limit",),
    Option.MASTER_VOLUME: ("master_volume",),
    Option.MUSIC_VOLUME: ("music_volume",),
    Option.EFFECTS_VOLUME: ("effects_volume",),
    Option.THEME: ("theme",),
    Option.MENU_BACKGROUND: ("menu_background",),
    Option.GUI_SIZE: ("gui_size",),
}
"""Settings fields behind each option."""

VOLUMES = {
    Option.MASTER_VOLUME: "master_volume",
    Option.MUSIC_VOLUME: "music_volume",
    Option.EFFECTS_VOLUME: "effects_volume",
}

PAGE_NOTES: dict[Page, str] = {
    Page.AUDIO: "There is no sound yet; volumes are saved for later.",
    Page.INTERFACE: "Click for the next value, right click for the previous.",
}
CONTROLS_NOTE = "Click a slot and press a key. Right click clears a slot."


@dataclass(frozen=True, slots=True)
class OptionRow:
    """A value; click to change it."""

    option: Option


@dataclass(frozen=True, slots=True)
class BindRow:
    """An action with its binding slots."""

    context: Context
    action: Action


type Row = OptionRow | BindRow


def page_rows(app: App, page: Page, controls: Context) -> list[Row]:
    """Rows of a settings page, top to bottom.

    `controls` is the program whose bindings the controls page shows.

    Returns:
        list[Row]: The rows.

    """
    if page is Page.CONTROLS:
        return [
            BindRow(controls, action) for action, _ in app.keybinds[controls]
        ]
    return [OptionRow(option) for option in PAGE_OPTIONS[page]]


def _fps_text(settings: Settings) -> str:
    text = fps_label(settings.fps_limit)
    return f"{text} (VSync on)" if settings.vsync else text


_VALUE_TEXT: dict[Option, Callable[[App], str]] = {
    Option.DISPLAY_MODE: lambda app: (
        "Fullscreen" if app.settings.fullscreen else "Windowed"
    ),
    Option.WINDOW_SIZE: lambda app: (
        f"{app.settings.window_width} x {app.settings.window_height}"
    ),
    Option.VSYNC: lambda app: "On" if app.settings.vsync else "Off",
    Option.FPS_LIMIT: lambda app: _fps_text(app.settings),
    Option.THEME: lambda app: app.ui.theme.label,
    Option.MENU_BACKGROUND: lambda app: MENU_BACKGROUND_LABELS[
        app.settings.menu_background
    ],
    Option.GUI_SIZE: lambda app: f"{app.settings.gui_size} px",
} | {
    option: lambda app, field=field: f"{getattr(app.settings, field)} %"
    for option, field in VOLUMES.items()
}


def option_value(app: App, option: Option) -> str:
    """Describe the current value of an option.

    Returns:
        str: Display text.

    """
    return _VALUE_TEXT[option](app)


def change_option(app: App, option: Option, step: int) -> None:
    """Move an option `step` values forward (or back), apply and save."""
    s = app.settings
    match option:
        case Option.DISPLAY_MODE:
            app.update_settings(fullscreen=not s.fullscreen)
        case Option.WINDOW_SIZE:
            width, height = cycle(
                WINDOW_SIZES, (s.window_width, s.window_height), step
            )
            app.update_settings(window_width=width, window_height=height)
        case Option.VSYNC:
            app.update_settings(vsync=not s.vsync)
        case Option.FPS_LIMIT:
            app.update_settings(fps_limit=cycle(FPS_LIMITS, s.fps_limit, step))
        case Option.THEME:
            names = app.ui.theme_names
            app.update_settings(theme=cycle(names, app.ui.theme_name, step))
        case Option.MENU_BACKGROUND:
            choices = list(MenuBackground)
            app.update_settings(
                menu_background=cycle(choices, s.menu_background, step)
            )
        case Option.GUI_SIZE:
            app.update_settings(gui_size=cycle(GUI_SIZES, s.gui_size, step))
        case _:
            field = VOLUMES[option]
            value = getattr(s, field) + step * VOLUME_STEP
            app.update_settings(**{field: min(max(value, 0), MAX_VOLUME)})


def set_volume(app: App, option: Option, fraction: float) -> None:
    """Set a volume from a click position on its slider."""
    steps = round(min(max(fraction, 0.0), 1.0) * MAX_VOLUME / VOLUME_STEP)
    app.update_settings(**{VOLUMES[option]: steps * VOLUME_STEP})


def reset_page(app: App, page: Page, controls: Context) -> None:
    """Restore the defaults of one page and save.

    The controls page resets only the bindings of `controls`.
    """
    if page is Page.CONTROLS:
        app.keybinds[controls].reset()
        app.update_settings()
        return
    defaults = Settings()
    app.update_settings(**{
        field: getattr(defaults, field)
        for option in PAGE_OPTIONS[page]
        for field in OPTION_FIELDS[option]
    })


class SettingsScene(Scene):
    """Every setting, on pages picked in a sidebar.

    Values: left click for the next value, right click for the previous.
    Volumes are sliders. Bindings: click a slot, then press a key, mouse
    button or wheel direction, with modifiers if wanted. Escape cancels,
    Backspace, Delete or a right click clears. Everything is applied and
    saved immediately.
    """

    def __init__(
        self,
        app: App,
        back: Scene,
        *,
        in_game: bool = False,
        page: Page = Page.VIDEO,
    ) -> None:
        """Create the screen. `back` is shown again when leaving."""
        super().__init__(app)
        self.back = back
        self.controls = back.controls
        """Only the program the settings were opened from is editable."""
        self.in_game = in_game
        self.page = page
        self.rows: list[Row] = []
        self.scroll = 0.0
        self.capturing: BindRow | None = None
        self.capture_slot = 0
        self._pending_modifier: int | None = None
        """Modifier key pressed while capturing, bound if released alone."""
        self.message = ""
        self.panel = Rect(0, 0, 0, 0)
        self.table = TableLayout.placed(0, 0, 0, 0)
        self.sidebar: list[Button] = []
        self.buttons: list[Button] = []
        self.show_page(page)

    # Layout

    def show_page(self, page: Page) -> None:
        """Switch to a page."""
        self.page = page
        self.rows = page_rows(self.app, page, self.controls)
        self.scroll = 0.0
        self.capturing = None
        self.message = PAGE_NOTES.get(
            page, CONTROLS_NOTE if page is Page.CONTROLS else ""
        )
        self.layout()

    def layout(self) -> None:
        """Place the panel, sidebar, table and footer for the window size."""
        w, h = self.app.screen
        width = SIDEBAR_WIDTH + TABLE_WIDTH + 3 * PADDING
        self.panel = Rect(
            (w - width) / 2,
            PANEL_TOP,
            width,
            max(h - PANEL_TOP - PANEL_BOTTOM_MARGIN, 0),
        )
        left = self.panel.x + PADDING
        top = self.panel.y + PADDING
        self.sidebar = [
            Button(
                f"page:{page}",
                page,
                aligned_rect(
                    (left, top + i * SIDEBAR_SPACING),
                    (SIDEBAR_WIDTH, SIDEBAR_BUTTON_HEIGHT),
                ),
            )
            for i, page in enumerate(Page)
        ]
        self.table = TableLayout.placed(
            len(self.rows),
            left + SIDEBAR_WIDTH + PADDING,
            top,
            self.panel.bottom - PADDING - MESSAGE_HEIGHT,
            ROW_HEIGHT,
        )
        self.scroll = self.table.clamp_scroll(self.scroll)

        entries = [("reset", "Reset Page"), ("back", "Back")]
        if self.in_game:
            if self.hosted_game is not None:
                entries.append(("lan", "Open to LAN"))
            entries.append(("menu", "Main Menu"))
        size = (FOOTER_BUTTON_WIDTH, self.app.ui.button.height)
        total = len(entries) * size[0] + (len(entries) - 1) * FOOTER_GAP
        x = (w - total) / 2
        y = self.panel.bottom + (PANEL_BOTTOM_MARGIN - size[1]) / 2
        self.buttons = [
            Button(
                button_id,
                label,
                aligned_rect((x + i * (size[0] + FOOTER_GAP), y), size),
            )
            for i, (button_id, label) in enumerate(entries)
        ]

    @property
    def hosted_game(self) -> PlayScene | None:
        """The game behind, if it may still be opened to the network."""
        back = self.back
        if isinstance(back, PlayScene) and back.can_open_to_lan:
            return back
        return None

    def _open_to_lan(self) -> None:
        game = self.hosted_game
        if game is None:
            return
        address = game.open_to_lan()
        self.message = (
            game.notice
            if address is None
            else f"Others on your network can join at {address}"
        )
        self.layout()

    def row_index(self, row: Row) -> int:
        """Position of a row on the current page.

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
        try:
            lost = self.app.keybinds[row.context].bind(
                row.action, slot, binding
            )
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
            case KeyEvent(key=key) if event.pressed and key in {
                glfw.KEY_BACKSPACE,
                glfw.KEY_DELETE,
            }:
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

    def _click_option(
        self, index: int, option: Option, event: MouseButtonEvent
    ) -> None:
        span = self.table.span_rect(index, self.scroll)
        if not span.contains_point(*event.pos):
            return
        if option in VOLUMES:
            track = self.slider_rect(index)
            set_volume(self.app, option, (event.pos[0] - track.x) / track.w)
        else:
            step = 1 if event.button == glfw.MOUSE_BUTTON_LEFT else -1
            change_option(self.app, option, step)
        self.message = f"{option}: {option_value(self.app, option)}"
        if option is Option.WINDOW_SIZE:
            self.layout()

    def _click_binding(self, row: BindRow, event: MouseButtonEvent) -> None:
        cell = self.table.cell_at(event.pos, self.scroll)
        if cell is None:
            return
        self.capturing, self.capture_slot = row, cell[1]
        if event.button == glfw.MOUSE_BUTTON_RIGHT:
            self._assign(None)
        else:
            self.message = (
                "Press a key, mouse button or wheel (modifiers allowed). "
                "Esc cancels, Backspace clears"
            )

    def _click_button(self, pos: tuple[float, float]) -> None:
        button_id = hit_button(self.sidebar + self.buttons, pos)
        match button_id:
            case str() if button_id.startswith("page:"):
                self.show_page(Page(button_id.removeprefix("page:")))
            case "reset":
                reset_page(self.app, self.page, self.controls)
                self.message = f"{self.page} reset to defaults"
                self.layout()
            case "back":
                self._leave()
            case "lan":
                self._open_to_lan()
            case "menu":
                self.back.leave()
                self.app.switch(MainMenu(self.app))
            case _:
                pass

    def _on_click(self, event: MouseButtonEvent) -> None:
        if event.button not in {
            glfw.MOUSE_BUTTON_LEFT,
            glfw.MOUSE_BUTTON_RIGHT,
        }:
            return
        index = self.table.row_at(event.pos, self.scroll)
        if index is not None:
            match self.rows[index]:
                case OptionRow(option):
                    self._click_option(index, option, event)
                case BindRow() as row:
                    self._click_binding(row, event)
            return
        if event.button == glfw.MOUSE_BUTTON_LEFT:
            self._click_button(event.pos)

    def on_event(self, event: Event) -> None:
        """Handle input."""
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
                    self.scroll - dy * ROW_HEIGHT
                )
            case _:
                pass

    def tick(self) -> None:
        """Let the scene behind the settings keep moving, if it wants to."""
        self.back.tick_backdrop()

    # Drawing

    def _text(
        self, text: str, pos: tuple[float, float], style: TextStyle
    ) -> None:
        self.app.text.draw(self.app.batch, text, pos, style)

    def slider_rect(self, index: int) -> Rect:
        """Track area of the slider in a row.

        Returns:
            Rect: Screen rectangle, leaving room for the value text.

        """
        span = self.table.span_rect(index, self.scroll)
        return Rect(span.x, span.y, span.w - SLIDER_LABEL_WIDTH, span.h)

    def _draw_slider(self, rect: Rect, option: Option) -> None:
        app = self.app
        value = getattr(app.settings, VOLUMES[option])
        track = Rect(
            rect.x,
            rect.center[1] - SLIDER_HEIGHT / 2,
            rect.w,
            SLIDER_HEIGHT,
        )
        radius = SLIDER_HEIGHT / 2
        app.batch.shape(
            (track.x, track.y, track.w, track.h),
            rgba(app.ui.color("button_inner")),
            radius=radius,
        )
        fill = track.w * value / MAX_VOLUME
        if fill > 0:
            app.batch.shape(
                (track.x, track.y, fill, track.h),
                rgba(app.ui.color("accent")),
                radius=radius,
            )
        knob = SLIDER_HEIGHT * 2
        app.batch.shape(
            (track.x + fill - knob / 2, rect.center[1] - knob / 2, knob, knob),
            rgba(app.ui.color("text")),
            radius=knob / 2,
        )

    def _draw_row(
        self, index: int, row: Row, mouse: tuple[float, float]
    ) -> None:
        app = self.app
        table = self.table
        label_style = TextStyle(
            16, rgba(app.ui.color("text")), Anchor.MIDDLE_LEFT
        )
        anchor = table.label_anchor(index, self.scroll)
        match row:
            case OptionRow(option):
                self._text(option, anchor, label_style)
                rect = table.span_rect(index, self.scroll)
                if option in VOLUMES:
                    rect = self.slider_rect(index)
                    self._draw_slider(rect, option)
                    value = TextStyle(
                        14, rgba(app.ui.color("text_dim")), Anchor.MIDDLE_LEFT
                    )
                    self._text(
                        option_value(app, option),
                        (rect.right + SLIDER_HEIGHT * 2, rect.center[1]),
                        value,
                    )
                else:
                    Button(option, option_value(app, option), rect).draw(
                        app.batch, app.text, app.ui, mouse
                    )
            case BindRow(context, action):
                self._text(action.label, anchor, label_style)
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
                        app.batch, app.text, app.ui, mouse, selected=capturing
                    )

    def _draw_scrollbar(self) -> None:
        table = self.table
        area = table.area
        content = table.rows * table.row_height
        height = area.h * area.h / content
        top = area.y + (area.h - height) * (self.scroll / table.max_scroll)
        self.app.batch.shape(
            (area.right + 8, top, 4, height),
            rgba(self.app.ui.color("text_dim"), 0.5),
            radius=2,
        )

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        w = app.screen[0]
        mouse = app.window.mouse_pos

        draw_menu_background(app, self.back, BACKDROP_DIM)
        self._text(
            "Settings",
            (w / 2, TITLE_Y),
            TextStyle(32, rgba(style.color("text")), Anchor.CENTER),
        )
        draw_panel(app.batch, self.panel, style)
        for button, page in zip(self.sidebar, Page, strict=True):
            button.draw(
                app.batch, app.text, style, mouse, selected=page is self.page
            )

        for index, row in enumerate(self.rows):
            if self.table.is_visible(index, self.scroll):
                self._draw_row(index, row, mouse)
        if self.table.max_scroll > 0:
            self._draw_scrollbar()

        if self.message:
            area = self.table.area
            self._text(
                self.message,
                (area.x, self.panel.bottom - PADDING - MESSAGE_HEIGHT / 2),
                TextStyle(
                    14, rgba(style.color("text_dim")), Anchor.MIDDLE_LEFT
                ),
            )
        for button in self.buttons:
            button.draw(app.batch, app.text, style, mouse)
        app.draw_cursor()
