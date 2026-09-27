# Copyright (c) 2026 Schunche
"""Experimental software."""

from enum import Enum


class ModSide(Enum):
    """Define sync between clients and servers."""

    CLIENT = 0b01
    SERVER = 0b10
    BOTH = 0b11

class Mod:
    def __init__(
        self,
        name: str,
        side: ModSide
    ) -> None:
        self._name: str = name

    @property
    def name(self) -> str:
        return self._name
