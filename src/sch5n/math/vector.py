# Copyright (c) 2026 Schunche
"""Experimental software."""

type IntTuple2 = tuple[int, int]
type IntTuple3 = tuple[int, int, int]
type IntTuple4 = tuple[int, int, int, int]

type FloatTuple2 = tuple[float, float]
type FloatTuple3 = tuple[float, float, float]
type FloatTuple4 = tuple[float, float, float, float]


def serialize_int_tuple_2(tup: IntTuple2) -> str:
    return f"{tup[0]};{tup[1]}"


def deserialize_int_tuple_2(s: str) -> IntTuple2:
    parts = s.split(";")
    return (int(parts[0]), int(parts[1]))


def parse_int_tuple2(value: object) -> IntTuple2:
    if not isinstance(value, list) or len(value) != 2:  # pyright: ignore[reportUnknownArgumentType]  # ruff: ignore[magic-value-comparison]
        msg = "Invalid IntTuple2"
        raise ValueError(msg)

    x, y = value  # pyright: ignore[reportUnknownVariableType]

    if type(x) is not int or type(y) is not int:  # pyright: ignore[reportUnknownArgumentType]
        msg_0 = "Invalid IntTuple2"
        raise ValueError(msg_0)

    return (x, y)


def parse_int_tuple3(value: object) -> IntTuple3:
    if not isinstance(value, list) or len(value) != 3:  # pyright: ignore[reportUnknownArgumentType] # ruff: ignore[magic-value-comparison]
        msg = "Invalid IntTuple3"
        raise ValueError(msg)

    x, y, z = value  # pyright: ignore[reportUnknownVariableType]

    if type(x) is not int or type(y) is not int or type(z) is not int:  # pyright: ignore[reportUnknownArgumentType]
        msg_0 = "Invalid IntTuple3"
        raise ValueError(msg_0)

    return (x, y, z)
