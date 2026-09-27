from sch5n.legacy.animation import Animation
from sch5n.legacy.item import Weapon
from sch5n.legacy.mob import Mob


class Enemy(Mob):
    def __init__(
        self,
        assets: dict[str, dict[str, Animation]],
        pos: list[float],
        weapon: Weapon | None = None,
    ) -> None:
        super().__init__(species="enemy", assets=assets, pos=pos)
        self.weapon: Weapon = weapon
