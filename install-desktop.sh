#!/bin/sh
# Adds the game to the app menu: ./install-desktop.sh
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
