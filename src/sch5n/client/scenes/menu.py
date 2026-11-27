# Copyright (c) 2026 Schunche
"""The title screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

import glfw

from sch5n.about import __version__
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import Button, aligned_rect, draw_panel, hit_button
from sch5n.client.window import KeyEvent, MouseButtonEvent, ResizeEvent
from sch5n.math.rect import Rect
lazy from sch5n.client.scenes.play import PlayScene
lazy from sch5n.client.scenes.settings import SettingsScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event

MENU_BUTTON_SIZE = (220, 40)
TITLE_SIZE = 56
PANEL_PADDING = 24
ENTRIES = (("play", "Play"), ("settings", "Settings"), ("exit", "Exit"))


class MainMenu(Scene):
    """Title, play, settings and exit."""

    def __init__(self, app: App) -> None:
        """Create the screen."""
        super().__init__(app)
        self.buttons: list[Button] = []
        self.panel = Rect(0, 0, 0, 0)
        self.layout()

    def layout(self) -> None:
        """Place the panel and buttons for the window size."""
        w, h = self.app.screen
        spacing = self.app.ui.main_menu.button_spacing
        bw, bh = MENU_BUTTON_SIZE
        height = (len(ENTRIES) - 1) * spacing + bh + 2 * PANEL_PADDING
        self.panel = Rect(
            (w - bw) / 2 - PANEL_PADDING,
            h * 0.55 - height / 2,
            bw + 2 * PANEL_PADDING,
            height,
        )
        top = self.panel.y + PANEL_PADDING
        self.buttons = [
            Button(
                button_id,
                label,
                aligned_rect(
                    (self.panel.x + PANEL_PADDING, top + i * spacing),
                    MENU_BUTTON_SIZE,
                ),
            )
            for i, (button_id, label) in enumerate(ENTRIES)
        ]

    def on_event(self, event: Event) -> None:
        """Handle clicks, escape and resizing."""
        match event:
            case ResizeEvent():
                self.layout()
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self.app.quit()
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT) if (
                event.pressed
            ):
                self.on_button(hit_button(self.buttons, event.pos))
            case _:
                pass

    def on_button(self, button_id: str | None) -> None:
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

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        w, h = app.screen
        app.draw_background()

        title = app.content.game.title
        shadow = TextStyle(TITLE_SIZE, (0.0, 0.0, 0.0, 0.5), Anchor.CENTER)
        app.text.draw(app.batch, title, (w / 2 + 3, h * 0.22 + 3), shadow)
        app.text.draw(
            app.batch,
            title,
            (w / 2, h * 0.22),
            TextStyle(TITLE_SIZE, rgba(style.color("accent")), Anchor.CENTER),
        )

        draw_panel(app.batch, self.panel, style)
        mouse = app.window.mouse_pos
        for button in self.buttons:
            button.draw(app.batch, app.text, style, mouse)

        app.text.draw(
            app.batch,
            f"v{__version__}",
            (w - style.outer_padding, h - style.outer_padding),
            TextStyle(14, rgba(style.color("text_dim")), Anchor.BOTTOM_RIGHT),
        )
        app.draw_cursor()
