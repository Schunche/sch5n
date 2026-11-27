# Copyright (c) 2026 Schunche
"""Typed configuration loaded from the `assets/base/data` JSON files."""

from __future__ import annotations

from enum import StrEnum
lazy from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

type Color = tuple[int, int, int]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GameMode(StrEnum):
    """How forgiving the game is."""

    SURVIVAL = "survival"
    ADMIN = "admin"


class PhysicsConfig(_Model):
    """World physics. Units are pixels and ticks."""

    gravity: float = 0.1
    max_fall_speed: float = 4.0


class PlayerConfig(_Model):
    """Player movement tuning. Units are pixels and ticks."""

    size: tuple[int, int] = (48, 48)
    walk_speed: float = 1.0
    acceleration: float = 0.1
    max_speed: float = 2.0
    friction: float = 0.1
    jump_velocity: float = 3.0
    wall_jump_velocity: tuple[float, float] = (3.5, 2.5)
    wall_slide_speed: float = 0.5
    airborne_after_ticks: int = 4
    max_jumps: dict[GameMode, int] = Field(
        default_factory=lambda: {GameMode.SURVIVAL: 1, GameMode.ADMIN: 256}
    )


class CameraConfig(_Model):
    """Camera follow behaviour."""

    smoothing: float = 2.0
    """Fraction of the distance (per second) the camera closes."""


class FloatingItemConfig(_Model):
    """Dropped item physics."""

    magnet_range: float = 3
    """In tiles."""
    magnet_strength: tuple[float, float] = (0.4, 0.15)
    terminal_velocity: float = 4.0
    gravity: float = 0.1
    air_resistance: float = 0.03


class StartingItem(_Model):
    """An item the player spawns with."""

    item: str
    amount: int = 1


class InventoryConfig(_Model):
    """Inventory dimensions."""

    columns: int = 10
    rows: int = 5
    starting_items: tuple[StartingItem, ...] = ()

    @property
    def size(self) -> int:
        """Number of slots."""
        return self.columns * self.rows


class ParticleConfig(_Model):
    """Ambient particle behaviour."""

    lifetime: int
    """In ticks."""
    spawn_chance: float
    """Chance per emitting tile per tick."""
    drift: tuple[float, float] = (0.2, 0.4)
    sway_amplitude: float = 0.0
    sway_frequency: float = 0.0
    follows_wind: bool = False


class CloudConfig(_Model):
    """Background clouds."""

    count: int = 16


class GameConfig(_Model):
    """Fixed game rules, `game.json`."""

    title: str = "sch5n"
    tick_rate: int = 60
    tile_size: int = 32
    sky_color: Color = (31, 127, 191)
    physics: PhysicsConfig = PhysicsConfig()
    player: PlayerConfig = PlayerConfig()
    camera: CameraConfig = CameraConfig()
    floating_item: FloatingItemConfig = FloatingItemConfig()
    inventory: InventoryConfig = InventoryConfig()
    particles: dict[str, ParticleConfig] = Field(default_factory=dict)
    clouds: CloudConfig = CloudConfig()


class Settings(_Model):
    """User adjustable settings, `settings.json`."""

    window_width: int = 1280
    window_height: int = 720
    vsync: bool = True
    fps_limit: int = 0
    """Frame cap when vsync is off. 0 means unlimited."""
    fullscreen: bool = False
    gui_size: int = 24
    keybinds: dict[str, dict[str, tuple[str, ...]]] = Field(
        default_factory=dict
    )
    """Context (`game`, `editor`, `viewer`) to action to bindings like
    `key:SPACE`. Missing entries use the defaults."""

    @field_validator("keybinds", mode="before")
    @classmethod
    def _upgrade_flat_keybinds(cls, value: object) -> object:
        """Accept the old format without contexts as the game's binds.

        Returns:
            object: Keybinds grouped by context.

        """
        if isinstance(value, dict) and any(
            isinstance(v, list | tuple) for v in value.values()
        ):
            return {"game": value}
        return value


class ButtonStyle(_Model):
    """Button look."""

    width: int = 128
    height: int = 32
    border_width: int = 4
    border_radius: int = 4
    font_size: int = 16


class SlotStyle(_Model):
    """Inventory slot look."""

    border_width: int = 4
    padding: int = 12
    alpha: int = 159
    amount_font_size: int = 12


class MainMenuStyle(_Model):
    """Main menu look."""

    background: str = "icon/lolBG"
    button_spacing: int = 64


class UiConfig(_Model):
    """GUI styling, `ui.json`."""

    colors: dict[str, Color]
    outer_padding: int = 16
    button: ButtonStyle = ButtonStyle()
    slot: SlotStyle = SlotStyle()
    main_menu: MainMenuStyle = MainMenuStyle()

    def color(self, name: str) -> Color:
        """Look up a named color.

        Returns:
            Color: RGB triple.

        Raises:
            KeyError: Unknown color name.

        """
        try:
            return self.colors[name]
        except KeyError:
            msg = f"Unknown UI color: {name!r}"
            raise KeyError(msg) from None


class AnimationClip(_Model):
    """A sequence of frames loaded from a texture directory."""

    path: str
    frame_ticks: int = 5
    loop: bool = False

    def frame_index(self, age: int, frame_count: int) -> int:
        """Frame to display after `age` ticks.

        Returns:
            int: Index in `range(frame_count)`.

        """
        if frame_count <= 0:
            return 0
        index = max(age, 0) // max(self.frame_ticks, 1)
        if self.loop:
            return index % frame_count
        return min(index, frame_count - 1)


class AnimationsConfig(_Model):
    """Which textures make up which animation, `animations.json`."""

    mobs: dict[str, dict[str, AnimationClip]]
    particles: dict[str, AnimationClip]
    tile_breakage: AnimationClip
    clouds: str
    cursor: str
    window_icon: str
    transparent_color: Color = (255, 0, 254)


def load_model[M: BaseModel](model: type[M], path: Path) -> M:
    """Validate a JSON file against a model.

    Returns:
        M: The parsed model.

    """
    return model.model_validate_json(path.read_text(encoding="utf-8"))
