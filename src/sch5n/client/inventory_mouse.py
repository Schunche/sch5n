# Copyright (c) 2026 Schunche
"""Mouse gestures on the open inventory: clicks, drags and double clicks.

The server makes every change. Here a gesture becomes the action to ask it
for.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import glfw

from sch5n.net.protocol import InventoryAction

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.window import MouseButtonEvent
    from sch5n.game.inventory import Inventory
    from sch5n.net.client import ClientSession

DOUBLE_CLICK_SECONDS = 0.35
"""Longest pause between the two clicks of a double click."""
BUTTONS = (glfw.MOUSE_BUTTON_LEFT, glfw.MOUSE_BUTTON_RIGHT)


@dataclass(slots=True)
class _Drag:
    button: int
    slots: list[int]
    """Slots visited, numbered like `Inventory.locate`."""

    @property
    def action(self) -> InventoryAction:
        if self.button == glfw.MOUSE_BUTTON_LEFT:
            return InventoryAction.SPREAD
        return InventoryAction.SPREAD_SINGLE


@dataclass(slots=True)
class InventoryMouse:
    """Turns mouse buttons on inventory slots into inventory actions.

    A stack on the cursor is put down when the button is let go, as the
    mouse may be dragged over more slots until then.
    """

    session: ClientSession
    clock: Callable[[], float] = time.monotonic
    _drag: _Drag | None = field(default=None, init=False)
    _last: tuple[int, float] | None = field(default=None, init=False)
    """Slot and time of the last left click."""

    def press(
        self, event: MouseButtonEvent, slot: int, inventory: Inventory
    ) -> None:
        """Handle a button pressed on a slot."""
        if event.button not in BUTTONS or self._drag is not None:
            return
        left = event.button == glfw.MOUSE_BUTTON_LEFT
        size = len(inventory)
        if event.mods & glfw.MOD_SHIFT and slot >= size:
            self._last = None
            self.session.inventory(InventoryAction.STOW_CRAFTING, slot - size)
            return
        if event.mods & glfw.MOD_SHIFT and left:
            self._last = None
            self.session.inventory(InventoryAction.QUICK_MOVE, slot)
            return
        now = self.clock()
        last, self._last = self._last, (slot, now) if left else None
        if (
            left
            and last is not None
            and last[0] == slot
            and now - last[1] <= DOUBLE_CLICK_SECONDS
        ):
            self._last = None
            self.session.inventory(InventoryAction.GATHER, slot)
            return
        cursor = inventory.cursor
        if cursor is not None and cursor.item.is_stackable:
            self._drag = _Drag(event.button, [slot])
        else:
            self._click(event.button, slot, size)

    def move(self, slot: int | None) -> None:
        """Note the slot under the mouse while dragging."""
        drag = self._drag
        if drag is not None and slot is not None and slot not in drag.slots:
            drag.slots.append(slot)
            self._last = None

    def release(self, button: int, inventory: Inventory) -> None:
        """Finish a drag: spread over its slots, or just click the one."""
        drag = self._drag
        if drag is None or drag.button != button:
            return
        self._drag = None
        if len(drag.slots) == 1:
            self._click(button, drag.slots[0], len(inventory))
        else:
            self.session.inventory(drag.action, slots=tuple(drag.slots))

    def cancel(self) -> None:
        """Forget any gesture, like when the inventory closes."""
        self._drag = self._last = None

    def preview(self, inventory: Inventory) -> Inventory:
        """Show what letting go of the button now would give.

        Returns:
            Inventory: The inventory itself unless dragging over several
            slots.

        """
        drag = self._drag
        if drag is None or len(drag.slots) == 1:
            return inventory
        shown = inventory.copy()
        single = drag.action is InventoryAction.SPREAD_SINGLE
        shown.spread(drag.slots, single=single)
        return shown

    def _click(self, button: int, slot: int, size: int) -> None:
        left = button == glfw.MOUSE_BUTTON_LEFT
        if slot < size:
            action = (
                InventoryAction.LEFT_CLICK
                if left
                else InventoryAction.RIGHT_CLICK
            )
            self.session.inventory(action, slot)
        else:
            action = (
                InventoryAction.CRAFTING_LEFT_CLICK
                if left
                else InventoryAction.CRAFTING_RIGHT_CLICK
            )
            self.session.inventory(action, slot - size)
