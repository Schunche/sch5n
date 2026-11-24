# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass, field
from warnings import deprecated
lazy import math

lazy import pygame

from sch5n.deprecated.loader import NAME_SPACE, SETTINGS
lazy from sch5n.deprecated.item_surface import ITEM_ICON


@deprecated("Create substitute")
@dataclass(repr=False)
class Item:
    """Basic item class."""

    id: int
    name: str
    description: str | None = field(default=None)
    use_time: int = field(default=int(SETTINGS.FPS // 2))
    amount: int = field(default=1)
    max_amount: int = field(default=2**10)

    def get_name(self) -> str:  # ruff: ignore[undocumented-public-method]
        return self.name.title()

    def render_icon(  # ruff: ignore[undocumented-public-method]
        self, surface: pygame.Surface, pos: tuple[int, int]
    ) -> None:
        surface.blit(ITEM_ICON[self.id], pos)

        # The amount number
        if self.max_amount != 1:
            font: pygame.font.Font = pygame.font.SysFont("arial", 12)

            text_rendered = font.render(
                str(self.amount),
                antialias=True,
                color=NAME_SPACE["color"]["text"],
            )
            text_rect: pygame.Rect = text_rendered.get_rect()
            text_rect.bottomright = (
                pos[0] + SETTINGS.gui_size,
                pos[1] + SETTINGS.gui_size,
            )

            surface.blit(text_rendered, text_rect)


@deprecated("Create substitute")
@dataclass
class Weapon(Item):  # ruff: ignore[undocumented-public-class]
    damage: int = field(default=5)  # This is strange
    knockback: int | None = field(default=5)


@deprecated("Create substitute")
@dataclass
class ReforgeableItem(Item):  # ruff: ignore[undocumented-public-class]
    reforge: str | None = field(default=None)

    def __post_init__(self) -> None:  # ruff: ignore[undocumented-magic-method]
        self.amount: int = 1
        self.max_amount: int = 1

    def get_name(self) -> str:  # ruff: ignore[undocumented-public-method]
        if self.reforge is None:
            return super().get_name()
        return f"{self.reforge.title()} {super().get_name()}"


@deprecated("Create substitute")
@dataclass
class Tool(Item):  # ruff: ignore[undocumented-public-class]
    tool_type: dict[str, int] = field(default_factory=lambda: {"pickaxe": 5})


@deprecated("Create substitute")
@dataclass
class SwingWeapon(Weapon, ReforgeableItem):  # ruff: ignore[undocumented-public-class]
    def __post_init__(self) -> None:  # ruff: ignore[undocumented-magic-method]
        super().__post_init__()

        self.frame: int | None = None
        self.minAngle: float = math.pi * 2 / 3
        self.maxAngle: float = math.pi * 2 / 3 - math.pi

        """
        if self.frame is None:
            self.angle = None
        else:
            self.angle = self.minAngle + \
                (self.maxAngle - self.minAngle) * self.frame
        """


@deprecated("Create substitute")
@dataclass(kw_only=True)
class SwingTool(SwingWeapon, Tool):  # ruff: ignore[undocumented-public-class]
    pass


@deprecated("Create substitute")
@dataclass
class PlaceableItem(Item):  # ruff: ignore[undocumented-public-class]
    def get_name(self) -> str:  # ruff: ignore[undocumented-public-method]
        return f"{super().get_name()} (x{self.amount!s})"


@deprecated("Create substitute")
@dataclass(kw_only=True)
class Block(PlaceableItem):  # ruff: ignore[undocumented-public-class]
    pass
