# Copyright (c) 2026 Schunche
"""The chat box: recent lines over the game, and a field to type in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import glfw

from sch5n.client.render.batch import rgba
from sch5n.client.render.text import Anchor, TextStyle
from sch5n.client.window import CharEvent, KeyEvent, ScrollEvent
from sch5n.game.chat import MAX_CHAT_LENGTH, ChatKind, sanitize

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.render.batch import SpriteBatch
    from sch5n.client.render.text import TextRenderer
    from sch5n.client.style import Style
    from sch5n.client.window import Event
    from sch5n.net.protocol import ChatMessage

TEXT_SIZE = 16
LINE_GAP = 2
PADDING = 8
SHOWN_LINES = 8
"""Lines visible at once while typing."""
RECENT_LINES = 6
"""Lines shown while the box is closed, as long as they are recent."""
SHOW_SECONDS = 10
"""How long a new line stays on screen while the box is closed."""
FADE_SECONDS = 1.5
MAX_WIDTH = 520
WIDTH_SHARE = 0.5
"""Largest share of the window the chat takes."""
MAX_SENT_HISTORY = 50
PAGE_LINES = 4
"""Lines the page keys scroll."""


def format_line(message: ChatMessage) -> str:
    """Write a chat message as shown on screen.

    Returns:
        str: The line.

    """
    match message.kind:
        case ChatKind.CHAT:
            return f"<{message.sender}> {message.text}"
        case ChatKind.JOIN:
            return f"{message.sender} joined the game"
        case ChatKind.LEAVE:
            return f"{message.sender} left the game"
        case ChatKind.SYSTEM:
            return message.text


def wrap(text: str, fits: int) -> list[str]:
    """Break text into lines of at most `fits` characters.

    Words longer than a line are split. Wrapping counts characters, which
    suits the game's monospaced fonts.

    Returns:
        list[str]: At least one line.

    """
    fits = max(1, fits)
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        while len(word) > fits:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:fits])
            word = word[fits:]  # ruff: ignore[redefined-loop-name]
        joined = f"{current} {word}" if current else word
        if len(joined) > fits:
            lines.append(current)
            current = word
        else:
            current = joined
    lines.append(current)
    return lines


@dataclass(slots=True)
class Entry:
    """A received line and when it arrived."""

    message: ChatMessage
    tick: int


class ChatBox:
    """Chat lines, the typed text, and how both are drawn."""

    def __init__(self) -> None:
        """Start closed and empty."""
        self.entries: list[Entry] = []
        self.open = False
        self.text = ""
        self.scroll = 0
        """Lines scrolled back from the newest."""
        self.sent: list[str] = []
        self._recall: int | None = None
        self._pending = ""

    def add(self, message: ChatMessage, tick: int) -> None:
        """Take in a line. A scrolled back view stays where it is."""
        self.entries.append(Entry(message, tick))
        if self.scroll:
            self.scroll += 1

    def start(self, prefix: str = "") -> None:
        """Open the box to type."""
        self.open = True
        self.text = prefix
        self.scroll = 0
        self._recall = None

    def close(self) -> None:
        """Stop typing, dropping what was typed."""
        self.open = False
        self.text = ""
        self.scroll = 0
        self._recall = None

    def type(self, chars: str) -> None:
        """Add printable characters, up to the longest message."""
        for char in chars:
            if char.isprintable() and len(self.text) < MAX_CHAT_LENGTH:
                self.text += char

    def backspace(self) -> None:
        """Delete the last character."""
        self.text = self.text[:-1]

    def submit(self) -> str:
        """Finish typing.

        Returns:
            str: The cleaned message to send, empty if there is none.

        """
        text = sanitize(self.text)
        if text and (not self.sent or self.sent[-1] != text):
            self.sent.append(text)
            del self.sent[:-MAX_SENT_HISTORY]
        self.close()
        return text

    def recall(self, step: int) -> None:
        """Bring back an earlier sent message (`step` -1) or return (+1)."""
        if not self.sent:
            return
        if self._recall is None:
            if step >= 0:
                return
            self._pending = self.text
            self._recall = len(self.sent)
        self._recall += step
        if self._recall >= len(self.sent):
            self._recall = None
            self.text = self._pending
            return
        self._recall = max(0, self._recall)
        self.text = self.sent[self._recall]

    def scroll_by(self, lines: int, total: int) -> None:
        """Look further back (positive) or forward, within `total` lines."""
        limit = max(0, total - SHOWN_LINES)
        self.scroll = max(0, min(limit, self.scroll + lines))

    def handle(self, event: Event, clipboard: Callable[[], str]) -> str:
        """React to input while the box is open.

        Returns:
            str: A message to send, empty for none.

        """
        match event:
            case CharEvent(char=char):
                self.type(char)
            case KeyEvent(action=glfw.RELEASE):
                pass
            case KeyEvent(key=glfw.KEY_ESCAPE):
                self.close()
            case KeyEvent(key=glfw.KEY_ENTER | glfw.KEY_KP_ENTER):
                return self.submit()
            case KeyEvent(key=glfw.KEY_V, mods=mods) if mods & (
                glfw.MOD_CONTROL | glfw.MOD_SUPER
            ):
                self.type(clipboard().replace("\n", " "))
            case KeyEvent(key=key):
                self._on_key(key)
            case ScrollEvent(dy=dy) if dy:
                self.scroll_by(round(dy) * 3, self.total_lines())
            case _:
                pass
        return ""

    def _on_key(self, key: int) -> None:
        match key:
            case glfw.KEY_BACKSPACE:
                self.backspace()
            case glfw.KEY_UP:
                self.recall(-1)
            case glfw.KEY_DOWN:
                self.recall(1)
            case glfw.KEY_PAGE_UP:
                self.scroll_by(PAGE_LINES, self.total_lines())
            case glfw.KEY_PAGE_DOWN:
                self.scroll_by(-PAGE_LINES, self.total_lines())
            case _:
                pass

    # Drawing

    def _wrapped(
        self, tick: int, tick_rate: int, fits: int
    ) -> list[tuple[str, ChatKind, float]]:
        """Break the lines that count into screen lines.

        Returns:
            list[tuple[str, ChatKind, float]]: Text, kind and opacity,
            oldest first.

        """
        shown: list[tuple[str, ChatKind, float]] = []
        for entry in self.entries:
            if self.open:
                alpha = 1.0
            else:
                left = ((SHOW_SECONDS * tick_rate) - (tick - entry.tick)) / (
                    FADE_SECONDS * tick_rate
                )
                alpha = min(1.0, left)
                if alpha <= 0:
                    continue
            shown.extend(
                (line, entry.message.kind, alpha)
                for line in wrap(format_line(entry.message), fits)
            )
        return shown

    def total_lines(self, fits: int = 60) -> int:
        """Screen lines the whole log takes, for scrolling.

        Returns:
            int: The count.

        """
        return sum(
            len(wrap(format_line(entry.message), fits))
            for entry in self.entries
        )

    def draw(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]
        self,
        batch: SpriteBatch,
        text: TextRenderer,
        style: Style,
        screen: tuple[int, int],
        tick: int,
        tick_rate: int,
        *,
        caret: bool,
    ) -> None:
        """Queue the chat in the lower left corner."""
        width = min(MAX_WIDTH, int(screen[0] * WIDTH_SHARE))
        char_w = max(1, text.measure("M", TEXT_SIZE)[0])
        fits = max(8, (width - 2 * PADDING) // char_w)
        lines = self._wrapped(tick, tick_rate, fits)
        count = SHOWN_LINES if self.open else RECENT_LINES
        end = len(lines) - self.scroll
        visible = lines[max(0, end - count) : max(0, end)]
        if not visible and not self.open:
            return
        line_h = text.measure("Mg", TEXT_SIZE)[1] + LINE_GAP
        margin = style.outer_padding
        field_h = line_h + 2 * PADDING
        bottom = screen[1] - margin
        if self.open:
            bottom -= field_h + PADDING
        top = bottom - len(visible) * line_h
        if self.open:
            batch.shape(
                (
                    margin,
                    top - PADDING,
                    width,
                    bottom - top + 2 * PADDING + field_h + PADDING,
                ),
                rgba(style.color("button_inner"), 0.75),
                radius=6,
            )
        for i, (line, kind, alpha) in enumerate(visible):
            name = "text" if kind is ChatKind.CHAT else "text_dim"
            if kind is ChatKind.SYSTEM:
                name = "accent"
            if not self.open:
                batch.shape(
                    (margin, top + i * line_h, width, line_h),
                    rgba(style.color("button_inner"), 0.45 * alpha),
                )
            text.draw(
                batch,
                line,
                (margin + PADDING, top + i * line_h),
                TextStyle(
                    size=TEXT_SIZE, color=rgba(style.color(name), alpha)
                ),
            )
        if self.open:
            field_y = bottom + PADDING
            batch.shape(
                (margin + PADDING // 2, field_y, width - PADDING, field_h),
                rgba(style.color("accent")),
                radius=4,
                border=1.5,
            )
            shown = self.text + ("|" if caret else "")
            while shown and text.measure(shown, TEXT_SIZE)[0] > (
                width - 4 * PADDING
            ):
                shown = shown[1:]
            text.draw(
                batch,
                shown,
                (margin + 2 * PADDING, field_y + field_h / 2),
                TextStyle(
                    size=TEXT_SIZE,
                    color=rgba(style.color("text")),
                    anchor=Anchor.MIDDLE_LEFT,
                ),
            )
