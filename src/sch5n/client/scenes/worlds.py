# Copyright (c) 2026 Schunche
"""Single player: pick a saved world, or start a new one."""

from __future__ import annotations

import time
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
from sch5n.client.window import CharEvent, KeyEvent, MouseButtonEvent
from sch5n.client.world_view import load_start_map
from sch5n.error.exceptions import ParseError
from sch5n.math.rect import Rect
from sch5n.world.save import (
    MAX_NAME_LENGTH,
    World,
    clean_name,
    list_worlds,
    load_world,
    unique_name,
    world_path,
)
lazy from sch5n.client.scenes.menu import draw_menu_background
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.world.save import WorldInfo

PANEL_WIDTH = 560
PADDING = 24
TITLE_Y = 60
FIELD_HEIGHT = 36
FIELD_GAP = 30
"""Space above a field, for its label."""
CREATE_WIDTH = 120
ROW_HEIGHT = 36
ROW_GAP = 8
MAX_LISTED_WORLDS = 6
FOOTER_WIDTH = 160
DIM = 0.55
TEXT_SIZE = 14
CARET_BLINK_TICKS = 30


def last_played(modified: float, now: float) -> str:
    """Describe when a world was saved, roughly.

    Returns:
        str: Like "just now", "5 minutes ago" or "3 days ago".

    """
    seconds = max(0.0, now - modified)
    for unit, length in (("day", 86400), ("hour", 3600), ("minute", 60)):
        count = int(seconds // length)
        if count:
            return f"{count} {unit}{"s" if count > 1 else ""} ago"
    return "just now"


class WorldsScene(Scene):
    """Lists saved worlds to play, and creates new ones."""

    def __init__(self, app: App, back: Scene) -> None:
        """Create the screen. `back` is shown again when leaving."""
        super().__init__(app)
        self.back = back
        self.worlds: list[WorldInfo] = list_worlds(app.worlds_dir)
        self.name = TextField(
            "name",
            "New world",
            Rect(0, 0, 0, 0),
            unique_name(app.worlds_dir, f"{app.settings.player_name}'s world"),
            MAX_NAME_LENGTH,
        )
        self.panel = Rect(0, 0, 0, 0)
        self.list_top = 0.0
        self.world_buttons: list[Button] = []
        self.buttons: list[Button] = []
        self.message = ""
        self.ticks = 0
        self.update_layout()

    def layout(self) -> None:
        """Place everything for the window size."""
        w, h = self.app.screen
        list_height = MAX_LISTED_WORLDS * (ROW_HEIGHT + ROW_GAP)
        height = 2 * PADDING + 2 * FIELD_GAP + FIELD_HEIGHT + list_height
        height += 2 * TEXT_SIZE
        self.panel = Rect(
            (w - PANEL_WIDTH) / 2, TITLE_Y + 40, PANEL_WIDTH, height
        )
        left = self.panel.x + PADDING
        inner = PANEL_WIDTH - 2 * PADDING
        y = self.panel.y + PADDING + FIELD_GAP
        self.name.rect = Rect(
            left, y, inner - CREATE_WIDTH - PADDING / 2, FIELD_HEIGHT
        )
        create = Button(
            "create",
            "Create",
            Rect(left + inner - CREATE_WIDTH, y, CREATE_WIDTH, FIELD_HEIGHT),
        )
        self.list_top = y + FIELD_HEIGHT + FIELD_GAP
        now = time.time()
        self.world_buttons = [
            Button(
                f"world:{index}",
                f"{world.name}  ({last_played(world.modified, now)})",
                Rect(
                    left,
                    self.list_top + index * (ROW_HEIGHT + ROW_GAP),
                    inner,
                    ROW_HEIGHT,
                ),
            )
            for index, world in enumerate(self.worlds[:MAX_LISTED_WORLDS])
        ]
        button_height = self.app.ui.button.height
        back = Button(
            "back",
            "Back",
            aligned_rect(
                (
                    (w - FOOTER_WIDTH) / 2,
                    min(self.panel.bottom + PADDING, h - button_height - 8),
                ),
                (FOOTER_WIDTH, button_height),
            ),
        )
        self.buttons = [create, back]

    def play(self, world: WorldInfo) -> None:
        """Load a saved world and play it."""
        try:
            loaded = load_world(world.path, self.app.content)
        except ParseError as error:
            self.message = f"Cannot open {world.name}: {error}"
            return
        self.app.switch(PlayScene.singleplayer(self.app, loaded, world.path))

    def create(self) -> None:
        """Start a new world from the start map, named as typed."""
        directory = self.app.worlds_dir
        name = clean_name(self.name.text)
        if world_path(directory, name).exists():
            self.message = f"A world called {name!r} already exists"
            return
        world = World(name, load_start_map(self.app), {})
        self.app.switch(
            PlayScene.singleplayer(
                self.app, world, world_path(directory, name)
            )
        )

    def _on_key(self, event: KeyEvent) -> None:
        if event.action not in {glfw.PRESS, glfw.REPEAT}:
            return
        match event.key:
            case glfw.KEY_ESCAPE:
                self.app.switch(self.back)
            case glfw.KEY_BACKSPACE:
                self.name.backspace()
            case glfw.KEY_ENTER | glfw.KEY_KP_ENTER:
                self.create()
            case glfw.KEY_V if event.mods & glfw.MOD_CONTROL:
                self.name.type(self.app.window.clipboard)
            case _:
                pass

    def _on_click(self, pos: tuple[float, float]) -> None:
        button_id = hit_button(self.buttons + self.world_buttons, pos)
        match button_id:
            case "create":
                self.create()
            case "back":
                self.app.switch(self.back)
            case str() if button_id.startswith("world:"):
                self.play(self.worlds[int(button_id.removeprefix("world:"))])
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle typing and clicks."""
        match event:
            case CharEvent(char=char):
                self.name.type(char)
            case KeyEvent():
                self._on_key(event)
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT) if (
                event.pressed
            ):
                self._on_click(event.pos)
            case _:
                pass

    def tick(self) -> None:
        """Keep the menu world going."""
        self.ticks += 1
        self.back.tick_backdrop()

    def _text(
        self, text: str, pos: tuple[float, float], style: TextStyle
    ) -> None:
        self.app.text.draw(self.app.batch, text, pos, style)

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        mouse = app.window.mouse_pos
        dim_color = rgba(style.color("text_dim"))

        draw_menu_background(app, self.back, DIM)
        self._text(
            "Singleplayer",
            (app.screen[0] / 2, TITLE_Y),
            TextStyle(32, rgba(style.color("text")), Anchor.CENTER),
        )
        draw_panel(app.batch, self.panel, style)
        caret = (self.ticks // CARET_BLINK_TICKS) % 2 == 0
        self.name.draw(app.batch, app.text, style, focused=True, caret=caret)
        self._text(
            "Your worlds",
            (self.panel.x + PADDING, self.list_top - 4),
            TextStyle(TEXT_SIZE, dim_color, Anchor.BOTTOM_LEFT),
        )
        if not self.world_buttons:
            self._text(
                "No saved worlds yet. Create one above.",
                (self.panel.x + PADDING, self.list_top + ROW_HEIGHT / 2),
                TextStyle(TEXT_SIZE + 2, dim_color, Anchor.MIDDLE_LEFT),
            )
        for button in self.world_buttons:
            button.draw(app.batch, app.text, style, mouse)
        if self.message:
            self._text(
                self.message,
                (self.panel.x + PADDING, self.panel.bottom - PADDING),
                TextStyle(
                    TEXT_SIZE, rgba(style.color("accent")), Anchor.MIDDLE_LEFT
                ),
            )
        for button in self.buttons:
            button.draw(app.batch, app.text, style, mouse)
        app.draw_cursor()
