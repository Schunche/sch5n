# Copyright (c) 2026 Schunche
"""Messages exchanged by the server and its clients.

Every message is a JSON object with a `type` field. Clients send
`Hello` first; the server answers with `Welcome` (the whole world) or
`Reject`. Then clients send their input every tick and the server sends
back a `Snapshot` of everything that moves every tick.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import zlib
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from sch5n.game.chat import ChatKind
from sch5n.game.config import MAX_NAME_LENGTH
from sch5n.world.tilemap import CHUNK_SIZE, Chunk

if TYPE_CHECKING:
    from sch5n.game.content import Content
    from sch5n.world.tilemap import TileMap

PROTOCOL_VERSION = 10
"""Raised whenever messages change incompatibly."""
MAX_CLIENT_FRAME = 4096
"""Largest message a client may send, in bytes."""
MAX_SPREAD = 128
"""Most slots one inventory message may name."""
MAX_SERVER_FRAME = 256 * 1024 * 1024
"""Largest message a server may send, in bytes. Welcome carries the
world."""
_TILES = CHUNK_SIZE * CHUNK_SIZE


class ProtocolError(ValueError):
    """A peer sent something that is not a valid message."""


class _Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# Client to server.


class Hello(_Message):
    """First message of a client: who it is and what it runs."""

    type: Literal["hello"] = "hello"
    protocol: int
    content: str
    """`content_fingerprint` of the client's blocks and items."""
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)


class InputMessage(_Message):
    """What a player does this tick. See `TickInput`."""

    type: Literal["input"] = "input"
    seq: int = Field(default=0, ge=0)
    """Counts up by one per input. Snapshots acknowledge it."""
    move_x: int = Field(default=0, ge=-1, le=1)
    jump: bool = False
    jump_held: bool = False
    use: bool = False
    place: bool = False
    target: tuple[int, int] | None = None


class InventoryAction(StrEnum):
    """Something done in the inventory GUI."""

    SELECT = "select"
    """Select hotbar slot `index`."""
    SCROLL = "scroll"
    """Move the hotbar selection by `index` slots."""
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    CLOSE = "close"
    """The inventory was closed: the cursor and crafting stacks go back."""
    CRAFTING_LEFT_CLICK = "crafting_left_click"
    """Like `LEFT_CLICK`, on slot `index` of the crafting grid."""
    CRAFTING_RIGHT_CLICK = "crafting_right_click"
    CRAFT = "craft"
    """Take the crafting result onto the cursor."""
    CRAFT_ALL = "craft_all"
    """Craft as much as possible into the inventory."""
    STOW_CRAFTING = "stow_crafting"
    """Move slot `index` of the crafting grid into the inventory."""
    QUICK_MOVE = "quick_move"
    """Shift click slot `index`: into the open chest, onto the body, or
    between the hotbar and the rest."""
    ARMOR_CLICK = "armor_click"
    """Wear or take off armor: click slot `index` of the armor slots."""
    SPREAD = "spread"
    """Share the cursor stack evenly among `slots`. See
    `Inventory.spread`."""
    SPREAD_SINGLE = "spread_single"
    """Put one item of the cursor stack into each of `slots`."""
    GATHER = "gather"
    """Collect matching items into slot `index`, numbered like `slots`."""


class InventoryMessage(_Message):
    """An inventory action of the player."""

    type: Literal["inventory"] = "inventory"
    action: InventoryAction
    index: int = 0
    slots: tuple[int, ...] = Field(default=(), max_length=MAX_SPREAD)
    """Slots numbered through the inventory, then the crafting grid."""


class ChatSend(_Message):
    """A player says something. The server cleans and limits the text."""

    type: Literal["chat"] = "chat"
    text: str


class ChestOpen(_Message):
    """The player opens the storage block at a tile."""

    type: Literal["chest_open"] = "chest_open"
    x: int
    y: int


class ChestClick(_Message):
    """A click on slot `index` of the open chest.

    It works like an inventory click. The server checks the index.
    """

    type: Literal["chest_click"] = "chest_click"
    index: int = Field(ge=0)
    right: bool = False
    quick: bool = False
    """Take the whole stack into the inventory, like a shift click."""


class ChestClose(_Message):
    """The player closes the chest."""

    type: Literal["chest_close"] = "chest_close"


class Goodbye(_Message):
    """The sender is leaving. Either side may send it."""

    type: Literal["bye"] = "bye"
    reason: str = ""


# Server to client.


class ChunkData(_Message):
    """One chunk of tiles: zlib compressed arrays, base64 encoded."""

    x: int
    y: int
    blocks: str
    """Little endian uint16 block ids, row by row."""
    variants: str
    """uint8 texture variants, row by row."""


class Welcome(_Message):
    """The client joined: its player and the world."""

    type: Literal["welcome"] = "welcome"
    player_id: int
    server_name: str
    chunks: list[ChunkData]


class Reject(_Message):
    """The client may not join."""

    type: Literal["reject"] = "reject"
    reason: str


class SwingState(_Message):
    """An item swing in progress. See `Swing`."""

    item: str
    age: int
    duration: int


class PlayerState(_Message):
    """Where a player is and what it is doing."""

    id: int
    name: str
    x: float
    y: float
    vx: float
    vy: float
    facing_left: bool
    action: str
    action_age: int = 0
    swing: SwingState | None = None
    jumps: int = 0
    air_time: int = 0
    jump_hold: int = 0
    jump_speed: float = 0.0
    wall_slide: bool = False
    use_cooldown: int = 0
    health: int = 20
    hunger: int = 20
    deaths: int = 0


class ItemState(_Message):
    """A dropped item: sprite position and contents."""

    item: str
    amount: int
    x: float
    y: float


class MobState(_Message):
    """A hostile creature."""

    kind: str
    x: float
    y: float
    facing_left: bool = False
    hurt: bool = False
    health: int = 0
    """Health left. Zero means it is not told."""


class ProjectileState(_Message):
    """An arrow in flight."""

    item: str
    x: float
    y: float
    vx: float
    vy: float
    hostile: bool = False


class Snapshot(_Message):
    """Everything that moves, sent every tick."""

    type: Literal["snapshot"] = "snapshot"
    tick: int
    clock: int = 0
    """Ticks the day and night count, see `Game.clock`."""
    ack: int | None = None
    """`seq` of the receiver's last input the server applied, `None`
    before the first. The receiver replays its later inputs on top."""
    wind: float
    players: list[PlayerState]
    items: list[ItemState]
    mobs: list[MobState] = []
    projectiles: list[ProjectileState] = []
    tiles: list[tuple[int, int, int, int]] = []
    """Tiles changed since the last snapshot: `(x, y, block, variant)`."""
    damage: list[tuple[int, int, float]] = []
    """Every partially broken tile: `(x, y, remaining durability)`."""


class StackState(_Message):
    """An item stack."""

    item: str
    amount: int


class InventoryState(_Message):
    """The client's own inventory, sent whenever it changes."""

    type: Literal["inventory_state"] = "inventory_state"
    slots: list[StackState | None]
    cursor: StackState | None
    selected: int
    crafting: list[StackState | None]
    armor: list[StackState | None] = []
    stations: list[str] = []
    """Crafting stations in reach, which some recipes need."""


class ChestState(_Message):
    """The chest a player has open. `slots` is `None` once it closed."""

    type: Literal["chest_state"] = "chest_state"
    x: int = 0
    y: int = 0
    slots: list[StackState | None] | None = None


class ChatMessage(_Message):
    """A line of chat, sent to everyone it concerns."""

    type: Literal["chat_message"] = "chat_message"
    kind: ChatKind = ChatKind.CHAT
    sender: str = ""
    """Name of the speaking player, or of the one who joined or left."""
    text: str = ""


type ClientMessage = Annotated[
    Hello
    | InputMessage
    | InventoryMessage
    | ChatSend
    | ChestOpen
    | ChestClick
    | ChestClose
    | Goodbye,
    Field(discriminator="type"),
]
type ServerMessage = Annotated[
    Welcome
    | Reject
    | Snapshot
    | InventoryState
    | ChestState
    | ChatMessage
    | Goodbye,
    Field(discriminator="type"),
]
type Message = ClientMessage | ServerMessage

_CLIENT_MESSAGES: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
_SERVER_MESSAGES: TypeAdapter[ServerMessage] = TypeAdapter(ServerMessage)


def encode(message: BaseModel) -> bytes:
    """Serialize a message.

    Returns:
        bytes: UTF-8 JSON.

    """
    return message.model_dump_json().encode()


def decode_client_message(data: bytes) -> ClientMessage:
    """Parse a message sent by a client.

    Returns:
        ClientMessage: The message.

    Raises:
        ProtocolError: It is not a valid client message.

    """
    try:
        return _CLIENT_MESSAGES.validate_json(data)
    except ValidationError as error:
        msg = f"Invalid client message: {error.error_count()} errors"
        raise ProtocolError(msg) from error


def decode_server_message(data: bytes) -> ServerMessage:
    """Parse a message sent by a server.

    Returns:
        ServerMessage: The message.

    Raises:
        ProtocolError: It is not a valid server message.

    """
    try:
        return _SERVER_MESSAGES.validate_json(data)
    except ValidationError as error:
        msg = f"Invalid server message: {error.error_count()} errors"
        raise ProtocolError(msg) from error


def content_fingerprint(content: Content) -> str:
    """Hash of everything both sides must agree on: block ids and items.

    Returns:
        str: Hex digest.

    """
    blocks = sorted((block.id, block.name) for block in content.blocks)
    items = sorted(item.name for item in content.items)
    recipes = [recipe.model_dump() for recipe in content.recipes]
    data = json.dumps([blocks, items, recipes]).encode()
    return hashlib.sha256(data).hexdigest()[:16]


def _pack(array: np.ndarray) -> str:
    return base64.b64encode(zlib.compress(array.tobytes())).decode("ascii")


def _unpack(text: str, dtype: str) -> np.ndarray:
    try:
        raw = zlib.decompress(base64.b64decode(text, validate=True))
    except (binascii.Error, zlib.error) as error:
        msg = "Corrupt chunk data"
        raise ProtocolError(msg) from error
    array = np.frombuffer(raw, dtype=dtype)
    if array.size != _TILES:
        msg = "Chunk data has the wrong size"
        raise ProtocolError(msg)
    return array.reshape(CHUNK_SIZE, CHUNK_SIZE).copy()


def encode_chunks(tilemap: TileMap) -> list[ChunkData]:
    """Pack every chunk of a tilemap.

    Returns:
        list[ChunkData]: The chunks.

    """
    return [
        ChunkData(
            x=cx,
            y=cy,
            blocks=_pack(chunk.blocks.astype("<u2")),
            variants=_pack(chunk.variants),
        )
        for (cx, cy), chunk in tilemap.chunks.items()
    ]


def decode_chunks(chunks: list[ChunkData], tilemap: TileMap) -> None:
    """Fill `tilemap` with packed chunks.

    Raises:
        ProtocolError: A chunk is corrupt or has unknown blocks.

    """
    known = len(tilemap.blocks)
    for data in chunks:
        blocks = _unpack(data.blocks, "<u2").astype(np.uint16)
        if blocks.size and int(blocks.max()) >= known:
            msg = "Chunk has unknown blocks"
            raise ProtocolError(msg)
        filled = int(np.count_nonzero(blocks))
        if filled:
            tilemap.chunks[data.x, data.y] = Chunk(
                blocks, _unpack(data.variants, "u1"), filled
            )
