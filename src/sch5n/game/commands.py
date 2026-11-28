# Copyright (c) 2026 Schunche
"""Chat commands that need no knowledge of the connections.

These are `/help`, `/players`, `/recipes` and `/me`. The server itself
handles the host's `/kick`, `/mute` and `/unmute`.

Commands run on the server. Each returns the lines to show only to the
one who typed it, or a line to tell everyone.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sch5n.game.content import Content, RecipeSpec

MAX_RECIPE_LINES = 6
"""Most recipes `/recipes` lists at once."""
TIMES = {
    "sunrise": 0.25,
    "day": 0.35,
    "noon": 0.5,
    "sunset": 0.75,
    "night": 0.9,
    "midnight": 0.0,
}
"""Moments of the day `/time` knows, see `daylight.phase`."""
DAY_TICKS = 24000
"""Ticks in a day as `/time` counts them, whatever the real tick rate."""
MAX_TIME_SPEED = 100.0
COMMANDS = {
    "help": "",
    "players": "",
    "recipes": "<item>",
    "me": "<action>",
    "msg": "<player> <text>",
    "home": "",
    "weather": "",
    "tp": "<player>",
    "clear": "",
    "kick": "<player>",
    "mute": "<player>",
    "unmute": "<player>",
    "give": "<item> [amount]",
    "time": "set <moment|ticks> | add <ticks> | speed <n> | query",
}
"""Commands and how they are used; the last few are for the host."""
ALIASES = {
    "?": "help",
    "list": "players",
    "recipe": "recipes",
    "w": "msg",
    "whisper": "msg",
    "tell": "msg",
}
PLAYER_COMMANDS = frozenset({"msg", "kick", "mute", "unmute", "tp"})
TIME_WORDS = ("set", "add", "speed", "query")
HELP = (
    "Commands: " + ", ".join(f"/{name}" for name in COMMANDS),
    "Type / and press Tab to complete; /<command> alone shows its usage.",
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


def usage(command: str) -> str:
    """How a command is used.

    Returns:
        str: Like `/give <item> [amount]`.

    """
    return f"/{command} {COMMANDS[command]}".strip()


def completions(
    text: str, players: Iterable[str], items: Iterable[str]
) -> list[str]:
    """Words that could finish the last word of a chat line.

    Only lines that start with a slash complete. Names with spaces are
    skipped for players; items use underscores.

    Returns:
        list[str]: Sorted candidates for the word being typed.

    """
    if not text.startswith("/"):
        return []
    words = text[1:].split(" ")
    index = len(words) - 1
    prefix = words[-1].lower()
    if index == 0:
        pool: Iterable[str] = COMMANDS
    else:
        command = ALIASES.get(words[0].lower(), words[0].lower())
        pool = _arguments(command, index, words, players, items)
    return sorted(w for w in set(pool) if w.lower().startswith(prefix))


def _arguments(
    command: str,
    index: int,
    words: list[str],
    players: Iterable[str],
    items: Iterable[str],
) -> Iterable[str]:
    if index == 1:
        if command == "time":
            return (*TIME_WORDS, *TIMES)
        if command in PLAYER_COMMANDS:
            return (name for name in players if " " not in name)
        if command in {"recipes", "give"}:
            return items
    elif command == "time" and words[1].lower() == "set":
        return TIMES
    return ()


def usage_line(text: str) -> str:
    """Find the usage of the command being typed, for a hint.

    Returns:
        str: Empty if `text` is not a known command.

    """
    if not text.startswith("/"):
        return ""
    name = text[1:].split(" ", maxsplit=1)[0].lower()
    name = ALIASES.get(name, name)
    return usage(name) if name in COMMANDS else ""


def help_lines(topic: str) -> tuple[str, ...]:
    """Explain all commands, or the usage of one.

    Returns:
        tuple[str, ...]: Lines to show.

    """
    name = topic.strip().lstrip("/").lower()
    name = ALIASES.get(name, name)
    if name in COMMANDS:
        return (usage(name),)
    if name:
        return (unknown_command(name),)
    return HELP


def unknown_command(command: str) -> str:
    """Tell that a command does not exist, suggesting a close one.

    Returns:
        str: The message.

    """
    close = difflib.get_close_matches(command.lower(), COMMANDS, n=1)
    hint = f" Did you mean /{close[0]}?" if close else " Try /help."
    return f"Unknown command /{command}.{hint}"


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
            return CommandResult(help_lines(argument))
        case "players" | "list":
            return CommandResult((
                f"{len(players)} online: {", ".join(players)}",
            ))
        case "recipes" | "recipe":
            return CommandResult(recipes_for(argument, content))
        case "me" if argument:
            return CommandResult(public=f"* {sender} {argument}")
        case _:
            return CommandResult((unknown_command(command),))
