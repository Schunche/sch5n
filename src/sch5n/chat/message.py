# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass
lazy from typing import Any


@dataclass(slots=True, frozen=True)
class ChatMessage:
    """Chat message."""

    sender: Any | None
    text: str
