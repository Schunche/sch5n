# Copyright (c) 2026 Schunche
"""The game itself."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.hud import Hud
from sch5n.client.keybinds import Action
from sch5n.client.render.batch import rgba
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.menu import SettingsScene
from sch5n.client.ui import Align, InventoryLayout, button_at, hit_button
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ResizeEvent,
    ScrollEvent,
)
from sch5n.client.world_view import (
    TileRenderer,
    draw_clouds,
    draw_floating_items,
    draw_particles,
    draw_player,
)
from sch5n.game.inventory import HOTBAR_SIZE
from sch5n.game.session import Game, TickInput
from sch5n.utility import path
from sch5n.world.io import load_tilemap

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.world.tilemap import TileMap

DEFAULT_MAP = "map1"


def load_world(app: App) -> TileMap:
    """Load the map chosen on the command line, or the default one.

    Returns:
        TileMap: The map.

    """
    map_path = app.options.map_path or path.MAPS_DIR / f"{DEFAULT_MAP}.json"
    return load_tilemap(map_path, app.content.blocks)


class PlayScene(Scene):
    """Plays a map."""

    def __init__(self, app: App, tilemap: TileMap | None = None) -> None:
        """Start a game session."""
        super().__init__(app)
        content = app.content
        self.game = Game(
            content,
            tilemap if tilemap is not None else load_world(app),
            mode=app.options.game_mode,
            seed=app.options.seed,
            cloud_variants=len(app.assets.clouds),
        )
        self.tile_size = content.game.tile_size
        self.camera = Camera()
        self.camera.center_on(self.game.player.body.center, app.screen)
        self.tiles = TileRenderer(app.assets, self.tile_size)
        self.hud = Hud(app.assets, app.text, app.ui, app.settings.gui_size)
        self.layout = InventoryLayout.create(
            content.game.inventory.columns,
            content.game.inventory.size,
            app.settings.gui_size,
            app.ui,
        )
        self.inventory_open = False
        self.debug = False
        self._jump_requested = False
        self._place_layout()

    def _place_layout(self) -> None:
        w, h = self.app.screen
        pad = self.app.ui.outer_padding
        self.buttons = [
            button_at(
                "settings",
                "Settings",
                (w - pad, h - pad),
                self.app.ui,
                Align.BOTTOM_RIGHT,
            )
        ]

    def _over_gui(self, pos: tuple[float, float]) -> bool:
        if self.layout.bounds(
            hotbar_only=not self.inventory_open
        ).contains_point(*pos):
            return True
        return (
            self.inventory_open and hit_button(self.buttons, pos) is not None
        )

    def _toggle_inventory(self) -> None:
        self.inventory_open = not self.inventory_open
        inventory = self.game.inventory
        if not self.inventory_open and inventory.cursor is not None:
            leftover = inventory.add(inventory.cursor)
            inventory.cursor = None
            if leftover is not None:
                player = self.game.player.body
                self.game.drop(
                    leftover,
                    (
                        int(player.center[0] // self.tile_size),
                        int(player.y // self.tile_size),
                    ),
                )

    def _on_action(self, action: Action) -> None:
        match action:
            case Action.INVENTORY:
                self._toggle_inventory()
            case Action.JUMP:
                self._jump_requested = True
            case Action.DEBUG:
                self.debug = not self.debug
            case _ if action.hotbar_slot is not None:
                self.game.inventory.select(action.hotbar_slot)
            case _:
                pass

    def _on_gui_click(self, event: MouseButtonEvent) -> bool:
        """Handle a click on the inventory GUI.

        Returns:
            bool: Whether the click hit the GUI.

        """
        inventory = self.game.inventory
        slot = self.layout.slot_at(
            event.pos, hotbar_only=not self.inventory_open
        )
        if slot is None:
            if (
                self.inventory_open
                and hit_button(self.buttons, event.pos) == "settings"
            ):
                self._open_settings()
                return True
            return False
        if not self.inventory_open:
            if event.button == glfw.MOUSE_BUTTON_LEFT and slot < HOTBAR_SIZE:
                inventory.select(slot)
        elif event.button == glfw.MOUSE_BUTTON_LEFT:
            inventory.left_click(slot)
        elif event.button == glfw.MOUSE_BUTTON_RIGHT:
            inventory.right_click(slot)
        return True

    def _open_settings(self) -> None:
        self.app.switch(SettingsScene(self.app, back=self, in_game=True))

    def on_event(self, event: Event) -> None:
        """Handle input."""
        match event:
            case ResizeEvent():
                self._place_layout()
                return
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                if self.inventory_open:
                    self._toggle_inventory()
                else:
                    self._open_settings()
                return
            case MouseButtonEvent() if event.pressed and self._on_gui_click(
                event
            ):
                return
            case ScrollEvent(dy=dy) if dy and not self.inventory_open:
                self.game.inventory.scroll(-int(math.copysign(1, dy)))
                return
            case _:
                pass
        action = self.app.keybinds.pressed(event)
        if action is not None:
            self._on_action(action)

    def tick(self) -> None:
        """Advance the game by one tick."""
        app = self.app
        window = app.window
        mouse = window.mouse_pos
        over_gui = self._over_gui(mouse)
        world_x, world_y = self.camera.screen_to_world(mouse)
        target = (
            None
            if over_gui
            else (
                math.floor(world_x / self.tile_size),
                math.floor(world_y / self.tile_size),
            )
        )
        keys = app.keybinds
        move_x = int(keys.is_held(Action.MOVE_RIGHT, window)) - int(
            keys.is_held(Action.MOVE_LEFT, window)
        )
        self.game.tick(
            TickInput(
                move_x=move_x,
                jump=self._jump_requested,
                use=keys.is_held(Action.USE_ITEM, window),
                place=keys.is_held(Action.PLACE_BLOCK, window),
                target=target,
                view=self.camera.view(app.screen),
            )
        )
        self._jump_requested = False
        self.camera.follow(
            self.game.player.body.center,
            app.screen,
            app.content.game.camera.smoothing / app.tick_rate,
        )

    def render(self) -> None:
        """Draw the world and the HUD."""
        app = self.app
        batch = app.batch
        game = self.game
        offset = self.camera.offset()

        app.clear(app.content.game.sky_color)
        batch.begin(app.screen)
        draw_clouds(batch, app.assets, game.ambience, offset, app.screen)

        batch.begin(app.screen, offset, self.camera.zoom)
        self.tiles.draw(batch, game.tilemap, self.camera.view(app.screen))
        draw_player(batch, app.assets, game.player)
        draw_particles(batch, app.assets, game.ambience)
        draw_floating_items(batch, app.assets, game.floating_items)

        batch.begin(app.screen)
        mouse = app.window.mouse_pos
        self.hud.draw_inventory(
            batch, self.layout, game.inventory, mouse, full=self.inventory_open
        )
        if self.inventory_open:
            for button in self.buttons:
                button.draw(batch, app.text, app.ui, mouse)
            self.hud.draw_cursor_stack(batch, game.inventory, mouse)
        if self.debug:
            self._draw_debug()
        app.draw_cursor()

    def _draw_debug(self) -> None:
        app = self.app
        body = self.game.player.body
        game = self.game
        lines = [
            f"{app.fps:.0f} fps, {app.batch.draw_calls} draw calls",
            f"player {body.x:.1f}, {body.y:.1f}",
            f"velocity {body.vx:.2f}, {body.vy:.2f}",
            (
                f"{len(game.tilemap)} tiles, {len(game.ambience.particles)} "
                f"particles, {len(game.floating_items)} items"
            ),
            f"wind {game.ambience.wind:+.2f}",
        ]
        x, y = app.screen[0] - 8, 8
        color = rgba(app.ui.color("text"))
        for line in lines:
            w, h = app.text.measure(line, 14)
            app.text.draw(app.batch, line, (x - w, y), 14, color)
            y += h + 2
