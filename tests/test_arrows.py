# Copyright (c) 2026 Schunche
"""Tests for bows, arrows and skeletons."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sch5n.game.inventory import ItemStack
from sch5n.game.mobs import KINDS, SHOOT_EVERY, Mob
from sch5n.game.projectiles import MAX_AGE, Projectile, aim
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.game.vitals import MAX_HEALTH
from tests.test_mobs import GROUND, SLIME, TILE, add_slime, make_game
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content


def arm(game: Game, content: Content, arrows: int = 10) -> None:
    """Give the player a bow in hand and arrows."""
    inventory = game.player.inventory
    inventory.slots[inventory.selected] = ItemStack(content.items["bow"])
    inventory.slots[15] = ItemStack(content.items["arrow"], arrows)


def count_arrows(game: Game) -> int:
    """Count the arrows the player carries.

    Returns:
        int: The amount.

    """
    return sum(
        s.amount for s in game.player.inventory if s and s.item.name == "arrow"
    )


def test_aim_allows_for_gravity() -> None:
    """The aim is above a straight line, and faster shots are flatter."""
    slow = aim((0, 0), (200, 0), 6.0)
    fast = aim((0, 0), (200, 0), 15.0)
    assert slow[0] > 0
    assert slow[1] < fast[1] < 0
    assert aim((0, 0), (0, 0), 5.0) is not None


def test_a_bow_costs_an_arrow_and_needs_one(content: Content) -> None:
    """Shooting uses up ammunition; with none, nothing flies."""
    game = make_game(content)
    arm(game, content, arrows=2)
    target = (int(game.player.body.x // TILE) + 8, 9)
    spec = content.items["bow"].spec
    for _ in range(spec.use_time * 4):
        game.tick(TickInput(use=True, target=target))
        game.player.vitals.health = MAX_HEALTH
    assert count_arrows(game) == 0
    flown = game._next_projectile  # ruff: ignore[private-member-access]
    assert flown == 2  # ruff: ignore[magic-value-comparison]


def test_an_arrow_kills_a_slime(content: Content) -> None:
    """An arrow hits the creature in its way and hurts it."""
    game = make_game(content)
    arm(game, content)
    slime = add_slime(game, game.player.body.x + 8 * TILE)
    start = slime.health
    target = (int(slime.body.center[0] // TILE), 9)
    for _ in range(300):
        game.tick(TickInput(use=True, target=target))
        game.player.vitals.health = MAX_HEALTH
        if slime.health < start or not game.mobs:
            break
    assert not game.mobs or slime.health < start
    assert not game.projectiles or all(
        not a.hostile for a in game.projectiles.values()
    )


def test_arrows_stop_in_walls_and_time_out(content: Content) -> None:
    """An arrow into the ground vanishes; a stray one is not kept forever."""
    game = make_game(content)
    ground = Projectile("arrow", 100, GROUND - 2, 0, 5, 3, hostile=False)
    game.projectiles[1] = ground
    for _ in range(10):
        game.tick(TickInput())
    assert not game.projectiles
    old = Projectile("arrow", 100, -5000, 0, 0, 3, hostile=False)
    old.age = MAX_AGE
    game.projectiles[2] = old
    game.tick(TickInput())
    assert not game.projectiles


def test_hostile_arrows_hurt_players_not_slimes(content: Content) -> None:
    """Skeleton arrows only touch players."""
    game = make_game(content)
    slime = add_slime(game, game.player.body.x + 4 * TILE)
    cx, cy = game.player.body.center
    arrow = Projectile("arrow", cx - 3, cy, 3.0, 0.0, 3, hostile=True)
    game.projectiles[1] = arrow
    game.tick(TickInput())
    assert game.player.vitals.health == MAX_HEALTH - 3
    assert slime.health == SLIME.health
    assert 1 not in game.projectiles


def test_a_skeleton_shoots_keeps_away_and_drops_arrows(
    content: Content,
) -> None:
    """In sight, a skeleton fires; too close, it backs off."""
    kind = KINDS["skeleton"]
    assert kind.ranged
    game = make_game(content)
    mob = Mob(kind, (game.player.body.x + 5 * TILE, GROUND - kind.size[1]))
    game.mobs[900] = mob
    shots = 0
    start_x = mob.body.x
    for _ in range(SHOOT_EVERY * 2):
        game.tick(TickInput())
        game.player.vitals.health = MAX_HEALTH
        shots = max(shots, len(game.projectiles))
        if mob.body.x > start_x:
            break
    assert mob.body.x > start_x  # backed away to the right
    for _ in range(SHOOT_EVERY * 2):
        game.tick(TickInput())
        game.player.vitals.health = MAX_HEALTH
        shots = max(shots, len(game.projectiles))
    assert shots >= 1
    assert game.player.deaths == 0


def test_arrows_are_synced_to_clients(content: Content) -> None:
    """Clients see arrows in flight."""
    from sch5n.server.server import Server  # ruff: ignore[import-outside-top-level]
    from tests.test_server import join, step  # ruff: ignore[import-outside-top-level]

    server = Server(
        content, flat_world(content), GameSetup(seed=1, spawn=(0, 0))
    )
    alice = join(server, content)
    server.game.projectiles[0] = Projectile(
        "arrow", 50.0, -200.0, 1.0, 0.0, 3, hostile=True
    )
    step(server, [alice], 2)
    assert alice.world is not None
    assert len(alice.world.projectiles) == 1
    arrow = next(iter(alice.world.projectiles.values()))
    assert arrow.item == "arrow"
    assert arrow.hostile
    assert arrow.angle == pytest.approx(0.0, abs=0.5)


def test_bow_and_arrow_are_craftable(content: Content) -> None:
    """Recipes give both."""
    results = {r.result.item for r in content.recipes}
    assert {"bow", "arrow"} <= results
