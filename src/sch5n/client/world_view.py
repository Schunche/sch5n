# Copyright (c) 2026 Schunche
"""Draws the world: tiles, entities, particles and clouds."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.batch import INSTANCE_FLOATS, WHITE, sprite_instances
from sch5n.game.mining import durability_fraction
from sch5n.utility import path
from sch5n.world.io import load_tilemap
from sch5n.world.tilemap import CHUNK_SHIFT, CHUNK_SIZE

STREAK_THICKNESS = 2
STREAK_OPACITY = 0.55
STREAK_WOBBLE = 3.0
"""Pixels a wind streak moves up and down."""
STREAK_WOBBLE_SPEED = 0.12

DEFAULT_MAP = "map1"
"""Map played when none is chosen on the command line."""

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sch5n.client.app import App
    from sch5n.client.assets import ClientAssets
    from sch5n.client.camera import Camera
    from sch5n.client.render.atlas import Region
    from sch5n.client.render.batch import RGBA, SpriteBatch
    from sch5n.game.ambient import Ambience, Cloud
    from sch5n.game.floating_item import FloatingItem
    from sch5n.game.player import Player
    from sch5n.game.session import Game
    from sch5n.math.rect import Rect
    from sch5n.math.vector import IntTuple2
    from sch5n.world.tilemap import Chunk, TileMap


class TileRenderer:
    """Draws tiles, caching the instance data of each chunk."""

    def __init__(self, assets: ClientAssets, tile_size: int) -> None:
        """Create a renderer for one atlas and tile size."""
        self.assets = assets
        self.tile_size = tile_size
        self._cache: dict[IntTuple2, tuple[int, np.ndarray]] = {}
        local = np.arange(CHUNK_SIZE)
        self._local_y, self._local_x = np.meshgrid(local, local, indexing="ij")

    def _chunk_instances(self, key: IntTuple2, chunk: Chunk) -> np.ndarray:
        cached = self._cache.get(key)
        if cached is not None and cached[0] == chunk.revision:
            return cached[1]

        mask = chunk.blocks != 0
        size = self.tile_size
        xs = (self._local_x[mask] + (key[0] << CHUNK_SHIFT)) * size
        ys = (self._local_y[mask] + (key[1] << CHUNK_SHIFT)) * size
        rects = np.stack(
            [xs, ys, np.full_like(xs, size), np.full_like(xs, size)], axis=1
        )
        variants = np.minimum(
            chunk.variants[mask], self.assets.block_uvs.shape[1] - 1
        )
        uvs = self.assets.block_uvs[chunk.blocks[mask], variants]
        instances = sprite_instances(rects, uvs)
        self._cache[key] = (chunk.revision, instances)
        return instances

    def draw(
        self,
        batch: SpriteBatch,
        tilemap: TileMap,
        view: Rect,
        *,
        breakage: bool = True,
        color: RGBA = WHITE,
    ) -> None:
        """Queue every tile overlapping `view`."""
        span = self.tile_size * CHUNK_SIZE
        cx0, cy0 = math.floor(view.left / span), math.floor(view.top / span)
        cx1, cy1 = (
            math.floor(view.right / span),
            math.floor(view.bottom / span),
        )

        parts = [
            self._chunk_instances((cx, cy), chunk)
            for cy in range(cy0, cy1 + 1)
            for cx in range(cx0, cx1 + 1)
            if (chunk := tilemap.chunks.get((cx, cy))) is not None
        ]
        if parts:
            instances = np.concatenate(parts) if len(parts) > 1 else parts[0]
            if color != WHITE:
                instances = instances.copy()
                instances[:, 8:12] = color
            batch.extend(self.assets.atlas, instances)

        # Drop cache entries of chunks that no longer exist.
        if len(self._cache) > len(tilemap.chunks):
            for key in self._cache.keys() - tilemap.chunks.keys():
                del self._cache[key]

        if breakage:
            self._draw_breakage(batch, tilemap)

    def _draw_breakage(self, batch: SpriteBatch, tilemap: TileMap) -> None:
        frames = self.assets.breakage
        size = self.tile_size
        for x, y in tilemap.damage:
            fraction = durability_fraction(tilemap, x, y)
            index = int((len(frames) - 1) * (1 - fraction))
            batch.sprite(
                self.assets.atlas,
                (x * size, y * size, size, size),
                frames[min(max(index, 0), len(frames) - 1)],
            )


def draw_player(
    batch: SpriteBatch, assets: ClientAssets, player: Player
) -> None:
    """Queue the player sprite, standing on the bottom of the hitbox.

    Frames are drawn at their own size, centered on the hitbox, so they
    may be wider than the body for swinging arms and legs.
    """
    animation = assets.mobs["player", player.action.value]
    frame = animation.frame(player.action_age)
    body = player.body
    x = round(body.x + (body.w - frame.width) / 2)
    y = round(body.y + body.h - frame.height)
    batch.sprite(
        assets.atlas,
        (x, y, frame.width, frame.height),
        frame,
        flip_x=player.facing_left,
    )


def draw_floating_items(
    batch: SpriteBatch, assets: ClientAssets, items: list[FloatingItem]
) -> None:
    """Queue dropped items."""
    for floating in items:
        r = floating.sprite_rect
        batch.sprite(
            assets.atlas,
            (r.x, r.y, r.w, r.h),
            assets.items[floating.stack.item.name],
        )


def draw_particles(
    batch: SpriteBatch, assets: ClientAssets, ambience: Ambience
) -> None:
    """Queue particles, centered on their position."""
    if not ambience.particles:
        return
    rows = np.zeros(
        (len(ambience.particles), INSTANCE_FLOATS), dtype=np.float32
    )
    for row, particle in zip(rows, ambience.particles, strict=True):
        region = assets.particles[particle.kind].frame(particle.age)
        row[0:4] = (
            particle.x - region.width / 2,
            particle.y - region.height / 2,
            region.width,
            region.height,
        )
        row[4:8] = region.uv
        row[8:12] = WHITE
    batch.extend(assets.atlas, rows)


def cloud_scale(depth: float) -> int:
    """Whole pixel scale of a cloud: near clouds are drawn bigger.

    Returns:
        int: 2 for the furthest clouds up to 4 for the nearest.

    """
    return max(1, round(1 + depth * 3))


def cloud_image(regions: Sequence[Region], cloud: Cloud) -> Region:
    """Pick the image for a cloud: small images for small clouds.

    Returns:
        Region: One of `regions`, which are ordered smallest first.

    """
    return regions[round(cloud.size * (len(regions) - 1))]


def place_cloud(
    cloud: Cloud,
    image: Region,
    camera_center: tuple[float, float],
    horizon: float,
    screen: tuple[float, float],
) -> tuple[tuple[float, float, float, float], float] | None:
    """Where a cloud appears on screen, and how opaque it is.

    Clouds float above the horizon with parallax: distant ones move less
    with the camera, sit lower, look smaller and fade into the sky.
    Horizontally they wrap around the screen.

    Returns:
        tuple[tuple[float, float, float, float], float] | None: Screen
        rectangle and opacity, or `None` when off screen.

    """
    width, height = screen
    scale = cloud_scale(cloud.depth)
    w, h = image.width * scale, image.height * scale
    x = (cloud.x - camera_center[0] * cloud.parallax) % (width + w) - w
    horizon_on_screen = (
        height / 2 + (horizon - camera_center[1]) * cloud.parallax
    )
    lift = cloud.altitude * (0.4 + 0.6 * cloud.depth)
    y = horizon_on_screen - lift - h
    if y > height or y + h < 0:
        return None
    opacity = 0.35 + 0.65 * cloud.depth
    return (round(x), round(y), w, h), opacity


def draw_clouds(
    batch: SpriteBatch,
    assets: ClientAssets,
    game: Game,
    camera_center: tuple[float, float],
    screen: tuple[float, float],
) -> None:
    """Queue clouds in screen space, far ones first."""
    if not assets.clouds:
        return
    for cloud in game.ambience.clouds:
        image = cloud_image(assets.clouds, cloud)
        placed = place_cloud(cloud, image, camera_center, game.horizon, screen)
        if placed is not None:
            rect, opacity = placed
            batch.sprite(assets.atlas, rect, image, (1.0, 1.0, 1.0, opacity))


def draw_wind_streaks(batch: SpriteBatch, ambience: Ambience) -> None:
    """Queue faint, wobbling lines where the wind blows. World space."""
    for streak in ambience.streaks:
        wobble = math.sin(streak.age * STREAK_WOBBLE_SPEED + streak.phase)
        batch.shape(
            (
                streak.x - streak.length / 2,
                streak.y + wobble * STREAK_WOBBLE,
                streak.length,
                STREAK_THICKNESS,
            ),
            (1.0, 1.0, 1.0, STREAK_OPACITY * streak.opacity),
            radius=STREAK_THICKNESS / 2,
        )


class WorldRenderer:
    """Draws a game session as the player sees it: sky, clouds, world."""

    def __init__(self, app: App) -> None:
        """Create the renderer."""
        self.app = app
        self.tiles = TileRenderer(app.assets, app.content.game.tile_size)

    def draw(
        self, game: Game, camera: Camera, *, show_player: bool = True
    ) -> None:
        """Draw everything but the HUD. Leaves a world space batch open."""
        app = self.app
        batch = app.batch
        offset = camera.offset()

        app.clear(app.content.game.sky_color)
        batch.begin(app.screen)
        view = camera.view(app.screen)
        draw_clouds(batch, app.assets, game, view.center, app.screen)

        batch.begin(app.screen, offset, camera.zoom)
        self.tiles.draw(batch, game.tilemap, camera.view(app.screen))
        if show_player:
            draw_player(batch, app.assets, game.player)
        draw_particles(batch, app.assets, game.ambience)
        draw_wind_streaks(batch, game.ambience)
        draw_floating_items(batch, app.assets, game.floating_items)


def load_world(app: App) -> TileMap:
    """Load the map chosen on the command line, or the default one.

    Returns:
        TileMap: The map.

    """
    map_path = app.options.map_path or path.MAPS_DIR / f"{DEFAULT_MAP}.json"
    return load_tilemap(map_path, app.content.blocks)
