import pygame

from sch5n.core.item import Item
from sch5n.core.loader import FIX_SETTINGS, NAME_SPACE, SETTINGS, load_sys_font
from sch5n.core.log import log_error

# https://fonts.google.com/specimen/Pixelify+Sans?query=pixel


def render_text(
    surface: pygame.Surface,
    pos: tuple[int, int],
    text: str,
    color: str = "text",
    font_name: str = "arial",
    font_size: int = 16,
) -> None:
    """Renders text to the specified surface.
    """
    font: pygame.font.Font = load_sys_font(font_name, size=font_size)
    text_rendered: pygame.Surface = font.render(
        text, antialias=True, color=NAME_SPACE["color"][color]
    )
    text_rect: pygame.Rect = text_rendered.get_rect()
    text_rect.center = (pos[0], pos[1])
    surface.blit(text_rendered, text_rect)


class Button:
    def __init__(
        self,
        pos: tuple[int, int],
        text: str,
        *,
        size: tuple[int, int] = (
            FIX_SETTINGS["GUI"]["standardButtonWidth"],
            FIX_SETTINGS["GUI"]["standardButtonHeight"],
        ),
        align_by: str = "topLeft",
        is_solid: bool = True,
        inner_color: str = "buttonInner",
        text_color: str = "text",
        hover_color: str = "buttonHover",
        border_color: str = "buttonBorder",
        font: pygame.font.Font = load_sys_font("arial"),
        border_width: int = FIX_SETTINGS["GUI"]["buttonBorderWidth"],
        border_radius: int = FIX_SETTINGS["GUI"]["buttonBorderRadius"],
    ) -> None:
        """TODO: is_solid
        Initializes a new instance of the `Button` class.
        """
        assert inner_color in NAME_SPACE["color"], (
            f"Invalid background color: {inner_color}"
        )
        assert text_color in NAME_SPACE["color"], (
            f"Invalid text color: {text_color}"
        )
        assert hover_color in NAME_SPACE["color"], (
            f"Invalid hover color: {hover_color}"
        )

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

        if align_by == "topLeft":
            self.inner_rect = pygame.Rect(
                self.pos[0], self.pos[1], self.size[0], self.size[1]
            )
            self.border_rect = pygame.Rect(
                self.pos[0], self.pos[1], self.size[0], self.size[1]
            )
            self.text_rendered = self.font.render(
                self.text, antialias=True,
                color=NAME_SPACE["color"][self.text_color]
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
            self.text_rendered: pygame.Surface = self.font.render(
                self.text, True, NAME_SPACE["color"][self.text_color]
            )
            self.text_rect: pygame.Rect = self.text_rendered.get_rect()
            self.text_rect.center = (
                self.pos[0],
                self.pos[1] - FIX_SETTINGS["GUI"]["buttonTextVerticalOffError"],
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
            self.text_rendered: pygame.Surface = self.font.render(
                self.text, True, NAME_SPACE["color"][self.text_color]
            )
            self.text_rect: pygame.Rect = self.text_rendered.get_rect()
            self.text_rect.center = (self.pos[0], self.pos[1])

        else:
            # Not implemented possibility will raise error
            msg = "Invalid align_by value"
            raise ValueError(msg)

    def push(self, mouse_pos: tuple[int, int]) -> bool:
        """Pushes the button."""
        if not self.border_rect.collidepoint(*mouse_pos):
            return False

        # Actual functionality here

        return True

    def render(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        """Render the button to the specified surface.
        """
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


class Inventory:
    def __init__(self, *args) -> None:

        self.inventory: dict[int, Item] = dict.fromkeys(range(FIX_SETTINGS["inventory_column"] * FIX_SETTINGS["inventory_row"]))
        for index, item in enumerate(args):
            self.inventory[index] = item

        inner_rect_size: int = SETTINGS["gui_size"] * 1.5
        self.inner_rects: list[pygame.Rect] = [
            pygame.Rect(
                FIX_SETTINGS["GUI"]["outer_window_padding"]
                + (i % FIX_SETTINGS["inventory_column"])
                * (inner_rect_size + FIX_SETTINGS["GUI"]["slotPadding"]),
                FIX_SETTINGS["GUI"]["outer_window_padding"]
                + (i // FIX_SETTINGS["inventory_column"])
                * (inner_rect_size + FIX_SETTINGS["GUI"]["slotPadding"]),
                inner_rect_size,
                inner_rect_size,
            )
            for i in range(len(self.inventory))
        ]
        self.not_hovered_inner = pygame.Surface(
            (inner_rect_size, inner_rect_size), pygame.SRCALPHA
        )
        self.not_hovered_inner.fill((
            *NAME_SPACE["color"]["buttonInner"],
            FIX_SETTINGS["GUI"]["slotTransparency"],
        ))

        self.hovered_inner = pygame.Surface(
            (inner_rect_size, inner_rect_size), pygame.SRCALPHA
        )
        self.hovered_inner.fill((
            *NAME_SPACE["color"]["buttonHover"],
            FIX_SETTINGS["GUI"]["slotTransparency"],
        ))

        self.border_rects: list[pygame.rect.Rect] = [
            pygame.Rect(
                FIX_SETTINGS["GUI"]["outer_window_padding"]
                - FIX_SETTINGS["GUI"]["slotBorderWidth"]
                + (i % FIX_SETTINGS["inventory_column"])
                * (inner_rect_size + FIX_SETTINGS["GUI"]["slotPadding"]),
                FIX_SETTINGS["GUI"]["outer_window_padding"]
                - FIX_SETTINGS["GUI"]["slotBorderWidth"]
                + (i // FIX_SETTINGS["inventory_column"])
                * (inner_rect_size + FIX_SETTINGS["GUI"]["slotPadding"]),
                inner_rect_size + 2 * FIX_SETTINGS["GUI"]["slotBorderWidth"],
                inner_rect_size + 2 * FIX_SETTINGS["GUI"]["slotBorderWidth"],
            )
            for i in range(len(self.inventory))
        ]

    def click(self, mouse_pos: tuple[int, int]) -> bool:
        # Placeholder
        if True:
            return False

        # Actual functionality here
        print("clicked")

        return True

    def get_item_by_num(self, slot_num: int) -> Item | None:
        return self.inventory[slot_num]

    def is_full(self) -> bool:
        """Returns whether the  inventory is full"""
        if None in self.inventory.values():
            return False
        return True

    def render_hotbar(
        self, surface: pygame.Surface, hotbar_num: int, mouse_pos: tuple[int, int]
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
            #    NAME_SPACE["color"]["buttonHover" if self.border_rects[slot_num].collidepoint(mouse_pos) else "buttonInner"],
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
                width=FIX_SETTINGS["GUI"]["buttonBorderWidth"],
                border_radius=FIX_SETTINGS["GUI"]["buttonBorderRadius"],
            )

            item = self.inventory[slot_num]
            if item is not None:
                item.renderIcon(
                    surface,
                    (
                        int(
                            self.inner_rects[slot_num].x
                            + self.inner_rects[slot_num].w * 0.5
                            - SETTINGS["gui_size"] * 0.5
                        ),
                        int(
                            self.inner_rects[slot_num].y
                            + self.inner_rects[slot_num].h * 0.5
                            - SETTINGS["gui_size"] * 0.5
                        ),
                    ),
                )

    def render_full_inventory(
        self, surface: pygame.Surface, hotbar_num: int, mouse_pos: tuple[int, int]
    ) -> None:
        # Actual inventory
        for slot_num, item in self.inventory.items():
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
                width=FIX_SETTINGS["GUI"]["buttonBorderWidth"],
                border_radius=FIX_SETTINGS["GUI"]["buttonBorderRadius"],
            )

            item = self.inventory[slot_num]
            if item is not None:
                item.renderIcon(
                    surface,
                    (
                        int(
                            self.inner_rects[slot_num].x
                            + self.inner_rects[slot_num].w * 0.5
                            - SETTINGS["gui_size"] * 0.5
                        ),
                        int(
                            self.inner_rects[slot_num].y
                            + self.inner_rects[slot_num].h * 0.5
                            - SETTINGS["gui_size"] * 0.5
                        ),
                    ),
                )

    def does_hover(self, mouse_pos: tuple[int, int]) -> bool:
        for slot_num in self.inventory:
            if self.border_rects[slot_num].collidepoint(mouse_pos):
                return True
        return False

    def get_slot_num(self, mouse_pos: tuple[int, int]) -> int | None:
        for slot_num, item in self.inventory.items():
            if self.border_rects[slot_num].collidepoint(mouse_pos):
                return slot_num

    def add_item(self, item: Item) -> Item | None:
        if item.max_amount == 1:
            if self.is_full():
                return item
            for key, slot in self.inventory.items():
                if slot is None:
                    self.inventory[item] = item
                    return None
        elif not self.is_full():
            for key, slot in self.inventory.items():
                if slot is None:
                    continue
                if slot.id == item.id:
                    if slot.amount == slot.max_amount:
                        continue

                    if slot.amount + item.amount <= slot.max_amount:
                        slot.amount += item.amount
                        return None
                    diff: int = slot.max_amount - slot.amount
                    slot.amount = item.max_amount
                    item.amount -= diff
            # To this point filled up all duplicants

            # If it has no empty slots return item
            if self.is_full():
                return item
            # So it has empty slots

            for key, slot in self.inventory.items():
                if slot is None:
                    self.inventory[key] = item
                    return None
            # Put it to the empty slot

        else:
            # Inventory is full
            for key, slot in self.inventory.items():
                if slot.id == item.id:
                    # Slot is full
                    if slot.amount == slot.max_amount:
                        continue

                    # The rest can be put there
                    if slot.amount + item.amount <= slot.max_amount:
                        slot.amount += item.amount
                        return None
                    # Decrease with some amount
                    diff: int = slot.max_amount - slot.amount
                    slot.amount = item.max_amount
                    item.amount -= diff
            # To this point filled up all duplicants

            # So there is some bonus amount
            return item
                # So it has empty slots

        log_error("Not all cases have been covered, in inventory adding")


class CursorSlot:
    def __init__(self, item: Item | None = None) -> None:
        self.slot = item

    def is_full(self) -> bool:
        """Returns whether the slot has an item"""
        if self.slot is not None:
            return True
        return False

    def get_item(self) -> Item | None:
        """Returns the item the cursor contains"""
        return self.slot

    def render_item_at_cursor(
        self, surface: pygame.Surface, mouse_pos: tuple[int, int]
    ) -> None:
        item = self.slot
        if item is not None:
            item.renderIcon(
                surface,
                (
                    int(mouse_pos[0] - SETTINGS["gui_size"] * 0.5),
                    int(mouse_pos[1] - SETTINGS["gui_size"] * 0.5),
                ),
            )
