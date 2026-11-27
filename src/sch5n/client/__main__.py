# Copyright (c) 2026 Schunche
"""Client entry points: the game and the map tools."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from sch5n.game.config import GameMode
from sch5n.log.logger import init as init_logging
from sch5n.utility import path
from sch5n.world.io import DEFAULT_MAP, map_file
lazy from sch5n.client.app import App, Options
lazy from sch5n.client.scenes.map_tools import MapScene
lazy from sch5n.client.scenes.menu import MainMenu
lazy from sch5n.client.scenes.multiplayer import MultiplayerScene

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sch5n.client.scenes.base import Scene


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Options shared by every windowed program."""
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        help="quit after this many frames (for automated runs)",
    )
    parser.add_argument(
        "--hidden", action="store_true", help="do not show the window"
    )


def _init() -> None:
    init_logging(path.CONFIG_DIR / "logging.json")


def main(argv: Sequence[str] | None = None) -> None:
    """Play the game."""
    parser = argparse.ArgumentParser(prog="sch5n client")
    parser.add_argument(
        "--map", type=map_file, default=None, help="map name or file"
    )
    parser.add_argument(
        "--game-mode",
        type=GameMode,
        choices=list(GameMode),
        default=GameMode.SURVIVAL,
        help="admin allows unlimited jumps (default: survival)",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--connect",
        metavar="ADDRESS",
        default=None,
        help="join the server at ADDRESS (host or host:port) right away",
    )
    add_common_arguments(parser)
    args = parser.parse_args(argv)

    _init()
    App(
        Options(
            map_path=args.map,
            game_mode=args.game_mode,
            seed=args.seed,
            connect=args.connect,
            max_frames=args.frames,
            hidden=args.hidden,
        )
    ).run(first_scene)


def first_scene(app: App) -> Scene:
    """Pick the main menu, or the multiplayer screen to join right away.

    Returns:
        Scene: The scene to start with.

    """
    menu = MainMenu(app)
    if app.options.connect is None:
        return menu
    scene = MultiplayerScene(app, back=menu)
    scene.join(app.options.connect)
    return scene


def viewer_main(argv: Sequence[str] | None = None) -> None:
    """Look at a map, or edit it with `--edit`."""
    parser = argparse.ArgumentParser(
        prog="sch5n view",
        description="Look at a map. With --edit, change it: Escape saves.",
    )
    parser.add_argument(
        "--map",
        type=map_file,
        default=map_file(DEFAULT_MAP),
        help="map name or file; a new name starts an empty map",
    )
    parser.add_argument(
        "--edit", action="store_true", help="place and erase tiles"
    )
    add_common_arguments(parser)
    args = parser.parse_args(argv)

    _init()
    App(
        Options(map_path=args.map, max_frames=args.frames, hidden=args.hidden)
    ).run(lambda app: MapScene(app, args.map, editing=args.edit))


if __name__ == "__main__":
    main()
