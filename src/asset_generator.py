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
MAP_BG_DIR = os.path.join(ASSET_DIR, "custom_map_1_forest")


def _fix_cut_tree_sprite():
    """Overwrite tile_cut_tree.png with the authentic CUT-tree object sprite from pokefirered decomp.

    sprites.json's tile_cut_tree is a placeholder uniform green 16x16 (wrong sprite). The real
    CUT bush is an object event (graphics/object_events/pics/misc/cut_tree.png, 64x16, 4 frames).
    We generate it at runtime from ../pokefirered chr (già reversata) so no static asset is stored.
    """
    if not Image:
        return
    candidates = [
        os.path.join(BASE_DIR, "..", "pokefirered", "graphics", "object_events", "pics", "misc", "cut_tree.png"),
        "/home/mf/Desktop/pokefirered/graphics/object_events/pics/misc/cut_tree.png",
    ]
    src = None
    for c in candidates:
        if os.path.exists(c):
            src = c
            break
    if not src:
        return
    try:
        img = Image.open(src).convert("RGBA")
        # 64x16 sheet: 4x 16x16. First frame is the idle small tree.
        frame = img.crop((0, 0, 16, 16))
        out_path = os.path.join(ASSET_DIR, "tile_cut_tree.png")
        # always overwrite if placeholder is detected or if frame differs
        # detect placeholder: sprites.json version is 16x16 uniform green (single palette)
        need = True
        if os.path.exists(out_path):
            existing = Image.open(out_path).convert("RGBA")
            # placeholder is uniform green -> 1 unique color + maybe alpha; real tree has >5 colors
            if len(set(existing.getdata())) > 4:
                # already seems like real tree, but ensure night tint matches map_renderer
                # we write night-tinted version to keep consistency with NIGHT_MODE
                pass
            else:
                need = True
        if need:
            # apply same night tint as map_renderer for consistency when used as tile fallback
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
            os.makedirs(ASSET_DIR, exist_ok=True)
            frame.save(out_path)
            print(f"[asset_generator] Fixed tile_cut_tree.png from {src}")
    except Exception as e:
        print(f"[asset_generator] cut_tree fix skipped: {e}")


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
    # Always ensure the cuttable bush uses the real ROM object sprite
    _fix_cut_tree_sprite()
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

    # Tile mapping: char -> (filename, pokefirered metatile offset)
    # Metatile IDs from pokefirered decomp - based on REAL Viridian Forest map data
    # Source: data/layouts/ViridianForest/map.bin + tilesets general + viridian_forest
    # Palettes: primary/general slots 0-6, secondary/viridian_forest slots 7-12
    TILE_FILES = {
        ".": "tile_grass.png",       # Metatile 0x008 (walkable ground, 136 cells in VF)
        "g": "tile_tall_grass.png",  # Metatile 0x00D (encounter grass, 766 cells in VF)
        "d": "tile_path.png",        # Metatile 0x0D9 (sandy/dirt path, 55 cells in VF)
        "p": "tile_path2.png",       # Metatile 0x0D1 (path variant)
        "s": "tile_path.png",        # Metatile 0x0D9
        "S": "tile_path.png",        # Metatile 0x0D9
        "1": "tile_tree_tl.png",     # Metatile 0x298 (VF tree canopy, 261 cells)
        "2": "tile_tree_tr.png",     # Metatile 0x299 (VF tree canopy, 304 cells)
        "3": "tile_tree_bl.png",     # Metatile 0x291 (VF tree lower, 245 cells)
        "4": "tile_tree_br.png",     # Metatile 0x292 (VF tree lower, 224 cells)
        "T": "tile_tree_thin.png",   # Metatile 0x290 (VF tree trunk/mid, 269 cells)
        "C": "tile_cut_tree.png",    # Metatile 0x284 (VF cuttable bush, 13 cells)
        "I": "tile_item.png",        # Custom (grass 0x00D + pokeball overlay)
        "F": "tile_fence.png",       # Metatile 0x04D (structure/fence, 99 cells in VF)
        "w": "tile_water.png",       # Metatile 0x12B (CalmWater, palette 4)
        "W": "tile_water_edge_t.png",# Metatile 0x132 (water/land edge)
        "R": "tile_roof_l.png",      # Metatile 0x048 (roof left)
        "r": "tile_roof_r.png",      # Metatile 0x049 (roof right)
        "L": "tile_wall_l.png",      # Metatile 0x044 (wall section)
        "l": "tile_wall_r.png",      # Metatile 0x045 (wall section)
        "D": "tile_door.png",        # Metatile 0x03D (General_Door)
        "f": "tile_fence.png",       # Metatile 0x04D
        "B": "tile_bridge.png",      # Metatile 0x0D8 (ledge/bridge area, 19 cells in VF)
        "A": "tile_arena.png",       # Metatile 0x001 (Plain_Mowed, open ground)
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
        map_data["background"] = f"custom_map_1_forest/{bg_name}"
        count += 1

    if count:
        print(f"[asset_generator] Rendered {count} map backgrounds")
    return True


def _fix_surf_sprites():
    """Composite LAPRAS (surf_blob) under player surf frames so 'manca il lapras sotto' is fixed.

    The ROM stores surf as two sprites: red_surf/green_surf (player, 16x32, PAL PLAYER) + surf_blob
    (Lapras mount, 32x32, its own palette). The original SpriteExtractor wrote only the player half,
    leaving a hole where Lapras should be. We rebuild the PNGs at runtime from the decomp chr
    (../pokefirered/graphics/... already reversata, no static asset) by compositing blob under player
    and applying the same night tint as the map.
    """
    if not Image:
        return
    candidates_blob = [
        os.path.join(BASE_DIR, "..", "pokefirered", "graphics", "object_events", "pics", "misc", "surf_blob.png"),
        "/home/mf/Desktop/pokefirered/graphics/object_events/pics/misc/surf_blob.png",
    ]
    blob_path = next((c for c in candidates_blob if os.path.exists(c)), None)
    if not blob_path:
        return
    configs = [
        ("player_red", "red_surf"),
        ("player_green", "green_surf"),
        ("player_blue", "green_surf"),  # Blue has no own surf sheet, falls back to Green
    ]
    try:
        from map_renderer import NIGHT_MODE, NIGHT_R, NIGHT_G, NIGHT_B, NIGHT_B_ADD
    except Exception:
        NIGHT_MODE = False
    blob_sheet = Image.open(blob_path).convert("RGBA")
    # surf_blob.png is 192x32 (6 frames of 32x32). Frames 0-2 are ride down/up/left
    def blob_frame(idx):
        # 32x32 frame
        x = idx * 32
        return blob_sheet.crop((x, 0, x + 32, 32))
    # mapping ride dir -> blob frame idx (observed: 0=down,1=up,2=left)
    blob_map = {"down": 0, "up": 1, "left": 2}
    for prefix, src_name in configs:
        candidates_src = [
            os.path.join(BASE_DIR, "..", "pokefirered", "graphics", "object_events", "pics", "people", f"{src_name}.png"),
            f"/home/mf/Desktop/pokefirered/graphics/object_events/pics/people/{src_name}.png",
        ]
        src_path = next((c for c in candidates_src if os.path.exists(c)), None)
        if not src_path:
            continue
        sheet = Image.open(src_path).convert("RGBA")
        # 288x32 = 9 frames of 32x32, each containing 16x32 player centered at +8
        def player_frame(idx):
            # extract 16x32 central
            x0 = idx * 32 + 8
            return sheet.crop((x0, 0, x0 + 16, 32))
        pairs = [("down", 0, 0), ("up", 1, 1), ("left", 2, 2),
                 ("mount_down", 9, 0), ("mount_up", 10, 1), ("mount_left", 11, 2)]
        # frame index mapping for mount uses same blob? mount blob is same shape but maybe bob अलग, use same
        for out_suffix, p_idx, b_idx in [("surf_down", 0, 0), ("surf_up", 1, 1), ("surf_left", 2, 2),
                                         ("surf_mount_down", 9, 0), ("surf_mount_up", 10, 1), ("surf_mount_left", 11, 2)]:
            try:
                # For mount frames idx 9-11, the player sheet still has them at those indices
                # The blob for mount we reuse ride blob (game reuses same blob with offset)
                pf = player_frame(p_idx if p_idx < 9 else p_idx - 9 + 3) if p_idx >= 9 else player_frame(p_idx)
                # For mount, actual player mount frame is at 9,10,11 in sheet? Our sheet has only 9 frames (0-8) ??? red_surf is 288=9 frames, so 9 is out of range.
                # For mount we fallback to ride frame (player standing on blob already)
                if p_idx >= 9:
                    pf = player_frame(0 if "down" in out_suffix else 1 if "up" in out_suffix else 2)
                bf = blob_frame(b_idx)
                # composite: 32x32 canvas, blob centered, player 16x32 at (8,0)
                canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
                canvas.paste(bf, (0, 0), bf)
                canvas.paste(pf, (8, 0), pf)
                # crop central 16x32 to match frontend expected size (16x32)
                # But blob extends 8px left/right beyond player; cropping to 16x32 would cut blob edges.
                # Keep 32x32 then center-crop to 16x32? For frontend we want 16x32 but blob would be truncated.
                # Instead keep 32x32 then frontend can handle 32x32? Frontend scales to TILE_SIZE x TILE_SIZE*2 (16x32->48x96).
                # To include full blob, we need to provide 32x32 and let frontend scale accordingly.
                # We will save as 32x32 and update frontend to handle both sizes via smoothscale.
                # For compatibility, save both 16x32 cropped and 32x32 wide, but frontend will load 16x32 path.
                # So produce 16x32 composite by extending canvas: place blob clipped to 16x32 bottom?
                # Better: create final 16x32 where blob is visible: blob's bottom part (y 16-32) is under feet,
                # within 16x32 the blob bottom appears at y ~20-28. The 32-wide blob left/right overhang beyond 16 would be lost.
                # So for 16-wide, we center blob's 16 central column: blob.crop(8,0,24,32) -> 16x32
                blob_center = bf.crop((8, 0, 24, 32))
                final16 = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
                final16 = Image.alpha_composite(final16, blob_center)
                final16 = Image.alpha_composite(final16, pf)
                if NIGHT_MODE:
                    # apply night tint to composite
                    px = final16.load()
                    for y in range(32):
                        for x in range(16):
                            r, g, b, a = px[x, y]
                            if a == 0:
                                continue
                            nr = int(r * NIGHT_R); ng = int(g * NIGHT_G); nb = int(min(255, b * NIGHT_B + NIGHT_B_ADD))
                            px[x, y] = (nr, ng, nb, a)
                out_path = os.path.join(ASSET_DIR, f"{prefix}_{out_suffix}.png")
                final16.save(out_path)
            except Exception as e:
                print(f"[asset_generator] surf composite {prefix} {out_suffix} skip: {e}")
    print("[asset_generator] Fixed surf sprites (lapras composite)")


def generate_all(rom_path=None):
    """Generate all assets. Call on first launch."""
    print("[asset_generator] Checking assets...")

    # 1. Sprites from sprites.json (includes cut_tree fix)
    generate_sprites()
    # ensure cut_tree is fixed even when sprites already existed (cached)
    _fix_cut_tree_sprite()

    # 2. Creature sprites from ROM
    if rom_path and os.path.exists(rom_path):
        from sprite_extractor import SpriteExtractor
        ext = SpriteExtractor(rom_path)
        ext.extract_all_creatures()
        # Real overworld player animations (up/down/left/right) from the ROM
        try:
            ext.extract_player_sprites()
            ext.extract_surf_sprites()
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
        map_bg_dir = os.path.join(ASSET_DIR, "custom_map_1_forest")
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
