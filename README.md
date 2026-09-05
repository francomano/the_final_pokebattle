# The Final PokéBattle

> A fully online MMO RPG: drop straight into the adventure map, explore, and clash in a final showdown — built with Python and Pygame, reading creature data from a **Pokémon Fire Red** GBA ROM.

`pokemon` `gba` `rom-hack` `firered` `mmorpg` `pygame` `python`

**Version 0.2 — PROTOTYPE**

⚠️ **Work in progress.** The current build is an offline prototype focused on the new adventure rules (3-minute adventure, final-area trigger, playing AI opponent, character unlocks). The online server is a later milestone. Expect rough edges and placeholder content.

---

## Overview

The Final PokéBattle is a **fully online MMO RPG**. There is no preparation phase — players drop directly into the adventure map and spawn into the game world. The server holds the data needed during a match; when the adventure ends, the match data is deleted and only the **final result (the winner)** is kept.

The game is **not** a ROM hack — it uses the ROM purely as a data source for creature stats, moves, types and sprites. All game logic, rendering, maps and overworld behavior are original.

This README describes the **offline prototype** that is currently being built toward that vision: it mirrors the online rules as a single-player practice mode, and the online server is a later milestone.

### What exists today (offline prototype)

- **Mode select** — Online (placeholder "non disponibile") / Offline (Campagna) → Offline goes to character select.
- Character select + starter pick, map exploration, wild encounters, and a final showdown.
- **HM Cut** and **HM Surf** — Surf rides across water with real ROM overworld surf sprites and a smooth mount/dismount animation (mount visible under the player).
- **Blue is the fixed rival** of the forest map: he is not selectable at the start, and defeating him unlocks him as a playable character.
- **Campagna 3 min + IA** — 3-minute timer in HUD, Blue (IA) moves toward the center with BFS, and reaching the central point teleports the other player and starts the final battle automatically; timer expiry also triggers the finale.
- **Facce allenatori in HUD** — trainer front pics taken only from the user's ROM, shown top-left (player) and top-right (rival).
- Night mode with darkened palettes and all sprites/tiles taken only from the user's ROM.

### Not yet implemented (planned)

- The online server (chat, clue loading, keeping only the winner).
- More character unlocks beyond Blue.

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

- **Campagna 3 min + IA** — timer 180s, Blue si muove (BFS + 15% random) verso il centro, gioca (incontri in erba alta, catture, level-up) e aggiorna la squadra; ogni partita è diversa per seed/spawn/path.
- **Indizi dinamici** — parlando con NPC ottieni [Indizio: ...] generato dalle azioni recenti di Blue (team, livello, zona); i segni statici restano fissi.
- **Final trigger** — raggiunta l'arena centrale il rivale in attesa viene teletrasportato e la battaglia finale parte automaticamente (vale anche se Blue è arrivato prima); allo scadere dei 3 min parte comunque.

---

## Current Features (offline prototype)

- 🎮 **Mode select** — Online (placeholder) / Offline Campagna
- 🎮 **Character select** — Red and Leaf playable at the start (starter + rival pairing). Blue is the fixed forest rival, not selectable until defeated.
- ⏱️ **3-minute Campagna + IA** — HUD timer (180s), Blue moves via BFS toward the center (`area_central` 10,5); reaching the center teleports the other and starts the final battle; timer expiry also triggers the finale
- 🧑‍🤝‍🧑 **Trainer faces in HUD** — front pics taken only from the user's ROM (top-left player, top-right rival) alongside team HP bars
- 🗺️ **Multi-map overworld** — Forest (south/north), River, Cave, House, Arena — with portals/edge-connections and collision from `maps.json`
- 🌙 **Night mode** — palettes darkened + blue moonlight tint and indigo overlay; applied to metatiles and object sprites at generation time and as a viewport overlay at render time
- 🌿 **Wild encounters** — tall-grass (`g`) trigger zones with per-map encounter rate; fishing (`w`/`B`) with Old Rod
- ⚔️ **Turn-based battle** — Gen III damage formula, type effectiveness, STAB, accuracy, PP, capture/flee
- 🪓 **HM Cut — authentic sprite** — small tree is the real object-event cut tree taken only from the user's ROM; `C` renders as grass + sprite overlay and is replaced by path when cut
- 🌊 **HM Surf + mount** — teach Surf to a water-type and ride; surf sprites are taken only from the user's ROM (water mount visible under the player) with mount/dismount frames
- 🌲 **Forest rendering** — huge-tree 3×3 metatiles (`0x298-0x2A2`) from the ROM, segment-aligned for cleaner edges
- 🏆 **Rival showdown** — the rival (Blue) waits in the center; defeating his whole team wins the match and unlocks him as playable
- 🎒 **Inventory & Party** — items, key items (Old Rod), HMs, healing, switching, faint handling

---

## Requirements

- Python 3.10+
- Pygame 2.x
- A legally obtained **Pokémon Fire Red** (U) GBA ROM — user provides their own, not included

```bash
pip install pygame
```

---

## Quick Start

```bash
# 1. Place your Pokémon Fire Red ROM file in the project root (.gba)
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
```

> **Not committed**: `assets/`, `.sprite_cache/`, `screenshots/`  
> **User-provided** (not committed): Pokémon Fire Red `.gba` ROM — all game data and sprites are extracted from this file at runtime

---

## Game Flow (current offline prototype)

0. **Mode Select** → Online (shows "non disponibile") / Offline Campagna → Offline goes to character select
1. **Character Select** → choose Red or Leaf (Blue is not selectable until unlocked)
2. **Starter Pick** → each character's starter options
3. **Explore (3 min)** → timer in HUD center-top, faces in HUD corners, Blue IA moves toward the center; wild encounters; find HM Cut and HM Surf
4. **Use HMs** → cut blocking trees, teach Surf and ride across the river
5. **Final Battle** → reaching the central point (`area_central` 10,5) teleports the other player and starts the showdown; timer expiry also teleports both and starts it
6. **Victory** → defeat the rival's whole team to win — and defeat Blue to unlock him as playable for the next run

---

## Technical Notes

- Map backgrounds are pre-rendered PNGs scaled 3× at load; overlay system paints cut-tree patches and item pickups on top
- Night mode darkens palettes and adds an indigo viewport overlay
- Battle damage uses the Gen III formula: `((2*Level/5+2) * Power * A/D) / 50 + 2) * STAB * TypeEff`
- Encounter rate is configurable per-tile in `maps.json`
- Smooth walking uses frame-interpolated offsets (12 frames per tile); IA Blue uses BFS toward the center and moves every 18 frames
- Surf uses mount/dismount frames; forest uses 3×3 huge-tree metatiles segment-aligned for cleaner edges
- HUD shows 3-minute countdown and trainer front pics (taken only from the user's ROM)
- Nothing proprietary is stored in the repository — all data comes only from the user's ROM

---

## License

This project is released for educational and portfolio purposes.  
All original code and map designs are created by the authors.  
No proprietary data or assets are included in the repository.
