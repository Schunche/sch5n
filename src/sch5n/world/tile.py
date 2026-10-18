# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass

lazy from sch5n.utility.identifier import Identifier


@dataclass
class Tile:
    id: Identifier
