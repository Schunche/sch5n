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


@dataclass(frozen=True, slots=True)
class TableLayout:
    """A vertically scrolling table: a label column and button columns.

    Only rows lying completely inside `area` are visible.
    """

    rows: int
    area: Rect
    """Visible part of the table on screen."""
    row_height: float
    label_width: float
    cell_width: float
    columns: int = 2
    gap: float = 12
    padding: float = 3
    """Vertical space between a row's edge and its buttons."""

    @classmethod
    def centered(  # ruff: ignore[too-many-arguments]
        cls,
        rows: int,
        screen: tuple[float, float],
        top: float,
        bottom: float,
        *,
        row_height: float = 32,
        label_width: float = 200,
        cell_width: float = 160,
    ) -> TableLayout:
        """Table centered horizontally between `top` and `bottom`.

        Returns:
            TableLayout: The layout.

        """
        width = label_width + 2 * (cell_width + 12)
        return cls(
            rows=rows,
            area=Rect(
                (screen[0] - width) / 2, top, width, max(bottom - top, 0)
            ),
            row_height=row_height,
            label_width=label_width,
            cell_width=cell_width,
        )

    @property
    def max_scroll(self) -> float:
        """Largest useful scroll offset."""
        return max(0.0, self.rows * self.row_height - self.area.h)

    def clamp_scroll(self, scroll: float) -> float:
        """Limit a scroll offset to the content.

        Returns:
            float: Offset in [0, max_scroll].

        """
        return min(max(scroll, 0.0), self.max_scroll)

    def row_top(self, row: int, scroll: float) -> float:
        """Screen y of a row's top edge.

        Returns:
            float: Screen y.

        """
        return self.area.y + row * self.row_height - scroll

    def is_visible(self, row: int, scroll: float) -> bool:
        """Whether a row is completely inside the visible area.

        Returns:
            bool: True if it is drawn.

        """
        top = self.row_top(row, scroll)
        return (
            0 <= row < self.rows
            and top >= self.area.top
            and top + self.row_height <= self.area.bottom + 1e-6
        )

    def label_anchor(self, row: int, scroll: float) -> tuple[float, float]:
        """Left middle point of a row's label.

        Returns:
            tuple[float, float]: Screen position.

        """
        return (self.area.x, self.row_top(row, scroll) + self.row_height / 2)

    def cell_rect(self, row: int, column: int, scroll: float) -> Rect:
        """Button rectangle of a cell.

        Returns:
            Rect: Screen rectangle.

        """
        x = (
            self.area.x
            + self.label_width
            + column * (self.cell_width + self.gap)
            + self.gap
        )
        return Rect(
            x,
            self.row_top(row, scroll) + self.padding,
            self.cell_width,
            self.row_height - 2 * self.padding,
        )

    def cell_at(
        self, pos: tuple[float, float], scroll: float
    ) -> tuple[int, int] | None:
        """Visible cell under a screen position.

        Returns:
            tuple[int, int] | None: `(row, column)`, if any.

        """
        if not self.area.contains_point(*pos):
            return None
        row = int((pos[1] - self.area.y + scroll) // self.row_height)
        if not self.is_visible(row, scroll):
            return None
        for column in range(self.columns):
            if self.cell_rect(row, column, scroll).contains_point(*pos):
                return (row, column)
        return None
