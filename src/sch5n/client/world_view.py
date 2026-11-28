# Copyright (c) 2026 Schunche
"""Draws the world: tiles, entities, particles and clouds."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

import numpy as np

from sch5n.client.animation import Animator
from sch5n.client.render.batch import (
    INSTANCE_FLOATS,
    WHITE,
    Transform,
    sprite_instances,
)
from sch5n.client.render.daynight import (
    darkness,
    draw_stars_and_moon,
    sky_at,
)
from sch5n.client.render.lightmap import (
    MAX_LIGHT,
    LightMap,
    light_field,
    night_pixels,
)
from sch5n.client.render.sky import horizon_on_screen
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.game.daylight import phase
from sch5n.game.mining import durability_fraction
from sch5n.game.player import Action
from sch5n.world.io import DEFAULT_MAP, load_tilemap, map_file
from sch5n.world.tilemap import CHUNK_SHIFT, CHUNK_SIZE

HALFWAY = 0.5
"""Keyframe blend at which discrete parts, like the arm pose, switch."""
STREAK_THICKNESS = 2
STREAK_OPACITY = 0.55
STREAK_WOBBLE = 3.0
"""Pixels a wind streak moves up and down."""
STREAK_WOBBLE_SPEED = 0.12
NAME_TAG_SIZE = 14
NAME_TAG_GAP = 6
"""Pixels between a player's head and its name."""
NAME_TAG_COLOR = (1.0, 1.0, 1.0, 0.95)
NAME_TAG_SHADOW = (0.0, 0.0, 0.0, 0.6)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sch5n.client.app import App
    from sch5n.client.assets import ClientAssets
    from sch5n.client.camera import Camera
    from sch5n.client.render.atlas import Region
    from sch5n.client.render.batch import RGBA, SpriteBatch
    from sch5n.game.ambient import Ambience, Cloud
    from sch5n.game.config import Rig, ScissorTool, SwingKey, ToolUseConfig
    from sch5n.game.content import ItemDef
    from sch5n.game.floating_item import FloatingItem
    from sch5n.game.mobs import Mob
    from sch5n.game.player import Player, Swing
    from sch5n.math.rect import Rect
    from sch5n.math.vector import IntTuple2
    from sch5n.world.tilemap import Chunk, TileMap


class TileRenderer:
    """Draws tiles, caching the instance data of each chunk."""

    def __init__(self, assets: ClientAssets, tile_size: int) -> None:
        """Create a renderer for one atlas and tile size."""
        self.assets = assets
        self.tile_size = tile_size
        self._cache: dict[IntTuple2, tuple[int, np.ndarray]] = {}
        local = np.arange(CHUNK_SIZE)
        self._local_y, self._local_x = np.meshgrid(local, local, indexing="ij")

    def _chunk_instances(self, key: IntTuple2, chunk: Chunk) -> np.ndarray:
        cached = self._cache.get(key)
        if cached is not None and cached[0] == chunk.revision:
            return cached[1]

        mask = chunk.blocks != 0
        size = self.tile_size
        xs = (self._local_x[mask] + (key[0] << CHUNK_SHIFT)) * size
        ys = (self._local_y[mask] + (key[1] << CHUNK_SHIFT)) * size
        rects = np.stack(
            [xs, ys, np.full_like(xs, size), np.full_like(xs, size)], axis=1
        )
        variants = np.minimum(
            chunk.variants[mask], self.assets.block_uvs.shape[1] - 1
        )
        uvs = self.assets.block_uvs[chunk.blocks[mask], variants]
        instances = sprite_instances(rects, uvs)
        self._cache[key] = (chunk.revision, instances)
        return instances

    def draw(
        self,
        batch: SpriteBatch,
        tilemap: TileMap,
        view: Rect,
        *,
        breakage: bool = True,
        color: RGBA = WHITE,
    ) -> None:
        """Queue every tile overlapping `view`."""
        span = self.tile_size * CHUNK_SIZE
        cx0, cy0 = math.floor(view.left / span), math.floor(view.top / span)
        cx1, cy1 = (
            math.floor(view.right / span),
            math.floor(view.bottom / span),
        )

        parts = [
            self._chunk_instances((cx, cy), chunk)
            for cy in range(cy0, cy1 + 1)
            for cx in range(cx0, cx1 + 1)
            if (chunk := tilemap.chunks.get((cx, cy))) is not None
        ]
        if parts:
            instances = np.concatenate(parts) if len(parts) > 1 else parts[0]
            if color != WHITE:
                instances = instances.copy()
                instances[:, 8:12] = color
            batch.extend(self.assets.atlas, instances)

        # Drop cache entries of chunks that no longer exist.
        if len(self._cache) > len(tilemap.chunks):
            for key in self._cache.keys() - tilemap.chunks.keys():
                del self._cache[key]

        if breakage:
            self._draw_breakage(batch, tilemap)

    def _draw_breakage(self, batch: SpriteBatch, tilemap: TileMap) -> None:
        frames = self.assets.breakage
        size = self.tile_size
        for x, y in tilemap.damage:
            fraction = durability_fraction(tilemap, x, y)
            index = int((len(frames) - 1) * (1 - fraction))
            batch.sprite(
                self.assets.atlas,
                (x * size, y * size, size, size),
                frames[min(max(index, 0), len(frames) - 1)],
            )


type Placed = tuple[tuple[float, float, float, float], Transform]
"""Rect and transform of a sprite."""


@dataclass(frozen=True, slots=True)
class ScissorPose:
    """The two halves of a scissor tool, like the lopper, on their hinge."""

    front: Placed
    """Half held by the front hand."""
    back: Placed
    """Half held by the other hand, behind the body."""
    hinge: tuple[float, float]
    """Where the halves cross, relative to the body sprite's top left."""


@dataclass(frozen=True, slots=True)
class HeldItemPose:
    """Where the swinging arm and item go, relative to the sprite's corner."""

    arm: int
    """Index of the arm pose."""
    arm_offset: tuple[float, float]
    """Top left of the arm image."""
    item_rect: tuple[float, float, float, float]
    item_transform: Transform
    behind: bool = False
    """Draw the arm and item behind the body."""
    off_arm: int | None = None
    """Index of the arm pose of the other hand, drawn behind the body."""
    scissors: ScissorPose | None = None
    """Halves drawn instead of the item, for scissor tools."""


def _eased(progress: float) -> float:
    """Ease a swing: fast at first, slowing down at the end.

    Returns:
        float: Eased progress in [0, 1].

    """
    return 1 - (1 - min(max(progress, 0.0), 1.0)) ** 2


def swing_direction(tool_use: ToolUseConfig, progress: float) -> float:
    """Direction of the swinging arm.

    Returns:
        float: Degrees clockwise from straight forward.

    """
    start, end = tool_use.swing
    return start + (end - start) * _eased(progress)


def item_direction(tool_use: ToolUseConfig, progress: float) -> float:
    """Direction the swung item points, from the grip to its head.

    The item is held across the fist, at the wrist angle to the arm.

    Returns:
        float: Degrees clockwise from straight forward.

    """
    start, end = tool_use.wrist
    wrist = start + (end - start) * _eased(progress)
    return swing_direction(tool_use, progress) + wrist


@dataclass(frozen=True, slots=True)
class SwingMoment:
    """One moment of a swing, as seen on one body frame."""

    progress: float
    """How far the swing is, 0 to 1."""
    shoulder: tuple[float, float]
    """Front shoulder in the body frame."""
    frame_width: float
    item_size: tuple[float, float]
    """Width and height of the item image, as drawn."""
    facing_left: bool


@dataclass(frozen=True, slots=True)
class SwingFrame:
    """A moment of a keyframed swing, between two of its keyframes."""

    arm: str
    item: float
    scale: float
    behind: bool
    body: str | None
    off_arm: str | None = None


def swing_frame(keys: Sequence[SwingKey], progress: float) -> SwingFrame:
    """Interpolate a keyframed swing.

    The item's direction and size blend between keyframes; the arm pose,
    the side of the body and the body pose switch halfway.

    Returns:
        SwingFrame: The swing at `progress`.

    """
    progress = min(max(progress, 0.0), 1.0)
    index = next(
        (i for i in range(1, len(keys)) if progress <= keys[i].at),
        len(keys) - 1,
    )
    start, end = keys[index - 1], keys[index]
    span = end.at - start.at
    f = (progress - start.at) / span if span > 0 else 1.0
    near = start if f < HALFWAY else end
    return SwingFrame(
        arm=near.arm,
        item=start.item + (end.item - start.item) * f,
        scale=start.scale + (end.scale - start.scale) * f,
        behind=near.behind,
        body=near.body,
        off_arm=near.off_arm,
    )


def tool_kind(item: ItemDef) -> str | None:
    """Tell the kind of tool an item is, like `axe`, for its swing.

    Returns:
        str | None: The first tool kind it has power for, if any.

    """
    return next(iter(item.spec.tool_power), None)


def overhead_arms(rig: Rig, tool_use: ToolUseConfig) -> list[int]:
    """Arm poses the overhead swing chooses from.

    Returns:
        list[int]: Indices of the poses.

    """
    if not rig.arm.names:
        return list(range(len(rig.arm.angles)))
    return [
        i
        for i, name in enumerate(rig.arm.names)
        if name in tool_use.overhead_arms
    ]


def held_item_pose(
    rig: Rig, tool_use: ToolUseConfig, moment: SwingMoment
) -> HeldItemPose:
    """Place the arm and the item for a moment of an overhead swing.

    Returns:
        HeldItemPose: Positions relative to the body sprite's top left.

    """
    angle = swing_direction(tool_use, moment.progress)
    arm = min(
        overhead_arms(rig, tool_use),
        key=lambda i: abs(rig.arm.angles[i] - angle),
    )
    return place_item(
        rig,
        tool_use,
        moment,
        Hold(arm, item_direction(tool_use, moment.progress)),
    )


def keyframe_pose(
    rig: Rig,
    tool_use: ToolUseConfig,
    moment: SwingMoment,
    frame: SwingFrame,
    *,
    mirrored: bool = False,
) -> HeldItemPose:
    """Place the arm and the item for a moment of a keyframed swing.

    A `mirrored` item is flipped across its handle, for swings that turn
    the other way round than overhead ones, so the blade leads.

    Returns:
        HeldItemPose: Positions relative to the body sprite's top left.

    """
    arm = rig.arm.names.index(frame.arm)
    hold = Hold(arm, frame.item, frame.scale, mirrored=mirrored)
    pose = place_item(rig, tool_use, moment, hold)
    off_arm = None
    if frame.off_arm is not None:
        off_arm = rig.arm.names.index(frame.off_arm)
    return replace(pose, behind=frame.behind, off_arm=off_arm)


def scissor_pose(
    rig: Rig,
    moment: SwingMoment,
    frame: SwingFrame,
    tool: ScissorTool,
    image_size: tuple[float, float],
) -> ScissorPose:
    """Place the two halves of a scissor tool, one handle in each hand.

    The hinge sits `tool.reach` ahead of the point between the hands, in
    the frame's item direction. Each half's handle points from the hinge
    to its hand and its blade the other way, so the blades open as the
    hands part and close as they meet. Without a second hand, both hands
    are the front one and the tool stays shut.

    Returns:
        ScissorPose: Positions relative to the body sprite's top left.

    """
    dx = moment.shoulder[0] - rig.arm.shoulder[0]
    dy = moment.shoulder[1] - rig.arm.shoulder[1]
    front_hand, back_hand = (
        (x + dx, y + dy)
        for x, y in (
            rig.arm.hands[rig.arm.names.index(name)]
            for name in (frame.arm, frame.off_arm or frame.arm)
        )
    )
    # Worked out facing right, then mirrored.
    direction = math.radians(frame.item)
    hinge = (
        (front_hand[0] + back_hand[0]) / 2 + tool.reach * math.cos(direction),
        (front_hand[1] + back_hand[1]) / 2 + tool.reach * math.sin(direction),
    )
    width, height = image_size
    hinge_x, hinge_y = tool.hinge
    drawn = hinge
    if moment.facing_left:
        drawn = (moment.frame_width - hinge[0], hinge[1])
        hinge_x = width - hinge_x

    def half(hand: tuple[float, float]) -> Placed:
        # The blade points away from the hand, through the hinge.
        blade = math.atan2(hinge[1] - hand[1], hinge[0] - hand[0])
        if moment.facing_left:
            blade = -blade
        return (
            (drawn[0] - hinge_x, drawn[1] - hinge_y, width, height),
            Transform(
                flip_x=moment.facing_left,
                rotation=blade,
                pivot=(hinge_x / width, hinge_y / height),
            ),
        )

    return ScissorPose(
        front=half(front_hand), back=half(back_hand), hinge=drawn
    )


@dataclass(frozen=True, slots=True)
class Hold:
    """How the arm holds the item at a moment."""

    arm: int
    """Index of the arm pose."""
    direction: float
    """Where the item points, degrees clockwise from straight forward."""
    scale: float = 1.0
    """Item size factor, around the grip."""
    mirrored: bool = False
    """Item mirrored across its handle, so its blade is on the other side."""


def place_item(
    rig: Rig, tool_use: ToolUseConfig, moment: SwingMoment, hold: Hold
) -> HeldItemPose:
    """Put the arm pose on the shoulder and the item in its hand.

    Returns:
        HeldItemPose: Positions relative to the body sprite's top left.

    """
    dx = moment.shoulder[0] - rig.arm.shoulder[0]
    dy = moment.shoulder[1] - rig.arm.shoulder[1]
    hand_x, hand_y = rig.arm.hands[hold.arm]
    grip_x, grip_y = tool_use.grip
    # Item images point up and forward (-45 degrees) from the grip.
    rotation = math.radians(hold.direction + 45)
    flip = False
    if hold.mirrored:
        # Mirroring across the handle is flipping (now pointing at -135
        # degrees) and turning a quarter more.
        flip = True
        grip_x = 1 - grip_x
        rotation += math.pi / 2
    if moment.facing_left:
        # Everything is mirrored around the sprite's middle.
        dx = -dx
        hand_x = moment.frame_width - hand_x
        grip_x = 1 - grip_x
        rotation = -rotation
        flip = not flip
    width = moment.item_size[0] * hold.scale
    height = moment.item_size[1] * hold.scale
    return HeldItemPose(
        arm=hold.arm,
        arm_offset=(dx, dy),
        item_rect=(
            dx + hand_x - grip_x * width,
            dy + hand_y - grip_y * height,
            width,
            height,
        ),
        item_transform=Transform(
            flip_x=flip,
            rotation=rotation,
            pivot=(grip_x, grip_y),
        ),
    )


class PlayerRenderer:
    """Draws the player, including items it swings."""

    def __init__(
        self, assets: ClientAssets, tool_use: ToolUseConfig | None
    ) -> None:
        """Create a renderer. Without `tool_use` swings are not shown."""
        self.assets = assets
        self.tool_use = tool_use if "player" in assets.rigs else None

    def draw(
        self, batch: SpriteBatch, player: Player, animator: Animator
    ) -> None:
        """Queue the player, standing on the bottom of the hitbox.

        Frames are drawn at their own size, centered on the hitbox, so
        they may be wider than the body for swinging arms and legs.
        """
        frame = animator.frame
        body = player.body
        corner = (
            round(body.x + (body.w - frame.width) / 2),
            round(body.y + body.h - frame.height),
        )
        if player.swing is not None and self.tool_use is not None:
            self._draw_swinging(batch, player, animator, corner)
            return
        batch.sprite(
            self.assets.atlas,
            (*corner, frame.width, frame.height),
            frame,
            transform=Transform(flip_x=player.facing_left),
        )

    def _swing_pose(
        self, player: Player, animator: Animator, swing: Swing
    ) -> tuple[Region, HeldItemPose]:
        """Armless body frame and arm and item placement for this tick.

        Returns:
            tuple[Region, HeldItemPose]: Body frame and pose.

        Raises:
            RuntimeError: Swings are not configured.

        """
        if self.tool_use is None:
            msg = "No tool use configured for the player"
            raise RuntimeError(msg)
        rig = self.assets.rigs["player"]
        kind = tool_kind(swing.item) or ""
        keys = self.tool_use.styles.get(kind)
        frame = None if keys is None else swing_frame(keys, swing.progress)
        clip = animator.clip
        index = None
        if frame is not None and frame.body and player.action is Action.IDLE:
            # Standing still, the whole body joins in, like stepping on a
            # shovel; on the move the legs keep running.
            clip, index = frame.body, 0
        # Both arms are drawn on their own when the tool takes two hands.
        one_handed = frame is None or frame.off_arm is None
        animation = (self.assets.armless if one_handed else self.assets.bare)[
            "player", clip
        ]
        if index is None:
            index = animation.frame_index(animator.age)
        body = animation.frames[index]
        moment = SwingMoment(
            progress=swing.progress,
            shoulder=rig.shoulders[clip][index],
            frame_width=body.width,
            item_size=self.assets.items[swing.item.name].size,
            facing_left=player.facing_left,
        )
        if frame is None:
            return body, held_item_pose(rig, self.tool_use, moment)
        pose = keyframe_pose(
            rig,
            self.tool_use,
            moment,
            frame,
            mirrored=kind in self.tool_use.mirrored,
        )
        tool = self.tool_use.scissors.get(swing.item.name)
        halves = self.assets.scissors.get(swing.item.name)
        if tool is not None and halves is not None:
            size = (halves[0].width, halves[0].height)
            pose = replace(
                pose, scissors=scissor_pose(rig, moment, frame, tool, size)
            )
        return body, pose

    def _draw_swinging(
        self,
        batch: SpriteBatch,
        player: Player,
        animator: Animator,
        corner: tuple[int, int],
    ) -> None:
        """Body without the drawn arms, then the item, then the front arm.

        When they are behind the body, the item and arm come first.
        """
        swing = player.swing
        if swing is None:
            return
        body, pose = self._swing_pose(player, animator, swing)
        x, y = corner
        mirror = Transform(flip_x=player.facing_left)
        halves = self.assets.scissors.get(swing.item.name)
        front: Placed = (pose.item_rect, pose.item_transform)
        image = self.assets.items[swing.item.name]
        if pose.off_arm is not None:
            # The other hand, on the far side of the body.
            self._draw_arm(batch, pose, pose.off_arm, corner, mirror)
        if pose.scissors is not None and halves is not None:
            # The half in the other hand, behind the body like that hand.
            self._draw_tool(batch, halves[1], pose.scissors.back, corner)
            front, image = pose.scissors.front, halves[0]
        if not pose.behind:
            batch.sprite(
                self.assets.atlas,
                (x, y, body.width, body.height),
                body,
                transform=mirror,
            )
        self._draw_tool(batch, image, front, corner)
        self._draw_arm(batch, pose, pose.arm, corner, mirror)
        if pose.behind:
            batch.sprite(
                self.assets.atlas,
                (x, y, body.width, body.height),
                body,
                transform=mirror,
            )

    def _draw_arm(
        self,
        batch: SpriteBatch,
        pose: HeldItemPose,
        index: int,
        corner: tuple[int, int],
        mirror: Transform,
    ) -> None:
        """Draw an arm in the arm pose `index`, at the shoulder."""
        arm = self.assets.arms["player"][index]
        (x, y), (ax, ay) = corner, pose.arm_offset
        batch.sprite(
            self.assets.atlas,
            (x + ax, y + ay, arm.width, arm.height),
            arm,
            transform=mirror,
        )

    def _draw_tool(
        self,
        batch: SpriteBatch,
        image: Region,
        placed: Placed,
        corner: tuple[int, int],
    ) -> None:
        """Draw the held item, or one half of it."""
        (x, y, w, h), transform = placed
        batch.sprite(
            self.assets.atlas,
            (corner[0] + x, corner[1] + y, w, h),
            image,
            transform=transform,
        )


def draw_floating_items(
    batch: SpriteBatch, assets: ClientAssets, items: Sequence[FloatingItem]
) -> None:
    """Queue dropped items."""
    for floating in items:
        r = floating.sprite_rect
        region = assets.items[floating.stack.item.name]
        w, h = region.width, region.height
        # At their own size, images sit on the bottom, centered.
        batch.sprite(
            assets.atlas,
            (r.x + (r.w - w) / 2, r.y + r.h - h, w, h),
            region,
        )


HURT_TINT = (1.0, 0.45, 0.45, 1.0)
"""Color multiplied onto a creature that was just hit."""


def draw_mobs(
    batch: SpriteBatch, assets: ClientAssets, mobs: Mapping[int, Mob]
) -> None:
    """Queue hostile creatures, red while hurt."""
    for mob in mobs.values():
        body = mob.body
        region = assets.mob_sprites[mob.kind.name]
        batch.sprite(
            assets.atlas,
            (body.x, body.y, body.w, body.h),
            region,
            HURT_TINT if mob.hurt else WHITE,
            Transform(flip_x=mob.facing_left),
        )


def draw_particles(
    batch: SpriteBatch, assets: ClientAssets, ambience: Ambience
) -> None:
    """Queue particles, centered on their position."""
    if not ambience.particles:
        return
    rows = np.zeros(
        (len(ambience.particles), INSTANCE_FLOATS), dtype=np.float32
    )
    for row, particle in zip(rows, ambience.particles, strict=True):
        region = assets.particles[particle.kind].frame(particle.age)
        row[0:4] = (
            particle.x - region.width / 2,
            particle.y - region.height / 2,
            region.width,
            region.height,
        )
        row[4:8] = region.uv
        row[8:12] = WHITE
    batch.extend(assets.atlas, rows)


def cloud_scale(depth: float) -> int:
    """Whole pixel scale of a cloud: near clouds are drawn bigger.

    Returns:
        int: 2 for the furthest clouds up to 4 for the nearest.

    """
    return max(1, round(1 + depth * 3))


def cloud_image(regions: Sequence[Region], cloud: Cloud) -> Region:
    """Pick the image for a cloud: small images for small clouds.

    Returns:
        Region: One of `regions`, which are ordered smallest first.

    """
    return regions[round(cloud.size * (len(regions) - 1))]


def place_cloud(
    cloud: Cloud,
    image: Region,
    camera_center: tuple[float, float],
    horizon: float,
    screen: tuple[float, float],
) -> tuple[tuple[float, float, float, float], float] | None:
    """Where a cloud appears on screen, and how opaque it is.

    Clouds float above the horizon with parallax: distant ones move less
    with the camera, sit lower, look smaller and fade into the sky.
    Horizontally they wrap around the screen.

    Returns:
        tuple[tuple[float, float, float, float], float] | None: Screen
        rectangle and opacity, or `None` when off screen.

    """
    width, height = screen
    scale = cloud_scale(cloud.depth)
    w, h = image.width * scale, image.height * scale
    x = (cloud.x - camera_center[0] * cloud.parallax) % (width + w) - w
    horizon_on_screen = (
        height / 2 + (horizon - camera_center[1]) * cloud.parallax
    )
    lift = cloud.altitude * (0.4 + 0.6 * cloud.depth)
    y = horizon_on_screen - lift - h
    if y > height or y + h < 0:
        return None
    opacity = 0.35 + 0.65 * cloud.depth
    return (round(x), round(y), w, h), opacity


def draw_clouds(
    batch: SpriteBatch,
    assets: ClientAssets,
    world: WorldView,
    camera_center: tuple[float, float],
    screen: tuple[float, float],
) -> None:
    """Queue clouds in screen space, far ones first."""
    if not assets.clouds:
        return
    for cloud in world.ambience.clouds:
        image = cloud_image(assets.clouds, cloud)
        placed = place_cloud(
            cloud, image, camera_center, world.horizon, screen
        )
        if placed is not None:
            rect, opacity = placed
            batch.sprite(assets.atlas, rect, image, (1.0, 1.0, 1.0, opacity))


def draw_wind_streaks(batch: SpriteBatch, ambience: Ambience) -> None:
    """Queue faint, wobbling lines where the wind blows. World space."""
    for streak in ambience.streaks:
        wobble = math.sin(streak.age * STREAK_WOBBLE_SPEED + streak.phase)
        batch.shape(
            (
                streak.x - streak.length / 2,
                streak.y + wobble * STREAK_WOBBLE,
                streak.length,
                STREAK_THICKNESS,
            ),
            (1.0, 1.0, 1.0, STREAK_OPACITY * streak.opacity),
            radius=STREAK_THICKNESS / 2,
        )


class WorldView(Protocol):
    """What drawing needs of a world: a `Game`, or a client's mirror.

    Read only, so either may keep its own, narrower types.
    """

    @property
    def tilemap(self) -> TileMap:
        """The tiles."""
        ...

    @property
    def ambience(self) -> Ambience:
        """Wind, clouds and particles."""
        ...

    @property
    def clock(self) -> int:
        """Ticks that tell the time of day."""
        ...

    @property
    def horizon(self) -> float:
        """World y where the sky begins."""
        ...

    @property
    def floating_items(self) -> Sequence[FloatingItem]:
        """Dropped items."""
        ...

    @property
    def mobs(self) -> Mapping[int, Mob]:
        """Hostile creatures by id."""
        ...

    @property
    def players(self) -> Mapping[int, Player]:
        """Players by id."""
        ...


class WorldRenderer:
    """Draws a world as a player sees it: sky, clouds, tiles, players.

    Also animates the players; call `tick` once per game tick.
    """

    def __init__(self, app: App) -> None:
        """Create the renderer."""
        self.app = app
        self.tiles = TileRenderer(app.assets, app.content.game.tile_size)
        self.animators: dict[int, Animator] = {}
        """Animation of each player, by id."""
        self.lightmap = LightMap(app.ctx)
        self.player_renderer = PlayerRenderer(
            app.assets, app.animations.tool_use.get("player")
        )
        self._name_style = TextStyle(
            NAME_TAG_SIZE, NAME_TAG_COLOR, Anchor.BOTTOM_CENTER
        )
        self._name_shadow = TextStyle(
            NAME_TAG_SIZE, NAME_TAG_SHADOW, Anchor.BOTTOM_CENTER
        )

    def _night_tiles(self, camera: Camera) -> tuple[int, int, int, int]:
        size = self.app.content.game.tile_size
        view = camera.view(self.app.screen)
        return (
            math.floor(view.x / size) - 1,
            math.floor(view.y / size) - 1,
            math.ceil(view.right / size) + 1,
            math.ceil(view.bottom / size) + 1,
        )

    def draw_night(self, world: WorldView, camera: Camera) -> None:
        """Darken the screen at night, except where lights shine.

        Draws in screen space, over the world.
        """
        app = self.app
        game = app.content.game
        shade = darkness(phase(world.clock, game.tick_rate))
        if shade <= 0.0:
            return
        x0, y0, x1, y1 = self._night_tiles(camera)
        tilemap = world.tilemap
        radii = tilemap.blocks.light[
            tilemap.region(
                x0 - MAX_LIGHT, y0 - MAX_LIGHT, x1 + MAX_LIGHT, y1 + MAX_LIGHT
            )
        ]
        field = light_field(radii)[MAX_LIGHT:-MAX_LIGHT, MAX_LIGHT:-MAX_LIGHT]
        size, zoom = game.tile_size, camera.zoom
        left, top = camera.top_left(app.screen)
        rect = (
            (x0 * size - left) * zoom,
            (y0 * size - top) * zoom,
            (x1 - x0) * size * zoom,
            (y1 - y0) * size * zoom,
        )
        app.batch.begin(app.screen)
        self.lightmap.draw(app.batch, night_pixels(field, shade), rect)

    def _animator(self, player_id: int, player: Player) -> Animator:
        animator = self.animators.get(player_id)
        if animator is None:
            assets = self.app.assets
            animator = self.animators[player_id] = Animator(
                {
                    action: animation
                    for (mob, action), animation in assets.mobs.items()
                    if mob == "player"
                },
                self.app.animations.transitions.get("player", ()),
                player.action.value,
            )
        return animator

    def tick(self, world: WorldView) -> None:
        """Advance every player's animation by one tick."""
        for player_id in self.animators.keys() - world.players.keys():
            del self.animators[player_id]
        for player_id, player in world.players.items():
            self._animator(player_id, player).update(player.action.value)

    def _draw_name(self, player: Player) -> None:
        body = player.body
        pos = (body.center[0], body.y - NAME_TAG_GAP)
        text = self.app.text
        batch = self.app.batch
        shadow = (pos[0] + 1, pos[1] + 1)
        text.draw(batch, player.name, shadow, self._name_shadow)
        text.draw(batch, player.name, pos, self._name_style)

    def draw(
        self,
        world: WorldView,
        camera: Camera,
        *,
        show_players: bool = True,
        local_id: int | None = None,
    ) -> None:
        """Draw everything but the HUD. Leaves a world space batch open.

        Players other than `local_id` get their name above them.
        """
        app = self.app
        batch = app.batch
        offset = camera.offset(app.screen)

        game = app.content.game
        day_phase = phase(world.clock, game.tick_rate)
        sky = sky_at(game.sky, day_phase)
        app.sky.draw(sky, camera, app.screen, world.horizon)
        batch.begin(app.screen)
        draw_stars_and_moon(
            batch,
            app.screen,
            horizon_on_screen(
                camera, world.horizon, app.screen[1], sky.parallax
            ),
            day_phase,
        )
        view = camera.view(app.screen)
        draw_clouds(batch, app.assets, world, view.center, app.screen)

        batch.begin(app.screen, offset, camera.zoom)
        self.tiles.draw(batch, world.tilemap, camera.view(app.screen))
        if show_players:
            for player_id, player in world.players.items():
                self.player_renderer.draw(
                    batch, player, self._animator(player_id, player)
                )
        draw_particles(batch, app.assets, world.ambience)
        draw_wind_streaks(batch, world.ambience)
        draw_floating_items(batch, app.assets, world.floating_items)
        draw_mobs(batch, app.assets, world.mobs)
        if show_players:
            for player_id, player in world.players.items():
                if player_id != local_id and player.name:
                    self._draw_name(player)


def load_start_map(app: App) -> TileMap:
    """Load the map chosen on the command line, or the default one.

    Returns:
        TileMap: The map.

    """
    map_path = app.options.map_path or map_file(DEFAULT_MAP)
    return load_tilemap(map_path, app.content.blocks)
