# Copyright (c) 2026 Schunche
"""Item stacks, the inventory grid and the item held by the cursor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from sch5n.game.content import ItemDef

HOTBAR_SIZE = 10


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
        if self.item.is_stackable:
            return f"{self.item.spec.name} (x{self.amount})"
        return self.item.spec.name


type Slot = ItemStack | None


class Inventory:
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
        self.selected: int = 0
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

    def _swap(self, index: int) -> None:
        self.slots[index], self.cursor = self.cursor, self.slots[index]

    def left_click(self, index: int) -> None:
        """Pick up, put down, swap, or merge the cursor stack into a slot."""
        slot, cursor = self.slots[index], self.cursor
        if slot is not None and cursor is not None and slot.can_merge(cursor):
            moved = min(slot.room, cursor.amount)
            slot.amount += moved
            cursor.amount -= moved
            if cursor.amount == 0:
                self.cursor = None
            return
        self._swap(index)

    def right_click(self, index: int) -> None:
        """Take half of a stack, or put a single item down."""
        slot, cursor = self.slots[index], self.cursor

        if cursor is None:
            if slot is None:
                return
            if not slot.item.is_stackable:
                self._swap(index)
                return
            taken = slot.split(slot.amount // 2)
            if taken.amount:
                self.cursor = taken
            return

        if not cursor.item.is_stackable:
            self._swap(index)
            return

        if slot is None:
            self.slots[index] = cursor.split(1)
        elif not slot.can_merge(cursor):
            self._swap(index)
            return
        elif slot.room > 0:
            slot.amount += 1
            cursor.amount -= 1

        if cursor.amount == 0:
            self.cursor = None
