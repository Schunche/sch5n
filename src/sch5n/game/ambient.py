# Copyright (c) 2026 Schunche
"""Purely cosmetic simulation: particles, clouds and wind."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sch5n.game.config import ParticleConfig
    from sch5n.math.rect import Rect
    from sch5n.world.tilemap import TileMap


@dataclass(slots=True)
class Particle:
    """A short lived decoration. `x`, `y` is its center."""

    kind: str
    x: float
    y: float
    vx: float
    vy: float
    age: int = 0


@dataclass(slots=True)
class Cloud:
    """A background cloud. Positions wrap around the screen."""

    x: float
    y: float
    depth: float
    """Parallax factor in (0, 1): smaller is further away."""
    speed: float
    variant: int


class Ambience:
    """Wind, clouds and particles emitted by blocks."""

    def __init__(
        self,
        particles: dict[str, ParticleConfig],
        cloud_count: int,
        cloud_variants: int,
        rng: np.random.Generator,
    ) -> None:
        """Roll the wind and scatter clouds."""
        self.config = particles
        self.rng = rng
        self.wind = float(rng.uniform(-1, 1))
        self.particles: list[Particle] = []
        self.clouds = sorted(
            (
                Cloud(
                    x=float(rng.random() * 99999),
                    y=float(rng.random() * 99999),
                    depth=(depth := float(rng.uniform(0.2, 0.8))),
                    speed=depth / (float(rng.uniform(0.05, 0.1)) * 64),
                    variant=int(rng.integers(max(cloud_variants, 1))),
                )
                for _ in range(cloud_count)
            ),
            key=lambda c: c.depth,
        )

    def _spawn(self, tilemap: TileMap, view: Rect, tile_size: int) -> None:
        x0 = math.floor(view.left / tile_size)
        y0 = math.floor(view.top / tile_size)
        x1 = math.ceil(view.right / tile_size)
        y1 = math.ceil(view.bottom / tile_size)
        region = tilemap.region(x0, y0, x1, y1)
        ys, xs = np.nonzero(tilemap.blocks.particle[region])
        if xs.size == 0:
            return

        for block_id in np.unique(region[ys, xs]).tolist():
            block = tilemap.blocks.get(block_id)
            if block is None or block.spec.particle is None:
                continue
            kind = block.spec.particle
            config = self.config.get(kind)
            if config is None:
                continue
            mask = region[ys, xs] == block_id
            rolls = self.rng.random(int(mask.sum())) < config.spawn_chance
            for tx, ty in zip(
                xs[mask][rolls].tolist(), ys[mask][rolls].tolist(), strict=True
            ):
                drift_x, drift_y = config.drift
                vx = self.wind if config.follows_wind else self.rng.random()
                self.particles.append(
                    Particle(
                        kind=kind,
                        x=(x0 + tx + self.rng.random()) * tile_size,
                        y=(y0 + ty + self.rng.random()) * tile_size,
                        vx=vx * drift_x,
                        vy=float(self.rng.random()) * drift_y,
                    )
                )

    def tick(
        self, tilemap: TileMap, view: Rect | None, tile_size: int
    ) -> None:
        """Move clouds, age particles and spawn new ones inside `view`."""
        for cloud in self.clouds:
            cloud.x += cloud.speed * self.wind

        alive: list[Particle] = []
        for particle in self.particles:
            config = self.config.get(particle.kind)
            if config is None or particle.age >= config.lifetime:
                continue
            particle.age += 1
            particle.x += particle.vx + config.sway_amplitude * math.sin(
                particle.age * config.sway_frequency
            )
            particle.y += particle.vy
            alive.append(particle)
        self.particles = alive

        if view is not None:
            self._spawn(tilemap, view, tile_size)
