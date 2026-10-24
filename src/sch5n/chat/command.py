# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar
lazy from collections.abc import Callable


class ChatCommandParseError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ChatCommandPart[T](ABC):
    value: str

    @classmethod
    @abstractmethod
    def parse(cls, s: str) -> ChatCommandPart[T] | None:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ChatCommand:
    start: str
    parts: list[ChatCommandPart[Any]]
    callbacks: list[Callable[..., None]]

    _COMMAND_START_CHAR: ClassVar[str] = "/"

    def parse(self, s: str) -> ChatCommand | None:
        raise NotImplementedError


class ChatCommandBuilder:
    def __init__(self, start: str) -> None:
        self.start = start
        self.parts: list[ChatCommandPart[Any]] = []
        self.callbacks: list[Callable[..., None]] = []

    def add_part(self, part: ChatCommandPart[Any]) -> None:
        self.parts.append(part)

    def add_callback(self, callback: Callable[..., None]) -> None:
        self.callbacks.append(callback)

    def build(self) -> ChatCommand:
        return ChatCommand(self.start, self.parts, self.callbacks)
