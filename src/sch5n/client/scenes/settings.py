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
    TextField,
    aligned_rect,
    draw_panel,
    hit_button,
)
from sch5n.client.video import FPS_LIMITS, WINDOW_SIZES, cycle, fps_label
from sch5n.client.window import (
    CharEvent,
    KeyEvent,
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
)
from sch5n.game.config import (
    MAX_NAME_LENGTH,
    MAX_PLAYERS,
    MAX_PORT,
    MIN_PLAYERS,
    CursorStyle,
    MenuBackground,
    Settings,
)
from sch5n.math.rect import Rect
lazy from sch5n.client.scenes.menu import MainMenu, draw_menu_background
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.app import App
    from sch5n.client.window import Event

GUI_SIZES = (16, 20, 24, 28, 32)
CURSOR_LABELS = {
    CursorStyle.GAME: "Game",
    CursorStyle.SYSTEM: "System",
}
MENU_BACKGROUND_LABELS = {
    MenuBackground.WORLD: "Game world",
    MenuBackground.THEME: "Theme",
}
VOLUME_STEP = 5
MAX_VOLUME = 100
PLAYER_LIMITS = tuple(range(MIN_PLAYERS, MAX_PLAYERS + 1))
CARET_BLINK_TICKS = 30

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
SLIDER_KNOB = SLIDER_HEIGHT * 2


class Page(StrEnum):
    """Settings pages, in sidebar order."""

    VIDEO = "Video"
    AUDIO = "Audio"
    INTERFACE = "Interface"
    MULTIPLAYER = "Multiplayer"
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
    FONT = "Font"
    CURSOR = "Cursor"
    PLAYER_NAME = "Display name"
    PORT = "Port"
    LAN_ANNOUNCE = "Show on network"
    MAX_PLAYERS = "Max players"


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
    Page.INTERFACE: (
        Option.THEME,
        Option.MENU_BACKGROUND,
        Option.GUI_SIZE,
        Option.FONT,
        Option.CURSOR,
    ),
    Page.MULTIPLAYER: (
        Option.PLAYER_NAME,
        Option.PORT,
        Option.LAN_ANNOUNCE,
        Option.MAX_PLAYERS,
    ),
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
    Option.FONT: ("font",),
    Option.CURSOR: ("cursor",),
    Option.PLAYER_NAME: ("player_name",),
    Option.PORT: ("multiplayer_port",),
    Option.LAN_ANNOUNCE: ("lan_announce",),
    Option.MAX_PLAYERS: ("max_players",),
}
"""Settings fields behind each option."""

VOLUMES = {
    Option.MASTER_VOLUME: "master_volume",
    Option.MUSIC_VOLUME: "music_volume",
    Option.EFFECTS_VOLUME: "effects_volume",
}

TEXT_OPTIONS = {
    Option.PLAYER_NAME: MAX_NAME_LENGTH,
    Option.PORT: len(str(MAX_PORT)),
}
"""Options typed in, with the longest text each takes."""

PAGE_NOTES: dict[Page, str] = {
    Page.AUDIO: "There is no sound yet; volumes are saved for later.",
    Page.INTERFACE: "Click for the next value, right click for the previous.",
    Page.MULTIPLAYER: "Used the next time you host or join a game.",
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
    Option.FONT: lambda app: (
        app.ui.config.fonts[app.ui.font_name(app.settings.font)].label
    ),
    Option.CURSOR: lambda app: CURSOR_LABELS[app.settings.cursor],
    Option.PLAYER_NAME: lambda app: app.settings.player_name,
    Option.PORT: lambda app: str(app.settings.multiplayer_port),
    Option.LAN_ANNOUNCE: lambda app: (
        "On" if app.settings.lan_announce else "Off"
    ),
    Option.MAX_PLAYERS: lambda app: str(app.settings.max_players),
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


def _change_number(app: App, option: Option, step: int) -> None:
    """Move the player limit or a volume."""
    s = app.settings
    if option is Option.MAX_PLAYERS:
        limit = cycle(PLAYER_LIMITS, s.max_players, step)
        app.update_settings(max_players=limit)
        return
    field = VOLUMES[option]
    value = getattr(s, field) + step * VOLUME_STEP
    app.update_settings(**{field: min(max(value, 0), MAX_VOLUME)})


def change_option(app: App, option: Option, step: int) -> None:
    """Move an option `step` values forward (or back), apply and save."""
    s = app.settings
    match option:
        case Option.DISPLAY_MODE | Option.VSYNC | Option.LAN_ANNOUNCE:
            (field,) = OPTION_FIELDS[option]
            app.update_settings(**{field: not getattr(s, field)})
        case Option.WINDOW_SIZE:
            width, height = cycle(
                WINDOW_SIZES, (s.window_width, s.window_height), step
            )
            app.update_settings(window_width=width, window_height=height)
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
        case Option.FONT:
            current = app.ui.font_name(s.font)
            app.update_settings(font=cycle(app.ui.font_names, current, step))
        case Option.CURSOR:
            app.update_settings(
                cursor=cycle(list(CursorStyle), s.cursor, step)
            )
        case _:
            _change_number(app, option, step)


def set_volume(app: App, option: Option, fraction: float) -> None:
    """Set a volume from a mouse position along its slider.

    Settings are only saved when the volume changes, as dragging calls this
    for every mouse movement.
    """
    steps = round(min(max(fraction, 0.0), 1.0) * MAX_VOLUME / VOLUME_STEP)
    value = steps * VOLUME_STEP
    field = VOLUMES[option]
    if value != getattr(app.settings, field):
        app.update_settings(**{field: value})


def set_text_option(app: App, option: Option, text: str) -> None:
    """Check a typed value, apply and save it.

    Raises:
        ValueError: The text is not a valid value; it says why.

    """
    if option is Option.PLAYER_NAME:
        name = " ".join(text.split())
        if not name:
            msg = "The name cannot be empty"
            raise ValueError(msg)
        app.update_settings(player_name=name[:MAX_NAME_LENGTH])
        return
    digits = text.strip()
    if not digits.isdecimal() or not 0 < int(digits) <= MAX_PORT:
        msg = f"The port must be a number from 1 to {MAX_PORT}"
        raise ValueError(msg)
    app.update_settings(multiplayer_port=int(digits))


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
    Volumes are sliders: click or drag. Names and ports are typed: click,
    type, then press Enter or click elsewhere; Escape cancels. Bindings:
    click a slot, then press a key, mouse button or wheel direction, with
    modifiers if wanted. Escape cancels, Backspace, Delete or a right click
    clears. Everything is applied and saved immediately.
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
        self.dragging: Option | None = None
        """Volume whose slider is being dragged."""
        self.editing: Option | None = None
        """Option being typed into `field`."""
        self.field = TextField("setting", "", Rect(0, 0, 0, 0))
        self.ticks = 0
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
        self.dragging = None
        self.editing = None
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

        entries = [
            ("reset", "Reset Page"),
            ("back", "Back"),
            *self._game_entries(),
        ]
        font = self.app.ui.button.font_size
        widths = [
            max(
                FOOTER_BUTTON_WIDTH, self.app.text.measure(label, font)[0] + 32
            )
            for _, label in entries
        ]
        height = self.app.ui.button.height
        total = sum(widths) + (len(entries) - 1) * FOOTER_GAP
        x = (w - total) / 2
        y = self.panel.bottom + (PANEL_BOTTOM_MARGIN - height) / 2
        self.buttons = []
        for (button_id, label), width in zip(entries, widths, strict=True):
            self.buttons.append(
                Button(button_id, label, aligned_rect((x, y), (width, height)))
            )
            x += width + FOOTER_GAP

    def _game_entries(self) -> list[tuple[str, str]]:
        """Footer buttons for the game behind, if opened from one.

        Returns:
            list[tuple[str, str]]: Button ids and labels.

        """
        back = self.back
        if not self.in_game or not isinstance(back, PlayScene):
            return []
        if back.server is None:
            return [("copy", "Save World Copy"), ("menu", "Main Menu")]
        entries = [("lan", "Open to LAN")] if back.can_open_to_lan else []
        return [
            *entries,
            ("menu", "Save & Quit"),
            ("discard", "Quit Without Saving"),
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

    def _drag_to(self, x: float) -> None:
        """Move the dragged slider to screen position `x`."""
        option = self.dragging
        if option is None:
            return
        track = self.slider_rect(self.row_index(OptionRow(option)))
        set_volume(self.app, option, (x - track.x) / track.w)
        self.message = f"{option}: {option_value(self.app, option)}"

    def _grab_slider(
        self, index: int, option: Option, event: MouseButtonEvent
    ) -> None:
        """Start dragging a slider pressed on its track or knob."""
        if event.button != glfw.MOUSE_BUTTON_LEFT:
            return
        track = self.slider_rect(index)
        # The knob reaches past the ends of the track.
        reach = SLIDER_KNOB / 2
        if track.x - reach <= event.pos[0] <= track.right + reach:
            self.dragging = option
            self._drag_to(event.pos[0])

    def _start_editing(self, option: Option) -> None:
        self.editing = option
        self.field = TextField(
            "setting",
            "",
            Rect(0, 0, 0, 0),
            option_value(self.app, option),
            TEXT_OPTIONS[option],
        )
        self.message = "Type, then press Enter. Esc cancels"

    def _finish_editing(self) -> bool:
        """Save what was typed.

        Returns:
            bool: False if it is not a valid value; `message` says why.

        """
        option = self.editing
        if option is None:
            return True
        try:
            set_text_option(self.app, option, self.field.text)
        except ValueError as error:
            self.message = str(error)
            return False
        self.editing = None
        self.message = f"{option}: {option_value(self.app, option)}"
        return True

    def _on_typing(self, event: KeyEvent) -> None:
        if event.action not in {glfw.PRESS, glfw.REPEAT}:
            return
        match event.key:
            case glfw.KEY_ESCAPE:
                self.editing = None
                self.message = "Cancelled"
            case glfw.KEY_BACKSPACE:
                self.field.backspace()
            case glfw.KEY_ENTER | glfw.KEY_KP_ENTER:
                self._finish_editing()
            case glfw.KEY_V if event.mods & glfw.MOD_CONTROL:
                self._type(self.app.window.clipboard)
            case _:
                pass

    def _type(self, chars: str) -> None:
        if self.editing is Option.PORT:
            chars = "".join(c for c in chars if c.isdecimal())
        self.field.type(chars)

    def _click_option(
        self, index: int, option: Option, event: MouseButtonEvent
    ) -> None:
        if option in VOLUMES:
            self._grab_slider(index, option, event)
            return
        span = self.table.span_rect(index, self.scroll)
        if not span.contains_point(*event.pos):
            return
        if option in TEXT_OPTIONS:
            if event.button == glfw.MOUSE_BUTTON_LEFT:
                self._start_editing(option)
            return
        step = 1 if event.button == glfw.MOUSE_BUTTON_LEFT else -1
        change_option(self.app, option, step)
        self.message = f"{option}: {option_value(self.app, option)}"
        if option in {Option.WINDOW_SIZE, Option.FONT}:
            # New sizes: the window's, or the text's on the buttons.
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
            case "discard":
                self.back.leave(save=False)
                self.app.switch(MainMenu(self.app))
            case "copy" if isinstance(self.back, PlayScene):
                name = self.back.save_copy()
                self.message = f"Saved a copy as {name!r}, under Singleplayer"
            case _:
                pass

    def _on_click(self, event: MouseButtonEvent) -> None:
        if event.button not in {
            glfw.MOUSE_BUTTON_LEFT,
            glfw.MOUSE_BUTTON_RIGHT,
        }:
            return
        if self.editing is not None:
            row = self.row_index(OptionRow(self.editing))
            if self.table.is_visible(row, self.scroll) and (
                self.table.span_rect(row, self.scroll).contains_point(
                    *event.pos
                )
            ):
                return
            if not self._finish_editing():
                # Clicking elsewhere drops a value that cannot be saved.
                self.editing = None
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
            case KeyEvent() if self.editing is not None:
                self._on_typing(event)
            case CharEvent(char=char) if self.editing is not None:
                self._type(char)
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self._leave()
            case MouseButtonEvent() if event.pressed:
                self._on_click(event)
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT):
                self.dragging = None
            case MouseMoveEvent(pos=(x, _)):
                self._drag_to(x)
            case ScrollEvent(dy=dy) if dy:
                self.scroll = self.table.clamp_scroll(
                    self.scroll - dy * ROW_HEIGHT
                )
            case _:
                pass

    def tick(self) -> None:
        """Let the scene behind the settings keep moving, if it wants to."""
        self.ticks += 1
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
        knob = SLIDER_KNOB
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
                elif option is self.editing:
                    self.field.rect = rect
                    self.field.draw(
                        app.batch,
                        app.text,
                        app.ui,
                        focused=True,
                        caret=(self.ticks // CARET_BLINK_TICKS) % 2 == 0,
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
