# Copyright (c) 2026 Schunche
"""Main menu and settings screens."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import glfw

from sch5n.client.keybinds import SLOTS, Action, Binding
from sch5n.client.render.batch import WHITE, rgba
from sch5n.client.render.text import Anchor
from sch5n.client.scenes.base import Scene
from sch5n.client.ui import (
    Align,
    Button,
    TableLayout,
    aligned_rect,
    button_column,
    hit_button,
)
from sch5n.client.window import (
    KeyEvent,
    MouseButtonEvent,
    ResizeEvent,
    ScrollEvent,
)
lazy from sch5n.client.scenes.play import PlayScene

if TYPE_CHECKING:
    from sch5n.client.app import App
    from sch5n.client.window import Event


class MenuScene(Scene):
    """Shared behaviour of simple button screens."""

    entries: ClassVar[tuple[tuple[str, str], ...]] = ()

    def __init__(self, app: App) -> None:
        """Create the screen."""
        super().__init__(app)
        self.buttons: list[Button] = []
        self.layout()

    def layout(self) -> None:
        """Place the buttons for the current window size."""
        w, h = self.app.screen
        self.buttons = button_column(
            self.entries,
            (w / 2, h / 2),
            self.app.ui.main_menu.button_spacing,
            self.app.ui,
        )

    def on_button(self, button_id: str) -> None:
        """React to a click on a button."""

    def on_escape(self) -> None:
        """React to the escape key."""

    def on_event(self, event: Event) -> None:
        """Handle clicks, escape and resizing."""
        match event:
            case ResizeEvent():
                self.layout()
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self.on_escape()
            case MouseButtonEvent(button=glfw.MOUSE_BUTTON_LEFT) if (
                event.pressed
            ):
                button_id = hit_button(self.buttons, event.pos)
                if button_id is not None:
                    self.on_button(button_id)
            case _:
                pass

    def draw_background(self) -> None:
        """Draw what is behind the buttons."""
        self.app.clear(self.app.ui.color("main_theme"))

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        self.draw_background()
        app.batch.begin(app.screen)
        self.draw_foreground()
        mouse = app.window.mouse_pos
        for button in self.buttons:
            button.draw(app.batch, app.text, app.ui, mouse)
        app.draw_cursor()

    def draw_foreground(self) -> None:
        """Draw extra content above the background."""


class MainMenu(MenuScene):
    """The title screen."""

    entries = (("play", "Play"), ("settings", "Settings"), ("exit", "Exit"))

    def on_button(self, button_id: str) -> None:
        """Start the game, open settings or quit."""
        match button_id:
            case "play":
                self.app.switch(PlayScene(self.app))
            case "settings":
                self.app.switch(SettingsScene(self.app, back=self))
            case "exit":
                self.app.quit()
            case _:
                pass

    def on_escape(self) -> None:
        """Quit."""
        self.app.quit()

    def draw_foreground(self) -> None:
        """Draw the background image stretched over the window."""
        app = self.app
        texture = app.texture(app.ui.main_menu.background)
        app.batch.sprite(texture, (0, 0, *app.screen))


class SettingsScene(Scene):
    """Shows settings and lets the player rebind controls.

    Click a binding, then press a key or mouse button. Escape cancels,
    Backspace or Delete clears the slot. Changes are saved immediately.
    """

    ROW_HEIGHT = 32
    TABLE_TOP = 120
    TABLE_BOTTOM_MARGIN = 130
    FOOTER_BUTTON_WIDTH = 160
    CLEAR_KEYS = frozenset({glfw.KEY_BACKSPACE, glfw.KEY_DELETE})

    def __init__(
        self, app: App, back: Scene, *, in_game: bool = False
    ) -> None:
        """Create the screen. `back` is shown again when leaving."""
        super().__init__(app)
        self.back = back
        self.in_game = in_game
        self.actions = [action for action, _ in app.keybinds]
        self.scroll = 0.0
        self.capturing: tuple[Action, int] | None = None
        """Slot waiting for a key press."""
        self.message = ""
        self.table = TableLayout.centered(0, app.screen, 0, 0)
        self.buttons: list[Button] = []
        self.layout()

    def layout(self) -> None:
        """Place the table and footer buttons for the window size."""
        w, h = self.app.screen
        self.table = TableLayout.centered(
            len(self.actions),
            (w, h),
            self.TABLE_TOP,
            h - self.TABLE_BOTTOM_MARGIN,
            row_height=self.ROW_HEIGHT,
        )
        self.scroll = self.table.clamp_scroll(self.scroll)

        entries = [("reset", "Reset Defaults"), ("back", "Back")]
        if self.in_game:
            entries.append(("menu", "Main Menu"))
        size = (self.FOOTER_BUTTON_WIDTH, self.app.ui.button.height)
        gap = 16
        total = len(entries) * size[0] + (len(entries) - 1) * gap
        x = (w - total) / 2
        self.buttons = [
            Button(
                button_id,
                label,
                aligned_rect(
                    (x + i * (size[0] + gap), h - 60), size, Align.TOP_LEFT
                ),
            )
            for i, (button_id, label) in enumerate(entries)
        ]

    # Input

    def _leave(self) -> None:
        self.app.switch(self.back)

    def _assign(self, binding: Binding | None) -> None:
        if self.capturing is None:
            return
        action, slot = self.capturing
        self.capturing = None
        try:
            lost = self.app.keybinds.bind(action, slot, binding)
        except ValueError as e:
            self.message = str(e)
            return
        if binding is None:
            self.message = f"Cleared {action.label}"
        elif lost is not None:
            self.message = (
                f"{binding.label} was moved from {lost.label} "
                f"to {action.label}"
            )
        else:
            self.message = f"{action.label}: {binding.label}"
        self.app.save_settings()

    def _on_capture(self, event: Event) -> None:
        match event:
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self.capturing = None
                self.message = "Cancelled"
            case KeyEvent(key=key) if event.pressed and key in self.CLEAR_KEYS:
                self._assign(None)
            case _:
                binding = Binding.from_event(event)
                if binding is not None:
                    self._assign(binding)

    def _on_click(self, event: MouseButtonEvent) -> None:
        if event.button != glfw.MOUSE_BUTTON_LEFT:
            return
        cell = self.table.cell_at(event.pos, self.scroll)
        if cell is not None:
            row, slot = cell
            self.capturing = (self.actions[row], slot)
            self.message = (
                "Press a key or mouse button (Esc cancels, Backspace clears)"
            )
            return
        match hit_button(self.buttons, event.pos):
            case "reset":
                self.app.keybinds.reset()
                self.app.save_settings()
                self.message = "Controls reset to defaults"
            case "back":
                self._leave()
            case "menu":
                self.app.switch(MainMenu(self.app))
            case _:
                pass

    def on_event(self, event: Event) -> None:
        """Handle input."""
        if isinstance(event, ResizeEvent):
            self.layout()
            return
        if self.capturing is not None:
            self._on_capture(event)
            return
        match event:
            case KeyEvent(key=glfw.KEY_ESCAPE) if event.pressed:
                self._leave()
            case MouseButtonEvent() if event.pressed:
                self._on_click(event)
            case ScrollEvent(dy=dy) if dy:
                self.scroll = self.table.clamp_scroll(
                    self.scroll - dy * self.ROW_HEIGHT
                )
            case _:
                pass

    # Drawing

    def _draw_cell(
        self,
        action: Action,
        slot: int,
        binding: Binding | None,
        mouse: tuple[float, float],
    ) -> None:
        app = self.app
        style = app.ui
        rect = self.table.cell_rect(
            self.actions.index(action), slot, self.scroll
        )
        capturing = self.capturing == (action, slot)
        label = "..." if capturing else (binding.label if binding else "-")
        Button(f"{action}:{slot}", label, rect).draw(
            app.batch, app.text, style, mouse
        )
        if capturing:
            app.batch.shape(
                (rect.x, rect.y, rect.w, rect.h),
                rgba(style.color("hotbar_selected_border")),
                radius=style.button.border_radius,
                border=style.button.border_width,
            )

    def render(self) -> None:
        """Draw the screen."""
        app = self.app
        style = app.ui
        batch = app.batch
        text_color = rgba(style.color("text"))
        w, h = app.screen
        mouse = app.window.mouse_pos

        app.clear(style.color("main_theme"))
        batch.begin(app.screen)
        app.text.draw(
            batch, "Settings", (w / 2, 40), 32, text_color, Anchor.CENTER
        )
        app.text.draw(
            batch, "Controls", (w / 2, 88), 20, text_color, Anchor.CENTER
        )

        table = self.table
        for row, action in enumerate(self.actions):
            if not table.is_visible(row, self.scroll):
                continue
            app.text.draw(
                batch,
                action.label,
                table.label_anchor(row, self.scroll),
                16,
                text_color,
                Anchor.MIDDLE_LEFT,
            )
            for slot, binding in enumerate(app.keybinds.slots(action)[:SLOTS]):
                self._draw_cell(action, slot, binding, mouse)

        if table.max_scroll > 0:
            self._draw_scrollbar()

        if self.message:
            app.text.draw(
                batch,
                self.message,
                (w / 2, h - 95),
                16,
                text_color,
                Anchor.CENTER,
            )
        for button in self.buttons:
            button.draw(batch, app.text, style, mouse)
        app.draw_cursor()

    def _draw_scrollbar(self) -> None:
        table = self.table
        area = table.area
        content = table.rows * table.row_height
        height = area.h * area.h / content
        top = area.y + (area.h - height) * (self.scroll / table.max_scroll)
        color = (*WHITE[:3], 0.3)
        self.app.batch.shape((area.right + 8, top, 4, height), color, radius=2)
