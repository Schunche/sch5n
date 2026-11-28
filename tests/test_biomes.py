# Copyright (c) 2026 Schunche
"""Tests for biomes, trees and ores in generated worlds."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from typing import TYPE_CHECKING

import numpy as np

from sch5n.world.biomes import BIOMES, MAX_WIDTH, MIN_WIDTH, biome_bands
from sch5n.world.generator import ORE_PAIRS, WorldSpec, generate
from tests.test_world_io import block_name

if TYPE_CHECKING:
    from sch5n.game.content import Content

WIDTH = 400


def test_bands_cover_the_width_without_gaps() -> None:
    """Stretches follow each other, differ from their neighbor, and fit."""
    for seed in range(20):
        bands = biome_bands(0, WIDTH, np.random.default_rng(seed))
        assert bands[0][0] == 0
        assert bands[-1][1] == WIDTH
        assert bands[0][2].name == "plains"
        for (_, end, biome), (start, _, other) in pairwise(bands):
            assert end == start
            assert biome.name != other.name
        for start, end, _ in bands[:-1]:
            assert MIN_WIDTH <= end - start <= MAX_WIDTH
        assert bands[-1][1] - bands[-1][0] >= MIN_WIDTH


def test_every_biome_names_real_blocks(content: Content) -> None:
    """Surface blocks and tree saplings exist in the game."""
    for biome in BIOMES.values():
        assert content.blocks.by_name(biome.top)
        assert content.blocks.by_name(biome.body)
        for wood in biome.trees:
            assert content.blocks.by_name(f"{wood}_sapling")


def test_worlds_have_deserts_snow_and_trees(content: Content) -> None:
    """A wide world holds several biomes and trees of more than one wood."""
    world = generate(
        content.blocks, WorldSpec(right=WIDTH, bottom=60), seed=11
    )
    names = Counter(block_name(content, b) for *_, b, _ in world.iter_tiles())
    assert names["sand"] > 0
    assert names["snow"] > 0
    assert names["grass"] > 0
    woods = {n for n in names if n.endswith("_log")}
    assert len(woods) >= 2  # ruff: ignore[magic-value-comparison]


def test_trees_stand_on_the_ground(content: Content) -> None:
    """Every log has a log or ground right below it."""
    world = generate(content.blocks, WorldSpec(right=WIDTH, bottom=60), seed=4)
    blocks = content.blocks
    for x, y, block, _ in world.iter_tiles():
        if y >= 0 or not block_name(content, block).endswith("_log"):
            continue
        below = blocks.get(world.get(x, y + 1))
        assert below is not None
        assert below.spec.solid or below.name.endswith(("_log", "_log_leaf"))


def test_worlds_hold_ores_deeper_for_rarer_ones(content: Content) -> None:
    """One ore of each pair is in the stone, and rarer ones lie deeper."""
    spec = WorldSpec(right=WIDTH, bottom=160)
    world = generate(content.blocks, spec, seed=2)
    depth: dict[str, list[int]] = {}
    for _, y, block, _ in world.iter_tiles():
        name = block_name(content, block)
        if any(name in pair for pair in ORE_PAIRS):
            depth.setdefault(name, []).append(y)
    assert len(depth) == len(ORE_PAIRS)
    for pair in ORE_PAIRS:
        assert sum(name in depth for name in pair) == 1
    means = sorted(
        (sum(rows) / len(rows), name) for name, rows in depth.items()
    )
    shallow = {name for _, name in means[:1]}
    assert shallow & {"copper", "tin", "iron", "lead"}


def test_a_player_can_stand_in_a_generated_world(content: Content) -> None:
    """The game runs on a generated world and the player stays on top."""
    from sch5n.game.session import Game, GameSetup, TickInput  # ruff: ignore[import-outside-top-level]

    world = generate(content.blocks, WorldSpec(right=WIDTH, bottom=60), seed=5)
    game = Game(content, world, GameSetup(seed=1, spawn=(160, 0)))
    for _ in range(200):
        game.tick(TickInput())
    assert game.player.body.y < 0


def test_the_home_stretch_is_plains() -> None:
    """Players start in plains, wherever home lies."""
    for seed in range(20):
        bands = biome_bands(-WIDTH, WIDTH, np.random.default_rng(seed), 0)
        assert bands[0][0] == -WIDTH
        assert bands[-1][1] == WIDTH
        home = next(b for s, e, b in bands if s <= 0 < e)
        assert home.name == "plains"
        for (_, _, biome), (_, _, other) in pairwise(bands):
            assert biome.name != other.name


def test_a_wandering_player_survives_a_generated_world(
    content: Content,
) -> None:
    """Walking, jumping and using things on generated ground never crash."""
    from sch5n.game.session import Game, GameSetup, TickInput  # ruff: ignore[import-outside-top-level]

    spec = WorldSpec(left=-WIDTH // 2, right=WIDTH // 2, home=0)
    game = Game(content, generate(content.blocks, spec, 3), GameSetup(seed=3))
    rng = np.random.default_rng(3)
    direction = 1
    for tick in range(3000):
        if tick % 100 == 0:
            direction = int(rng.integers(-1, 2))
        x, y = game.player.body.center
        target = (int(x // 32) + int(rng.integers(-4, 5)), int(y // 32))
        game.tick(
            TickInput(
                move_x=direction,
                jump=tick % 40 == 0,
                use=tick % 3 == 0,
                place=tick % 7 == 0,
                target=target,
            )
        )
    assert game.player.deaths >= 0


def test_stone_starts_close_to_the_surface(content: Content) -> None:
    """The dirt layer is thin: most columns hit stone within 30 tiles."""
    spec = WorldSpec(left=-100, right=100, home=0)
    tiles = generate(content.blocks, spec, 4)
    stone = content.blocks.id_of("stone")
    shallow = sum(
        any(tiles.get(x, y) == stone for y in range(spec.top, 30))
        for x in range(spec.left, spec.right)
    )
    assert shallow > (spec.right - spec.left) * 0.9
