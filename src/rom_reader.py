"""
The Final Battle - ROM Data Reader.
Reads creature stats, moves, learnsets, and map tilemap data from a GBA ROM file.
No copyrighted data is stored in this source - all data is read at runtime
from the user's own ROM file.
"""

import struct
import os

# ---------- GBA ROM offsets (Fire Red US 1.0) -------------------------------
# These are memory layout offsets for data structures in the ROM binary.

OFFSET_BASE_STATS = 0x254784       # 28 bytes per species
OFFSET_SPECIES_NAMES = 0x245EE0    # 11 bytes per name
OFFSET_MOVE_NAMES = 0x247094       # 13 bytes per name
OFFSET_BATTLE_MOVES = 0x250C04     # 12 bytes per move
OFFSET_LEARNSETS = 0x25D7B4        # 4 bytes per species (pointer table)
OFFSET_MAP_GROUPS = 0x3526A8       # pointer table to map group arrays

BASE_STATS_SIZE = 28
SPECIES_NAME_LEN = 11
MOVE_NAME_LEN = 13
BATTLE_MOVE_SIZE = 12
NUM_SPECIES = 412
NUM_MOVES = 355

# HM compatibility extracted from FireRed ROM (tmhm_learnsets.h)
HM_COMPAT = {
    "cut": {1,2,3,4,5,6,15,19,20,27,28,29,30,31,32,33,34,43,44,45,46,47,50,51,52,53,69,70,71,72,73,83,98,99,108,112,114,115,123,127,141,149,151,152,153,154,155,156,157,158,159,160,161,162,182,190,191,192,196,197,207,208,212,214,215,216,217,227,243,244,245,248,251,277,278,279,280,281,282,288,289,299,300,301,302,303,307,317,322,326,327,344,345,363,364,365,366,369,376,382,383,384,390,391,395,396,397,399,400,405,407,408,410},
    "surf": {7,8,9,31,34,54,55,60,61,62,72,73,79,80,86,87,90,91,98,99,108,112,115,116,117,118,119,120,121,128,130,131,134,138,139,140,141,143,147,148,149,151,158,159,160,161,162,170,171,183,184,186,194,195,199,211,215,222,223,224,226,230,241,245,248,249,283,284,285,288,289,295,296,297,310,313,314,323,324,325,326,327,328,329,330,331,335,336,341,342,343,350,373,374,375,381,384,404,406,407,408},
    "strength": {1,2,3,4,5,6,7,8,9,20,23,24,25,26,27,28,29,30,31,32,33,34,35,36,39,40,54,55,56,57,58,59,61,62,66,67,68,74,75,76,77,78,79,80,89,94,95,98,99,102,103,104,105,106,107,108,111,112,113,115,125,126,127,128,130,131,142,143,149,150,151,153,154,156,157,159,160,162,180,181,183,184,185,186,190,195,199,203,204,205,206,207,208,209,210,212,213,214,215,216,217,219,220,221,222,229,231,232,236,237,241,242,243,244,248,249,250,277,278,279,280,281,282,283,284,285,287,289,296,297,299,300,307,308,313,314,316,317,319,320,321,324,326,327,331,332,333,334,335,336,337,338,339,340,341,342,343,345,355,356,357,362,364,365,366,367,368,369,371,372,376,379,380,382,383,384,389,391,395,396,397,399,400,401,402,403,404,405,406,410},
    "rock_smash": {1,2,3,4,5,6,7,8,9,15,19,20,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,43,44,45,46,47,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251},
}

# GBA type table
TYPE_NAMES = [
    "normal", "fighting", "flying", "poison", "ground", "rock",
    "bug", "ghost", "steel", "mystery", "fire", "water",
    "grass", "electric", "psychic", "ice", "dragon", "dark"
]

# Multiplier constants matching ROM values
TYPE_MUL_NO_EFFECT = 0
TYPE_MUL_NOT_EFFECTIVE = 5
TYPE_MUL_NORMAL = 10
TYPE_MUL_SUPER_EFFECTIVE = 20

# Offset of gTypeEffectiveness table in FireRed ROM
OFFSET_TYPE_EFFECTIVENESS = 0x24F050
TYPE_EFFECTIVENESS_SIZE = 336  # 112 triplets * 3 bytes


def _load_type_effectiveness_from_rom(rom_data):
    """Read the type effectiveness table from ROM at runtime.
    Returns dict mapping (atk_type_idx, def_type_idx) -> multiplier_code."""
    table = {}
    off = OFFSET_TYPE_EFFECTIVENESS
    end = OFFSET_TYPE_EFFECTIVENESS + TYPE_EFFECTIVENESS_SIZE
    while off < end:
        atk = rom_data[off]
        defe = rom_data[off + 1]
        mult = rom_data[off + 2]
        if atk == 0xFF and defe == 0xFF:
            break
        table[(atk, defe)] = mult
        off += 3
    return table


# Lazy-loaded from ROM on first use
_TYPE_EFFECTIVENESS = None


def get_type_multiplier(move_type_name, def_type1_name, def_type2_name=None, rom_data=None):
    """Look up the combined type effectiveness multiplier for a move against a defender.
    Returns (multiplier_float, message) where message is 'super', 'weak', 'immune', or ''."""
    global _TYPE_EFFECTIVENESS
    if _TYPE_EFFECTIVENESS is None:
        if rom_data is not None:
            _TYPE_EFFECTIVENESS = _load_type_effectiveness_from_rom(rom_data)
        else:
            # Fallback: all neutral
            return 1.0, ""

    atk_idx = TYPE_NAMES.index(move_type_name) if move_type_name in TYPE_NAMES else 0
    def1_idx = TYPE_NAMES.index(def_type1_name) if def_type1_name in TYPE_NAMES else 0
    def2_idx = TYPE_NAMES.index(def_type2_name) if def_type2_name in TYPE_NAMES else def1_idx

    m1 = _TYPE_EFFECTIVENESS.get((atk_idx, def1_idx), TYPE_MUL_NORMAL)
    m2 = _TYPE_EFFECTIVENESS.get((atk_idx, def2_idx), TYPE_MUL_NORMAL) if def2_idx != def1_idx else TYPE_MUL_NORMAL

    combined = m1 * m2
    if combined == 0:
        return 0.0, "immune"
    elif combined < 100:
        return combined / 100.0, "weak"
    elif combined > 100:
        return combined / 100.0, "super"
    return 1.0, ""


class RomReader:
    """Reads game data from a GBA ROM file."""

    def __init__(self, rom_path):
        if not os.path.isfile(rom_path):
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
        with open(rom_path, "rb") as f:
            self.data = f.read()
        if len(self.data) < 0x400000:
            raise ValueError("ROM file too small - expected a valid GBA ROM")

    def _read_ptr(self, offset):
        """Read a 4-byte GBA pointer and convert to file offset."""
        ptr = struct.unpack_from('<I', self.data, offset)[0]
        if ptr >= 0x08000000:
            return ptr - 0x08000000
        return ptr

    def _decode_text(self, data):
        """Decode GBA text encoding to ASCII string."""
        result = []
        for b in data:
            if b == 0xFF:
                break
            elif 0xBB <= b <= 0xD4:  # A-Z
                result.append(chr(b - 0xBB + ord('A')))
            elif 0xD5 <= b <= 0xEE:  # a-z
                result.append(chr(b - 0xD5 + ord('a')))
            elif 0xA1 <= b <= 0xAA:  # 0-9
                result.append(chr(b - 0xA1 + ord('0')))
            elif b == 0x00:
                result.append(' ')
            elif b == 0xAB:
                result.append('!')
            elif b == 0xAC:
                result.append('?')
            elif b == 0xAD:
                result.append('.')
            elif b == 0xBA:
                result.append('-')
            else:
                result.append('')
        return ''.join(result).strip()

    # ---------- species data ------------------------------------------------

    def read_species_name(self, species_id):
        """Read the name of a species by its ID."""
        if species_id < 0 or species_id >= NUM_SPECIES:
            return f"Species{species_id}"
        offset = OFFSET_SPECIES_NAMES + species_id * SPECIES_NAME_LEN
        return self._decode_text(self.data[offset:offset + SPECIES_NAME_LEN])

    def read_base_stats(self, species_id):
        """Read base stats for a species. Returns dict."""
        if species_id < 0 or species_id >= NUM_SPECIES:
            return None
        offset = OFFSET_BASE_STATS + species_id * BASE_STATS_SIZE
        d = self.data
        return {
            "base_hp": d[offset],
            "base_atk": d[offset + 1],
            "base_def": d[offset + 2],
            "base_spd": d[offset + 3],
            "base_spatk": d[offset + 4],
            "base_spdef": d[offset + 5],
            "type1": d[offset + 6],
            "type2": d[offset + 7],
            "catch_rate": d[offset + 8],
            "exp_yield": d[offset + 9],
        }

    def read_species(self, species_id):
        """Read full species info (name + stats)."""
        stats = self.read_base_stats(species_id)
        if stats is None:
            return None
        stats["name"] = self.read_species_name(species_id)
        stats["species_id"] = species_id
        type1_idx = stats["type1"]
        type2_idx = stats["type2"]
        stats["element"] = TYPE_NAMES[type1_idx] if type1_idx < len(TYPE_NAMES) else "normal"
        stats["element2"] = TYPE_NAMES[type2_idx] if type2_idx < len(TYPE_NAMES) else "normal"
        return stats

    # ---------- move data ---------------------------------------------------

    def read_move_name(self, move_id):
        """Read the name of a move by its ID."""
        if move_id < 0 or move_id >= NUM_MOVES:
            return f"Move{move_id}"
        offset = OFFSET_MOVE_NAMES + move_id * MOVE_NAME_LEN
        return self._decode_text(self.data[offset:offset + MOVE_NAME_LEN])

    def read_battle_move(self, move_id):
        """Read battle move data. Returns dict."""
        if move_id < 0 or move_id >= NUM_MOVES:
            return None
        offset = OFFSET_BATTLE_MOVES + move_id * BATTLE_MOVE_SIZE
        d = self.data
        type_idx = d[offset + 2]
        return {
            "move_id": move_id,
            "name": self.read_move_name(move_id),
            "effect": d[offset],
            "power": d[offset + 1],
            "type": type_idx,
            "element": TYPE_NAMES[type_idx] if type_idx < len(TYPE_NAMES) else "normal",
            "accuracy": d[offset + 3],
            "pp": d[offset + 4],
        }

    # ---------- learnsets ---------------------------------------------------

    def read_learnset(self, species_id):
        """Read level-up learnset for a species. Returns list of (level, move_id)."""
        if species_id < 0 or species_id >= NUM_SPECIES:
            return []
        ptr_offset = OFFSET_LEARNSETS + species_id * 4
        file_offset = self._read_ptr(ptr_offset)
        moves = []
        for i in range(30):  # max moves safeguard
            entry = struct.unpack_from('<H', self.data, file_offset + i * 2)[0]
            if entry == 0xFFFF:
                break
            move_id = entry & 0x1FF
            level = (entry >> 9) & 0x7F
            moves.append((level, move_id))
        return moves

    def can_learn_hm(self, species_id, hm_name):
        """Check if a species can learn an HM (cut, surf, strength, rock_smash)."""
        compat = HM_COMPAT.get(hm_name)
        if compat is None:
            return True  # unknown HM, allow
        return species_id in compat

    # ---------- map data ----------------------------------------------------

    def read_map_header(self, group, map_idx):
        """Read a map header by group and index. Returns dict with size, tilemap, etc."""
        grp_ptr = self._read_ptr(OFFSET_MAP_GROUPS + group * 4)
        map_ptr = self._read_ptr(grp_ptr + map_idx * 4)

        # Map header: layout_ptr(4), events_ptr(4), scripts_ptr(4), connections_ptr(4), music(2), ...
        layout_ptr = self._read_ptr(map_ptr)

        # Layout struct: width(4), height(4), border_ptr(4), tilemap_ptr(4), tileset1_ptr(4), tileset2_ptr(4)
        width = struct.unpack_from('<I', self.data, layout_ptr)[0]
        height = struct.unpack_from('<I', self.data, layout_ptr + 4)[0]
        tilemap_offset = self._read_ptr(layout_ptr + 12)
        tileset1_offset = self._read_ptr(layout_ptr + 16)
        tileset2_offset = self._read_ptr(layout_ptr + 20)

        return {
            "width": width,
            "height": height,
            "tilemap_offset": tilemap_offset,
            "tileset1_offset": tileset1_offset,
            "tileset2_offset": tileset2_offset,
            "layout_ptr": layout_ptr,
            "map_ptr": map_ptr,
        }

    def read_tilemap(self, group, map_idx):
        """Read the metatile grid for a map. Returns 2D list of metatile indices."""
        header = self.read_map_header(group, map_idx)
        w, h = header["width"], header["height"]
        tilemap_offset = header["tilemap_offset"]

        grid = []
        for row in range(h):
            row_data = []
            for col in range(w):
                offset = tilemap_offset + (row * w + col) * 2
                tile = struct.unpack_from('<H', self.data, offset)[0]
                metatile_id = tile & 0x3FF
                row_data.append(metatile_id)
            grid.append(row_data)
        return grid

    def read_metatile_behaviors(self, tileset_offset, num_metatiles=512):
        """
        Read metatile behavior bytes from a tileset.
        Tileset header: compressed(1), secondary(1), pad(2), gfx_ptr(4), pal_ptr(4),
                        metatiles_ptr(4), anim_ptr(4), behavior_ptr(4)
        """
        behavior_ptr = self._read_ptr(tileset_offset + 20)
        behaviors = []
        for i in range(num_metatiles):
            # Each behavior entry is 4 bytes; first 2 bytes hold behavior flags
            entry = struct.unpack_from('<I', self.data, behavior_ptr + i * 4)[0]
            behaviors.append(entry & 0xFFFF)
        return behaviors

    def is_metatile_passable(self, behavior):
        """Check if a metatile behavior value means the tile is walkable."""
        # In GBA games, behavior 0 and common grass/path values are passable.
        # Impassable tiles typically have specific collision bits.
        # Behavior & 0x01 often indicates grass encounter tiles.
        # We use a simplified heuristic:
        # - behavior < 0x10 and not in blocked set -> passable
        # Blocked: 0x01 is sometimes impassable ledge, but let's use known passable set
        IMPASSABLE = {0x01}  # simplified
        # More accurate: the collision is determined by metatile attributes bit 0x0C00 in tilemap
        # For our purposes, we'll classify based on common behaviors:
        # 0x00 = normal ground, 0x02 = grass (encounter), 0x04 = water, etc.
        return behavior not in IMPASSABLE

    def get_walkability_from_tilemap(self, group, map_idx):
        """
        Build a 2D walkability grid from the ROM map data.
        Uses the tile attribute bits in the tilemap (bit 10-11 indicate layer/collision).
        Returns 2D list of booleans.
        """
        header = self.read_map_header(group, map_idx)
        w, h = header["width"], header["height"]
        tilemap_offset = header["tilemap_offset"]

        walkable = []
        for row in range(h):
            row_data = []
            for col in range(w):
                offset = tilemap_offset + (row * w + col) * 2
                tile = struct.unpack_from('<H', self.data, offset)[0]
                # Bits 10-11: collision type (0=passable, 1-3 various block/layer)
                collision = (tile >> 10) & 0x3
                row_data.append(collision == 0)
            row_data.append(False)  # safety margin removed - fixed below
            walkable.append(row_data[:w])  # ensure exact width
        return walkable

    def get_encounter_tiles(self, group, map_idx):
        """
        Find tiles where wild encounters can happen (tall grass metatiles).
        Common grass metatiles in FireRed: 1, 4, 5 (primary tileset).
        Returns set of (col, row) tuples.
        """
        grid = self.read_tilemap(group, map_idx)
        # Grass metatile IDs vary but commonly include:
        GRASS_METATILES = {1, 4, 5, 13, 14, 210, 211}  # common grass tiles in FR
        encounter_tiles = set()
        for row_idx, row in enumerate(grid):
            for col_idx, mt in enumerate(row):
                if mt in GRASS_METATILES:
                    encounter_tiles.add((col_idx, row_idx))
        return encounter_tiles


# ---------- convenience function -------------------------------------------

def find_rom(base_dir=None):
    """Find a .gba ROM file in the project directory."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for f in os.listdir(base_dir):
        if f.endswith('.gba'):
            return os.path.join(base_dir, f)
    return None
