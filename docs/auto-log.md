# Autonomous work log

Work done on the `claude/auto` branch, newest last.

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
