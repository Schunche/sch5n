# sch5n

Experimental software

**New to Python? Read [GETTING_STARTED.md](GETTING_STARTED.md)**: download,
double click `play.bat` (Windows) or run `./play.sh` (Linux), and play.

## Run

The launchers `play.bat` and `play.sh` install [uv](https://docs.astral.sh/uv/)
if needed and start the game; arguments are passed on (`./play.sh view --edit --map mymap`).
`uninstall.bat` and `uninstall.sh` remove the user's settings, logs and,
when confirmed, worlds, uv and the game folder; `--yes` confirms all but
removing uv.

On Linux the taskbar icon comes from a desktop entry. `play.sh` installs it;
if you start the game another way, run `./install-desktop.sh` once, and again
after moving the game folder.

### Python 3.15

For development, install [uv](https://docs.astral.sh/uv/), then:

    uv sync --python 3.15
    uv run sch5n

`uv build` builds the wheel and source distribution.

## Usage

    sch5n                       # play (same as `sch5n client`)
    sch5n client --map procedural --seed 1
    sch5n client --game-mode admin   # unlimited jumps; survival is the default
    sch5n client --connect 192.168.1.20  # join a server right away
    sch5n server                # dedicated server, no window (see below)
    sch5n view --map procedural # fly over a map (default: map1)
    sch5n view --edit --map mymap  # edit a map
    sch5n generate mymap --seed 42 --width 300 --height 160

Prefix with `uv run` when the virtual environment is not activated.

### Multiplayer

One server runs the game; any number of clients play in it. The server owns
the world, the players, their inventories, mining and dropped items. Every
tick each client sends its input and the server sends back what moved.
Leaves, clouds and wind streaks are drawn by each client, blown by the
server's wind.

Clients predict their own player, so lag doesn't make walking, jumping or
swinging feel slow. Each input moves the player right away with the same
code the server runs, and is numbered. The server applies each player's
inputs one per tick, in order, and every snapshot says which input it has
reached. The client then puts its player where the server has it and
replays the inputs still on their way. Normally that lands exactly where
the player already was; when it doesn't, like when another player built a
wall in the way, the server's version wins. Breaking blocks, items and
other players still arrive with the lag. F3 shows how many inputs are on
their way and how often a prediction was corrected.

- **Singleplayer** lists your saved worlds and creates new ones (from the
  `--map` map, or `map1`), then runs a server inside the game, connected
  in memory.
- **Open to LAN** (Esc in a singleplayer game) makes that server accept
  players from the network and announce itself there (mDNS / zeroconf). The
  address to join is shown in the game and on the F3 screen. A singleplayer
  game pauses while the settings are open; once open to the network it
  keeps running.
- **Multiplayer** in the main menu lists the games found on your network
  and joins one, or the address you type (`host` or `host:port`; Ctrl+V
  pastes).
- **`sch5n server`** runs a dedicated server without a window, OpenGL or
  pygame, for example on a headless machine:

      sch5n server --port 47315 --map map1 --name "My server"
      sch5n server --no-lan   # do not announce it on the local network

  Ctrl+C stops and saves it. The world is saved under the server's name
  and continued on the next start; `--map` only seeds a new one, and
  `--worlds-dir` saves elsewhere. Port 47315 is the default; players on
  other networks need it forwarded on the server's router.

#### Saving

Worlds are saved with their blocks and every player's inventory (players
get theirs back by name), in your user data directory:
`~/.local/share/sch5n/worlds` on Linux,
`C:\Users\<you>\AppData\Local\Schunche\sch5n\worlds` on Windows. The
host's in-game settings have **Save & Quit** and **Quit Without Saving**;
closing the window saves too. Guests get **Save World Copy**, which saves
the world as they see it (their copy is complete and up to date) as a new
world of their own, with their inventory.

Players who leave and come back with the same name get their inventory
back while the server runs. Clients must run the same game version and
data; others are turned away with a reason. Messages are length prefixed
JSON over TCP, validated on arrival; a client that sends something invalid
or too large is disconnected, the server goes on.

### Survival

Health and hunger are shown at the bottom (the saved world keeps them). Eat
food (apples) by holding the left mouse button with it in hand. At night
slimes, zombies, bats and arrow-shooting skeletons come out, and rarely the King Slime (swords hit hardest; a bow shoots arrows at the cursor while you hold the left mouse button); torches keep
them away and light the dark. Defeated creatures drop slime balls (torches),
cloth (armor, beds) and more. Smelt ore at a furnace (stand next to it) and craft
tools and armor of copper, iron and the other metals; wear armor in the three
slots next to the crafting grid. A bed (right click it) sets where you respawn, and at night skips to morning if no creature is within 16 tiles.
Worlds made by `python -m sch5n.world` have plains, desert and snow biomes,
trees, and one ore of every pair; use one with `--map <name>`, or pick
"Terrain: Generated" on the Worlds screen to start a fresh one. Falls of more
than 7 tiles hurt (one health per extra tile; admins are immune). Rain falls
on about a third of the days and stops under a roof. Short tips appear for
new players (turn them off in Settings, Interface). Sound
effects are generated placeholders that follow the master and effects
volume; music is not implemented.

### Controls

Default game controls:

| Input | Action |
| --- | --- |
| A / D | Move |
| Space | Jump (wall jump while sliding on a wall) |
| Left mouse | Use the held item: shovel for dirt, pickaxe for stone (it digs dirt too, slower), axe for trees (a broken log fells the tree above it), lopper for leaves (the axe cuts them too, slower). Blocks are within reach up to `player.reach` (5) tiles away |
| Right mouse | Place the held block; on a chest, open it; on a bed, set your spawn point. Food in hand: hold the left mouse button to eat |
| T / Enter | Chat (Enter sends, Esc cancels, Up/Down recall your messages, PageUp/PageDown scroll). `/help` lists the commands; `/home` takes you to your bed or spawn |
| Wheel, 1-0 | Select hotbar slot |
| + / - (or Ctrl + wheel) | Zoom the world in or out: 0.5x, 1x, 2x or 3x |
| M | Show or hide the minimap (the world around you, creatures in red, other players in green) |
| Tab | Inventory: left click picks up / swaps / merges, right click splits / places one, shift + click moves a stack (into a chest, onto the body, or between hotbar and the rest). Armor goes in the three slots right of the crafting grid. The Recipes button lists every recipe |
| Esc | Close inventory, open settings |
| F3 | Debug info |

The map viewer pans with WASD and zooms with the wheel. With `--edit`,
left/right mouse place/erase and Ctrl+S saves; a message says whether it
worked. Click a block in the palette on the right to pick it (the wheel
scrolls the palette while the mouse is over it), or step through the blocks
with Q/E. Viewing and editing share one set of controls. F1 opens the
settings. Esc quits; with unsaved changes it, like closing the window, first
asks to **Save & Quit**, **Quit Without Saving** or **Keep Editing**.

#### The default map (developers only)

`data/maps/map1.json` seeds new worlds and servers and is the main menu
background, so it is protected. `--edit` refuses it. Only while developing
(a git checkout, or `SCH5N_DEV=1`; see below) can it be changed:

    ./play.sh view --edit-default

Everywhere else `--edit-default` and `--overwrite-default` don't exist and
the map is never written.

Each save that changes it first copies the previous version to
`data/maps/backups/` (ignored by git). To restore one, copy it back over
`data/maps/map1.json`. `sch5n generate map1` likewise needs
`--overwrite-default`.

### Settings

The settings screen (main menu, Esc in game, F1 in the map tools) has a page
per topic:

- **Video**: windowed or fullscreen, window size, VSync, frame rate limit.
- **Audio**: master, music and effects volume, on sliders you click or
  drag. There is no sound yet; the values are stored for later.
- **Interface**: theme, menu background, GUI size, font and cursor. The
  menu background is either the game world (a live world behind the main
  menu, the paused game behind the in-game settings) or the theme's
  background. Fonts are listed under `fonts` in `data/ui.json`: VT323
  (default), Jersey 10 and Pixelify Sans, pixel fonts shipped with the
  game; Arial, from the computer (Liberation Sans or Arimo stand in where
  Arial is not installed, as their letters have Arial's sizes); and Classic,
  pygame's built in font. Add one by putting it, with its license, in
  `assets/fonts` and listing it there.
  The cursor is the game's or the system's normal pointer.
- **Multiplayer**: your display name; the port (47315 by default) that
  **Open to LAN** listens on and that addresses without a port join;
  whether your hosted game is listed on the network; and the most players,
  you included, it admits. Click the name or port, type, then press Enter.
  Changes count from the next game you host or join. `sch5n server` takes
  its port from `--port` instead.
- **Controls**: the bindings of what you are in. The game and the map
  viewer (also when editing) each have their own, and each can only be
  changed from inside it. Click a slot,
  then press a key, mouse button or wheel direction, with modifiers if you
  like (Ctrl+S). Esc cancels, Backspace or right click clears. Esc itself
  cannot be rebound.

Click a value for the next option, right click for the previous one.
**Reset Page** restores the defaults of the page you are on.

Every program uses the same settings. They are saved immediately to
`settings.json` in your user config directory (e.g.
`~/.config/sch5n/settings.json` on Linux), which overrides
`data/settings.json`.

The game cursor is the operating system cursor showing
`assets/textures/icon/cursor.png`, so it never lags. Setting `cursor_color` in
`settings.json` (e.g. `[255, 120, 120]`) hides it and has the game draw the
image tinted with that color instead. The System cursor is always the
operating system's normal pointer.

### Themes

Themes live in `data/ui.json`: Dusk (default), Forest, Ocean,
Ember and Classic (the original look). A theme sets the GUI colors and the
menu background: an animated, pixelated shader in three colors
(`assets/shaders/background.frag`), an image, or a solid color. Add your
own by copying an entry.

## Dependencies

- [Python 3.15](https://www.python.org/)
    - [glfw](https://pypi.org/project/glfw/): window and input
    - [moderngl](https://moderngl.readthedocs.io/): rendering
    - [pygame-ce](https://www.pyga.me): image loading and text rendering
    - [numpy](https://numpy.org/), [pydantic](https://docs.pydantic.dev/)
    - [zeroconf](https://pypi.org/project/zeroconf/): finding games on the
      local network
- Fonts, each under the SIL Open Font License 1.1, whose license file in
  `assets/fonts` must ship with it:
  [VT323](https://fonts.google.com/specimen/VT323) by Peter Hull,
  [Jersey 10](https://fonts.google.com/specimen/Jersey+10) by Sarah Cadigan-Fried
  and [Pixelify Sans](https://fonts.google.com/specimen/Pixelify+Sans) by
  Stefie Justprince. Pixel fonts are drawn at their native size, where one
  font pixel is one screen pixel, and enlarged by whole factors with hard
  edges, so they stay crisp. Arial is not shipped (its license forbids it);
  the game uses the one installed on the computer.

## Layout

    assets/              what draws the game
        textures/        images
        shaders/         GLSL shaders
        fonts/           pixel fonts and their licenses
    data/                what defines the game: rules, blocks, items, animations, UI style, default settings (JSON)
        maps/            bundled maps, and the ones made with the editor
    dev/                 ignored by git: everything the game writes while developing
        user/            settings, logging config, logs and worlds
        tmp/             temporary files of the tests
    src/sch5n/           source code only
        game/            game rules: player, inventory, mining, items, particles (no GL, no window)
        world/           chunked tilemap, map files, world generator
        net/             protocol, TCP and in-memory connections, LAN discovery, client session
        server/          the authoritative game server and `sch5n server` (no GL, no window)
        client/          glfw window, scenes, HUD
            render/      texture atlas, instanced sprite batch, text
        math/, log/, utility/, ...
    tests/

The sky behind the world is a shader too (`assets/shaders/sky.frag`): a
smooth gradient from a bright horizon to a deep blue zenith with a soft
sun glow, moving with slight parallax, that turns dark navy deep
underground. Its colors, sun and sizes are under `sky` in `game.json`.

The game logic runs at a fixed tick rate and never touches the window or
OpenGL, so it can be tested directly. Rendering packs every texture into one
atlas and draws all sprites with instancing; tiles are cached per chunk, so a
frame is a handful of draw calls.

### Where the game writes

Players' settings, worlds, logging configuration (`logging.json`, written
with the defaults on first start) and logs go to their user directories,
so they survive updates. While developing, nothing is written outside the
game folder: all of it goes to `dev/user/` instead, and the tests keep
their temporary files in `dev/tmp/`. A git checkout counts as developing;
`SCH5N_DEV=1` or `SCH5N_DEV=0` decides explicitly.

Each start logs to `latest.log.jsonl` in the logs directory. The previous
one is renamed after when it was written (`2026-11-27_16-26-17.log.jsonl`)
and only the ten newest of those are kept. If another program of the game
is still writing `latest.log.jsonl`, the new one adds to it instead.

## Tests

    uv run pytest                 # logic tests; rendering tests are skipped without a display
    xvfb-run -a uv run pytest     # everything, headless

The suite runs on every push (`.github/workflows/tests.yml`).

## Sources

- [Tilemap & particles](https://www.youtube.com/watch?v=2gABYM5M0ww)

- [Map generation](https://www.youtube.com/watch?v=Pgt82G4Jxac)

- [Logging](https://www.youtube.com/watch?v=9L77QExPmI0)