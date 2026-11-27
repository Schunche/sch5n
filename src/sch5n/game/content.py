# Copyright (c) 2026 Schunche
"""Block and item definitions, and the bundle of all loaded game data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from sch5n.game.config import (
    AnimationsConfig,
    GameConfig,
    Settings,
    UiConfig,
    load_model,
)
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

AIR = 0
"""Block id of empty space."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BlockSpec(_Model):
    """A block as written in `blocks.json`."""

    textures: tuple[str, ...]
    solid: bool = False
    durability: int | None = None
    tool: str | None = None
    """Tool type able to break it. `None` means unbreakable."""
    drop: str | None = None
    """Item id dropped when broken."""
    transform_to: str | None = None
    """Block left behind instead of air when broken."""
    particle: str | None = None
    """Ambient particle emitted by the block."""
    aliases: tuple[str, ...] = ()
    """Legacy names accepted when loading maps."""


class BlocksFile(_Model):
    """`blocks.json`."""

    default_durability: int = 100
    blocks: dict[str, BlockSpec]


class ItemSpec(_Model):
    """An item as written in `items.json`."""

    name: str
    icon: str
    max_stack: int = 1024
    use_time: int = 30
    """Ticks between uses."""
    tool_power: dict[str, int] = Field(default_factory=dict)
    damage: int = 0
    knockback: int = 0
    places: str | None = None
    """Block id placed by this item."""
    drop_size: int = 16
    """Size in pixels of the item when lying in the world."""


class ItemsFile(_Model):
    """`items.json`."""

    items: dict[str, ItemSpec]


@dataclass(frozen=True, slots=True)
class BlockDef:
    """A registered block."""

    id: int
    name: str
    spec: BlockSpec
    durability: int

    @property
    def is_breakable(self) -> bool:
        """Whether any tool can break it."""
        return self.spec.tool is not None


@dataclass(frozen=True, slots=True)
class ItemDef:
    """A registered item."""

    name: str
    spec: ItemSpec

    @property
    def is_stackable(self) -> bool:
        """Whether more than one fits in a slot."""
        return self.spec.max_stack > 1

    @property
    def is_tool(self) -> bool:
        """Whether it can break blocks."""
        return bool(self.spec.tool_power)


class BlockRegistry:
    """Maps block names to dense integer ids used by the tilemap."""

    def __init__(self, data: BlocksFile) -> None:
        """Register all blocks. Id 0 is reserved for air.

        Raises:
            ValueError: A block transforms into an unknown block.

        """
        self._blocks: list[BlockDef | None] = [None]
        self._by_name: dict[str, BlockDef] = {}
        self._aliases: dict[str, str] = {}

        for name, spec in data.blocks.items():
            block = BlockDef(
                id=len(self._blocks),
                name=name,
                spec=spec,
                durability=spec.durability or data.default_durability,
            )
            self._blocks.append(block)
            self._by_name[name] = block
            for alias in spec.aliases:
                self._aliases[alias] = name

        for block in self._by_name.values():
            target = block.spec.transform_to
            if target is not None and target not in self._by_name:
                msg = f"{block.name}: unknown transform_to {target!r}"
                raise ValueError(msg)

        count = len(self._blocks)
        self.solid = np.zeros(count, dtype=np.bool_)
        """`solid[block_id]` lookup table."""
        self.particle = np.zeros(count, dtype=np.bool_)
        """`particle[block_id]` lookup table, whether it emits particles."""
        for block in self._by_name.values():
            self.solid[block.id] = block.spec.solid
            self.particle[block.id] = block.spec.particle is not None

    def __len__(self) -> int:
        """Count block ids, air included.

        Returns:
            int: Number of ids.

        """
        return len(self._blocks)

    def __iter__(self) -> Iterator[BlockDef]:
        """Iterate over registered blocks (air excluded).

        Returns:
            Iterator: The iterator.

        """
        return iter(self._by_name.values())

    def get(self, block_id: int) -> BlockDef | None:
        """Block for an id. `None` for air.

        Returns:
            BlockDef | None: The block.

        """
        return self._blocks[block_id]

    def by_name(self, name: str) -> BlockDef:
        """Block for a name or legacy alias.

        Returns:
            BlockDef: The block.

        Raises:
            KeyError: Unknown block.

        """
        block = self._by_name.get(self._aliases.get(name, name))
        if block is None:
            msg = f"Unknown block: {name!r}"
            raise KeyError(msg)
        return block

    def id_of(self, name: str) -> int:
        """Id for a block name. Accepts legacy aliases.

        Returns:
            int: The block id.

        """
        return self.by_name(name).id


class ItemRegistry:
    """All known items by name."""

    def __init__(self, data: ItemsFile, blocks: BlockRegistry) -> None:
        """Register items and validate references to blocks.

        Raises:
            ValueError: An item or block refers to something unknown, or
                a stack size is not positive.

        """
        self._items = {
            name: ItemDef(name=name, spec=spec)
            for name, spec in data.items.items()
        }
        for item in self._items.values():
            if item.spec.places is not None:
                blocks.by_name(item.spec.places)
            if item.spec.max_stack < 1:
                msg = f"{item.name}: max_stack must be positive"
                raise ValueError(msg)

        for block in blocks:
            if block.spec.drop is not None and block.spec.drop not in self:
                msg = f"{block.name}: unknown drop {block.spec.drop!r}"
                raise ValueError(msg)

    def __contains__(self, name: object) -> bool:
        """Check whether an item exists.

        Returns:
            bool: True if `name` is a registered item.

        """
        return name in self._items

    def __iter__(self) -> Iterator[ItemDef]:
        """Iterate over items.

        Returns:
            Iterator: The iterator.

        """
        return iter(self._items.values())

    def __getitem__(self, name: str) -> ItemDef:
        """Get an item by name.

        Returns:
            ItemDef: The item.

        """
        return self._items[name]


@dataclass(frozen=True, slots=True)
class Content:
    """Everything loaded from the data directory."""

    game: GameConfig
    blocks: BlockRegistry
    items: ItemRegistry

    @classmethod
    def load(cls, data_dir: Path) -> Content:
        """Load and cross-validate the game data files.

        Returns:
            Content: The loaded content.

        """
        blocks = BlockRegistry(
            load_model(BlocksFile, data_dir / "blocks.json")
        )
        return cls(
            game=load_model(GameConfig, data_dir / "game.json"),
            blocks=blocks,
            items=ItemRegistry(
                load_model(ItemsFile, data_dir / "items.json"), blocks
            ),
        )


def load_settings(data_dir: Path, user_file: Path | None = None) -> Settings:
    """Load the user's settings.

    `user_file` wins if it exists, otherwise the bundled `settings.json`,
    otherwise built-in defaults. An unreadable user file is ignored.

    Returns:
        Settings: User settings.

    """
    if user_file is not None and user_file.exists():
        try:
            return load_model(Settings, user_file)
        except OSError, ValueError:
            LOGGER.exception("Ignoring broken settings file %s", user_file)
    path = data_dir / "settings.json"
    return load_model(Settings, path) if path.exists() else Settings()


def save_settings(settings: Settings, user_file: Path) -> None:
    """Write the user's settings, creating parent directories."""
    user_file.parent.mkdir(parents=True, exist_ok=True)
    user_file.write_text(settings.model_dump_json(indent=4), encoding="utf-8")


def load_ui(data_dir: Path) -> UiConfig:
    """Load `ui.json`.

    Returns:
        UiConfig: GUI styling.

    """
    return load_model(UiConfig, data_dir / "ui.json")


def load_animations(data_dir: Path) -> AnimationsConfig:
    """Load `animations.json`.

    Returns:
        AnimationsConfig: Animation definitions.

    """
    return load_model(AnimationsConfig, data_dir / "animations.json")
