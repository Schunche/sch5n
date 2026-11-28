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
- Not saved with worlds yet: vitals start full on joining.
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
