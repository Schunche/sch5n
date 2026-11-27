# Copyright (c) 2026 Schunche
"""The GUI style in use: `ui.json` sizes plus the selected theme."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sch5n.game.config import ThemeColors
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from sch5n.game.config import (
        ButtonStyle,
        MainMenuStyle,
        Rgba,
        SlotStyle,
        Theme,
        UiConfig,
    )

COLOR_NAMES = frozenset(ThemeColors.model_fields)


class Style:
    """GUI style with a switchable theme.

    Widgets keep a reference to one `Style`; switching the theme changes
    them all at once.
    """

    def __init__(self, config: UiConfig, theme: str) -> None:
        """Use `theme`, or the default theme if it does not exist."""
        self.config = config
        self.theme_name = config.default_theme
        self.set_theme(theme)

    @property
    def theme(self) -> Theme:
        """The active theme."""
        return self.config.themes[self.theme_name]

    @property
    def theme_names(self) -> list[str]:
        """Every theme, in `ui.json` order."""
        return list(self.config.themes)

    def set_theme(self, name: str) -> None:
        """Switch themes. Unknown names select the default theme."""
        if name not in self.config.themes:
            LOGGER.warning("Unknown theme %r, using the default", name)
            name = self.config.default_theme
        self.theme_name = name

    @property
    def font_names(self) -> list[str]:
        """Every font, in `ui.json` order."""
        return list(self.config.fonts)

    def font_name(self, name: str) -> str:
        """Pick a font that exists: `name`, or the default font.

        Returns:
            str: The font's name in `ui.json`.

        """
        if name in self.config.fonts:
            return name
        LOGGER.warning("Unknown font %r, using the default", name)
        return self.config.default_font

    def color(self, name: str) -> Rgba:
        """Look up a color of the active theme.

        Returns:
            Rgba: The color, with or without alpha.

        Raises:
            KeyError: Unknown color name.

        """
        if name not in COLOR_NAMES:
            msg = f"Unknown UI color: {name!r}"
            raise KeyError(msg)
        return getattr(self.theme.colors, name)

    @property
    def outer_padding(self) -> int:
        """Distance of GUI elements from the window edge."""
        return self.config.outer_padding

    @property
    def button(self) -> ButtonStyle:
        """Button sizes."""
        return self.config.button

    @property
    def slot(self) -> SlotStyle:
        """Inventory slot sizes."""
        return self.config.slot

    @property
    def main_menu(self) -> MainMenuStyle:
        """Main menu layout."""
        return self.config.main_menu
