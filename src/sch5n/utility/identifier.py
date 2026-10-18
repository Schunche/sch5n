# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from dataclasses import dataclass

type Mod = bytes
type Id = bytes


_IDENTIFIER_SEP = b":"


@dataclass(slots=True, frozen=True)
class Identifier:
    mod: Mod
    id: Id

    def __post_init__(self) -> None:
        if any((
            not self.mod,
            not self.id,
            self.mod.isascii(),
            self.id.isascii(),
            _IDENTIFIER_SEP in self.mod,
            _IDENTIFIER_SEP in self.id,
        )):
            raise ValueError

    def serialize(self) -> bytes:
        return self.mod + _IDENTIFIER_SEP + self.id

    @classmethod
    def deserialize(cls, s: bytes) -> Identifier:
        parts = s.split(_IDENTIFIER_SEP)
        return Identifier(*parts)
