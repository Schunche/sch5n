# sch5n

Experimental software

**New to Python? Read [GETTING_STARTED.md](GETTING_STARTED.md)**: download,
double click `play.bat` (Windows) or run `./play.sh` (Linux), and play.

## Run

The launchers `play.bat` and `play.sh` install [uv](https://docs.astral.sh/uv/)
if needed and start the game; arguments are passed on (`./play.sh view --edit --map map1`).

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
    sch5n view --edit --map map1  # edit a map, Esc saves and quits
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

### Controls

Default game controls:

| Input | Action |
| --- | --- |
| A / D | Move |
| Space | Jump (wall jump while sliding on a wall) |
| Left mouse | Use the held item: shovel for dirt, pickaxe for stone (it digs dirt too, slower), axe for trees |
| Right mouse | Place the held block |
| Wheel, 1-0 | Select hotbar slot |
| Tab | Inventory: left click picks up / swaps / merges, right click splits / places one |
| Esc | Close inventory, open settings |
| F3 | Debug info |

The map viewer pans with WASD and zooms with the wheel. With `--edit` it
defaults to left/right mouse to place/erase, wheel to pick a tile,
Ctrl+wheel to zoom and Ctrl+S to save. F1 opens the settings.

### Settings

The settings screen (main menu, Esc in game, F1 in the map tools) has a page
per topic:

- **Video**: windowed or fullscreen, window size, VSync, frame rate limit.
- **Audio**: master, music and effects volume. There is no sound yet; the
  values are stored for later.
- **Interface**: theme, menu background and GUI size. The menu background is
  either the game world (a live world behind the main menu, the paused game
  behind the in-game settings) or the theme's background.
- **Controls**: the bindings of what you are in. The game, the map viewer
  and the map viewer while editing each have their own (the wheel zooms
  when viewing but picks the tile when editing), and each can only be
  changed from inside it. Click a slot,
  then press a key, mouse button or wheel direction, with modifiers if you
  like (Ctrl+S). Esc cancels, Backspace or right click clears. Esc itself
  cannot be rebound.

Click a value for the next option, right click for the previous one.
**Reset Page** restores the defaults of the page you are on.

Every program uses the same settings. They are saved immediately to
`settings.json` in your user config directory (e.g.
`~/.config/sch5n/settings.json` on Linux), which overrides
`assets/base/data/settings.json`.

The mouse cursor is the operating system cursor showing
`textures/icon/cursor.png`, so it never lags. Setting `cursor_color` in
`settings.json` (e.g. `[255, 120, 120]`) hides it and has the game draw the
image tinted with that color instead.

### Themes

Themes live in `assets/base/data/ui.json`: Dusk (default), Forest, Ocean,
Ember and Classic (the original look). A theme sets the GUI colors and the
menu background: an animated, pixelated shader in three colors
(`assets/shader/background.frag`), an image, or a solid color. Add your
own by copying an entry.

## Dependencies

- [Python 3.15](https://www.python.org/)
    - [glfw](https://pypi.org/project/glfw/): window and input
    - [moderngl](https://moderngl.readthedocs.io/): rendering
    - [pygame-ce](https://www.pyga.me): image loading and text rendering
    - [numpy](https://numpy.org/), [pydantic](https://docs.pydantic.dev/)
    - [zeroconf](https://pypi.org/project/zeroconf/): finding games on the
      local network

## Layout

    assets/
        base/
            config/      logging configuration
            data/        game rules, blocks, items, animations, UI style, user settings (JSON)
            maps/        bundled maps
            textures/    images
        shader/          GLSL shaders
    src/sch5n/           source code only
        game/            game rules: player, inventory, mining, items, particles (no GL, no window)
        world/           chunked tilemap, map files, world generator
        net/             protocol, TCP and in-memory connections, LAN discovery, client session
        server/          the authoritative game server and `sch5n server` (no GL, no window)
        client/          glfw window, scenes, HUD
            render/      texture atlas, instanced sprite batch, text
        math/, log/, utility/, ...
    tests/

The game logic runs at a fixed tick rate and never touches the window or
OpenGL, so it can be tested directly. Rendering packs every texture into one
atlas and draws all sprites with instancing; tiles are cached per chunk, so a
frame is a handful of draw calls.

## Tests

    uv run pytest                 # logic tests; rendering tests are skipped without a display
    xvfb-run -a uv run pytest     # everything, headless

The suite runs on every push (`.github/workflows/tests.yml`).

## Sources

- [Tilemap & particles](https://www.youtube.com/watch?v=2gABYM5M0ww)

- [Map generation](https://www.youtube.com/watch?v=Pgt82G4Jxac)

- [Logging](https://www.youtube.com/watch?v=9L77QExPmI0)