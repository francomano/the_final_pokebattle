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

TILE_MAP_DEFAULT = {
    'T': None,       # Forest pattern (special handling)
    'M': 0x071,      # Mountain rock
    'G': 0x0A9,      # Cave entrance (dark)
    'W': 0x003,      # Sign
    'N': 0x003,      # Sign post (with collision)
    'C': 0x01C,      # Cut tree (green)
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
        self.gen_tile_data = decompress_lz77(self.rom, GEN_TILES_OFF)
        self.vf_tile_data = decompress_lz77(self.rom, VF_TILES_OFF)
        self.gen_num_tiles = len(self.gen_tile_data) // 32
        self.gen_meta = self.rom[GEN_MT_OFF:GEN_MT_OFF + 640 * 16]
        self.vf_meta = self.rom[VF_MT_OFF:VF_MT_OFF + 43 * 16]

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
                if mt_id is None and ch == 'T':
                    mt_id = FOREST_PATTERN[r % 3][c % 3]
                elif mt_id is None:
                    mt_id = 0x009
                tile_img = self._render_metatile(mt_id)
                bg.paste(tile_img, (c * 16, r * 16), tile_img)

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
