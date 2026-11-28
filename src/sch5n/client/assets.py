# Copyright (c) 2026 Schunche
"""Loads every texture the client needs into a single atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.atlas import AtlasBuilder, Region, create_texture
from sch5n.client.render.image import load_rgba
from sch5n.game.config import Rig, load_model
from sch5n.game.mobs import KINDS
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    import moderngl

    from sch5n.game.config import AnimationClip, AnimationsConfig
    from sch5n.game.content import Content, ItemDef

type Key = str
"""Texture path relative to the textures directory, without extension."""

ARROW: Key = "gui/arrow"
"""White arrow pointing right, tinted when drawn."""


def frame_files(directory: Path) -> list[Path]:
    """Animation frames of a directory: PNGs with numeric names, in order.

    Returns:
        list[Path]: Frame files.

    """
    frames = [p for p in directory.glob("*.png") if p.stem.isdigit()]
    return sorted(frames, key=lambda p: int(p.stem))


def whole_factor(size: int, length: int) -> int:
    """How many whole times `length` fits in `size`, at least once.

    Enlarging by whole factors keeps pixel art sharp and its pixels square.

    Returns:
        int: The factor.

    """
    return max(size // max(length, 1), 1)


def fit_to_tile(pixels: np.ndarray, size: int) -> np.ndarray:
    """Make a texture of any size cover one tile, without blurring it.

    A smaller texture is enlarged by the least whole factor that covers the
    tile, so a 16 pixel one is doubled on a 32 pixel tile. Whatever sticks
    out is cropped evenly, and so is a texture larger than the tile.

    Returns:
        np.ndarray: `size` by `size` pixels.

    """
    factor = -(-size // min(pixels.shape[:2]))
    if factor > 1:
        pixels = pixels.repeat(factor, axis=0).repeat(factor, axis=1)
    height, width = pixels.shape[:2]
    top, left = (height - size) // 2, (width - size) // 2
    return pixels[top : top + size, left : left + size]


def fit_images(
    builder: AtlasBuilder[Key], keys: list[Key], size: int
) -> list[Key]:
    """Make packed images cover a tile, like the cracks of a damaged one.

    Returns:
        list[Key]: The same keys.

    """
    for key in keys:
        builder.add(key, fit_to_tile(builder.images[key], size))
    return keys


def layer_tiles(layers: list[np.ndarray]) -> np.ndarray:
    """Draw tiles of one size over each other, the first one at the bottom.

    Returns:
        np.ndarray: New pixels, opaque where any layer is opaque.

    """
    below = layers[0].astype(np.float32) / 255
    for layer in layers[1:]:
        above = layer.astype(np.float32) / 255
        cover = above[..., 3:]
        under = below[..., 3:] * (1 - cover)
        alpha = cover + under
        color = above[..., :3] * cover + below[..., :3] * under
        color /= np.where(alpha > 0, alpha, 1)
        below = np.concatenate((color, alpha), axis=-1)
    return np.rint(below * 255).astype(np.uint8)


def tile_name(texture: str | tuple[str, ...]) -> Key:
    """Name of a block texture, or of layers composed into one.

    Returns:
        Key: The texture itself, or its layers joined with `+`.

    """
    return texture if isinstance(texture, str) else "+".join(texture)


def add_block_textures(
    builder: AtlasBuilder[Key],
    textures_dir: Path,
    content: Content,
    colorkey: tuple[int, int, int],
) -> dict[Key, Key]:
    """Pack every block texture, made to cover a tile.

    Layered textures are composed here, each layer fitted to the tile first,
    so their sizes may differ.

    Returns:
        dict[Key, Key]: Where each tile was packed. A enlarged or cropped
        texture gets its own key, apart from items using the original.

    """
    keys: dict[Key, Key] = {}
    for block in content.blocks:
        for texture in block.spec.textures:
            name = tile_name(texture)
            layers = (texture,) if isinstance(texture, str) else texture
            sources = [
                load_rgba(textures_dir / f"{layer}.png", colorkey)
                for layer in layers
            ]
            tiles = [fit_to_tile(s, content.game.tile_size) for s in sources]
            tile = layer_tiles(tiles) if len(tiles) > 1 else tiles[0]
            changed = len(tiles) == 1 and tile.shape != sources[0].shape
            keys[name] = f"{name}@tile" if changed else name
            builder.add(keys[name], tile)
    return keys


def tile_regions(
    content: Content,
    regions: Mapping[Key, Region],
    tile_keys: Mapping[Key, Key],
) -> tuple[dict[Key, Region], dict[int, tuple[Region, ...]]]:
    """Find the packed block textures.

    Returns:
        tuple[dict[Key, Region], dict[int, tuple[Region, ...]]]: Tiles by
        texture, and the variants of every block by id.

    """
    tiles = {texture: regions[key] for texture, key in tile_keys.items()}
    blocks = {
        block.id: tuple(tiles[tile_name(t)] for t in block.spec.textures)
        for block in content.blocks
    }
    return tiles, blocks


def item_images(
    content: Content,
    regions: Mapping[Key, Region],
    tiles: Mapping[Key, Region],
    item_keys: Mapping[str, Key],
) -> tuple[dict[str, Region], dict[str, Region]]:
    """Images of items, as packed and as drawn on the ground and in hand.

    A block item is drawn as its tile, `drop_size` across. Other images
    smaller than `drop_size` are enlarged by a whole factor; larger ones
    keep their size.

    Returns:
        tuple[dict[str, Region], dict[str, Region]]: Packed images and
        drawn images, by item name.

    """
    icons: dict[str, Region] = {}
    drawn: dict[str, Region] = {}
    for item in content.items:
        size = item.spec.drop_size
        tile = tiles.get(item.spec.icon)
        if tile is not None:
            icons[item.name] = tile
            drawn[item.name] = tile.drawn_at(size, size)
            continue
        image = regions[item_keys[item.name]]
        factor = whole_factor(size, max(image.size))
        icons[item.name] = image
        drawn[item.name] = image.drawn_at(
            image.width * factor, image.height * factor
        )
    return icons, drawn


@dataclass(frozen=True, slots=True)
class Animation:
    """An animation clip with its atlas regions."""

    clip: AnimationClip
    frames: tuple[Region, ...]

    def frame(self, age: int) -> Region:
        """Region to show after `age` ticks.

        Returns:
            Region: The frame.

        """
        return self.frames[self.clip.frame_index(age, len(self.frames))]

    def frame_index(self, age: int) -> int:
        """Index of the frame shown after `age` ticks.

        Returns:
            int: Index into `frames`.

        """
        return self.clip.frame_index(age, len(self.frames))

    @property
    def duration(self) -> int:
        """Ticks until a non looping clip reaches its last frame's end."""
        return len(self.frames) * max(self.clip.frame_ticks, 1)


def body_copies(
    animations: AnimationsConfig,
) -> dict[tuple[str, str, str], AnimationClip]:
    """Mob clips read from their armless and bare directories.

    Returns:
        dict[tuple[str, str, str], AnimationClip]: Copies by directory kind
        (`armless` or `bare`), mob and action.

    """
    return {
        (part, mob, action): clip.model_copy(
            update={"path": f"{directory}/{action}"}
        )
        for mob, tool_use in animations.tool_use.items()
        for part, directory in (
            ("armless", tool_use.armless),
            ("bare", tool_use.bare),
        )
        for action, clip in animations.mobs[mob].items()
    }


class ClientAssets:
    """The texture atlas and lookups into it."""

    def __init__(  # ruff: ignore[too-many-locals, too-many-statements]
        self,
        ctx: moderngl.Context,
        textures_dir: Path,
        content: Content,
        animations: AnimationsConfig,
    ) -> None:
        """Load and pack all textures."""
        self.textures_dir = textures_dir
        self.animations = animations
        self.colorkey = animations.transparent_color
        builder: AtlasBuilder[Key] = AtlasBuilder(width=1024)

        def add(key: Key) -> Key:
            if key not in builder.images:
                file = textures_dir / f"{key}.png"
                builder.add(key, load_rgba(file, self.colorkey))
            return key

        def add_clip(clip: AnimationClip) -> list[Key]:
            files = frame_files(textures_dir / clip.path)
            if not files:
                msg = f"No frames in {textures_dir / clip.path}"
                raise FileNotFoundError(msg)
            return [add(f"{clip.path}/{f.stem}") for f in files]

        tile_keys = add_block_textures(
            builder, textures_dir, content, self.colorkey
        )
        item_keys = {item.name: add(item.spec.icon) for item in content.items}
        sprite_keys = {name: add(f"mob/{name}") for name in KINDS}
        mob_keys = {
            (mob, action): (clip, add_clip(clip))
            for mob, actions in animations.mobs.items()
            for action, clip in actions.items()
        }
        body_keys = {
            key: (clip, add_clip(clip))
            for key, clip in body_copies(animations).items()
        }
        arm_keys = {
            mob: [
                add(f"{tool_use.arm}/{f.stem}")
                for f in frame_files(textures_dir / tool_use.arm)
            ]
            for mob, tool_use in animations.tool_use.items()
        }
        scissor_keys = {
            item: (add(tool.front), add(tool.back))
            for tool_use in animations.tool_use.values()
            for item, tool in tool_use.scissors.items()
        }
        particle_keys = {
            name: (clip, add_clip(clip))
            for name, clip in animations.particles.items()
        }
        breakage_keys = fit_images(
            builder,
            add_clip(animations.tile_breakage),
            content.game.tile_size,
        )
        cloud_keys = [
            add(f"{animations.clouds}/{f.stem}")
            for f in frame_files(textures_dir / animations.clouds)
        ]
        gui_keys = (add(animations.cursor), add(ARROW))

        pixels, regions = builder.build()
        self.atlas = create_texture(ctx, pixels)
        LOGGER.debug(
            "Packed %s images into a %sx%s atlas",
            len(regions),
            pixels.shape[1],
            pixels.shape[0],
        )

        self.tiles, self.blocks = tile_regions(content, regions, tile_keys)
        self.icons, self.items = item_images(
            content, regions, self.tiles, item_keys
        )
        self.mobs = {
            key: Animation(clip, tuple(regions[k] for k in keys))
            for key, (clip, keys) in mob_keys.items()
        }
        self.mob_sprites = {
            name: regions[key] for name, key in sprite_keys.items()
        }
        """Single image of every hostile creature, by kind."""
        self.armless, self.bare = (
            {
                (mob, action): Animation(clip, tuple(regions[k] for k in keys))
                for (of, mob, action), (clip, keys) in body_keys.items()
                if of == part
            }
            for part in ("armless", "bare")
        )
        """Copies of mob clips for swinging items: without the front arm,
        and without either arm for two-handed swings."""
        self.arms = {
            mob: tuple(regions[k] for k in keys)
            for mob, keys in arm_keys.items()
        }
        """Front arm poses per mob, matching `rigs[mob].arm`."""
        self.scissors = {
            item: (regions[front], regions[back])
            for item, (front, back) in scissor_keys.items()
        }
        """Front and back halves of items drawn as two halves in use, by
        item name, see `ScissorTool`."""
        self.rigs = {
            mob: load_model(Rig, textures_dir / tool_use.rig)
            for mob, tool_use in animations.tool_use.items()
        }
        self._check_rigs()
        self.particles = {
            name: Animation(clip, tuple(regions[k] for k in keys))
            for name, (clip, keys) in particle_keys.items()
        }
        self.breakage = tuple(regions[k] for k in breakage_keys)
        self.clouds = tuple(
            sorted(
                (regions[k] for k in cloud_keys),
                key=lambda r: r.width * r.height,
            )
        )
        """Cloud images, smallest first."""
        self.cursor, self.arrow = (regions[k] for k in gui_keys)

        variants = max((len(v) for v in self.blocks.values()), default=1)
        self.block_uvs = np.zeros(
            (len(content.blocks), variants, 4), dtype=np.float32
        )
        """`block_uvs[block, variant]`: texture coordinates for bulk use."""
        for block, block_regions in self.blocks.items():
            for variant in range(variants):
                region = block_regions[min(variant, len(block_regions) - 1)]
                self.block_uvs[block, variant] = region.uv

    def _check_rigs(self) -> None:
        """Make sure every rig matches the frames it describes.

        Raises:
            ValueError: A rig and its frames disagree.

        """
        for mob, rig in self.rigs.items():
            arms = self.arms[mob]
            if not len(arms) == len(rig.arm.angles) == len(rig.arm.hands):
                msg = f"{mob}: rig describes another number of arm poses"
                raise ValueError(msg)
            if rig.arm.names and len(rig.arm.names) != len(arms):
                msg = f"{mob}: rig names another number of arm poses"
                raise ValueError(msg)
            self._check_styles(mob, rig)
            for (owner, action), animation in self.mobs.items():
                if owner != mob:
                    continue
                shoulders = rig.shoulders.get(action, ())
                if len(shoulders) != len(animation.frames):
                    msg = f"{mob}/{action}: rig has no shoulder per frame"
                    raise ValueError(msg)

    def _check_styles(self, mob: str, rig: Rig) -> None:
        """Make sure keyframed swings use arm and body poses that exist.

        Raises:
            ValueError: A keyframe names an unknown pose.

        """
        for kind, keys in self.animations.tool_use[mob].styles.items():
            for key in keys:
                for arm in (key.arm, key.off_arm):
                    if arm is not None and arm not in rig.arm.names:
                        msg = f"{mob} {kind} swing: unknown arm pose {arm!r}"
                        raise ValueError(msg)
                if key.body is not None and (mob, key.body) not in self.mobs:
                    msg = f"{mob} {kind} swing: unknown body pose {key.body!r}"
                    raise ValueError(msg)

    def slot_icon(self, item: ItemDef, slot_size: int) -> Region:
        """Image of an item as drawn in an inventory slot.

        Small images are enlarged by the largest whole factor that fits the
        slot. Ones larger than the slot show their middle.

        Returns:
            Region: The image, with the size to draw it at.

        """
        image = self.icons[item.name].crop(slot_size, slot_size)
        factor = whole_factor(slot_size, max(image.size))
        return image.drawn_at(image.width * factor, image.height * factor)

    def load_image(
        self, path: str, size: tuple[int, int] | None = None
    ) -> np.ndarray:
        """Load a texture outside of the atlas, e.g. a background.

        Returns:
            np.ndarray: RGBA pixels.

        """
        return load_rgba(
            self.textures_dir / f"{path}.png", self.colorkey, size
        )

    def release(self) -> None:
        """Free the atlas textures."""
        self.atlas.release()
