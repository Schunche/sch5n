# Copyright (c) 2026 Schunche
"""Experimental software."""

import socket
import time

import psutil
from zeroconf import InterfaceChoice, IPVersion, ServiceInfo, Zeroconf

type IPv4Address = str
type IPv6Address = str


def get_all_lan_ips() -> tuple[list[IPv4Address], list[IPv4Address]]:
    """Scans all network interfaces and returns all valid IPv4 and IPv6 addresses."""
    ipv4_list = []
    ipv6_list = []

    for addresses in psutil.net_if_addrs().values():
        for addr in addresses:
            if addr.address.startswith("127.") or addr.address == "::1":
                continue

            if addr.family == socket.AF_INET:
                ipv4_list.append(addr.address)
            elif addr.family == socket.AF_INET6:
                clean_ip = addr.address.split("%")[0]
                if (
                    not clean_ip.startswith("ff")
                    and not clean_ip.startswith("fe80")
                    and clean_ip != "::"
                ):
                    ipv6_list.append(clean_ip)

    return ipv4_list, ipv6_list


def start_multi_interface_host():
    ipv4_ips, ipv6_ips = get_all_lan_ips()

    if not ipv4_ips and not ipv6_ips:
        print("[ERROR] No active network interfaces found!")
        return

    game_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    game_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    game_socket.bind(("::", 0))

    assigned_port = game_socket.getsockname()[1]
    print(
        f"[HOST] Game socket listening on dynamically assigned port: {assigned_port}"
    )

    addresses_bytes = []
    print("[HOST] Registering service on the following local paths:")

    for ip in ipv4_ips:
        print(f" -> IPv4: {ip}")
        addresses_bytes.append(socket.inet_aton(ip))

    for ip in ipv6_ips:
        print(f" -> IPv6: {ip}")
        try:
            addresses_bytes.append(socket.inet_pton(socket.AF_INET6, ip))
        except Exception:
            continue

    service_type = "_pythonlan._tcp.local."

    instance_name = f"Multi-Interface Lobby.{service_type}"

    info = ServiceInfo(
        type_=service_type,
        name=instance_name,
        addresses=addresses_bytes,
        port=assigned_port,
        properties={b"multi_iface": b"true"},
    )

    zc = Zeroconf(ip_version=IPVersion.All, interfaces=InterfaceChoice.All)
    zc.register_service(info)

    print(
        "[HOST] mDNS server broadcasting across all interfaces... Press Ctrl+C to stop."
    )

    try:
        game_socket.listen(5)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[HOST] Shutting down...")
    finally:
        zc.unregister_service(info)
        zc.close()
        game_socket.close()


if __name__ == "__main__":
    start_multi_interface_host()
