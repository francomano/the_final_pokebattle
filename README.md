# The Final PokéBattle

> A retro-style monster-catching RPG built with Python and Pygame, using ROM data for creature stats and sprites.

**Version 0.1 — PROTOTYPE**

⚠️ **This is an early prototype / proof-of-concept.** It demonstrates the core mechanics (exploration, battles, HM puzzles) but is far from a finished game. Expect rough edges, placeholder content, and incomplete features. Contributions and feedback are very welcome!

---

## Overview

The Final PokéBattle is a turn-based RPG that reads creature data (stats, types, moves, sprites) from a Game Boy Advance ROM file and wraps it in an original overworld with custom maps, NPCs, HM puzzles, and a final boss battle.

The game is **not** a ROM hack — it uses the ROM purely as a data source. All game logic, rendering, map layouts, and overworld logic are original.

> **Status:** Prototype. The current build provides a single playable run (~15 min) with one map set, limited encounters, and a final boss. Many systems are stubbed or minimal.

---

## Features (v0.1)

- 🎮 **Three playable characters** — Red, Blue, Leaf (with unique rival pairing)
- 🗺️ **Multi-map overworld** — Forest, River, Cave, Arena (with pre-rendered backgrounds)
- 🌿 **Wild encounters** — Walk through tall grass to find creatures
- ⚔️ **Turn-based battle system** — Type effectiveness, STAB, accuracy, PP tracking
- 🪓 **HM Cut** — Find the HM item, teach it to a creature, cut blocking trees
- 🏆 **Final Boss** — Defeat the Rival in the Arena to win
- 🎒 **Inventory & Party** — Manage items, heal, switch creatures
- 🖼️ **Sprite extraction** — All visual assets generated from ROM at runtime

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

On first launch the game extracts all sprites (creatures, players, NPCs, tiles) from the ROM into the `assets/` folder and `.sprite_cache/`.

---

## Repository Structure

```
the_final_pokebattle/
├── src/
│   ├── frontend.py          # Pygame rendering, input, game loop
│   ├── game.py              # Core game logic (movement, battle, state)
│   ├── rom_reader.py        # ROM data extraction (stats, moves, types)
│   └── sprite_extractor.py  # Sprite + tileset extraction from ROM
├── data/
│   ├── maps.json            # Map layouts, portals, NPCs, walkable tiles
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

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│  frontend   │◄────►│    game      │◄────►│  rom_reader  │
│  (pygame)   │      │  (logic)     │      │  (ROM data)  │
└─────────────┘      └──────────────┘      └──────────────┘
       │                     │                      │
       ▼                     ▼                      ▼
   Rendering          State Machine           Creature DB
   Input Loop         Battle Engine           Move/Type data
   Animations         Map/Portal sys          Sprite offsets
```

- **frontend.py** — Draws maps (BG + overlay), players, NPCs, battles; handles keyboard input and smooth walking animation
- **game.py** — `GameSession` manages state (`EXPLORING`, `BATTLE`, `FINAL_BATTLE`, `WIN`), player movement, collisions, HM logic, wild encounters, battle turns
- **rom_reader.py** — Reads GBA ROM structure for base stats, type chart, move data, evolution chains
- **sprite_extractor.py** — Decodes LZ77-compressed 4bpp sprites from ROM, generates all tiles, player, NPC, and creature PNGs into `assets/`

---

## Game Flow

1. **Character Select** → Choose Red, Blue, or Leaf (rival auto-assigned)
2. **Starter Pick** → Bulbasaur, Charmander, or Squirtle
3. **Explore Forest** → Wild encounters in tall grass, find HM Cut in cave
4. **Cut Trees** → Teach Cut to a creature, clear the path south
5. **Arena Battle** → Talk to Rival to trigger final battle
6. **Victory** → Defeat Rival's team to win!

---

## Technical Notes

- Map backgrounds are pre-rendered PNGs scaled 3× at load; overlay system paints cut-tree patches and item pickups on top
- Battle damage uses Gen III formula: `((2*Level/5+2) * Power * A/D) / 50 + 2) * STAB * TypeEff`
- Wild encounter rate is configurable per-tile in `maps.json`
- Smooth walking uses frame-interpolated offsets (8 frames per tile)
- All visual assets are extracted from the ROM at runtime — nothing proprietary is stored in the repository

---

## License

This project is released for educational and portfolio purposes.  
All original code and map designs are created by the authors.  
No proprietary data or assets are included in the repository.
