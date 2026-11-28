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

from sch5n.game.chat import (
    CHAT_HISTORY,
    ChatKind,
    RateLimit,
    sanitize,
)
from sch5n.game.commands import (
    DAY_TICKS,
    MAX_TIME_SPEED,
    TIMES,
    run_command,
    usage,
)
from sch5n.game.config import MAX_PLAYERS
from sch5n.game.crafting import craft, craft_all, fill_recipe
from sch5n.game.daylight import DAY_SECONDS, phase
from sch5n.game.inventory import MAX_CRAFTING_SIDE, ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.game.smelting import FUEL, INPUT
from sch5n.game.weather import rain_amount
from sch5n.log.logger import LOGGER
from sch5n.net.connection import Listener, SocketConnection, local_pair
from sch5n.net.discovery import Announcer
from sch5n.net.protocol import (
    MAX_CLIENT_FRAME,
    MAX_NAME_LENGTH,
    PROTOCOL_VERSION,
    ChatMessage,
    ChatSend,
    ChestClick,
    ChestClose,
    ChestOpen,
    ChestState,
    Goodbye,
    Hello,
    InputMessage,
    InventoryAction,
    InventoryMessage,
    InventoryState,
    ItemState,
    MobState,
    PlayerState,
    ProjectileState,
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

MAX_RAIN_LOOKAHEAD = 10
"""Days `/weather` looks ahead."""
MAX_GIVE = 1024
"""Most items one `/give` hands over."""
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
    chest: tuple[int, int] | None = None
    """Tile of the storage block the player has open."""
    sent_chest: ChestState | None = None
    muted: bool = False
    chat_limit: RateLimit = field(default_factory=RateLimit)
    ended: bool = False
    """The client left, or the server sent it away."""


def _reject(client: _Client, reason: str) -> None:
    LOGGER.info("Rejected %s: %s", client.connection.address, reason)
    client.ended = True
    client.connection.send(Reject(reason=reason))
    client.connection.close(reason)


def _tell(client: _Client, text: str) -> None:
    client.connection.send(ChatMessage(kind=ChatKind.SYSTEM, text=text))


def _kick(client: _Client, reason: str) -> None:
    LOGGER.info("Kicking %s: %s", client.name or "a client", reason)
    client.ended = True
    client.connection.send(Goodbye(reason=reason))
    client.connection.close(reason)


def _stack_state(slot: Slot) -> StackState | None:
    if slot is None:
        return None
    return StackState(item=slot.item.name, amount=slot.amount)


def _click_grid(inventory: Inventory, message: InventoryMessage) -> None:
    """Click a slot of the crafting grid.

    A click beyond the grid is ignored: the grid shrank while the click was
    on its way.
    """
    if message.index >= len(inventory.crafting):
        return
    if message.action is InventoryAction.CRAFTING_LEFT_CLICK:
        inventory.left_click(message.index, crafting=True)
    else:
        inventory.right_click(message.index, crafting=True)


def _arrange(
    inventory: Inventory, message: InventoryMessage, content: Content
) -> None:
    """Move many items at once. Slots that no longer exist are ignored."""
    match message.action:
        case InventoryAction.CRAFT:
            craft(inventory, content)
        case InventoryAction.CRAFT_ALL:
            craft_all(inventory, content)
        case InventoryAction.STOW_CRAFTING:
            inventory.stow_crafting(message.index)
        case InventoryAction.GATHER:
            inventory.gather(message.index)
        case InventoryAction.FILL_RECIPE | InventoryAction.FILL_RECIPE_ALL:
            fill_recipe(
                inventory,
                content,
                message.index,
                maximum=message.action is InventoryAction.FILL_RECIPE_ALL,
            )
        case _:
            single = message.action is InventoryAction.SPREAD_SINGLE
            inventory.spread(message.slots, single=single)


def inventory_state(inventory: Inventory) -> InventoryState:
    """Describe an inventory for its owner.

    Returns:
        InventoryState: The message.

    """
    return InventoryState(
        slots=[_stack_state(slot) for slot in inventory],
        cursor=_stack_state(inventory.cursor),
        selected=inventory.selected,
        crafting=[_stack_state(slot) for slot in inventory.crafting],
        armor=[_stack_state(slot) for slot in inventory.armor],
        stations=sorted(inventory.stations),
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
        health=player.vitals.health,
        hunger=player.vitals.hunger,
        deaths=player.deaths,
    )


class Server:
    """Runs a game for any number of clients. Call `step` every tick."""

    def __init__(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        content: Content,
        tilemap: TileMap,
        setup: GameSetup = SERVER_SETUP,
        name: str = "sch5n server",
        inventories: dict[str, Inventory] | None = None,
        chests: dict[tuple[int, int], Inventory] | None = None,
        clock: int = 0,
    ) -> None:
        """Start the game. Nobody can join over the network until `listen`.

        `setup.host_player` is ignored: every player joins as a client.
        Players named in `inventories`, from a saved world, get theirs back
        when they join.
        """
        self.content = content
        self.name = name
        self.max_players = MAX_PLAYERS
        """Players admitted; later ones are told the server is full."""
        tilemap.changes = []
        self.game = Game(
            content,
            tilemap,
            replace(setup, host_player=False),
        )
        if inventories:
            self.game.restore_inventories(inventories)
        if chests:
            self.game.chests.update(chests)
        self.game.time_offset = clock
        self.fingerprint = content_fingerprint(content)
        self.clients: list[_Client] = []
        self.host = ""
        """Name of the player who may kick and mute, empty for nobody."""
        self.chat_log: deque[ChatMessage] = deque(maxlen=CHAT_HISTORY)
        """Everything said lately, oldest first. New players get it."""
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
        name = sanitize(wanted, MAX_NAME_LENGTH) or "Player"
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
        if self.player_count >= self.max_players:
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
        for line in self.chat_log:
            client.connection.send(line)
        self.broadcast(ChatMessage(kind=ChatKind.JOIN, sender=client.name))

    def broadcast(self, message: ChatMessage) -> None:
        """Show a line of chat to every joined player, and remember it."""
        self.chat_log.append(message)
        for client in self.clients:
            if client.player_id is not None and not client.ended:
                client.connection.send(message)

    def say(self, text: str) -> None:
        """Announce something to everyone, as the server."""
        text = sanitize(text)
        if text:
            self.broadcast(ChatMessage(kind=ChatKind.SYSTEM, text=text))

    def _chat(self, client: _Client, message: ChatSend) -> None:
        text = sanitize(message.text)
        if not text:
            return
        if not client.chat_limit.allow(self.game.ticks):
            client.connection.send(
                ChatMessage(
                    kind=ChatKind.SYSTEM,
                    text="You are sending messages too fast.",
                )
            )
            return
        if text.startswith("/"):
            self._command(client, text)
            return
        if client.muted:
            _tell(client, "You are muted.")
            return
        LOGGER.info("<%s> %s", client.name, text)
        self.broadcast(ChatMessage(sender=client.name, text=text))

    def _moderate(self, client: _Client, command: str, who: str) -> None:
        """Kick, mute or unmute a player, if the sender is the host."""
        if not self.host or client.name != self.host:
            _tell(client, "Only the host can do that.")
            return
        wanted = " ".join(who.split()).lower()
        target = next(
            (
                c
                for c in self.clients
                if c.player_id is not None and c.name.lower() == wanted
            ),
            None,
        )
        if target is None:
            _tell(client, f"Nobody is called {who!r}.")
        elif target is client:
            _tell(client, "You cannot do that to yourself.")
        elif command == "kick":
            _kick(target, "Kicked by the host")
        else:
            target.muted = command == "mute"
            done = "muted" if target.muted else "unmuted"
            self.say(f"{target.name} was {done}")

    def _whisper(self, client: _Client, argument: str) -> None:
        """Tell one player something in private: `/msg <player> <text>`."""
        if client.muted:
            _tell(client, "You are muted.")
            return
        words = " ".join(argument.split())
        lowered = words.lower()
        names = sorted(
            (c for c in self.clients if c.player_id is not None),
            key=lambda c: len(c.name),
            reverse=True,
        )
        target = next(
            (c for c in names if lowered.startswith(c.name.lower() + " ")),
            None,
        )
        text = sanitize(words[len(target.name) :]) if target else ""
        if target is None or not text:
            _tell(client, "Use /msg <player> <text>.")
        elif target is client:
            _tell(client, "You cannot whisper to yourself.")
        else:
            LOGGER.info("<%s> to %s: %s", client.name, target.name, text)
            target.connection.send(
                ChatMessage(sender=f"{client.name} (private)", text=text)
            )
            _tell(client, f"To {target.name}: {text}")

    def _set_time(self, client: _Client, argument: str) -> None:
        """Change the time, if the sender is the host.

        `/time set|add|speed|query`, and `/time <moment>` for short.
        """
        if not self.host or client.name != self.host:
            _tell(client, "Only the host can do that.")
            return
        word, _, rest = argument.strip().lower().partition(" ")
        rest = rest.strip()
        if word in TIMES:
            word, rest = "set", word
        if not word:
            word = "query"
        action = {
            "set": self._time_set,
            "add": self._time_add,
            "speed": self._time_speed,
            "query": self._time_query,
        }.get(word)
        if action is None:
            _tell(client, f"Use {usage("time")}.")
            return
        action(client, rest)

    def _time_set(self, client: _Client, text: str) -> None:
        if text in TIMES:
            self.game.set_time(TIMES[text])
        elif text.isdigit():
            self.game.set_time((int(text) % DAY_TICKS) / DAY_TICKS)
        else:
            _tell(client, f"Use /time set <{"|".join(TIMES)}|ticks>.")
            return
        self.say(f"The time was set to {text}")

    def _time_add(self, client: _Client, text: str) -> None:
        try:
            ticks = int(text)
        except ValueError:
            _tell(client, "Use /time add <ticks>. A day is 24000 ticks.")
            return
        self.game.add_time(ticks / DAY_TICKS)
        self.say(f"The time moved by {ticks} ticks")

    def _time_speed(self, client: _Client, text: str) -> None:
        try:
            speed = float(text)
        except ValueError:
            speed = -1.0
        if not 0 <= speed <= MAX_TIME_SPEED:
            _tell(client, f"Use /time speed <0 to {MAX_TIME_SPEED:g}>.")
            return
        self.game.time_scale = speed
        self.say(f"Time now passes at speed {speed:g}")

    def _time_query(self, client: _Client, _text: str) -> None:
        game = self.game
        rate = game.config.tick_rate
        moment = int(phase(game.clock, rate) * DAY_TICKS)
        day = game.clock // (DAY_SECONDS * rate) + 1
        _tell(
            client,
            f"It is {moment} ticks into day {day}; speed {game.time_scale:g}.",
        )

    def _give(self, client: _Client, argument: str) -> None:
        """Give the host items: `/give <item> [amount]`."""
        if not self.host or client.name != self.host:
            _tell(client, "Only the host can do that.")
            return
        words = argument.split()
        amount = 1
        if words and words[-1].isdigit():
            amount = max(1, min(int(words.pop()), MAX_GIVE))
        name = "_".join(words).lower()
        items = self.game.content.items
        if client.player_id is None or name not in items:
            _tell(client, "Use /give <item name> [amount].")
            return
        item = items[name]
        left = self.game.players[client.player_id].inventory.add(
            ItemStack(item, amount)
        )
        given = amount - (left.amount if left else 0)
        _tell(client, f"Gave {given} {item.spec.name}.")

    def _weather(self, client: _Client) -> None:
        """Say whether it rains, and when the next shower comes."""
        rate = self.game.config.tick_rate
        day_ticks = DAY_SECONDS * rate
        clock = self.game.clock
        if rain_amount(clock, rate) > 0:
            _tell(client, "It is raining.")
            return
        step = max(1, day_ticks // 48)
        for ahead in range(step, day_ticks * MAX_RAIN_LOOKAHEAD, step):
            if rain_amount(clock + ahead, rate) > 0:
                hours = ahead / day_ticks * 24
                _tell(
                    client,
                    f"Dry. The next rain is in about {hours:.0f} hours.",
                )
                return
        _tell(client, "Dry, and no rain is coming soon.")

    def _go_home(self, client: _Client) -> None:
        if client.player_id is None:
            return
        self.game.go_home(self.game.players[client.player_id])
        _tell(client, "You are home.")

    def _command(self, client: _Client, text: str) -> None:
        command, _, argument = text.removeprefix("/").partition(" ")
        if command.lower() in {"kick", "mute", "unmute"}:
            self._moderate(client, command.lower(), argument)
            return
        if command.lower() == "time":
            self._set_time(client, argument)
            return
        if command.lower() == "give":
            self._give(client, argument)
            return
        if command.lower() == "home":
            self._go_home(client)
            return
        if command.lower() == "weather":
            self._weather(client)
            return
        if command.lower() in {"msg", "w", "whisper", "tell"}:
            self._whisper(client, argument)
            return
        names = [c.name for c in self.clients if c.player_id is not None]
        result = run_command(text, client.name, names, self.content)
        for line in result.private:
            client.connection.send(
                ChatMessage(kind=ChatKind.SYSTEM, text=line)
            )
        if result.public:
            self.say(result.public)

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
            case InventoryAction.QUICK_MOVE | InventoryAction.ARMOR_CLICK:
                self._move_or_wear(client, inventory, message)
            case (
                InventoryAction.CRAFTING_LEFT_CLICK
                | InventoryAction.CRAFTING_RIGHT_CLICK
            ) if 0 <= index < MAX_CRAFTING_SIDE**2:
                _click_grid(inventory, message)
            case (
                InventoryAction.CRAFT
                | InventoryAction.CRAFT_ALL
                | InventoryAction.STOW_CRAFTING
                | InventoryAction.GATHER
                | InventoryAction.FILL_RECIPE
                | InventoryAction.FILL_RECIPE_ALL
                | InventoryAction.SPREAD
                | InventoryAction.SPREAD_SINGLE
            ):
                _arrange(inventory, message, self.game.content)
            case InventoryAction.CLOSE:
                self.game.return_cursor_stack(player)
            case _:
                _kick(client, "Invalid inventory slot")

    def _move_or_wear(
        self, client: _Client, inventory: Inventory, message: InventoryMessage
    ) -> None:
        """Shift click a slot, or click an armor slot."""
        if message.action is InventoryAction.ARMOR_CLICK:
            inventory.armor_click(message.index)
        else:
            chest = self._reachable_chest(client)
            span = None
            if chest is not None and self._smelter_open(client):
                stack = (
                    inventory.slots[message.index]
                    if 0 <= message.index < len(inventory)
                    else None
                )
                span = self._smelter_span(stack)
                if span is None:
                    return
            inventory.quick_move(message.index, chest, span)

    def _smelter_open(self, client: _Client) -> bool:
        if client.chest is None:
            return False
        block = self.game.content.blocks.get(
            self.game.tilemap.get(*client.chest)
        )
        return block is not None and block.spec.smelter

    def _smelter_span(self, stack: ItemStack | None) -> tuple[int, int] | None:
        """Choose the furnace slots a stack may be shift clicked into.

        Returns:
            tuple[int, int] | None: Half-open slot range, `None` if the
            furnace takes no such thing.

        """
        if stack is None:
            return None
        if stack.item.name in self.game.content.smelting:
            return (INPUT, INPUT + 1)
        if stack.item.spec.fuel > 0:
            return (FUEL, FUEL + 1)
        return None

    def _reachable_chest(self, client: _Client) -> Inventory | None:
        """Find the chest a player has open, if it is in reach.

        Returns:
            Inventory | None: The contents, `None` if the chest is gone or
            too far.

        """
        if client.player_id is None or client.chest is None:
            return None
        player = self.game.players[client.player_id]
        if not player.can_reach(client.chest):
            return None
        return self.game.chest_at(*client.chest)

    def _open_chest(self, client: _Client, message: ChestOpen) -> None:
        if client.player_id is not None:
            player = self.game.players[client.player_id]
            if self.game.sleep_in(player, (message.x, message.y)):
                _tell(client, "Your spawn point is set to this bed.")
                return
        client.chest = (message.x, message.y)
        if self._reachable_chest(client) is None:
            client.chest = None

    def _click_chest(self, client: _Client, message: ChestClick) -> None:
        chest = self._reachable_chest(client)
        if chest is None or client.player_id is None:
            return
        if message.index >= len(chest):
            _kick(client, "Invalid chest slot")
            return
        inventory = self.game.players[client.player_id].inventory
        if message.quick:
            inventory.take_from(chest, message.index)
            return
        chest.cursor, inventory.cursor = inventory.cursor, None
        if message.right:
            chest.right_click(message.index)
        else:
            chest.left_click(message.index)
        chest.cursor, inventory.cursor = None, chest.cursor

    def _chest_state(self, client: _Client) -> ChestState | None:
        """Work out what to tell a client about its chest.

        Returns:
            ChestState | None: The message, `None` if there is nothing new.

        """
        chest = self._reachable_chest(client)
        if chest is None or client.chest is None:
            client.chest = None
            state = ChestState()
        else:
            x, y = client.chest
            state = ChestState(
                x=x, y=y, slots=[_stack_state(slot) for slot in chest]
            )
        previous = client.sent_chest
        if state.slots is None:
            client.sent_chest = None
            return None if previous is None else state
        if state == previous:
            return None
        client.sent_chest = state
        return state

    def _chest_message(
        self, client: _Client, message: ChestOpen | ChestClick | ChestClose
    ) -> None:
        match message:
            case ChestOpen():
                self._open_chest(client, message)
            case ChestClick():
                self._click_chest(client, message)
            case ChestClose():
                client.chest = None

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
            case ChatSend() if joined:
                self._chat(client, message)
            case ChestOpen() | ChestClick() | ChestClose() if joined:
                self._chest_message(client, message)
            case ChestOpen() | ChestClick() | ChestClose() if joined:
                self._chest_message(client, message)
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
        left: list[str] = []
        for client in self.clients:
            if not client.connection.closed:
                remaining.append(client)
                continue
            if client.player_id is not None:
                self.game.remove_player(client.player_id)
                left.append(client.name)
                LOGGER.info(
                    "%s left (%s)",
                    client.name,
                    client.connection.reason or "disconnected",
                )
        self.clients = remaining
        for name in left:
            self.broadcast(ChatMessage(kind=ChatKind.LEAVE, sender=name))

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
            clock=game.clock,
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
            mobs=[
                MobState(
                    kind=mob.kind.name,
                    x=mob.body.x,
                    y=mob.body.y,
                    facing_left=mob.facing_left,
                    hurt=mob.hurt > 0,
                    health=mob.health,
                )
                for mob in game.mobs.values()
            ],
            projectiles=[
                ProjectileState(
                    item=arrow.item,
                    x=arrow.x,
                    y=arrow.y,
                    vx=arrow.vx,
                    vy=arrow.vy,
                    hostile=arrow.hostile,
                )
                for arrow in game.projectiles.values()
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
        for text in self.game.announcements:
            self.say(text)
        self.game.announcements.clear()

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
            chest_state = self._chest_state(client)
            if chest_state is not None:
                client.connection.send(chest_state)
        for client in self.clients:
            client.connection.flush()

    def save(self, path: Path, owner: str | None = None) -> None:
        """Save the world, with every player's inventory, as `self.name`.

        `owner` is the host of a single player world.
        """
        save_world(
            path,
            self.name,
            self.game.tilemap,
            self.game.inventories(),
            owner,
            self.game.chest_contents(),
            self.game.clock,
        )

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
