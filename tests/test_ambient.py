# Copyright (c) 2026 Schunche
"""Wind, clouds and wind streaks."""

from __future__ import annotations

import numpy as np
import pytest

from sch5n.client.render.atlas import Region
from sch5n.client.world_view import cloud_image, cloud_scale, place_cloud
from sch5n.game.ambient import Ambience, Cloud, Wind
from sch5n.game.config import WindConfig
from sch5n.math.rect import Rect
from sch5n.world.tilemap import TileMap
lazy from sch5n.game.content import Content

TILE = 32
TICKS = 3000
SCREEN = (1280.0, 720.0)
VIEW = Rect(0, 0, *SCREEN)
STRONG = 1.4


def strong_wind(ambience: Ambience, strength: float = STRONG) -> None:
    """Make the wind blow steadily at `strength`."""
    wind = ambience.wind
    wind.prevailing = wind.strength = wind.target = strength
    wind.config = WindConfig(gust_strength=0.0)


def run(ambience: Ambience, tilemap: TileMap, ticks: int) -> None:
    """Advance the ambience with the whole screen in view."""
    for _ in range(ticks):
        ambience.tick(tilemap, VIEW, TILE)


def test_wind_gusts_are_smooth_bounded_and_seeded() -> None:
    """The wind changes in small steps, within limits, the same per seed."""
    config = WindConfig()

    def history(seed: int) -> list[float]:
        wind = Wind(config, np.random.default_rng(seed))
        values = []
        for _ in range(TICKS):
            wind.tick()
            values.append(wind.strength)
        return values

    values = history(3)
    assert values == history(3)
    assert values != history(4)
    steps = np.abs(np.diff(values))
    assert steps.max() <= config.change_rate + 1e-9
    assert max(abs(v) for v in values) <= config.max
    assert max(values) - min(values) > config.change_rate * 100


def test_streaks_need_wind(content: Content) -> None:
    """Calm air has no streaks; in a strong wind they blow along with it."""
    tilemap = TileMap(content.blocks)
    calm = Ambience(content.game, np.random.default_rng(1))
    strong_wind(calm, 0.0)
    run(calm, tilemap, 200)
    assert not calm.streaks

    windy = Ambience(content.game, np.random.default_rng(1))
    strong_wind(windy, -STRONG)
    run(windy, tilemap, 200)
    assert windy.streaks
    assert all(streak.vx < 0 for streak in windy.streaks)
    assert all(0 <= s.opacity <= 1 for s in windy.streaks)


def test_streaks_never_start_inside_blocks(content: Content) -> None:
    """Wind does not blow through solid ground."""
    tilemap = TileMap(content.blocks)
    stone = content.blocks.id_of("stone")
    for x in range(40):
        for y in range(23):
            tilemap.set(x, y, stone)
    ambience = Ambience(content.game, np.random.default_rng(2))
    strong_wind(ambience)
    run(ambience, tilemap, 300)
    assert not ambience.streaks


def test_leaves_turn_with_the_wind(content: Content) -> None:
    """Falling leaves are pushed by the current wind, not only at spawn."""
    tilemap = TileMap(content.blocks)
    leaf = content.blocks.id_of("oak_leaf")
    for x in range(10):
        tilemap.set(x, 5, leaf)
    ambience = Ambience(content.game, np.random.default_rng(5))
    strong_wind(ambience)
    run(ambience, tilemap, 400)
    assert ambience.particles
    strong_wind(ambience, -STRONG)
    ambience.particles = ambience.particles[:20]
    for _ in range(300):
        ambience.tick(tilemap, None, TILE)
    assert all(p.vx < 0 for p in ambience.particles)


def test_clouds_drift_with_the_wind(content: Content) -> None:
    """Clouds move downwind; far clouds are drawn first."""
    ambience = Ambience(content.game, np.random.default_rng(6))
    strong_wind(ambience)
    before = [cloud.x for cloud in ambience.clouds]
    for _ in range(100):
        ambience.tick(TileMap(content.blocks), None, TILE)
    moved = [c.x - b for c, b in zip(ambience.clouds, before, strict=True)]
    assert all(m > 0 for m in moved)
    low, high = content.game.clouds.altitude
    assert all(low <= c.altitude <= high for c in ambience.clouds)
    depths = [c.depth for c in ambience.clouds]
    assert depths == sorted(depths)


def make_cloud(depth: float, altitude: float = 100.0) -> Cloud:
    """Create a cloud at a depth.

    Returns:
        Cloud: The cloud.

    """
    return Cloud(x=500, altitude=altitude, depth=depth, speed=0, size=0.5)


IMAGE = Region(0, 0, 1, 1, 40, 12)


def test_clouds_stay_above_the_horizon() -> None:
    """Clouds sit above the horizon and vanish when looking underground."""
    horizon = 200.0
    looking_at_horizon = (640.0, horizon)
    for depth in (0.2, 0.5, 0.9):
        placed = place_cloud(
            make_cloud(depth), IMAGE, looking_at_horizon, horizon, SCREEN
        )
        assert placed is not None
        (_, y, _, h), _ = placed
        assert y + h < SCREEN[1] / 2  # Above the horizon line.

    deep_underground = (640.0, horizon + 5000)
    assert (
        place_cloud(make_cloud(0.9), IMAGE, deep_underground, horizon, SCREEN)
        is None
    )


def test_far_clouds_are_smaller_fainter_and_lower() -> None:
    """Distance shows in size, opacity and height."""
    center = (640.0, 0.0)
    far = place_cloud(make_cloud(0.2), IMAGE, center, 0.0, SCREEN)
    near = place_cloud(make_cloud(0.9), IMAGE, center, 0.0, SCREEN)
    assert far is not None
    assert near is not None
    (_, far_y, far_w, far_h), far_opacity = far
    (_, near_y, near_w, _), near_opacity = near
    assert far_w < near_w
    assert far_opacity < near_opacity
    assert far_y + far_h > near_y
    assert cloud_scale(0.2) < cloud_scale(0.9)


@pytest.mark.parametrize(("size", "index"), [(0.0, 0), (1.0, 2), (0.5, 1)])
def test_cloud_image_follows_size(size: float, index: int) -> None:
    """Small clouds use the small images."""
    images = [Region(0, 0, 1, 1, w, w) for w in (8, 20, 110)]
    cloud = Cloud(x=0, altitude=0, depth=0.5, speed=0, size=size)
    assert cloud_image(images, cloud) is images[index]
