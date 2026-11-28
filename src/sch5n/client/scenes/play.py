# Copyright (c) 2026 Schunche
"""The game itself, as one client of a server.

Single player runs a server inside the game, connected in memory. Opening
it to the local network makes that server listen for other players too.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

import glfw

from sch5n.client.camera import Camera
from sch5n.client.chat import ChatBox
from sch5n.client.hud import (
    Hud,
    SlotLook,
    VitalsLook,
    draw_vitals,
    item_tooltip,
)
from sch5n.client.inventory_mouse import BUTTONS, InventoryMouse
from sch5n.client.keybinds import Action, Context
from sch5n.client.recipe_book import RecipeBook
from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.scenes.base import Scene
from sch5n.client.scenes.settings import SettingsScene
from sch5n.client.ui import (
    Align,
    CraftingLayout,
    InventoryLayout,
    button_at,
    hit_button,
)
from sch5n.client.window import (
    CharEvent,
    KeyEvent,
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
)
from sch5n.client.world_view import (
    WorldRenderer,
    load_start_map,
)
from sch5n.game.config import GameMode
from sch5n.game.crafting import crafted
from sch5n.game.daylight import DAY_SECONDS, phase
from sch5n.game.session import GameSetup, TickInput
from sch5n.game.vitals import MAX_HEALTH, MAX_HUNGER
from sch5n.log.logger import LOGGER
from sch5n.net.client import ClientSession, SessionState
from sch5n.net.discovery import lan_addresses
from sch5n.net.protocol import InventoryAction
from sch5n.server.server import Server
from sch5n.world.save import World, save_world, unique_name, world_path
lazy from sch5n.client.scenes.menu import MainMenu

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.client.app import App
    from sch5n.client.window import Event
    from sch5n.game.inventory import ItemStack
    from sch5n.game.player import Player
    from sch5n.net.client import ClientWorld

NOTICE_TICKS = 600
"""How long a notice, like the LAN address, stays on screen."""
NOTICE_SIZE = 16
DEATH_TICKS = 180
"""How long the death screen stays."""
DEATH_SIZE = 48
ARMOR_LABEL = TextStyle(
    size=14, color=(220, 220, 230, 255), anchor=Anchor.BOTTOM_RIGHT
)
"""Style of the text above the armor slots."""
HURT_FLASH_TICKS = 12
HURT_FLASH_ALPHA = 0.3
BOSS_BAR_WIDTH = 360
BOSS_NAME = TextStyle(size=16, anchor=Anchor.BOTTOM_CENTER)
CHEST_COLUMNS = 9
"""Slots per row in an open chest."""
CARET_TICKS = 30
"""Ticks the chat caret is on or off."""


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
        self.player_name = app.settings.player_name
        """Name joined with. Saves use it, even if the setting changes
        during the game."""
        self.world: ClientWorld = session.world
        self.tile_size = app.content.game.tile_size
        self.camera = Camera()
        self.renderer = WorldRenderer(app)
        self.inventory_open = False
        self.mouse = InventoryMouse(session)
        self.debug = False
        self.chat = ChatBox()
        self._deaths_seen = 0
        self.death_ticks = 0
        self.hurt_ticks = 0
        """Ticks left of the red flash after taking damage."""
        self._health_seen: int | None = None
        """Ticks left of the death screen."""
        self.book = RecipeBook(app.content)
        self._chat_seen = 0
        self._skip_char = False
        """Ignore the character typed by the key that opened the chat."""
        self.ticks = 0
        self.notice = ""
        self.notice_ticks = 0
        self._jump_requested = False
        self._left = False
        self.save_path: Path | None = None
        """Where leaving saves the hosted world."""
        player = self.world.player
        if player is not None:
            self.camera.center_on(player.body.center)
        self._build_hud()
        self.update_layout()
        app.at_exit(self.leave)

    @classmethod
    def singleplayer(
        cls,
        app: App,
        world: World | None = None,
        save_path: Path | None = None,
    ) -> PlayScene:
        """Start a game served by a server inside this one.

        Args:
            app: The application.
            world: The world to play. `None` plays the map chosen on the
                command line, or the default one.
            save_path: Where leaving saves the world. `None` never saves.

        Returns:
            PlayScene: The scene.

        """
        settings = app.settings
        if world is None:
            world = World(
                f"{settings.player_name}'s world", load_start_map(app), {}
            )
        world.hand_over(settings.player_name)
        server = Server(
            app.content,
            world.tilemap,
            GameSetup(mode=app.options.game_mode, seed=app.options.seed),
            name=world.name,
            inventories=world.inventories,
            chests=world.chests,
        )
        server.host = settings.player_name
        session = ClientSession(
            server.connect_local(),
            app.content,
            settings.player_name,
            app.options.game_mode,
        )
        server.step()
        session.poll()
        scene = cls(app, session, server)
        scene.save_path = save_path
        return scene

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
            settings = self.app.settings
            port, announce = settings.multiplayer_port, settings.lan_announce
            self.server.max_players = settings.max_players
            try:
                self.server.listen("", port, announce=announce)
            except OSError:
                LOGGER.info("Cannot use port %s, using another", port)
                try:
                    self.server.listen("", 0, announce=announce)
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

    def leave(self, *, save: bool = True) -> None:
        """Disconnect, and stop the server if this game hosts one.

        A hosted world is saved unless `save` is off. Closing the window
        leaves this way too, saving.
        """
        if self._left:
            return
        self._left = True
        self.session.close()
        if self.server is not None:
            self.server.close("The host left the game")
            if save:
                self.save()
        self.app.cancel_at_exit(self.leave)

    def save(self) -> Path | None:
        """Save the hosted world where it was loaded from.

        Returns:
            Path | None: The file, `None` if this game saves nowhere.

        """
        if self.server is None or self.save_path is None:
            return None
        self.server.save(self.save_path, owner=self.player_name)
        return self.save_path

    def save_copy(self) -> str:
        """Save the world this client sees to this computer, as a new world.

        Guests keep a full copy of the server's world, so they can save it
        without asking. Their own inventory is saved with it, under their
        own name from the settings as it was when joining (the server may
        have changed it), as that is who plays the copy in single player.

        Returns:
            str: The new world's name.

        """
        directory = self.app.worlds_dir
        name = unique_name(directory, self.world.server_name)
        save_world(
            world_path(directory, name),
            name,
            self.world.tilemap,
            {self.player_name: self.world.inventory},
        )
        return name

    def _build_hud(self) -> None:
        """Size the HUD from the current GUI settings."""
        app = self.app
        inventory = app.content.game.inventory
        self.hud = Hud(app.assets, app.text, app.ui, app.settings.gui_size)
        self.inventory_layout = InventoryLayout.create(
            inventory.columns, inventory.size, app.settings.gui_size, app.ui
        )
        self._lay_out_crafting()
        self._lay_out_armor()
        self._lay_out_chest()

    def _lay_out_armor(self) -> None:
        """Place the armor slots at the right end of the crafting row."""
        layout = self.inventory_layout
        step = layout.slot_size + layout.padding
        count = len(self.world.inventory.armor)
        self.armor_layout = replace(
            layout,
            columns=count,
            slot_count=count,
            origin=(
                layout.origin[0] + (layout.columns - count) * step,
                self.crafting_layout.slot_rect(0).y,
            ),
        )

    def _lay_out_chest(self) -> None:
        """Place the grid of an open chest right of the inventory."""
        bounds = self.inventory_layout.bounds(hotbar_only=False)
        gap = self.app.ui.outer_padding
        layout = self.inventory_layout
        self.chest_layout = replace(
            layout,
            columns=CHEST_COLUMNS,
            slot_count=self.app.content.blocks.by_name("chest").spec.container
            or CHEST_COLUMNS,
            origin=(bounds.right + 2 * gap + layout.border, layout.origin[1]),
        )

    def _lay_out_crafting(self) -> None:
        """Place the grid, whatever size the server says it has."""
        self.crafting_layout = CraftingLayout(
            self.inventory_layout, self.world.inventory.crafting_side
        )
        self._place_book()

    def _place_book(self) -> None:
        """Put the recipe book beside the crafting grid.

        A window too narrow for that gets it below the inventory.
        """
        crafting = self.crafting_layout.bounds()
        inventory = self.inventory_layout.bounds(hotbar_only=False)
        gap = self.app.ui.outer_padding
        row = self.app.settings.gui_size * 1.5 + 8
        screen = self.app.screen
        self.book.place(crafting.right + gap, crafting.y, screen, row)
        if not self.book.usable:
            self.book.place(inventory.x, inventory.bottom + gap, screen, row)

    def on_enter(self) -> None:
        """Pick up settings changed while away, like the GUI size."""
        self._build_hud()
        self.layout()

    def layout(self) -> None:
        """Place the settings button for the window size."""
        w, h = self.app.screen
        pad = self.app.ui.outer_padding
        step = self.app.ui.button.height + pad
        self.buttons = [
            button_at(
                "settings",
                "Settings",
                (w - pad, h - pad),
                self.app.ui,
                Align.BOTTOM_RIGHT,
            ),
            button_at(
                "recipes",
                "Recipes",
                (w - pad, h - pad - step),
                self.app.ui,
                Align.BOTTOM_RIGHT,
            ),
        ]

    def _over_gui(self, pos: tuple[float, float]) -> bool:
        if (
            self.inventory_open
            and self.world.chest is not None
            and self.chest_layout.bounds(hotbar_only=False).contains_point(
                *pos
            )
        ):
            return True
        if self.inventory_layout.bounds(
            hotbar_only=not self.inventory_open
        ).contains_point(*pos):
            return True
        return self.inventory_open and (
            self.crafting_layout.bounds().contains_point(*pos)
            or self.armor_layout.bounds(hotbar_only=False).contains_point(*pos)
            or self.book.contains(pos)
            or hit_button(self.buttons, pos) is not None
        )

    def _toggle_inventory(self) -> None:
        self.inventory_open = not self.inventory_open
        if not self.inventory_open:
            self.mouse.cancel()
            self.session.close_chest()
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
            case Action.CHAT if not self.inventory_open:
                self.chat.start()
                self._skip_char = True
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
        if not self.inventory_open:
            slot = self.inventory_layout.slot_at(event.pos, hotbar_only=True)
            if slot is None:
                return False
            if event.button == glfw.MOUSE_BUTTON_LEFT:
                self.session.inventory(InventoryAction.SELECT, slot)
            return True
        if self._click_chest(event) or self._click_armor(event):
            return True
        slot = self._slot_under(event.pos)
        if slot is not None:
            self.mouse.press(event, slot, self.world.inventory)
        elif self.crafting_layout.on_result(event.pos):
            if event.button in BUTTONS:
                shift = event.mods & glfw.MOD_SHIFT
                self.session.inventory(
                    InventoryAction.CRAFT_ALL
                    if shift
                    else InventoryAction.CRAFT
                )
        else:
            return self._click_button_or_book(event.pos)
        return True

    def _click_button_or_book(self, pos: tuple[float, float]) -> bool:
        """Press the settings or recipes button.

        Returns:
            bool: Whether the click hit a button or the recipe book.

        """
        match hit_button(self.buttons, pos):
            case "settings":
                self.mouse.cancel()
                self._open_settings()
            case "recipes":
                self.mouse.cancel()
                self.book.open = not self.book.open
            case _:
                return self.book.contains(pos)
        return True

    def _chest_slot_at(self, pos: tuple[float, float]) -> int | None:
        if self.world.chest is None:
            return None
        return self.chest_layout.slot_at(pos, hotbar_only=False)

    def _click_armor(self, event: MouseButtonEvent) -> bool:
        """Wear or take off armor with a click on an armor slot.

        Returns:
            bool: Whether the click hit an armor slot.

        """
        slot = self.armor_layout.slot_at(event.pos, hotbar_only=False)
        if slot is None or event.button not in BUTTONS:
            return slot is not None
        self.mouse.cancel()
        self.session.inventory(InventoryAction.ARMOR_CLICK, slot)
        return True

    def _click_chest(self, event: MouseButtonEvent) -> bool:
        """Click a slot of the open chest.

        Returns:
            bool: Whether the click hit one.

        """
        slot = self._chest_slot_at(event.pos)
        if slot is None or event.button not in BUTTONS:
            return slot is not None
        self.mouse.cancel()
        right = event.button == glfw.MOUSE_BUTTON_RIGHT
        quick = bool(event.mods & glfw.MOD_SHIFT) and not right
        self.session.click_chest(slot, right=right, quick=quick)
        return True

    def _try_open_chest(self, event: MouseButtonEvent) -> bool:
        """Open the chest under the mouse, if there is one in reach.

        Returns:
            bool: Whether a chest was opened.

        """
        player = self.player
        if (
            player is None
            or event.button != glfw.MOUSE_BUTTON_RIGHT
            or self._over_gui(event.pos)
        ):
            return False
        wx, wy = self.camera.screen_to_world(event.pos, self.app.screen)
        tile = (
            math.floor(wx / self.tile_size),
            math.floor(wy / self.tile_size),
        )
        block = self.world.tilemap.blocks.get(self.world.tilemap.get(*tile))
        if (
            block is None
            or not (block.spec.container or block.spec.bed)
            or not player.can_reach(tile)
        ):
            return False
        self.session.open_chest(*tile)
        self.inventory_open = block.spec.container is not None
        return True

    def _slot_under(self, pos: tuple[float, float]) -> int | None:
        """Find the slot of the open inventory at `pos`.

        Returns:
            int | None: Its number as in `Inventory.locate`, if any.

        """
        slot = self.inventory_layout.slot_at(pos, hotbar_only=False)
        if slot is not None:
            return slot
        slot = self.crafting_layout.slot_at(pos)
        return None if slot is None else len(self.world.inventory) + slot

    def _open_settings(self) -> None:
        self.app.switch(SettingsScene(self.app, back=self, in_game=True))

    def _on_chat_event(self, event: Event) -> None:
        """Type into the open chat box."""
        if isinstance(event, CharEvent) and self._skip_char:
            self._skip_char = False
            return
        text = self.chat.handle(event, lambda: self.app.window.clipboard)
        if text:
            self.session.say(text)

    def on_event(self, event: Event) -> None:
        """Handle input."""
        if self.chat.open:
            self._on_chat_event(event)
            return
        match event:
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
            case MouseButtonEvent() if event.pressed and self._try_open_chest(
                event
            ):
                return
            case MouseButtonEvent() if not event.pressed:
                self.mouse.release(event.button, self.world.inventory)
            case ScrollEvent(dy=dy) if (
                self.inventory_open
                and self.book.contains(self.app.window.mouse_pos)
            ):
                self.book.scroll_by(-1 if dy > 0 else 1)
            case MouseMoveEvent() if self.inventory_open:
                self.mouse.move(self._slot_under(event.pos))
            case _:
                pass
        action = self.app.keybinds[Context.GAME].pressed(event)
        if action is not None:
            self._on_action(action)

    def _input(self) -> TickInput:
        if self.chat.open:
            return TickInput()
        app = self.app
        window = app.window
        mouse = window.mouse_pos
        world_x, world_y = self.camera.screen_to_world(mouse, app.screen)
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
        self._take_chat()
        self._lay_out_crafting()
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
        self._watch_deaths()
        if self.death_ticks:
            self.death_ticks -= 1
        player = self.player
        if player is not None:
            self.camera.follow(
                player.body.center,
                app.content.game.camera.smoothing / app.tick_rate,
            )

    def _watch_deaths(self) -> None:
        """Show the death screen when the server counts another death."""
        player = self.player
        if player is None:
            return
        if player.deaths > self._deaths_seen:
            self.death_ticks = DEATH_TICKS
            self.mouse.cancel()
        elif (
            self._health_seen is not None
            and player.vitals.health < self._health_seen
        ):
            self.hurt_ticks = HURT_FLASH_TICKS
        self._deaths_seen = player.deaths
        self._health_seen = player.vitals.health
        if self.hurt_ticks:
            self.hurt_ticks -= 1

    def _draw_hurt(self) -> None:
        """Flash the screen red for a moment after taking damage."""
        if not self.hurt_ticks or self.death_ticks:
            return
        w, h = self.app.screen
        share = self.hurt_ticks / HURT_FLASH_TICKS
        self.app.batch.shape(
            (0, 0, w, h), rgba((200, 0, 0), HURT_FLASH_ALPHA * share)
        )

    def _draw_death(self) -> None:
        """Dim the game and say the player died, fading away."""
        app = self.app
        fade = min(1.0, self.death_ticks / app.tick_rate)
        w, h = app.screen
        app.batch.shape((0, 0, w, h), rgba((120, 0, 0), 0.45 * fade))
        app.text.draw(
            app.batch,
            "You died",
            (w / 2, h / 2 - 20),
            TextStyle(
                size=DEATH_SIZE,
                color=rgba(app.ui.color("text"), fade),
                anchor=Anchor.CENTER,
            ),
        )
        app.text.draw(
            app.batch,
            "Back at the start, fed and well",
            (w / 2, h / 2 + 30),
            TextStyle(
                size=NOTICE_SIZE,
                color=rgba(app.ui.color("text_dim"), fade),
                anchor=Anchor.CENTER,
            ),
        )

    def _take_chat(self) -> None:
        """Move newly received chat lines into the chat box."""
        session = self.session
        new = min(session.chat_count - self._chat_seen, len(session.chat))
        if new > 0:
            for message in list(session.chat)[-new:]:
                self.chat.add(message, self.ticks)
        self._chat_seen = session.chat_count

    def tick(self) -> None:
        """Advance the game by one tick."""
        self.ticks += 1
        self._skip_char = False
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
        self.renderer.draw_night(self.world, self.camera)

    def render(self) -> None:
        """Draw the world and the HUD."""
        app = self.app
        batch = app.batch
        inventory = self.mouse.preview(self.world.inventory)
        self.draw_backdrop()
        batch.begin(app.screen)
        mouse = app.window.mouse_pos
        self.hud.draw_inventory(
            batch,
            self.inventory_layout,
            inventory,
            mouse,
            full=self.inventory_open,
        )
        if self.inventory_open:
            for button in self.buttons:
                button.draw(batch, app.text, app.ui, mouse)
            self.hud.draw_crafting(
                batch,
                self.crafting_layout,
                inventory,
                crafted(inventory, app.content),
                mouse,
            )
            self._draw_armor(mouse)
            self._draw_chest(mouse)
            self.book.draw(batch, app.text, app.ui, self.hud, inventory)
            self._draw_station()
            self.hud.draw_cursor_stack(batch, inventory, mouse)
            self._draw_tooltip(mouse)
        if self.notice_ticks:
            self._draw_notice()
        self._draw_vitals()
        self._draw_boss()
        self._draw_hurt()
        if self.death_ticks:
            self._draw_death()
        self.chat.draw(
            batch,
            app.text,
            app.ui,
            app.screen,
            self.ticks,
            app.tick_rate,
            caret=(self.ticks // CARET_TICKS) % 2 == 0,
        )
        if self.debug:
            self._draw_debug()
        app.draw_cursor()

    def _draw_vitals(self) -> None:
        """Draw health and hunger at the bottom, unless an admin plays."""
        player = self.player
        if player is None or self.app.options.game_mode is GameMode.ADMIN:
            return
        app = self.app
        vitals = player.vitals
        draw_vitals(
            app.batch,
            app.text,
            app.ui,
            VitalsLook(
                app.screen[0] / 2, app.screen[1] - app.ui.outer_padding
            ),
            (vitals.health, MAX_HEALTH),
            (vitals.hunger, MAX_HUNGER),
        )

    def _draw_armor(self, mouse: tuple[float, float]) -> None:
        """Draw the worn armor, and what is defended."""
        layout = self.armor_layout
        armor = self.world.inventory.armor
        hovered = layout.slot_at(mouse, hotbar_only=False)
        for index, stack in enumerate(armor):
            self.hud.draw_slot(
                self.app.batch,
                layout.slot_rect(index),
                stack,
                layout.border,
                SlotLook(hovered=index == hovered, selected=False, alpha=1.0),
            )
        first = layout.slot_rect(0)
        defense = self.world.inventory.defense
        self.app.text.draw(
            self.app.batch,
            f"Defense {defense}",
            (first.x - self.app.ui.outer_padding, first.bottom),
            ARMOR_LABEL,
        )

    def _draw_boss(self) -> None:
        """Show the health of a boss that is around, at the top."""
        boss = next((m for m in self.world.mobs.values() if m.kind.boss), None)
        if boss is None:
            return
        app = self.app
        width = min(BOSS_BAR_WIDTH, app.screen[0] * 0.6)
        x, y = (app.screen[0] - width) / 2, app.ui.outer_padding + 70
        share = max(0.0, min(1.0, boss.health / boss.kind.health))
        app.text.draw(
            app.batch,
            boss.kind.display_name,
            (app.screen[0] / 2, y - 4),
            BOSS_NAME,
        )
        app.batch.shape((x - 2, y - 2, width + 4, 16), rgba((0, 0, 0), 0.7))
        app.batch.shape((x, y, width * share, 12), rgba((200, 50, 60), 1.0))

    def _draw_chest(self, mouse: tuple[float, float]) -> None:
        """Draw the slots of the open chest."""
        chest = self.world.chest
        if chest is None:
            return
        layout = self.chest_layout
        hovered = layout.slot_at(mouse, hotbar_only=False)
        for index in range(len(chest)):
            self.hud.draw_slot(
                self.app.batch,
                layout.slot_rect(index),
                chest[index],
                layout.border,
                SlotLook(hovered=index == hovered, selected=False, alpha=1.0),
            )

    def _draw_station(self) -> None:
        """Name the crafting station in reach, if the grid is enlarged."""
        side = self.world.inventory.crafting_side
        content = self.app.content
        for item in content.items:
            places = item.spec.places
            if places is None:
                continue
            if content.blocks.by_name(places).spec.crafting_side == side:
                self.hud.draw_station(
                    self.app.batch, self.crafting_layout, item
                )
                return

    def hovered_stack(self, mouse: tuple[float, float]) -> ItemStack | None:
        """Find the stack under the mouse in the open inventory.

        Returns:
            ItemStack | None: The stack, `None` over an empty slot, outside
            the inventory, or while the cursor holds a stack.

        """
        inventory = self.world.inventory
        if not self.inventory_open or inventory.cursor is not None:
            return None
        chest_slot = self._chest_slot_at(mouse)
        if chest_slot is not None and self.world.chest is not None:
            return self.world.chest[chest_slot]
        slot = self.inventory_layout.slot_at(mouse, hotbar_only=False)
        if slot is not None:
            return inventory[slot]
        slot = self.crafting_layout.slot_at(mouse)
        if slot is not None:
            return inventory.crafting[slot]
        slot = self.armor_layout.slot_at(mouse, hotbar_only=False)
        if slot is not None:
            return inventory.armor[slot]
        return self._hovered_result(mouse)

    def _hovered_result(self, mouse: tuple[float, float]) -> ItemStack | None:
        inventory = self.world.inventory
        if self.crafting_layout.on_result(mouse):
            return crafted(inventory, self.app.content)
        return None

    def _draw_tooltip(self, mouse: tuple[float, float]) -> None:
        stack = self.hovered_stack(mouse)
        if stack is not None:
            self.hud.draw_tooltip(
                self.app.batch,
                item_tooltip(stack, self.app.tick_rate),
                mouse,
                self.app.screen,
            )

    def _draw_notice(self) -> None:
        app = self.app
        layout = (
            self.crafting_layout.bounds()
            if self.inventory_open
            else self.inventory_layout.bounds(hotbar_only=True)
        )
        fade = min(1.0, self.notice_ticks / app.tick_rate)
        app.text.draw(
            app.batch,
            self.notice,
            (layout.x, layout.bottom + 32),
            TextStyle(
                size=NOTICE_SIZE, color=rgba(app.ui.color("accent"), fade)
            ),
        )

    def _clock_line(self) -> str:
        rate = self.app.tick_rate
        day_ticks = DAY_SECONDS * rate
        hours = phase(self.world.clock, rate) * 24
        day = self.world.clock // day_ticks + 1
        return f"time {int(hours):02d}:{int(hours % 1 * 60):02d}, day {day}"

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
            self._clock_line(),
            f"{len(world.mobs)} creatures",
            f"{world.server_name}: {len(world.players)} players",
            (
                f"{len(world.pending)} inputs ahead of the server "
                f"(~{len(world.pending) * 1000 // app.tick_rate} ms), "
                f"{world.corrections} corrections"
            ),
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
