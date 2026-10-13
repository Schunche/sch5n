import socket
import time

import psutil
from zeroconf import IPVersion, ServiceInfo, Zeroconf


def get_all_lan_ips():
    """Scans all network interfaces and returns all valid IPv4 and IPv6 addresses."""
    ipv4_list = []
    ipv6_list = []

    # Iterate through all network interfaces (physical and virtual)
    for interface_name, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            # Skip loopback interfaces (localhost)
            if addr.address.startswith("127.") or addr.address == "::1":
                continue

            if addr.family == socket.AF_INET:  # IPv4
                ipv4_list.append(addr.address)
            elif addr.family == socket.AF_INET6:  # IPv6
                clean_ip = addr.address.split("%")[0]
                # Skip loopback (::1), multicast (ff), and link-local (fe80)
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

    # 1. Create a dual-stack socket that binds globally to ALL interfaces
    game_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    game_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    game_socket.bind(("::", 0))  # Port 0 picks a random open port globally

    assigned_port = game_socket.getsockname()[1]
    print(
        f"[HOST] Game socket listening on dynamically assigned port: {assigned_port}"
    )

    # 2. Pack every single discovered IP into the mDNS payload
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

    service_type = "_pythonlan._udp.local."

    instance_name = f"Multi-Interface Lobby.{service_type}"

    info = ServiceInfo(
        type_=service_type,
        name=instance_name,
        addresses=addresses_bytes,  # Array containing ALL of your interface IPs
        port=assigned_port,
        properties={b"multi_iface": b"true"},
    )

    # 3. Passing interfaces=None tells Zeroconf to listen & broadcast on ALL interfaces
    zc = Zeroconf(ip_version=IPVersion.All, interfaces=None)
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
