# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from typing import NamedTuple, Self


class IntTuple2(NamedTuple):
    x: int
    y: int

    def serialize(self) -> str:
        return f"{self.x};{self.y}"

    @classmethod
    def deserialize(cls, s: str) -> Self:
        parts = s.split(";")
        return cls(int(parts[0]), int(parts[1]))

    def copy(self) -> IntTuple2:
        return IntTuple2(self.x, self.y)

    def scalei(self, num: int) -> IntTuple2:
        return IntTuple2(self.x * num, self.y * num)

    def scalef(self, num: float) -> FloatTuple2:
        return FloatTuple2(self.x * num, self.y * num)


class FloatTuple2(NamedTuple):
    x: float
    y: float

    def serialize(self) -> str:
        return f"{self.x};{self.y}"

    @classmethod
    def deserialize(cls, s: str) -> Self:
        parts = s.split(";")
        return cls(float(parts[0]), float(parts[1]))

    def copy(self) -> FloatTuple2:
        return FloatTuple2(self.x, self.y)

    def scale(self, num: float) -> FloatTuple2:
        return FloatTuple2(self.x * num, self.y * num)
