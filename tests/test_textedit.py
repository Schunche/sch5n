# Copyright (c) 2026 Schunche
"""Text editing shared by every input, and chat command completion."""

from __future__ import annotations

import glfw

from sch5n.client.chat import ChatBox
from sch5n.client.textedit import TextEdit
from sch5n.client.window import KeyEvent
from sch5n.game.commands import completions, usage_line

CTRL = glfw.MOD_CONTROL
SHIFT = glfw.MOD_SHIFT


class Clip:
    """A fake clipboard."""

    def __init__(self, text: str = "") -> None:
        """Hold `text`."""
        self.text = text

    def get(self) -> str:
        """Read it.

        Returns:
            str: The text.

        """
        return self.text

    def set(self, text: str) -> None:
        """Replace it."""
        self.text = text


def key(
    edit: TextEdit, key_: int, mods: int = 0, clip: Clip | None = None
) -> None:
    """Press an editing key."""
    clip = clip or Clip()
    assert edit.handle_key(key_, mods, clip.get, clip.set)


def test_caret_moves_and_inserts_in_the_middle() -> None:
    """Arrows, Home and End move the caret; typing inserts there."""
    edit = TextEdit("hello", 20)
    key(edit, glfw.KEY_LEFT)
    key(edit, glfw.KEY_LEFT)
    edit.type("X")
    assert edit.text == "helXlo"
    key(edit, glfw.KEY_HOME)
    edit.type(">")
    key(edit, glfw.KEY_END)
    edit.type("<")
    assert edit.text == ">helXlo<"
    key(edit, glfw.KEY_DELETE)
    key(edit, glfw.KEY_BACKSPACE)
    assert edit.text == ">helXlo"


def test_ctrl_jumps_and_deletes_whole_words() -> None:
    """Ctrl skips words with the arrows and deletes them whole."""
    edit = TextEdit("one two  three", 40)
    key(edit, glfw.KEY_LEFT, CTRL)
    assert edit.caret == len("one two  ")
    key(edit, glfw.KEY_LEFT, CTRL)
    assert edit.caret == len("one ")
    key(edit, glfw.KEY_RIGHT, CTRL)
    assert edit.caret == len("one two")
    key(edit, glfw.KEY_BACKSPACE, CTRL)
    assert edit.text == "one   three"
    key(edit, glfw.KEY_DELETE, CTRL)
    assert edit.text == "one "


def test_selection_copy_cut_paste_and_replace() -> None:
    """Shift selects; Ctrl+A, C, X and V work; typing replaces."""
    clip = Clip()
    edit = TextEdit("abc def", 40)
    key(edit, glfw.KEY_LEFT, CTRL | SHIFT)
    assert edit.selected_text() == "def"
    key(edit, glfw.KEY_C, CTRL, clip)
    assert clip.text == "def"
    key(edit, glfw.KEY_X, CTRL, clip)
    assert edit.text == "abc "
    key(edit, glfw.KEY_HOME)
    key(edit, glfw.KEY_V, CTRL, clip)
    assert edit.text == "defabc "
    key(edit, glfw.KEY_A, CTRL)
    edit.type("z")
    assert edit.text == "z"
    key(edit, glfw.KEY_LEFT, SHIFT)
    assert edit.selected_text() == "z"
    key(edit, glfw.KEY_RIGHT)
    assert edit.caret == 1
    assert not edit.selected_text()


def test_length_limit_and_unprintable_input() -> None:
    """Typing stops at the limit and ignores control characters."""
    edit = TextEdit("", 5)
    edit.type("ab\x07cdefg")
    assert edit.text == "abcde"


def test_command_completions() -> None:
    """Tab candidates for commands, subcommands, players and items."""
    players = ["Alice", "Bob"]
    items = ["iron_axe", "iron_pickaxe", "stick"]
    assert "time" in completions("/ti", players, items)
    assert "give" in completions("/", players, items)
    assert completions("/time s", players, items) == [
        "set",
        "speed",
        "sunrise",
        "sunset",
    ]
    assert completions("/time set ni", players, items) == ["night"]
    assert completions("/give iron_", players, items) == [
        "iron_axe",
        "iron_pickaxe",
    ]
    assert completions("/msg a", players, items) == ["Alice"]
    assert completions("hello", players, items) == []
    assert usage_line("/give").startswith("/give <item>")


def test_tab_completes_in_the_chat_box() -> None:
    """Tab fills a unique word, or the shared start of several."""
    box = ChatBox()
    box.complete = lambda text: completions(
        text, [], ["iron_axe", "iron_pickaxe"]
    )
    box.start("/give iro")
    box.handle(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0), lambda: "")
    assert box.text == "/give iron_"
    box.type("a")
    box.handle(KeyEvent(glfw.KEY_TAB, glfw.PRESS, 0), lambda: "")
    assert box.text == "/give iron_axe "
    assert box.hint().startswith("/give")
