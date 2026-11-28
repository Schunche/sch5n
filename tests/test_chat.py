# Copyright (c) 2026 Schunche
"""The chat box: wrapping, typing, history and the lines it shows."""

from __future__ import annotations

import glfw

from sch5n.client.chat import ChatBox, format_line, wrap
from sch5n.client.window import CharEvent, KeyEvent, ScrollEvent
from sch5n.game.chat import MAX_CHAT_LENGTH, ChatKind, sanitize
from sch5n.net.protocol import ChatMessage

TICK_RATE = 60


def press(box: ChatBox, key: int) -> str:
    """Press a key in an open chat box.

    Returns:
        str: What it sent.

    """
    return box.handle(KeyEvent(key, glfw.PRESS, 0), lambda: "")


def type_text(box: ChatBox, text: str) -> None:
    """Type characters into the box."""
    for char in text:
        box.handle(CharEvent(char), lambda: "")


def test_sanitize() -> None:
    """Control, bidi and format characters go; spaces collapse."""
    assert sanitize("  a \t b\n\nc\x00 ") == "a b c"
    assert sanitize("x" + chr(0x200B) + chr(0x202E) + "y") == "xy"
    assert sanitize("é漢😀") == "é漢😀"
    assert sanitize("y" * 500) == "y" * MAX_CHAT_LENGTH
    assert sanitize("a" * 3 + " " * 5, limit=4) == "aaa"
    assert not sanitize("\x07\x08")


def test_wrap() -> None:
    """Lines break at spaces, and overlong words are split."""
    assert wrap("one two three", 7) == ["one two", "three"]
    assert wrap("a" * 10, 4) == ["aaaa", "aaaa", "aa"]
    assert wrap("", 5) == [""]


def test_format_lines() -> None:
    """Every kind of line reads naturally."""
    assert format_line(ChatMessage(sender="a", text="hi")) == "<a> hi"
    join = ChatMessage(kind=ChatKind.JOIN, sender="a")
    assert format_line(join) == "a joined the game"
    leave = ChatMessage(kind=ChatKind.LEAVE, sender="a")
    assert format_line(leave) == "a left the game"
    system = ChatMessage(kind=ChatKind.SYSTEM, text="hello")
    assert format_line(system) == "hello"


def test_typing_and_sending() -> None:
    """Enter sends the cleaned text and closes the box."""
    box = ChatBox()
    box.start()
    type_text(box, "hi  there")
    press(box, glfw.KEY_BACKSPACE)
    assert box.text == "hi  ther"
    assert press(box, glfw.KEY_ENTER) == "hi ther"
    assert not box.open
    assert not box.text


def test_empty_and_cancelled_messages_send_nothing() -> None:
    """Blank text sends nothing; Escape drops the text."""
    box = ChatBox()
    box.start()
    type_text(box, "   ")
    assert not press(box, glfw.KEY_ENTER)
    box.start()
    type_text(box, "nope")
    assert not press(box, glfw.KEY_ESCAPE)
    assert not box.open
    assert not box.sent


def test_typing_is_limited() -> None:
    """Typing stops at the longest message, and control chars are ignored."""
    box = ChatBox()
    box.start()
    type_text(box, "x" * (MAX_CHAT_LENGTH + 10) + "\x00")
    assert len(box.text) == MAX_CHAT_LENGTH


def test_earlier_messages_can_be_recalled() -> None:
    """Up brings back what was sent, down returns to what was typed."""
    box = ChatBox()
    for text in ("first", "second"):
        box.start()
        type_text(box, text)
        press(box, glfw.KEY_ENTER)
    box.start()
    type_text(box, "draft")
    press(box, glfw.KEY_UP)
    assert box.text == "second"
    press(box, glfw.KEY_UP)
    assert box.text == "first"
    press(box, glfw.KEY_UP)
    assert box.text == "first"
    press(box, glfw.KEY_DOWN)
    press(box, glfw.KEY_DOWN)
    assert box.text == "draft"


def test_paste_and_scrollback() -> None:
    """Pasting flattens lines; scrolling stays within the log."""
    box = ChatBox()
    box.start()
    box.handle(
        KeyEvent(glfw.KEY_V, glfw.PRESS, glfw.MOD_CONTROL), lambda: "a\nb"
    )
    assert box.text == "a b"
    for number in range(30):
        box.add(ChatMessage(sender="x", text=str(number)), 0)
    total = box.total_lines()
    box.handle(ScrollEvent(0, 1000), lambda: "")
    assert 0 < box.scroll <= total
    box.handle(ScrollEvent(0, -1000), lambda: "")
    assert box.scroll == 0
