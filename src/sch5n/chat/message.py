# Copyright (c) 2026 Schunche
"""Experimental software."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass(slots=True, frozen=True)
class ChatMessage:
    """Chat message."""

    sender: Any | None
    text: str
