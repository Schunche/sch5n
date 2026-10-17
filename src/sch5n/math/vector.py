# Copyright (c) 2026 Schunche
"""Experimental software."""

type IntTuple2 = tuple[int, int]
type FloatTuple2 = tuple[float, float]


def deserialize_int_tuple_2(s: str) -> IntTuple2:
    parts = s.split(";")
    return (int(parts[0]), int(parts[1]))
