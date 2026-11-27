# Copyright (c) 2026 Schunche
"""Heads-up display: hotbar, inventory and the item held by the cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.game.inventory import HOTBAR_SIZE

if TYPE_CHECKING:
    from sch5n.client.assets import ClientAssets
    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.client.ui import InventoryLayout
    from sch5n.game.config import UiConfig
    from sch5n.game.inventory import Inventory, ItemStack


class Hud:
    """Draws the inventory GUI."""

    def __init__(
        self,
        assets: ClientAssets,
        text: TextRenderer,
        style: UiConfig,
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
        batch.sprite(
            self.assets.atlas,
            (x, y, size, size),
            self.assets.items[stack.item.name],
        )
        if stack.item.is_stackable:
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
            inner = layout.slot_rect(index)
            border = inner.inflated(layout.border)
            fill = "button_hover" if index == hovered else "button_inner"
            batch.shape(
                (inner.x, inner.y, inner.w, inner.h),
                rgba(style.color(fill), alpha),
            )
            edge = (
                "hotbar_selected_border"
                if index == inventory.selected
                else "button_border"
            )
            batch.shape(
                (border.x, border.y, border.w, border.h),
                rgba(style.color(edge)),
                radius=style.button.border_radius,
                border=style.button.border_width,
            )
            stack = inventory[index]
            if stack is not None:
                self.draw_stack(batch, stack, inner.center)

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

    def draw_cursor_stack(
        self,
        batch: SpriteBatch,
        inventory: Inventory,
        mouse: tuple[float, float],
    ) -> None:
        """Draw the stack held by the cursor."""
        if inventory.cursor is not None:
            self.draw_stack(batch, inventory.cursor, mouse)
