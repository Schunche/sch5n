# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass
from abc import ABC
from typing import Literal

from sch5n.chat.format import TextStyle
from sch5n.utility.identifier import Identifier


@dataclass
class MessagePart(ABC):
    style: TextStyle


@dataclass
class TextMessagePart(MessagePart):
    text: str


@dataclass
class ItemMessagePart(MessagePart):
    item_id: Identifier


@dataclass(kw_only=True)
class TextModifierMessagePart(MessagePart):
    modifier: Literal["italic", "bold", "underline", "cross"]
    value: bool


class Message:
    def __init__(self, s: str) -> None:
        self.parts: list[MessagePart] = []
        self._parse("")

    def _parse_instruction(self, s: str) -> MessagePart | None:
        s = s.lower().removeprefix("!").split("=", maxsplit=1)[0]
        if s not in ["italic", "bold", "underline", "cross", "size", "color"]:
            return None

    def _parse(self, s: str) -> None:
        pass
