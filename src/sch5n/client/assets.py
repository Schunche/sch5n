# Copyright (c) 2026 Schunche
"""Loads every texture the client needs into a single atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from sch5n.client.render.atlas import AtlasBuilder, Region, create_texture
from sch5n.client.render.image import load_rgba
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from pathlib import Path

    import moderngl

    from sch5n.game.config import AnimationClip, AnimationsConfig
    from sch5n.game.content import Content

type Key = str
"""Texture path relative to the textures directory, without extension."""


def frame_files(directory: Path) -> list[Path]:
    """Animation frames of a directory: PNGs with numeric names, in order.

    Returns:
        list[Path]: Frame files.

    """
    frames = [p for p in directory.glob("*.png") if p.stem.isdigit()]
    return sorted(frames, key=lambda p: int(p.stem))


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

    @property
    def duration(self) -> int:
        """Ticks until a non looping clip reaches its last frame's end."""
        return len(self.frames) * max(self.clip.frame_ticks, 1)


class ClientAssets:
    """The texture atlas and lookups into it."""

    def __init__(
        self,
        ctx: moderngl.Context,
        textures_dir: Path,
        content: Content,
        animations: AnimationsConfig,
    ) -> None:
        """Load and pack all textures."""
        self.textures_dir = textures_dir
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

        block_keys = {
            block.id: [add(texture) for texture in block.spec.textures]
            for block in content.blocks
        }
        item_keys = {item.name: add(item.spec.icon) for item in content.items}
        mob_keys = {
            (mob, action): (clip, add_clip(clip))
            for mob, actions in animations.mobs.items()
            for action, clip in actions.items()
        }
        particle_keys = {
            name: (clip, add_clip(clip))
            for name, clip in animations.particles.items()
        }
        breakage_keys = add_clip(animations.tile_breakage)
        cloud_keys = [
            add(f"{animations.clouds}/{f.stem}")
            for f in frame_files(textures_dir / animations.clouds)
        ]
        cursor_key = add(animations.cursor)

        pixels, regions = builder.build()
        self.atlas = create_texture(ctx, pixels)
        LOGGER.debug(
            "Packed %s images into a %sx%s atlas",
            len(regions),
            pixels.shape[1],
            pixels.shape[0],
        )

        self.blocks: dict[int, tuple[Region, ...]] = {
            block: tuple(regions[k] for k in keys)
            for block, keys in block_keys.items()
        }
        self.items = {name: regions[k] for name, k in item_keys.items()}
        self.mobs = {
            key: Animation(clip, tuple(regions[k] for k in keys))
            for key, (clip, keys) in mob_keys.items()
        }
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
        self.cursor = regions[cursor_key]

        variants = max((len(v) for v in self.blocks.values()), default=1)
        self.block_uvs = np.zeros(
            (len(content.blocks), variants, 4), dtype=np.float32
        )
        """`block_uvs[block, variant]`: texture coordinates for bulk use."""
        for block, block_regions in self.blocks.items():
            for variant in range(variants):
                region = block_regions[min(variant, len(block_regions) - 1)]
                self.block_uvs[block, variant] = region.uv

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
        """Free the atlas texture."""
        self.atlas.release()
