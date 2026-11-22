# Copyright (c) 2026 Schunche
"""Experimental software."""

from contextlib import suppress
from dataclasses import dataclass
from sch5n.math.vector import IntTuple4

UNSET = sentinel("UNSET")


def parse_color(s: str, *, allow_off: bool = False) -> IntTuple4:
    s = s.lower()
    mult = 17 if allow_off else 16
    if s.startswith("#"):
        s = s.removeprefix("#")
        match len(s):
            case 3:
                return (
                    int(s[0], 16) * mult,
                    int(s[1], 16) * mult,
                    int(s[2], 16) * mult,
                    255,
                )
            case 4:
                return (
                    int(s[0], 16) * mult,
                    int(s[1], 16) * mult,
                    int(s[2], 16) * mult,
                    int(s[3], 16) * mult,
                )
            case 6:
                return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
            case 8:
                return (
                    int(s[0:2], 16),
                    int(s[2:4], 16),
                    int(s[4:6], 16),
                    int(s[6:8], 16),
                )
            case _:
                raise ValueError

    raise ValueError


@dataclass(slots=True, kw_only=True)
class TextStyle:
    color: IntTuple4 | None = None
    size: int | None = None
    cross: bool = False
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def reset(self) -> None:
        other = type(self)()

        for field, value in other.__dataclass_fields__.items():
            setattr(self, field, value)

    def change(self, segment: str) -> None:
        segment = segment.lower()

        if segment in ["italic", "bold", "underline", "cross"]:
            setattr(self, segment.removeprefix("!"), segment.startswith("!"))
            return

        if segment == "!color":
            self.color = None
            return
        if segment == "!size":
            self.size = None
            return

        match segment.split("=", maxsplit=1):
            case [name, value]:
                match name:
                    case "color":
                        color = UNSET
                        with suppress(ValueError):
                            color = parse_color(value)
                        if color is not UNSET:
                            self.color = color

                    case "size":
                        size = UNSET
                        with suppress(ValueError):
                            size = abs(int(value)) if value != "0" else None
                        if size is not UNSET:
                            self.size = size

                    case _:
                        raise NotImplementedError

            case _:
                raise NotImplementedError

        raise NotImplementedError
