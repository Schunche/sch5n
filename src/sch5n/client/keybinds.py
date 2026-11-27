# Copyright (c) 2026 Schunche
"""Rebindable controls: which keys and mouse buttons trigger which action."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import glfw

from sch5n.client.window import KeyEvent, MouseButtonEvent
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from sch5n.client.window import Event, Window

SLOTS = 2
"""Bindings per action: primary and secondary."""


class Action(StrEnum):
    """Things the player can do with a key or mouse button."""

    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    JUMP = "jump"
    USE_ITEM = "use_item"
    PLACE_BLOCK = "place_block"
    INVENTORY = "inventory"
    DEBUG = "debug"
    HOTBAR_1 = "hotbar_1"
    HOTBAR_2 = "hotbar_2"
    HOTBAR_3 = "hotbar_3"
    HOTBAR_4 = "hotbar_4"
    HOTBAR_5 = "hotbar_5"
    HOTBAR_6 = "hotbar_6"
    HOTBAR_7 = "hotbar_7"
    HOTBAR_8 = "hotbar_8"
    HOTBAR_9 = "hotbar_9"
    HOTBAR_10 = "hotbar_10"

    @property
    def label(self) -> str:
        """Name shown in the settings."""
        return self.value.replace("_", " ").capitalize()

    @property
    def hotbar_slot(self) -> int | None:
        """Hotbar index selected by this action, if any."""
        prefix = "hotbar_"
        if self.value.startswith(prefix):
            return int(self.value.removeprefix(prefix)) - 1
        return None


class Device(StrEnum):
    """Input device of a binding."""

    KEY = "key"
    MOUSE = "mouse"


def _names(prefix: str, preferred: Iterable[str]) -> dict[int, str]:
    """Map glfw constant values to names, preferring readable aliases."""  # ruff: ignore[docstring-missing-returns]
    names: dict[int, str] = {}
    for preferred_name in preferred:
        names[getattr(glfw, prefix + preferred_name)] = preferred_name
    for attr in dir(glfw):
        if not attr.startswith(prefix):
            continue
        name = attr.removeprefix(prefix)
        if name in {"LAST", "UNKNOWN"}:
            continue
        names.setdefault(getattr(glfw, attr), name)
    return names


_KEY_NAMES = _names("KEY_", ())
_MOUSE_NAMES = _names("MOUSE_BUTTON_", ("LEFT", "RIGHT", "MIDDLE"))
_KEY_CODES = {name: code for code, name in _KEY_NAMES.items()}
_MOUSE_CODES = {name: code for code, name in _MOUSE_NAMES.items()} | {
    f"BUTTON_{i}": getattr(glfw, f"MOUSE_BUTTON_{i}") for i in range(1, 9)
}


@dataclass(frozen=True, slots=True)
class Binding:
    """One key or mouse button."""

    device: Device
    code: int
    """glfw key or mouse button constant."""

    @classmethod
    def key(cls, code: int) -> Binding:
        """Binding of a keyboard key.

        Returns:
            Binding: The binding.

        """
        return cls(Device.KEY, code)

    @classmethod
    def mouse(cls, code: int) -> Binding:
        """Binding of a mouse button.

        Returns:
            Binding: The binding.

        """
        return cls(Device.MOUSE, code)

    @classmethod
    def parse(cls, text: str) -> Binding:
        """Parse the settings file format, e.g. `key:SPACE`, `mouse:LEFT`.

        Returns:
            Binding: The binding.

        Raises:
            ValueError: Unknown device or name.

        """
        device, _, name = text.partition(":")
        name = name.upper()
        match device.lower():
            case Device.KEY if name in _KEY_CODES:
                return cls.key(_KEY_CODES[name])
            case Device.MOUSE if name in _MOUSE_CODES:
                return cls.mouse(_MOUSE_CODES[name])
            case _:
                msg = f"Unknown binding: {text!r}"
                raise ValueError(msg)

    @classmethod
    def from_event(cls, event: Event) -> Binding | None:
        """Binding pressed by an event.

        Returns:
            Binding | None: `None` unless a key or button went down.

        """
        match event:
            case KeyEvent() if event.pressed:
                return cls.key(event.key)
            case MouseButtonEvent() if event.pressed:
                return cls.mouse(event.button)
            case _:
                return None

    @property
    def name(self) -> str:
        """Glfw style name, e.g. `SPACE`."""
        names = _KEY_NAMES if self.device is Device.KEY else _MOUSE_NAMES
        return names.get(self.code, str(self.code))

    @property
    def label(self) -> str:
        """Readable name, e.g. `Space` or `Mouse Left`."""
        text = self.name.replace("_", " ").title()
        return f"Mouse {text}" if self.device is Device.MOUSE else text

    def __str__(self) -> str:
        """Format for the settings file."""  # ruff: ignore[docstring-missing-returns]
        return f"{self.device}:{self.name}"

    def is_down(self, window: Window) -> bool:
        """Whether it is currently held.

        Returns:
            bool: True while held.

        """
        if self.device is Device.KEY:
            return window.is_key_down(self.code)
        return window.is_mouse_down(self.code)


type Slots = tuple[Binding | None, ...]

_DIGITS = "1234567890"
DEFAULTS: dict[Action, tuple[str, ...]] = {
    Action.MOVE_LEFT: ("key:A", "key:LEFT"),
    Action.MOVE_RIGHT: ("key:D", "key:RIGHT"),
    Action.JUMP: ("key:SPACE",),
    Action.USE_ITEM: ("mouse:LEFT",),
    Action.PLACE_BLOCK: ("mouse:RIGHT",),
    Action.INVENTORY: ("key:TAB",),
    Action.DEBUG: ("key:F3",),
} | {Action(f"hotbar_{i + 1}"): (f"key:{d}",) for i, d in enumerate(_DIGITS)}

RESERVED = frozenset({Binding.key(glfw.KEY_ESCAPE)})
"""Bindings that always mean "back" and cannot be assigned."""


def _slots(texts: Iterable[str]) -> Slots:
    bindings: list[Binding | None] = []
    for text in texts:
        try:
            binding = Binding.parse(text)
        except ValueError:
            LOGGER.warning("Ignoring invalid key binding %r", text)
            continue
        bindings.append(None if binding in RESERVED else binding)
    bindings = bindings[:SLOTS]
    return tuple(bindings + [None] * (SLOTS - len(bindings)))


class Keybinds:
    """The bindings of every action. Each action has `SLOTS` slots."""

    def __init__(
        self, config: Mapping[str, Iterable[str]] | None = None
    ) -> None:
        """Build from settings data. Missing actions get their defaults."""
        self._slots: dict[Action, Slots] = {}
        config = config or {}
        for action in Action:
            texts = config.get(action.value)
            self._slots[action] = _slots(
                DEFAULTS[action] if texts is None else texts
            )
        for name in config:
            if name not in {action.value for action in Action}:
                LOGGER.warning("Ignoring unknown action %r", name)
        self._index: dict[Binding, Action] = {}
        self._reindex()

    def _reindex(self) -> None:
        self._index = {
            binding: action
            for action, slots in self._slots.items()
            for binding in slots
            if binding is not None
        }

    def __iter__(self) -> Iterator[tuple[Action, Slots]]:
        """Iterate over actions and their slots in display order.

        Returns:
            Iterator: `(action, slots)` pairs.

        """
        return iter(self._slots.items())

    def slots(self, action: Action) -> Slots:
        """Bindings of an action, `None` for empty slots.

        Returns:
            Slots: One entry per slot.

        """
        return self._slots[action]

    def action_for(self, binding: Binding | None) -> Action | None:
        """Find the action triggered by a binding.

        Returns:
            Action | None: The action, if bound.

        """
        return None if binding is None else self._index.get(binding)

    def pressed(self, event: Event) -> Action | None:
        """Find the action started by an input event.

        Returns:
            Action | None: The action, if the event pressed a bound input.

        """
        return self.action_for(Binding.from_event(event))

    def is_held(self, action: Action, window: Window) -> bool:
        """Whether any binding of `action` is held.

        Returns:
            bool: True while held.

        """
        return any(
            b is not None and b.is_down(window) for b in self._slots[action]
        )

    def bind(
        self, action: Action, slot: int, binding: Binding | None
    ) -> Action | None:
        """Put `binding` in a slot (or clear it with `None`).

        A binding can only trigger one action: it is removed from any other
        slot first.

        Returns:
            Action | None: The action that lost the binding, if any.

        Raises:
            ValueError: The binding is reserved.

        """
        if binding in RESERVED:
            msg = f"{binding.label} cannot be rebound"  # type: ignore[union-attr]
            raise ValueError(msg)
        stolen_from: Action | None = None
        if binding is not None:
            for other, slots in self._slots.items():
                if binding in slots:
                    self._slots[other] = tuple(
                        None if b == binding else b for b in slots
                    )
                    if other is not action:
                        stolen_from = other
        slots = list(self._slots[action])
        slots[slot] = binding
        self._slots[action] = tuple(slots)
        self._reindex()
        return stolen_from

    def reset(self) -> None:
        """Restore every default."""
        self._slots = Keybinds()._slots  # ruff: ignore[private-member-access]
        self._reindex()

    def to_config(self) -> dict[str, list[str]]:
        """Encode for the settings file.

        Returns:
            dict[str, list[str]]: Action name to bindings.

        """
        return {
            action.value: [str(b) for b in slots if b is not None]
            for action, slots in self._slots.items()
        }
