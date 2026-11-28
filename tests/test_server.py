# Copyright (c) 2026 Schunche
"""Multiplayer: several players in one game, the server and its clients."""

from __future__ import annotations

import logging
import multiprocessing
import socket
import sys
import time
from collections import deque
from typing import TYPE_CHECKING

import pytest

from sch5n.game.chat import (
    CHAT_BURST,
    CHAT_REFILL_TICKS,
    MAX_CHAT_LENGTH,
    ChatKind,
)
from sch5n.game.config import DEFAULT_PORT, GameMode
from sch5n.game.content import AIR
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.net.client import (
    ClientSession,
    Dialer,
    SessionState,
    parse_address,
)
from sch5n.net.connection import HEADER_SIZE, Connection, local_pair
from sch5n.net.discovery import Announcer, Browser, lan_addresses
from sch5n.net.protocol import (
    MAX_CLIENT_FRAME,
    PROTOCOL_VERSION,
    ChatSend,
    Hello,
    InputMessage,
    InventoryAction,
    ProtocolError,
    content_fingerprint,
    decode_chunks,
    decode_client_message,
    decode_server_message,
    encode,
    encode_chunks,
)
from sch5n.server.__main__ import main as server_main
from sch5n.server.server import HELLO_TIMEOUT_TICKS, MAX_PLAYERS, Server
from sch5n.world.save import load_world, world_path
from sch5n.world.tilemap import TileMap
from tests.test_session import flat_world

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pydantic import BaseModel

    from sch5n.game.content import Content
    from sch5n.game.player import Player
    from sch5n.net.protocol import ClientMessage, ServerMessage

SETUP = GameSetup(seed=1, spawn=(0, 0))
MINE_TICKS = 200
TCP_TIMEOUT = 5.0
KEPT_SLOT = 5
KEPT_AMOUNT = 7
DIRT_SLOT = 2
DIRT_AMOUNT = 3
SURFACE = 10
"""Top row of `flat_world`."""
HOTBAR_PICK = 4
PLAYERS = 2
DISCOVERY_PORT = 47124
DISCOVERY_TIMEOUT = 15.0


@pytest.fixture
def server(content: Content) -> Server:
    """Run a server on a flat world, not on the network yet.

    Returns:
        Server: The server.

    """
    return Server(content, flat_world(content), SETUP, name="test")


def join(
    server: Server, content: Content, name: str = "alice"
) -> ClientSession:
    """Connect a client in memory and let the server welcome it.

    Returns:
        ClientSession: The joined session.

    """
    session = ClientSession(
        server.connect_local(), content, name, GameMode.SURVIVAL
    )
    server.step()
    session.poll()
    assert session.state is SessionState.PLAYING
    return session


def step(
    server: Server, sessions: list[ClientSession], ticks: int = 1
) -> None:
    """Run the server and let every client take in the result."""
    for _ in range(ticks):
        server.step()
        for session in sessions:
            session.poll()


def wait_until(
    condition: Callable[[], bool],
    server: Server,
    sessions: list[ClientSession],
) -> None:
    """Step until `condition` holds, for network round trips."""
    deadline = time.monotonic() + TCP_TIMEOUT
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        step(server, sessions)
        time.sleep(0.002)


# Several players in one game.


def test_players_join_and_leave(content: Content) -> None:
    """Players get their own ids, bodies and inventories."""
    game = Game(content, flat_world(content), GameSetup(host_player=False))
    with pytest.raises(LookupError):
        _ = game.player
    first, second = game.add_player("a"), game.add_player("b")
    assert first != second
    assert game.players[first].inventory is not game.players[second].inventory
    game.remove_player(first)
    assert list(game.players) == [second]


def test_returning_player_gets_its_inventory_back(content: Content) -> None:
    """Leaving keeps the inventory, by name, for when the player returns."""
    game = Game(content, flat_world(content), GameSetup(host_player=False))
    player_id = game.add_player("alice")
    game.players[player_id].inventory.slots[KEPT_SLOT] = ItemStack(
        content.items["dirt_block"], KEPT_AMOUNT
    )
    game.remove_player(player_id)
    again = game.add_player("alice")
    stack = game.players[again].inventory[KEPT_SLOT]
    assert stack is not None
    assert stack.amount == KEPT_AMOUNT


def test_each_player_follows_its_own_input(content: Content) -> None:
    """Input is per player: one walks right while the other stands."""
    game = Game(content, flat_world(content), SETUP)
    walker = next(iter(game.players))
    stander = game.add_player("b")
    x_walker = game.players[walker].body.x
    x_stander = game.players[stander].body.x
    for _ in range(30):
        game.tick({walker: TickInput(move_x=1)})
    assert game.players[walker].body.x > x_walker
    assert game.players[stander].body.x == x_stander


def test_cannot_place_inside_another_player(content: Content) -> None:
    """Blocks are not placed where any player stands."""
    game = Game(content, flat_world(content), SETUP)
    builder = next(iter(game.players))
    other = game.players[game.add_player("b")]
    inventory = game.players[builder].inventory
    inventory.slots[DIRT_SLOT] = ItemStack(
        content.items["dirt_block"], DIRT_AMOUNT
    )
    inventory.select(DIRT_SLOT)
    tile = (int(other.body.center[0] // 32), int(other.body.center[1] // 32))
    for _ in range(40):
        game.tick({builder: TickInput(place=True, target=tile)})
    assert game.tilemap.get(*tile) == AIR


# Protocol.


def test_messages_round_trip() -> None:
    """Messages survive encoding, and junk is refused."""
    hello = Hello(protocol=PROTOCOL_VERSION, content="abc", name="Ann")
    assert decode_client_message(encode(hello)) == hello
    move = InputMessage(move_x=-1, jump=True, target=(3, -4))
    assert decode_client_message(encode(move)) == move
    for junk in (b"", b"[]", b'{"type": "nope"}', b'{"type": "input"'):
        with pytest.raises(ProtocolError):
            decode_client_message(junk)
    with pytest.raises(ProtocolError):
        decode_client_message(encode(InputMessage()).replace(b"0", b"5"))
    # A client message is not a server message.
    with pytest.raises(ProtocolError):
        decode_server_message(encode(hello))


def test_chunks_round_trip(content: Content) -> None:
    """The world sent to a joining client is the server's world."""
    world = flat_world(content)
    world.set(-40, -40, content.blocks.id_of("stone"), 2)
    copy = TileMap(content.blocks)
    decode_chunks(encode_chunks(world), copy)
    assert sorted(copy.iter_tiles()) == sorted(world.iter_tiles())


def test_corrupt_chunks_are_refused(content: Content) -> None:
    """Chunks with bad data or unknown blocks are protocol errors."""
    chunk = encode_chunks(flat_world(content))[0]
    with pytest.raises(ProtocolError):
        decode_chunks(
            [chunk.model_copy(update={"blocks": "!!"})],
            TileMap(content.blocks),
        )
    other = encode_chunks(flat_world(content))[0]
    with pytest.raises(ProtocolError):
        decode_chunks(
            [other.model_copy(update={"blocks": chunk.variants})],
            TileMap(content.blocks),
        )


def test_parse_address() -> None:
    """Addresses are `host`, `host:port` or `[ipv6]:port`."""
    assert parse_address("example.org") == ("example.org", DEFAULT_PORT)
    assert parse_address(" 10.0.0.2:4000 ") == ("10.0.0.2", 4000)
    assert parse_address("[::1]:5") == ("::1", 5)
    assert parse_address("example.org", 4000) == ("example.org", 4000)
    assert parse_address("example.org:5", 4000) == ("example.org", 5)
    for bad in ("", ":4000", "host:port", "host:0", "host:70000"):
        with pytest.raises(ValueError, match=r"."):
            parse_address(bad)


# The server with in-memory clients.


def test_singleplayer_through_the_server(
    server: Server, content: Content
) -> None:
    """A client in memory plays like before: walking and mining."""
    session = join(server, content)
    world = session.world
    assert world is not None
    assert world.player is not None
    assert len(world.tilemap) == len(server.game.tilemap)
    x0 = world.player.body.x
    target = (1, SURFACE)
    for _ in range(MINE_TICKS):
        session.send_input(TickInput(use=True, target=target))
        step(server, [session])
    assert world.tilemap.get(*target) == AIR
    assert server.game.tilemap.get(*target) == AIR
    for _ in range(60):
        session.send_input(TickInput(move_x=1))
        step(server, [session])
    assert world.player.body.x > x0
    assert world.player.body.x == server.game.player.body.x


def test_players_see_each_other_and_the_world(
    server: Server, content: Content
) -> None:
    """What one player does, the other sees."""
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    step(server, [alice, bob])
    assert alice.world is not None
    assert bob.world is not None
    assert {p.name for p in alice.world.players.values()} == {"alice", "bob"}
    assert alice.world.local_id != bob.world.local_id

    target = (2, SURFACE)
    for _ in range(MINE_TICKS):
        alice.send_input(TickInput(use=True, target=target))
        step(server, [alice, bob])
    assert bob.world.tilemap.get(*target) == AIR
    # Bob sees Alice swing.
    for _ in range(3):
        alice.send_input(TickInput(use=True, target=(3, SURFACE)))
        step(server, [alice, bob])
    seen = bob.world.players[alice.world.local_id]
    assert seen.swing is not None


def test_inventory_actions_go_through_the_server(
    server: Server, content: Content
) -> None:
    """Inventory changes are made by the server and sent back."""
    session = join(server, content)
    world = session.world
    assert world is not None
    session.inventory(InventoryAction.SELECT, HOTBAR_PICK)
    step(server, [session])
    assert world.inventory.selected == HOTBAR_PICK
    session.inventory(InventoryAction.LEFT_CLICK, 0)
    step(server, [session])
    assert world.inventory.cursor is not None
    session.inventory(InventoryAction.CLOSE)
    step(server, [session])
    assert world.inventory.cursor is None
    assert world.inventory[0] is not None


def test_crafting_is_done_by_the_server(
    server: Server, content: Content
) -> None:
    """Grid clicks and crafting go to the server and come back."""
    session = join(server, content)
    world = session.world
    assert world is not None
    inventory = server.game.players[world.local_id].inventory
    inventory.slots[KEPT_SLOT] = ItemStack(content.items["oak_log"], 1)
    session.inventory(InventoryAction.LEFT_CLICK, KEPT_SLOT)
    session.inventory(InventoryAction.CRAFTING_LEFT_CLICK, 1)
    step(server, [session])
    assert world.inventory.crafting[1] is not None
    session.inventory(InventoryAction.CRAFT)
    step(server, [session])
    assert world.inventory.crafting[1] is None
    assert world.inventory.cursor is not None
    assert world.inventory.cursor.item.name == "oak_planks"
    session.inventory(InventoryAction.CLOSE)
    step(server, [session])
    assert world.inventory.cursor is None


def test_late_clicks_on_a_shrunk_grid_are_ignored(
    server: Server, content: Content
) -> None:
    """A click on a 3x3 slot after leaving the bench does not kick."""
    session = join(server, content)
    session.inventory(InventoryAction.CRAFTING_LEFT_CLICK, 8)
    step(server, [session])
    step(server, [session])
    assert server.player_count == 1


def test_clients_see_the_same_texture_variant(
    server: Server, content: Content
) -> None:
    """A tile's variant reaches every client."""
    session = join(server, content)
    bench = content.blocks.id_of("crafting_bench")
    server.game.tilemap.set(2, -20, bench, 1)
    step(server, [session])
    assert session.world is not None
    assert session.world.tilemap.get_variant(2, -20) == 1


def test_names_are_made_unique(server: Server, content: Content) -> None:
    """Two players with the same name are told apart."""
    first = join(server, content, "sam")
    second = join(server, content, "sam")
    step(server, [first, second])
    assert {p.name for p in server.game.players.values()} == {"sam", "sam 2"}


def test_leaving_removes_the_player(server: Server, content: Content) -> None:
    """A player that leaves disappears for the others."""
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    step(server, [alice, bob])
    bob.close()
    step(server, [alice])
    assert alice.world is not None
    assert [p.name for p in alice.world.players.values()] == ["alice"]


def test_server_closing_ends_sessions(
    server: Server, content: Content
) -> None:
    """Clients learn why the game ended."""
    session = join(server, content)
    server.close("Maintenance")
    session.poll()
    assert session.state is SessionState.CLOSED
    assert session.error == "Maintenance"


def test_mismatched_clients_are_rejected(
    server: Server, content: Content
) -> None:
    """Other game data or protocol versions cannot join."""
    for hello in (
        Hello(protocol=PROTOCOL_VERSION, content="other", name="x"),
        Hello(
            protocol=PROTOCOL_VERSION + 1,
            content=content_fingerprint(content),
            name="x",
        ),
    ):
        connection = server.connect_local()
        connection.send(hello)
        server.step()
        messages = connection.receive()
        assert [m.type for m in messages] == ["reject"]
        assert connection.closed
    assert server.player_count == 0


def test_misbehaving_clients_are_kicked(server: Server) -> None:
    """Input before hello is not allowed."""
    connection = server.connect_local()
    connection.send(InputMessage())
    server.step()
    assert [m.type for m in connection.receive()] == ["bye"]
    assert connection.closed
    assert not server.clients


def test_silent_clients_are_dropped(server: Server) -> None:
    """A connection that never says hello does not stay forever."""
    connection = server.connect_local()
    for _ in range(HELLO_TIMEOUT_TICKS + 2):
        server.step()
    connection.receive()
    assert connection.closed
    assert not server.clients


def test_server_has_room_for_a_limited_number(
    server: Server, content: Content
) -> None:
    """The server says when it is full."""
    for index in range(MAX_PLAYERS):
        join(server, content, f"p{index}")
    late = ClientSession(
        server.connect_local(), content, "late", GameMode.SURVIVAL
    )
    server.step()
    late.poll()
    assert late.state is SessionState.CLOSED
    assert late.error == "The server is full."


def test_hosts_may_admit_fewer_players(
    server: Server, content: Content
) -> None:
    """A lower player limit is kept."""
    server.max_players = 1
    join(server, content, "first")
    late = ClientSession(
        server.connect_local(), content, "late", GameMode.SURVIVAL
    )
    server.step()
    late.poll()
    assert late.error == "The server is full."


# Over TCP.


def connect_tcp(server: Server, content: Content, name: str) -> ClientSession:
    """Join a listening server over TCP on this computer.

    Returns:
        ClientSession: The joined session.

    """
    assert server.port is not None
    dialer = Dialer("127.0.0.1", server.port)
    deadline = time.monotonic() + TCP_TIMEOUT
    while (connection := dialer.take()) is None:
        assert dialer.error is None, dialer.error
        assert time.monotonic() < deadline, "could not connect"
        server.step()
        time.sleep(0.002)
    session = ClientSession(connection, content, name, GameMode.SURVIVAL)
    wait_until(
        lambda: session.state is not SessionState.JOINING, server, [session]
    )
    return session


def test_tcp_clients_play_together(server: Server, content: Content) -> None:
    """A host in memory and a client over TCP share the game."""
    port = server.listen("127.0.0.1", 0, announce=False)
    assert port == server.port
    host = join(server, content, "host")
    guest = connect_tcp(server, content, "guest")
    assert guest.state is SessionState.PLAYING
    guest_world, host_world = guest.world, host.world
    assert guest_world is not None
    assert host_world is not None
    wait_until(
        lambda: len(guest_world.players) == PLAYERS, server, [host, guest]
    )

    target = (-3, SURFACE)
    for _ in range(MINE_TICKS):
        guest.send_input(TickInput(use=True, target=target))
        step(server, [host, guest])
        time.sleep(0.0005)
    wait_until(
        lambda: host_world.tilemap.get(*target) == AIR, server, [host, guest]
    )

    server.close()
    wait_until(
        lambda: guest.state is SessionState.CLOSED, server, [host, guest]
    )
    assert guest.error == "The server closed"


def raw_client(port: int) -> socket.socket:
    """Connect a plain socket, to send whatever a test wants.

    Returns:
        socket.socket: The connected socket.

    """
    sock = socket.create_connection(("127.0.0.1", port), timeout=TCP_TIMEOUT)
    sock.settimeout(TCP_TIMEOUT)
    return sock


def closed_by_server(sock: socket.socket, server: Server) -> bool:
    """Step the server until it hangs up on `sock`.

    Returns:
        bool: Whether it did in time.

    """
    sock.settimeout(0.01)
    deadline = time.monotonic() + TCP_TIMEOUT
    while time.monotonic() < deadline:
        server.step()
        try:
            if sock.recv(65536) == b"":
                return True
        except TimeoutError:
            continue
        except OSError:
            return True
    return False


@pytest.mark.parametrize(
    "payload",
    [
        b"\x00\x00\x00\x04junk",
        (MAX_CLIENT_FRAME + 1).to_bytes(HEADER_SIZE, "big"),
        b"\x00\x00\x00\x02{}",
    ],
    ids=["junk", "too large", "no type"],
)
def test_bad_frames_disconnect(server: Server, payload: bytes) -> None:
    """Malformed or oversized messages end the connection, not the server."""
    port = server.listen("127.0.0.1", 0, announce=False)
    sock = raw_client(port)
    with sock:
        sock.sendall(payload)
        assert closed_by_server(sock, server)
    assert not server.clients


def test_port_in_use(server: Server, content: Content, tmp_path: Path) -> None:
    """A taken port is an error, and the CLI exits with an error code."""
    port = server.listen("127.0.0.1", 0, announce=False)
    other = Server(content, flat_world(content))
    with pytest.raises(OSError, match=r"."):
        other.listen("127.0.0.1", port, announce=False)
    with pytest.raises(SystemExit) as stopped:
        server_main([
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-lan",
            "--worlds-dir",
            str(tmp_path),
        ])
    assert stopped.value.code == 1


def test_dedicated_server_runs_and_keeps_its_world(
    tmp_path: Path, content: Content, caplog: pytest.LogCaptureFixture
) -> None:
    """`sch5n server` serves, saves when it stops, and continues later."""
    arguments = [
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--no-lan",
        "--ticks",
        "3",
        "--name",
        "Test world",
        "--worlds-dir",
        str(tmp_path),
    ]
    server_main(arguments)
    saved = world_path(tmp_path, "Test world")
    assert saved.exists()
    world = load_world(saved, content)
    assert world.name == "Test world"
    with caplog.at_level(logging.INFO, logger="sch5n"):
        server_main(arguments)
    assert "Continuing the world" in caplog.text


def loaded_gui_modules() -> list[str]:
    """Window, OpenGL and font libraries loaded in this process.

    Returns:
        list[str]: Their module names.

    """
    return sorted({"glfw", "moderngl", "pygame"} & set(sys.modules))


def test_server_is_headless() -> None:
    """The server never loads the window, OpenGL or font libraries.

    This module imports the server; a fresh interpreter imports it and
    nothing else.
    """
    with multiprocessing.get_context("spawn").Pool(1) as pool:
        assert pool.apply(loaded_gui_modules) == []


def test_local_pair_delivers_in_order() -> None:
    """The in-memory connection keeps order and reports closing."""
    left: Connection[ClientMessage, ServerMessage]
    right: Connection[ServerMessage, ClientMessage]
    left, right = local_pair()
    moves = [InputMessage(move_x=move) for move in (-1, 0, 1)]
    for move in moves:
        left.send(move)
    assert right.receive() == moves
    left.close("bye")
    assert right.receive() == []
    assert right.closed
    assert right.reason == "bye"


def test_goodbye_before_hanging_up_is_read(
    server: Server, content: Content, caplog: pytest.LogCaptureFixture
) -> None:
    """A client's last words arrive even though it closes right after."""
    server.listen("127.0.0.1", 0, announce=False)
    guest = connect_tcp(server, content, "guest")
    guest.close()
    with caplog.at_level(logging.INFO, logger="sch5n"):
        deadline = time.monotonic() + TCP_TIMEOUT
        while server.player_count:
            assert time.monotonic() < deadline
            server.step()
            time.sleep(0.002)
    assert "guest left (Left the game)" in caplog.text


def test_lan_discovery() -> None:
    """A game announced on the network is found by the browser."""
    if not lan_addresses():
        pytest.skip("This computer is on no network")
    announcer = Announcer("Discovery test", DISCOVERY_PORT)
    browser = Browser()
    try:
        deadline = time.monotonic() + DISCOVERY_TIMEOUT
        while not any(g.port == DISCOVERY_PORT for g in browser.games):
            assert time.monotonic() < deadline, "not found"
            time.sleep(0.1)
        game = next(g for g in browser.games if g.port == DISCOVERY_PORT)
        assert game.name == "Discovery test"
        assert game.address == f"{game.host}:{DISCOVERY_PORT}"
    finally:
        announcer.close()
        browser.close()


# Client side prediction.

LAG_TICKS = 10
"""Ticks each way: a round trip of a third of a second."""


class Delayed[Out: BaseModel, In: BaseModel](Connection[Out, In]):
    """A connection that holds messages back, like a slow network.

    Time is counted in calls to `receive`, which clients make once per
    tick.
    """

    def __init__(self, inner: Connection[Out, In], ticks: int) -> None:
        """Delay `inner` by `ticks` in each direction."""
        super().__init__()
        self.inner = inner
        self.ticks = ticks
        self.now = 0
        self.outgoing: deque[tuple[int, Out]] = deque()
        self.incoming: deque[tuple[int, In]] = deque()

    def send(self, message: Out) -> None:
        """Send `message` after the delay."""
        self.outgoing.append((self.now + self.ticks, message))

    def receive(self) -> list[In]:
        """Advance time; deliver what is due both ways.

        Returns:
            list[In]: Messages whose delay is over.

        """
        self.now += 1
        while self.outgoing and self.outgoing[0][0] <= self.now:
            self.inner.send(self.outgoing.popleft()[1])
        for message in self.inner.receive():
            self.incoming.append((self.now + self.ticks, message))
        due = []
        while self.incoming and self.incoming[0][0] <= self.now:
            due.append(self.incoming.popleft()[1])
        self.closed = self.inner.closed and not self.incoming
        return due


def lagged(server: Server, content: Content) -> ClientSession:
    """Join over a connection with `LAG_TICKS` of delay each way.

    Returns:
        ClientSession: The joined session.

    """
    connection = Delayed(server.connect_local(), LAG_TICKS)
    session = ClientSession(connection, content, "far", GameMode.SURVIVAL)
    connection.receive()
    for _ in range(3 * LAG_TICKS):
        step(server, [session])
    assert session.world is not None
    assert session.world.player is not None
    return session


def play(
    server: Server, session: ClientSession, ticks: int, inp: TickInput
) -> None:
    """Send the same input for `ticks`, the way the game does."""
    for _ in range(ticks):
        session.send_input(inp)
        step(server, [session])


def own_player(session: ClientSession) -> Player:
    """Get the session's own player.

    Returns:
        Player: The player.

    """
    assert session.world is not None
    player = session.world.player
    assert player is not None
    return player


def test_own_player_moves_right_away(server: Server, content: Content) -> None:
    """With lag, the own player moves at once; the server catches up."""
    session = lagged(server, content)
    world = session.world
    assert world is not None
    player = own_player(session)
    on_server = server.game.players[world.local_id]
    x0, y0 = player.body.x, player.body.y

    play(server, session, 1, TickInput(move_x=1, jump=True, jump_held=True))
    assert player.body.x > x0
    assert player.body.y < y0
    assert on_server.body.x == x0  # The input is still on its way.

    play(server, session, 60, TickInput(move_x=1))
    play(server, session, LAG_TICKS, TickInput())
    # Every input sent is in flight for a round trip.
    assert len(world.pending) >= 2 * LAG_TICKS - 1
    step(server, [session], 3 * LAG_TICKS)
    assert not world.pending
    assert (player.body.x, player.body.y) == (
        on_server.body.x,
        on_server.body.y,
    )
    assert world.corrections == 0


def test_prediction_is_corrected(server: Server, content: Content) -> None:
    """When the server disagrees, its word counts and the client follows."""
    session = lagged(server, content)
    world = session.world
    assert world is not None
    player = own_player(session)
    on_server = server.game.players[world.local_id]

    play(server, session, 2 * LAG_TICKS, TickInput(move_x=1))
    # A wall appears just ahead of where the server has the player. The
    # client, ahead of the server, walks into it before it learns of it.
    stone = content.blocks.id_of("stone")
    wall_x = int((on_server.body.x + on_server.body.w + 33) // 32)
    for y in range(SURFACE - 4, SURFACE):
        server.game.tilemap.set(wall_x, y, stone)
    play(server, session, 40, TickInput(move_x=1))
    step(server, [session], 3 * LAG_TICKS)
    assert player.body.x + player.body.w <= wall_x * 32
    assert player.body.x == on_server.body.x
    assert world.corrections > 0


def test_without_prediction_the_player_waits(
    server: Server, content: Content
) -> None:
    """Turning prediction off shows the lag: nothing moves at first."""
    session = lagged(server, content)
    assert session.world is not None
    session.world.prediction = False
    player = own_player(session)
    x0 = player.body.x
    play(server, session, LAG_TICKS, TickInput(move_x=1))
    assert own_player(session).body.x == x0
    play(server, session, 2 * LAG_TICKS + 2, TickInput(move_x=1))
    assert own_player(session).body.x > x0
    del player


def test_server_uses_one_input_per_tick(
    server: Server, content: Content
) -> None:
    """Inputs are applied one per tick, catching up after a burst."""
    session = join(server, content)
    assert session.world is not None
    burst = 10
    for _ in range(burst):
        session.send_input(TickInput(move_x=1))
    server.step()
    queued = server.clients[0].inputs
    assert len(queued) == burst - 2
    while queued:
        server.step()
    session.poll()
    assert session.world.pending == deque()


def test_inputs_out_of_order_are_refused(server: Server) -> None:
    """A client cannot send an input twice."""
    connection = server.connect_local()
    connection.send(
        Hello(protocol=PROTOCOL_VERSION, content=server.fingerprint, name="x")
    )
    server.step()
    connection.send(InputMessage(seq=5))
    connection.send(InputMessage(seq=5))
    server.step()
    assert connection.receive()[-1].type == "bye"
    assert connection.closed


# Chat.


def lines(session: ClientSession) -> list[tuple[str, str, str]]:
    """Describe a session's chat as kind, sender and text.

    Returns:
        list[tuple[str, str, str]]: The lines, oldest first.

    """
    return [(m.kind.value, m.sender, m.text) for m in session.chat]


def test_chat_is_broadcast_by_the_server(
    server: Server, content: Content
) -> None:
    """Everyone sees what a player says, under the server's name for them."""
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    step(server, [alice, bob])
    alice.say("hello   there")
    step(server, [alice, bob], 2)
    assert ("chat", "alice", "hello there") in lines(alice)
    assert ("chat", "alice", "hello there") in lines(bob)
    assert ("join", "bob", "") in lines(alice)


def test_chat_is_cleaned_and_limited(server: Server, content: Content) -> None:
    """Control characters go, long text is cut, blank text is dropped."""
    alice = join(server, content)
    dirty = "a\x00b\x1b[31m" + chr(0x202E) + "x" * 500
    alice.connection.send(ChatSend(text=dirty))
    alice.connection.send(ChatSend(text=" \t\n "))
    step(server, [alice], 2)
    said = [m for m in alice.chat if m.kind is ChatKind.CHAT]
    assert len(said) == 1
    assert len(said[0].text) == MAX_CHAT_LENGTH
    assert said[0].text.startswith("ab[31m")
    assert all(c.isprintable() for c in said[0].text)


def test_chat_cannot_be_spoofed(server: Server, content: Content) -> None:
    """Clients cannot send join messages or choose the sender."""
    alice = join(server, content)
    with pytest.raises(ProtocolError):
        decode_client_message(
            b'{"type": "chat", "text": "hi", "sender": "server"}'
        )
    with pytest.raises(ProtocolError):
        decode_client_message(b'{"type": "chat_message", "text": "hi"}')
    step(server, [alice])


def test_chat_is_rate_limited(server: Server, content: Content) -> None:
    """A flood is dropped, and the sender is told."""
    alice = join(server, content)
    for number in range(CHAT_BURST + 3):
        alice.say(f"spam {number}")
    step(server, [alice], 2)
    said = [m for m in alice.chat if m.kind is ChatKind.CHAT]
    assert len(said) == CHAT_BURST
    assert any(m.kind is ChatKind.SYSTEM for m in alice.chat)
    step(server, [alice], CHAT_REFILL_TICKS)
    alice.say("again")
    step(server, [alice], 2)
    assert ("chat", "alice", "again") in lines(alice)


def test_leaving_is_announced_and_history_is_given(
    server: Server, content: Content
) -> None:
    """Players see who left; newcomers see what was said before."""
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    alice.say("first")
    step(server, [alice, bob], 2)
    bob.close()
    step(server, [alice], 2)
    assert ("leave", "bob", "") in lines(alice)
    carol = join(server, content, "carol")
    step(server, [carol])
    assert ("chat", "alice", "first") in lines(carol)
    server.say("restart \x07soon")
    step(server, [alice, carol], 2)
    assert ("system", "", "restart soon") in lines(carol)


def test_vitals_reach_the_client_and_deaths_are_announced(
    server: Server, content: Content
) -> None:
    """Health and hunger are synced; starving is announced in chat."""
    alice = join(server, content, "alice")
    player = next(iter(server.game.players.values()))
    player.vitals.hunger = 7
    step(server, [alice])
    assert alice.world is not None
    assert alice.world.player is not None
    assert alice.world.player.vitals.hunger == 7  # ruff: ignore[magic-value-comparison]
    server.game.announcements.append("alice starved")
    step(server, [alice], 2)
    assert ("system", "", "alice starved") in lines(alice)


def test_chat_commands(server: Server, content: Content) -> None:
    """Commands answer only the sender; /me is for everyone."""
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    step(server, [alice, bob])
    alice.say("/players")
    alice.say("/recipes stone pickaxe")
    alice.say("/nope")
    alice.say("/me waves")
    step(server, [alice, bob], 2)
    mine = [m.text for m in alice.chat if m.kind is ChatKind.SYSTEM]
    assert "2 online: alice, bob" in mine
    assert any(t.startswith("Stone Pickaxe:") for t in mine)
    assert any("Unknown command /nope" in t for t in mine)
    theirs = [m.text for m in bob.chat if m.kind is ChatKind.SYSTEM]
    assert theirs == ["* alice waves"]
    assert not [m for m in bob.chat if m.kind is ChatKind.CHAT]


def test_the_host_can_mute_and_kick(server: Server, content: Content) -> None:
    """Only the host moderates; muted players cannot speak."""
    server.host = "alice"
    alice = join(server, content, "alice")
    bob = join(server, content, "bob")
    step(server, [alice, bob])
    bob.say("/mute alice")
    step(server, [alice, bob], 2)
    assert any("Only the host" in m.text for m in bob.chat)
    alice.say("/mute BOB")
    step(server, [alice, bob], 2)
    assert any(m.text == "bob was muted" for m in bob.chat)
    bob.say("hello?")
    step(server, [alice, bob], 2)
    assert any(m.text == "You are muted." for m in bob.chat)
    assert not [m for m in alice.chat if m.kind is ChatKind.CHAT]
    alice.say("/unmute bob")
    bob.say("hi")
    step(server, [alice, bob], 2)
    assert ("chat", "bob", "hi") in lines(alice)
    alice.say("/kick nobody")
    alice.say("/kick alice")
    alice.say("/kick bob")
    step(server, [alice, bob], 3)
    assert bob.state is SessionState.CLOSED
    assert bob.error == "Kicked by the host"
    assert ("leave", "bob", "") in lines(alice)
    assert any("Nobody is called" in m.text for m in alice.chat)
    assert alice.state is SessionState.PLAYING
