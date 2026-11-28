# Copyright (c) 2026 Schunche
"""The recipe book: every recipe, with what it needs and what you have."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.game.inventory import ItemStack
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from sch5n.client.hud import Hud
    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.client.style import Style
    from sch5n.game.content import Content, ItemDef, RecipeSpec
    from sch5n.game.inventory import Inventory

MIN_WIDTH = 220
MAX_WIDTH = 420
PADDING = 8
TITLE_SIZE = 16
SMALL_SIZE = 12
SCROLL_ROWS = 1


@dataclass(frozen=True, slots=True)
class Need:
    """An ingredient: any of `choices`, `amount` of them."""

    choices: tuple[ItemDef, ...]
    amount: int


@dataclass(frozen=True, slots=True)
class Entry:
    """A recipe prepared for display."""

    result: ItemDef
    amount: int
    needs: tuple[Need, ...]
    grid: str
    """Smallest grid it fits, like `2x2`, empty for shapeless recipes."""
    station: str = ""
    """Station it needs, like `furnace`."""


def needs_of(recipe: RecipeSpec, content: Content) -> tuple[Need, ...]:
    """List what a recipe uses, each ingredient once with its amount.

    Returns:
        tuple[Need, ...]: The ingredients in order of first appearance.

    """
    counts: dict[tuple[str, ...], int] = {}
    if recipe.pattern:
        for symbol in "".join(recipe.pattern):
            if symbol != " ":
                key = recipe.choices(symbol)
                counts[key] = counts.get(key, 0) + 1
    else:
        for name in recipe.ingredients:
            counts[name,] = counts.get((name,), 0) + 1
    return tuple(
        Need(tuple(content.items[name] for name in names), amount)
        for names, amount in counts.items()
    )


def entries(content: Content) -> list[Entry]:
    """Prepare every recipe.

    Returns:
        list[Entry]: One entry per recipe, in the order of the file.

    """
    return [
        Entry(
            content.items[recipe.result.item],
            recipe.result.amount,
            needs_of(recipe, content),
            f"{len(recipe.pattern[0])}x{len(recipe.pattern)}"
            if recipe.pattern
            else "",
            recipe.station or "",
        )
        for recipe in content.recipes
    ]


def have(inventory: Inventory) -> dict[str, int]:
    """Count the items in the inventory's slots.

    Returns:
        dict[str, int]: Amount by item name.

    """
    totals: dict[str, int] = {}
    for slot in inventory:
        if slot is not None:
            name = slot.item.name
            totals[name] = totals.get(name, 0) + slot.amount
    return totals


def can_make(entry: Entry, totals: dict[str, int]) -> bool:
    """Whether the inventory holds everything a recipe uses.

    Choices share the stock, so this is exact for recipes whose symbols
    do not overlap in what they accept, and generous otherwise.

    Returns:
        bool: True if all ingredients are there.

    """
    return all(
        sum(totals.get(item.name, 0) for item in need.choices) >= need.amount
        for need in entry.needs
    )


class RecipeBook:
    """A scrolling list of recipes beside the crafting grid."""

    def __init__(self, content: Content) -> None:
        """Prepare the recipes."""
        self.entries = entries(content)
        self.open = False
        self.scroll = 0
        """Index of the first row shown."""
        self.rect = Rect(0, 0, 0, 0)
        self.row_height = 0.0

    def place(
        self, left: float, top: float, screen: tuple[int, int], row: float
    ) -> None:
        """Fit the list between a corner and the screen's bottom right."""
        width = min(MAX_WIDTH, screen[0] - left - PADDING)
        height = screen[1] - top - 3 * PADDING - row
        self.row_height = row
        self.rect = Rect(left, top, max(0, width), max(0, height))
        self.scroll = max(0, min(self.scroll, self.max_scroll))

    @property
    def usable(self) -> bool:
        """Whether there is room to draw it."""
        return self.rect.w >= MIN_WIDTH and self.visible_rows > 0

    @property
    def visible_rows(self) -> int:
        """Rows that fit under the title."""
        if self.row_height <= 0:
            return 0
        return int((self.rect.h - 2 * PADDING - TITLE_SIZE) // self.row_height)

    @property
    def max_scroll(self) -> int:
        """Largest first row."""
        return max(0, len(self.entries) - self.visible_rows)

    def scroll_by(self, rows: int) -> None:
        """Move the list, keeping it within its bounds."""
        self.scroll = max(0, min(self.max_scroll, self.scroll + rows))

    def contains(self, pos: tuple[float, float]) -> bool:
        """Whether a screen position is on the open list.

        Returns:
            bool: True if the book is open there.

        """
        return self.open and self.usable and self.rect.contains_point(*pos)

    def draw(
        self,
        batch: SpriteBatch,
        text: TextRenderer,
        style: Style,
        hud: Hud,
        inventory: Inventory,
    ) -> None:
        """Draw the list. Recipes that can be made now are outlined."""
        if not (self.open and self.usable):
            return
        rect = self.rect
        batch.shape(
            (rect.x, rect.y, rect.w, rect.h),
            rgba(style.color("button_inner"), 0.85),
            radius=6,
        )
        text.draw(
            batch,
            "Recipes",
            (rect.x + PADDING, rect.y + PADDING),
            TextStyle(size=TITLE_SIZE, color=rgba(style.color("accent"))),
        )
        totals = have(inventory)
        top = rect.y + 2 * PADDING + TITLE_SIZE
        shown = self.entries[self.scroll : self.scroll + self.visible_rows]
        for index, entry in enumerate(shown):
            row = Rect(
                rect.x + PADDING,
                top + index * self.row_height,
                rect.w - 2 * PADDING,
                self.row_height - 2,
            )
            if can_make(entry, totals):
                batch.shape(
                    (row.x, row.y, row.w, row.h),
                    rgba(style.color("accent")),
                    radius=4,
                    border=1.5,
                )
            self._draw_entry(batch, text, style, hud, entry, row)

    def _draw_entry(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        batch: SpriteBatch,
        text: TextRenderer,
        style: Style,
        hud: Hud,
        entry: Entry,
        row: Rect,
    ) -> None:
        step = self.row_height
        cy = row.y + row.h / 2
        hud.draw_stack(
            batch,
            ItemStack(entry.result, entry.amount),
            (row.x + step / 2, cy),
        )
        text.draw(
            batch,
            "<",
            (row.x + step + 4, cy),
            TextStyle(
                size=TITLE_SIZE,
                color=rgba(style.color("text_dim")),
                anchor=Anchor.MIDDLE_LEFT,
            ),
        )
        x = row.x + step * 1.6
        for need in entry.needs:
            if x + step > row.right:
                break
            hud.draw_stack(
                batch,
                ItemStack(need.choices[0], need.amount),
                (x + step / 2, cy),
            )
            x += step
        label = entry.station.capitalize() or entry.grid
        if label:
            text.draw(
                batch,
                label,
                (row.right - 2, row.bottom - 2),
                TextStyle(
                    size=SMALL_SIZE,
                    color=rgba(style.color("text_dim")),
                    anchor=Anchor.BOTTOM_RIGHT,
                ),
            )
