# Copyright (c) 2026 Schunche
"""A glfw window with an OpenGL 3.3 core context and an event queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import glfw

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A keyboard key changed state. Values are glfw constants."""

    key: int
    action: int
    mods: int

    @property
    def pressed(self) -> bool:
        """Key went down (repeats excluded)."""
        return self.action == glfw.PRESS


@dataclass(frozen=True, slots=True)
class MouseButtonEvent:
    """A mouse button changed state at `pos` (window coordinates)."""

    button: int
    action: int
    mods: int
    pos: tuple[float, float]

    @property
    def pressed(self) -> bool:
        """Button went down."""
        return self.action == glfw.PRESS


@dataclass(frozen=True, slots=True)
class ScrollEvent:
    """Mouse wheel moved. Positive `dy` is away from the user."""

    dx: float
    dy: float


@dataclass(frozen=True, slots=True)
class ResizeEvent:
    """The window changed size (window coordinates)."""

    width: int
    height: int


type Event = KeyEvent | MouseButtonEvent | ScrollEvent | ResizeEvent


class WindowError(RuntimeError):
    """The window or its OpenGL context could not be created."""


class Window:
    """Owns the glfw window. Input arrives as `Event`s via `poll`."""

    def __init__(
        self,
        title: str,
        size: tuple[int, int],
        *,
        vsync: bool = True,
        visible: bool = True,
    ) -> None:
        """Open a window and make its context current.

        Raises:
            WindowError: glfw failed.

        """
        if not glfw.init():
            msg = "Could not initialize glfw"
            raise WindowError(msg)

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)  # ruff: ignore[boolean-positional-value-in-call]
        glfw.window_hint(glfw.VISIBLE, visible)
        glfw.window_hint(glfw.RESIZABLE, True)  # ruff: ignore[boolean-positional-value-in-call]

        self.handle = glfw.create_window(size[0], size[1], title, None, None)
        if not self.handle:
            glfw.terminate()
            msg = "Could not create a window with OpenGL 3.3"
            raise WindowError(msg)

        glfw.make_context_current(self.handle)
        glfw.swap_interval(1 if vsync else 0)

        self._events: list[Event] = []
        glfw.set_key_callback(self.handle, self._on_key)
        glfw.set_mouse_button_callback(self.handle, self._on_mouse_button)
        glfw.set_scroll_callback(self.handle, self._on_scroll)
        glfw.set_window_size_callback(self.handle, self._on_resize)

    def _on_key(
        self, _w: object, key: int, _sc: int, action: int, mods: int
    ) -> None:
        self._events.append(KeyEvent(key, action, mods))

    def _on_mouse_button(
        self, _w: object, button: int, action: int, mods: int
    ) -> None:
        self._events.append(
            MouseButtonEvent(button, action, mods, self.mouse_pos)
        )

    def _on_scroll(self, _w: object, dx: float, dy: float) -> None:
        self._events.append(ScrollEvent(dx, dy))

    def _on_resize(self, _w: object, width: int, height: int) -> None:
        self._events.append(ResizeEvent(width, height))

    def poll(self) -> list[Event]:
        """Process OS events.

        Returns:
            list[Event]: Events since the last call.

        """
        glfw.poll_events()
        events, self._events = self._events, []
        return events

    @property
    def size(self) -> tuple[int, int]:
        """Window size in screen coordinates."""
        return glfw.get_window_size(self.handle)

    @property
    def framebuffer_size(self) -> tuple[int, int]:
        """Size in pixels (differs from `size` on high DPI screens)."""
        return glfw.get_framebuffer_size(self.handle)

    @property
    def mouse_pos(self) -> tuple[float, float]:
        """Cursor position in window coordinates."""
        return glfw.get_cursor_pos(self.handle)

    @property
    def should_close(self) -> bool:
        """The user asked to close the window."""
        return bool(glfw.window_should_close(self.handle))

    def is_key_down(self, key: int) -> bool:
        """Whether a key is held.

        Returns:
            bool: True while held.

        """
        return glfw.get_key(self.handle, key) == glfw.PRESS

    def is_mouse_down(self, button: int) -> bool:
        """Whether a mouse button is held.

        Returns:
            bool: True while held.

        """
        return glfw.get_mouse_button(self.handle, button) == glfw.PRESS

    def set_title(self, title: str) -> None:
        """Change the title bar text."""
        glfw.set_window_title(self.handle, title)

    def set_icon(self, pixels: np.ndarray) -> None:
        """Set the window icon from an RGBA array `(height, width, 4)`."""
        height, width = pixels.shape[:2]
        glfw.set_window_icon(self.handle, 1, [(width, height, pixels)])

    def hide_cursor(self) -> None:
        """Hide the OS cursor while it is over the window."""
        glfw.set_input_mode(self.handle, glfw.CURSOR, glfw.CURSOR_HIDDEN)

    def close(self) -> None:
        """Request the window to close."""
        glfw.set_window_should_close(self.handle, True)  # ruff: ignore[boolean-positional-value-in-call]

    def swap(self) -> None:
        """Present the frame."""
        glfw.swap_buffers(self.handle)

    def destroy(self) -> None:
        """Destroy the window and shut glfw down."""
        glfw.destroy_window(self.handle)
        glfw.terminate()

    @staticmethod
    def time() -> float:
        """Seconds since glfw initialized.

        Returns:
            float: Time in seconds.

        """
        return glfw.get_time()
