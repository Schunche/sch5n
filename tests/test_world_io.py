# Copyright (c) 2026 Schunche
"""Map files and generation."""

from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest

from sch5n.error.exceptions import ParseError
from sch5n.utility import path
from sch5n.world.generator import WorldSpec, generate
from sch5n.world.io import (
    load_tilemap,
    save_tilemap,
    tilemap_from_json,
    tilemap_to_json,
)
lazy from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from sch5n.game.content import BlockRegistry, Content


def test_legacy_format_with_aliases(blocks: BlockRegistry) -> None:
    """Old maps load, with old block names, and save with new ones."""
    tilemap = tilemap_from_json(
        {"3;-4": {"block": "oldLog", "variant": 0}, "0;0": {"block": "stone"}},
        blocks,
    )
    assert tilemap.get(3, -4) == blocks.id_of("log")
    assert tilemap_to_json(tilemap) == {
        "3;-4": {"block": "log", "variant": 0},
        "0;0": {"block": "stone", "variant": 0},
    }


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"1,2": {"block": "stone"}},
        {"1;2": {"block": "unknown"}},
        {"1;2": {"variant": 0}},
        {"1;2": {"block": "stone", "variant": "x"}},
    ],
)
def test_invalid_maps_are_rejected(
    blocks: BlockRegistry, data: object
) -> None:
    """Malformed map data is a parse error."""
    with pytest.raises(ParseError):
        tilemap_from_json(data, blocks)  # type: ignore[arg-type]


def test_save_load_roundtrip(tmp_path: Path, tilemap: TileMap) -> None:
    """Saved maps load back unchanged."""
    tilemap.set(-5, 9, 2)
    tilemap.set(100, -100, 1)
    target = tmp_path / "maps" / "x.json"
    save_tilemap(target, tilemap)
    loaded = load_tilemap(target, tilemap.blocks)
    assert sorted(loaded.iter_tiles()) == sorted(tilemap.iter_tiles())


@pytest.mark.parametrize("name", ["map1", "procedural"])
def test_bundled_maps_load(content: Content, name: str) -> None:
    """The maps shipped with the game load."""
    tilemap = load_tilemap(path.MAPS_DIR / f"{name}.json", content.blocks)
    assert len(tilemap) > 0


def test_generation_is_deterministic(content: Content) -> None:
    """The same seed generates the same world."""
    spec = WorldSpec(right=60, bottom=40)
    a = generate(content.blocks, spec, seed=7)
    b = generate(content.blocks, spec, seed=7)
    assert sorted(a.iter_tiles()) == sorted(b.iter_tiles())
    assert len(a) == 60 * 40
    assert a.bounds() == (0, 0, 60, 40)
    dirt, stone = content.blocks.id_of("dirt"), content.blocks.id_of("stone")
    assert {block for _, _, block, _ in a.iter_tiles()} <= {dirt, stone}
