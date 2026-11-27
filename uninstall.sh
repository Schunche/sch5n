#!/bin/sh
# Removes the game: ./uninstall.sh
# Deletes your settings, logs and (if you want) your saved worlds, then
# offers to remove uv and the game folder. It asks before each step.
# "./uninstall.sh --yes" answers yes to everything but removing uv.
set -u

GAME=$(cd "$(dirname "$0")" && pwd)
CONFIG="${XDG_CONFIG_HOME:-${HOME:?}/.config}/sch5n"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/sch5n"
LOGS="${XDG_STATE_HOME:-$HOME/.local/state}/sch5n"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
ENTRY="$SHARE/applications/sch5n.desktop"
ICON="$SHARE/icons/hicolor/512x512/apps/sch5n.png"
YES=0
if [ "${1:-}" = "--yes" ]; then
    YES=1
fi

# ask QUESTION: yes or no, no by default. --yes says yes.
ask() {
    if [ "$YES" = 1 ]; then
        return 0
    fi
    printf '%s [y/N] ' "$1"
    read -r answer || return 1
    case "$answer" in
        y | Y | yes | Yes | YES) return 0 ;;
        *) return 1 ;;
    esac
}

if [ ! -f "$GAME/data/game.json" ] || [ ! -f "$GAME/play.sh" ]; then
    echo "This file must stay in the game folder; $GAME is not one."
    exit 1
fi

echo "This removes the game:"
echo "  your settings  $CONFIG"
echo "  your logs      $LOGS"
echo "  your worlds    $DATA (you will be asked)"
echo "  the game       $GAME (you will be asked)"
if ! ask "Uninstall the game?"; then
    echo "Nothing was removed."
    exit 0
fi

rm -rf "$CONFIG" "$LOGS"
rm -f "$ENTRY" "$ICON"
echo "Removed your settings and logs."

if [ -d "$DATA/worlds" ]; then
    if ask "Delete your saved worlds too? They cannot be brought back."; then
        rm -rf "$DATA"
        echo "Removed your worlds."
    else
        echo "Kept your worlds in $DATA/worlds"
    fi
else
    rm -rf "$DATA"
fi

# uv may be used by other programs too, so it is only removed when asked,
# never by --yes.
if [ "$YES" = 0 ] && command -v uv >/dev/null 2>&1; then
    if ask "Remove uv and the Python it downloaded? Say no if other programs use uv."; then
        uv cache clean
        rm -rf "$(uv python dir)" "$(uv tool dir)"
        rm -f "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx"
        echo "Removed uv."
    fi
fi

if ask "Delete the game folder $GAME?"; then
    cd / && rm -rf "$GAME"
    echo "Removed the game folder. Goodbye!"
else
    echo "Kept the game folder. Delete it yourself whenever you like."
fi
