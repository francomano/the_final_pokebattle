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
- **HM Cut** and **HM Surf** — Surf rides across water with real ROM overworld surf sprites and a smooth mount/dismount animation.
- **Blue is the fixed rival** of the forest map: he is not selectable at the start, and defeating him unlocks him as a playable character.
- All sprites are extracted from the ROM at runtime (nothing pre-baked in the repo).

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

- **Human-like AI** — the AI opponent moves differently every match.
- **3-minute limit** is kept, like online.
- **Replayability** — the same map type can be played many times, but every match plays out differently.
- **Character unlocks** — new characters (playable character + starter) are unlocked by defeating them. Blue is removed from the playable roster and is always the rival in the forest map; defeating him unlocks him as playable.
- **Static clue signs** — signs hold fixed clues on the map (e.g. where a rare creature is).
- **Dynamic NPC dialogue** — NPCs change their dialogues/suggestions based on what the opponent is doing.
- **Final trigger** — reach the **central area** and stand on a specific spot to start the final challenge; otherwise it triggers when the 3 minutes expire.

---

## Current Features (offline prototype)

- 🎮 **Character select** — Red and Leaf playable at the start (starter + rival pairing). Blue is the fixed forest rival, not selectable until defeated.
- 🗺️ **Multi-map overworld** — Forest, River, Cave, Arena
- 🌿 **Wild encounters** — trigger zones in tall grass
- ⚔️ **Turn-based battle** — type effectiveness, STAB, accuracy, PP
- 🪓 **HM Cut** — teach it and clear blocking trees
- 🌊 **HM Surf** — teach it to a water-type, ride across water with real ROM overworld surf sprites and a smooth mount/dismount animation (player glides on/off the Pokémon)
- 🏆 **Rival showdown** — the fixed rival (Blue) waits in the forest; defeating his whole team wins the match and unlocks him as playable
- 🎒 **Inventory & Party** — items, healing, switching
- 🖼️ **Runtime sprite extraction** — all assets generated from the ROM at runtime (nothing pre-baked in the repo)

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
# 2. Run the game — assets are generated automatically on first launch
python src/frontend.py
```

On first launch the game extracts all sprites (creatures, players, surf, NPCs, tiles) from the ROM into the `assets/` folder and `.sprite_cache/`.

---

## Repository Structure

```
the_final_pokebattle/
├── src/
│   ├── frontend.py          # Pygame rendering, input, game loop, animations
│   ├── game.py              # Core game logic (movement, battle, state, timers)
│   ├── rom_reader.py        # ROM data extraction (stats, moves, types)
│   └── sprite_extractor.py  # Sprite + tileset extraction from ROM (incl. surf)
├── data/
│   ├── maps.json            # Map layouts, portals, NPCs, walkable tiles, clue zones
│   └── characters.json      # Playable characters and rival config
├── custom_map_1_forest/
│   └── map.json             # Map editor source data
├── .gitignore
├── README.md
├── CONTRIBUTING.md
└── idea.txt                 # Original game design notes
```

> **Generated at runtime** (not committed): `assets/`, `.sprite_cache/`, `screenshots/`  
> **User-provided** (not committed): ROM file (`.gba`)  
> **Excluded** (reference only): `pokefirered/`

---

## Game Flow (current offline prototype)

1. **Character Select** → choose Red or Leaf (Blue is not selectable until unlocked)
2. **Starter Pick** → each character's starter options (e.g. Bulbasaur, Charmander, Squirtle)
3. **Explore** → wild encounters in the forest; find HM Cut and HM Surf
4. **Use HMs** → cut blocking trees, teach Surf and ride across the river
5. **Final Battle** → reach the Rival in the forest to trigger the showdown
6. **Victory** → defeat the rival's whole team to win — and defeat Blue to unlock him as playable for the next run

> Note: the 3-minute adventure timer and the central-area trigger are the next planned step (see idea.txt) and are not wired up yet.

---

## Technical Notes

- Map backgrounds are pre-rendered PNGs scaled 3× at load; overlay system paints cut-tree patches and item pickups on top
- Battle damage uses the Gen III formula: `((2*Level/5+2) * Power * A/D) / 50 + 2) * STAB * TypeEff`
- Encounter rate is configurable per-tile in `maps.json`
- Smooth walking uses frame-interpolated offsets (8 frames per tile)
- Surf: mounted/unmounted overworld sprites are extracted from the ROM; the player rides across water with a mount animation on entry and a get-off animation when returning to land
- All visual assets are extracted from the ROM at runtime — nothing proprietary is stored in the repository

---

## License

This project is released for educational and portfolio purposes.  
All original code and map designs are created by the authors.  
No proprietary data or assets are included in the repository.
