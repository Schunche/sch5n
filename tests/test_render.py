# Copyright (c) 2026 Schunche
"""Rendering through a real (hidden) window. Skipped without a display."""

from __future__ import annotations

import json
import math
import time
from typing import TYPE_CHECKING

import glfw
import moderngl
import numpy as np
import pytest

from sch5n.client.app import App, Options
from sch5n.client.keybinds import Action, Binding, Context, Mod
from sch5n.client.render.batch import Transform
from sch5n.client.scenes.map_tools import EditorScene, ViewerScene
from sch5n.client.scenes.menu import MainMenu
from sch5n.client.scenes.multiplayer import MultiplayerScene
from sch5n.client.scenes.play import PlayScene
from sch5n.client.scenes.settings import (
    BindRow,
    Option,
    OptionRow,
    Page,
    SettingsScene,
)
from sch5n.client.scenes.worlds import WorldsScene
from sch5n.client.window import (
    CharEvent,
    KeyEvent,
    MouseButtonEvent,
    ScrollEvent,
    WindowError,
)
from sch5n.client.world_view import load_start_map
from sch5n.game.config import Settings
from sch5n.net.client import ClientSession
from sch5n.server.server import Server
from sch5n.world.save import list_worlds, load_world

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sch5n.client.scenes.base import Scene
    from sch5n.client.scenes.settings import Row
    from sch5n.client.ui import Button

RED = (255, 0, 0)
MIN_BACKGROUND_STD = 10
"""A drawn background image is far from a flat color."""
MIN_SKY_SHARE = 0.3
"""At least this much of the game screen is open sky."""
MAX_GAME_DRAW_CALLS = 8
WARMUP_TICKS = 30
JOIN_TIMEOUT = 10.0
"""Seconds a join over the network may take."""


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[App]:
    """Open a hidden window with its own settings file.

    Yields:
        App: The application.

    """
    user = tmp_path_factory.mktemp("user")
    try:
        application = App(
            Options(
                hidden=True,
                seed=0,
                settings_file=user / "settings.json",
                worlds_dir=user / "worlds",
            )
        )
    except (WindowError, moderngl.Error, glfw.GLFWError) as e:
        # No display, or no OpenGL 3.3 (e.g. a server, or Linux without
        # xvfb-run): rendering cannot be tested here.
        pytest.skip(f"No OpenGL 3.3 window available: {e}")
    yield application
    application.release()


def read_pixels(app: App) -> np.ndarray:
    """Read back the screen.

    Returns:
        np.ndarray: RGB pixels, top row first.

    """
    # The viewport, not the window: the OS may resize the window (e.g. to
    # fit a small screen) before the app has handled that event.
    _, _, w, h = app.ctx.viewport
    data = app.ctx.screen.read(viewport=(0, 0, w, h), components=3)
    return np.frombuffer(data, np.uint8).reshape(h, w, 3)[::-1]


def draw(app: App, scene: Scene) -> np.ndarray:
    """Render one frame of a scene.

    Returns:
        np.ndarray: The rendered pixels.

    """
    app.batch.draw_calls = 0
    scene.render()
    app.batch.flush()
    return read_pixels(app)


def press(key: int, mods: int = 0) -> KeyEvent:
    """Create a key press event.

    Returns:
        KeyEvent: The event.

    """
    return KeyEvent(key, glfw.PRESS, mods)


def click(
    pos: tuple[float, float], *, right: bool = False
) -> MouseButtonEvent:
    """Create a mouse click event.

    Returns:
        MouseButtonEvent: The event.

    """
    button = glfw.MOUSE_BUTTON_RIGHT if right else glfw.MOUSE_BUTTON_LEFT
    return MouseButtonEvent(button, glfw.PRESS, 0, pos)


def show_row(settings: SettingsScene, row: Row) -> int:
    """Scroll the settings so that `row` is visible.

    Returns:
        int: The row's index.

    """
    index = settings.row_index(row)
    settings.scroll = settings.table.clamp_scroll(
        index * settings.table.row_height - settings.table.area.h / 2
    )
    assert settings.table.is_visible(index, settings.scroll)
    return index


def test_shapes_and_sprites(app: App) -> None:
    """Shapes and sprites land on the expected pixels."""
    app.clear((0, 0, 0))
    app.batch.begin(app.screen)
    app.batch.shape((10, 10, 20, 20), (1.0, 0.0, 0.0, 1.0))
    app.batch.sprite(
        app.assets.atlas, (40, 10, 32, 32), app.assets.blocks[1][0]
    )
    app.batch.flush()
    pixels = read_pixels(app)
    assert tuple(pixels[20, 20]) == RED
    assert pixels[20, 56].any()
    assert not pixels[100, 100].any()


def test_scenes_render(app: App) -> None:
    """The menu and the game draw, the game in a few draw calls."""
    menu_pixels = draw(app, MainMenu(app))
    assert menu_pixels.std() > MIN_BACKGROUND_STD

    play = PlayScene.singleplayer(app)
    for _ in range(WARMUP_TICKS):
        play.tick()
    pixels = draw(app, play)
    sky = tuple(app.content.game.sky_color)
    sky_share = (pixels.reshape(-1, 3) == sky).all(axis=1).mean()
    assert sky_share > MIN_SKY_SHARE
    # The whole world is a handful of batched draw calls.
    assert app.batch.draw_calls <= MAX_GAME_DRAW_CALLS


def test_text_cache_reuses_textures(app: App) -> None:
    """Drawing the same text again reuses its texture."""
    app.batch.begin(app.screen)
    app.text.draw(app.batch, "hello", (0, 0))
    cached = app.text.cached_count
    app.text.draw(app.batch, "hello", (0, 20))
    assert app.text.cached_count == cached
    app.batch.flush()


def test_play_scene_input(app: App) -> None:
    """Hotbar and inventory react to input in the game."""
    play = PlayScene.singleplayer(app)
    inventory = play.world.inventory
    assert play.server is not None
    server_inventory = play.server.game.players[play.world.local_id].inventory

    # Changes go to the server and come back with the next tick.
    play.on_event(ScrollEvent(0, -1))
    play.tick()
    assert inventory.selected == server_inventory.selected == 1
    play.on_event(press(glfw.KEY_3))
    play.tick()
    assert inventory.selected == Action.HOTBAR_3.hotbar_slot

    play.on_event(press(glfw.KEY_TAB))
    assert play.inventory_open
    play.on_event(click(play.inventory_layout.slot_rect(0).center))
    play.tick()
    assert inventory.cursor is not None
    assert inventory[0] is None

    # Closing the inventory puts the held stack back.
    play.on_event(press(glfw.KEY_TAB))
    play.tick()
    assert not play.inventory_open
    assert inventory.cursor is None
    assert inventory[0] is not None
    play.leave()


def test_rebind_in_settings_and_play(app: App) -> None:
    """Rebinding in the settings changes the game's controls and is saved."""
    play = PlayScene.singleplayer(app)
    settings = SettingsScene(app, back=play, in_game=True, page=Page.CONTROLS)
    jump = BindRow(Context.GAME, Action.JUMP)
    index = show_row(settings, jump)
    cell = settings.table.cell_rect(index, 0, settings.scroll).center
    binds = app.keybinds[Context.GAME]

    # Escape cancels without changing anything.
    settings.on_event(click(cell))
    assert settings.capturing == jump
    settings.on_event(press(glfw.KEY_ESCAPE))
    assert settings.capturing is None
    assert binds.slots(Action.JUMP)[0] == Binding.key(glfw.KEY_SPACE)

    # Rebind jump to K.
    settings.on_event(click(cell))
    settings.on_event(press(glfw.KEY_K))
    assert binds.action_for(Binding.key(glfw.KEY_K)) is Action.JUMP
    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert saved["keybinds"]["game"]["jump"] == ["key:K"]
    assert draw(app, settings).any()

    # The game uses the new binding right away.
    play.on_event(press(glfw.KEY_SPACE))
    assert not play.jump_requested
    play.on_event(press(glfw.KEY_K))
    assert play.jump_requested

    # Right click clears a slot.
    settings.on_event(click(cell, right=True))
    assert binds.slots(Action.JUMP)[0] is None

    # Reset restores the defaults.
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(click(reset.rect.center))
    assert binds.action_for(Binding.key(glfw.KEY_SPACE)) is Action.JUMP


def test_capture_modifier_combinations(
    app: App, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Modifier combinations, lone modifiers and the wheel can be bound."""
    editor = EditorScene(app, tmp_path_factory.mktemp("maps") / "m.json")
    settings = SettingsScene(app, back=editor, page=Page.CONTROLS)
    binds = app.keybinds[Context.EDITOR]
    reset = BindRow(Context.EDITOR, Action.RESET_CAMERA)
    index = show_row(settings, reset)

    def capture(slot: int) -> None:
        """Start capturing a binding for a slot of the row."""
        cell = settings.table.cell_rect(index, slot, settings.scroll).center
        settings.on_event(click(cell))

    # Ctrl, then Shift+R: modifiers held during the press become part of it.
    capture(0)
    settings.on_event(press(glfw.KEY_LEFT_CONTROL, glfw.MOD_CONTROL))
    assert settings.capturing == reset
    settings.on_event(press(glfw.KEY_R, glfw.MOD_CONTROL | glfw.MOD_SHIFT))
    assert binds.slots(Action.RESET_CAMERA)[0] == Binding.key(
        glfw.KEY_R, Mod.CTRL | Mod.SHIFT
    )

    # A modifier pressed and released alone binds the modifier key.
    capture(1)
    settings.on_event(press(glfw.KEY_LEFT_ALT, glfw.MOD_ALT))
    settings.on_event(KeyEvent(glfw.KEY_LEFT_ALT, glfw.RELEASE, 0))
    assert binds.slots(Action.RESET_CAMERA)[1] == Binding.key(
        glfw.KEY_LEFT_ALT
    )

    # Wheel directions can be bound too.
    capture(1)
    settings.on_event(ScrollEvent(0, 1, glfw.MOD_SHIFT))
    assert binds.slots(Action.RESET_CAMERA)[1] == Binding.wheel(1, Mod.SHIFT)
    app.keybinds.reset()
    app.update_settings()


def test_video_options_apply_and_save(app: App) -> None:
    """Video options change the window and are saved."""
    settings = SettingsScene(app, back=MainMenu(app))

    def click_option(option: Option, *, right: bool = False) -> None:
        """Click the value of a video option."""
        index = show_row(settings, OptionRow(option))
        span = settings.table.span_rect(index, settings.scroll)
        settings.on_event(click(span.center, right=right))

    before = (app.settings.window_width, app.settings.window_height)
    # Step down, to a size that fits even small (CI) screens.
    click_option(Option.WINDOW_SIZE, right=True)
    after = (app.settings.window_width, app.settings.window_height)
    assert after < before
    app.window.poll()
    assert tuple(app.window.size) == after

    vsync = app.settings.vsync
    click_option(Option.VSYNC)
    assert app.settings.vsync is not vsync

    click_option(Option.FPS_LIMIT)
    limit = app.settings.fps_limit
    click_option(Option.FPS_LIMIT, right=True)
    click_option(Option.FPS_LIMIT)
    assert app.settings.fps_limit == limit

    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert (saved["window_width"], saved["window_height"]) == after
    assert saved["vsync"] is not vsync
    assert saved["fps_limit"] == limit

    click_option(Option.WINDOW_SIZE)
    app.window.poll()
    assert (app.settings.window_width, app.settings.window_height) == before


def test_editor_uses_its_own_binds(
    app: App, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The map editor and viewer use their own controls."""
    target = tmp_path_factory.mktemp("maps") / "new.json"
    editor = EditorScene(app, target)
    editor.on_event(ScrollEvent(0, 1))
    assert editor.selected == 1
    zoom = editor.camera.zoom
    editor.on_event(ScrollEvent(0, 1, glfw.MOD_CONTROL))
    assert editor.camera.zoom > zoom
    assert editor.selected == 1
    editor.on_event(press(glfw.KEY_S, glfw.MOD_CONTROL))
    assert target.exists()

    viewer = ViewerScene(app, target)
    viewer.on_event(ScrollEvent(0, 1))
    assert viewer.camera.zoom > 1

    viewer.on_event(press(glfw.KEY_F1))
    assert isinstance(app.pending_scene, SettingsScene)


def click_value(
    settings: SettingsScene, option: Option, fraction: float = 0.5
) -> None:
    """Click an option's value, `fraction` of the way along it."""
    index = show_row(settings, OptionRow(option))
    span = settings.table.span_rect(index, settings.scroll)
    settings.on_event(click((span.x + span.w * fraction, span.center[1])))


def test_sidebar_switches_pages(app: App) -> None:
    """Each sidebar button shows its own page."""
    settings = SettingsScene(app, back=MainMenu(app))
    for page, button in zip(Page, list(settings.sidebar), strict=True):
        settings.on_event(click(button.rect.center))
        assert settings.page is page
        if page is Page.CONTROLS:
            assert all(isinstance(row, BindRow) for row in settings.rows)
        else:
            assert all(isinstance(row, OptionRow) for row in settings.rows)
        assert draw(app, settings).any()


def test_theme_switch_applies_and_saves(app: App) -> None:
    """Changing the theme recolors the GUI at once and is saved."""
    settings = SettingsScene(app, back=MainMenu(app), page=Page.INTERFACE)
    before = app.ui.theme_name
    accent = app.ui.color("accent")
    click_value(settings, Option.THEME)
    assert app.ui.theme_name != before
    assert app.ui.color("accent") != accent
    saved = json.loads(app.settings_file.read_text(encoding="utf-8"))
    assert saved["theme"] == app.ui.theme_name
    click_value(settings, Option.THEME, fraction=0.5)
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(click(reset.rect.center))
    assert app.ui.theme_name == Settings().theme


def test_volume_sliders(app: App) -> None:
    """A click on a slider sets the volume; reset restores defaults."""
    settings = SettingsScene(app, back=MainMenu(app), page=Page.AUDIO)
    index = show_row(settings, OptionRow(Option.MUSIC_VOLUME))
    track = settings.slider_rect(index)
    settings.on_event(click((track.x + track.w * 0.25, track.center[1])))
    quarter = 25
    assert app.settings.music_volume == quarter
    settings.on_event(click((track.right + 1000, track.center[1])))
    assert app.settings.music_volume == quarter
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(click(reset.rect.center))
    assert app.settings.music_volume == Settings().music_volume


def test_background_shader_animates(app: App) -> None:
    """The menu background moves over time and is not a flat color."""
    background = app.ui.config.themes["dusk"].background
    app.background.draw(background, 0.0)
    first = read_pixels(app)
    app.background.draw(background, 120.0)
    later = read_pixels(app)
    assert first.std() > MIN_BACKGROUND_STD
    assert (first != later).any()


def test_gui_size_applies_when_returning_to_game(app: App) -> None:
    """The game picks up a new GUI size when the settings close."""
    play = PlayScene.singleplayer(app)
    settings = SettingsScene(app, back=play, in_game=True, page=Page.INTERFACE)
    click_value(settings, Option.GUI_SIZE)
    settings.on_event(press(glfw.KEY_ESCAPE))
    assert app.pending_scene is play
    play.on_enter()
    assert play.inventory_layout.slot_size == pytest.approx(
        app.settings.gui_size * 1.5
    )
    app.update_settings(gui_size=Settings().gui_size)


def test_main_menu_runs_the_world(app: App) -> None:
    """The main menu shows a live world that keeps running."""
    menu = MainMenu(app)
    start = menu.world.camera.center
    for _ in range(WARMUP_TICKS):
        menu.tick()
    assert menu.world.game.ticks == WARMUP_TICKS
    assert menu.world.camera.center != start
    assert draw(app, menu).std() > MIN_BACKGROUND_STD

    # It keeps running behind the settings.
    settings = SettingsScene(app, back=menu)
    settings.tick()
    assert menu.world.game.ticks == WARMUP_TICKS + 1


def test_menu_background_setting(app: App) -> None:
    """Menus show the world behind them, or the theme if chosen."""
    menu = MainMenu(app)
    settings = SettingsScene(app, back=menu, page=Page.INTERFACE)
    with_world = draw(app, settings)
    click_value(settings, Option.MENU_BACKGROUND)
    assert app.settings.menu_background is not Settings().menu_background
    with_theme = draw(app, settings)
    assert (with_world != with_theme).any()
    click_value(settings, Option.MENU_BACKGROUND)
    assert app.settings.menu_background is Settings().menu_background


def cursor_pixels(app: App) -> np.ndarray:
    """Draw only the game's own cursor, at a known place.

    Returns:
        np.ndarray: The pixels around the cursor.

    """
    app.clear((0, 0, 0))
    app.batch.begin(app.screen)
    app.draw_cursor((40, 40))
    app.batch.flush()
    return read_pixels(app)[40:72, 40:72]


def test_uncolored_cursor_is_the_system_cursor(app: App) -> None:
    """Without a color the OS draws the cursor; with one the game does."""
    assert app.settings.cursor_color is None
    assert app.window.cursor.visible
    assert not cursor_pixels(app).any()

    app.update_settings(cursor_color=(255, 0, 0))
    assert not app.window.cursor.visible
    drawn = cursor_pixels(app)
    assert drawn.any()
    assert not drawn[..., 1:].any()  # Tinted red: no green or blue left.

    app.update_settings(cursor_color=None)
    assert app.window.cursor.visible


def test_each_program_edits_only_its_own_controls(
    app: App, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The game, the editor and the viewer each reach only their bindings."""
    target = tmp_path_factory.mktemp("maps") / "m.json"
    origins = {
        Context.GAME: [MainMenu(app), PlayScene.singleplayer(app)],
        Context.EDITOR: [EditorScene(app, target)],
        Context.VIEWER: [ViewerScene(app, target)],
    }
    for context, scenes in origins.items():
        for scene in scenes:
            settings = SettingsScene(app, back=scene, page=Page.CONTROLS)
            contexts = {row.context for row in settings.rows}
            assert contexts == {context}, type(scene).__name__


def test_reset_controls_keeps_other_programs(
    app: App, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Resetting the controls page leaves other programs' bindings alone."""
    viewer = ViewerScene(app, tmp_path_factory.mktemp("maps") / "m.json")
    app.keybinds[Context.GAME].bind(Action.JUMP, 0, Binding.key(glfw.KEY_K))
    app.keybinds[Context.VIEWER].bind(
        Action.RESET_CAMERA, 0, Binding.key(glfw.KEY_K)
    )
    settings = SettingsScene(app, back=viewer, page=Page.CONTROLS)
    reset = next(b for b in settings.buttons if b.id == "reset")
    settings.on_event(click(reset.rect.center))
    assert (
        app.keybinds[Context.VIEWER].action_for(Binding.key(glfw.KEY_R))
        is Action.RESET_CAMERA
    )
    assert (
        app.keybinds[Context.GAME].action_for(Binding.key(glfw.KEY_K))
        is Action.JUMP
    )
    app.keybinds.reset()
    app.update_settings()


def test_rotated_sprite(app: App) -> None:
    """A wide sprite rotated by 90 degrees around its center stands up."""
    app.clear((0, 0, 0))
    app.batch.begin(app.screen)
    app.batch.sprite(
        app.assets.atlas,
        (100, 145, 100, 10),
        app.assets.blocks[1][0],  # An opaque tile texture.
        transform=Transform(rotation=math.pi / 2),
    )
    app.batch.flush()
    pixels = read_pixels(app).any(axis=2)
    ys, xs = pixels.nonzero()
    width, height = 100, 10
    slack = 5
    assert xs.max() - xs.min() < height + slack  # Narrow,
    assert ys.max() - ys.min() > width - 2 * slack  # and tall.


def joined(app: App, host: PlayScene) -> bool:
    """Whether a game other than the host's is about to start.

    Returns:
        bool: True once the guest's game is the next scene.

    """
    scene = app.pending_scene
    return (
        isinstance(scene, PlayScene)
        and scene is not host
        and scene.server is None
    )


def test_open_to_lan_and_join(app: App) -> None:
    """A single player game opens to the network; another client joins."""
    host = PlayScene.singleplayer(app)
    assert host.server is not None
    settings = SettingsScene(app, back=host, in_game=True)
    lan = next(b for b in settings.buttons if b.id == "lan")
    settings.on_event(click(lan.rect.center))
    port = host.server.port
    assert port is not None
    assert str(port) in settings.message
    assert all(b.id != "lan" for b in settings.buttons)

    # Join through the multiplayer screen, typing the address.
    joining = MultiplayerScene(app, back=MainMenu(app))
    joining.on_enter()
    joining.address.text = ""
    for char in f"127.0.0.1:{port}":
        joining.on_event(CharEvent(char))
    joining.on_event(press(glfw.KEY_ENTER))
    assert joining.joining
    deadline = time.monotonic() + JOIN_TIMEOUT
    while not joined(app, host):
        assert time.monotonic() < deadline, joining.message
        host.tick()
        joining.tick()
        time.sleep(0.002)
    guest = app.pending_scene
    assert isinstance(guest, PlayScene)
    joining.on_exit()

    deadline = time.monotonic() + JOIN_TIMEOUT
    while len(host.world.players) < len(("host", "guest")):
        assert time.monotonic() < deadline
        host.tick()
        guest.tick()
        time.sleep(0.002)
    assert draw(app, guest).any()

    # The guest goes back to the main menu, told why, when the host quits.
    host.leave()
    deadline = time.monotonic() + JOIN_TIMEOUT
    while not isinstance(menu := app.pending_scene, MainMenu) or not (
        menu.notice
    ):
        assert time.monotonic() < deadline
        guest.tick()
        time.sleep(0.002)
    assert menu.notice == "The host left the game"
    assert draw(app, menu).any()
    app.switch(menu)


def test_resizing_keeps_the_view_and_the_layout(app: App) -> None:
    """A resized window keeps the view and lays out every screen again.

    Like maximizing: the player stays in the middle, and screens hidden
    behind a menu are laid out again when they return.
    """
    play = PlayScene.singleplayer(app)
    for _ in range(WARMUP_TICKS):
        play.tick()
    settings = SettingsScene(app, back=play, in_game=True)
    center = play.camera.center
    original = app.screen
    try:
        # The window is maximized while the settings are open.
        app.screen = (original[0] + 320, original[1] + 180)
        settings.update_layout()
        footer = settings.buttons
        middle = (footer[0].rect.x + footer[-1].rect.right) / 2
        assert middle == pytest.approx(app.screen[0] / 2)

        # Back in the game: same view center, HUD in the new corner.
        play.update_layout()
        assert play.camera.view(app.screen).center == pytest.approx(center)
        pad = app.ui.outer_padding
        assert play.buttons[0].rect.right == app.screen[0] - pad
        assert play.buttons[0].rect.bottom == app.screen[1] - pad
        play.tick()
        moved = math.dist(play.camera.center, center)
        assert moved < 1
    finally:
        app.screen = original
        play.update_layout()
        play.leave()


def footer_button(settings: SettingsScene, button_id: str) -> Button:
    """Find a button in the settings footer.

    Returns:
        Button: The button.

    """
    return next(b for b in settings.buttons if b.id == button_id)


def test_worlds_are_saved_unless_asked_not_to(app: App) -> None:
    """Save & Quit keeps changes; Quit Without Saving throws them away."""
    stone = app.content.blocks.id_of("stone")
    worlds = WorldsScene(app, back=MainMenu(app))
    worlds.name.text = ""
    for char in "Test world":
        worlds.on_event(CharEvent(char))
    worlds.on_event(press(glfw.KEY_ENTER))
    play = app.pending_scene
    assert isinstance(play, PlayScene)
    assert play.server is not None

    # Build something, then save and quit from the in-game settings.
    play.server.game.tilemap.set(0, -40, stone)
    settings = SettingsScene(app, back=play, in_game=True)
    settings.on_event(click(footer_button(settings, "menu").rect.center))
    assert isinstance(app.pending_scene, MainMenu)

    # The world is listed, and has the block.
    worlds = WorldsScene(app, back=MainMenu(app))
    assert [w.name for w in worlds.worlds][:1] == ["Test world"]
    worlds.on_event(click(worlds.world_buttons[0].rect.center))
    again = app.pending_scene
    assert isinstance(again, PlayScene)
    assert again.server is not None
    assert again.server.game.tilemap.get(0, -40) == stone

    # This time, quit without saving: the change is gone next time.
    again.server.game.tilemap.set(1, -40, stone)
    settings = SettingsScene(app, back=again, in_game=True)
    settings.on_event(click(footer_button(settings, "discard").rect.center))
    world = load_world(worlds.worlds[0].path, app.content)
    assert world.tilemap.get(0, -40) == stone
    assert world.tilemap.get(1, -40) != stone

    # A name in use is refused.
    worlds = WorldsScene(app, back=MainMenu(app))
    worlds.name.text = "Test world"
    worlds.create()
    assert "already exists" in worlds.message


def test_guests_save_a_copy(app: App) -> None:
    """Players in someone else's game can keep the world on their computer."""
    host = Server(app.content, load_start_map(app), name="Host's world")
    guest_session = ClientSession(
        host.connect_local(), app.content, "Guest", app.options.game_mode
    )
    host.step()
    guest_session.poll()
    guest = PlayScene(app, guest_session)
    settings = SettingsScene(app, back=guest, in_game=True)
    ids = [b.id for b in settings.buttons]
    assert "copy" in ids
    assert "discard" not in ids
    settings.on_event(click(footer_button(settings, "copy").rect.center))
    assert "Host's world" in settings.message

    saved = next(w for w in list_worlds(app.worlds_dir) if "Host" in w.name)
    world = load_world(saved.path, app.content)
    assert len(world.tilemap) == len(host.game.tilemap)
    # Kept under the name the player plays single player games with.
    assert app.settings.player_name in world.inventories
    guest.leave()
    host.close()


def test_hovered_items_show_a_tooltip(app: App) -> None:
    """In the open inventory, hovering an item describes it."""
    play = PlayScene.singleplayer(app)
    play.inventory_open = True
    slot = play.inventory_layout.slot_rect(0).center
    empty = play.inventory_layout.slot_rect(20).center
    assert play.hovered_stack(slot) is not None
    assert play.hovered_stack(empty) is None
    play.inventory_open = False
    assert play.hovered_stack(slot) is None
    play.leave()
