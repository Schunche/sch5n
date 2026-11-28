# Copyright (c) 2026 Schunche
"""Health, hunger and eating."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.config import GameMode
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.game.vitals import (
    HUNGER_SECONDS,
    MAX_HEALTH,
    MAX_HUNGER,
    STARVE_SECONDS,
    Vitals,
)
from tests.test_session import flat_world

if TYPE_CHECKING:
    from sch5n.game.content import Content

RATE = 60
HURT = 10
APPLES = 3


def test_hunger_drops_slowly() -> None:
    """One point is lost every `HUNGER_SECONDS`."""
    vitals = Vitals()
    for _ in range(HUNGER_SECONDS * RATE - 1):
        vitals.tick(RATE)
    assert vitals.hunger == MAX_HUNGER
    vitals.tick(RATE)
    assert vitals.hunger == MAX_HUNGER - 1


def test_starving_hurts_and_kills() -> None:
    """Without food health drains until the player dies."""
    vitals = Vitals(hunger=0)
    died = False
    for _ in range(MAX_HEALTH * STARVE_SECONDS * RATE):
        died = vitals.tick(RATE)
        if died:
            break
    assert died
    assert vitals.health <= 0


def test_a_fed_player_heals() -> None:
    """Health comes back while well fed."""
    vitals = Vitals(health=HURT)
    for _ in range(HURT * RATE):
        vitals.tick(RATE)
    assert vitals.health > HURT


def test_eating() -> None:
    """Food fills hunger up to the top, and a full player does not eat."""
    vitals = Vitals(hunger=10)
    assert vitals.eat(5)
    assert vitals.hunger == 15  # ruff: ignore[magic-value-comparison]
    assert vitals.eat(10)
    assert vitals.hunger == MAX_HUNGER
    assert not vitals.eat(5)
    assert not vitals.eat(0)


def test_admins_are_not_hungry() -> None:
    """Admins keep full vitals."""
    vitals = Vitals(health=3, hunger=0)
    assert not vitals.tick(RATE, immune=True)
    assert (vitals.health, vitals.hunger) == (MAX_HEALTH, MAX_HUNGER)


def make_game(content: Content, mode: GameMode = GameMode.SURVIVAL) -> Game:
    """Start a game on flat ground.

    Returns:
        Game: The game.

    """
    return Game(
        content,
        flat_world(content),
        GameSetup(seed=1, spawn=(0, 0), mode=mode),
    )


def test_eating_an_apple_in_game(content: Content) -> None:
    """Holding the use button eats one apple when hungry, not when full."""
    game = make_game(content)
    player = game.player
    player.inventory.slots[player.inventory.selected] = ItemStack(
        content.items["apple"], APPLES
    )
    game.tick(TickInput(use=True))
    assert player.inventory.held is not None
    assert player.inventory.held.amount == APPLES  # full: not eaten
    player.vitals.hunger = 5
    for _ in range(content.items["apple"].spec.use_time):
        game.tick(TickInput(use=True))
    assert player.vitals.hunger == 10  # ruff: ignore[magic-value-comparison]
    assert player.inventory.held is not None
    assert player.inventory.held.amount == 2  # ruff: ignore[magic-value-comparison]
    for _ in range(100):
        game.tick(TickInput(use=True))
    assert player.vitals.hunger == MAX_HUNGER


def test_starving_in_game_sends_the_player_home(content: Content) -> None:
    """A starved player respawns fed, and the game announces it."""
    game = make_game(content)
    player = game.player
    player.name = "ann"
    player.vitals.hunger = 0
    player.vitals.health = 1
    player.body.x += 300
    for _ in range(STARVE_SECONDS * RATE):
        game.tick(TickInput())
    assert player.vitals.health == MAX_HEALTH
    assert player.vitals.hunger == MAX_HUNGER
    assert game.announcements == ["ann starved"]


def test_admins_do_not_starve(content: Content) -> None:
    """Hunger does nothing in admin mode."""
    game = make_game(content, GameMode.ADMIN)
    game.player.vitals.hunger = 0
    game.tick(TickInput())
    assert game.player.vitals.hunger == MAX_HUNGER
