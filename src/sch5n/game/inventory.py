# Copyright (c) 2026 Schunche
"""Item stacks, the inventory grid and the item held by the cursor."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sch5n.game.vitals import Vitals

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from sch5n.game.content import ItemDef

HOTBAR_SIZE = 10
CRAFTING_SIDE = 2
"""Slots along one side of the crafting grid a player carries."""
MAX_CRAFTING_SIDE = 3
"""The largest grid, like at a crafting bench."""
ARMOR_PARTS = ("head", "chest", "legs")
"""What the armor slots hold, in order."""
DEFENSE_PERCENT = 6
"""Share of damage each defense point takes away."""
MAX_DEFENSE_PERCENT = 80


@dataclass(slots=True)
class ItemStack:
    """Some amount of one item."""

    item: ItemDef
    amount: int = 1

    @property
    def max_amount(self) -> int:
        """Largest amount allowed in one stack."""
        return self.item.spec.max_stack

    @property
    def room(self) -> int:
        """How many more fit in this stack."""
        return self.max_amount - self.amount

    def can_merge(self, other: ItemStack) -> bool:
        """Whether `other` may be added onto this stack.

        Returns:
            bool: Same stackable item.

        """
        return self.item is other.item and self.item.is_stackable

    def split(self, amount: int) -> ItemStack:
        """Take `amount` off this stack into a new one.

        Returns:
            ItemStack: The taken part.

        """
        amount = min(amount, self.amount)
        self.amount -= amount
        return ItemStack(self.item, amount)

    @property
    def display_name(self) -> str:
        """Name shown to the player."""
        if self.amount > 1:
            return f"{self.item.spec.name} (x{self.amount})"
        return self.item.spec.name


type Slot = ItemStack | None


class Inventory:  # ruff: ignore[too-many-public-methods]
    """A fixed number of slots plus the stack held by the cursor.

    The first `HOTBAR_SIZE` slots form the hotbar.
    """

    def __init__(self, size: int, items: Iterable[ItemStack] = ()) -> None:
        """Create an inventory, filling `items` into the first slots.

        Raises:
            ValueError: `size` is smaller than the hotbar.

        """
        if size < HOTBAR_SIZE:
            msg = f"Inventory needs at least {HOTBAR_SIZE} slots"
            raise ValueError(msg)
        self.slots: list[Slot] = [None] * size
        self.cursor: Slot = None
        self.crafting: list[Slot] = [None] * CRAFTING_SIDE**2
        """The square crafting grid, row by row."""
        self.armor: list[Slot] = [None] * len(ARMOR_PARTS)
        """What is worn, one slot for each of `ARMOR_PARTS`."""
        self.selected: int = 0
        self.vitals = Vitals()
        self.stations: frozenset[str] = frozenset()
        """Names of the crafting stations in reach, set by the server."""
        """Health and hunger of the owner. They travel with the inventory,
        so saved worlds keep them."""
        """Index of the active hotbar slot."""
        for index, stack in enumerate(items):
            self.slots[index] = stack

    def __len__(self) -> int:
        """Count slots.

        Returns:
            int: Number of slots.

        """
        return len(self.slots)

    def __iter__(self) -> Iterator[Slot]:
        """Iterate over slots.

        Returns:
            Iterator: The iterator.

        """
        return iter(self.slots)

    def __getitem__(self, index: int) -> Slot:
        """Get a slot by index.

        Returns:
            Slot: The stack in the slot, `None` if empty.

        """
        return self.slots[index]

    @property
    def crafting_side(self) -> int:
        """Slots along one side of the crafting grid."""
        return math.isqrt(len(self.crafting))

    def resize_crafting(self, side: int) -> list[ItemStack]:
        """Change the size of the crafting grid.

        Stacks keep their row and column.

        Returns:
            list[ItemStack]: The stacks outside the new grid, which are
            no longer in it.

        """
        old = self.crafting_side
        grid: list[Slot] = [None] * side**2
        outside: list[ItemStack] = []
        for index, stack in enumerate(self.crafting):
            row, column = divmod(index, old)
            if row < side and column < side:
                grid[row * side + column] = stack
            elif stack is not None:
                outside.append(stack)
        self.crafting = grid
        return outside

    @property
    def is_full(self) -> bool:
        """No empty slot left."""
        return None not in self.slots

    @property
    def held(self) -> Slot:
        """The stack in use: the cursor's, otherwise the selected one."""
        return (
            self.cursor
            if self.cursor is not None
            else self.slots[self.selected]
        )

    def select(self, index: int) -> None:
        """Select a hotbar slot, wrapping around."""
        self.selected = index % HOTBAR_SIZE

    def scroll(self, steps: int) -> None:
        """Move the hotbar selection."""
        self.select(self.selected + steps)

    def copy(self) -> Inventory:
        """Copy the inventory and every stack in it.

        Returns:
            Inventory: An independent copy.

        """

        def stack_copy(stack: Slot) -> Slot:
            return (
                None if stack is None else ItemStack(stack.item, stack.amount)
            )

        copied = Inventory(len(self))
        copied.slots = [stack_copy(s) for s in self.slots]
        copied.crafting = [stack_copy(s) for s in self.crafting]
        copied.armor = [stack_copy(s) for s in self.armor]
        copied.cursor = stack_copy(self.cursor)
        copied.selected = self.selected
        return copied

    @property
    def defense(self) -> int:
        """Defense points of everything worn."""
        return sum(s.item.spec.defense for s in self.armor if s is not None)

    def soften(self, damage: int) -> int:
        """Take the worn armor into account for a blow.

        Returns:
            int: The damage that gets through, at least 1.

        """
        percent = min(self.defense * DEFENSE_PERCENT, MAX_DEFENSE_PERCENT)
        return max(1, round(damage * (100 - percent) / 100))

    def armor_click(self, index: int) -> None:
        """Wear or take off a piece of armor with the cursor.

        A piece goes only into the slot of its body part. The piece worn
        there comes onto the cursor.
        """
        if not 0 <= index < len(self.armor):
            return
        cursor = self.cursor
        if cursor is not None and cursor.item.spec.armor != ARMOR_PARTS[index]:
            return
        self._swap(self.armor, index)

    def locate(self, index: int) -> tuple[list[Slot], int] | None:
        """Find a slot numbered through the inventory, then the grid.

        Index `len(self)` is the first slot of the crafting grid.

        Returns:
            tuple[list[Slot], int] | None: The list holding the slot and
            its place there, `None` if there is no such slot.

        """
        if 0 <= index < len(self.slots):
            return self.slots, index
        index -= len(self.slots)
        if 0 <= index < len(self.crafting):
            return self.crafting, index
        return None

    def spread(self, indices: Iterable[int], *, single: bool) -> None:
        """Share the cursor stack among slots, like dragging over them.

        Only empty slots and ones with room for the same item take part.
        Each gets an equal share, or one item if `single`; with more slots
        than items, the first ones get one each. The rest stays on the
        cursor.

        Args:
            indices: Slots as numbered by `locate`, in the order visited.
            single: Place one item in each.

        """
        cursor = self.cursor
        if cursor is None:
            return
        targets: list[tuple[list[Slot], int]] = []
        for index in dict.fromkeys(indices):
            found = self.locate(index)
            if found is None:
                continue
            slot = found[0][found[1]]
            if slot is None or (slot.can_merge(cursor) and slot.room > 0):
                targets.append(found)
        if not targets:
            return
        targets = targets[: cursor.amount]
        share = 1 if single else cursor.amount // len(targets)
        for slots, place in targets:
            slot = slots[place]
            if slot is None:
                slots[place] = cursor.split(min(share, cursor.max_amount))
            else:
                moved = min(share, slot.room)
                slot.amount += moved
                cursor.amount -= moved
        if cursor.amount == 0:
            self.cursor = None

    def gather(self, index: int) -> None:
        """Collect every matching item of the inventory into one slot.

        The cursor stack, as picked up by the first click of a double click,
        goes back into the slot first.
        """
        found = self.locate(index)
        if found is None:
            return
        slots, place = found
        target, cursor = slots[place], self.cursor
        if target is None:
            slots[place], self.cursor = cursor, None
        elif cursor is not None and target.can_merge(cursor):
            moved = min(target.room, cursor.amount)
            target.amount += moved
            cursor.amount -= moved
            if cursor.amount == 0:
                self.cursor = None
        target = slots[place]
        if target is None:
            return
        for other, stack in enumerate(self.slots):
            if stack is None or stack is target or not target.can_merge(stack):
                continue
            moved = min(target.room, stack.amount)
            target.amount += moved
            stack.amount -= moved
            if stack.amount == 0:
                self.slots[other] = None

    def room_for(self, item: ItemDef) -> int:
        """Count how many more of an item the slots can take.

        Returns:
            int: Free space, in items.

        """
        probe = ItemStack(item)
        return sum(
            item.spec.max_stack
            if slot is None
            else (slot.room if slot.can_merge(probe) else 0)
            for slot in self.slots
        )

    def stow_crafting(self, index: int) -> None:
        """Move a stack of the crafting grid into the inventory.

        What does not fit stays in the grid.
        """
        if not 0 <= index < len(self.crafting):
            return
        stack = self.crafting[index]
        if stack is not None:
            self.crafting[index] = self.add(stack)

    def add(self, stack: ItemStack) -> ItemStack | None:
        """Put a stack in, topping up existing stacks first.

        `stack` is consumed (its amount is reduced).

        Returns:
            ItemStack | None: What did not fit, `None` if everything fit.

        """
        for slot in self.slots:
            if stack.amount == 0:
                return None
            if slot is not None and slot.can_merge(stack):
                moved = min(slot.room, stack.amount)
                slot.amount += moved
                stack.amount -= moved

        if stack.amount == 0:
            return None

        for index, slot in enumerate(self.slots):
            if slot is None:
                self.slots[index] = ItemStack(stack.item, stack.amount)
                stack.amount = 0
                return None

        return stack

    def consume_held(self, amount: int = 1) -> None:
        """Remove items from the held stack."""
        if self.cursor is not None:
            self.cursor.amount -= amount
            if self.cursor.amount <= 0:
                self.cursor = None
            return
        slot = self.slots[self.selected]
        if slot is not None:
            slot.amount -= amount
            if slot.amount <= 0:
                self.slots[self.selected] = None

    def _swap(self, slots: list[Slot], index: int) -> None:
        slots[index], self.cursor = self.cursor, slots[index]

    def left_click(self, index: int, *, crafting: bool = False) -> None:
        """Pick up, put down, swap, or merge the cursor stack into a slot.

        `index` is a slot of the crafting grid if `crafting` is set.
        """
        slots = self.crafting if crafting else self.slots
        slot, cursor = slots[index], self.cursor
        if slot is not None and cursor is not None and slot.can_merge(cursor):
            moved = min(slot.room, cursor.amount)
            slot.amount += moved
            cursor.amount -= moved
            if cursor.amount == 0:
                self.cursor = None
            return
        self._swap(slots, index)

    def right_click(self, index: int, *, crafting: bool = False) -> None:
        """Take half of a stack, or put a single item down.

        `index` is a slot of the crafting grid if `crafting` is set.
        """
        slots = self.crafting if crafting else self.slots
        slot, cursor = slots[index], self.cursor

        if cursor is None:
            if slot is None:
                return
            if not slot.item.is_stackable:
                self._swap(slots, index)
                return
            taken = slot.split(slot.amount // 2)
            if taken.amount:
                self.cursor = taken
            return

        if not cursor.item.is_stackable:
            self._swap(slots, index)
            return

        if slot is None:
            slots[index] = cursor.split(1)
        elif not slot.can_merge(cursor):
            self._swap(slots, index)
            return
        elif slot.room > 0:
            slot.amount += 1
            cursor.amount -= 1

        if cursor.amount == 0:
            self.cursor = None
