# Copyright (c) 2026 Schunche
"""GUI layout and widgets. Layout is plain geometry, testable without GL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.textedit import TextEdit
from sch5n.game.inventory import HOTBAR_SIZE
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.client.style import Style


TABLE_LABEL_WIDTH = 200
TABLE_CELL_WIDTH = 160
TABLE_GAP = 12
TABLE_COLUMNS = 2
TABLE_WIDTH = TABLE_LABEL_WIDTH + TABLE_COLUMNS * (
    TABLE_CELL_WIDTH + TABLE_GAP
)
PANEL_RADIUS = 10
FIELD_PADDING = 10
FIELD_LABEL_SIZE = 14
PANEL_BORDER = 2
CRAFTING_GAP = 16
"""Pixels between the inventory slots and the crafting grid."""


class Align(StrEnum):
    """Which point of a widget its position refers to."""

    TOP_LEFT = "top_left"
    CENTER = "center"
    BOTTOM_RIGHT = "bottom_right"


def aligned_rect(
    pos: tuple[float, float],
    size: tuple[float, float],
    align: Align = Align.TOP_LEFT,
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
        style: Style,
        mouse: tuple[float, float],
        *,
        selected: bool = False,
    ) -> None:
        """Queue the button for drawing. `selected` adds an accent border."""
        b = style.button
        r = self.rect
        rect = (r.x, r.y, r.w, r.h)
        inner = "button_hover" if self.contains(mouse) else "button_inner"
        batch.shape(rect, rgba(style.color(inner)), radius=b.border_radius)
        border = "accent" if selected else "button_border"
        batch.shape(
            rect,
            rgba(style.color(border)),
            radius=b.border_radius,
            border=b.border_width if selected else b.border_width / 2,
        )
        text.draw(
            batch,
            self.label,
            r.center,
            TextStyle(
                size=b.font_size,
                color=rgba(style.color("text")),
                anchor=Anchor.CENTER,
            ),
        )


def draw_panel(batch: SpriteBatch, rect: Rect, style: Style) -> None:
    """Queue a translucent rounded panel with a thin border."""
    box = (rect.x, rect.y, rect.w, rect.h)
    batch.shape(box, rgba(style.color("panel")), radius=PANEL_RADIUS)
    batch.shape(
        box,
        rgba(style.color("button_border"), 0.6),
        radius=PANEL_RADIUS,
        border=PANEL_BORDER,
    )


def button_at(
    button_id: str,
    label: str,
    pos: tuple[float, float],
    style: Style,
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
    style: Style,
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


class TextField(TextEdit):
    """A one line text input with a label above it."""

    def __init__(
        self,
        id: str,  # ruff: ignore[builtin-argument-shadowing]
        label: str,
        rect: Rect,
        text: str = "",
        max_length: int = 64,
    ) -> None:
        """Make a field showing `text`."""
        super().__init__(text, max_length)
        self.id = id
        self.label = label
        self.rect = rect

    def contains(self, pos: tuple[float, float]) -> bool:
        """Whether a screen position is on the field.

        Returns:
            bool: True if hovered.

        """
        return self.rect.contains_point(*pos)

    def draw(
        self,
        batch: SpriteBatch,
        text: TextRenderer,
        style: Style,
        *,
        focused: bool,
        caret: bool,
    ) -> None:
        """Queue the field. `caret` shows the blinking text cursor."""
        b = style.button
        r = self.rect
        box = (r.x, r.y, r.w, r.h)
        batch.shape(box, rgba(style.color("button_inner")), radius=4)
        batch.shape(
            box,
            rgba(style.color("accent" if focused else "button_border")),
            radius=4,
            border=b.border_width / 2,
        )
        text.draw(
            batch,
            self.label,
            (r.x, r.y - 4),
            TextStyle(
                size=FIELD_LABEL_SIZE,
                color=rgba(style.color("text_dim")),
                anchor=Anchor.BOTTOM_LEFT,
            ),
        )
        left = r.x + FIELD_PADDING
        start, end = self.selection
        if focused and start != end:
            x0 = left + (
                text.measure(self.text[:start], b.font_size)[0] if start else 0
            )
            x1 = left + text.measure(self.text[:end], b.font_size)[0]
            batch.shape(
                (x0, r.y + 4, x1 - x0, r.h - 8),
                rgba(style.color("accent"), 0.4),
            )
        text.draw(
            batch,
            self.text,
            (left, r.center[1]),
            TextStyle(
                size=b.font_size,
                color=rgba(style.color("text")),
                anchor=Anchor.MIDDLE_LEFT,
            ),
        )
        if focused and caret:
            x = left + (
                text.measure(self.text[: self.caret], b.font_size)[0]
                if self.caret
                else 0
            )
            batch.shape((x, r.y + 5, 2, r.h - 10), rgba(style.color("text")))


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
        cls, columns: int, slot_count: int, gui_size: int, style: Style
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
class CraftingLayout:
    """Where the crafting grid and its result are drawn.

    They sit under the slots, the grid left of an arrow and the result.
    """

    inventory: InventoryLayout
    side: int
    """Slots along one side of the grid."""

    @property
    def _step(self) -> float:
        return self.inventory.slot_size + self.inventory.padding

    @property
    def _top(self) -> float:
        slots = self.inventory.bounds(hotbar_only=False)
        return slots.bottom + CRAFTING_GAP + self.inventory.border

    def slot_rect(self, index: int) -> Rect:
        """Inner rectangle of a grid slot.

        Returns:
            Rect: Screen rectangle.

        """
        row, column = divmod(index, self.side)
        size = self.inventory.slot_size
        return Rect(
            self.inventory.origin[0] + column * self._step,
            self._top + row * self._step,
            size,
            size,
        )

    @property
    def result_rect(self) -> Rect:
        """Inner rectangle of the result slot."""
        size = self.inventory.slot_size
        return Rect(
            self.inventory.origin[0] + (self.side + 1) * self._step,
            self._top + (self.side - 1) * self._step / 2,
            size,
            size,
        )

    @property
    def station_pos(self) -> tuple[float, float]:
        """Left middle of the note naming the station that enlarges it."""
        result = self.result_rect
        return (result.right + CRAFTING_GAP, result.center[1])

    @property
    def arrow_center(self) -> tuple[float, float]:
        """Middle of the space between the grid and the result."""
        left = self.slot_rect(self.side - 1).right
        return ((left + self.result_rect.x) / 2, self.result_rect.center[1])

    def slot_at(self, pos: tuple[float, float]) -> int | None:
        """Grid slot whose border box contains `pos`.

        Returns:
            int | None: Slot index, if any.

        """
        border = self.inventory.border
        for index in range(self.side**2):
            if self.slot_rect(index).inflated(border).contains_point(*pos):
                return index
        return None

    def on_result(self, pos: tuple[float, float]) -> bool:
        """Whether `pos` is on the result slot.

        Returns:
            bool: True over its border box.

        """
        box = self.result_rect.inflated(self.inventory.border)
        return box.contains_point(*pos)

    def bounds(self) -> Rect:
        """Area covered by the grid and the result, borders included.

        Returns:
            Rect: Screen rectangle.

        """
        border = self.inventory.border
        first = self.slot_rect(0)
        last = self.slot_rect(self.side**2 - 1)
        return Rect(
            first.x - border,
            first.y - border,
            self.result_rect.right - first.x + 2 * border,
            last.bottom - first.y + 2 * border,
        )


@dataclass(frozen=True, slots=True)
class GridLayout:
    """A grid of square cells, scrolled vertically by whole rows."""

    count: int
    columns: int
    visible_rows: int
    origin: tuple[float, float]
    """Top left of the first visible cell."""
    cell: float
    gap: float

    @property
    def rows(self) -> int:
        """Rows needed for every cell."""
        return -(-self.count // self.columns)

    @property
    def max_scroll(self) -> int:
        """Largest useful number of rows scrolled past."""
        return max(0, self.rows - self.visible_rows)

    @property
    def area(self) -> Rect:
        """Screen rectangle of the visible cells."""
        step = self.cell + self.gap
        shown = min(self.rows, self.visible_rows)
        return Rect(
            *self.origin,
            self.columns * step - self.gap,
            max(shown * step - self.gap, 0),
        )

    def clamp_scroll(self, scroll: int) -> int:
        """Limit a scroll offset to the content.

        Returns:
            int: Rows in [0, max_scroll].

        """
        return min(max(scroll, 0), self.max_scroll)

    def scroll_to(self, index: int, scroll: int) -> int:
        """Scroll as little as needed to show a cell.

        Returns:
            int: The new scroll offset.

        """
        row = index // self.columns
        lowest = row - self.visible_rows + 1
        return self.clamp_scroll(min(max(scroll, lowest), row))

    def visible(self, scroll: int) -> range:
        """Cells shown at a scroll offset.

        Returns:
            range: Their indices.

        """
        first = scroll * self.columns
        last = (scroll + self.visible_rows) * self.columns
        return range(first, min(last, self.count))

    def cell_rect(self, index: int, scroll: int) -> Rect:
        """Screen rectangle of a cell.

        Returns:
            Rect: The cell, which may be outside the visible area.

        """
        row, column = divmod(index, self.columns)
        step = self.cell + self.gap
        return Rect(
            self.origin[0] + column * step,
            self.origin[1] + (row - scroll) * step,
            self.cell,
            self.cell,
        )

    def cell_at(self, pos: tuple[float, float], scroll: int) -> int | None:
        """Visible cell under a screen position.

        Returns:
            int | None: Its index, if any.

        """
        for index in self.visible(scroll):
            if self.cell_rect(index, scroll).contains_point(*pos):
                return index
        return None


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
    def centered(
        cls,
        rows: int,
        screen: tuple[float, float],
        top: float,
        bottom: float,
        row_height: float = 32,
    ) -> TableLayout:
        """Lay out a table with the default column widths.

        It is centered horizontally and fills `top` to `bottom`.

        Returns:
            TableLayout: The layout.

        """
        left = (screen[0] - TABLE_WIDTH) / 2
        return cls.placed(rows, left, top, bottom, row_height)

    @classmethod
    def placed(
        cls,
        rows: int,
        left: float,
        top: float,
        bottom: float,
        row_height: float = 32,
    ) -> TableLayout:
        """Lay out a table with the default column widths at `left`.

        Returns:
            TableLayout: The layout.

        """
        return cls(
            rows=rows,
            area=Rect(left, top, TABLE_WIDTH, max(bottom - top, 0)),
            row_height=row_height,
            label_width=TABLE_LABEL_WIDTH,
            cell_width=TABLE_CELL_WIDTH,
            columns=TABLE_COLUMNS,
            gap=TABLE_GAP,
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

    def span_rect(self, row: int, scroll: float) -> Rect:
        """Rectangle covering every button column of a row.

        Returns:
            Rect: Screen rectangle.

        """
        first = self.cell_rect(row, 0, scroll)
        last = self.cell_rect(row, self.columns - 1, scroll)
        return Rect(first.x, first.y, last.right - first.x, first.h)

    def row_at(self, pos: tuple[float, float], scroll: float) -> int | None:
        """Visible row under a screen position.

        Returns:
            int | None: Row index, if any.

        """
        if not self.area.contains_point(*pos):
            return None
        row = int((pos[1] - self.area.y + scroll) // self.row_height)
        return row if self.is_visible(row, scroll) else None

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
