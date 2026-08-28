# The Final PokéBattle

> A fully online MMO RPG: drop straight into the adventure map, explore, and clash in a final showdown — built with Python and Pygame, reading creature data from a GBA ROM.

**Version 0.2 — PROTOTYPE**

⚠️ **Work in progress.** The current build is an offline prototype focused on the new adventure rules (3-minute adventure, final-area trigger, playing AI opponent, character unlocks). The online server is a later milestone. Expect rough edges and placeholder content.

---

## Overview

The Final PokéBattle is a **fully online MMO RPG**. There is no preparation phase — players drop directly into the adventure map and spawn into the game world. The server holds the data needed during a match; when the adventure ends, the match data is deleted and only the **final result (the winner)** is kept.

The game is **not** a ROM hack — it uses the ROM purely as a data source for creature stats, moves, types and sprites. All game logic, rendering, maps and overworld behavior are original.

The full design lives in [`idea.txt`](idea.txt). This README describes the **offline prototype** that is currently being built toward that vision: it mirrors the online rules as a single-player practice mode, and the online server is a later milestone.

### What exists today (offline prototype)

- Character select + starter pick, map exploration, wild encounters, and a final showdown.
- **HM Cut** and **HM Surf** — Surf rides across water with real ROM overworld surf sprites and a smooth mount/dismount animation (mount visible under the player).
- **Blue is the fixed rival** of the forest map: he is not selectable at the start, and defeating him unlocks him as a playable character.
- Night mode with darkened palettes and all sprites/tiles taken only from the user's ROM.

### Not yet implemented (planned, see idea.txt)

- Human-like AI opponent that moves differently every match.
- The 3-minute adventure timer and the central-area final-battle trigger.
- Dynamic NPC dialogue driven by the opponent's actions, and more character unlocks.
- The online server (chat, clue loading, keeping only the winner).

---

## The Concept

- **No lobby / no pre-game setup** — a match *is* an entire adventure played out inside the map.
- **Adventure + final battle** — players explore, battle wild creatures, collect items and interact with the world; the showdown is a PvP battle between players.
- **Adventure limit** — the adventure lasts at most **3 minutes**.
- **Final battle trigger** — the showdown starts when a player reaches the final area, or when the 3-minute limit expires. Players arrive with the state and resources they accumulated.
- **Battle uses live state** — combat uses the game state exactly as it is at the moment battle starts.
- **Server is authoritative** — handles chat and clue loading between players; after the match it keeps only the winner.

---

## Online Mode (later milestone)

- Played directly in the world; spawned into the map, no prep.
- Server manages match data, chat and clue loading.
- On match end, match data is scrapped; only the winner is conserved.

---

## Offline Mode (current focus)

A single-player practice mode mirroring the online rules:

- **Static clue signs** — signs hold fixed clues on the map (e.g. where a rare creature is).
- **Dynamic NPC dialogue** — NPCs change their dialogues/suggestions based on world state.
- **Final trigger** — reach the **central area** and stand on a specific spot to start the final challenge.

---

## Current Features (offline prototype)

- 🎮 **Character select** — Red and Leaf playable at the start (starter + rival pairing). Blue is the fixed forest rival, not selectable until defeated.
- 🗺️ **Multi-map overworld** — Forest (south/north), River, Cave, House, Arena — with portals/edge-connections and collision from `maps.json`
- 🌙 **Night mode** — palettes darkened + blue moonlight tint and indigo overlay; applied to metatiles and object sprites at generation time and as a viewport overlay at render time
- 🌿 **Wild encounters** — tall-grass (`g`) trigger zones with per-map encounter rate; fishing (`w`/`B`) with Old Rod
- ⚔️ **Turn-based battle** — Gen III damage formula, type effectiveness, STAB, accuracy, PP, capture/flee
- 🪓 **HM Cut — authentic sprite** — small tree is the real object-event cut tree taken only from the user's ROM; `C` renders as grass + sprite overlay and is replaced by path when cut
- 🌊 **HM Surf + mount** — teach Surf to a water-type and ride; surf sprites are taken only from the user's ROM (water mount visible under the player) with mount/dismount frames
- 🌲 **Forest rendering** — huge-tree 3×3 metatiles (`0x298-0x2A2`) from the ROM, segment-aligned for cleaner edges
- 🏆 **Rival showdown** — the fixed rival (Blue) waits in the arena; defeating his whole team wins the match and unlocks him as playable
- 🎒 **Inventory & Party** — items, key items (Old Rod), HMs, healing, switching, faint handling

---

## Requirements

- Python 3.10+
- Pygame 2.x
- A legally obtained GBA ROM file (user provides their own, not included)

```bash
pip install pygame
```

---

## Quick Start

```bash
# 1. Place your ROM file in the project root (any .gba file)
# 2. Run the game
python src/frontend.py
```

---

## Repository Structure

```
the_final_pokebattle/
├── src/
│   ├── frontend.py          # Pygame rendering, input, camera, HUD, night overlay
│   ├── game.py              # Core game logic (movement, battle, state, inventory)
│   ├── rom_reader.py        # ROM data extraction (stats, moves, types, tilemaps)
│   ├── sprite_extractor.py  # Creature / OW sprite extraction from ROM (decompression)
│   ├── map_renderer.py      # ROM metatile rendering (forest, water, night palettes)
│   └── asset_generator.py   # Glues sprites + maps together, palette handling
├── data/
│   ├── maps.json            # Map layouts, portals, NPCs, walkable tiles, clue zones
│   ├── characters.json      # Playable characters and rival config
│   └── sprites.json         # Packed tile / UI sprites (decompressed at runtime)
├── assets/                  # Generated at runtime (git-ignored), pre-rendered maps
├── .sprite_cache/           # Generated at runtime (git-ignored), creature sprites
├── .gitignore
├── README.md
├── CONTRIBUTING.md
└── idea.txt                 # Original game design notes
```

> **Not committed**: `assets/`, `.sprite_cache/`, `screenshots/`  
> **User-provided** (not committed): ROM file (`.gba`) — all game data and sprites are taken only from this file

---

## Game Flow (current offline prototype)

1. **Character Select** → choose Red or Leaf (Blue is not selectable until unlocked)
2. **Starter Pick** → each character's starter options
3. **Explore** → wild encounters in the forest; find HM Cut and HM Surf
4. **Use HMs** → cut blocking trees, teach Surf and ride across the river
5. **Final Battle** → reach the Rival in the forest to trigger the showdown
6. **Victory** → defeat the rival's whole team to win — and defeat Blue to unlock him as playable for the next run

> Note: the 3-minute adventure timer and the central-area trigger are the next planned step (see idea.txt) and are not wired up yet.

---

## Technical Notes

- Map backgrounds are pre-rendered PNGs scaled 3× at load; overlay system paints cut-tree patches and item pickups on top
- Night mode darkens palettes and adds an indigo viewport overlay
- Battle damage uses the Gen III formula: `((2*Level/5+2) * Power * A/D) / 50 + 2) * STAB * TypeEff`
- Encounter rate is configurable per-tile in `maps.json`
- Smooth walking uses frame-interpolated offsets (12 frames per tile)
- Surf uses mount/dismount frames; forest uses 3×3 huge-tree metatiles segment-aligned for cleaner edges
- Nothing proprietary is stored in the repository — all data comes only from the user's ROM

---

## License

This project is released for educational and portfolio purposes.  
All original code and map designs are created by the authors.  
No proprietary data or assets are included in the repository.
