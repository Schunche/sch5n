# Copyright (c) 2026 Schunche
"""Joining a game: games found on the local network, or by address."""

from __future__ import annotations

from typing import TYPE_CHECKING

import glfw

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import (
    Button,
    TextField,
    aligned_rect,
    draw_panel,
    hit_button,
)
from sch5n.client.window import (
    CharEvent,
    KeyEvent,
    MouseButtonEvent,
    ResizeEvent,
)
from sch5n.math.rect import Rect
from sch5n.net.client import ClientSession, Dialer, SessionState, parse_address
from sch5n.net.discovery import Browser
from sch5n.net.protocol import MAX_NAME_LENGTH
lazy from sch5n.client.scenes.menu import draw_menu_background
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.net.discovery import LanGame

PANEL_WIDTH = 560
PADDING = 24
TITLE_Y = 60
FIELD_HEIGHT = 36
FIELD_GAP = 30
"""Space above a field, for its label."""
JOIN_WIDTH = 120
GAME_ROW_HEIGHT = 36
GAME_ROW_GAP = 8
MAX_LISTED_GAMES = 5
FOOTER_WIDTH = 160
DIM = 0.55
HEADER_SIZE = 16
MESSAGE_SIZE = 14
REFRESH_TICKS = 30
"""How often the list of games on the network is refreshed."""
JOIN_TIMEOUT_TICKS = 600
"""Give up joining after this many ticks without being welcomed."""
CARET_BLINK_TICKS = 30


class MultiplayerScene(Scene):
    """Lists games on the network and joins one, or one typed in."""

    def __init__(self, app: App, back: Scene) -> None:
        """Create the screen. `back` is shown again when leaving."""
        super().__init__(app)
        self.back = back
        settings = app.settings
        self.name = TextField(
            "name",
            "Your name",
            Rect(0, 0, 0, 0),
            settings.player_name,
            MAX_NAME_LENGTH,
        )
        self.address = TextField(
            "address", "Server address", Rect(0, 0, 0, 0), settings.last_server
        )
        self.focused: TextField = self.address
        self.browser: Browser | None = None
        self.games: list[LanGame] = []
        self.game_buttons: list[Button] = []
        self.buttons: list[Button] = []
        self.panel = Rect(0, 0, 0, 0)
        self.games_top = 0.0
        self.message = ""
        self.dialer: Dialer | None = None
        self.session: ClientSession | None = None
        self.joining_ticks = 0
        self.ticks = 0
        self.layout()

    @property
    def joining(self) -> bool:
        """Whether a connection is being made."""
        return self.dialer is not None or self.session is not None

    def on_enter(self) -> None:
        """Start looking for games on the network."""
        if self.browser is None:
            self.browser = Browser()

    def on_exit(self) -> None:
        """Stop looking for games, and joining."""
        if self.joining:
            self.cancel()
        if self.browser is not None:
            self.browser.close()
            self.browser = None

    def layout(self) -> None:
        """Place everything for the window size."""
        w, h = self.app.screen
        button_height = self.app.ui.button.height
        list_height = MAX_LISTED_GAMES * (GAME_ROW_HEIGHT + GAME_ROW_GAP)
        height = (
            2 * PADDING
            + 2 * (FIELD_GAP + FIELD_HEIGHT)
            + FIELD_GAP
            + list_height
            + MESSAGE_SIZE * 2
        )
        self.panel = Rect(
            (w - PANEL_WIDTH) / 2, TITLE_Y + 40, PANEL_WIDTH, height
        )
        left = self.panel.x + PADDING
        inner = PANEL_WIDTH - 2 * PADDING
        y = self.panel.y + PADDING + FIELD_GAP
        self.name.rect = Rect(left, y, inner / 2, FIELD_HEIGHT)
        y += FIELD_HEIGHT + FIELD_GAP
        self.address.rect = Rect(
            left, y, inner - JOIN_WIDTH - PADDING / 2, FIELD_HEIGHT
        )
        join = Button(
            "join",
            "Join",
            Rect(left + inner - JOIN_WIDTH, y, JOIN_WIDTH, FIELD_HEIGHT),
        )
        self.games_top = y + FIELD_HEIGHT + FIELD_GAP
        footer_y = min(self.panel.bottom + PADDING, h - button_height - 8)
        footer = (
            Button(
                "cancel",
                "Cancel",
                aligned_rect(
                    ((w - FOOTER_WIDTH) / 2, footer_y),
                    (FOOTER_WIDTH, button_height),
                ),
            )
            if self.joining
            else Button(
                "back",
                "Back",
                aligned_rect(
                    ((w - FOOTER_WIDTH) / 2, footer_y),
                    (FOOTER_WIDTH, button_height),
                ),
            )
        )
        self.buttons = [footer] if self.joining else [join, footer]
        self._place_games()

    def _place_games(self) -> None:
        left = self.panel.x + PADDING
        inner = PANEL_WIDTH - 2 * PADDING
        self.game_buttons = [
            Button(
                f"game:{index}",
                f"{game.name}  ({game.address})",
                Rect(
                    left,
                    self.games_top + index * (GAME_ROW_HEIGHT + GAME_ROW_GAP),
                    inner,
                    GAME_ROW_HEIGHT,
                ),
            )
            for index, game in enumerate(self.games[:MAX_LISTED_GAMES])
        ]

    def _refresh_games(self) -> None:
        if self.browser is None:
            return
        games = self.browser.games
        if games != self.games:
            self.games = games
            self._place_games()

    # Joining

    def join(self, address: str | None = None) -> None:
        """Connect to `address`, or to the one typed in."""
        if self.joining:
            return
        if address is not None:
            self.address.text = address
        name = " ".join(self.name.text.split())
        if not name:
            self.message = "Type a name first"
            self.focused = self.name
            return
        try:
            host, port = parse_address(self.address.text)
        except ValueError as error:
            self.message = str(error)
            self.focused = self.address
            return
        self.app.update_settings(
            player_name=name, last_server=self.address.text.strip()
        )
        self.message = f"Connecting to {host}:{port}..."
        self.dialer = Dialer(host, port)
        self.joining_ticks = 0
        self.layout()

    def cancel(self, reason: str = "") -> None:
        """Stop joining, showing `reason`."""
        if self.dialer is not None:
            self.dialer.cancel()
            self.dialer = None
        if self.session is not None:
            self.session.close()
            self.session = None
        self.message = reason
        self.layout()

    def _tick_joining(self) -> None:
        self.joining_ticks += 1
        if self.joining_ticks > JOIN_TIMEOUT_TICKS:
            self.cancel("The server did not answer")
            return
        dialer = self.dialer
        if dialer is not None:
            if dialer.error is not None:
                self.cancel(dialer.error)
                return
            connection = dialer.take()
            if connection is None:
                return
            self.dialer = None
            self.session = ClientSession(
                connection,
                self.app.content,
                self.app.settings.player_name,
                self.app.options.game_mode,
            )
            self.message = "Joining..."
        session = self.session
        if session is None:
            return
        session.poll()
        if session.state is SessionState.CLOSED:
            self.session = None
            self.cancel(session.error or "Disconnected")
            return
        if session.world is not None and session.world.player is not None:
            self.session = None
            self.app.switch(PlayScene(self.app, session))

    # Input

    def _on_key(self, event: KeyEvent) -> None:
        if event.action not in {glfw.PRESS, glfw.REPEAT}:
            return
        match event.key:
            case glfw.KEY_ESCAPE:
                if self.joining:
                    self.cancel("Cancelled")
                else:
                    self.app.switch(self.back)
            case glfw.KEY_BACKSPACE:
                self.focused.backspace()
            case glfw.KEY_TAB:
                self.focused = (
                    self.name if self.focused is self.address else self.address
                )
            case glfw.KEY_ENTER | glfw.KEY_KP_ENTER:
                self.join()
            case glfw.KEY_V if event.mods & glfw.MOD_CONTROL:
                self.focused.type(self.app.window.clipboard)
            case _:
                pass

    def _on_click(self, pos: tuple[float, float]) -> None:
        for field in (self.name, self.address):
            if field.contains(pos):
                self.focused = field
                return
        button_id = hit_button(self.buttons + self.game_buttons, pos)
        match button_id:
            case "join":
                self.join()
            case "back":
                self.app.switch(self.back)
            case "cancel":
                self.cancel("Cancelled")
            case str() if button_id.startswith("game:") and not self.joining:
                index = int(button_id.removeprefix("game:"))
                self.join(self.games[index].address)
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle typing and clicks."""
        match event:
            case CharEvent(char=char) if not self.joining:
                self.focused.type(char)
            case KeyEvent():
                self._on_key(event)
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT) if (
                event.pressed
            ):
                self._on_click(event.pos)
            case ResizeEvent():
                self.layout()
            case _:
                pass

    def tick(self) -> None:
        """Keep the menu world going, refresh games and join."""
        self.ticks += 1
        self.back.tick_backdrop()
        if self.ticks % REFRESH_TICKS == 1:
            self._refresh_games()
        if self.joining:
            self._tick_joining()

    # Drawing

    def _text(
        self, text: str, pos: tuple[float, float], style: TextStyle
    ) -> None:
        self.app.text.draw(self.app.batch, text, pos, style)

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        w = app.screen[0]
        mouse = app.window.mouse_pos
        text_color = rgba(style.color("text"))
        dim_color = rgba(style.color("text_dim"))

        draw_menu_background(app, self.back, DIM)
        self._text(
            "Multiplayer",
            (w / 2, TITLE_Y),
            TextStyle(32, text_color, Anchor.CENTER),
        )
        draw_panel(app.batch, self.panel, style)
        caret = (self.ticks // CARET_BLINK_TICKS) % 2 == 0
        for field in (self.name, self.address):
            field.draw(
                app.batch,
                app.text,
                style,
                focused=field is self.focused and not self.joining,
                caret=caret,
            )
        self._text(
            "Games on your network",
            (self.panel.x + PADDING, self.games_top - 4),
            TextStyle(MESSAGE_SIZE, dim_color, Anchor.BOTTOM_LEFT),
        )
        if not self.game_buttons:
            self._text(
                "Looking for games...",
                (self.panel.x + PADDING, self.games_top + GAME_ROW_HEIGHT / 2),
                TextStyle(HEADER_SIZE, dim_color, Anchor.MIDDLE_LEFT),
            )
        for button in self.game_buttons:
            button.draw(app.batch, app.text, style, mouse)
        if self.message:
            self._text(
                self.message,
                (self.panel.x + PADDING, self.panel.bottom - PADDING),
                TextStyle(
                    MESSAGE_SIZE,
                    rgba(style.color("accent")),
                    Anchor.MIDDLE_LEFT,
                ),
            )
        for button in self.buttons:
            button.draw(app.batch, app.text, style, mouse)
        app.draw_cursor()
