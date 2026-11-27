# Copyright (c) 2026 Schunche
"""Base class of every screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event


class Scene:
    """A screen. The app forwards input to it, ticks it and draws it.

    `tick` runs at the fixed game tick rate, `render` once per frame.
    """

    def __init__(self, app: App) -> None:
        """Create the scene."""
        self.app = app

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
