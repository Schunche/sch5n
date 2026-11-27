# Copyright (c) 2026 Schunche
"""Purely cosmetic simulation: wind, clouds, wind streaks and particles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sch5n.game.config import (
        CloudConfig,
        GameConfig,
        ParticleConfig,
        WindConfig,
        WindStreakConfig,
    )
    from sch5n.math.rect import Rect
    from sch5n.world.tilemap import TileMap

REFERENCE_VIEW_WIDTH = 1280
"""View width the streak rate is given for."""
WIND_STEER = 0.02
"""How quickly wind blown particles adapt to the current wind, per tick."""
SIZE_JITTER = 0.3
"""Randomness of cloud size around what their depth suggests."""


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
    """A background cloud.

    `x` is in its parallax layer and wraps around the screen. `altitude` is
    the height above the horizon of the nearest layer; renderers lower it
    for distant clouds.
    """

    x: float
    altitude: float
    depth: float
    """Distance in (0, 1): smaller is further away."""
    parallax: float
    """How much the cloud moves with the camera, in (0, 1)."""
    speed: float
    """Pixels per tick at wind strength 1."""
    size: float
    """Which cloud image to use, 0 the smallest and 1 the largest."""


@dataclass(slots=True)
class WindStreak:
    """A faint line in the air, blown along by the wind. World pixels."""

    x: float
    y: float
    vx: float
    length: float
    lifetime: int
    phase: float
    """Offset of its up and down wobble."""
    age: int = 0

    @property
    def opacity(self) -> float:
        """Fades in, then out, over its life. In [0, 1]."""
        return math.sin(math.pi * min(self.age / self.lifetime, 1.0))


class Wind:
    """Wind strength (negative blows left) that changes in gusts.

    Every session has a prevailing wind; gusts pull the wind towards a
    nearby strength for a while, then pick another.
    """

    def __init__(self, config: WindConfig, rng: np.random.Generator) -> None:
        """Roll the prevailing wind."""
        self.config = config
        self.rng = rng
        self.prevailing = float(rng.uniform(-1, 1))
        self.strength = self.prevailing
        self.target = self.prevailing
        self._next_gust = 0

    def _roll_gust(self) -> None:
        config = self.config
        self.target = float(
            np.clip(
                self.prevailing
                + self.rng.uniform(
                    -config.gust_strength, config.gust_strength
                ),
                -config.max,
                config.max,
            )
        )
        low, high = config.gust_interval
        self._next_gust = int(self.rng.integers(low, high + 1))

    def tick(self) -> None:
        """Turn towards the current gust; start a new gust when due."""
        if self._next_gust <= 0:
            self._roll_gust()
        self._next_gust -= 1
        step = self.config.change_rate
        delta = self.target - self.strength
        self.strength += max(-step, min(step, delta))


class Ambience:
    """Wind, clouds, wind streaks and particles emitted by blocks."""

    def __init__(self, config: GameConfig, rng: np.random.Generator) -> None:
        """Roll the wind and scatter clouds."""
        self.particle_config: dict[str, ParticleConfig] = config.particles
        self.streak_config: WindStreakConfig = config.wind_streaks
        self.rng = rng
        self.wind = Wind(config.wind, rng)
        self.particles: list[Particle] = []
        self.streaks: list[WindStreak] = []
        self.clouds = self._scatter_clouds(config.clouds)

    def _scatter_clouds(self, config: CloudConfig) -> list[Cloud]:
        rng = self.rng
        low, high = config.altitude
        clouds = []
        for _ in range(config.count):
            depth = float(rng.uniform(0.2, 0.9))
            nearness = (depth - 0.2) / 0.7
            parallax = depth**config.parallax
            clouds.append(
                Cloud(
                    x=float(rng.random() * 99999),
                    altitude=float(rng.uniform(low, high)),
                    depth=depth,
                    parallax=parallax,
                    speed=config.speed
                    * parallax
                    * float(rng.uniform(0.7, 1.3)),
                    size=float(
                        np.clip(
                            nearness + rng.uniform(-SIZE_JITTER, SIZE_JITTER),
                            0,
                            1,
                        )
                    ),
                )
            )
        # Far clouds first, so near ones are drawn over them.
        return sorted(clouds, key=lambda c: c.depth)

    def _spawn_particles(
        self, tilemap: TileMap, view: Rect, tile_size: int
    ) -> None:
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
            config = self.particle_config.get(kind)
            if config is None:
                continue
            mask = region[ys, xs] == block_id
            rolls = self.rng.random(int(mask.sum())) < config.spawn_chance
            for tx, ty in zip(
                xs[mask][rolls].tolist(), ys[mask][rolls].tolist(), strict=True
            ):
                drift_x, drift_y = config.drift
                push = (
                    self.wind.strength
                    if config.follows_wind
                    else self.rng.random()
                )
                self.particles.append(
                    Particle(
                        kind=kind,
                        x=(x0 + tx + self.rng.random()) * tile_size,
                        y=(y0 + ty + self.rng.random()) * tile_size,
                        vx=push * drift_x,
                        vy=float(self.rng.random()) * drift_y,
                    )
                )

    def _spawn_streaks(
        self, tilemap: TileMap, view: Rect, tile_size: int
    ) -> None:
        config = self.streak_config
        wind = self.wind.strength
        if abs(wind) < config.min_wind:
            return
        expected = config.rate * abs(wind) * view.w / REFERENCE_VIEW_WIDTH
        count = int(self.rng.poisson(expected))
        for _ in range(count):
            x = view.x + float(self.rng.random()) * view.w
            y = view.y + float(self.rng.random()) * view.h
            if tilemap.is_solid(
                math.floor(x / tile_size), math.floor(y / tile_size)
            ):
                continue
            self.streaks.append(
                WindStreak(
                    x=x,
                    y=y,
                    vx=wind * config.speed * float(self.rng.uniform(0.8, 1.2)),
                    length=float(self.rng.uniform(*config.length)),
                    lifetime=config.lifetime,
                    phase=float(self.rng.uniform(0, math.tau)),
                )
            )

    def _tick_particles(self) -> None:
        alive: list[Particle] = []
        for particle in self.particles:
            config = self.particle_config.get(particle.kind)
            if config is None or particle.age >= config.lifetime:
                continue
            if config.follows_wind:
                target = self.wind.strength * config.drift[0]
                particle.vx += (target - particle.vx) * WIND_STEER
            particle.age += 1
            particle.x += particle.vx + config.sway_amplitude * math.sin(
                particle.age * config.sway_frequency
            )
            particle.y += particle.vy
            alive.append(particle)
        self.particles = alive

    def _tick_streaks(self) -> None:
        alive: list[WindStreak] = []
        for streak in self.streaks:
            streak.age += 1
            if streak.age >= streak.lifetime:
                continue
            streak.x += streak.vx
            alive.append(streak)
        self.streaks = alive

    def tick(
        self,
        tilemap: TileMap,
        view: Rect | None,
        tile_size: int,
        wind: float | None = None,
    ) -> None:
        """Advance the wind and everything it moves.

        New particles and streaks only appear inside `view`. Clients pass
        the server's `wind` so everyone sees the same weather.
        """
        if wind is None:
            self.wind.tick()
        else:
            self.wind.strength = wind
        for cloud in self.clouds:
            cloud.x += cloud.speed * self.wind.strength
        self._tick_particles()
        self._tick_streaks()
        if view is not None:
            self._spawn_particles(tilemap, view, tile_size)
            self._spawn_streaks(tilemap, view, tile_size)
