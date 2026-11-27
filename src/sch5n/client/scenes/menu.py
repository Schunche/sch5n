# Copyright (c) 2026 Schunche
"""Main menu and settings screens."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import glfw

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import button_column, hit_button
from sch5n.client.window import KeyEvent, MouseButtonEvent, ResizeEvent
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.ui import Button
    from sch5n.client.window import Event


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


class SettingsScene(MenuScene):
    """Shows the current settings and controls."""

    def __init__(
        self, app: App, back: Scene, *, in_game: bool = False
    ) -> None:
        """Create the screen. `back` is shown again when leaving."""
        self.back = back
        self.entries = (("back", "Back"),)
        if in_game:
            self.entries += (("menu", "Main Menu"),)
        super().__init__(app)

    def layout(self) -> None:
        """Place buttons in the lower part of the window."""
        w, h = self.app.screen
        self.buttons = button_column(
            self.entries,
            (w / 2, h * 0.75),
            self.app.ui.main_menu.button_spacing,
            self.app.ui,
        )

    def on_button(self, button_id: str) -> None:
        """Go back, or to the main menu."""
        match button_id:
            case "back":
                self.app.switch(self.back)
            case "menu":
                self.app.switch(MainMenu(self.app))
            case _:
                pass

    def on_escape(self) -> None:
        """Go back."""
        self.app.switch(self.back)

    def draw_foreground(self) -> None:
        """List settings and controls."""
        app = self.app
        s = app.settings
        color = rgba(app.ui.color("text"))
        lines = [
            ("Settings", 32),
            (f"Window: {s.window_width} x {s.window_height}", 16),
            (
                (
                    f"VSync: {"on" if s.vsync else "off"}"
                    f"   GUI size: {s.gui_size}"
                ),
                16,
            ),
            ("Edit assets/base/data/settings.json to change these.", 16),
            ("", 16),
            ("A / D: move   Space: jump   Tab: inventory   Esc: back", 16),
            ("Left mouse: use item   Right mouse: place block", 16),
            ("Wheel / 1-0: select hotbar slot   F3: debug info", 16),
        ]
        y = app.screen[1] * 0.15
        for line, size in lines:
            app.text.draw(
                app.batch,
                line,
                (app.screen[0] / 2, y),
                size,
                color,
                Anchor.CENTER,
            )
            y += size * 2
