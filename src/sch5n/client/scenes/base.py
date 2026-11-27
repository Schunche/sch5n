# Copyright (c) 2026 Schunche
"""Base class of every screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from sch5n.client.keybinds import Context

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event


class Scene:
    """A screen. The app forwards input to it, ticks it and draws it.

    `tick` runs at the fixed game tick rate, `render` once per frame.
    """

    controls: ClassVar[Context] = Context.GAME
    """Program whose key bindings the settings opened here may change."""
    has_backdrop: ClassVar[bool] = False
    """Whether `draw_backdrop` draws something."""

    def __init__(self, app: App) -> None:
        """Create the scene."""
        self.app = app
        self._layout_size: tuple[int, int] | None = None
        """Window size `layout` last ran for."""

    def layout(self) -> None:
        """Place everything that depends on the window size."""

    def update_layout(self) -> None:
        """Run `layout` if the window size changed since it last ran.

        The app calls this before the scene handles input or draws, so a
        scene that was hidden behind another while the window changed
        size is laid out again when it comes back.
        """
        if self._layout_size != self.app.screen:
            self._layout_size = self.app.screen
            self.layout()

    def on_enter(self) -> None:
        """Prepare for becoming the active scene."""

    def on_exit(self) -> None:
        """Clean up when no longer the active scene."""

    def on_event(self, event: Event) -> None:
        """Handle an input event."""

    def tick(self) -> None:
        """Advance one fixed tick."""

    def render(self) -> None:
        """Draw a frame."""

    def leave(self) -> None:
        """End what the scene runs, like a game, before the main menu."""

    def tick_backdrop(self) -> None:
        """Advance while a menu opened from this scene is shown."""

    def draw_backdrop(self) -> None:
        """Draw what this scene shows behind menus opened from it.

        Only called when `has_backdrop` is set.
        """
