# Getting started

This guide is for playing the game without knowing anything about Python or
programming. You don't need to install Python yourself: the game's
launcher sets up everything it needs on its own.

## What you need

- **Windows 10 or 11**, or **Linux**. macOS is not supported yet.
- **A graphics card or chip that supports OpenGL 3.3.** Almost every computer
  from the last ten years does. Keep its drivers up to date.
- **An internet connection the first time** you start the game. It downloads
  about 400 MB once (its own copy of Python and the libraries the game uses).
  After that it works offline.

## 1. Download the game

1. Open the game's page on GitHub.
2. Click the green **Code** button, then **Download ZIP**.
3. Find the ZIP in your Downloads folder and extract it:
   - **Windows:** right click it, choose **Extract All...**, then **Extract**.
   - **Linux:** right click it and choose **Extract Here**, or run
     `unzip` on it.

You now have a folder with the game in it. You can move it anywhere you like,
for example to your Documents.

## 2. Start the game

### Windows

1. Open the game folder.
2. Double click **`play.bat`**.
   - Windows may warn you, because the file came from the internet. If it
     says *"Windows protected your PC"*, click **More info**, then
     **Run anyway**. If it shows *"Open File - Security Warning"*, click
     **Run**.
   - If you can't see the `.bat` ending, look for the `play` file whose type
     is *Windows Batch File*.
3. A black window opens and shows what is being downloaded. The first start
   takes a few minutes; later starts take a few seconds.
4. The game window opens. Leave the black window open while you play: it
   closes by itself when the game does.

### Linux

1. Open a terminal in the game folder. In most file managers you can right
   click inside the folder and choose **Open in Terminal**.
2. Type this and press Enter:

   ```sh
   ./play.sh
   ```

3. The first start downloads what the game needs and takes a few minutes;
   later starts take a few seconds.

## 3. Play

In the main menu, click **Singleplayer**. Type a name for a new world and
click **Create**, or click one of your saved worlds to continue it.

| Input | Action |
| --- | --- |
| A / D or the arrow keys | Walk |
| Space | Jump. Hold it to jump higher. Jump while sliding down a wall to jump off it |
| Left mouse button | Use the item in your hand: dig dirt with the shovel, mine stone with the pickaxe, chop trees with the axe |
| Right mouse button | Place the block in your hand |
| Mouse wheel, 1 to 0 | Choose a hotbar slot |
| Tab | Open the inventory. Point at an item to see what it does. Left click picks up or swaps items, right click takes half or puts one down |
| Esc | Close the inventory, open the settings |
| F3 | Show technical information |

### Saving

Press **Esc** and click **Save & Quit** to save your world and go back to
the main menu, or **Quit Without Saving** to throw away what you did since
the last save. Closing the game window saves too.

Worlds are kept in your user folder, so they stay when you update the game:

- **Windows:** `C:\Users\<you>\AppData\Local\Schunche\sch5n\worlds`
- **Linux:** `~/.local/share/sch5n/worlds`

### Settings

Open **Settings** from the main menu, or press **Esc** in the game. Pick a
page on the left:

- **Video:** window size, fullscreen, VSync and the frame rate limit.
- **Audio:** volume. There is no sound yet; your choice is kept for later.
- **Interface:** colour theme, what the menus show behind them, and the size
  of the inventory.
- **Controls:** click a key on the right, then press the key or mouse button
  you want instead. Esc cancels, right click clears.

Settings are saved as soon as you change them, in your user folder, so they
stay when you update the game:

- **Windows:** `C:\Users\<you>\AppData\Local\Schunche\sch5n\settings.json`
- **Linux:** `~/.config/sch5n/settings.json`

Delete that file to go back to the default settings.

## Playing together

Everyone needs the same version of the game.

### On the same network (home, LAN party)

1. One player starts a **Singleplayer** game, presses **Esc** and clicks
   **Open to LAN**. The game shows an address like `192.168.1.20:47315`.
2. The others click **Multiplayer** in the main menu and type their name.
   The game appears under *Games on your network*; click it. If it doesn't show up, type the
   address into **Server address** and click **Join**.

When the player who opened the game quits, the game ends for everyone.
The world is theirs: it is saved on their computer. Anyone else can keep a
copy: press **Esc** and click **Save World Copy**. The copy appears under
**Singleplayer**, with your inventory, to play on your own or open to LAN.

Windows may ask whether Python may use the network the first time. Allow it
on **private networks**, or others can't join.

### A server that keeps running

A **dedicated server** runs the game without a window, so it can keep going
on a spare computer while players come and go. In a command window in the
game folder (see [The map tools](#the-map-tools) for how to open one):

```bat
play.bat server
```

On Linux: `./play.sh server`. It shows the port players need. Close it with
**Ctrl+C**; it saves the world and continues it the next time it starts.
Players join through **Multiplayer**, like above.

To play with friends over the internet instead, the server's router must
forward TCP port 47315 to the server computer, and the others join with the
router's public address. How to forward a port depends on the router; look
up its manual.

## The map tools

The game comes with two tools for its maps. Start them with a word after the
launcher's name.

- **Map viewer:** look at a whole map. WASD to move, mouse wheel to zoom.
- **Map editor:** change a map. WASD to move, left click places, right click
  erases, the mouse wheel picks the block, Ctrl+S saves, Esc saves and quits.

On **Windows**, open the game folder, click the address bar at the top of the
window, type `cmd` and press Enter. A black window opens in the game folder.
Then type one of these and press Enter:

```bat
play.bat view map1
play.bat edit map1
play.bat view procedural
```

On **Linux**, in the terminal:

```sh
./play.sh view map1
./play.sh edit map1
```

Maps are in `assets/base/maps`. Editing a map name that doesn't exist yet,
like `play.bat edit mymap`, starts a new, empty map. To play on it, start
the game with `play.bat client --map mymap` and create a new world under
**Singleplayer**: new worlds start from that map.

## Updating

Download the new ZIP and extract it, just like the first time. You can delete
the old folder. Your settings and worlds are kept, as they live in your user
folder.
Maps you made are inside the old folder's `assets/base/maps`: copy them over
first.

## Removing the game

1. Delete the game folder.
2. Optionally, delete your settings and worlds (see [Settings](#settings)
   and [Saving](#saving) for where).
3. Optionally, remove what the launcher downloaded. On Windows, delete the
   `uv` folders in `C:\Users\<you>\AppData\Local` and
   `C:\Users\<you>\AppData\Roaming`, and `uv.exe` in
   `C:\Users\<you>\.local\bin`. On Linux, delete `~/.local/share/uv`,
   `~/.cache/uv` and `~/.local/bin/uv`.

## Problems

**The game window doesn't open, and the black window mentions OpenGL or
"Could not create a window".**
Your graphics drivers are probably out of date. Install the latest driver
from your graphics card maker (NVIDIA, AMD or Intel) and try again. Remote
desktop sessions and some virtual machines don't offer OpenGL 3.3 at all.

**The black window closes immediately.**
Start it from a command window so the message stays visible: open `cmd` in
the game folder as described in [The map tools](#the-map-tools) and type
`play.bat`.

**"uv is not recognized" or "uv: command not found".**
The launcher installed uv, but your computer hasn't noticed yet. Log out and
back in (or restart), then start the game again.

**The first start fails while downloading.**
Check your internet connection and start the game again. Whatever finished
downloading is kept, so the second try is shorter. Some antivirus programs
or company networks block the download; try another network.

**Linux: "Permission denied" when running `./play.sh`.**
Make it runnable with `chmod +x play.sh`, then try again.

**Others can't find or join my game.**
Check that you are on the same network, and that Windows allowed Python on
private networks (search the Start menu for *Allow an app through Windows
Firewall*, find Python, tick **Private**). Some networks, like guest or
school Wi-Fi, keep devices apart; nothing can be done about those.

**Linux: errors about `libGL` or `GLX`.**
Install your distribution's Mesa OpenGL packages, for example
`sudo apt install libgl1-mesa-dri libglx-mesa0` on Ubuntu or Debian.

**Something else.**
The game writes a log to `dev/user/logs/sch5n.log.jsonl` in the game folder.
When you report a problem, include that file and what you were doing.

## What is all this?

The game is written in **Python**, a programming language. Running a Python
program normally means installing Python and the libraries the program uses,
in the right versions. The launchers use a tool called **uv** to do that for
you: it downloads a private copy of Python and the libraries into its own
folder, without touching anything else on your computer, and then starts the
game.
