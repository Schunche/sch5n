# Copyright (c) 2026 Schunche
"""Collision of moving boxes with tiles."""

import pytest

from sch5n.game.physics import Body, approach, move_and_collide
from tests.conftest import floor
lazy from sch5n.world.tilemap import TileMap

TS = 32


def test_lands_on_floor(tilemap: TileMap) -> None:
    """Falling onto the floor stops exactly on top of it."""
    floor(tilemap, 5)
    body = Body(0, 5 * TS - 48 - 3, 48, 48)
    hits = move_and_collide(body, 0, 4, tilemap, TS)
    assert hits.down
    assert body.y == 5 * TS - 48


def test_falls_freely_without_tiles(tilemap: TileMap) -> None:
    """Nothing stops a body in empty space."""
    body = Body(0, 0, 10, 10)
    assert not move_and_collide(body, 3, 4, tilemap, TS).vertical
    assert (body.x, body.y) == (3, 4)


@pytest.mark.parametrize(
    ("dx", "x", "side"), [(8, 2 * TS - 20, "right"), (-8, TS, "left")]
)
def test_walls_stop_movement(
    tilemap: TileMap, dx: float, x: float, side: str
) -> None:
    """Moving into a wall stops at its face."""
    stone = tilemap.blocks.id_of("stone")
    tilemap.set(0, 0, stone)
    tilemap.set(2, 0, stone)
    body = Body(TS + 6, 4, 20, 20)
    hits = move_and_collide(body, dx, 0, tilemap, TS)
    assert getattr(hits, side)
    assert body.x == x


def test_ceiling(tilemap: TileMap) -> None:
    """Moving up into a ceiling stops below it."""
    floor(tilemap, 0)
    body = Body(0, TS + 1, 10, 10)
    assert move_and_collide(body, 0, -3, tilemap, TS).up
    assert body.y == TS


def test_non_solid_tiles_are_ignored(tilemap: TileMap) -> None:
    """Bodies pass through non solid blocks."""
    tilemap.set(0, 1, tilemap.blocks.id_of("log"))
    body = Body(0, TS - 10, 10, 10)
    assert not move_and_collide(body, 0, 4, tilemap, TS).down


def test_sliding_along_floor_is_not_blocked(tilemap: TileMap) -> None:
    """Touching the floor does not block horizontal movement."""
    floor(tilemap, 1)
    body = Body(0, 0, 32, 32)
    step = 5
    hits = move_and_collide(body, step, 0, tilemap, TS)
    assert not hits.horizontal
    assert body.x == step


def test_approach() -> None:
    """Approaching a target never overshoots."""
    assert approach(1.0, 0.0, 0.3) == pytest.approx(0.7)
    assert approach(-0.1, 0.0, 0.3) == pytest.approx(0.0)
