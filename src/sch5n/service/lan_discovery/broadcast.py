# Copyright (c) 2026 Schunche
"""Experimental software."""

import socket
import time
lazy from itertools import chain

lazy import psutil
lazy from zeroconf import InterfaceChoice, IPVersion, ServiceInfo, Zeroconf

lazy from sch5n.log.logger import LOGGER

type IPv4AddressBytes = bytes
type IPv6AddressBytes = bytes

type IPv4AddressStr = str
type IPv6AddressStr = str

type IPv4Address = IPv4AddressBytes | IPv4AddressStr
type IPv6Address = IPv6AddressBytes | IPv6AddressStr


def get_all_lan_ips() -> tuple[list[IPv4AddressStr], list[IPv6AddressStr]]:
    """Scan all network interfaces and returns valid IPv4 and IPv6 addresses.

    Returns:
        tuple[list[IPv4Address], list[IPv6Address]]: Addresses.

    """
    ipv4_list: list[IPv4AddressStr] = []
    ipv6_list: list[IPv6AddressStr] = []

    for addr in chain.from_iterable(psutil.net_if_addrs().values()):
        if addr.address.startswith("127.") or addr.address == "::1":
            continue

        if addr.family == socket.AF_INET:
            ipv4_list.append(addr.address)
        elif addr.family == socket.AF_INET6:
            ip = addr.address.split("%")[0]
            if all((
                not ip.startswith("ff"),
                not ip.startswith("fe80"),
                ip != "::",
            )):
                ipv6_list.append(ip)

    return ipv4_list, ipv6_list


def _main() -> None:
    ipv4_ips, ipv6_ips = get_all_lan_ips()

    if not ipv4_ips and not ipv6_ips:
        LOGGER.error("[HOST][ERROR] No active network interfaces found!")
        return

    game_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    game_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    game_socket.bind(("::", 0))

    port = game_socket.getsockname()[1]
    LOGGER.info(
        "[HOST] Game socket listening on dynamically assigned port: %s", port
    )

    addresses_bytes: list[IPv4AddressBytes | IPv6AddressBytes] = []
    LOGGER.info("[HOST] Registering service on the following local paths:")

    for ip in ipv4_ips:
        LOGGER.info(" -> IPv4: %s", ip)
        addresses_bytes.append(socket.inet_aton(ip))

    for ip in ipv6_ips:
        LOGGER.info(" -> IPv6: %s", ip)
        addresses_bytes.append(socket.inet_pton(socket.AF_INET6, ip))

    service_type = "_pythonlan._tcp.local."

    instance_name = f"Multi-Interface Lobby.{service_type}"

    info = ServiceInfo(
        type_=service_type,
        name=instance_name,
        addresses=addresses_bytes,
        port=port,
        properties={b"multi_iface": b"true"},
    )

    zc = Zeroconf(ip_version=IPVersion.All, interfaces=InterfaceChoice.All)
    zc.register_service(info)

    LOGGER.info("[HOST] mDNS server broadcasting across all interfaces...")
    LOGGER.info("[HOST] Press Ctrl+C to stop...")

    try:
        game_socket.listen(5)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("\n[HOST] Shutting down...")
    finally:
        zc.unregister_service(info)
        zc.close()
        game_socket.close()


if __name__ == "__main__":
    _main()
