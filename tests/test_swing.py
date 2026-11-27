# Copyright (c) 2026 Schunche
"""Swinging tools and blocks."""

from __future__ import annotations

import itertools
import math

import pydantic
import pytest

from sch5n.client.assets import frame_files
from sch5n.client.render.image import load_rgba
from sch5n.client.world_view import (
    HeldItemPose,
    SwingFrame,
    SwingMoment,
    held_item_pose,
    keyframe_pose,
    swing_direction,
    swing_frame,
    tool_kind,
)
from sch5n.game.config import Rig, SwingKey, ToolUseConfig, load_model
from sch5n.game.content import AIR, Content, ItemDef, load_animations
from sch5n.game.inventory import ItemStack
from sch5n.game.session import Game, GameSetup, TickInput
from sch5n.utility import path
from sch5n.world.tilemap import TileMap

TILE = 32

FORESHORTENED = 0.5
"""Item size while the axe points at the viewer, at most."""
DOWN = 90
"""Item direction straight down."""


@pytest.fixture
def game(content: Content) -> Game:
    """Start a game on flat ground with the starting tools.

    Returns:
        Game: The game, player at tile column 0.

    """
    tilemap = TileMap(content.blocks)
    dirt = content.blocks.id_of("dirt")
    for x in range(-30, 30):
        for y in range(10, 14):
            tilemap.set(x, y, dirt)
    return Game(content, tilemap, GameSetup(seed=1, spawn=(0, 0)))


def swings(game: Game, ticks: int, inputs: TickInput) -> list[int]:
    """Run the game with the same input and record every new swing.

    Returns:
        list[int]: Ticks at which a swing started.

    """
    started = []
    current = None
    for tick in range(ticks):
        game.tick(inputs)
        swing = game.player.swing
        if swing is not None and swing is not current:
            started.append(tick)
        current = swing
    return started


def held_item(game: Game) -> ItemDef:
    """Get the item in the player's hand.

    Returns:
        ItemDef: The item.

    """
    held = game.inventory.held
    assert held is not None
    return held.item


def test_holding_use_swings_back_to_back(game: Game) -> None:
    """A held button keeps swinging, one swing per use time."""
    use_time = held_item(game).spec.use_time
    rounds = 4
    started = swings(
        game, use_time * rounds, TickInput(use=True, target=(1, 10))
    )
    assert len(started) >= rounds - 1
    gaps = {b - a for a, b in itertools.pairwise(started)}
    assert gaps == {use_time}


def test_swing_lasts_the_use_time(game: Game) -> None:
    """A single swing takes the item's use time, then ends."""
    pickaxe = held_item(game)
    game.player.start_swing(pickaxe, toward_x=1000)
    for _ in range(pickaxe.spec.use_time):
        game.tick(TickInput())
    assert game.player.swing is not None
    assert game.player.swing.progress == pytest.approx(1.0)
    game.tick(TickInput())
    assert game.player.swing is None


def test_back_to_back_swings_never_blink(game: Game) -> None:
    """Holding the button, the item stays visible between swings."""
    use_time = held_item(game).spec.use_time
    inputs = TickInput(move_x=1, use=True, target=(3, 10))
    swings(game, use_time, inputs)  # Wait for the first swing.
    for _ in range(use_time * 3):
        game.tick(inputs)
        assert game.player.swing is not None


def test_swinging_at_air_and_wrong_blocks_still_swings(
    game: Game, content: Content
) -> None:
    """Swings animate even when nothing is hit."""
    assert swings(game, 60, TickInput(use=True, target=(2, 6)))  # Empty air.
    game.inventory.select(1)  # The axe cannot break dirt.
    assert swings(game, 60, TickInput(use=True, target=(1, 10)))
    assert game.tilemap.get(1, 10) == content.blocks.id_of("dirt")


def test_player_faces_what_it_swings_at(game: Game) -> None:
    """The player turns to the target and keeps facing it while moving."""
    swings(game, 40, TickInput(use=True, target=(-3, 10)))
    assert game.player.facing_left
    game.tick(TickInput(move_x=1, use=True, target=(-3, 10)))
    assert game.player.facing_left  # Walking away mid swing.
    for _ in range(60):
        game.tick(TickInput(move_x=1))
    assert not game.player.facing_left  # Free to turn after the swing.


def test_placing_blocks_swings(game: Game, content: Content) -> None:
    """Placing a block swings the block."""
    game.inventory.slots[2] = ItemStack(content.items["dirt_block"], 5)
    game.inventory.select(2)
    started = swings(game, 40, TickInput(place=True, target=(3, 9)))
    assert started
    assert game.tilemap.get(3, 9) != AIR


# Drawing


@pytest.fixture(scope="module")
def rig() -> Rig:
    """Load the player's rig.

    Returns:
        Rig: Shoulder and hand positions.

    """
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    return load_model(Rig, path.TEXTURES_DIR / tool_use.rig)


def test_rig_matches_the_frames(rig: Rig) -> None:
    """Every clip has an armless copy and a shoulder for every frame."""
    animations = load_animations(path.DATA_DIR)
    tool_use = animations.tool_use["player"]
    for action, clip in animations.mobs["player"].items():
        frames = frame_files(path.TEXTURES_DIR / clip.path)
        armless = frame_files(path.TEXTURES_DIR / tool_use.armless / action)
        assert len(armless) == len(frames) == len(rig.shoulders[action])
        for normal, bare in zip(frames, armless, strict=True):
            assert load_rgba(normal).shape == load_rgba(bare).shape
            assert (load_rgba(bare)[..., 3] > 0).sum() < (
                load_rgba(normal)[..., 3] > 0
            ).sum()
    arms = frame_files(path.TEXTURES_DIR / tool_use.arm)
    assert len(arms) == len(rig.arm.angles) == len(rig.arm.hands)


def test_swing_goes_from_overhead_to_forward_down() -> None:
    """The swing starts fast behind the head and ends forward and down."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    start, end = tool_use.swing
    assert swing_direction(tool_use, 0) == start
    assert swing_direction(tool_use, 1) == end
    halfway = swing_direction(tool_use, 0.5)
    assert halfway > (start + end) / 2  # Eased: most of the way already.


def moment(progress: float, *, facing_left: bool) -> SwingMoment:
    """Create a moment of a swing on the idle frame.

    Returns:
        SwingMoment: The moment.

    """
    return SwingMoment(
        progress=progress,
        shoulder=(25.0, 25.0),
        frame_width=40,
        item_size=32,
        facing_left=facing_left,
    )


def test_arm_follows_the_item(rig: Rig) -> None:
    """The arm goes from raised to lowered during a swing."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    arms = [
        held_item_pose(rig, tool_use, moment(p / 10, facing_left=False)).arm
        for p in range(11)
    ]
    assert arms == sorted(arms)
    names = [rig.arm.names[arm] for arm in arms]
    assert names[0] == "overhead"
    assert names[-1] == "down_forward"
    assert set(names) <= set(tool_use.overhead_arms)


@pytest.mark.parametrize("progress", [0.0, 0.3, 0.7, 1.0])
def test_facing_left_mirrors_the_swing(rig: Rig, progress: float) -> None:
    """Facing left is the exact mirror image of facing right."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    right = held_item_pose(rig, tool_use, moment(progress, facing_left=False))
    left = held_item_pose(rig, tool_use, moment(progress, facing_left=True))
    width = 40
    rx, ry, rw, rh = right.item_rect
    lx, ly, _, _ = left.item_rect
    assert left.arm == right.arm
    assert lx == pytest.approx(width - (rx + rw))
    assert ly == pytest.approx(ry)
    assert left.item_transform.rotation == pytest.approx(
        -right.item_transform.rotation
    )
    assert left.item_transform.flip_x
    assert not right.item_transform.flip_x
    # The grip sits on the hand.
    gx, gy = right.item_transform.pivot
    hand = rig.arm.hands[right.arm]
    assert (rx + gx * rw, ry + gy * rh) == pytest.approx(hand)


def item_pointing(rig: Rig, progress: float) -> float:
    """Direction the drawn item points, facing right.

    Returns:
        float: Degrees clockwise from straight forward.

    """
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    pose = held_item_pose(rig, tool_use, moment(progress, facing_left=False))
    # Item images point at -45 degrees before rotating.
    return math.degrees(pose.item_transform.rotation) - 45


def test_tool_is_held_across_the_fist(rig: Rig) -> None:
    """The tool starts cocked behind the head and strikes forward, down."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    start = item_pointing(rig, 0.0)
    end = item_pointing(rig, 1.0)
    backwards, straight_down = -180, 90
    assert start <= backwards + 20  # Pointing back, behind the head.
    assert 0 < end < straight_down  # Forward and down.
    # Held across the fist: never in line with the arm while winding up.
    arm = swing_direction(tool_use, 0.0)
    assert abs(start - arm) == pytest.approx(abs(tool_use.wrist[0]))


def frames(kind: str) -> list[SwingFrame]:
    """Sample a tool kind's keyframed swing.

    Returns:
        list[SwingFrame]: The swing at 21 points from start to end.

    """
    keys = load_animations(path.DATA_DIR).tool_use["player"].styles[kind]
    return [swing_frame(keys, p / 20) for p in range(21)]


def test_tools_swing_their_own_way(content: Content) -> None:
    """Pickaxes swing overhead; axes and shovels have their own swings."""
    styles = load_animations(path.DATA_DIR).tool_use["player"].styles
    assert tool_kind(content.items["copper_pickaxe"]) not in styles
    assert tool_kind(content.items["copper_axe"]) == "axe"
    assert tool_kind(content.items["iron_shovel"]) == "shovel"
    assert tool_kind(content.items["dirt_block"]) is None


def test_axe_chops_by_turning() -> None:
    """The axe winds up behind the turned away body, then whips through.

    Seen from the side, it points at the viewer midway, so it looks small.
    """
    chop = frames("axe")
    assert chop[0].behind
    assert chop[0].arm == "back"
    assert not chop[-1].behind
    assert chop[-1].arm == "forward"
    assert min(f.scale for f in chop) < FORESHORTENED
    sides = [f.behind for f in chop]
    # Behind first, then in front: one switch, as the body turns once.
    assert sides == sorted(sides, reverse=True)


def test_shovel_is_stepped_on() -> None:
    """The shovel goes straight down, gets stepped on, then levered."""
    dig = frames("shovel")
    bodies = [f.body for f in dig]
    assert bodies[0] == "dig_hold"
    step, press = bodies.index("dig_step"), bodies.index("dig_press")
    assert 0 < step < press
    assert all(f.item == pytest.approx(DOWN) for f in dig[step : press + 1])
    assert dig[-1].body == "dig_hold"


def test_keyframes_blend_the_item() -> None:
    """Between keyframes the item turns smoothly; the arm switches."""
    keys = (
        SwingKey(at=0, arm="back", item=180),
        SwingKey(at=1, arm="forward", item=0, scale=0.5),
    )
    quarter = swing_frame(keys, 0.25)
    assert quarter.item == pytest.approx(135)
    assert quarter.scale == pytest.approx(0.875)
    assert quarter.arm == "back"
    assert swing_frame(keys, 0.75).arm == "forward"
    with pytest.raises(pydantic.ValidationError):
        ToolUseConfig(armless="a", arm="b", rig="c", styles={"axe": keys[:1]})


def drawn_at(pose: HeldItemPose, u: float, v: float) -> tuple[float, float]:
    """Where a point of the item image ends up, as the renderer draws it.

    Returns:
        tuple[float, float]: Position relative to the body sprite's corner.

    """
    x, y, w, h = pose.item_rect
    t = pose.item_transform
    if t.flip_x:
        u = 1 - u
    px, py = t.pivot
    dx, dy = (u - px) * w, (v - py) * h
    c, s = math.cos(t.rotation), math.sin(t.rotation)
    return (x + px * w + dx * c - dy * s, y + py * h + dx * s + dy * c)


HANDLE_TIP = (0.85, 0.15)
"""Top right of an item image: the end of the handle, at the head."""
BLADE = (0.85, 0.5)
"""A point below the handle's diagonal, on the side of the blade."""


def blade_side(pose: HeldItemPose) -> float:
    """Which side of the drawn handle the blade is on.

    Returns:
        float: Positive when clockwise of the handle, seen from the grip.

    """
    gx, gy = drawn_at(pose, 0.15, 0.85)
    tx, ty = drawn_at(pose, *HANDLE_TIP)
    bx, by = drawn_at(pose, *BLADE)
    return (tx - gx) * (by - gy) - (ty - gy) * (bx - gx)


@pytest.mark.parametrize("facing_left", [False, True])
def test_mirrored_item_flips_its_blade_only(
    rig: Rig, *, facing_left: bool
) -> None:
    """A mirrored item has its blade across the handle, nothing else moves."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    frame = SwingFrame(
        arm="forward", item=20, scale=1, behind=False, body=None
    )
    at = moment(0.5, facing_left=facing_left)
    plain = keyframe_pose(rig, tool_use, at, frame)
    mirrored = keyframe_pose(rig, tool_use, at, frame, mirrored=True)
    for point in [(0.15, 0.85), HANDLE_TIP]:
        assert drawn_at(mirrored, *point) == pytest.approx(
            drawn_at(plain, *point)
        )
    assert blade_side(mirrored) * blade_side(plain) < 0


def test_axe_blade_leads_the_chop(rig: Rig) -> None:
    """The chop turns counterclockwise, so the blade is on that side."""
    tool_use = load_animations(path.DATA_DIR).tool_use["player"]
    assert "axe" in tool_use.mirrored
    chop = frames("axe")
    assert chop[0].item > chop[-1].item  # Counterclockwise, facing right.
    for frame in chop:
        pose = keyframe_pose(
            rig, tool_use, moment(0.5, facing_left=False), frame, mirrored=True
        )
        assert blade_side(pose) < 0
    # Overhead swings turn clockwise: their blade is on the other side.
    overhead = held_item_pose(rig, tool_use, moment(0.5, facing_left=False))
    assert blade_side(overhead) > 0


def test_only_keyframed_swings_are_mirrored() -> None:
    """Overhead swings cannot be mirrored."""
    with pytest.raises(pydantic.ValidationError):
        ToolUseConfig(armless="a", arm="b", rig="c", mirrored=("pickaxe",))
