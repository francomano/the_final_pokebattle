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

# The secondary tilesets sit consecutively in the ROM tileset-header table.
# These are the FireRed (U) 1.0 entries for Viridian City (index 2) and
# Viridian Forest (index 34).  Keeping offsets here means the artwork still
# comes exclusively from the player supplied ROM at runtime.
VIRIDIAN_CITY_TILES_OFF = 0x26D9C0
VIRIDIAN_CITY_PAL_OFF = 0x26DFC0
VIRIDIAN_CITY_MT_OFF = 0x2A2FBC
# Mt. Ember's exterior uses the Sevii Islands 1-3 secondary tileset.
SEVII_MOUNTAIN_TILES_OFF = 0x298B70
SEVII_MOUNTAIN_PAL_OFF = 0x299AA4
SEVII_MOUNTAIN_MT_OFF = 0x2CD1CC
BUILDING_TILES_OFF = 0x277894
BUILDING_PAL_OFF = 0x277A5C
BUILDING_MT_OFF = 0x2B3524
MT_EMBER_TILES_OFF = 0x29532C
MT_EMBER_PAL_OFF = 0x2967D4
MT_EMBER_MT_OFF = 0x2CA454

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
    'Q': 0x0A8,      # Cave entrance left shoulder
    'P': 0x0AA,      # Cave entrance right shoulder
    # Upper three-piece cap for the General cave entrance.  It must be drawn
    # with these matching metatiles rather than the unrelated mountain tile.
    'U': 0x0A0,      # Cave roof left
    'V': 0x0A1,      # Cave roof centre
    'X': 0x0A2,      # Cave roof right
    'Y': 0x098,      # Cave crown left
    'Z': 0x099,      # Cave crown centre
    '!': 0x09A,      # Cave crown right
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
    'z': 0x009,      # Sand/desert floor (fallback for non-desert maps)
    'F': 0x079,      # Fence/wall (dark)
    'H': 0x05D,      # House wall center
    '[': 0x05C,      # House wall left
    ']': 0x05E,      # House wall right
    '^': 0x048,      # Roof left
    '~': 0x049,      # Roof center
    '`': 0x04A,      # Roof right
}

# A normal Kanto house is made from the Viridian City secondary tileset, not
# from the general/forest tileset.  The old ^/~ /[ /H characters pointed at
# unrelated general metatiles, which is why the roofs looked like a flat brick
# slab.  The compact symbols below form the real facade (the door is
# still the shared General door metatile).
CITY_HOUSE_TILES = {
    'q': ('viridian_city', 0x280), 'w': ('viridian_city', 0x281),
    'e': ('viridian_city', 0x282), 'r': ('viridian_city', 0x283),
    't': ('viridian_city', 0x284), 'a': ('viridian_city', 0x285),
    's': ('viridian_city', 0x288), 'f': ('viridian_city', 0x289),
    'k': ('viridian_city', 0x28A), 'l': ('viridian_city', 0x28B),
    'x': ('viridian_city', 0x290), 'v': ('viridian_city', 0x291),
    'u': ('viridian_city', 0x292), 'i': ('viridian_city', 0x293),
    'p': ('viridian_city', 0x294), 'y': ('viridian_city', 0x28D),
    '1': ('viridian_city', 0x298), '2': ('viridian_city', 0x299),
    '3': ('viridian_city', 0x29A), '4': ('viridian_city', 0x29B),
    '5': ('viridian_city', 0x29C), '6': ('viridian_city', 0x2A0),
    '7': ('viridian_city', 0x2A2), '8': ('viridian_city', 0x2A3),
    '9': ('viridian_city', 0x2A4),
    '0': ('viridian_city', 0x284),
}

# Desert-specific tile map: uses real sand/rock metatiles from ROM
TILE_MAP_DESERT = {
    'T': 0x071,      # Mountain rock
    'M': 0x073,      # Mountain wall border (dark face)
    '.': 0x115,      # Desert sand floor
    'z': 0x115,      # Desert sand floor (walkable)
    'r': 0x0D9,      # Rocky ground
    'R': 0x115,      # Breakable rock (object sprite overlay on sand)
    'g': 0x115,      # Desert vegetation (sand, encounters)
    'd': 0x0D9,      # Path/dirt (gravel)
    'w': 0x12B,      # Water/swamp
    'A': 0x0DC,      # Arena floor (earthy ground)
    'F': 0x079,      # Fence/wall
    'D': 0x03D,      # Door
    'N': 0x003,      # Sign post
    's': 0x115,      # Spawn point 1 (sand)
    'S': 0x115,      # Spawn point 2 (sand)
    'B': 0x0D9,      # Bridge/path
    'W': 0x003,      # Sign
    'E': 0x115,      # Encounter sand
    'I': 0x115,      # Item on sand
    'C': 0x115,      # Cuttable (render as sand)
    'b': 0x0B7,      # Boulder (pushable, Strength HM)
    'K': 0x0A9,      # Cave entrance (dark opening)
    'Q': 0x0A8,      # Cave entrance left
    'P': 0x0AA,      # Cave entrance right
    'O': 0x0DC,      # Shelter interior floor
    'm': 0x070,      # Mountain face (internal, different from border)
    'c': 0x0D0,      # Rocky ground
    'v': 0x0D6,      # Cliff edge on desert
    'H': 0x05D,      # House wall center (same as forest house)
    'h': 0x05C,      # House wall left (same as forest house)
    'j': 0x05E,      # House wall right (same as forest house)
    '^': 0x048,      # Roof left (brown)
    '~': 0x049,      # Roof center (brown)
    '`': 0x04A,      # Roof right (brown)
    'o': 0x070,      # Interior floor
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
    'M': 0x03C,      # Interior wall (alias for market)
    '.': 0x030,      # Interior tiled floor (not outdoor grass)
    'o': 0x03D,      # Visible, walkable interior exit threshold
    'W': 0x003,      # Sign/bookshelf
    'N': 0x003,      # Sign post (with collision)
    # A doorway has to remain visible: portals are walkable, but rendering them
    # as plain floor made the player appear to be stopped by an invisible exit.
    'D': 0x03D,
    'd': 0x030,      # Floor
    'I': 0x030,      # Item (on floor)
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
        self.gen_tile_data = decompress_lz77(self.rom, GEN_TILES_OFF)
        self.gen_num_tiles = len(self.gen_tile_data) // 32
        self.gen_meta = self.rom[GEN_MT_OFF:GEN_MT_OFF + 640 * 16]
        self.secondary_tilesets = {}
        self._load_secondary_tileset('viridian_forest', VF_TILES_OFF, VF_PAL_OFF, VF_MT_OFF, 43)
        self._load_secondary_tileset('viridian_city', VIRIDIAN_CITY_TILES_OFF,
                                     VIRIDIAN_CITY_PAL_OFF, VIRIDIAN_CITY_MT_OFF, 64)
        self._load_secondary_tileset('sevii_mountains', SEVII_MOUNTAIN_TILES_OFF,
                                     SEVII_MOUNTAIN_PAL_OFF, SEVII_MOUNTAIN_MT_OFF, 512)
        self._load_secondary_tileset('building', BUILDING_TILES_OFF, BUILDING_PAL_OFF,
                                     BUILDING_MT_OFF, 256)
        self._load_secondary_tileset('mt_ember', MT_EMBER_TILES_OFF, MT_EMBER_PAL_OFF,
                                     MT_EMBER_MT_OFF, 224)
        self.cut_tree_sprite = self._load_cut_tree_sprite()
        # Load rock smash object sprite (4 frames for animation)
        self.rock_smash_frames = self._load_rock_smash_sprite()

    def _load_secondary_tileset(self, name, tiles_offset, palette_offset, metatile_offset, metatile_count):
        """Load a secondary tileset and merge its palettes with General."""
        pals = list(self.gen_pals)
        secondary_pals = self._load_palettes(palette_offset)
        for i in range(7, 13):
            if i < len(secondary_pals):
                pals[i] = secondary_pals[i]
        if NIGHT_MODE:
            pals = self._apply_night_to_pals(pals)
        self.secondary_tilesets[name] = {
            'pals': pals,
            'tiles': decompress_lz77(self.rom, tiles_offset),
            'meta': self.rom[metatile_offset:metatile_offset + metatile_count * 16],
        }

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
        """Load cut-tree object sprite from assets/ (generated from sprites.json at startup)."""
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "tile_cut_tree_0.png"),
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
            if NIGHT_MODE:
                px = img.load()
                for y in range(img.height):
                    for x in range(img.width):
                        r, g, b, a = px[x, y]
                        if a == 0:
                            continue
                        nr = int(r * NIGHT_R)
                        ng = int(g * NIGHT_G)
                        nb = int(min(255, b * NIGHT_B + NIGHT_B_ADD))
                        px[x, y] = (nr, ng, nb, a)
            return img
        except Exception:
            return None

    def _load_rock_smash_sprite(self):
        """Load rock smash object sprite frames from assets/ (generated from sprites.json)."""
        frames = []
        for i in range(4):
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", f"tile_rock_smash_{i}.png")
            if os.path.exists(path):
                try:
                    img = Image.open(path).convert("RGBA")
                    if NIGHT_MODE:
                        px = img.load()
                        for y in range(img.height):
                            for x in range(img.width):
                                r, g, b, a = px[x, y]
                                if a == 0:
                                    continue
                                nr = int(r * NIGHT_R)
                                ng = int(g * NIGHT_G)
                                nb = int(min(255, b * NIGHT_B + NIGHT_B_ADD))
                                px[x, y] = (nr, ng, nb, a)
                    frames.append(img)
                except Exception:
                    pass
        return frames if frames else None

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

    def _get_tile(self, idx, secondary='viridian_forest'):
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
            secondary_data = self.secondary_tilesets[secondary]['tiles']
            if off + 32 > len(secondary_data):
                return np.zeros((8, 8), dtype=np.uint8)
            t = np.zeros((8, 8), dtype=np.uint8)
            for r in range(8):
                for c in range(4):
                    b = secondary_data[off + r*4 + c]
                    t[r, c*2] = b & 0xF
                    t[r, c*2+1] = (b >> 4) & 0xF
            return t

    def _render_metatile(self, mt_id, secondary='viridian_forest'):
        cache_key = (secondary, mt_id)
        if cache_key in self._mt_cache:
            return self._mt_cache[cache_key]
        if mt_id >= 0x280:
            local = mt_id - 0x280
            tileset = self.secondary_tilesets[secondary]
            if local * 16 + 16 > len(tileset['meta']):
                return Image.new('RGBA', (16, 16), (255, 0, 255, 255))
            meta = tileset['meta']
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
                t = self._get_tile(tidx, secondary)
                if hf: t = np.fliplr(t)
                if vfl: t = np.flipud(t)
                pal = self.secondary_tilesets[secondary]['pals'][pidx]
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
        self._mt_cache[cache_key] = result
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

    @staticmethod
    def _is_water(layout, row, col):
        return (0 <= row < len(layout)
                and 0 <= col < len(layout[row])
                and layout[row][col] == 'w')

    @staticmethod
    def _desert_mountain_mt_id(layout, row, col):
        """Select Mt. Ember's mountain metatiles, with matched edge pieces."""
        def mountain(y, x):
            return 0 <= y < len(layout) and 0 <= x < len(layout[y]) and layout[y][x] == 'M'

        north = mountain(row - 1, col)
        south = mountain(row + 1, col)
        west = mountain(row, col - 1)
        east = mountain(row, col + 1)
        # 351/353 are the paired Mt. Ember exterior rock faces.  They are
        # intentionally used as a matched checker rather than treating the
        # unrelated General cliff/boulder tiles as mountains.
        return ('sevii_mountains', 0x351 if (row + col) % 2 else 0x353)

    @staticmethod
    def _city_house_mt_id(layout, row, col, ch):
        """Map facade symbols only inside a q-anchored house rectangle.

        ``w`` is also the global water symbol, so adding the facade dictionary
        to an entire map turned every river into a roof tile.
        """
        for y, line in enumerate(layout):
            for x, anchor in enumerate(line):
                if anchor == 'q' and x <= col < x + 5 and y <= row < y + 4:
                    return CITY_HOUSE_TILES.get(ch)
        return None

    def render_map(self, map_key, layout, output_path):
        """Render a single map layout to a PNG file."""
        if 'cave' in map_key:
            tile_map = {**TILE_MAP_DEFAULT, **TILE_MAP_CAVE}
        elif 'house' in map_key or 'market' in map_key:
            tile_map = {**TILE_MAP_DEFAULT, **TILE_MAP_HOUSE}
        elif 'desert' in map_key or 'rock' in map_key:
            tile_map = {**TILE_MAP_DEFAULT, **TILE_MAP_DESERT}
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
                if (city_house := self._city_house_mt_id(layout, r, c, ch)) is not None:
                    mt_id = city_house
                elif ch == 'T' and mt_id is None:
                    mt_id = self._forest_mt_id(layout, r, c)
                elif ch in 'Mm' and ('desert' in map_key or 'rock' in map_key):
                    mt_id = self._desert_mountain_mt_id(layout, r, c)
                elif ch == 'C':
                    # 'C' was incorrectly rendered as 0x01C (wrong sprite). Real CUT tree is an object event,
                    # not a metatile. Render walkable grass underneath and overlay the authentic sprite later.
                    mt_id = 0x009 if 'cave' in map_key else 0x00D  # grass/ground gives correct grass under tree
                elif mt_id is None:
                    mt_id = 0x009
                secondary = 'viridian_forest'
                if isinstance(mt_id, tuple):
                    secondary, mt_id = mt_id
                tile_img = self._render_metatile(mt_id, secondary)
                bg.paste(tile_img, (c * 16, r * 16), tile_img)
                if ch == 'C' and getattr(self, 'cut_tree_sprite', None) is not None:
                    # Center 16x16 object sprite on the 16x16 metatile (object is exactly 16x16)
                    bg.paste(self.cut_tree_sprite, (c * 16, r * 16), self.cut_tree_sprite)
                elif ch == 'R' and getattr(self, 'rock_smash_frames', None) is not None:
                    # Breakable rock: overlay first frame (idle rock) on sand
                    bg.paste(self.rock_smash_frames[0], (c * 16, r * 16), self.rock_smash_frames[0])

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
            bg_path = map_data.get("background", "")
            if not bg_path:
                continue
            # ``background`` is relative to the asset directory.  Using the
            # parent of output_dir wrote duplicate generated folders at the
            # repository root and left the in-game assets stale.
            out_path = os.path.join(output_dir, bg_path)
            layout = map_data.get("layout", [])
            if not layout:
                continue
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            if self.render_map(map_key, layout, out_path):
                count += 1

        if count:
            print(f"[map_renderer] Rendered {count} map backgrounds from ROM")
        return count


def render_maps_from_rom(rom_path, maps_json_path, output_dir):
    """Convenience function called by asset_generator."""
    renderer = MapRenderer(rom_path)
    return renderer.render_all_maps(maps_json_path, output_dir)
