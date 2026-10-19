# Copyright (c) 2026 Schunche
"""Experimental software."""

type IntTuple2 = tuple[int, int]
type IntTuple3 = tuple[int, int, int]
type IntTuple4 = tuple[int, int, int, int]

type FloatTuple2 = tuple[float, float]
type FloatTuple3 = tuple[float, float, float]
type FloatTuple4 = tuple[float, float, float, float]


def deserialize_int_tuple_2(s: str) -> IntTuple2:
    parts = s.split(";")
    return (int(parts[0]), int(parts[1]))
