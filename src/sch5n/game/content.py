# Copyright (c) 2026 Schunche
"""Block and item definitions, and the bundle of all loaded game data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from sch5n.game.config import (
    AnimationsConfig,
    GameConfig,
    Settings,
    UiConfig,
    load_model,
)
from sch5n.game.inventory import CRAFTING_SIDE, MAX_CRAFTING_SIDE
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

AIR = 0
"""Block id of empty space."""


type Layers = Annotated[tuple[str, ...], Field(min_length=1)]
"""Textures drawn over each other into one tile, bottom first."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TreePart(StrEnum):
    """What a block is in a tree."""

    TRUNK = "trunk"
    """Wood: falls with the tree and drops its log."""
    CROWN = "crown"
    """Leaves: fall with the tree."""


class Trim(_Model):
    """A tool that turns a block into another one instead of breaking it."""

    tool: str
    """Tool type that trims, like `lopper`."""
    into: str
    """Block left after trimming."""
    durability: int = Field(default=50, gt=0)


class ChanceDrop(_Model):
    """An extra item a broken block may drop, on top of its `drop`."""

    item: str
    chance: float = Field(default=1.0, gt=0, le=1)
    """Probability that it drops at all."""
    min_amount: int = Field(default=1, gt=0)
    max_amount: int = Field(default=1, gt=0)


class BlockSpec(_Model):
    """A block as written in `blocks.json`."""

    textures: tuple[str | Layers, ...]
    """Tile variants: each a texture, or a list of textures to layer."""
    solid: bool = False
    durability: int | None = None
    tool: str | None = None
    """Tool type that breaks it best. `None` means unbreakable."""
    slower_tools: tuple[str, ...] = ()
    """Other tool types that break it too, with `slower_tool_power` of
    their power. A pickaxe digs dirt, but a shovel is made for it."""
    slower_tool_power: float = Field(default=0.7, gt=0, le=1)
    drop: str | None = None
    """Item id dropped when broken."""
    extra_drops: tuple[ChanceDrop, ...] = ()
    """Items that may also drop when the block is broken."""
    transform_to: str | None = None
    """Block left behind instead of air when broken."""
    particle: str | None = None
    """Ambient particle emitted by the block."""
    trim: Trim | None = None
    """Like a lopper turning a leafy log into a log: nothing drops and
    nothing falls."""
    tree: TreePart | None = None
    """Part of a tree: breaking a trunk block fells everything above."""
    aliases: tuple[str, ...] = ()
    """Legacy names accepted when loading maps."""
    plant_on: tuple[str, ...] = ()
    """For plants: the blocks it can be planted on."""
    grows_after: tuple[float, float] | None = None
    """For saplings: the shortest and longest seconds until it is a tree."""
    crafting_side: int | None = Field(
        default=None, ge=CRAFTING_SIDE, le=MAX_CRAFTING_SIDE
    )
    """For stations: the crafting grid side of players within reach."""
    hand_pickup: bool = False
    """An empty hand picks it up at once."""


class BlocksFile(_Model):
    """`blocks.json`."""

    default_durability: int = 100
    blocks: dict[str, BlockSpec]


class ItemSpec(_Model):
    """An item as written in `items.json`."""

    name: str
    icon: str
    description: str = ""
    """Shown when the item is hovered in the inventory."""
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
    aliases: tuple[str, ...] = ()
    """Legacy names accepted when loading saved inventories."""
    food: int = Field(default=0, ge=0)
    """Hunger points eating it restores. Zero means it is not food."""


class ItemsFile(_Model):
    """`items.json`."""

    items: dict[str, ItemSpec]


class RecipeResult(_Model):
    """What a recipe makes."""

    item: str
    amount: int = Field(default=1, gt=0)


class RecipeSpec(_Model):
    """A recipe in `recipes.json`, shapeless or shaped.

    A shapeless one lists `ingredients`, each filling one slot anywhere. A
    shaped one draws its `pattern`, a row per string, with the items named
    in `key` and spaces for empty slots. It fits anywhere in the grid. A
    symbol may list several items, any of which fills its slots.
    """

    ingredients: tuple[str, ...] = Field(
        default=(), max_length=MAX_CRAFTING_SIDE**2
    )
    pattern: tuple[str, ...] = Field(default=(), max_length=MAX_CRAFTING_SIDE)
    key: dict[str, str | tuple[str, ...]] = Field(default_factory=dict)
    result: RecipeResult

    def choices(self, symbol: str) -> tuple[str, ...]:
        """List the items a pattern symbol stands for.

        Returns:
            tuple[str, ...]: The item names.

        """
        named = self.key[symbol]
        return (named,) if isinstance(named, str) else named

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if bool(self.ingredients) == bool(self.pattern):
            msg = "A recipe needs ingredients or a pattern, not both"
            raise ValueError(msg)
        if not self.pattern:
            return self
        widths = {len(row) for row in self.pattern}
        if len(widths) != 1 or max(widths) > MAX_CRAFTING_SIDE:
            msg = "Pattern rows must be equally long and fit the grid"
            raise ValueError(msg)
        symbols = set("".join(self.pattern)) - {" "}
        if not symbols or not symbols <= self.key.keys():
            msg = "Every pattern symbol needs an item in the key"
            raise ValueError(msg)
        if not all(self.choices(symbol) for symbol in self.key):
            msg = "A key symbol needs at least one item"
            raise ValueError(msg)
        return self


class RecipesFile(_Model):
    """`recipes.json`."""

    recipes: tuple[RecipeSpec, ...] = ()


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
            trim = block.spec.trim
            if trim is not None and trim.into not in self._by_name:
                msg = f"{block.name}: unknown trim into {trim.into!r}"
                raise ValueError(msg)

        for block in self._by_name.values():
            for ground in block.spec.plant_on:
                if ground not in self._by_name:
                    msg = f"{block.name}: unknown plant_on {ground!r}"
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
        self._aliases = {
            alias: item.name
            for item in self._items.values()
            for alias in item.spec.aliases
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
            for extra in block.spec.extra_drops:
                if extra.item not in self:
                    msg = f"{block.name}: unknown drop {extra.item!r}"
                    raise ValueError(msg)
                if extra.min_amount > extra.max_amount:
                    msg = f"{block.name}: min_amount above max_amount"
                    raise ValueError(msg)

    def __contains__(self, name: object) -> bool:
        """Check whether an item exists, by name or legacy alias.

        Returns:
            bool: True if `name` is a registered item.

        """
        return self._aliases.get(str(name), name) in self._items

    def __iter__(self) -> Iterator[ItemDef]:
        """Iterate over items.

        Returns:
            Iterator: The iterator.

        """
        return iter(self._items.values())

    def __getitem__(self, name: str) -> ItemDef:
        """Get an item by name or legacy alias.

        Returns:
            ItemDef: The item.

        """
        return self._items[self._aliases.get(name, name)]


def _check_recipes(
    recipes: tuple[RecipeSpec, ...], items: ItemRegistry
) -> None:
    """Make sure recipes use known items and make stacks that exist.

    Raises:
        ValueError: A recipe names an unknown item, or makes more than a
            stack of it holds.

    """
    for recipe in recipes:
        result = recipe.result
        keyed = (n for symbol in recipe.key for n in recipe.choices(symbol))
        names = (*recipe.ingredients, *keyed, result.item)
        for name in names:
            if name not in items:
                msg = f"Recipe for {result.item}: unknown item {name!r}"
                raise ValueError(msg)
        if result.amount > items[result.item].spec.max_stack:
            msg = f"Recipe for {result.item}: more than a stack"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Content:
    """Everything loaded from the data directory."""

    game: GameConfig
    blocks: BlockRegistry
    items: ItemRegistry
    recipes: tuple[RecipeSpec, ...] = ()

    @classmethod
    def load(cls, data_dir: Path) -> Content:
        """Load and cross-validate the game data files.

        Returns:
            Content: The loaded content.

        """
        blocks = BlockRegistry(
            load_model(BlocksFile, data_dir / "blocks.json")
        )
        items = ItemRegistry(
            load_model(ItemsFile, data_dir / "items.json"), blocks
        )
        recipes = load_model(RecipesFile, data_dir / "recipes.json").recipes
        _check_recipes(recipes, items)
        return cls(
            game=load_model(GameConfig, data_dir / "game.json"),
            blocks=blocks,
            items=items,
            recipes=recipes,
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
