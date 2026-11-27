# Copyright (c) 2026 Schunche
"""Message transports: in memory for single player, TCP for multiplayer.

Connections never block and never raise on a broken peer: `receive`
returns what arrived and marks the connection closed, with a reason,
when the peer left or misbehaved.
"""

from __future__ import annotations

import errno
import socket
from collections import deque
from typing import TYPE_CHECKING

from sch5n.log.logger import LOGGER
from sch5n.net.protocol import ProtocolError, encode

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel

HEADER_SIZE = 4
"""Every frame starts with its length as a big endian uint32."""
RECEIVE_SIZE = 65536
MAX_PENDING_OUTPUT = 64 * 1024 * 1024
"""A peer that lets this much pile up is too slow and gets dropped."""
CLOSE_FLUSH_TIMEOUT = 1.0
"""Seconds to finish sending when closing, for the goodbye message."""


class Connection[Out: BaseModel, In: BaseModel]:
    """Sends `Out` messages and receives `In` messages."""

    def __init__(self) -> None:
        """Start open."""
        self.closed = False
        self.reason = ""
        """Why the connection closed, for the player."""

    def send(self, message: Out) -> None:
        """Queue a message. Ignored once closed."""
        raise NotImplementedError

    def receive(self) -> list[In]:
        """Take every message that arrived."""
        raise NotImplementedError

    def flush(self) -> None:
        """Push queued messages out, as far as possible without waiting."""

    def close(self, reason: str = "") -> None:
        """Close the connection. Queued messages are still delivered."""
        if not self.closed:
            self.closed = True
            self.reason = reason

    @property
    def address(self) -> str:
        """Where the peer is, for logs."""
        return "local"


class _Pipe[T]:
    """One direction of an in-memory connection."""

    def __init__(self) -> None:
        self.messages: deque[T] = deque()
        self.closed = False
        self.reason = ""


class LocalConnection[Out: BaseModel, In: BaseModel](Connection[Out, In]):
    """One end of an in-memory connection, made by `local_pair`.

    Messages are handed over as objects, without serialization.
    """

    def __init__(self, outgoing: _Pipe[Out], incoming: _Pipe[In]) -> None:
        """Connect two pipes."""
        super().__init__()
        self._outgoing = outgoing
        self._incoming = incoming

    def send(self, message: Out) -> None:
        """Hand a message to the other end."""
        if not self.closed and not self._outgoing.closed:
            self._outgoing.messages.append(message)

    def receive(self) -> list[In]:
        """Take every message the other end sent.

        Returns:
            list[In]: The messages, oldest first.

        """
        messages = list(self._incoming.messages)
        self._incoming.messages.clear()
        if self._incoming.closed and not self.closed:
            super().close(self._incoming.reason or "Disconnected")
        return messages

    def close(self, reason: str = "") -> None:
        """Close both ends. The other end sees it after its messages."""
        self._outgoing.closed = True
        self._outgoing.reason = reason
        super().close(reason)


def local_pair[A: BaseModel, B: BaseModel]() -> tuple[
    LocalConnection[A, B], LocalConnection[B, A]
]:
    """Two connected ends: the first sends `A`, the second sends `B`.

    Returns:
        tuple: Both ends.

    """
    a_to_b: _Pipe[A] = _Pipe()
    b_to_a: _Pipe[B] = _Pipe()
    return LocalConnection(a_to_b, b_to_a), LocalConnection(b_to_a, a_to_b)


def configure_socket(sock: socket.socket) -> None:
    """Make a connected TCP socket non blocking and low latency."""
    sock.settimeout(0.0)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class SocketConnection[Out: BaseModel, In: BaseModel](Connection[Out, In]):
    """Length prefixed JSON frames over a connected TCP socket."""

    def __init__(
        self,
        sock: socket.socket,
        decode: Callable[[bytes], In],
        max_frame: int,
    ) -> None:
        """Take over a connected socket.

        Args:
            sock: The socket. It is made non blocking.
            decode: Parses one received frame.
            max_frame: Larger incoming frames are a protocol error.

        """
        super().__init__()
        configure_socket(sock)
        self._sock = sock
        self._decode = decode
        self._max_frame = max_frame
        self._input = bytearray()
        self._output = bytearray()
        try:
            peer = sock.getpeername()
            self._address = f"{peer[0]}:{peer[1]}"
        except OSError:
            self._address = "unknown"

    @property
    def address(self) -> str:
        """The peer's address and port."""
        return self._address

    @property
    def pending_output(self) -> int:
        """Bytes queued but not sent yet."""
        return len(self._output)

    def send(self, message: Out) -> None:
        """Queue a message and try to send it."""
        if self.closed:
            return
        data = encode(message)
        self._output += len(data).to_bytes(HEADER_SIZE, "big")
        self._output += data
        if len(self._output) > MAX_PENDING_OUTPUT:
            self._fail("Too slow to keep up")
            return
        self.flush()

    def flush(self) -> None:
        """Send as much queued data as the socket takes right now."""
        while self._output and not self.closed:
            try:
                sent = self._sock.send(self._output)
            except BlockingIOError:
                return
            except OSError as error:
                self._fail(f"Connection lost: {error.strerror or error}")
                return
            del self._output[:sent]

    def _read(self) -> str | None:
        """Read what arrived.

        Returns:
            str | None: Why the connection ended, `None` while it lasts.

        """
        while True:
            try:
                data = self._sock.recv(RECEIVE_SIZE)
            except BlockingIOError:
                return None
            except OSError as error:
                return f"Connection lost: {error.strerror or error}"
            if not data:
                return "Disconnected"
            self._input += data

    def receive(self) -> list[In]:
        """Read and parse every complete frame that arrived.

        Messages sent right before the peer hung up, like a goodbye, are
        still returned; the connection is closed after them.

        Returns:
            list[In]: The messages, oldest first.

        """
        if self.closed:
            return []
        ended = self._read()
        messages: list[In] = []
        buffer = self._input
        while len(buffer) >= HEADER_SIZE:
            size = int.from_bytes(buffer[:HEADER_SIZE], "big")
            if size > self._max_frame:
                self._fail("Message too large")
                break
            end = HEADER_SIZE + size
            if len(buffer) < end:
                break
            frame = bytes(buffer[HEADER_SIZE:end])
            del buffer[:end]
            try:
                messages.append(self._decode(frame))
            except ProtocolError as error:
                self._fail(str(error))
                break
        if ended is not None and not self.closed:
            self._fail(ended)
        return messages

    def _fail(self, reason: str) -> None:
        LOGGER.debug("Connection to %s closed: %s", self._address, reason)
        self._output.clear()
        self.close(reason)

    def close(self, reason: str = "") -> None:
        """Send what is queued (briefly waiting for it), then close."""
        if self._sock.fileno() == -1:
            super().close(reason)
            return
        if self._output:
            try:
                self._sock.settimeout(CLOSE_FLUSH_TIMEOUT)
                self._sock.sendall(self._output)
            except OSError:
                LOGGER.debug("Could not finish sending to %s", self._address)
            self._output.clear()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            LOGGER.debug("%s was already disconnected", self._address)
        self._sock.close()
        super().close(reason)


class Listener:
    """A listening TCP socket that accepts without blocking."""

    def __init__(self, host: str, port: int) -> None:
        """Listen on `host` and `port`. Port 0 picks a free one.

        An empty host listens on every interface, IPv4 and IPv6 if the
        system can. Raises `OSError` when the address is taken or
        invalid.

        """
        if not host and socket.has_dualstack_ipv6():
            self._sock = socket.create_server(
                ("::", port), family=socket.AF_INET6, dualstack_ipv6=True
            )
        else:
            self._sock = socket.create_server((host, port))
        self._sock.settimeout(0.0)
        self.port: int = self._sock.getsockname()[1]

    def accept(self) -> socket.socket | None:
        """Take one waiting connection.

        Returns:
            socket.socket | None: The connected socket, `None` if nobody
            is waiting.

        Raises:
            OSError: The listening socket broke.

        """
        try:
            sock, _ = self._sock.accept()
        except BlockingIOError:
            return None
        except OSError as error:
            if error.errno in {errno.ECONNABORTED, errno.EMFILE}:
                return None
            raise
        return sock

    def close(self) -> None:
        """Stop listening."""
        self._sock.close()
