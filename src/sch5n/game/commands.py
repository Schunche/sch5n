# Copyright (c) 2026 Schunche
"""Chat commands that need no knowledge of the connections.

These are `/help`, `/players`, `/recipes` and `/me`. The server itself
handles the host's `/kick`, `/mute` and `/unmute`.

Commands run on the server. Each returns the lines to show only to the
one who typed it, or a line to tell everyone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sch5n.game.content import Content, RecipeSpec

MAX_RECIPE_LINES = 6
"""Most recipes `/recipes` lists at once."""
HELP = (
    "Commands: /help, /players, /recipes <item>, /me <action>",
    "The host also has /kick, /mute and /unmute <player>, and /time <moment>.",
    "T or Enter opens the chat, Esc closes it.",
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    """What a command wants shown."""

    private: tuple[str, ...] = ()
    """Lines for the sender alone."""
    public: str = ""
    """A line for everyone."""


def describe_recipe(recipe: RecipeSpec, content: Content) -> str:
    """Write a recipe in one line, like `2 Oak Planks: 2x2 stick`.

    Returns:
        str: The description.

    """
    items = content.items

    def label(names: Iterable[str]) -> str:
        return "/".join(items[name].spec.name for name in names)

    made = items[recipe.result.item].spec.name
    if recipe.result.amount > 1:
        made = f"{recipe.result.amount} {made}"
    if recipe.pattern:
        needs = ", ".join(
            f"{symbol} = {label(recipe.choices(symbol))}"
            for symbol in sorted(recipe.key)
        )
        shape = f"{len(recipe.pattern[0])}x{len(recipe.pattern)}"
        return f"{made}: {shape} grid, {needs}"
    counts: dict[str, int] = {}
    for name in recipe.ingredients:
        counts[name] = counts.get(name, 0) + 1
    needs = ", ".join(
        f"{amount} {label([name])}" for name, amount in counts.items()
    )
    return f"{made}: {needs}"


def recipes_for(query: str, content: Content) -> tuple[str, ...]:
    """Find recipes whose result matches a name.

    Returns:
        tuple[str, ...]: Descriptions; a hint when nothing matches.

    """
    query = query.strip().lower().replace("_", " ")
    found = [
        describe_recipe(recipe, content)
        for recipe in content.recipes
        if not query
        or query in content.items[recipe.result.item].spec.name.lower()
    ]
    if not found:
        return (f"No recipe makes {query!r}.",)
    shown = found[:MAX_RECIPE_LINES]
    if len(found) > len(shown):
        shown.append(f"...and {len(found) - len(shown)} more. Be specific.")
    return tuple(shown)


def run_command(
    text: str, sender: str, players: list[str], content: Content
) -> CommandResult:
    """Run a chat line that starts with a slash.

    Returns:
        CommandResult: What to show.

    """
    command, _, argument = text.removeprefix("/").partition(" ")
    argument = argument.strip()
    match command.lower():
        case "help" | "?":
            return CommandResult(HELP)
        case "players" | "list":
            return CommandResult((
                f"{len(players)} online: {", ".join(players)}",
            ))
        case "recipes" | "recipe":
            return CommandResult(recipes_for(argument, content))
        case "me" if argument:
            return CommandResult(public=f"* {sender} {argument}")
        case _:
            return CommandResult((f"Unknown command /{command}. Try /help.",))
