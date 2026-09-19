# Copyright (c) 2026 Schunche
"""Experimental software."""

import secrets


def randf() -> float:
    """Generate a random float in the range [0.0, 1.0).

    Returns:
        float: Generated number

    """
    return secrets.randbits(53) / 2**53
