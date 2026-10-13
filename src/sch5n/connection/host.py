# Copyright (c) 2026 Schunche
"""Experimental software."""

import json
import socket
import time

DISCOVERY_PORT = 37020
GAME_PORT = 27015

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

message = json.dumps({
    "name": "Schun's World",
    "port": GAME_PORT,
    "version": 1,
}).encode()

try:
    while True:
        sock.sendto(
            message,
            ("255.255.255.255", DISCOVERY_PORT),
        )
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    sock.close()
