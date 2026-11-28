#!/bin/sh
# Starts the game: ./play.sh
# On the first run it installs uv, which downloads the right Python and
# everything the game needs. Later runs start straight away.
# Extra arguments are passed on, e.g. "./play.sh view --edit --map mymap".
set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv, the tool that runs the game. This happens only once."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
fi

# Offers once to add the game to the app menu and the Desktop. The answer
# is remembered; without a terminal to ask in, nothing is added.
ASKED="${XDG_CONFIG_HOME:-${HOME:?}/.config}/sch5n/shortcuts-asked"
if [ "$(uname)" = Linux ] && [ ! -f "$ASKED" ] && [ -t 0 ] && [ "$#" -eq 0 ]; then
    printf 'Add the game to your apps menu? [y/N] '
    read -r menu || menu=n
    printf 'Add a shortcut to your Desktop? [y/N] '
    read -r desk || desk=n
    mkdir -p "$(dirname "$ASKED")"
    echo "menu=$menu desktop=$desk" > "$ASKED"
    case "$menu$desk" in
        *[yY]*) ;;
        *) echo "No shortcuts added. ./install-desktop.sh adds them later." ;;
    esac
    case "$desk" in
        y | Y | yes | Yes)
            ./install-desktop.sh --desktop || true
            case "$menu" in
                y | Y | yes | Yes) ;;
                *) rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/sch5n.desktop" ;;
            esac
            ;;
        *)
            case "$menu" in
                y | Y | yes | Yes) ./install-desktop.sh || true ;;
            esac
            ;;
    esac
fi

exec uv run --no-dev --python 3.15 sch5n "$@"
