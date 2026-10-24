# Copyright (c) 2026 Schunche
"""Experimental software."""

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

lazy from sch5n.log.logger import LOGGER


class GameServerListener(ServiceListener):
    """Custom sevice listener."""

    @override
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            port = info.port
            LOGGER.info("Server detected: %s - on port: %s", name, port)
            LOGGER.info("Available connection routes:")

            for ip in info.parsed_addresses(IPVersion.All):
                if ":" in ip:
                    LOGGER.info("\t[IPv6] -> [%s]:%s", ip, port)
                else:
                    LOGGER.info("\t[IPv4] -> [%s]:%s", ip, port)

    @override
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    @override
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        LOGGER.info("\n[CLIENT] Server left network: %s", name)


def _main() -> None:
    zc = Zeroconf(ip_version=IPVersion.All, interfaces=InterfaceChoice.All)
    listener = GameServerListener()

    LOGGER.info("[CLIENT] Scanning all interfaces for multi-route servers...")
    LOGGER.info("[CLIENT] Press Ctrl+C to stop...")

    _browser: Thread = ServiceBrowser(zc, "_pythonlan._tcp.local.", listener)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("\n[CLIENT] Scan stopped.")
    finally:
        zc.close()


if __name__ == "__main__":
    _main()
