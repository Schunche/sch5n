# Copyright (c) 2026 Schunche
"""Experimental software."""

import time

from zeroconf import (
    InterfaceChoice,
    IPVersion,
    ServiceBrowser,
    ServiceListener,
    Zeroconf,
)


class GameServerListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            port = info.port
            print(f"Server detected: {name} - on port: {port}")
            print("Available connection routes:")

            for ip in info.parsed_addresses(IPVersion.All):
                if ":" in ip:
                    print(f"\t[IPv6] -> [{ip}]:{port}")
                else:
                    print(f"\t[IPv4] -> {ip}:{port}")

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
