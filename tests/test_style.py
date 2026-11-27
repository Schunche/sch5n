# Copyright (c) 2026 Schunche
"""Themes and the GUI style."""

from __future__ import annotations

import pydantic
import pygame
import pytest

from sch5n.client.render.text import system_font
from sch5n.client.style import COLOR_NAMES, Style
from sch5n.game.config import BackgroundKind, Settings, UiConfig
from sch5n.game.content import load_ui
from sch5n.utility import path

MIN_THEMES = 2


@pytest.fixture(scope="module")
def config() -> UiConfig:
    """Load `ui.json`.

    Returns:
        UiConfig: GUI sizes and themes.

    """
    return load_ui(path.DATA_DIR)


def test_bundled_themes_are_complete(config: UiConfig) -> None:
    """There are alternatives, all distinct and with usable backgrounds."""
    assert len(config.themes) >= MIN_THEMES
    labels = [theme.label for theme in config.themes.values()]
    assert len(set(labels)) == len(labels)
    for theme in config.themes.values():
        background = theme.background
        if background.kind is BackgroundKind.IMAGE:
            assert background.image is not None
            assert (path.TEXTURES_DIR / f"{background.image}.png").exists()


def test_style_switches_and_falls_back(config: UiConfig) -> None:
    """Switching themes changes the colors; unknown themes use the default."""
    first, second = list(config.themes)[:MIN_THEMES]
    style = Style(config, first)
    before = style.color("accent")
    style.set_theme(second)
    assert style.theme_name == second
    assert style.color("accent") == config.themes[second].colors.accent
    assert style.color("accent") != before

    assert Style(config, "no such theme").theme_name == config.default_theme


def test_unknown_color_is_an_error(config: UiConfig) -> None:
    """Typos in color names fail loudly."""
    style = Style(config, config.default_theme)
    assert {style.color(name) for name in COLOR_NAMES}
    with pytest.raises(KeyError, match="Unknown UI color"):
        style.color("hotbar_selected_border")


def test_default_theme_must_exist(config: UiConfig) -> None:
    """A config naming a missing default theme is rejected."""
    data = config.model_dump()
    data["default_theme"] = "missing"
    with pytest.raises(pydantic.ValidationError, match="default theme"):
        UiConfig.model_validate(data)


@pytest.mark.parametrize("volume", [-1, 101])
def test_volumes_are_percentages(volume: int) -> None:
    """Volumes outside 0 to 100 are rejected."""
    with pytest.raises(pydantic.ValidationError):
        Settings(master_volume=volume)


def test_fonts_exist_with_their_licenses(config: UiConfig) -> None:
    """Every font file in config.json is there, with its license next to it."""
    assert config.default_font in config.fonts
    for font in config.fonts.values():
        if font.file is None:
            continue
        file = path.FONTS_DIR / font.file
        assert file.is_file()
        assert list(path.FONTS_DIR.glob(f"{file.stem}*OFL*.txt"))


def test_unknown_font_falls_back(config: UiConfig) -> None:
    """A font name from an old settings file picks the default."""
    style = Style(config, config.default_theme)
    assert style.font_name("Comic Sans") == config.default_font
    assert style.font_name("classic") == "classic"


def test_system_fonts_must_really_be_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A substitute does not count as the font, unless nothing else is."""
    installed = {
        "arial": "/fonts/FreeSans.ttf",  # A substitute, as on Linux.
        "liberationsans": "/fonts/LiberationSans-Regular.ttf",
    }
    monkeypatch.setattr(pygame.font, "match_font", installed.get)
    assert (
        system_font(["arial", "liberationsans"]) == installed["liberationsans"]
    )
    assert system_font(["arial"]) == installed["arial"]
    assert system_font(["comic"]) is None
