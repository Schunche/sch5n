# Copyright (c) 2026 Schunche
"""The authoritative game server.

The server owns the world. Every tick it applies an input of each
connected player, advances the game and sends every client a snapshot.
Clients connect in memory (the player hosting a single player game) or
over TCP. It imports nothing that needs a window, so it runs headless.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from itertools import starmap
from typing import TYPE_CHECKING

from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.log.logger import LOGGER
from sch5n.net.connection import Listener, SocketConnection, local_pair
from sch5n.net.discovery import Announcer
from sch5n.net.protocol import (
    MAX_CLIENT_FRAME,
    MAX_NAME_LENGTH,
    PROTOCOL_VERSION,
    Goodbye,
    Hello,
    InputMessage,
    InventoryAction,
    InventoryMessage,
    InventoryState,
    ItemState,
    PlayerState,
    Reject,
    Snapshot,
    StackState,
    SwingState,
    Welcome,
    content_fingerprint,
    decode_client_message,
    encode_chunks,
)
from sch5n.world.save import save_world

if TYPE_CHECKING:
    from pathlib import Path

    from sch5n.game.content import Content
    from sch5n.game.inventory import Inventory, Slot
    from sch5n.game.player import Player
    from sch5n.net.connection import Connection
    from sch5n.net.protocol import ClientMessage, ServerMessage
    from sch5n.world.tilemap import TileMap

    type ServerSide = Connection[ServerMessage, ClientMessage]
    type ClientSide = Connection[ClientMessage, ServerMessage]

MAX_PLAYERS = 16
HELLO_TIMEOUT_TICKS = 600
"""Clients that do not say hello within this many ticks are dropped."""
MAX_MESSAGES_PER_TICK = 64
"""Clients sending more than this in one tick are flooding."""
INPUT_BACKLOG = 4
"""With more inputs than this waiting, two are used per tick."""
MAX_QUEUED_INPUTS = 120
"""Older inputs beyond this are dropped; the client gets corrected."""
SERVER_SETUP = GameSetup(host_player=False)


@dataclass(slots=True)
class _Client:
    """A connection and, once joined, its player."""

    connection: ServerSide
    connected_at: int
    """Server tick of the connection."""
    player_id: int | None = None
    name: str = ""
    inputs: deque[InputMessage] = field(default_factory=deque)
    """Inputs not applied yet, oldest first."""
    received: int = -1
    """`seq` of the newest input received."""
    ack: int | None = None
    """`seq` of the newest input applied."""
    sent_inventory: InventoryState | None = None
    ended: bool = False
    """The client left, or the server sent it away."""


def _reject(client: _Client, reason: str) -> None:
    LOGGER.info("Rejected %s: %s", client.connection.address, reason)
    client.ended = True
    client.connection.send(Reject(reason=reason))
    client.connection.close(reason)


def _kick(client: _Client, reason: str) -> None:
    LOGGER.info("Kicking %s: %s", client.name or "a client", reason)
    client.ended = True
    client.connection.send(Goodbye(reason=reason))
    client.connection.close(reason)


def _stack_state(slot: Slot) -> StackState | None:
    if slot is None:
        return None
    return StackState(item=slot.item.name, amount=slot.amount)


def inventory_state(inventory: Inventory) -> InventoryState:
    """Describe an inventory for its owner.

    Returns:
        InventoryState: The message.

    """
    return InventoryState(
        slots=[_stack_state(slot) for slot in inventory],
        cursor=_stack_state(inventory.cursor),
        selected=inventory.selected,
    )


def player_state(player_id: int, player: Player) -> PlayerState:
    """Describe a player for everyone.

    Returns:
        PlayerState: The description.

    """
    body = player.body
    swing = player.swing
    return PlayerState(
        id=player_id,
        name=player.name,
        x=body.x,
        y=body.y,
        vx=body.vx,
        vy=body.vy,
        facing_left=player.facing_left,
        action=player.action.value,
        action_age=player.action_age,
        swing=None
        if swing is None
        else SwingState(
            item=swing.item.name, age=swing.age, duration=swing.duration
        ),
        jumps=player.jumps,
        air_time=player.air_time,
        jump_hold=player.jump_hold,
        jump_speed=player.jump_speed,
        wall_slide=player.wall_slide,
        use_cooldown=player.use_cooldown,
    )


class Server:
    """Runs a game for any number of clients. Call `step` every tick."""

    def __init__(
        self,
        content: Content,
        tilemap: TileMap,
        setup: GameSetup = SERVER_SETUP,
        name: str = "sch5n server",
        inventories: dict[str, Inventory] | None = None,
    ) -> None:
        """Start the game. Nobody can join over the network until `listen`.

        `setup.host_player` is ignored: every player joins as a client.
        Players named in `inventories`, from a saved world, get theirs back
        when they join.
        """
        self.content = content
        self.name = name
        tilemap.changes = []
        self.game = Game(
            content,
            tilemap,
            replace(setup, host_player=False),
        )
        if inventories:
            self.game.restore_inventories(inventories)
        self.fingerprint = content_fingerprint(content)
        self.clients: list[_Client] = []
        self.listener: Listener | None = None
        self.announcer: Announcer | None = None

    @property
    def port(self) -> int | None:
        """TCP port, `None` while not listening."""
        return None if self.listener is None else self.listener.port

    @property
    def player_count(self) -> int:
        """Players in the game."""
        return len(self.game.players)

    def listen(
        self, host: str = "", port: int = 0, *, announce: bool = True
    ) -> int:
        """Accept players over the network, and announce the game.

        Raises `OSError` when the port is taken or the address invalid.

        Args:
            host: Interface address; empty for every interface.
            port: TCP port; 0 picks a free one.
            announce: Make the game visible on the local network.

        Returns:
            int: The port listened on.

        """
        if self.listener is not None:
            return self.listener.port
        self.listener = Listener(host, port)
        LOGGER.info("%s listening on port %s", self.name, self.listener.port)
        if announce:
            self.announcer = Announcer(self.name, self.listener.port)
        return self.listener.port

    def connect_local(self) -> ClientSide:
        """Connect a client in memory, like the host of a single player game.

        Returns:
            ClientSide: The client's end of the connection.

        """
        client_end, server_end = local_pair()
        self.clients.append(_Client(server_end, self.game.ticks))
        return client_end

    def _accept(self) -> None:
        if self.listener is None:
            return
        while (sock := self.listener.accept()) is not None:
            connection: ServerSide = SocketConnection(
                sock, decode_client_message, MAX_CLIENT_FRAME
            )
            LOGGER.info("Connection from %s", connection.address)
            self.clients.append(_Client(connection, self.game.ticks))

    def _unique_name(self, wanted: str) -> str:
        name = " ".join(wanted.split())[:MAX_NAME_LENGTH] or "Player"
        taken = {c.name for c in self.clients if c.player_id is not None}
        candidate, number = name, 2
        while candidate in taken:
            suffix = f" {number}"
            candidate = name[: MAX_NAME_LENGTH - len(suffix)] + suffix
            number += 1
        return candidate

    def _hello(self, client: _Client, hello: Hello) -> None:
        if hello.protocol != PROTOCOL_VERSION:
            _reject(
                client,
                f"The server runs protocol {PROTOCOL_VERSION}, "
                f"you run {hello.protocol}. Use the same game version.",
            )
            return
        if hello.content != self.fingerprint:
            _reject(
                client, "The server has different blocks or items than you."
            )
            return
        if self.player_count >= MAX_PLAYERS:
            _reject(client, "The server is full.")
            return
        client.name = self._unique_name(hello.name)
        client.player_id = self.game.add_player(client.name)
        client.connection.send(
            Welcome(
                player_id=client.player_id,
                server_name=self.name,
                chunks=encode_chunks(self.game.tilemap),
            )
        )
        LOGGER.info(
            "%s joined from %s", client.name, client.connection.address
        )

    def _inventory(self, client: _Client, message: InventoryMessage) -> None:
        if client.player_id is None:
            return
        player = self.game.players[client.player_id]
        inventory = player.inventory
        index = message.index
        match message.action:
            case InventoryAction.SELECT:
                inventory.select(index)
            case InventoryAction.SCROLL:
                inventory.scroll(index)
            case InventoryAction.LEFT_CLICK if 0 <= index < len(inventory):
                inventory.left_click(index)
            case InventoryAction.RIGHT_CLICK if 0 <= index < len(inventory):
                inventory.right_click(index)
            case InventoryAction.CLOSE:
                self.game.return_cursor_stack(player)
            case _:
                _kick(client, "Invalid inventory slot")

    def _handle(self, client: _Client, message: ClientMessage) -> None:
        joined = client.player_id is not None
        match message:
            case Hello() if not joined:
                self._hello(client, message)
            case InputMessage() if joined:
                if message.seq <= client.received:
                    _kick(client, "Inputs out of order")
                    return
                client.received = message.seq
                client.inputs.append(message)
            case InventoryMessage() if joined:
                self._inventory(client, message)
            case Goodbye():
                client.ended = True
                client.connection.reason = message.reason or "Left"
                client.connection.close(client.connection.reason)
            case _:
                _kick(client, f"Unexpected {message.type} message")

    def _receive(self, client: _Client) -> None:
        connection = client.connection
        messages = connection.receive()
        if len(messages) > MAX_MESSAGES_PER_TICK:
            _kick(client, "Too many messages")
            return
        for message in messages:
            if client.ended:
                return
            self._handle(client, message)
        waited = self.game.ticks - client.connected_at
        if client.player_id is None and waited > HELLO_TIMEOUT_TICKS:
            _kick(client, "Did not say hello")

    def _drop_closed(self) -> None:
        remaining: list[_Client] = []
        for client in self.clients:
            if not client.connection.closed:
                remaining.append(client)
                continue
            if client.player_id is not None:
                self.game.remove_player(client.player_id)
                LOGGER.info(
                    "%s left (%s)",
                    client.name,
                    client.connection.reason or "disconnected",
                )
        self.clients = remaining

    def _step_players(self) -> None:
        """Step each player once per input its client sent.

        Inputs queue up, one is used per tick: the server then simulates a
        player exactly like its client predicts it. After a lag spike two
        are used per tick until the backlog is gone. A player whose input
        did not arrive in time waits for it.
        """
        for client in self.clients:
            if client.player_id is None:
                continue
            queue = client.inputs
            while len(queue) > MAX_QUEUED_INPUTS:
                queue.popleft()
            count = 2 if len(queue) > INPUT_BACKLOG else 1
            for _ in range(min(count, len(queue))):
                message = queue.popleft()
                self.game.step_player(
                    client.player_id,
                    TickInput(
                        move_x=message.move_x,
                        jump=message.jump,
                        jump_held=message.jump_held,
                        use=message.use,
                        place=message.place,
                        target=message.target,
                    ),
                )
                client.ack = message.seq

    def _snapshot(self) -> Snapshot:
        game = self.game
        tilemap = game.tilemap
        changes = tilemap.changes or []
        tilemap.changes = []
        return Snapshot(
            tick=game.ticks,
            wind=game.ambience.wind.strength,
            players=list(starmap(player_state, game.players.items())),
            items=[
                ItemState(
                    item=floating.stack.item.name,
                    amount=floating.stack.amount,
                    x=floating.sprite_rect.x,
                    y=floating.sprite_rect.y,
                )
                for floating in game.floating_items
            ],
            tiles=changes,
            damage=[(x, y, left) for (x, y), left in tilemap.damage.items()],
        )

    def step(self) -> None:
        """Accept, read input, advance the game one tick, send the result."""
        self._accept()
        for client in self.clients:
            self._receive(client)
        self._drop_closed()

        self._step_players()
        self.game.tick_world()

        snapshot = self._snapshot()
        for client in self.clients:
            if client.player_id is None:
                continue
            client.connection.send(
                snapshot.model_copy(update={"ack": client.ack})
            )
            state = inventory_state(
                self.game.players[client.player_id].inventory
            )
            if state != client.sent_inventory:
                client.connection.send(state)
                client.sent_inventory = state
        for client in self.clients:
            client.connection.flush()

    def save(self, path: Path) -> None:
        """Save the world, with every player's inventory, as `self.name`."""
        save_world(path, self.name, self.game.tilemap, self.game.inventories())

    def stop_listening(self) -> None:
        """Stop accepting and announcing. Connected players stay."""
        if self.announcer is not None:
            self.announcer.close()
            self.announcer = None
        if self.listener is not None:
            self.listener.close()
            self.listener = None

    def close(self, reason: str = "The server closed") -> None:
        """Say goodbye to everyone and stop."""
        for client in self.clients:
            client.connection.send(Goodbye(reason=reason))
            client.connection.close(reason)
        self._drop_closed()
        self.stop_listening()
