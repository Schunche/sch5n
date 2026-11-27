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
from sch5n.game.config import Settings
from sch5n.math.rect import Rect
from sch5n.net.protocol import MAX_NAME_LENGTH as MAX_PLAYER_NAME_LENGTH
from sch5n.world.save import (
    MAX_NAME_LENGTH,
    World,
    clean_name,
    delete_world,
    list_worlds,
    load_world,
    set_favorite,
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
FAVORITE_WIDTH = 50
DELETE_WIDTH = 64
SMALL_GAP = 6


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
        settings = app.settings
        self.player_name = TextField(
            "player",
            "Your name",
            Rect(0, 0, 0, 0),
            settings.player_name,
            MAX_PLAYER_NAME_LENGTH,
        )
        self.world_name = TextField(
            "name", "New world", Rect(0, 0, 0, 0), "", MAX_NAME_LENGTH
        )
        self._world_name_typed = False
        """Once the world name is typed, it no longer follows the player."""
        self._suggest_world_name()
        self.focused = (
            self.player_name
            if settings.player_name == Settings().player_name
            else self.world_name
        )
        """The field typing goes to. The player name comes first while it
        is still the default."""
        self.panel = Rect(0, 0, 0, 0)
        self.list_top = 0.0
        self.world_buttons: list[Button] = []
        self.side_buttons: list[Button] = []
        """Favorite and delete buttons of the listed worlds."""
        self.confirming: int | None = None
        """The world whose deletion awaits a second click."""
        self.buttons: list[Button] = []
        self.message = ""
        self.ticks = 0
        self.update_layout()

    def _suggest_world_name(self) -> None:
        if not self._world_name_typed:
            player = " ".join(self.player_name.text.split()) or "Player"
            self.world_name.text = unique_name(
                self.app.worlds_dir, f"{player}'s world"
            )[:MAX_NAME_LENGTH]

    def _type(self, text: str) -> None:
        self.focused.type(text)
        self._edited()

    def _edited(self) -> None:
        if self.focused is self.world_name:
            self._world_name_typed = True
        else:
            self._suggest_world_name()

    def _take_player_name(self) -> bool:
        """Save the typed player name to the settings.

        Returns:
            bool: False, with a message, if no name was typed.

        """
        name = " ".join(self.player_name.text.split())
        if not name:
            self.message = "Type your name first"
            self.focused = self.player_name
            return False
        if name != self.app.settings.player_name:
            self.app.update_settings(player_name=name)
        return True

    def layout(self) -> None:
        """Place everything for the window size."""
        w, h = self.app.screen
        list_height = MAX_LISTED_WORLDS * (ROW_HEIGHT + ROW_GAP)
        height = 2 * PADDING + 3 * FIELD_GAP + 2 * FIELD_HEIGHT + list_height
        height += 2 * TEXT_SIZE
        self.panel = Rect(
            (w - PANEL_WIDTH) / 2, TITLE_Y + 40, PANEL_WIDTH, height
        )
        left = self.panel.x + PADDING
        inner = PANEL_WIDTH - 2 * PADDING
        y = self.panel.y + PADDING + FIELD_GAP
        self.player_name.rect = Rect(left, y, inner / 2, FIELD_HEIGHT)
        y += FIELD_HEIGHT + FIELD_GAP
        self.world_name.rect = Rect(
            left, y, inner - CREATE_WIDTH - PADDING / 2, FIELD_HEIGHT
        )
        create = Button(
            "create",
            "Create",
            Rect(left + inner - CREATE_WIDTH, y, CREATE_WIDTH, FIELD_HEIGHT),
        )
        self.list_top = y + FIELD_HEIGHT + FIELD_GAP
        now = time.time()
        row_width = inner - FAVORITE_WIDTH - DELETE_WIDTH - 2 * SMALL_GAP
        self.world_buttons = []
        self.side_buttons = []
        for index, world in enumerate(self.worlds[:MAX_LISTED_WORLDS]):
            row_y = self.list_top + index * (ROW_HEIGHT + ROW_GAP)
            star = "* " if world.favorite else ""
            self.world_buttons.append(
                Button(
                    f"world:{index}",
                    f"{star}{world.name}  "
                    f"({last_played(world.modified, now)})",
                    Rect(left, row_y, row_width, ROW_HEIGHT),
                )
            )
            fav_x = left + row_width + SMALL_GAP
            self.side_buttons.append(
                Button(
                    f"fav:{index}",
                    "Unfav" if world.favorite else "Fav",
                    Rect(fav_x, row_y, FAVORITE_WIDTH, ROW_HEIGHT),
                )
            )
            self.side_buttons.append(
                Button(
                    f"del:{index}",
                    "Sure?" if self.confirming == index else "Delete",
                    Rect(
                        fav_x + FAVORITE_WIDTH + SMALL_GAP,
                        row_y,
                        DELETE_WIDTH,
                        ROW_HEIGHT,
                    ),
                )
            )
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
        if not self._take_player_name():
            return
        try:
            loaded = load_world(world.path, self.app.content)
        except ParseError as error:
            self.message = f"Cannot open {world.name}: {error}"
            return
        self.app.switch(PlayScene.singleplayer(self.app, loaded, world.path))

    def toggle_favorite(self, world: WorldInfo) -> None:
        """Pin a world to the top of the list, or unpin it."""
        set_favorite(world.path, favorite=not world.favorite)
        self._refresh()

    def delete(self, index: int) -> None:
        """Delete a world, after a second click on its button."""
        if self.confirming != index:
            self.confirming = index
            self.layout()
            return
        world = self.worlds[index]
        try:
            delete_world(world.path)
        except OSError as error:
            self.message = f"Cannot delete {world.name}: {error}"
        else:
            self.message = f"Deleted {world.name}"
        self._refresh(keep_message=True)

    def _refresh(self, *, keep_message: bool = False) -> None:
        self.worlds = list_worlds(self.app.worlds_dir)
        self.confirming = None
        if not keep_message:
            self.message = ""
        self._suggest_world_name()
        self.layout()

    def create(self) -> None:
        """Start a new world from the start map, named as typed."""
        if not self._take_player_name():
            return
        directory = self.app.worlds_dir
        name = clean_name(self.world_name.text)
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
                self.focused.backspace()
                self._edited()
            case glfw.KEY_TAB:
                self.focused = (
                    self.world_name
                    if self.focused is self.player_name
                    else self.player_name
                )
            case glfw.KEY_ENTER | glfw.KEY_KP_ENTER:
                self.create()
            case glfw.KEY_V if event.mods & glfw.MOD_CONTROL:
                self._type(self.app.window.clipboard)
            case _:
                pass

    def _on_click(self, pos: tuple[float, float]) -> None:
        for field in (self.player_name, self.world_name):
            if field.contains(pos):
                self.focused = field
                return
        button_id = hit_button(
            self.buttons + self.world_buttons + self.side_buttons, pos
        )
        if self.confirming is not None and button_id != (
            f"del:{self.confirming}"
        ):
            self.confirming = None
            self.layout()
        match button_id:
            case "create":
                self.create()
            case "back":
                self.app.switch(self.back)
            case str() if button_id.startswith("world:"):
                self.play(self.worlds[int(button_id.removeprefix("world:"))])
            case str() if button_id.startswith("fav:"):
                index = int(button_id.removeprefix("fav:"))
                self.toggle_favorite(self.worlds[index])
            case str() if button_id.startswith("del:"):
                self.delete(int(button_id.removeprefix("del:")))
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle typing and clicks."""
        match event:
            case CharEvent(char=char):
                self._type(char)
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
        for field in (self.player_name, self.world_name):
            field.draw(
                app.batch,
                app.text,
                style,
                focused=field is self.focused,
                caret=caret,
            )
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
        for button in self.world_buttons + self.side_buttons:
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
