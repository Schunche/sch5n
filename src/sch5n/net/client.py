# Copyright (c) 2026 Schunche
"""The client's end of a game: talks to a server and mirrors its world.

The mirror has the same shape as `Game` where drawing needs it
(`tilemap`, `players`, `floating_items`, `ambience`, `horizon`), so the
world renderer draws either. Leaves, clouds and wind streaks are cosmetic
and simulated here, blown by the server's wind.
"""

from __future__ import annotations

import socket
import threading
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np

from sch5n.game.ambient import Ambience
from sch5n.game.floating_item import FloatingItem
from sch5n.game.inventory import Inventory, ItemStack
from sch5n.game.player import Action, Player, Swing
from sch5n.net.connection import SocketConnection
from sch5n.net.protocol import (
    DEFAULT_PORT,
    MAX_SERVER_FRAME,
    PROTOCOL_VERSION,
    Goodbye,
    Hello,
    InputMessage,
    InventoryAction,
    InventoryMessage,
    InventoryState,
    ProtocolError,
    Reject,
    Snapshot,
    Welcome,
    content_fingerprint,
    decode_chunks,
    decode_server_message,
)
from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from sch5n.game.config import GameMode
    from sch5n.game.content import Content
    from sch5n.game.inventory import Slot
    from sch5n.game.session import TickInput
    from sch5n.math.rect import Rect
    from sch5n.net.connection import Connection
    from sch5n.net.protocol import (
        ClientMessage,
        PlayerState,
        ServerMessage,
        StackState,
    )

    type ClientSide = Connection[ClientMessage, ServerMessage]

CONNECT_TIMEOUT = 5.0
"""Seconds to wait for a server to accept the connection."""
MAX_PORT = 65535
MAX_VARIANT = 255
"""Variants are stored as uint8."""


def parse_address(text: str) -> tuple[str, int]:
    """Split `host:port`. The port is optional; IPv6 hosts use brackets.

    Returns:
        tuple[str, int]: Host and port.

    Raises:
        ValueError: The text is not an address.

    """
    text = text.strip()
    if text.startswith("["):
        host, _, rest = text[1:].partition("]")
        port_text = rest.removeprefix(":")
    elif text.count(":") == 1:
        host, _, port_text = text.partition(":")
    else:
        host, port_text = text, ""
    if not host:
        msg = "Type the address of a server"
        raise ValueError(msg)
    if not port_text:
        return host, DEFAULT_PORT
    if not port_text.isdigit() or not 0 < int(port_text) <= MAX_PORT:
        msg = f"{port_text!r} is not a port"
        raise ValueError(msg)
    return host, int(port_text)


class Dialer:
    """Connects to a server in the background, so the screen stays live."""

    def __init__(self, host: str, port: int) -> None:
        """Start connecting."""
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._error: str | None = None
        self._cancelled = False
        threading.Thread(
            target=self._connect, name="sch5n-connect", daemon=True
        ).start()

    def _connect(self) -> None:
        try:
            sock = socket.create_connection(
                (self.host, self.port), timeout=CONNECT_TIMEOUT
            )
        except OSError as error:
            message = error.strerror or str(error) or type(error).__name__
            with self._lock:
                self._error = f"Could not connect: {message}"
            return
        with self._lock:
            if self._cancelled:
                sock.close()
                return
            self._socket = sock

    @property
    def error(self) -> str | None:
        """Why connecting failed, once it did."""
        with self._lock:
            return self._error

    def take(self) -> ClientSide | None:
        """Take the connection, once established.

        Returns:
            ClientSide | None: The connection, `None` while connecting or
            after failing.

        """
        with self._lock:
            sock, self._socket = self._socket, None
        if sock is None:
            return None
        return SocketConnection(sock, decode_server_message, MAX_SERVER_FRAME)

    def cancel(self) -> None:
        """Give up, closing the connection if it gets established."""
        with self._lock:
            self._cancelled = True
            sock, self._socket = self._socket, None
        if sock is not None:
            sock.close()


def _stack(content: Content, state: StackState | None) -> Slot:
    if state is None:
        return None
    return ItemStack(content.items[state.item], state.amount)


class ClientWorld:
    """What a client knows of the server's world."""

    def __init__(
        self, content: Content, welcome: Welcome, mode: GameMode
    ) -> None:
        """Build the world from the server's welcome.

        A `ProtocolError` from `decode_chunks` means the world data is
        invalid.
        """
        self.content = content
        self.config = content.game
        self.mode = mode
        self.local_id = welcome.player_id
        self.server_name = welcome.server_name
        self.tilemap = TileMap(content.blocks)
        decode_chunks(welcome.chunks, self.tilemap)
        bounds = self.tilemap.bounds()
        self.horizon = (bounds[1] if bounds else 0) * self.config.tile_size
        """World y of the top of the world, where the sky begins."""
        self.ambience = Ambience(self.config, np.random.default_rng())
        self.players: dict[int, Player] = {}
        self.floating_items: list[FloatingItem] = []
        self.inventory = Inventory(self.config.inventory.size)
        self.ticks = 0

    @property
    def player(self) -> Player | None:
        """The player of this client, once the server has sent it."""
        return self.players.get(self.local_id)

    def _player(self, state: PlayerState) -> Player:
        player = self.players.get(state.id)
        if player is None:
            inventory = self.inventory if state.id == self.local_id else None
            player = Player(
                self.config,
                inventory or Inventory(self.config.inventory.size),
                (state.x, state.y),
                self.mode,
                name=state.name,
            )
        body = player.body
        body.x, body.y, body.vx, body.vy = state.x, state.y, state.vx, state.vy
        player.name = state.name
        player.facing_left = state.facing_left
        action = Action(state.action)
        if action != player.action:
            player.action = action
            player.action_age = 0
        else:
            player.action_age += 1
        if state.swing is None:
            player.swing = None
        else:
            player.swing = Swing(
                self.content.items[state.swing.item],
                state.swing.duration,
                state.swing.age,
            )
        return player

    def apply_snapshot(self, snapshot: Snapshot) -> None:
        """Take over what moved.

        Raises:
            ProtocolError: The snapshot names unknown blocks or items.

        """
        try:
            players = {
                state.id: self._player(state) for state in snapshot.players
            }
            items = [
                FloatingItem(
                    ItemStack(self.content.items[item.item], item.amount),
                    (item.x, item.y),
                )
                for item in snapshot.items
            ]
        except (KeyError, ValueError) as error:
            msg = f"Invalid snapshot: {error}"
            raise ProtocolError(msg) from error
        known = len(self.content.blocks)
        for x, y, block, variant in snapshot.tiles:
            if not 0 <= block < known or not 0 <= variant <= MAX_VARIANT:
                msg = "Unknown block"
                raise ProtocolError(msg)
            self.tilemap.set(x, y, block, variant)
        self.players = players
        self.floating_items = items
        self.tilemap.damage = {(x, y): left for x, y, left in snapshot.damage}
        self.ambience.wind.strength = snapshot.wind
        self.ticks = snapshot.tick

    def apply_inventory(self, state: InventoryState) -> None:
        """Take over the server's view of this player's inventory.

        Raises:
            ProtocolError: The inventory names unknown items.

        """
        inventory = self.inventory
        try:
            slots = [_stack(self.content, slot) for slot in state.slots]
            cursor = _stack(self.content, state.cursor)
        except KeyError as error:
            msg = f"Unknown item {error}"
            raise ProtocolError(msg) from error
        if len(slots) != len(inventory):
            msg = "The inventory has the wrong size"
            raise ProtocolError(msg)
        inventory.slots = slots
        inventory.cursor = cursor
        inventory.select(state.selected)

    def tick_ambience(self, view: Rect | None) -> None:
        """Move leaves, clouds and wind streaks with the server's wind."""
        self.ambience.tick(
            self.tilemap,
            view,
            self.config.tile_size,
            self.ambience.wind.strength,
        )


class SessionState(StrEnum):
    """Where a client session is."""

    JOINING = "joining"
    PLAYING = "playing"
    CLOSED = "closed"


class ClientSession:
    """A client connected to a server. Call `poll` every tick."""

    def __init__(
        self,
        connection: ClientSide,
        content: Content,
        name: str,
        mode: GameMode,
    ) -> None:
        """Say hello to the server.

        Args:
            connection: Connection to the server.
            content: Game data; it must match the server's.
            name: Player name.
            mode: Game mode, for how players look and move.

        """
        self.connection = connection
        self.content = content
        self.mode = mode
        self.state = SessionState.JOINING
        self.error: str | None = None
        """Why the session closed, for the player."""
        self.world: ClientWorld | None = None
        connection.send(
            Hello(
                protocol=PROTOCOL_VERSION,
                content=content_fingerprint(content),
                name=name,
            )
        )
        connection.flush()

    def _end(self, reason: str) -> None:
        self.state = SessionState.CLOSED
        self.error = reason
        self.connection.close(reason)

    def _handle(self, message: ServerMessage) -> None:
        match message:
            case Welcome() if self.world is None:
                self.world = ClientWorld(self.content, message, self.mode)
                self.state = SessionState.PLAYING
            case Snapshot() if self.world is not None:
                self.world.apply_snapshot(message)
            case InventoryState() if self.world is not None:
                self.world.apply_inventory(message)
            case Reject() | Goodbye():
                self._end(message.reason or "Disconnected")
            case _:
                msg = f"Unexpected {message.type} message"
                raise ProtocolError(msg)

    def poll(self) -> None:
        """Handle what the server sent."""
        if self.state is SessionState.CLOSED:
            return
        try:
            for message in self.connection.receive():
                self._handle(message)
                if self.state is SessionState.CLOSED:
                    return
        except ProtocolError as error:
            self._end(f"The server sent something invalid: {error}")
            return
        if self.connection.closed:
            self._end(self.connection.reason or "Disconnected")

    def send_input(self, inp: TickInput) -> None:
        """Tell the server what the player does this tick."""
        if self.state is not SessionState.PLAYING:
            return
        self.connection.send(
            InputMessage(
                move_x=inp.move_x,
                jump=inp.jump,
                jump_held=inp.jump_held,
                use=inp.use,
                place=inp.place,
                target=inp.target,
            )
        )
        self.connection.flush()

    def inventory(self, action: InventoryAction, index: int = 0) -> None:
        """Do something in the inventory."""
        if self.state is SessionState.PLAYING:
            self.connection.send(InventoryMessage(action=action, index=index))

    def close(self) -> None:
        """Leave the game."""
        if self.state is not SessionState.CLOSED:
            self.connection.send(Goodbye(reason="Left the game"))
            self._end("Left the game")
