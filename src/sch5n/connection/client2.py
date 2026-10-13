import socket
import time

from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf


class GameServerListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            port = info.port
            print("\n=========================================")
            print(f" SERVER DETECTED: {name}")
            print(f" Dynamic Port: {port}")
            print(" Available connection routes:")

            for addr_bytes in info.addresses:
                if len(addr_bytes) == 4:
                    ip = socket.inet_ntoa(addr_bytes)
                    print(f"  [IPv4 Route] -> {ip}:{port}")
                elif len(addr_bytes) == 16:
                    ip = socket.inet_ntop(socket.AF_INET6, addr_bytes)
                    print(f"  [IPv6 Route] -> [{ip}]:{port}")
            print("=========================================")

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"\n[CLIENT] Server left network: {name}")


def discover_servers():
    # Setting interfaces=None here means the client scans for hosts on ALL of its network cards too
    zc = Zeroconf(ip_version=IPVersion.All, interfaces=None)
    listener = GameServerListener()

    print(
        "[CLIENT] Scanning all interfaces for multi-route servers... Press Ctrl+C."
    )
    browser = ServiceBrowser(zc, "_pythonlan._udp.local.", listener)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[CLIENT] Scan stopped.")
    finally:
        zc.close()


if __name__ == "__main__":
    discover_servers()
