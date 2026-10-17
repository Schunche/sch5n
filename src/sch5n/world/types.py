# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass
from enum import Enum, StrEnum

type Seed = str


class Difficulty(StrEnum):
    CASUAL = "Casual"
    EXPERT = "Expert"
    MASTER = "Master"


class Size(Enum):
    SMALL = (4200, 1200)
    MEDIUM = (6400, 1800)
    LARGE = (8400, 2400)


@dataclass(slots=True)
class Options:
    seed: Seed
    size: Size
    difficulty: Difficulty
