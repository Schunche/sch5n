#!/bin/sh
# Adds the game to the app menu: ./install-desktop.sh
# "./install-desktop.sh --desktop" also puts a shortcut on your Desktop.
# Linux desktops, Wayland ones especially, take a window's taskbar icon
# from this entry. Run it again after moving the game folder.
set -eu

GAME=$(cd "$(dirname "$0")" && pwd)
SHARE="${XDG_DATA_HOME:-${HOME:?}/.local/share}"
APPS="$SHARE/applications"
ICONS="$SHARE/icons/hicolor/512x512/apps"

mkdir -p "$APPS" "$ICONS"
cp "$GAME/assets/textures/icon/main.png" "$ICONS/sch5n.png"
# Lets desktops notice the new icon.
touch "$SHARE/icons/hicolor"

# The name of the file and StartupWMClass match the window's app id.
cat > "$APPS/sch5n.desktop" <<ENTRY
[Desktop Entry]
Type=Application
Name=sch5n
Exec="$GAME/play.sh"
Icon=sch5n
Terminal=false
Categories=Game;
StartupWMClass=sch5n
ENTRY

if [ "${1:-}" = "--desktop" ]; then
    DESK=$(xdg-user-dir DESKTOP 2>/dev/null || echo "${HOME:?}/Desktop")
    if [ -d "$DESK" ]; then
        cp "$APPS/sch5n.desktop" "$DESK/sch5n.desktop"
        chmod +x "$DESK/sch5n.desktop"
        # GNOME asks once before trusting a shortcut; this is best effort.
        gio set "$DESK/sch5n.desktop" metadata::trusted true 2>/dev/null || true
        echo "Added a shortcut to $DESK"
    else
        echo "No Desktop folder found."
    fi
fi
