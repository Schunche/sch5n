# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from typing import TYPE_CHECKING

lazy from jmespath import compile as _compile
lazy from jmespath import search as _search
lazy from jmespath.parser import ParsedResult

if TYPE_CHECKING:
    lazy from jmespath import Options as _Options

type JsonArray = list[Json]
type JsonObject = dict[str, Json]
type Json = bool | float | int | str | JsonArray | JsonObject | None


class JsonQuery(str):  # ruff: ignore[subclass-builtin]
    """JMESPath query string."""

    __slots__ = ()

    def compile(self) -> ParsedResult:
        """Compile query for faster use.

        Returns:
            ParsedResult: Faster query.

        """
        return _compile(self)


def search(
    data: Json, query: JsonQuery, options: _Options | None = None
) -> Json | None:
    """Search for an expression in a JSON object.

    Args:
        data (Json): JSON data.
        query (JsonQuery): Query expression.
        options (_Options | None, optional): JSON query options.

    Returns:
        Json | None: Query result.

    """
    return _search(query, data, options)
