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
