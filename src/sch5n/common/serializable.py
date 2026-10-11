# Copyright (c) 2026 Schunche
"""Experimental software."""

from abc import ABC, abstractmethod
from typing import Self


class Serializable[T: str | bytes](ABC):
    @abstractmethod
    def serialize(self) -> T: ...

    @classmethod
    @abstractmethod
    def deserialize(cls, s: T) -> Self: ...


class StrSerializable(Serializable[str]): ...
