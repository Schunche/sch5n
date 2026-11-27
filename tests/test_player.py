# Copyright (c) 2026 Schunche
"""Player movement."""

import pytest

from sch5n.game.config import GameConfig, GameMode
from sch5n.game.inventory import Inventory
from sch5n.game.player import Action, Player
from tests.conftest import floor
lazy from sch5n.world.tilemap import TileMap

CONFIG = GameConfig()


def make_player(
    mode: GameMode = GameMode.SURVIVAL, pos: tuple[float, float] = (0, 0)
) -> Player:
    """Create a player with an empty inventory.

    Returns:
        Player: The player.

    """
    return Player(CONFIG, Inventory(10), pos, mode)


def settle(player: Player, tilemap: TileMap, ticks: int = 120) -> None:
    """Let the player stand still for a while."""
    for _ in range(ticks):
        player.tick(tilemap, 0)


def test_falls_and_lands(tilemap: TileMap) -> None:
    """The player falls onto the ground and idles."""
    floor(tilemap, 4)
    player = make_player()
    settle(player, tilemap)
    assert player.body.y == 4 * 32 - CONFIG.player.size[1]
    assert player.action is Action.IDLE


def test_runs_and_accelerates(tilemap: TileMap) -> None:
    """Running speeds up to the maximum speed."""
    floor(tilemap, 4, -100, 100)
    player = make_player()
    settle(player, tilemap)
    x0 = player.body.x
    for _ in range(60):
        player.tick(tilemap, -1)
    assert player.action is Action.RUN
    assert player.facing_left
    assert player.body.vx == pytest.approx(-CONFIG.player.max_speed)
    assert player.body.x < x0 - 60


def test_survival_has_one_jump(tilemap: TileMap) -> None:
    """Survival players cannot jump in the air."""
    floor(tilemap, 4)
    player = make_player()
    settle(player, tilemap)
    assert player.jump()
    player.tick(tilemap, 0)
    assert not player.jump()
    assert player.body.vy < 0


def test_admin_can_jump_in_the_air() -> None:
    """Admin players can jump again mid air."""
    player = make_player(GameMode.ADMIN)
    assert player.jump()
    assert player.jump()


def test_wall_slide_and_wall_jump(tilemap: TileMap) -> None:
    """Sliding down a wall slows the fall; wall jumps push away."""
    stone = tilemap.blocks.id_of("stone")
    for y in range(-20, 20):
        tilemap.set(3, y, stone)
    width = CONFIG.player.size[0]
    player = make_player(GameMode.ADMIN, pos=(3 * 32 - width - 1, 0))
    for _ in range(30):
        player.tick(tilemap, 1)
    assert player.wall_slide
    assert player.action is Action.WALL_SLIDE
    assert player.body.vy <= CONFIG.player.wall_slide_speed
    assert not player.facing_left

    player.jump()
    assert player.body.vx < 0  # Pushed away from the wall.
    assert player.body.vy == -CONFIG.player.wall_jump_velocity[1]


def jump_height(tilemap: TileMap, *, hold: bool) -> float:
    """Jump from the ground and measure how high the player gets.

    Returns:
        float: Peak height in pixels.

    """
    floor(tilemap, 4, -100, 100)
    player = make_player()
    settle(player, tilemap)
    ground = player.body.y
    player.jump()
    peak = ground
    for _ in range(120):
        player.tick(tilemap, 0, jump_held=hold)
        peak = min(peak, player.body.y)
    return ground - peak


def test_holding_jump_jumps_higher(tilemap: TileMap) -> None:
    """A tap is a hop; holding the key reaches several tiles."""
    tap = jump_height(tilemap, hold=False)
    held = jump_height(tilemap, hold=True)
    tile = CONFIG.tile_size
    assert tap < 1.5 * tile
    assert held > 3 * tile
    assert held > 2 * tap


def test_rising_and_falling_actions(tilemap: TileMap) -> None:
    """The action tells rising from falling, for the animations."""
    floor(tilemap, 4, -100, 100)
    player = make_player()
    settle(player, tilemap)
    player.jump()
    seen = []
    for _ in range(120):
        player.tick(tilemap, 0)
        if not seen or seen[-1] is not player.action:
            seen.append(player.action)
    assert seen == [Action.JUMP, Action.FALL, Action.IDLE]


def test_gravity_is_snappy(tilemap: TileMap) -> None:
    """Falling 5 tiles takes well under a second."""
    floor(tilemap, 10, -100, 100)
    player = make_player(pos=(0, 10 * 32 - CONFIG.player.size[1] - 5 * 32))
    ticks = 0
    while not player.body.collisions.down:
        player.tick(tilemap, 0)
        ticks += 1
    assert ticks < CONFIG.tick_rate * 0.6
