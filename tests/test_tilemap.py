# Copyright (c) 2026 Schunche
"""Chunked tile storage."""

import numpy as np

from sch5n.game.content import AIR
from sch5n.world.tilemap import CHUNK_SIZE, TileMap


def test_set_get_including_negative_coordinates(tilemap: TileMap) -> None:
    """Tiles can be stored anywhere, also at negative coordinates."""
    stone = tilemap.blocks.id_of("stone")
    positions = [(0, 0), (-1, -1), (CHUNK_SIZE, 3), (-CHUNK_SIZE - 5, 70)]
    for x, y in positions:
        tilemap.set(x, y, stone, 0)
        assert tilemap.get(x, y) == stone
        assert tilemap.is_solid(x, y)
    assert len(tilemap) == len(positions)
    assert tilemap.get(1, 0) == AIR


def test_empty_chunks_are_dropped(tilemap: TileMap) -> None:
    """Chunks without tiles are freed."""
    tilemap.set(3, 3, 1)
    assert len(tilemap.chunks) == 1
    tilemap.set(3, 3, AIR)
    assert not tilemap.chunks
    tilemap.set(5, 5, AIR)  # Setting air in nowhere creates nothing.
    assert not tilemap.chunks


def test_revision_changes_on_write(tilemap: TileMap) -> None:
    """Writing to a chunk bumps its revision."""
    tilemap.set(0, 0, 1)
    chunk = tilemap.chunks[0, 0]
    before = chunk.revision
    tilemap.set(1, 0, 1)
    assert chunk.revision > before


def test_set_clears_damage(tilemap: TileMap) -> None:
    """Replacing a block forgets its damage."""
    tilemap.set(0, 0, 1)
    tilemap.damage[0, 0] = 5
    tilemap.set(0, 0, 2)
    assert (0, 0) not in tilemap.damage


def test_region_spans_chunks(tilemap: TileMap) -> None:
    """Regions are assembled across chunk borders."""
    first, second = 1, 2
    tilemap.set(-1, -1, first)
    tilemap.set(CHUNK_SIZE, 0, second)
    region = tilemap.region(-2, -2, CHUNK_SIZE + 1, 1)
    assert region.shape == (3, CHUNK_SIZE + 3)
    assert region[1, 1] == first
    assert region[2, CHUNK_SIZE + 2] == second
    assert int(np.count_nonzero(region)) == len((first, second))


def test_bounds_and_surface(tilemap: TileMap) -> None:
    """Bounds cover every tile; the surface is the top solid tile."""
    assert tilemap.bounds() is None
    tilemap.set(2, 10, tilemap.blocks.id_of("log"))  # Not solid.
    ground = 12
    tilemap.set(2, ground, tilemap.blocks.id_of("stone"))
    tilemap.set(-3, 40, tilemap.blocks.id_of("stone"))
    assert tilemap.bounds() == (-3, 10, 3, 41)
    assert tilemap.surface_y(2, 0, 100) == ground
    assert tilemap.surface_y(7, 0, 100) is None


def test_iter_tiles(tilemap: TileMap) -> None:
    """Iteration yields every tile with its coordinates."""
    tilemap.set(-40, 7, 3, 0)
    tilemap.set(1, 2, 1, 0)
    assert sorted(tilemap.iter_tiles()) == [(-40, 7, 3, 0), (1, 2, 1, 0)]
