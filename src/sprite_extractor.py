"""
The Final Battle - Sprite Extractor.
Extracts creature sprites, palettes, and tileset graphics from the GBA ROM.
Saves them as PNG files in a local cache directory.
No copyrighted data in source - only extraction logic and structural offsets.
"""

import struct
import os
import sys

# ---------- ROM offsets (Fire Red US 1.0) -----------------------------------
OFFSET_FRONT_PICS = 0x2350AC    # 8 bytes per species (ptr, size_tag)
OFFSET_BACK_PICS = 0x235E54     # 8 bytes per species
OFFSET_PALETTES = 0x23730C      # 8 bytes per species (ptr, tag)
OFFSET_SHINY_PALS = 0x2385CC    # shiny palettes
OFFSET_TILESET_HDR = 0x2D4A94   # primary outdoor tileset header
OFFSET_OW_SPRITES = 0x39FDB0    # overworld sprite table (approximate)

NUM_SPECIES = 412
SPRITE_SIZE_4BPP = 2048         # 64x64 pixels at 4bpp
SPRITE_WH = 64                  # sprite width/height in pixels

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- LZ77 decompression ---------------------------------------------

def decompress_lz77(data, offset):
    """Decompress GBA LZ77 (type 0x10) data."""
    if offset >= len(data) or data[offset] != 0x10:
        return None
    decompressed_size = struct.unpack_from('<I', data, offset)[0] >> 8
    if decompressed_size == 0 or decompressed_size > 0x40000:
        return None
    result = bytearray()
    src = offset + 4
    try:
        while len(result) < decompressed_size:
            if src >= len(data):
                break
            flags = data[src]; src += 1
            for bit in range(8):
                if len(result) >= decompressed_size:
                    break
                if flags & (0x80 >> bit):
                    if src + 1 >= len(data):
                        return bytes(result)
                    byte1 = data[src]; byte2 = data[src + 1]; src += 2
                    length = (byte1 >> 4) + 3
                    disp = ((byte1 & 0x0F) << 8) | byte2
                    for _ in range(length):
                        if len(result) >= decompressed_size:
                            break
                        pos = len(result) - disp - 1
                        if pos < 0:
                            result.append(0)
                        else:
                            result.append(result[pos])
                else:
                    if src >= len(data):
                        return bytes(result)
                    result.append(data[src]); src += 1
    except (IndexError, OverflowError):
        pass
    return bytes(result[:decompressed_size])


# ---------- palette parsing -------------------------------------------------

def parse_gba_palette(pal_data):
    """Parse 32 bytes of GBA RGB555 palette into list of (R,G,B,A) tuples."""
    colors = []
    for i in range(0, min(32, len(pal_data)), 2):
        c = struct.unpack_from('<H', pal_data, i)[0]
        r = (c & 0x1F) << 3
        g = ((c >> 5) & 0x1F) << 3
        b = ((c >> 10) & 0x1F) << 3
        colors.append((r, g, b, 255))
    # color 0 is transparent
    if colors:
        colors[0] = (0, 0, 0, 0)
    return colors


# ---------- 4bpp tile to pixels ---------------------------------------------

def decode_4bpp_sprite(tile_data, width=64, height=64, palette=None):
    """
    Decode 4bpp tiled GBA sprite data into RGBA pixel array.
    GBA sprites are stored in 8x8 tiles, in row-major tile order.
    Returns flat list of (R,G,B,A) tuples, row by row.
    """
    if palette is None:
        # grayscale fallback
        palette = [(i * 17, i * 17, i * 17, 255 if i > 0 else 0) for i in range(16)]

    pixels = [(0, 0, 0, 0)] * (width * height)
    tiles_per_row = width // 8
    tile_idx = 0
    byte_idx = 0

    for tile_y in range(height // 8):
        for tile_x in range(tiles_per_row):
            for py in range(8):
                for px in range(0, 8, 2):
                    if byte_idx >= len(tile_data):
                        return pixels
                    byte = tile_data[byte_idx]; byte_idx += 1
                    # low nybble first
                    pix_x = tile_x * 8 + px
                    pix_y = tile_y * 8 + py
                    idx_lo = byte & 0x0F
                    idx_hi = (byte >> 4) & 0x0F
                    pos1 = pix_y * width + pix_x
                    pos2 = pix_y * width + pix_x + 1
                    if pos1 < len(pixels):
                        pixels[pos1] = palette[idx_lo] if idx_lo < len(palette) else (0,0,0,0)
                    if pos2 < len(pixels):
                        pixels[pos2] = palette[idx_hi] if idx_hi < len(palette) else (0,0,0,0)
            tile_idx += 1
    return pixels


# ---------- PNG writer (minimal, no dependencies) ---------------------------

def _write_png(filename, pixels, width, height):
    """Write RGBA pixels to a PNG file using only stdlib (zlib)."""
    import zlib

    def _chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    # IDAT
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter byte: none
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            raw_data.extend([r, g, b, a])
    compressed = zlib.compress(bytes(raw_data), 9)

    with open(filename, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')  # signature
        f.write(_chunk(b'IHDR', ihdr_data))
        f.write(_chunk(b'IDAT', compressed))
        f.write(_chunk(b'IEND', b''))


# ---------- main extractor class --------------------------------------------

class SpriteExtractor:
    """Extracts and caches sprites from the ROM."""

    def __init__(self, rom_path, cache_dir=None):
        with open(rom_path, 'rb') as f:
            self.rom = f.read()
        if cache_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cache_dir = os.path.join(base, ".sprite_cache")
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _read_ptr(self, offset):
        ptr = struct.unpack_from('<I', self.rom, offset)[0]
        return ptr - 0x08000000 if ptr >= 0x08000000 else ptr

    def extract_creature_sprite(self, species_id):
        """Extract front sprite for a species. Returns path to PNG."""
        png_path = os.path.join(self.cache_dir, f"creature_{species_id:03d}.png")
        if os.path.exists(png_path):
            return png_path

        # read sprite data
        pic_offset = OFFSET_FRONT_PICS + species_id * 8
        sprite_ptr = self._read_ptr(pic_offset)
        sprite_data = decompress_lz77(self.rom, sprite_ptr)
        if not sprite_data:
            return None

        # read palette
        pal_offset = OFFSET_PALETTES + species_id * 8
        pal_ptr = self._read_ptr(pal_offset)
        pal_data = decompress_lz77(self.rom, pal_ptr)
        if not pal_data:
            palette = None
        else:
            palette = parse_gba_palette(pal_data)

        # decode and save
        pixels = decode_4bpp_sprite(sprite_data, SPRITE_WH, SPRITE_WH, palette)
        _write_png(png_path, pixels, SPRITE_WH, SPRITE_WH)
        return png_path

    def extract_tileset(self, max_tiles=128):
        """Extract overworld tileset tiles. Returns path to tileset PNG."""
        png_path = os.path.join(self.cache_dir, "tileset.png")
        if os.path.exists(png_path):
            return png_path

        # Tileset header
        tiles_gfx_ptr = self._read_ptr(OFFSET_TILESET_HDR + 4)
        pal_ptr = self._read_ptr(OFFSET_TILESET_HDR + 8)

        # Decompress tile graphics
        tile_gfx = decompress_lz77(self.rom, tiles_gfx_ptr)
        if not tile_gfx:
            return None

        # Decompress palette (16 colors * 16 palettes = 512 bytes)
        pal_raw = decompress_lz77(self.rom, pal_ptr)
        if not pal_raw:
            palette = [(i*17, i*17, i*17, 255) for i in range(16)]
        else:
            # use first palette (first 32 bytes)
            palette = parse_gba_palette(pal_raw[:32])

        # Render tiles in a grid (16 tiles per row)
        tiles_per_row = 16
        num_tiles = min(max_tiles, len(tile_gfx) // 32)  # 32 bytes per 8x8 tile at 4bpp
        rows = (num_tiles + tiles_per_row - 1) // tiles_per_row
        img_w = tiles_per_row * 8
        img_h = rows * 8
        pixels = [(0, 0, 0, 0)] * (img_w * img_h)

        for t in range(num_tiles):
            tx = (t % tiles_per_row) * 8
            ty = (t // tiles_per_row) * 8
            base = t * 32
            for py in range(8):
                for px in range(0, 8, 2):
                    if base >= len(tile_gfx):
                        break
                    byte = tile_gfx[base]; base += 1
                    idx_lo = byte & 0x0F
                    idx_hi = (byte >> 4) & 0x0F
                    pos1 = (ty + py) * img_w + (tx + px)
                    pos2 = (ty + py) * img_w + (tx + px + 1)
                    if pos1 < len(pixels):
                        pixels[pos1] = palette[idx_lo]
                    if pos2 < len(pixels):
                        pixels[pos2] = palette[idx_hi]

        _write_png(png_path, pixels, img_w, img_h)
        return png_path

    def extract_all_creatures(self, count=99):
        """Extract front sprites for first N species."""
        extracted = 0
        for i in range(1, count + 1):
            path = self.extract_creature_sprite(i)
            if path:
                extracted += 1
        return extracted

    def get_creature_sprite_path(self, species_id):
        """Get path to creature sprite, extracting if needed."""
        png_path = os.path.join(self.cache_dir, f"creature_{species_id:03d}.png")
        if os.path.exists(png_path):
            return png_path
        return self.extract_creature_sprite(species_id)


    def extract_player_sprites(self):
        """Extract the three playable overworld sprites from the ROM.

        FireRed stores each overworld character as a raw 4bpp tile sheet of 9
        consecutive 16x32 frames (256 bytes each):
            frame 0 = facing south/down (idle)
            frame 1 = facing north/up   (idle)
            frame 2 = facing west/left  (idle)
            frame 3/4 = walking south
            frame 5/6 = walking north
            frame 7/8 = walking west
        Facing east just horizontally flips the west frames. The results are
        written as PNGs into the shared asset folder with the same names the
        frontend's Assets loader expects, so the runtime uses the real ROM
        animations instead of the placeholder block sprites.
        """
        players = {
            # prefix : (sprite_sheet_offset, palette_offset)
            "player_red":    (0x35BB68, 0x35B968),
            "player_green":  (0x35D268, 0x35B968),
            "player_blue":   (0x38A428, 0x36D868),
        }
        out_dir = os.path.join(BASE_DIR, "assets")
        os.makedirs(out_dir, exist_ok=True)

        for prefix, (sheet_off, pal_off) in players.items():
            pal = self._palette_at(pal_off)
            frames = [self._decode_ow_frame(sheet_off, i, pal) for i in range(9)]
            # idle + walk frames per direction
            mapping = {
                f"{prefix}_down.png":           frames[0],
                f"{prefix}_up.png":             frames[1],
                f"{prefix}_left.png":           frames[2],
                f"{prefix}_walk_down_1.png":    frames[3],
                f"{prefix}_walk_down_2.png":    frames[4],
                f"{prefix}_walk_up_1.png":      frames[5],
                f"{prefix}_walk_up_2.png":      frames[6],
                f"{prefix}_walk_left_1.png":    frames[7],
                f"{prefix}_walk_left_2.png":    frames[8],
            }
            for name, pixels in mapping.items():
                _write_png(os.path.join(out_dir, name), pixels, 16, 32)

    def _palette_at(self, offset):
        """Read a 16-color GBA RGB555 palette at a ROM file offset."""
        colors = []
        for i in range(16):
            c = struct.unpack_from('<H', self.rom, offset + i * 2)[0]
            r = (c & 0x1F) << 3
            g = ((c >> 5) & 0x1F) << 3
            b = ((c >> 10) & 0x1F) << 3
            colors.append((r, g, b, 255))
        colors[0] = (0, 0, 0, 0)  # transparent
        return colors

    def _decode_ow_frame(self, sheet_off, frame, palette):
        """Decode one 16x32 overworld frame (tiled 2x4, 4bpp) to RGBA pixels."""
        base = sheet_off + frame * 256  # 256 bytes per frame
        pixels = [(0, 0, 0, 0)] * (16 * 32)
        for ty in range(4):
            for tx in range(2):
                tile = base + (ty * 2 + tx) * 32  # 32 bytes per 8x8 tile
                for py in range(8):
                    for px in range(0, 8, 2):
                        b = self.rom[tile + py * 4 + px // 2]
                        idx_lo = b & 0x0F
                        idx_hi = (b >> 4) & 0x0F
                        x = tx * 8 + px
                        y = ty * 8 + py
                        pixels[y * 16 + x] = palette[idx_lo]
                        pixels[y * 16 + x + 1] = palette[idx_hi]
        return pixels

# ---------- CLI usage -------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract sprites from GBA ROM")
    parser.add_argument("--rom", required=True, help="Path to GBA ROM file")
    parser.add_argument("--count", type=int, default=99, help="Number of creature sprites to extract")
    args = parser.parse_args()

    print(f"Extracting sprites from: {args.rom}")
    extractor = SpriteExtractor(args.rom)

    # Extract creature sprites
    n = extractor.extract_all_creatures(args.count)
    print(f"Extracted {n} creature sprites")

    # Extract tileset
    ts = extractor.extract_tileset()
    if ts:
        print(f"Tileset saved to: {ts}")

    print(f"All sprites cached in: {extractor.cache_dir}")
