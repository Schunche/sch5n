# Copyright (c) 2026 Schunche
"""Rebindable controls: which inputs trigger which action.

Every program (the game, the map editor, the map viewer) has its own
`Context` with its own bindings. A binding is a key, a mouse button or a
mouse wheel direction, optionally with modifiers (`ctrl+key:S`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING

import glfw

from sch5n.client.window import KeyEvent, MouseButtonEvent, ScrollEvent
from sch5n.log.logger import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from sch5n.client.window import Event, Window

SLOTS = 2
"""Bindings per action: primary and secondary."""


class Context(StrEnum):
    """A program with its own set of controls."""

    GAME = "game"
    VIEWER = "viewer"
    """The map viewer, also when editing."""

    @property
    def label(self) -> str:
        """Name shown in the settings."""
        return {
            Context.GAME: "Game",
            Context.VIEWER: "Map Viewer",
        }[self]


class Action(StrEnum):
    """Things that can be bound. Which ones apply depends on the context."""

    # Game
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    JUMP = "jump"
    USE_ITEM = "use_item"
    PLACE_BLOCK = "place_block"
    INVENTORY = "inventory"
    DEBUG = "debug"
    HOTBAR_NEXT = "hotbar_next"
    HOTBAR_PREVIOUS = "hotbar_previous"
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
    # Map tools
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    RESET_CAMERA = "reset_camera"
    NEXT_TILE = "next_tile"
    PREVIOUS_TILE = "previous_tile"
    PLACE_TILE = "place_tile"
    ERASE_TILE = "erase_tile"
    SAVE = "save"
    SETTINGS = "settings"

    @property
    def label(self) -> str:
        """Name shown in the settings."""
        return self.value.replace("_", " ").capitalize()

    @property
    def hotbar_slot(self) -> int | None:
        """Hotbar index selected by this action, if any."""
        number = self.value.removeprefix("hotbar_")
        return int(number) - 1 if number.isdigit() else None


class Device(StrEnum):
    """Input device of a binding."""

    KEY = "key"
    MOUSE = "mouse"
    WHEEL = "wheel"


class Mod(IntFlag):
    """Modifier keys, same values as glfw's `MOD_*`."""

    NONE = 0
    SHIFT = glfw.MOD_SHIFT
    CTRL = glfw.MOD_CONTROL
    ALT = glfw.MOD_ALT
    SUPER = glfw.MOD_SUPER


MOD_MASK = Mod.SHIFT | Mod.CTRL | Mod.ALT | Mod.SUPER
MODIFIER_KEYS: dict[int, Mod] = {
    glfw.KEY_LEFT_SHIFT: Mod.SHIFT,
    glfw.KEY_RIGHT_SHIFT: Mod.SHIFT,
    glfw.KEY_LEFT_CONTROL: Mod.CTRL,
    glfw.KEY_RIGHT_CONTROL: Mod.CTRL,
    glfw.KEY_LEFT_ALT: Mod.ALT,
    glfw.KEY_RIGHT_ALT: Mod.ALT,
    glfw.KEY_LEFT_SUPER: Mod.SUPER,
    glfw.KEY_RIGHT_SUPER: Mod.SUPER,
}
_MOD_NAMES = {
    Mod.CTRL: "ctrl",
    Mod.SHIFT: "shift",
    Mod.ALT: "alt",
    Mod.SUPER: "super",
}
"""In display order."""

WHEEL_UP = 1
WHEEL_DOWN = -1


def _names(prefix: str, preferred: Iterable[str]) -> dict[int, str]:
    """Map glfw constant values to names, preferring readable aliases.

    Returns:
        dict[int, str]: Constant value to name without `prefix`.

    """
    names = {getattr(glfw, prefix + name): name for name in preferred}
    for attr in dir(glfw):
        name = attr.removeprefix(prefix)
        if attr.startswith(prefix) and name not in {"LAST", "UNKNOWN"}:
            names.setdefault(getattr(glfw, attr), name)
    return names


_NAMES: dict[Device, dict[int, str]] = {
    Device.KEY: _names("KEY_", ()),
    Device.MOUSE: _names("MOUSE_BUTTON_", ("LEFT", "RIGHT", "MIDDLE")),
    Device.WHEEL: {WHEEL_UP: "UP", WHEEL_DOWN: "DOWN"},
}
_CODES: dict[Device, dict[str, int]] = {
    device: {name: code for code, name in names.items()}
    for device, names in _NAMES.items()
}


def mods_of(window: Window) -> Mod:
    """Read the modifier keys currently held.

    Returns:
        Mod: The held modifiers.

    """
    return Mod(window.held_mods()) & MOD_MASK


@dataclass(frozen=True, slots=True)
class Binding:
    """A key, mouse button or wheel direction, with required modifiers."""

    device: Device
    code: int
    """glfw key or mouse button constant, or `WHEEL_UP` / `WHEEL_DOWN`."""
    mods: Mod = Mod.NONE

    @classmethod
    def key(cls, code: int, mods: Mod = Mod.NONE) -> Binding:
        """Binding of a keyboard key.

        Returns:
            Binding: The binding.

        """
        return cls(Device.KEY, code, mods)

    @classmethod
    def mouse(cls, code: int, mods: Mod = Mod.NONE) -> Binding:
        """Binding of a mouse button.

        Returns:
            Binding: The binding.

        """
        return cls(Device.MOUSE, code, mods)

    @classmethod
    def wheel(cls, direction: int, mods: Mod = Mod.NONE) -> Binding:
        """Binding of a mouse wheel direction.

        Returns:
            Binding: The binding.

        """
        return cls(Device.WHEEL, direction, mods)

    @classmethod
    def parse(cls, text: str) -> Binding:
        """Parse the settings file format, e.g. `ctrl+key:S`, `wheel:UP`.

        Returns:
            Binding: The binding.

        Raises:
            ValueError: Unknown modifier, device or name.

        """
        *mod_names, target = text.lower().split("+")
        mods = Mod.NONE
        by_name = {name: mod for mod, name in _MOD_NAMES.items()}
        for name in mod_names:
            if name not in by_name:
                msg = f"Unknown modifier in binding: {text!r}"
                raise ValueError(msg)
            mods |= by_name[name]
        device_name, _, name = target.partition(":")
        try:
            device = Device(device_name)
            code = _CODES[device][name.upper()]
        except ValueError, KeyError:
            msg = f"Unknown binding: {text!r}"
            raise ValueError(msg) from None
        return cls(device, code, mods)

    @classmethod
    def from_event(cls, event: Event) -> Binding | None:
        """Binding pressed by an event.

        Pressing a modifier key binds the key itself, without modifiers.

        Returns:
            Binding | None: `None` unless a key, button or wheel was used.

        """
        match event:
            case KeyEvent() if event.pressed:
                if event.key in MODIFIER_KEYS:
                    return cls.key(event.key)
                return cls.key(event.key, Mod(event.mods) & MOD_MASK)
            case MouseButtonEvent() if event.pressed:
                return cls.mouse(event.button, Mod(event.mods) & MOD_MASK)
            case ScrollEvent(dy=dy) if dy:
                direction = WHEEL_UP if dy > 0 else WHEEL_DOWN
                return cls.wheel(direction, Mod(event.mods) & MOD_MASK)
            case _:
                return None

    @property
    def name(self) -> str:
        """Name as in glfw constants, e.g. `SPACE`."""
        return _NAMES[self.device].get(self.code, str(self.code))

    @property
    def label(self) -> str:
        """Readable name, e.g. `Ctrl+S` or `Mouse Left`."""
        text = self.name.replace("_", " ").title()
        if self.device is not Device.KEY:
            text = f"{self.device.title()} {text}"
        mods = [
            name.title()
            for mod, name in _MOD_NAMES.items()
            if mod in self.mods
        ]
        return "+".join([*mods, text])

    def __str__(self) -> str:
        """Format for the settings file.

        Returns:
            str: E.g. `ctrl+key:S`.

        """
        mods = [name for mod, name in _MOD_NAMES.items() if mod in self.mods]
        return "+".join([*mods, f"{self.device}:{self.name}"])

    @property
    def input(self) -> tuple[Device, int]:
        """The physical input, ignoring modifiers."""
        return (self.device, self.code)

    def is_down(self, window: Window, held: Mod) -> bool:
        """Whether it is held. Wheel bindings are never held.

        Returns:
            bool: True while the input and its modifiers are held.

        """
        if self.mods & ~held:
            return False
        match self.device:
            case Device.KEY:
                return window.is_key_down(self.code)
            case Device.MOUSE:
                return window.is_mouse_down(self.code)
            case Device.WHEEL:
                return False


type Slots = tuple[Binding | None, ...]

_DIGITS = "1234567890"
_PAN = {
    Action.PAN_UP: ("key:W", "key:UP"),
    Action.PAN_DOWN: ("key:S", "key:DOWN"),
    Action.PAN_LEFT: ("key:A", "key:LEFT"),
    Action.PAN_RIGHT: ("key:D", "key:RIGHT"),
}
DEFAULTS: dict[Context, dict[Action, tuple[str, ...]]] = {
    Context.GAME: {
        Action.MOVE_LEFT: ("key:A", "key:LEFT"),
        Action.MOVE_RIGHT: ("key:D", "key:RIGHT"),
        Action.JUMP: ("key:SPACE",),
        Action.USE_ITEM: ("mouse:LEFT",),
        Action.PLACE_BLOCK: ("mouse:RIGHT",),
        Action.INVENTORY: ("key:TAB",),
        Action.DEBUG: ("key:F3",),
        Action.HOTBAR_NEXT: ("wheel:DOWN",),
        Action.HOTBAR_PREVIOUS: ("wheel:UP",),
    }
    | {
        Action(f"hotbar_{i + 1}"): (f"key:{d}",) for i, d in enumerate(_DIGITS)
    },
    Context.VIEWER: {
        **_PAN,
        Action.ZOOM_IN: ("wheel:UP",),
        Action.ZOOM_OUT: ("wheel:DOWN",),
        Action.RESET_CAMERA: ("key:R",),
        Action.SETTINGS: ("key:F1",),
        # Only while editing.
        Action.PLACE_TILE: ("mouse:LEFT",),
        Action.ERASE_TILE: ("mouse:RIGHT",),
        Action.NEXT_TILE: ("shift+wheel:DOWN", "key:E"),
        Action.PREVIOUS_TILE: ("shift+wheel:UP", "key:Q"),
        Action.SAVE: ("ctrl+key:S",),
    },
}

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
        if binding.input != Binding.key(glfw.KEY_ESCAPE).input:
            bindings.append(binding)
    bindings = bindings[:SLOTS]
    return tuple(bindings + [None] * (SLOTS - len(bindings)))


def _context_slots(
    context: Context, config: Mapping[str, Iterable[str]]
) -> dict[Action, Slots]:
    """Parse the bindings of a context, using defaults for missing actions.

    Returns:
        dict[Action, Slots]: Slots of every action of the context.

    """
    return {
        action: _slots(config.get(action.value, texts))
        for action, texts in DEFAULTS[context].items()
    }


class ContextBinds:
    """Bindings of one context. Each action has `SLOTS` slots.

    When bindings share an input, the one with the most matching modifiers
    wins: with Ctrl held, `ctrl+key:S` fires and `key:S` counts as not held.
    """

    def __init__(
        self,
        context: Context,
        config: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        """Build from settings data. Missing actions get their defaults."""
        self.context = context
        config = config or {}
        self._slots = _context_slots(context, config)
        for name in config:
            if name not in {action.value for action in DEFAULTS[context]}:
                LOGGER.warning("Ignoring unknown %s action %r", context, name)
        self._by_input: dict[
            tuple[Device, int], list[tuple[Binding, Action]]
        ] = {}
        self._reindex()

    def _reindex(self) -> None:
        self._by_input = {}
        for action, slots in self._slots.items():
            for binding in slots:
                if binding is not None:
                    self._by_input.setdefault(binding.input, []).append((
                        binding,
                        action,
                    ))

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

    def _best(
        self, device: Device, code: int, held: Mod
    ) -> tuple[Binding, Action] | None:
        candidates = [
            (binding, action)
            for binding, action in self._by_input.get((device, code), ())
            if not binding.mods & ~held
        ]
        return max(
            candidates, key=lambda c: c[0].mods.bit_count(), default=None
        )

    def action_for(self, binding: Binding | None) -> Action | None:
        """Find the action triggered when `binding` is pressed exactly.

        Returns:
            Action | None: The action, if any binding matches.

        """
        if binding is None:
            return None
        best = self._best(binding.device, binding.code, binding.mods)
        return None if best is None else best[1]

    def pressed(self, event: Event) -> Action | None:
        """Find the action started by an input event.

        Returns:
            Action | None: The action, if the event pressed a bound input.

        """
        return self.action_for(Binding.from_event(event))

    def is_held(self, action: Action, window: Window) -> bool:
        """Whether any binding of `action` is held and not overridden.

        Returns:
            bool: True while held.

        """
        held = mods_of(window)
        for binding in self._slots[action]:
            if binding is None or not binding.is_down(window, held):
                continue
            best = self._best(binding.device, binding.code, held)
            if best is not None and best[1] is action:
                return True
        return False

    def bind(
        self, action: Action, slot: int, binding: Binding | None
    ) -> Action | None:
        """Put `binding` in a slot (or clear it with `None`).

        A binding can only trigger one action in a context: it is removed
        from any other slot first.

        Returns:
            Action | None: The action that lost the binding, if any.

        Raises:
            ValueError: The binding is reserved.

        """
        if binding is not None and binding.input in {
            b.input for b in RESERVED
        }:
            msg = f"{binding.label} cannot be rebound"
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
        """Restore the defaults of this context."""
        self._slots = _context_slots(self.context, {})
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


class Keybinds:
    """Bindings of every context."""

    def __init__(
        self, config: Mapping[str, Mapping[str, Iterable[str]]] | None = None
    ) -> None:
        """Build from settings data, `{context: {action: [binding]}}`."""
        config = config or {}
        for name in config:
            if name not in {context.value for context in Context}:
                LOGGER.warning("Ignoring keybinds of unknown context %r", name)
        self._contexts = {
            context: ContextBinds(context, config.get(context.value))
            for context in Context
        }

    def __getitem__(self, context: Context) -> ContextBinds:
        """Get the bindings of one context.

        Returns:
            ContextBinds: The context's bindings.

        """
        return self._contexts[context]

    def __iter__(self) -> Iterator[ContextBinds]:
        """Iterate over contexts in display order.

        Returns:
            Iterator: Context bindings.

        """
        return iter(self._contexts.values())

    def reset(self) -> None:
        """Restore every default, in place."""
        for binds in self._contexts.values():
            binds.reset()

    def to_config(self) -> dict[str, dict[str, list[str]]]:
        """Encode for the settings file.

        Returns:
            dict[str, dict[str, list[str]]]: Context to action to bindings.

        """
        return {
            binds.context.value: binds.to_config()
            for binds in self._contexts.values()
        }
