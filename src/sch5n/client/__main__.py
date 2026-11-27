# Copyright (c) 2026 Schunche
"""Client entry points: the game and the map tools."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from sch5n.game.config import GameMode
from sch5n.log.logger import init as init_logging
from sch5n.utility import path
lazy from sch5n.client.app import App, Options
lazy from sch5n.client.scenes.map_tools import EditorScene, ViewerScene
lazy from sch5n.client.scenes.menu import MainMenu

if TYPE_CHECKING:
    from collections.abc import Sequence


def map_file(name: str) -> Path:
    """Resolve a map argument: a path, or the name of a bundled map.

    Returns:
        Path: The map file.

    """
    candidate = Path(name)
    if candidate.suffix == ".json" or candidate.exists():
        return candidate
    return path.MAPS_DIR / f"{name}.json"


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
    add_common_arguments(parser)
    args = parser.parse_args(argv)

    _init()
    App(
        Options(
            map_path=args.map,
            game_mode=args.game_mode,
            seed=args.seed,
            max_frames=args.frames,
            hidden=args.hidden,
        )
    ).run(MainMenu)


def _tool_main(
    prog: str,
    scene: type[ViewerScene],
    argv: Sequence[str] | None,
) -> None:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument(
        "map", type=map_file, nargs="?", default=map_file("map1")
    )
    add_common_arguments(parser)
    args = parser.parse_args(argv)

    _init()
    App(
        Options(map_path=args.map, max_frames=args.frames, hidden=args.hidden)
    ).run(lambda app: scene(app, args.map))


def editor_main(argv: Sequence[str] | None = None) -> None:
    """Edit a map."""
    _tool_main("sch5n edit", EditorScene, argv)


def viewer_main(argv: Sequence[str] | None = None) -> None:
    """Look at a map."""
    _tool_main("sch5n view", ViewerScene, argv)


if __name__ == "__main__":
    main()
