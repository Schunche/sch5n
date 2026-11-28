# Autonomous work log

Work done on the `claude/auto` branch, newest last.

## Standing rules for resumes

- Run the full test suite (`xvfb-run -a uv run pytest -q`) only once per
  usage window: at the very start of each resume, which checks everything
  from the previous window. Fix any failures first, then run only the
  relevant tests for the rest of that window. Failures that cannot be fixed
  at once go under "Failing tests" below, committed.
- Last full run: all tests passed (after the climbing animation).

### Failing tests

None.

### Priority list from the user (do first, in this order)

Done: recipe book click fills the grid (shift: all sets), ladders, zoom,
four armor slots, tall grass, grass dying under blocks.
Todo: nothing left from this list.

## Multiplayer chat

- Protocol 5: `ChatSend` (client to server) and `ChatMessage` (server to
  client). The server owns names and kinds, so clients cannot spoof senders
  or fake join messages.
- `sch5n.game.chat`: limits (160 characters, burst of 5 messages then one
  per half second at 60 ticks) and `sanitize`, which drops control and
  invisible characters and collapses whitespace.
- The server announces joins and leaves, replays recent history to new
  players, and tells a flooding player to slow down. `Server.say` lets the
  host or a dedicated server announce things.
- Client: `T` or `Enter` opens the chat (rebindable under Settings →
  Controls), `Enter` sends, `Esc` cancels, `Up`/`Down` recall sent messages,
  `PageUp`/`PageDown` or the wheel scroll back, `Ctrl+V` pastes. Recent
  lines show over the game for ten seconds. Names come from Settings →
  Multiplayer → Display name. Single player works the same way.
- Tests: `tests/test_chat.py`, chat tests in `tests/test_server.py` and
  `tests/test_render.py`.

## Wooden and stone axes and shovels

- New items `wooden_axe`, `wooden_shovel`, `stone_axe`, `stone_shovel` and
  their recipes (axe: two materials on top, then one beside a stick; shovel:
  material over two sticks). They use the existing textures under
  `assets/textures/tool/`, and get weaker and slower than the copper ones.
- Test: `tests/test_crafting.py`.

## Placeholder texture

- `assets/textures/tool/stone_axe.png` is a placeholder: the iron axe
  recolored with the stone pickaxe's grays. Replace it with real art. (The
  commit that added the stone axe forgot it and the game would not start;
  fixed in the next commit.)

## Health, hunger and edible apples

- `sch5n.game.vitals.Vitals`: health and hunger, 20 each. Hunger drops by one
  every 24 s; at 14 or more health regenerates (one per 4 s); at 0 health
  drains (one per 6 s) and a starved player respawns fed, announced in chat.
  Admin mode is immune and shows no bars.
- Items may have `food` (hunger restored) in `data/items.json`. Holding use
  with food in hand eats one per use time when not full. The apple restores 5.
- Protocol 6: `PlayerState` carries `health` and `hunger`. The server runs
  everything; clients only display it (bars at the bottom of the screen).
- Vitals live on the `Inventory`, so they are saved with worlds and kept
  when a player leaves and returns (`health`/`hunger` keys; older saves start
  full; loading never starts a player below 1 health).
- Tests: `tests/test_vitals.py`, a sync test in `tests/test_server.py`.

## Grass

- World generation covers dirt that is open to the sky with grass
  (`generate`). The bundled maps are untouched.
- Grass spreads (`spreads_onto` in `data/blocks.json`, handled by
  `Garden`): every few ticks a random column's topmost solid tile turns to
  grass when it is dirt with open air above and grass next to it. Saplings
  already grew on grass.
- Tests in `tests/test_session.py` and `tests/test_world_io.py`.
- Not done: grass reverting to dirt when covered.

## Chat commands and a text recipe book

- `sch5n.game.commands`: `/help`, `/players`, `/recipes <item>` (lists the
  recipes that make a matching item, shaped ones as grid size and key),
  `/me <action>`. They run on the server, answers go only to the sender,
  `/me` to everyone. Unknown commands get a hint.
- Next ideas: a graphical recipe book, saving vitals with worlds, grass
  reverting when covered, a server-side mute/kick for hosts.

## Host moderation

- `Server.host` names the player who may use `/kick`, `/mute` and
  `/unmute <player>`; a hosted single player game sets it to the host's
  display name. Muted players are told so and cannot speak; kicked players
  see "Kicked by the host". Dedicated servers have no host, so nobody can.

## Recipe book

- `sch5n.client.recipe_book`: a "Recipes" button next to Settings (visible
  while the inventory is open) shows a scrollable list of every recipe:
  result, ingredient icons with amounts, and the smallest grid (`2x2`,
  `3x3`; none for shapeless). Recipes whose ingredients are all in your
  inventory get an accent outline. It sits beside the crafting grid, or
  below the inventory in a narrow window. Client side only; the server still
  decides what crafting does.
- Tests: `tests/test_recipe_book.py`, a render test in `tests/test_render.py`.

## Ores, smelting and metal tools

- Every ore block (copper to platinum) is now breakable with a pickaxe, the
  harder metals take longer, and drops `<metal>_ore`.
- Smelting: a shapeless recipe, one ore and two sticks as fuel, makes an
  ingot (copper and iron only so far; the other ores are collectable for
  later). It needs a furnace in reach (below).
- Copper and iron pickaxe, axe, shovel and lopper recipes from ingots.
- Placeholder art (drawn by script, please replace):
  `assets/textures/item/copper_ingot.png`,
  `assets/textures/item/iron_ingot.png`. Ore items reuse the block textures.
- Tests in `tests/test_crafting.py`.

## Furnace and recipe stations

- Recipes may require a `station` (e.g. `"station": "furnace"` in
  `data/recipes.json`); blocks declare which station they are with
  `"station": "furnace"` in `data/blocks.json`. The server finds the
  stations within reach (`Game._stations_near`), stores them on the
  inventory and sends them in `InventoryState.stations`, so clients show
  the same result the server crafts.
- New furnace block and item: eight cobblestones in a ring on a 3x3 grid.
  Ore smelting now needs one in reach. The recipe book labels station
  recipes with the station's name.
- Placeholder art: `assets/textures/tile/furnace/0.png` (cobblestone with
  a fire opening); replace it with real art.

## Chests

- Block `chest` (`"container": 27` in `data/blocks.json`), crafted from a
  ring of eight oak planks on a 3x3 grid. Right click a chest within reach
  to open it: its slots appear to the right of the inventory; left and
  right clicks work like in the inventory, through the cursor.
- Server authoritative: protocol 7 adds `ChestOpen`, `ChestClick`,
  `ChestClose` and `ChestState`. The server checks reach and the slot
  number, shares one chest between players who have it open, closes it for
  a player who walks away or when it is broken, and drops its contents when
  the block is broken (`Game.chests`, `Game.chest_at`).
- Saved in worlds under `"chests"` (`"x;y"` to an inventory); chests whose
  block is gone are not saved. Guests' "save a copy" does not include chests.
- Placeholder art: `assets/textures/tile/chest/0.png`, drawn by script.
- Tests in `tests/test_server.py`, `tests/test_world_save.py`,
  `tests/test_render.py`.

## Day and night

- `sch5n.game.daylight`: a day lasts 10 minutes (`DAY_SECONDS`) and a new
  game starts in the morning. Time is the server's tick count, which
  snapshots already carry, so everybody sees the same time and no protocol
  change was needed. Loading a world starts a new morning.
- `sch5n.client.render.daynight`: the sky blends to night colors with warm
  dawn and dusk glows and the sun glow travels across the sky; at night a
  dark blue tint covers the world (not the HUD).
- Tests: `tests/test_daylight.py`. Not done: stars/moon art, a `/time`
  command, light sources (torches) that push the dark back.

## Slimes, damage and the death screen

- `sch5n.game.mobs`: hostile creatures (`KINDS`, only `slime` so far).
  Slimes spawn on the ground 14 to 24 tiles from a player at night (up to 3
  per player, 16 in all), walk towards players in sight (14 tiles), hop
  over steps, and fade away in daylight or far from everyone. Touching one
  costs 2 health, with a short pause and a knockback. Admins are immune.
- Players hit them by swinging any tool at their tile; tools' `damage`
  counts (at least 1) with a knockback. Slimes die after a few hits and may
  drop a `slime_ball` (not used in any recipe yet).
- `Game.hurt_player` handles damage; at 0 health (or starvation) a player
  respawns fed and `deaths` goes up. The server announces it in chat.
- Protocol 8: `Snapshot.mobs` and `PlayerState.deaths`. The client shows a
  "You died" screen for three seconds when its death counter rises.
- Placeholder art (drawn by script): `assets/textures/mob/slime.png`
  (drawn at 2x, nearest neighbour) and
  `assets/textures/item/slime_ball.png`.
- Tests: `tests/test_mobs.py`, a render test in `tests/test_render.py`.

## /time and a stability pass

- `/time sunrise|day|noon|sunset|night|midnight` (host only) moves the
  clock (`Game.set_time`, `Game.time_offset`). Snapshots carry `clock`
  (ticks plus the shift) next to `tick`, and the sky and slime spawning
  use it.
- Extra tests for edge cases: a server saved and restored keeps chests,
  health and hunger; wild chest coordinates (huge or negative) are
  harmless.
- Night sky: a fixed scatter of stars and a moon (opposite the sun) fade in
  with the dark (`draw_stars_and_moon`). Cosmetic, no art needed.

## Torches and light

- Block `torch` (`"light": 7` radius in tiles in `data/blocks.json`): placed
  against a solid block, picked up by hand (or an axe). At night a warm glow
  of stacked translucent circles is drawn around every light in view, over
  the dark tint (`draw_lights`); slimes do not spawn within 8 tiles of one.
  Recipes: stick + leaf makes one, stick + slime ball makes four.
- The glow is a client-side effect only (it does not lift the dark tint
  under it); real per-tile lighting would be a bigger rendering change.
- Placeholder art: `assets/textures/tile/torch/0.png`.
- Tests in `tests/test_mobs.py` and `tests/test_crafting.py`.

## Light map

- `client/render/lightmap.py`: lights now cut a smooth hole out of the night.
  `light_field` spreads every torch over a tile grid (strongest light wins, at
  most 400 sources per frame), `night_pixels` colors it (cool dark, warm where
  lit) and `LightMap` draws it as one linearly filtered texture, a pixel per
  tile, over the view. It replaces the old stacked-circle glow
  (`draw_night`/`draw_lights` became `WorldRenderer.draw_night`).
- Tests: `tests/test_lightmap.py`, plus a render test that a torch brightens
  the midnight screen.

## Type check

- Pyright is clean over the whole project: the last 8 errors in tests were narrowed away.

## Performance check

- Server: 16 players in memory on a 1200x600 and a 6000x3000 world take about 2 ms per tick (budget 16.7 ms), 3 ms with the mob cap reached. The cost does not grow with the world size. World generation of 6000x3000 takes about 12 s, once.
- Client: the light map was the one hot spot when zoomed out (400 torches, 12 ms). The glow of each radius is now computed once and stamped, giving 5 ms in that extreme case, 1-3 ms normally.

## Zombies

- A second night creature: the zombie (16x32, 14 health, touch hurts 3,
  sees 18 tiles) drops `cloth`. Kinds now have a spawn `weight`
  (slime 2, zombie 1) and `Game._pick_kind` chooses one.
- Placeholder art to replace: `assets/textures/mob/zombie.png`,
  `assets/textures/item/cloth.png`.

## Armor

- Items can be armor (`armor` body part: head/chest/legs, `defense` points
  in `data/items.json`). Nine pieces: cloth (cap, tunic, pants; from zombie
  cloth), copper and iron (helmet, chestplate, leggings; from ingots), with
  crafting recipes.
- `Inventory.armor` holds the worn pieces, `armor_click` wears/removes with
  the cursor (only into the right slot), `soften` takes 6% of damage per
  defense point (max 80%, min 1 damage). Armor protects against creature
  touches, not hunger. Saved with the inventory, synced in `InventoryState`,
  new `InventoryAction.ARMOR_CLICK` (protocol version 9).
- Client: three armor slots at the right end of the crafting row, with a
  "Defense n" label and tooltips. Armor is not drawn on the player yet.
- Placeholder art to replace: `assets/textures/item/{cloth,copper,iron}_*`
  armor icons (`cloth_cap`, `cloth_tunic`, `cloth_pants`, `*_helmet`,
  `*_chestplate`, `*_leggings`).
- Tests: `tests/test_armor.py`.

## King Slime (boss)

- `king_slime` (96x72, 120 health, touch hurts 4, sees 40 tiles) may come
  at night, 4% per spawn try, never more than one at a time, and fades at
  daybreak like the other creatures. Defeating it drops 10 slime balls and
  announces "The King Slime fell!" in chat.
- Kinds gained `weight` 0 (never part of the crowd), `drop_amount`, `boss`.
  `MobState.health` tells clients how hurt a mob is, so the top of the
  screen shows a boss health bar.
- Placeholder art to replace: `assets/textures/mob/king_slime.png` (the
  slime at 6x with a crown).
- Tests: `tests/test_mobs.py`.

## Tree variety

- Birch (tall and slim, pale bark) and pine (pointed crown, dark leaves)
  join the oak. Blocks `<wood>_log`, `_leaf`, `_log_leaf`, `_sapling` are
  appended to the end of `data/blocks.json` (so older block ids stay), plus
  items `<wood>_log` and `<wood>_sapling`. Leaves drop their own sapling,
  logs craft into oak planks.
- `game/plants.py`: `TREES` maps a wood to its shape; `grow_tree` reads the
  wood from the sapling it grows.
- Placeholder art to replace (recolored from the oak): `tile/birchLog`,
  `tile/birchLeaf`, `tile/pineLog`, `tile/pineLeaf`, `item/birch_sapling.png`,
  `item/pine_sapling.png` under `assets/textures/`.
- Tests: `tests/test_session.py` (each sapling grows its own tree).

## Biomes, trees and ores in generated worlds

- New `world/biomes.py`: stretches of 50-110 columns of plains (grass, oak
  and birch trees), desert (6 rows of sand, no trees) and tundra (snow on
  top, pine trees); the first stretch is always plains, neighbors differ.
- `world/generator.py`: `grow_surface` covers the surface per biome and
  grows trees (`WorldSpec.trees` turns them off) with the same shapes the
  saplings use. `place_ores` finally puts one ore of every pair into the
  stone as small veins: copper/tin shallow, gold/platinum deepest. (Before,
  generated worlds contained no ores at all.)
- Blocks `sand` and `snow` (appended to the end of `data/blocks.json`) and
  items `sand_block`, `snow_block`. Placeholder art to replace:
  `assets/textures/tile/sand/0.png`, `tile/snow/0.png`.
- `data/maps/map1.json` is untouched.
- Tests: `tests/test_biomes.py`, `tests/test_world_io.py`.
- A generated map is used by saving it with `python -m sch5n.world <name> [--seed N]` and starting a new world or server with `--map <name>`.

## Beds

- Block and item `bed` (3 cloth over 3 planks). Right-click a bed in reach
  to set your spawn point (a chat line confirms it); you respawn standing on
  it as long as it stands. Saved with the inventory as `home`.
- Block spec `bed: true`; `Game.sleep_in`; the client reuses the
  right-click path of chests and `ChestOpen` (no new message).
- Placeholder art to replace: `assets/textures/tile/bed/0.png`.

## All metals

- Generated worlds hold one ore of each pair, so every ore now works: tin,
  lead, silver, tungsten, gold and platinum smelt into ingots at a furnace
  (ore plus two sticks) and make a pickaxe, axe, shovel and a three-piece
  armor set (recipes like the copper and iron ones). Power and defense grow
  with the depth of the ore pair: tin 23, lead 42, silver 60, tungsten 72,
  gold 80, platinum 95 (pickaxe power); armor defense up to 11 per set.
- Gold and platinum tools reuse the existing `golden_*` and `diamond_*`
  textures (not mine, untouched). Placeholder art to replace: every
  `assets/textures/item/{tin,lead,silver,tungsten,gold,platinum}_*` and
  `assets/textures/tool/{tin,lead,silver,tungsten}_{pickaxe,axe,shovel}.png`.
- Loppers stay copper and iron only.
- Tests: `tests/test_crafting.py`.

## Shift click

- Shift + left click on an inventory slot: with a chest open the stack goes
  into the chest, armor goes on if its slot is free, anything else swaps
  between the hotbar and the rest. Shift + left click on a chest slot takes
  the stack. (`InventoryAction.QUICK_MOVE`, `ChestClick.quick`,
  `Inventory.quick_move/take_from`.)
- Tests: `tests/test_armor.py`, `tests/test_render.py`.

## Bats

- `bat` (16x12, 4 health, bite 1, fast, sees 20 tiles) flutters through the
  air towards players at night: no gravity, a gentle bob. It spawns 4-8 rows
  above the ground, drops a leaf now and then. Kinds gained `flying`.
- Placeholder art to replace: `assets/textures/mob/bat.png`.
- Tests: `tests/test_mobs.py`.

## Hurt flash

- Taking damage flashes the screen red for 12 ticks (`PlayScene.hurt_ticks`); joining with less than full health does not. Test in `tests/test_render.py`.

## Whispers

- `/msg <player> <text>` (also /w, /whisper, /tell) sends a private line; the receiver sees "name (private)", the sender a "To ..." line. Works with spaces in names, respects mute. Test in `tests/test_server.py`.

## Debug clock

- F3 shows the time of day and day number and the number of creatures.

## Swords

- A sword for every material (wooden, stone, copper, tin, iron, lead,
  silver, tungsten, gold, platinum): tool kind `sword`, damage 4 to 14, so
  creatures (and the King Slime) are fought with something better than a
  pickaxe. Recipes: two blades over a stick (planks, cobblestone/stone block
  or ingots). They use the default swing animation for now (no sword style
  in `data/animations.json`).
- Placeholder art to replace: `assets/textures/tool/<material>_sword.png`.
- Tests: `tests/test_mobs.py`.

## Bow, arrows and skeletons

- New `game/projectiles.py`: arrows fly with gravity (checked every 4
  pixels so thin targets are hit), stop in solid tiles, hit one creature
  (player arrows) or one player (creature arrows), last 300 ticks.
  `aim()` allows for gravity.
- Items `bow` (hold the left mouse button; one arrow per 28 ticks, 5 damage,
  aimed at the cursor tile) and `arrow`; spec fields `ammo`, `shot_damage`,
  `shot_speed` in `data/items.json`. Recipes: stick over cloth makes 4
  arrows; the bow is three stick/cloth rows.
- The skeleton (16x32, 10 health) keeps about 9 tiles from a player (backs
  off when closer), shoots an arrow every ~110 ticks (3 damage, half a
  contact cooldown of protection after a hit) and drops arrows.
- Network: `Snapshot.projectiles` (protocol version 10); clients draw them
  rotated along their flight (`draw_projectiles`).
- Placeholder art to replace: `assets/textures/item/arrow.png`,
  `item/bow.png`, `mob/skeleton.png`.
- Tests: `tests/test_arrows.py`.

## Rain

- `game/weather.py`: `rain_amount(clock, tick_rate)` is a pure function of
  the clock (no state, no network): about a third of days have one shower
  (not the first day), 0.12-0.32 of a day long, building up and dying down.
  `/time` shifts it with the clock.
- `client/render/rain.py` draws a gray veil and falling streaks (slanted by
  the wind); `WorldRenderer.draw_rain` fades it out under a roof (a solid
  tile above the camera).
- Tests: `tests/test_weather.py`, `tests/test_render.py`.

## Tooltips

- Tooltips of swords/tools show "Damage n", armor "Defense n", bows what they shoot. Armor descriptions no longer repeat the defense.

## Fuzz test

- `tests/test_fuzz.py` sends 600 rounds of random, well formed messages (inputs with wild targets, every inventory action with wild slots, chat commands, chest and bed clicks) at a server through the in-memory connection; it must keep running (kicked clients rejoin). Seeds 5 to 8 were run.

## Minimap

- Key M (rebindable: `Action.MINIMAP`) shows a 128x96 tile map around the
  player in the top right, 2 px per tile, colored with the average color of
  each block's texture (`client/render/minimap.py`); creatures are red dots,
  other players green, you yellow. It is one small texture updated per frame
  while shown.
- Tests: `tests/test_minimap.py`, `tests/test_render.py`.

## Generated worlds from the Worlds screen

- A "Terrain" button next to the player name toggles between the start map
  and a generated world (biomes, trees, ores) for new worlds.
- `biome_bands` and `WorldSpec` take a `home` column that is always plains,
  so the spawn at x = 0 never lands in a desert or on snow.
- No new art.

## Fall damage

- `Player` measures a fall from its highest point to the landing
  (`landed_from`, in tiles); `Game` hurts a player for each tile beyond
  `SAFE_FALL` (7). Wall slides and respawns reset the measure; admins are
  immune. Clients only predict movement, so nothing changed on the wire.
- No new art.

## Playtest pass

- Scripted wandering bots on four generated worlds for 20000 ticks each
  found no crashes; deaths were all from creatures at night.
- A shorter version is now a test in `tests/test_biomes.py`.

## Sound effects

- `client/audio.py` synthesizes six placeholder sounds (break, place, hit,
  hurt, chat, craft) from noise and tones at start, so there are no audio
  files. `Audio` plays them through pygame's mixer at master x effects
  volume and does nothing without a sound device or in hidden runs.
- The client world records the block changes of each snapshot
  (`tile_changes`); the play scene plays break, place and hit sounds for
  changes within 24 tiles, a hurt sound on damage and a chat sound on new
  messages. A craft sound plays when the crafting result is taken.
- Music is not implemented; the music slider still has no effect.

## Tips for new players

- `client/hints.py`: one tip at a time at the top of the screen, each once
  per session, for the controls (first 20 s), the first unarmed night and
  after a death. `Settings.show_hints` (default on) turns them off, and
  Settings, Interface has a "Tips" toggle.
- No new art.

## Night balance

- A bot that only walked, never fought, died 11 to 28 times in one day
  with fists. Now: creatures spawn every 130 ticks (was 90), two per
  player (was three), touches pause 70 ticks (was 45), and a respawned
  player is safe for 3 seconds. The same bot dies 5 to 18 times; real
  players who fight, build and light torches do far better.
- The boss test waits longer for its rarer spawn chance.

## Boss helpers

- At half health the King Slime calls two slimes to its sides, once, and
  says so in chat. Helpers are ordinary slimes and may exceed the usual
  creature cap. No new art.

## /home

- `/home` in chat sends the player to their bed or the spawn point
  (`Game.go_home`), with the usual 3 seconds of safety after respawning.

## Re-check

- After sounds, tips, falls and boss changes: the server fuzz test passes,
  and 16 players on a 3000 wide world cost 3.7 ms per tick (budget 16.7).

## Baked apple

- Apple + stick at a furnace makes a Baked Apple (restores 9 hunger, an
  apple 5). Placeholder art: it reuses `item/apple`.

## Sleeping

- Right clicking a bed at night also skips to morning (`MORNING`), unless a
  creature is within 16 tiles; either way the chat says what happened. In
  multiplayer one player's sleep moves the clock for everyone. No new art.

## Shallower stone

- The dirt layer of generated worlds is now 24 rows (`DIRT_ROWS`, half the
  depth in worlds too shallow for that) instead of the upper half, so stone
  starts close to the surface. Ores still lie by their share of the stone
  layer. Fewer dirt strokes in the stone (`DIRT_STROKES`) keep it from
  filling the gap, and the top 4 rows are always dirt so grass grows on
  every column. The first stone is now about 19 rows down on average
  (was about 80). `data/maps/map1.json` is untouched.

## Recipe book fills the grid

- Clicking a recipe in the book lays its ingredients out in the crafting
  grid (the grid is cleared into the inventory first); shift + click fills
  it with as many sets as the inventory holds. New `FILL_RECIPE` and
  `FILL_RECIPE_ALL` inventory actions (protocol 11) and `fill_recipe` in
  `game/crafting.py`. Recipes that do not fit the grid or need a station out
  of reach do nothing.

## Ladders

- Block and item `ladder`: 7 sticks in an H on the 3x3 grid make 3. It is
  walk-through (`climbable` block field); inside it, holding jump climbs
  (`climb_speed`), otherwise the player sinks at most `ladder_slide_speed`.
  It stops falls, hangs from walls and from other ladders, and an empty
  hand picks it up. Placeholder art: `assets/textures/tile/ladder/0.png`.
- Climbing has an animation: `Action.CLIMB`, clip `mob/player/climb` (two
  frames, the wall slide pose and its mirror, so the arms swap), also for
  the `armless` and `bare` variants, with shoulders in `rig.json`.
  Placeholder art to replace: `mob/player/{climb,armless/climb,bare/climb}`.

## Zoom

- In play, `+` / `-` (also the keypad) or Ctrl + wheel step the camera through
  0.5x, 1x, 2x and 3x (`ZOOM_LEVELS`), whole numbers or halves so pixel art
  stays sharp. They are the `ZOOM_IN` / `ZOOM_OUT` actions of the game
  context and can be rebound.

## Boots

- A fourth armor slot, `feet` (slots: head, chest, legs, feet), with boots
  for all nine sets (`*_boots`, same defense as the leggings, a 2x2 ring of
  the material: `M M / M M`). Older saves load with an empty feet slot.
  Placeholder art to replace: `assets/textures/item/*_boots.png` (the lower
  part of each leggings icon). The tips are hidden while the inventory is
  open.

## Tall grass and dying grass

- Breaking a grass block drops Tall Grass 30% of the time (extra drop). Tall
  Grass is a walk-through plant (`tall_grass` block and item) that can be
  planted on dirt or grass; an empty hand or a lopper picks it up. Generated
  worlds carry it on a quarter of the grass in grass biomes (`GRASS_CHANCE`;
  off with `trees=False`). Placeholder art: `tile/tall_grass/0.png`.
- A solid block placed on grass starts a 20 to 40 second timer
  (`SMOTHER_SECONDS`, `Garden.smothering`); when it runs out and the block is
  still there, the grass becomes dirt. The older random check for buried
  grass still runs too.

## Furnace with its own interface

- The furnace is now a 3 slot container (Ore, Fuel, Result), opened with a
  right click like a chest, not a recipe in the crafting grid. `Game` ticks
  every opened furnace (`game/smelting.py`): fuel (`fuel` seconds on items:
  stick 8, plank 12, log 30) is lit only when there is something to smelt
  and room for the result; an item takes `seconds` (6 by default) while it
  burns. The fire (burning ticks, progress) is not saved; contents are.
- Smelting data moved to `smelting` in `recipes.json` (`SmeltSpec`, in
  `Content.smelting` by input item); the nine station recipes (8 ores and the
  baked apple) left the grid recipes. Protocol 12 (the content fingerprint
  includes smelting). `Inventory` may now have fewer than 10 slots.
- The recipe book lists what a furnace makes after the other recipes
  (labelled Furnace); clicking those does nothing. Shift click sends ore to
  the input slot and fuel to the fuel slot of an open furnace.

## Ore tiers

- `min_power` on blocks: the least power of the block's own tool type that
  can break it. Iron and lead need 20 (a stone pickaxe), silver and tungsten
  40 (iron or lead pickaxe), gold 55 (silver or tungsten), platinum 70 (gold).
  Copper and tin need none. Ore item tooltips say which pickaxe to bring.
  A too weak tool does nothing to the block (like a wrong tool).

## /give

- The host can type `/give <item name> [amount]` (up to 1024) to put items
  in their inventory, for testing and building. Others are told it is for
  the host only.

## Pickup sound

- A short `pickup` blip plays when the item total in the inventory grows
  (not while the inventory is open, so moving stacks stays quiet).

## Day announcements

- Chat says "Day N begins" at every sunrise (also after sleeping through
  the night). The game starts on day 1.

## Desktop shortcuts
- `install-desktop.sh --desktop` copies the app-menu entry to the Desktop; new `install-desktop.bat` makes Windows Start menu/Desktop shortcuts. Paths are resolved at install time. Players only (play.sh installs the menu entry; dev setup doesn't).
- Shortcuts are now opt-in: play.sh/play.bat ask once (remembered in the user config dir), never when non-interactive or run with arguments.

## Empty start and hand-breaking leaves
- Procedural ("Terrain: Generated") is now the default on the Worlds screen; new generated worlds give the player an empty inventory. The start map keeps the iron tools.
- Leaves break by hand (`hand_power`); any held item that isn't a tool (stick, leaf, blocks) punches too. Path: leaves → sticks → planks → bench → wooden tools (test_hand_leaves).

## Chat commands and text editing
- Shared `client/textedit.py` (`TextEdit`): caret, arrows, Home/End, Shift selection, Ctrl word jump/delete, Ctrl+A/C/X/V. Used by chat and every `TextField` (world name, player name, server address, setting values). Chat keeps Up/Down history.
- Chat: Tab completes commands, `/time` subcommands, player names and item names; a hint line above the box lists candidates or the usage.
- `/time set <moment|ticks>`, `/time add <ticks>`, `/time speed <n>` (0 stops the clock), `/time query`; `/time <moment>` still works. A day is 24000 ticks for `/time`.

## Time of day is saved
- World files keep the `clock` (ticks plus any `/time` shift), so loading a world resumes at the same moment of the day. The dedicated server also restores chests and the clock now.

## Help and weather
- `/help <command>` shows one usage; unknown commands suggest the closest one. `/weather` says whether it rains and about when the next shower is.
- `/tp <player>` (host only) takes the host to another player; command dispatch in the server is a table now and honours aliases (`/w`, `/tell`).

## Glass
- New `glass` block/item, smelted from sand in a furnace. Placeholder art (generated, translucent blue): `assets/textures/tile/glass/0.png`. Replace freely.
- `/clear` (host only) empties the host's inventory.
