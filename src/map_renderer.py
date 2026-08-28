"""
ROM-based map renderer.
Renders map backgrounds using authentic metatiles extracted directly from the ROM.
"""

import struct
import os
import json
import numpy as np
from PIL import Image

# Offsets for FireRed (U) ROM
GEN_TILES_OFF = 0xEA1D68
GEN_PAL_OFF = 0xEA1B68
GEN_MT_OFF = 0x29F6C8
VF_TILES_OFF = 0x287F94
VF_PAL_OFF = 0x288444
VF_MT_OFF = 0x2B90B4

FOREST_PATTERN = [
    [0x298, 0x299, 0x29A],
    [0x290, 0x291, 0x292],
    [0x2A0, 0x2A1, 0x2A2],
]

# True -> render everything with night palette / lighting
NIGHT_MODE = True
NIGHT_R = 0.52
NIGHT_G = 0.55
NIGHT_B = 0.72
NIGHT_B_ADD = 10  # slight blue moonlight offset

TILE_MAP_DEFAULT = {
    'T': None,       # Forest pattern (special handling - 3x3 huge tree, aligned per segment)
    'M': 0x071,      # Mountain rock
    'G': 0x0A9,      # Cave entrance (dark)
    'W': 0x003,      # Sign
    'N': 0x003,      # Sign post (with collision)
    'C': None,       # Cut tree - handled as ground + object sprite overlay (real ROM object)
    '.': 0x009,      # Ground
    'g': 0x00D,      # Tall grass
    'd': 0x0D9,      # Path/dirt
    'w': 0x12B,      # Water
    'B': 0x0D9,      # Bridge (path)
    'D': 0x03D,      # Door
    'I': 0x00D,      # Item (grass)
    'E': 0x00D,      # Encounter grass
    'A': 0x001,      # Arena floor
    'F': 0x079,      # Fence/wall (dark)
    'H': 0x05D,      # House wall center
    '[': 0x05C,      # House wall left
    ']': 0x05E,      # House wall right
    '^': 0x048,      # Roof left
    '~': 0x049,      # Roof center
    '`': 0x04A,      # Roof right
}

TILE_MAP_CAVE = {
    'T': 0x071,      # Rock wall
    'd': 0x07B,      # Cave floor
    'E': 0x0A9,      # Exit (dark opening)
    'I': 0x07B,      # Item (cave floor)
    '.': 0x07B,      # Cave floor
    'W': 0x003,      # Sign
    'N': 0x003,      # Sign post (with collision)
}

TILE_MAP_HOUSE = {
    'T': 0x03C,      # Interior wall
    '.': 0x001,      # Floor
    'W': 0x003,      # Sign/bookshelf
    'N': 0x003,      # Sign post (with collision)
    'D': 0x03D,      # Door
    'd': 0x001,      # Floor
}


def decompress_lz77(data, offset):
    ds = data[offset+1] | (data[offset+2] << 8) | (data[offset+3] << 16)
    result = bytearray()
    src = offset + 4
    while len(result) < ds:
        if src >= len(data): break
        flags = data[src]; src += 1
        for bit in range(8):
            if len(result) >= ds: break
            if flags & (0x80 >> bit):
                if src + 1 >= len(data): break
                b1 = data[src]; b2 = data[src+1]; src += 2
                l = ((b1 >> 4) & 0xF) + 3
                d_ = ((b1 & 0xF) << 8) | b2; d_ += 1
                for j in range(l):
                    if len(result) >= ds: break
                    pos = len(result) - d_
                    result.append(result[pos] if pos >= 0 else 0)
            else:
                if src >= len(data): break
                result.append(data[src]); src += 1
    return bytes(result[:ds])


class MapRenderer:
    def __init__(self, rom_path):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()
        self._load_tilesets()
        self._mt_cache = {}

    def _load_tilesets(self):
        self.gen_pals = self._load_palettes(GEN_PAL_OFF)
        vf_pals = self._load_palettes(VF_PAL_OFF)
        self.combined_pals = list(self.gen_pals)
        for i in range(7, 13):
            if i < len(vf_pals):
                self.combined_pals[i] = vf_pals[i]
        if NIGHT_MODE:
            self.combined_pals = self._apply_night_to_pals(self.combined_pals)
        self.gen_tile_data = decompress_lz77(self.rom, GEN_TILES_OFF)
        self.vf_tile_data = decompress_lz77(self.rom, VF_TILES_OFF)
        self.gen_num_tiles = len(self.gen_tile_data) // 32
        self.gen_meta = self.rom[GEN_MT_OFF:GEN_MT_OFF + 640 * 16]
        self.vf_meta = self.rom[VF_MT_OFF:VF_MT_OFF + 43 * 16]
        # Load real cut-tree object sprite from pokefirered decomp (chr already reversata)
        self.cut_tree_sprite = self._load_cut_tree_sprite()

    def _apply_night_to_pals(self, pals):
        dark = []
        for pal in pals:
            nd = []
            for (r, g, b) in pal:
                nr = int(r * NIGHT_R)
                ng = int(g * NIGHT_G)
                nb = int(min(255, b * NIGHT_B + NIGHT_B_ADD))
                # also darken overall luminance slightly
                nd.append((nr, ng, nb))
            dark.append(nd)
        return dark

    def _load_cut_tree_sprite(self):
        """Load the authentic CUT-tree object sprite (16x16) from pokefirered decomp.

        The object is not a metatile but an OW sprite: graphics/object_events/pics/misc/cut_tree.png.
        We read the PNG at runtime from ../pokefirered (no static asset) and also apply night tint.
        """
        # try multiple candidate locations (REPO root + project sibling)
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "pokefirered", "graphics", "object_events", "pics", "misc", "cut_tree.png"),
            "/home/mf/Desktop/pokefirered/graphics/object_events/pics/misc/cut_tree.png",
        ]
        path = None
        for c in candidates:
            if os.path.exists(c):
                path = c
                break
        if not path:
            return None
        try:
            img = Image.open(path).convert("RGBA")
            # 64x16 sheet -> first 16x16 frame is idle tree
            frame = img.crop((0, 0, 16, 16))
            if NIGHT_MODE:
                # darken the sprite to match night lighting
                # per-pixel multiply
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
            return frame
        except Exception:
            return None

    def _load_palettes(self, offset, count=16):
        pals = []
        for p in range(count):
            colors = []
            for c in range(16):
                val = struct.unpack_from('<H', self.rom, offset + (p*16+c)*2)[0]
                r = (val & 0x1F) * 8
                g = ((val >> 5) & 0x1F) * 8
                b = ((val >> 10) & 0x1F) * 8
                colors.append((r, g, b))
            pals.append(colors)
        return pals

    def _get_tile(self, idx):
        if idx < self.gen_num_tiles:
            off = idx * 32
            if off + 32 > len(self.gen_tile_data):
                return np.zeros((8, 8), dtype=np.uint8)
            t = np.zeros((8, 8), dtype=np.uint8)
            for r in range(8):
                for c in range(4):
                    b = self.gen_tile_data[off + r*4 + c]
                    t[r, c*2] = b & 0xF
                    t[r, c*2+1] = (b >> 4) & 0xF
            return t
        else:
            idx2 = idx - self.gen_num_tiles
            off = idx2 * 32
            if off + 32 > len(self.vf_tile_data):
                return np.zeros((8, 8), dtype=np.uint8)
            t = np.zeros((8, 8), dtype=np.uint8)
            for r in range(8):
                for c in range(4):
                    b = self.vf_tile_data[off + r*4 + c]
                    t[r, c*2] = b & 0xF
                    t[r, c*2+1] = (b >> 4) & 0xF
            return t

    def _render_metatile(self, mt_id):
        if mt_id in self._mt_cache:
            return self._mt_cache[mt_id]
        if mt_id >= 0x280:
            local = mt_id - 0x280
            if local * 16 + 16 > len(self.vf_meta):
                return Image.new('RGBA', (16, 16), (255, 0, 255, 255))
            meta = self.vf_meta
            off = local * 16
        else:
            if mt_id * 16 + 16 > len(self.gen_meta):
                return Image.new('RGBA', (16, 16), (255, 0, 255, 255))
            meta = self.gen_meta
            off = mt_id * 16
        refs = struct.unpack_from('<8H', meta, off)
        result = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
        positions = [(0, 0), (8, 0), (0, 8), (8, 8)]
        for layer in range(2):
            for pi in range(4):
                ref = refs[layer * 4 + pi]
                tidx = ref & 0x3FF
                hf = (ref >> 10) & 1
                vfl = (ref >> 11) & 1
                pidx = (ref >> 12) & 0xF
                t = self._get_tile(tidx)
                if hf: t = np.fliplr(t)
                if vfl: t = np.flipud(t)
                pal = self.combined_pals[pidx]
                rgba = np.zeros((8, 8, 4), dtype=np.uint8)
                for y in range(8):
                    for x in range(8):
                        ci = int(t[y, x])
                        if ci == 0:
                            rgba[y, x] = (0, 0, 0, 0)
                        else:
                            r, g, b = pal[ci]
                            rgba[y, x] = (r, g, b, 255)
                img = Image.fromarray(rgba, 'RGBA')
                px, py = positions[pi]
                result.paste(img, (px, py), img)
        self._mt_cache[mt_id] = result
        return result

    def _forest_mt_id(self, layout, r, c):
        """Return aligned 3x3 huge-tree metatile so forest edges are never mid-cut.

        Classic bug: FOREST_PATTERN[r%3][c%3] tiles seamlessly only when the whole map is T.
        As soon as a clearing interrupts the forest, c%3 resumes in the middle of a tree (looks sliced).
        We instead anchor each contiguous T-run to its own left/top edge and force the bottom/right
        edge of each segment to always show the tree's bottom/right slice (so a 1- or 2-wide strip
        does not show a middle slice against grass - which looked 'frammentato').
        """
        row_str = layout[r]
        # left edge of this horizontal T-segment
        left = c
        while left > 0 and left - 1 < len(row_str) and row_str[left - 1] == 'T':
            left -= 1
        # top edge of vertical T-run at column c
        top = r
        while top > 0 and c < len(layout[top - 1]) and layout[top - 1][c] == 'T':
            top -= 1
        seg_col = c - left
        seg_row = r - top
        # Detect if this cell is at the right/bottom edge of its T-segment.
        # Those edges must show the rightmost/bottommost tree slice to look 'intero'.
        is_right = (c + 1 >= len(row_str) or row_str[c + 1] != 'T')
        is_bottom = (r + 1 >= len(layout) or c >= len(layout[r + 1]) or layout[r + 1][c] != 'T')
        col_idx = 2 if is_right else seg_col % 3
        row_idx = 2 if is_bottom else seg_row % 3
        # For segments narrower than 3, avoid showing middle slice alone: map col 0->0, 1->2 already does.
        # For height 1 strips (rare), showing bottom row (2) is more natural than top.
        return FOREST_PATTERN[row_idx][col_idx]

    def render_map(self, map_key, layout, output_path):
        """Render a single map layout to a PNG file."""
        if 'cave' in map_key:
            tile_map = {**TILE_MAP_DEFAULT, **TILE_MAP_CAVE}
        elif 'house' in map_key:
            tile_map = {**TILE_MAP_DEFAULT, **TILE_MAP_HOUSE}
        else:
            tile_map = TILE_MAP_DEFAULT

        rows = len(layout)
        cols = max(len(r) for r in layout) if layout else 0
        if rows == 0 or cols == 0:
            return False

        bg = Image.new('RGBA', (cols * 16, rows * 16), (0, 0, 0, 255))

        for r, row_str in enumerate(layout):
            for c, ch in enumerate(row_str):
                mt_id = tile_map.get(ch)
                if ch == 'T' and mt_id is None:
                    mt_id = self._forest_mt_id(layout, r, c)
                elif ch == 'C':
                    # 'C' was incorrectly rendered as 0x01C (wrong sprite). Real CUT tree is an object event,
                    # not a metatile. Render walkable grass underneath and overlay the authentic sprite later.
                    mt_id = 0x009 if 'cave' in map_key else 0x00D  # grass/ground gives correct grass under tree
                elif mt_id is None:
                    mt_id = 0x009
                tile_img = self._render_metatile(mt_id)
                bg.paste(tile_img, (c * 16, r * 16), tile_img)
                if ch == 'C' and getattr(self, 'cut_tree_sprite', None) is not None:
                    # Center 16x16 object sprite on the 16x16 metatile (object is exactly 16x16)
                    bg.paste(self.cut_tree_sprite, (c * 16, r * 16), self.cut_tree_sprite)

        # Night post-process: slight additional vignette / dark overlay for forest maps
        if NIGHT_MODE:
            # Multiply with a dark indigo overlay (keeps moonlit blue tint already in palette)
            overlay = Image.new('RGBA', bg.size, (18, 20, 45, 38))
            bg = Image.alpha_composite(bg.convert('RGBA'), overlay)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        bg.save(output_path)
        return True

    def render_all_maps(self, maps_json_path, output_dir):
        """Render all maps from maps.json."""
        with open(maps_json_path) as f:
            maps = json.load(f)

        count = 0
        for map_key, map_data in maps.items():
            bg_name = f"{map_key}_rendered.png"
            out_path = os.path.join(output_dir, bg_name)
            if os.path.exists(out_path):
                continue
            layout = map_data.get("layout", [])
            if not layout:
                continue
            if self.render_map(map_key, layout, out_path):
                count += 1

        if count:
            print(f"[map_renderer] Rendered {count} map backgrounds from ROM")
        return count


def render_maps_from_rom(rom_path, maps_json_path, output_dir):
    """Convenience function called by asset_generator."""
    renderer = MapRenderer(rom_path)
    return renderer.render_all_maps(maps_json_path, output_dir)
