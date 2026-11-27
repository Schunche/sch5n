# Copyright (c) 2026 Schunche
"""GUI layout and widgets. Layout is plain geometry, testable without GL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor
from sch5n.game.inventory import HOTBAR_SIZE
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.game.config import UiConfig


class Align(StrEnum):
    """Which point of a widget its position refers to."""

    TOP_LEFT = "top_left"
    CENTER = "center"
    BOTTOM_RIGHT = "bottom_right"


def aligned_rect(
    pos: tuple[float, float], size: tuple[float, float], align: Align
) -> Rect:
    """Rectangle of `size` positioned by `align` at `pos`.

    Returns:
        Rect: The placed rectangle.

    """
    x, y = pos
    w, h = size
    match align:
        case Align.TOP_LEFT:
            return Rect(x, y, w, h)
        case Align.CENTER:
            return Rect(x - w / 2, y - h / 2, w, h)
        case Align.BOTTOM_RIGHT:
            return Rect(x - w, y - h, w, h)


@dataclass(slots=True)
class Button:
    """A clickable labelled rectangle."""

    id: str
    label: str
    rect: Rect

    def contains(self, pos: tuple[float, float]) -> bool:
        """Whether a screen position is on the button.

        Returns:
            bool: True if hovered.

        """
        return self.rect.contains_point(*pos)

    def draw(
        self,
        batch: SpriteBatch,
        text: TextRenderer,
        style: UiConfig,
        mouse: tuple[float, float],
    ) -> None:
        """Queue the button for drawing."""
        b = style.button
        r = self.rect
        rect = (r.x, r.y, r.w, r.h)
        inner = "button_hover" if self.contains(mouse) else "button_inner"
        batch.shape(rect, rgba(style.color(inner)), radius=b.border_radius)
        batch.shape(
            rect,
            rgba(style.color("button_border")),
            radius=b.border_radius,
            border=b.border_width,
        )
        text.draw(
            batch,
            self.label,
            r.center,
            b.font_size,
            rgba(style.color("text")),
            Anchor.CENTER,
        )


def button_at(
    button_id: str,
    label: str,
    pos: tuple[float, float],
    style: UiConfig,
    align: Align = Align.CENTER,
) -> Button:
    """Create a standard sized button.

    Returns:
        Button: The button.

    """
    size = (style.button.width, style.button.height)
    return Button(button_id, label, aligned_rect(pos, size, align))


def button_column(
    entries: Sequence[tuple[str, str]],
    center: tuple[float, float],
    spacing: float,
    style: UiConfig,
) -> list[Button]:
    """Buttons stacked vertically, the first one centered at `center`.

    Returns:
        list[Button]: The buttons, top to bottom.

    """
    return [
        button_at(
            button_id, label, (center[0], center[1] + i * spacing), style
        )
        for i, (button_id, label) in enumerate(entries)
    ]


def hit_button(buttons: list[Button], pos: tuple[float, float]) -> str | None:
    """Id of the button under `pos`.

    Returns:
        str | None: The button id, if any.

    """
    for button in buttons:
        if button.contains(pos):
            return button.id
    return None


@dataclass(frozen=True, slots=True)
class InventoryLayout:
    """Where each inventory slot is drawn on screen."""

    columns: int
    slot_count: int
    slot_size: float
    """Inner size of a slot."""
    padding: float
    """Gap between slots."""
    border: float
    origin: tuple[float, float]
    """Top left of the first slot's inner area."""

    @classmethod
    def create(
        cls, columns: int, slot_count: int, gui_size: int, style: UiConfig
    ) -> InventoryLayout:
        """Layout from the GUI settings.

        Returns:
            InventoryLayout: The layout.

        """
        border = style.slot.border_width
        return cls(
            columns=columns,
            slot_count=slot_count,
            slot_size=gui_size * 1.5,
            padding=style.slot.padding,
            border=border,
            origin=(style.outer_padding, style.outer_padding),
        )

    def slot_rect(self, index: int) -> Rect:
        """Inner rectangle of a slot.

        Returns:
            Rect: Screen rectangle.

        """
        step = self.slot_size + self.padding
        return Rect(
            self.origin[0] + (index % self.columns) * step,
            self.origin[1] + (index // self.columns) * step,
            self.slot_size,
            self.slot_size,
        )

    def slot_at(
        self, pos: tuple[float, float], *, hotbar_only: bool
    ) -> int | None:
        """Slot whose border box contains `pos`.

        Returns:
            int | None: Slot index, if any.

        """
        count = (
            min(HOTBAR_SIZE, self.slot_count)
            if hotbar_only
            else self.slot_count
        )
        for index in range(count):
            if (
                self
                .slot_rect(index)
                .inflated(self.border)
                .contains_point(*pos)
            ):
                return index
        return None

    def bounds(self, *, hotbar_only: bool) -> Rect:
        """Area covered by the visible slots, borders included.

        Returns:
            Rect: Screen rectangle.

        """
        count = (
            min(HOTBAR_SIZE, self.slot_count)
            if hotbar_only
            else self.slot_count
        )
        first = self.slot_rect(0)
        last = self.slot_rect(count - 1)
        right = self.slot_rect(min(self.columns, count) - 1)
        return Rect(
            first.x - self.border,
            first.y - self.border,
            right.right - first.x + 2 * self.border,
            last.bottom - first.y + 2 * self.border,
        )
