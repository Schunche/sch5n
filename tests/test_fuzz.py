# Copyright (c) 2026 Schunche
"""A client that sends nonsense must not crash the server."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from sch5n.game.config import GameMode
from sch5n.game.inventory import ItemStack
from sch5n.game.session import GameSetup
from sch5n.net.client import ClientSession, SessionState
from sch5n.net.protocol import (
    ChatSend,
    ChestClick,
    ChestClose,
    ChestOpen,
    InputMessage,
    InventoryAction,
    InventoryMessage,
)
from sch5n.server.server import Server
from tests.test_server import step
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content
    from sch5n.net.protocol import ClientMessage

ROUNDS = 600
BIG = 10**6
TEXTS = ("", "hi", "/msg", "/msg x y", "/time", "/kick", "x" * 400, "/\x00")


def _input(rng: np.random.Generator, seq: int) -> ClientMessage:
    return InputMessage(
        seq=seq,
        move_x=int(rng.integers(-1, 2)),
        jump=bool(rng.integers(2)),
        use=bool(rng.integers(2)),
        place=bool(rng.integers(2)),
        target=(int(rng.integers(-BIG, BIG)), int(rng.integers(-3, 60)))
        if rng.integers(2)
        else None,
    )


def _inventory(rng: np.random.Generator, _seq: int) -> ClientMessage:
    actions = list(InventoryAction)
    index = int(
        rng.integers(-3, 60) if rng.integers(2) else rng.integers(-BIG, BIG)
    )
    return InventoryMessage(
        action=actions[int(rng.integers(len(actions)))],
        index=index,
        slots=tuple(
            int(v) for v in rng.integers(-5, 80, int(rng.integers(5)))
        ),
    )


def _chat(rng: np.random.Generator, _seq: int) -> ClientMessage:
    return ChatSend(text=TEXTS[int(rng.integers(len(TEXTS)))])


def _open(rng: np.random.Generator, _seq: int) -> ClientMessage:
    return ChestOpen(x=int(rng.integers(-3, 10)), y=int(rng.integers(5, 12)))


def _click(rng: np.random.Generator, _seq: int) -> ClientMessage:
    return ChestClick(
        index=int(rng.integers(0, 60)),
        right=bool(rng.integers(2)),
        quick=bool(rng.integers(2)),
    )


def _close(_rng: np.random.Generator, _seq: int) -> ClientMessage:
    return ChestClose()


MAKERS = (_input, _inventory, _chat, _open, _click, _close)


def random_message(rng: np.random.Generator, seq: int) -> ClientMessage:
    """Make a random but well formed message.

    Returns:
        ClientMessage: The message.

    """
    return MAKERS[int(rng.integers(len(MAKERS)))](rng, seq)


def test_random_messages_do_not_crash_the_server(content: Content) -> None:
    """Whatever a client sends, the server keeps running and replies."""
    rng = np.random.default_rng(5)
    server = Server(
        content, flat_world(content), GameSetup(seed=1, spawn=(0, 0))
    )
    server.game.tilemap.set(1, 9, content.blocks.id_of("chest"))
    server.game.tilemap.set(2, 9, content.blocks.id_of("bed"))
    joined = 0
    session: ClientSession | None = None
    seq = 0
    for _ in range(ROUNDS):
        if session is None or session.state is not SessionState.PLAYING:
            session = ClientSession(
                server.connect_local(),
                content,
                f"fuzz{joined}",
                GameMode.SURVIVAL,
            )
            joined += 1
            seq = 0
            step(server, [session], 2)
            if session.state is not SessionState.PLAYING:
                continue
            player = next(iter(server.game.players.values()))
            player.inventory.slots[12] = ItemStack(
                content.items["iron_helmet"]
            )
            player.inventory.cursor = ItemStack(content.items["stick"], 3)
        for _ in range(int(rng.integers(1, 4))):
            seq += 1
            session.connection.send(random_message(rng, seq))
        step(server, [session])
    assert joined >= 1
    assert server.game.ticks >= ROUNDS
