# Copyright (c) 2026 Schunche
"""Experimental software."""

import datetime as dt
import json
import logging
import pathlib
from typing import NotRequired, TypedDict, cast

import pygame

from sch5n.deprecated.loader import NAME_SPACE, SETTINGS, get_bit
from sch5n.math.vector import FloatTuple2, IntTuple2, deserialize_int_tuple_2

_logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

NEIGHBOR_OFFSETS: list[tuple[int, int]] = [
    (i, j) for j in range(-2, 3) for i in range(-2, 3)
]
PHYSICS_TILES: set[str] = set(NAME_SPACE["physics_tiles"])


def _generate_radom_map_name() -> str:
    return str(dt.datetime.now(dt.UTC).timestamp()).replace(".", "_")


class Tile(TypedDict):
    block: str
    variant: int
    durability: NotRequired[int]


class Tilemap:
    """A class representing a tilemap in a game.

    Attributes:
        assets (dict[str, dict[int, pygame.Surface]]): A dictionary mapping.
        tile_size (int): The size of each tile in pixels.
        tilemap (dict[IntTuple2, dict[str, str | int]]): A dictionary.

    """

    def __init__(
        self,
        assets: dict[str, dict[int, pygame.Surface]],
        map_name: str | None = None,
    ) -> None:
        """Initialize a Tilemap object.

        Args:
            assets (dict[str, dict[int, pygame.Surface]]): Dictionary mapping.

        """
        self.assets: dict[str, dict[int, pygame.Surface]] = assets
        self.map_name: str = (
            _generate_radom_map_name() if map_name is None else map_name
        )
        self.tilemap: dict[IntTuple2, Tile] = {}

        self.load_map(alias=self.map_name)

    def extract_any_variant(
        self, block: str, *, do_keep: bool
    ) -> list[tuple[IntTuple2, Tile]]:
        """Extract tiles matching specified block from the tilemap.

        Args:
            block (str): A string to match.
            do_keep (bool, optional): Whether to do_keep extracted tiles.

        Returns:
            list[tuple[tuple[int, int], Tile]]: A list of matched tiles.

        """
        matches: list[tuple[IntTuple2, Tile]] = []
        for location, tile in self.tilemap.copy().items():
            if tile["block"] == block:
                matches.append((
                    (
                        location[0] * SETTINGS.tile_size,
                        location[1] * SETTINGS.tile_size,
                    ),
                    tile.copy(),
                ))
                if not do_keep:
                    del self.tilemap[location]

        return matches

    def extract(
        self, id_pair: tuple[str, int], *, do_keep: bool
    ) -> list[tuple[tuple[int, int], Tile]]:
        """Extract tiles matching specified block from the tilemap.

        Args:
            id_pair (tuple[str | int]): A tuple containing block to match.
            do_keep (bool, optional): Whether to do_keep extracted tiles.

        Returns:
            list[tuple[tuple[int, int], Tile]]: A list of matched tiles.

        """
        matches: list[tuple[tuple[int, int], Tile]] = []
        for location, tile in self.tilemap.copy().items():
            if (tile["block"], tile["variant"]) == id_pair:
                matches.append((
                    (
                        location[0] * SETTINGS.tile_size,
                        location[1] * SETTINGS.tile_size,
                    ),
                    tile.copy(),
                ))
                if not do_keep:
                    del self.tilemap[location]

        return matches

    def insert_tile(self, pos: IntTuple2, tile: Tile) -> None:
        """Insert a tile into the tilemap.

        Args:
            pos (IntTuple2): The position to insert the tile.
            tile (Tile): The tile to place.

        """
        self.tilemap[pos] = tile

    def is_tile_at(self, pos: IntTuple2) -> bool:
        """Check if there is a tile at the specified position.

        Args:
            pos (IntTuple2): The position to check.

        Returns:
            bool: True if there is a tile at the position, False otherwise.

        """
        return pos in self.tilemap

    def delete_tile(self, pos: IntTuple2) -> None:
        """Delete a tile from the tilemap.

        Args:
            pos (IntTuple2): The position of the tile to delete.

        """
        del self.tilemap[pos]

    def load_map(self, alias: str) -> None:
        """Load a tilemap from a JSON file.

        Args:
            alias (str, optional): The alias of the tilemap to load.

        """
        str_keys_tilemap: dict[str, Tile] = {}

        try:
            with pathlib.Path(f"src/map/{alias}/tilemap.json").open(
                encoding="utf-8"
            ) as file:
                str_keys_tilemap = cast("dict[str, Tile]", json.load(file))
        except FileNotFoundError:
            _logger.critical("File '%s/tilemap.json' not found.", alias)
            return

        tuple_keys_tilemap: dict[IntTuple2, Tile] = {}
        for key, value in str_keys_tilemap.items():
            tuple_keys_tilemap[deserialize_int_tuple_2(key)] = value

        self.tilemap = tuple_keys_tilemap

        _logger.info("'%s' found and loaded as tilemap", alias)
        _logger.debug("'%s' currently has %s tiles", alias, len(self.tilemap))

    def save_map(self, alias: str = "map1") -> None:
        """Save the current tilemap to a JSON file.

        Args:
            alias (str, optional): The alias of the tilemap to save.

        """
        str_keys_tilemap: dict[str, Tile] = {
            f"{key[0]};{key[1]}": value for key, value in self.tilemap.items()
        }

        with pathlib.Path(f"src/map/{alias}/tilemap.json").open(
            mode="w", encoding="utf-8"
        ) as file:
            json.dump(str_keys_tilemap, file, indent=4)

        _logger.info("Tilemap saved to '%s/tilemap.json'", alias)

    def tiles_around(
        self, world_pos: FloatTuple2
    ) -> list[tuple[IntTuple2, Tile]]:
        """Get tiles around the specified position.

        Args:
            world_pos (FloatTuple2): The position to check.

        Returns:
            list[tuple[IntTuple2, Tile]]: A list of tiles.

        """
        tiles: list[tuple[IntTuple2, Tile]] = []
        tile_pos: IntTuple2 = (
            int(world_pos[0] // SETTINGS.tile_size),
            int(world_pos[1] // SETTINGS.tile_size),
        )
        for offset in NEIGHBOR_OFFSETS:
            check_location: IntTuple2 = (
                tile_pos[0] + offset[0],
                tile_pos[1] + offset[1],
            )
            if check_location in self.tilemap:
                tiles.append((check_location, self.tilemap[check_location]))
        return tiles

    def physics_rects_around(
        self, world_pos: IntTuple2
    ) -> list[pygame.rect.Rect]:
        """Get physics rectangles around the specified position.

        Args:
            world_pos (IntTuple2): The position to check.

        Returns:
            list[pygame.rect.Rect]: A list of physics rectangles.

        """
        return [
            pygame.Rect(
                tile[0][0] * SETTINGS.tile_size,
                tile[0][1] * SETTINGS.tile_size,
                SETTINGS.tile_size,
                SETTINGS.tile_size,
            )
            for tile in self.tiles_around((world_pos[0], world_pos[1]))
            if tile[1]["block"] in PHYSICS_TILES
        ]

    def render(
        self, surface: pygame.Surface, offset: IntTuple2 = (0, 0)
    ) -> None:
        """Render the tilemap on the given surface with an optional offset.

        Args:
            surface (pygame.Surface): The surface to render the tilemap on.
            offset (tuple[float], optional): Offset to apply on the tilemap.

        """
        for x in range(
            offset[0] // SETTINGS.tile_size - 1,
            (offset[0] + surface.width) // SETTINGS.tile_size + 1,
        ):
            for y in range(
                offset[1] // SETTINGS.tile_size - 1,
                (offset[1] + surface.get_height()) // SETTINGS.tile_size + 1,
            ):
                location: IntTuple2 = (x, y)
                if location in self.tilemap:
                    tile: Tile = self.tilemap[location]
                    world_pos: IntTuple2 = (
                        location[0] * SETTINGS.tile_size - offset[0],
                        location[1] * SETTINGS.tile_size - offset[1],
                    )

                    surface.blit(
                        self.assets["tile"][tile["block"]][tile["variant"]],
                        world_pos,
                    )

                    if "durability" in tile:
                        breakage_name = (
                            tile["block"]
                            if tile["block"]
                            in NAME_SPACE["durability_of_tile"]
                            else "_"
                        )
                        surface.blit(
                            self.assets["tileBreakage"][
                                int(
                                    (len(self.assets["tileBreakage"]) - 1)
                                    * (
                                        1
                                        - (
                                            tile["durability"]
                                            / NAME_SPACE["durability_of_tile"][
                                                breakage_name
                                            ]
                                        )
                                    )
                                )
                            ],
                            world_pos,
                        )

    def render_seek(
        self, surface: pygame.Surface, offset: FloatTuple2 = (0, 0)
    ) -> None:
        """Render the tilemap on the given surface with an optional offset.

        Args:
            surface (pygame.Surface): The surface to render the tilemap on.
            offset (FloatTuple2, optional) = (0, 0): The offset to apply.

        """
        for x in range(
            int(offset[0] // SETTINGS.tile_size - 1),
            int((offset[0] + surface.get_width()) // SETTINGS.tile_size + 1),
        ):
            for y in range(
                int(offset[1] // SETTINGS.tile_size - 1),
                int(
                    (offset[1] + surface.get_height()) // SETTINGS.tile_size
                    + 1
                ),
            ):
                location: IntTuple2 = (x, y)
                tile = self.tilemap.get(location)
                if tile is not None:
                    surface.blit(
                        self.assets["tile"][get_bit(tile["block"])],
                        (
                            location[0] * SETTINGS.tile_size - offset[0],
                            location[1] * SETTINGS.tile_size - offset[1],
                        ),
                    )

    def get_rects_on_window(
        self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)
    ) -> list[pygame.rect.Rect]:
        """Get the rects of tiles visible on the given surface window.

        Args:
            surface (pygame.Surface): The surface representing the window.
            offset (tuple[float], optional): The offset position.

        Returns:
            list[pygame.Rect]: A list of pygame.Rect.

        """
        rects: list[pygame.rect.Rect] = []
        for x in range(
            offset[0] // SETTINGS.tile_size - 1,
            (offset[0] + surface.get_width()) // SETTINGS.tile_size + 1,
        ):
            for y in range(
                offset[1] // SETTINGS.tile_size - 1,
                (offset[1] + surface.get_height()) // SETTINGS.tile_size + 1,
            ):
                location: tuple[int, int] = (x, y)
                if location in self.tilemap:
                    rects.append(
                        pygame.Rect(
                            x * SETTINGS.tile_size,
                            y * SETTINGS.tile_size,
                            SETTINGS.tile_size,
                            SETTINGS.tile_size,
                        )
                    )
        return rects

    def get_tile_at(self, pos: IntTuple2) -> Tile | None:
        """Get the tile at the specified position.

        Args:
            pos (IntTuple2): The position to check.

        Returns:
            Tile | None: The tile at the specified position.

        """
        if pos in self.tilemap:
            return self.tilemap[pos]

        return None

    def set_tile(self, pos: IntTuple2, tile: Tile) -> None:
        """Set the tile at the specified position to the given tile.

        Args:
            pos (IntTuple2): The position to set the tile at.
            tile (dict[str, str | int]): The tile to set.

        """
        self.tilemap[pos] = tile

    def break_tile(self, pos: IntTuple2) -> None:
        """Break the tile at the specified position.

        Args:
            pos (IntTuple2): The position to break.

        """
        tile = self.get_tile_at(pos)
        if tile is None:
            return
        if tile["block"] in NAME_SPACE["transformTile"]:
            self.set_tile(
                pos,
                {
                    "block": NAME_SPACE["transformTile"][tile["block"]],
                    "variant": tile["variant"],
                },
            )
        else:
            self.delete_tile(pos)

        # TODO: Spawn particles of the tile
