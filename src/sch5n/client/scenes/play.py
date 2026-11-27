# Copyright (c) 2026 Schunche
"""The game itself, as one client of a server.

Single player runs a server inside the game, connected in memory. Opening
it to the local network makes that server listen for other players too.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.hud import Hud
from sch5n.client.keybinds import Action, Context
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.settings import SettingsScene
from sch5n.client.ui import Align, InventoryLayout, button_at, hit_button
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ResizeEvent,
)
from sch5n.client.world_view import WorldRenderer, load_world
from sch5n.game.inventory import HOTBAR_SIZE
from sch5n.game.session import GameSetup, TickInput
from sch5n.log.logger import LOGGER
from sch5n.net.client import ClientSession, SessionState
from sch5n.net.discovery import lan_addresses
from sch5n.net.protocol import DEFAULT_PORT, InventoryAction
from sch5n.server.server import Server
lazy from sch5n.client.scenes.menu import MainMenu

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.game.player import Player
    from sch5n.net.client import ClientWorld
    from sch5n.world.tilemap import TileMap

NOTICE_TICKS = 600
"""How long a notice, like the LAN address, stays on screen."""
NOTICE_SIZE = 16


class PlayScene(Scene):
    """Plays a game served by a server, local or remote."""

    has_backdrop = True

    def __init__(
        self, app: App, session: ClientSession, server: Server | None = None
    ) -> None:
        """Play in a joined session.

        Args:
            app: The application.
            session: A session that has been welcomed by its server.
            server: The server running inside this game, if it hosts.

        Raises:
            ValueError: The session has not joined yet.

        """
        super().__init__(app)
        if session.world is None:
            msg = "The session has not joined a game yet"
            raise ValueError(msg)
        self.session = session
        self.server = server
        self.world: ClientWorld = session.world
        self.tile_size = app.content.game.tile_size
        self.camera = Camera()
        self.renderer = WorldRenderer(app)
        self.inventory_open = False
        self.debug = False
        self.notice = ""
        self.notice_ticks = 0
        self._jump_requested = False
        self._left = False
        player = self.world.player
        if player is not None:
            self.camera.center_on(player.body.center, app.screen)
        self._build_hud()
        self._place_layout()
        app.at_exit(self.leave)

    @classmethod
    def singleplayer(
        cls, app: App, tilemap: TileMap | None = None
    ) -> PlayScene:
        """Start a game served by a server inside this one.

        Returns:
            PlayScene: The scene.

        """
        settings = app.settings
        server = Server(
            app.content,
            tilemap if tilemap is not None else load_world(app),
            GameSetup(mode=app.options.game_mode, seed=app.options.seed),
            name=f"{settings.player_name}'s world",
        )
        session = ClientSession(
            server.connect_local(),
            app.content,
            settings.player_name,
            app.options.game_mode,
        )
        server.step()
        session.poll()
        return cls(app, session, server)

    @property
    def player(self) -> Player | None:
        """The player of this client."""
        return self.world.player

    @property
    def jump_requested(self) -> bool:
        """Whether a jump will be sent on the next tick."""
        return self._jump_requested

    @property
    def can_open_to_lan(self) -> bool:
        """Whether this game hosts and does not listen yet."""
        return self.server is not None and self.server.port is None

    @property
    def lan_address(self) -> str | None:
        """Where other players join, once open to the network."""
        if self.server is None or self.server.port is None:
            return None
        addresses = lan_addresses()
        host = addresses[0] if addresses else "localhost"
        return f"{host}:{self.server.port}"

    def open_to_lan(self) -> str | None:
        """Let players on the local network join this game.

        Returns:
            str | None: The address to join, `None` if it did not work.

        """
        if self.server is None:
            return None
        if self.server.port is None:
            try:
                self.server.listen("", DEFAULT_PORT)
            except OSError:
                LOGGER.info("Port %s is taken, using another", DEFAULT_PORT)
                try:
                    self.server.listen("", 0)
                except OSError as error:
                    self.show_notice(f"Could not open to LAN: {error}")
                    return None
        address = self.lan_address
        self.show_notice(f"Open to LAN at {address}")
        return address

    def show_notice(self, text: str) -> None:
        """Show a message over the game for a while."""
        self.notice = text
        self.notice_ticks = NOTICE_TICKS

    def leave(self) -> None:
        """Disconnect, and stop the server if this game hosts one."""
        if self._left:
            return
        self._left = True
        self.session.close()
        if self.server is not None:
            self.server.close("The host left the game")
        self.app.cancel_at_exit(self.leave)

    def _build_hud(self) -> None:
        """Size the HUD from the current GUI settings."""
        app = self.app
        inventory = app.content.game.inventory
        self.hud = Hud(app.assets, app.text, app.ui, app.settings.gui_size)
        self.layout = InventoryLayout.create(
            inventory.columns, inventory.size, app.settings.gui_size, app.ui
        )

    def on_enter(self) -> None:
        """Pick up settings changed while away, like the GUI size."""
        self._build_hud()
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
        if not self.inventory_open:
            self.session.inventory(InventoryAction.CLOSE)

    def _on_action(self, action: Action) -> None:
        inventory = self.session.inventory
        match action:
            case Action.INVENTORY:
                self._toggle_inventory()
            case Action.JUMP:
                self._jump_requested = True
            case Action.DEBUG:
                self.debug = not self.debug
            case Action.HOTBAR_NEXT if not self.inventory_open:
                inventory(InventoryAction.SCROLL, 1)
            case Action.HOTBAR_PREVIOUS if not self.inventory_open:
                inventory(InventoryAction.SCROLL, -1)
            case _ if action.hotbar_slot is not None:
                inventory(InventoryAction.SELECT, action.hotbar_slot)
            case _:
                pass

    def _on_gui_click(self, event: MouseButtonEvent) -> bool:
        """Handle a click on the inventory GUI.

        Returns:
            bool: Whether the click hit the GUI.

        """
        inventory = self.session.inventory
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
                inventory(InventoryAction.SELECT, slot)
        elif event.button == glfw.MOUSE_BUTTON_LEFT:
            inventory(InventoryAction.LEFT_CLICK, slot)
        elif event.button == glfw.MOUSE_BUTTON_RIGHT:
            inventory(InventoryAction.RIGHT_CLICK, slot)
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
            case _:
                pass
        action = self.app.keybinds[Context.GAME].pressed(event)
        if action is not None:
            self._on_action(action)

    def _input(self) -> TickInput:
        app = self.app
        window = app.window
        mouse = window.mouse_pos
        world_x, world_y = self.camera.screen_to_world(mouse)
        target = (
            None
            if self._over_gui(mouse)
            else (
                math.floor(world_x / self.tile_size),
                math.floor(world_y / self.tile_size),
            )
        )
        keys = app.keybinds[Context.GAME]
        move_x = int(keys.is_held(Action.MOVE_RIGHT, window)) - int(
            keys.is_held(Action.MOVE_LEFT, window)
        )
        return TickInput(
            move_x=move_x,
            jump=self._jump_requested,
            jump_held=keys.is_held(Action.JUMP, window),
            use=keys.is_held(Action.USE_ITEM, window),
            place=keys.is_held(Action.PLACE_BLOCK, window),
            target=target,
        )

    def _advance(self, inp: TickInput) -> None:
        """Send input, run the hosted server, and take in what changed."""
        self.session.send_input(inp)
        if self.server is not None:
            self.server.step()
        self.session.poll()
        if self.session.state is SessionState.CLOSED:
            reason = self.session.error or "Disconnected"
            self.leave()
            self.app.switch(MainMenu(self.app, notice=reason))
            return
        app = self.app
        self.world.tick_ambience(self.camera.view(app.screen))
        self.renderer.tick(self.world)
        if self.notice_ticks:
            self.notice_ticks -= 1
        player = self.player
        if player is not None:
            self.camera.follow(
                player.body.center,
                app.screen,
                app.content.game.camera.smoothing / app.tick_rate,
            )

    def tick(self) -> None:
        """Advance the game by one tick."""
        self._advance(self._input())
        self._jump_requested = False

    def tick_backdrop(self) -> None:
        """Keep the game going behind the settings.

        A single player game pauses. Other players keep playing, so a
        game open to the network or on another server goes on.
        """
        if self.server is not None and self.server.port is None:
            return
        self._advance(TickInput())

    def draw_backdrop(self) -> None:
        """Draw the world without the HUD."""
        self.renderer.draw(
            self.world, self.camera, local_id=self.world.local_id
        )

    def render(self) -> None:
        """Draw the world and the HUD."""
        app = self.app
        batch = app.batch
        inventory = self.world.inventory
        self.draw_backdrop()
        batch.begin(app.screen)
        mouse = app.window.mouse_pos
        self.hud.draw_inventory(
            batch, self.layout, inventory, mouse, full=self.inventory_open
        )
        if self.inventory_open:
            for button in self.buttons:
                button.draw(batch, app.text, app.ui, mouse)
            self.hud.draw_cursor_stack(batch, inventory, mouse)
        if self.notice_ticks:
            self._draw_notice()
        if self.debug:
            self._draw_debug()
        app.draw_cursor()

    def _draw_notice(self) -> None:
        app = self.app
        layout = self.layout.bounds(hotbar_only=not self.inventory_open)
        fade = min(1.0, self.notice_ticks / app.tick_rate)
        app.text.draw(
            app.batch,
            self.notice,
            (layout.x, layout.bottom + 32),
            TextStyle(
                size=NOTICE_SIZE, color=rgba(app.ui.color("accent"), fade)
            ),
        )

    def debug_lines(self) -> list[str]:
        """Technical information shown with F3.

        Returns:
            list[str]: The lines.

        """
        app = self.app
        world = self.world
        lines = [f"{app.fps:.0f} fps, {app.batch.draw_calls} draw calls"]
        player = self.player
        if player is not None:
            body = player.body
            lines += [
                f"player {body.x:.1f}, {body.y:.1f}",
                f"velocity {body.vx:.2f}, {body.vy:.2f}",
            ]
        lines += [
            (
                f"{len(world.tilemap)} tiles, "
                f"{len(world.ambience.particles)} particles, "
                f"{len(world.floating_items)} items"
            ),
            f"wind {world.ambience.wind.strength:+.2f}",
            f"{world.server_name}: {len(world.players)} players",
        ]
        if self.lan_address is not None:
            lines.append(f"open to LAN at {self.lan_address}")
        return lines

    def _draw_debug(self) -> None:
        app = self.app
        x, y = app.screen[0] - 8, 8
        color = rgba(app.ui.color("text"))
        for line in self.debug_lines():
            w, h = app.text.measure(line, 14)
            app.text.draw(
                app.batch, line, (x - w, y), TextStyle(size=14, color=color)
            )
            y += h + 2
