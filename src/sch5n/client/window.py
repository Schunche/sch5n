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
    mods: int = 0
    """glfw `MOD_*` flags held while scrolling."""


@dataclass(frozen=True, slots=True)
class ResizeEvent:
    """The window changed size (window coordinates)."""

    width: int
    height: int


@dataclass(frozen=True, slots=True)
class CharEvent:
    """A character was typed, for text fields."""

    char: str


_MODIFIERS = (
    (glfw.KEY_LEFT_SHIFT, glfw.KEY_RIGHT_SHIFT, glfw.MOD_SHIFT),
    (glfw.KEY_LEFT_CONTROL, glfw.KEY_RIGHT_CONTROL, glfw.MOD_CONTROL),
    (glfw.KEY_LEFT_ALT, glfw.KEY_RIGHT_ALT, glfw.MOD_ALT),
    (glfw.KEY_LEFT_SUPER, glfw.KEY_RIGHT_SUPER, glfw.MOD_SUPER),
)

type Event = (
    KeyEvent | MouseButtonEvent | ScrollEvent | ResizeEvent | CharEvent
)


class Cursor:
    """The OS mouse cursor over a window."""

    def __init__(self, window: object) -> None:
        """Control the cursor of a glfw window handle."""
        self._window = window
        self._image: object | None = None
        """glfw cursor handle made by `set_image`."""

    def hide(self) -> None:
        """Hide the OS cursor while it is over the window."""
        glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_HIDDEN)

    def set_image(
        self, pixels: np.ndarray, hotspot: tuple[int, int] = (0, 0)
    ) -> None:
        """Show the OS cursor, looking like an RGBA image.

        The operating system draws it, so it never lags behind the mouse.
        """
        height, width = pixels.shape[:2]
        image = glfw.create_cursor((width, height, pixels), *hotspot)
        glfw.set_cursor(self._window, image)
        self.release()
        self._image = image
        glfw.set_input_mode(self._window, glfw.CURSOR, glfw.CURSOR_NORMAL)

    @property
    def visible(self) -> bool:
        """Whether the OS cursor is shown over the window."""
        mode = glfw.get_input_mode(self._window, glfw.CURSOR)
        return mode == glfw.CURSOR_NORMAL

    def release(self) -> None:
        """Free the cursor image."""
        if self._image is not None:
            glfw.destroy_cursor(self._image)
            self._image = None


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
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE if visible else glfw.FALSE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)

        self.handle = glfw.create_window(size[0], size[1], title, None, None)
        if not self.handle:
            glfw.terminate()
            msg = "Could not create a window with OpenGL 3.3"
            raise WindowError(msg)

        glfw.make_context_current(self.handle)
        glfw.swap_interval(1 if vsync else 0)

        self._events: list[Event] = []
        self.cursor = Cursor(self.handle)
        glfw.set_key_callback(self.handle, self._on_key)
        glfw.set_mouse_button_callback(self.handle, self._on_mouse_button)
        glfw.set_scroll_callback(self.handle, self._on_scroll)
        glfw.set_window_size_callback(self.handle, self._on_resize)
        glfw.set_char_callback(self.handle, self._on_char)

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
        self._events.append(ScrollEvent(dx, dy, self.held_mods()))

    def _on_resize(self, _w: object, width: int, height: int) -> None:
        self._events.append(ResizeEvent(width, height))

    def _on_char(self, _w: object, codepoint: int) -> None:
        self._events.append(CharEvent(chr(codepoint)))

    @property
    def clipboard(self) -> str:
        """Text on the clipboard, empty if there is none."""
        data = glfw.get_clipboard_string(self.handle)
        if isinstance(data, bytes):
            return data.decode("utf-8", "replace")
        return data or ""

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

    def held_mods(self) -> int:
        """Read the modifier keys currently held.

        Returns:
            int: glfw `MOD_*` flags.

        """
        mods = 0
        for left, right, flag in _MODIFIERS:
            if self.is_key_down(left) or self.is_key_down(right):
                mods |= flag
        return mods

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

    @property
    def is_fullscreen(self) -> bool:
        """Whether the window covers a monitor."""
        return bool(glfw.get_window_monitor(self.handle))

    def set_size(self, size: tuple[int, int]) -> None:
        """Resize a windowed window."""
        if not self.is_fullscreen:
            glfw.set_window_size(self.handle, *size)

    def set_fullscreen(
        self, *, fullscreen: bool, size: tuple[int, int]
    ) -> None:
        """Switch to fullscreen on the primary monitor, or back to `size`."""
        if fullscreen == self.is_fullscreen:
            return
        if fullscreen:
            monitor = glfw.get_primary_monitor()
            if not monitor:
                return
            mode = glfw.get_video_mode(monitor)
            glfw.set_window_monitor(
                self.handle,
                monitor,
                0,
                0,
                mode.size.width,
                mode.size.height,
                mode.refresh_rate,
            )
        else:
            glfw.set_window_monitor(
                self.handle, None, 100, 100, size[0], size[1], 0
            )

    @staticmethod
    def set_vsync(*, vsync: bool) -> None:
        """Wait for the display refresh when presenting frames."""
        glfw.swap_interval(1 if vsync else 0)

    def close(self) -> None:
        """Request the window to close."""
        glfw.set_window_should_close(self.handle, glfw.TRUE)

    def swap(self) -> None:
        """Present the frame."""
        glfw.swap_buffers(self.handle)

    def destroy(self) -> None:
        """Destroy the window and shut glfw down."""
        self.cursor.release()
        glfw.destroy_window(self.handle)
        glfw.terminate()

    @staticmethod
    def time() -> float:
        """Seconds since glfw initialized.

        Returns:
            float: Time in seconds.

        """
        return glfw.get_time()
