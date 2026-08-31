"""Asset Generator — Reconstructs all game assets at runtime.

This module regenerates the assets/ folder from:
1. data/sprites.json — Tile, player, NPC, item sprite data (palette + compressed pixels)
2. ROM file — Creature sprites (via sprite_extractor)
3. Tile-based map rendering — Pre-rendered map backgrounds from tiles + layout

No proprietary assets are stored in the repository. Everything is generated on first launch.
"""

import os
import sys
import json
import base64
import zlib
import struct

try:
    from PIL import Image
except ImportError:
    Image = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
DATA_DIR = os.path.join(BASE_DIR, "data")
SPRITE_DATA = os.path.join(DATA_DIR, "sprites.json")
MAP_BG_DIR = os.path.join(ASSET_DIR, "rocky_desert")


def _generate_sheet_sprites():
    """Generate multi-frame sheet sprites (cut_tree, rock_smash) from sprites.json data."""
    if not Image:
        return
    if not os.path.exists(SPRITE_DATA):
        return
    with open(SPRITE_DATA) as f:
        sprites = json.load(f)
    sheet_configs = [
        ("tile_cut_tree_sheet", "tile_cut_tree.png", 4),
        ("tile_rock_smash_sheet", "tile_rock_smash.png", 4),
    ]
    for sheet_key, out_name, num_frames in sheet_configs:
        if sheet_key not in sprites:
            continue
        entry = sprites[sheet_key]
        w, h = entry['w'], entry['h']
        palette = [tuple(c) for c in entry['pal']]
        raw = zlib.decompress(base64.b64decode(entry['data']))
        img = Image.new('RGBA', (w, h))
        img.putdata([palette[b] for b in raw])
        frame_w = w // num_frames
        for i in range(num_frames):
            frame = img.crop((i * frame_w, 0, (i + 1) * frame_w, h))
            try:
                from map_renderer import NIGHT_MODE, NIGHT_R, NIGHT_G, NIGHT_B, NIGHT_B_ADD
                if NIGHT_MODE:
                    px = frame.load()
                    for y in range(frame.height):
                        for x in range(frame.width):
                            r, g, b, a = px[x, y]
                            if a == 0:
                                continue
                            nr = int(r * NIGHT_R)
                            ng = int(g * NIGHT_G)
                            nb = int(min(255, b * NIGHT_B + NIGHT_B_ADD))
                            px[x, y] = (nr, ng, nb, a)
            except Exception:
                pass
            out_path = os.path.join(ASSET_DIR, f"{out_name.replace('.png', f'_{i}.png')}")
            frame.save(out_path)
        out_full = os.path.join(ASSET_DIR, out_name)
        img.save(out_full)
    rock_smash_path = os.path.join(ASSET_DIR, "tile_rock_smash.png")
    rock_path = os.path.join(ASSET_DIR, "tile_rock.png")
    if os.path.exists(rock_smash_path) and not os.path.exists(rock_path):
        sheet = Image.open(rock_smash_path).convert("RGBA")
        sheet.crop((0, 0, 16, 16)).save(rock_path)


def generate_sprites():
    """Reconstruct tile/player/NPC/item PNGs from sprites.json."""
    if not Image:
        print("[asset_generator] Pillow not installed, using pygame fallback")
        return generate_sprites_pygame()

    if not os.path.exists(SPRITE_DATA):
        print(f"[asset_generator] Missing {SPRITE_DATA}")
        return False

    os.makedirs(ASSET_DIR, exist_ok=True)

    with open(SPRITE_DATA) as f:
        sprites = json.load(f)

    count = 0
    for name, entry in sprites.items():
        out_path = os.path.join(ASSET_DIR, f"{name}.png")
        if os.path.exists(out_path):
            continue
        w, h = entry['w'], entry['h']
        palette = [tuple(c) for c in entry['pal']]
        raw = zlib.decompress(base64.b64decode(entry['data']))
        img = Image.new('RGBA', (w, h))
        img.putdata([palette[b] for b in raw])
        img.save(out_path)
        count += 1

    if count:
        print(f"[asset_generator] Generated {count} sprite PNGs")
    _generate_sheet_sprites()
    return True


def generate_sprites_pygame():
    """Fallback: generate sprites using pygame (no Pillow needed)."""
    try:
        import pygame
    except ImportError:
        print("[asset_generator] Neither Pillow nor pygame available")
        return False

    if not os.path.exists(SPRITE_DATA):
        return False

    os.makedirs(ASSET_DIR, exist_ok=True)

    with open(SPRITE_DATA) as f:
        sprites = json.load(f)

    count = 0
    for name, entry in sprites.items():
        out_path = os.path.join(ASSET_DIR, f"{name}.png")
        if os.path.exists(out_path):
            continue
        w, h = entry['w'], entry['h']
        palette = [tuple(c) for c in entry['pal']]
        raw = zlib.decompress(base64.b64decode(entry['data']))
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            for x in range(w):
                color = palette[raw[y * w + x]]
                surf.set_at((x, y), color)
        pygame.image.save(surf, out_path)
        count += 1

    if count:
        print(f"[asset_generator] Generated {count} sprite PNGs (pygame)")
    return True


def generate_map_backgrounds():
    """Pre-render map backgrounds from tiles + map layouts."""
    try:
        import pygame
    except ImportError:
        print("[asset_generator] pygame not available for map BG rendering")
        return False

    maps_path = os.path.join(DATA_DIR, "maps.json")
    if not os.path.exists(maps_path):
        return False

    with open(maps_path) as f:
        maps = json.load(f)

    TILE_FILES = {
        ".": "tile_grass.png",
        "g": "tile_tall_grass.png",
        "d": "tile_path.png",
        "p": "tile_path2.png",
        "s": "tile_path.png",
        "S": "tile_path.png",
        "1": "tile_tree_tl.png",
        "2": "tile_tree_tr.png",
        "3": "tile_tree_bl.png",
        "4": "tile_tree_br.png",
        "T": "tile_tree_thin.png",
        "C": "tile_cut_tree.png",
        "I": "tile_item.png",
        "F": "tile_fence.png",
        "w": "tile_water.png",
        "W": "tile_water_edge_t.png",
        "R": "tile_rock.png",
        "r": "tile_path.png",
        "L": "tile_wall_l.png",
        "l": "tile_wall_r.png",      # Metatile 0x045 (wall section)
        "D": "tile_door.png",        # Metatile 0x03D (General_Door)
        "f": "tile_fence.png",       # Metatile 0x04D
        "B": "tile_bridge.png",      # Metatile 0x0D8 (ledge/bridge area, 19 cells in VF)
        "A": "tile_arena.png",       # Metatile 0x001 (Plain_Mowed, open ground)
        "z": "tile_dirt.png",        # Metatile 0x115 (desert sand floor)
        "r": "tile_dirt.png",        # Metatile 0x1D5 (sand with scattered rocks)
        "R": "tile_dirt.png",        # Metatile 0x1D6 (sand with rock cluster)
        "E": "tile_tall_grass.png",  # Metatile 0x00D (encounter area)
        "N": "tile_sign.png",        # Metatile 0x003 (sign post)
    }

    # Load tile images
    tiles = {}
    for ch, fname in TILE_FILES.items():
        path = os.path.join(ASSET_DIR, fname)
        if os.path.exists(path):
            tiles[ch] = pygame.image.load(path).convert_alpha()
        else:
            surf = pygame.Surface((16, 16), pygame.SRCALPHA)
            surf.fill((100, 100, 100, 255))
            tiles[ch] = surf

    os.makedirs(MAP_BG_DIR, exist_ok=True)
    count = 0

    for map_key, map_data in maps.items():
        bg_name = f"{map_key}_rendered.png"
        out_path = os.path.join(MAP_BG_DIR, bg_name)
        if os.path.exists(out_path):
            continue

        layout = map_data.get("layout", [])
        if not layout:
            continue

        rows = len(layout)
        cols = max(len(row) for row in layout) if layout else 0
        bg = pygame.Surface((cols * 16, rows * 16), pygame.SRCALPHA)

        for r, row_str in enumerate(layout):
            for c, ch in enumerate(row_str):
                tile = tiles.get(ch)
                if tile:
                    bg.blit(tile, (c * 16, r * 16))
                else:
                    # Default grass
                    bg.blit(tiles.get('.', pygame.Surface((16, 16))), (c * 16, r * 16))

        pygame.image.save(bg, out_path)
        # Update map data to reference the background
        map_data["background"] = f"rocky_desert/{bg_name}"
        count += 1

    if count:
        print(f"[asset_generator] Rendered {count} map backgrounds")
    return True


def _fix_surf_sprites():
    """Skip surf blob composite - surf sprites are extracted from ROM via sprite_extractor."""
    pass


def generate_all(rom_path=None):
    """Generate all assets. Call on first launch."""
    print("[asset_generator] Checking assets...")

    # 1. Sprites from sprites.json (includes multi-frame sheets)
    generate_sprites()
    _generate_sheet_sprites()

    # 2. Creature sprites from ROM
    if rom_path and os.path.exists(rom_path):
        from sprite_extractor import SpriteExtractor
        ext = SpriteExtractor(rom_path)
        ext.extract_all_creatures()
        # Real overworld player animations (up/down/left/right) from the ROM
        try:
            ext.extract_player_sprites()
            ext.extract_npc_overworld_sprites()
            ext.extract_surf_sprites()
            ext.extract_trainer_front_pics()
            _fix_surf_sprites()
        except Exception as e:
            print(f"[asset_generator] OW player sprites skipped: {e}")
        # Copy creature sprites to assets/
        cache_dir = os.path.join(BASE_DIR, ".sprite_cache")
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.startswith("creature_") and f.endswith(".png"):
                    src = os.path.join(cache_dir, f)
                    # Map creature_001.png -> pokemon_001.png for compatibility
                    dst_name = f.replace("creature_", "pokemon_")
                    dst = os.path.join(ASSET_DIR, dst_name)
                    if not os.path.exists(dst):
                        import shutil
                        shutil.copy2(src, dst)

    # 3. Map backgrounds (ROM-based renderer)
    try:
        from map_renderer import render_maps_from_rom
        maps_json = os.path.join(BASE_DIR, "data", "maps.json")
        map_bg_dir = os.path.join(ASSET_DIR, "rocky_desert")
        if rom_path and os.path.exists(rom_path):
            render_maps_from_rom(rom_path, maps_json, map_bg_dir)
        else:
            # Fallback: try pygame-based generation
            import pygame
            if not pygame.get_init():
                pygame.init()
                pygame.display.set_mode((1, 1))
            generate_map_backgrounds()
    except Exception as e:
        print(f"[asset_generator] Map BG generation skipped: {e}")

    print("[asset_generator] Done.")


if __name__ == "__main__":
    # Find ROM file
    rom = None
    for f in os.listdir(BASE_DIR):
        if f.endswith('.gba'):
            rom = os.path.join(BASE_DIR, f)
            break
    generate_all(rom)
