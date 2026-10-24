# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from collections.abc import Awaitable

lazy from sch5n.world.types import Options as WorldGenerationOptions


async def generate(options: WorldGenerationOptions) -> Awaitable[None]:
    raise NotImplementedError
