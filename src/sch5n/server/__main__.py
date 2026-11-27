# Copyright (c) 2026 Schunche
"""The dedicated server: `sch5n server`. Runs without a window."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from sch5n.error.exceptions import ParseError
from sch5n.game.config import GameMode
from sch5n.game.content import Content
from sch5n.game.session import GameSetup
from sch5n.log.logger import LOGGER
from sch5n.log.logger import init as init_logging
from sch5n.net.connection import finish_closing
from sch5n.net.protocol import DEFAULT_PORT
from sch5n.server.server import Server
from sch5n.utility import path
from sch5n.world.io import DEFAULT_MAP, load_tilemap, map_file
from sch5n.world.save import World, load_world, user_worlds_dir, world_path

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_CATCH_UP_TICKS = 5
"""Ticks skipped instead of run late after a stall, like a slow disk."""


def parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Read the command line.

    Returns:
        argparse.Namespace: The options.

    """
    parser = argparse.ArgumentParser(
        prog="sch5n server",
        description="Run a game that players join over the network.",
    )
    parser.add_argument(
        "--host",
        default="",
        help="address to listen on (default: every interface)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port (default: {DEFAULT_PORT}, 0 picks a free one)",
    )
    parser.add_argument(
        "--name",
        default="sch5n server",
        help="shown to players; the world is saved under this name",
    )
    parser.add_argument(
        "--map",
        type=map_file,
        default=map_file(DEFAULT_MAP),
        help="map name or file a new world starts from",
    )
    parser.add_argument(
        "--worlds-dir",
        type=Path,
        default=None,
        help="where worlds are saved (default: your user data directory)",
    )
    parser.add_argument(
        "--game-mode",
        type=GameMode,
        choices=list(GameMode),
        default=GameMode.SURVIVAL,
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--no-lan",
        action="store_true",
        help="do not announce the game on the local network",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=None,
        help="stop after this many ticks (for automated runs)",
    )
    return parser.parse_args(argv)


def run(server: Server, tick_rate: int, ticks: int | None = None) -> None:
    """Step the server at `tick_rate` until interrupted or `ticks` ran."""
    period = 1.0 / tick_rate
    deadline = time.perf_counter()
    done = 0
    while ticks is None or done < ticks:
        server.step()
        done += 1
        deadline += period
        now = time.perf_counter()
        if now - deadline > period * MAX_CATCH_UP_TICKS:
            deadline = now
        elif deadline > now:
            time.sleep(deadline - now)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the dedicated server until Ctrl+C."""
    args = parse_arguments(argv)
    init_logging()
    console = logging.getHandlerByName("stderr")
    if console is not None:
        console.setLevel(logging.INFO)

    content = Content.load(path.DATA_DIR)
    save_path = world_path(args.worlds_dir or user_worlds_dir(), args.name)
    if save_path.exists():
        try:
            world = load_world(save_path, content)
        except ParseError as error:
            LOGGER.error("%s", error)
            sys.exit(1)
        LOGGER.info("Continuing the world saved in %s", save_path)
    else:
        world = World(args.name, load_tilemap(args.map, content.blocks), {})
        LOGGER.info("New world from %s", args.map.stem)
    server = Server(
        content,
        world.tilemap,
        GameSetup(mode=args.game_mode, seed=args.seed),
        name=args.name,
        inventories=world.inventories,
    )
    try:
        port = server.listen(args.host, args.port, announce=not args.no_lan)
    except OSError as error:
        LOGGER.error("Cannot listen on port %s: %s", args.port, error)
        sys.exit(1)
    LOGGER.info(
        "Players join with this computer's address and port %s. Press"
        " Ctrl+C to stop and save.",
        port,
    )
    try:
        run(server, content.game.tick_rate, args.ticks)
    except KeyboardInterrupt:
        # Shutting down takes a moment; another Ctrl+C must not cut it.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        LOGGER.info("Stopping")
    finally:
        server.close()
        finish_closing()
        server.save(save_path)
    LOGGER.info("Stopped")


if __name__ == "__main__":
    main()
