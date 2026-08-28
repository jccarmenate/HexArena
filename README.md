# HexArena

🇬🇧 English (you are here) · 🇪🇸 [Leer en español](README.es.md)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-informational.svg)

Desktop Hex game for Windows, packaged as a single portable `.exe`
(no installer). Play against the AI with difficulty levels, local
player-vs-player, and networked player-vs-player (LAN / direct IP).

<p align="center">
  <img src="docs/preview.svg" alt="HexArena board" width="640">
</p>

## Features

- **Custom AI**: MCTS search with RAVE, distance bias (Dijkstra), and
  bridge recognition — not a third-party library.
- **3 difficulty levels**: from "makes human-like mistakes" to "plays with
  every heuristic active", by tuning time budget and heuristic
  aggressiveness in a single parameterized engine.
- **3 game modes**: against the AI, local player-vs-player (hotseat), and
  networked player-vs-player (one player hosts, the other connects by IP).
- **A single portable `.exe`**: no installer, no external dependencies,
  runs from any folder or USB drive.
- **Centralized rules engine**: a single source of truth for
  adjacency/connection/legality, shared by the AI, local mode, and
  networking — no duplicated logic that can drift out of sync.

## Origin

Grew out of a university AI project (a Hex-playing agent via MCTS) that
only existed as a Python class with no board or interface. HexArena
picks it up from scratch as a complete application: a custom rules
engine, a merged and improved AI, three game modes, a polished
interface, and real packaging for Windows.

## Running in development

```bash
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Building the portable .exe

```bash
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pyinstaller hex_app.spec
```

The result lands in `dist/HexArena.exe`: a single file, no installer,
that runs from any folder or USB drive. The first time Windows runs it,
it may show a SmartScreen warning (the executable isn't signed); choose
"More info" → "Run anyway".

## Tests

```bash
.venv\Scripts\python tests\test_engine.py      # rules + AI: legality, connectivity, bridges
.venv\Scripts\python tests\test_network.py     # host/client over TCP on localhost
.venv\Scripts\python tests\test_difficulty.py  # Hard must beat Easy (slow, ~10s)
```

## Structure

```
main.py             entry point: creates the pywebview window
engine/board.py      HexBoard: rules, adjacency, connectivity, bridges
engine/ai.py         HexAI: MCTS + RAVE, Dijkstra bias, difficulty levels
engine/network.py    TCP host/client for network mode
engine/api.py        bridge between pywebview and the UI (window.pywebview.api.*)
ui/                  index.html + style.css + app.js
tests/                rules, AI, and network tests
scripts/make_preview.py  generates docs/preview.svg (the image above)
```

## Network mode — scope

One player hosts the game (listens on their local network) and shares
their IP and port; the other connects directly. It's LAN / direct IP,
with no matchmaking or NAT traversal — to play over the internet, the
host would need to set up port-forwarding on their router themselves.

## License

[MIT](LICENSE)
