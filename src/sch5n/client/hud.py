# Copyright (c) 2026 Schunche
"""Heads-up display: hotbar, inventory and the item held by the cursor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.game.inventory import HOTBAR_SIZE
from sch5n.math.rect import Rect

if TYPE_CHECKING:
    from sch5n.client.assets import ClientAssets
    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.client.style import Style
    from sch5n.client.ui import CraftingLayout, InventoryLayout
    from sch5n.game.content import ItemDef
    from sch5n.game.inventory import Inventory, ItemStack


TOOLTIP_PADDING = 10
TOOLTIP_GAP = 4
"""Pixels between tooltip lines."""
TOOLTIP_OFFSET = (18, 18)
"""Where the tooltip sits relative to the mouse."""
TOOLTIP_TITLE_SIZE = 16
TOOLTIP_TEXT_SIZE = 14
TOOLTIP_RADIUS = 6


class LineKind(StrEnum):
    """How a tooltip line looks."""

    TITLE = "title"
    TEXT = "text"
    STAT = "stat"


@dataclass(frozen=True, slots=True)
class TooltipLine:
    """One line of an item tooltip."""

    text: str
    kind: LineKind = LineKind.TEXT


def item_tooltip(stack: ItemStack, tick_rate: int) -> list[TooltipLine]:
    """Describe a hovered item: name, description and what it does.

    Returns:
        list[TooltipLine]: The lines, title first.

    """
    item = stack.item
    spec = item.spec
    lines = [TooltipLine(stack.display_name, LineKind.TITLE)]
    if spec.description:
        lines.append(TooltipLine(spec.description))
    lines.extend(
        TooltipLine(f"{kind.capitalize()} power {power}", LineKind.STAT)
        for kind, power in spec.tool_power.items()
    )
    if item.is_tool:
        seconds = spec.use_time / tick_rate
        lines.append(TooltipLine(f"Swings in {seconds:.2f} s", LineKind.STAT))
    if item.is_tool and spec.damage:
        lines.append(TooltipLine(f"Damage {spec.damage}", LineKind.STAT))
    if spec.ammo:
        lines.append(
            TooltipLine(
                f"Shoots {spec.ammo}s for {spec.shot_damage} damage",
                LineKind.STAT,
            )
        )
    if spec.armor:
        lines.append(TooltipLine(f"Defense {spec.defense}", LineKind.STAT))
    if spec.food:
        lines.append(
            TooltipLine(f"Restores {spec.food} hunger", LineKind.STAT)
        )
    if item.is_stackable:
        lines.append(
            TooltipLine(f"Stacks up to {spec.max_stack}", LineKind.STAT)
        )
    return lines


def tooltip_rect(
    size: tuple[float, float],
    mouse: tuple[float, float],
    screen: tuple[float, float],
) -> Rect:
    """Place a tooltip of `size` next to the mouse, inside the screen.

    It flips to the other side of the mouse where it would not fit.

    Returns:
        Rect: The tooltip's rectangle.

    """
    w, h = size
    x, y = mouse[0] + TOOLTIP_OFFSET[0], mouse[1] + TOOLTIP_OFFSET[1]
    if x + w > screen[0]:
        x = mouse[0] - TOOLTIP_OFFSET[0] - w
    if y + h > screen[1]:
        y = mouse[1] - TOOLTIP_OFFSET[1] - h
    return Rect(max(0.0, x), max(0.0, y), w, h)


@dataclass(frozen=True, slots=True)
class VitalsLook:
    """Where and how the health and hunger bars are drawn."""

    center_x: float
    bottom: float


VITAL_COLORS = {"health": (214, 64, 64), "hunger": (222, 148, 56)}
BAR_WIDTH = 150
BAR_HEIGHT = 14
BAR_GAP = 16


def draw_vitals(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
    batch: SpriteBatch,
    text: TextRenderer,
    style: Style,
    where: VitalsLook,
    health: tuple[int, int],
    hunger: tuple[int, int],
) -> None:
    """Draw two bars, health left and hunger right, with their numbers.

    `health` and `hunger` are current and maximum values.
    """
    bars = (("health", health), ("hunger", hunger))
    left = where.center_x - BAR_GAP / 2 - BAR_WIDTH
    for index, (name, (value, top)) in enumerate(bars):
        x = left + index * (BAR_WIDTH + BAR_GAP)
        y = where.bottom - BAR_HEIGHT
        box = (x, y, BAR_WIDTH, BAR_HEIGHT)
        batch.shape(box, rgba(style.color("button_inner"), 0.8), radius=3)
        fill = BAR_WIDTH * max(0, min(value, top)) / max(1, top)
        if fill > 0:
            batch.shape(
                (x, y, fill, BAR_HEIGHT),
                rgba(VITAL_COLORS[name]),
                radius=3,
            )
        batch.shape(
            box, rgba(style.color("button_border")), radius=3, border=1.5
        )
        text.draw(
            batch,
            f"{value}",
            (x + BAR_WIDTH / 2, y + BAR_HEIGHT / 2),
            TextStyle(
                size=12,
                color=rgba(style.color("text")),
                anchor=Anchor.CENTER,
            ),
        )


@dataclass(frozen=True, slots=True)
class SlotLook:
    """How a slot box is drawn."""

    hovered: bool = False
    selected: bool = False
    alpha: float = 1.0
    """Opacity of its fill."""


PLAIN_SLOT = SlotLook()


class Hud:
    """Draws the inventory GUI."""

    def __init__(
        self,
        assets: ClientAssets,
        text: TextRenderer,
        style: Style,
        gui_size: int,
    ) -> None:
        """Create the HUD renderer."""
        self.assets = assets
        self.text = text
        self.style = style
        self.gui_size = gui_size

    def draw_stack(
        self, batch: SpriteBatch, stack: ItemStack, center: tuple[float, float]
    ) -> None:
        """Draw an item icon with its amount, centered at `center`."""
        size = self.gui_size
        x, y = round(center[0] - size / 2), round(center[1] - size / 2)
        region = self.assets.slot_icon(stack.item, size * 3 // 2)
        w, h = region.width, region.height
        batch.sprite(
            self.assets.atlas,
            (round(center[0] - w / 2), round(center[1] - h / 2), w, h),
            region,
        )
        if stack.amount > 1:
            self.text.draw(
                batch,
                str(stack.amount),
                (x + size, y + size),
                TextStyle(
                    size=self.style.slot.amount_font_size,
                    color=rgba(self.style.color("text")),
                    anchor=Anchor.BOTTOM_RIGHT,
                ),
            )

    def draw_inventory(
        self,
        batch: SpriteBatch,
        layout: InventoryLayout,
        inventory: Inventory,
        mouse: tuple[float, float],
        *,
        full: bool,
    ) -> None:
        """Draw the hotbar, or every slot when `full`."""
        style = self.style
        hovered = layout.slot_at(mouse, hotbar_only=not full)
        alpha = 1.0 if full else style.slot.alpha / 255
        count = len(inventory) if full else HOTBAR_SIZE
        for index in range(count):
            self.draw_slot(
                batch,
                layout.slot_rect(index),
                inventory[index],
                layout.border,
                SlotLook(index == hovered, index == inventory.selected, alpha),
            )

        if not full:
            held = inventory[inventory.selected]
            if held is not None:
                bounds = layout.bounds(hotbar_only=True)
                self.text.draw(
                    batch,
                    held.display_name,
                    (bounds.x, bounds.bottom + 6),
                    TextStyle(
                        size=style.button.font_size,
                        color=rgba(style.color("text")),
                    ),
                )

    def draw_slot(
        self,
        batch: SpriteBatch,
        inner: Rect,
        stack: ItemStack | None,
        border_width: float,
        look: SlotLook = PLAIN_SLOT,
    ) -> None:
        """Draw one slot box and what is in it."""
        style = self.style
        border = inner.inflated(border_width)
        fill = "button_hover" if look.hovered else "button_inner"
        batch.shape(
            (inner.x, inner.y, inner.w, inner.h),
            rgba(style.color(fill), look.alpha),
        )
        edge = "accent" if look.selected else "button_border"
        batch.shape(
            (border.x, border.y, border.w, border.h),
            rgba(style.color(edge)),
            radius=style.button.border_radius,
            border=style.button.border_width,
        )
        if stack is not None:
            self.draw_stack(batch, stack, inner.center)

    def draw_crafting(
        self,
        batch: SpriteBatch,
        layout: CraftingLayout,
        inventory: Inventory,
        result: ItemStack | None,
        mouse: tuple[float, float],
    ) -> None:
        """Draw the crafting grid, an arrow and the result."""
        hovered = layout.slot_at(mouse)
        border = layout.inventory.border
        for index, stack in enumerate(inventory.crafting):
            self.draw_slot(
                batch,
                layout.slot_rect(index),
                stack,
                border,
                SlotLook(hovered=index == hovered),
            )
        arrow = self.assets.arrow
        x, y = layout.arrow_center
        batch.sprite(
            self.assets.atlas,
            (
                round(x - arrow.width / 2),
                round(y - arrow.height / 2),
                arrow.width,
                arrow.height,
            ),
            arrow,
            rgba(self.style.color("text")),
        )
        self.draw_slot(
            batch,
            layout.result_rect,
            result,
            border,
            SlotLook(hovered=layout.on_result(mouse)),
        )

    def draw_station(
        self, batch: SpriteBatch, layout: CraftingLayout, station: ItemDef
    ) -> None:
        """Show which station enlarges the grid: its icon and name."""
        x, y = layout.station_pos
        size = layout.inventory.slot_size
        icon = self.assets.slot_icon(station, round(size))
        batch.sprite(
            self.assets.atlas,
            (round(x), round(y - icon.height / 2), icon.width, icon.height),
            icon,
        )
        self.text.draw(
            batch,
            station.spec.name,
            (x + icon.width + TOOLTIP_PADDING, y),
            TextStyle(
                size=self.style.button.font_size,
                color=rgba(self.style.color("accent")),
                anchor=Anchor.MIDDLE_LEFT,
            ),
        )

    def draw_tooltip(
        self,
        batch: SpriteBatch,
        lines: list[TooltipLine],
        mouse: tuple[float, float],
        screen: tuple[float, float],
    ) -> None:
        """Draw a tooltip panel next to the mouse."""
        style = self.style
        styles = {
            LineKind.TITLE: TextStyle(
                TOOLTIP_TITLE_SIZE, rgba(style.color("accent"))
            ),
            LineKind.TEXT: TextStyle(
                TOOLTIP_TEXT_SIZE, rgba(style.color("text"))
            ),
            LineKind.STAT: TextStyle(
                TOOLTIP_TEXT_SIZE, rgba(style.color("text_dim"))
            ),
        }
        sizes = [
            self.text.measure(line.text, styles[line.kind].size)
            for line in lines
        ]
        width = max(w for w, _ in sizes) + 2 * TOOLTIP_PADDING
        height = (
            sum(h for _, h in sizes)
            + TOOLTIP_GAP * (len(lines) - 1)
            + 2 * TOOLTIP_PADDING
        )
        rect = tooltip_rect((width, height), mouse, screen)
        box = (rect.x, rect.y, rect.w, rect.h)
        batch.shape(box, rgba(style.color("panel")), radius=TOOLTIP_RADIUS)
        batch.shape(
            box,
            rgba(style.color("button_border")),
            radius=TOOLTIP_RADIUS,
            border=1,
        )
        y = rect.y + TOOLTIP_PADDING
        for line, (_, h) in zip(lines, sizes, strict=True):
            self.text.draw(
                batch,
                line.text,
                (rect.x + TOOLTIP_PADDING, y),
                styles[line.kind],
            )
            y += h + TOOLTIP_GAP

    def draw_cursor_stack(
        self,
        batch: SpriteBatch,
        inventory: Inventory,
        mouse: tuple[float, float],
    ) -> None:
        """Draw the stack held by the cursor."""
        if inventory.cursor is not None:
            self.draw_stack(batch, inventory.cursor, mouse)
