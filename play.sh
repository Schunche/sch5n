#!/bin/sh
# Starts the game: ./play.sh
# On the first run it installs uv, which downloads the right Python and
# everything the game needs. Later runs start straight away.
# Extra arguments are passed on, e.g. "./play.sh edit map1".
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv, the tool that runs the game. This happens only once."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
fi

exec uv run --no-dev --python 3.15 sch5n "$@"
