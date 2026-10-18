# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
from typing import override
lazy import time
lazy from threading import Thread

from zeroconf import (
    InterfaceChoice,
    IPVersion,
    ServiceBrowser,
    ServiceListener,
    Zeroconf,
)

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class GameServerListener(ServiceListener):
    """Custom sevice listener."""

    @override
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            port = info.port
            _logger.info("Server detected: %s - on port: %s", name, port)
            _logger.info("Available connection routes:")

            for ip in info.parsed_addresses(IPVersion.All):
                if ":" in ip:
                    _logger.info("\t[IPv6] -> [%s]:%s", ip, port)
                else:
                    _logger.info("\t[IPv4] -> [%s]:%s", ip, port)

    @override
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    @override
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        _logger.info("\n[CLIENT] Server left network: %s", name)


def _main() -> None:
    zc = Zeroconf(ip_version=IPVersion.All, interfaces=InterfaceChoice.All)
    listener = GameServerListener()

    _logger.info("[CLIENT] Scanning all interfaces for multi-route servers...")
    _logger.info("[CLIENT] Press Ctrl+C to stop...")

    _browser: Thread = ServiceBrowser(zc, "_pythonlan._tcp.local.", listener)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _logger.info("\n[CLIENT] Scan stopped.")
    finally:
        zc.close()


if __name__ == "__main__":
    _main()
