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

DEFAULT_MAP = "map1"
"""Map played when none is chosen on the command line."""

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.assets import ClientAssets
    from sch5n.client.camera import Camera
    from sch5n.client.render.batch import RGBA, SpriteBatch
    from sch5n.game.ambient import Ambience
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
    """Queue the player sprite."""
    animation = assets.mobs["player", player.action.value]
    body = player.body
    batch.sprite(
        assets.atlas,
        (body.x, body.y, body.w, body.h),
        animation.frame(player.action_age),
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


def draw_clouds(
    batch: SpriteBatch,
    assets: ClientAssets,
    ambience: Ambience,
    camera_offset: tuple[float, float],
    screen: tuple[float, float],
) -> None:
    """Queue clouds in screen space, with parallax and wrap around."""
    if not assets.clouds:
        return
    width, height = screen
    for cloud in ambience.clouds:
        region = assets.clouds[cloud.variant % len(assets.clouds)]
        w, h = region.width, region.height
        x = (cloud.x - camera_offset[0] * cloud.depth) % (width + w) - w
        y = (cloud.y - camera_offset[1] * cloud.depth) % (height + h) - h
        batch.sprite(assets.atlas, (round(x), round(y), w, h), region)


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
        draw_clouds(batch, app.assets, game.ambience, offset, app.screen)

        batch.begin(app.screen, offset, camera.zoom)
        self.tiles.draw(batch, game.tilemap, camera.view(app.screen))
        if show_player:
            draw_player(batch, app.assets, game.player)
        draw_particles(batch, app.assets, game.ambience)
        draw_floating_items(batch, app.assets, game.floating_items)


def load_world(app: App) -> TileMap:
    """Load the map chosen on the command line, or the default one.

    Returns:
        TileMap: The map.

    """
    map_path = app.options.map_path or path.MAPS_DIR / f"{DEFAULT_MAP}.json"
    return load_tilemap(map_path, app.content.blocks)
