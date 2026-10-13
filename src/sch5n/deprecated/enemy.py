# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING

from sch5n.deprecated.mob import Mob

if TYPE_CHECKING:
    from sch5n.deprecated.animation import Animation
    from sch5n.deprecated.item import Weapon


class Enemy(Mob):
    def __init__(
        self,
        assets: dict[str, dict[str, Animation]],
        pos: list[float],
        weapon: Weapon | None = None,
    ) -> None:
        super().__init__(species="enemy", assets=assets, pos=pos)
        self.weapon: Weapon = weapon
