# Copyright (c) 2026 Schunche
"""Experimental software."""

from warnings import deprecated
lazy from typing import cast

lazy import pygame

from sch5n.deprecated.loader import (
    FIX_SETTINGS,
    NAME_SPACE,
    SETTINGS,
    load_sys_font,
)
lazy from sch5n.deprecated.item import Item
lazy from sch5n.log.logger import LOGGER

# https://fonts.google.com/specimen/Pixelify+Sans?query=pixel


@deprecated("Create substitute.")
def render_text(
    surface: pygame.Surface,
    pos: tuple[int, int],
    text: str,
    color: str = "text",
    font_name: str = "arial",
    font_size: int = 16,
) -> None:
    """Render text to the specified surface."""
    font: pygame.font.Font = load_sys_font(font_name, size=font_size)
    text_rendered: pygame.Surface = font.render(
        text, antialias=True, color=NAME_SPACE["color"][color]
    )
    text_rect: pygame.Rect = text_rendered.get_rect()
    text_rect.center = (pos[0], pos[1])
    surface.blit(text_rendered, text_rect)


@deprecated("Create substitute.")
class Button:
    def __init__(
        self,
        pos: tuple[int, int],
        text: str,
        *,
        size: tuple[int, int] = (
            FIX_SETTINGS.GUI.standard_button_width,
            FIX_SETTINGS.GUI.standard_button_height,
        ),
        align_by: str = "topLeft",
        is_solid: bool = True,  # ruff: ignore[unused-method-argument]
        inner_color: str = "buttonInner",
        text_color: str = "text",
        hover_color: str = "buttonHover",
        border_color: str = "buttonBorder",
        font: pygame.font.Font | None = None,
        border_width: int = FIX_SETTINGS.GUI.button_border_width,
        border_radius: int = FIX_SETTINGS.GUI.button_border_radius,
    ) -> None:
        """Initialize a new instance of the `Button` class.

        TODO: is_solid.

        """
        if inner_color not in NAME_SPACE["color"]:
            msg = f"Invalid background color: {inner_color}"
            raise ValueError(msg)

        if text_color not in NAME_SPACE["color"]:
            msg = f"Invalid text color: {text_color}"
            raise ValueError(msg)

        if hover_color not in NAME_SPACE["color"]:
            msg = f"Invalid hover color: {hover_color}"
            raise ValueError(msg)

        if font is None:
            font = load_sys_font("arial")

        self.pos: tuple[int, int] = pos
        self.size: tuple[int, int] = size
        self.text: str = text.title()
        self.inner_color: str = inner_color
        self.text_color: str = text_color
        self.border_color: str = border_color
        self.hover_color: str = hover_color
        self.font: pygame.font.Font = font

        self.border_width: int = border_width
        self.border_radius: int = border_radius

        self.inner_rect: pygame.Rect
        self.border_rect: pygame.Rect
        self.text_rendered: pygame.Surface
        self.text_rect: pygame.Rect

        if align_by == "topLeft":
            self.inner_rect = pygame.Rect(
                self.pos[0], self.pos[1], self.size[0], self.size[1]
            )
            self.border_rect = pygame.Rect(
                self.pos[0], self.pos[1], self.size[0], self.size[1]
            )
            self.text_rendered = self.font.render(
                self.text,
                antialias=True,
                color=NAME_SPACE["color"][self.text_color],
            )
            self.text_rect = self.text_rendered.get_rect()
            self.text_rect.center = (
                self.pos[0] + self.size[0] // 2,
                self.pos[1] + self.size[1] // 2,
            )

        elif align_by == "center":
            self.inner_rect = pygame.Rect(
                self.pos[0] - int(self.size[0] / 2),
                self.pos[1] - int(self.size[1] / 2),
                self.size[0] - self.border_width * 2,
                self.size[1] - self.border_width * 2,
            )
            self.border_rect = pygame.Rect(
                self.pos[0] - self.border_width - int(self.size[0] / 2),
                self.pos[1] - self.border_width - int(self.size[1] / 2),
                self.size[0],
                self.size[1],
            )
            self.text_rendered = self.font.render(
                self.text,
                antialias=True,
                color=NAME_SPACE["color"][self.text_color],
            )
            self.text_rect = self.text_rendered.get_rect()
            self.text_rect.center = (
                self.pos[0],
                self.pos[1] - FIX_SETTINGS.GUI.button_text_vertical_off_error,
            )

        elif align_by == "bottom_right":
            self.inner_rect = pygame.Rect(
                self.pos[0] - self.border_width - int(self.size[0] / 2),
                self.pos[1] - self.border_width - int(self.size[1] / 2),
                self.size[0] - self.border_width * 2,
                self.size[1] - self.border_width * 2,
            )
            self.border_rect = pygame.Rect(
                self.pos[0] + self.border_width - int(self.size[0] / 2),
                self.pos[1] + self.border_width - int(self.size[1] / 2),
                self.size[0],
                self.size[1],
            )
            self.text_rendered = self.font.render(
                self.text,
                antialias=True,
                color=NAME_SPACE["color"][self.text_color],
            )
            self.text_rect = self.text_rendered.get_rect()
            self.text_rect.center = (self.pos[0], self.pos[1])

        else:
            # Not implemented possibility will raise error
            msg = "Invalid align_by value"
            raise ValueError(msg)

    def push(self, mouse_pos: tuple[int, int]) -> bool:
        """Pushes the button."""
        if not self.border_rect.collidepoint(*mouse_pos):  # ruff: ignore[needless-bool]
            return False

        # Actual functionality here

        return True

    def render(
        self, surface: pygame.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        """Render the button to the specified surface."""
        is_hovered: bool = False
        if self.border_rect.collidepoint(*mouse_pos):
            is_hovered = True

        # Buttons inner color
        pygame.draw.rect(
            surface,
            NAME_SPACE["color"][
                self.hover_color if is_hovered else self.inner_color
            ],
            self.inner_rect,
        )
        # Buttons border
        pygame.draw.rect(
            surface,
            NAME_SPACE["color"][self.border_color],
            self.border_rect,
            width=self.border_width,
            border_radius=self.border_radius,
        )
        # Buttons text
        surface.blit(self.text_rendered, self.text_rect)


@deprecated("Create substitute.")
class Inventory:
    def __init__(self, *args: Item) -> None:

        self.slots: dict[int, Item | None] = dict.fromkeys(
            range(FIX_SETTINGS.inventory_column * FIX_SETTINGS.inventory_row)
        )
        for index, item in enumerate(args):
            self.slots[index] = item

        inner_rect_size: int = int(SETTINGS.gui_size * 1.5)
        self.inner_rects: list[pygame.Rect] = [
            pygame.Rect(
                FIX_SETTINGS.GUI.outer_window_padding
                + (i % FIX_SETTINGS.inventory_column)
                * (inner_rect_size + FIX_SETTINGS.GUI.slot_padding),
                FIX_SETTINGS.GUI.outer_window_padding
                + (i // FIX_SETTINGS.inventory_column)
                * (inner_rect_size + FIX_SETTINGS.GUI.slot_padding),
                inner_rect_size,
                inner_rect_size,
            )
            for i in range(len(self.slots))
        ]
        self.not_hovered_inner = pygame.Surface(
            (inner_rect_size, inner_rect_size), pygame.SRCALPHA
        )
        self.not_hovered_inner.fill((
            *NAME_SPACE["color"]["buttonInner"],
            FIX_SETTINGS.GUI.slot_transparency,
        ))

        self.hovered_inner = pygame.Surface(
            (inner_rect_size, inner_rect_size), pygame.SRCALPHA
        )
        self.hovered_inner.fill((
            *NAME_SPACE["color"]["buttonHover"],
            FIX_SETTINGS.GUI.slot_transparency,
        ))

        self.border_rects: list[pygame.rect.Rect] = [
            pygame.Rect(
                FIX_SETTINGS.GUI.outer_window_padding
                - FIX_SETTINGS.GUI.slot_border_width
                + (i % FIX_SETTINGS.inventory_column)
                * (inner_rect_size + FIX_SETTINGS.GUI.slot_padding),
                FIX_SETTINGS.GUI.outer_window_padding
                - FIX_SETTINGS.GUI.slot_border_width
                + (i // FIX_SETTINGS.inventory_column)
                * (inner_rect_size + FIX_SETTINGS.GUI.slot_padding),
                inner_rect_size + 2 * FIX_SETTINGS.GUI.slot_border_width,
                inner_rect_size + 2 * FIX_SETTINGS.GUI.slot_border_width,
            )
            for i in range(len(self.slots))
        ]

    def click(self, mouse_pos: tuple[int, int]) -> bool:  # ruff: ignore[no-self-use, unused-method-argument]
        # Placeholder
        return False

        # Actual functionality here

    def get_item_by_num(self, slot_num: int) -> Item | None:
        return self.slots[slot_num]

    def is_full(self) -> bool:
        """Whether the inventory is full."""
        return None not in self.slots.values()

    def render_hotbar(
        self,
        surface: pygame.Surface,
        hotbar_num: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        # Actual inventory
        for slot_num in range(10):  # The number of slots in a row
            surface.blit(
                self.hovered_inner
                if self.border_rects[slot_num].collidepoint(mouse_pos)
                else self.not_hovered_inner,
                self.inner_rects[slot_num].topleft,
            )
            # pygame.draw.rect(
            #    surface,
            #    NAME_SPACE["color"]["buttonHover" if self\
            #        .border_rects[slot_num]\
            #        .collidepoint(mouse_pos) else "buttonInner"],
            #    self.inner_rects[slot_num]
            # )
            pygame.draw.rect(
                surface,
                NAME_SPACE["color"][
                    "hotbarSelectedBorder"
                    if slot_num == hotbar_num
                    else "buttonBorder"
                ],
                self.border_rects[slot_num],
                width=FIX_SETTINGS.GUI.button_border_width,
                border_radius=FIX_SETTINGS.GUI.button_border_radius,
            )

            item = self.slots[slot_num]
            if item is not None:
                item.render_icon(
                    surface,
                    (
                        int(
                            self.inner_rects[slot_num].x
                            + self.inner_rects[slot_num].w * 0.5
                            - SETTINGS.gui_size * 0.5
                        ),
                        int(
                            self.inner_rects[slot_num].y
                            + self.inner_rects[slot_num].h * 0.5
                            - SETTINGS.gui_size * 0.5
                        ),
                    ),
                )

    def render_full_inventory(
        self,
        surface: pygame.Surface,
        hotbar_num: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        # Actual inventory
        for slot_num, item in self.slots.items():
            pygame.draw.rect(
                surface,
                NAME_SPACE["color"][
                    "buttonHover"
                    if self.border_rects[slot_num].collidepoint(mouse_pos)
                    else "buttonInner"
                ],
                self.inner_rects[slot_num],
            )
            pygame.draw.rect(
                surface,
                NAME_SPACE["color"][
                    "hotbarSelectedBorder"
                    if slot_num == hotbar_num
                    else "buttonBorder"
                ],
                self.border_rects[slot_num],
                width=FIX_SETTINGS.GUI.button_border_width,
                border_radius=FIX_SETTINGS.GUI.button_border_radius,
            )

            if item is not None:
                item.render_icon(
                    surface,
                    (
                        int(
                            self.inner_rects[slot_num].x
                            + self.inner_rects[slot_num].w * 0.5
                            - SETTINGS.gui_size * 0.5
                        ),
                        int(
                            self.inner_rects[slot_num].y
                            + self.inner_rects[slot_num].h * 0.5
                            - SETTINGS.gui_size * 0.5
                        ),
                    ),
                )

    def does_hover(self, mouse_pos: tuple[int, int]) -> bool:
        for slot_num in self.slots:
            if self.border_rects[slot_num].collidepoint(mouse_pos):
                return True
        return False

    def get_slot_num(self, mouse_pos: tuple[int, int]) -> int | None:
        for slot_num in self.slots:
            if self.border_rects[slot_num].collidepoint(mouse_pos):
                return slot_num

        return None

    def add_item(self, item: Item) -> Item | None:
        if item.max_amount == 1:
            if self.is_full():
                return item
            for key, slot in self.slots.copy().items():
                if slot is None:
                    self.slots[key] = item
                    return None
        elif not self.is_full():
            for slot in self.slots.values():
                if slot is None:
                    continue
                if slot.id == item.id:
                    if slot.amount == slot.max_amount:
                        continue

                    if slot.amount + item.amount <= slot.max_amount:
                        slot.amount += item.amount
                        return None
                    diff = slot.max_amount - slot.amount
                    slot.amount = item.max_amount
                    item.amount -= diff
            # To this point filled up all duplicants

            # If it has no empty slots return item
            if self.is_full():
                return item
            # So it has empty slots

            for key, slot in self.slots.items():
                if slot is None:
                    self.slots[key] = item
                    return None
            # Put it to the empty slot

        else:
            # Inventory is full
            for slot in self.slots.values():
                slot = cast("Item", slot)
                if slot.id == item.id:
                    # Slot is full
                    if slot.amount == slot.max_amount:
                        continue

                    # The rest can be put there
                    if slot.amount + item.amount <= slot.max_amount:
                        slot.amount += item.amount
                        return None
                    # Decrease with some amount
                    diff = slot.max_amount - slot.amount
                    slot.amount = item.max_amount
                    item.amount -= diff
            # To this point filled up all duplicants

            # So there is some bonus amount
            return item
            # So it has empty slots

        LOGGER.critical("Not all cases have been covered, in inventory adding")
        return None


@deprecated("Create substitute.")
class CursorSlot:
    def __init__(self, item: Item | None = None) -> None:
        self.slot = item

    def is_full(self) -> bool:
        """Whether the slot has an item."""
        return self.slot is not None

    def get_item(self) -> Item | None:
        """Item the cursor contains."""
        return self.slot

    def render_item_at_cursor(
        self, surface: pygame.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        item = self.slot
        if item is not None:
            item.render_icon(
                surface,
                (
                    int(mouse_pos[0] - SETTINGS.gui_size * 0.5),
                    int(mouse_pos[1] - SETTINGS.gui_size * 0.5),
                ),
            )

    def empty(self) -> None:
        self.slot = None
