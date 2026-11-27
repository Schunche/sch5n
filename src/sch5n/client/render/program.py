# Copyright (c) 2026 Schunche
"""Shader program helpers."""

from __future__ import annotations

import moderngl


def uniform(program: moderngl.Program, name: str) -> moderngl.Uniform:
    """Look up a uniform of a shader program.

    Returns:
        moderngl.Uniform: The uniform, to set its `value`.

    Raises:
        TypeError: `name` is not a uniform, like an attribute.

    """
    member = program[name]
    if not isinstance(member, moderngl.Uniform):
        msg = f"{name!r} is not a uniform"
        raise TypeError(msg)
    return member
