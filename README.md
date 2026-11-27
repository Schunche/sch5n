# sch5n

Experimental software

## Run

### Python 3.15

Install [uv](https://docs.astral.sh/uv/), then:

    uv sync --python 3.15
    uv run sch5n

`uv build` builds the wheel and source distribution.

## Usage

    sch5n                       # play (same as `sch5n client`)
    sch5n client --map procedural --seed 1
    sch5n client --game-mode admin   # unlimited jumps; survival is the default
    sch5n view procedural       # fly over a map
    sch5n edit map1             # edit a map, Esc saves and quits
    sch5n generate mymap --seed 42 --width 300 --height 160

Prefix with `uv run` when the virtual environment is not activated.

### Controls

Default game controls:

| Input | Action |
| --- | --- |
| A / D | Move |
| Space | Jump (wall jump while sliding on a wall) |
| Left mouse | Use the held item: mine with pickaxe or axe |
| Right mouse | Place the held block |
| Wheel, 1-0 | Select hotbar slot |
| Tab | Inventory: left click picks up / swaps / merges, right click splits / places one |
| Esc | Close inventory, open settings |
| F3 | Debug info |

The map editor defaults to WASD to pan, left/right mouse to place/erase,
wheel to pick a tile, Ctrl+wheel to zoom and Ctrl+S to save. The map viewer
pans with WASD and zooms with the wheel. F1 opens the settings in both.

### Settings

The settings screen (main menu, Esc in game, F1 in the map tools) has a page
per topic:

- **Video**: windowed or fullscreen, window size, VSync, frame rate limit.
- **Audio**: master, music and effects volume. There is no sound yet; the
  values are stored for later.
- **Interface**: theme, menu background and GUI size. The menu background is
  either the game world (a live world behind the main menu, the paused game
  behind the in-game settings) or the theme's background.
- **Controls**: the bindings of the program you are in. The game, the map
  editor and the map viewer each have their own, and each can only be
  changed from inside that program. Click a slot,
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

## Development

### For fast development - No documentation checking

    ruff check . --fix --ignore PLR0915 --ignore PLR0912 --ignore C901 --ignore D417 --ignore D103 --ignore D107 --ignore D101 --ignore D102 --ignore DOC201 --ignore D105 --ignore PLR0911 --ignore DOC501 --ignore PLR0913 --ignore PLR0917 --ignore PLR1702

## Sources

- [Tilemap & particles](https://www.youtube.com/watch?v=2gABYM5M0ww)

- [Map generation](https://www.youtube.com/watch?v=Pgt82G4Jxac)

- [Logging](https://www.youtube.com/watch?v=9L77QExPmI0)