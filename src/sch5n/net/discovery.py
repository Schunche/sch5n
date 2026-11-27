# Copyright (c) 2026 Schunche
"""Finding games on the local network with multicast DNS (zeroconf).

Servers open to the network announce themselves; the multiplayer screen
browses for them. Both are best effort: networks that block multicast
just show no games, and players type the address instead.
"""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, override

import psutil
from zeroconf import (
    Error as ZeroconfError,
)
from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceInfo,
    ServiceListener,
    Zeroconf,
)

from sch5n.log.logger import LOGGER
from sch5n.net.protocol import PROTOCOL_VERSION

if TYPE_CHECKING:
    from collections.abc import Callable

SERVICE_TYPE = "_sch5n._tcp.local."
RESOLVE_TIMEOUT_MS = 3000
_SERVICE_NAME_LIMIT = 60
"""mDNS instance names may be 63 bytes long."""


def lan_addresses() -> list[str]:
    """IPv4 addresses of this computer on its networks, loopback excluded.

    Returns:
        list[str]: Addresses, like `"192.168.1.20"`.

    """
    return [
        address.address
        for address in chain.from_iterable(psutil.net_if_addrs().values())
        if address.family == socket.AF_INET
        and not address.address.startswith(("127.", "169.254."))
    ]


@dataclass(frozen=True, slots=True)
class LanGame:
    """A game announced on the local network."""

    name: str
    host: str
    port: int

    @property
    def address(self) -> str:
        """`host:port`, as typed to join."""
        return f"{self.host}:{self.port}"


def _in_background(task: Callable[[], None], name: str) -> None:
    threading.Thread(target=task, name=name, daemon=True).start()


class Announcer:
    """Announces a server on the local network until closed."""

    def __init__(self, name: str, port: int) -> None:
        """Start announcing in the background.

        Args:
            name: Server name shown to players.
            port: TCP port the server listens on.

        """
        self.name = name
        self.port = port
        self._lock = threading.Lock()
        self._zeroconf: Zeroconf | None = None
        self._info: ServiceInfo | None = None
        self._closed = False
        _in_background(self._register, "sch5n-announce")

    def _register(self) -> None:
        addresses = lan_addresses()
        if not addresses:
            LOGGER.info("No network to announce the game on")
            return
        label = "".join(c for c in self.name if c.isprintable() and c != ".")
        info = ServiceInfo(
            SERVICE_TYPE,
            f"{label[:_SERVICE_NAME_LIMIT] or "sch5n"}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(a) for a in addresses],
            port=self.port,
            properties={
                "name": self.name,
                "protocol": str(PROTOCOL_VERSION),
            },
        )
        try:
            zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            zeroconf.register_service(info, allow_name_change=True)
        except (OSError, ZeroconfError) as error:
            LOGGER.warning("Could not announce the game: %s", error)
            return
        with self._lock:
            if self._closed:
                zeroconf.close()
                return
            self._zeroconf, self._info = zeroconf, info
        LOGGER.info("Announcing %r on %s", self.name, ", ".join(addresses))

    def close(self) -> None:
        """Stop announcing."""
        with self._lock:
            self._closed = True
            zeroconf, info = self._zeroconf, self._info
            self._zeroconf = None
        if zeroconf is None or info is None:
            return
        try:
            zeroconf.unregister_service(info)
        except (OSError, ZeroconfError) as error:
            LOGGER.debug("Could not withdraw the announcement: %s", error)
        zeroconf.close()


class _Listener(ServiceListener):
    """Resolves announced services into `LanGame`s."""

    def __init__(self, browser: Browser) -> None:
        self.browser = browser

    def _resolve(self, zc: Zeroconf, type_: str, name: str) -> None:
        def resolve() -> None:
            info = ServiceInfo(type_, name)
            if not info.request(zc, RESOLVE_TIMEOUT_MS):
                return
            addresses = info.parsed_addresses(IPVersion.V4Only)
            if not addresses or info.port is None:
                return
            properties = info.decoded_properties
            if properties.get("protocol") != str(PROTOCOL_VERSION):
                return
            title = properties.get("name") or name.removesuffix(
                f".{SERVICE_TYPE}"
            )
            self.browser.found(name, LanGame(title, addresses[0], info.port))

        _in_background(resolve, "sch5n-resolve")

    @override
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._resolve(zc, type_, name)

    @override
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._resolve(zc, type_, name)

    @override
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.browser.lost(name)


class Browser:
    """Collects the games announced on the local network until closed."""

    def __init__(self) -> None:
        """Start browsing in the background."""
        self._lock = threading.Lock()
        self._games: dict[str, LanGame] = {}
        self._zeroconf: Zeroconf | None = None
        self._closed = False
        _in_background(self._start, "sch5n-browse")

    def _start(self) -> None:
        try:
            zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
            ServiceBrowser(zeroconf, SERVICE_TYPE, _Listener(self))
        except (OSError, ZeroconfError) as error:
            LOGGER.warning("Could not look for games: %s", error)
            return
        with self._lock:
            if self._closed:
                zeroconf.close()
                return
            self._zeroconf = zeroconf

    def found(self, key: str, game: LanGame) -> None:
        """Remember an announced game."""
        with self._lock:
            self._games[key] = game

    def lost(self, key: str) -> None:
        """Forget a game that is no longer announced."""
        with self._lock:
            self._games.pop(key, None)

    @property
    def games(self) -> list[LanGame]:
        """Games found so far, by name."""
        with self._lock:
            return sorted(self._games.values(), key=lambda g: g.name)

    def close(self) -> None:
        """Stop browsing."""
        with self._lock:
            self._closed = True
            zeroconf = self._zeroconf
            self._zeroconf = None
        if zeroconf is not None:
            zeroconf.close()
