# Copyright (c) 2026 Schunche
"""Map files and generation."""

from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest

from sch5n.client import __main__ as client_main
from sch5n.error.exceptions import ParseError
from sch5n.utility import path
from sch5n.world import io
from sch5n.world.__main__ import main as generate_main
from sch5n.world.generator import WorldSpec, generate
from sch5n.world.io import (
    load_tilemap,
    save_tilemap,
    tilemap_from_json,
    tilemap_to_json,
)
lazy from sch5n.world.tilemap import TileMap

if TYPE_CHECKING:
    from collections.abc import Callable

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


@pytest.fixture
def default_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Stand a temporary default map in for the real one, while developing.

    Returns:
        Path: The stand in.

    """
    monkeypatch.setenv(path.DEV_ENV_VAR, "1")
    monkeypatch.setattr(io, "MAPS_DIR", tmp_path)
    monkeypatch.setattr(path, "MAPS_DIR", tmp_path)
    target = tmp_path / f"{io.DEFAULT_MAP}.json"
    target.write_text("{}", encoding="utf-8")
    return target


def test_only_the_default_map_is_protected(default_map: Path) -> None:
    """The default map is recognised however its path is written."""
    assert io.is_protected(default_map)
    assert io.is_protected(
        default_map.parent / ".." / default_map.parent.name / default_map.name
    )
    assert not io.is_protected(default_map.with_name("other.json"))
    default_map.unlink()
    assert io.is_protected(default_map)


def test_saving_the_default_map_backs_it_up(
    default_map: Path, tilemap: TileMap
) -> None:
    """Every change keeps the previous version; no change keeps nothing."""
    backups = default_map.parent / io.BACKUP_DIR
    tilemap.set(1, 2, 1)
    save_tilemap(default_map, tilemap)
    first = default_map.read_bytes()
    save_tilemap(default_map, tilemap)
    assert [file.read_bytes() for file in backups.iterdir()] == [b"{}"]
    tilemap.set(3, 4, 1)
    save_tilemap(default_map, tilemap)
    assert sorted(file.read_bytes() for file in backups.iterdir()) == sorted([
        b"{}",
        first,
    ])


def test_failed_backup_leaves_the_default_map(
    default_map: Path, tilemap: TileMap
) -> None:
    """Without a backup the default map is not overwritten."""
    (default_map.parent / io.BACKUP_DIR).write_text("", encoding="utf-8")
    tilemap.set(1, 2, 1)
    with pytest.raises(io.BackupError, match=io.BACKUP_DIR):
        save_tilemap(default_map, tilemap)
    assert default_map.read_bytes() == b"{}"


def test_other_maps_are_not_backed_up(
    default_map: Path, tilemap: TileMap
) -> None:
    """Ordinary maps are saved without backups."""
    other = default_map.with_name("other.json")
    save_tilemap(other, tilemap)
    tilemap.set(1, 2, 1)
    save_tilemap(other, tilemap)
    assert not (default_map.parent / io.BACKUP_DIR).exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--edit"],
        ["--edit", "--map", "map1"],
        ["--edit-default", "--map", "other"],
        ["--edit", "--edit-default"],
    ],
)
@pytest.mark.usefixtures("default_map")
def test_viewer_refuses_wrong_edit_flags(argv: list[str]) -> None:
    """The default map is edited with its own flag only, before any window."""
    if "map1" in argv:
        argv = [*argv[:-1], str(path.MAPS_DIR / "map1.json")]
    with pytest.raises(SystemExit):
        client_main.viewer_main(argv)


def test_generator_refuses_the_default_map(default_map: Path) -> None:
    """Generating over the default map must be asked for."""
    with pytest.raises(SystemExit):
        generate_main([io.DEFAULT_MAP])
    assert default_map.read_bytes() == b"{}"


def test_default_map_is_read_only_outside_development(
    default_map: Path, tilemap: TileMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Players' copies never write the default map, but save other maps."""
    monkeypatch.setenv(path.DEV_ENV_VAR, "0")
    tilemap.set(1, 2, 1)
    with pytest.raises(PermissionError, match="read-only"):
        save_tilemap(default_map, tilemap)
    assert default_map.read_bytes() == b"{}"
    assert not (default_map.parent / io.BACKUP_DIR).exists()
    save_tilemap(default_map.with_name("other.json"), tilemap)


@pytest.mark.parametrize(
    "command",
    [
        (client_main.viewer_main, ["--edit-default"]),
        (client_main.viewer_main, ["--edit"]),
        (generate_main, [io.DEFAULT_MAP]),
        (generate_main, [io.DEFAULT_MAP, "--overwrite-default"]),
    ],
)
@pytest.mark.parametrize("developing", ["0", "1"])
def test_default_map_options_are_for_developers(
    command: tuple[Callable[[list[str]], None], list[str]],
    developing: str,
    default_map: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Only developers are offered, or told about, the override options."""
    main, argv = command
    monkeypatch.setenv(path.DEV_ENV_VAR, developing)
    with pytest.raises(SystemExit):
        main(["--help"])
    offered = "-default" in capsys.readouterr().out
    assert offered == (developing == "1")
    if developing == "0":
        with pytest.raises(SystemExit):
            main(argv)
        error = capsys.readouterr().err.split("error:")[1]
        if not any(arg.endswith("-default") for arg in argv):
            assert "-default" not in error
        assert default_map.read_bytes() == b"{}"


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
