# Copyright (c) 2026 Schunche
"""Typed configuration loaded from the `assets/base/data` JSON files."""

from __future__ import annotations

from enum import StrEnum
lazy from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

type Color = tuple[int, int, int]
type Rgba = tuple[int, int, int] | tuple[int, int, int, int]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class GameMode(StrEnum):
    """How forgiving the game is."""

    SURVIVAL = "survival"
    ADMIN = "admin"


class MenuBackground(StrEnum):
    """What menus show behind them."""

    WORLD = "world"
    """The world: a live one on the main menu, the paused game in game."""
    THEME = "theme"
    """The theme's background."""


class PhysicsConfig(_Model):
    """World physics. Units are pixels and ticks."""

    gravity: float = 0.4
    max_fall_speed: float = 10.0


class PlayerConfig(_Model):
    """Player movement tuning. Units are pixels and ticks."""

    size: tuple[int, int] = (20, 46)
    """Hitbox in pixels. The sprite is drawn bottom centered on it."""
    walk_speed: float = 1.0
    acceleration: float = 0.1
    max_speed: float = 2.0
    friction: float = 0.1
    jump_velocity: float = 5.0
    jump_hold_ticks: int = 15
    """Ticks a held jump keeps rising at `jump_velocity`."""
    wall_jump_velocity: tuple[float, float] = (4.5, 5.0)
    """Push away from the wall and lift."""
    wall_slide_speed: float = 1.5
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
    magnet_strength: tuple[float, float] = (0.4, 0.45)
    terminal_velocity: float = 8.0
    gravity: float = 0.3
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

    count: int = 24
    altitude: tuple[float, float] = (80.0, 520.0)
    """Height above the horizon in pixels, for the nearest clouds."""
    speed: float = 0.5
    """Pixels per tick of the nearest clouds at wind strength 1."""
    parallax: float = 1.3
    """How strongly depth separates the cloud layers. 1 moves each layer
    with its depth; higher values make distant clouds follow the camera
    and the wind less, so the layers drift apart more."""


class WindConfig(_Model):
    """Wind that blows in gusts."""

    max: float = 1.5
    """Strongest wind, either way."""
    gust_strength: float = 0.6
    """How far a gust may stray from the session's prevailing wind."""
    gust_interval: tuple[int, int] = (240, 900)
    """Ticks between gusts."""
    change_rate: float = 0.0015
    """How fast the wind turns towards a gust, per tick."""


class WindStreakConfig(_Model):
    """Faint lines in the air that show the wind."""

    rate: float = 0.1
    """Expected new streaks per tick at wind strength 1, for a 1280 pixel
    wide view."""
    min_wind: float = 0.25
    """No streaks in a calmer wind."""
    lifetime: int = 100
    length: tuple[float, float] = (40.0, 140.0)
    speed: float = 3.0
    """Pixels per tick at wind strength 1."""


class SkyConfig(_Model):
    """The sky behind the world. Sizes are screen pixels unless noted."""

    horizon: Color = (166, 214, 240)
    middle: Color = (31, 127, 191)
    zenith: Color = (18, 56, 122)
    deep: Color = (24, 20, 28)
    """Shown through holes deep underground."""
    height: float = 900.0
    """From the horizon to the zenith color."""
    parallax: float = 0.15
    """How much the sky moves with the camera, in (0, 1]."""
    bands: int = 10
    """Color steps from horizon to zenith, dithered in between."""
    pixel_size: int = 4
    underground: tuple[float, float] = (192.0, 960.0)
    """World pixels below the surface where the deep color starts and
    where it takes over."""


class GameConfig(_Model):
    """Fixed game rules, `game.json`."""

    title: str = "sch5n"
    tick_rate: int = 60
    tile_size: int = 32
    sky: SkyConfig = SkyConfig()
    physics: PhysicsConfig = PhysicsConfig()
    player: PlayerConfig = PlayerConfig()
    camera: CameraConfig = CameraConfig()
    floating_item: FloatingItemConfig = FloatingItemConfig()
    inventory: InventoryConfig = InventoryConfig()
    particles: dict[str, ParticleConfig] = Field(default_factory=dict)
    clouds: CloudConfig = CloudConfig()
    wind: WindConfig = WindConfig()
    wind_streaks: WindStreakConfig = WindStreakConfig()


class Settings(_Model):
    """User adjustable settings, `settings.json`."""

    window_width: int = 1280
    window_height: int = 720
    vsync: bool = True
    fps_limit: int = 0
    """Frame cap when vsync is off. 0 means unlimited."""
    fullscreen: bool = False
    gui_size: int = 24
    theme: str = "dusk"
    """Name of a theme in `ui.json`."""
    menu_background: MenuBackground = MenuBackground.WORLD
    cursor_color: Color | None = None
    """`None` uses the operating system cursor with the cursor image. A
    color hides it and draws the cursor image tinted with this color."""
    master_volume: int = Field(default=100, ge=0, le=100)
    music_volume: int = Field(default=70, ge=0, le=100)
    effects_volume: int = Field(default=80, ge=0, le=100)
    player_name: str = Field(default="Player", min_length=1, max_length=24)
    """Shown to other players in multiplayer."""
    last_server: str = ""
    """Address typed last on the multiplayer screen."""
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

    button_spacing: int = 64


class ThemeColors(_Model):
    """Every color a theme defines. Each may have an alpha component."""

    background: Rgba
    """Screen clear color, behind everything."""
    panel: Rgba
    """Panels behind menu content."""
    button_inner: Rgba
    button_border: Rgba
    button_hover: Rgba
    text: Rgba
    text_dim: Rgba
    """Secondary text, like hints."""
    accent: Rgba
    """Selection: the active hotbar slot, page or binding."""


class BackgroundKind(StrEnum):
    """What fills the screen behind menus."""

    SHADER = "shader"
    """Animated, pixelated noise in the theme's colors."""
    IMAGE = "image"
    SOLID = "solid"


class ThemeBackground(_Model):
    """Menu background of a theme."""

    kind: BackgroundKind = BackgroundKind.SHADER
    colors: tuple[Color, Color, Color] = (
        (20, 16, 40),
        (70, 40, 110),
        (240, 140, 90),
    )
    """Dark, middle and highlight color of the shader."""
    speed: float = 1.0
    pixel_size: int = 4
    """Size of the shader's pixels, to match the pixel art."""
    image: str | None = None
    """Texture for `kind: image`."""


class Theme(_Model):
    """A named look for the GUI."""

    label: str
    colors: ThemeColors
    background: ThemeBackground = ThemeBackground()


class UiConfig(_Model):
    """GUI styling and themes, `ui.json`."""

    default_theme: str
    themes: dict[str, Theme]
    outer_padding: int = 16
    button: ButtonStyle = ButtonStyle()
    slot: SlotStyle = SlotStyle()
    main_menu: MainMenuStyle = MainMenuStyle()

    @model_validator(mode="after")
    def _default_theme_exists(self) -> UiConfig:
        """Check that the default theme is defined.

        Returns:
            UiConfig: The validated config.

        Raises:
            ValueError: The default theme is missing.

        """
        if self.default_theme not in self.themes:
            msg = f"Unknown default theme {self.default_theme!r}"
            raise ValueError(msg)
        return self


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


class Transition(_Model):
    """A clip played once when an animation changes from one to another."""

    from_: tuple[str, ...] = Field(alias="from")
    to: tuple[str, ...]
    play: str
    """Clip played in between; it must not loop."""


class ToolUseConfig(_Model):
    """How a mob swings items.

    The body is drawn without its front arm, then the item rotating around
    the hand, then the arm pose closest to the item's direction.
    """

    armless: str
    """Texture directory with an armless copy of every clip."""
    arm: str
    """Texture directory with the front arm poses."""
    rig: str
    """JSON file with shoulder and hand positions, see `Rig`."""
    swing: tuple[float, float] = (-100.0, 55.0)
    """Direction of the arm at the start and end of a swing, in degrees,
    clockwise from straight forward."""
    wrist: tuple[float, float] = (-90.0, -15.0)
    """Angle of the item to the arm at the start and end of a swing: cocked
    back across the fist, then snapping through to strike."""
    grip: tuple[float, float] = (0.15, 0.85)
    """Where the hand holds an item image, as a fraction of its size. Item
    images point up and forward (45 degrees) from the grip."""


class ArmRig(_Model):
    """Front arm poses: their shoulder, hand positions and directions."""

    shoulder: tuple[float, float]
    angles: tuple[float, ...]
    """Direction of each pose, degrees clockwise from straight forward."""
    hands: tuple[tuple[float, float], ...]


class Rig(_Model):
    """Attachment points in sprite pixels, written next to the frames."""

    shoulders: dict[str, tuple[tuple[float, float], ...]]
    """Front shoulder in every frame of every clip."""
    arm: ArmRig


class AnimationsConfig(_Model):
    """Which textures make up which animation, `animations.json`."""

    mobs: dict[str, dict[str, AnimationClip]]
    transitions: dict[str, tuple[Transition, ...]] = Field(
        default_factory=dict
    )
    """Per mob, clips that bridge changes between animations."""
    tool_use: dict[str, ToolUseConfig] = Field(default_factory=dict)
    """Per mob, how it swings items."""
    particles: dict[str, AnimationClip]
    tile_breakage: AnimationClip
    clouds: str
    cursor: str
    window_icon: str
    transparent_color: Color = (255, 0, 254)

    @model_validator(mode="after")
    def _transitions_use_known_clips(self) -> AnimationsConfig:
        """Check that transitions name clips of their mob.

        Returns:
            AnimationsConfig: The validated config.

        Raises:
            ValueError: A transition names an unknown or looping clip.

        """
        for mob, transitions in self.transitions.items():
            clips = self.mobs.get(mob, {})
            for transition in transitions:
                names = {*transition.from_, *transition.to, transition.play}
                unknown = names - clips.keys()
                if unknown:
                    msg = f"{mob} transition uses unknown clips {unknown}"
                    raise ValueError(msg)
                if clips[transition.play].loop:
                    msg = f"{mob} transition clip {transition.play} loops"
                    raise ValueError(msg)
        return self


def load_model[M: BaseModel](model: type[M], path: Path) -> M:
    """Validate a JSON file against a model.

    Returns:
        M: The parsed model.

    """
    return model.model_validate_json(path.read_text(encoding="utf-8"))
