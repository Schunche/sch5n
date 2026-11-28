# Copyright (c) 2026 Schunche
"""Hostile creatures: moving, spawning at night, hurting and being hurt."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from sch5n.game.config import GameMode
from sch5n.game.daylight import DAY_SECONDS, START
from sch5n.game.inventory import ItemStack
from sch5n.game.mobs import CONTACT_COOLDOWN, KINDS, Mob
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.game.vitals import MAX_HEALTH, MAX_HUNGER
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

SLIME = KINDS["slime"]
TILE = 32
GROUND = 10 * TILE
"""World y of the top of `flat_world`."""
MIDNIGHT = int(((0.0 - START) % 1) * DAY_SECONDS * 60)
NOON = int(((0.5 - START) % 1) * DAY_SECONDS * 60)


def make_game(content: Content, mode: GameMode = GameMode.SURVIVAL) -> Game:
    """Start a game on flat ground.

    Returns:
        Game: The game, with its player standing at the origin.

    """
    game = Game(
        content,
        flat_world(content),
        GameSetup(seed=1, spawn=(0, 0), mode=mode),
    )
    game.tick(TickInput())
    return game


def add_slime(game: Game, x: float) -> Mob:
    """Put a slime on the ground at `x`.

    Returns:
        Mob: The new mob.

    """
    mob = Mob(SLIME, (x, GROUND - SLIME.size[1]))
    game.mobs[len(game.mobs) + 100] = mob
    return mob


def test_slimes_walk_towards_the_player(content: Content) -> None:
    """A slime in sight closes in; one out of sight stands still."""
    game = make_game(content)
    near = add_slime(game, game.player.body.x + 6 * TILE)
    start = near.body.x
    for _ in range(30):
        game.tick(TickInput())
    assert near.body.x < start
    assert near.facing_left
    far = add_slime(game, game.player.body.x + 40 * TILE)
    far_start = far.body.x
    for _ in range(30):
        game.tick(TickInput())
    assert far.body.x == pytest.approx(far_start)


def test_a_touch_hurts_with_a_pause_between(content: Content) -> None:
    """A touch takes health and pushes the player; a second has to wait."""
    game = make_game(content)
    player = game.player
    add_slime(game, player.body.x)
    game.tick(TickInput())
    assert player.vitals.health == MAX_HEALTH - SLIME.damage
    game.tick(TickInput())
    assert player.vitals.health == MAX_HEALTH - SLIME.damage
    assert player.hurt_cooldown > 0
    assert player.hurt_cooldown <= CONTACT_COOLDOWN


def test_dying_sends_the_player_home(content: Content) -> None:
    """At zero health the player respawns whole, and it is announced."""
    game = make_game(content)
    player = game.player
    player.name = "ann"
    player.vitals.health = 1
    player.body.x += 500
    game.hurt_player(player, 2, "was slain")
    assert player.vitals.health == MAX_HEALTH
    assert player.vitals.hunger == MAX_HUNGER
    assert player.deaths == 1
    assert player.body.x < 400  # ruff: ignore[magic-value-comparison]
    assert game.announcements == ["ann was slain"]


def test_admins_cannot_be_hurt(content: Content) -> None:
    """Creatures do nothing to admins."""
    game = make_game(content, GameMode.ADMIN)
    add_slime(game, game.player.body.x)
    game.tick(TickInput())
    assert game.player.vitals.health == MAX_HEALTH


def test_a_tool_swing_hurts_and_kills(content: Content) -> None:
    """Swinging at a slime damages it, pushes it, and kills it in the end."""
    game = make_game(content)
    player = game.player
    pick = content.items["iron_axe"]
    player.inventory.slots[player.inventory.selected] = ItemStack(pick)
    slime = add_slime(game, player.body.x + 2 * TILE)
    tile = (int(slime.body.center[0] // TILE), 9)
    for _ in range(200):
        if not game.mobs:
            break
        game.tick(TickInput(use=True, target=tile))
        if game.mobs:
            tile = (int(slime.body.center[0] // TILE), 9)
    assert not game.mobs
    assert game.player.vitals.health > 0


def test_a_killed_slime_may_drop_goo(content: Content) -> None:
    """Dying drops the kind's item, for some seeds."""
    dropped = False
    for seed in range(20):
        game = Game(
            content,
            flat_world(content),
            GameSetup(seed=seed, spawn=(0, 0)),
        )
        add_slime(game, 0)
        game.mobs[next(iter(game.mobs))].health = 1
        game.mobs[next(iter(game.mobs))].hit(1, 0)
        game._mob_died(next(iter(game.mobs)))  # ruff: ignore[private-member-access]
        dropped = dropped or any(
            f.stack.item.name == SLIME.drop for f in game.floating_items
        )
    assert dropped


def test_slimes_appear_at_night_only(content: Content) -> None:
    """They spawn near the player in the dark, and fade in daylight."""
    day = make_game(content)
    day.ticks = NOON
    for _ in range(600):
        day.tick(TickInput())
    assert not day.mobs
    night = make_game(content)
    night.ticks = MIDNIGHT
    for _ in range(600):
        night.tick(TickInput())
        night.player.vitals.health = MAX_HEALTH
    assert night.mobs
    assert sum(not m.kind.boss for m in night.mobs.values()) <= 3  # ruff: ignore[magic-value-comparison]
    night.ticks = NOON
    for _ in range(3000):
        night.tick(TickInput())
        night.player.vitals.health = MAX_HEALTH
    assert not night.mobs


def test_mobs_are_synced_to_clients(content: Content) -> None:
    """Clients get the creatures and the death counter."""
    from sch5n.server.server import Server  # ruff: ignore[import-outside-top-level]
    from tests.test_server import join, step  # ruff: ignore[import-outside-top-level]

    server = Server(
        content, flat_world(content), GameSetup(seed=1, spawn=(0, 0))
    )
    alice = join(server, content)
    add_slime(server.game, 600)
    server.game.player.deaths = 2
    step(server, [alice], 2)
    assert alice.world is not None
    assert [m.kind.name for m in alice.world.mobs.values()] == ["slime"]
    assert alice.world.player is not None
    assert alice.world.player.deaths == 2  # ruff: ignore[magic-value-comparison]


def test_no_creatures_appear_next_to_a_torch(content: Content) -> None:
    """Lights keep the dark away from where they shine."""
    game = make_game(content)
    game.ticks = MIDNIGHT
    torch = content.blocks.id_of("torch")
    for x in range(-60, 60, 4):
        game.tilemap.set(x, 9, torch)
    for _ in range(900):
        game.tick(TickInput())
    assert not game.mobs


def test_zombies_hit_harder_and_drop_cloth(content: Content) -> None:
    """A zombie is tougher than a slime; its touch hurts more."""
    zombie = KINDS["zombie"]
    assert zombie.health > SLIME.health
    assert zombie.damage > SLIME.damage
    assert zombie.drop in content.items
    game = make_game(content)
    mob = Mob(zombie, (game.player.body.x, GROUND - zombie.size[1]))
    game.mobs[500] = mob
    before = game.player.vitals.health
    game.tick(TickInput())
    assert game.player.vitals.health == before - zombie.damage


def test_both_kinds_spawn_at_night(content: Content) -> None:
    """Over many tries the dark brings slimes and zombies."""
    game = make_game(content)
    seen = {game._pick_kind().name for _ in range(200)}  # ruff: ignore[private-member-access]
    assert seen == {k.name for k in KINDS.values() if k.weight}


def test_the_boss_comes_once_and_drops_a_lot(content: Content) -> None:
    """At night one king slime may appear; killing it drops many balls."""
    from sch5n.game.session import BOSS  # ruff: ignore[import-outside-top-level]

    boss = KINDS[BOSS]
    assert boss.boss
    assert boss.weight == 0
    game = make_game(content)
    game.ticks = MIDNIGHT
    for _ in range(4000):
        game.tick(TickInput())
        game.player.vitals.health = MAX_HEALTH
        if any(m.kind.boss for m in game.mobs.values()):
            break
    assert sum(m.kind.boss for m in game.mobs.values()) == 1
    for _ in range(600):
        game.tick(TickInput())
        game.player.vitals.health = MAX_HEALTH
    assert sum(m.kind.boss for m in game.mobs.values()) <= 1
    game.announcements.clear()
    mob_id = next(i for i, m in game.mobs.items() if m.kind.boss)
    game._mob_died(mob_id)  # ruff: ignore[private-member-access]
    assert any(
        f.stack.item.name == boss.drop and f.stack.amount == boss.drop_amount
        for f in game.floating_items
    )
    assert any("fell" in text for text in game.announcements)


def test_bats_fly_to_the_player_without_falling(content: Content) -> None:
    """A bat hovers in the air and closes in on a player in sight."""
    bat = KINDS["bat"]
    assert bat.flying
    game = make_game(content)
    start = (game.player.body.x + 6 * TILE, GROUND - 6 * TILE)
    mob = Mob(bat, start)
    game.mobs[700] = mob
    for _ in range(20):
        game.tick(TickInput())
        game.player.vitals.health = MAX_HEALTH
    assert mob.body.y < GROUND - bat.size[1] - 2 * TILE  # still in the air
    gap = abs(mob.body.center[0] - game.player.body.center[0])
    assert gap < 6 * TILE


def test_a_bat_bite_is_light(content: Content) -> None:
    """A bat touching the player takes one health."""
    bat = KINDS["bat"]
    game = make_game(content)
    mob = Mob(bat, (game.player.body.x, game.player.body.y))
    game.mobs[701] = mob
    before = game.player.vitals.health
    game.tick(TickInput())
    assert game.player.vitals.health == before - bat.damage
