# CLAUDE.md

Standing rules for working in this repo.

## Workflow rules

- Python 3.15 is required. If the environment can't run it, run tests through a Remote Control session on the user's machine, from the repo root.
- No file should tie to an exact machine (no absolute local paths, usernames or hostnames); keep paths broad and repo-relative.
- Run only the tests relevant to a change. Never run the full suite unless the user asks.
- Run those relevant tests automatically after every change, without asking.
- Never commit, merge or push to `main`/`master`. Work happens on the `claude/terraria-game-refactor-ls68lp` branch.
- If a subagent or thread can't do something because of a permission or environment limit, the main agent does that work itself instead of handing it back to the user.

## Project facts

- Non-placeable items (`stick`, `leaf`, `bird_nest`) and `extra_drops` live in `data/blocks.json`.
- Tool animations live in `data/animations.json`.
- World favorites are stored in `favorites.json` next to the worlds.
