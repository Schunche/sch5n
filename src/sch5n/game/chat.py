# Copyright (c) 2026 Schunche
"""Chat rules shared by the server and the clients: limits and cleaning."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum

MAX_CHAT_LENGTH = 160
"""Longest chat message, in characters."""
CHAT_HISTORY = 100
"""Messages kept for scrollback."""
CHAT_BURST = 5
"""Messages a player may send in quick succession."""
CHAT_REFILL_TICKS = 30
"""Ticks until a player may send one more message after a burst."""


class ChatKind(StrEnum):
    """What a chat line is."""

    CHAT = "chat"
    """A player said something."""
    JOIN = "join"
    LEAVE = "leave"
    SYSTEM = "system"
    """Information from the server, for one player or everyone."""


def sanitize(text: str, limit: int = MAX_CHAT_LENGTH) -> str:
    """Make text safe to show.

    Control and invisible characters go, whitespace becomes single spaces
    and the text is cut to `limit` characters.

    Returns:
        str: The cleaned text, empty if nothing printable was left.

    """
    kept = [
        " " if char.isspace() else char
        for char in text
        if char.isspace()
        or unicodedata.category(char) not in {"Cc", "Cf", "Cs", "Co", "Cn"}
    ]
    return " ".join("".join(kept).split())[:limit].rstrip()


@dataclass(slots=True)
class RateLimit:
    """Allows `CHAT_BURST` messages at once, then one per refill period."""

    tokens: float = CHAT_BURST
    last_tick: int = 0

    def allow(self, tick: int) -> bool:
        """Spend a token at server tick `tick`.

        Returns:
            bool: Whether the message may be sent.

        """
        gained = max(0, tick - self.last_tick) / CHAT_REFILL_TICKS
        self.tokens = min(CHAT_BURST, self.tokens + gained)
        self.last_tick = tick
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True
