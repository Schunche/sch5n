# Copyright (c) 2026 Schunche
"""Health and hunger of a player."""

from __future__ import annotations

from dataclasses import dataclass

MAX_HEALTH = 20
MAX_HUNGER = 20
HUNGER_SECONDS = 24
"""Seconds until a well fed player loses one point of hunger."""
REGEN_SECONDS = 4
"""Seconds between points of health regained while well fed."""
STARVE_SECONDS = 6
"""Seconds between points of health lost while starving."""
WELL_FED = 14
"""Hunger from which health comes back."""


@dataclass(slots=True)
class Vitals:
    """What keeps a player going. Admins need no food and cannot be hurt."""

    health: int = MAX_HEALTH
    hunger: int = MAX_HUNGER
    _hunger_ticks: int = 0
    _health_ticks: int = 0

    def eat(self, food: int) -> bool:
        """Eat something worth `food` points.

        Returns:
            bool: Whether it was eaten; a full player does not eat.

        """
        if food <= 0 or self.hunger >= MAX_HUNGER:
            return False
        self.hunger = min(MAX_HUNGER, self.hunger + food)
        return True

    def restore(self) -> None:
        """Bring health and hunger back to the top, like after dying."""
        self.health = MAX_HEALTH
        self.hunger = MAX_HUNGER
        self._hunger_ticks = self._health_ticks = 0

    def tick(self, tick_rate: int, *, immune: bool = False) -> bool:
        """Advance one tick.

        Returns:
            bool: Whether the player died of hunger.

        """
        if immune:
            self.restore()
            return False
        self._hunger_ticks += 1
        if self._hunger_ticks >= HUNGER_SECONDS * tick_rate:
            self._hunger_ticks = 0
            self.hunger = max(0, self.hunger - 1)
        self._health_ticks += 1
        if self.hunger == 0:
            if self._health_ticks >= STARVE_SECONDS * tick_rate:
                self._health_ticks = 0
                self.health -= 1
        elif self.hunger >= WELL_FED and self.health < MAX_HEALTH:
            if self._health_ticks >= REGEN_SECONDS * tick_rate:
                self._health_ticks = 0
                self.health += 1
        else:
            self._health_ticks = 0
        return self.health <= 0
