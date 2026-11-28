# Copyright (c) 2026 Schunche
"""Single line text editing shared by every text input.

Arrows, Home and End move the caret; Shift selects; Ctrl jumps whole
words and deletes them; Ctrl+A, C, X and V select all, copy, cut and
paste.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import glfw

if TYPE_CHECKING:
    from collections.abc import Callable

    from sch5n.client.window import Window

CTRL = glfw.MOD_CONTROL | glfw.MOD_SUPER


def _is_word(char: str) -> bool:
    return char.isalnum() or char == "_"


class TextEdit:
    """Text with a caret and an optional selection."""

    def __init__(self, text: str = "", max_length: int = 64) -> None:
        """Start with the caret after `text`."""
        self.max_length = max_length
        self._text = text
        self.caret = len(text)
        self.anchor = self.caret
        """The other end of the selection; equal to `caret` for none."""

    @property
    def text(self) -> str:
        """The whole text."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value[: self.max_length]
        self.caret = self.anchor = len(self._text)

    @property
    def selection(self) -> tuple[int, int]:
        """Start and end of the selected text; equal when none."""
        return min(self.caret, self.anchor), max(self.caret, self.anchor)

    def selected_text(self) -> str:
        """Get the selected text.

        Returns:
            str: Empty when nothing is selected.

        """
        start, end = self.selection
        return self._text[start:end]

    def _delete_selection(self) -> bool:
        start, end = self.selection
        if start == end:
            return False
        self._text = self._text[:start] + self._text[end:]
        self.caret = self.anchor = start
        return True

    def type(self, chars: str) -> None:
        """Insert printable characters at the caret, up to `max_length`.

        A selection is replaced.
        """
        clean = "".join(c for c in chars if c.isprintable())
        self._delete_selection()
        room = self.max_length - len(self._text)
        clean = clean[: max(0, room)]
        before, after = self._text[: self.caret], self._text[self.caret :]
        self._text = before + clean + after
        self.caret = self.anchor = self.caret + len(clean)

    def backspace(self, *, word: bool = False) -> None:
        """Delete the selection, or the character or word before the caret."""
        if self._delete_selection() or self.caret == 0:
            return
        start = self.word_left(self.caret) if word else self.caret - 1
        self._text = self._text[:start] + self._text[self.caret :]
        self.caret = self.anchor = start

    def delete(self, *, word: bool = False) -> None:
        """Delete the selection, or the character or word after the caret."""
        if self._delete_selection() or self.caret >= len(self._text):
            return
        end = self.word_right(self.caret) if word else self.caret + 1
        self._text = self._text[: self.caret] + self._text[end:]
        self.anchor = self.caret

    def word_left(self, index: int) -> int:
        """Find the start of the word before `index`.

        Returns:
            int: The position.

        """
        text = self._text
        while index > 0 and not _is_word(text[index - 1]):
            index -= 1
        while index > 0 and _is_word(text[index - 1]):
            index -= 1
        return index

    def word_right(self, index: int) -> int:
        """Find the end of the word after `index`.

        Returns:
            int: The position.

        """
        text = self._text
        while index < len(text) and not _is_word(text[index]):
            index += 1
        while index < len(text) and _is_word(text[index]):
            index += 1
        return index

    def move(self, to: int, *, select: bool) -> None:
        """Put the caret at `to`, extending the selection if asked."""
        self.caret = max(0, min(len(self._text), to))
        if not select:
            self.anchor = self.caret

    def select_all(self) -> None:
        """Select everything."""
        self.anchor = 0
        self.caret = len(self._text)

    def _move_key(self, key: int, *, word: bool, select: bool) -> bool:
        start, end = self.selection
        match key:
            case glfw.KEY_LEFT:
                if start != end and not select and not word:
                    self.move(start, select=False)
                else:
                    to = self.word_left(self.caret) if word else self.caret - 1
                    self.move(to, select=select)
            case glfw.KEY_RIGHT:
                if start != end and not select and not word:
                    self.move(end, select=False)
                else:
                    to = (
                        self.word_right(self.caret) if word else self.caret + 1
                    )
                    self.move(to, select=select)
            case glfw.KEY_HOME:
                self.move(0, select=select)
            case glfw.KEY_END:
                self.move(len(self._text), select=select)
            case _:
                return False
        return True

    def handle_key(
        self,
        key: int,
        mods: int,
        clipboard: Callable[[], str],
        set_clipboard: Callable[[str], None] = lambda _text: None,
    ) -> bool:
        """React to a key press or repeat.

        Returns:
            bool: Whether the key was an editing key and was used.

        """
        ctrl = bool(mods & CTRL)
        select = bool(mods & glfw.MOD_SHIFT)
        if self._move_key(key, word=ctrl, select=select):
            return True
        match key:
            case glfw.KEY_BACKSPACE:
                self.backspace(word=ctrl)
            case glfw.KEY_DELETE:
                self.delete(word=ctrl)
            case glfw.KEY_A if ctrl:
                self.select_all()
            case glfw.KEY_C if ctrl:
                if self.selected_text():
                    set_clipboard(self.selected_text())
            case glfw.KEY_X if ctrl:
                if self.selected_text():
                    set_clipboard(self.selected_text())
                    self._delete_selection()
            case glfw.KEY_V if ctrl:
                self.type(clipboard().replace("\n", " "))
            case _:
                return False
        return True

    def handle_window_key(self, key: int, mods: int, window: Window) -> bool:
        """`handle_key` with the window's clipboard.

        Returns:
            bool: Whether the key was an editing key and was used.

        """
        return self.handle_key(
            key,
            mods,
            lambda: window.clipboard,
            lambda text: setattr(window, "clipboard", text),
        )
