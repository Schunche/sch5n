# Copyright (c) 2026 Schunche
"""Client code that does not need a window: layout, camera, atlas packing."""

import numpy as np
import pytest

from sch5n.client.assets import frame_files
from sch5n.client.camera import MAX_ZOOM, Camera
from sch5n.client.render.atlas import (
    AtlasBuilder,
    next_power_of_two,
    pack_shelves,
)
from sch5n.client.render.image import apply_colorkey, load_rgba
from sch5n.client.render.text import Anchor, anchored
from sch5n.client.style import Style
from sch5n.client.ui import (
    Align,
    InventoryLayout,
    aligned_rect,
    button_column,
    hit_button,
)
from sch5n.game.config import AnimationClip, GameConfig, load_model
from sch5n.game.content import load_animations, load_ui
from sch5n.utility import path

ATLAS_WIDTH = 256
PADDING = 1
OPAQUE = 255


@pytest.fixture(scope="module")
def ui() -> Style:
    """Load the real GUI style.

    Returns:
        Style: The style from `ui.json` with its default theme.

    """
    config = load_ui(path.DATA_DIR)
    return Style(config, config.default_theme)


def test_camera_roundtrip_and_zoom() -> None:
    """Screen positions map to world positions, also while zooming."""
    cam = Camera(100, 50)
    assert cam.screen_to_world((10, 20)) == (110, 70)
    cam.zoom_at(2.0, (100, 100))
    assert cam.screen_to_world((100, 100)) == pytest.approx((200, 150))
    cam.zoom = 100
    assert cam.zoom == MAX_ZOOM


def test_camera_follow_converges() -> None:
    """Following a point eventually centers it on screen."""
    cam = Camera()
    for _ in range(500):
        cam.follow((1000, 1000), (200, 100), 0.05)
    assert (cam.x, cam.y) == pytest.approx((900, 950))
    assert cam.view((200, 100)).center == pytest.approx((1000, 1000))


def test_pack_shelves_no_overlap() -> None:
    """Packed rectangles stay inside the area and keep their padding apart."""
    rng = np.random.default_rng(0)
    sizes = {
        i: (int(rng.integers(1, 60)), int(rng.integers(1, 60)))
        for i in range(200)
    }
    positions, height = pack_shelves(sizes, ATLAS_WIDTH, padding=PADDING)
    rects = [(*positions[k], *sizes[k]) for k in sizes]
    for i, (x, y, w, h) in enumerate(rects):
        assert x >= PADDING
        assert y >= PADDING
        assert x + w <= ATLAS_WIDTH - PADDING
        assert y + h <= height - PADDING
        for x2, y2, w2, h2 in rects[i + 1 :]:
            assert (
                x + w + 1 <= x2
                or x2 + w2 + 1 <= x
                or y + h + 1 <= y2
                or y2 + h2 + 1 <= y
            )


def test_pack_rejects_too_wide() -> None:
    """An image wider than the atlas is an error."""
    with pytest.raises(ValueError, match="does not fit"):
        pack_shelves({"a": (300, 1)}, 256)


def test_atlas_regions_point_at_pixels() -> None:
    """Atlas regions address the right pixels and edges are extruded."""
    builder: AtlasBuilder[str] = AtlasBuilder(width=64)
    red = np.zeros((4, 6, 4), np.uint8)
    red[...] = (255, 0, 0, 255)
    builder.add("red", red)
    builder.add("blue", np.full((3, 3, 4), (0, 0, 255, 255), np.uint8))
    pixels, regions = builder.build()
    assert pixels.shape[0] == next_power_of_two(pixels.shape[0])
    r = regions["red"]
    x, y = round(r.u0 * 64), round(r.v0 * pixels.shape[0])
    assert (r.width, r.height) == (6, 4)
    assert (pixels[y : y + 4, x : x + 6] == red).all()
    # Edge pixels are extruded into the padding.
    assert tuple(pixels[y - 1, x]) == (255, 0, 0, 255)


def test_colorkey() -> None:
    """The color key turns only matching pixels transparent."""
    pixels = np.array([[[255, 0, 254, 255], [1, 2, 3, 255]]], np.uint8)
    apply_colorkey(pixels, (255, 0, 254))
    assert pixels[0, 0, 3] == 0
    assert pixels[0, 1, 3] == OPAQUE


def test_anchored_text() -> None:
    """Text anchors resolve to the top left corner."""
    assert anchored((100, 100), (20, 10), Anchor.CENTER) == (90, 95)
    assert anchored((100, 100), (20, 10), Anchor.BOTTOM_RIGHT) == (80, 90)


def test_aligned_rect() -> None:
    """Bottom right alignment puts the rectangle left of the point."""
    rect = aligned_rect((100, 100), (20, 10), Align.BOTTOM_RIGHT)
    assert (rect.right, rect.bottom) == (100, 100)


def test_buttons(ui: Style) -> None:
    """Clicks hit the button they land on, and only that one."""
    buttons = button_column([("a", "A"), ("b", "B")], (200, 100), 64, ui)
    assert hit_button(buttons, (200, 100)) == "a"
    assert hit_button(buttons, (200, 164)) == "b"
    assert hit_button(buttons, (0, 0)) is None


def test_inventory_layout(ui: Style) -> None:
    """Slots are laid out in rows, and hit tests respect the hotbar mode."""
    columns, gui_size = 10, 24
    layout = InventoryLayout.create(columns, 50, gui_size, ui)
    first, below = layout.slot_rect(0), layout.slot_rect(columns)
    assert first.w == pytest.approx(gui_size * 1.5)
    assert below.x == first.x
    assert below.y == first.y + first.h + ui.slot.padding
    assert layout.slot_at(below.center, hotbar_only=False) == columns
    assert layout.slot_at(below.center, hotbar_only=True) is None
    gap = (first.right + layout.slot_rect(1).x) / 2
    assert layout.slot_at((gap, first.center[1]), hotbar_only=True) is None
    hotbar = layout.bounds(hotbar_only=True)
    assert hotbar.contains_point(*layout.slot_rect(9).center)


@pytest.mark.parametrize(
    ("clip", "ages", "frames"),
    [
        (
            AnimationClip(path="x", frame_ticks=5, loop=True),
            [0, 4, 5, 19, 20],
            [0, 0, 1, 3, 0],
        ),
        (
            AnimationClip(path="x", frame_ticks=5, loop=False),
            [0, 19, 20, 1000],
            [0, 3, 3, 3],
        ),
    ],
    ids=["loop", "once"],
)
def test_animation_frames(
    clip: AnimationClip, ages: list[int], frames: list[int]
) -> None:
    """Looping clips wrap around, others stop on their last frame."""
    assert [clip.frame_index(age, 4) for age in ages] == frames


MIN_COLORS = 6
"""A real character has hair, skin, clothes and an outline."""


def test_player_frames_are_real_sprites() -> None:
    """Player frames are real art that fits around the hitbox.

    Every animation has frames of one size, with transparency and several
    colors, at least as big as the hitbox.
    """
    animations = load_animations(path.DATA_DIR)
    width, height = load_model(
        GameConfig, path.DATA_DIR / "game.json"
    ).player.size
    sizes = set()
    for clip in animations.mobs["player"].values():
        files = frame_files(path.TEXTURES_DIR / clip.path)
        assert files, clip.path
        for file in files:
            pixels = load_rgba(file)
            sizes.add(pixels.shape[:2])
            alpha = pixels[..., 3]
            assert (alpha == 0).any(), file  # Not a filled box.
            opaque = pixels[alpha > 0][:, :3]
            assert len({tuple(c) for c in opaque.tolist()}) >= MIN_COLORS
    assert len(sizes) == 1
    ((frame_height, frame_width),) = sizes
    assert frame_width >= width
    assert frame_height >= height
