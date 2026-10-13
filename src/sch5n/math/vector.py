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

    def copy(self) -> Self:
        return type(self)(self.x, self.y)

    def scalei(self, num: int) -> Self:
        return type(self)(self.x * num, self.y * num)

    def scalef(self, num: float) -> FloatTuple2:
        return FloatTuple2(self.x * num, self.y * num)

    def with_x(self, x: int) -> Self:
        return type(self)(x, self.y)

    def with_y(self, y: int) -> Self:
        return type(self)(self.x, y)

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)


class FloatTuple2(NamedTuple):
    x: float
    y: float

    def serialize(self) -> str:
        return f"{self.x};{self.y}"

    @classmethod
    def deserialize(cls, s: str) -> Self:
        parts = s.split(";")
        return cls(float(parts[0]), float(parts[1]))

    def copy(self) -> Self:
        return type(self)(self.x, self.y)

    def scale(self, num: float) -> Self:
        return type(self)(self.x * num, self.y * num)

    def with_x(self, x: float) -> FloatTuple2:
        return type(self)(x, self.y)

    def with_y(self, y: float) -> FloatTuple2:
        return type(self)(self.x, y)

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)
