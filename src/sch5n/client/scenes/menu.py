# Copyright (c) 2026 Schunche
"""The title screen, with the game running behind it."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.about import __version__
from sch5n.client.camera import Camera
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import Button, aligned_rect, draw_panel, hit_button
from sch5n.client.window import KeyEvent, MouseButtonEvent
from sch5n.client.world_view import WorldRenderer, load_start_map
from sch5n.game.config import MenuBackground
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.math.rect import Rect
lazy from sch5n.client.scenes.multiplayer import MultiplayerScene
lazy from sch5n.client.scenes.settings import SettingsScene
lazy from sch5n.client.scenes.worlds import WorldsScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event

MENU_BUTTON_SIZE = (220, 40)
TITLE_SIZE = 56
PANEL_PADDING = 24
ENTRIES = (
    ("singleplayer", "Singleplayer"),
    ("multiplayer", "Multiplayer"),
    ("settings", "Settings"),
    ("exit", "Exit"),
)
NOTICE_SIZE = 16
VERSION_SIZE = 14
VERSION_ICON_GAP = 6

DRIFT_PERIOD = (2400, 3700)
"""Ticks for one camera sway, horizontally and vertically."""
DRIFT_RANGE = (0.15, 0.06)
"""How far the camera sways, as a fraction of the screen."""
CAMERA_SMOOTHING = 0.02
DIM = 0.35
"""Opacity of the theme color over the world, for readability."""


def dim_screen(app: App, alpha: float) -> None:
    """Darken the whole screen with the theme's background color."""
    app.batch.begin(app.screen)
    app.batch.shape(
        (0, 0, *app.screen), rgba(app.ui.color("background"), alpha)
    )


def draw_menu_background(app: App, scene: Scene, dim: float) -> None:
    """Draw `scene`'s backdrop dimmed, or the theme background.

    The user's menu background setting decides, and scenes without a
    backdrop always get the theme background.
    """
    wants_world = app.settings.menu_background is MenuBackground.WORLD
    if wants_world and scene.has_backdrop:
        scene.draw_backdrop()
        dim_screen(app, dim)
    else:
        app.draw_background()


class MenuWorld:
    """A game session shown behind the menus, with a drifting camera."""

    def __init__(self, app: App) -> None:
        """Load the map Play would load and start it."""
        self.app = app
        self.game = Game(
            app.content,
            load_start_map(app),
            GameSetup(host_player=False),
        )
        bounds = self.game.tilemap.bounds() or (0, 0, 1, 1)
        size = app.content.game.tile_size
        self.center = (
            (bounds[0] + bounds[2]) / 2 * size,
            (bounds[1] + bounds[3]) / 2 * size,
        )
        self.camera = Camera()
        self.camera.center_on(self._target())
        self.renderer = WorldRenderer(app)

    def _target(self) -> tuple[float, float]:
        ticks = self.game.ticks
        w, h = self.app.screen
        return (
            self.center[0]
            + math.sin(ticks * math.tau / DRIFT_PERIOD[0])
            * w
            * DRIFT_RANGE[0],
            self.center[1]
            + math.sin(ticks * math.tau / DRIFT_PERIOD[1])
            * h
            * DRIFT_RANGE[1],
        )

    def tick(self) -> None:
        """Advance the world and move the camera."""
        self.game.tick(TickInput(view=self.camera.view(self.app.screen)))
        self.camera.follow(self._target(), CAMERA_SMOOTHING)

    def draw(self) -> None:
        """Draw the world."""
        self.renderer.draw(self.game, self.camera)


class MainMenu(Scene):
    """Title, single player, multiplayer, settings and exit."""

    has_backdrop = True

    def __init__(self, app: App, notice: str = "") -> None:
        """Create the screen and start the background world.

        `notice` is shown under the buttons, like why a game ended.
        """
        super().__init__(app)
        self.notice = notice
        self.world = MenuWorld(app)
        self.buttons: list[Button] = []
        self.panel = Rect(0, 0, 0, 0)
        self.update_layout()

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
        """Handle clicks and escape."""
        match event:
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
            case "singleplayer":
                self.app.switch(WorldsScene(self.app, back=self))
            case "multiplayer":
                self.app.switch(MultiplayerScene(self.app, back=self))
            case "settings":
                self.app.switch(SettingsScene(self.app, back=self))
            case "exit":
                self.app.quit()
            case _:
                pass

    def tick(self) -> None:
        """Keep the background world running."""
        self.world.tick()

    def tick_backdrop(self) -> None:
        """Keep the world running behind the settings too."""
        self.world.tick()

    def draw_backdrop(self) -> None:
        """Draw the running world."""
        self.world.draw()

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        w, h = app.screen
        draw_menu_background(app, self, DIM)

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

        if self.notice:
            app.text.draw(
                app.batch,
                self.notice,
                (w / 2, self.panel.bottom + PANEL_PADDING),
                TextStyle(
                    NOTICE_SIZE, rgba(style.color("accent")), Anchor.CENTER
                ),
            )
        self._draw_version()
        app.draw_cursor()

    def _draw_version(self) -> None:
        """Draw the game icon and version in the bottom right corner."""
        app = self.app
        style = app.ui
        w, h = app.screen
        text = f"v{__version__}"
        right = w - style.outer_padding
        bottom = h - style.outer_padding
        app.text.draw(
            app.batch,
            text,
            (right, bottom),
            TextStyle(
                VERSION_SIZE, rgba(style.color("text")), Anchor.BOTTOM_RIGHT
            ),
        )
        width, height = app.text.measure(text, VERSION_SIZE)
        icon = app.texture(app.animations.window_icon, (height, height))
        app.batch.sprite(
            icon,
            (
                round(right - width - VERSION_ICON_GAP - height),
                round(bottom - height),
                height,
                height,
            ),
        )
