# Copyright (c) 2026 Schunche
"""Experimental software."""

import socket
import time

from zeroconf import (
    InterfaceChoice,
    IPVersion,
    ServiceBrowser,
    ServiceListener,
    Zeroconf,
)

IPV4_BYTE_COUNT = 4
IPV6_BYTE_COUNT = 16


class GameServerListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            port = info.port
            print(f" SERVER DETECTED: {name}")
            print(f"\tPort: {port}")
            print("\tAvailable connection routes:")

            for addr_bytes in info.addresses:
                if len(addr_bytes) == IPV4_BYTE_COUNT:
                    ip = socket.inet_ntoa(addr_bytes)
                    print(f"\t\t[IPv4] -> {ip}:{port}")
                elif len(addr_bytes) == IPV6_BYTE_COUNT:
                    ip = socket.inet_ntop(socket.AF_INET6, addr_bytes)
                    print(f"\t\t[IPv6] -> [{ip}]:{port}")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"\n[CLIENT] Server left network: {name}")


def discover_servers():
    zc = Zeroconf(ip_version=IPVersion.All, interfaces=InterfaceChoice.All)
    listener = GameServerListener()

    print(
        "[CLIENT] Scanning all interfaces for multi-route servers... Press Ctrl+C."
    )
    browser = ServiceBrowser(zc, "_pythonlan._tcp.local.", listener)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[CLIENT] Scan stopped.")
    finally:
        zc.close()


if __name__ == "__main__":
    discover_servers()
