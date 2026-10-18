# Copyright (c) 2026 Schunche
"""Experimental software."""

from copy import deepcopy
from typing import TYPE_CHECKING, override

from sch5n.deprecated.gui import CursorSlot, Inventory
from sch5n.deprecated.item import Item, Tool
from sch5n.deprecated.item_data import ITEM_DATA
from sch5n.deprecated.loader import NAME_SPACE
from sch5n.deprecated.mob import Mob

if TYPE_CHECKING:
    from sch5n.deprecated.animation import Animation
    from sch5n.deprecated.tilemap import Tilemap
    from sch5n.math.vector import FloatTuple2


class Player(Mob):
    """A class representing the player character in the game."""

    def __init__(
        self,
        assets: dict[str, dict[str, Animation]],
        pos: FloatTuple2,
        game_mode: str = "survival",
    ) -> None:
        """Initialize a Player object.

        Args:
            assets (dict[str, dict[str, Animation]]): Player assets.
            pos (FloatTuple2): The initial position of the player.

        """
        super().__init__(species="player", assets=assets, pos=pos)
        self.airTime: int = 0

        self.max_jumps: int
        if game_mode == "admin":
            self.max_jumps = 2**8
        else:
            self.max_jumps = 1
        self.jumps: int = self.max_jumps

        self.wall_slide = False

        # Inventory management
        self.inventory: Inventory = Inventory(
            deepcopy(ITEM_DATA[0]), deepcopy(ITEM_DATA[1])
        )
        self.hotbar_num: int = 0
        self.cursor_slot: CursorSlot = CursorSlot()

        self.tool_use_penalty: int = 0

    def get_item_in_hand(self) -> Item | None:
        return (
            self.inventory.get_item_by_num(self.hotbar_num)
            if self.cursor_slot.get_item() is None
            else self.cursor_slot.get_item()
        )

    def get_inventory(self) -> dict[int, Item | None]:
        """You can only assingn to this for some reason."""
        return self.inventory.slots

    @override
    def update(self, tilemap: Tilemap, movement: FloatTuple2 = (0, 0)) -> None:
        """Update the player's position and animation.

        Args:
            tilemap: The tilemap object representing the game's environment.
            movement (tuple, optional): A tuple representing movement input.

        """
        # Inherit parent's .update
        super().update(tilemap, movement=movement)

        # Reset number of jumps
        self.airTime += 1
        if self.collisions["down"]:
            self.airTime = 0
            self.jumps = self.max_jumps

        activation_time = 4

        # Check for wall slide
        self.wall_slide = False
        if (
            self.collisions["left"] or self.collisions["right"]
        ) and self.airTime > activation_time:
            self.wall_slide = True
            self.velocity = (self.velocity[0], min(self.velocity[1], 0.5))
            if self.collisions["right"]:
                self.flip = False
            else:
                self.flip = True
            self.set_action("wall_slide")

        # Set action
        if not self.wall_slide:
            if self.airTime > activation_time:
                self.set_action("jump")
            elif movement[0] != 0:
                self.set_action("run")
            else:
                self.set_action("idle")

    def jump(self) -> None:
        if self.wall_slide:
            if self.flip:
                self.velocity = (3.5, self.velocity[1])
            else:
                self.velocity = (-3.5, self.velocity[1])

            self.velocity = (self.velocity[0], -2.5)
            self.airTime = 5
            self.jumps = max(0, self.jumps - 1)

        elif self.jumps:
            self.velocity = (self.velocity[0], -3)
            self.jumps -= 1
            self.airTime = 5

    def is_able_to_break(self, block: str) -> bool:
        """Whether the player can break the given block with the given tool.

        Returns:
            bool: Whether the player can break the given block with the tool.

        """
        tool = self.get_item_in_hand()
        if (tool is None) or (not isinstance(tool, Tool)):
            return False
        for tool_type in tool.tool_type:
            if block in NAME_SPACE["toolRequired"][tool_type]:
                return True
        return False

    def break_tile_with(self, block: str) -> str | None:
        """Tool type the player is able to break the given block with.

        Args:
            block (str): The block to check

        Returns:
            str: The tool type if the player is able to break the tile.

        """
        tool = self.get_item_in_hand()
        if (tool is None) or (not isinstance(tool, Tool)):
            return None
        for tool_type in tool.tool_type:
            if block in NAME_SPACE["toolRequired"][tool_type]:
                return tool_type
        return "pickaxe"
