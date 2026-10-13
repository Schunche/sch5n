# Copyright (c) 2026 Schunche
"""Experimental software."""

import json
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("", 0))
sock.settimeout(5)

servers = set()

try:
    while True:
        data, address = sock.recvfrom(4096)
        if address not in servers:
            servers.add(address)
        try:
            server = json.loads(data.decode())
        except UnicodeDecodeError, json.JSONDecodeError:
            continue

        print(
            f"Found {server["name"]} "
            f"at {address[0]}:{server["port"]} version: {server["version"]}"
        )
        print(servers)
except TimeoutError:
    print("No more servers found.")
finally:
    sock.close()
